"""NeXroll, not the plugin's Max Intros, decides how many prerolls Jellyfin and
Emby play. A Max Intros of 1 used to be the only way to get one preroll from a
random category, and it cut every sequence to its first block."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import backend.models as models
from backend.shuffle_bag import clear_shuffle_bags, shuffle_bag_sample
from tests.test_trailer_filters import db, route  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def fresh_bags():
    clear_shuffle_bags()
    yield
    clear_shuffle_bags()


def helpers():
    count = route("_plugin_random_count", PLUGIN_RANDOM_COUNT_MAX=20)
    play = route("_plugin_play_list", shuffle_bag_sample=shuffle_bag_sample, _plugin_random_count=count)
    return count, play


POOL = [f"/p/{c}.mp4" for c in "abcdef"]


def test_a_random_category_plays_one_preroll_by_default():
    _, play = helpers()
    picked = play(SimpleNamespace(plugin_random_count=None), POOL, "shuffle")
    assert len(picked) == 1 and picked[0] in POOL


def test_the_configured_count_is_honoured():
    _, play = helpers()
    picked = play(SimpleNamespace(plugin_random_count=3), POOL, "shuffle")
    assert len(picked) == 3 and len(set(picked)) == 3


def test_the_whole_category_is_heard_before_anything_repeats():
    _, play = helpers()
    setting = SimpleNamespace(plugin_random_count=1)
    first_round = [play(setting, POOL, "shuffle")[0] for _ in POOL]
    assert sorted(first_round) == sorted(POOL)


@pytest.mark.parametrize("mode", ["sequential", "single"])
def test_sequences_and_in_order_lists_play_in_full(mode):
    _, play = helpers()
    seq = ["/p/intro.mp4", "/p/trailer1.mp4", "/p/trailer2.mp4", "/p/feature.mp4"]
    assert play(SimpleNamespace(plugin_random_count=1), seq, mode) == seq


def test_each_category_keeps_its_own_rotation():
    # They used to share one, so switching categories started it over.
    _, play = helpers()
    setting = SimpleNamespace(plugin_random_count=1)
    other = [f"/q/{c}.mp4" for c in "xyz"]
    heard = [play(setting, POOL, "shuffle", ("category", 1))[0] for _ in range(3)]
    play(setting, other, "shuffle", ("category", 2))
    heard += [play(setting, POOL, "shuffle", ("category", 1))[0] for _ in range(3)]
    assert sorted(heard) == sorted(POOL)


def test_an_empty_list_stays_empty():
    _, play = helpers()
    assert play(SimpleNamespace(plugin_random_count=1), [], "shuffle") == []


@pytest.mark.parametrize("raw,expected", [(None, 1), (0, 1), (3, 3), (99, 20), ("junk", 1), (-2, 1)])
def test_count_is_kept_within_bounds(raw, expected):
    count, _ = helpers()
    assert count(SimpleNamespace(plugin_random_count=raw)) == expected


def test_the_setting_round_trips(db):
    count, _ = helpers()
    put = route("put_plugin_playback_settings", HTTPException=HTTPException, PLUGIN_RANDOM_COUNT_MAX=20)
    get = route("get_plugin_playback_settings", _plugin_random_count=count, PLUGIN_RANDOM_COUNT_MAX=20)
    assert get(db)["random_count"] == 1
    assert put(SimpleNamespace(random_count=2), db)["random_count"] == 2
    assert get(db)["random_count"] == 2
    assert db.query(models.Setting).first().plugin_random_count == 2


@pytest.mark.parametrize("bad", [0, 21])
def test_out_of_range_counts_are_refused(db, bad):
    put = route("put_plugin_playback_settings", HTTPException=HTTPException, PLUGIN_RANDOM_COUNT_MAX=20)
    with pytest.raises(HTTPException) as err:
        put(SimpleNamespace(random_count=bad), db)
    assert err.value.status_code == 422


def test_upgrades_add_the_column_at_startup():
    """ensure_settings_schema_now only runs after a failed Plex status query;
    the startup block is what upgrades an existing database. Without it the
    first settings query on an upgraded install fails with no such column."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(encoding="utf-8")
    assert '_sqlite_has_column("settings", "plugin_random_count")' in src
    assert '_sqlite_add_column("settings", "plugin_random_count INTEGER")' in src


def test_the_endpoints_are_not_shadowed_by_the_generic_settings_route():
    """/settings/{key} answers any single-segment settings path declared after it."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(encoding="utf-8")
    generic = src.index('@app.get("/settings/{key}")')
    assert src.index('@app.get("/settings/plugin-playback")') < generic
    assert src.index('@app.put("/settings/plugin-playback")') < src.index('@app.put("/settings/{key}")')
