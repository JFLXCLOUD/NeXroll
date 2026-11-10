"""The "Available Now!" window for titles Radarr or Sonarr has downloaded.

User report (November 2026): The Odyssey was on the Coming Soon list for its
digital release (November 16/17), was downloaded early, and then "got
removed". The rendered list itself kept it, but everything else counted Days
visible from the trailer's downloaded_at (when NeX-Up downloaded the trailer,
weeks earlier): the Upcoming page dropped the movie the moment Radarr had it,
and every sync deleted its trailer at once (the auto-sync had no window at
all). Now the Upcoming pages follow the list (release date) and a trailer
stays Days visible days after its title arrives (available_at).
"""

import ast
import asyncio
import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend import available_now, list_exclusions, models, radarr_servers, sonarr_servers, trailer_upkeep
from backend import scheduler as scheduler_module
from backend.timeutil import utcnow
from tests import test_radarr_servers as R
from tests import test_sonarr_servers as S

TODAY = datetime.date.today()
NOW = datetime.datetime(2026, 11, 9, 12, 0)
BACKEND = Path(__file__).parents[1] / "backend"


class Row:
    def __init__(self, radarr_movie_id=1, available_at=None):
        self.radarr_movie_id = radarr_movie_id
        self.available_at = available_at
        self.title = f"movie {radarr_movie_id}"


# ---- Rules ---------------------------------------------------------------

def test_lists_count_from_the_release_date():
    passed = available_now.release_window_passed
    assert not passed((TODAY + datetime.timedelta(days=8)).isoformat(), 1)  # downloaded early
    assert not passed(TODAY.isoformat(), 1)
    assert not passed((TODAY - datetime.timedelta(days=1)).isoformat(), 1)
    assert passed((TODAY - datetime.timedelta(days=2)).isoformat(), 1)
    assert not passed((TODAY - datetime.timedelta(days=3)).isoformat(), 3)
    assert passed((TODAY - datetime.timedelta(days=4)).isoformat(), 3)
    assert passed("2026-11-01T00:00:00Z", 3, today=datetime.date(2026, 11, 9))
    assert passed(datetime.datetime(2026, 11, 1, 20), 3, today=datetime.date(2026, 11, 9))
    assert passed(datetime.date(2026, 11, 1), 3, today=datetime.date(2026, 11, 9))
    for unknown in (None, "", "soon"):
        assert not passed(unknown, 1), unknown  # the list keeps these too


def test_an_arrival_is_noted_once_and_forgotten_when_the_file_goes():
    row = Row()
    assert available_now.track_arrival(row, True, NOW) is True
    later = NOW + datetime.timedelta(days=1)
    assert available_now.track_arrival(row, True, later) is False
    assert row.available_at == NOW
    assert available_now.track_arrival(row, False, later) is False
    assert row.available_at is None  # a deleted copy; the next download starts again
    assert available_now.track_arrival(row, True, later) is True and row.available_at == later


def test_a_trailer_stays_days_visible_days_after_its_title_arrives():
    assert not available_now.trailer_window_passed(Row(), 3, NOW)
    assert not available_now.trailer_window_passed(Row(available_at=NOW - datetime.timedelta(days=3, hours=23)), 3, NOW)
    assert available_now.trailer_window_passed(Row(available_at=NOW - datetime.timedelta(days=4)), 3, NOW)
    assert available_now.trailer_removal_date(None, 3) is None
    assert available_now.trailer_removal_date(NOW, 3) == NOW + datetime.timedelta(days=4)


def test_movie_sync_leaves_movies_it_could_not_read_alone():
    arriving, old, gone, unread = Row(1), Row(2, NOW - datetime.timedelta(days=5)), Row(3, NOW), Row(4, NOW - datetime.timedelta(days=9))
    seen = []
    past = available_now.movie_trailers_past_window(
        [arriving, old, gone, unread], reported_ids={1, 2, 3}, downloaded_ids={1, 2},
        available_days=3, now=NOW, on_arrival=seen.append)
    assert past == [old]
    assert seen == [arriving] and arriving.available_at == NOW
    assert gone.available_at is None  # Radarr reports it without a file now
    assert unread.available_at == NOW - datetime.timedelta(days=9)  # its Radarr didn't answer


