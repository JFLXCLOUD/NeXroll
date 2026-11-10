"""NeX-Up options the end-to-end test found ignored or wrong (November 2026).

- The automatic movie sync follows Include unmonitored movies, the release
  date preference, the storage limit and deleted trailer files, as the Sync
  button always did (trailer_upkeep).
- Maximum stored trailers counts the TV trailers already stored (it counted
  one sync's downloads, so every sync could add that many more).
- A download delay of 0 is 0, not 5.
- Re-releases of old movies get no trailer; Upcoming and the list hide them.
- Stored release dates follow Radarr and Sonarr, so a moved title is no
  longer removed by its old date and downloaded again.
- The automatic TV sync keeps a premiere's trailer for Days visible, like the
  Sync button (it used a fixed 5 days).
- List exclusions are kept per title and outlive the trailer.
- Generate, the regenerate after a sync and the preview build their titles in
  one function, which follows Include unmonitored movies and the Available
  Now Maximum items.
- /nexup/trailers/playback no longer fails when a trailer has a release date.
"""

import ast
import asyncio
import datetime
import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend import available_now, list_exclusions, models, radarr_servers, sonarr_servers, trailer_upkeep
from backend import scheduler as scheduler_module
from backend.radarr_connector import RadarrConnector
from backend.timeutil import utcnow
from backend.trailer_filters import genre_json
from tests import test_radarr_servers as R
from tests import test_sonarr_servers as S

TODAY = datetime.date.today()
BACKEND = Path(__file__).parents[1] / "backend"


def day(offset):
    return (TODAY + datetime.timedelta(days=offset)).isoformat()


def midnight(offset):
    return datetime.datetime.combine(TODAY + datetime.timedelta(days=offset), datetime.time())


class SizedDownloader:
    """Writes each trailer as a real 1 KB file in the storage folders and
    reports storage the way TrailerDownloader does."""

    def __init__(self, storage_path, quality="1080", max_duration=0, **options):
        self.base = Path(storage_path)
        for folder in ("movies", "tv"):
            (self.base / folder).mkdir(parents=True, exist_ok=True)

    async def download_trailer(self, url, title, tmdb_id=None, tvdb_id=None, year=None):
        path = self.base / ("tv" if tvdb_id else "movies") / f"{title}_trailer.mp4"
        path.write_bytes(b"x" * 1024)
        return {"path": str(path), "size_mb": 0.001, "duration": 100, "resolution": "1080p"}

    def get_storage_usage(self):
        total = sum(f.stat().st_size for f in self.base.rglob("*_trailer.*"))
        return {"total_size_gb": total / 1024 ** 3, "total_size_mb": total / 1024 ** 2}

    def cleanup_partial_downloads(self, *args, **kwargs):
        return 0


@pytest.fixture
def db(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    R.SERVERS.clear()
    S.SERVERS.clear()
    with factory() as session:
        session.add(models.Setting(nexup_radarr_url=R.HD, nexup_radarr_api_key="k1",
                                   nexup_sonarr_url=S.HD, nexup_sonarr_api_key="k2",
                                   nexup_storage_path=str(tmp_path), nexup_download_delay=0,
                                   nexup_coming_soon_available_days=3))
        session.commit()
        with patch("backend.radarr_connector.RadarrConnector", R.FakeRadarr), \
                patch("backend.sonarr_connector.SonarrConnector", S.FakeSonarr), \
                patch("backend.radarr_connector.TrailerDownloader", SizedDownloader):
            yield session
    engine.dispose()


def setting_of(db, **values):
    setting = db.query(models.Setting).first()
    for name, value in values.items():
        setattr(setting, name, value)
    db.commit()
    return setting


def auto_movie_sync(db):
    sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)
    asyncio.run(sched._sync_radarr_trailers(db, db.query(models.Setting).first()))
    return {t.title: t for t in db.query(models.ComingSoonTrailer).all()}


