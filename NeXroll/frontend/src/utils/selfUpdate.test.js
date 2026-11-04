import { INSTALL_RUN_TIMEOUT_MS, NOT_PICKED_UP_MS, installRunFromReply, installRunLost, isInstallRunActive } from './selfUpdate';
import { compareVersions } from './versions';

const START = 1_000_000;
const run = (extra = {}) => ({ version: '2.3.1', requestId: 'abc123ef', phase: 'running', message: 'Starting the updater...', startedAt: START, ...extra });
const status = (state, extra = {}) => ({ state, message: `${state} message`, request_id: 'abc123ef', ...extra });

test('versions order like the backend: stable after its pre-releases, 2.10 after 2.9', () => {
  expect(compareVersions('2.3.1', '2.3.0')).toBe(1);
  expect(compareVersions('v2.3.0', '2.3.0')).toBe(0);
  expect(compareVersions('2.10.0', '2.9.9')).toBe(1);
  expect(compareVersions('2.3.0', '2.3.0-beta.4')).toBe(1);
  expect(compareVersions('2.3.0-rc.1', '2.3.0-beta.9')).toBe(1);
});

test('the updater steps show as they happen', () => {
  const reply = { current_version: '2.3.0', status: status('downloading') };
  expect(installRunFromReply(run(), reply, START + 5000)).toMatchObject({ phase: 'running', message: 'Downloading the installer...' });
});

test('the new version answering ends the run, whatever the updater last wrote', () => {
  const reply = { current_version: '2.3.1', status: status('restarting') };
  expect(installRunFromReply(run({ phase: 'restarting' }), reply, START + 60000).phase).toBe('done');
  expect(installRunFromReply(run(), { current_version: '2.3.2', status: null }, START).phase).toBe('done');
});

test('a status from an earlier update is not this one', () => {
  const reply = { current_version: '2.3.0', status: status('failed', { request_id: 'old0001' }) };
  expect(installRunFromReply(run(), reply, START + 5000)).toEqual(run());
});

test('an updater that never picks the request up is reported', () => {
  const reply = { current_version: '2.3.0', status: status('done', { request_id: 'old0001' }) };
  const result = installRunFromReply(run(), reply, START + NOT_PICKED_UP_MS + 1);
  expect(result.phase).toBe('failed');
  expect(result.message).toMatch(/NeXroll Updater/);
});

test('the updater giving up shows its reason', () => {
  for (const state of ['failed', 'up_to_date']) {
    const result = installRunFromReply(run(), { current_version: '2.3.0', status: status(state) }, START + 5000);
    expect(result).toMatchObject({ phase: 'failed', message: `${state} message` });
  }
});

test('NeXroll not answering is the restart, until it takes too long', () => {
  expect(installRunLost(run(), START + 30000)).toMatchObject({ phase: 'restarting' });
  expect(installRunLost(run({ phase: 'restarting' }), START + INSTALL_RUN_TIMEOUT_MS + 1).phase).toBe('failed');
  const stuck = { current_version: '2.3.0', status: status('installing') };
  expect(installRunFromReply(run(), stuck, START + INSTALL_RUN_TIMEOUT_MS + 1).phase).toBe('failed');
});

test('a finished run is left alone', () => {
  const done = run({ phase: 'done' });
  expect(isInstallRunActive(done)).toBe(false);
  expect(installRunFromReply(done, { current_version: '2.3.0', status: status('failed') })).toBe(done);
  expect(installRunLost(done)).toBe(done);
  expect(isInstallRunActive(null)).toBe(false);
});
