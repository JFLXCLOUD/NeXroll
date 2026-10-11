"""How often each kind of schedule rewrites Plex's preroll list.

Plex holds a fixed list, so random picks (random blocks, random NeX-Up and
Library Trailers blocks) only change when NeXroll writes a new one. Each test
drives the real scheduler tick by tick on a fake clock, with a fake Plex that
records every write, and checks the rewrites come on the rotation interval:
not every tick, and not never.
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

START = datetime.datetime(2026, 10, 14, 20, 0)  # a Wednesday evening in October
TICK = datetime.timedelta(seconds=60)


class FakePlex:
    writes = []

    def __init__(self, url=None, token=None, *args, **kwargs):
        self.url = url
        self.token = token
        self.headers = {"X-Plex-Token": token or ""}
        self._verify = True

    def get_server_info(self):
        return {"platform": "windows" if os.name == "nt" else "linux"}

    def set_preroll(self, value):
        FakePlex.writes.append(value)
        return True

    def get_preroll(self):
        return FakePlex.writes[-1] if FakePlex.writes else ""


class RotationHarness(unittest.TestCase):
    def setUp(self):
        FakePlex.writes = []
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.clock = [START]
        self.defer = [False]

        with self.Session() as db:
            self.cat_a = self._category(db, "A", 6)
            self.cat_b = self._category(db, "B", 4)
            db.add(models.Setting(plex_url="http://plex.test", plex_token="token", timezone="UTC"))
            db.commit()

        self.scheduler = scheduler_module.Scheduler()
        patches = [
            patch.object(scheduler_module, "SessionLocal", self.Session),
            patch.object(scheduler_module, "_localized_now", lambda *a, **k: self.clock[0]),
            patch.object(scheduler_module, "PlexConnector", FakePlex),
            patch.object(scheduler_module, "_scheduler_log", MagicMock()),
            patch.object(scheduler_module, "_scheduler_verbose", MagicMock()),
            patch.object(self.scheduler, "_defer_preroll_write", lambda *a, **k: self.defer[0]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    # -- fixtures -----------------------------------------------------------

    def _category(self, db, name, count):
        category = models.Category(name=name)
        db.add(category)
        db.flush()
        for i in range(count):
            path = os.path.join(self.tmp.name, f"{name}_{i}.mp4")
            with open(path, "wb") as handle:
                handle.write(b"x")
            db.add(models.Preroll(filename=os.path.basename(path), path=path, category_id=category.id, enabled=True))
        db.flush()
        return category.id

    def _preroll_ids(self, category_id):
        with self.Session() as db:
            return [p.id for p in db.query(models.Preroll).filter(models.Preroll.category_id == category_id)]

    def random_block(self, category_id=None, count=1):
        return {"type": "random", "category_id": category_id or self.cat_a, "count": count}

    def fixed_block(self):
        return {"type": "fixed", "preroll_ids": self._preroll_ids(self.cat_b)[:2]}

    def add_schedule(self, *, category_id=None, sequence=None, type="daily", pattern=None,
                     start=None, end=None, **extra):
        with self.Session() as db:
            schedule = models.Schedule(
                name=extra.pop("name", f"{type} schedule"),
                type=type,
                start_date=start or (START - datetime.timedelta(days=1)),
                end_date=end,
                category_id=category_id,
                sequence=json.dumps(sequence) if sequence is not None else None,
                recurrence_pattern=json.dumps(pattern) if pattern else None,
                is_active=True,
                **extra,
            )
            db.add(schedule)
            db.commit()
            return schedule.id

    def set_filler(self, **fields):
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            setting.filler_enabled = True
            for key, value in fields.items():
                setattr(setting, key, value)
            db.commit()

    def save_sequence(self, blocks):
        with self.Session() as db:
            seq = models.SavedSequence(name="Filler", blocks=json.dumps(blocks))
            db.add(seq)
            db.commit()
            return seq.id

    # -- driving ------------------------------------------------------------

    def run_minutes(self, minutes):
        """One scheduler tick per minute, `minutes` + 1 ticks including now."""
        for _ in range(minutes + 1):
            self.scheduler._check_and_execute_schedules_locked()
            self.clock[0] += TICK

    def expected_rotations(self, minutes):
        """Writes for a rotating list over `minutes`: the first apply, then one per interval."""
        return 1 + (minutes * 60) // int(self.scheduler._rotation_interval_seconds)


class ScheduleRotationTests(RotationHarness):
    def test_rotation_interval_is_three_minutes(self):
        self.assertEqual(self.scheduler._rotation_interval_seconds, 180)

    def test_a_sequence_schedule_with_a_random_block_rotates_on_the_interval(self):
        self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(12))
        self.assertGreater(len(set(FakePlex.writes)), 1, "random picks never changed")

    def test_a_sequence_of_fixed_blocks_is_written_once(self):
        self.add_schedule(sequence=[self.fixed_block()])
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), 1)

    def test_a_category_schedule_with_a_random_sequence_rotates(self):
        self.add_schedule(category_id=self.cat_a, sequence=[self.fixed_block(), self.random_block()])
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(12))

    def test_a_random_category_schedule_is_written_once(self):
        # Plex gets the whole category and picks before each movie itself.
        self.add_schedule(category_id=self.cat_a)
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), 1)
        self.assertEqual(FakePlex.writes[0].count(";"), 5)

    def test_a_random_trailer_block_rotates(self):
        block = {"type": "nexup_trailers", "mode": "random", "count": 1, "source": "movies"}
        self.add_schedule(sequence=[self.random_block(), block])
        self.run_minutes(6)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(6))

    def test_an_exclusive_winner_rotates(self):
        self.add_schedule(category_id=self.cat_b, priority=9, name="loser")
        self.add_schedule(sequence=[self.random_block()], exclusive=True, priority=5, name="winner")
        self.run_minutes(9)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(9))
        self.assertTrue(all("A_" in w for w in FakePlex.writes))

    def test_every_schedule_type_rotates(self):
        today = START.date()
        cases = {
            "daily": dict(type="daily", pattern={"timeRange": {"start": "18:00", "end": "23:00"}}),
            "weekly": dict(type="weekly", pattern={"weekDays": ["wednesday"]}),
            "monthly": dict(type="monthly", pattern={"months": [10], "monthDays": [today.day]}),
            "yearly": dict(type="yearly", start=datetime.datetime(2000, 10, 1), end=datetime.datetime(2000, 10, 31, 23, 59)),
            "holiday": dict(type="holiday", start=datetime.datetime(2026, 10, 13), end=datetime.datetime(2026, 10, 15, 23, 59)),
        }
        for name, kwargs in cases.items():
            with self.subTest(schedule_type=name):
                FakePlex.writes = []
                with self.Session() as db:
                    db.query(models.Schedule).delete()
                    setting = db.query(models.Setting).first()
                    setting.active_schedule_id = None
                    setting.active_category = None
                    db.commit()
                self.scheduler = type(self.scheduler)()
                with patch.object(self.scheduler, "_defer_preroll_write", lambda *a, **k: False):
                    self.add_schedule(sequence=[self.random_block()], name=name, **kwargs)
                    self.run_minutes(6)
                self.assertEqual(len(FakePlex.writes), self.expected_rotations(6))

    def test_a_sequence_schedule_that_wins_back_is_applied_again(self):
        # X applies, Y outranks it for a minute, then X wins again inside one
        # rotation interval: Plex still has Y's list, so X must be rewritten.
        x = self.add_schedule(sequence=[self.fixed_block()], name="X", priority=5)
        self.run_minutes(0)
        y = self.add_schedule(sequence=[self.random_block(self.cat_a)], name="Y", priority=9)
        self.run_minutes(0)
        with self.Session() as db:
            db.query(models.Schedule).filter(models.Schedule.id == y).first().is_active = False
            db.commit()
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 3)
        self.assertEqual(FakePlex.writes[-1], FakePlex.writes[0])
        self.assertIsNotNone(x)

    def test_rotations_stay_out_of_the_logs_events(self):
        log = scheduler_module._scheduler_log
        self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(6)
        successes = [c for c in log.call_args_list if str(c.args[0]).startswith("SUCCESS setting sequence")]
        self.assertEqual(len(successes), self.expected_rotations(6))
        self.assertTrue(successes[0].kwargs.get("event"), "the first apply is an event")
        self.assertFalse(any(c.kwargs.get("event") for c in successes[1:]), "rotations are not")

    def test_a_held_rotation_is_retried_until_it_lands(self):
        self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(0)  # first apply
        self.defer[0] = True
        self.run_minutes(5)  # due at 3 min, held
        self.assertEqual(len(FakePlex.writes), 1)
        self.defer[0] = False
        self.run_minutes(0)  # minute 6: lands now
        self.assertEqual(len(FakePlex.writes), 2)

    def test_a_held_category_change_lands_on_the_next_free_tick(self):
        # Production, October 9: the switch to a category schedule was held by
        # playback and only retried by the five-minute verification.
        self.add_schedule(category_id=self.cat_a, name="evening", priority=5)
        self.run_minutes(0)
        self.add_schedule(category_id=self.cat_b, name="late night", priority=9)
        self.defer[0] = True
        self.run_minutes(2)
        self.assertEqual(len(FakePlex.writes), 1)
        self.defer[0] = False
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertIn("B_", FakePlex.writes[-1])
        self.run_minutes(5)
        self.assertEqual(len(FakePlex.writes), 2, "written once it landed, not again")

    def test_a_held_verification_reapply_lands_on_the_next_free_tick(self):
        # Production, October 11: verification found Plex on the wrong list,
        # the guard held the fix, and only the next verification (5 minutes
        # later) would have retried it.
        self.add_schedule(category_id=self.cat_a)
        self.run_minutes(0)
        FakePlex.writes.append("someone else's list")
        self.defer[0] = True
        self.scheduler._last_verification_time = None
        self.scheduler._deferred_write_since = self.clock[0]
        self.scheduler._verify_and_reapply_if_needed()
        self.assertEqual(len(FakePlex.writes), 2)
        self.defer[0] = False
        self.scheduler._deferred_write_since = None
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 3)
        self.assertIn("A_", FakePlex.writes[-1])

    def test_a_rotation_plex_did_not_take_is_retried_when_jellyfin_is_also_set_up(self):
        # Jellyfin pulls, so the apply still "succeeds"; Plex must not lose its turn.
        with self.Session() as db:
            db.query(models.Setting).first().jellyfin_url = "http://jellyfin.test"
            db.commit()
        self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(0)
        self.defer[0] = True
        self.run_minutes(3)
        self.defer[0] = False
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)


class FillerAndBlendRotationTests(RotationHarness):
    def test_a_filler_category_is_written_once(self):
        self.set_filler(filler_type="category", filler_category_id=self.cat_a)
        self.run_minutes(10)
        self.assertEqual(len(FakePlex.writes), 1)

    def test_a_filler_sequence_with_a_random_block_rotates_on_the_interval(self):
        seq_id = self.save_sequence([self.random_block()])
        self.set_filler(filler_type="sequence", filler_sequence_id=seq_id)
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(12))

    def test_a_fixed_filler_sequence_is_written_once(self):
        seq_id = self.save_sequence([self.fixed_block()])
        self.set_filler(filler_type="sequence", filler_sequence_id=seq_id)
        self.run_minutes(10)
        self.assertEqual(len(FakePlex.writes), 1)

    def test_leaving_filler_for_a_schedule_applies_the_schedule(self):
        self.set_filler(filler_type="category", filler_category_id=self.cat_b)
        self.run_minutes(1)
        self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertIn("A_", FakePlex.writes[-1])

    def test_returning_to_filler_applies_it_again(self):
        self.set_filler(filler_type="category", filler_category_id=self.cat_b)
        schedule_id = self.add_schedule(sequence=[self.random_block()])
        self.run_minutes(1)
        with self.Session() as db:
            db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first().is_active = False
            db.commit()
        self.run_minutes(3)
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertIn("B_", FakePlex.writes[-1])

    def test_blended_category_schedules_switch_on_the_interval_not_every_tick(self):
        self.add_schedule(category_id=self.cat_a, blend_enabled=True, name="blend A")
        self.add_schedule(category_id=self.cat_b, blend_enabled=True, name="blend B")
        self.run_minutes(30)
        self.assertLessEqual(len(FakePlex.writes), self.expected_rotations(30))

    def test_a_blend_picks_again_as_soon_as_its_members_change(self):
        self.add_schedule(category_id=self.cat_a, blend_enabled=True, name="blend A")
        self.add_schedule(category_id=self.cat_b, blend_enabled=True, name="blend B")
        self.run_minutes(0)
        before = len(FakePlex.writes)
        self.add_schedule(sequence=[self.random_block(self.cat_a)], blend_enabled=True, name="blend C")
        with patch.object(scheduler_module.random, "choice", lambda items: items[-1]):
            self.run_minutes(0)
        self.assertEqual(len(FakePlex.writes), before + 1)

    def test_blended_sequences_re_pick_on_the_interval(self):
        self.add_schedule(sequence=[self.random_block(self.cat_a)], blend_enabled=True, name="blend A")
        self.add_schedule(sequence=[self.random_block(self.cat_b)], blend_enabled=True, name="blend B")
        self.run_minutes(12)
        self.assertEqual(len(FakePlex.writes), self.expected_rotations(12))


if __name__ == "__main__":
    unittest.main()
