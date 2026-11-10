"""NeX-Up reads more than one Radarr (user request: a 1080p and a 4K Radarr
holding different movies, so a 4K-only Marvel movie never reached Coming Soon).

The servers are read as one library: a movie in both is one entry keyed as
the main Radarr keys it, a movie only on another server gets a key of its own,
it counts as downloaded when any copy is, and stored rows follow a movie that
gains or loses a copy. A server that can't be read must never look like its
movies left the library.
"""

import asyncio
import ast
import datetime
import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend import library_trailers, models, radarr_servers
from backend import scheduler as scheduler_module
from backend.radarr_connector import RadarrConnector
from backend.timeutil import utcnow

TODAY = datetime.datetime.now().date()
HD, UHD = "http://hd.test", "http://uhd.test"
UHD_KEY = radarr_servers.KEY_STRIDE  # server 1's movie keys start here

# url -> {"movies": [...], "tags": [...], "error": str, "instance": str}
SERVERS = {}


class FakeRadarr(RadarrConnector):
    """The real parsers, with Radarr's answers taken from SERVERS."""

    def _data(self):
        data = SERVERS.get(self.base_url)
        if data is None or data.get("error"):
            raise RuntimeError((data or {}).get("error") or "Connection refused")
        return data

    async def fetch_all_movies(self):
        return [dict(m) for m in self._data()["movies"]]

    async def fetch_tags(self):
        return list(self._data().get("tags", []))

    async def get_movie_by_id(self, radarr_id):
        return next((dict(m) for m in self._data()["movies"] if m["id"] == radarr_id), None)

    async def test_connection(self):
        try:
            data = self._data()
        except RuntimeError as exc:
            return {"success": False, "message": str(exc)}
        return {"success": True, "version": "6.0.4", "appName": "Radarr", "instanceName": data.get("instance", "Radarr")}


def movie(radarr_id, tmdb, title, days=30, has_file=False, trailer="yt", **extra):
    release = (TODAY + datetime.timedelta(days=days)).isoformat()
    record = {"id": radarr_id, "tmdbId": tmdb, "title": title, "year": TODAY.year, "status": "announced",
              "monitored": True, "hasFile": has_file, "digitalRelease": f"{release}T00:00:00Z",
              "youTubeTrailerId": f"{trailer}{radarr_id}" if trailer else None,
              "path": f"/movies/{title}", "images": [], "genres": ["Action"]}
    record.update(extra)
    return record


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    storage = tempfile.TemporaryDirectory()
    SERVERS.clear()
    library_trailers._movie_cache.update(key=None, at=0.0, library=None)
    with factory() as session:
        session.add(models.Setting(nexup_radarr_url=HD, nexup_radarr_api_key="k1",
                                   nexup_storage_path=storage.name, nexup_download_delay=0))
        session.add(models.RadarrServer(name="Radarr 4K", url=UHD, api_key="k2"))
        session.commit()
        with patch("backend.radarr_connector.RadarrConnector", FakeRadarr):
            yield session
    engine.dispose()
    storage.cleanup()


def read(session, **kwargs):
    return asyncio.run(radarr_servers.fetch_library(session, **kwargs))


def test_keys_leave_the_main_radarrs_ids_alone():
    assert radarr_servers.movie_key(0, 41) == 41
    assert radarr_servers.movie_key(2, 41) == 2 * radarr_servers.KEY_STRIDE + 41
    assert radarr_servers.split_key(41) == (0, 41)
    assert radarr_servers.split_key(2 * radarr_servers.KEY_STRIDE + 41) == (2, 41)


def test_other_servers_are_only_read_with_a_main_radarr(db):
    assert [s["name"] for s in radarr_servers.servers(db)] == ["Radarr", "Radarr 4K"]
    setting = db.query(models.Setting).first()
    setting.nexup_radarr_url = None
    db.commit()
    assert radarr_servers.servers(db) == []


