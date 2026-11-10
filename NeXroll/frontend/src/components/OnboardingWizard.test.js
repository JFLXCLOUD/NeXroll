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
// Radarr/Sonarr and the preroll folder answer 200 for a failure, with the
// reason in the body. The wizard used to read every 200 as success.
function mockSetup(overrides = {}) {
  global.fetch = jest.fn((url, options = {}) => {
    for (const [prefix, answer] of Object.entries(overrides)) {
      if (url.startsWith(prefix)) return ok(typeof answer === 'function' ? answer(url, options) : answer);
    }
    if (url.startsWith('/onboarding/status')) return ok({ is_rerun: false, users_exist: false, has_server: false });
    if (url.startsWith('/onboarding/docker-info')) return ok({ is_docker: false, prerolls_dir: 'C:\\Prerolls', mounts: [], mappings: [], nexup_suggested_path: 'C:\\Prerolls\\nexup_trailers' });
    if (url.startsWith('/settings/preroll-folder')) return ok({ current_folder: 'C:\\Prerolls', default_folder: 'C:\\Prerolls', is_custom: false });
    return ok({});
  });
}
const openStep = async (label) => {
  fireEvent.click(await screen.findByRole('button', { name: label }));
};

test('a Radarr that refuses the key is not reported as connected', async () => {
  mockSetup({
    '/nexup/radarr/connect': { success: false, message: 'Invalid API key' },
    '/nexup/sonarr/connect': { success: true },
  });
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  await openStep('NeX-Up');
  fireEvent.change(screen.getByLabelText('Radarr URL'), { target: { value: 'http://radarr:7878' } });
  fireEvent.change(screen.getByLabelText('Radarr API Key'), { target: { value: 'wrong' } });
  fireEvent.change(screen.getByLabelText('Sonarr URL'), { target: { value: 'http://sonarr:8989' } });
  fireEvent.change(screen.getByLabelText('Sonarr API Key'), { target: { value: 'right' } });
  fireEvent.click(screen.getByRole('button', { name: /^Connect$/ }));
  expect(await screen.findByText(/Radarr did not connect: the API key was not accepted\. Sonarr connected\./)).toBeInTheDocument();
  // The trailer folder shown is kept, since NeX-Up downloads nothing without one.
  await waitFor(() => expect(fetch.mock.calls.some(([url, o]) => url.startsWith('/nexup/settings?storage_path=') && o.method === 'PUT')).toBe(true));
  await openStep('Finish');
  expect(screen.getByText('Sonarr connected')).toBeInTheDocument();
  // No media server: the last step says so instead of "You're all set!".
  expect(screen.getByText('One thing is still missing')).toBeInTheDocument();
});

test('a URL without its API key is called out, and nothing is sent', async () => {
  mockSetup();
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  await openStep('NeX-Up');
  fireEvent.change(screen.getByLabelText('Radarr URL'), { target: { value: 'http://radarr:7878' } });
  fireEvent.click(screen.getByRole('button', { name: /^Connect$/ }));
  expect(await screen.findByText('Radarr needs both the URL and the API key.')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.startsWith('/nexup/radarr/connect'))).toBe(false);
  // Leaving with it typed asks once, then lets you go.
  fireEvent.click(screen.getByRole('button', { name: /Skip for now/ }));
  expect(screen.getByText(/have not connected/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Continue without it/ }));
  expect(await screen.findByText('Preroll storage')).toBeInTheDocument();
});

test('a folder NeXroll cannot write to is not reported as saved', async () => {
  mockSetup({
    '/settings/preroll-folder': (url, options) => (options.method === 'PUT'
      ? { error: 'Folder is not writable: [WinError 3]' }
      : { current_folder: 'C:\\Prerolls', default_folder: 'C:\\Prerolls', is_custom: false }),
  });
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  await openStep('Storage');
  expect(await screen.findByText('C:\\Prerolls')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Use a different folder/), { target: { value: 'Z:\\nope' } });
  fireEvent.click(screen.getByRole('button', { name: /Save folder/ }));
  expect(await screen.findByText(/can't create or write to that folder/)).toBeInTheDocument();
});

test('reopening the wizard shows what is already connected', async () => {
  mockSetup({
    '/onboarding/status': { is_rerun: true, users_exist: true, has_server: true },
    '/jellyfin/status': { connected: true },
    '/nexup/settings': { radarr_connected: true, sonarr_connected: false, storage_path: 'C:\\Prerolls\\nexup_trailers' },
  });
  render(<OnboardingWizard apiUrl={apiUrl} darkMode onFinish={() => {}} />);
  await openStep('Media Server');
  expect(await screen.findByText('Jellyfin connected')).toBeInTheDocument();
  await openStep('NeX-Up');
  expect(screen.getByText(/Radarr is connected/)).toBeInTheDocument();
});
