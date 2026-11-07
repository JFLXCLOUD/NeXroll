"""Audit after the November 6 trailer report: other ways Plex could be handed
a file that isn't there, or have its list changed mid-prerolls.

- A file in the list Plex was given that is renamed, moved to another
  category's folder, sent to the Trash or deleted outside NeXroll left its
  old path in Plex's list. Category schedules were put right by the
  five-minute verification; a fixed sequence or a filler never was.
- Apply buttons and the external API wrote Plex at once, mid-prerolls too.
- Generated videos were rendered straight into the file Plex plays.
- Jellyfin and Emby ignored a schedule's Sequential playback setting.
- The Scheduler tile's "Last applied" read last_run, stamped even on a
  failed apply.
"""

import datetime
import json
import os
from types import SimpleNamespace
from unittest import mock

import pytest

from backend import models
from backend import scheduler as sched
from backend.dynamic_preroll import DynamicPrerollGenerator
from tests.test_playback_guard import IDLE_XML, SESSION_XML, FakeSetting, response
from tests.test_rotation_cadence import FakePlex, RotationHarness
from tests.test_trailer_filters import db, route  # noqa: F401  (db is a fixture)


class ListedFileTests(RotationHarness):
    def move(self, category_id, index=0, new_name="renamed.mp4"):
        """What the edit dialog's rename (or a category move) does."""
        with self.Session() as db:
            row = (db.query(models.Preroll).filter(models.Preroll.category_id == category_id)
                   .order_by(models.Preroll.id).all()[index])
            old = row.path
            new = os.path.join(os.path.dirname(old), new_name)
            os.rename(old, new)
            row.path = new
            db.commit()
            return old, new

    def test_a_renamed_preroll_in_a_category_list_is_rewritten(self):
        self.add_schedule(category_id=self.cat_a)
        self.run_minutes(0)
        old, new = self.move(self.cat_a)
        self.scheduler._check_listed_files()
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertNotIn(old, FakePlex.writes[-1])
        self.assertIn(new, FakePlex.writes[-1])

    def test_a_fixed_sequence_is_rewritten_too(self):
        # Fixed sequences are written once and never rotated or verified.
        self.add_schedule(sequence=[self.fixed_block()])
        self.run_minutes(5)
        self.assertEqual(len(FakePlex.writes), 1)
        old, new = self.move(self.cat_b, index=1, new_name="moved.mp4")
        self.scheduler._check_listed_files()
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertIn(new, FakePlex.writes[-1])

    def test_filler_is_rewritten_too(self):
        self.set_filler(filler_type="category", filler_category_id=self.cat_b)
        self.run_minutes(0)
        old, new = self.move(self.cat_b)
        self.scheduler._check_listed_files()
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertIn(new, FakePlex.writes[-1])

    def test_a_file_the_library_still_lists_is_acted_on_once(self):
        # Deleted outside NeXroll: the row stays until the next scan, so the
        # rewrite still has it. It must not become a rewrite every minute.
        self.add_schedule(category_id=self.cat_a)
        self.run_minutes(0)
        with self.Session() as db:
            os.remove(db.query(models.Preroll).filter(models.Preroll.category_id == self.cat_a).first().path)
        for _ in range(4):
            self.scheduler._check_listed_files()
            self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)

    def test_a_folder_that_is_gone_is_offline_storage_not_a_moved_file(self):
        offline = os.path.join(self.tmp.name, "nas-share", "Christmas", "a.mp4")
        self.scheduler._applied_local_paths = {offline}
        self.scheduler._check_listed_files()
        self.assertIsNone(self.scheduler._refresh_requested_at)

    def test_nothing_gone_means_nothing_written(self):
        self.add_schedule(category_id=self.cat_a)
        self.run_minutes(0)
        for _ in range(3):
            self.scheduler._check_listed_files()
            self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 1)

    def test_last_applied_names_the_write_plex_took(self):
        self.add_schedule(category_id=self.cat_a, name="Christmas Schedule")
        self.assertIsNone(self.scheduler.last_plex_write())
        self.run_minutes(0)
        last = self.scheduler.last_plex_write()
        self.assertEqual(last["what"], "Christmas Schedule")
        self.assertTrue(last["at"].startswith("2026-10-14T20:00"))

    def test_a_held_write_is_not_last_applied(self):
        self.add_schedule(category_id=self.cat_a, name="Held")
        self.defer[0] = True
        self.run_minutes(2)
        self.assertIsNone(self.scheduler.last_plex_write())


class TestManualWriteGuard:
    def scheduler(self):
        s = sched.Scheduler()
        s._sleep = lambda seconds: None
        return s

    def test_prerolls_playing_block_a_manual_write(self):
        s = self.scheduler()
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=SESSION_XML)):
            assert s.playback_blocks_manual_write(FakeSetting()) == 1
        assert s.deferred_write_state() is None, "nothing is queued, so nothing is reported as waiting"

    def test_idle_plex_lets_it_through_after_the_later_looks(self):
        s = self.scheduler()
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=IDLE_XML)) as get:
            assert s.playback_blocks_manual_write(FakeSetting()) == 0
        assert get.call_count == 3

    def test_guard_off_or_no_plex_never_blocks(self):
        s = self.scheduler()
        off = FakeSetting()
        off.playback_guard_minutes = 0
        no_plex = SimpleNamespace(plex_url=None, plex_token=None)
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=SESSION_XML)) as get:
            assert s.playback_blocks_manual_write(off) == 0
            assert s.playback_blocks_manual_write(no_plex) == 0
        assert get.call_count == 0


