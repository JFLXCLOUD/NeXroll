import React, { useEffect, useState } from 'react';
import { AlertTriangle, Save } from 'lucide-react';

// How many prerolls Jellyfin and Emby play is decided by NeXroll, as it is for
// Plex: one from a random category (or the number set here), every block of a
// sequence. Plugins from 1.14.1 (Jellyfin 10.11, Emby) and 1.15.1 (Jellyfin 12)
// play exactly what NeXroll sends. Older ones still apply their own Max Intros,
// which is what used to cut sequences short, so this also says when an
// installed plugin needs updating.

// True when the plugin plays NeXroll's list as sent (1.14.1+ / 1.15.1+).
export function pluginPlaysExactList(version) {
  const parts = String(version || '').split('.').map((n) => parseInt(n, 10));
  if (parts.length < 3 || parts.some((n) => Number.isNaN(n))) return null; // unknown
  const [major, minor, patch] = parts;
  if (major !== 1) return major > 1;
  if (minor === 14 || minor === 15) return patch >= 1;
  return minor > 15;
}

// Why an older plugin will still cut sequences short, or null when it won't.
export function legacyPluginWarning(server, version, maxIntros) {
  if (pluginPlaysExactList(version) !== false) return null;
  const cap = Number(maxIntros) || 0;
  if (server === 'emby') {
    return `This Emby plugin (v${version}) plays only the first ${cap > 0 ? cap : 1} preroll${cap > 1 ? 's' : ''} NeXroll sends${cap > 0 ? '' : ' (1 by default)'}, so sequences are cut short. Download the updated plugin above, replace it in Emby's plugins folder and restart Emby.`;
  }
  if (cap > 0) {
    return `This plugin (v${version}) still applies Max intros = ${cap}, so sequences stop after ${cap} preroll${cap === 1 ? '' : 's'}. Update the plugin (a plugin installed from the NeXroll repository updates itself), or set Max intros to 0.`;
  }
  return null; // an older Jellyfin plugin with Max intros 0 plays what NeXroll sends
}

export default function PluginPlayback({ apiUrl, server, pluginVersion, maxIntros }) {
  const [count, setCount] = useState('');
  const [max, setMax] = useState(20);
  const [status, setStatus] = useState({ busy: false, msg: '', ok: true });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(apiUrl('settings/plugin-playback'), { cache: 'no-store' });
        const data = res.ok ? await res.json() : null;
        if (alive && data) { setCount(String(data.random_count)); setMax(data.max || 20); }
      } catch { /* keep the field empty; saving still works */ }
    })();
    return () => { alive = false; };
  }, [apiUrl]);

  const save = async () => {
    const n = parseInt(count, 10);
    if (!(n >= 1 && n <= max)) { setStatus({ busy: false, ok: false, msg: `Choose between 1 and ${max}.` }); return; }
    setStatus({ busy: true, ok: true, msg: '' });
    try {
      const res = await fetch(apiUrl('settings/plugin-playback'), {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ random_count: n }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error((data && data.detail) || `Could not save (${res.status})`);
      setCount(String(data.random_count));
      setStatus({ busy: false, ok: true, msg: 'Saved. It applies from the next movie or episode.' });
    } catch (e) {
      setStatus({ busy: false, ok: false, msg: e.message });
    }
  };

  const warning = legacyPluginWarning(server, pluginVersion, maxIntros);
  const serverName = server === 'emby' ? 'Emby' : 'Jellyfin';
  return (
    <div className="nx-plugin-playback">
      <label htmlFor={`nx-random-count-${server}`}>Prerolls from a random category</label>
      <div className="nx-plugin-playback-row">
        <input id={`nx-random-count-${server}`} type="number" min="1" max={max} value={count}
          onChange={(e) => setCount(e.target.value)} />
        <button type="button" className="button" onClick={save} disabled={status.busy}>
          <Save size={14} /> Save
        </button>
      </div>
      <small>
        How many prerolls {serverName} plays before each movie or episode when a random category is active.
        NeXroll picks them, working through the whole category before repeating. Sequences and categories set
        to play in order always play in full. The same setting covers Jellyfin and Emby.
      </small>
      {status.msg && <small className={status.ok ? 'nx-plugin-playback-ok' : 'nx-plugin-playback-bad'}>{status.msg}</small>}
      {warning && (
        <div className="nx-plugin-playback-warning" role="alert">
          <AlertTriangle size={16} /> <span>{warning}</span>
        </div>
      )}
    </div>
  );
}
