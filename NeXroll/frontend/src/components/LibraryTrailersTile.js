import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Library, ArrowRight, RefreshCw } from 'lucide-react';

export default function LibraryTrailersTile({ apiUrl, onOpen, detail = 'detailed' }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const mounted = useRef(false);
  const pending = useRef(false);
  const startingRef = useRef(false);
  const refresh = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(apiUrl('nexup/library/settings'), { signal: controller.signal, cache: 'no-store' });
      if (!response.ok) throw new Error('Unable to refresh Library Trailers.');
      const next = await response.json();
      if (!next?.summary || !next?.config || !next?.sync) throw new Error('Library Trailers status is unavailable.');
      if (mounted.current) { setData(next); setError(''); }
    } catch (e) { if (mounted.current) setError(e.name === 'AbortError' ? 'Library Trailers status timed out.' : e.message); }
    finally { clearTimeout(timer); pending.current = false; }
  }, [apiUrl]);
  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = setInterval(refresh, 5000);
    window.addEventListener('focus', refresh);
    return () => { mounted.current = false; clearInterval(timer); window.removeEventListener('focus', refresh); };
  }, [refresh]);
  const sync = async () => {
    if (startingRef.current || data?.sync?.running) return;
    startingRef.current = true; setStarting(true); setError('');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(apiUrl('nexup/library/sync'), { method: 'POST', signal: controller.signal });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Unable to start Library Trailers sync.');
      if (mounted.current) setData(previous => ({ ...previous, sync: { ...previous.sync, running: true, status: 'Starting sync...' } }));
    } catch (e) { if (mounted.current) setError(e.message); }
    finally { clearTimeout(timeout); startingRef.current = false; if (mounted.current) setStarting(false); }
  };
  const busy = starting || data?.sync?.running;
  const summary = data?.summary;
  const config = data?.config;
  const last = data?.sync?.finished_at;
  const lastDate = last ? new Date(/Z$|[+-]\d\d:\d\d$/.test(last) ? last : `${last}Z`) : null;
  return <div className="card nx-focus-tile nx-library-trailers-tile">
    <div className="nx-tile-head"><h2><Library size={16} /> Library Trailers</h2>
      <button className="nx-card-link nx-no-drag" onPointerDown={e => e.stopPropagation()} onClick={onOpen}>Open <ArrowRight size={12} /></button></div>
    {!data ? <p className="nx-focus-sub">{error || 'Loading Library Trailers...'}</p> : <>
      <p className="nx-tile-bignum">{summary.local + summary.downloaded} <span className="nx-tile-bignum-unit">available</span></p>
      <div className="nx-tile-rows">
        <div className="nx-tile-row"><span>Local trailers</span><strong>{summary.local}</strong></div>
        <div className="nx-tile-row"><span>Downloaded</span><strong>{summary.downloaded}</strong></div>
        {detail === 'detailed' && <>
          <div className="nx-tile-row"><span>Download storage</span><strong>{summary.downloaded_gb} / {config.max_gb} GB</strong></div>
          <div className="nx-tile-row"><span>Outside selection</span><strong>{summary.outside}</strong></div>
          <div className="nx-tile-row"><span>Errors</span><strong>{summary.errors}</strong></div>
        </>}
      </div>
      <p className="nx-focus-sub" role="status">{busy ? data.sync.status || 'Syncing...' : data.sync.error ? `Sync failed: ${data.sync.error}` : lastDate && !Number.isNaN(lastDate.getTime()) ? `Last sync: ${lastDate.toLocaleString()}` : 'No sync completed since restart.'}</p>
      {!config.enabled ? <p className="nx-focus-sub">Enable Library Trailers to sync.</p> : !data.radarr_connected && <p className="nx-focus-sub">Connect Radarr to sync your library.</p>}
    </>}
    {error && data && <p role="alert" className="nx-focus-sub">{error}</p>}
    <div className="nx-library-trailers-actions">
      <button type="button" className="nx-dash-action nx-no-drag" onPointerDown={e => e.stopPropagation()} onClick={sync}
        disabled={!config?.enabled || !data?.radarr_connected || busy || Boolean(error)}>
        <RefreshCw size={14} className={busy ? 'spin' : ''} /> {busy ? 'Syncing...' : 'Sync Library Trailers'}
      </button>
      {error && <button type="button" className="nx-card-link nx-no-drag" onPointerDown={e => e.stopPropagation()} onClick={refresh}>Retry status</button>}
    </div>
  </div>;
}
