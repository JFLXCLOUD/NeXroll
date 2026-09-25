"""Issue #40: yearly metadata, playback windows, and upgrade compatibility."""
import datetime as dt
import ast
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload, Session
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend import scheduler as module
from backend import models
from backend.yearly_schedules import migrate_yearly_schedules
from tests.test_scheduler import make_schedule


class YearlyScheduleTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = module.Scheduler()

    def next_run(self, schedule, now):
        with patch.object(module, '_localized_now', return_value=now):
            return self.scheduler._calculate_next_run(schedule)

    def test_beta11_sentinel_end_is_not_an_expiration(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 10, 1),
                                 end_date=dt.datetime(2000, 10, 31, 23, 59))
        self.assertEqual(self.next_run(schedule, dt.datetime(2026, 9, 24)),
                         dt.datetime(2026, 10, 1))
        self.assertEqual(self.next_run(schedule, dt.datetime(2026, 11, 1)),
                         dt.datetime(2027, 10, 1))

    def test_legacy_real_years_recur_and_preserve_boundary_times(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2023, 12, 15, 18),
                                 end_date=dt.datetime(2024, 1, 15, 3))
        self.assertEqual(self.next_run(schedule, dt.datetime(2026, 9, 24)),
                         dt.datetime(2026, 12, 15, 18))
        self.assertTrue(self.scheduler._is_schedule_active(schedule, dt.datetime(2027, 1, 15, 2)))
        self.assertFalse(self.scheduler._is_schedule_active(schedule, dt.datetime(2027, 1, 15, 4)))

    def test_active_season_and_no_end_are_available_now(self):
        now = dt.datetime(2026, 10, 15, 12)
        for end in (dt.datetime(2000, 10, 31, 23, 59), None):
            schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 10, 1), end_date=end)
            self.assertEqual(self.next_run(schedule, now), now)

    def test_leap_boundary_does_not_disable_an_entire_season(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 2, 29),
                                 end_date=dt.datetime(2000, 3, 3, 23, 59))
        self.assertTrue(self.scheduler._is_schedule_active(schedule, dt.datetime(2027, 3, 1)))
        self.assertEqual(self.next_run(schedule, dt.datetime(2027, 2, 28)), dt.datetime(2027, 3, 1))

    def test_single_leap_day_skips_non_leap_years(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 2, 29, 18),
                                 end_date=dt.datetime(2000, 2, 29, 23, 59))
        self.assertEqual(self.next_run(schedule, dt.datetime(2025, 3, 1)), dt.datetime(2028, 2, 29, 18))

    def test_daily_window_within_season_uses_next_eligible_day(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 10, 1),
                                 end_date=dt.datetime(2000, 10, 31, 23, 59),
                                 recurrence_pattern='{"timeRange":{"start":"20:00","end":"22:00"}}')
        self.assertEqual(self.next_run(schedule, dt.datetime(2026, 10, 15, 23)), dt.datetime(2026, 10, 16, 20))

    def test_first_nights_overnight_tail_keeps_its_evening_boundary(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2000, 12, 15, 18),
                                 end_date=dt.datetime(2000, 12, 31, 23, 59),
                                 recurrence_pattern='{"timeRange":{"start":"22:00","end":"03:00"}}')
        self.assertTrue(self.scheduler._is_schedule_active(schedule, dt.datetime(2026, 12, 16, 1)))
        self.assertFalse(self.scheduler._is_schedule_active(schedule, dt.datetime(2026, 12, 15, 1)))

    def test_future_linked_yearly_holiday_keeps_first_year(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2027, 11, 25),
                                 end_date=dt.datetime(2027, 11, 25, 23, 59),
                                 holiday_name='Thanksgiving', holiday_country='US')
        with patch.object(self.scheduler, '_get_holiday_date', return_value=dt.date(2027, 11, 25)):
            self.assertEqual(self.next_run(schedule, dt.datetime(2026, 9, 24)), dt.datetime(2027, 11, 25))

    def test_holiday_outage_is_resolved_once_per_year_per_search_and_retried(self):
        schedule = make_schedule(type='yearly', start_date=dt.datetime(2026, 11, 25),
                                 end_date=dt.datetime(2026, 11, 25, 23, 59),
                                 holiday_name='Thanksgiving', holiday_country='US')
        with patch.object(self.scheduler, '_get_holiday_date', return_value=None) as lookup:
            for _ in range(2):
                self.assertEqual(self.next_run(schedule, dt.datetime(2026, 9, 24)), dt.datetime(2026, 11, 25))
            self.assertEqual(lookup.call_count, 2)


class YearlyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.scheduler = module.Scheduler()
        self.clock = patch.object(module, '_localized_now', return_value=dt.datetime(2026, 9, 24))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def test_migration_repairs_old_and_beta11_rows_without_losing_fields(self):
        category = models.Category(name='Seasonal')
        self.db.add(category)
        self.db.flush()
        for year, end in [(2023, dt.datetime(2024, 1, 15, 3)),
                          (2000, dt.datetime(2000, 1, 15, 3)), (2024, None),
                          (2000, dt.datetime(2000, 2, 29, 23, 59))]:
            row = models.Schedule(name=f'Legacy {year} {end}', type='yearly',
                start_date=dt.datetime(year, 12, 15, 18) if not end or end.month != 2 else dt.datetime(2000, 2, 29),
                end_date=end, category_id=category.id, fallback_category_id=category.id,
                is_active=False, playlist=True, priority=9, exclusive=True,
                blend_enabled=True, color='#112233', source_sequence_id=17,
                sequence='[{"type":"random","category_id":1}]', preroll_ids='[42]',
                recurrence_pattern='{"timeRange":{"start":"22:00","end":"03:00"}}',
                last_run=dt.datetime(2025, 12, 16))
            self.db.add(row)
        self.db.commit()
        columns = [c.name for c in models.Schedule.__table__.columns if c.name not in ('start_date', 'end_date', 'next_run')]
        before = {r.id: {c: getattr(r, c) for c in columns} for r in self.db.query(models.Schedule)}
        self.assertEqual(migrate_yearly_schedules(self.db, self.scheduler._calculate_next_run), 4)
        self.db.commit()
        self.db.expire_all()
        for row in self.db.query(models.Schedule):
            self.assertEqual({c: getattr(row, c) for c in columns}, before[row.id])
            self.assertEqual(row.start_date.year, 2000)
            self.assertIsNotNone(row.next_run)
            if row.end_date:
                self.assertEqual(row.end_date.year, 2000)
        self.assertEqual(migrate_yearly_schedules(self.db, self.scheduler._calculate_next_run), 0)

    def test_linked_holidays_and_other_types_keep_dates(self):
        for kind, linked in [('yearly', True), ('holiday', True), ('weekly', False)]:
            row = models.Schedule(name=kind, type=kind, start_date=dt.datetime(2027, 11, 25),
                end_date=dt.datetime(2027, 11, 25, 23, 59),
                holiday_name='Thanksgiving' if linked else None, holiday_country='US' if linked else None)
            self.db.add(row)
        self.db.commit()
        with patch.object(self.scheduler, '_get_holiday_date', return_value=dt.date(2027, 11, 25)):
            migrate_yearly_schedules(self.db, self.scheduler._calculate_next_run)
        self.db.commit()
        for row in self.db.query(models.Schedule):
            self.assertEqual(row.start_date.year, 2027)
            self.assertEqual(row.end_date.year, 2027)

    def test_failed_upgrade_can_roll_back_all_rows(self):
        for name in ['one', 'two']:
            self.db.add(models.Schedule(name=name, type='yearly', start_date=dt.datetime(2023, 10, 1)))
        self.db.commit()
        with self.assertRaises(RuntimeError):
            migrate_yearly_schedules(self.db, Mock(side_effect=[dt.datetime(2026, 10, 1), RuntimeError('interrupted')]))
        self.db.rollback()
        self.assertEqual([r.start_date.year for r in self.db.query(models.Schedule)], [2023, 2023])

    def test_real_create_edit_list_handlers_normalize_and_refresh(self):
        # Load the actual route bodies without importing main.py, which starts
        # background workers and probes installed media services at import time.
        wanted = {'ScheduleCreate', '_refresh_schedule_next_run', 'create_schedule', 'update_schedule', 'get_schedules'}
        source = ast.parse((Path(__file__).parents[1] / 'backend/main.py').read_text(encoding='utf-8'))
        nodes = [node for node in source.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted]
        self.scheduler.trigger_immediate_check = Mock()
        env = dict(datetime=dt, Optional=Optional, BaseModel=BaseModel, Session=Session,
                   Depends=Depends, get_db=lambda: self.db, app=FastAPI(), HTTPException=HTTPException,
                   models=models, scheduler=self.scheduler, joinedload=joinedload,
                   _validate_schedule_references=Mock(), _file_log=Mock(), log_event=Mock())
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'schedule_routes', 'exec'), env)
        payload = env['ScheduleCreate'](name='Halloween', type='yearly', start_date='2023-10-01T00:00', end_date='2023-10-31T23:59')
        created = env['create_schedule'](payload, self.db)
        self.assertEqual(created['start_date'], '2000-10-01T00:00:00')
        self.assertEqual(created['next_run'], '2026-10-01T00:00:00')
        payload.start_date, payload.end_date = '2024-12-15T18:00', '2025-01-15T03:00'
        env['update_schedule'](created['id'], payload, self.db)
        row = self.db.get(models.Schedule, created['id'])
        self.assertEqual(row.next_run, dt.datetime(2026, 12, 15, 18))
        # A persisted stale value must not survive a list request a year later.
        with patch.object(module, '_localized_now', return_value=dt.datetime(2027, 9, 24)):
            listed = env['get_schedules'](self.db)
        self.assertEqual(listed[0]['next_run'], '2027-12-15T18:00:00')
        self.assertEqual(row.next_run, dt.datetime(2026, 12, 15, 18))  # GET did not dirty the DB.
