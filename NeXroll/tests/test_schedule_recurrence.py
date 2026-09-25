import datetime as dt
import ast
import asyncio
import json
from pathlib import Path
from typing import Optional
import unittest
from unittest.mock import patch, Mock

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, joinedload

from backend import scheduler as module
from backend import models
from backend.schedule_recurrence import migrate_schedules, refresh_linked_holidays
from tests.test_scheduler import make_schedule


class RecurrenceParityTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = module.Scheduler()

    def next(self, schedule, now):
        with patch.object(module, '_localized_now', return_value=now):
            result = self.scheduler._calculate_next_run(schedule)
        if result:
            self.assertTrue(self.scheduler._is_schedule_active(schedule, result), result)
            self.assertGreaterEqual(result, now)
        return result

    def test_daily_first_day_cannot_run_before_start_boundary(self):
        s = make_schedule(type='daily', start_date=dt.datetime(2026, 10, 1, 18),
                          recurrence_pattern='{"timeRange":{"start":"12:00","end":"22:00"}}')
        self.assertEqual(self.next(s, dt.datetime(2026, 9, 24)), dt.datetime(2026, 10, 1, 18))

    def test_weekly_applies_all_saved_constraints(self):
        s = make_schedule(type='weekly', recurrence_pattern=json.dumps({
            'weekDays': ['monday'], 'months': [11], 'timeRange': {'start': '20:00'}}))
        self.assertEqual(self.next(s, dt.datetime(2026, 9, 24)), dt.datetime(2026, 11, 2, 20))

    def test_monthly_preserves_future_start_and_end(self):
        s = make_schedule(type='monthly', start_date=dt.datetime(2027, 6, 15, 18),
                          end_date=dt.datetime(2027, 7, 1),
                          recurrence_pattern='{"months":[6],"monthDays":[15],"timeRange":{"start":"20:00"}}')
        self.assertEqual(self.next(s, dt.datetime(2026, 1, 1)), dt.datetime(2027, 6, 15, 20))

    def test_legacy_monthly_without_day_filter_is_every_day(self):
        s = make_schedule(type='monthly', start_date=dt.datetime(2020, 1, 1),
                          recurrence_pattern='{"months":[10]}')
        now = dt.datetime(2026, 10, 15, 12)
        self.assertEqual(self.next(s, now), now)

    def test_numeric_strings_and_weekday_case_are_compatible(self):
        s = make_schedule(type='monthly', recurrence_pattern='{"months":["10"],"monthDays":["5"],"weekDays":["Monday"]}')
        self.assertTrue(self.scheduler._is_schedule_active(s, dt.datetime(2026, 10, 5, 12)))

    def test_malformed_recurrence_never_crashes_or_becomes_all_day(self):
        for pattern in ['[]', 'null', '{bad', '{"timeRange":{"start":"25:90"}}', '{"months":[13]}']:
            with self.subTest(pattern=pattern):
                s = make_schedule(type='daily', recurrence_pattern=pattern)
                self.assertFalse(self.scheduler._is_schedule_active(s, dt.datetime(2026, 9, 24, 12)))
                self.assertIsNone(self.next(s, dt.datetime(2026, 9, 24, 12)))

    def test_all_types_report_current_availability(self):
        for kind in ['daily', 'weekly', 'monthly', 'custom']:
            s = make_schedule(type=kind)
            now = dt.datetime(2026, 9, 24, 12)
            self.assertEqual(self.next(s, now), now)

    def test_expired_schedule_has_no_next_run(self):
        for kind in ['daily', 'weekly', 'monthly', 'custom']:
            s = make_schedule(type=kind, end_date=dt.datetime(2026, 1, 2))
            self.assertIsNone(self.next(s, dt.datetime(2026, 9, 24)))

    def test_static_holiday_leap_boundary_keeps_valid_range_days(self):
        s = make_schedule(type='holiday', start_date=dt.datetime(2024, 2, 29), end_date=dt.datetime(2024, 3, 2, 23, 59))
        self.assertTrue(self.scheduler._is_schedule_active(s, dt.datetime(2027, 3, 1)))

    def test_leap_day_crosses_non_leap_century(self):
        s = make_schedule(type='monthly', start_date=dt.datetime(2000, 1, 1), recurrence_pattern='{"months":[2],"monthDays":[29]}')
        self.assertEqual(self.next(s, dt.datetime(2097, 1, 1)), dt.datetime(2104, 2, 29))

    def test_overnight_last_day_tail_then_expires(self):
        for kind in ['daily', 'weekly', 'monthly']:
            s = make_schedule(type=kind, start_date=dt.datetime(2026, 9, 25),
                end_date=dt.datetime(2026, 9, 25, 23, 59),
                recurrence_pattern='{"timeRange":{"start":"22:00","end":"03:00"}}')
            self.assertEqual(self.next(s, dt.datetime(2026, 9, 26, 2)), dt.datetime(2026, 9, 26, 2))
            self.assertIsNone(self.next(s, dt.datetime(2026, 9, 26, 4)))