def auto_tv_sync(db):
    sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)
    asyncio.run(sched._sync_sonarr_trailers(db, db.query(models.Setting).first()))
    return {(t.title, t.season_number): t for t in db.query(models.ComingSoonTVTrailer).all()}


async def _nothing(*args, **kwargs):
    return None


def load_main(db, names, **extra):
    """The named main.py functions, without importing main."""
    app = FastAPI()

    def get_db():
        yield db

    env = dict(app=app, models=models, Session=Session, Depends=Depends, HTTPException=HTTPException,
               Body=Body, Optional=Optional, get_db=get_db, radarr_servers=radarr_servers,
               sonarr_servers=sonarr_servers, available_now=available_now, trailer_upkeep=trailer_upkeep,
               list_exclusions=list_exclusions, utcnow=utcnow, datetime=datetime, asyncio=asyncio, re=re,
               genre_json=genre_json, or_=or_, Path=Path, _nexup_sync_progress={},
               _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None,
               scheduler=SimpleNamespace(retire_trailer_files=lambda *a, **k: None),
               shuffle_bag_sample=lambda key, items, count: list(items)[:count],
               _create_preroll_from_tv_trailer=_nothing, _add_synced_trailers_to_categories=lambda db: None,
               _auto_regenerate_coming_soon_list=_nothing, **extra)
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<nexup-option-routes>", "exec"), env)
    return env


def list_items(db, source="both"):
    env = load_main(db, {"_coming_soon_list_items"})
    return asyncio.run(env["_coming_soon_list_items"](db, db.query(models.Setting).first(), source,
                                                       lambda *a, **k: None))


# ---- Shared rules ---------------------------------------------------------

def test_a_download_delay_of_zero_is_zero():
    assert trailer_upkeep.download_delay(SimpleNamespace(nexup_download_delay=0)) == 0
    assert trailer_upkeep.download_delay(SimpleNamespace(nexup_download_delay=12)) == 12
    assert trailer_upkeep.download_delay(SimpleNamespace(nexup_download_delay=None)) == 5
    assert trailer_upkeep.max_trailers(SimpleNamespace(nexup_max_trailers=None)) == 10
    assert trailer_upkeep.max_trailers(SimpleNamespace(nexup_max_trailers=0)) == 0
    assert trailer_upkeep.max_storage_gb(SimpleNamespace(nexup_max_storage_gb=None)) == 5.0


def test_old_re_releases_get_no_trailer():
    parser = RadarrConnector("http://radarr.test", "k")
    movies = [R.movie(1, 11, "New", days=20), R.movie(2, 22, "Last Year", days=20, year=TODAY.year - 1),
              R.movie(3, 33, "4K Re-release", days=20, year=TODAY.year - 2)]
    assert [m["title"] for m in parser.parse_upcoming_from_raw(movies, 90)] == ["New", "Last Year"]
    assert [m["title"] for m in parser.upcoming_from_raw(movies, 90)] == ["New", "Last Year"]


def test_a_missing_file_only_counts_when_its_folder_is_there(tmp_path):
    (tmp_path / "movies").mkdir()
    assert trailer_upkeep.file_is_gone(str(tmp_path / "movies" / "gone.mp4"))
    assert not trailer_upkeep.file_is_gone(str(tmp_path / "unplugged" / "kept.mp4"))
    assert not trailer_upkeep.file_is_gone(None)


# ---- Automatic movie sync -------------------------------------------------

def test_auto_movie_sync_follows_include_unmonitored_movies(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Monitored", days=10),
                                  R.movie(2, 22, "Unmonitored", days=12, monitored=False)]}
    assert set(auto_movie_sync(db)) == {"Monitored"}
    setting_of(db, nexup_include_unmonitored_movies=True)
    assert set(auto_movie_sync(db)) == {"Monitored", "Unmonitored"}


