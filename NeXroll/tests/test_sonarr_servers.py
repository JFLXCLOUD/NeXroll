"""NeX-Up reads more than one Sonarr, the Sonarr side of test_radarr_servers.

A show in both is one entry keyed as the main Sonarr keys it, a show only on
another server gets a key of its own, a season counts as downloaded once any
copy has episodes, and calendar premieres use the same keys as the shows even
when only the other server's calendar lists the premiere.
"""

import asyncio
import datetime
import os
import tempfile
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models, sonarr_servers
from backend import scheduler as scheduler_module
from backend.sonarr_connector import SonarrConnector
from backend.timeutil import utcnow
from tests.test_radarr_servers import ROUTES, route_client

TODAY = datetime.datetime.now().date()
HD, UHD = "http://hd-sonarr.test", "http://uhd-sonarr.test"
UHD_KEY = sonarr_servers.KEY_STRIDE

# url -> {"series": [...], "calendar": [...], "error": str, "instance": str}
SERVERS = {}
SERIES_READS = []


class FakeSonarr(SonarrConnector):
    """The real parsers, with Sonarr's answers taken from SERVERS."""

    def _data(self):
        data = SERVERS.get(self.base_url)
        if data is None or data.get("error"):
            raise RuntimeError((data or {}).get("error") or "Connection refused")
        return data

    async def fetch_all_series(self):
        SERIES_READS.append(self.base_url)
        return [dict(s) for s in self._data()["series"]]

    async def fetch_calendar(self, start_date=None, end_date=None):
        return [e for e in self._data().get("calendar", [])
                if start_date.date() <= datetime.date.fromisoformat(e["airDate"]) <= end_date.date()]

    async def test_connection(self):
        try:
            data = self._data()
        except RuntimeError as exc:
            return {"success": False, "message": str(exc)}
        return {"success": True, "version": "4.0.15", "appName": "Sonarr", "instanceName": data.get("instance", "Sonarr")}


def series(series_id, tvdb, title, seasons, monitored=True):
    """seasons: {number: (episodes downloaded, episodes in total)}"""
    return {"id": series_id, "tvdbId": tvdb, "imdbId": f"tt{tvdb}", "title": title, "year": TODAY.year,
            "monitored": monitored, "network": "HBO", "genres": ["Drama"], "images": [],
            "statistics": {"episodeFileCount": sum(f for f, _ in seasons.values()),
                           "totalEpisodeCount": sum(t for _, t in seasons.values())},
            "seasons": [{"seasonNumber": n, "monitored": True,
                         "statistics": {"episodeFileCount": f, "totalEpisodeCount": t}} for n, (f, t) in seasons.items()]}


def premiere(series_id, tvdb, title, season, offset, has_file=False, monitored=True):
    aired = datetime.datetime.combine(TODAY + datetime.timedelta(days=offset), datetime.time(12))
    return {"seriesId": series_id, "seasonNumber": season, "episodeNumber": 1, "title": "Episode 1",
            "airDate": aired.date().isoformat(), "airDateUtc": aired.isoformat() + "Z", "hasFile": has_file,
            "series": {"id": series_id, "tvdbId": tvdb, "title": title, "monitored": monitored, "images": []}}


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = tempfile.TemporaryDirectory()
    SERVERS.clear()
    SERIES_READS.clear()
    with factory() as session:
        session.add(models.Setting(nexup_sonarr_url=HD, nexup_sonarr_api_key="k1",
                                   nexup_storage_path=storage.name, nexup_download_delay=0))
        session.add(models.SonarrServer(name="Sonarr 4K", url=UHD, api_key="k2"))
        session.commit()
        with patch("backend.sonarr_connector.SonarrConnector", FakeSonarr):
            yield session
    engine.dispose()
    storage.cleanup()


def read(session, **kwargs):
    return asyncio.run(sonarr_servers.fetch_library(session, **kwargs))


def premieres(session, recent_days=0, include_unmonitored=False):
    shows, failed = asyncio.run(sonarr_servers.upcoming_premieres(
        session, session.query(models.Setting).first(), 90, include_unmonitored=include_unmonitored, recent_days=recent_days))
    return {(s["title"], s["season_number"]): s for s in shows}, failed


