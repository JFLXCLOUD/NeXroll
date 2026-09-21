import { layoutSequence } from './SequenceFlowView';

const title = block => block.label || block.type;
const describe_ = block => `${block.type} block`;
const layout = (blocks, advanced = false) => layoutSequence({
  blocks,
  advanced,
  selectedIndex: 0,
  blockTitle: title,
  blockDescription: describe_,
  getCategoryName: id => `Category ${id}`,
});

const guarded = (otherwise) => ({
  type: 'coming_soon_list',
  layout: 'grid',
  condition: { match: 'all', rules: [{ kind: 'trailers_available', min: 1 }] },
  ...(otherwise ? { otherwise } : {}),
});

describe('layoutSequence', () => {
  test('runs from start through each block to end, with a + on every gap', () => {
    const { nodes, edges } = layout([{ type: 'random' }, { type: 'fixed' }]);
    expect(nodes.map(n => n.id)).toEqual(['start', 'b-0', 'b-1', 'end']);
    expect(edges.map(e => [e.source, e.target, e.data.insertAt])).toEqual([
      ['start', 'b-0', 0],
      ['b-0', 'b-1', 1],
      ['b-1', 'end', 2],
    ]);
  });

  test('an empty sequence is start straight to end, inserting at 0', () => {
    const { nodes, edges } = layout([]);
    expect(nodes.map(n => n.id)).toEqual(['start', 'end']);
    expect(edges).toHaveLength(1);
    expect(edges[0].data.insertAt).toBe(0);
  });

  test('in Advanced mode a condition becomes an IF with true and false branches that rejoin', () => {
    const { nodes, edges } = layout([guarded({ type: 'random', category_id: 4, count: 1 }), { type: 'fixed' }], true);
    expect(nodes.map(n => n.id)).toEqual(['start', 'if-0', 'b-0', 'o-0', 'b-1', 'end']);
    const pairs = edges.map(e => `${e.source}${e.sourceHandle ? `:${e.sourceHandle}` : ''}>${e.target}`);
    expect(pairs).toEqual(['start>if-0', 'if-0:true>b-0', 'if-0:false>o-0', 'b-0>b-1', 'o-0>b-1', 'b-1>end']);
    // One "+" for the gap after the branches, not two.
    expect(edges.filter(e => e.target === 'b-1' && e.data.insertAt != null)).toHaveLength(1);
    expect(nodes.find(n => n.id === 'o-0').data.description).toBe('1 preroll from Category 4 play instead');
  });

  test('a condition with no alternative branches to Skip', () => {
    const { nodes } = layout([guarded()], true);
    expect(nodes.find(n => n.id === 'o-0').type).toBe('skip');
  });

  test('in Simple mode a conditional block stays a single node with a badge', () => {
    const { nodes } = layout([guarded()], false);
    expect(nodes.map(n => n.id)).toEqual(['start', 'b-0', 'end']);
    expect(nodes[1].data.badge).toBe('Conditional');
  });
});

describe('saved canvas positions', () => {
  test('keeps geometry with the same block after reorder, selection, and settings edits', () => {
    const first = { id: 'first', type: 'random', flow_positions: { simple_b: { x: 410, y: 175 } } };
    const second = { id: 'second', type: 'fixed' };
    const result = layout([second, { ...first, count: 3 }]);
    expect(result.nodes.find(node => node.id === 'b-first').position).toEqual({ x: 410, y: 175 });
    expect(result.edges.map(edge => [edge.source, edge.target])).toEqual([
      ['start', 'b-second'], ['b-second', 'b-first'], ['b-first', 'end'],
    ]);
  });
  test('remembers separate simple and advanced geometry, including both branches', () => {
    const block = { ...guarded(), id: 'guard', flow_positions: {
      simple_b: { x: 1, y: 2 }, advanced_b: { x: 500, y: -200 }, advanced_o: { x: 510, y: 200 },
    } };
    expect(layout([block]).nodes.find(node => node.id === 'b-guard').position).toEqual({ x: 1, y: 2 });
    const advanced = layout([block], true);
    expect(advanced.nodes.find(node => node.id === 'b-guard').position).toEqual({ x: 500, y: -200 });
    expect(advanced.nodes.find(node => node.id === 'o-guard')).toMatchObject({ draggable: true, position: { x: 510, y: 200 } });
  });
  test('ignores invalid imported coordinates', () => {
    const block = { type: 'fixed', flow_positions: { simple_b: { x: 'bad', y: null } } };
    expect(layout([block]).nodes[1].position).toEqual(layout([{ type: 'fixed' }]).nodes[1].position);
  });
});
