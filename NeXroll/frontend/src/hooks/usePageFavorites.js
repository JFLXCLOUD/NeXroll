import { useCallback, useEffect, useRef, useState } from 'react';

export default function usePageFavorites(apiUrl, scope) {
  const [state, setState] = useState({ scope, pages: [], ready: false, error: '' });
  const [saving, setSaving] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  const request = useCallback(async (path, options = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(apiUrl(path), { ...options, signal: controller.signal, cache: 'no-store' });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Favorites could not be saved.');
      if (!Array.isArray(body.pages)) throw new Error('Favorites are unavailable.');
      return body.pages;
    } finally { clearTimeout(timeout); }
  }, [apiUrl]);
  const refresh = useCallback(async () => {
    if (pending.current) return;
    const token = generation.current;
    try {
      const pages = await request('navigation/favorites');
      if (token === generation.current && !pending.current) setState({ scope, pages, ready: true, error: '' });
    } catch {
      if (token === generation.current) setState(old => ({ ...old, scope, error: 'Unable to load Favorites. Try again.' }));
    }
  }, [request, scope]);
  useEffect(() => {
    generation.current += 1; pending.current = false; setSaving(false);
    setState({ scope, pages: [], ready: false, error: '' });
    refresh();
    window.addEventListener('focus', refresh);
    return () => { generation.current += 1; window.removeEventListener('focus', refresh); };
  }, [scope, refresh]);
  const toggle = async page => {
    if (pending.current || !state.ready || state.scope !== scope) return;
    pending.current = true; setSaving(true);
    const token = ++generation.current;
    try {
      const pages = await request(`navigation/favorites/${page}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ favorite: !state.pages.includes(page) }),
      });
      if (token === generation.current) setState({ scope, pages, ready: true, error: '' });
    } catch {
      if (token === generation.current) setState(old => ({ ...old, error: 'Favorites could not be saved. Try again.' }));
    } finally { if (token === generation.current) { pending.current = false; setSaving(false); } }
  };
  return { pages: state.scope === scope ? state.pages : [], ready: state.scope === scope && state.ready,
    error: state.scope === scope ? state.error : '', saving, toggle, refresh };
}