def test_auto_movie_sync_follows_the_release_date_preference(db):
    cinema = f"{day(5)}T00:00:00Z"
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Digital", days=40, inCinemas=cinema),
                                  R.movie(2, 22, "Cinema Only", days=40, digitalRelease=None, inCinemas=cinema)]}
    setting_of(db, nexup_release_date_preference="digital_only")
    rows = auto_movie_sync(db)
    assert set(rows) == {"Digital"}, "a theatrical-only movie has no digital date"
    setting_of(db, nexup_release_date_preference="theatrical")
    rows = auto_movie_sync(db)
    assert set(rows) == {"Digital", "Cinema Only"}
    assert (rows["Cinema Only"].release_type, available_now.as_date(rows["Cinema Only"].release_date)) == \
        ("theatrical", TODAY + datetime.timedelta(days=5))
    # The digital movie's stored date follows the preference too.
    assert rows["Digital"].release_type == "theatrical"


def test_auto_movie_sync_stops_at_the_storage_limit(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(i, i * 10, f"Movie {i}", days=10 + i) for i in range(1, 4)]}
    setting_of(db, nexup_max_storage_gb=5e-7)  # about 500 bytes; each trailer is 1 KB
    assert set(auto_movie_sync(db)) == {"Movie 1"}


def test_auto_movie_sync_drops_trailers_whose_file_was_deleted(db, tmp_path):
    (tmp_path / "movies").mkdir(exist_ok=True)
    gone = tmp_path / "movies" / "Deleted_trailer.mp4"
    unplugged = tmp_path / "unplugged" / "Offline_trailer.mp4"
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Deleted", days=10), R.movie(2, 22, "Offline", days=12)]}
    db.add_all([
        models.ComingSoonTrailer(radarr_movie_id=1, tmdb_id=11, title="Deleted", status="downloaded",
                                 local_path=str(gone), downloaded_at=utcnow()),
        models.ComingSoonTrailer(radarr_movie_id=2, tmdb_id=22, title="Offline", status="downloaded",
                                 local_path=str(unplugged), downloaded_at=utcnow()),
        models.Preroll(filename=gone.name, path=str(gone), display_name="[Trailer] Deleted"),
    ])
    db.commit()
    rows = auto_movie_sync(db)
    assert set(rows) == {"Deleted", "Offline"}
    assert Path(rows["Deleted"].local_path).exists(), "downloaded again"
    assert rows["Offline"].local_path == str(unplugged), "an unseen folder says nothing"
    assert db.query(models.Preroll).filter(models.Preroll.path == str(gone)).count() == 0


def test_a_moved_movie_keeps_its_trailer_by_the_new_date(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Pushed Back", days=30)]}
    db.add(models.ComingSoonTrailer(radarr_movie_id=1, tmdb_id=11, title="Pushed Back", status="downloaded",
                                    release_date=midnight(-20), release_type="theatrical", downloaded_at=utcnow()))
    db.commit()
    row = auto_movie_sync(db)["Pushed Back"]
    assert available_now.as_date(row.release_date) == TODAY + datetime.timedelta(days=30)
    assert row.release_type == "digital"


def test_every_sync_refreshes_dates_and_shares_the_rules():
    """The Sync buttons and the automatic syncs use the same trailer_upkeep
    rules, so they can't drift apart again."""
    from tests.test_available_now_window import functions
    checked = {**functions(BACKEND / "main.py", {"sync_nexup", "sync_sonarr_trailers"}),
               **functions(BACKEND / "scheduler.py", {"_sync_radarr_trailers", "_sync_sonarr_trailers"})}
    expected = {"sync_nexup": {"refresh_movie_dates", "drop_orphans", "movie_options", "download_delay", "max_trailers"},
                "_sync_radarr_trailers": {"refresh_movie_dates", "drop_orphans", "movie_options", "download_delay",
                                          "max_trailers", "storage_full"},
                "sync_sonarr_trailers": {"refresh_show_dates", "download_delay", "max_trailers", "storage_full"},
                "_sync_sonarr_trailers": {"refresh_show_dates", "download_delay", "max_trailers", "storage_full"}}
    for name, fn in checked.items():
        used = {node.func.attr for node in ast.walk(fn) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "trailer_upkeep"}
        assert expected[name] <= used, (name, expected[name] - used)
        source = ast.unparse(fn)
        assert "nexup_download_delay" not in source, name


# ---- TV --------------------------------------------------------------------

def test_auto_tv_sync_keeps_a_premiere_trailer_for_days_visible(db):
    setting_of(db, nexup_coming_soon_available_days=7)
    S.SERVERS[S.HD] = {"series": [S.series(4, 100, "Six Days", {1: (0, 8)}), S.series(5, 200, "Nine Days", {1: (0, 8)})]}
    db.add_all([
        models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=1, title="Six Days",
                                   status="downloaded", release_date=midnight(-6), downloaded_at=utcnow()),
        models.ComingSoonTVTrailer(sonarr_series_id=5, tvdb_id=200, season_number=1, title="Nine Days",
                                   status="downloaded", release_date=midnight(-9), downloaded_at=utcnow()),
    ])
    db.commit()
    assert set(auto_tv_sync(db)) == {("Six Days", 1)}, "it used to go 5 days after the premiere"


