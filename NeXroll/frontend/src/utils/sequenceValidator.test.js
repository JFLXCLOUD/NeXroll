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

describe('sequenceHasUnsavedChanges', () => {
  const { sequenceHasUnsavedChanges, cloneSequenceWithIds } = require('./sequenceValidator');
  const saved = { name: 'Friday Night', description: 'Weekend opener',
    blocks: [{ type: 'fixed', preroll_ids: [1] }, { type: 'random', category_id: 2, count: 1 }] };

  test('a freshly opened sequence is not dirty despite its cloned block ids', () => {
    // The Edit button stamps a client-only id on every block. Comparing raw
    // would report an edit the moment the editor opened, so Cancel would always
    // prompt and the prompt would mean nothing.
    const blocks = cloneSequenceWithIds(saved.blocks);
    expect(blocks[0].id).toBeDefined();
    expect(sequenceHasUnsavedChanges(blocks, saved.name, saved.description, saved)).toBe(false);
  });

  test('changing a block is dirty', () => {
    const blocks = cloneSequenceWithIds(saved.blocks);
    blocks[1] = { ...blocks[1], count: 3 };
    expect(sequenceHasUnsavedChanges(blocks, saved.name, saved.description, saved)).toBe(true);
  });

  test('adding, removing and reordering blocks are all dirty', () => {
    const blocks = cloneSequenceWithIds(saved.blocks);
    expect(sequenceHasUnsavedChanges([...blocks, { type: 'separator', duration: 3 }],
      saved.name, saved.description, saved)).toBe(true);
    expect(sequenceHasUnsavedChanges([blocks[0]], saved.name, saved.description, saved)).toBe(true);
    expect(sequenceHasUnsavedChanges([blocks[1], blocks[0]], saved.name, saved.description, saved)).toBe(true);
  });

  test('renaming or redescribing is dirty, but surrounding whitespace is not', () => {
    const blocks = cloneSequenceWithIds(saved.blocks);
    expect(sequenceHasUnsavedChanges(blocks, 'Saturday Night', saved.description, saved)).toBe(true);
    expect(sequenceHasUnsavedChanges(blocks, saved.name, 'Something else', saved)).toBe(true);
    expect(sequenceHasUnsavedChanges(blocks, '  Friday Night  ', '  Weekend opener  ', saved)).toBe(false);
  });

  test('moving a block on the flow canvas is dirty, because that geometry is saved', () => {
    const blocks = cloneSequenceWithIds(saved.blocks);
    blocks[0] = { ...blocks[0], flow_positions: { simple_b: { x: 40, y: 12 } } };
    expect(sequenceHasUnsavedChanges(blocks, saved.name, saved.description, saved)).toBe(true);
  });

  test('a condition added in Advanced mode is dirty', () => {
    const blocks = cloneSequenceWithIds(saved.blocks);
    blocks[0] = { ...blocks[0],
      condition: { match: 'all', rules: [{ kind: 'trailers_available', source: 'both', min: 1 }] } };
    expect(sequenceHasUnsavedChanges(blocks, saved.name, saved.description, saved)).toBe(true);
  });

  test('an untouched new sequence is not dirty, but any content makes it dirty', () => {
    expect(sequenceHasUnsavedChanges([], '', '', null)).toBe(false);
    expect(sequenceHasUnsavedChanges([], '   ', '  ', null)).toBe(false);
    expect(sequenceHasUnsavedChanges([{ type: 'fixed', preroll_ids: [1] }], '', '', null)).toBe(true);
    expect(sequenceHasUnsavedChanges([], 'Named but empty', '', null)).toBe(true);
  });
});
