import {
  appendCommunityLengthParams, communityLengthBounds, formatPrerollLength,
} from './communityLength';

test.each([
  ['', null, null],
  ['le15', null, 15],
  ['le30', null, 30],
  ['le60', null, 60],
  ['60to120', 60, 120],
  ['over120', 121, null],
  ['unknown-preset', null, null],
])('preset %s gives min %s and max %s', (preset, min, max) => {
  expect(communityLengthBounds(preset)).toEqual({ min, max });
});

test('a custom range rounds, ignores blanks and swaps reversed bounds', () => {
  expect(communityLengthBounds('custom', '', '30')).toEqual({ min: null, max: 30 });
  expect(communityLengthBounds('custom', '10.4', '')).toEqual({ min: 10, max: null });
  expect(communityLengthBounds('custom', '90', '20')).toEqual({ min: 20, max: 90 });
  expect(communityLengthBounds('custom', '-5', 'abc')).toEqual({ min: null, max: null });
});

test('only set bounds become request parameters', () => {
  const params = new URLSearchParams();
  expect(appendCommunityLengthParams(params, 'le30')).toBe(true);
  expect(params.toString()).toBe('max_duration=30');
  const none = new URLSearchParams();
  expect(appendCommunityLengthParams(none, '')).toBe(false);
  expect(none.toString()).toBe('');
});

test.each([
  [12.4, '0:12'], [29.6, '0:30'], [65, '1:05'], [750, '12:30'],
  [null, null], [undefined, null], [0, null], ['abc', null],
])('formats %s as %s', (seconds, text) => {
  expect(formatPrerollLength(seconds)).toBe(text);
});
