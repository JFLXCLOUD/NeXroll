"""A skipped block plays nothing, and filler can be one fixed preroll.

User report (Discord, October 21): "Unless the genre is Family, play one from
JellyJo; otherwise skip" played a JellyJo preroll before Family movies too.
The block was skipped correctly, but the empty sequence then fell through to
the schedule's category, which the schedule form sets to the first category
block's, i.e. the very category that was skipped. Any sequence with a
condition may now play nothing on purpose, on every server and every path
(schedule, filler, manual apply); only an unconditional sequence keeps the old
category fallback.

Also covered: Emby's cache sync gets every file a sequence could play (it plays
only cached files), Jellyfin/Emby take a sequence Plex has nothing to play for,
generated and preroll fillers and Clear When Inactive wait for the playback
guard, saving filler settings doesn't override an active schedule, and the
new fixed-preroll filler on Plex, Jellyfin/Emby and both.
"""
import datetime
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from backend import models, scheduler as sched
from backend.trailer_filters import has_trailer_policy
from tests.test_rotation_cadence import FakePlex, RotationHarness
from tests.test_trailer_filters import db, route  # noqa: F401  (db is a fixture)


def not_family(category_id, **extra):
    return {"type": "random", "category_id": category_id, "count": 1,
            "condition": {"match": "all", "rules": [
                {"kind": "genre", "values": ["Family", "Children"], "negate": True}]}, **extra}


def genre(category_id, *genres, **extra):
    return {"type": "random", "category_id": category_id, "count": 1,
            "condition": {"match": "all", "rules": [{"kind": "genre", "values": list(genres)}]}, **extra}


def add_category(db, tmp_path, name, files=1):
    category = models.Category(name=name)
    db.add(category)
    db.flush()
    paths = []
    for i in range(files):
        path = tmp_path / f"{name}-{i}.mp4"
        path.write_bytes(b"video")
        db.add(models.Preroll(filename=path.name, path=str(path), category_id=category.id, enabled=True))
        paths.append(str(path))
    db.flush()
    return category.id, paths


def activate(db, blocks, category_id=None):
    """A running schedule as the schedule form saves it: its category is the
    first category block's, and a category + sequence schedule keeps it in
    active_category."""
    schedule = models.Schedule(id=1, name="Seq", type="daily", start_date=datetime.datetime(2026, 1, 1),
                               category_id=category_id, sequence=json.dumps(blocks), is_active=True)
    db.add(schedule)
    setting = db.query(models.Setting).first()
    setting.active_schedule_id = schedule.id
    setting.active_category = category_id
    db.commit()


def intros(db, **kwargs):
    return route('_resolve_current_intros')(db, server_type="Jellyfin", **kwargs)["paths"]


# -- the report ----------------------------------------------------------------

def test_a_skipped_block_plays_nothing_on_jellyfin(db, tmp_path):
    cat, files = add_category(db, tmp_path, "JellyJo")
    activate(db, [not_family(cat, else_if=True)], category_id=cat)
    assert intros(db, genres=["Family"]) == []
    assert intros(db, genres=["Action"]) == files


def test_an_else_if_chain_with_no_match_and_no_otherwise_plays_nothing(db, tmp_path):
    horror, _ = add_category(db, tmp_path, "Horror")
    scifi, _ = add_category(db, tmp_path, "SciFi")
    activate(db, [genre(horror, "Horror"), genre(scifi, "Science Fiction", else_if=True)], category_id=horror)
    assert intros(db, genres=["Comedy"]) == []


def test_an_otherwise_still_plays(db, tmp_path):
    jellyjo, _ = add_category(db, tmp_path, "JellyJo")
    christmas, christmas_files = add_category(db, tmp_path, "Christmas")
    block = not_family(jellyjo)
    block["otherwise"] = {"type": "random", "category_id": christmas, "count": 1}
    activate(db, [block], category_id=jellyjo)
    assert intros(db, genres=["Family"]) == christmas_files


def test_an_unconditional_sequence_keeps_the_category_fallback(db, tmp_path):
    # Only conditions changed: an empty unconditional block still falls back.
    empty, _ = add_category(db, tmp_path, "Empty", files=0)
    full, files = add_category(db, tmp_path, "Full")
    activate(db, [{"type": "random", "category_id": empty, "count": 1}], category_id=full)
    assert intros(db) == files


@pytest.mark.parametrize("selection", ["manual", "filler"])
def test_a_skipped_saved_sequence_plays_nothing(db, tmp_path, selection):
    cat, _ = add_category(db, tmp_path, "JellyJo")
    seq = models.SavedSequence(name="Not family", blocks=json.dumps([not_family(cat)]))
    db.add(seq)
    db.flush()
    setting = db.query(models.Setting).first()
    setting.active_category = cat  # whatever was playing before
    if selection == "manual":
        setting.applied_sequence_id = seq.id
        setting.override_expires_at = datetime.datetime(2026, 9, 26)  # route's clock is 2026-09-25
    else:
        setting.filler_active = f"sequence:{seq.id}"
    db.commit()
    assert intros(db, genres=["Family"]) == []


