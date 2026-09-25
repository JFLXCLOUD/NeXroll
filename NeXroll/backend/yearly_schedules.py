"""Year-agnostic seasonal windows and lossless normalization of older rows."""


def in_yearly_window(start, end, now):
    # Compare month/day/time directly: replacing the year can invalidate Feb 29
    # and incorrectly disable an entire season in a non-leap year.
    key = lambda value: (value.month, value.day, value.time())
    first, last, current = key(start), key(end), key(now)
    return first <= current <= last if first <= last else current >= first or current <= last


def normalize_yearly_schedule(schedule):
    """Keep every field and boundary time; only the unused year changes.

    Linked holidays retain their first-year pin. Missing end dates retain the
    existing year-round meaning. Leap year 2000 can represent every month/day.
    """
    if schedule.type != 'yearly' or (
        getattr(schedule, 'holiday_name', None) and getattr(schedule, 'holiday_country', None)
    ):
        return False
    changed = False
    for field in ('start_date', 'end_date'):
        value = getattr(schedule, field, None)
        if value and value.year != 2000:
            setattr(schedule, field, value.replace(year=2000))
            changed = True
    return changed


def migrate_yearly_schedules(db, calculate_next_run):
    """Repair existing rows in the caller's transaction before scheduling starts.

    Safe to repeat and also repairs beta.11 rows already using year 2000 whose
    next_run was NULL. IDs, relationships, paused state and history are untouched.
    """
    from backend.models import Schedule
    changed = 0
    for schedule in db.query(Schedule).filter(Schedule.type == 'yearly').all():
        normalized = normalize_yearly_schedule(schedule)
        next_run = calculate_next_run(schedule)
        if normalized or schedule.next_run != next_run:
            schedule.next_run = next_run
            changed += 1
    return changed
