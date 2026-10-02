import { blocksHaveConditions, chainBounds, chainInfo, chainLabel, describeBlockCondition } from './sequenceConditions';

const genre = (...values) => ({ match: 'all', rules: [{ kind: 'genre', values }] });
const blocks = [
  { type: 'fixed' },
  { type: 'random', condition: genre('Horror') },
  { type: 'random', condition: genre('Science Fiction'), else_if: true },
  { type: 'random', else_if: true },
  { type: 'random', condition: genre('Action'), else_if: true },
];

test('chainBounds matches the backend', () => {
  expect(chainBounds(blocks, 0)).toEqual([0, 0]);
  expect(chainBounds(blocks, 1)).toEqual([1, 4]);
  expect(chainBounds(blocks, 3)).toEqual([1, 4]);
});

test('chainInfo describes a block\'s place in its chain', () => {
  expect(chainInfo(blocks, 0)).toMatchObject({ elseIf: false, canChain: false, continues: false });
  expect(chainInfo(blocks, 1)).toMatchObject({ elseIf: false, canChain: false, continues: true });
  expect(chainInfo(blocks, 2)).toMatchObject({ elseIf: true, canChain: true, continues: true, neverPlays: false });
  expect(chainInfo(blocks, 3)).toMatchObject({ elseIf: true, canChain: true, neverPlays: false });
  // After the Else, which always plays when reached.
  expect(chainInfo(blocks, 4)).toMatchObject({ elseIf: true, canChain: false, blockedAbove: true, neverPlays: true });
});

test('chain labels and summaries', () => {
  expect(chainLabel(blocks[2])).toBe('Else if');
  expect(chainLabel(blocks[3])).toBe('Else');
  const name = () => 'House';
  expect(describeBlockCondition(blocks[1].condition, null, name, chainInfo(blocks, 1)))
    .toBe('Plays only when the genre is Horror. Otherwise, the Else if block below is checked.');
  expect(describeBlockCondition(blocks[2].condition, { type: 'random', category_id: 9 }, name, { elseIf: true }))
    .toBe('Else if: plays only when no block above it in the chain played and the genre is Science Fiction. If no block in the chain plays, 1 preroll from House play instead.');
  expect(describeBlockCondition(null, null, name, { elseIf: true }))
    .toBe('Else: plays only when no block above it in the chain played.');
  // Unchanged outside a chain.
  expect(describeBlockCondition(blocks[1].condition, null, name))
    .toBe('Plays only when the genre is Horror. Otherwise, the block is skipped.');
});

test('a chain counts as conditional even where a member has no condition', () => {
  expect(blocksHaveConditions([{ type: 'fixed' }, { type: 'fixed', else_if: true }])).toBe(true);
  expect(blocksHaveConditions([{ type: 'fixed', else_if: true }])).toBe(false);
});
