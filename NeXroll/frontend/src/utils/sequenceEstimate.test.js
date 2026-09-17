import { estimateSequence, describeEstimate, formatDuration, ASSUMED } from './sequenceEstimate';

const prerolls = [
  { id: 1, category_id: 10, duration: 11 },
  { id: 2, category_id: 10, duration: 12 },
  { id: 3, category_id: 20, duration: 60 },
  { id: 4, category_id: 20 }, // duration never recorded
];

describe('estimateSequence', () => {
  test('an empty sequence estimates nothing', () => {
    expect(estimateSequence([], prerolls)).toEqual({
      seconds: 0, variations: 1, exact: true, blocks: 0,
    });
  });

  test('fixed blocks use the real durations, not a per-block guess', () => {
    // The reported bug: two clips totalling 23s were announced as 4m 10s,
    // because the old code charged two minutes per block.
    const result = estimateSequence(
      [{ type: 'fixed', preroll_ids: [1, 2] }], prerolls);
    expect(result.seconds).toBe(23);
    expect(result.exact).toBe(true);
  });

  test('a deterministic sequence has exactly one variation', () => {
    const result = estimateSequence([
      { type: 'preroll', preroll_id: 1 },
      { type: 'fixed', preroll_ids: [2, 3] },
    ], prerolls);
    expect(result.variations).toBe(1);
    expect(result.seconds).toBe(11 + 12 + 60);
  });

  test('a random block varies by how many ways it can be drawn', () => {
    // Two prerolls in category 10, pick one: two possible plays.
    expect(estimateSequence(
      [{ type: 'random', category_id: 10, count: 1 }], prerolls).variations).toBe(2);
    // Pick both, in order: two orderings.
    expect(estimateSequence(
      [{ type: 'random', category_id: 10, count: 2 }], prerolls).variations).toBe(2);
  });

  test('variations multiply across random blocks', () => {
    const result = estimateSequence([
      { type: 'random', category_id: 10, count: 1 },
      { type: 'random', category_id: 20, count: 1 },
    ], prerolls);
    expect(result.variations).toBe(4);
  });

  test('a missing duration makes the estimate approximate', () => {
    const result = estimateSequence([{ type: 'fixed', preroll_ids: [4] }], prerolls);
    expect(result.exact).toBe(false);
    expect(result.seconds).toBe(ASSUMED.preroll);
  });

  test('content chosen at playback time is never called exact', () => {
    for (const type of ['nexup_trailers', 'coming_soon_list', 'dynamic_preroll']) {
      expect(estimateSequence([{ type }], prerolls).exact).toBe(false);
    }
  });

  test('a generated block uses the real duration of the file it names', () => {
    // It plays one specific file every time, so there is nothing to estimate
    // once the library has measured it.
    const withGenerated = [...prerolls, { id: 9, filename: 'ident.mp4', duration: 7 }];
    const result = estimateSequence(
      [{ type: 'dynamic_preroll', filename: 'ident.mp4' }], withGenerated);
    expect(result.seconds).toBe(7);
    expect(result.exact).toBe(true);
    expect(result.variations).toBe(1);
  });

  test('a generated block falls back when the file is unknown', () => {
    const result = estimateSequence(
      [{ type: 'dynamic_preroll', filename: 'missing.mp4' }], prerolls);
    expect(result.seconds).toBe(ASSUMED.generated);
    expect(result.exact).toBe(false);
  });

  test('separators take no time', () => {
    expect(estimateSequence([{ type: 'separator' }], prerolls).seconds).toBe(0);
  });

  test('sequential plays the whole category', () => {
    const result = estimateSequence(
      [{ type: 'sequential', category_id: 10 }], prerolls);
    expect(result.seconds).toBe(23);
    expect(result.variations).toBe(1);
  });

  test('an empty category cannot be estimated exactly', () => {
    const result = estimateSequence(
      [{ type: 'sequential', category_id: 999 }], prerolls);
    expect(result.exact).toBe(false);
  });
});

describe('formatDuration', () => {
  test('keeps seconds visible below a minute', () => {
    expect(formatDuration(23)).toBe('23s');
    expect(formatDuration(0)).toBe('0s');
  });

  test('shows minutes and seconds, not a rounded-up minute', () => {
    expect(formatDuration(65)).toBe('1m 05s');
    expect(formatDuration(250)).toBe('4m 10s');
  });

  test('shows hours for long sequences', () => {
    expect(formatDuration(3720)).toBe('1h 02m');
  });
});

describe('describeEstimate', () => {
  test('an empty builder shows dashes rather than a made-up minute', () => {
    const d = describeEstimate([], prerolls);
    expect(d).toMatchObject({ blocks: '0', duration: '—', variations: '—' });
    expect(d.plays).toMatch(/Add a block/);
  });

  test('a deterministic sequence says so', () => {
    const d = describeEstimate([{ type: 'fixed', preroll_ids: [1, 2] }], prerolls);
    expect(d.duration).toBe('23s');
    expect(d.variations).toBe('1');
    expect(d.plays).toBe('Plays the same every time');
  });

  test('an approximate estimate is marked with a tilde', () => {
    const d = describeEstimate([{ type: 'nexup_trailers', count: 2 }], prerolls);
    expect(d.duration.startsWith('~')).toBe(true);
  });

  test('a shuffling sequence says it shuffles', () => {
    const d = describeEstimate([{ type: 'random', category_id: 10, count: 1 }], prerolls);
    expect(d.plays).toBe('Shuffles between runs');
    expect(d.variations).toBe('2');
  });
});
