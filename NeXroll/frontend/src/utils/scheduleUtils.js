const parseTimeToMinutes = (value) => {
  if (!value) return null;
  const match = String(value).match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;

  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
  return hours * 60 + minutes;
};

/**
 * Return whether two scheduler time windows share at least one minute.
 * Missing start times represent an all-day schedule, while a missing end time
 * runs through 23:59. Scheduler boundaries are inclusive.
 */
export const timeRangesOverlap = (start1, end1, start2, end2) => {
  const toRanges = (start, end) => {
    if (!start) return [[0, 23 * 60 + 59]];

    const startMinutes = parseTimeToMinutes(start);
    const endMinutes = end ? parseTimeToMinutes(end) : 23 * 60 + 59;
    if (startMinutes === null || endMinutes === null) return [];

    return endMinutes < startMinutes
      ? [[startMinutes, 23 * 60 + 59], [0, endMinutes]]
      : [[startMinutes, endMinutes]];
  };

  const ranges1 = toRanges(start1, end1);
  const ranges2 = toRanges(start2, end2);
  return ranges1.some(([startA, endA]) =>
    ranges2.some(([startB, endB]) => startA <= endB && startB <= endA)
  );
};

const toAnchoredTimeRange = (start, end, dayOffset = 0) => {
  const dayStart = dayOffset * 24 * 60;
  if (!start) return [dayStart, dayStart + 23 * 60 + 59];

  const startMinutes = parseTimeToMinutes(start);
  const endMinutes = end ? parseTimeToMinutes(end) : 23 * 60 + 59;
  if (startMinutes === null || endMinutes === null) return null;

  return [
    dayStart + startMinutes,
    dayStart + endMinutes + (endMinutes < startMinutes ? 24 * 60 : 0)
  ];
};

/**
 * Compare concrete occurrences whose recurrence dates may be adjacent. The
 * returned minute range is relative to the first occurrence's anchor day.
 */
export const getAnchoredTimeRangeOverlap = (
  start1,
  end1,
  dayOffset1,
  start2,
  end2,
  dayOffset2
) => {
  const first = toAnchoredTimeRange(start1, end1, dayOffset1);
  const second = toAnchoredTimeRange(start2, end2, dayOffset2);
  if (!first || !second) return null;

  const overlapStart = Math.max(first[0], second[0]);
  const overlapEnd = Math.min(first[1], second[1]);
  return overlapStart <= overlapEnd ? { start: overlapStart, end: overlapEnd } : null;
};

export const getScheduleTimeRange = (schedule) => {
  try {
    const pattern = typeof schedule?.recurrence_pattern === 'string'
      ? JSON.parse(schedule.recurrence_pattern)
      : schedule?.recurrence_pattern;
    return pattern?.timeRange || {};
  } catch {
    return {};
  }
};

/** Return whether any equal-priority pair is active during the same time window. */
export const hasSamePriorityTimeOverlap = (schedules = []) => {
  for (let firstIndex = 0; firstIndex < schedules.length; firstIndex += 1) {
    const first = schedules[firstIndex];
    const firstPriorityValue = first?.priority ?? 5;
    const firstPriority = Number.isFinite(Number(firstPriorityValue)) ? Number(firstPriorityValue) : 5;
    const firstTimeRange = getScheduleTimeRange(first);

    for (let secondIndex = firstIndex + 1; secondIndex < schedules.length; secondIndex += 1) {
      const second = schedules[secondIndex];
      const secondPriorityValue = second?.priority ?? 5;
      const secondPriority = Number.isFinite(Number(secondPriorityValue)) ? Number(secondPriorityValue) : 5;
      if (firstPriority !== secondPriority) continue;

      const secondTimeRange = getScheduleTimeRange(second);
      if (getAnchoredTimeRangeOverlap(
        firstTimeRange.start,
        firstTimeRange.end,
        0,
        secondTimeRange.start,
        secondTimeRange.end,
        0
      )) {
        return true;
      }
    }
  }

  return false;
};

