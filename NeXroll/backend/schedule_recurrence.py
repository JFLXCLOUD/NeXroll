"""Shared validation and compatibility rules for persisted schedule recurrence."""
import json
import re
from functools import lru_cache

WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
SCHEDULE_TYPES = ('daily', 'weekly', 'monthly', 'yearly', 'holiday', 'custom')


def parse_recurrence(raw):
    if raw is None or raw == '':
        return {}
    return _parse_string(raw) if isinstance(raw, str) else _normalize(raw)


@lru_cache(maxsize=512)
def _parse_string(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError('Recurrence must be valid JSON.') from exc
    return _normalize(value)


def _normalize(value):
    if not isinstance(value, dict):
        raise ValueError('Recurrence must be a JSON object.')
    result = dict(value)
    for key, maximum in [('months', 12), ('monthDays', 31)]:
        values = value.get(key)
        if values is None:
            continue
        if not isinstance(values, list):
            raise ValueError(f'{key} must be a list.')
        normalized = []
        for item in values:
            if isinstance(item, bool) or not re.fullmatch(r'\d{1,2}', str(item)) or not 1 <= int(item) <= maximum:
                raise ValueError(f'{key} must contain numbers from 1 to {maximum}.')
            normalized.append(int(item))
        result[key] = list(dict.fromkeys(normalized))
    if value.get('weekDays') is not None:
        if not isinstance(value['weekDays'], list):
            raise ValueError('weekDays must be a list.')
        days = [str(day).strip().lower() for day in value['weekDays']]
        if any(day not in WEEKDAYS for day in days):
            raise ValueError('weekDays must contain full weekday names.')
        result['weekDays'] = list(dict.fromkeys(days))
    if value.get('timeRange') is not None:
        window = value['timeRange']
        if not isinstance(window, dict):
            raise ValueError('timeRange must be an object.')
        window = dict(window)
        for key in ('start', 'end'):
            text = window.get(key) or ''
            if text:
                if not isinstance(text, str) or not re.fullmatch(r'\d{1,2}(:\d{2})?', text):
                    raise ValueError('Times must use HH:MM.')
                parts = text.split(':')
                hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
                if hour > 23 or minute > 59:
                    raise ValueError('Times must be between 00:00 and 23:59.')
                window[key] = f'{hour:02d}:{minute:02d}'
        if window.get('end') and not window.get('start'):
            raise ValueError('Set a daily start time or clear the daily end time.')
        result['timeRange'] = window
    return result


def recurrence_error(schedule):
    if schedule.type not in SCHEDULE_TYPES:
        return 'Unsupported schedule type.'
    try:
        parse_recurrence(schedule.recurrence_pattern)
    except ValueError as exc:
        return str(exc)
    return None


def migrate_schedules(db, calculate_next_run):
    """Preserve dates/content/history; repair known representations and metadata.

    Invalid legacy JSON stays available for repair, never broadens into all-day
    playback, and is reported by the API. The caller owns the transaction.
    """
    from backend.models import Schedule
    from backend.yearly_schedules import normalize_yearly_schedule
    changed = 0
    for schedule in db.query(Schedule).all():
        before = (schedule.start_date, schedule.end_date, schedule.recurrence_pattern, schedule.next_run)
        normalize_yearly_schedule(schedule)
        if schedule.recurrence_pattern:
            try:
                parsed = parse_recurrence(schedule.recurrence_pattern)
                if parsed != json.loads(schedule.recurrence_pattern):
                    schedule.recurrence_pattern = json.dumps(parsed)
            except (ValueError, TypeError):
                pass
        schedule.next_run = calculate_next_run(schedule)
        after = (schedule.start_date, schedule.end_date, schedule.recurrence_pattern, schedule.next_run)
        changed += before != after
    return changed


def refresh_linked_holidays(db, now, scheduler):
    """One refresh policy for startup, the daily tick, and manual refresh."""
    import datetime as dt
    from backend.models import Schedule
    rows = db.query(Schedule).filter(Schedule.type.in_(['holiday', 'yearly']),
        Schedule.holiday_name.isnot(None), Schedule.holiday_country.isnot(None)).all()
    updated, errors, dates = [], [], {}
    for row in rows:
        if row.start_date and row.start_date.year > now.year:
            continue
        if scheduler._is_schedule_active(row, now, dates):
            continue  # includes the after-midnight tail across New Year
        key = (row.holiday_name, row.holiday_country, now.year)
        if key not in dates:
            dates[key] = scheduler._get_holiday_date(*key)
        resolved = dates[key]
        if resolved is None:
            errors.append({'schedule_id': row.id, 'holiday': row.holiday_name,
                           'error': f'Holiday unavailable for {now.year}; stored dates preserved'})
            continue
        old_date = row.start_date
        if old_date and old_date.date() == resolved:
            continue
        row.start_date = dt.datetime.combine(resolved, old_date.time() if old_date else dt.time.min)
        row.end_date = dt.datetime.combine(resolved, row.end_date.time() if row.end_date else dt.time(23, 59, 59))
        updated.append({'id': row.id, 'name': row.name, 'holiday': row.holiday_name,
                        'old_date': old_date.strftime('%Y-%m-%d') if old_date else None,
                        'new_date': resolved.isoformat()})
    if updated:
        db.commit()
    return {'total_holiday_schedules': len(rows), 'updated_count': len(updated),
            'updated_schedules': updated, 'errors': errors, 'year': now.year}
