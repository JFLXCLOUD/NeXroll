import React, { useState } from 'react';
import { Globe } from 'lucide-react';
import { browserTimeZone, zoneOffsetMinutes, zoneTimeLabel } from '../utils/timezones';

/**
 * Shown on the Dashboard and Schedules when NeXroll's timezone is on a
 * different offset from this device's. Issue #50: an install left on the
 * default UTC ran a Central-time user's schedules six hours early, and nothing
 * on the page said so. "Use <zone>" switches NeXroll to this device's zone;
 * "Keep" hides the notice in this browser until either zone changes.
 *
 * Props: timeZone (NeXroll's), onUse(zone) -> Promise, now (optional Date).
 */
const DISMISS_KEY = 'nx_timezone_notice_dismissed';

const readDismissed = () => {
  try {
    return localStorage.getItem(DISMISS_KEY) || '';
  } catch {
    return '';
  }
};

const timeLabel = date => date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

export default function TimezoneNotice({ timeZone, onUse, now = new Date() }) {
  const [dismissed, setDismissed] = useState(readDismissed);
  const [busy, setBusy] = useState(false);
  const device = browserTimeZone();
  const serverOffset = zoneOffsetMinutes(timeZone, now);
  const deviceOffset = -now.getTimezoneOffset();
  const pair = `${timeZone}|${device || ''}`;
  if (!timeZone || serverOffset === null || serverOffset === deviceOffset || dismissed === pair) return null;

  // Where a schedule set for 10 PM on NeXroll's clock lands on this device.
  const tenPm = new Date(2000, 0, 1, 22, 0);
  const landsAt = new Date(tenPm.getTime() + (deviceOffset - serverOffset) * 60000);

  const keep = () => {
    try { localStorage.setItem(DISMISS_KEY, pair); } catch { /* shows again next visit */ }
    setDismissed(pair);
  };
  const use = async () => {
    setBusy(true);
    try {
      await onUse(device);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="nx-tz-notice" role="status">
      <Globe size={18} aria-hidden="true" />
      <div className="nx-tz-notice-text">
        <strong>Schedules run on {timeZone} time, not this device&apos;s</strong>
        <span>
          It&apos;s {zoneTimeLabel(timeZone, now)} on NeXroll&apos;s clock and {timeLabel(now)} here
          {device ? ` (${device})` : ''}. A schedule set for {timeLabel(tenPm)} starts at {timeLabel(landsAt)} here.
        </span>
      </div>
      <div className="nx-tz-notice-actions">
        {device && (
          <button type="button" className="button" disabled={busy} onClick={use}>
            {busy ? 'Saving...' : `Use ${device}`}
          </button>
        )}
        <button type="button" className="button button-secondary" disabled={busy} onClick={keep}>
          Keep {timeZone}
        </button>
      </div>
    </div>
  );
}
