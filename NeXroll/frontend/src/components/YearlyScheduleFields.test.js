import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import YearlyScheduleFields from './YearlyScheduleFields';
import { buildRecurrencePattern, normalizeScheduleDateForStorage } from '../utils/scheduleUtils';

function Editor({ initial = { start_date: '', end_date: '' } }) {
  const [value, setValue] = useState(initial);
  return <><YearlyScheduleFields value={value} onChange={setValue} /><output data-testid="saved">{JSON.stringify(value)}</output></>;
}
const saved = () => JSON.parse(screen.getByTestId('saved').textContent);

test('creates a year-free seasonal range and can return to all year', () => {
  const { container } = render(<Editor />);
  fireEvent.change(screen.getByLabelText('Yearly date range'), { target: { value: 'range' } });
  fireEvent.change(screen.getByLabelText('Starts month'), { target: { value: '12' } });
  fireEvent.change(screen.getByLabelText('Starts day'), { target: { value: '15' } });
  fireEvent.change(screen.getByLabelText('Ends day'), { target: { value: '15' } });
  expect(saved()).toEqual({ start_date: '2000-12-15T00:00', end_date: '2000-01-15T23:59' });
  expect(container.querySelector('input[type="datetime-local"]')).toBeNull();
  expect(screen.getByText(/wraps into the next year/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Yearly date range'), { target: { value: 'all' } });
  expect(saved().end_date).toBe('');
});

test('editing legacy dates keeps first and last day times', () => {
  render(<Editor initial={{ start_date: '2023-10-01T18:30', end_date: '2023-10-31T03:15' }} />);
  expect(screen.getByLabelText('Starts time').value).toBe('18:30');
  expect(screen.getByLabelText('Ends time').value).toBe('03:15');
  fireEvent.change(screen.getByLabelText('Starts day'), { target: { value: '2' } });
  expect(saved().start_date).toBe('2000-10-02T18:30');
  expect(normalizeScheduleDateForStorage('yearly', saved().end_date)).toBe('2000-10-31T03:15');
});

test('month changes cannot save impossible dates and February offers leap day', () => {
  render(<Editor initial={{ start_date: '2000-01-31T00:00', end_date: '2000-03-01T23:59' }} />);
  fireEvent.change(screen.getByLabelText('Starts month'), { target: { value: '2' } });
  expect(saved().start_date).toBe('2000-02-29T00:00');
  expect(screen.getByLabelText('Starts day').options.length).toBe(29);
  expect(screen.getByText(/only in leap years/)).toBeTruthy();
});

test('linked annual holidays retain their first year and dynamic holiday identity', () => {
  const initial = { start_date: '2027-11-25T00:00', end_date: '2027-11-25T23:59', holiday_name: 'Thanksgiving', holiday_country: 'US' };
  render(<Editor initial={initial} />);
  expect(screen.getByText(/starting in 2027/)).toBeTruthy();
  expect(screen.queryByLabelText('Yearly date range')).toBeNull();
  expect(saved()).toEqual(initial);
});

test('yearly daily time windows persist without inheriting other form types constraints', () => {
  expect(buildRecurrencePattern({ type: 'yearly', timeRange: { start: '22:00', end: '03:00' }, weekDays: ['monday'], selectedMonths: [8], monthDays: [1] }))
    .toEqual({ timeRange: { start: '22:00', end: '03:00' } });
});
