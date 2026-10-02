import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CategorySelect from './CategorySelect';

const categories = [{ id: 2, name: 'Kids' }, { id: 1, name: 'Halloween' }];

let latest;
const Harness = ({ onCreateCategory }) => {
  const [value, setValue] = useState('');
  latest = value;
  return (
    <CategorySelect categories={categories} value={value} onChange={setValue}
      onCreateCategory={onCreateCategory} emptyLabel="No category" ariaLabel="Category" />
  );
};

test('lists categories by name with a New category option last', () => {
  render(<Harness onCreateCategory={jest.fn()} />);
  const options = Array.from(screen.getByLabelText('Category').options).map(o => o.textContent);
  expect(options).toEqual(['No category', 'Halloween', 'Kids', '+ New category…']);
});

test('creates a category on the spot and selects it', async () => {
  const create = jest.fn().mockResolvedValue({ id: 7, name: 'Christmas' });
  render(<Harness onCreateCategory={create} />);
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: '__new_category__' } });
  fireEvent.change(screen.getByLabelText('New category name'), { target: { value: '  Christmas ' } });
  fireEvent.click(screen.getByRole('button', { name: /Create/ }));
  await waitFor(() => expect(latest).toBe('7'));
  expect(create).toHaveBeenCalledWith('Christmas');
  expect(screen.queryByLabelText('New category name')).not.toBeInTheDocument();
});

test('an existing name is selected instead of duplicated', () => {
  const create = jest.fn();
  render(<Harness onCreateCategory={create} />);
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: '__new_category__' } });
  fireEvent.change(screen.getByLabelText('New category name'), { target: { value: 'kids' } });
  fireEvent.keyDown(screen.getByLabelText('New category name'), { key: 'Enter' });
  expect(create).not.toHaveBeenCalled();
  expect(latest).toBe('2');
});

test('Escape and Cancel go back to the dropdown without changing it', () => {
  render(<Harness onCreateCategory={jest.fn()} />);
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: '__new_category__' } });
  fireEvent.keyDown(screen.getByLabelText('New category name'), { key: 'Escape' });
  expect(screen.getByLabelText('Category')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: '__new_category__' } });
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(latest).toBe('');
});

test('a failed create keeps the name so it can be retried', async () => {
  const create = jest.fn().mockResolvedValue(null);
  render(<Harness onCreateCategory={create} />);
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: '__new_category__' } });
  fireEvent.change(screen.getByLabelText('New category name'), { target: { value: 'Bad' } });
  fireEvent.click(screen.getByRole('button', { name: /Create/ }));
  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(screen.getByLabelText('New category name')).toHaveValue('Bad');
  expect(latest).toBe('');
});

test('without a create handler there is no New category option', () => {
  render(<Harness />);
  const options = Array.from(screen.getByLabelText('Category').options).map(o => o.textContent);
  expect(options).not.toContain('+ New category…');
});
