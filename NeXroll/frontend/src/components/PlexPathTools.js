import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle, XCircle, HelpCircle, Search, FolderOpen, Folder, ChevronLeft, RefreshCw, Film, X } from 'lucide-react';

// Tools for the Plex side of path mapping. Everything here asks the Plex
// server itself, through the folder browser Plex Web uses when you add a
// library folder, so it shows exactly what Plex can open. Plex-only: the
// Jellyfin and Emby plugin downloads prerolls from NeXroll and needs no path.

async function readJson(response) {
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!response.ok) {
    const detail = data && (typeof data.detail === 'string' ? data.detail : data.detail?.message || data.message);
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

export function StatusIcon({ status, size = 15 }) {
  if (status === 'visible') return <CheckCircle size={size} className="nx-plexpath-ok" aria-label="Plex can see this file" />;
  if (status === 'missing') return <XCircle size={size} className="nx-plexpath-bad" aria-label="Plex cannot see this file" />;
  return <HelpCircle size={size} className="nx-plexpath-unknown" aria-label="Could not check" />;
}

// Plex reports its host OS by internal name ("MacOSX"); show the familiar one.
export function platformName(platform) {
  return { MacOSX: 'macOS', Windows: 'Windows', Linux: 'Linux' }[platform] || platform;
}

export function statusText(status) {
  if (status === 'visible') return 'Plex can open this file';
  if (status === 'missing') return 'Plex cannot open this file';
  return 'Could not check with Plex';
}

// "Can Plex open your prerolls?" for whatever is in Plex's preroll setting now.
export function PlexPathCheck({ apiUrl, refreshKey = 0, onResult }) {
  const [state, setState] = useState({ loading: true });
  const mounted = useRef(true);
  const report = useRef(onResult);
  report.current = onResult;
  const run = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: '' }));
    try {
      const data = await readJson(await fetch(apiUrl('plex/preroll-check'), { cache: 'no-store' }));
      if (mounted.current) setState({ loading: false, data });
      const results = data?.results || [];
      if (report.current) report.current({
        total: results.length,
        missing: results.filter(r => r.status === 'missing').length,
        unknown: results.filter(r => r.status === 'unknown').length,
        platform: data?.platform || null,
      });
    } catch (e) {
      if (mounted.current) setState({ loading: false, error: e.message });
      if (report.current) report.current(null);
    }
  }, [apiUrl]);
  useEffect(() => { mounted.current = true; run(); return () => { mounted.current = false; }; }, [run, refreshKey]);

  const { loading, data, error } = state;
  const results = data?.results || [];
  const missing = results.filter(r => r.status === 'missing');
  const visible = results.filter(r => r.status === 'visible');
  let tone = 'unknown';
  let headline = 'Checking with Plex...';
  if (!loading && error) { headline = `Could not check with Plex: ${error}`; }
  else if (!loading && data && data.reachable === false) { headline = 'Plex did not answer, so its preroll setting could not be read.'; }
  else if (!loading && data && !results.length) { headline = data.message || 'Plex has no preroll set yet.'; }
  else if (!loading && data) {
    if (missing.length === 0 && visible.length) { tone = 'ok'; headline = `Plex can open all ${results.length} preroll file${results.length === 1 ? '' : 's'} it is set to play.`; }
    else if (missing.length === results.length) { tone = 'bad'; headline = `Plex cannot open any of the ${results.length} preroll file${results.length === 1 ? '' : 's'} it is set to play, so nothing will play before your movies.`; }
    else if (missing.length) { tone = 'warn'; headline = `Plex cannot open ${missing.length} of the ${results.length} preroll files it is set to play.`; }
    else { headline = 'Plex could not be asked about these files.'; }
  }

  return (
    <div className={`nx-plexpath-check nx-plexpath-tone-${tone}`} role="status" aria-live="polite">
      <div className="nx-plexpath-check-head">
        {tone === 'ok' ? <CheckCircle size={18} className="nx-plexpath-ok" /> : tone === 'unknown' ? <HelpCircle size={18} className="nx-plexpath-unknown" /> : <XCircle size={18} className="nx-plexpath-bad" />}
        <div className="nx-plexpath-check-text">
          <strong>Can Plex open your prerolls?</strong>
          <span>{headline}</span>
        </div>
        <button type="button" className="button nx-plexpath-ghost" onClick={run} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> {loading ? 'Checking' : 'Check again'}
        </button>
      </div>
      {missing.length > 0 && (
        <ul className="nx-plexpath-list">
          {missing.slice(0, 8).map(r => (
            <li key={r.path}>
              <code>{r.path}</code>
              <span>{r.reason}</span>
            </li>
          ))}
          {missing.length > 8 && <li className="nx-plexpath-more">and {missing.length - 8} more</li>}
        </ul>
      )}
      {data && data.enabled === false && (
        <p className="nx-plexpath-note">The check before applying is turned off (NEXROLL_PLEX_PATH_CHECK=0), so NeXroll will not leave these out.</p>
      )}
    </div>
  );
}

