/**
 * Settings > System > Install update (Windows installer builds).
 *
 * POST /update/install starts the NeXroll Updater task (backend/self_update.py),
 * which stops NeXroll, installs the release and starts it again. The page then
 * polls GET /update/install: its `status` is what the updater last wrote, and
 * `current_version` is the NeXroll answering. NeXroll is unreachable for a
 * minute or two in between.
 *
 * A run is { version, requestId, phase, message, startedAt }, phase being
 * 'running', 'restarting' (NeXroll not answering), 'done' or 'failed'.
 */
import { compareVersions } from './versions';

export const INSTALL_RUN_TIMEOUT_MS = 15 * 60 * 1000;
// The updater writes its first status within seconds of the task starting.
export const NOT_PICKED_UP_MS = 90 * 1000;

const STEP_MESSAGES = {
  starting: 'Starting the updater...',
  checking: 'Finding the release on GitHub...',
  downloading: 'Downloading the installer...',
  installing: 'Installing. NeXroll stops for a few minutes...',
  restarting: 'Starting NeXroll again...',
};

const TIMED_OUT = 'The update is taking longer than expected. update.log, in the update folder inside the NeXroll install folder, says what happened.';

export const isInstallRunActive = (run) => !!run && (run.phase === 'running' || run.phase === 'restarting');

const failed = (run, message) => ({ ...run, phase: 'failed', message });
const done = (run) => ({ ...run, phase: 'done', message: 'Reloading the page...' });

/** The run after a GET /update/install reply. */
export const installRunFromReply = (run, reply, now = Date.now()) => {
  if (!isInstallRunActive(run)) return run;
  // The new version answering is the end, whatever the updater last wrote.
  if (reply?.current_version && compareVersions(reply.current_version, run.version) >= 0) return done(run);
  const status = reply?.status;
  const ours = !!status && !!run.requestId && status.request_id === run.requestId;
  if (!ours) {
    if (now - run.startedAt > NOT_PICKED_UP_MS) {
      return failed(run, 'The updater did not start. Task Scheduler should list a task named NeXroll Updater; installing NeXroll by hand adds it again.');
    }
    return run;
  }
  if (status.state === 'failed' || status.state === 'up_to_date' || status.state === 'verified') {
    return failed(run, status.message || 'The update did not finish.');
  }
  if (status.state === 'done') return done(run);
  if (now - run.startedAt > INSTALL_RUN_TIMEOUT_MS) return failed(run, TIMED_OUT);
  return { ...run, phase: 'running', message: STEP_MESSAGES[status.state] || run.message };
};

/** The run when NeXroll doesn't answer. */
export const installRunLost = (run, now = Date.now()) => {
  if (!isInstallRunActive(run)) return run;
  if (now - run.startedAt > INSTALL_RUN_TIMEOUT_MS) return failed(run, TIMED_OUT);
  return { ...run, phase: 'restarting', message: 'NeXroll is restarting with the new version...' };
};
