/**
 * NeXroll's clock vs. this browser's.
 *
 * Schedules run on NeXroll's timezone (Settings > General > Timezone, UTC
 * until someone picks one), and their times are stored as plain wall-clock
 * times on that clock ("22:00", "2026-11-03T00:43"). The pages read those as
 * this browser's local time, which is only right while both clocks agree.
 * Issue #50: a Central-time user still on UTC saw LateNight (10 PM to 6 AM)
 * win at 6:45 PM, the calendar's "now" line in the wrong place, and LateNight
 * "up next" at 12:43 AM while it was already playing.
 *
 * wallClock() gives a Date whose local fields read NeXroll's wall time, so
 * pages compare schedule times with NeXroll's "now". With both clocks on the
 * same offset it returns the date unchanged.
 */

/** Minutes the zone is ahead of UTC at `date`, or null if this browser doesn't know it. */
export const zoneOffsetMinutes = (timeZone, date = new Date()) => {
  if (!timeZone) return null;
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).formatToParts(date);
    const get = type => Number(parts.find(p => p.type === type)?.value);
    const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour') % 24, get('minute'), get('second'));
    const whole = Math.floor(date.getTime() / 1000) * 1000;
    const minutes = Math.round((asUtc - whole) / 60000);
    return Number.isFinite(minutes) ? minutes : null;
  } catch {
    return null;
  }
};

export const browserTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
};

/** True when NeXroll's zone is on a different offset from this browser right now. */
export const zonesDiffer = (timeZone, date = new Date()) => {
  const offset = zoneOffsetMinutes(timeZone, date);
  return offset !== null && offset !== -date.getTimezoneOffset();
};

/** `date` moved so its local fields show the wall time in `timeZone`. */
export const wallClock = (timeZone, date = new Date()) => {
  const offset = zoneOffsetMinutes(timeZone, date);
  if (offset === null) return date;
  const local = -date.getTimezoneOffset();
  return offset === local ? date : new Date(date.getTime() + (offset - local) * 60000);
};

/** "6:45 PM" on the zone's clock. */
export const zoneTimeLabel = (timeZone, date = new Date()) => {
  try {
    return date.toLocaleTimeString([], { timeZone, hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
};

/** This browser's zone if it's one of `known` (the server's list), else null. */
export const suggestedTimeZone = (known = []) => {
  const own = browserTimeZone();
  const names = known.map(zone => (typeof zone === 'string' ? zone : zone?.value)).filter(Boolean);
  return own && names.includes(own) ? own : null;
};