// "Find it for me": search the Plex server for NeXroll's preroll folder.
export function FindPlexFolder({ apiUrl, onUseMapping }) {
  const [state, setState] = useState({ phase: 'idle' });
  const search = async () => {
    setState({ phase: 'searching' });
    try {
      const data = await readJson(await fetch(apiUrl('settings/path-mappings/detect'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      }));
      setState({ phase: 'done', data });
    } catch (e) {
      setState({ phase: 'done', error: e.message });
    }
  };
  const { phase, data, error } = state;
  return (
    <div className="nx-plexpath-find">
      <div className="nx-plexpath-find-head">
        <div>
          <strong>Find it for me</strong>
          <span>NeXroll looks through the folders your Plex server can see for the one holding your prerolls, and sets up the mapping.</span>
        </div>
        <button type="button" className="button nx-plexpath-primary" onClick={search} disabled={phase === 'searching'}>
          <Search size={14} /> {phase === 'searching' ? 'Searching Plex...' : 'Find it for me'}
        </button>
      </div>
      {phase === 'searching' && <p className="nx-plexpath-note">Searching the Plex server's folders. This can take up to half a minute on a large server.</p>}
      {phase === 'done' && error && <p className="nx-plexpath-result nx-plexpath-tone-bad">{error}</p>}
      {phase === 'done' && data && !data.found && <p className="nx-plexpath-result nx-plexpath-tone-bad">{data.reason}</p>}
      {phase === 'done' && data?.found && data.already_working && (
        <p className="nx-plexpath-result nx-plexpath-tone-ok">
          Your mappings already work: Plex opens NeXroll's preroll folder as <code>{data.plex_folder}</code>.
        </p>
      )}
      {phase === 'done' && data?.found && !data.already_working && !data.mapping_needed && (
        <p className="nx-plexpath-result nx-plexpath-tone-ok">
          Plex sees NeXroll's preroll folder at the same path, <code>{data.plex_folder}</code>, so no mapping is needed.
        </p>
      )}
      {phase === 'done' && data?.found && data.mapping_needed && data.suggestion && (
        <div className="nx-plexpath-result nx-plexpath-tone-ok">
          <p>Found it. Plex sees NeXroll's preroll folder under a different path:</p>
          <div className="nx-plexpath-pair">
            <div><span>NeXroll</span><code>{data.suggestion.local}</code></div>
            <div aria-hidden="true" className="nx-plexpath-arrow">{'→'}</div>
            <div><span>Plex</span><code>{data.suggestion.plex}</code></div>
          </div>
          <p className="nx-plexpath-note">
            {data.used_marker
              ? 'Confirmed with a small test file NeXroll placed in the folder and then removed.'
              : `Confirmed by finding ${data.verified?.length || 0} of your prerolls there.`}
          </p>
          {state.added
            ? <p className="nx-plexpath-added"><CheckCircle size={15} className="nx-plexpath-ok" /> Mapping added. Plex gets these paths the next time NeXroll applies your prerolls.</p>
            : (
              <button type="button" className="button nx-plexpath-primary" disabled={state.adding} onClick={async () => {
                setState(s => ({ ...s, adding: true }));
                const ok = await onUseMapping(data.suggestion);
                setState(s => ({ ...s, adding: false, added: ok !== false }));
              }}>
                {state.adding ? 'Adding...' : 'Add this mapping'}
              </button>
            )}
        </div>
      )}
    </div>
  );
}

// Folder picker over the Plex server's filesystem.
export function PlexFolderPicker({ apiUrl, open, initialPath = '', onPick, onClose }) {
  const [path, setPath] = useState('');
  const [state, setState] = useState({ loading: false });
  const load = useCallback(async (p) => {
    setState({ loading: true });
    try {
      const data = await readJson(await fetch(apiUrl(`plex/browse?path=${encodeURIComponent(p || '')}`), { cache: 'no-store' }));
      setPath(data.path || '');
      setState({ loading: false, data });
    } catch (e) {
      setState({ loading: false, error: e.message });
    }
  }, [apiUrl]);
  useEffect(() => { if (open) load(initialPath || ''); }, [open, initialPath, load]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  const { loading, data, error } = state;
  const atRoot = !path;
  return (
    <div className="nx-modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="nx-modal nx-plexpath-picker" role="dialog" aria-modal="true" aria-labelledby="nx-plexpath-picker-title" onClick={e => e.stopPropagation()}>
        <div className="nx-modal-header">
          <div className="nx-modal-heading">
            <h3 id="nx-plexpath-picker-title" className="nx-modal-title">Browse the Plex server</h3>
            <p className="nx-plexpath-subtitle">These are the folders Plex itself can see{data?.platform ? ` on ${platformName(data.platform)}` : ''}. Pick the one that holds your prerolls.</p>
          </div>
          <button type="button" className="nx-modal-close" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="nx-modal-body nx-plexpath-picker-body">
        <div className="nx-plexpath-crumb">
          <button type="button" className="button nx-plexpath-ghost" disabled={atRoot || loading}
            onClick={() => load(data?.parent || '')}>
            <ChevronLeft size={14} /> Up
          </button>
          <code title={path || 'Top level'}>{path || 'Top level'}</code>
        </div>
        <div className="nx-plexpath-folders">
          {loading && <p className="nx-plexpath-note">Asking Plex...</p>}
          {!loading && error && <p className="nx-plexpath-result nx-plexpath-tone-bad">{error}</p>}
          {!loading && data && (data.dirs || []).map(d => (
            <button type="button" key={d.path} className="nx-plexpath-folder" onClick={() => load(d.path)}>
              <Folder size={15} /> <span>{d.name}</span>
            </button>
          ))}
          {!loading && data && !atRoot && !(data.dirs || []).length && (
            <p className="nx-plexpath-note">No folders inside. If you expected some, Plex may not have permission to read this folder.</p>
          )}
        </div>
        {!loading && data && !atRoot && (
          <div className="nx-plexpath-videos">
            <Film size={14} />
            {data.video_count
              ? <span>{data.video_count} video{data.video_count === 1 ? '' : 's'} here, such as <em>{data.videos.slice(0, 3).join(', ')}</em></span>
              : <span>No videos directly in this folder.</span>}
          </div>
        )}
        </div>
        <div className="nx-plexpath-picker-foot">
          <button type="button" className="button nx-plexpath-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="button nx-plexpath-primary" disabled={atRoot || loading} onClick={() => onPick(path)}>
            <FolderOpen size={14} /> Use this folder
          </button>
        </div>
      </div>
    </div>
  );
}