def test_any_condition_means_a_sequence_may_play_nothing():
    assert has_trailer_policy([not_family(1)])
    assert has_trailer_policy([{"type": "random", "category_id": 1, "condition": {"rules": [
        {"kind": "time_window", "start": "18:00", "end": "23:00"}]}}])
    assert not has_trailer_policy([{"type": "random", "category_id": 1}])
    assert not has_trailer_policy([{"type": "random", "category_id": 1, "condition": {"rules": []}}])


# -- Emby's cache sync -----------------------------------------------------------

def test_the_whole_pool_lists_every_branch_in_full_without_rotating(db, tmp_path):
    jellyjo, jellyjo_files = add_category(db, tmp_path, "JellyJo", files=3)
    christmas, christmas_files = add_category(db, tmp_path, "Christmas", files=2)
    block = not_family(jellyjo)
    block["otherwise"] = {"type": "random", "category_id": christmas, "count": 1}
    activate(db, [block], category_id=jellyjo)
    with patch.object(sched, "shuffle_bag_sample", side_effect=AssertionError("rotation consumed")):
        pool = route('_resolve_current_intros')(db, media_type="Movie", item_id="0", whole_pool=True)["paths"]
    assert sorted(pool) == sorted(jellyjo_files + christmas_files)


def test_a_playback_request_still_gets_one_pick(db, tmp_path):
    jellyjo, files = add_category(db, tmp_path, "JellyJo", files=3)
    activate(db, [not_family(jellyjo)], category_id=jellyjo)
    picked = intros(db, genres=["Action"])
    assert len(picked) == 1 and picked[0] in files


# -- the scheduler: Plex, Jellyfin/Emby and both ----------------------------------

class SkipOnServersTests(RotationHarness):
    def set_servers(self, plex=True, jellyfin=False):
        with self.Session() as db:
            s = db.query(models.Setting).first()
            s.plex_url = "http://plex.test" if plex else None
            s.jellyfin_url = "http://jellyfin.test" if jellyfin else None
            db.commit()

    def state(self):
        with self.Session() as db:
            s = db.query(models.Setting).first()
            return s.filler_active, s.active_schedule_id, s.active_category

    def test_plex_clears_its_list_for_a_genre_only_sequence(self):
        # Plex never knows the genre, so the block takes its Skip: Plex should
        # play nothing, not keep whatever the last schedule left there.
        FakePlex.writes = ["old schedule"]
        self.add_schedule(category_id=self.cat_a, sequence=[not_family(self.cat_a)])
        self.run_minutes(0)
        self.assertEqual(FakePlex.writes[-1], "")

    def test_jellyfin_only_takes_a_sequence_with_nothing_for_plex(self):
        self.set_servers(plex=False, jellyfin=True)
        with self.Session() as db:
            empty = models.Category(name="Empty")
            db.add(empty)
            db.commit()
            empty_id = empty.id
        schedule_id = self.add_schedule(sequence=[{"type": "random", "category_id": empty_id, "count": 1}])
        self.run_minutes(0)
        self.assertEqual(self.state()[1], schedule_id)
        self.assertIn(schedule_id, self.scheduler._last_rotation_time, "re-applied every tick")

    def test_both_servers_take_a_sequence_with_nothing_for_plex(self):
        self.set_servers(plex=True, jellyfin=True)
        with self.Session() as db:
            empty = models.Category(name="Empty")
            db.add(empty)
            db.commit()
            empty_id = empty.id
        seq_id = self.save_sequence([{"type": "random", "category_id": empty_id, "count": 1}])
        self.set_filler(filler_type="sequence", filler_sequence_id=seq_id)
        self.run_minutes(0)
        self.assertEqual(self.state()[0], f"sequence:{seq_id}", "Jellyfin never got the filler")
        self.assertEqual(FakePlex.writes, [], "Plex keeps its list when there is nothing for it")