def test_a_moved_premiere_keeps_its_trailer(db):
    S.SERVERS[S.HD] = {"series": [S.series(4, 100, "Delayed", {1: (0, 8)})],
                       "calendar": [S.premiere(4, 100, "Delayed", 1, 20)]}
    db.add(models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=1, title="Delayed",
                                      status="downloaded", release_date=midnight(-10), downloaded_at=utcnow()))
    db.commit()
    row = auto_tv_sync(db)[("Delayed", 1)]
    assert available_now.as_date(row.release_date) == TODAY + datetime.timedelta(days=20)


class FakeTVTrailers:
    def __init__(self, *args, **kwargs):
        pass

    async def get_tv_trailers(self, tvdb_id=None, imdb_id=None):
        return [{"url": f"https://www.youtube.com/watch?v=tv{tvdb_id}"}]


def test_tv_sync_counts_stored_trailers_toward_the_limit(db):
    S.SERVERS[S.HD] = {"series": [S.series(i, i * 100, f"Show {i}", {1: (0, 8)}) for i in range(1, 6)],
                       "calendar": [S.premiere(i, i * 100, f"Show {i}", 1, 10 + i) for i in range(1, 6)]}
    setting_of(db, nexup_max_trailers=2)
    env = load_main(db, {"sync_sonarr_trailers"})
    with patch("backend.sonarr_connector.TVTrailerFetcher", FakeTVTrailers):
        first = asyncio.run(env["sync_sonarr_trailers"](db=db))
        second = asyncio.run(env["sync_sonarr_trailers"](db=db))
    assert first["downloaded"] == 2
    assert second["downloaded"] == 0, "the second sync used to add two more"
    assert db.query(models.ComingSoonTVTrailer).filter(models.ComingSoonTVTrailer.status == "downloaded").count() == 2


class FailingDownloader(SizedDownloader):
    """Fails like a download yt-dlp couldn't finish, or raises."""
    raises = False

    async def download_trailer(self, url, title, tmdb_id=None, tvdb_id=None, year=None):
        if FailingDownloader.raises:
            raise RuntimeError("connection reset")
        return {"error": "DOWNLOAD_FAILED", "message": "DOWNLOAD_FAILED: nothing came back"}


def one_premiere_and_sync(db):
    S.SERVERS[S.HD] = {"series": [S.series(1, 100, "Retry Me", {1: (0, 8)})],
                       "calendar": [S.premiere(1, 100, "Retry Me", 1, 12)]}
    env = load_main(db, {"sync_sonarr_trailers"})

    def sync(downloader=SizedDownloader):
        with patch("backend.sonarr_connector.TVTrailerFetcher", FakeTVTrailers), \
                patch("backend.radarr_connector.TrailerDownloader", downloader):
            return asyncio.run(env["sync_sonarr_trailers"](db=db))
    return sync


