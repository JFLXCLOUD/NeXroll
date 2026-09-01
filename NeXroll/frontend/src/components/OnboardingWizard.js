import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Rocket, Server, Sparkles, HardDrive, UserPlus, CheckCircle,
  ChevronLeft, ChevronRight, Loader2, ExternalLink, Check, AlertCircle,
  FolderSync, ArrowRight, Plus, X, Box, HelpCircle
} from 'lucide-react';

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

// The Paths step exists only on a container install, so the run's step list is
// built from this rather than being fixed.
const BASE_STEPS = [
  { key: 'welcome', label: 'Welcome', icon: Rocket },
  { key: 'server', label: 'Media Server', icon: Server },
  { key: 'paths', label: 'Paths', icon: FolderSync, dockerOnly: true },
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

  // Docker path mappings. dockerInfo stays null off-container, which is what
  // keeps the Paths step out of the list entirely.
  const [dockerInfo, setDockerInfo] = useState(null);
  const [installInfo, setInstallInfo] = useState(null);
  const [install, setInstall] = useState(null); // {is_rerun, users_exist, has_server}
  const [pathRows, setPathRows] = useState([{ local: '', plex: '' }]);
  const [pathBusy, setPathBusy] = useState(false);
  const [pathResult, setPathResult] = useState(null);
  const [pathHelpOpen, setPathHelpOpen] = useState(false);
  const [testPath, setTestPath] = useState('');
  const [testOut, setTestOut] = useState(null);

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
        if (!data.is_docker) return;
        setDockerInfo(data);
        // Seed the first row with the one mapping every install needs: the
        // folder NeXroll writes prerolls into. The user only has to supply the
        // right-hand side, which is the half only they can know.
        if (Array.isArray(data.mappings) && data.mappings.length) setPathRows(data.mappings);
        else if (data.prerolls_dir) setPathRows([{ local: data.prerolls_dir, plex: '' }]);
      } catch { /* not fatal: the step simply does not appear */ }
    })();
    return () => { cancelled = true; };
  }, [apiUrl]);

  const steps = useMemo(
    () => BASE_STEPS.filter((s) => !s.dockerOnly || !!dockerInfo),
    [dockerInfo]
  );
  const step = steps[Math.min(stepIdx, steps.length - 1)];
  const next = () => setStepIdx((i) => Math.min(i + 1, steps.length - 1));
  const back = () => setStepIdx((i) => Math.max(i - 1, 0));

  const safeJson = async (res) => { try { return await res.json(); } catch { return null; } };

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
          body: JSON.stringify({ url: serverUrl, api_key: serverApiKey }),
        });
      } else if (serverType === 'emby') {
        res = await fetch(apiUrl('/emby/connect'), {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: serverUrl, api_key: serverApiKey }),
        });
      } else {
        // Plex token-based connect (OAuth is handled on the full Connect page)
        res = await fetch(apiUrl('/plex/connect'), {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: serverUrl, token: serverApiKey }),
        });
      }
      const data = await safeJson(res);
      if (res.ok) {
        setServerResult({ ok: true, msg: 'Connected successfully.' });
      } else {
        setServerResult({ ok: false, msg: (data && (data.detail || data.message)) || 'Connection failed. Check the URL and token/key.' });
      }
    } catch {
      setServerResult({ ok: false, msg: 'Could not reach the server. Check the URL.' });
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

  const connectNexup = async () => {
    setNexupBusy(true);
    setNexupResult(null);
    const results = [];
    try {
      if (radarrUrl && radarrKey) {
        const r = await fetch(apiUrl(`/nexup/radarr/connect?url=${encodeURIComponent(radarrUrl)}&api_key=${encodeURIComponent(radarrKey)}`), { method: 'POST', credentials: 'include' });
        results.push(`Radarr: ${r.ok ? 'connected' : 'failed'}`);
      }
      if (sonarrUrl && sonarrKey) {
        const s = await fetch(apiUrl(`/nexup/sonarr/connect?url=${encodeURIComponent(sonarrUrl)}&api_key=${encodeURIComponent(sonarrKey)}`), { method: 'POST', credentials: 'include' });
        results.push(`Sonarr: ${s.ok ? 'connected' : 'failed'}`);
      }
      const anyFail = results.some((r) => r.includes('failed'));
      setNexupResult({ ok: !anyFail && results.length > 0, msg: results.length ? results.join(' · ') : 'Nothing to connect.' });
    } catch {
      setNexupResult({ ok: false, msg: 'Connection error.' });
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
        body: JSON.stringify({ folder: storagePath }),
      });
      const data = await safeJson(res);
      if (res.ok) setStorageResult({ ok: true, msg: 'Storage folder saved.' });
      else setStorageResult({ ok: false, msg: (data && (data.detail || data.message)) || 'Could not save folder.' });
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
  const summaryItems = [
    { label: 'Media server', done: !!(serverResult && serverResult.ok) || plexOAuth.status === 'connected' || !!(install && install.has_server),
      detail: (serverResult && serverResult.ok) || plexOAuth.status === 'connected' || (install && install.has_server)
        ? 'Connected' : 'Not connected yet' },
    ...(dockerInfo ? [{ label: 'Path mappings', done: !!(pathResult && pathResult.ok) || !!(dockerInfo.mappings && dockerInfo.mappings.length),
      detail: (pathResult && pathResult.ok) || (dockerInfo.mappings && dockerInfo.mappings.length) ? 'Saved' : 'Not set — prerolls may not play' }] : []),
    { label: 'NeX-Up', done: !!(nexupResult && nexupResult.ok), detail: (nexupResult && nexupResult.ok) ? 'Connected' : 'Optional, skipped' },
    { label: 'Storage', done: !!(storageResult && storageResult.ok), detail: (storageResult && storageResult.ok) ? 'Custom folder saved' : 'Using the default folder' },
    { label: 'Account', done: accountExists || !!(acctResult && acctResult.ok), detail: accountExists || (acctResult && acctResult.ok) ? 'Ready' : 'No login required' },
  ];

  const isDockerInstall = !!(installInfo && installInfo.is_docker);
  const suggestedNexupPath = (installInfo && installInfo.nexup_suggested_path) || '';
  const exampleLocal = (dockerInfo && dockerInfo.prerolls_dir) || '/data/prerolls';
  const mountList = (dockerInfo && Array.isArray(dockerInfo.mounts)) ? dockerInfo.mounts : [];
  // Fill the first empty NeXroll-side field, or append a row if all are taken.
  const applyMountToRow = (mount) => setPathRows((rows) => {
    const i = rows.findIndex((r) => !r.local);
    if (i === -1) return [...rows, { local: mount, plex: '' }];
    return rows.map((r, ri) => (ri === i ? { ...r, local: mount } : r));
  });

  const updatePathRow = (idx, key, value) =>
    setPathRows((rows) => rows.map((r, i) => (i === idx ? { ...r, [key]: value } : r)));
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
      if (res.ok) setPathResult({ ok: true, msg: `Saved ${mappings.length} mapping${mappings.length === 1 ? '' : 's'}.` });
      else setPathResult({ ok: false, msg: (data && (data.detail || data.message)) || 'Could not save mappings.' });
    } catch {
      setPathResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setPathBusy(false);
    }
  };

  // Translate a real path through the saved rules, so the user can see the
  // answer their media server will be given rather than trusting the mapping.
  const runPathTest = async () => {
    const target = (testPath || '').trim();
    if (!target) return;
    setTestOut({ pending: true });
    try {
      const res = await fetch(apiUrl('settings/path-mappings/test'), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: [target] }),
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
    try {
      await fetch(apiUrl('/onboarding/complete'), { method: 'POST', credentials: 'include' });
    } catch { /* best effort */ }
    setFinishing(false);
    if (onFinish) onFinish();
  };

  // ---- UI helpers ----
  const card = {
    width: '100%', maxWidth: '640px',
    backgroundColor: darkMode ? '#25253a' : '#fff',
    borderRadius: '16px', padding: '2rem',
    boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
    border: `1px solid ${darkMode ? '#3a3a5a' : '#e0e0e0'}`,
  };
  const txt = darkMode ? '#e0e0e0' : '#222';
  const sub = darkMode ? '#aaa' : '#666';
  const inputStyle = {
    width: '100%', padding: '0.6rem 0.75rem', borderRadius: '8px',
    border: `1px solid ${darkMode ? '#3a3a5a' : '#ccc'}`,
    background: darkMode ? '#1e1e2e' : '#fff', color: txt, fontSize: '0.95rem',
  };
  const labelStyle = { display: 'block', marginBottom: '0.35rem', fontWeight: 600, color: txt, fontSize: '0.85rem' };
  const primaryBtn = {
    padding: '0.6rem 1.25rem', border: 'none', borderRadius: '8px',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.95rem',
    display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
  };
  const ghostBtn = {
    padding: '0.6rem 1.1rem', border: `1px solid ${darkMode ? '#3a3a5a' : '#ccc'}`,
    borderRadius: '8px', background: 'transparent', color: txt, cursor: 'pointer', fontSize: '0.9rem',
    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
  };

  const ResultBadge = ({ result }) => {
    if (!result) return null;
    return (
      <div style={{
        marginTop: '0.75rem', padding: '0.6rem 0.8rem', borderRadius: '8px', fontSize: '0.85rem',
        display: 'flex', alignItems: 'center', gap: '0.5rem',
        background: result.ok ? 'rgba(40,167,69,0.12)' : 'rgba(220,53,69,0.12)',
        color: result.ok ? '#22c55e' : '#ef4444',
        border: `1px solid ${result.ok ? 'rgba(40,167,69,0.35)' : 'rgba(220,53,69,0.35)'}`,
      }}>
        {result.ok ? <Check size={16} /> : <AlertCircle size={16} />}
        <span>{result.msg}</span>
      </div>
    );
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '1.5rem',
      backgroundColor: darkMode ? '#1a1a2e' : '#f5f5f5',
    }}>
      {/* Step indicator */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        {steps.map((s, i) => {
          const Icon = s.icon;
          const active = i === stepIdx;
          const done = i < stepIdx;
          return (
            <div key={s.key} style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.35rem 0.7rem',
              borderRadius: '20px', fontSize: '0.78rem', fontWeight: active ? 700 : 500,
              background: active ? 'rgba(102,126,234,0.18)' : (done ? 'rgba(40,167,69,0.12)' : 'transparent'),
              color: active ? '#818cf8' : (done ? '#22c55e' : sub),
              border: `1px solid ${active ? 'rgba(102,126,234,0.4)' : 'transparent'}`,
            }}>
              {done ? <Check size={14} /> : <Icon size={14} />}
              <span>{s.label}</span>
            </div>
          );
        })}
      </div>

      <div style={card}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '1.25rem' }}>
          <img src={darkMode ? '/NeXroll_Logo_WHT.png' : '/NeXroll_Logo_BLK.png'} alt="NeXroll" style={{ height: '46px' }} />
        </div>

        {/* ---- Welcome ---- */}
        {step.key === 'welcome' && (
          <div style={{ textAlign: 'center' }}>
            <Rocket size={40} style={{ color: '#818cf8', marginBottom: '0.75rem' }} />
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
                  style={{ ...ghostBtn, flex: 1, justifyContent: 'center', textTransform: 'capitalize',
                    borderColor: serverType === t ? '#667eea' : (darkMode ? '#3a3a5a' : '#ccc'),
                    background: serverType === t ? 'rgba(102,126,234,0.12)' : 'transparent',
                    color: serverType === t ? '#818cf8' : txt, fontWeight: serverType === t ? 700 : 500 }}>
                  {t}
                </button>
              ))}
            </div>

            {serverType === 'plex' ? (
              <div style={{
                marginBottom: '1rem', padding: '0.9rem 1rem', borderRadius: '10px',
                background: darkMode ? 'rgba(246,104,94,0.10)' : 'rgba(246,104,94,0.08)',
                border: `1px solid ${darkMode ? 'rgba(246,104,94,0.30)' : 'rgba(246,104,94,0.25)'}`,
              }}>
                <div style={{ fontWeight: 700, color: txt, fontSize: '0.88rem', marginBottom: '0.3rem' }}>
                  Sign in with Plex (recommended)
                </div>
                <p style={{ color: sub, fontSize: '0.82rem', margin: '0 0 0.75rem', lineHeight: 1.55 }}>
                  Opens Plex in a new tab. Approve NeXroll there and we will find your
                  server and its token automatically, so there is nothing to copy by hand.
                </p>

                {plexOAuth.status === 'connected' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#22c55e', fontSize: '0.86rem', fontWeight: 600 }}>
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
                        <a href={plexOAuth.url} target="_blank" rel="noopener noreferrer" style={{ color: '#818cf8' }}>
                          open the Plex sign-in page
                        </a>.
                      </div>
                    )}
                    {plexOAuth.status === 'expired' && (
                      <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: '#f59e0b' }}>
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
              <label style={labelStyle}>Server URL</label>
              <input
                style={inputStyle}
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder={serverType === 'plex' ? 'http://192.168.1.10:32400' : 'http://192.168.1.10:8096'}
              />
              <div style={{ height: '0.75rem' }} />
              <label style={labelStyle}>{serverType === 'plex' ? 'Plex Token' : 'API Key'}</label>
              <input
                type="password"
                autoComplete="off"
                style={inputStyle}
                value={serverApiKey}
                onChange={(e) => setServerApiKey(e.target.value)}
                placeholder={serverType === 'plex' ? 'X-Plex-Token' : 'API key'}
              />
              <div style={{ marginTop: '1rem' }}>
                <button type="button" style={primaryBtn} disabled={serverBusy || !serverUrl || !serverApiKey} onClick={connectServer}>
                  {serverBusy ? <Loader2 size={16} className="spin" /> : <Server size={16} />} Test &amp; Connect
                </button>
              </div>
            </details>
            <ResultBadge result={serverResult} />
          </div>
        )}

        {/* ---- Path Mappings (Docker only) ---- */}
        {step.key === 'paths' && (
          <div>
            <h2 style={{ color: txt, marginTop: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Box size={20} style={{ color: '#818cf8' }} /> One thing Docker needs
            </h2>
            <p style={{ color: sub, marginTop: 0, lineHeight: 1.6 }}>
              NeXroll is running in a container. Inside it, your files live at one path.
              Your media server sees those same files at a <em>different</em> path. When
              NeXroll tells the server which preroll to play, it has to send the path the
              server understands.
            </p>
            <p style={{ color: sub, marginTop: '0.6rem', lineHeight: 1.6 }}>
              Get this wrong and nothing looks broken: the server accepts the setting and
              then quietly plays no preroll. So it is worth two minutes now.
            </p>

            {/* Worked example, using this install's real preroll folder. */}
            <div style={{
              marginTop: '1rem', padding: '0.85rem 1rem', borderRadius: '10px',
              background: darkMode ? 'rgba(102,126,234,0.10)' : 'rgba(102,126,234,0.08)',
              border: `1px solid ${darkMode ? 'rgba(102,126,234,0.30)' : 'rgba(102,126,234,0.25)'}`,
            }}>
              <div style={{ fontWeight: 700, color: txt, fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                The same file, two names
              </div>
              <div style={{ display: 'grid', gap: '0.35rem', fontSize: '0.78rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
                <div style={{ color: sub }}>
                  NeXroll sees{'\u00a0\u00a0'}
                  <span style={{ color: txt }}>{exampleLocal}/holiday/xmas.mp4</span>
                </div>
                <div style={{ color: sub }}>
                  Server sees{'\u00a0\u00a0\u00a0'}
                  <span style={{ color: txt }}>/mnt/media/prerolls/holiday/xmas.mp4</span>
                </div>
              </div>
              <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: sub }}>
                So the mapping is <code style={{ color: '#818cf8' }}>{exampleLocal}</code>
                {' '}<ArrowRight size={11} style={{ verticalAlign: 'middle' }} />{' '}
                <code style={{ color: '#818cf8' }}>/mnt/media/prerolls</code>. Only the start of
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
                        border: `1px solid ${darkMode ? '#3a3a5a' : '#ccc'}`,
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
                <div key={idx} style={{ display: 'flex', gap: '0.45rem', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {idx === 0 && <label style={labelStyle}>Path inside NeXroll</label>}
                    <input
                      style={inputStyle}
                      value={row.local}
                      placeholder={exampleLocal}
                      onChange={(e) => updatePathRow(idx, 'local', e.target.value)}
                    />
                  </div>
                  <ArrowRight size={16} style={{ color: '#818cf8', flexShrink: 0, marginBottom: '0.65rem' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {idx === 0 && <label style={labelStyle}>Path your media server uses</label>}
                    <input
                      style={inputStyle}
                      value={row.plex}
                      placeholder="/mnt/media/prerolls"
                      onChange={(e) => updatePathRow(idx, 'plex', e.target.value)}
                    />
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
              style={{ ...ghostBtn, marginTop: '0.9rem', border: 'none', padding: '0.3rem 0', color: '#818cf8' }}
            >
              <HelpCircle size={15} /> Where do I find my server&apos;s path?
            </button>
            {pathHelpOpen && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.82rem', color: sub, lineHeight: 1.65 }}>
                <p style={{ margin: '0 0 0.5rem' }}>
                  <strong style={{ color: txt }}>If your media server also runs in Docker:</strong> open
                  its compose file or container settings and look at its volumes. Each one reads{' '}
                  <code>host path : container path</code>. The <em>right</em> side is what that server
                  sees, and that is what belongs in the right-hand column above.
                </p>
                <p style={{ margin: '0 0 0.5rem' }}>
                  <strong style={{ color: txt }}>If your media server runs directly on the host</strong>{' '}
                  (or another machine): use the folder as that machine sees it, for example{' '}
                  <code>/mnt/media/prerolls</code>, <code>D:\Media\Prerolls</code>, or{' '}
                  <code>\\NAS\media\prerolls</code>.
                </p>
                <p style={{ margin: 0 }}>
                  <strong style={{ color: txt }}>Still unsure?</strong> In Plex, open Settings, Manage,
                  Libraries, then Edit a library: the folders listed there are exactly the paths Plex
                  uses. Jellyfin and Emby show the same under their library settings.
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
              <div style={{ marginTop: '1rem', paddingTop: '0.9rem', borderTop: `1px solid ${darkMode ? '#3a3a5a' : '#e0e0e0'}` }}>
                <label style={labelStyle}>Check it (optional)</label>
                <div style={{ display: 'flex', gap: '0.45rem' }}>
                  <input
                    style={{ ...inputStyle, flex: 1 }}
                    value={testPath}
                    placeholder={`${exampleLocal}/holiday/xmas.mp4`}
                    onChange={(e) => setTestPath(e.target.value)}
                  />
                  <button type="button" style={ghostBtn} onClick={runPathTest} disabled={!testPath.trim()}>
                    {testOut && testOut.pending ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Translate
                  </button>
                </div>
                {testOut && !testOut.pending && (
                  <div style={{ marginTop: '0.55rem', fontSize: '0.8rem', color: sub }}>
                    {testOut.error || !testOut.output ? (
                      <span style={{ color: '#ef4444' }}>
                        No mapping matched that path. Check that the left-hand column above starts the same way.
                      </span>
                    ) : (
                      <>
                        Your media server will be told:{' '}
                        <code style={{ color: '#22c55e' }}>{testOut.output}</code>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

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
            <label style={labelStyle}>Radarr URL</label>
            <input style={inputStyle} value={radarrUrl} onChange={(e) => setRadarrUrl(e.target.value)} placeholder="http://192.168.1.10:7878" />
            <div style={{ height: '0.5rem' }} />
            <label style={labelStyle}>Radarr API Key</label>
            <input type="password" autoComplete="off" style={inputStyle} value={radarrKey} onChange={(e) => setRadarrKey(e.target.value)} />
            <div style={{ height: '1rem' }} />
            <label style={labelStyle}>Sonarr URL</label>
            <input style={inputStyle} value={sonarrUrl} onChange={(e) => setSonarrUrl(e.target.value)} placeholder="http://192.168.1.10:8989" />
            <div style={{ height: '0.5rem' }} />
            <label style={labelStyle}>Sonarr API Key</label>
            <input type="password" autoComplete="off" style={inputStyle} value={sonarrKey} onChange={(e) => setSonarrKey(e.target.value)} />
            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn} disabled={nexupBusy || (!radarrUrl && !sonarrUrl)} onClick={connectNexup}>
                {nexupBusy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />} Connect
              </button>
            </div>
            <ResultBadge result={nexupResult} />

            {/* Trailer storage. Asked here rather than left to the NeX-Up page,
                because a trailer NeX-Up can download but the media server cannot
                open is the most common way this feature appears broken. */}
            <div style={{ marginTop: '1.4rem', paddingTop: '1.1rem', borderTop: `1px solid ${darkMode ? '#3a3a5a' : '#e0e0e0'}` }}>
              <div style={{ fontWeight: 700, color: txt, fontSize: '0.9rem', marginBottom: '0.3rem' }}>
                Where should trailers be saved?
              </div>
              <p style={{ color: sub, fontSize: '0.83rem', margin: '0 0 0.75rem', lineHeight: 1.55 }}>
                {isDockerInstall
                  ? 'This path is inside the container. Keeping it under your prerolls folder means it is already mounted and already reachable by your media server.'
                  : 'Keeping this under your prerolls folder means your media server can reach it with no extra setup.'}
              </p>

              <label style={labelStyle}>Trailer folder</label>
              <input
                style={inputStyle}
                value={nexupStorage}
                onChange={(e) => { setNexupStorage(e.target.value); setStorageCheck(null); }}
                placeholder={suggestedNexupPath}
              />
              {suggestedNexupPath && nexupStorage !== suggestedNexupPath && (
                <button
                  type="button"
                  style={{ ...ghostBtn, marginTop: '0.5rem', border: 'none', padding: '0.25rem 0', color: '#818cf8', fontSize: '0.8rem' }}
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
                  background: storageCheck.reachable ? 'rgba(40,167,69,0.12)' : 'rgba(245,158,11,0.12)',
                  color: storageCheck.reachable ? '#22c55e' : '#f59e0b',
                  border: `1px solid ${storageCheck.reachable ? 'rgba(40,167,69,0.35)' : 'rgba(245,158,11,0.35)'}`,
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
            <p style={{ color: sub, marginTop: 0 }}>
              Where should NeXroll store uploaded prerolls? Leave blank to use the default location.
            </p>
            <label style={labelStyle}>Storage folder path</label>
            <input style={inputStyle} value={storagePath} onChange={(e) => setStoragePath(e.target.value)}
              placeholder="/data/prerolls  (or  C:\\NeXroll\\Prerolls)" />
            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn} disabled={storageBusy || !storagePath} onClick={saveStorage}>
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
                  background: 'rgba(40,167,69,0.12)', color: '#22c55e',
                  border: '1px solid rgba(40,167,69,0.35)', fontSize: '0.85rem',
                }}>
                  <Check size={16} /> Account already set up
                </div>
              </>
            ) : (
              <>
                <p style={{ color: sub, marginTop: 0 }}>
                  Recommended. Creates an admin account so you can require login to protect your NeXroll.
                </p>
                <label style={labelStyle}>Username</label>
                <input style={inputStyle} value={acctUser} onChange={(e) => setAcctUser(e.target.value)} placeholder="admin" autoComplete="username" />
                <div style={{ fontSize: '0.75rem', color: acctUser && validateUsername(acctUser) ? '#f59e0b' : sub, marginTop: '0.25rem' }}>
                  {(acctUser && validateUsername(acctUser)) || 'Letters and numbers only, at least 3 characters.'}
                </div>
                <div style={{ height: '0.5rem' }} />
                <label style={labelStyle}>Password</label>
                <input type="password" style={inputStyle} value={acctPass} onChange={(e) => setAcctPass(e.target.value)} autoComplete="new-password" />
                <div style={{ fontSize: '0.75rem', color: acctPass && validatePassword(acctPass) ? '#f59e0b' : sub, marginTop: '0.25rem' }}>
                  {(acctPass && validatePassword(acctPass)) || 'At least 8 characters, mixed case, and a number.'}
                </div>
                <div style={{ height: '0.5rem' }} />
                <label style={labelStyle}>Confirm password</label>
                <input type="password" style={inputStyle} value={acctConfirm} onChange={(e) => setAcctConfirm(e.target.value)} autoComplete="new-password" />
                {acctConfirm && acctPass !== acctConfirm && (
                  <div style={{ fontSize: '0.75rem', color: '#f59e0b', marginTop: '0.25rem' }}>Passwords do not match.</div>
                )}
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.9rem', color: txt, fontSize: '0.88rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={acctEnableAuth} onChange={(e) => setAcctEnableAuth(e.target.checked)} />
                  Require login after setup (recommended)
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
            <CheckCircle size={44} style={{ color: '#22c55e', marginBottom: '0.75rem' }} />
            <h2 style={{ color: txt, margin: '0 0 0.5rem' }}>You&apos;re all set!</h2>
            <p style={{ color: sub, lineHeight: 1.6, maxWidth: '420px', margin: '0 auto 1rem' }}>
              Here is where things stand. Anything left undone is waiting for you in the
              sidebar, and you can reopen this wizard any time from Settings, System.
            </p>

            {/* What actually got configured, so nobody has to guess. */}
            <div style={{ textAlign: 'left', maxWidth: '440px', margin: '0 auto 1.25rem', display: 'grid', gap: '0.4rem' }}>
              {summaryItems.map((item) => (
                <div key={item.label} style={{
                  display: 'flex', alignItems: 'center', gap: '0.55rem',
                  padding: '0.5rem 0.7rem', borderRadius: '9px',
                  border: `1px solid ${darkMode ? '#3a3a5a' : '#e0e0e0'}`,
                  background: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                }}>
                  {item.done
                    ? <Check size={15} style={{ color: '#22c55e', flexShrink: 0 }} />
                    : <span style={{ width: 15, height: 15, borderRadius: '50%', flexShrink: 0, border: `1.5px solid ${sub}` }} />}
                  <span style={{ color: txt, fontSize: '0.85rem', fontWeight: 600, minWidth: '106px' }}>{item.label}</span>
                  <span style={{ color: sub, fontSize: '0.8rem' }}>{item.detail}</span>
                </div>
              ))}
            </div>

            <button type="button" style={{ ...primaryBtn, fontSize: '1rem', padding: '0.7rem 1.6rem' }}
              disabled={finishing} onClick={completeOnboarding}>
              {finishing ? <Loader2 size={18} className="spin" /> : <Rocket size={18} />} Finish &amp; open NeXroll
            </button>
          </div>
        )}

        {/* ---- Footer nav ---- */}
        {step.key !== 'done' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.75rem' }}>
            <button type="button" style={{ ...ghostBtn, visibility: stepIdx === 0 ? 'hidden' : 'visible' }} onClick={back}>
              <ChevronLeft size={16} /> Back
            </button>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {stepIdx !== 0 && (
                <button type="button" style={ghostBtn} onClick={next}>Skip</button>
              )}
              <button type="button" style={primaryBtn} onClick={next}>
                {stepIdx === 0 ? 'Get started' : 'Next'} <ChevronRight size={16} />
              </button>
            </div>
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