def test_a_show_on_both_servers_is_one_entry_with_the_best_season_counts(db):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {1: (10, 10), 2: (0, 8)})]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {2: (3, 8)}), series(9, 200, "Severance", {1: (0, 9)})]}
    lib = read(db)
    by_title = {s["title"]: s for s in lib.series}
    assert len(lib.series) == 2
    expanse = by_title["The Expanse"]
    assert expanse["id"] == 4 and expanse["nexrollServer"] == "Sonarr"
    assert {s["seasonNumber"]: s["statistics"]["episodeFileCount"] for s in expanse["seasons"]} == {1: 10, 2: 3}
    assert by_title["Severance"]["id"] == UHD_KEY + 9
    assert lib.find(UHD_KEY + 7) is expanse, "any copy's key finds the show"
    assert lib.aliases == {4: 4, UHD_KEY + 7: 4, UHD_KEY + 9: UHD_KEY + 9}


def test_premieres_from_both_calendars_appear_once_with_the_shows_keys(db):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {1: (10, 10), 2: (0, 8)}),
                              series(5, 300, "Aired Recently", {3: (0, 8)})],
                   "calendar": [premiere(4, 100, "The Expanse", 2, 10), premiere(5, 300, "Aired Recently", 3, -2)]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {2: (0, 8)}), series(9, 200, "Severance", {2: (0, 9)}),
                               series(11, 300, "Aired Recently", {3: (1, 8)})],
                    "calendar": [premiere(7, 100, "The Expanse", 2, 10), premiere(9, 200, "Severance", 2, 5),
                                 premiere(11, 300, "Aired Recently", 3, -2, has_file=True)]}
    shows, failed = premieres(db, recent_days=7)
    assert failed == []
    assert sorted(shows) == [("Aired Recently", 3), ("Severance", 2), ("The Expanse", 2)]
    assert shows[("The Expanse", 2)]["sonarr_id"] == 4
    assert shows[("Severance", 2)]["sonarr_id"] == UHD_KEY + 9
    assert shows[("Severance", 2)]["sonarr_server"] == "Sonarr 4K"
    recent = shows[("Aired Recently", 3)]
    assert (recent["sonarr_id"], recent["has_file"]) == (5, True), "available once either Sonarr has it"


def test_a_premiere_only_the_4k_calendar_lists_still_gets_the_main_key(db):
    # The main Sonarr has the show unmonitored, so its calendar entry is left out.
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {3: (0, 8)}, monitored=False)],
                   "calendar": [premiere(4, 100, "The Expanse", 3, 10, monitored=False)]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {3: (0, 8)})],
                    "calendar": [premiere(7, 100, "The Expanse", 3, 10)]}
    shows, _ = premieres(db)
    assert [(k, s["sonarr_id"]) for k, s in shows.items()] == [(("The Expanse", 3), 4)]


def test_one_sonarr_reads_only_its_calendar(db):
    db.query(models.SonarrServer).delete()
    db.commit()
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {2: (0, 8)})],
                   "calendar": [premiere(4, 100, "The Expanse", 2, 10)]}
    shows, _ = premieres(db)
    assert shows[("The Expanse", 2)]["sonarr_id"] == 4
    assert SERIES_READS == [], "the series list isn't needed for keys with one Sonarr"


def test_an_unreachable_sonarr_is_reported_and_the_rest_still_read(db):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {2: (0, 8)})],
                   "calendar": [premiere(4, 100, "The Expanse", 2, 10)]}
    SERVERS[UHD] = {"error": "timed out"}
    shows, failed = premieres(db)
    assert list(shows) == [("The Expanse", 2)]
    assert failed == ["Sonarr 4K"]


