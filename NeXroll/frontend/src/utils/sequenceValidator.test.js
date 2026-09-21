import { sanitizeSequence } from './sequenceValidator';

describe('sanitizeSequence', () => {
  test('keeps a sequential block\'s category and count', () => {
    // Saving used to drop both, so the block played nothing.
    expect(sanitizeSequence([{ id: 'ui-1', type: 'sequential', category_id: 7, count: 3 }]))
      .toEqual([{ type: 'sequential', category_id: 7, count: 3 }]);
  });

  test('keeps a block condition and a cleaned alternative', () => {
    const condition = { match: 'all', rules: [{ kind: 'trailers_available', min: 1 }] };
    const [saved] = sanitizeSequence([{
      id: 'ui-2',
      type: 'coming_soon_list',
      layout: 'grid',
      condition,
      otherwise: { type: 'random', category_id: 4, count: 2, label: 'ignored', ui_only: true },
    }]);
    expect(saved).toEqual({
      type: 'coming_soon_list',
      layout: 'grid',
      condition,
      otherwise: { type: 'random', category_id: 4, count: 2 },
    });
  });

  test('keeps a library trailers block\'s settings', () => {
    expect(sanitizeSequence([{ id: 'ui-3', type: 'library_trailers', count: 3, mode: 'newest', genres: ['Horror'], match_playing: true }]))
      .toEqual([{ type: 'library_trailers', count: 3, mode: 'newest', genres: ['Horror'], match_playing: true }]);
  });

  test('drops an empty condition and any alternative left behind', () => {
    const [saved] = sanitizeSequence([{
      type: 'fixed',
      preroll_ids: [1],
      condition: { rules: [] },
      otherwise: { type: 'random', category_id: 4 },
    }]);
    expect(saved).toEqual({ type: 'fixed', preroll_ids: [1] });
  });
});

 test('saved flow geometry survives JSON and cloned IDs; malformed points are discarded', () => {
   const { stringifySequence, parseSequence, cloneSequenceWithIds } = require('./sequenceValidator');
   const [block] = cloneSequenceWithIds(parseSequence(stringifySequence([{ type: 'fixed', preroll_ids: [1],
     flow_positions: { simple_b: { x: -210, y: 150 }, advanced_if: { x: 40, y: -90 },
       advanced_o: { x: Infinity, y: 0 }, unknown: { x: 0, y: 0 } } }])));
   expect(block.flow_positions).toEqual({ simple_b: { x: -210, y: 150 }, advanced_if: { x: 40, y: -90 } });
 });
