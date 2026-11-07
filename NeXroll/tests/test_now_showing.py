"""What the dashboard's Current & next schedule tile says, case by case.

Production, November 6: Christmas (6 prerolls) and Thanksgiving (an empty
category) were both blending. The tile read "Shuffle / 0 prerolls / Blending
Christmas Schedule + Thanksgiving Schedule", the blend was stuck retrying
Thanksgiving, and Plex played the previous night's Adult Swim list all day.

Each test drives the real scheduler on a fake clock with a fake Plex, then
asks now_showing.describe() what the dashboard should say.
"""

import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models as models
import backend.scheduler as scheduler_module
from backend import health_summary, now_showing

START = datetime.datetime(2026, 11, 6, 12, 0)  # a Friday, midday
TICK = datetime.timedelta(seconds=60)
ALL_DAY = None


class FakePlex:
    writes = []
    refuse = ()  # substrings of preroll lists Plex rejects

    def __init__(self, url=None, token=None, *args, **kwargs):
        self.url, self.token = url, token
        self.headers = {"X-Plex-Token": token or ""}
        self._verify = True

    def get_server_info(self):
        return {"platform": "windows" if os.name == "nt" else "linux"}

    def set_preroll(self, value):
        if any(bad in value for bad in FakePlex.refuse):
            return False
        FakePlex.writes.append(value)
        return True

    def get_preroll(self):
        return FakePlex.writes[-1] if FakePlex.writes else ""


