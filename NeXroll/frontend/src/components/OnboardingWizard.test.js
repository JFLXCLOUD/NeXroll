import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import OnboardingWizard from './OnboardingWizard';

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
