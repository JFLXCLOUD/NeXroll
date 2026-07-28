import datetime
import json
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend import scheduler as scheduler_module


def make_schedule(**overrides):
    values = {
        "id": 1,
        "name": "Test schedule",
        "type": "weekly",
        "start_date": datetime.datetime(2026, 1, 1),
        "end_date": None,
        "recurrence_pattern": None,
        "holiday_name": None,
        "holiday_country": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ScheduleWindowTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = scheduler_module.Scheduler()

    def test_weekly_overnight_window_uses_the_starting_weekday(self):
        schedule = make_schedule(
            recurrence_pattern=json.dumps({
                "weekDays": ["friday"],
                "timeRange": {"start": "22:00", "end": "03:00"},
            })
        )

        self.assertTrue(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2026, 8, 1, 1, 0))
        )  # Saturday morning belongs to Friday night's window.
        self.assertFalse(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2026, 7, 31, 1, 0))
        )  # Friday morning belongs to Thursday night's window.

    def test_monthly_overnight_window_uses_the_starting_month_and_day(self):
        schedule = make_schedule(
            type="monthly",
            start_date=datetime.datetime(2000, 1, 1),
            recurrence_pattern=json.dumps({
                "months": [1],
                "monthDays": [31],
                "timeRange": {"start": "22:00", "end": "03:00"},
            }),
        )

        self.assertTrue(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2026, 2, 1, 1, 0))
        )
        self.assertFalse(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2026, 1, 31, 1, 0))
        )

    def test_yearly_overnight_window_can_cross_new_year(self):
        schedule = make_schedule(
            type="yearly",
            start_date=datetime.datetime(2000, 12, 31, 0, 0),
            end_date=datetime.datetime(2000, 12, 31, 23, 59),
            recurrence_pattern=json.dumps({
                "timeRange": {"start": "22:00", "end": "03:00"},
            }),
        )

        self.assertTrue(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2027, 1, 1, 1, 0))
        )
        self.assertFalse(
            self.scheduler._is_schedule_active(schedule, datetime.datetime(2026, 12, 31, 1, 0))
        )

    def test_future_pinned_linked_holiday_does_not_run_a_year_early(self):
        schedule = make_schedule(
            type="holiday",
            start_date=datetime.datetime(2027, 11, 25),
            end_date=datetime.datetime(2027, 11, 25, 23, 59),
            holiday_name="Thanksgiving",
            holiday_country="US",
        )

        with patch.object(
            self.scheduler,
            "_get_holiday_date",
            return_value=datetime.date(2026, 11, 26),
        ) as holiday_lookup:
            self.assertFalse(
                self.scheduler._is_schedule_active(
                    schedule,
                    datetime.datetime(2026, 11, 26, 12, 0),
                )
            )

        holiday_lookup.assert_not_called()

    def test_future_static_holiday_does_not_run_a_year_early(self):
        schedule = make_schedule(
            type="holiday",
            start_date=datetime.datetime(2027, 7, 4),
            end_date=datetime.datetime(2027, 7, 4, 23, 59),
        )

        self.assertFalse(
            self.scheduler._is_schedule_active(
                schedule,
                datetime.datetime(2026, 7, 4, 12, 0),
            )
        )


class NextRunTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = scheduler_module.Scheduler()

    def test_monthly_next_run_uses_recurrence_days_and_skips_invalid_dates(self):
        schedule = make_schedule(
            type="monthly",
            start_date=datetime.datetime(2000, 1, 1),
            recurrence_pattern=json.dumps({
                "months": [2, 3],
                "monthDays": [31],
                "timeRange": {"start": "20:30", "end": "22:00"},
            }),
        )
        now = datetime.datetime(2026, 2, 1, 12, 0)

        with patch.object(scheduler_module, "_localized_now", return_value=now):
            next_run = self.scheduler._calculate_next_run(schedule)

        self.assertEqual(next_run, datetime.datetime(2026, 3, 31, 20, 30))

    def test_monthly_next_run_handles_sparse_leap_day_configuration(self):
        schedule = make_schedule(
            type="monthly",
            start_date=datetime.datetime(2000, 1, 1),
            recurrence_pattern=json.dumps({"months": [2], "monthDays": [29]}),
        )

        with patch.object(
            scheduler_module, "_localized_now", return_value=datetime.datetime(2025, 3, 1)
        ):
            next_run = self.scheduler._calculate_next_run(schedule)

        self.assertEqual(next_run, datetime.datetime(2028, 2, 29))

    def test_yearly_next_run_skips_non_leap_years(self):
        schedule = make_schedule(
            type="yearly",
            start_date=datetime.datetime(2000, 2, 29, 18, 0),
        )

        with patch.object(
            scheduler_module, "_localized_now", return_value=datetime.datetime(2025, 3, 1)
        ):
            next_run = self.scheduler._calculate_next_run(schedule)

        self.assertEqual(next_run, datetime.datetime(2028, 2, 29, 18, 0))


class SequentialSequenceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()

        def media_path(name):
            path = os.path.join(self.temp_dir.name, name)
            with open(path, "wb") as media_file:
                media_file.write(b"test")
            return path

        with self.Session() as db:
            category = models.Category(name="Sequence category")
            other = models.Category(name="Other category")
            db.add_all([category, other])
            db.flush()

            primary = models.Preroll(
                filename="primary.mp4",
                path=media_path("primary.mp4"),
                category_id=category.id,
                enabled=True,
            )
            disabled = models.Preroll(
                filename="disabled.mp4",
                path=media_path("disabled.mp4"),
                category_id=category.id,
                enabled=False,
            )
            secondary = models.Preroll(
                filename="secondary.mp4",
                path=media_path("secondary.mp4"),
                category_id=other.id,
                enabled=True,
                categories=[category],
            )
            missing = models.Preroll(
                filename="missing.mp4",
                path=os.path.join(self.temp_dir.name, "missing.mp4"),
                category_id=category.id,
                enabled=True,
            )
            third = models.Preroll(
                filename="third.mp4",
                path=media_path("third.mp4"),
                category_id=category.id,
                enabled=True,
            )
            db.add_all([primary, disabled, secondary, missing, third])
            db.flush()

            blocks = [{
                "type": "sequential",
                "categoryId": str(category.id),
                "count": 3,
            }]
            saved_sequence = models.SavedSequence(
                name="Sequential only",
                blocks=json.dumps(blocks),
            )
            db.add_all([
                saved_sequence,
                models.Setting(plex_url="http://plex.invalid", plex_token="token"),
            ])
            db.commit()

            self.category_id = category.id
            self.saved_sequence_id = saved_sequence.id
            self.expected_ids = [primary.id, secondary.id, third.id]
            self.expected_paths = [
                os.path.abspath(primary.path),
                os.path.abspath(secondary.path),
                os.path.abspath(third.path),
            ]

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_sequential_block_uses_stable_id_order_and_skips_ineligible_rows(self):
        with self.Session() as db:
            resolved = scheduler_module.resolve_category_sequence_block(
                {
                    "type": "sequential",
                    "categoryId": str(self.category_id),
                    "count": 3,
                },
                db,
            )
            self.assertEqual([preroll.id for preroll in resolved], self.expected_ids)
            fallback_resolved = scheduler_module.resolve_category_sequence_block(
                {"type": "sequential", "count": 3},
                db,
                fallback_category_id=self.category_id,
            )
            self.assertEqual(
                [preroll.id for preroll in fallback_resolved],
                self.expected_ids,
            )
            self.assertEqual(
                scheduler_module.resolve_category_sequence_block(
                    {"type": "sequential", "category_id": "invalid", "count": 2},
                    db,
                ),
                [],
            )
            self.assertEqual(
                scheduler_module.resolve_category_sequence_block(
                    {"type": "sequential", "category_id": 999999, "count": 2},
                    db,
                ),
                [],
            )

    def test_sequential_only_schedule_and_saved_filler_apply_identically(self):
        connector = MagicMock()
        connector.get_server_info.return_value = {"platform": "Windows"}
        connector.set_preroll.return_value = True
        schedule = make_schedule(
            name="Sequential schedule",
            category_id=None,
            sequence=json.dumps([{
                "type": "sequential",
                "categoryId": str(self.category_id),
                "count": 3,
            }]),
        )

        with self.Session() as db, patch.object(
            scheduler_module,
            "PlexConnector",
            return_value=connector,
        ):
            scheduler = scheduler_module.Scheduler()
            self.assertTrue(scheduler._apply_schedule_sequence_to_plex(schedule, db))
            self.assertTrue(scheduler._apply_saved_sequence_to_plex(self.saved_sequence_id, db))

        expected = ",".join(self.expected_paths)
        self.assertEqual(
            [call.args[0] for call in connector.set_preroll.call_args_list],
            [expected, expected],
        )


class SchedulerTransitionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.now = datetime.datetime(2026, 7, 31, 23, 0)
        self.scheduler = scheduler_module.Scheduler()

    def tearDown(self):
        self.engine.dispose()

    def _seed_categories(self, db):
        primary = models.Category(name="Primary")
        fallback = models.Category(name="Fallback")
        db.add_all([primary, fallback])
        db.flush()
        return primary, fallback

    def _run_check(self):
        return patch.multiple(
            scheduler_module,
            SessionLocal=self.Session,
            _localized_now=MagicMock(return_value=self.now),
            _scheduler_log=MagicMock(),
            _scheduler_verbose=MagicMock(),
        )

    def test_concurrent_ticks_are_serialized(self):
        first_entered = threading.Event()
        release_first = threading.Event()
        second_entered = threading.Event()
        calls = []

        def fake_check():
            calls.append(threading.current_thread().name)
            if len(calls) == 1:
                first_entered.set()
                release_first.wait(timeout=1)
            else:
                second_entered.set()

        with patch.object(self.scheduler, "_check_and_execute_schedules_locked", side_effect=fake_check):
            first = threading.Thread(target=self.scheduler._check_and_execute_schedules, name="first")
            second = threading.Thread(target=self.scheduler._check_and_execute_schedules, name="second")
            first.start()
            self.assertTrue(first_entered.wait(timeout=1))
            second.start()
            self.assertFalse(second_entered.wait(timeout=0.05))
            release_first.set()
            first.join(timeout=1)
            second.join(timeout=1)

        self.assertTrue(second_entered.is_set())
        self.assertEqual(calls, ["first", "second"])

    def test_linked_holiday_dates_refresh_for_the_current_year_but_keep_future_pins(self):
        with self.Session() as db:
            current = models.Schedule(
                name="Current Thanksgiving",
                type="holiday",
                start_date=datetime.datetime(2025, 11, 27),
                end_date=datetime.datetime(2025, 11, 27, 23, 59),
                holiday_name="Thanksgiving",
                holiday_country="US",
                is_active=True,
            )
            future = models.Schedule(
                name="Future Thanksgiving",
                type="holiday",
                start_date=datetime.datetime(2027, 11, 25),
                end_date=datetime.datetime(2027, 11, 25, 23, 59),
                holiday_name="Thanksgiving",
                holiday_country="US",
                is_active=True,
            )
            db.add_all([current, future])
            db.commit()
            current_id, future_id = current.id, future.id

        refresh_now = datetime.datetime(2026, 1, 2, 8, 0)
        with self.Session() as db, patch.object(
            self.scheduler,
            "_get_holiday_date",
            return_value=datetime.date(2026, 11, 26),
        ) as holiday_lookup:
            self.scheduler._refresh_linked_holiday_dates_if_needed(db, refresh_now)

        with self.Session() as db:
            current = db.get(models.Schedule, current_id)
            future = db.get(models.Schedule, future_id)
            self.assertEqual(current.start_date, datetime.datetime(2026, 11, 26))
            self.assertEqual(current.end_date, datetime.datetime(2026, 11, 26, 23, 59, 59))
            self.assertEqual(future.start_date, datetime.datetime(2027, 11, 25))
        holiday_lookup.assert_called_once_with("Thanksgiving", "US", 2026)

    def test_same_category_fallback_reapplies_and_clears_stale_schedule_pointer(self):
        with self.Session() as db:
            primary, _ = self._seed_categories(db)
            ended = models.Schedule(
                name="Ended",
                type="daily",
                start_date=self.now - datetime.timedelta(days=2),
                end_date=self.now - datetime.timedelta(days=1),
                category_id=primary.id,
                fallback_category_id=primary.id,
                is_active=True,
            )
            db.add(ended)
            db.flush()
            db.add(models.Setting(
                active_category=primary.id,
                active_schedule_id=ended.id,
                last_schedule_fallback=primary.id,
            ))
            db.commit()
            primary_id, ended_id = primary.id, ended.id

        self.scheduler._last_logged_state = f"schedule_active:{ended_id}:{primary_id}"
        with self._run_check(), patch.object(
            self.scheduler, "_apply_category_to_plex", return_value=True
        ) as apply_category:
            self.scheduler._check_and_execute_schedules()

        apply_category.assert_called_once()
        self.assertEqual(apply_category.call_args.args[0], primary_id)
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            self.assertIsNone(setting.active_schedule_id)
            self.assertIsNone(setting.filler_active)

    def test_active_schedule_reapplies_when_leaving_same_category_filler_state(self):
        with self.Session() as db:
            primary, _ = self._seed_categories(db)
            active = models.Schedule(
                name="Active",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=primary.id,
                is_active=True,
            )
            db.add(active)
            db.flush()
            db.add(models.Setting(
                active_category=primary.id,
                active_schedule_id=active.id,
                filler_active=f"category:{primary.id}",
            ))
            db.commit()
            primary_id, active_id = primary.id, active.id

        with self._run_check(), patch.object(
            self.scheduler, "_apply_category_to_plex", return_value=True
        ) as apply_category:
            self.scheduler._check_and_execute_schedules()

        apply_category.assert_called_once()
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            self.assertEqual(setting.active_schedule_id, active_id)
            self.assertIsNone(setting.filler_active)

    def test_category_backed_sequence_retries_when_no_apply_marker_exists(self):
        with self.Session() as db:
            primary, _ = self._seed_categories(db)
            active = models.Schedule(
                name="Sequence",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=primary.id,
                sequence=json.dumps([{"type": "fixed", "preroll_id": 999}]),
                is_active=True,
            )
            db.add(active)
            db.flush()
            db.add(models.Setting(active_category=primary.id, active_schedule_id=active.id))
            db.commit()
            active_id = active.id

        with self._run_check(), patch.object(
            self.scheduler, "_apply_schedule_sequence_to_plex", return_value=True
        ) as apply_sequence:
            self.scheduler._check_and_execute_schedules()

        apply_sequence.assert_called_once()
        self.assertEqual(self.scheduler._last_rotation_time[active_id], self.now)

    def test_random_nexup_sequence_rotates_after_the_rotation_interval(self):
        with self.Session() as db:
            primary, _ = self._seed_categories(db)
            active = models.Schedule(
                name="Random trailers",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=primary.id,
                sequence=json.dumps([{
                    "type": "nexup_trailers",
                    "source": "both",
                    "mode": "random",
                    "count": 2,
                }]),
                is_active=True,
            )
            db.add(active)
            db.flush()
            db.add(models.Setting(active_category=primary.id, active_schedule_id=active.id))
            db.commit()
            active_id = active.id

        self.scheduler._last_rotation_time[active_id] = self.now - datetime.timedelta(seconds=601)
        with self._run_check(), patch.object(
            self.scheduler, "_apply_schedule_sequence_to_plex", return_value=True
        ) as apply_sequence:
            self.scheduler._check_and_execute_schedules()

        apply_sequence.assert_called_once()
        self.assertEqual(self.scheduler._last_rotation_time[active_id], self.now)

    def test_sequence_only_schedule_is_a_valid_winner(self):
        with self.Session() as db:
            active = models.Schedule(
                name="Sequence only",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=None,
                sequence=json.dumps([{"type": "fixed", "preroll_id": 999}]),
                is_active=True,
            )
            db.add(active)
            db.flush()
            db.add(models.Setting())
            db.commit()
            active_id = active.id

        log = MagicMock()
        with patch.multiple(
            scheduler_module,
            SessionLocal=self.Session,
            _localized_now=MagicMock(return_value=self.now),
            _scheduler_log=log,
            _scheduler_verbose=MagicMock(),
        ), patch.object(
            self.scheduler, "_apply_schedule_sequence_to_plex", return_value=True
        ) as apply_sequence:
            self.scheduler._check_and_execute_schedules()

        apply_sequence.assert_called_once()
        self.assertFalse(any("no category_id" in str(call).lower() for call in log.call_args_list))
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            self.assertEqual(setting.active_schedule_id, active_id)
            self.assertIsNone(setting.active_category)

    def test_legacy_null_priority_does_not_crash_winner_selection(self):
        with self.Session() as db:
            primary, _ = self._seed_categories(db)
            active = models.Schedule(
                name="Legacy priority",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=primary.id,
                is_active=True,
            )
            db.add(active)
            db.flush()
            active_id = active.id
            db.add(models.Setting())
            db.commit()
            db.execute(
                models.Schedule.__table__.update()
                .where(models.Schedule.id == active_id)
                .values(priority=None)
            )
            db.commit()

        with self._run_check(), patch.object(
            self.scheduler, "_apply_category_to_plex", return_value=True
        ) as apply_category:
            self.scheduler._check_and_execute_schedules()

        apply_category.assert_called_once()