class Harness(unittest.TestCase):
    def setUp(self):
        FakePlex.writes, FakePlex.refuse = [], ()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.clock = [START]
        self.defer = [False]
        with self.Session() as db:
            self.christmas = self.category(db, "Christmas", 6)
            self.thanksgiving = self.category(db, "Thanksgiving", 0)
            self.adult_swim = self.category(db, "Adult Swim", 3)
            db.add(models.Setting(plex_url="http://plex.test", plex_token="token", timezone="UTC"))
            db.commit()
        self.scheduler = scheduler_module.Scheduler()
        self.log = MagicMock()
        patches = [
            patch.object(scheduler_module, "SessionLocal", self.Session),
            patch.object(scheduler_module, "_localized_now", lambda *a, **k: self.clock[0]),
            patch.object(scheduler_module, "PlexConnector", FakePlex),
            patch.object(scheduler_module, "_scheduler_log", self.log),
            patch.object(scheduler_module, "_scheduler_verbose", MagicMock()),
            patch.object(self.scheduler, "_defer_preroll_write", lambda *a, **k: self.defer[0]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    # -- fixtures -----------------------------------------------------------

    def category(self, db, name, count, disabled=0):
        category = models.Category(name=name)
        db.add(category)
        db.flush()
        for i in range(count + disabled):
            path = os.path.join(self.tmp.name, f"{name.replace(' ', '')}_{i}.mp4")
            with open(path, "wb") as handle:
                handle.write(b"x")
            db.add(models.Preroll(filename=os.path.basename(path), path=path, category_id=category.id,
                                  enabled=i < count))
        db.flush()
        return category.id

    def schedule(self, name, *, category_id=None, sequence=None, hours=ALL_DAY, **extra):
        with self.Session() as db:
            row = models.Schedule(
                name=name, type="daily",
                start_date=START - datetime.timedelta(days=30),
                category_id=category_id,
                sequence=json.dumps(sequence) if sequence is not None else None,
                recurrence_pattern=json.dumps({"timeRange": {"start": hours[0], "end": hours[1]}}) if hours else None,
                is_active=True, **extra)
            db.add(row)
            db.commit()
            return row.id

    def settings(self, **fields):
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            for key, value in fields.items():
                setattr(setting, key, value)
            db.commit()

    def run_minutes(self, minutes=0):
        for _ in range(minutes + 1):
            self.scheduler._check_and_execute_schedules_locked()
            self.clock[0] += TICK

    def showing(self):
        with self.Session() as db:
            return now_showing.describe(db, self.scheduler, self.clock[0])


class BlendTests(Harness):
    def test_production_blend_plays_christmas_and_says_thanksgiving_is_left_out(self):
        christmas = self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True, priority=5)
        thanksgiving = self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving,
                                     blend_enabled=True, priority=7)
        # Production picked Thanksgiving first; it must not be picked at all now.
        with patch.object(scheduler_module.random, "choice", lambda items: items[-1]):
            self.run_minutes(10)
        self.assertTrue(FakePlex.writes, "the blend never applied anything")
        self.assertTrue(all("Christmas_" in w for w in FakePlex.writes))

        shown = self.showing()
        self.assertEqual(shown["kind"], "blend")
        self.assertEqual((shown["title"], shown["subtitle"]), ("Christmas Schedule", "Christmas"))
        self.assertEqual((shown["mode"], shown["preroll_count"]), ("Shuffle", 6))
        self.assertEqual(shown["warnings"], [
            "Thanksgiving Schedule is left out of the blend: Thanksgiving has no enabled prerolls."])
        self.assertEqual(shown["problem"], "Thanksgiving Schedule left out")
        partners = {p["name"]: p for p in shown["blend"]["schedules"]}
        self.assertTrue(partners["Christmas Schedule"]["current"])
        self.assertEqual(partners["Thanksgiving Schedule"]["preroll_count"], 0)
        self.assertFalse(partners["Thanksgiving Schedule"]["playable"])
        self.assertEqual(shown["blend"]["interval_minutes"], 3)
        self.assertEqual(shown["schedule_states"],
                         {str(christmas): "playing", str(thanksgiving): "no_prerolls"})

    def test_the_blend_announcement_and_the_left_out_warning_are_logged_once(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True)
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving, blend_enabled=True)
        self.run_minutes(10)
        lines = [str(c.args[0]) for c in self.log.call_args_list]
        self.assertEqual(sum(line.startswith("BLEND MODE ACTIVATED") for line in lines), 1)
        self.assertEqual(sum("is left out" in line for line in lines), 1)

    def test_a_pick_plex_refused_is_dropped_and_the_next_tick_picks_again(self):
        # Before: a failed pick was kept as "held" and retried every tick, forever.
        self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True)
        self.schedule("Adult Swim", category_id=self.adult_swim, blend_enabled=True)
        FakePlex.refuse = ("AdultSwim_",)
        picks = iter([1, 0, 0, 0])
        with patch.object(scheduler_module.random, "choice", lambda items: items[next(picks) % len(items)]):
            self.run_minutes(1)
        self.assertEqual(len(FakePlex.writes), 1)
        self.assertIn("Christmas_", FakePlex.writes[0])
        self.assertIsNone(self.scheduler._blend_pending)

    def test_a_held_pick_is_still_kept_until_plex_takes_it(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True)
        self.schedule("Adult Swim", category_id=self.adult_swim, blend_enabled=True)
        self.defer[0] = True
        self.scheduler._deferred_write_since = START
        self.run_minutes(0)
        held = self.scheduler._blend_pending
        self.assertIsNotNone(held)
        self.run_minutes(3)
        self.assertEqual(self.scheduler._blend_pending, held)

    def test_a_blend_with_nothing_to_play_plays_nothing(self):
        # JB, November 6: nothing to play means nothing plays. Plex gets an
        # empty list once, rather than keeping the previous schedule's list.
        with self.Session() as db:
            other_empty = self.category(db, "Fall", 0)
            db.commit()
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving, blend_enabled=True)
        self.schedule("Fall Schedule", category_id=other_empty, blend_enabled=True)
        self.run_minutes(6)
        self.assertEqual(FakePlex.writes, [""], "one empty list, not one every rotation")
        shown = self.showing()
        self.assertEqual(shown["kind"], "blend")
        self.assertEqual(shown["title"], "Blend")
        self.assertEqual(shown["warnings"], [
            "None of the blended schedules has prerolls to play, so no prerolls play until one of them has some."])

    def test_a_schedule_without_blend_is_not_blending(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True)
        self.schedule("Adult Swim", category_id=self.adult_swim, blend_enabled=True)
        solo = self.schedule("Default", category_id=self.adult_swim, priority=9)
        self.run_minutes(0)
        self.assertEqual(self.showing()["schedule_states"][str(solo)], "not_blending")