def season_rows(db):
    return db.query(models.ComingSoonTVTrailer).filter(models.ComingSoonTVTrailer.sonarr_series_id == 1).all()


def test_tv_sync_tries_a_failed_download_again(db):
    sync = one_premiere_and_sync(db)
    assert sync(FailingDownloader)["downloaded"] == 0
    assert [r.status for r in season_rows(db)] == ["error"]
    result = sync()
    assert result["downloaded"] == 1, "the failed row used to block the season for good"
    assert [r.status for r in season_rows(db)] == ["downloaded"]


def test_a_tv_download_that_raises_is_recorded_as_failed(db):
    sync = one_premiere_and_sync(db)
    FailingDownloader.raises = True
    try:
        sync(FailingDownloader)
    finally:
        FailingDownloader.raises = False
    rows = season_rows(db)
    assert [(r.status, r.error_message) for r in rows] == [("error", "connection reset")]
    assert sync()["downloaded"] == 1


def test_tv_sync_leaves_a_running_download_alone_and_replaces_a_stale_one(db):
    sync = one_premiere_and_sync(db)
    started = utcnow() - datetime.timedelta(minutes=5)
    db.add(models.ComingSoonTVTrailer(sonarr_series_id=1, tvdb_id=100, season_number=1, title="Retry Me",
                                      status="downloading", created_at=started, updated_at=started))
    db.commit()
    assert sync()["downloaded"] == 0
    assert [r.status for r in season_rows(db)] == ["downloading"]
    row = season_rows(db)[0]
    row.created_at = row.updated_at = utcnow() - datetime.timedelta(hours=2)  # NeXroll stopped mid-download
    db.commit()
    assert sync()["downloaded"] == 1
    assert [r.status for r in season_rows(db)] == ["downloaded"]


def test_which_earlier_tries_a_sync_replaces(tmp_path):
    now = utcnow()
    kept_file = tmp_path / "kept.mp4"
    kept_file.write_bytes(b"x")

    def row(status, minutes=0, path=None):
        at = now - datetime.timedelta(minutes=minutes)
        return SimpleNamespace(status=status, created_at=at, updated_at=at, local_path=path)
    failed, stale = row("error"), row("downloading", 120)
    assert trailer_upkeep.failed_tries([], now) == []
    assert trailer_upkeep.failed_tries([failed, stale], now) == [failed, stale]
    assert trailer_upkeep.failed_tries([failed, row("downloaded")], now) is None
    assert trailer_upkeep.failed_tries([row("downloading", 5)], now) is None
    assert trailer_upkeep.failed_tries([row("pending", path=str(kept_file))], now) is None, "a file on disk is a trailer"


def test_the_storage_limit_must_be_more_than_zero(db):
    from fastapi import Query
    from backend import trailer_language
    env = load_main(db, {"update_nexup_settings"}, Query=Query, os=os, MAX_GENERATED_DURATION=600,
                    QR_MODULE_STYLES={}, trailer_language=trailer_language)
    with TestClient(env["app"]) as client:
        assert client.put("/nexup/settings", params={"max_storage_gb": 20}).status_code == 200
        assert db.query(models.Setting).first().nexup_max_storage_gb == 20
        for bad in (0, -3):
            assert client.put("/nexup/settings", params={"max_storage_gb": bad}).status_code == 400
        db.expire_all()
        assert db.query(models.Setting).first().nexup_max_storage_gb == 20


def test_refresh_show_dates_only_moves_seasons_the_calendar_has():
    rows = [SimpleNamespace(sonarr_series_id=4, season_number=2, title="A", release_date=midnight(-3)),
            SimpleNamespace(sonarr_series_id=5, season_number=1, title="B", release_date=midnight(-3))]
    changed = trailer_upkeep.refresh_show_dates(rows, [{"sonarr_id": 4, "season_number": 2, "release_date": day(12)}])
    assert changed == 1
    assert available_now.as_date(rows[0].release_date) == TODAY + datetime.timedelta(days=12)
    assert rows[1].release_date == midnight(-3)