class VerificationClockTests(unittest.TestCase):
    def test_verification_uses_the_configured_timezone_clock(self):
        scheduler = scheduler_module.Scheduler()
        db = MagicMock()
        db.query.return_value.first.return_value = None
        configured_now = datetime.datetime(2026, 8, 1, 1, 0)

        with patch.object(
            scheduler_module, "_localized_now", return_value=configured_now
        ) as localized_now, patch.object(scheduler_module, "SessionLocal", return_value=db):
            scheduler._verify_and_reapply_if_needed()

        localized_now.assert_called_once_with()
        db.close.assert_called_once_with()


class VerificationModeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.now = datetime.datetime(2026, 7, 31, 23, 0)

        with self.Session() as db:
            category = models.Category(name="Playlist")
            db.add(category)
            db.flush()
            schedule = models.Schedule(
                name="Playlist schedule",
                type="daily",
                start_date=self.now - datetime.timedelta(days=1),
                category_id=category.id,
                playlist=True,
                is_active=True,
            )
            db.add(schedule)
            db.flush()
            db.add_all([
                models.Preroll(filename="one.mp4", path="one.mp4", category_id=category.id, enabled=True),
                models.Preroll(filename="two.mp4", path="two.mp4", category_id=category.id, enabled=True),
                models.Preroll(filename="disabled.mp4", path="disabled.mp4", category_id=category.id, enabled=False),
                models.Setting(
                    plex_url="http://plex.invalid",
                    active_category=category.id,
                    active_schedule_id=schedule.id,
                ),
            ])
            db.commit()
            self.category_id = category.id

    def tearDown(self):
        self.engine.dispose()

    def _patch_verification(self, connector):
        return patch.multiple(
            scheduler_module,
            SessionLocal=self.Session,
            _localized_now=MagicMock(return_value=self.now),
            PlexConnector=MagicMock(return_value=connector),
            _scheduler_log=MagicMock(),
            _scheduler_verbose=MagicMock(),
        )

    def test_verification_uses_playlist_delimiter_and_ignores_disabled_prerolls(self):
        connector = MagicMock()
        expected = ",".join([os.path.abspath("one.mp4"), os.path.abspath("two.mp4")])
        connector.get_preroll.return_value = expected
        scheduler = scheduler_module.Scheduler()

        with self._patch_verification(connector), patch.object(
            scheduler, "_apply_category_to_plex", return_value=True
        ) as apply_category:
            scheduler._verify_and_reapply_if_needed()

        apply_category.assert_not_called()

    def test_verification_reapply_preserves_the_tracked_schedule_mode(self):
        connector = MagicMock()
        connector.get_preroll.return_value = "wrong"
        scheduler = scheduler_module.Scheduler()

        with self._patch_verification(connector), patch.object(
            scheduler, "_apply_category_to_plex", return_value=True
        ) as apply_category:
            scheduler._verify_and_reapply_if_needed()

        apply_category.assert_called_once()
        self.assertEqual(apply_category.call_args.args[0], self.category_id)
        self.assertTrue(apply_category.call_args.kwargs["schedule"].playlist)


if __name__ == "__main__":
    unittest.main()