class ScheduleTests(Harness):
    def test_an_empty_winner_plays_nothing_and_says_why(self):
        # Production before the blend: Thanksgiving (priority 7) beat Christmas
        # with an empty category, and Plex kept the night before's list all
        # day. JB: "have it do nothing". Plex now gets an empty list, once.
        christmas = self.schedule("Christmas Schedule", category_id=self.christmas, priority=5)
        thanksgiving = self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving, priority=7)
        self.run_minutes(2)
        self.assertEqual(FakePlex.writes, [""])
        shown = self.showing()
        self.assertEqual(shown["kind"], "schedule")
        self.assertEqual((shown["title"], shown["subtitle"], shown["preroll_count"]),
                         ("Thanksgiving Schedule", "Thanksgiving", 0))
        self.assertEqual(shown["warnings"], [
            "Thanksgiving has no enabled prerolls. No prerolls play until it has some."])
        self.assertEqual(shown["schedule_states"],
                         {str(christmas): "outranked", str(thanksgiving): "no_prerolls"})
        check = health_summary.showing_check(shown)
        self.assertEqual((check["key"], check["status"], check["value"]),
                         ("showing", "warn", "Thanksgiving: no prerolls"))
        self.assertEqual(check["detail"], shown["warnings"][0])
        self.assertIsNone(health_summary.showing_check({"warnings": []}))

    def test_the_log_no_longer_calls_an_empty_category_held_for_playback(self):
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving)
        self.run_minutes(2)
        lines = [str(c.args[0]) for c in self.log.call_args_list]
        self.assertFalse(any("held for playback" in line for line in lines), lines)

    def test_mode_is_the_schedules_playback_setting(self):
        self.schedule("Christmas in order", category_id=self.christmas, playlist=True)
        self.run_minutes(0)
        self.assertIn(",", FakePlex.writes[-1])
        self.assertEqual(self.showing()["mode"], "Sequential")

    def test_disabled_prerolls_are_not_counted(self):
        with self.Session() as db:
            mixed = self.category(db, "Mixed", 2, disabled=3)
            db.commit()
        self.schedule("Mixed", category_id=mixed)
        self.run_minutes(0)
        self.assertEqual(self.showing()["preroll_count"], 2)

    def test_a_sequence_schedule_shows_no_category_count(self):
        block = {"type": "random", "category_id": self.christmas, "count": 1}
        self.schedule("Movie night", category_id=self.adult_swim, sequence=[block])
        self.run_minutes(0)
        shown = self.showing()
        self.assertEqual((shown["subtitle"], shown["mode"], shown["preroll_count"]), ("Sequence", "Sequence", None))
        self.assertEqual(shown["warnings"], [])

    def test_an_exclusive_winner_is_flagged_and_the_rest_are_outranked(self):
        other = self.schedule("Christmas Schedule", category_id=self.christmas, priority=9)
        winner = self.schedule("Adult Swim Nightly", category_id=self.adult_swim, exclusive=True, priority=1)
        self.run_minutes(0)
        shown = self.showing()
        self.assertEqual((shown["title"], shown["exclusive"]), ("Adult Swim Nightly", True))
        self.assertEqual(shown["schedule_states"], {str(other): "outranked", str(winner): "playing"})

    def test_plex_refusing_a_category_with_prerolls_says_plex_is_behind(self):
        self.schedule("Christmas Schedule", category_id=self.christmas)
        FakePlex.refuse = ("Christmas_",)
        self.run_minutes(1)
        self.assertEqual(self.showing()["warnings"], [
            "Plex hasn't taken this change yet, so it's still playing its previous prerolls. "
            "NeXroll tries again every minute; System health shows whether Plex is reachable."])

    def test_jellyfin_only_says_nothing_plays(self):
        self.settings(plex_url=None, jellyfin_url="http://jellyfin.test")
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving)
        self.run_minutes(0)
        self.assertEqual(self.showing()["warnings"],
                         ["Thanksgiving has no enabled prerolls. No prerolls play until it has some."])

    def test_an_empty_winner_plays_again_once_it_has_prerolls(self):
        # The 5-minute verification re-applies the category when it fills up.
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving)
        self.run_minutes(0)
        self.assertEqual(FakePlex.writes, [""])
        with self.Session() as db:
            path = os.path.join(self.tmp.name, "turkey.mp4")
            with open(path, "wb") as handle:
                handle.write(b"x")
            db.add(models.Preroll(filename="turkey.mp4", path=path, category_id=self.thanksgiving, enabled=True))
            db.commit()
        self.scheduler._last_verification_time = None
        self.scheduler._verify_and_reapply_if_needed()
        self.assertIn("turkey.mp4", FakePlex.writes[-1])

    def test_a_cleared_pointer_after_an_edit_still_names_the_winner(self):
        self.schedule("Christmas Schedule", category_id=self.christmas)
        self.run_minutes(0)
        self.settings(active_schedule_id=None)
        self.assertEqual(self.showing()["title"], "Christmas Schedule")


