import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import NexUpApprovedPages from './NexUpApprovedPages';

// NeX-Up > Settings: a PO-token provider that still runs but is older than
// the release NeXroll installs is offered as an update (2.0.0 keeps running;
// 2.0.1 and 2.0.2 are dependency security releases), and the TMDB key text no
// longer talks about a built-in key (TMDB revoked it; none ships now).
const openSettings = ({ status = {}, settings = {} } = {}) => {
  const onInstallPotoken = jest.fn();
  render(<NexUpApprovedPages activeTab="nexup/settings" settings={{ storage_path: 'C:/trailers', ...settings }}
    storage={{ total_size_gb: 1.2 }} potoken={{ status }} youtubeSetup={{ status: {} }}
    onUpdateSettings={() => {}} onOpenFolder={() => {}} onTestPotoken={() => {}}
    onConfigureYoutube={() => {}} onInstallPotoken={onInstallPotoken} onTestTmdbKey={() => {}} />);
  return onInstallPotoken;
};

const RUNNING_2_0_0 = {
  installed: true, healthy: true, outdated: false, update_available: true,
  installed_version: '2.0.0', required_version: '2.0.0', recommended_version: '2.0.2',
};

test('a provider older than the current release offers Update and stays ready', () => {
  const onInstallPotoken = openSettings({ status: RUNNING_2_0_0 });
  expect(screen.getByText(/Version 2\.0\.0 works; 2\.0\.2 updates its dependencies/)).toBeInTheDocument();
  expect(screen.getByText('PO-token provider is configured')).toBeInTheDocument();
  expect(screen.queryByText('Update the PO-token provider')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Update' }));
  expect(onInstallPotoken).toHaveBeenCalledTimes(1);
});

test('the current release shows Installed and no Update button', () => {
  openSettings({ status: { ...RUNNING_2_0_0, update_available: false, installed_version: '2.0.2' } });
  expect(screen.getByText('Installed and available.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Update' })).not.toBeInTheDocument();
});

test('a provider below the minimum still gets the security warning', () => {
  openSettings({ status: { installed: true, outdated: true, update_available: false, installed_version: '1.3.1', required_version: '2.0.0' } });
  expect(screen.getByText('Update the PO-token provider')).toBeInTheDocument();
  expect(screen.getByText(/has a security flaw fixed in 2\.0\.0/)).toBeInTheDocument();
});

test('the TMDB key text no longer mentions a built-in key', () => {
  openSettings({ settings: { trailer_language: 'de-DE', trailer_languages: [{ code: 'en', label: 'English' }, { code: 'de-DE', label: 'German' }] } });
  expect(screen.getByText(/Finds more trailers to try when Radarr's link fails/)).toBeInTheDocument();
  expect(screen.getByText(/which needs your own free API key/)).toBeInTheDocument();
  expect(screen.queryByText(/built into NeXroll/)).not.toBeInTheDocument();
});
