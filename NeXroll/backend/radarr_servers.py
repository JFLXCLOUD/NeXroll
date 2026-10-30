"""Every Radarr NeX-Up reads from, read together as one library.

The main Radarr lives in the settings row (nexup_radarr_url/api_key) as it
always has. More can be added (models.RadarrServer), such as a 4K instance
holding movies the main one doesn't. They are only used while the main one
is connected.

* A movie is one entry however many servers hold it, matched by TMDB id. Its
  record comes from the first server that has it (the main one first), and it
  counts as downloaded (hasFile) and monitored when any copy is.
* Each movie's ``id`` is a NeXroll-wide key, stored as radarr_movie_id on
  trailer rows and in Library Trailers settings. The main Radarr's movies keep
  their Radarr id, so a single-Radarr install sees no change; another
  server's movie is ``server_id * KEY_STRIDE + radarr_id``. Tag ids work the
  same way, with tags of the same name merged.
* ``aliases`` maps every copy's key to the key its movie uses now, and
  ``rehome`` moves stored rows along when a movie gains or loses a copy.
* A server that can't be read is listed in ``failed``. Its movies are simply
  missing, so callers must not take that to mean they left the library.
"""
import asyncio
import logging
from typing import Optional

from backend import models

logger = logging.getLogger(__name__)

MAIN = 0
KEY_STRIDE = 1_000_000_000
MAIN_NAME = "Radarr"
MODEL = models.RadarrServer


def movie_key(server_id, radarr_id) -> int:
    radarr_id = int(radarr_id)
    return radarr_id if not server_id else int(server_id) * KEY_STRIDE + radarr_id