class OutsideSchedulesTests(Harness):
    def test_a_fallback_category_is_not_named_after_another_schedule(self):
        # The old tile looked up "the last schedule on this category" and named it.
        self.schedule("Christmas evenings", category_id=self.christmas, hours=("18:00", "22:00"))
        self.settings(active_category=self.christmas, last_schedule_fallback=self.christmas)
        shown = self.showing()
        self.assertEqual(shown["kind"], "fallback")
        self.assertEqual((shown["title"], shown["subtitle"]), ("Christmas", "Fallback category (no schedule is running)"))

    def test_filler(self):
        with self.Session() as db:
            seq = models.SavedSequence(name="Gap filler", blocks=json.dumps([]))
            db.add(seq)
            db.commit()
            seq_id = seq.id
        self.settings(filler_active=f"category:{self.adult_swim}")
        shown = self.showing()
        self.assertEqual((shown["kind"], shown["title"], shown["preroll_count"]), ("filler", "Adult Swim", 3))
        self.assertEqual(shown["subtitle"], "Fallback filler (no schedule is running)")
        self.settings(filler_active=f"sequence:{seq_id}")
        self.assertEqual((self.showing()["title"], self.showing()["mode"]), ("Gap filler", "Sequence"))
        self.settings(filler_active=f"category:{self.thanksgiving}")
        self.assertEqual(self.showing()["warnings"], [
            "Thanksgiving has no enabled prerolls. No prerolls play until it has some."])

    def test_a_sequence_applied_by_hand(self):
        until = START + datetime.timedelta(minutes=15)
        self.settings(applied_sequence_id=3, applied_sequence_name="Trailers", override_expires_at=until)
        shown = self.showing()
        self.assertEqual((shown["kind"], shown["title"], shown["until"]), ("manual", "Trailers", until.isoformat()))

    def test_passive_cleared_and_nothing(self):
        self.settings(passive_mode=True)
        self.assertEqual(self.showing()["kind"], "passive")
        self.settings(passive_mode=False, clear_when_inactive=True)
        self.assertEqual(self.showing()["kind"], "cleared")
        self.settings(clear_when_inactive=False)
        shown = self.showing()
        self.assertEqual((shown["kind"], shown["title"], shown["up_next"]), ("none", None, None))


class UpNextTests(Harness):
    def test_the_next_schedule_takes_over(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, hours=("08:00", "18:00"))
        self.schedule("Adult Swim Nightly", category_id=self.adult_swim, hours=("23:30", "05:00"))
        nxt = self.showing()["up_next"]
        self.assertEqual((nxt["name"], nxt["at"], nxt["subtitle"]),
                         ("Adult Swim Nightly", "2026-11-06T23:30:00", "Adult Swim"))
        self.assertIsNone(nxt["note"])
        self.assertIsNone(nxt["warning"])

    def test_a_lower_priority_start_says_what_outranks_it(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, priority=9)
        self.schedule("Friday Night Movies", category_id=self.adult_swim, priority=3, hours=("20:00", "23:00"))
        self.assertEqual(self.showing()["up_next"]["note"],
                         "Won't play while Christmas Schedule runs (priority 9 over 3)")

    def test_an_exclusive_schedule_still_running_keeps_it_off(self):
        self.schedule("Movie Marathon", category_id=self.adult_swim, exclusive=True)
        self.schedule("Friday Night Movies", category_id=self.christmas, priority=10, hours=("20:00", "23:00"))
        self.assertEqual(self.showing()["up_next"]["note"], "Won't play while Movie Marathon (exclusive) runs")

    def test_joining_a_blend_names_only_partners_that_play(self):
        self.schedule("Christmas Schedule", category_id=self.christmas, blend_enabled=True)
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving, blend_enabled=True)
        self.schedule("Friday Night Movies", category_id=self.adult_swim, blend_enabled=True, hours=("20:00", "23:00"))
        self.assertEqual(self.showing()["up_next"]["note"], "Joins the blend with Christmas Schedule")

    def test_joining_a_blend_of_empty_schedules_is_taking_over(self):
        self.schedule("Thanksgiving Schedule", category_id=self.thanksgiving, blend_enabled=True)
        self.schedule("Friday Night Movies", category_id=self.adult_swim, blend_enabled=True, hours=("20:00", "23:00"))
        self.assertIsNone(self.showing()["up_next"]["note"])

    def test_a_next_schedule_with_nothing_to_play_is_flagged(self):
        self.schedule("Thanksgiving dinner", category_id=self.thanksgiving, hours=("17:00", "20:00"))
        self.assertEqual(self.showing()["up_next"]["warning"],
                         "Thanksgiving has no enabled prerolls, so it has nothing to play.")


if __name__ == "__main__":
    unittest.main()
