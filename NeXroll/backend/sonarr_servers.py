"""Every Sonarr NeX-Up reads from, read together: the Sonarr side of
radarr_servers.py, which explains the keys and the failure rule.

* A show is one entry however many servers hold it, matched by TVDB id. Its
  record comes from the first server that has it (the main one first). Each
  season takes its episode counts from the copy with the most, so a season
  counts as downloaded once any server has episodes of it.
* Show keys work like movie keys: the main Sonarr's shows keep their series
  id, another server's show is ``server_id * KEY_STRIDE + series_id``. They
  are stored as sonarr_series_id on TV trailer rows.
* Premieres (the Coming Soon source) come from each server's calendar, one
  per show and season, keyed like the shows. With one Sonarr the series list
  isn't needed for that and isn't read.
"""
import asyncio
import logging
from typing import Optional

from backend import models
from backend.radarr_servers import KEY_STRIDE, MAIN, normalize_url, split_key  # noqa: F401 (re-exported)
from backend.radarr_servers import movie_key as series_key

logger = logging.getLogger(__name__)

MAIN_NAME = "Sonarr"
MODEL = models.SonarrServer


def server_name(row) -> str:
    return (row.name or "").strip() or f"{MAIN_NAME} {row.id}"


def servers(db, setting=None) -> list:
    """[{"id", "name", "url", "api_key"}], the main Sonarr first, then the
    others in the order they were added. Empty without a main Sonarr."""
    setting = setting if setting is not None else db.query(models.Setting).first()
    url = getattr(setting, "nexup_sonarr_url", None) if setting else None
    key = getattr(setting, "nexup_sonarr_api_key", None) if setting else None
    if not (url and key):
        return []
    found = [{"id": MAIN, "name": MAIN_NAME, "url": url, "api_key": key}]
    for row in db.query(models.SonarrServer).order_by(models.SonarrServer.id).all():
        found.append({"id": row.id, "name": server_name(row), "url": row.url, "api_key": row.api_key})
    return found


def connector(server):
    from backend.sonarr_connector import SonarrConnector
    return SonarrConnector(server["url"], server["api_key"])


class SonarrLibrary:
    def __init__(self, configured):
        self.servers = configured
        self.series = []
        self.by_key = {}
        self.aliases = {}
        self.failed = []
        self.calendars = []  # [(server, episodes)]

    @property
    def connected(self) -> bool:
        return bool(self.servers)

    def failed_names(self) -> list:
        return [f["name"] for f in self.failed]

    def canonical(self, key):
        return self.aliases.get(key, key)

    def find(self, key) -> Optional[dict]:
        return self.by_key.get(self.canonical(key))

    def parser(self):
        """A connector for the list parsers, which make no requests."""
        return connector(self.servers[0])

    def premieres(self, include_unmonitored: bool = False, recent_days: int = 0) -> list:
        """SonarrConnector.get_upcoming_premieres across every calendar read:
        one entry per show and season, available if any server has it."""
        found = {}
        for server, episodes in self.calendars:
            for premiere in connector(server).premieres_from_calendar(episodes, include_unmonitored, recent_days):
                if premiere.get("sonarr_id") is None:
                    continue
                premiere["sonarr_id"] = self.canonical(series_key(server["id"], premiere["sonarr_id"]))
                premiere["sonarr_server"] = server["name"]
                slot = (premiere["sonarr_id"], premiere["season_number"])
                if slot in found:
                    found[slot]["has_file"] = bool(found[slot]["has_file"] or premiere["has_file"])
                else:
                    found[slot] = premiere
        return sorted(found.values(), key=lambda p: p["release_date"] or "9999-99-99")


async def fetch_library(db, setting=None, with_series: bool = True, calendar: Optional[tuple] = None) -> SonarrLibrary:
    """Every configured Sonarr's series (merged) and, with ``calendar`` as a
    (start, end) pair, their calendars. Without ``with_series`` the series are
    still read when there is more than one Sonarr: premieres need them to key
    a show the same way on every server."""
    configured = servers(db, setting)
    lib = SonarrLibrary(configured)
    read_series = with_series or len(configured) > 1

    async def read(server):
        conn = connector(server)
        try:
            series = await conn.fetch_all_series() if read_series else None
            episodes = await conn.fetch_calendar(*calendar) if calendar else None
        except Exception as exc:
            logger.warning("Could not read %s: %s", server["name"], exc)
            return None, None, str(exc) or exc.__class__.__name__
        return series, episodes, None

    results = await asyncio.gather(*(read(s) for s in configured))
    readings = []
    for server, (series, episodes, error) in zip(configured, results):
        if error is not None:
            lib.failed.append({"id": server["id"], "name": server["name"], "error": error})
            continue
        if series is not None:
            readings.append((server, series))
        if episodes is not None:
            lib.calendars.append((server, episodes))
    _merge(lib, readings)
    return lib