def split_key(key) -> tuple:
    """(server id, Radarr's own id) for a movie key."""
    key = int(key)
    return (key // KEY_STRIDE, key % KEY_STRIDE) if key >= KEY_STRIDE else (MAIN, key)


def normalize_url(url: Optional[str]) -> str:
    url = str(url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def server_name(row) -> str:
    return (row.name or "").strip() or f"{MAIN_NAME} {row.id}"


def servers(db, setting=None) -> list:
    """[{"id", "name", "url", "api_key"}], the main Radarr first, then the
    others in the order they were added. Empty without a main Radarr."""
    setting = setting if setting is not None else db.query(models.Setting).first()
    url = getattr(setting, "nexup_radarr_url", None) if setting else None
    key = getattr(setting, "nexup_radarr_api_key", None) if setting else None
    if not (url and key):
        return []
    found = [{"id": MAIN, "name": MAIN_NAME, "url": url, "api_key": key}]
    for row in db.query(models.RadarrServer).order_by(models.RadarrServer.id).all():
        found.append({"id": row.id, "name": server_name(row), "url": row.url, "api_key": row.api_key})
    return found


def find_server(db, server_id, setting=None) -> Optional[dict]:
    return next((s for s in servers(db, setting) if s["id"] == server_id), None)


def connector(server):
    from backend.radarr_connector import RadarrConnector
    return RadarrConnector(server["url"], server["api_key"])


class RadarrLibrary:
    def __init__(self, configured):
        self.servers = configured
        self.movies = []
        self.aliases = {}
        self.failed = []
        self.tags = []

    @property
    def connected(self) -> bool:
        return bool(self.servers)

    @property
    def read_any(self) -> bool:
        return len(self.failed) < len(self.servers)

    def failed_names(self) -> list:
        return [f["name"] for f in self.failed]

    def canonical(self, key):
        return self.aliases.get(key, key)

    def parser(self):
        """A connector for the movie-list parsers, which make no requests."""
        return connector(self.servers[0])


async def fetch_library(db, setting=None, with_tags: bool = False) -> RadarrLibrary:
    """Every configured Radarr's movies, merged. ``with_tags`` also reads the
    tags (Library Trailers filters on them); without it the other servers'
    movies carry no tags, since their ids mean nothing next to the main one's."""
    configured = servers(db, setting)
    lib = RadarrLibrary(configured)

    async def read(server):
        conn = connector(server)
        try:
            movies = await conn.fetch_all_movies()
        except Exception as exc:
            logger.warning("Could not read movies from %s: %s", server["name"], exc)
            return None, None, str(exc) or exc.__class__.__name__
        tags = None
        if with_tags:
            try:
                tags = await conn.fetch_tags()
            except Exception as exc:
                logger.warning("Could not read tags from %s: %s", server["name"], exc)
        return movies, tags, None

    results = await asyncio.gather(*(read(s) for s in configured))
    for server, (_movies, _tags, error) in zip(configured, results):
        if error is not None:
            lib.failed.append({"id": server["id"], "name": server["name"], "error": error})
    _merge(lib, [(s, m, t) for s, (m, t, e) in zip(configured, results) if e is None])
    return lib


def _merge(lib: RadarrLibrary, readings) -> None:
    tag_map, labels = {}, {}
    for server, _movies, tags in readings:
        for tag in tags or []:
            label = str(tag.get("label") or "")
            merged = labels.get(label.lower())
            if merged is None:
                merged = labels[label.lower()] = movie_key(server["id"], tag["id"])
                lib.tags.append({"id": merged, "label": label})
            tag_map[(server["id"], tag["id"])] = merged

    def tag_ids(server_id, ids):
        out = []
        for tag_id in ids or []:
            merged = tag_map.get((server_id, tag_id), tag_id if server_id == MAIN else None)
            if merged is not None and merged not in out:
                out.append(merged)
        return out

    by_tmdb = {}
    for server, movies, _tags in readings:
        for raw in movies:
            if not isinstance(raw, dict) or raw.get("id") is None:
                continue
            key = movie_key(server["id"], raw["id"])
            copy = {"key": key, "server": server["name"], "path": raw.get("path"),
                    "hasFile": bool(raw.get("hasFile"))}
            tmdb = raw.get("tmdbId") or None
            entry = by_tmdb.get(tmdb) if tmdb else None
            if entry is None:
                entry = dict(raw)
                entry["id"] = key
                entry["tags"] = tag_ids(server["id"], raw.get("tags"))
                entry["nexrollServer"] = server["name"]
                entry["nexrollCopies"] = [copy]
                lib.movies.append(entry)
                if tmdb:
                    by_tmdb[tmdb] = entry
            else:
                entry["nexrollCopies"].append(copy)
                if raw.get("hasFile") and not entry.get("hasFile"):
                    entry["hasFile"] = True
                    entry["movieFile"] = entry.get("movieFile") or raw.get("movieFile")
                entry["monitored"] = bool(entry.get("monitored") or raw.get("monitored"))
                entry["youTubeTrailerId"] = entry.get("youTubeTrailerId") or raw.get("youTubeTrailerId")
                if raw.get("added") and (not entry.get("added") or str(raw["added"]) < str(entry["added"])):
                    entry["added"] = raw["added"]
                entry["tags"] = entry["tags"] + [t for t in tag_ids(server["id"], raw.get("tags")) if t not in entry["tags"]]
            lib.aliases[key] = entry["id"]


def rehome(db, model, lib: RadarrLibrary) -> int:
    """Point stored rows (radarr_movie_id) at the key their movie uses now:
    by TMDB id first, else by the copy they were keyed on. Rows not linked
    to Radarr (0) and movies no server reported stay as they are. The caller
    commits."""
    by_tmdb = {m["tmdbId"]: m["id"] for m in lib.movies if m.get("tmdbId")}
    changed = 0
    for row in db.query(model).filter(model.radarr_movie_id > 0).all():
        home = by_tmdb.get(row.tmdb_id) if row.tmdb_id else None
        if home is None:
            home = lib.aliases.get(row.radarr_movie_id)
        if home is not None and home != row.radarr_movie_id:
            row.radarr_movie_id = home
            changed += 1
    return changed


async def upcoming_movies(db, setting, days_ahead: int = 90, include_unmonitored: bool = False,
                          release_date_preference: str = "digital_first") -> tuple:
    """(upcoming movies incl. "Available Now!" ones, failed server names),
    as RadarrConnector.get_upcoming_movies but across every server."""
    lib = await fetch_library(db, setting)
    if not lib.movies:
        return [], lib.failed_names()
    movies = lib.parser().upcoming_from_raw(lib.movies, days_ahead, include_unmonitored, release_date_preference)
    return movies, lib.failed_names()


async def get_movie(db, key, setting=None) -> Optional[dict]:
    """One movie by key, straight from the Radarr that holds it; None when
    that server is gone or doesn't have it."""
    server_id, radarr_id = split_key(key)
    server = find_server(db, server_id, setting)
    if server is None:
        return None
    movie = await connector(server).get_movie_by_id(radarr_id)
    if movie:
        movie["nexrollServer"] = server["name"]
    return movie


def movies_by_key_sync(db, setting=None, timeout: int = 25) -> dict:
    """{key: raw movie} from every server, for synchronous callers. A server
    that fails is logged and left out."""
    import requests
    found = {}
    for server in servers(db, setting):
        try:
            response = requests.get(f"{str(server['url']).rstrip('/')}/api/v3/movie",
                                    headers={"X-Api-Key": server["api_key"]}, timeout=timeout)
            response.raise_for_status()
            for movie in response.json():
                if movie.get("id") is not None:
                    found[movie_key(server["id"], movie["id"])] = movie
        except Exception as exc:
            logger.warning("Could not read movies from %s: %s", server["name"], exc)
    return found


def sensitive_values(db) -> set:
    """The other servers' URLs and keys, for log redaction."""
    vals = set()
    for row in db.query(models.RadarrServer).all():
        for value in (row.url, row.api_key):
            if value and str(value).strip():
                vals.add(str(value).strip())
                vals.add(str(value).strip().rstrip("/"))
    return vals
