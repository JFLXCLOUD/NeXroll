import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PluginPlayback, { pluginPlaysExactList, legacyPluginWarning } from './PluginPlayback';

const apiUrl = p => '/' + p;

test.each([
  ['1.14.0.0', false], ['1.14.1.0', true], ['1.15.0.0', false], ['1.15.1.0', true],
  ['1.16.0.0', true], ['2.0.0.0', true], ['', null], ['garbage', null],
])('plugin %s plays the exact list: %s', (version, expected) => {
  expect(pluginPlaysExactList(version)).toBe(expected);
});

test('an older Emby plugin always warns, since it defaults to one preroll', () => {
  expect(legacyPluginWarning('emby', '1.14.0.0', 0)).toMatch(/only the first 1 preroll NeXroll sends \(1 by default\)/);
  expect(legacyPluginWarning('emby', '1.14.0.0', 3)).toMatch(/only the first 3 prerolls/);
});

test('an older Jellyfin plugin warns only when Max intros caps the list', () => {
  expect(legacyPluginWarning('jellyfin', '1.14.0.0', 1)).toMatch(/Max intros = 1, so sequences stop after 1 preroll\./);
  expect(legacyPluginWarning('jellyfin', '1.15.0.0', 0)).toBeNull();
});

test('current plugins never warn', () => {
  expect(legacyPluginWarning('jellyfin', '1.15.1.0', 1)).toBeNull();
  expect(legacyPluginWarning('emby', '1.14.1.0', 0)).toBeNull();
});

test('loads and saves the random-category count', async () => {
  global.fetch = jest.fn((url, options) => {
    if (options && options.method === 'PUT') {
      return Promise.resolve({ ok: true, json: async () => ({ random_count: JSON.parse(options.body).random_count, max: 20 }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ random_count: 1, max: 20 }) });
  });
  render(<PluginPlayback apiUrl={apiUrl} server="jellyfin" pluginVersion="1.14.1.0" maxIntros={0} />);
  const input = screen.getByLabelText('Prerolls from a random category');
  await waitFor(() => expect(input).toHaveValue(1));
  fireEvent.change(input, { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: /Save/ }));
  expect(await screen.findByText(/Saved\. It applies from the next movie or episode\./)).toBeInTheDocument();
  const put = fetch.mock.calls.find(([, o]) => o && o.method === 'PUT');
  expect(put[0]).toBe('/settings/plugin-playback');
  expect(JSON.parse(put[1].body)).toEqual({ random_count: 2 });
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('refuses a count outside the range without calling the server', async () => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => ({ random_count: 1, max: 20 }) }));
  render(<PluginPlayback apiUrl={apiUrl} server="emby" pluginVersion="1.14.0.0" maxIntros={0} />);
  const input = screen.getByLabelText('Prerolls from a random category');
  await waitFor(() => expect(input).toHaveValue(1));
  fireEvent.change(input, { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: /Save/ }));
  expect(await screen.findByText('Choose between 1 and 20.')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([, o]) => o && o.method === 'PUT')).toBe(false);
  expect(screen.getByRole('alert')).toHaveTextContent(/Download the updated plugin/);
});