def test_tv_rows_follow_a_show_that_gained_a_copy(db):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {2: (0, 8)})]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {2: (0, 8)}), series(9, 200, "Severance", {2: (0, 9)})]}
    db.add_all([
        models.ComingSoonTVTrailer(sonarr_series_id=UHD_KEY + 7, tvdb_id=100, season_number=2, title="The Expanse"),
        models.ComingSoonTVTrailer(sonarr_series_id=UHD_KEY + 9, tvdb_id=200, season_number=2, title="Severance"),
        models.ComingSoonTVTrailer(sonarr_series_id=0, tvdb_id=100, season_number=1, title="Not linked"),
    ])
    db.commit()
    assert sonarr_servers.rehome(db, read(db)) == 1
    keys = {r.title: r.sonarr_series_id for r in db.query(models.ComingSoonTVTrailer).all()}
    assert keys == {"The Expanse": 4, "Severance": UHD_KEY + 9, "Not linked": 0}


class NoDownloads:
    def __init__(self, *args, **kwargs):
        pass

    async def download_trailer(self, *args, **kwargs):
        raise AssertionError("the TV auto-sync downloads nothing")


def test_tv_auto_sync_expires_a_season_the_other_sonarr_has(db, tmp_path):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {2: (0, 8)}), series(5, 300, "Kept", {1: (0, 8)})]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {2: (2, 8)})]}
    files = []
    for title in ("The Expanse", "Kept"):
        path = tmp_path / f"{title}.mp4"
        path.write_bytes(b"x")
        files.append(path)
    db.add_all([
        models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=2, title="The Expanse",
                                   status="downloaded", local_path=str(files[0])),
        models.ComingSoonTVTrailer(sonarr_series_id=5, tvdb_id=300, season_number=1, title="Kept",
                                   status="downloaded", local_path=str(files[1])),
    ])
    db.commit()
    sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)
    with patch("backend.radarr_connector.TrailerDownloader", NoDownloads):
        asyncio.run(sched._sync_sonarr_trailers(db, db.query(models.Setting).first()))
    assert [r.title for r in db.query(models.ComingSoonTVTrailer).all()] == ["Kept"]
    assert not files[0].exists() and files[1].exists()


SONARR_ROUTES = (ROUTES - {"get_upcoming_movies"}) | {"get_upcoming_shows"}


def test_sonarr_servers_share_the_endpoints(db):
    SERVERS["http://anime.test:8990"] = {"series": [], "instance": "Sonarr-Anime"}
    with route_client(db, SONARR_ROUTES) as client:
        assert client.get("/nexup/lidarr/servers").status_code == 404
        assert client.post("/nexup/sonarr/servers", json={"url": HD, "api_key": "x"}).json()["detail"] == "That Sonarr is already connected."
        added = client.post("/nexup/sonarr/servers", json={"url": "anime.test:8990", "api_key": "k3"}).json()
        assert added["success"] is True and added["server"]["name"] == "Sonarr-Anime"
        assert [s["name"] for s in client.get("/nexup/sonarr/servers").json()["servers"]] == ["Sonarr 4K", "Sonarr-Anime"]
        assert client.get("/nexup/radarr/servers").json() == {"servers": []}
        assert client.delete(f"/nexup/sonarr/servers/{added['server']['id']}").json()["success"] is True


def test_upcoming_shows_page_lists_both_sonarrs(db):
    SERVERS[HD] = {"series": [series(4, 100, "The Expanse", {2: (0, 8)})],
                   "calendar": [premiere(4, 100, "The Expanse", 2, 10)]}
    SERVERS[UHD] = {"series": [series(7, 100, "The Expanse", {2: (0, 8)}), series(9, 200, "Severance", {2: (0, 9)})],
                    "calendar": [premiere(7, 100, "The Expanse", 2, 10), premiere(9, 200, "Severance", 2, 5)]}
    db.add(models.ComingSoonTVTrailer(sonarr_series_id=UHD_KEY + 7, tvdb_id=100, season_number=2, title="The Expanse",
                                      status="downloaded", downloaded_at=utcnow()))
    db.commit()
    with route_client(db, SONARR_ROUTES) as client:
        body = client.get("/nexup/sonarr/upcoming").json()
    shows = {s["title"]: s for s in body["shows"]}
    assert set(shows) == {"The Expanse", "Severance"}
    assert shows["The Expanse"]["sonarr_id"] == 4 and shows["The Expanse"]["downloaded"] is True
    assert shows["Severance"]["sonarr_id"] == UHD_KEY + 9
    assert body["failed_servers"] == []