def test_an_outage_never_restarts_a_window():
    """The 4K Radarr reports a movie without a file while the main one, which
    has it, is down: the arrival stands (it used to be cleared, so the window
    started over once the main Radarr was back)."""
    row = Row(available_at=NOW - datetime.timedelta(days=5))
    assert available_now.track_arrival(row, False, NOW, clear=False) is False
    assert row.available_at == NOW - datetime.timedelta(days=5)
    assert available_now.track_arrival(Row(), True, NOW, clear=False) is True  # arrivals still start
    held = Row(1, NOW - datetime.timedelta(days=5))
    past = available_now.movie_trailers_past_window(
        [held], reported_ids={1}, downloaded_ids=set(), available_days=1, now=NOW, complete=False)
    assert past == [] and held.available_at == NOW - datetime.timedelta(days=5)
    past = available_now.movie_trailers_past_window(
        [held], reported_ids={1}, downloaded_ids={1}, available_days=1, now=NOW, complete=True)
    assert past == [held]  # back up: removed, its window long over


def test_days_visible_reads_the_setting():
    class Setting:
        nexup_coming_soon_available_days = 7
    assert available_now.days_visible(Setting()) == 7
    assert available_now.days_visible(None) == 1


# ---- Upcoming pages and trailer lists --------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    R.SERVERS.clear()
    S.SERVERS.clear()
    with factory() as session:
        session.add(models.Setting(nexup_radarr_url=R.HD, nexup_radarr_api_key="k1",
                                   nexup_sonarr_url=S.HD, nexup_sonarr_api_key="k2",
                                   nexup_coming_soon_available_days=3, nexup_trailer_retention_days=7))
        session.commit()
        with patch("backend.radarr_connector.RadarrConnector", R.FakeRadarr), \
                patch("backend.sonarr_connector.SonarrConnector", S.FakeSonarr):
            yield session
    engine.dispose()


def client_for(db, names):
    """The named main.py functions on a bare app, without importing main."""
    app = FastAPI()

    def get_db():
        yield db

    env = dict(app=app, models=models, Session=Session, Depends=Depends, HTTPException=HTTPException,
               Body=Body, Optional=Optional, get_db=get_db, radarr_servers=radarr_servers,
               sonarr_servers=sonarr_servers, available_now=available_now, utcnow=utcnow, datetime=datetime,
               list_exclusions=list_exclusions, trailer_upkeep=trailer_upkeep,
               _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None,
               _backfill_trailer_posters=lambda db: 0)
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<available-now-routes>", "exec"), env)
    return TestClient(app)


def test_upcoming_page_keeps_a_movie_downloaded_before_its_release(db):
    R.SERVERS[R.HD] = {"movies": [
        R.movie(3131, 1368337, "The Odyssey", days=8, has_file=True),
        R.movie(2, 2, "Out Today", days=0, has_file=True),
        R.movie(3, 3, "Out Three Days", days=-3, has_file=True),
        R.movie(4, 4, "Out Four Days", days=-4, has_file=True),
        R.movie(5, 5, "Released Not Downloaded", days=-4),
    ]}
    # Its trailer came weeks before the movie; that used to end the window.
    db.add(models.ComingSoonTrailer(radarr_movie_id=3131, tmdb_id=1368337, title="The Odyssey", status="downloaded",
                                    downloaded_at=utcnow() - datetime.timedelta(days=70)))
    db.commit()
    with client_for(db, {"get_upcoming_movies"}) as client:
        movies = {m["title"]: m for m in client.get("/nexup/radarr/upcoming").json()["movies"]}
    assert set(movies) == {"The Odyssey", "Out Today", "Out Three Days", "Released Not Downloaded"}
    assert movies["The Odyssey"]["available_now"] is True and movies["The Odyssey"]["downloaded"] is True
    assert movies["Released Not Downloaded"]["available_now"] is False


def test_upcoming_shows_page_keeps_a_downloaded_premiere_while_the_list_does(db):
    S.SERVERS[S.HD] = {
        "series": [S.series(4, 100, "Phony", {1: (1, 8)}), S.series(5, 200, "Old Premiere", {1: (1, 8)})],
        "calendar": [S.premiere(4, 100, "Phony", 1, -2, has_file=True),
                     S.premiere(5, 200, "Old Premiere", 1, -5, has_file=True)],
    }
    db.add(models.ComingSoonTVTrailer(sonarr_series_id=4, tvdb_id=100, season_number=1, title="Phony",
                                      status="downloaded", downloaded_at=utcnow() - datetime.timedelta(days=60)))
    db.commit()
    with client_for(db, {"get_upcoming_shows"}) as client:
        shows = {s["title"]: s for s in client.get("/nexup/sonarr/upcoming").json()["shows"]}
    assert set(shows) == {"Phony"}
    assert shows["Phony"]["available_now"] is True and shows["Phony"]["downloaded"] is True