/** Build the only valid "play both" resolution when exclusivity is involved. */
export const buildBlendBothChanges = (first, second) => [
  { scheduleId: first.id, field: 'exclusive', value: false },
  { scheduleId: second.id, field: 'exclusive', value: false },
  { scheduleId: first.id, field: 'blend_enabled', value: true },
  { scheduleId: second.id, field: 'blend_enabled', value: true }
];

/** Return a valid priority that beats an exclusive schedule, or null at the cap. */
export const priorityToBeatExclusive = (exclusivePriority, candidatePriority) => {
  const exclusive = Number.isFinite(Number(exclusivePriority)) ? Number(exclusivePriority) : 5;
  const candidate = Number.isFinite(Number(candidatePriority)) ? Number(candidatePriority) : 5;
  if (exclusive >= 10) return null;
  return Math.min(10, Math.max(candidate, exclusive + 1));
};

/** A pair enters backend blend mode only when both schedules opt in. */
export const isEffectiveBlendPair = (first, second) => (
  Boolean(first?.blend_enabled) && Boolean(second?.blend_enabled)
);

const normalizedPriority = (schedule) => {
  const value = Number(schedule?.priority ?? 5);
  return Number.isFinite(value) ? value : 5;
};

/** Use the same stable pair identifier as the conflict wizard. */
export const getSchedulePairKey = (first, second) => (
  [first?.id, second?.id].sort().join('-')
);

/**
 * Build one concrete scheduler occurrence on a minute timeline. End minutes
 * are inclusive in the scheduler, so the internal range is half-open and ends
 * one minute later. Overnight occurrences extend into the following day.
 */
export const buildScheduleTimeOccurrence = (schedule, dayOffset = 0) => {
  const timeRange = getScheduleTimeRange(schedule);
  const dayStart = dayOffset * 24 * 60;
  if (!timeRange.start) {
    return { schedule, start: dayStart, end: dayStart + 24 * 60 };
  }

  const startMinutes = parseTimeToMinutes(timeRange.start);
  const parsedEnd = timeRange.end ? parseTimeToMinutes(timeRange.end) : 23 * 60 + 59;
  if (startMinutes === null || parsedEnd === null) {
    return { schedule, start: dayStart, end: dayStart + 24 * 60 };
  }

  const overnightOffset = parsedEnd < startMinutes ? 24 * 60 : 0;
  return {
    schedule,
    start: dayStart + startMinutes,
    end: dayStart + parsedEnd + overnightOffset + 1
  };
};

const pairCombinations = (schedules) => {
  const pairs = [];
  for (let firstIndex = 0; firstIndex < schedules.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < schedules.length; secondIndex += 1) {
      pairs.push([schedules[firstIndex], schedules[secondIndex]]);
    }
  }
  return pairs;
};

/**
 * Evaluate concrete occurrences exactly as the scheduler does at each time
 * segment: exclusives win first; otherwise two or more active blend schedules
 * blend; otherwise only a tie at the highest active priority is ambiguous.
 */
