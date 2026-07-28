import {
  buildBlendBothChanges,
  buildRecurrencePattern,
  evaluateScheduleTimeSegments,
  getAnchoredTimeRangeOverlap,
  hasSamePriorityTimeOverlap,
  isEffectiveBlendPair,
  isYearlyOrHolidayScheduleActiveOnDay,
  normalizeScheduleDateForStorage,
  priorityToBeatExclusive,
  timeRangesOverlap,
  yearlyOrHolidayDateRangesOverlap
} from './scheduleUtils';

describe('evaluateScheduleTimeSegments', () => {
  const schedule = (
    id,
    start,
    end,
    { blend = false, exclusive = false, priority = 5 } = {}
  ) => ({
    id,
    blend_enabled: blend,
    exclusive,
    priority,
    recurrence_pattern: JSON.stringify({ timeRange: { start, end } })
  });

  test('does not report a normal conflict while two active blend schedules cover it', () => {
    const state = evaluateScheduleTimeSegments([
      schedule(1, '09:00', '12:00', { blend: true }),
      schedule(2, '09:00', '12:00', { blend: true }),
      schedule(3, '09:00', '12:00')
    ]);

    expect(state.hasBlend).toBe(true);
    expect(state.hasConflict).toBe(false);
    expect(state.conflictPairs).toEqual([]);
  });

  test('does not combine disjoint blend windows and preserves their real ties', () => {
    const state = evaluateScheduleTimeSegments([
      schedule(1, '00:00', '08:00', { blend: true }),
      schedule(2, '12:00', '18:00', { blend: true }),
      schedule(3, '00:00', '18:00')
    ]);

    expect(state.hasBlend).toBe(false);
    expect(state.hasConflict).toBe(true);
    expect(state.conflictPairs.map(pair => pair.key).sort()).toEqual(['1-3', '2-3']);
  });

  test('only reports ties at the highest active normal priority', () => {
    const lowerTie = evaluateScheduleTimeSegments([
      schedule(1, '09:00', '12:00', { priority: 5 }),
      schedule(2, '09:00', '12:00', { priority: 5 }),
      schedule(3, '09:00', '12:00', { priority: 8 })
    ]);
    expect(lowerTie.hasConflict).toBe(false);

    const topTie = evaluateScheduleTimeSegments([
      schedule(1, '09:00', '12:00', { priority: 8 }),
      schedule(2, '09:00', '12:00', { priority: 8 }),
      schedule(3, '09:00', '12:00', { priority: 5 })
    ]);
    expect(topTie.conflictPairs.map(pair => pair.key)).toEqual(['1-2']);
  });

  test('applies exclusive selection before blend mode and only flags top exclusive ties', () => {
    const state = evaluateScheduleTimeSegments([
      schedule(1, '09:00', '12:00', { blend: true }),
      schedule(2, '09:00', '12:00', { blend: true }),
      schedule(3, '09:00', '12:00', { exclusive: true, priority: 8 }),
      schedule(4, '09:00', '12:00', { exclusive: true, priority: 6 })
    ]);

    expect(state.hasBlend).toBe(false);
    expect(state.hasConflict).toBe(false);
    expect(state.winnerScheduleIds).toContain(3);
  });
});

describe('exclusive conflict resolutions', () => {
  test('play-both clears exclusivity and enables blending on both schedules', () => {
    expect(buildBlendBothChanges({ id: 1 }, { id: 2 })).toEqual([
      { scheduleId: 1, field: 'exclusive', value: false },
      { scheduleId: 2, field: 'exclusive', value: false },
      { scheduleId: 1, field: 'blend_enabled', value: true },
      { scheduleId: 2, field: 'blend_enabled', value: true }
    ]);
  });

  test('winning priority never exceeds the scheduler cap', () => {
    expect(priorityToBeatExclusive(5, 9)).toBe(9);
    expect(priorityToBeatExclusive(9, 10)).toBe(10);
    expect(priorityToBeatExclusive(10, 1)).toBeNull();
  });

  test('a lone blend flag still uses normal winner selection', () => {
    expect(isEffectiveBlendPair({ blend_enabled: true }, { blend_enabled: false })).toBe(false);
    expect(isEffectiveBlendPair({ blend_enabled: true }, { blend_enabled: true })).toBe(true);
  });
});

describe('buildRecurrencePattern', () => {
  test('keeps a weekly start-only time window', () => {
    expect(buildRecurrencePattern({
      type: 'weekly',
      weekDays: ['monday'],
      timeRange: { start: '18:30', end: '' }
    })).toEqual({
      weekDays: ['monday'],
      timeRange: { start: '18:30', end: '' }
    });
  });

  test('does not add an empty optional weekly time window', () => {
    expect(buildRecurrencePattern({
      type: 'weekly',
      weekDays: ['friday'],
      timeRange: { start: '', end: '' }
    })).toEqual({ weekDays: ['friday'] });
  });
});