def test_trailer_lists_show_when_an_arrived_titles_trailer_goes(db):
    arrived = utcnow() - datetime.timedelta(days=1)
    release = datetime.datetime.combine(TODAY + datetime.timedelta(days=8), datetime.time())
    db.add_all([
        models.ComingSoonTrailer(radarr_movie_id=3131, title="The Odyssey", status="downloaded", release_date=release,
                                 downloaded_at=utcnow() - datetime.timedelta(days=70), available_at=arrived),
        models.ComingSoonTrailer(radarr_movie_id=7, title="Still Coming", status="downloaded", release_date=release,
                                 downloaded_at=utcnow() - datetime.timedelta(days=70)),
        models.ComingSoonTVTrailer(sonarr_series_id=4, season_number=1, title="Phony", status="downloaded",
                                   release_date=release, downloaded_at=utcnow(), available_at=arrived),
    ])
    db.commit()
    with client_for(db, {"get_nexup_trailers", "_trailer_matches_preference", "get_sonarr_trailers"}) as client:
        movies = {t["title"]: t for t in client.get("/nexup/trailers").json()["trailers"]}
        shows = {t["title"]: t for t in client.get("/nexup/sonarr/trailers").json()}
    gone = (arrived + datetime.timedelta(days=4)).isoformat()  # Days visible 3, then the next sync
    assert movies["The Odyssey"]["removal_date"] == gone
    assert movies["The Odyssey"]["available_at"] == arrived.isoformat()
    # Not downloaded yet: retention from its release date, as before.
    assert movies["Still Coming"]["removal_date"] == (release + datetime.timedelta(days=7)).isoformat()
    assert movies["Still Coming"]["available_at"] is None
    assert shows["Phony"]["removal_date"] == gone


# ---- Syncs ---------------------------------------------------------------

def test_auto_sync_keeps_an_arrived_movies_trailer_for_days_visible(db, tmp_path):
    trailer_file = tmp_path / "The Odyssey.mp4"
    trailer_file.write_bytes(b"x")
    R.SERVERS[R.HD] = {"movies": [R.movie(3131, 1368337, "The Odyssey", days=8, has_file=True, trailer=None)]}
    db.add(models.ComingSoonTrailer(radarr_movie_id=3131, tmdb_id=1368337, title="The Odyssey", status="downloaded",
                                    local_path=str(trailer_file), downloaded_at=utcnow() - datetime.timedelta(days=70)))
    setting = db.query(models.Setting).first()
    setting.nexup_storage_path = str(tmp_path)
    setting.nexup_download_delay = 0
    db.commit()
    sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)

    def sync():
        with patch("backend.radarr_connector.TrailerDownloader", R.FakeDownloader):
            asyncio.run(sched._sync_radarr_trailers(db, db.query(models.Setting).first()))
        return db.query(models.ComingSoonTrailer).all()

    first = sync()
    assert [t.title for t in first] == ["The Odyssey"] and trailer_file.exists()
    arrived = first[0].available_at
    assert arrived is not None
    assert sync()[0].available_at == arrived  # a later sync doesn't restart it
    first[0].available_at = utcnow() - datetime.timedelta(days=4)
    db.commit()
    assert sync() == []
    assert not trailer_file.exists()


def functions(path, names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names}


def test_no_window_counts_from_the_trailers_own_download():
    """downloaded_at is when the trailer was downloaded; it must never start
    the Available Now window again (main.py and scheduler.py)."""
    checked = {**functions(BACKEND / "main.py", {"get_upcoming_movies", "get_upcoming_shows", "sync_nexup",
                                                 "sync_sonarr_trailers"}),
               **functions(BACKEND / "scheduler.py", {"_sync_radarr_trailers", "_sync_sonarr_trailers"})}
    assert len(checked) == 6
    for name, fn in checked.items():
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
                assert not (isinstance(node.right, ast.Attribute) and node.right.attr == "downloaded_at"), name
        calls = {node.func.attr for node in ast.walk(fn)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "available_now"}
        expected = {"get_upcoming_movies": "release_window_passed", "get_upcoming_shows": "release_window_passed",
                    "sync_nexup": "movie_trailers_past_window", "_sync_radarr_trailers": "movie_trailers_past_window",
                    "sync_sonarr_trailers": "track_arrival", "_sync_sonarr_trailers": "track_arrival"}[name]
        assert expected in calls, name
        if expected in ("movie_trailers_past_window", "track_arrival"):
            # A server that couldn't be read must not clear an arrival.
            keyword = "complete" if expected == "movie_trailers_past_window" else "clear"
            passed = [kw for node in ast.walk(fn) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == expected
                      for kw in node.keywords if kw.arg == keyword]
            assert passed and "library.failed" in ast.unparse(passed[0].value), name