export const evaluateScheduleOccurrenceSegments = (
  occurrences = [],
  windowStart = 0,
  windowEnd = 24 * 60
) => {
  const clippedOccurrences = occurrences
    .filter(occurrence => occurrence?.schedule && occurrence.start < occurrence.end)
    .map(occurrence => ({
      ...occurrence,
      start: Math.max(windowStart, occurrence.start),
      end: Math.min(windowEnd, occurrence.end)
    }))
    .filter(occurrence => occurrence.start < occurrence.end);

  const boundaries = [...new Set([
    windowStart,
    windowEnd,
    ...clippedOccurrences.flatMap(occurrence => [occurrence.start, occurrence.end])
  ])].sort((first, second) => first - second);

  const segments = [];
  const conflictPairsByKey = new Map();
  const blendScheduleIds = new Set();
  const winnerScheduleIds = new Set();

  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const start = boundaries[index];
    const end = boundaries[index + 1];
    if (start >= end) continue;

    // Adjacent recurrence anchors can refer to the same schedule. De-duplicate
    // it before applying group semantics for this segment.
    const activeById = new Map();
    clippedOccurrences.forEach((occurrence, occurrenceIndex) => {
      if (occurrence.start >= end || occurrence.end <= start) return;
      const identity = occurrence.schedule.id ?? `occurrence-${occurrenceIndex}`;
      activeById.set(identity, occurrence.schedule);
    });
    const activeSchedules = [...activeById.values()];
    if (activeSchedules.length === 0) continue;

    const exclusiveSchedules = activeSchedules.filter(schedule => schedule.exclusive);
    const activeBlendSchedules = activeSchedules.filter(schedule => schedule.blend_enabled);
    let mode = 'normal';
    let selectedSchedules = [];
    let segmentConflictPairs = [];

    if (exclusiveSchedules.length > 0) {
      mode = 'exclusive';
      const topPriority = Math.max(...exclusiveSchedules.map(normalizedPriority));
      selectedSchedules = exclusiveSchedules.filter(
        schedule => normalizedPriority(schedule) === topPriority
      );
      if (selectedSchedules.length > 1) {
        segmentConflictPairs = pairCombinations(selectedSchedules);
      }
    } else if (activeBlendSchedules.length >= 2) {
      mode = 'blend';
      selectedSchedules = activeBlendSchedules;
      activeBlendSchedules.forEach(schedule => blendScheduleIds.add(schedule.id));
    } else {
      const topPriority = Math.max(...activeSchedules.map(normalizedPriority));
      selectedSchedules = activeSchedules.filter(
        schedule => normalizedPriority(schedule) === topPriority
      );
      if (selectedSchedules.length > 1) {
        segmentConflictPairs = pairCombinations(selectedSchedules);
      }
    }

    selectedSchedules.forEach(schedule => winnerScheduleIds.add(schedule.id));
    const conflictPairKeys = segmentConflictPairs.map(([first, second]) => {
      const key = getSchedulePairKey(first, second);
      if (!conflictPairsByKey.has(key)) {
        conflictPairsByKey.set(key, {
          key,
          scheduleIds: [first.id, second.id],
          mode,
          segments: []
        });
      }
      conflictPairsByKey.get(key).segments.push({ start, end });
      return key;
    });

    segments.push({
      start,
      end,
      mode,
      activeScheduleIds: activeSchedules.map(schedule => schedule.id),
      selectedScheduleIds: selectedSchedules.map(schedule => schedule.id),
      conflictPairKeys
    });
  }

  const conflictPairs = [...conflictPairsByKey.values()];
  return {
    hasBlend: blendScheduleIds.size >= 2,
    hasConflict: conflictPairs.length > 0,
    blendScheduleIds: [...blendScheduleIds],
    winnerScheduleIds: [...winnerScheduleIds],
    conflictPairs,
    segments
  };
};

/**
 * Evaluate a representative calendar day. Including the previous anchor makes
 * overnight windows participate in their after-midnight segment.
 */
export const evaluateScheduleTimeSegments = (schedules = []) => {
  const occurrences = schedules.flatMap(schedule => [
    buildScheduleTimeOccurrence(schedule, -1),
    buildScheduleTimeOccurrence(schedule, 0)
  ]);
  return evaluateScheduleOccurrenceSegments(occurrences);
};

/** Store ordinary yearly schedules year-agnostically while preserving holiday pins. */
export const normalizeScheduleDateForStorage = (scheduleType, value) => {
  if (scheduleType !== 'yearly' || !value) return value;
  const match = /^(\d{4})-(\d{2})-(\d{2})(T.*)?$/.exec(String(value));
  if (!match) return value;
  return `2000-${match[2]}-${match[3]}${match[4] || ''}`;
};

