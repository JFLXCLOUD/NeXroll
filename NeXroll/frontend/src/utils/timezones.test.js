import { browserTimeZone, suggestedTimeZone, wallClock, zoneOffsetMinutes, zonesDiffer, zoneTimeLabel } from './timezones';

const JAN = new Date(Date.UTC(2026, 0, 15, 12, 0));
const JUL = new Date(Date.UTC(2026, 6, 15, 12, 0));
// A zone on a different offset from whatever zone the tests run in.
const OTHER = -JAN.getTimezoneOffset() === 330 ? 'UTC' : 'Asia/Kolkata';

test('zoneOffsetMinutes follows the zone, daylight saving included', () => {
  expect(zoneOffsetMinutes('UTC', JAN)).toBe(0);
  expect(zoneOffsetMinutes('America/Chicago', JAN)).toBe(-360);
  expect(zoneOffsetMinutes('America/Chicago', JUL)).toBe(-300);
  expect(zoneOffsetMinutes('Asia/Kolkata', JAN)).toBe(330);
  expect(zoneOffsetMinutes('Not/A_Zone', JAN)).toBeNull();
  expect(zoneOffsetMinutes(null, JAN)).toBeNull();
});

test('wallClock reads the zone\'s wall time in local fields', () => {
  const utc = wallClock('UTC', JAN);
  expect([utc.getFullYear(), utc.getMonth(), utc.getDate(), utc.getHours(), utc.getMinutes()]).toEqual([2026, 0, 15, 12, 0]);
  const chicago = wallClock('America/Chicago', JAN);
  expect([chicago.getDate(), chicago.getHours()]).toEqual([15, 6]);
});

test('with both clocks on one offset nothing moves', () => {
  expect(wallClock(browserTimeZone(), JAN)).toBe(JAN);
  expect(wallClock(null, JAN)).toBe(JAN);
  expect(wallClock('Not/A_Zone', JAN)).toBe(JAN);
  expect(zonesDiffer(browserTimeZone(), JAN)).toBe(false);
  expect(zonesDiffer(OTHER, JAN)).toBe(true);
  expect(zonesDiffer('Not/A_Zone', JAN)).toBe(false);
});

test('issue #50: 00:47 UTC is 6:47 PM the evening before in Chicago', () => {
  const posted = new Date(Date.UTC(2026, 10, 3, 0, 47));
  expect(zoneTimeLabel('America/Chicago', posted)).toMatch(/6:47\sPM/);
  expect(zoneTimeLabel('UTC', posted)).toMatch(/12:47\sAM/);
});

test('suggestedTimeZone offers this browser\'s zone only when the server knows it', () => {
  const own = browserTimeZone();
  expect(suggestedTimeZone([{ value: 'UTC' }, { value: own }])).toBe(own);
  expect(suggestedTimeZone(['UTC', own])).toBe(own);
  expect(suggestedTimeZone([{ value: 'Some/Other' }])).toBeNull();
  expect(suggestedTimeZone([])).toBeNull();
});