# ---- Exclusions --------------------------------------------------------------

def test_an_exclusion_outlives_its_trailer(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Skip Me", days=10), R.movie(2, 22, "Keep Me", days=12)]}
    db.add(models.ComingSoonTrailer(radarr_movie_id=1, tmdb_id=11, title="Skip Me", status="downloaded"))
    db.commit()
    trailer_id = db.query(models.ComingSoonTrailer).one().id
    env = load_main(db, {"toggle_trailer_exclusion"})
    with TestClient(env["app"]) as client:
        assert client.put(f"/nexup/trailers/{trailer_id}/exclude").json()["excluded_from_list"] is True
    assert [i["title"] for i in list_items(db)] == ["Keep Me"]
    db.query(models.ComingSoonTrailer).delete()  # arrival window, retention or a delete
    db.commit()
    assert [i["title"] for i in list_items(db)] == ["Keep Me"], "it used to come back"


def test_any_upcoming_title_can_be_excluded_and_put_back(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "No Trailer", days=10)]}
    env = load_main(db, {"get_upcoming_movies", "list_coming_soon_exclusions", "set_coming_soon_exclusion"})
    body = {"kind": "movie", "tmdb_id": 11, "title": "No Trailer", "excluded": True}
    with TestClient(env["app"]) as client:
        assert client.put("/nexup/coming-soon-list/exclusions", json=body).json()["excluded_from_list"] is True
        assert client.get("/nexup/radarr/upcoming").json()["movies"][0]["excluded_from_list"] is True
        assert [e["external_id"] for e in client.get("/nexup/coming-soon-list/exclusions").json()["exclusions"]] == [11]
        assert list_items(db) == []
        client.put("/nexup/coming-soon-list/exclusions", json={**body, "excluded": False})
        assert client.get("/nexup/radarr/upcoming").json()["movies"][0]["excluded_from_list"] is False
        assert client.put("/nexup/coming-soon-list/exclusions", json={"kind": "film", "title": "x", "excluded": True}).status_code == 400
        assert client.put("/nexup/coming-soon-list/exclusions", json={"kind": "movie", "excluded": True}).status_code == 400
    assert [i["title"] for i in list_items(db)] == ["No Trailer"]


def test_a_show_exclusion_covers_every_season(db):
    S.SERVERS[S.HD] = {"series": [S.series(4, 100, "Severance", {1: (8, 8), 2: (0, 8)})],
                       "calendar": [S.premiere(4, 100, "Severance", 2, 10), S.premiere(4, 100, "Severance", 3, 60)]}
    list_exclusions.set_excluded(db, list_exclusions.SHOW, 100, "Severance", True)
    db.commit()
    assert list_items(db, "shows") == []


def test_exclusions_from_older_versions_are_kept(db):
    db.add_all([models.ComingSoonTrailer(radarr_movie_id=1, tmdb_id=11, title="Old Flag", excluded_from_list=True),
                models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=1, title="Old Show",
                                           excluded_from_list=True),
                models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=2, title="Old Show",
                                           excluded_from_list=True)])
    db.commit()
    assert list_exclusions.load(db).excludes(list_exclusions.MOVIE, 11, "Old Flag")
    assert list_exclusions.backfill(db) == 2  # one per title, not per season
    db.commit()
    assert list_exclusions.backfill(db) == 0
    db.query(models.ComingSoonTrailer).delete()
    db.query(models.ComingSoonTVTrailer).delete()
    db.commit()
    found = list_exclusions.load(db)
    assert found.excludes(list_exclusions.MOVIE, 11, "Old Flag")
    assert found.excludes(list_exclusions.SHOW, 100, "Old Show")


