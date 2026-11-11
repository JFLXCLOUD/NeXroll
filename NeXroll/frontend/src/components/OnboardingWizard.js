import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Rocket, Server, Sparkles, HardDrive, UserPlus, CheckCircle,
  ChevronLeft, ChevronRight, Loader2, ExternalLink, Check, AlertCircle,
  FolderSync, ArrowRight, Plus, X, Box, HelpCircle, FolderOpen
} from 'lucide-react';
import { FindPlexFolder, PlexFolderPicker, StatusIcon, statusText } from './PlexPathTools';
import { suggestedTimeZone } from '../utils/timezones';

/**
 * NeXroll v2 — First-run Onboarding Wizard
 *
 * Shown only for a genuinely fresh install (GET /onboarding/status -> needs_onboarding).
 * Walks the user through the essentials, reusing existing backend endpoints. Every
 * step after Welcome is skippable; the user can finish at any point and fill in the
 * rest later from the new sidebar pages.
 *
 * Props:
 *   apiUrl(path)   -> string         the App's API URL resolver
 *   darkMode       boolean           theme
 *   onFinish()                       called after POST /onboarding/complete succeeds
 */

// The Paths step only appears when Plex needs it (see showPaths), so the run's
// step list is built from this rather than being fixed.
const SERVER_LABELS = { plex: 'Plex', jellyfin: 'Jellyfin', emby: 'Emby' };

const BASE_STEPS = [
  { key: 'welcome', label: 'Welcome', icon: Rocket },
  { key: 'server', label: 'Media Server', icon: Server },
  { key: 'paths', label: 'Paths', icon: FolderSync, pathsStep: true },
  { key: 'nexup', label: 'NeX-Up', icon: Sparkles },
  { key: 'storage', label: 'Storage', icon: HardDrive },
  { key: 'account', label: 'Account', icon: UserPlus },
  { key: 'done', label: 'Finish', icon: CheckCircle },
];

