import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PlexPathCheck, FindPlexFolder, PlexFolderPicker } from './PlexPathTools';

const apiUrl = p => '/' + p;
const reply = (value, ok = true, status = 200) =>
  Promise.resolve({ ok, status, text: async () => JSON.stringify(value) });

beforeEach(() => { global.fetch = jest.fn(); });

test('says plainly when Plex cannot open any of its prerolls, with each reason', async () => {
  fetch.mockImplementation(() => reply({
    plex_configured: true, reachable: true, enabled: true,
    results: [
      { path: '/data/prerolls/Halloween/a.m4v', status: 'missing', reason: 'Plex has no folder /data/prerolls.' },
      { path: '/data/prerolls/b.mp4', status: 'missing', reason: 'Plex has no folder /data/prerolls.' },
    ],
  }));
  render(<PlexPathCheck apiUrl={apiUrl} />);
  expect(await screen.findByText(/cannot open any of the 2 preroll files/)).toBeInTheDocument();
  expect(screen.getByText('/data/prerolls/Halloween/a.m4v')).toBeInTheDocument();
  expect(screen.getAllByText('Plex has no folder /data/prerolls.')).toHaveLength(2);
  expect(fetch).toHaveBeenCalledWith('/plex/preroll-check', expect.anything());
});

test('reports a healthy setup and re-checks on demand', async () => {
  fetch.mockImplementation(() => reply({
    plex_configured: true, reachable: true, results: [{ path: '/p/a.mp4', status: 'visible', reason: '' }],
  }));
  render(<PlexPathCheck apiUrl={apiUrl} />);
  expect(await screen.findByText('Plex can open all 1 preroll file it is set to play.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Check again/ }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});

test('reports a summary for the page header', async () => {
  fetch.mockImplementation(() => reply({
    plex_configured: true, reachable: true, platform: 'MacOSX',
    results: [{ path: '/a.mp4', status: 'visible' }, { path: '/b.mp4', status: 'missing', reason: 'x' }],
  }));
  const onResult = jest.fn();
  render(<PlexPathCheck apiUrl={apiUrl} onResult={onResult} />);
  await waitFor(() => expect(onResult).toHaveBeenCalledWith({ total: 2, missing: 1, unknown: 0, platform: 'MacOSX' }));
});

test('an error from the check is shown rather than a false all-clear', async () => {
  fetch.mockImplementation(() => reply({ detail: 'Plex refused' }, false, 502));
  render(<PlexPathCheck apiUrl={apiUrl} />);
  expect(await screen.findByText('Could not check with Plex: Plex refused')).toBeInTheDocument();
});

test('Find it for me proposes the mapping and hands it back when accepted', async () => {
  const suggestion = { local: '/data/prerolls', plex: '/Volumes/Plex/PreRoll' };
  fetch.mockImplementation(() => reply({ found: true, already_working: false, mapping_needed: true, suggestion, verified: ['a', 'b', 'c'] }));
  const onUse = jest.fn();
  render(<FindPlexFolder apiUrl={apiUrl} onUseMapping={onUse} />);
  fireEvent.click(screen.getByRole('button', { name: /Find it for me/ }));
  expect(await screen.findByText('/Volumes/Plex/PreRoll')).toBeInTheDocument();
  expect(screen.getByText('Confirmed by finding 3 of your prerolls there.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Add this mapping' }));
  expect(onUse).toHaveBeenCalledWith(suggestion);
  expect(await screen.findByText(/Mapping added\./)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add this mapping' })).not.toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe('/settings/path-mappings/detect');
  expect(fetch.mock.calls[0][1].method).toBe('POST');
});

test('Find it for me explains when nothing was found', async () => {
  fetch.mockImplementation(() => reply({ found: false, reason: 'No folder the Plex server can see contains NeXroll\'s prerolls.' }));
  render(<FindPlexFolder apiUrl={apiUrl} onUseMapping={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: /Find it for me/ }));
  expect(await screen.findByText(/No folder the Plex server can see/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add this mapping' })).not.toBeInTheDocument();
});

test('Find it for me says when no mapping is needed', async () => {
  fetch.mockImplementation(() => reply({ found: true, already_working: true, mapping_needed: false, plex_folder: '/data/Prerolls' }));
  render(<FindPlexFolder apiUrl={apiUrl} onUseMapping={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: /Find it for me/ }));
  expect(await screen.findByText(/Your mappings already work/)).toBeInTheDocument();
});

test('the picker walks Plex folders and returns the chosen one', async () => {
  const listings = {
    '': { path: '', parent: null, platform: 'Linux', dirs: [{ name: '/data', path: '/data' }] },
    '/data': { path: '/data', parent: '/', platform: 'Linux', dirs: [{ name: 'Prerolls', path: '/data/Prerolls' }], video_count: 0, videos: [] },
    '/data/Prerolls': { path: '/data/Prerolls', parent: '/data', platform: 'Linux', dirs: [], video_count: 2, videos: ['a.mp4', 'b.mp4'] },
  };
  fetch.mockImplementation(url => reply(listings[decodeURIComponent(url.split('path=')[1] || '')]));
  const onPick = jest.fn();
  render(<PlexFolderPicker apiUrl={apiUrl} open onPick={onPick} onClose={() => {}} />);
  expect(screen.getByRole('dialog', { name: 'Browse the Plex server' })).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: '/data' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Prerolls' }));
  expect(await screen.findByText(/2 videos here/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Use this folder/ }));
  expect(onPick).toHaveBeenCalledWith('/data/Prerolls');
});

test('the picker cannot choose the top level and closes on Escape', async () => {
  fetch.mockImplementation(() => reply({ path: '', parent: null, dirs: [{ name: '/', path: '/' }] }));
  const onClose = jest.fn();
  render(<PlexFolderPicker apiUrl={apiUrl} open onPick={() => {}} onClose={onClose} />);
  await screen.findByRole('button', { name: '/' });
  expect(screen.getByRole('button', { name: /Use this folder/ })).toBeDisabled();
  fireEvent.keyDown(window, { key: 'Escape' });
  expect(onClose).toHaveBeenCalled();
});