def _merge(lib: SonarrLibrary, readings) -> None:
    by_tvdb = {}
    for server, series_list in readings:
        for raw in series_list:
            if not isinstance(raw, dict) or raw.get("id") is None:
                continue
            key = series_key(server["id"], raw["id"])
            copy = {"key": key, "server": server["name"], "path": raw.get("path")}
            tvdb = raw.get("tvdbId") or None
            entry = by_tvdb.get(tvdb) if tvdb else None
            if entry is None:
                entry = dict(raw)
                entry["id"] = key
                entry["statistics"] = dict(raw.get("statistics") or {})
                entry["seasons"] = [dict(s, statistics=dict(s.get("statistics") or {})) for s in raw.get("seasons") or []]
                entry["nexrollServer"] = server["name"]
                entry["nexrollCopies"] = [copy]
                lib.series.append(entry)
                lib.by_key[key] = entry
                if tvdb:
                    by_tvdb[tvdb] = entry
            else:
                entry["nexrollCopies"].append(copy)
                entry["monitored"] = bool(entry.get("monitored") or raw.get("monitored"))
                entry["imdbId"] = entry.get("imdbId") or raw.get("imdbId")
                _take_counts(entry["statistics"], raw.get("statistics") or {})
                seasons = {s.get("seasonNumber"): s for s in entry["seasons"]}
                for season in raw.get("seasons") or []:
                    mine = seasons.get(season.get("seasonNumber"))
                    if mine is None:
                        entry["seasons"].append(dict(season, statistics=dict(season.get("statistics") or {})))
                        continue
                    mine["monitored"] = bool(mine.get("monitored") or season.get("monitored"))
                    _take_counts(mine["statistics"], season.get("statistics") or {})
            lib.aliases[key] = entry["id"]


def _take_counts(mine: dict, theirs: dict) -> None:
    for name in ("episodeFileCount", "episodeCount", "totalEpisodeCount"):
        if (theirs.get(name) or 0) > (mine.get(name) or 0):
            mine[name] = theirs[name]


def rehome(db, lib: SonarrLibrary) -> int:
    """Point TV trailer rows (sonarr_series_id) at the key their show uses
    now: by TVDB id first, else by the copy they were keyed on. Needs the
    series list; the caller commits."""
    by_tvdb = {s["tvdbId"]: s["id"] for s in lib.series if s.get("tvdbId")}
    changed = 0
    model = models.ComingSoonTVTrailer
    for row in db.query(model).filter(model.sonarr_series_id > 0).all():
        home = by_tvdb.get(row.tvdb_id) if row.tvdb_id else None
        if home is None:
            home = lib.aliases.get(row.sonarr_series_id)
        if home is not None and home != row.sonarr_series_id:
            row.sonarr_series_id = home
            changed += 1
    return changed


async def upcoming_premieres(db, setting, days_ahead: int = 90, include_unmonitored: bool = False,
                             recent_days: int = 0) -> tuple:
    """(premieres from every Sonarr, failed server names), as
    SonarrConnector.get_upcoming_premieres."""
    from backend.sonarr_connector import SonarrConnector
    lib = await fetch_library(db, setting, with_series=False,
                              calendar=SonarrConnector.calendar_window(days_ahead, recent_days))
    return lib.premieres(include_unmonitored, recent_days), lib.failed_names()


def series_by_key_sync(db, setting=None, timeout: int = 25) -> dict:
    """{key: raw series} from every server, for synchronous callers. A
    server that fails is logged and left out."""
    import requests
    found = {}
    for server in servers(db, setting):
        try:
            response = requests.get(f"{str(server['url']).rstrip('/')}/api/v3/series",
                                    headers={"X-Api-Key": server["api_key"]}, timeout=timeout)
            response.raise_for_status()
            for series in response.json():
                if series.get("id") is not None:
                    found[series_key(server["id"], series["id"])] = series
        except Exception as exc:
            logger.warning("Could not read series from %s: %s", server["name"], exc)
    return found


def sensitive_values(db) -> set:
    """The other servers' URLs and keys, for log redaction."""
    vals = set()
    for row in db.query(models.SonarrServer).all():
        for value in (row.url, row.api_key):
            if value and str(value).strip():
                vals.add(str(value).strip())
                vals.add(str(value).strip().rstrip("/"))
    return vals