def load_schedule_routes(db, scheduler):
    """Actual handlers, isolated from main.py's import-time workers and services."""
    wanted = {'ScheduleCreate', '_validate_schedule_references', '_resolve_holiday_window',
              '_refresh_schedule_next_run', 'create_schedule', 'update_schedule', 'get_schedules', 'scheduler_debug',
              'ExternalScheduleCreate', 'external_create_schedule'}
    tree = ast.parse((Path(__file__).parents[1] / 'backend/main.py').read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in wanted]
    scheduler.trigger_immediate_check = Mock()
    env = dict(datetime=dt, json=json, Optional=Optional, BaseModel=BaseModel,
        Session=Session, Depends=Depends, app=FastAPI(), get_db=lambda: db, require_api_key_full=Mock(),
        HTTPException=HTTPException, models=models, scheduler=scheduler,
        joinedload=joinedload, _file_log=Mock(), log_event=Mock(),
        _has_valid_sequence=lambda s: bool(s.sequence and json.loads(s.sequence)),
        _localized_now=lambda *args: module._localized_now())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'schedule_routes', 'exec'), env)
    return env


class ScheduleUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(models.Category(id=1, name='Test category'))
        self.db.commit()
        self.scheduler = module.Scheduler()
        self.clock = patch.object(module, '_localized_now', return_value=dt.datetime(2026, 9, 24, 12))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def test_old_formats_migrate_without_reinterpreting_windows_or_losing_fields(self):
        fixtures = [
            ('daily', None),  # legacy continuous daily range
            ('weekly', '{"weekDays":["Friday"],"timeRange":{"start":"22","end":"03:00"}}'),
            ('monthly', '{"monthDays":[15,31]}'),  # v1.10.14: no months filter
            ('monthly', '{"months":[10],"monthDays":[1,15]}'),  # v2 sentinel-era recurrence
            ('holiday', None),  # fixed-date legacy holiday, no country/name
            ('custom', None),
            ('daily', '[]'),  # damaged data must survive for repair
        ]
        for i, (kind, pattern) in enumerate(fixtures):
            self.db.add(models.Schedule(name=f'Old {i}', type=kind,
                start_date=dt.datetime(2024, 10, 1, 18), end_date=dt.datetime(2028, 10, 31, 23, 59),
                recurrence_pattern=pattern, category_id=1, fallback_category_id=1,
                is_active=i % 2 == 0, playlist=True, priority=8, exclusive=True,
                sequence='[{"type":"random","category_id":1}]', source_sequence_id=42,
                preroll_ids='[7]', blend_enabled=True, color='#123456', last_run=dt.datetime(2025, 10, 1)))
        self.db.commit()
        fields = [c.name for c in models.Schedule.__table__.columns if c.name not in ('next_run', 'recurrence_pattern')]
        before = {r.id: {k: getattr(r, k) for k in fields} for r in self.db.query(models.Schedule)}
        self.assertGreater(migrate_schedules(self.db, self.scheduler._calculate_next_run), 0)
        self.db.commit()
        self.db.expire_all()
        for row in self.db.query(models.Schedule):
            self.assertEqual({k: getattr(row, k) for k in fields}, before[row.id])
        damaged = self.db.query(models.Schedule).filter_by(name='Old 6').one()
        self.assertEqual(damaged.recurrence_pattern, '[]')
        self.assertIsNone(damaged.next_run)
        self.assertEqual(migrate_schedules(self.db, self.scheduler._calculate_next_run), 0)

    def test_create_edit_list_validate_all_types_and_refresh_stale_dates(self):
        env = load_schedule_routes(self.db, self.scheduler)
        for kind in ['daily', 'weekly', 'monthly', 'holiday', 'custom']:
            payload = env['ScheduleCreate'](name=kind, type=kind, start_date='2026-10-01T18:00',
                end_date='2026-10-02T23:59', category_id=1,
                recurrence_pattern='{"timeRange":{"start":"20:00","end":"22:00"}}')
            created = env['create_schedule'](payload, self.db)
            self.assertEqual(created['next_run'], '2026-10-01T20:00:00')
            payload.is_active = False
            payload.priority = 8
            env['update_schedule'](created['id'], payload, self.db)
            row = self.db.get(models.Schedule, created['id'])
            self.assertFalse(row.is_active)
            self.assertEqual(row.priority, 8)
        with patch.object(module, '_localized_now', return_value=dt.datetime(2027, 9, 24)):
            listed = env['get_schedules'](self.db)
        for row in listed:
            self.assertEqual(row['next_run'], '2027-10-01T20:00:00' if row['type'] == 'holiday' else None)
        for pattern in ['[]', '{"months":[13]}', '{"timeRange":{"end":"03:00"}}']:
            with self.assertRaises(HTTPException) as error:
                env['create_schedule'](env['ScheduleCreate'](name='bad', type='daily', start_date='2026-01-01', category_id=1, recurrence_pattern=pattern), self.db)
            self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(self.db.query(models.Schedule).count(), 5)

    def test_holiday_create_honors_pin_and_edit_survives_api_outage(self):
        env = load_schedule_routes(self.db, self.scheduler)
        payload = env['ScheduleCreate'](name='Future Thanksgiving', type='holiday', start_date='2028-11-23T00:00',
            end_date='2028-11-23T23:59:59', category_id=1, holiday_name='Thanksgiving', holiday_country='US',
            recurrence_pattern='{"timeRange":{"start":"22:00","end":"03:00"}}')
        with patch.object(self.scheduler, '_get_holiday_date', return_value=dt.date(2028, 11, 23)):
            created = env['create_schedule'](payload, self.db)
        self.assertTrue(created['start_date'].startswith('2028-'))
        with patch.object(self.scheduler, '_get_holiday_date', return_value=None):
            payload.name = 'Renamed while offline'
            env['update_schedule'](created['id'], payload, self.db)
        row = self.db.get(models.Schedule, created['id'])
        self.assertEqual(row.start_date.year, 2028)
        self.assertEqual(json.loads(row.recurrence_pattern)['timeRange']['end'], '03:00')

    def test_refresh_keeps_new_years_overnight_tail_and_retries_outages(self):
        row = models.Schedule(name='New Year Eve', type='holiday', start_date=dt.datetime(2026, 12, 31),
            end_date=dt.datetime(2026, 12, 31, 23, 59), holiday_name='New Year Eve', holiday_country='US',
            recurrence_pattern='{"timeRange":{"start":"22:00","end":"03:00"}}')
        self.db.add(row)
        self.db.commit()
        with patch.object(self.scheduler, '_get_holiday_date', side_effect=lambda name, country, year: dt.date(year, 12, 31)):
            result = refresh_linked_holidays(self.db, dt.datetime(2027, 1, 1, 1), self.scheduler)
            self.assertEqual(result['updated_count'], 0)
            self.assertTrue(self.scheduler._is_schedule_active(row, dt.datetime(2027, 1, 1, 1)))
        with patch.object(self.scheduler, '_get_holiday_date', return_value=None):
            result = refresh_linked_holidays(self.db, dt.datetime(2027, 1, 2), self.scheduler)
            self.assertEqual(row.start_date.year, 2026)
            self.assertEqual(len(result['errors']), 1)

    def test_diagnostics_can_explain_malformed_legacy_rows(self):
        self.db.add(models.Schedule(name='Needs repair', type='daily', start_date=dt.datetime(2020, 1, 1),
                                    is_active=True, recurrence_pattern='[]'))
        self.db.commit()
        result = load_schedule_routes(self.db, self.scheduler)['scheduler_debug'](self.db)
        self.assertEqual(result['active_schedules'], [])
        self.assertIn('JSON object', str(result))

    def test_invalid_legacy_schedule_can_be_paused_but_not_reenabled(self):
        row = models.Schedule(name='Invalid', type='daily', start_date=dt.datetime(2020, 1, 1),
                              category_id=1, is_active=True, recurrence_pattern='[]')
        self.db.add(row)
        self.db.commit()
        env = load_schedule_routes(self.db, self.scheduler)
        payload = env['ScheduleCreate'](name=row.name, type=row.type, start_date=row.start_date.isoformat(),
            category_id=1, recurrence_pattern='[]', is_active=False)
        env['update_schedule'](row.id, payload, self.db)
        self.assertFalse(row.is_active)
        payload.is_active = True
        with self.assertRaises(HTTPException):
            env['update_schedule'](row.id, payload, self.db)

    def test_external_creation_also_receives_normalization_and_metadata(self):
        env = load_schedule_routes(self.db, self.scheduler)
        payload = env['ExternalScheduleCreate'](name='External yearly', schedule_type='yearly',
            start_date='2023-10-01T00:00', end_date='2023-10-31T23:59', category_id=1)
        result = asyncio.run(env['external_create_schedule'](payload, None, self.db))
        row = self.db.get(models.Schedule, result['schedule']['id'])
        self.assertEqual(row.start_date.year, 2000)
        self.assertEqual(row.next_run, dt.datetime(2026, 10, 1))
