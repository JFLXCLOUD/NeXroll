import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import TrailerRatingFilter from './TrailerRatingFilter';
import BlockEditor from './BlockEditor';
import { sanitizeSequence, validateSequence } from '../utils/sequenceValidator';

test('removing the last selected rating keeps the restriction enabled', () => {
  let current;
  function Harness() {
    const [value, setValue] = useState({});
    current = value;
    return <TrailerRatingFilter value={value} onChange={patch => setValue(v => ({ ...v, ...patch }))} />;
  }
  render(<Harness />);
  fireEvent.click(screen.getByLabelText('Restrict age ratings'));
  expect(screen.getByText(/No ratings selected/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('PG'));
  expect(current).toEqual({ restrict_ratings: true, ratings: ['PG'] });
  fireEvent.click(screen.getByLabelText('PG'));
  expect(current).toEqual({ restrict_ratings: true, ratings: [] });
  expect(screen.getByLabelText('Restrict age ratings')).toBeChecked();
  fireEvent.click(screen.getByLabelText('Restrict age ratings'));
  expect(current.restrict_ratings).toBe(false);
});

test('saved and alternative filters survive serialization; old blocks stay unchanged', () => {
  const condition = { rules: [{ kind: 'trailers_available', pool: 'block' }] };
  const blocks = [{ type: 'library_trailers', count: 2, ratings: ['G', 'PG'], restrict_ratings: true,
    condition, otherwise: { type: 'nexup_trailers', count: 1, ratings: ['PG'], restrict_ratings: true } }];
  const saved = JSON.parse(JSON.stringify(sanitizeSequence(blocks)));
  expect(saved[0].ratings).toEqual(['G', 'PG']);
  expect(saved[0].otherwise.ratings).toEqual(['PG']);
  expect(saved[0].condition).toEqual(condition);
  expect(sanitizeSequence([{ type: 'nexup_trailers', count: 2 }])[0]).not.toHaveProperty('ratings');
  expect(validateSequence([{ type: 'library_trailers', ratings: 'PG' }]).valid).toBe(false);
});

test('legacy modal editor saves and reopens a restricted trailer block', () => {
  const onSave = jest.fn();
  const props = { categories: [], prerolls: [], isNew: false, onSave, onCancel: jest.fn() };
  const { unmount } = render(<BlockEditor {...props} block={{ id: 'a', type: 'library_trailers', count: 2 }} />);
  fireEvent.click(screen.getByLabelText('Restrict age ratings'));
  fireEvent.click(screen.getByLabelText('PG'));
  fireEvent.click(screen.getByRole('button', { name: /save|update block/i }));
  expect(onSave).toHaveBeenCalled();
  const saved = onSave.mock.calls[0][0];
  expect(saved.ratings).toEqual(['PG']);
  unmount();
  render(<BlockEditor {...props} block={saved} />);
  expect(screen.getByLabelText('PG')).toBeChecked();
});
