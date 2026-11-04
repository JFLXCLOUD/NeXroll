import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OnboardingWizard from './OnboardingWizard';
import { browserTimeZone } from '../utils/timezones';

const apiUrl = p => (p.startsWith('/') ? p : '/' + p);
const ok = (value) => Promise.resolve({ ok: true, status: 200, json: async () => value, text: async () => JSON.stringify(value) });

function mockServer({ plexConnected, docker }) {
  global.fetch = jest.fn((url) => {
    if (url.startsWith('/plex/status')) return ok({ connected: plexConnected });
    if (url.startsWith('/onboarding/status')) return ok({ is_rerun: false, users_exist: false, has_server: plexConnected });
    if (url.startsWith('/onboarding/docker-info')) {
      return ok({ is_docker: docker, prerolls_dir: docker ? '/data/prerolls' : 'C:\\ProgramData\\NeXroll\\Prerolls', mounts: [], mappings: [] });
    }
    return ok({});
  });
}

// Only Plex uses path mappings, so the Paths step follows Plex rather than Docker.
test.each([
  ['Plex connected on a Windows install', { plexConnected: true, docker: false }, true],
  ['nothing connected on a Windows install', { plexConnected: false, docker: false }, false],
  ['Docker before any server is connected', { plexConnected: false, docker: true }, true],
])('Paths step: %s', async (_, server, shown) => {
  mockServer(server);
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/plex/status', expect.anything()));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/onboarding/docker-info', expect.anything()));
  if (shown) expect(await screen.findByText('Paths')).toBeInTheDocument();
  else {
    await new Promise(r => setTimeout(r, 50));
    expect(screen.queryByText('Paths')).not.toBeInTheDocument();
  }
});

// Issue #50: schedules ran on UTC because nothing asked for a timezone.
function mockTimezones({ rerun, serverZone }) {
  const own = browserTimeZone();
  global.fetch = jest.fn((url, options = {}) => {
    if (url.startsWith('/onboarding/status')) return ok({ is_rerun: rerun, users_exist: rerun, has_server: false });
    if (url === '/settings/timezone' && options.method === 'PUT') return ok({ timezone: JSON.parse(options.body).timezone });
    if (url === '/settings/timezone') return ok({ timezone: serverZone });
    if (url === '/settings/timezones') return ok({ timezones: [{ value: 'UTC', label: 'UTC' }, { value: 'Europe/Paris', label: 'Europe/Paris' }, { value: own, label: own }] });
    return ok({});
  });
  return own;
}

const timezonePuts = () => fetch.mock.calls.filter(([url, options]) => url === '/settings/timezone' && options && options.method === 'PUT');

test('a fresh install still on UTC starts from this browser\'s timezone and saves it', async () => {
  const own = mockTimezones({ rerun: false, serverZone: 'UTC' });
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  const select = await screen.findByLabelText('Your timezone');
  await waitFor(() => expect(select).toHaveValue(own));
  fireEvent.click(screen.getByRole('button', { name: /Get started/ }));
  await waitFor(() => expect(timezonePuts()).toHaveLength(own === 'UTC' ? 0 : 1));
  if (own !== 'UTC') expect(JSON.parse(timezonePuts()[0][1].body)).toEqual({ timezone: own });
});

test('a rerun keeps the saved timezone unless it is changed, and skipping still saves a change', async () => {
  mockTimezones({ rerun: true, serverZone: 'Europe/Paris' });
  const onFinish = jest.fn();
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={onFinish} />);
  const select = await screen.findByLabelText('Your timezone');
  await waitFor(() => expect(select).toHaveValue('Europe/Paris'));
  fireEvent.click(screen.getByRole('button', { name: /Get started/ }));
  await new Promise(r => setTimeout(r, 20));
  expect(timezonePuts()).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: /Back/ }));
  fireEvent.change(await screen.findByLabelText('Your timezone'), { target: { value: 'UTC' } });
  fireEvent.click(screen.getByRole('button', { name: /Close the wizard/ }));
  await waitFor(() => expect(onFinish).toHaveBeenCalled());
  expect(JSON.parse(timezonePuts()[0][1].body)).toEqual({ timezone: 'UTC' });
});