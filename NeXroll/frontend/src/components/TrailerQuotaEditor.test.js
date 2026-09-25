import React, { useState } from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import TrailerQuotaEditor, { TrailerQuotaReport } from './TrailerQuotaEditor';

test('rating and genre targets persist through a settings serialization round trip', () => {
  let current;
  function Harness() {
    const [value, setValue] = useState([]);
    current = value;
    return <TrailerQuotaEditor value={value} onChange={v => setValue(JSON.parse(JSON.stringify(v)))} genres={[{ name: 'Horror' }, { name: 'Comedy' }]} />;
  }
  render(<Harness />);
  fireEvent.click(screen.getByText('Add minimum target'));
  expect(current).toEqual([{ kind: 'rating', values: ['G', 'PG'], min: 2 }]);
  fireEvent.click(screen.getByText('Add minimum target'));
  fireEvent.change(screen.getByLabelText('Target 2 type'), { target: { value: 'genre' } });
  expect(screen.getByText(/Choose at least one genre/)).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Horror'));
  fireEvent.change(screen.getByLabelText('Target 2 minimum'), { target: { value: '5' } });
  expect(current[1]).toEqual({ kind: 'genre', values: ['Horror'], min: 5 });
  fireEvent.click(screen.getByLabelText('Remove target 1'));
  expect(current).toEqual([{ kind: 'genre', values: ['Horror'], min: 5 }]);
  fireEvent.click(screen.getByLabelText('Remove target 1'));
  expect(current).toEqual([]);
});

test('shortfall is shown as unmet, not as a successful sync', () => {
  render(<TrailerQuotaReport entries={[{ values: ['PG'], available: 1, min: 2, shortfall: 1, matching_movies: 4, reason: 'Capacity is full' }]} />);
  expect(screen.getByText('PG: 1 / 2')).toBeInTheDocument();
  expect(screen.getByText(/1 more needed. Capacity is full/)).toBeInTheDocument();
});

test('running sync disables target edits', () => {
  render(<TrailerQuotaEditor value={[{ kind: 'rating', values: ['PG'], min: 1 }]} onChange={jest.fn()} disabled />);
  expect(screen.getByText('Add minimum target')).toBeDisabled();
  expect(screen.getByLabelText('Target 1 minimum')).toBeDisabled();
  expect(within(screen.getByRole('group', { name: 'Target 1' })).getByLabelText('PG')).toBeDisabled();
});