def test_a_movie_on_both_servers_is_one_entry(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Thunderbolts"), movie(6, 300, "HD Only")]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Thunderbolts", has_file=True, added="2020-01-01T00:00:00Z"),
                               movie(12, 200, "Avengers Doomsday")]}
    lib = read(db)
    by_title = {m["title"]: m for m in lib.movies}
    assert len(lib.movies) == 3
    both = by_title["Thunderbolts"]
    assert both["id"] == 5 and both["nexrollServer"] == "Radarr"
    assert both["hasFile"] is True, "a file on either server counts"
    assert both["added"] == "2020-01-01T00:00:00Z"
    assert [c["key"] for c in both["nexrollCopies"]] == [5, UHD_KEY + 9]
    assert by_title["Avengers Doomsday"]["id"] == UHD_KEY + 12
    assert by_title["Avengers Doomsday"]["nexrollServer"] == "Radarr 4K"
    assert lib.aliases == {5: 5, 6: 6, UHD_KEY + 9: 5, UHD_KEY + 12: UHD_KEY + 12}


def test_upcoming_list_includes_movies_only_on_the_4k_server(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Thunderbolts")]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Thunderbolts"), movie(12, 200, "Avengers Doomsday")]}
    movies, failed = asyncio.run(radarr_servers.upcoming_movies(db, db.query(models.Setting).first(), 90))
    assert failed == []
    assert sorted((m["title"], m["radarr_id"]) for m in movies) == [("Avengers Doomsday", UHD_KEY + 12), ("Thunderbolts", 5)]
    assert next(m for m in movies if m["title"] == "Avengers Doomsday")["radarr_server"] == "Radarr 4K"


def test_tags_merge_by_name_and_keep_the_main_ids(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "A", tags=[1])], "tags": [{"id": 1, "label": "marvel"}]}
    SERVERS[UHD] = {"movies": [movie(9, 200, "B", tags=[1, 3])],
                    "tags": [{"id": 1, "label": "anime"}, {"id": 3, "label": "Marvel"}]}
    lib = read(db, with_tags=True)
    assert lib.tags == [{"id": 1, "label": "marvel"}, {"id": UHD_KEY + 1, "label": "anime"}]
    assert {m["title"]: m["tags"] for m in lib.movies} == {"A": [1], "B": [UHD_KEY + 1, 1]}
    # Without the tag lists another server's tag ids can't be translated.
    assert {m["title"]: m["tags"] for m in read(db).movies} == {"A": [1], "B": []}


def test_an_unreachable_server_is_reported_and_the_rest_still_read(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "A")]}
    SERVERS[UHD] = {"error": "timed out"}
    lib = read(db)
    assert [m["title"] for m in lib.movies] == ["A"]
    assert lib.failed_names() == ["Radarr 4K"]
    assert lib.read_any


def test_rows_follow_a_movie_that_gained_a_copy(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Thunderbolts")]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Thunderbolts"), movie(12, 200, "Doomsday")]}
    db.add_all([
        models.ComingSoonTrailer(radarr_movie_id=UHD_KEY + 9, tmdb_id=100, title="Thunderbolts"),
        models.ComingSoonTrailer(radarr_movie_id=UHD_KEY + 9, tmdb_id=None, title="Legacy without tmdb"),
        models.ComingSoonTrailer(radarr_movie_id=0, tmdb_id=100, title="Manual, not linked"),
        models.ComingSoonTrailer(radarr_movie_id=UHD_KEY + 12, tmdb_id=200, title="Doomsday"),
    ])
    db.commit()
    assert radarr_servers.rehome(db, models.ComingSoonTrailer, read(db)) == 2
    keys = {r.title: r.radarr_movie_id for r in db.query(models.ComingSoonTrailer).all()}
    assert keys == {"Thunderbolts": 5, "Legacy without tmdb": 5, "Manual, not linked": 0, "Doomsday": UHD_KEY + 12}


def test_get_movie_asks_the_server_that_holds_it(db):
    SERVERS[HD] = {"movies": [movie(12, 1, "HD twelve")]}
    SERVERS[UHD] = {"movies": [movie(12, 2, "4K twelve")]}
    assert asyncio.run(radarr_servers.get_movie(db, 12))["title"] == "HD twelve"
    assert asyncio.run(radarr_servers.get_movie(db, UHD_KEY + 12))["title"] == "4K twelve"
    assert asyncio.run(radarr_servers.get_movie(db, 7 * radarr_servers.KEY_STRIDE + 12)) is None


