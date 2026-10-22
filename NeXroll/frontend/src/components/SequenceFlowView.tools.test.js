import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import SequenceFlowView, { layoutSequence } from './SequenceFlowView';

// React Flow measures its canvas; jsdom has no layout, so give it the APIs.
// Unmeasured nodes stay visibility: hidden, which leaves their buttons with no
// accessible name, so the tests find them by aria-label and menu text instead.
beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  if (!global.DOMMatrixReadOnly) {
    global.DOMMatrixReadOnly = class {
      constructor(transform) {
        const scale = /scale\(([\d.]+)\)/.exec(transform || '');
        this.m22 = scale ? Number(scale[1]) : 1;
      }
    };
  }
});

const notFamily = (otherwise) => ({
  id: 'block-1',
  type: 'random',
  category_id: 4,
  count: 1,
  condition: { match: 'all', rules: [{ kind: 'genre', values: ['Family'], negate: true }] },
  ...(otherwise ? { otherwise } : {}),
});

const showFlow = (blocks, props = {}) => {
  const handlers = { onRemove: jest.fn(), onChangeType: jest.fn(), onChangeOtherwise: jest.fn() };
  render(
    <SequenceFlowView
      blocks={blocks}
      advanced
      selectedIndex={0}
      onSelect={jest.fn()}
      onMove={jest.fn()}
      onInsert={jest.fn()}
      onPositionsChange={jest.fn()}
      blockTitle={block => block.type}
      blockDescription={block => `${block.type} block`}
      getCategoryName={id => `Category ${id}`}
      darkMode
      {...handlers}
      {...props}
    />
  );
  return handlers;
};

test('a block offers Edit and Delete', () => {
  const handlers = showFlow([{ id: 'a', type: 'random', category_id: 4 }, { id: 'b', type: 'fixed' }]);
  fireEvent.click(screen.getByLabelText('Delete block 2'));
  expect(handlers.onRemove).toHaveBeenCalledWith(1);
});

test('Edit lists the block types, marks the current one and changes the type', () => {
  const handlers = showFlow([{ id: 'a', type: 'sequential', category_id: 4 }]);
  fireEvent.click(screen.getByLabelText('Change the type of block 1'));
  const menu = screen.getByRole('menu', { hidden: true });
  expect(within(menu).getByText('Category')).toHaveAttribute('aria-current', 'true');
  fireEvent.click(within(menu).getByText('Fixed preroll'));
  expect(handlers.onChangeType).toHaveBeenCalledWith(0, 'fixed');
  expect(screen.queryByRole('menu', { hidden: true })).not.toBeInTheDocument();
});

test('picking the current type changes nothing', () => {
  const handlers = showFlow([{ id: 'a', type: 'fixed' }]);
  fireEvent.click(screen.getByLabelText('Change the type of block 1'));
  fireEvent.click(within(screen.getByRole('menu', { hidden: true })).getByText('Fixed preroll'));
  expect(handlers.onChangeType).not.toHaveBeenCalled();
});

test('an Otherwise can change what plays, or be deleted to Skip', () => {
  const handlers = showFlow([notFamily({ type: 'random', category_id: 5, count: 1 })]);
  fireEvent.click(screen.getByLabelText('Change what plays instead at step 1'));
  fireEvent.click(within(screen.getByRole('menu', { hidden: true })).getByText('Library trailers'));
  expect(handlers.onChangeOtherwise).toHaveBeenCalledWith(0, 'library_trailers');
  fireEvent.click(screen.getByLabelText('Skip instead at step 1'));
  expect(handlers.onChangeOtherwise).toHaveBeenCalledWith(0, 'skip');
});

test('a Skip can be given something to play, and cannot be deleted', () => {
  const handlers = showFlow([notFamily()]);
  expect(screen.queryByLabelText(/Skip instead/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Play something instead of skipping at step 1'));
  fireEvent.click(within(screen.getByRole('menu', { hidden: true })).getByText('Category'));
  expect(handlers.onChangeOtherwise).toHaveBeenCalledWith(0, 'random');
});

test('one menu at a time', () => {
  showFlow([{ id: 'a', type: 'random' }, { id: 'b', type: 'fixed' }]);
  fireEvent.click(screen.getByLabelText('Change the type of block 1'));
  fireEvent.click(screen.getByLabelText('Change the type of block 2'));
  expect(screen.getAllByRole('menu', { hidden: true })).toHaveLength(1);
});

test('without the handlers the canvas shows no tools', () => {
  showFlow([{ id: 'a', type: 'random' }], { onRemove: undefined, onChangeType: undefined, onChangeOtherwise: undefined });
  expect(screen.queryByLabelText(/Delete block/)).not.toBeInTheDocument();
});

test('the layout gives the tools the block type and the Otherwise choice', () => {
  const { nodes } = layoutSequence({
    blocks: [notFamily({ type: 'nexup_trailers', count: 1 })],
    advanced: true,
    selectedIndex: 0,
    blockTitle: block => block.type,
    blockDescription: () => '',
    getCategoryName: () => '',
  });
  expect(nodes.find(node => node.id.startsWith('b-')).data.type).toBe('random');
  expect(nodes.find(node => node.id.startsWith('o-')).data.otherwiseChoice).toBe('nexup_trailers');
});