def test_putting_a_title_back_clears_old_flags_and_ids_beat_titles(db):
    db.add(models.ComingSoonTrailer(radarr_movie_id=1, tmdb_id=11, title="Dune", excluded_from_list=True))
    db.commit()
    list_exclusions.set_excluded(db, list_exclusions.MOVIE, 11, "Dune", False)
    db.commit()
    assert not list_exclusions.load(db).excludes(list_exclusions.MOVIE, 11, "Dune")
    assert db.query(models.ComingSoonTrailer).one().excluded_from_list is False
    list_exclusions.set_excluded(db, list_exclusions.MOVIE, 11, "Dune", True)
    db.commit()
    found = list_exclusions.load(db)
    assert not found.excludes(list_exclusions.MOVIE, 99, "Dune"), "another movie with the same title"
    assert found.excludes(list_exclusions.MOVIE, None, "dune ")
    list_exclusions.set_excluded(db, list_exclusions.MOVIE, None, "Title Only", True)
    db.commit()
    assert list_exclusions.load(db).excludes(list_exclusions.MOVIE, 42, "Title Only")


# ---- Coming Soon list titles -------------------------------------------------

def test_the_list_follows_include_unmonitored_movies(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Monitored", days=10),
                                  R.movie(2, 22, "Unmonitored", days=12, monitored=False)]}
    assert [i["title"] for i in list_items(db)] == ["Monitored"]
    setting_of(db, nexup_include_unmonitored_movies=True)
    assert [i["title"] for i in list_items(db)] == ["Monitored", "Unmonitored"]


def test_preview_and_list_apply_the_same_windows_and_limits(db):
    R.SERVERS[R.HD] = {"movies": [R.movie(1, 11, "Arrived Two Days Ago", days=-2, has_file=True),
                                  R.movie(2, 22, "Arrived Yesterday", days=-1, has_file=True),
                                  R.movie(3, 33, "Arrived Long Ago", days=-6, has_file=True),
                                  R.movie(4, 44, "Coming", days=9)]}
    S.SERVERS[S.HD] = {"series": [S.series(4, 100, "Aired Recently", {1: (1, 8)}), S.series(5, 200, "Aired Too Long Ago", {1: (1, 8)})],
                       "calendar": [S.premiere(4, 100, "Aired Recently", 1, -1, has_file=True),
                                    S.premiere(5, 200, "Aired Too Long Ago", 1, -5, has_file=True)]}
    setting_of(db, nexup_coming_soon_max_available_now=1)
    titles = [i["title"] for i in list_items(db)]
    assert titles == ["Arrived Yesterday", "Coming"], "one Available Now title, the most recent"
    env = load_main(db, {"_coming_soon_list_items", "preview_coming_soon_list"})
    with TestClient(env["app"]) as client:
        preview = client.get("/nexup/preroll/coming-soon-list/preview", params={"max_items": 1}).json()
    assert [i["title"] for i in preview["items"]] == ["Arrived Yesterday"]
    assert preview["total_available"] == 2
    setting_of(db, nexup_coming_soon_max_available_now=0)
    titles = [i["title"] for i in list_items(db)]
    # The show 5 days past its premiere is past Days visible (3) in the
    # preview too now; the preview used to keep it.
    assert titles == ["Arrived Two Days Ago", "Arrived Yesterday", "Aired Recently", "Coming"]


# ---- Playback endpoint -------------------------------------------------------

def test_playback_endpoint_answers_when_a_trailer_has_a_release_date(db, tmp_path):
    setting_of(db, nexup_enabled=True, nexup_trailers_per_playback=2)
    db.add(models.ComingSoonTrailer(radarr_movie_id=1, title="Dated", status="downloaded", is_enabled=True,
                                    release_date=midnight(4), local_path=str(tmp_path / "x.mp4")))
    db.commit()
    env = load_main(db, {"get_nexup_playback_trailers"})
    with TestClient(env["app"]) as client:
        response = client.get("/nexup/trailers/playback")
    assert response.status_code == 200
    assert response.json()["trailers"][0]["days_until"] == 4
