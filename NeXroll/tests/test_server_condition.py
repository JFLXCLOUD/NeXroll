"""A block can play on some media servers and not others.

With Plex and Jellyfin or Emby connected at once, every schedule played the
same prerolls on all of them. A "server" rule lets a block play only on the
servers it names, with its Otherwise playing everywhere else.
"""
import datetime
import json
from unittest.mock import Mock, patch

import pytest

from backend import models, scheduler as sched
from backend.sequence_conditions import (PlaybackContext, condition_holds, describe_condition, evaluate_rule,
                                         normalize_server)
from tests.test_trailer_filters import db, route  # noqa: F401  (db is a fixture)

NOW = datetime.datetime(2026, 10, 31, 20, 0)


def rule(*servers, negate=False):
    return {"kind": "server", "values": list(servers), **({"negate": True} if negate else {})}


@pytest.mark.parametrize("server,values,negate,expected", [
    ("jellyfin", ["jellyfin"], False, True),
    ("plex", ["jellyfin"], False, False),
    ("emby", ["jellyfin", "emby"], False, True),
    ("plex", ["plex"], True, False),
    ("jellyfin", ["plex"], True, True),
    (None, ["jellyfin"], False, None),   # a plugin too old to say
    (None, ["plex"], True, None),        # unknown is never met, "unless" included
    ("plex", [], False, None),           # nothing chosen
])
def test_the_rule_matches_the_asking_server(server, values, negate, expected):
    assert evaluate_rule(rule(*values, negate=negate), PlaybackContext(now=NOW, server=server)) is expected


def test_an_unknown_server_plays_the_otherwise():
    condition = {"match": "all", "rules": [rule("jellyfin")]}
    assert condition_holds(condition, PlaybackContext(now=NOW, server=None)) is False


@pytest.mark.parametrize("raw,expected", [("Jellyfin", "jellyfin"), ("EMBY", "emby"), ("plex", "plex"),
                                          (None, None), ("Kodi", None), ("", None)])
def test_server_names_are_normalized(raw, expected):
    assert normalize_server(raw) == expected


def test_the_rule_reads_well():
    assert describe_condition({"rules": [rule("jellyfin", "emby")]}) == "playing on Jellyfin or Emby"
    assert describe_condition({"rules": [rule("plex", negate=True)]}) == "not playing on Plex"


@pytest.fixture
def two_folders(db, tmp_path):
    """A Halloween schedule whose first block plays one category on Jellyfin
    and another everywhere else."""
    cats = {}
    files = {}
    for name in ("Halloween Jellyfin", "Halloween Plex"):
        category = models.Category(name=name)
        db.add(category)
        db.flush()
        path = tmp_path / f"{name}.mp4"
        path.write_bytes(b"video")
        db.add(models.Preroll(filename=path.name, path=str(path), category_id=category.id, enabled=True))
        cats[name], files[name] = category, str(path)
    blocks = [{"type": "random", "category_id": cats["Halloween Jellyfin"].id, "count": 1,
               "condition": {"match": "all", "rules": [rule("jellyfin")]},
               "otherwise": {"type": "random", "category_id": cats["Halloween Plex"].id, "count": 1}}]
    schedule = models.Schedule(id=31, name="Halloween", type="daily", start_date=datetime.datetime(2026, 1, 1),
                               sequence=json.dumps(blocks), is_active=True)
    db.add(schedule)
    setting = db.query(models.Setting).first()
    setting.active_schedule_id = schedule.id
    setting.plex_url, setting.plex_token = "http://plex.invalid", "test"
    db.commit()
    return schedule, files


@pytest.mark.parametrize("header,expected", [("Jellyfin", "Halloween Jellyfin"), ("Emby", "Halloween Plex"),
                                             (None, "Halloween Plex")])
def test_the_plugin_gets_its_own_prerolls(db, two_folders, header, expected):
    _, files = two_folders
    paths = route('_resolve_current_intros')(db, server_type=header)['paths']
    assert paths == [files[expected]]


def test_plex_gets_the_otherwise(db, two_folders):
    schedule, files = two_folders
    connector = Mock()
    connector.get_server_info.return_value = {"platform": "Windows"}  # the test paths are Windows paths
    connector.set_preroll.return_value = True
    scheduler = sched.Scheduler()
    with patch.object(sched, 'PlexConnector', return_value=connector), \
            patch.object(scheduler, '_defer_preroll_write', return_value=False):
        scheduler._apply_schedule_sequence_to_plex(schedule, db)
    connector.set_preroll.assert_called_once_with(files["Halloween Plex"])


def test_every_plex_path_says_it_is_plex():
    """Plex resolves in the scheduler and in two main.py paths; a context built
    without the server would make every "server" rule unknown on Plex."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "backend"
    scheduler_src = (root / "scheduler.py").read_text(encoding="utf-8")
    main_src = (root / "main.py").read_text(encoding="utf-8")
    assert scheduler_src.count('playback_context(db, media_type="movie", server_type="plex")') == 3
    assert 'playback_context(db, media_type="movie")' not in scheduler_src + main_src