/** Build the recurrence JSON object shared by schedule create and update. */
export const buildRecurrencePattern = ({
  type,
  timeRange = {},
  weekDays = [],
  selectedMonths = [],
  monthDays = []
}) => {
  const pattern = {};
  const normalizedTimeRange = {
    start: timeRange.start || '',
    end: timeRange.end || ''
  };

  if (type === 'daily' && normalizedTimeRange.start) {
    pattern.timeRange = normalizedTimeRange;
  }
  if (type === 'weekly' && weekDays.length > 0) {
    pattern.weekDays = [...weekDays];
    if (normalizedTimeRange.start) pattern.timeRange = normalizedTimeRange;
  }
  if (type === 'monthly') {
    if (selectedMonths.length > 0) pattern.months = [...selectedMonths];
    if (monthDays.length > 0) pattern.monthDays = [...monthDays];
    if (normalizedTimeRange.start) pattern.timeRange = normalizedTimeRange;
  }

  return pattern;
};

const parseMonthDay = (value) => {
  if (!value) return null;
  const match = String(value).match(/^\d{4}-(\d{2})-(\d{2})/);
  if (!match) return null;

  const month = Number(match[1]);
  const day = Number(match[2]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return month * 100 + day;
};

/**
 * Day-level activity check for yearly and holiday schedules. A standard yearly
 * schedule without an end date is intentionally year-round, matching the
 * backend scheduler; a holiday without an end date remains a single-day event.
 */
export const isYearlyOrHolidayScheduleActiveOnDay = (schedule, dayTime) => {
  if (!schedule?.start_date) return false;

  const dayDate = dayTime instanceof Date ? dayTime : new Date(dayTime);
  if (Number.isNaN(dayDate.getTime())) return false;

  // Holiday Browser entries can be deliberately created for a future year.
  // They become annual only after that configured first year; otherwise a
  // future Thanksgiving, for example, would also appear and run this year.
  const startDate = new Date(schedule.start_date);
  const isLinkedHoliday = schedule.type === 'holiday' || (
    Boolean(schedule.holiday_name) && Boolean(schedule.holiday_country)
  );
  if (
    isLinkedHoliday
    && !Number.isNaN(startDate.getTime())
    && dayDate.getFullYear() < startDate.getFullYear()
  ) {
    return false;
  }

  if (schedule.type === 'yearly' && !schedule.end_date) return true;

  const startMonthDay = parseMonthDay(schedule.start_date);
  const endMonthDay = parseMonthDay(schedule.end_date || schedule.start_date);
  if (startMonthDay === null || endMonthDay === null) return false;

  const currentMonthDay = (dayDate.getMonth() + 1) * 100 + dayDate.getDate();
  if (startMonthDay <= endMonthDay) {
    return currentMonthDay >= startMonthDay && currentMonthDay <= endMonthDay;
  }

  // Range crosses New Year, such as December 15 through January 15.
  return currentMonthDay >= startMonthDay || currentMonthDay <= endMonthDay;
};

/** Compare two recurring month/day windows, including New-Year wrapping. */
export const yearlyOrHolidayDateRangesOverlap = (scheduleA, scheduleB) => {
  const toRanges = (schedule) => {
    const startMonthDay = parseMonthDay(schedule?.start_date);
    if (startMonthDay === null) return [];
    if (schedule.type === 'yearly' && !schedule.end_date) return [[101, 1231]];

    const endMonthDay = parseMonthDay(schedule.end_date || schedule.start_date);
    if (endMonthDay === null) return [];
    return startMonthDay <= endMonthDay
      ? [[startMonthDay, endMonthDay]]
      : [[startMonthDay, 1231], [101, endMonthDay]];
  };

  const rangesA = toRanges(scheduleA);
  const rangesB = toRanges(scheduleB);
  return rangesA.some(([startA, endA]) =>
    rangesB.some(([startB, endB]) => startA <= endB && startB <= endA)
  );
};
