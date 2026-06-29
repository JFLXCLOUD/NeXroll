import React, { useState } from 'react';
import {
  Rocket, Server, Sparkles, HardDrive, UserPlus, CheckCircle,
  ChevronLeft, ChevronRight, Loader2, ExternalLink, Check, AlertCircle
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
 *   onDeepLink(tab)                  jump into a full section (also completes onboarding)
 */

const STEPS = [
  { key: 'welcome', label: 'Welcome', icon: Rocket },
  { key: 'server', label: 'Media Server', icon: Server },
  { key: 'nexup', label: 'NeX-Up', icon: Sparkles },
  { key: 'storage', label: 'Storage', icon: HardDrive },
  { key: 'account', label: 'Account', icon: UserPlus },
  { key: 'done', label: 'Finish', icon: CheckCircle },
];

function OnboardingWizard({ apiUrl, darkMode, onFinish, onDeepLink }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [finishing, setFinishing] = useState(false);

  // --- Step state ---
  const [serverType, setServerType] = useState('plex'); // plex | jellyfin | emby
  const [serverUrl, setServerUrl] = useState('');
  const [serverApiKey, setServerApiKey] = useState('');
  const [serverBusy, setServerBusy] = useState(false);
  const [serverResult, setServerResult] = useState(null); // {ok, msg}

  const [radarrUrl, setRadarrUrl] = useState('');
  const [radarrKey, setRadarrKey] = useState('');
  const [sonarrUrl, setSonarrUrl] = useState('');
  const [sonarrKey, setSonarrKey] = useState('');
  const [nexupBusy, setNexupBusy] = useState(false);
  const [nexupResult, setNexupResult] = useState(null);

  const [storagePath, setStoragePath] = useState('');
  const [storageBusy, setStorageBusy] = useState(false);
  const [storageResult, setStorageResult] = useState(null);

  const [acctUser, setAcctUser] = useState('');
  const [acctPass, setAcctPass] = useState('');
  const [acctConfirm, setAcctConfirm] = useState('');
  const [acctEnableAuth, setAcctEnableAuth] = useState(true);
  const [acctBusy, setAcctBusy] = useState(false);
  const [acctResult, setAcctResult] = useState(null);

  const step = STEPS[stepIdx];
  const next = () => setStepIdx((i) => Math.min(i + 1, STEPS.length - 1));
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

  const createAccount = async () => {
    if (acctPass !== acctConfirm) { setAcctResult({ ok: false, msg: 'Passwords do not match.' }); return; }
    const pwErr = validatePassword(acctPass);
    if (pwErr) { setAcctResult({ ok: false, msg: pwErr }); return; }
    setAcctBusy(true);
    setAcctResult(null);
    try {
      const res = await fetch(apiUrl('/auth/register'), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: acctUser, password: acctPass, display_name: acctUser }),
      });
      const data = await safeJson(res);
      if (!res.ok) { setAcctResult({ ok: false, msg: (data && data.detail) || 'Could not create account.' }); setAcctBusy(false); return; }

      // Optionally enable "require login" now that an admin exists.
      if (acctEnableAuth) {
        try {
          await fetch(apiUrl('/auth/settings'), {
            method: 'PUT', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auth_enabled: true }),
          });
        } catch { /* non-fatal */ }
      }
      setAcctResult({ ok: true, msg: acctEnableAuth ? 'Admin account created. Login is now required.' : 'Admin account created.' });
    } catch {
      setAcctResult({ ok: false, msg: 'Connection error.' });
    } finally {
      setAcctBusy(false);
    }
  };

  const completeOnboarding = async (deepLinkTab) => {
    setFinishing(true);
    try {
      await fetch(apiUrl('/onboarding/complete'), { method: 'POST', credentials: 'include' });
    } catch { /* best effort */ }
    setFinishing(false);
    if (deepLinkTab && onDeepLink) onDeepLink(deepLinkTab);
    else if (onFinish) onFinish();
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
        {STEPS.map((s, i) => {
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
            <h2 style={{ color: txt, margin: '0 0 0.5rem' }}>Welcome to NeXroll</h2>
            <p style={{ color: sub, lineHeight: 1.6, margin: '0 auto 0.5rem', maxWidth: '460px' }}>
              Let's get you set up. This quick wizard will connect your media server,
              optionally configure NeX-Up trailer automation, choose where prerolls are
              stored, and create your account. Every step is optional — you can skip
              anything and finish it later from the sidebar.
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
              <div>
                <p style={{ color: sub, fontSize: '0.88rem' }}>
                  Plex supports sign-in with your Plex account (recommended) on the full
                  Connections page. You can also paste a server URL and token below.
                </p>
                <button type="button" style={{ ...ghostBtn, marginBottom: '1rem' }} onClick={() => completeOnboarding('connect')}>
                  <ExternalLink size={15} /> Open full Plex sign-in
                </button>
              </div>
            ) : null}

            <label style={labelStyle}>Server URL</label>
            <input style={inputStyle} value={serverUrl} onChange={(e) => setServerUrl(e.target.value)}
              placeholder={serverType === 'plex' ? 'http://192.168.1.10:32400' : 'http://192.168.1.10:8096'} />
            <div style={{ height: '0.75rem' }} />
            <label style={labelStyle}>{serverType === 'plex' ? 'Plex Token' : 'API Key'}</label>
            <input style={inputStyle} value={serverApiKey} onChange={(e) => setServerApiKey(e.target.value)}
              placeholder={serverType === 'plex' ? 'X-Plex-Token' : 'API key'} />

            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn} disabled={serverBusy || !serverUrl} onClick={connectServer}>
                {serverBusy ? <Loader2 size={16} className="spin" /> : <Server size={16} />} Test &amp; Connect
              </button>
            </div>
            <ResultBadge result={serverResult} />
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
            <input style={inputStyle} value={radarrKey} onChange={(e) => setRadarrKey(e.target.value)} />
            <div style={{ height: '1rem' }} />
            <label style={labelStyle}>Sonarr URL</label>
            <input style={inputStyle} value={sonarrUrl} onChange={(e) => setSonarrUrl(e.target.value)} placeholder="http://192.168.1.10:8989" />
            <div style={{ height: '0.5rem' }} />
            <label style={labelStyle}>Sonarr API Key</label>
            <input style={inputStyle} value={sonarrKey} onChange={(e) => setSonarrKey(e.target.value)} />
            <div style={{ marginTop: '1rem' }}>
              <button type="button" style={primaryBtn} disabled={nexupBusy || (!radarrUrl && !sonarrUrl)} onClick={connectNexup}>
                {nexupBusy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />} Connect
              </button>
            </div>
            <ResultBadge result={nexupResult} />
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
            <p style={{ color: sub, marginTop: 0 }}>
              Recommended. Creates an admin account so you can require login to protect your NeXroll.
            </p>
            <label style={labelStyle}>Username</label>
            <input style={inputStyle} value={acctUser} onChange={(e) => setAcctUser(e.target.value)} placeholder="admin" autoComplete="username" />
            <div style={{ height: '0.5rem' }} />
            <label style={labelStyle}>Password</label>
            <input type="password" style={inputStyle} value={acctPass} onChange={(e) => setAcctPass(e.target.value)} autoComplete="new-password" />
            <div style={{ fontSize: '0.75rem', color: sub, marginTop: '0.25rem' }}>
              At least 8 characters, mixed case, and a number.
            </div>
            <div style={{ height: '0.5rem' }} />
            <label style={labelStyle}>Confirm password</label>
            <input type="password" style={inputStyle} value={acctConfirm} onChange={(e) => setAcctConfirm(e.target.value)} autoComplete="new-password" />
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
          </div>
        )}

        {/* ---- Done ---- */}
        {step.key === 'done' && (
          <div style={{ textAlign: 'center' }}>
            <CheckCircle size={44} style={{ color: '#22c55e', marginBottom: '0.75rem' }} />
            <h2 style={{ color: txt, margin: '0 0 0.5rem' }}>You're all set!</h2>
            <p style={{ color: sub, lineHeight: 1.6, maxWidth: '420px', margin: '0 auto 1rem' }}>
              NeXroll is ready. You can revisit any of these settings any time from the
              sidebar. Click Finish to open your dashboard.
            </p>
            <button type="button" style={{ ...primaryBtn, fontSize: '1rem', padding: '0.7rem 1.6rem' }}
              disabled={finishing} onClick={() => completeOnboarding(null)}>
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
        <button type="button" onClick={() => completeOnboarding(null)} disabled={finishing}
          style={{ marginTop: '1rem', background: 'none', border: 'none', color: sub, cursor: 'pointer', fontSize: '0.8rem', textDecoration: 'underline' }}>
          Skip setup and go straight to NeXroll
        </button>
      )}
    </div>
  );
}

export default OnboardingWizard;