function OnboardingWizard({ apiUrl, darkMode, onFinish }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [finishing, setFinishing] = useState(false);

  // --- Step state ---
  const [serverType, setServerType] = useState('plex'); // plex | jellyfin | emby
  // Which servers this wizard has already connected. NeXroll drives every
  // connected server at once, so the step is not done after the first one -
  // it offers to add the others rather than moving on as if you only have one.
  const [connectedServers, setConnectedServers] = useState([]);
  const [serverUrl, setServerUrl] = useState('');
  const [serverApiKey, setServerApiKey] = useState('');
  const [serverBusy, setServerBusy] = useState(false);
  const [serverResult, setServerResult] = useState(null); // {ok, msg}
  // Plex device login, run here rather than by sending the user to the Connect
  // page: that exit completed onboarding, so signing in meant leaving the wizard
  // for good.
  const [plexOAuth, setPlexOAuth] = useState({ id: null, url: '', status: 'idle' });
  const oauthPollRef = useRef(null);

  const [radarrUrl, setRadarrUrl] = useState('');
  const [radarrKey, setRadarrKey] = useState('');
  const [sonarrUrl, setSonarrUrl] = useState('');
  const [sonarrKey, setSonarrKey] = useState('');
  const [nexupBusy, setNexupBusy] = useState(false);
  const [nexupResult, setNexupResult] = useState(null);
  // What is connected, from this run or an earlier one ({radarr, sonarr}).
  const [arrConnected, setArrConnected] = useState({ radarr: false, sonarr: false });
  const [trailerFolderSaved, setTrailerFolderSaved] = useState(false);
  // The preroll folder in use ({current_folder, default_folder, is_custom}).
  const [folderInfo, setFolderInfo] = useState(null);
  // Steps the user has been on, and a reminder shown once before leaving a
  // step with something typed but not saved.
  const [visited, setVisited] = useState(() => new Set(['welcome']));
  const [leaveNote, setLeaveNote] = useState(null);
  // Trailer storage. Kept with the NeX-Up step because the folder only matters
  // once Radarr/Sonarr are downloading into it.
  const [nexupStorage, setNexupStorage] = useState('');
  const [nexupStorageBusy, setNexupStorageBusy] = useState(false);
  const [nexupStorageResult, setNexupStorageResult] = useState(null);
  const [storageCheck, setStorageCheck] = useState(null);

  const [storagePath, setStoragePath] = useState('');
  const [storageBusy, setStorageBusy] = useState(false);
  const [storageResult, setStorageResult] = useState(null);

  const [acctUser, setAcctUser] = useState('');
  const [acctPass, setAcctPass] = useState('');
  const [acctConfirm, setAcctConfirm] = useState('');
  const [acctEnableAuth, setAcctEnableAuth] = useState(true);
  const [acctBusy, setAcctBusy] = useState(false);
  const [acctResult, setAcctResult] = useState(null);

  // Path mappings. dockerInfo stays null off-container; installInfo always
  // carries the preroll folder and any saved mappings.
  const [dockerInfo, setDockerInfo] = useState(null);
  const [installInfo, setInstallInfo] = useState(null);
  const [install, setInstall] = useState(null); // {is_rerun, users_exist, has_server}
  const [pathRows, setPathRows] = useState([{ local: '', plex: '' }]);
  const [pathBusy, setPathBusy] = useState(false);
  const [pathResult, setPathResult] = useState(null);
  const [pathDirty, setPathDirty] = useState(false);
  const [pathHelpOpen, setPathHelpOpen] = useState(false);
  const [testPath, setTestPath] = useState('');
  const [testOut, setTestOut] = useState(null);
  // Whether Plex is connected, from this wizard or an earlier run. Only Plex
  // needs path mappings, and with it connected NeXroll can ask Plex directly.
  const [plexReady, setPlexReady] = useState(false);
  const [pickerRow, setPickerRow] = useState(null);

  // Timezone. Schedules run on NeXroll's clock, which stays on UTC until
  // someone picks a zone, and nothing used to ask (issue #50: a Central-time
  // install ran every schedule six hours early). A fresh install still on UTC
  // starts from this browser's zone.
  const [tzList, setTzList] = useState([]);
  const [tzServer, setTzServer] = useState(null);
  const [tzPicked, setTzPicked] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [current, list] = await Promise.all([
          fetch(apiUrl('/settings/timezone'), { credentials: 'include' }).then(r => (r.ok ? r.json() : null)),
          fetch(apiUrl('/settings/timezones'), { credentials: 'include' }).then(r => (r.ok ? r.json() : null)),
        ]);
        if (cancelled) return;
        if (list && Array.isArray(list.timezones)) setTzList(list.timezones);
        if (current && current.timezone) setTzServer(current.timezone);
      } catch { /* the step works without it; Settings has the same choice */ }
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(apiUrl('/plex/status'), { credentials: 'include' });
        const data = res.ok ? await res.json() : null;
        if (!cancelled && data && data.connected) {
          setPlexReady(true);
          setConnectedServers((prev) => (prev.includes('plex') ? prev : [...prev, 'plex']));
        }
      } catch { /* treated as not connected */ }
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  // What an earlier run already set up, so reopening the wizard shows it
  // instead of empty forms that look like nothing is connected.
  useEffect(() => {
    let cancelled = false;
    const read = async (path) => {
      try {
        const res = await fetch(apiUrl(path), { credentials: 'include' });
        return res.ok ? await res.json() : null;
      } catch { return null; }
    };
    ['jellyfin', 'emby'].forEach(async (kind) => {
      const data = await read(`/${kind}/status`);
      if (!cancelled && data && data.connected) {
        setConnectedServers((prev) => (prev.includes(kind) ? prev : [...prev, kind]));
      }
    });
    (async () => {
      const data = await read('/nexup/settings');
      if (cancelled || !data) return;
      setArrConnected({ radarr: !!data.radarr_connected, sonarr: !!data.sonarr_connected });
      if (data.storage_path) setTrailerFolderSaved(true);
    })();
    (async () => {
      const data = await read('/settings/preroll-folder');
      if (!cancelled && data && data.current_folder) setFolderInfo(data);
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(apiUrl('/onboarding/status'), { credentials: 'include' });
        if (res.ok && !cancelled) setInstall(await res.json());
      } catch { /* the wizard still works without it */ }
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(apiUrl('/onboarding/docker-info'), { credentials: 'include' });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled || !data) return;
        setInstallInfo(data);
        // Pre-fill trailer storage with whatever is configured, else the
        // recommended folder, so the common case is one click.
        setNexupStorage(data.nexup_storage_path || data.nexup_suggested_path || '');
        // Seed the first row with the one mapping every install needs: the
        // folder NeXroll writes prerolls into. The user only has to supply the
        // right-hand side, which is the half only they can know.
        if (Array.isArray(data.mappings) && data.mappings.length) setPathRows(data.mappings);
        else if (data.prerolls_dir) setPathRows([{ local: data.prerolls_dir, plex: '' }]);
        if (data.is_docker) setDockerInfo(data);
      } catch { /* not fatal: the step simply does not appear */ }
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  // The Paths step appears whenever Plex is connected, Docker or not (a Plex on
  // another computer needs a mapping just as much), and on Docker until a
  // server is chosen. Only Plex uses mappings, so an install connected only to
  // Jellyfin or Emby skips it.
  const pluginOnly = connectedServers.length > 0 && !connectedServers.includes('plex') && !plexReady;
  const showPaths = plexReady || (!!dockerInfo && !pluginOnly);
  const steps = useMemo(
    () => BASE_STEPS.filter((s) => !s.pathsStep || showPaths),
    [showPaths]
  );
  const step = steps[Math.min(stepIdx, steps.length - 1)];
  const goTo = (i) => {
    const target = Math.max(0, Math.min(i, steps.length - 1));
    setLeaveNote(null);
    setVisited((prev) => new Set(prev).add(steps[target].key));
    setStepIdx(target);
  };
  const next = () => goTo(stepIdx + 1);
  const back = () => goTo(stepIdx - 1);

  const safeJson = async (res) => { try { return await res.json(); } catch { return null; } };

  // With Plex just connected, find NeXroll's folders on it and save the
  // mappings needed, so the Paths step usually has nothing left to ask.
  const setUpPlexPaths = async () => {
    try {
      const res = await fetch(apiUrl('settings/path-mappings/auto-setup'), { method: 'POST', credentials: 'include' });
      const data = res.ok ? await safeJson(res) : null;
      if (!data) return;
      const saved = Array.isArray(data.saved) ? data.saved : [];
      if (saved.length) {
        const bare = (p) => (p || '').trim().replace(/[\\/]+$/, '').toLowerCase();
        const replaced = new Set(saved.map((m) => bare(m.local)));
        setPathRows((rows) => [
          ...rows.filter((r) => (r.local || '').trim() && (r.plex || '').trim() && !replaced.has(bare(r.local))),
          ...saved,
        ]);
        setPathDirty(false);
        setPathResult({ ok: true, msg: saved.length === 1
          ? `NeXroll found your preroll folder on the Plex server (${saved[0].plex}) and saved the mapping.`
          : `NeXroll found your folders on the Plex server and saved ${saved.length} mappings.` });
      } else if (data.working) {
        setPathResult({ ok: true, msg: 'Plex already reaches your preroll folder, so no mapping is needed.' });
      }
    } catch { /* the Paths step still offers Find it for me */ }
  };

  // Radarr and Sonarr report failures in their own words; say them plainly.
  const arrReason = (raw) => {
    const text = String(raw || '').trim();
    if (/api key/i.test(text)) return 'the API key was not accepted';
    if (!text || /connection attempts failed|connect|refused|timed? ?out|unreachable|name or service/i.test(text)) {
      return 'nothing answered at that address';
    }
    return text.replace(/[.\s]+$/, '');
  };
  // The same for a media server: never show a raw network error.
  const serverReason = (raw, label) => {
    const text = String(raw || '').trim();
    if (!text) return `Could not connect to ${label}. Check the address and the ${label === 'Plex' ? 'token' : 'API key'}.`;
    if (/HTTPConnectionPool|Max retries|NewConnectionError|WinError|Errno|timed out/i.test(text)) {
      return `Nothing answered at that address. Check the URL and that ${label} is running.`;
    }
    return text.replace(/^Connection error:\s*(\d{3}:\s*)?/i, '');
  };

  // ---- Actions (reuse existing endpoints) ----
  const connectServer = async () => {
    setServerBusy(true);
    setServerResult(null);
    try {
      let res;
      if (serverType === 'jellyfin') {
        res = await fetch(apiUrl('/jellyfin/connect'), {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: serverUrl.trim(), api_key: serverApiKey.trim() }),
        });
      } else if (serverType === 'emby') {
        res = await fetch(apiUrl('/emby/connect'), {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: serverUrl.trim(), api_key: serverApiKey.trim() }),
        });
      } else {
        // Plex token-based connect (OAuth is handled on the full Connect page)
        res = await fetch(apiUrl('/plex/connect'), {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: serverUrl.trim(), token: serverApiKey.trim() }),
        });
      }
      const data = await safeJson(res);
      const label = SERVER_LABELS[serverType];
      if (res.ok) {
        setConnectedServers((prev) => (prev.includes(serverType) ? prev : [...prev, serverType]));
        if (serverType === 'plex') { setPlexReady(true); setUpPlexPaths(); }
        setServerResult({ ok: true, msg: `${label} connected.` });
        setServerUrl('');
        setServerApiKey('');
      } else {
        const detail = data && (typeof data.detail === 'string' ? data.detail : data.message);
        setServerResult({ ok: false, msg: serverReason(detail, label) });
      }
    } catch {
      setServerResult({ ok: false, msg: 'NeXroll did not answer. Check that it is still running.' });
    } finally {
      setServerBusy(false);
    }
  };

  const stopOAuthPoll = () => {
    if (oauthPollRef.current) {
      clearInterval(oauthPollRef.current);
      oauthPollRef.current = null;
    }
  };
  useEffect(() => stopOAuthPoll, []);

  const startPlexSignIn = async () => {
    setServerResult(null);
    setPlexOAuth({ id: null, url: '', status: 'starting' });
    try {
      const res = await fetch(apiUrl('plex/tv/start'), { method: 'POST', credentials: 'include' });
      const data = await safeJson(res);
      if (!res.ok || !data || !data.id || !data.url) {
        throw new Error((data && data.detail) || 'Could not start Plex sign-in.');
      }
      setPlexOAuth({ id: data.id, url: data.url, status: 'pending' });
      // Popup blockers are common; the URL is also shown so it can be opened by hand.
      try { window.open(data.url, '_blank', 'noopener,noreferrer'); } catch { /* shown below instead */ }

      stopOAuthPoll();
      oauthPollRef.current = setInterval(async () => {
        try {
          const r = await fetch(apiUrl(`plex/tv/status/${data.id}`), { credentials: 'include' });
          const s = await safeJson(r);
          if (s && s.status === 'success') {
            stopOAuthPoll();
            setPlexOAuth((p) => ({ ...p, status: 'connecting' }));
            const c = await fetch(apiUrl('plex/tv/connect'), {
              method: 'POST', credentials: 'include',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: data.id, save_token: true }),
            });
            const cd = await safeJson(c);
            if (c.ok && cd && cd.connected) {
              setPlexOAuth((p) => ({ ...p, status: 'connected' }));
              setConnectedServers((prev) => (prev.includes('plex') ? prev : [...prev, 'plex']));
              setPlexReady(true);
              setUpPlexPaths();
              setServerResult({ ok: true, msg: cd.server_name ? `Connected to ${cd.server_name}.` : 'Connected to Plex.' });
            } else {
              setPlexOAuth((p) => ({ ...p, status: 'idle' }));
              setServerResult({ ok: false, msg: (cd && (cd.detail || cd.message)) || 'Signed in, but no reachable server was found.' });
            }
          } else if (s && (s.status === 'expired' || s.status === 'not_found')) {
            stopOAuthPoll();
            setPlexOAuth((p) => ({ ...p, status: 'expired' }));
          }
        } catch { /* transient poll errors are not worth surfacing */ }
      }, 2000);
    } catch (e) {
      setPlexOAuth({ id: null, url: '', status: 'idle' });
      setServerResult({ ok: false, msg: (e && e.message) || 'Could not start Plex sign-in.' });
    }
  };

  const saveNexupStorage = async () => {
    const folder = nexupStorage.trim();
    if (!folder) return;
    setNexupStorageBusy(true);
    setNexupStorageResult(null);
    setStorageCheck(null);
    try {
      const res = await fetch(apiUrl(`nexup/settings?storage_path=${encodeURIComponent(folder)}`), {
        method: 'PUT', credentials: 'include',
      });
      const data = await safeJson(res);
      if (!res.ok) {
        setNexupStorageResult({ ok: false, msg: (data && (data.detail || data.message)) || 'Could not save the trailer folder.' });
        return;
      }
      setNexupStorageResult({ ok: true, msg: 'Trailer folder saved.' });
      setTrailerFolderSaved(true);
      // Saving is only half of it: report whether the media server can actually
      // open files there, which is what decides if trailers ever play.
      try {
        const check = await fetch(apiUrl(`nexup/storage-check?path=${encodeURIComponent(folder)}`), { credentials: 'include' });
        if (check.ok) setStorageCheck(await check.json());
      } catch { /* the folder is saved either way */ }
    } catch {
      setNexupStorageResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setNexupStorageBusy(false);
    }
  };

  // Radarr and Sonarr answer 200 with {success: false, message} when the
  // address or key is wrong, so the status code alone says nothing.
  const connectArr = async (kind, url, key) => {
    const label = kind === 'radarr' ? 'Radarr' : 'Sonarr';
    try {
      const res = await fetch(
        apiUrl(`/nexup/${kind}/connect?url=${encodeURIComponent(url.trim())}&api_key=${encodeURIComponent(key.trim())}`),
        { method: 'POST', credentials: 'include' }
      );
      const data = await safeJson(res);
      if (res.ok && data && data.success !== false) return { kind, label, ok: true };
      const why = data && (data.message || (typeof data.detail === 'string' ? data.detail : ''));
      return { kind, label, ok: false, why: arrReason(why) };
    } catch {
      return { kind, label, ok: false, why: 'NeXroll did not answer' };
    }
  };

  const connectNexup = async () => {
    const jobs = [];
    const half = [];
    if (radarrUrl.trim() && radarrKey.trim()) jobs.push(['radarr', radarrUrl, radarrKey]);
    else if (radarrUrl.trim() || radarrKey.trim()) half.push('Radarr');
    if (sonarrUrl.trim() && sonarrKey.trim()) jobs.push(['sonarr', sonarrUrl, sonarrKey]);
    else if (sonarrUrl.trim() || sonarrKey.trim()) half.push('Sonarr');
    if (!jobs.length) {
      setNexupResult({ ok: false, msg: `${half.join(' and ') || 'Radarr or Sonarr'} needs both the URL and the API key.` });
      return;
    }
    setNexupBusy(true);
    setNexupResult(null);
    try {
      const results = [];
      for (const [kind, url, key] of jobs) results.push(await connectArr(kind, url, key));
      const good = results.filter((r) => r.ok);
      if (good.length) {
        setArrConnected((prev) => ({ ...prev, ...Object.fromEntries(good.map((r) => [r.kind, true])) }));
        if (good.some((r) => r.kind === 'radarr')) { setRadarrUrl(''); setRadarrKey(''); }
        if (good.some((r) => r.kind === 'sonarr')) { setSonarrUrl(''); setSonarrKey(''); }
      }
      const parts = results.map((r) => (r.ok ? `${r.label} connected.` : `${r.label} did not connect: ${r.why}.`));
      half.forEach((label) => parts.push(`${label} needs both the URL and the API key.`));
      setNexupResult({ ok: good.length === results.length && !half.length, msg: parts.join(' ') });
      // NeX-Up downloads nothing until it has a folder, and there is no
      // default: keep the one shown below unless another is already saved.
      if (good.length && !trailerFolderSaved && nexupStorage.trim()) await saveNexupStorage();
    } finally {
      setNexupBusy(false);
    }
  };

  const saveStorage = async () => {
    setStorageBusy(true);
    setStorageResult(null);
    try {
      const res = await fetch(apiUrl('settings/preroll-folder'), {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: storagePath.trim() }),
      });
      const data = await safeJson(res);
      // A folder NeXroll can't write to is answered 200 with {error}.
      if (res.ok && data && data.status === 'ok' && data.folder) {
        setStorageResult({ ok: true, msg: `Prerolls will be stored in ${data.folder}.` });
        setFolderInfo((prev) => ({ ...(prev || {}), current_folder: data.folder, is_custom: true }));
        setStoragePath('');
      } else {
        setStorageResult({ ok: false, msg: "NeXroll can't create or write to that folder. Check the path, and that the drive or share exists." });
      }
    } catch {
      setStorageResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setStorageBusy(false);
    }
  };

  const validatePassword = (pw) => {
    if (pw.length < 8) return 'Password must be at least 8 characters';
    if (pw === pw.toLowerCase() || pw === pw.toUpperCase()) return 'Password needs both uppercase and lowercase letters';
    if (!/\d/.test(pw)) return 'Password must contain at least one number';
    return null;
  };

  // Mirrors the server's rules, so the user is corrected as they type instead of
  // by a 422 after pressing the button.
  const validateUsername = (name) => {
    const value = (name || '').trim();
    if (value.length < 3) return 'Username must be at least 3 characters';
    if (!/^[a-z0-9]+$/i.test(value)) return 'Username can only contain letters and numbers';
    return null;
  };

  const createAccount = async () => {
    const userErr = validateUsername(acctUser);
    if (userErr) { setAcctResult({ ok: false, msg: userErr }); return; }
    if (acctPass !== acctConfirm) { setAcctResult({ ok: false, msg: 'Passwords do not match.' }); return; }
    const pwErr = validatePassword(acctPass);
    if (pwErr) { setAcctResult({ ok: false, msg: pwErr }); return; }
    setAcctBusy(true);
    setAcctResult(null);
    try {
      const username = acctUser.trim().toLowerCase();
      const res = await fetch(apiUrl('/auth/register'), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password: acctPass, display_name: acctUser.trim() }),
      });
      const data = await safeJson(res);
      if (!res.ok) { setAcctResult({ ok: false, msg: (data && data.detail) || 'Could not create account.' }); setAcctBusy(false); return; }

      // Registering the first user turns "require login" on server-side, so the
      // choice has to be sent either way -- only sending it when checked left
      // the box unable to turn login back off.
      try {
        await fetch(apiUrl('/auth/settings'), {
          method: 'PUT', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ auth_enabled: !!acctEnableAuth }),
        });
      } catch { /* non-fatal: the server default already matches the recommended choice */ }

      // Sign the new admin in now. Without this, finishing the wizard drops
      // straight onto a login screen for the password just typed.
      let signedIn = false;
      if (acctEnableAuth) {
        try {
          const login = await fetch(apiUrl('/auth/login'), {
            method: 'POST', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password: acctPass, remember_me: true }),
          });
          signedIn = login.ok;
        } catch { /* the user can still log in by hand */ }
      }
      setAcctResult({
        ok: true,
        msg: acctEnableAuth
          ? (signedIn ? 'Admin account created and you are signed in. Login will be required from now on.'
                      : 'Admin account created. Login is now required.')
          : 'Admin account created. Login is not required.',
      });
    } catch {
      setAcctResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setAcctBusy(false);
    }
  };

  const isRerun = !!(install && install.is_rerun);
  const accountExists = !!(install && install.users_exist);
  const tzSuggested = suggestedTimeZone(tzList);
  const tzChoice = tzPicked
    || (!isRerun && tzServer === 'UTC' && tzSuggested ? tzSuggested : tzServer);

  // Saved on the way out of Welcome and when the wizard closes, so skipping
  // setup still keeps the zone shown on the first screen.
  const saveTimezoneChoice = async () => {
    if (!tzChoice || tzChoice === tzServer) return;
    try {
      const res = await fetch(apiUrl('/settings/timezone'), {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timezone: tzChoice }),
      });
      if (res.ok) setTzServer(tzChoice);
    } catch { /* Settings, General has the same choice */ }
  };
  const startSetup = () => { saveTimezoneChoice(); next(); };
  const jumpTo = (i) => { if (stepIdx === 0 && i !== 0) saveTimezoneChoice(); goTo(i); };

  const naming = (ids) => ids.map((id) => SERVER_LABELS[id] || id).join(' and ');
  const serverDone = connectedServers.length > 0 || !!(install && install.has_server);
  const pluginServers = connectedServers.filter((id) => id !== 'plex');
  const arrNames = [arrConnected.radarr && 'Radarr', arrConnected.sonarr && 'Sonarr'].filter(Boolean);
  const mappingsSaved = !!(pathResult && pathResult.ok) || !!(installInfo && installInfo.mappings && installInfo.mappings.length);
  const accountDone = accountExists || !!(acctResult && acctResult.ok);
  const currentFolder = (folderInfo && folderInfo.current_folder) || (installInfo && installInfo.prerolls_dir) || '';

  // Which steps are really done, as opposed to walked past.
  const stepDone = {
    welcome: stepIdx > 0,
    server: serverDone,
    paths: mappingsSaved,
    nexup: arrNames.length > 0,
    storage: visited.has('storage') && step.key !== 'storage',
    account: accountDone,
    done: false,
  };

  // Something typed on this step that no button has saved yet.
  const unsaved = {
    server: (serverUrl.trim() || serverApiKey.trim()) ? 'You entered server details but have not connected. Press Test & Connect to use them.' : null,
    paths: pathDirty ? 'You changed the path mappings but have not saved them. Press Save mappings to keep them.' : null,
    nexup: (radarrUrl.trim() || radarrKey.trim() || sonarrUrl.trim() || sonarrKey.trim())
      ? 'You entered Radarr or Sonarr details but have not connected. Press Connect to use them.' : null,
    storage: storagePath.trim() ? 'You entered a folder but have not saved it. Press Save folder to use it.' : null,
    account: (!accountDone && (acctUser.trim() || acctPass)) ? 'You filled in an account but have not created it. Press Create account to make it.' : null,
  }[step.key] || null;
  const advance = () => {
    if (unsaved && leaveNote !== step.key) { setLeaveNote(step.key); return; }
    next();
  };
  const onEnter = (action) => (e) => { if (e.key === 'Enter') { e.preventDefault(); action(); } };

  const summaryItems = [
    { label: 'Media server', done: serverDone,
      detail: connectedServers.length ? `${naming(connectedServers)} connected` : (serverDone ? 'Connected' : 'Not connected yet') },
    ...(showPaths ? [{ label: 'Path mappings', done: mappingsSaved,
      detail: mappingsSaved ? 'Saved' : 'Not set, so Plex may not find your prerolls' }] : []),
    { label: 'NeX-Up', done: arrNames.length > 0 && trailerFolderSaved,
      detail: arrNames.length
        ? (trailerFolderSaved ? `${arrNames.join(' and ')} connected` : `${arrNames.join(' and ')} connected, but no trailer folder is saved`)
        : 'Optional, skipped' },
    { label: 'Storage', done: true,
      detail: currentFolder
        ? ((folderInfo && folderInfo.is_custom) ? currentFolder : `Default folder: ${currentFolder}`)
        : 'Using the default folder' },
    { label: 'Account', done: accountDone, detail: accountDone ? 'Ready' : 'No login required' },
    ...(tzChoice ? [{ label: 'Timezone', done: true, detail: `Schedules run on ${tzChoice} time` }] : []),
  ];

  const isDockerInstall = !!(installInfo && installInfo.is_docker);
  const suggestedNexupPath = (installInfo && installInfo.nexup_suggested_path) || '';
  const exampleLocal = (installInfo && installInfo.prerolls_dir) || '/data/prerolls';
  // A sample file under that folder, in the folder's own separator style.
  const exampleFile = exampleLocal.includes('\\') && !exampleLocal.includes('/')
    ? `${exampleLocal}\\holiday\\xmas.mp4` : `${exampleLocal}/holiday/xmas.mp4`;
  const mountList = (dockerInfo && Array.isArray(dockerInfo.mounts)) ? dockerInfo.mounts : [];
  // Fill the first empty NeXroll-side field, or append a row if all are taken.
  const applyMountToRow = (mount) => setPathRows((rows) => {
    const i = rows.findIndex((r) => !r.local);
    if (i === -1) return [...rows, { local: mount, plex: '' }];
    return rows.map((r, ri) => (ri === i ? { ...r, local: mount } : r));
  });

  const updatePathRow = (idx, key, value) => {
    setPathDirty(true);
    setPathRows((rows) => rows.map((r, i) => (i === idx ? { ...r, [key]: value } : r)));
  };
  const addPathRow = () => setPathRows((rows) => [...rows, { local: '', plex: '' }]);
  const removePathRow = (idx) =>
    setPathRows((rows) => (rows.length > 1 ? rows.filter((_, i) => i !== idx) : [{ local: '', plex: '' }]));

  const savePathMappings = async () => {
    const mappings = pathRows
      .map((r) => ({ local: (r.local || '').trim(), plex: (r.plex || '').trim() }))
      .filter((r) => r.local && r.plex);
    if (!mappings.length) {
      setPathResult({ ok: false, msg: 'Fill in both sides of at least one row first.' });
      return;
    }
    setPathBusy(true);
    setPathResult(null);
    try {
      const res = await fetch(apiUrl('settings/path-mappings'), {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mappings }),
      });
      const data = await safeJson(res);
      if (res.ok) { setPathDirty(false); setPathResult({ ok: true, msg: `Saved ${mappings.length} mapping${mappings.length === 1 ? '' : 's'}.` }); }
      else setPathResult({ ok: false, msg: (data && (data.detail || data.message)) || 'Could not save mappings.' });
    } catch {
      setPathResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setPathBusy(false);
    }
  };

  // Save the mappings "Find it for me" proposed (one per folder NeXroll sends
  // Plex files from), replacing any row for the same NeXroll folder. Returns
  // whether it saved, for the panel's confirmation.
  const saveFoundMappings = async (suggestions) => {
    const bare = (p) => (p || '').trim().replace(/[\\/]+$/, '').toLowerCase();
    const incoming = (suggestions || []).map((s) => ({ local: s.local, plex: s.plex }));
    const replaced = new Set(incoming.map((s) => bare(s.local)));
    const mappings = [
      ...pathRows
        .map((r) => ({ local: (r.local || '').trim(), plex: (r.plex || '').trim() }))
        .filter((r) => r.local && r.plex && !replaced.has(bare(r.local))),
      ...incoming,
    ];
    try {
      const res = await fetch(apiUrl('settings/path-mappings'), {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mappings }),
      });
      if (!res.ok) return false;
      setPathRows(mappings);
      setPathDirty(false);
      setPathResult({ ok: true, msg: incoming.length === 1 ? 'Mapping saved.' : `${incoming.length} mappings saved.` });
      return true;
    } catch {
      return false;
    }
  };

  // Translate a real path through the saved rules, so the user can see the
  // answer Plex will be given, and ask Plex whether it can open it.
  const runPathTest = async () => {
    const target = (testPath || '').trim();
    if (!target) return;
    setTestOut({ pending: true });
    try {
      const res = await fetch(apiUrl('settings/path-mappings/test'), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: [target], check_plex: plexReady }),
      });
      const data = await safeJson(res);
      const first = data && Array.isArray(data.results) ? data.results[0] : null;
      setTestOut(first ? { ...first, pending: false } : { pending: false, error: true });
    } catch {
      setTestOut({ pending: false, error: true });
    }
  };

  const completeOnboarding = async () => {
    setFinishing(true);
    await saveTimezoneChoice();
    try {
      await fetch(apiUrl('/onboarding/complete'), { method: 'POST', credentials: 'include' });
    } catch { /* best effort */ }
    setFinishing(false);
    if (onFinish) onFinish();
  };

  // ---- UI helpers ----
  // Colors come from the theme, so a wizard reopened under any theme matches it.
  const ACCENT = 'var(--button-bg)';
  const GOOD = 'var(--success-color)';
  const BAD = 'var(--error-color)';
  const WARN = 'var(--warning-color)';
  const LINE = 'var(--border-color)';
  const TINT = (color, pct) => `color-mix(in srgb, ${color} ${pct}%, transparent)`;
  const card = {
    width: '100%', maxWidth: '640px',
    backgroundColor: 'var(--card-bg)',
    borderRadius: '16px', padding: '2rem',
    boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
    border: `1px solid ${LINE}`,
  };
  const txt = 'var(--text-color)';
  const sub = 'var(--text-secondary)';
  const inputStyle = {
    width: '100%', padding: '0.6rem 0.75rem', borderRadius: '8px',
    border: `1px solid ${LINE}`,
    background: 'var(--input-bg)', color: txt, fontSize: '0.95rem',
  };
  const labelStyle = { display: 'block', marginBottom: '0.35rem', fontWeight: 600, color: txt, fontSize: '0.85rem' };
  const primaryBtn = {
    padding: '0.6rem 1.25rem', border: 'none', borderRadius: '8px',
    background: ACCENT,
    color: 'var(--button-text)', fontWeight: 600, cursor: 'pointer', fontSize: '0.95rem',
    display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
  };
  const ghostBtn = {
    padding: '0.6rem 1.1rem', border: `1px solid ${LINE}`,
    borderRadius: '8px', background: 'transparent', color: txt, cursor: 'pointer', fontSize: '0.9rem',
    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
  };

  const ResultBadge = ({ result }) => {
    if (!result) return null;
    return (
      <div style={{
        marginTop: '0.75rem', padding: '0.6rem 0.8rem', borderRadius: '8px', fontSize: '0.85rem',
        display: 'flex', flexWrap: 'nowrap', alignItems: 'flex-start', gap: '0.5rem', lineHeight: 1.45,
        background: result.ok ? 'var(--success-soft)' : 'var(--error-soft)',
        color: result.ok ? GOOD : BAD,
        border: `1px solid ${TINT(result.ok ? GOOD : BAD, 35)}`,
      }}>
        {result.ok ? <Check size={16} style={{ flexShrink: 0 }} /> : <AlertCircle size={16} style={{ flexShrink: 0 }} />}
        <span role={result.ok ? 'status' : 'alert'} style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>{result.msg}</span>
      </div>
    );
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '1.5rem',
      backgroundColor: 'var(--bg-color)',
    }}>
      {/* Step indicator: a tick means the step is set up, not just passed. */}
      <nav aria-label="Setup steps" style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        {steps.map((s, i) => {
          const Icon = s.icon;
          const active = i === stepIdx;
          const done = !active && !!stepDone[s.key];
          const skipped = !active && !done && visited.has(s.key);
          return (
            <button key={s.key} type="button" onClick={() => jumpTo(i)}
              aria-current={active ? 'step' : undefined}
              title={done ? `${s.label}: done` : (skipped ? `${s.label}: skipped for now` : s.label)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.35rem 0.7rem',
                borderRadius: '20px', fontSize: '0.78rem', fontWeight: active ? 700 : 500, cursor: 'pointer',
                background: active ? TINT(ACCENT, 18) : (done ? 'var(--success-soft)' : 'transparent'),
                color: active ? ACCENT : (done ? GOOD : sub),
                border: `1px solid ${active ? TINT(ACCENT, 40) : 'transparent'}`,
                opacity: skipped ? 0.75 : 1,
              }}>
              {done ? <Check size={14} /> : <Icon size={14} />}
              <span>{s.label}</span>
            </button>
          );
        })}
      </nav>

      <div style={card}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '1.25rem' }}>
          <img src={darkMode ? '/icons/nexroll-logo-white.png' : '/icons/nexroll-logo-black.png'} alt="NeXroll" style={{ height: '46px' }} />
        </div>

        {/* ---- Welcome ---- */}
        {step.key === 'welcome' && (
          <div style={{ textAlign: 'center' }}>
            <Rocket size={40} style={{ color: ACCENT, marginBottom: '0.75rem' }} />
            <h2 style={{ color: txt, margin: '0 0 0.5rem' }}>
              {isRerun ? 'Setup wizard' : 'Welcome to NeXroll'}
            </h2>
            <p style={{ color: sub, lineHeight: 1.6, margin: '0 auto 0.5rem', maxWidth: '460px' }}>
              {isRerun
                ? 'Your existing settings are untouched. Walk through the steps and change anything you want; skip whatever is already right.'
                : "Let's get you set up. This quick wizard connects your media server, optionally configures NeX-Up trailer automation, chooses where prerolls are stored, and creates your account."}
            </p>
            <p style={{ color: sub, lineHeight: 1.6, margin: '0 auto', maxWidth: '460px', fontSize: '0.85rem' }}>
              Every step is optional, and you can reopen this wizard later from Settings, System.
            </p>
            {tzList.length > 0 && tzChoice && (
              <div style={{ textAlign: 'left', maxWidth: '360px', margin: '1.25rem auto 0' }}>
                <label htmlFor="nx-wizard-timezone" style={labelStyle}>Your timezone</label>
                <select
                  id="nx-wizard-timezone"
                  value={tzChoice}
                  onChange={(e) => setTzPicked(e.target.value)}
                  style={inputStyle}
                >
                  {tzList.map((tz) => (
                    <option key={tz.value} value={tz.value}>{tz.label}</option>
                  ))}
                </select>
                <p style={{ color: sub, fontSize: '0.78rem', margin: '0.35rem 0 0', lineHeight: 1.5 }}>
                  Schedules start and stop on this clock.
                  {tzSuggested && tzChoice === tzSuggested && !isRerun ? ' Taken from this browser.' : ''}
                </p>
              </div>
            )}
          </div>
        )}

        {/* ---- Media Server ---- */}
        {step.key === 'server' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0 }}>Connect your media server</h2>
            <p style={{ color: sub, marginTop: 0 }}>Choose your server, then connect.</p>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              {['plex', 'jellyfin', 'emby'].map((t) => (
                <button key={t} type="button" onClick={() => { setServerType(t); setServerResult(null); }}
                  aria-pressed={serverType === t}
                  style={{ ...ghostBtn, flex: 1, justifyContent: 'center',
                    borderColor: serverType === t ? ACCENT : LINE,
                    background: serverType === t ? TINT(ACCENT, 12) : 'transparent',
                    color: serverType === t ? ACCENT : txt, fontWeight: serverType === t ? 700 : 500 }}>
                  {SERVER_LABELS[t]}
                </button>
              ))}
            </div>

            {/* Jellyfin and Emby play prerolls only through the NeXroll Intros
                plugin, and the wizard never said so - you could finish setup
                with a healthy connection and still have nothing ever play.
                Reported four times against the Emby step. */}
            {(serverType === 'jellyfin' || serverType === 'emby') && (
              <div style={{
                marginBottom: '1rem', padding: '0.85rem 1rem', borderRadius: '10px',
                background: 'var(--warning-soft)',
                border: `1px solid ${TINT(WARN, 30)}`,
              }}>
                <div style={{ fontWeight: 700, color: txt, fontSize: '0.88rem', marginBottom: '0.3rem' }}>
                  {serverType === 'emby' ? 'Emby' : 'Jellyfin'} also needs the NeXroll Intros plugin
                </div>
                <p style={{ color: sub, fontSize: '0.82rem', margin: 0, lineHeight: 1.55 }}>
                  Connecting here lets NeXroll manage your prerolls, but{' '}
                  {serverType === 'emby' ? 'Emby' : 'Jellyfin'} plays them through the plugin - without
                  it nothing appears before your films. Finish this wizard, then open{' '}
                  <strong>Connect</strong>, where NeXroll offers the plugin for download along with
                  the install steps for your server.
                </p>
              </div>
            )}

            {serverType === 'plex' ? (
              <div style={{
                marginBottom: '1rem', padding: '0.9rem 1rem', borderRadius: '10px',
                background: TINT(ACCENT, 10),
                border: `1px solid ${TINT(ACCENT, 30)}`,
              }}>
                <div style={{ fontWeight: 700, color: txt, fontSize: '0.88rem', marginBottom: '0.3rem' }}>
                  Sign in with Plex (recommended)
                </div>
                <p style={{ color: sub, fontSize: '0.82rem', margin: '0 0 0.75rem', lineHeight: 1.55 }}>
                  Opens Plex in a new tab. Approve NeXroll there and we will find your
                  server and its token automatically, so there is nothing to copy by hand.
                </p>

                {plexOAuth.status === 'connected' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: GOOD, fontSize: '0.86rem', fontWeight: 600 }}>
                    <Check size={16} /> Signed in with Plex
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      style={primaryBtn}
                      disabled={plexOAuth.status === 'starting' || plexOAuth.status === 'pending' || plexOAuth.status === 'connecting'}
                      onClick={startPlexSignIn}
                    >
                      {plexOAuth.status === 'starting' || plexOAuth.status === 'connecting'
                        ? <Loader2 size={16} className="spin" />
                        : <ExternalLink size={16} />}
                      {plexOAuth.status === 'pending'
                        ? 'Waiting for Plex...'
                        : plexOAuth.status === 'connecting'
                          ? 'Finding your server...'
                          : plexOAuth.status === 'expired'
                            ? 'Try signing in again'
                            : 'Sign in with Plex'}
                    </button>

                    {plexOAuth.status === 'pending' && (
                      <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: sub, lineHeight: 1.55 }}>
                        Waiting for you to approve NeXroll in the Plex tab. If no tab opened,
                        your browser blocked the popup:{' '}
                        <a href={plexOAuth.url} target="_blank" rel="noopener noreferrer" style={{ color: ACCENT }}>
                          open the Plex sign-in page
                        </a>.
                      </div>
                    )}
                    {plexOAuth.status === 'expired' && (
                      <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: WARN }}>
                        That sign-in request timed out. Start it again when you are ready.
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : null}

            <details style={{ marginBottom: '0.5rem' }} open={serverType !== 'plex'}>
              <summary style={{ cursor: 'pointer', color: sub, fontSize: '0.84rem', marginBottom: '0.6rem' }}>
                {serverType === 'plex' ? 'Or enter a server URL and token manually' : 'Server details'}
              </summary>
              <label htmlFor="nx-wiz-server-url" style={labelStyle}>Server URL</label>
              <input
                id="nx-wiz-server-url"
                onKeyDown={onEnter(() => { if (!serverBusy && serverUrl.trim() && serverApiKey.trim()) connectServer(); })}
                style={inputStyle}
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder={serverType === 'plex' ? 'http://192.168.1.10:32400' : 'http://192.168.1.10:8096'}
              />
              <div style={{ height: '0.75rem' }} />
              <label htmlFor="nx-wiz-server-key" style={labelStyle}>{serverType === 'plex' ? 'Plex Token' : 'API Key'}</label>
              <input
                id="nx-wiz-server-key"
                onKeyDown={onEnter(() => { if (!serverBusy && serverUrl.trim() && serverApiKey.trim()) connectServer(); })}
                type="password"
                autoComplete="off"
                style={inputStyle}
                value={serverApiKey}
                onChange={(e) => setServerApiKey(e.target.value)}
                placeholder={serverType === 'plex' ? 'X-Plex-Token' : 'API key'}
              />
              <div style={{ marginTop: '1rem' }}>
                <button type="button" style={primaryBtn} disabled={serverBusy || !serverUrl.trim() || !serverApiKey.trim()} onClick={connectServer}>
                  {serverBusy ? <Loader2 size={16} className="spin" /> : <Server size={16} />} {serverBusy ? 'Connecting...' : 'Test & Connect'}
                </button>
              </div>
            </details>
            <ResultBadge result={serverResult} />

            {/* Prerolls apply to every connected server, so having connected one
                is the moment to say a second is possible - not the Connect page
                the user may not visit for weeks. */}
            {connectedServers.length > 0 && (() => {
              const LABELS = SERVER_LABELS;
              const remaining = ['plex', 'jellyfin', 'emby'].filter((t) => !connectedServers.includes(t));
              return (
                <div style={{
                  marginTop: '1rem', padding: '0.85rem 1rem', borderRadius: '10px',
                  background: TINT(ACCENT, 10),
                  border: `1px solid ${TINT(ACCENT, 30)}`,
                }}>
                  <div style={{ fontWeight: 700, color: txt, fontSize: '0.88rem', marginBottom: '0.3rem' }}>
                    {naming(connectedServers)} connected
                  </div>
                  {remaining.length > 0 ? (
                    <>
                      <p style={{ color: sub, fontSize: '0.82rem', margin: '0 0 0.75rem', lineHeight: 1.55 }}>
                        You can run more than one. Add {naming(remaining)} too and everything you
                        schedule will play on all of them. Or continue — you can add more later
                        from the Connect page.
                      </p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {remaining.map((t) => (
                          <button key={t} type="button" style={ghostBtn}
                            onClick={() => { setServerType(t); setServerResult(null); setServerUrl(''); setServerApiKey(''); }}>
                            <Server size={15} /> Add {LABELS[t]}
                          </button>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p style={{ color: sub, fontSize: '0.82rem', margin: 0, lineHeight: 1.55 }}>
                      All three are connected. Everything you schedule plays on each of them.
                    </p>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* ---- Path Mappings (Docker only) ---- */}
        {step.key === 'paths' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Box size={20} style={{ color: ACCENT }} /> {dockerInfo ? 'One thing Docker needs' : 'Make sure Plex can find your prerolls'}
            </h2>
            <p style={{ color: sub, marginTop: 0, lineHeight: 1.6 }}>
              {dockerInfo
                ? 'NeXroll is running in a container. Inside it, your files live at one path. Plex sees those same files at a different path. '
                : 'Plex plays prerolls straight from its own disk. If Plex runs on another computer, or reaches the folder through a network share, it sees your prerolls under a different path from NeXroll. '}
              When NeXroll tells Plex which preroll to play, it has to send the path Plex understands.
            </p>
            <p style={{ color: sub, marginTop: '0.6rem', lineHeight: 1.6 }}>
              Get this wrong and nothing looks broken: Plex accepts the setting and
              then quietly plays no preroll. Only Plex needs this; Jellyfin and Emby get prerolls from NeXroll directly.
            </p>

            {/* With Plex connected, NeXroll can ask Plex instead of the user working it out. */}
            {plexReady && (
              <div style={{ marginTop: '1rem' }}>
                <FindPlexFolder apiUrl={apiUrl} onUseMappings={saveFoundMappings} />
                <p style={{ color: sub, fontSize: '0.8rem', margin: '0.6rem 0 0' }}>
                  If NeXroll and Plex share the same path there is nothing to add, and Find it for me says so.
                  Otherwise you can fill in the mapping yourself below.
                </p>
              </div>
            )}

            {/* Worked example, using this install's real preroll folder. */}
            <div style={{
              marginTop: '1rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: TINT(ACCENT, 10),
              border: `1px solid ${TINT(ACCENT, 30)}`,
            }}>
              <div style={{ fontWeight: 700, color: txt, fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                The same file, two names
              </div>
              <div style={{ display: 'grid', gap: '0.35rem', fontSize: '0.78rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflowWrap: 'anywhere', minWidth: 0 }}>
                <div style={{ color: sub }}>
                  NeXroll sees{'\u00a0\u00a0'}
                  <span style={{ color: txt }}>{exampleFile}</span>
                </div>
                <div style={{ color: sub }}>
                  Plex sees{'\u00a0\u00a0\u00a0\u00a0\u00a0'}
                  <span style={{ color: txt }}>/mnt/media/prerolls/holiday/xmas.mp4</span>
                </div>
              </div>
              <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: sub }}>
                So the mapping is <code style={{ color: ACCENT, overflowWrap: 'anywhere' }}>{exampleLocal}</code>
                {' '}<ArrowRight size={11} style={{ verticalAlign: 'middle' }} />{' '}
                <code style={{ color: ACCENT }}>/mnt/media/prerolls</code>. Only the start of
                the path changes; NeXroll keeps the rest.
              </div>
            </div>

            {/* Real mount points, so nobody has to remember their compose file. */}
            {mountList.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <div style={{ ...labelStyle, marginBottom: '0.45rem' }}>
                  Folders mounted into this container
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                  {mountList.map((m) => (
                    <button
                      key={m}
                      type="button"
                      title={`Use ${m} as the NeXroll side`}
                      onClick={() => applyMountToRow(m)}
                      style={{
                        padding: '0.25rem 0.55rem', borderRadius: '999px', cursor: 'pointer',
                        border: `1px solid ${LINE}`,
                        background: 'transparent', color: txt, fontSize: '0.74rem',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                      }}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                <div style={{ fontSize: '0.74rem', color: sub, marginTop: '0.4rem' }}>
                  Click one to drop it into the NeXroll column below.
                </div>
              </div>
            )}

            {/* The mapping rows. */}
            <div style={{ marginTop: '1.1rem', display: 'grid', gap: '0.6rem' }}>
              {pathRows.map((row, idx) => (
                <div key={idx} className="nx-wiz-path-row" style={{ display: 'flex', gap: '0.45rem', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {idx === 0 && <label style={labelStyle}>Path inside NeXroll</label>}
                    <input
                      style={inputStyle}
                      value={row.local}
                      placeholder={exampleLocal}
                      onChange={(e) => updatePathRow(idx, 'local', e.target.value)}
                    />
                  </div>
                  <ArrowRight size={16} style={{ color: ACCENT, flexShrink: 0, marginBottom: '0.65rem' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {idx === 0 && <label style={labelStyle}>Path Plex uses</label>}
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <input
                        style={inputStyle}
                        value={row.plex}
                        placeholder="/mnt/media/prerolls"
                        onChange={(e) => updatePathRow(idx, 'plex', e.target.value)}
                      />
                      {plexReady && (
                        <button type="button" onClick={() => setPickerRow(idx)}
                          title="Pick this folder from the Plex server's own view"
                          style={{ ...ghostBtn, padding: '0.55rem 0.6rem', flexShrink: 0 }}>
                          <FolderOpen size={14} /> Browse Plex
                        </button>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removePathRow(idx)}
                    title="Remove this row"
                    style={{ ...ghostBtn, padding: '0.55rem 0.6rem', flexShrink: 0 }}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
              <button type="button" style={{ ...ghostBtn, alignSelf: 'flex-start' }} onClick={addPathRow}>
                <Plus size={14} /> Add another mapping
              </button>
            </div>

            {/* "Where do I find that?" is the question this step always raises. */}
            <button
              type="button"
              onClick={() => setPathHelpOpen((o) => !o)}
              style={{ ...ghostBtn, marginTop: '0.9rem', border: 'none', padding: '0.3rem 0', color: ACCENT }}
            >
              <HelpCircle size={15} /> Where do I find the path Plex uses?
            </button>
            {pathHelpOpen && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.82rem', color: sub, lineHeight: 1.65 }}>
                <p style={{ margin: '0 0 0.5rem' }}>
                  <strong style={{ color: txt }}>If Plex also runs in Docker:</strong> open
                  its compose file or container settings and look at its volumes. Each one reads{' '}
                  <code>host path : container path</code>. The <em>right</em> side is what that server
                  sees, and that is what belongs in the right-hand column above.
                </p>
                <p style={{ margin: '0 0 0.5rem' }}>
                  <strong style={{ color: txt }}>If Plex runs directly on the host</strong>{' '}
                  (or another machine): use the folder as that machine sees it, for example{' '}
                  <code>/mnt/media/prerolls</code>, <code>D:\Media\Prerolls</code>, or{' '}
                  <code>\\NAS\media\prerolls</code>.
                </p>
                <p style={{ margin: 0 }}>
                  <strong style={{ color: txt }}>Still unsure?</strong>{' '}
                  {plexReady ? 'Use Browse Plex beside the right-hand column to pick the folder from Plex\'s own view. Or, ' : ''}
                  in Plex, open Settings, Manage, Libraries, then Edit a library: the folders listed there
                  are exactly the paths Plex uses.
                </p>
              </div>
            )}

            <div style={{ marginTop: '1.1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" style={primaryBtn} disabled={pathBusy} onClick={savePathMappings}>
                {pathBusy ? <Loader2 size={16} className="spin" /> : <FolderSync size={16} />} Save mappings
              </button>
            </div>
            <ResultBadge result={pathResult} />

            {/* Prove it: translate a real path with the rules just saved. */}
            {pathResult && pathResult.ok && (
              <div style={{ marginTop: '1rem', paddingTop: '0.9rem', borderTop: `1px solid ${LINE}` }}>
                <label style={labelStyle}>Check it (optional)</label>
                <div style={{ display: 'flex', gap: '0.45rem' }}>
                  <input
                    style={{ ...inputStyle, flex: 1 }}
                    value={testPath}
                    placeholder={exampleFile}
                    onChange={(e) => setTestPath(e.target.value)}
                  />
                  <button type="button" style={ghostBtn} onClick={runPathTest} disabled={!testPath.trim()}>
                    {testOut && testOut.pending ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Translate
                  </button>
                </div>
                {testOut && !testOut.pending && (
                  <div style={{ marginTop: '0.55rem', fontSize: '0.8rem', color: sub }}>
                    {testOut.error || !testOut.output ? (
                      <span style={{ color: BAD }}>Could not translate that path. Try again.</span>
                    ) : (
                      <>
                        {testOut.matched === false && (
                          <div style={{ color: WARN, marginBottom: '0.3rem' }}>
                            No mapping matched that path, so Plex would get it unchanged. Check that the left-hand column above starts the same way.
                          </div>
                        )}
                        Plex will be told:{' '}
                        <code style={{ color: testOut.matched === false ? txt : GOOD, overflowWrap: 'anywhere' }}>{testOut.output}</code>
                        {testOut.plex && (
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.35rem', marginTop: '0.35rem' }}>
                            <StatusIcon status={testOut.plex.status} size={14} />
                            <span>
                              <strong style={{ color: txt }}>{statusText(testOut.plex.status)}.</strong>
                              {testOut.plex.reason ? ` ${testOut.plex.reason}` : ''}
                            </span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            <PlexFolderPicker
              apiUrl={apiUrl}
              open={pickerRow !== null}
              initialPath={pickerRow !== null ? ((pathRows[pickerRow] || {}).plex || '') : ''}
              onPick={(p) => { updatePathRow(pickerRow, 'plex', p); setPickerRow(null); }}
              onClose={() => setPickerRow(null)}
            />

            <p style={{ color: sub, fontSize: '0.78rem', marginTop: '1rem', marginBottom: 0 }}>
              You can skip this and set it up later under Settings, Path Mappings.
            </p>
          </div>
        )}

        {/* ---- NeX-Up ---- */}
        {step.key === 'nexup' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0 }}>NeX-Up (optional)</h2>
            <p style={{ color: sub, marginTop: 0 }}>
              Connect Radarr and/or Sonarr to auto-download trailers for upcoming content.
              Skip if you don't use them.
            </p>
            {arrNames.length > 0 && (
              <div style={{
                marginBottom: '0.9rem', padding: '0.6rem 0.8rem', borderRadius: '9px', fontSize: '0.84rem',
                display: 'flex', flexWrap: 'nowrap', alignItems: 'flex-start', gap: '0.5rem', lineHeight: 1.45,
                background: 'var(--success-soft)', color: GOOD, border: `1px solid ${TINT(GOOD, 35)}`,
              }}>
                <Check size={16} style={{ flexShrink: 0 }} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  {arrNames.join(' and ')} {arrNames.length > 1 ? 'are' : 'is'} connected. Fill in a field below only to add the other one or to replace a connection.
                </span>
              </div>
            )}
            <label htmlFor="nx-wiz-radarr-url" style={labelStyle}>Radarr URL{arrConnected.radarr ? ' (connected)' : ''}</label>
            <input id="nx-wiz-radarr-url" onKeyDown={onEnter(connectNexup)} style={inputStyle} value={radarrUrl} onChange={(e) => setRadarrUrl(e.target.value)} placeholder="http://192.168.1.10:7878" />
            <div style={{ height: '0.5rem' }} />
            <label htmlFor="nx-wiz-radarr-key" style={labelStyle}>Radarr API Key</label>
            <input id="nx-wiz-radarr-key" onKeyDown={onEnter(connectNexup)} type="password" autoComplete="off" style={inputStyle} value={radarrKey} onChange={(e) => setRadarrKey(e.target.value)} />
            <div style={{ height: '1rem' }} />
            <label htmlFor="nx-wiz-sonarr-url" style={labelStyle}>Sonarr URL{arrConnected.sonarr ? ' (connected)' : ''}</label>
            <input id="nx-wiz-sonarr-url" onKeyDown={onEnter(connectNexup)} style={inputStyle} value={sonarrUrl} onChange={(e) => setSonarrUrl(e.target.value)} placeholder="http://192.168.1.10:8989" />
            <div style={{ height: '0.5rem' }} />
            <label htmlFor="nx-wiz-sonarr-key" style={labelStyle}>Sonarr API Key</label>
            <input id="nx-wiz-sonarr-key" onKeyDown={onEnter(connectNexup)} type="password" autoComplete="off" style={inputStyle} value={sonarrKey} onChange={(e) => setSonarrKey(e.target.value)} />
            <p style={{ color: sub, fontSize: '0.78rem', margin: '0.4rem 0 0', lineHeight: 1.5 }}>
              The API key is in Radarr and Sonarr under Settings, General.
            </p>
            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn}
                disabled={nexupBusy || !(radarrUrl.trim() || radarrKey.trim() || sonarrUrl.trim() || sonarrKey.trim())}
                onClick={connectNexup}>
                {nexupBusy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />} {nexupBusy ? 'Connecting...' : 'Connect'}
              </button>
            </div>
            <ResultBadge result={nexupResult} />

            {/* Trailer storage. Asked here rather than left to the NeX-Up page,
                because a trailer NeX-Up can download but the media server cannot
                open is the most common way this feature appears broken. */}
            <div style={{ marginTop: '1.4rem', paddingTop: '1.1rem', borderTop: `1px solid ${LINE}` }}>
              <div style={{ fontWeight: 700, color: txt, fontSize: '0.9rem', marginBottom: '0.3rem' }}>
                Where should trailers be saved?
              </div>
              <p style={{ color: sub, fontSize: '0.83rem', margin: '0 0 0.75rem', lineHeight: 1.55 }}>
                {isDockerInstall
                  ? 'This path is inside the container. Keeping it under your prerolls folder means it is already mounted and already reachable by your media server.'
                  : 'Keeping this under your prerolls folder means your media server can reach it with no extra setup.'}
              </p>

              <label htmlFor="nx-wiz-trailer-folder" style={labelStyle}>Trailer folder</label>
              <input
                id="nx-wiz-trailer-folder"
                onKeyDown={onEnter(() => { if (!nexupStorageBusy && nexupStorage.trim()) saveNexupStorage(); })}
                style={inputStyle}
                value={nexupStorage}
                onChange={(e) => { setNexupStorage(e.target.value); setStorageCheck(null); }}
                placeholder={suggestedNexupPath}
              />
              {suggestedNexupPath && nexupStorage !== suggestedNexupPath && (
                <button
                  type="button"
                  style={{ ...ghostBtn, marginTop: '0.5rem', border: 'none', padding: '0.25rem 0', color: ACCENT, fontSize: '0.8rem' }}
                  onClick={() => { setNexupStorage(suggestedNexupPath); setStorageCheck(null); }}
                >
                  Use the recommended folder ({suggestedNexupPath})
                </button>
              )}

              <div style={{ marginTop: '0.9rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button type="button" style={primaryBtn} disabled={nexupStorageBusy || !nexupStorage.trim()} onClick={saveNexupStorage}>
                  {nexupStorageBusy ? <Loader2 size={16} className="spin" /> : <HardDrive size={16} />} Save trailer folder
                </button>
              </div>
              <ResultBadge result={nexupStorageResult} />

              {storageCheck && (
                <div style={{
                  marginTop: '0.7rem', padding: '0.6rem 0.8rem', borderRadius: '9px',
                  display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.82rem', lineHeight: 1.5,
                  background: storageCheck.reachable ? 'var(--success-soft)' : 'var(--warning-soft)',
                  color: storageCheck.reachable ? GOOD : WARN,
                  border: `1px solid ${TINT(storageCheck.reachable ? GOOD : WARN, 35)}`,
                }}>
                  {storageCheck.reachable ? <Check size={15} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                                          : <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '0.1rem' }} />}
                  <span>{storageCheck.detail}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ---- Storage ---- */}
        {step.key === 'storage' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0 }}>Preroll storage</h2>
            <p style={{ color: sub, marginTop: 0, lineHeight: 1.6 }}>
              {currentFolder
                ? 'Uploaded prerolls are stored here. This works as it is; change it only if you want them on another drive or share.'
                : 'Where should NeXroll store uploaded prerolls? Leave blank to use the default location.'}
            </p>
            {currentFolder && (
              <div style={{
                marginBottom: '1rem', padding: '0.6rem 0.8rem', borderRadius: '9px',
                border: `1px solid ${LINE}`, background: 'var(--neutral-soft)',
              }}>
                <div style={{ color: sub, fontSize: '0.75rem', marginBottom: '0.15rem' }}>
                  {(folderInfo && folderInfo.is_custom) ? 'Your folder' : 'Default folder'}
                </div>
                <code style={{ color: txt, fontSize: '0.84rem', overflowWrap: 'anywhere' }}>{currentFolder}</code>
              </div>
            )}
            <label htmlFor="nx-wiz-storage" style={labelStyle}>Use a different folder (optional)</label>
            <input id="nx-wiz-storage" style={inputStyle} value={storagePath} onChange={(e) => setStoragePath(e.target.value)}
              onKeyDown={onEnter(() => { if (!storageBusy && storagePath.trim()) saveStorage(); })}
              placeholder={currentFolder.includes('\\') ? 'D:\\Media\\Prerolls' : '/media/prerolls'} />
            <p style={{ color: sub, fontSize: '0.78rem', margin: '0.35rem 0 0', lineHeight: 1.5 }}>
              The folder is created if it does not exist.
              {isRerun ? ' Prerolls already in the old folder are not moved; Settings, Storage can move them.' : ''}
            </p>
            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn} disabled={storageBusy || !storagePath.trim()} onClick={saveStorage}>
                {storageBusy ? <Loader2 size={16} className="spin" /> : <HardDrive size={16} />} Save folder
              </button>
            </div>
            <ResultBadge result={storageResult} />
          </div>
        )}

        {/* ---- Account ---- */}
        {step.key === 'account' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0 }}>Create your account</h2>
            {accountExists ? (
              <>
                <p style={{ color: sub, marginTop: 0, lineHeight: 1.6 }}>
                  This NeXroll already has an account, so there is nothing to do here.
                  Add or change accounts any time under Settings, Users.
                </p>
                <div style={{
                  marginTop: '0.9rem', padding: '0.7rem 0.9rem', borderRadius: '10px',
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  background: 'var(--success-soft)', color: GOOD,
                  border: `1px solid ${TINT(GOOD, 35)}`, fontSize: '0.85rem',
                }}>
                  <Check size={16} /> Account already set up
                </div>
              </>
            ) : (acctResult && acctResult.ok) ? (
              <ResultBadge result={acctResult} />
            ) : (
              <>
                <p style={{ color: sub, marginTop: 0 }}>
                  Recommended. Creates an admin account so you can require login to protect your NeXroll.
                </p>
                <label htmlFor="nx-wiz-user" style={labelStyle}>Username</label>
                <input id="nx-wiz-user" onKeyDown={onEnter(createAccount)} style={inputStyle} value={acctUser} onChange={(e) => setAcctUser(e.target.value)} placeholder="admin" autoComplete="username" />
                <div style={{ fontSize: '0.75rem', color: acctUser && validateUsername(acctUser) ? WARN : sub, marginTop: '0.25rem' }}>
                  {(acctUser && validateUsername(acctUser)) || 'Letters and numbers only, at least 3 characters.'}
                </div>
                <div style={{ height: '0.5rem' }} />
                <label htmlFor="nx-wiz-pass" style={labelStyle}>Password</label>
                <input id="nx-wiz-pass" onKeyDown={onEnter(createAccount)} type="password" style={inputStyle} value={acctPass} onChange={(e) => setAcctPass(e.target.value)} autoComplete="new-password" />
                <div style={{ fontSize: '0.75rem', color: acctPass && validatePassword(acctPass) ? WARN : sub, marginTop: '0.25rem' }}>
                  {(acctPass && validatePassword(acctPass)) || 'At least 8 characters, mixed case, and a number.'}
                </div>
                <div style={{ height: '0.5rem' }} />
                <label htmlFor="nx-wiz-confirm" style={labelStyle}>Confirm password</label>
                <input id="nx-wiz-confirm" onKeyDown={onEnter(createAccount)} type="password" style={inputStyle} value={acctConfirm} onChange={(e) => setAcctConfirm(e.target.value)} autoComplete="new-password" />
                {acctConfirm && acctPass !== acctConfirm && (
                  <div style={{ fontSize: '0.75rem', color: WARN, marginTop: '0.25rem' }}>Passwords do not match.</div>
                )}
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.9rem', color: txt, fontSize: '0.88rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={acctEnableAuth} onChange={(e) => setAcctEnableAuth(e.target.checked)}
                    style={{ flex: '0 0 auto', margin: 0 }} />
                  <span style={{ flex: 1, minWidth: 0 }}>Require login after setup (recommended)</span>
                </label>
                <div style={{ marginTop: '1rem' }}>
                  <button type="button" style={primaryBtn} disabled={acctBusy || !acctUser || !acctPass} onClick={createAccount}>
                    {acctBusy ? <Loader2 size={16} className="spin" /> : <UserPlus size={16} />} Create account
                  </button>
                </div>
                <ResultBadge result={acctResult} />
              </>
            )}
          </div>
        )}

        {/* ---- Done ---- */}
        {step.key === 'done' && (
          <div style={{ textAlign: 'center' }}>
            {serverDone
              ? <CheckCircle size={44} style={{ color: GOOD, marginBottom: '0.75rem' }} />
              : <Server size={44} style={{ color: WARN, marginBottom: '0.75rem' }} />}
            <h2 style={{ color: txt, margin: '0 0 0.5rem' }}>{serverDone ? "You're all set!" : 'One thing is still missing'}</h2>
            <p style={{ color: sub, lineHeight: 1.6, maxWidth: '420px', margin: '0 auto 1rem' }}>
              {serverDone
                ? 'Here is where things stand. Anything left undone is waiting for you in the sidebar, and you can reopen this wizard any time from Settings, System.'
                : 'No media server is connected, so nothing can play yet. Connect one now, or later from the Connect page.'}
            </p>
            {!serverDone && (
              <div style={{ marginBottom: '1rem' }}>
                <button type="button" style={ghostBtn} onClick={() => jumpTo(steps.findIndex((x) => x.key === 'server'))}>
                  <Server size={15} /> Connect a media server
                </button>
              </div>
            )}

            {/* What actually got configured, so nobody has to guess. */}
            <div style={{ textAlign: 'left', maxWidth: '440px', margin: '0 auto 1.25rem', display: 'grid', gap: '0.4rem' }}>
              {summaryItems.map((item) => (
                <div key={item.label} style={{
                  display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.2rem 0.55rem',
                  padding: '0.5rem 0.7rem', borderRadius: '9px',
                  border: `1px solid ${LINE}`,
                  background: 'var(--neutral-soft)',
                }}>
                  {item.done
                    ? <Check size={15} style={{ color: GOOD, flexShrink: 0 }} />
                    : <span style={{ width: 15, height: 15, borderRadius: '50%', flexShrink: 0, border: `1.5px solid ${sub}` }} />}
                  <span style={{ color: txt, fontSize: '0.85rem', fontWeight: 600, minWidth: '106px' }}>{item.label}</span>
                  <span style={{ color: sub, fontSize: '0.8rem', flex: '1 1 170px', minWidth: 0, overflowWrap: 'anywhere' }}>{item.detail}</span>
                </div>
              ))}
            </div>

            {pluginServers.length > 0 && (
              <p style={{ color: sub, fontSize: '0.83rem', lineHeight: 1.55, maxWidth: '440px', margin: '0 auto 1.25rem', textAlign: 'left' }}>
                <strong style={{ color: txt }}>Next:</strong> {naming(pluginServers)} {pluginServers.length > 1 ? 'play' : 'plays'} prerolls
                through the NeXroll Intros plugin. If it is not installed yet, open Connect after this for the download and the steps.
              </p>
            )}
            <button type="button" style={{ ...primaryBtn, fontSize: '1rem', padding: '0.7rem 1.6rem' }}
              disabled={finishing} onClick={completeOnboarding}>
              {finishing ? <Loader2 size={18} className="spin" /> : <Rocket size={18} />} Finish &amp; open NeXroll
            </button>
          </div>
        )}

        {/* ---- Footer nav ---- */}
        {step.key !== 'done' && leaveNote === step.key && unsaved && (
          <div role="alert" style={{
            marginTop: '1.25rem', padding: '0.6rem 0.8rem', borderRadius: '9px', fontSize: '0.84rem', lineHeight: 1.5,
            background: 'var(--warning-soft)', color: WARN, border: `1px solid ${TINT(WARN, 35)}`,
          }}>
            {unsaved} Or continue without it.
          </div>
        )}
        {step.key !== 'done' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: leaveNote === step.key && unsaved ? '0.9rem' : '1.75rem' }}>
            <button type="button" style={{ ...ghostBtn, visibility: stepIdx === 0 ? 'hidden' : 'visible' }} onClick={back}>
              <ChevronLeft size={16} /> Back
            </button>
            {/* One way forward. It reads Skip until the step has something set up. */}
            <button type="button" style={stepIdx === 0 || stepDone[step.key] || step.key === 'storage' ? primaryBtn : ghostBtn}
              onClick={stepIdx === 0 ? startSetup : advance}>
              {stepIdx === 0 ? 'Get started'
                : (leaveNote === step.key && unsaved) ? 'Continue without it'
                  : (stepDone[step.key] || step.key === 'storage') ? 'Next' : 'Skip for now'} <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Skip-everything escape hatch */}
      {step.key !== 'done' && (
        <button type="button" onClick={completeOnboarding} disabled={finishing}
          style={{ marginTop: '1rem', background: 'none', border: 'none', color: sub, cursor: 'pointer', fontSize: '0.8rem', textDecoration: 'underline' }}>
          {isRerun ? 'Close the wizard and go back to NeXroll' : 'Skip setup and go straight to NeXroll'}
        </button>
      )}
    </div>
  );
}

export default OnboardingWizard;
