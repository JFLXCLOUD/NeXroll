import {
  DEFAULT_SORT_DIRECTION,
  DEFAULT_SORT_FIELD,
  describeSort,
  isSortField,
  sortDirectionOrDefault,
  sortFieldOrDefault,
  sortPrerolls
} from './prerollSort';

const preroll = (id, overrides = {}) => ({
  id,
  filename: `preroll${id}.mp4`,
  display_name: null,
  duration: 10,
  upload_date: '2026-01-01T00:00:00',
  ...overrides
});

const ids = (list) => list.map(item => item.id);
const names = (list) => list.map(item => item.display_name || item.filename);

describe('sort field and direction normalization', () => {
  it('accepts the three supported fields and rejects anything else', () => {
    expect(isSortField('added')).toBe(true);
    expect(isSortField('name')).toBe(true);
    expect(isSortField('duration')).toBe(true);
    expect(isSortField('file_size')).toBe(false);
  });

  it('falls back to defaults for missing or corrupt stored preferences', () => {
    expect(sortFieldOrDefault(null)).toBe(DEFAULT_SORT_FIELD);
    expect(sortFieldOrDefault('nonsense')).toBe(DEFAULT_SORT_FIELD);
    expect(sortFieldOrDefault('duration')).toBe('duration');
    expect(sortDirectionOrDefault(null)).toBe(DEFAULT_SORT_DIRECTION);
    expect(sortDirectionOrDefault('sideways')).toBe(DEFAULT_SORT_DIRECTION);
    expect(sortDirectionOrDefault('asc')).toBe('asc');
  });

  it('describes each direction in terms of the field being sorted', () => {
    expect(describeSort('added', 'desc')).toBe('Newest first');
    expect(describeSort('added', 'asc')).toBe('Oldest first');
    expect(describeSort('name', 'asc')).toBe('A to Z');
    expect(describeSort('duration', 'desc')).toBe('Longest first');
  });
});

describe('sortPrerolls', () => {
  it('does not mutate the array it was given', () => {
    const list = [preroll(2), preroll(1)];
    const snapshot = ids(list);

    sortPrerolls(list, 'name', 'asc');

    expect(ids(list)).toEqual(snapshot);
  });

  it('tolerates an empty or missing list', () => {
    expect(sortPrerolls([], 'name', 'asc')).toEqual([]);
    expect(sortPrerolls(undefined, 'name', 'asc')).toEqual([]);
    expect(sortPrerolls(null, 'added', 'desc')).toEqual([]);
  });

  describe('by last added', () => {
    const list = [
      preroll(1, { upload_date: '2026-01-01T00:00:00' }),
      preroll(2, { upload_date: '2026-08-16T00:00:00' }),
      preroll(3, { upload_date: '2026-04-20T00:00:00' })
    ];

    it('puts the newest first by default', () => {
      expect(ids(sortPrerolls(list, 'added', 'desc'))).toEqual([2, 3, 1]);
    });

    it('reverses to oldest first', () => {
      expect(ids(sortPrerolls(list, 'added', 'asc'))).toEqual([1, 3, 2]);
    });

    it('treats a missing or unparseable date as the oldest possible', () => {
      const withGaps = [
        preroll(1, { upload_date: '2026-01-01T00:00:00' }),
        preroll(2, { upload_date: null }),
        preroll(3, { upload_date: 'not a date' })
      ];
      expect(ids(sortPrerolls(withGaps, 'added', 'desc'))).toEqual([1, 2, 3]);
    });
  });

  describe('by name', () => {
    it('orders numbered files naturally, not lexically', () => {
      // The lexical answer would be bumper1, bumper10, bumper2 - which is what
      // users notice immediately in a library of numbered bumpers.
      const list = [
        preroll(1, { filename: 'bumper10.mp4' }),
        preroll(2, { filename: 'bumper2.mp4' }),
        preroll(3, { filename: 'bumper1.mp4' })
      ];

      expect(names(sortPrerolls(list, 'name', 'asc')))
        .toEqual(['bumper1.mp4', 'bumper2.mp4', 'bumper10.mp4']);
    });

    it('is case insensitive', () => {
      const list = [
        preroll(1, { filename: 'zebra.mp4' }),
        preroll(2, { filename: 'Apple.mp4' }),
        preroll(3, { filename: 'mango.mp4' })
      ];

      expect(names(sortPrerolls(list, 'name', 'asc')))
        .toEqual(['Apple.mp4', 'mango.mp4', 'zebra.mp4']);
    });

    it('sorts on the display name when one is set', () => {
      const list = [
        preroll(1, { filename: 'aaa.mp4', display_name: 'Zulu' }),
        preroll(2, { filename: 'zzz.mp4', display_name: 'Alpha' })
      ];

      expect(names(sortPrerolls(list, 'name', 'asc'))).toEqual(['Alpha', 'Zulu']);
    });

    it('reverses cleanly', () => {
      const list = [
        preroll(1, { filename: 'a.mp4' }),
        preroll(2, { filename: 'b.mp4' }),
        preroll(3, { filename: 'c.mp4' })
      ];

      expect(ids(sortPrerolls(list, 'name', 'desc'))).toEqual([3, 2, 1]);
    });
  });

  describe('by duration', () => {
    const list = [
      preroll(1, { duration: 30 }),
      preroll(2, { duration: 5.5 }),
      preroll(3, { duration: 120 })
    ];

    it('puts the longest first by default', () => {
      expect(ids(sortPrerolls(list, 'duration', 'desc'))).toEqual([3, 1, 2]);
    });

    it('reverses to shortest first', () => {
      expect(ids(sortPrerolls(list, 'duration', 'asc'))).toEqual([2, 1, 3]);
    });

    it('sinks prerolls with no known duration to the bottom in both directions', () => {
      // A null duration means "never probed", not "zero seconds" - showing those
      // first when sorting shortest-first would be actively misleading.
      const withGaps = [
        preroll(1, { duration: null }),
        preroll(2, { duration: 30 }),
        preroll(3, { duration: 0 }),
        preroll(4, { duration: 5 })
      ];

      expect(ids(sortPrerolls(withGaps, 'duration', 'asc'))).toEqual([4, 2, 1, 3]);
      expect(ids(sortPrerolls(withGaps, 'duration', 'desc'))).toEqual([2, 4, 1, 3]);
    });
  });

  describe('stability', () => {
    it('breaks ties on id so paging does not shuffle between renders', () => {
      const tied = [
        preroll(9, { duration: 10 }),
        preroll(3, { duration: 10 }),
        preroll(7, { duration: 10 })
      ];

      expect(ids(sortPrerolls(tied, 'duration', 'desc'))).toEqual([3, 7, 9]);
      expect(ids(sortPrerolls(tied, 'duration', 'asc'))).toEqual([3, 7, 9]);
    });

    it('produces the same order when run repeatedly', () => {
      const list = [
        preroll(4, { filename: 'same.mp4', duration: 10 }),
        preroll(1, { filename: 'same.mp4', duration: 10 }),
        preroll(2, { filename: 'same.mp4', duration: 10 })
      ];

      const once = ids(sortPrerolls(list, 'name', 'asc'));
      const twice = ids(sortPrerolls(sortPrerolls(list, 'name', 'asc'), 'name', 'asc'));

      expect(once).toEqual([1, 2, 4]);
      expect(twice).toEqual(once);
    });
  });
});
