import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import TimezoneNotice from './TimezoneNotice';
import { browserTimeZone } from '../utils/timezones';

const NOW = new Date(Date.UTC(2026, 10, 3, 0, 47));
const DEVICE = browserTimeZone();
// A zone on a different offset from whatever zone the tests run in.
const OTHER = -NOW.getTimezoneOffset() === 330 ? 'UTC' : 'Asia/Kolkata';

beforeEach(() => localStorage.clear());

test('says when NeXroll runs on another clock and switches it to this device\'s', async () => {
  const onUse = jest.fn(() => Promise.resolve(true));
  render(<TimezoneNotice timeZone={OTHER} now={NOW} onUse={onUse} />);
  expect(screen.getByText(`Schedules run on ${OTHER} time, not this device's`)).toBeInTheDocument();
  expect(screen.getByText(/A schedule set for 10:00\sPM starts at/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: `Use ${DEVICE}` }));
  await waitFor(() => expect(onUse).toHaveBeenCalledWith(DEVICE));
});

test('stays hidden while both clocks agree', () => {
  const { container } = render(<TimezoneNotice timeZone={DEVICE} now={NOW} onUse={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

test('Keep hides it in this browser until either zone changes', () => {
  const { unmount } = render(<TimezoneNotice timeZone={OTHER} now={NOW} onUse={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: `Keep ${OTHER}` }));
  expect(screen.queryByText(/Schedules run on/)).not.toBeInTheDocument();
  unmount();
  const again = render(<TimezoneNotice timeZone={OTHER} now={NOW} onUse={() => {}} />);
  expect(again.container).toBeEmptyDOMElement();
  again.unmount();
  const third = OTHER === 'UTC' ? 'Asia/Tokyo' : 'UTC';
  render(<TimezoneNotice timeZone={third} now={NOW} onUse={() => {}} />);
  expect(screen.getByText(`Schedules run on ${third} time, not this device's`)).toBeInTheDocument();
});