class FillerPrerollTests(RotationHarness):
    def preroll(self):
        with self.Session() as db:
            p = db.query(models.Preroll).filter(models.Preroll.category_id == self.cat_b).first()
            return p.id, os.path.abspath(p.path)

    def state(self):
        with self.Session() as db:
            s = db.query(models.Setting).first()
            return s.filler_active, s.filler_preroll_id

    def test_plex_gets_the_one_preroll_once(self):
        pid, path = self.preroll()
        self.set_filler(filler_type="preroll", filler_preroll_id=pid)
        self.run_minutes(10)
        self.assertEqual(FakePlex.writes, [path])
        self.assertEqual(self.state()[0], f"preroll:{pid}")

    def test_jellyfin_only_records_it(self):
        pid, _ = self.preroll()
        with self.Session() as db:
            s = db.query(models.Setting).first()
            s.plex_url, s.jellyfin_url = None, "http://jellyfin.test"
            db.commit()
        self.set_filler(filler_type="preroll", filler_preroll_id=pid)
        self.run_minutes(0)
        self.assertEqual(self.state()[0], f"preroll:{pid}")
        self.assertEqual(FakePlex.writes, [])

    def test_it_waits_for_the_playback_guard_but_reaches_jellyfin_at_once(self):
        pid, path = self.preroll()
        with self.Session() as db:
            db.query(models.Setting).first().jellyfin_url = "http://jellyfin.test"
            db.commit()
        self.set_filler(filler_type="preroll", filler_preroll_id=pid)
        self.defer[0] = True
        self.run_minutes(2)
        self.assertEqual(FakePlex.writes, [])
        self.assertEqual(self.state()[0], f"preroll:{pid}")
        self.defer[0] = False
        self.run_minutes(2)
        self.assertEqual(FakePlex.writes, [path])

    def test_a_generated_filler_waits_for_the_playback_guard(self):
        folder = os.path.join(self.tmp.name, "dynamic_prerolls")
        os.makedirs(folder)
        with open(os.path.join(folder, "promo.mp4"), "wb") as handle:
            handle.write(b"x")
        with self.Session() as db:
            db.query(models.Setting).first().nexup_storage_path = self.tmp.name
            db.commit()
        self.set_filler(filler_type="dynamic", filler_dynamic_filename="promo.mp4")
        self.defer[0] = True
        self.run_minutes(2)
        self.assertEqual(FakePlex.writes, [], "written while prerolls were playing")
        self.defer[0] = False
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 1)

    def test_deleting_the_preroll_clears_the_choice(self):
        pid, _ = self.preroll()
        self.set_filler(filler_type="preroll", filler_preroll_id=pid)
        with self.Session() as db:
            db.delete(db.query(models.Preroll).filter(models.Preroll.id == pid).one())
            db.commit()
        self.assertIsNone(self.state()[1])

    def test_a_missing_preroll_plays_nothing_and_logs(self):
        self.set_filler(filler_type="preroll", filler_preroll_id=987654)
        self.run_minutes(0)
        self.assertEqual(FakePlex.writes, [])
        self.assertIsNone(self.state()[0])


class ClearWhenInactiveGuardTests(RotationHarness):
    def test_a_held_clear_reaches_jellyfin_at_once_and_plex_later(self):
        with self.Session() as db:
            db.query(models.Setting).first().jellyfin_url = "http://jellyfin.test"
            db.commit()
        schedule_id = self.add_schedule(category_id=self.cat_a)
        self.run_minutes(0)
        with self.Session() as db:
            db.query(models.Schedule).filter(models.Schedule.id == schedule_id).one().is_active = False
            s = db.query(models.Setting).first()
            s.clear_when_inactive = True
            db.commit()
        self.defer[0] = True
        self.run_minutes(2)
        self.assertNotEqual(FakePlex.writes[-1], "", "cleared while prerolls were playing")
        with self.Session() as db:
            self.assertIsNone(db.query(models.Setting).first().active_category, "Jellyfin kept the schedule")
        self.defer[0] = False
        self.run_minutes(0)
        self.assertEqual(FakePlex.writes[-1], "")


# -- saving filler settings ---------------------------------------------------------

def test_saving_filler_runs_the_scheduler_instead_of_writing_filler(db, tmp_path):
    _, files = add_category(db, tmp_path, "Filler")
    pid = db.query(models.Preroll).first().id
    ticks = []

    class FakeScheduler:
        def trigger_immediate_check(self):
            ticks.append(True)

        def apply_filler_now(self):
            raise AssertionError("filler written without the scheduler's checks")

    update = route('update_filler_settings', scheduler=FakeScheduler(), _file_log=lambda *a, **k: None,
                   log_event=lambda *a, **k: None)
    result = update(enabled=True, filler_type="preroll", preroll_id=pid, db=db)
    assert ticks == [True]
    assert result["preroll_id"] == pid and result["applied"] is False
    assert update(preroll_id=999999, db=db) == {"error": "Preroll ID 999999 not found"}
    assert update(filler_type="nonsense", db=db)["error"].startswith("Invalid filler type")


def test_the_plugin_plays_the_filler_preroll(db, tmp_path):
    _, files = add_category(db, tmp_path, "Filler")
    pid = db.query(models.Preroll).first().id
    setting = db.query(models.Setting).first()
    setting.filler_active = f"preroll:{pid}"
    db.commit()
    result = route('_resolve_current_intros')(db, server_type="Emby")
    assert result == {"paths": [os.path.abspath(files[0])], "mode": "single"}


def test_a_restore_translates_the_filler_preroll(tmp_path):
    from tests.test_backup_restore import FakeSecrets, load, session
    restore = load(FakeSecrets())['_restore_settings']
    db = session(tmp_path / "db.db")
    restore(db, {"filler_type": "preroll", "filler_preroll_id": 7}, {}, {}, {7: 42})
    assert db.query(models.Setting).first().filler_preroll_id == 42
    db.query(models.Setting).first().filler_preroll_id = 5
    db.commit()
    restore(db, {"filler_type": "category"}, {}, {}, {})  # a backup from before the filler preroll
    assert db.query(models.Setting).first().filler_preroll_id is None
    db.close()
