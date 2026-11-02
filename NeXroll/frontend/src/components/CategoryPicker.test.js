import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import CategoryPicker from './CategoryPicker';

const categories = [
  { id: 2, name: 'kids' },
  { id: 1, name: 'Halloween' },
  { id: 9, name: 'NeX-Up Movie Trailers', is_system: true },
  { id: 3, name: 'Christmas' },
];

let latest;
const Harness = ({ onCreateCategory, primary = '', secondary = [], list = categories }) => {
  const [value, setValue] = useState({ primary, secondary });
  latest = value;
  return (
    <CategoryPicker
      categories={list}
      primaryId={value.primary}
      secondaryIds={value.secondary}
      onChange={(p, s) => setValue({ primary: p, secondary: s })}
      onCreateCategory={onCreateCategory}
    />
  );
};

const field = () => screen.getByRole('combobox');
const optionNames = () => within(screen.getByRole('listbox')).queryAllByRole('option').map(o => o.textContent);

test('lists your categories alphabetically, then the system ones', () => {
  render(<Harness />);
  fireEvent.focus(field());
  expect(optionNames()).toEqual(['Christmas', 'Halloween', 'kids', 'NeX-Up Movie Trailers']);
  expect(screen.getByText('System categories')).toBeInTheDocument();
});

test('the first category chosen becomes the primary, later ones secondary', () => {
  render(<Harness />);
  fireEvent.focus(field());
  fireEvent.click(screen.getByRole('option', { name: 'Halloween' }));
  fireEvent.click(screen.getByRole('option', { name: 'Christmas' }));
  expect(latest).toEqual({ primary: '1', secondary: ['3'] });
  // Removing the primary promotes the next one.
  fireEvent.click(screen.getByRole('option', { name: 'Halloween' }));
  expect(latest).toEqual({ primary: '3', secondary: [] });
});

test('chips keep the chosen order and remove on their x', () => {
  render(<Harness primary="3" secondary={['1']} />);
  const removes = screen.getAllByRole('button', { name: /^Remove / });
  expect(removes.map(b => b.getAttribute('aria-label'))).toEqual(['Remove Christmas', 'Remove Halloween']);
  fireEvent.click(screen.getByRole('button', { name: 'Remove Christmas' }));
  expect(latest).toEqual({ primary: '1', secondary: [] });
});

test('typing filters, arrows move and Enter ticks the highlighted category', () => {
  render(<Harness />);
  fireEvent.focus(field());
  fireEvent.change(field(), { target: { value: 'i' } });
  expect(optionNames()).toEqual(['Christmas', 'kids', 'NeX-Up Movie Trailers']);
  fireEvent.keyDown(field(), { key: 'ArrowDown' });
  fireEvent.keyDown(field(), { key: 'Enter' });
  expect(latest).toEqual({ primary: '2', secondary: [] });
  // Enter clears the search so the next name can be typed.
  expect(field()).toHaveValue('');
});

test('Enter on a partial name picks the match instead of creating it', () => {
  const create = jest.fn();
  render(<Harness onCreateCategory={create} />);
  fireEvent.focus(field());
  fireEvent.change(field(), { target: { value: 'hallo' } });
  fireEvent.keyDown(field(), { key: 'Enter' });
  expect(create).not.toHaveBeenCalled();
  expect(latest).toEqual({ primary: '1', secondary: [] });
});

test('Enter on a name nothing matches creates it and selects it', async () => {
  const create = jest.fn().mockResolvedValue({ id: 7, name: 'Summer' });
  render(<Harness onCreateCategory={create} primary="1" />);
  fireEvent.focus(field());
  fireEvent.change(field(), { target: { value: ' Summer ' } });
  fireEvent.keyDown(field(), { key: 'Enter' });
  await waitFor(() => expect(latest).toEqual({ primary: '1', secondary: ['7'] }));
  expect(create).toHaveBeenCalledWith('Summer');
});

test('after New category, Enter creates even when the name partly matches one', async () => {
  const create = jest.fn().mockResolvedValue({ id: 8, name: 'Hall' });
  render(<Harness onCreateCategory={create} />);
  fireEvent.focus(field());
  fireEvent.click(screen.getByRole('button', { name: /New category/ }));
  expect(field()).toHaveAttribute('placeholder', 'Name the new category, then press Enter');
  fireEvent.change(field(), { target: { value: 'Hall' } });
  fireEvent.keyDown(field(), { key: 'Enter' });
  await waitFor(() => expect(create).toHaveBeenCalledWith('Hall'));
});

test('Backspace in an empty search removes the last chip', () => {
  render(<Harness primary="1" secondary={['3']} />);
  fireEvent.keyDown(field(), { key: 'Backspace' });
  expect(latest).toEqual({ primary: '1', secondary: [] });
});

test('Escape closes the list', () => {
  render(<Harness />);
  fireEvent.focus(field());
  expect(screen.getByRole('listbox')).toBeInTheDocument();
  fireEvent.keyDown(field(), { key: 'Escape' });
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});

test('ids missing from the list survive a change', () => {
  render(<Harness primary="99" secondary={[]} />);
  fireEvent.focus(field());
  fireEvent.click(screen.getByRole('option', { name: 'kids' }));
  expect(latest).toEqual({ primary: '99', secondary: ['2'] });
});

test('Clear removes every category', () => {
  render(<Harness primary="1" secondary={['2']} />);
  fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
  expect(latest).toEqual({ primary: '', secondary: [] });
});