def test_a_request_waits_briefly_for_the_scheduler_not_for_its_second_look():
    # Saving a schedule runs a tick; one that writes Plex now pauses 5 s for
    # the second look, and the save shouldn't hang on it.
    import threading
    import time
    s = sched.Scheduler()
    done = threading.Event()

    def slow_tick():
        time.sleep(0.6)
        done.set()

    s._check_and_execute_schedules = slow_tick
    started = time.monotonic()
    s.trigger_immediate_check(wait_seconds=0.1)
    assert time.monotonic() - started < 0.5
    assert done.wait(3), "the tick still runs to the end"
    done.clear()
    s.trigger_immediate_check(wait_seconds=3)
    assert done.is_set(), "a quick tick is finished when the request carries on"


def refuse(count, force=False, plex_url="http://plex"):
    fn = route("_refuse_write_during_prerolls",
               scheduler=SimpleNamespace(playback_blocks_manual_write=lambda setting: count),
               HTTPException=_HTTPException)
    return fn(SimpleNamespace(plex_url=plex_url), force)


class _HTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def test_the_apply_endpoints_answer_409_while_prerolls_play():
    with pytest.raises(_HTTPException) as caught:
        refuse(1)
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "playback"
    assert refuse(1, force=True) is None
    assert refuse(0) is None
    assert refuse(1, plex_url=None) is None


# -- generated videos ----------------------------------------------------------

def generator(tmp_path):
    gen = DynamicPrerollGenerator.__new__(DynamicPrerollGenerator)
    gen.output_dir = tmp_path
    return gen


def test_a_render_replaces_the_video_only_when_it_is_complete(tmp_path):
    gen = generator(tmp_path)
    final = tmp_path / "coming_soon_grid.mp4"
    final.write_bytes(b"old")
    seen = {}

    def render(name):
        seen["during"] = final.read_bytes()  # what Plex would find mid-render
        (tmp_path / name).write_bytes(b"new")
        return str(tmp_path / name)

    assert gen._render_staged(render, "coming_soon_grid.mp4") == str(final)
    assert seen["during"] == b"old"
    assert final.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["coming_soon_grid.mp4"]


def test_a_failed_render_keeps_the_old_video(tmp_path):
    gen = generator(tmp_path)
    final = tmp_path / "coming_soon_grid.mp4"
    final.write_bytes(b"old")

    def render(name):
        (tmp_path / name).write_bytes(b"half")  # ffmpeg died part way
        return None

    assert gen._render_staged(render, "coming_soon_grid.mp4") is None
    assert final.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["coming_soon_grid.mp4"]


def test_a_video_held_open_keeps_the_old_one_after_retrying(tmp_path):
    gen = generator(tmp_path)
    final = tmp_path / "coming_soon_grid.mp4"
    final.write_bytes(b"old")

    def render(name):
        (tmp_path / name).write_bytes(b"new")
        return str(tmp_path / name)

    with mock.patch("backend.dynamic_preroll.os.replace", side_effect=PermissionError("in use")) as rep, \
            mock.patch("backend.dynamic_preroll.time.sleep") as nap:
        assert gen._render_staged(render, "coming_soon_grid.mp4") is None
    assert rep.call_count == 6 and nap.call_count == 5
    assert final.read_bytes() == b"old"


def test_the_staging_file_is_hidden_from_the_folder_scan():
    assert DynamicPrerollGenerator._staging_name("coming_soon_grid.mp4").startswith(".")
    assert DynamicPrerollGenerator._staging_name("coming_soon_grid.mp4").endswith(".mp4")


# -- Jellyfin / Emby follow the schedule's Playback setting -------------------

@pytest.mark.parametrize("playlist, mode", [(True, "sequential"), (False, "shuffle")])
def test_jellyfin_plays_a_category_schedule_the_way_plex_does(db, tmp_path, playlist, mode):
    category = models.Category(name="Christmas")
    db.add(category)
    db.flush()
    for i in range(3):
        path = tmp_path / f"xmas{i}.mp4"
        path.write_bytes(b"x")
        db.add(models.Preroll(filename=path.name, path=str(path), category_id=category.id, enabled=True))
    schedule = models.Schedule(name="Christmas Schedule", type="daily", start_date=datetime.datetime(2026, 1, 1),
                               category_id=category.id, is_active=True, playlist=playlist)
    db.add(schedule)
    db.flush()
    setting = db.query(models.Setting).first()
    setting.active_category, setting.active_schedule_id = category.id, schedule.id
    db.commit()
    result = route("_resolve_current_intros")(db, server_type="Jellyfin")
    assert result["mode"] == mode
    assert len(result["paths"]) == 3
