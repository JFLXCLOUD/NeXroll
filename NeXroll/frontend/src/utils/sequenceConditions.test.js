import { blocksHaveConditions, chainBounds, chainInfo, chainLabel, describeBlockCondition, insertBlockAt, moveBlockTo, removeBlockAt, tidyChains } from './sequenceConditions';

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

// Which blocks follow the one above them, by name: the shape of every chain.
const flags = list => list.map(block => `${block.name}${block.else_if ? '+' : ''}`).join(' ');
const named = (name, elseIf = false) => ({ type: 'random', name, condition: genre(name), ...(elseIf ? { else_if: true } : {}) });
// A (alone), then the chain H > M1 > M2, then B (alone).
const chain = () => [named('A'), named('H'), named('M1', true), named('M2', true), named('B')];

describe('keeping Else if chains whole', () => {
  test('removing the block that starts a chain makes the next member start it', () => {
    // Left alone, M1 joined A's chain and an unconditional A always won.
    expect(flags(removeBlockAt(chain(), 1))).toBe('A M1 M2+ B');
  });

  test('removing a member keeps the rest of its chain', () => {
    expect(flags(removeBlockAt(chain(), 2))).toBe('A H M2+ B');
  });

  test('the first block never keeps a flag', () => {
    expect(flags(removeBlockAt(chain(), 0))).toBe('H M1+ M2+ B');
    expect(flags(tidyChains([named('X', true), named('Y', true)]))).toBe('X Y+');
    // A stale flag on the first block must not pull it into a block added above.
    expect(flags(insertBlockAt([named('X', true)], 0, named('N')))).toBe('N X');
  });

  test('a block inserted between two members joins the chain', () => {
    expect(flags(insertBlockAt(chain(), 2, named('N')))).toBe('A H N+ M1+ M2+ B');
    expect(flags(insertBlockAt(chain(), 1, named('N')))).toBe('A N H M1+ M2+ B');
    expect(flags(insertBlockAt(chain(), 4, named('N')))).toBe('A H M1+ M2+ N B');
  });

  test('moving inside a chain changes priority and keeps the chain', () => {
    expect(flags(moveBlockTo(chain(), 1, 2))).toBe('A M1 H+ M2+ B');
    expect(flags(moveBlockTo(chain(), 3, 1))).toBe('A M2 H+ M1+ B');
  });

  test('a block leaving its chain plays on its own', () => {
    expect(flags(moveBlockTo(chain(), 1, 0))).toBe('H A M1 M2+ B');
    expect(flags(moveBlockTo(chain(), 2, 4))).toBe('A H M2+ B M1');
    expect(flags(moveBlockTo(chain(), 3, 4))).toBe('A H M1+ B M2');
  });

  test('a block dropped between two members of another chain joins it', () => {
    expect(flags(moveBlockTo(chain(), 4, 3))).toBe('A H M1+ B+ M2+');
    expect(flags(moveBlockTo(chain(), 0, 2))).toBe('H M1+ A+ M2+ B');
  });

  test('out-of-range moves change nothing', () => {
    expect(flags(moveBlockTo(chain(), 1, 9))).toBe('A H M1+ M2+ B');
    expect(flags(moveBlockTo(chain(), 2, 2))).toBe('A H M1+ M2+ B');
  });
});