class FakeDownloader:
    def __init__(self, storage_path, quality, max_duration=0, **options):
        self.storage_path = storage_path

    async def download_trailer(self, url, title, tmdb_id=None, tvdb_id=None, year=None):
        path = os.path.join(self.storage_path, f"{title}.mp4")
        with open(path, "wb") as f:
            f.write(b"trailer")
        return {"path": path, "size_mb": 1.0, "duration": 120, "resolution": "1080p"}


def test_auto_sync_downloads_4k_only_movies_once_and_expires_by_any_copy(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Thunderbolts"), movie(7, 300, "Released Elsewhere")]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Thunderbolts"), movie(12, 200, "Avengers Doomsday"),
                               movie(15, 300, "Released Elsewhere", has_file=True)]}
    db.add(models.ComingSoonTrailer(radarr_movie_id=7, tmdb_id=300, title="Released Elsewhere", status="downloaded"))
    db.commit()
    sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)

    def sync():
        with patch("backend.radarr_connector.TrailerDownloader", FakeDownloader):
            asyncio.run(sched._sync_radarr_trailers(db, db.query(models.Setting).first()))
        return {r.title: r for r in db.query(models.ComingSoonTrailer).all()}

    # The 4K copy's file counts: the trailer's Available Now window starts...
    rows = sync()
    assert set(rows) == {"Thunderbolts", "Avengers Doomsday", "Released Elsewhere"}
    assert rows["Thunderbolts"].radarr_movie_id == 5 and rows["Avengers Doomsday"].radarr_movie_id == UHD_KEY + 12
    assert rows["Released Elsewhere"].available_at is not None
    assert rows["Thunderbolts"].available_at is None
    # ...and once it has run out (Days visible defaults to 1) the trailer goes.
    rows["Released Elsewhere"].available_at = utcnow() - datetime.timedelta(days=2)
    db.commit()
    assert set(sync()) == {"Thunderbolts", "Avengers Doomsday"}


def test_library_sync_stops_when_a_radarr_cannot_be_read(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Kept", has_file=True)]}
    SERVERS[UHD] = {"error": "timed out"}
    setting = db.query(models.Setting).first()
    setting.library_trailers_config = json.dumps({"enabled": True, "download": False})
    db.add(models.LibraryTrailer(radarr_movie_id=UHD_KEY + 3, tmdb_id=900, title="On the 4K server",
                                 source="local", status="available", local_path=__file__))
    db.commit()
    with pytest.raises(library_trailers.LibraryTrailerError, match="Radarr 4K"):
        asyncio.run(library_trailers.run_sync(db))
    assert [r.title for r in db.query(models.LibraryTrailer).all()] == ["On the 4K server"]


def test_library_sync_with_one_unreachable_radarr_no_longer_empties_the_library(db):
    SERVERS[HD] = {"error": "timed out"}
    db.query(models.RadarrServer).delete()
    setting = db.query(models.Setting).first()
    setting.library_trailers_config = json.dumps({"enabled": True, "download": False})
    db.add(models.LibraryTrailer(radarr_movie_id=5, title="Kept", source="local", status="available", local_path=__file__))
    db.commit()
    with pytest.raises(library_trailers.LibraryTrailerError):
        asyncio.run(library_trailers.run_sync(db))
    assert db.query(models.LibraryTrailer).count() == 1


def test_library_finds_a_trailer_next_to_the_4k_copy(db, tmp_path):
    hd_dir, uhd_dir = tmp_path / "hd" / "Dune", tmp_path / "uhd" / "Dune"
    hd_dir.mkdir(parents=True)
    uhd_dir.mkdir(parents=True)
    (uhd_dir / "Dune-trailer.mp4").write_bytes(b"x")
    SERVERS[HD] = {"movies": [movie(5, 100, "Dune", path=str(hd_dir))]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Dune", has_file=True, path=str(uhd_dir))]}
    lib = read(db, with_tags=True)
    config = library_trailers.normalize_config({"enabled": True, "download": False})
    result = asyncio.run(library_trailers.sync_library_trailers(db, lib.movies, None, config))
    assert result["local_found"] == 1
    row = db.query(models.LibraryTrailer).one()
    assert (row.radarr_movie_id, row.local_path) == (5, str(uhd_dir / "Dune-trailer.mp4"))


def test_picked_movies_follow_their_movie(db):
    SERVERS[HD] = {"movies": [movie(5, 100, "Dune", has_file=True)]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Dune")]}
    config = library_trailers.canonical_config({"picked": [UHD_KEY + 9], "always_include": [], "never_include": [7]}, read(db))
    assert config["picked"] == [5] and config["never_include"] == [7]


# ---- Endpoints -----------------------------------------------------------

ROUTES = {"_ARR_SERVER_KINDS", "_arr_kind", "_arr_server_out", "_arr_server_row", "list_arr_servers",
          "add_arr_server", "test_arr_server", "remove_arr_server", "get_upcoming_movies"}


def route_client(db, routes):
    """The named main.py functions on a bare app, without importing main."""
    from backend import available_now, list_exclusions, sonarr_servers, trailer_upkeep
    app = FastAPI()

    def get_db():
        yield db

    env = dict(app=app, models=models, Session=Session, Depends=Depends, HTTPException=HTTPException,
               Body=Body, Optional=Optional, get_db=get_db, radarr_servers=radarr_servers,
               sonarr_servers=sonarr_servers, available_now=available_now,
               list_exclusions=list_exclusions, trailer_upkeep=trailer_upkeep,
               _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None,
               utcnow=utcnow, datetime=datetime)
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))

    def name_of(node):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return getattr(node, "name", None)

    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign))
             and name_of(n) in routes]
    assert {name_of(n) for n in nodes} == routes
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<arr-routes>", "exec"), env)
    return TestClient(app)