describe('normalizeScheduleDateForStorage', () => {
  test('normalizes ordinary yearly schedules but preserves Holiday Browser years', () => {
    expect(normalizeScheduleDateForStorage('yearly', '2027-11-25T00:00'))
      .toBe('2000-11-25T00:00');
    expect(normalizeScheduleDateForStorage('holiday', '2027-11-25T00:00'))
      .toBe('2027-11-25T00:00');
  });
});

describe('timeRangesOverlap', () => {
  test('treats a shared boundary minute as overlap like the scheduler', () => {
    expect(timeRangesOverlap('09:00', '12:00', '12:00', '15:00')).toBe(true);
  });

  test('handles overnight windows without flagging the daytime gap', () => {
    expect(timeRangesOverlap('22:00', '03:00', '04:00', '21:00')).toBe(false);
    expect(timeRangesOverlap('22:00', '03:00', '02:00', '04:00')).toBe(true);
  });

  test('allows adjacent conflict-wizard windows without a shared minute', () => {
    expect(timeRangesOverlap('00:00', '11:59', '12:00', '23:59')).toBe(false);
  });
});

describe('hasSamePriorityTimeOverlap', () => {
  const schedule = (priority, start, end) => ({
    priority,
    recurrence_pattern: JSON.stringify({ timeRange: { start, end } })
  });

  test('does not flag equal-priority schedules whose daily windows do not overlap', () => {
    expect(hasSamePriorityTimeOverlap([
      schedule(5, '09:00', '10:00'),
      schedule(5, '18:00', '19:00')
    ])).toBe(false);
  });

  test('flags an equal-priority pair only when their time windows overlap', () => {
    expect(hasSamePriorityTimeOverlap([
      schedule(5, '09:00', '12:00'),
      schedule(7, '10:00', '11:00'),
      schedule(5, '11:00', '13:00')
    ])).toBe(true);
  });
});

describe('getAnchoredTimeRangeOverlap', () => {
  test('matches an overnight occurrence to an early window anchored the next day', () => {
    expect(getAnchoredTimeRangeOverlap('22:00', '03:00', 0, '02:00', '04:00', 1))
      .toEqual({ start: 26 * 60, end: 27 * 60 });
  });

  test('does not match that early window when both occurrences anchor to Friday', () => {
    expect(getAnchoredTimeRangeOverlap('22:00', '03:00', 0, '02:00', '04:00', 0))
      .toBeNull();
  });
});

describe('isYearlyOrHolidayScheduleActiveOnDay', () => {
  test('treats a yearly schedule without an end date as year-round', () => {
    const schedule = { type: 'yearly', start_date: '2000-06-01T00:00', end_date: null };
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2026, 0, 15))).toBe(true);
  });

  test('keeps a holiday without an end date to its single calendar day', () => {
    const schedule = { type: 'holiday', start_date: '2000-07-04T00:00', end_date: null };
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2026, 6, 4))).toBe(true);
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2026, 6, 5))).toBe(false);
  });

  test('does not activate a future-pinned linked holiday a year early', () => {
    const schedule = {
      type: 'holiday',
      start_date: '2027-11-25T00:00',
      end_date: '2027-11-25T23:59',
      holiday_name: 'Thanksgiving',
      holiday_country: 'US'
    };
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2026, 10, 25))).toBe(false);
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2027, 10, 25))).toBe(true);
  });

  test('supports yearly ranges that cross New Year', () => {
    const schedule = {
      type: 'yearly',
      start_date: '2000-12-15T00:00',
      end_date: '2000-01-15T23:59'
    };
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2026, 11, 20))).toBe(true);
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2027, 0, 10))).toBe(true);
    expect(isYearlyOrHolidayScheduleActiveOnDay(schedule, new Date(2027, 1, 1))).toBe(false);
  });
});

describe('yearlyOrHolidayDateRangesOverlap', () => {
  test('detects overlap across a New-Year-wrapping window', () => {
    const winter = {
      type: 'yearly',
      start_date: '2000-12-15T00:00',
      end_date: '2000-01-15T23:59'
    };
    const newYear = {
      type: 'holiday',
      start_date: '2000-01-01T00:00',
      end_date: '2000-01-01T23:59'
    };
    expect(yearlyOrHolidayDateRangesOverlap(winter, newYear)).toBe(true);
  });

  test('treats a no-end yearly schedule as overlapping any recurring date', () => {
    const yearRound = { type: 'yearly', start_date: '2000-06-01T00:00', end_date: null };
    const halloween = { type: 'holiday', start_date: '2000-10-31T00:00', end_date: null };
    expect(yearlyOrHolidayDateRangesOverlap(yearRound, halloween)).toBe(true);
  });
});