@pytest.fixture
def client(db):
    with route_client(db, ROUTES) as test_client:
        yield test_client


def test_adding_a_server_tests_it_and_never_returns_its_key(db, client):
    SERVERS["http://4k.test:7879"] = {"movies": [], "instance": "Radarr4K"}
    assert client.post("/nexup/radarr/servers", json={"url": HD + "/", "api_key": "x"}).status_code == 400
    assert client.post("/nexup/radarr/servers", json={"url": "http://down.test", "api_key": "x"}).json()["success"] is False
    added = client.post("/nexup/radarr/servers", json={"url": "4k.test:7879", "api_key": "k3"}).json()
    assert added["success"] is True
    assert added["server"]["name"] == "Radarr4K" and added["server"]["url"] == "http://4k.test:7879"
    listed = client.get("/nexup/radarr/servers").json()["servers"]
    assert [s["name"] for s in listed] == ["Radarr 4K", "Radarr4K"]
    assert all("api_key" not in s for s in listed)
    assert client.post(f"/nexup/radarr/servers/{added['server']['id']}/test").json()["success"] is True


def test_a_removed_servers_id_is_never_reused(db, client):
    SERVERS["http://new.test"] = {"movies": []}
    first = db.query(models.RadarrServer).one().id
    assert client.delete(f"/nexup/radarr/servers/{first}").json()["success"] is True
    assert client.delete(f"/nexup/radarr/servers/{first}").status_code == 404
    added = client.post("/nexup/radarr/servers", json={"url": "http://new.test", "api_key": "k"}).json()
    assert added["server"]["id"] != first
    assert added["server"]["name"] == "Radarr 2"


def test_upcoming_page_shows_both_servers_and_knows_the_moved_trailer(db, client):
    SERVERS[HD] = {"movies": [movie(5, 100, "Thunderbolts")]}
    SERVERS[UHD] = {"movies": [movie(9, 100, "Thunderbolts"), movie(12, 200, "Avengers Doomsday")]}
    db.add(models.ComingSoonTrailer(radarr_movie_id=UHD_KEY + 9, tmdb_id=100, title="Thunderbolts",
                                    status="downloaded", downloaded_at=utcnow()))
    db.commit()
    body = client.get("/nexup/radarr/upcoming").json()
    movies = {m["title"]: m for m in body["movies"]}
    assert set(movies) == {"Thunderbolts", "Avengers Doomsday"}
    assert movies["Thunderbolts"]["radarr_id"] == 5 and movies["Thunderbolts"]["downloaded"] is True
    assert movies["Avengers Doomsday"]["radarr_id"] == UHD_KEY + 12
    assert body["failed_servers"] == []
