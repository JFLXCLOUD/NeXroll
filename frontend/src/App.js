import React, { useState, useEffect } from 'react';

// API helpers that resolve the backend base dynamically (works in Docker and behind proxies)
const apiBase = () => {
  try {
    if (typeof window !== 'undefined') {
      const b = window.__nexrollApiBase || (window.location && window.location.origin) || '';
      return String(b).replace(/\/+$/, '');
    }
  } catch {}
  return '';
};
const apiUrl = (path) => {
  try {
    const p = String(path || '').replace(/^\/+/, '');
    if (/^https?:\/\//i.test(String(path))) return String(path);
    const b = apiBase();
    return b ? `${b}/${p}` : `/${p}`;
  } catch {
    return path;
  }
};
// Runtime API base resolver + CORS shield: rewrite hardcoded http://localhost:9393 to same-origin or configured base
(function setupNeXrollApiBase() {
  try {
    const envBase = (typeof process !== 'undefined' && process && process.env && process.env.REACT_APP_API_BASE)
      ? String(process.env.REACT_APP_API_BASE)
      : null;
    const globalBase = (typeof window !== 'undefined' && window && window.NEXROLL_API_BASE)
      ? String(window.NEXROLL_API_BASE)
      : null;
    const sameOrigin = (typeof window !== 'undefined' && window.location && window.location.origin)
      ? String(window.location.origin)
      : '';
    const isDevUi = (typeof window !== 'undefined' && window.location && (window.location.port === '3000'));
    const base = (globalBase || envBase || (isDevUi ? 'http://localhost:9393' : sameOrigin) || '').replace(/\/+$/, '');
    const LOCAL_BASES = [
      'http://localhost:9393',
      'http://127.0.0.1:9393',
      'https://localhost:9393',
      'https://127.0.0.1:9393'
    ];

    const rewriteUrl = (u) => {
      try {
        if (typeof u !== 'string') return u;
        for (const lb of LOCAL_BASES) {
          if (u.startsWith(lb)) {
            const suffix = u.slice(lb.length);
            return base + (suffix.startsWith('/') ? suffix : '/' + suffix);
          }
        }
        return u;
      } catch {
        return u;
      }
    };

    // Expose helpers for incremental adoption
    if (typeof window !== 'undefined') {
      window.__nexrollApiBase = base;
      window.__nexrollRewriteApiUrl = rewriteUrl;
    }

    // Patch fetch to normalize absolute localhost calls at runtime
    if (typeof window !== 'undefined' && typeof window.fetch === 'function') {
      const origFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        try {
          if (typeof input === 'string') {
            return origFetch(rewriteUrl(input), init);
          } else if (input && typeof input === 'object' && typeof input.url === 'string') {
            // If a Request object is passed, clone with rewritten URL (best-effort)
            const Req = window.Request || null;
            if (Req) {
              const req2 = new Req(rewriteUrl(input.url), input);
              return origFetch(req2, init);
            }
          }
        } catch {}
        return origFetch(input, init);
      };
    }

    // Patch EventSource (SSE) similarly
    if (typeof window !== 'undefined' && typeof window.EventSource === 'function') {
      const OrigES = window.EventSource;
      const PatchedES = function(url, config) {
        const u2 = rewriteUrl(url);
        return new OrigES(u2, config);
      };
      PatchedES.prototype = OrigES.prototype;
      // Preserve static constants
      PatchedES.CONNECTING = OrigES.CONNECTING;
      PatchedES.OPEN = OrigES.OPEN;
      PatchedES.CLOSED = OrigES.CLOSED;
      window.EventSource = PatchedES;
    }
  } catch {
    // silent
  }
})();
const Modal = ({ title, onClose, children, width = 700 }) => {
  React.useEffect(() => {
    const onEsc = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    document.addEventListener('keydown', onEsc);
    return () => document.removeEventListener('keydown', onEsc);
  }, [onClose]);

  return (
    <div className="nx-modal-overlay" onMouseDown={(e) => { if (e.target.classList.contains('nx-modal-overlay')) onClose && onClose(); }}>
      <div className="nx-modal" style={{ maxWidth: width }}>
        <div className="nx-modal-header">
          <h3 className="nx-modal-title">{title}</h3>
          <button className="nx-modal-close" type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="nx-modal-body">
          {children}
        </div>
      </div>
    </div>
  );
};

const CategoryPicker = ({ categories, primaryId, secondaryIds, onChange, onCreateCategory, label = 'Categories', placeholder = 'Search categories…' }) => {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const containerRef = React.useRef(null);
  const inputRef = React.useRef(null);
  const listboxId = React.useMemo(() => 'nx-catpicker-list-' + Math.random().toString(36).slice(2), []);

  React.useEffect(() => {
    const onDocClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  React.useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const [creating, setCreating] = React.useState(false);

  const items = Array.isArray(categories) ? categories.map(c => ({ id: String(c.id), name: c.name })) : [];
  const normalizedPrimary = primaryId ? String(primaryId) : '';
  const normalizedSecondary = Array.isArray(secondaryIds) ? secondaryIds.map(String) : [];

  const selectedSet = new Set([normalizedPrimary, ...normalizedSecondary].filter(Boolean));

  const filtered = items.filter(i => i.name.toLowerCase().includes(query.toLowerCase()));

  const normalizedQuery = (query || '').trim();
  const existsByName = items.some(i => i.name.toLowerCase() === normalizedQuery.toLowerCase());
  const showCreate = !!onCreateCategory && normalizedQuery.length > 0 && !existsByName;

  const handleCreateCategory = async () => {
    if (!showCreate || !onCreateCategory) return;
    try {
      setCreating(true);
      const created = await onCreateCategory(normalizedQuery);
      if (created && created.id) {
        const newId = String(created.id);
        if (!normalizedPrimary) {
          onChange(newId, normalizedSecondary);
        } else {
          const nextSecondary = [...normalizedSecondary, newId].filter((v, i, a) => v && a.indexOf(v) === i);
          onChange(normalizedPrimary, nextSecondary);
        }
        setQuery('');
        setOpen(false);
      }
    } catch (err) {
      alert('Failed to create category: ' + (err && err.message ? err.message : err));
    } finally {
      setCreating(false);
    }
  };

  const toggle = (id) => {
    id = String(id);
    const isSelected = selectedSet.has(id);

    if (isSelected) {
      // Removing
      if (id === normalizedPrimary) {
        // Remove primary; promote first secondary (if any) to primary
        const remaining = normalizedSecondary.filter(x => x !== id);
        if (remaining.length > 0) {
          const newPrimary = remaining[0];
          const newSecondary = remaining.slice(1);
          onChange(newPrimary, newSecondary);
        } else {
          onChange('', []);
        }
      } else {
        const newSecondary = normalizedSecondary.filter(x => x !== id);
        onChange(normalizedPrimary, newSecondary);
      }
    } else {
      // Adding
      if (!normalizedPrimary) {
        onChange(id, normalizedSecondary);
      } else {
        const nextSecondary = [...normalizedSecondary, id].filter((v, i, a) => v && a.indexOf(v) === i);
        onChange(normalizedPrimary, nextSecondary);
      }
    }
  };

  const makePrimary = (id) => {
    id = String(id);
    if (id === normalizedPrimary) return;
    let nextSecondary = normalizedSecondary.filter(x => x !== id);
    if (normalizedPrimary) {
      nextSecondary = [normalizedPrimary, ...nextSecondary.filter(x => x !== normalizedPrimary)];
    }
    // Dedupe + remove blanks
    nextSecondary = nextSecondary.filter((v, i, a) => v && a.indexOf(v) === i);
    onChange(id, nextSecondary);
    setOpen(false);
  };

  const clearAll = () => {
    onChange('', []);
    setQuery('');
    setOpen(false);
  };

  const selectedItems = items.filter(i => selectedSet.has(i.id));
  const primaryItem = items.find(i => i.id === normalizedPrimary) || null;

  return (
    <div ref={containerRef} className="nx-catpicker">
      <label className="nx-label" style={{ marginBottom: '0.35rem' }}>{label}</label>

      <div
        className={`nx-catpicker-input ${open ? 'open' : ''}`}
        onClick={() => setOpen(true)}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
      >
        {primaryItem ? (
          <span className="nx-chip primary" title="Primary category">
            ⭐ {primaryItem.name}
            <button
              type="button"
              className="nx-chip-x"
              onClick={(e) => { e.stopPropagation(); toggle(primaryItem.id); }}
              aria-label="Remove primary"
              title="Remove primary"
            >
              ×
            </button>
          </span>
        ) : (
          <span className="nx-chip ghost">No primary</span>
        )}

        {selectedItems.filter(i => i.id !== normalizedPrimary).map(i => (
          <span key={i.id} className="nx-chip" title="Secondary category">
            {i.name}
            <button
              type="button"
              className="nx-chip-star"
              onClick={(e) => { e.stopPropagation(); makePrimary(i.id); }}
              aria-label={`Make ${i.name} primary`}
              title="Make primary"
            >
              ⭐
            </button>
            <button
              type="button"
              className="nx-chip-x"
              onClick={(e) => { e.stopPropagation(); toggle(i.id); }}
              aria-label={`Remove ${i.name}`}
              title="Remove"
            >
              ×
            </button>
          </span>
        ))}

        <input
          ref={inputRef}
          className="nx-catpicker-hidden-input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
        />

        {(normalizedPrimary || normalizedSecondary.length > 0) && (
          <button
            type="button"
            className="nx-catpicker-clear"
            onClick={(e) => { e.stopPropagation(); clearAll(); }}
            title="Clear all"
          >
            Clear
          </button>
        )}
      </div>

      {open && (
        <div className="nx-catpicker-dropdown">
          <div className="nx-catpicker-search">
            <input
              type="text"
              placeholder={placeholder}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {showCreate && (
            <div className="nx-catpicker-create">
              <button
                type="button"
                className="button"
                onClick={(e) => { e.stopPropagation(); handleCreateCategory(); }}
                disabled={creating}
                title={creating ? 'Creating…' : `Create category "${normalizedQuery}"`}
              >
                ➕ Create "{normalizedQuery}"{creating ? '…' : ''}
              </button>
            </div>
          )}
          <div id={listboxId} className="nx-catpicker-list" role="listbox">
            {filtered.length === 0 ? (
              <div className="nx-catpicker-empty">No categories found</div>
            ) : filtered.map(i => {
              const selected = selectedSet.has(i.id);
              const isPrimary = normalizedPrimary === i.id;
              return (
                <div
                  key={i.id}
                  className={`nx-catpicker-item ${selected ? 'selected' : ''}`}
                  onClick={() => toggle(i.id)}
                  role="option"
                  aria-selected={selected}
                >
                  <input type="checkbox" checked={selected} readOnly />
                  <span className="nx-catpicker-name">{i.name}</span>
                  <button
                    type="button"
                    className={`nx-catpicker-star ${isPrimary ? 'active' : ''}`}
                    onClick={(e) => { e.stopPropagation(); makePrimary(i.id); }}
                    title={isPrimary ? 'Primary' : 'Make primary'}
                    aria-label={isPrimary ? `${i.name} is primary` : `Make ${i.name} primary`}
                  >
                    ⭐
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
function App() {
  const [plexStatus, setPlexStatus] = useState('Disconnected');
  const [plexServerInfo, setPlexServerInfo] = useState(null);
  const [prerolls, setPrerolls] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [categories, setCategories] = useState([]);
  const [holidayPresets, setHolidayPresets] = useState([]);
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [activeTab, setActiveTab] = useState('dashboard');
  const [plexConfig, setPlexConfig] = useState({
    url: '',
    token: '',
    library: ''
  });
  const [schedulerStatus, setSchedulerStatus] = useState({ running: false, active_schedules: 0 });
  const [backupFile, setBackupFile] = useState(null);
  const [communityTemplates, setCommunityTemplates] = useState([]);
  const [selectedSchedules, setSelectedSchedules] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [editingPreroll, setEditingPreroll] = useState(null);
  const [editingCategory, setEditingCategory] = useState(null);
  const [stableTokenStatus, setStableTokenStatus] = useState({
    has_stable_token: false,
    config_file_exists: false,
    token_length: 0
  });
  // Plex.tv OAuth UI state and helpers
  const [plexOAuth, setPlexOAuth] = useState({ id: null, url: '', status: 'idle', error: null });
  const oauthPollRef = React.useRef(null);
  // Stable token management (optional advanced)
  const [showStableTokenSave, setShowStableTokenSave] = useState(false);
  const [stableTokenInput, setStableTokenInput] = useState('');
  const [systemVersion, setSystemVersion] = useState(null);
  const [ffmpegInfo, setFfmpegInfo] = useState(null);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [showUpdateBanner, setShowUpdateBanner] = useState(false);
  // Docker Quick Connect UI state
  const [prerollView, setPrerollView] = useState(() => {
    try { return localStorage.getItem('prerollView') || 'grid'; } catch { return 'grid'; }
  });

  // Upload/Import mode for dashboard
  const [uploadMode, setUploadMode] = useState('upload'); // 'upload' or 'import'

  // PWA install state
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  // Path Mappings & External Mapping UI state
  const [pathMappings, setPathMappings] = useState([]);
  const [pathMappingsLoading, setPathMappingsLoading] = useState(false);
  const [mappingTestInput, setMappingTestInput] = useState('');
  const [mappingTestResults, setMappingTestResults] = useState([]);
  const [mapRootForm, setMapRootForm] = useState({
    root_path: '',
    category_id: '',
    recursive: true,
    extensions: 'mp4,mkv,avi,mov',
    generate_thumbnails: true,
    tags: ''
  });
  const [mapRootLoading, setMapRootLoading] = useState(false);
  const [mapRootLoadingMsg, setMapRootLoadingMsg] = useState('');

// Genre mapping UI state
const [genreMaps, setGenreMaps] = useState([]);
const [genreMapsLoading, setGenreMapsLoading] = useState(false);
const [gmForm, setGmForm] = useState({ genre: '', category_id: '' });
const [gmEditing, setGmEditing] = useState(null);
const [genresTestInput, setGenresTestInput] = useState('');
const [genresResolveResult, setGenresResolveResult] = useState(null);
const [genresApplyLoading, setGenresApplyLoading] = useState(false);
const [genreSettings, setGenreSettings] = useState({
genre_auto_apply: true,
genre_priority_mode: 'schedules_override',
genre_override_ttl_seconds: 10
});
const [recentGenreApplications, setRecentGenreApplications] = useState([]);
const [genreSettingsLoading, setGenreSettingsLoading] = useState(false);
  // Category preroll management UI state
  const [categoryPrerolls, setCategoryPrerolls] = useState({});
  const [categoryPrerollsLoading, setCategoryPrerollsLoading] = useState({});
  const [categoryAddSelection, setCategoryAddSelection] = useState({});
// Calendar view state
const [showCalendar, setShowCalendar] = useState(false);
const [calendarMonth, setCalendarMonth] = useState(() => {
  const d = new Date();
  return d.getMonth() + 1; // 1-12
});
const [calendarYear, setCalendarYear] = useState(() => {
  const d = new Date();
  return d.getFullYear();
});
const [calendarMode, setCalendarMode] = useState('month'); // 'month' | 'year'

// Date/time helpers: treat backend datetimes as UTC and format for local display/inputs
const ensureUtcIso = (s) => {
  if (!s || typeof s !== 'string') return s;
  return (s.endsWith('Z') || s.includes('+')) ? s : (s + 'Z');
};
const toLocalInputValue = (isoOrNaive) => {
  if (!isoOrNaive) return '';
  const d = new Date(ensureUtcIso(isoOrNaive));
  const pad = (n) => String(n).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
};
const toLocalDisplay = (isoOrNaive) => {
  if (!isoOrNaive) return 'N/A';
  try {
    const d = new Date(ensureUtcIso(isoOrNaive));
    return d.toLocaleString();
  } catch {
    return isoOrNaive;
  }
};
const toLocalInputFromDate = (d) => {
  if (!d) return '';
  const pad = (n) => String(n).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
};
  // Schedule form state
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    type: 'monthly',
    start_date: '',
    end_date: '',
    category_id: '',
    shuffle: false,
    playlist: false,
    fallback_category_id: ''
  });

  // Upload form state
  const [uploadForm, setUploadForm] = useState({
    tags: '',
    category_id: '',
    category_ids: [],
    description: ''
  });
  const [editForm, setEditForm] = useState({
    display_name: '',
    new_filename: '',
    tags: '',
    category_id: '',
    category_ids: [],
    description: ''
  });

  // Filter state
  const [filterTags, setFilterTags] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [availableTags, setAvailableTags] = useState([]);

  // Preroll pagination and selection
  const [selectedPrerollIds, setSelectedPrerollIds] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => {
    try {
      const v = parseInt(localStorage.getItem('prerollPageSize') || '20', 10);
      return Math.min(50, Math.max(20, isNaN(v) ? 20 : v));
    } catch {
      return 20;
    }
  });
  const [bulkCategoryId, setBulkCategoryId] = useState('');

  // Load theme preference from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('darkMode');
    if (savedTheme) {
      setDarkMode(JSON.parse(savedTheme));
    }
  }, []);

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
    document.body.className = darkMode ? 'dark' : 'light';
  }, [darkMode]);

  useEffect(() => {
    try { localStorage.setItem('prerollView', prerollView); } catch {}
  }, [prerollView]);

  // Persist and clamp preroll pagination
  useEffect(() => {
    try { localStorage.setItem('prerollPageSize', String(pageSize)); } catch {}
  }, [pageSize]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil((prerolls || []).length / pageSize));
    setCurrentPage(prev => Math.min(prev, totalPages));
  }, [prerolls.length, pageSize]);

  useEffect(() => {
    // Reset to first page when filters change
    setCurrentPage(1);
  }, [filterCategory, filterTags]);

  // Ensure tab title always shows "NeXroll" (guards against cached index.html/manifest)
  useEffect(() => {
    try {
      if (document && document.title !== 'NeXroll') {
        document.title = 'NeXroll';
      }
    } catch {}
  }, []);

  // Safe JSON parser to prevent UI breakage if an endpoint returns non-JSON or HTTP 500/HTML
  const safeJson = async (r) => {
    try {
      return await r.json();
    } catch (e) {
      return r && typeof r.status === 'number' ? { __error: true, status: r.status } : {};
    }
  };

  // Version helpers and GitHub update check
  const normalizeVersionString = (input) => {
    try {
      if (!input) return '0.0.0';
      let s = String(input).trim();
      // strip leading "v"
      s = s.replace(/^v+/i, '');
      // treat "-" and "_" as separators
      s = s.replace(/[_-]/g, '.');
      // pick up to 4 numeric segments
      const m = s.match(/(\d+(?:\.\d+){0,3})/);
      return m ? m[1] : '0.0.0';
    } catch {
      return '0.0.0';
    }
  };

  const parseVersion = (v) => {
    const parts = normalizeVersionString(v).split('.').map(n => parseInt(n, 10) || 0);
    while (parts.length < 3) parts.push(0);
    return parts.slice(0, 4);
  };

  const compareVersions = (a, b) => {
    const pa = parseVersion(a);
    const pb = parseVersion(b);
    const len = Math.max(pa.length, pb.length);
    for (let i = 0; i < len; i++) {
      const ai = pa[i] || 0;
      const bi = pb[i] || 0;
      if (ai > bi) return 1;
      if (ai < bi) return -1;
    }
    return 0;
  };

  const extractVersionFromRelease = (data) => {
    const tag = (data && data.tag_name) || '';
    const name = (data && data.name) || '';
    return normalizeVersionString(tag || name);
  };

  const checkForUpdates = async (installedVersion) => {
    try {
      const now = Date.now();
      const lastChecked = parseInt(localStorage.getItem('nx_update_checked_at') || '0', 10);
      let latest = null;

      if (!lastChecked || (now - lastChecked) > (12 * 60 * 60 * 1000)) {
        const res = await fetch('https://api.github.com/repos/JFLXCLOUD/NeXroll/releases/latest', {
          headers: { 'Accept': 'application/vnd.github+json' }
        });
        if (!res.ok) {
          // Fallback: use releases/latest page if API blocked
          latest = {
            version: null,
            url: 'https://github.com/JFLXCLOUD/NeXroll/releases/latest',
            name: 'Latest Release'
          };
        } else {
          const data = await res.json();
          latest = {
            version: extractVersionFromRelease(data),
            url: data.html_url || 'https://github.com/JFLXCLOUD/NeXroll/releases/latest',
            name: data.name || data.tag_name || 'Latest Release'
          };
        }
        localStorage.setItem('nx_latest_release_info', JSON.stringify(latest));
        localStorage.setItem('nx_update_checked_at', String(now));
      } else {
        const cached = localStorage.getItem('nx_latest_release_info');
        latest = cached ? JSON.parse(cached) : null;
      }

      if (latest && latest.version && installedVersion) {
        const dismissed = normalizeVersionString(localStorage.getItem('nx_dismissed_version') || '');
        const cmp = compareVersions(latest.version, installedVersion);
        setUpdateInfo(latest);
        setShowUpdateBanner(cmp > 0 && dismissed !== normalizeVersionString(latest.version));
      } else {
        setShowUpdateBanner(false);
      }
    } catch (e) {
      console.warn('Update check failed:', e);
    }
  };

  const handleDismissUpdate = () => {
    try {
      if (updateInfo && updateInfo.version) {
        localStorage.setItem('nx_dismissed_version', normalizeVersionString(updateInfo.version));
      }
    } catch {}
    setShowUpdateBanner(false);
  };

  const handleInstallPWA = async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;

    console.log('PWA install outcome:', outcome);
    setDeferredPrompt(null);
    setShowInstallPrompt(false);

    if (outcome === 'accepted') {
      setIsInstalled(true);
    }
  };

  const dismissInstallPrompt = () => {
    setShowInstallPrompt(false);
  };
 
  const toggleTheme = () => {
    setDarkMode(!darkMode);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds

    // Live status via Server-Sent Events (SSE)
    let es;
    try {
      es = new EventSource(apiUrl('/events'));
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data && data.scheduler) {
            setSchedulerStatus(prev => ({
              ...prev,
              running: !!data.scheduler.running
            }));
          }
        } catch (e) {
          // ignore parse errors
        }
      };
      // Swallow transient network disconnects; EventSource auto-reconnects.
      es.onerror = () => {};
    } catch (e) {
      // SSE not available
    }

    return () => {
      clearInterval(interval);
      try { es && es.close(); } catch {}
    };
  }, []);

  // Check GitHub for latest release once system version is known
  useEffect(() => {
    if (!systemVersion) return;
    const installed = normalizeVersionString(
      (systemVersion.registry_version || systemVersion.api_version || '').toString()
    );
    checkForUpdates(installed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [systemVersion]);

  // PWA install prompt handling
  useEffect(() => {
    // Check if already installed
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    const isInWebAppiOS = window.navigator.standalone === true;
    setIsInstalled(isStandalone || isInWebAppiOS);

    // Listen for the beforeinstallprompt event
    const handleBeforeInstallPrompt = (e) => {
      console.log('PWA install prompt available');
      e.preventDefault();
      setDeferredPrompt(e);
      setShowInstallPrompt(true);
    };

    // Listen for successful installation
    const handleAppInstalled = () => {
      console.log('PWA was installed');
      setDeferredPrompt(null);
      setShowInstallPrompt(false);
      setIsInstalled(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);
 
  const fetchData = () => {
    // Fetch all data
    Promise.all([
      fetch('http://localhost:9393/plex/status'),
      fetch(`http://localhost:9393/prerolls?category_id=${filterCategory}&tags=${filterTags}`),
      fetch('http://localhost:9393/schedules'),
      fetch('http://localhost:9393/categories'),
      fetch('http://localhost:9393/holiday-presets'),
      fetch('http://localhost:9393/scheduler/status'),
      fetch('http://localhost:9393/tags'),
      fetch('http://localhost:9393/community-templates'),
      fetch('http://localhost:9393/plex/stable-token/status'),
      fetch('http://localhost:9393/system/version'),
      fetch('http://localhost:9393/system/ffmpeg-info'),
      fetch('http://localhost:9393/genres/recent-applications')
    ]).then(responses => Promise.all(responses.map(safeJson)))
      .then(([plex, prerolls, schedules, categories, holidays, scheduler, tags, templates, stableToken, sysVersion, ffmpeg, recentGenreApps]) => {
        setPlexStatus(plex.connected ? 'Connected' : 'Disconnected');
        setPlexServerInfo(plex);
        setPrerolls(Array.isArray(prerolls) ? prerolls : []);
        setSchedules(Array.isArray(schedules) ? schedules : []);
        setCategories(Array.isArray(categories) ? categories : []);
        setHolidayPresets(Array.isArray(holidays) ? holidays : []);
        setSchedulerStatus(scheduler || { running: false, active_schedules: 0 });
        setAvailableTags(Array.isArray(tags?.tags) ? tags.tags : []);
        setCommunityTemplates(Array.isArray(templates) ? templates : []);
        setStableTokenStatus(stableToken || {
          has_stable_token: false,
          config_file_exists: false,
          token_length: 0
        });
        setSystemVersion(sysVersion || null);
        setFfmpegInfo(ffmpeg || null);
        setRecentGenreApplications(Array.isArray(recentGenreApps?.applications) ? recentGenreApps.applications : []);
      }).catch(err => {
        console.error('Fetch error:', err);
        // Set default values on error
        setPrerolls([]);
        setSchedules([]);
        setCategories([]);
        setHolidayPresets([]);
        setSchedulerStatus({ running: false, active_schedules: 0 });
        setAvailableTags([]);
        setCommunityTemplates([]);
        setStableTokenStatus({
          has_stable_token: false,
          config_file_exists: false,
          token_length: 0
        });
        setSystemVersion(null);
        setFfmpegInfo(null);
        setRecentGenreApplications([]);
      });
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select files to upload');
      return;
    }

    const totalFiles = files.length;
    const results = [];

    // Reset progress
    setUploadProgress({});

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const formData = new FormData();
        formData.append('file', file);
        if (uploadForm.tags.trim()) formData.append('tags', uploadForm.tags.trim());
        if (uploadForm.category_id) formData.append('category_id', uploadForm.category_id);
        if (uploadForm.category_ids && uploadForm.category_ids.length > 0) {
          const ids = uploadForm.category_ids.map(id => parseInt(id)).filter(n => !isNaN(n));
          if (ids.length > 0) formData.append('category_ids', JSON.stringify(ids));
        }
        if (uploadForm.description.trim()) formData.append('description', uploadForm.description.trim());

        const response = await fetch('http://localhost:9393/prerolls/upload', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        results.push({ file: file.name, success: true, data });

        // Update progress
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: { status: 'completed', progress: 100 }
        }));

      } catch (error) {
        console.error(`Upload error for ${file.name}:`, error);
        results.push({ file: file.name, success: false, error: error.message });

        // Update progress with error
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: { status: 'error', progress: 0, error: error.message }
        }));
      }
    }

    // Show summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    if (failed === 0) {
      alert(`All ${totalFiles} files uploaded successfully!`);
    } else if (successful === 0) {
      alert(`Failed to upload any files. Please check the errors.`);
    } else {
      alert(`${successful} files uploaded successfully, ${failed} failed.`);
    }

    // Clear files and form
    setFiles([]);
    setUploadForm({ tags: '', category_id: '', category_ids: [], description: '' });
    fetchData();
  };

  const handleCreateSchedule = (e) => {
    e.preventDefault();

    // Validate required fields
    if (!scheduleForm.name.trim()) {
      alert('Schedule name is required');
      return;
    }
    if (!scheduleForm.start_date) {
      alert('Start date is required');
      return;
    }
    if (!scheduleForm.category_id) {
      alert('Please select a category');
      return;
    }

    // Ensure category_id is valid
    const categoryId = parseInt(scheduleForm.category_id);
    if (isNaN(categoryId) || categoryId <= 0) {
      alert('Please select a valid category');
      return;
    }

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      end_date: scheduleForm.end_date || null,
      category_id: categoryId,
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist
    };
    if (scheduleForm.fallback_category_id) {
      scheduleData.fallback_category_id = parseInt(scheduleForm.fallback_category_id);
    }

    fetch('http://localhost:9393/schedules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(res => {
        if (!res.ok) {
          return res.text().then(text => {
            throw new Error(`HTTP ${res.status}: ${text}`);
          });
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule created successfully!');
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: false, playlist: false
        });
        // Add the new schedule to the state immediately with category info
        if (data.category) {
          setSchedules(prev => [...prev, data]);
        } else {
          // If no category in response, refresh data
          fetchData();
        }
      })
      .catch(error => {
        console.error('Schedule creation error:', error);
        alert('Failed to create schedule: ' + error.message);
      });
  };


  const handleInitHolidays = () => {
    fetch('http://localhost:9393/holiday-presets/init', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert('Holiday presets initialized!');
        fetchData();
      });
  };

  const handleApplyCategoryToPlex = (categoryId, categoryName) => {
    const message = `Apply category "${categoryName}" to Plex?\n\nThis will send ALL prerolls from this category to Plex.`;
    if (window.confirm(message)) {
      fetch(`http://localhost:9393/categories/${categoryId}/apply-to-plex`, { method: 'POST' })
        .then(res => {
          if (!res.ok) {
            return res.json().then(err => {
              throw new Error(err.detail || 'Failed to apply category to Plex');
            });
          }
          return res.json();
        })
        .then(data => {
          let successMessage = `Category applied to Plex!\n\nPrerolls applied (${data.preroll_count} total):`;
          if (data.prerolls && data.prerolls.length > 0) {
            data.prerolls.forEach((preroll, index) => {
              successMessage += `\n${index + 1}. ${preroll}`;
            });
          }
          if (data.rotation_info) {
            // rotation_info removed from UI per feedback
          }
          alert(successMessage);
          fetchData();
        })
        .catch(error => {
          alert('Failed to apply category to Plex: ' + error.message);
        });
    }
  };


  const handleRemoveCategoryFromPlex = (categoryId, categoryName) => {
    if (window.confirm(`Remove category "${categoryName}" from Plex?`)) {
      fetch(`http://localhost:9393/categories/${categoryId}/remove-from-plex`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          alert('Category removed from Plex!');
          fetchData();
        })
        .catch(error => {
          alert('Failed to remove category from Plex: ' + error.message);
        });
    }
  };

  const toggleScheduler = () => {
    const action = schedulerStatus.running ? 'stop' : 'start';
    fetch(`http://localhost:9393/scheduler/${action}`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert(`Scheduler ${action}ed!`);
        fetchData();
      });
  };

  const handleBackupDatabase = () => {
    fetch('http://localhost:9393/backup/database')
      .then(res => res.json())
      .then(data => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `nexroll_backup_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        alert('Database backup downloaded!');
      })
      .catch(error => {
        console.error('Backup error:', error);
        alert('Backup failed: ' + error.message);
      });
  };

  const handleBackupFiles = () => {
    fetch('http://localhost:9393/backup/files', {
      method: 'POST'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        // Convert base64 or binary data to blob
        const blob = new Blob([new Uint8Array(data.content)], { type: data.content_type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        alert('Files backup downloaded!');
      })
      .catch(error => {
        console.error('File backup error:', error);
        alert('File backup failed: ' + error.message);
      });
  };

  const handleRestoreDatabase = () => {
    if (!backupFile) {
      alert('Please select a backup file first');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const backupData = JSON.parse(e.target.result);
        fetch('http://localhost:9393/restore/database', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(backupData)
        })
          .then(res => res.json())
          .then(data => {
            alert('Database restored successfully!');
            setBackupFile(null);
            fetchData();
          })
          .catch(error => {
            console.error('Restore error:', error);
            alert('Restore failed: ' + error.message);
          });
      } catch (error) {
        alert('Invalid backup file format');
      }
    };
    reader.readAsText(backupFile);
  };

  const handleRestoreFiles = () => {
    if (!backupFile) {
      alert('Please select a ZIP file first');
      return;
    }

    const formData = new FormData();
    formData.append('file', backupFile);
    fetch('http://localhost:9393/restore/files', {
      method: 'POST',
      body: formData
    })
      .then(res => res.json())
      .then(data => {
        alert('Files restored successfully!');
        setBackupFile(null);
      })
      .catch(error => {
        console.error('File restore error:', error);
        alert('File restore failed: ' + error.message);
      });
  };

  const handleInitTemplates = () => {
    fetch('http://localhost:9393/community-templates/init', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert('Community templates initialized!');
        fetchData();
      })
      .catch(error => {
        console.error('Template init error:', error);
        alert('Failed to initialize templates: ' + error.message);
      });
  };

  const handleImportTemplate = (templateId) => {
    fetch(`http://localhost:9393/community-templates/${templateId}/import`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert(`Template imported! ${data.imported_schedules} schedules created.`);
        fetchData();
      })
      .catch(error => {
        console.error('Template import error:', error);
        alert('Failed to import template: ' + error.message);
      });
  };

  const handleCreateTemplate = () => {
    if (selectedSchedules.length === 0) {
      alert('Please select at least one schedule to create a template');
      return;
    }

    const templateName = prompt('Enter template name:');
    if (!templateName) return;

    const templateDescription = prompt('Enter template description:');
    const templateCategory = prompt('Enter template category (e.g., Holiday, Seasonal, Custom):', 'Custom');

    const templateData = {
      name: templateName,
      description: templateDescription || '',
      author: 'NeXroll User',
      category: templateCategory || 'Custom',
      schedule_ids: JSON.stringify(selectedSchedules),
      tags: JSON.stringify(['user-created'])
    };

    fetch('http://localhost:9393/community-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(templateData)
    })
      .then(res => res.json())
      .then(data => {
        alert('Template created successfully!');
        setSelectedSchedules([]);
        fetchData();
      })
      .catch(error => {
        console.error('Template creation error:', error);
        alert('Failed to create template: ' + error.message);
      });
  };

  const handleDeleteSchedule = (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return;

    fetch(`http://localhost:9393/schedules/${scheduleId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete schedule error:', error);
        alert('Failed to delete schedule: ' + error.message);
      });
  };

  const handleEditSchedule = (schedule) => {
    setEditingSchedule(schedule);
    setScheduleForm({
      name: schedule.name,
      type: schedule.type,
      start_date: toLocalInputValue(schedule.start_date),
      end_date: toLocalInputValue(schedule.end_date),
      category_id: schedule.category_id || '',
      shuffle: schedule.shuffle,
      playlist: schedule.playlist,
      fallback_category_id: schedule.fallback_category_id || ''
    });
 };

  const handleUpdateSchedule = (e) => {
    e.preventDefault();
    if (!editingSchedule) return;

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      end_date: scheduleForm.end_date || null,
      category_id: parseInt(scheduleForm.category_id),
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist
    };
    if (scheduleForm.fallback_category_id) {
      scheduleData.fallback_category_id = parseInt(scheduleForm.fallback_category_id);
    }

    fetch(`http://localhost:9393/schedules/${editingSchedule.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule updated successfully!');
        setEditingSchedule(null);
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: false, playlist: false
        });
        fetchData();
      })
      .catch(error => {
        console.error('Update schedule error:', error);
        alert('Failed to update schedule: ' + error.message);
      });
  };

  const handleDeletePreroll = (prerollId) => {
    if (!window.confirm('Are you sure you want to delete this preroll?')) return;

    fetch(`http://localhost:9393/prerolls/${prerollId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Preroll deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete preroll error:', error);
        alert('Failed to delete preroll: ' + error.message);
      });
  };

  const handleEditPreroll = (preroll) => {
    setEditingPreroll(preroll);
    let tagsStr = '';
    try {
      if (preroll.tags) {
        const t = typeof preroll.tags === 'string' ? JSON.parse(preroll.tags) : preroll.tags;
        if (Array.isArray(t)) tagsStr = t.join(', ');
        else if (typeof preroll.tags === 'string') tagsStr = preroll.tags;
      }
    } catch {
      tagsStr = typeof preroll.tags === 'string' ? preroll.tags : '';
    }
    const primaryId = preroll.category_id || (preroll.category?.id || '');
    const assocIds = Array.isArray(preroll.categories) ? preroll.categories.map(c => String(c.id)) : [];
    setEditForm({
      display_name: preroll.display_name || '',
      new_filename: '',
      tags: tagsStr,
      category_id: primaryId ? String(primaryId) : '',
      category_ids: assocIds,
      description: preroll.description || ''
    });
  };

  const handleUpdatePreroll = (e) => {
    e.preventDefault();
    if (!editingPreroll) return;

    const payload = {};
    if (editForm.tags && editForm.tags.trim()) payload.tags = editForm.tags.trim();
    if (editForm.category_id) payload.category_id = parseInt(editForm.category_id);
    if (editForm.category_ids && editForm.category_ids.length > 0) {
      payload.category_ids = editForm.category_ids.map(id => parseInt(id)).filter(n => !isNaN(n));
    }
    if (editForm.description && editForm.description.trim()) payload.description = editForm.description.trim();
    if (typeof editForm.display_name === 'string') payload.display_name = editForm.display_name.trim();
    if (editForm.new_filename && editForm.new_filename.trim()) payload.new_filename = editForm.new_filename.trim();

    fetch(`http://localhost:9393/prerolls/${editingPreroll.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(() => {
        alert('Preroll updated successfully!');
        setEditingPreroll(null);
        setEditForm({ display_name: '', new_filename: '', tags: '', category_id: '', category_ids: [], description: '' });
        fetchData();
      })
      .catch(error => {
        console.error('Update preroll error:', error);
        alert('Failed to update preroll: ' + error.message);
      });
  };

  const handleDeleteCategory = (categoryId) => {
    if (!window.confirm('Are you sure you want to delete this category? This may affect associated schedules and prerolls.')) return;

    fetch(`http://localhost:9393/categories/${categoryId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Category deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete category error:', error);
        alert('Failed to delete category: ' + error.message);
      });
  };

  const handleEditCategory = (category) => {
    setEditingCategory(category);
    setNewCategory({ name: category.name, description: category.description || '', plex_mode: (category.plex_mode || 'shuffle') });
    try { loadCategoryPrerolls(category.id); } catch (e) {}
  };

  const handleUpdateCategory = async (e) => {
    e.preventDefault();
    if (!editingCategory) return;

    const name = (newCategory.name || '').trim();
    const description = (newCategory.description || '').trim();
    if (!name) {
      alert('Category name is required');
      return;
    }

    try {
      const res = await fetch(`http://localhost:9393/categories/${editingCategory.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, plex_mode: newCategory.plex_mode || 'shuffle' })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}

      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }

      alert('Category updated successfully!');
      setEditingCategory(null);
      setNewCategory({ name: '', description: '' });

      if (data && data.id) {
        setCategories(prev => prev.map(c => c.id === data.id ? data : c));
      } else {
        fetchData();
      }
    } catch (error) {
      console.error('Update category error:', error);
      alert(error.message.includes('already exists') ? 'Category name already exists' : 'Failed to update category: ' + error.message);
    }
  };

  const handleUpdateCategoryAndApply = async (e) => {
    e.preventDefault();
    if (!editingCategory) return;

    const name = (newCategory.name || '').trim();
    const description = (newCategory.description || '').trim();
    if (!name) {
      alert('Category name is required');
      return;
    }

    try {
      const res = await fetch(`http://localhost:9393/categories/${editingCategory.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, plex_mode: newCategory.plex_mode || 'shuffle' })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}

      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }

      if (data && data.id) {
        setCategories(prev => prev.map(c => (c.id === data.id ? data : c)));
      }

      const idToApply = (data && data.id) || editingCategory.id;
      const nameToApply = (data && data.name) || name;
      const resApply = await fetch(`http://localhost:9393/categories/${idToApply}/apply-to-plex`, { method: 'POST' });
      const applyText = await resApply.text();
      let applyData = null;
      try { applyData = applyText ? JSON.parse(applyText) : null; } catch {}

      if (!resApply.ok) {
        const msg = (applyData && (applyData.detail || applyData.message)) || applyText || `HTTP ${resApply.status}`;
        throw new Error(`Saved but failed to apply to Plex: ${msg}`);
      }

      alert(`Saved and applied "${nameToApply}" to Plex!`);
      setEditingCategory(null);
      setNewCategory({ name: '', description: '' });
      fetchData();
    } catch (error) {
      console.error('Save & Apply category error:', error);
      alert(error.message || 'Failed to save/apply category');
    }
  };

  // Category preroll management helpers

  const loadCategoryPrerolls = async (categoryId) => {
    setCategoryPrerollsLoading(prev => ({ ...prev, [categoryId]: true }));
    try {
      const res = await fetch(`http://localhost:9393/categories/${categoryId}/prerolls`);
      const data = await safeJson(res);
      setCategoryPrerolls(prev => ({ ...prev, [categoryId]: Array.isArray(data) ? data : [] }));
    } catch (e) {
      console.error('Load category prerolls error:', e);
      setCategoryPrerolls(prev => ({ ...prev, [categoryId]: [] }));
    } finally {
      setCategoryPrerollsLoading(prev => ({ ...prev, [categoryId]: false }));
    }
  };


  const handleCategoryRemovePreroll = async (categoryId, preroll) => {
    if (!preroll) return;
    if (preroll.category_id === categoryId) {
      alert('Cannot remove the primary category here. Use "Edit Preroll" to change the primary category.');
      return;
    }
    if (!window.confirm(`Remove "${preroll.display_name || preroll.filename}" from this category?`)) return;
    try {
      const res = await fetch(`http://localhost:9393/categories/${categoryId}/prerolls/${preroll.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setCategoryPrerolls(prev => ({
        ...prev,
        [categoryId]: (prev[categoryId] || []).filter(p => p.id !== preroll.id)
      }));
      fetchData();
    } catch (e) {
      console.error('Remove preroll from category error:', e);
      alert('Failed to remove preroll from category: ' + e.message);
    }
  };

  const handleCategoryAddPreroll = async (categoryId) => {
    const sel = categoryAddSelection[categoryId] || {};
    const prerollId = sel.prerollId || '';
    if (!prerollId) {
      alert('Please select a preroll to add');
      return;
    }
    try {
      const res = await fetch(`http://localhost:9393/categories/${categoryId}/prerolls/${prerollId}?set_primary=${sel.setPrimary ? 'true' : 'false'}`, { method: 'POST' });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      await res.json().catch(() => null);
      setCategoryAddSelection(prev => ({ ...prev, [categoryId]: { prerollId: '', setPrimary: false } }));
      loadCategoryPrerolls(categoryId);
      fetchData();
      alert(`Preroll added to category${sel.setPrimary ? ' and set as primary' : ''}!`);
    } catch (e) {
      console.error('Add preroll to category error:', e);
      alert('Failed to add preroll to category: ' + e.message);
    }
  };

  const availablePrerollsForCategory = (categoryId) => {
    const assigned = new Set((categoryPrerolls[categoryId] || []).map(p => p.id));
    return prerolls.filter(p => !assigned.has(p.id));
  };

  // UI helpers and derived values for prerolls list
  const formatBytes = (bytes) => {
    const b = Number(bytes) || 0;
    if (b <= 0) return '0 B';
    const units = ['B','KB','MB','GB','TB','PB'];
    const i = Math.floor(Math.log(b) / Math.log(1024));
    const val = b / Math.pow(1024, i);
    const prec = i === 0 ? 0 : (val >= 100 ? 0 : val >= 10 ? 1 : 2);
    return `${val.toFixed(prec)} ${units[i]}`;
  };
  const totalStorageBytes = prerolls.reduce((sum, p) => sum + (Number(p.file_size) || 0), 0);

  const totalPrerolls = prerolls.length;
  const totalPages = Math.max(1, Math.ceil(totalPrerolls / pageSize));
  const currentPageClamped = Math.min(currentPage, totalPages);
  const pageStartIndex = (currentPageClamped - 1) * pageSize;
  const pageEndIndex = Math.min(pageStartIndex + pageSize, totalPrerolls);
  const visiblePrerolls = prerolls.slice(pageStartIndex, pageEndIndex);
  const visibleIds = visiblePrerolls.map(p => p.id);
  const allSelectedOnPage = visibleIds.length > 0 && visibleIds.every(id => selectedPrerollIds.includes(id));

  const toggleSelectPreroll = (id) => {
    setSelectedPrerollIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };
  const selectAllVisible = (ids, checked) => {
    setSelectedPrerollIds(prev => {
      const set = new Set(prev);
      if (checked) {
        ids.forEach(id => set.add(id));
      } else {
        ids.forEach(id => set.delete(id));
      }
      return Array.from(set);
    });
  };
  const clearSelection = () => setSelectedPrerollIds([]);

  const handleBulkSetPrimary = async (categoryId) => {
    const cid = parseInt(categoryId, 10);
    if (!cid || isNaN(cid)) { alert('Select a target category'); return; }
    if (selectedPrerollIds.length === 0) { alert('No prerolls selected'); return; }
    if (!window.confirm(`Change primary category for ${selectedPrerollIds.length} preroll(s)? This will move files on disk.`)) return;
    let ok = 0, fail = 0;
    for (const id of selectedPrerollIds) {
      try {
        const res = await fetch(`http://localhost:9393/prerolls/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category_id: cid })
        });
        if (!res.ok) fail++; else ok++;
      } catch { fail++; }
    }
    alert(`Primary category updated. Success: ${ok}, Failed: ${fail}`);
    setSelectedPrerollIds([]);
    setBulkCategoryId('');
    fetchData();
  };

  const handleBulkDeleteSelected = async () => {
    const count = selectedPrerollIds.length;
    if (count === 0) { alert('No prerolls selected'); return; }
    if (!window.confirm(`Delete ${count} selected preroll(s)?\n\nManaged files may be deleted from disk. External mapped files are protected and will not be removed.`)) return;
    let ok = 0, fail = 0;
    for (const id of selectedPrerollIds) {
      try {
        const res = await fetch(`http://localhost:9393/prerolls/${id}`, { method: 'DELETE' });
        if (!res.ok) fail++; else ok++;
      } catch {
        fail++;
      }
    }
    alert(`Delete completed. Success: ${ok}, Failed: ${fail}`);
    setSelectedPrerollIds([]);
    fetchData();
  };

  const createCategoryInline = async (name) => {
    const n = String(name || '').trim();
    if (!n) return null;
    try {
      const res = await fetch('http://localhost:9393/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: n, description: '', plex_mode: 'shuffle' })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }
      if (data && data.id) {
        setCategories(prev => prev.some(c => c.id === data.id) ? prev : [...prev, data]);
      }
      return data;
    } catch (err) {
      alert('Failed to create category: ' + (err && err.message ? err.message : err));
      return null;
    }
  };

  const renderDashboard = () => (
    <div>
      <h1 className="header">NeXroll Dashboard</h1>

 
      <div className="grid">
        <div className="card">
          <h2>Plex Status</h2>
          <p style={{ color: plexStatus === 'Connected' ? 'var(--success-color, #28a745)' : 'var(--error-color, #dc3545)' }}>
            {plexStatus}
            {plexServerInfo?.name && (
              <span style={{ fontSize: '0.9rem', marginLeft: '0.5rem', color: 'var(--text-color)' }}>
                - {plexServerInfo.name}
              </span>
            )}
          </p>
          {plexServerInfo && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #666)', marginTop: '0.5rem' }}>
              <div>Version: {plexServerInfo.version}</div>
              <div>Platform: {plexServerInfo.platform}</div>
            </div>
          )}
        </div>
        <div className="card">
          <h2>Prerolls</h2>
          <p>{prerolls.length} uploaded</p>
          <button onClick={handleReinitThumbnails} className="button" style={{ marginTop: '0.5rem' }}>
            🔄 Reinitialize Thumbnails
          </button>
        </div>
        <div className="card">
          <h2>Storage</h2>
          <p>{formatBytes(totalStorageBytes)} used</p>
        </div>
        <div className="card">
          <h2>Schedules</h2>
          <p>{schedules.length} active</p>
        </div>
        <div className="card">
          <h2>Scheduler</h2>
          <p style={{ color: schedulerStatus.running ? 'green' : 'red' }}>
            {schedulerStatus.running ? 'Running' : 'Stopped'}
          </p>
          <button onClick={toggleScheduler} className="button" style={{ marginTop: '0.5rem' }}>
            {schedulerStatus.running ? 'Stop' : 'Start'} Scheduler
          </button>
        </div>

        {recentGenreApplications.length > 0 && (
          <div className="card">
            <h2>Recent Genre Prerolls</h2>
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              {recentGenreApplications.map((app, idx) => (
                <div key={idx} style={{ fontSize: '0.9rem', padding: '0.5rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                  <div style={{ fontWeight: 'bold', color: '#28a745' }}>
                    {app.genre} → {app.category_name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.25rem' }}>
                    {new Date(app.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="upload-section">
        <h2>Add Prerolls</h2>

        {/* Tab buttons for Upload vs Import */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          <button
            type="button"
            className={`button ${uploadMode === 'upload' ? '' : 'button-secondary'}`}
            onClick={() => setUploadMode('upload')}
            style={{ flex: 1 }}
          >
            📤 Upload Files
          </button>
          <button
            type="button"
            className={`button ${uploadMode === 'import' ? '' : 'button-secondary'}`}
            onClick={() => setUploadMode('import')}
            style={{ flex: 1 }}
          >
            📁 Import Folder
          </button>
        </div>

        {uploadMode === 'upload' && (
          <form onSubmit={handleUpload}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <input
                type="file"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files))}
                accept="video/*"
                required
                className="nx-input"
              />
              {files.length > 0 && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#666' }}>
                  {files.length} file{files.length !== 1 ? 's' : ''} selected
                  <ul style={{ marginTop: '0.25rem', paddingLeft: '1rem' }}>
                    {files.map((file, index) => (
                      <li key={index} style={{ fontSize: '0.8rem' }}>
                        {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                        {uploadProgress[file.name] && (
                          <span style={{
                            marginLeft: '0.5rem',
                            color: uploadProgress[file.name].status === 'completed' ? 'green' :
                                  uploadProgress[file.name].status === 'error' ? 'red' : '#666'
                          }}>
                            {uploadProgress[file.name].status === 'completed' ? '✓' :
                             uploadProgress[file.name].status === 'error' ? '✗' : '...'}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <input
                type="text"
                placeholder="Tags (comma separated)"
                value={uploadForm.tags}
                onChange={(e) => setUploadForm({...uploadForm, tags: e.target.value})}
                className="nx-input"
              />
              <CategoryPicker
                categories={categories}
                primaryId={uploadForm.category_id}
                secondaryIds={uploadForm.category_ids}
                onChange={(primary, secondary) => setUploadForm({ ...uploadForm, category_id: primary, category_ids: secondary })}
                onCreateCategory={createCategoryInline}
                label="Categories"
                placeholder="Search categories…"
              />
              <textarea
                placeholder="Description (Optional)"
                value={uploadForm.description}
                onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                rows="3"
                style={{ padding: '0.5rem', resize: 'vertical' }}
              />
            </div>
            <button type="submit" className="button" disabled={files.length === 0}>
              Upload {files.length > 0 ? `${files.length} Preroll${files.length !== 1 ? 's' : ''}` : 'Prerolls'}
            </button>
          </form>
        )}

        {uploadMode === 'import' && (
          <div>
            <p style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>
              Index files from an existing folder into NeXroll without moving them on disk. These files are marked as external (managed=false).
            </p>
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              <input
                type="text"
                placeholder="Root path (e.g., C:\\Prerolls or \\\\NAS\\share\\prerolls)"
                value={mapRootForm.root_path}
                onChange={(e) => setMapRootForm({ ...mapRootForm, root_path: e.target.value })}
                disabled={mapRootLoading}
                style={{ padding: '0.5rem' }}
              />
              <select
                value={mapRootForm.category_id}
                onChange={(e) => setMapRootForm({ ...mapRootForm, category_id: e.target.value })}
                className="nx-select"
                disabled={mapRootLoading}
                style={{ padding: '0.5rem' }}
              >
                <option value="">Select Category</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={!!mapRootForm.recursive}
                    onChange={(e) => setMapRootForm({ ...mapRootForm, recursive: e.target.checked })}
                    disabled={mapRootLoading}
                  />
                  Recurse subfolders
                </label>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={!!mapRootForm.generate_thumbnails}
                    onChange={(e) => setMapRootForm({ ...mapRootForm, generate_thumbnails: e.target.checked })}
                    disabled={mapRootLoading}
                  />
                  Generate thumbnails
                </label>
              </div>
              <input
                type="text"
                placeholder="Extensions (comma-separated, no dots) e.g., mp4,mkv,avi,mov"
                value={mapRootForm.extensions}
                onChange={(e) => setMapRootForm({ ...mapRootForm, extensions: e.target.value })}
                disabled={mapRootLoading}
                style={{ padding: '0.5rem' }}
              />
              <input
                type="text"
                placeholder="Tags (optional, comma-separated)"
                value={mapRootForm.tags}
                onChange={(e) => setMapRootForm({ ...mapRootForm, tags: e.target.value })}
                disabled={mapRootLoading}
                style={{ padding: '0.5rem' }}
              />
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button type="button" className="button" onClick={() => submitMapRoot(false)} disabled={mapRootLoading}>🧪 Dry Run</button>
                <button type="button" className="button" onClick={() => submitMapRoot(true)} disabled={mapRootLoading} style={{ backgroundColor: '#28a745' }}>
                  📥 Import Now
                </button>
              </div>
              {mapRootLoading && (
                <div className="nx-map-progress" style={{ marginTop: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span className="nx-spinner" aria-hidden="true"></span>
                    <span style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
                      {mapRootLoadingMsg || 'Working…'}
                    </span>
                  </div>
                  <div className="nx-progress"><div className="bar"></div></div>
                </div>
              )}
            </div>
            <div className="nx-help" style={{ marginTop: '0.75rem', padding: '0.75rem', border: '1px dashed var(--border-color)', borderRadius: '6px', background: 'var(--card-bg)' }}>
              <h3 style={{ margin: 0, marginBottom: '0.5rem' }}>Docker/NAS guidance</h3>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                <li>If NeXroll runs in Docker, the container cannot see Windows mapped drives or UNC paths by default. Mount your NAS/host folder into the container and use the container path in "Root path".</li>
                <li>UNC paths like \\NAS\share aren't usable inside Linux containers. Mount the SMB share on the host (e.g., /mnt/nas) and map it into the container.</li>
                <li>If Plex runs on Windows, ensure Plex can access the same media folder via a Windows path (e.g., <code>Z:\Prerolls</code> or <code>\\NAS\share\Prerolls</code>). Then add a path mapping from the NeXroll path (e.g., <code>/data/prerolls</code> in Docker or a local/UNC path on Windows) to that Windows path so NeXroll sends Plex a reachable path.</li>
                <li>Example docker run: <code>docker run -d --name nexroll -p 9393:9393 -v /mnt/nas/prerolls:/nas/prerolls jbrns/nexroll:latest</code> → then use <code>/nas/prerolls</code> as the Root path.</li>
                <li>docker-compose example:</li>
              </ul>
              <pre className="nx-code" style={{ whiteSpace: 'pre-wrap', marginTop: '0.5rem' }}>
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:latest
    ports:
      - "9393:9393"
    volumes:
      - /mnt/nas/prerolls:/nas/prerolls
              </pre>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>
                Tip: Use the "UNC/Local → Plex Path Mappings" section in Settings to translate your local or container paths (e.g., <code>/nas/prerolls</code> or <code>\\NAS\share\prerolls</code>) into the Plex-visible mount on your Plex host (e.g., <code>/mnt/prerolls</code>).
              </div>
            </div>
          </div>
        )}
      </div>

      {editingPreroll && (
        <Modal
          title="Edit Preroll"
          onClose={() => { setEditingPreroll(null); setEditForm({ display_name: '', new_filename: '', tags: '', category_id: '', category_ids: [], description: '' }); }}
        >
          <form onSubmit={handleUpdatePreroll}>
            <div className="nx-form-grid">
              <div className="nx-field">
                <label className="nx-label">Display Name</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Optional friendly name"
                  value={editForm.display_name}
                  onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">New File Name</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Optional rename on disk (extension optional)"
                  value={editForm.new_filename}
                  onChange={(e) => setEditForm({ ...editForm, new_filename: e.target.value })}
                />
              </div>
              <div className="nx-field nx-span-2">
                <CategoryPicker
                  categories={categories}
                  primaryId={editForm.category_id}
                  secondaryIds={editForm.category_ids}
                  onChange={(primary, secondary) => setEditForm({ ...editForm, category_id: primary, category_ids: secondary })}
                  onCreateCategory={createCategoryInline}
                  label="Categories"
                  placeholder="Search categories…"
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">Tags</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Comma separated"
                  value={editForm.tags}
                  onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                />
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">Description</label>
                <textarea
                  className="nx-textarea"
                  placeholder="Optional details"
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  rows="4"
                />
              </div>
            </div>
            <div className="nx-actions">
              <button type="submit" className="button">Save Changes</button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => { setEditingPreroll(null); setEditForm({ display_name: '', new_filename: '', tags: '', category_id: '', category_ids: [], description: '' }); }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
      <div className="card">
        <h2>Prerolls</h2>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <button
            type="button"
            className="button"
            onClick={() => setPrerollView('grid')}
            style={{ backgroundColor: prerollView === 'grid' ? '#28a745' : '#6c757d' }}
          >
            Grid
          </button>
          <button
            type="button"
            className="button"
            onClick={() => setPrerollView('list')}
            style={{ backgroundColor: prerollView === 'list' ? '#28a745' : '#6c757d' }}
          >
            List
          </button>
        </div>

        {/* Filter + Pagination Controls */}
        <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            style={{ padding: '0.5rem' }}
          >
            <option value="">All Categories</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter by tags"
            value={filterTags}
            onChange={(e) => setFilterTags(e.target.value)}
            className="nx-input"
          />
          <button
            onClick={() => { setCurrentPage(1); fetchData(); }}
            className="button"
            style={{ padding: '0.5rem 1rem' }}
          >
            Filter
          </button>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
              Per page:
              <select
                value={pageSize}
                onChange={(e) => { const v = parseInt(e.target.value, 10); setPageSize(v); setCurrentPage(1); }}
                className="nx-select"
                style={{ marginLeft: '0.5rem' }}
              >
                {[20, 30, 40, 50].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
        </div>

        {/* Selection + Bulk Actions */}
        <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="checkbox"
              checked={allSelectedOnPage}
              onChange={(e) => selectAllVisible(visibleIds, e.target.checked)}
            />
            Select all on page
          </label>
          <button
            type="button"
            className="button-secondary"
            onClick={clearSelection}
            disabled={selectedPrerollIds.length === 0}
            title="Clear selected prerolls"
          >
            Clear selection
          </button>
          <span style={{ fontSize: '0.9rem', color: '#666' }}>Selected: {selectedPrerollIds.length}</span>
          <button
            type="button"
            className="button"
            onClick={handleBulkDeleteSelected}
            disabled={selectedPrerollIds.length === 0}
            style={{ backgroundColor: '#dc3545' }}
            title="Delete all selected prerolls"
          >
            Delete Selected
          </button>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select
              className="nx-select"
              value={bulkCategoryId}
              onChange={(e) => setBulkCategoryId(e.target.value)}
              style={{ minWidth: 200 }}
            >
              <option value="">Set Primary Category…</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
            <button
              type="button"
              className="button"
              onClick={() => handleBulkSetPrimary(bulkCategoryId)}
              disabled={!bulkCategoryId || selectedPrerollIds.length === 0}
              title="Change primary category for all selected prerolls"
            >
              Apply to Selected
            </button>
          </div>
        </div>

        {/* Available Tags */}
        {availableTags.length > 0 && (
          <div style={{ marginBottom: '1rem' }}>
            <p style={{ fontSize: '0.9rem', color: '#666' }}>Available tags: {availableTags.join(', ')}</p>
          </div>
        )}

        <div className="preroll-grid" style={{ display: prerollView === 'grid' ? 'grid' : 'none' }}>
          {visiblePrerolls.map(preroll => (
            <div key={preroll.id} className="preroll-item">
              <div className="preroll-header" style={{ marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                  <input
                    type="checkbox"
                    checked={selectedPrerollIds.includes(preroll.id)}
                    onChange={() => toggleSelectPreroll(preroll.id)}
                    title="Select preroll"
                  />
                  <p className="preroll-title" style={{ fontWeight: 'bold', margin: 0 }}>{preroll.display_name || preroll.filename}</p>
                </div>
                <div className="preroll-actions">
                  <button
                    onClick={() => handleEditPreroll(preroll)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem' }}
                    title="Edit preroll"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeletePreroll(preroll.id)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem', backgroundColor: '#dc3545' }}
                    title="Delete preroll"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              {preroll.thumbnail && (
                <img
                  src={apiUrl(`static/${preroll.thumbnail}`)}
                  alt="thumbnail"
                  onError={(e) => {
                    try {
                      const rel = preroll.thumbnail || '';
                      const parts = rel.split('/');
                      const category = parts[2] || 'Default';
                      const filename = parts.slice(3).join('/') || (parts.length ? parts[parts.length - 1] : '');
                      e.currentTarget.onerror = null;
                      e.currentTarget.src = apiUrl(`thumbgen/${encodeURIComponent(category)}/${encodeURIComponent(filename)}`);
                    } catch (_) {
                      // ignore
                    }
                  }}
                />
              )}
              {preroll.category && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Primary: {preroll.category.name}</p>}
              {Array.isArray(preroll.categories) && preroll.categories.filter(c => !preroll.category || c.id !== preroll.category.id).length > 0 && (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Also in: {preroll.categories
                    .filter(c => !preroll.category || c.id !== preroll.category.id)
                    .map(c => c.name)
                    .join(', ')}
                </p>
              )}
              {preroll.tags && (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Tags: {Array.isArray(preroll.tags) ? preroll.tags.join(', ') : preroll.tags}
                </p>
              )}
              {preroll.description && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{preroll.description}</p>}
              {preroll.duration && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Duration: {Math.round(preroll.duration)}s</p>}
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted, #999)' }}>
                {new Date(preroll.upload_date).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
        {/* Pagination (Grid) */}
        {prerollView === 'grid' && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              Showing {totalPrerolls === 0 ? 0 : (pageStartIndex + 1)}-{pageEndIndex} of {totalPrerolls}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button className="button-secondary" disabled={currentPageClamped === 1} onClick={() => setCurrentPage(p => Math.max(1, p - 1))}>◀ Prev</button>
              <span style={{ fontSize: '0.9rem' }}>Page {currentPageClamped} of {totalPages}</span>
              <button className="button-secondary" disabled={currentPageClamped === totalPages} onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}>Next ▶</button>
            </div>
          </div>
        )}
      </div>
      <div className="preroll-list" style={{ display: prerollView === 'list' ? 'block' : 'none' }}>
       {visiblePrerolls.map(preroll => (
         <div key={preroll.id} style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border-color)' }}>
           <input
             type="checkbox"
             checked={selectedPrerollIds.includes(preroll.id)}
             onChange={() => toggleSelectPreroll(preroll.id)}
             title="Select preroll"
           />
           {preroll.thumbnail && (
             <img
               src={apiUrl(`static/${preroll.thumbnail}`)}
               alt="thumbnail"
               style={{ width: 120, height: 'auto', borderRadius: 4 }}
               onError={(e) => {
                 try {
                   const rel = preroll.thumbnail || '';
                   const parts = rel.split('/');
                   const category = parts[2] || 'Default';
                   const filename = parts.slice(3).join('/') || (parts.length ? parts[parts.length - 1] : '');
                   e.currentTarget.onerror = null;
                   e.currentTarget.src = apiUrl(`thumbgen/${encodeURIComponent(category)}/${encodeURIComponent(filename)}`);
                 } catch (_) {}
               }}
             />
           )}
           <div style={{ flex: 1, minWidth: 0 }}>
             <div className="preroll-row-title" style={{ fontWeight: 'bold' }}>{preroll.display_name || preroll.filename}</div>
             {preroll.category && <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Primary: {preroll.category.name}</div>}
             {Array.isArray(preroll.categories) && preroll.categories.filter(c => !preroll.category || c.id !== preroll.category.id).length > 0 && (
               <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                 Also in: {preroll.categories
                   .filter(c => !preroll.category || c.id !== preroll.category.id)
                   .map(c => c.name)
                   .join(', ')}
               </div>
             )}
             {preroll.tags && (
               <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                 Tags: {Array.isArray(preroll.tags) ? preroll.tags.join(', ') : preroll.tags}
               </div>
             )}
             {preroll.description && <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{preroll.description}</div>}
             {preroll.duration && <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Duration: {Math.round(preroll.duration)}s</div>}
             <div style={{ fontSize: '0.8rem', color: 'var(--text-muted, #999)' }}>
               {new Date(preroll.upload_date).toLocaleDateString()}
             </div>
           </div>
           <div style={{ display: 'flex', gap: '0.25rem' }}>
             <button
               onClick={() => handleEditPreroll(preroll)}
               className="button"
               style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
               title="Edit preroll"
             >
               ✏️
             </button>
             <button
               onClick={() => handleDeletePreroll(preroll.id)}
               className="button"
               style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', backgroundColor: '#dc3545' }}
               title="Delete preroll"
             >
               🗑️
             </button>
           </div>
         </div>
       ))}
       {/* Pagination (List) */}
       <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
         <div style={{ fontSize: '0.9rem', color: '#666' }}>
           Showing {totalPrerolls === 0 ? 0 : (pageStartIndex + 1)}-{pageEndIndex} of {totalPrerolls}
         </div>
         <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
           <button className="button-secondary" disabled={currentPageClamped === 1} onClick={() => setCurrentPage(p => Math.max(1, p - 1))}>◀ Prev</button>
           <span style={{ fontSize: '0.9rem' }}>Page {currentPageClamped} of {totalPages}</span>
           <button className="button-secondary" disabled={currentPageClamped === totalPages} onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}>Next ▶</button>
         </div>
       </div>
      </div>
    </div>
  );

  const renderSchedules = () => (
    <div>
      <h1 className="header">Schedule Management</h1>
<div className="card" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
  <button className="button" onClick={() => setShowCalendar(!showCalendar)}>
    {showCalendar ? 'Hide Calendar' : 'Show Calendar'}
  </button>
  <label style={{ fontSize: '0.9rem' }}>View:</label>
  <select value={calendarMode} onChange={(e) => setCalendarMode(e.target.value)} className="nx-select">
    <option value="month">Month</option>
    <option value="year">Year</option>
  </select>
  {calendarMode === 'month' && (
    <>
      <label style={{ fontSize: '0.9rem' }}>Month:</label>
      <select value={calendarMonth} onChange={(e) => setCalendarMonth(parseInt(e.target.value, 10))} className="nx-select">
        {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
          <option key={m} value={m}>{new Date(2000, m - 1, 1).toLocaleString(undefined, { month: 'long' })}</option>
        ))}
      </select>
      <label style={{ fontSize: '0.9rem' }}>Year:</label>
      <input type="number" value={calendarYear} onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)} className="nx-input" style={{ width: 90 }} />
      <button
        className="button"
        onClick={() => { let m = calendarMonth - 1; let y = calendarYear; if (m < 1) { m = 12; y--; } setCalendarMonth(m); setCalendarYear(y); }}
        title="Previous Month"
      >◀</button>
      <button
        className="button"
        onClick={() => { let m = calendarMonth + 1; let y = calendarYear; if (m > 12) { m = 1; y++; } setCalendarMonth(m); setCalendarYear(y); }}
        title="Next Month"
      >▶</button>
    </>
  )}
  {calendarMode === 'year' && (
    <>
      <label style={{ fontSize: '0.9rem' }}>Year:</label>
      <input type="number" value={calendarYear} onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)} className="nx-input" style={{ width: 90 }} />
    </>
  )}
</div>
<div style={{ display: showCalendar ? 'block' : 'none' }}>
  {calendarMode === 'month' ? (() => {
    const monthIndex = calendarMonth - 1;
    const startOfMonth = new Date(calendarYear, monthIndex, 1);
    const start = new Date(startOfMonth);
    start.setDate(start.getDate() - start.getDay()); // back to Sunday

    const days = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      days.push(d);
    }

    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };

    const scheds = (schedules || []).map(s => ({
      ...s,
      sDay: normalizeDay(s.start_date),
      eDay: normalizeDay(s.end_date) ?? normalizeDay(s.start_date),
      cat: catMap.get(s.category_id) || { name: (s.category?.name || 'Unknown'), color: '#6c757d' }
    }));

    const byDay = new Map(); // dayTime -> Set of cat ids
    days.forEach(d => {
      const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      byDay.set(t, new Set());
    });

    for (const s of scheds) {
      if (s.sDay == null || s.eDay == null) continue;
      for (const d of days) {
        const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
        if (t >= s.sDay && t <= s.eDay) {
          const set = byDay.get(t);
          if (set) set.add(s.category_id);
        }
      }
    }

    const monthName = startOfMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' });

    return (
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0 }}>{monthName}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px' }}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(dow => (
            <div key={dow} style={{ fontWeight: 'bold', textAlign: 'center', padding: '4px 0' }}>{dow}</div>
          ))}
          {days.map((d, idx) => {
            const inMonth = d.getMonth() === monthIndex;
            const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
            const cats = Array.from(byDay.get(t) || []);
            return (
              <div key={idx} style={{
                border: '1px solid var(--border-color)',
                backgroundColor: inMonth ? 'var(--card-bg)' : 'rgba(0,0,0,0.03)',
                minHeight: 72,
                padding: '4px',
                borderRadius: '4px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ position: 'absolute', top: 4, right: 6, fontSize: '0.8rem', color: '#666' }}>{d.getDate()}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '18px' }}>
                  {cats.slice(0, 4).map((cid, i) => {
                    const cat = catMap.get(cid) || { name: 'Unknown', color: '#6c757d' };
                    return (
                      <span key={cid + '_' + i} title={cat.name} style={{
                        backgroundColor: cat.color, color: '#fff', borderRadius: '3px',
                        padding: '2px 4px', fontSize: '0.72rem', maxWidth: '100%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                      }}>
                        {cat.name}
                      </span>
                    );
                  })}
                  {cats.length > 4 && (
                    <span style={{ fontSize: '0.72rem', color: '#666' }}>+{cats.length - 4} more</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {(categories || []).map((c, idx) => (
            <span key={c.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
              <span style={{ width: 12, height: 12, backgroundColor: palette[idx % palette.length], display: 'inline-block', borderRadius: 2 }} />
              {c.name}
            </span>
          ))}
        </div>
      </div>
    );
  })() : (() => {
    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    // Count scheduled days per month
    const counts = Array.from({ length: 12 }, (_, m) => ({ month: m, cats: new Map() }));
    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    const yearStart = new Date(calendarYear, 0, 1).getTime();
    const yearEnd = new Date(calendarYear, 11, 31).getTime();

    for (const s of (schedules || [])) {
      const sDay = normalizeDay(s.start_date);
      const eDay = normalizeDay(s.end_date) ?? sDay;
      if (sDay == null || eDay == null) continue;

      // intersect with chosen year
      const from = Math.max(sDay, yearStart);
      const to = Math.min(eDay, yearEnd);
      if (from > to) continue;

      const catId = s.category_id;
      for (let t = from; t <= to; t += 86400000) {
        const d = new Date(t);
        const m = d.getMonth();
        const map = counts[m].cats;
        map.set(catId, (map.get(catId) || 0) + 1);
      }
    }

    return (
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{calendarYear}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
          {counts.map((entry) => {
            const monthName = new Date(calendarYear, entry.month, 1).toLocaleString(undefined, { month: 'long' });
            const topCats = Array.from(entry.cats.entries()).sort((a, b) => b[1] - a[1]).slice(0, 3);
            return (
              <div key={entry.month} style={{ border: '1px solid var(--border-color)', borderRadius: 6, padding: 8, background: 'var(--card-bg)' }}>
                <div style={{ fontWeight: 'bold', marginBottom: 6 }}>{monthName}</div>
                {topCats.length === 0 ? (
                  <div style={{ fontSize: '0.85rem', color: '#666' }}>No scheduled days</div>
                ) : (
                  <div style={{ display: 'grid', gap: 4 }}>
                    {topCats.map(([cid, cnt], i) => {
                      const cat = catMap.get(cid) || { name: 'Unknown', color: '#6c757d' };
                      return (
                        <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
                          <span style={{ width: 12, height: 12, backgroundColor: cat.color, display: 'inline-block', borderRadius: 2 }} />
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</span>
                          <span style={{ color: '#666' }}>{cnt}d</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  })()}
</div>

      <div className="upload-section">
        <h2>Create New Schedule</h2>
        <form onSubmit={handleCreateSchedule}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <input
              type="text"
              placeholder="Schedule Name"
              value={scheduleForm.name}
              onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            />
            <select
              value={scheduleForm.type}
              onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
              style={{ padding: '0.5rem' }}
            >
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
              <option value="holiday">Holiday</option>
              <option value="custom">Custom</option>
            </select>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Start Date & Time</label>
              <input
                type="datetime-local"
                value={scheduleForm.start_date}
                onChange={(e) => setScheduleForm({...scheduleForm, start_date: e.target.value})}
                required
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>End Date & Time (Optional)</label>
              <input
                type="datetime-local"
                value={scheduleForm.end_date}
                onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <select
              value={scheduleForm.category_id}
              onChange={(e) => setScheduleForm({...scheduleForm, category_id: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            >
              <option value="">Select Category</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Holiday Preset (Optional)</label>
              <select
                value=""
                onChange={(e) => {
                  const preset = holidayPresets.find(p => p.id === parseInt(e.target.value));
                  if (preset) {
                    const currentYear = new Date().getFullYear();

                    // Use date range fields if available, otherwise fall back to single day
                    let startDate, endDate;
                    if (preset.start_month && preset.start_day && preset.end_month && preset.end_day) {
                      // Use the new date range fields
                      startDate = new Date(currentYear, preset.start_month - 1, preset.start_day, 0, 0, 0);
                      endDate = new Date(currentYear, preset.end_month - 1, preset.end_day, 23, 59, 59);
                    } else {
                      // Fall back to old single day format for backward compatibility
                      startDate = new Date(currentYear, preset.month - 1, preset.day, 12, 0, 0);
                      endDate = new Date(currentYear, preset.month - 1, preset.day, 23, 59, 59);
                    }

                    setScheduleForm({
                      ...scheduleForm,
                      name: `${preset.name} Schedule`,
                      type: 'holiday',
                      start_date: toLocalInputFromDate(startDate),
                      end_date: endDate.toISOString().slice(0, 16),
                      category_id: preset.category_id.toString()
                    });
                  }
                }}
                style={{ padding: '0.5rem', width: '100%' }}
              >
                <option value="">Choose Holiday Preset</option>
                {holidayPresets.map(preset => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name} ({preset.start_month ? `${preset.start_month}/${preset.start_day} - ${preset.end_month}/${preset.end_day}` : `${preset.month}/${preset.day}`})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ marginRight: '1rem' }}>
              <input
                type="checkbox"
                checked={scheduleForm.shuffle}
                onChange={(e) => setScheduleForm({...scheduleForm, shuffle: e.target.checked})}
              />
              Random
            </label>
            <label>
              <input
                type="checkbox"
                checked={scheduleForm.playlist}
                onChange={(e) => setScheduleForm({...scheduleForm, playlist: e.target.checked})}
              />
              Sequential
            </label>
          </div>
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Fallback Category</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              When no schedule is active, this category will be used as the default for preroll selection.
            </p>
            <select
              value={scheduleForm.fallback_category_id || ''}
              onChange={(e) => setScheduleForm({...scheduleForm, fallback_category_id: e.target.value})}
              style={{ padding: '0.5rem', width: '200px' }}
            >
              <option value="">No Fallback</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="button">{editingSchedule ? 'Update Schedule' : 'Create Schedule'}</button>
          {/* edit handled via modal */}
        </form>
      </div>

      {editingSchedule && (
        <Modal
          title="Edit Schedule"
          onClose={() => {
            setEditingSchedule(null);
            setScheduleForm({
              name: '', type: 'monthly', start_date: '', end_date: '',
              category_id: '', shuffle: false, playlist: false, fallback_category_id: ''
            });
          }}
        >
          <form onSubmit={handleUpdateSchedule}>
            <div className="nx-form-grid">
              <div className="nx-field">
                <label className="nx-label">Name</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Schedule Name"
                  value={scheduleForm.name}
                  onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
                  required
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">Type</label>
                <select
                  className="nx-select"
                  value={scheduleForm.type}
                  onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="holiday">Holiday</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div className="nx-field">
                <label className="nx-label">Start Date & Time</label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.start_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, start_date: e.target.value})}
                  required
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">End Date & Time (Optional)</label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.end_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">Category</label>
                <select
                  className="nx-select"
                  value={scheduleForm.category_id}
                  onChange={(e) => setScheduleForm({...scheduleForm, category_id: e.target.value})}
                  required
                >
                  <option value="">Select Category</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="nx-field">
                <label className="nx-label">Fallback Category</label>
                <select
                  className="nx-select"
                  value={scheduleForm.fallback_category_id || ''}
                  onChange={(e) => setScheduleForm({...scheduleForm, fallback_category_id: e.target.value})}
                >
                  <option value="">No Fallback</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">
                  <input
                    type="checkbox"
                    checked={scheduleForm.shuffle}
                    onChange={(e) => setScheduleForm({...scheduleForm, shuffle: e.target.checked})}
                    style={{ marginRight: '0.5rem' }}
                  />
                  Random
                </label>
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">
                  <input
                    type="checkbox"
                    checked={scheduleForm.playlist}
                    onChange={(e) => setScheduleForm({...scheduleForm, playlist: e.target.checked})}
                    style={{ marginRight: '0.5rem' }}
                  />
                  Sequential
                </label>
              </div>
            </div>
            <div className="nx-actions">
              <button type="submit" className="button">Update Schedule</button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => {
                  setEditingSchedule(null);
                  setScheduleForm({
                    name: '', type: 'monthly', start_date: '', end_date: '',
                    category_id: '', shuffle: false, playlist: false, fallback_category_id: ''
                  });
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      <div className="card">
        <h2>Active Schedules</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {schedules.map(schedule => (
            <div key={schedule.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{schedule.name}</h3>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleEditSchedule(schedule)}
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                  >
                    ✏️ Edit
                  </button>
                  <button
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', backgroundColor: '#dc3545' }}
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
              <p>Type: {schedule.type} | Category: {schedule.category?.name || 'N/A'}</p>
              <p>Status: {schedule.is_active ? 'Active' : 'Inactive'}</p>
              <p>Start: {toLocalDisplay(schedule.start_date)}{schedule.end_date ? ` | End: ${toLocalDisplay(schedule.end_date)}` : ''}</p>
              <p>Shuffle: {schedule.shuffle ? 'Yes' : 'No'} | Playlist: {schedule.playlist ? 'Yes' : 'No'}</p>
              {schedule.next_run && <p>Next Run: {toLocalDisplay(schedule.next_run)}</p>}
              {schedule.last_run && <p>Last Run: {toLocalDisplay(schedule.last_run)}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const [newCategory, setNewCategory] = useState({ name: '', description: '', plex_mode: 'shuffle' });

  const handleCreateCategory = async (e) => {
    e.preventDefault();

    const name = (newCategory.name || '').trim();
    const description = (newCategory.description || '').trim();
    if (!name) {
      alert('Category name is required');
      return;
    }

    try {
      const res = await fetch('http://localhost:9393/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, plex_mode: newCategory.plex_mode || 'shuffle' })
      });

      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}

      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }

      alert('Category created successfully!');
      setNewCategory({ name: '', description: '' });

      if (data && data.id) {
        setCategories(prev => [...prev, data]);
      } else {
        fetchData();
      }
    } catch (error) {
      console.error('Category creation error:', error);
      alert(error.message.includes('already exists') ? 'Category already exists' : 'Failed to create category: ' + error.message);
    }
  };

  const renderCategories = () => (
    <div>
      <h1 className="header">Category Management</h1>
      <div className="card" style={{ marginBottom: '1rem' }}>
        <button onClick={handleInitHolidays} className="button">Load Holiday Categories</button>
      </div>

      <div className="upload-section">
        <h2>Create New Category</h2>
        <form onSubmit={handleCreateCategory}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', marginBottom: '1rem' }}>
            <input
              type="text"
              placeholder="Category Name"
              value={newCategory.name}
              onChange={(e) => setNewCategory({...newCategory, name: e.target.value})}
              required
              className="nx-input"
            />
            <input
              type="text"
              placeholder="Description (Optional)"
              value={newCategory.description}
              onChange={(e) => setNewCategory({...newCategory, description: e.target.value})}
              className="nx-input"
            />
            <select
              value={newCategory.plex_mode}
              onChange={(e) => setNewCategory({ ...newCategory, plex_mode: e.target.value })}
              style={{ padding: '0.5rem' }}
            >
              <option value="shuffle">Random</option>
              <option value="playlist">Sequential</option>
            </select>
          </div>
          <button type="submit" className="button">{editingCategory ? 'Update Category' : 'Create Category'}</button>
          {/* edit handled via modal */}
        </form>
      </div>

      {editingCategory && (
        <Modal
          title="Edit Category"
          onClose={() => { setEditingCategory(null); setNewCategory({ name: '', description: '' }); }}
          width={820}
        >
          <form onSubmit={handleUpdateCategory}>
            <div className="nx-form-grid">
              <div className="nx-field nx-span-2">
                <label className="nx-label">Category Name</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Category Name"
                  value={newCategory.name}
                  onChange={(e) => setNewCategory({...newCategory, name: e.target.value})}
                  required
                />
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">Description</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Optional description"
                  value={newCategory.description}
                  onChange={(e) => setNewCategory({...newCategory, description: e.target.value})}
                />
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">Plex Mode</label>
                <select
                  className="nx-select"
                  value={newCategory.plex_mode || 'shuffle'}
                  onChange={(e) => setNewCategory({ ...newCategory, plex_mode: e.target.value })}
                >
                  <option value="shuffle">Random</option>
                  <option value="playlist">Sequential</option>
                </select>
              </div>
            </div>
            <div className="nx-actions">
              <button type="submit" className="button">Update Category</button>
              <button
                type="button"
                className="button"
                onClick={handleUpdateCategoryAndApply}
                style={{ backgroundColor: '#28a745' }}
                title="Save changes and apply to Plex"
              >
                Save & Apply
              </button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => { setEditingCategory(null); setNewCategory({ name: '', description: '' }); }}
              >
                Cancel
              </button>
            </div>
          </form>

          <div style={{ borderTop: '1px solid var(--border-color)', margin: '1rem 0' }} />

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <h3 className="nx-modal-title" style={{ fontSize: '1rem', margin: 0 }}>Manage Prerolls</h3>
              <button
                type="button"
                className="button-secondary"
                onClick={() => { try { loadCategoryPrerolls(editingCategory.id); } catch (e) {} }}
                title="Refresh list"
              >
                Refresh
              </button>
            </div>

            {categoryPrerollsLoading[editingCategory.id] ? (
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Loading prerolls…</div>
            ) : (
              <>
                <div className="nx-field nx-span-2" style={{ marginBottom: '0.5rem' }}>
                  <label className="nx-label">Assigned Prerolls</label>
                  {(categoryPrerolls[editingCategory.id] || []).length === 0 ? (
                    <p style={{ fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>No prerolls assigned</p>
                  ) : (
                    <div style={{ display: 'grid', gap: '0.4rem' }}>
                      {(categoryPrerolls[editingCategory.id] || []).map(p => (
                        <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.4rem 0.6rem' }}>
                          <span style={{ fontSize: '0.9rem' }}>
                            {p.display_name || p.filename}
                            {p.category_id === editingCategory.id && (
                              <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#28a745' }}>(Primary)</span>
                            )}
                          </span>
                          <div>
                            <button
                              onClick={() => handleEditPreroll(p)}
                              className="button"
                              style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', marginRight: '0.25rem' }}
                              title="Edit preroll"
                            >
                              ✏️
                            </button>
                            <button
                              onClick={() => handleCategoryRemovePreroll(editingCategory.id, p)}
                              className="button"
                              disabled={p.category_id === editingCategory.id}
                              style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', backgroundColor: p.category_id === editingCategory.id ? '#6c757d' : '#dc3545', cursor: p.category_id === editingCategory.id ? 'not-allowed' : 'pointer' }}
                              title={p.category_id === editingCategory.id ? 'Cannot remove primary here' : 'Remove from this category'}
                            >
                              🗑️ Remove
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="nx-form-grid" style={{ marginTop: '0.5rem' }}>
                  <div className="nx-field nx-span-2">
                    <label className="nx-label">Add a Preroll to this Category</label>
                    <select
                      className="nx-select"
                      value={(categoryAddSelection[editingCategory.id]?.prerollId) || ''}
                      onChange={(e) => setCategoryAddSelection(prev => ({ ...prev, [editingCategory.id]: { ...(prev[editingCategory.id] || {}), prerollId: e.target.value } }))}
                    >
                      <option value="">Select preroll…</option>
                      {availablePrerollsForCategory(editingCategory.id).map(p => (
                        <option key={p.id} value={p.id}>
                          {(p.display_name || p.filename) + (p.category_id ? ` — Primary: ${categories.find(c => c.id === p.category_id)?.name || 'Unknown'}` : '')}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="nx-field nx-span-2">
                    <label className="nx-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                      <input
                        type="checkbox"
                        checked={Boolean(categoryAddSelection[editingCategory.id]?.setPrimary)}
                        onChange={(e) => setCategoryAddSelection(prev => ({ ...prev, [editingCategory.id]: { ...(prev[editingCategory.id] || {}), setPrimary: e.target.checked } }))}
                      />
                      Set as Primary (moves the file under this category)
                    </label>
                  </div>
                  <div className="nx-actions nx-span-2" style={{ justifyContent: 'flex-start' }}>
                    <button
                      type="button"
                      className="button"
                      disabled={!categoryAddSelection[editingCategory.id]?.prerollId}
                      onClick={() => handleCategoryAddPreroll(editingCategory.id)}
                    >
                      ➕ Add to Category
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </Modal>
      )}

      {false && (<div className="upload-section">
        <h2>Holiday Presets</h2>
        <p style={{ marginBottom: '0.5rem', color: '#666' }}>
          Initialize to create holiday categories and preset date ranges. Use them on the Schedules page via the "Holiday Preset" picker or by selecting the created categories.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={handleInitHolidays} className="button">Initialize Holiday Presets</button>
          <button onClick={() => setActiveTab('schedules')} className="button" style={{ backgroundColor: '#6c757d' }}>
            Go to Schedules
          </button>
        </div>
        <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
          {holidayPresets.map(preset => (
            <div key={preset.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <h3>{preset.name}</h3>
              <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                {preset.start_month ?
                  `${preset.start_month}/${preset.start_day} - ${preset.end_month}/${preset.end_day}` :
                  `${preset.month}/${preset.day}`
                }
              </p>
              <p style={{ fontSize: '0.9rem' }}>{preset.description}</p>
            </div>
          ))}
        </div>
      </div>)}

      <div className="card">
        <h2>Categories</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem' }}>
          {categories.map(category => (
            <div key={category.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{category.name}</h3>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => handleEditCategory(category)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem' }}
                    title="Edit category"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeleteCategory(category.id)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem', backgroundColor: '#dc3545' }}
                    title="Delete category"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>{category.description || 'No description'}</p>
              <p style={{ fontSize: '0.8rem', color: '#666' }}>Plex Preroll Mode: {category.plex_mode === 'playlist' ? 'Sequential' : 'Random'}</p>

              {/* Apply to Plex Section */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem', marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Plex Status:</span>
                  <span style={{
                    fontSize: '0.8rem',
                    color: category.apply_to_plex ? 'green' : '#666',
                    fontWeight: category.apply_to_plex ? 'bold' : 'normal'
                  }}>
                    {category.apply_to_plex ? 'Applied' : 'Not Applied'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => handleApplyCategoryToPlex(category.id, category.name)}
                    className="button"
                    style={{
                      fontSize: '0.7rem',
                      padding: '0.25rem 0.5rem',
                      backgroundColor: category.apply_to_plex ? '#28a745' : '#007bff',
                      flex: 1
                    }}
                    title="Apply this category to Plex"
                  >
                    {category.apply_to_plex ? '🔄 Reapply' : '🎬 Apply to Plex'}
                  </button>
                  {category.apply_to_plex && (
                    <button
                      onClick={() => handleRemoveCategoryFromPlex(category.id, category.name)}
                      className="button"
                      style={{
                        fontSize: '0.7rem',
                        padding: '0.25rem 0.5rem',
                        backgroundColor: '#6c757d'
                      }}
                      title="Remove from Plex"
                    >
                      ❌ Remove
                    </button>
                  )}
                </div>
              </div>

              {/* Manage Prerolls */}
              <div style={{ borderTop: '1px dashed var(--border-color)', paddingTop: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  onClick={() => handleEditCategory(category)}
                  className="button"
                  style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', backgroundColor: '#17a2b8' }}
                  title="Manage prerolls in this category"
                >
                  Manage Prerolls
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const handleConnectPlex = (e) => {
    e.preventDefault();
    fetch('http://localhost:9393/plex/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: plexConfig.url,
        token: plexConfig.token
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.connected) {
          alert('Successfully connected to Plex using manual token!');
          fetchData();
        } else {
          alert('Failed to connect to Plex. Please check your URL and token.');
        }
      })
      .catch(error => {
        console.error('Plex connection error:', error);
        alert('Failed to connect to Plex: ' + error.message);
      });
  };

  const handleConnectPlexStableToken = (e) => {
    e.preventDefault();
    fetch('http://localhost:9393/plex/connect/stable-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: plexConfig.url,
        token: '' // Not needed for stable token method
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.connected) {
          alert('Successfully connected to Plex using stable token!');
          fetchData();
        } else {
          alert('Failed to connect to Plex. Please check your URL and ensure the stable token is configured.');
        }
      })
      .catch(error => {
        console.error('Plex stable token connection error:', error);
        alert('Failed to connect to Plex: ' + error.message);
      });
  };


  const handleDisconnectPlex = () => {
    if (window.confirm('Are you sure you want to disconnect from Plex? This will clear all stored connection settings.')) {
      fetch('http://localhost:9393/plex/disconnect', {
        method: 'POST'
      })
        .then(res => res.json())
        .then(data => {
          alert('Successfully disconnected from Plex!');
          // Clear local state
          setPlexConfig({ url: '', token: '', library: '' });
          setPlexStatus('Disconnected');
          setPlexServerInfo(null);
          fetchData();
        })
        .catch(error => {
          console.error('Plex disconnect error:', error);
          alert('Failed to disconnect from Plex: ' + error.message);
        });
    }
  };

  // -------- Plex Stable Token: save/update (advanced) --------
  const handleSaveStableToken = async (e) => {
    e.preventDefault();
    const tok = (stableTokenInput || '').trim();
    if (!tok) {
      alert('Enter a token to save.');
      return;
    }
    try {
      const res = await fetch(`http://localhost:9393/plex/stable-token/save?token=${encodeURIComponent(tok)}`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || data?.message || `HTTP ${res.status}`);
      alert('Stable token saved. You can now connect using Method 1.');
      setStableTokenInput('');
      setShowStableTokenSave(false);
      fetchData();
    } catch (err) {
      alert('Failed to save stable token: ' + (err?.message || err));
    }
  };

  // -------- Plex.tv OAuth helpers --------
  const clearOAuthPoll = () => {
    try {
      if (oauthPollRef.current) {
        clearInterval(oauthPollRef.current);
        oauthPollRef.current = null;
      }
    } catch {}
  };

  const startPlexOAuth = async () => {
    try {
      setPlexOAuth({ id: null, url: '', status: 'starting', error: null });
      const res = await fetch('http://localhost:9393/plex/tv/start', { method: 'POST' });
      const data = await res.json();
      if (!res.ok || !data?.id || !data?.url) {
        throw new Error(data?.detail || 'Failed to start Plex.tv login');
      }
      setPlexOAuth({ id: data.id, url: data.url, status: 'pending', error: null });
      try { window.open(data.url, '_blank', 'noopener,noreferrer'); } catch {}

      clearOAuthPoll();
      oauthPollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`http://localhost:9393/plex/tv/status/${data.id}`);
          const s = await r.json();
          if (s?.status === 'success') {
            clearOAuthPoll();
            setPlexOAuth(prev => ({ ...prev, status: 'authorized' }));
            await finishPlexOAuth(data.id);
          } else if (s?.status === 'expired' || s?.status === 'not_found') {
            clearOAuthPoll();
            setPlexOAuth(prev => ({ ...prev, status: 'expired' }));
          }
        } catch {
          // ignore transient errors during polling
        }
      }, 2000);
    } catch (e) {
      setPlexOAuth({ id: null, url: '', status: 'error', error: String(e?.message || e) });
    }
  };

  const finishPlexOAuth = async (id) => {
    const sid = id || plexOAuth.id;
    if (!sid) return;
    setPlexOAuth(prev => ({ ...prev, status: 'connecting' }));
    try {
      const res = await fetch('http://localhost:9393/plex/tv/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: sid, save_token: true })
      });
      const data = await res.json();
      if (!res.ok || !data?.connected) {
        throw new Error(data?.detail || data?.message || `HTTP ${res.status}`);
      }
      setPlexOAuth(prev => ({ ...prev, status: 'connected' }));
      alert('Successfully connected to Plex via Plex.tv!');
      fetchData();
    } catch (e) {
      setPlexOAuth(prev => ({ ...prev, status: 'error', error: String(e?.message || e) }));
    }
  };

  const cancelPlexOAuth = () => {
    clearOAuthPoll();
    setPlexOAuth({ id: null, url: '', status: 'idle', error: null });
  };

  // Cleanup poller on unmount
  React.useEffect(() => {
    return () => { clearOAuthPoll(); };
  }, []);

  const renderPlex = () => (
    <div>
      <h1 className="header">Plex Integration</h1>

      <div className="card nx-plex-card">
        <h2>Connect to Plex Server</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Connect your local Plex server to enable automatic preroll scheduling and media synchronization.
        </p>
        <div className="nx-plex-steps">
          <span className="nx-step"><span className="nx-badge">1</span> Stable Token</span>
          <span className="nx-step"><span className="nx-badge">2</span> Manual X-Plex-Token</span>
          <span className="nx-step"><span className="nx-badge">3</span> Plex.tv Auth</span>
        </div>
        {/* Stable Token Connection */}
        <div className="upload-section nx-plex-method" style={{ marginBottom: '2rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>🌟 Method 1: Stable Token (Recommended)</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Uses a non-expiring token stored securely. The installer selects "Plex Stable Token Setup" by default.
            If your Plex server runs on a different machine, run "Setup Plex Stable Token" from the Start Menu
            on that machine to configure it, then connect here.
          </p>

          <div className="nx-plex-note" style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px dashed var(--border-color)', marginBottom: '0.75rem' }}>
            <strong>Tip:</strong> For best results, use Method 1. It's resilient to password changes and service restarts.
          </div>
          <div style={{ marginBottom: '1rem', display: 'grid', gap: '0.3rem', fontSize: '0.9rem' }}>
            <div><strong>Stable Token:</strong> <span className={`nx-chip nx-status ${stableTokenStatus.has_stable_token ? 'ok' : 'bad'}`}>{stableTokenStatus.has_stable_token ? 'Configured' : 'Not Configured'}</span></div>
            {stableTokenStatus.has_stable_token && (
              <div><strong>Token Length:</strong> {stableTokenStatus.token_length} characters</div>
            )}
            {stableTokenStatus.provider && (
              <div><strong>Storage:</strong> {stableTokenStatus.provider}</div>
            )}
          </div>

          <form onSubmit={handleConnectPlexStableToken}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Plex Server URL
                </label>
                <input
                  type="url"
                  placeholder="http://192.168.1.100:32400"
                  value={plexConfig.url}
                  onChange={(e) => setPlexConfig({...plexConfig, url: e.target.value})}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="submit"
                className="button button-success"
                title={stableTokenStatus.has_stable_token ? 'Connect using configured stable token' : 'Attempt connection; if not configured, you will be prompted'}
              >
                Connect with Stable Token
              </button>
              {!stableTokenStatus.has_stable_token && (
                <span style={{ fontSize: '0.9rem', color: '#666' }}>
                  If the stable token isn’t configured yet, run "Setup Plex Stable Token" from the Start Menu,
                  then try again.
                </span>
              )}
            </div>
          </form>

          {/* Advanced: Save/Update stable token locally (optional) */}
          <div style={{ marginTop: '0.75rem' }}>
            <button
              type="button"
              className="button-secondary"
              onClick={() => setShowStableTokenSave(!showStableTokenSave)}
              style={{ fontSize: '0.85rem' }}
              title="Save or update the stable token in secure storage"
            >
              {showStableTokenSave ? 'Hide Advanced' : 'Advanced: Save/Update Stable Token'}
            </button>
            {showStableTokenSave && (
              <form onSubmit={handleSaveStableToken} style={{ marginTop: '0.5rem', display: 'grid', gap: '0.5rem' }}>
                <input
                  type="password"
                  placeholder="Paste your stable token"
                  value={stableTokenInput}
                  onChange={(e) => setStableTokenInput(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem' }}
                />
                <button type="submit" className="button" style={{ backgroundColor: '#17a2b8' }}>
                  Save Stable Token
                </button>
              </form>
            )}
          </div>
          <details className="nx-plex-help" style={{ marginTop: '0.75rem' }}>
            <summary>Docker/Remote: save token headlessly</summary>
            <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.25rem' }}>
              If NeXroll runs in Docker or on a different host than Plex, you can paste your Plex token via “Advanced: Save/Update Stable Token” above,
              or run this from any machine that can reach NeXroll:
            </div>
            <pre className="nx-code" style={{ whiteSpace: 'pre-wrap', marginTop: '0.5rem' }}>
curl -X POST "http://YOUR_HOST:9393/plex/stable-token/save?token=YOUR_PLEX_TOKEN"
            </pre>
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              Then click “Connect with Stable Token” and enter your Plex Server URL (e.g., http://192.168.1.100:32400). Make sure your Plex server is claimed and Remote Access is enabled if it’s off-LAN.
            </div>
          </details>
        </div>

        {/* Method 2: Manual X-Plex-Token */}
        <div className="upload-section nx-plex-method" style={{ marginBottom: '2rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>🧰 Method 2: Manual X-Plex-Token</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Enter your Plex server URL and authentication token manually.
          </p>

          <form onSubmit={handleConnectPlex}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Plex Server URL
                </label>
                <input
                  type="url"
                  placeholder="http://192.168.1.100:32400"
                  value={plexConfig.url}
                  onChange={(e) => setPlexConfig({ ...plexConfig, url: e.target.value })}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  X-Plex-Token
                </label>
                <input
                  type="password"
                  placeholder="Enter your X-Plex-Token"
                  value={plexConfig.token}
                  onChange={(e) => setPlexConfig({ ...plexConfig, token: e.target.value })}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
                <details className="nx-plex-help">
                  <summary>How to get your X-Plex-Token</summary>
                  <ol style={{ marginTop: '0.5rem' }}>
                    <li>Open Plex Web at your server's URL (e.g., http://your-plex-server:32400/web)</li>
                    <li>Sign in to your Plex account</li>
                    <li>Go to Settings → General → Advanced</li>
                    <li>Enable "Show Advanced" if needed</li>
                    <li>Copy the "Authentication Token" (X-Plex-Token)</li>
                  </ol>
                  <p style={{ fontSize: '0.85rem', color: '#666' }}>
                    Note: For remote servers, ensure you can access the Plex Web interface from your current location.
                  </p>
                </details>
              </div>
            </div>

            <button type="submit" className="button">Connect with Manual Token</button>
          </form>
        </div>

        {/* Plex.tv Authentication */}
        <div className="upload-section nx-plex-method" style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>Method 3: Plex.tv Authentication</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.75rem' }}>
            Sign in with Plex.tv to auto-discover a reachable server and save credentials securely.
          </p>

          {(plexOAuth.status === 'idle' || plexOAuth.status === 'error') && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="button"
                className="button button-warn"
                onClick={startPlexOAuth}
                title="Start Plex.tv device login"
              >
                Start Plex.tv Login
              </button>
              {plexOAuth.status === 'error' && (
                <span style={{ color: '#dc3545', fontSize: '0.85rem' }}>{plexOAuth.error}</span>
              )}
            </div>
          )}

          {(plexOAuth.status === 'starting' || plexOAuth.status === 'pending') && (
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {plexOAuth.url && (
                  <a
                    href={plexOAuth.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="button"
                    style={{ backgroundColor: '#0ea5e9' }}
                  >
                    Open Login
                  </a>
                )}
                <button type="button" className="button-secondary" onClick={cancelPlexOAuth}>
                  Cancel
                </button>
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>
                Waiting for authorization from Plex.tv…
              </div>
            </div>
          )}

          {plexOAuth.status === 'authorized' && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="button"
                className="button button-success"
                onClick={() => finishPlexOAuth(plexOAuth.id)}
              >
                Connect Now
              </button>
              {plexOAuth.url && (
                <a
                  href={plexOAuth.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="button-secondary"
                >
                  Open Login
                </a>
              )}
            </div>
          )}

          {plexOAuth.status === 'connecting' && (
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              Connecting to your Plex server…
            </div>
          )}

          {plexOAuth.status === 'connected' && (
            <div style={{ fontSize: '0.9rem', color: 'green', fontWeight: 'bold' }}>
              Connected via Plex.tv!
            </div>
          )}
        </div>

        {/* Docker Note (Quick Connect removed in favor of Plex.tv auth) */}
        <div className="upload-section nx-plex-method" style={{ marginBottom: '2rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>🐳 Docker Note</h3>
          <p style={{ fontSize: '0.9rem', color: '#666' }}>
            When running NeXroll in Docker, use <strong>Method 3: Plex.tv Authentication</strong> above to connect.
            After connecting, configure <em>UNC/Local → Plex Path Mappings</em> in Settings to translate container/local paths
            (e.g., <code>/data/prerolls</code>) to the path Plex can see on its host
            (e.g., <code>Z:\Prerolls</code> or <code>\\NAS\share\Prerolls</code> on Windows, or <code>/mnt/prerolls</code> on Linux).
          </p>
        </div>

        {/* Remote Server Setup Guide */}
        <div style={{ marginTop: '2rem', padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>Connecting to Remote Plex Servers</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            If your Plex server is not on the same machine as NeXroll, you'll need to ensure remote access is configured:
          </p>
          <ul style={{ fontSize: '0.9rem', color: '#666', paddingLeft: '1.5rem', marginBottom: '1rem' }}>
            <li>Enable remote access in your Plex server settings</li>
            <li>Ensure your router forwards port 32400 to your Plex server</li>
            <li>Use your external IP address or domain name in the Server URL field</li>
            <li>If using HTTPS, include 'https://' in the URL</li>
          </ul>
          <p style={{ fontSize: '0.9rem', color: '#666' }}>
            <strong>Example URLs:</strong><br/>
            Local: http://192.168.1.100:32400<br/>
            Remote: https://my-plex-server.example.com:32400<br/>
            Plex Cloud: https://app.plex.tv/desktop (use your server's URL)
          </p>
        </div>

        {/* Disconnect Button */}
        {plexStatus === 'Connected' && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handleDisconnectPlex}
              className="button button-danger"
            >
              Disconnect from Plex
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Plex Status</h2>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div><strong>Connection:</strong> <span className={`nx-chip nx-status ${plexStatus === 'Connected' ? 'ok' : 'bad'}`}>{plexStatus}</span></div>
          <div><strong>Server URL:</strong> {plexConfig.url || 'Not configured'}</div>
          <div><strong>Token:</strong> {plexConfig.token ? '••••••••' : 'Not configured'}</div>
        </div>
        {plexStatus === 'Connected' && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handleDisconnectPlex}
              className="button button-danger"
            >
              Disconnect from Plex
            </button>
          </div>
        )}
      </div>

    </div>
  );

  const handleDownloadDiagnostics = async () => {
    try {
      const res = await fetch('http://localhost:9393/diagnostics/bundle');
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `NeXroll_Diagnostics_${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Failed to download diagnostics: ' + (e && e.message ? e.message : e));
    }
  };

  const recheckFfmpeg = () => {
    fetch('http://localhost:9393/system/ffmpeg-info')
      .then(res => res.json())
      .then(data => setFfmpegInfo(data))
      .catch(() => setFfmpegInfo(null));
  };

  const handleReinitThumbnails = async () => {
    if (!window.confirm('Rebuild all thumbnails now? This may take several minutes depending on your library size.')) return;
    try {
      const res = await fetch('http://localhost:9393/thumbnails/rebuild?force=true', { method: 'POST' });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }
      alert(`Thumbnails rebuilt:\nProcessed: ${data.processed}\nGenerated: ${data.generated}\nSkipped: ${data.skipped}\nFailures: ${data.failures}`);
      fetchData();
    } catch (err) {
      console.error('Thumbnail rebuild error:', err);
      alert('Thumbnail rebuild failed: ' + err.message);
    }
  };

  const handleShowSystemPaths = async () => {
    try {
      const res = await fetch('http://localhost:9393/system/paths');
      const data = await res.json();
      alert([
        `Install: ${data.install_root || 'n/a'}`,
        `Resource: ${data.resource_root || 'n/a'}`,
        `Frontend: ${data.frontend_dir || 'n/a'}`,
        `Data: ${data.data_dir || 'n/a'}`,
        `Prerolls: ${data.prerolls_dir || 'n/a'}`,
        `Thumbnails: ${data.thumbnails_dir || 'n/a'}`,
        `Logs: ${data.log_path || data.log_dir || 'n/a'}`,
        `DB: ${data.db_path || data.db_url || 'n/a'}`
      ].join('\n'));
    } catch (e) {
      alert('Failed to load system paths');
    }
  };

  // === Path mappings helpers and External Mapping actions ===
  const normalizeMappingList = (data) => {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.mappings)) return data.mappings;
    return [];
  };

  const loadPathMappings = async () => {
    setPathMappingsLoading(true);
    try {
      const res = await fetch('http://localhost:9393/settings/path-mappings');
      const data = await safeJson(res);
      const list = normalizeMappingList(data).map(m => ({
        local: m.local ?? m.source ?? m.from ?? '',
        plex: m.plex ?? m.target ?? m.to ?? ''
      }));
      setPathMappings(list.length ? list : [{ local: '', plex: '' }]);
    } catch (_) {
      setPathMappings([{ local: '', plex: '' }]);
    } finally {
      setPathMappingsLoading(false);
    }
  };

  const addMappingRow = () => setPathMappings(prev => [...prev, { local: '', plex: '' }]);
  const updateMappingRow = (idx, field, value) =>
    setPathMappings(prev => prev.map((m, i) => (i === idx ? { ...m, [field]: value } : m)));
  const removeMappingRow = (idx) =>
    setPathMappings(prev => prev.filter((_, i) => i !== idx));

  const tryPutMappings = async (list, shape) => {
    const body = shape === 'array' ? list : { mappings: list };
    const res = await fetch('http://localhost:9393/settings/path-mappings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch {}
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  };

  const savePathMappings = async () => {
    const list = (pathMappings || [])
      .map(m => ({ local: (m.local || '').trim(), plex: (m.plex || '').trim() }))
      .filter(m => m.local && m.plex);
    try {
      await tryPutMappings(list, 'array').catch(async () => await tryPutMappings(list, 'object'));
      alert('Path mappings saved.');
      await loadPathMappings();
    } catch (e) {
      alert('Failed to save mappings: ' + (e && e.message ? e.message : e));
    }
  };

  const runMappingsTest = async () => {
    const lines = (mappingTestInput || '')
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      alert('Enter one or more paths to test.');
      return;
    }
    try {
      const res = await fetch('/settings/path-mappings/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: lines })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      let results = [];
      if (Array.isArray(data)) results = data;
      else if (data && Array.isArray(data.results)) results = data.results;
      else if (data && Array.isArray(data.mapped)) results = data.mapped;
      else results = lines.map(s => ({ input: s, output: s, matched: false }));
      const norm = results.map(r => {
        if (typeof r === 'string') return { input: r, output: r, matched: false };
        const input = r.input ?? r.source ?? r.local ?? r.original ?? '';
        const output = r.output ?? r.result ?? r.plex ?? r.target ?? '';
        const matched = 'matched' in r ? !!r.matched : (input && output && input !== output);
        return { input, output, matched };
      });
      setMappingTestResults(norm);
    } catch (e) {
      alert('Failed to run test: ' + (e && e.message ? e.message : e));
    }
  };

  // === Genre Mapping helpers ===
  const parseGenreList = (input) => {
    try {
      return String(input || '')
        .split(/[\n,]/)
        .map(s => s.trim())
        .filter(Boolean);
    } catch {
      return [];
    }
  };

  const loadGenreMaps = async () => {
    setGenreMapsLoading(true);
    try {
      const res = await fetch(apiUrl('/genres/map'));
      const data = await safeJson(res);
      setGenreMaps(Array.isArray(data?.mappings) ? data.mappings : []);
    } catch (e) {
      console.error('Load genre maps error:', e);
      setGenreMaps([]);
    } finally {
      setGenreMapsLoading(false);
    }
  };

  const loadGenreSettings = async () => {
    try {
      const res = await fetch(apiUrl('/settings/genre'));
      const data = await safeJson(res);
      if (data && typeof data === 'object') {
        setGenreSettings(data);
      }
    } catch (err) {
      console.error('Load genre settings error:', err);
    }
  };

  const loadRecentGenreApplications = async () => {
    try {
      const res = await fetch(apiUrl('/genres/recent-applications'));
      const data = await safeJson(res);
      if (data && Array.isArray(data.applications)) {
        setRecentGenreApplications(data.applications);
      }
    } catch (err) {
      console.error('Load recent genre applications error:', err);
    }
  };

  const updateGenreSettings = async (updates) => {
    setGenreSettingsLoading(true);
    try {
      const params = new URLSearchParams();
      if (updates.genre_auto_apply !== undefined) {
        params.append('genre_auto_apply', updates.genre_auto_apply.toString());
      }
      if (updates.genre_priority_mode !== undefined) {
        params.append('genre_priority_mode', updates.genre_priority_mode);
      }
      if (updates.genre_override_ttl_seconds !== undefined) {
        params.append('genre_override_ttl_seconds', updates.genre_override_ttl_seconds.toString());
      }
      const res = await fetch(apiUrl('/settings/genre?' + params.toString()), {
        method: 'PUT'
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      await loadGenreSettings(); // Reload settings
      alert('Genre settings updated successfully!');
    } catch (err) {
      alert('Failed to update genre settings: ' + (err?.message || err));
    } finally {
      setGenreSettingsLoading(false);
    }
  };

  const cancelEditGenreMap = () => {
    setGmEditing(null);
    setGmForm({ genre: '', category_id: '' });
  };

  const submitGenreMap = async (e) => {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const genre = (gmForm.genre || '').trim();
    const cid = parseInt(gmForm.category_id, 10);
    if (!genre) {
      alert('Enter a Plex genre (e.g., Horror, Comedy)');
      return;
    }
    if (!cid || isNaN(cid)) {
      alert('Select a target category');
      return;
    }
    try {
      let res, text, data;
      if (gmEditing && gmEditing.id) {
        res = await fetch(apiUrl(`/genres/map/${gmEditing.id}`), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ genre, category_id: cid })
        });
        text = await res.text();
        try { data = text ? JSON.parse(text) : null; } catch {}
        if (!res.ok) throw new Error((data && (data.detail || data.message)) || text || `HTTP ${res.status}`);
        alert('Mapping updated.');
      } else {
        res = await fetch(apiUrl('/genres/map'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ genre, category_id: cid })
        });
        text = await res.text();
        try { data = text ? JSON.parse(text) : null; } catch {}
        if (!res.ok) throw new Error((data && (data.detail || data.message)) || text || `HTTP ${res.status}`);
        alert('Mapping created.');
      }
      cancelEditGenreMap();
      await loadGenreMaps();
    } catch (err) {
      alert('Failed to save mapping: ' + (err?.message || err));
    }
  };

  const editGenreMap = (m) => {
    try {
      setGmEditing(m);
      setGmForm({ genre: m?.genre || '', category_id: String(m?.category_id || '') });
    } catch {
      setGmEditing(m);
    }
  };

  const deleteGenreMap = async (mapId) => {
    if (!mapId) return;
    if (!window.confirm('Delete this genre mapping?')) return;
    try {
      const res = await fetch(apiUrl(`/genres/map/${mapId}`), { method: 'DELETE' });
      const data = await safeJson(res);
      if (!res.ok) throw new Error((data && (data.detail || data.message)) || `HTTP ${res.status}`);
      await loadGenreMaps();
    } catch (err) {
      alert('Failed to delete mapping: ' + (err?.message || err));
    }
  };

  const resolveGenresNow = async () => {
    const list = parseGenreList(genresTestInput);
    if (list.length === 0) {
      alert('Enter one or more genres to resolve.');
      return;
    }
    try {
      const res = await fetch(apiUrl('/genres/resolve'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genres: list })
      });
      const data = await safeJson(res);
      setGenresResolveResult(data);
      if (!res.ok) {
        alert('Resolve failed: ' + ((data && (data.detail || data.message)) || `HTTP ${res.status}`));
      }
    } catch (err) {
      alert('Resolve error: ' + (err?.message || err));
    }
  };

  const applyGenresNow = async () => {
    const list = parseGenreList(genresTestInput);
    if (list.length === 0) {
      alert('Enter one or more genres to apply.');
      return;
    }
    setGenresApplyLoading(true);
    try {
      const res = await fetch(apiUrl('/genres/apply'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genres: list })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }
      setGenresResolveResult(data);
      alert(`Applied category "${data?.category?.name || 'Unknown'}" for matched genre "${data?.matched_genre || list[0]}" to Plex.`);
      try { fetchData(); } catch {}
    } catch (err) {
      alert('Apply error: ' + (err?.message || err));
    } finally {
      setGenresApplyLoading(false);
    }
  };

  const applyGenreRow = async (genre) => {
    const g = String(genre || '').trim();
    if (!g) return;
    setGenresApplyLoading(true);
    try {
      const res = await fetch(apiUrl('/genres/apply'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genres: [g] })
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }
      alert(`Applied category "${data?.category?.name || 'Unknown'}" for matched genre "${data?.matched_genre || g}" to Plex.`);
      try { fetchData(); } catch {}
    } catch (err) {
      alert('Apply error: ' + (err?.message || err));
    } finally {
      setGenresApplyLoading(false);
    }
  };

  const submitMapRoot = async (applyNow) => {
    const root = (mapRootForm.root_path || '').trim();
    if (!root) { alert('Enter a root path'); return; }
    const cid = parseInt(mapRootForm.category_id, 10);
    if (!cid || isNaN(cid)) { alert('Select a category'); return; }

    const payload = {
      root_path: root,
      category_id: cid,
      recursive: !!mapRootForm.recursive,
      dry_run: !applyNow,
      generate_thumbnails: !!mapRootForm.generate_thumbnails
    };
    const exts = (mapRootForm.extensions || '')
      .split(/[,\s]+/)
      .map(s => s.trim().replace(/^\./, ''))
      .filter(Boolean);
    if (exts.length) payload.extensions = exts;
    const tagsStr = (mapRootForm.tags || '').trim();
    if (tagsStr) {
      const tagsArr = tagsStr.split(/[,\s]+/).map(s => s.trim()).filter(Boolean);
      if (tagsArr.length) payload.tags = tagsArr;
    }

    setMapRootLoading(true);
    setMapRootLoadingMsg(applyNow ? 'Mapping files… This may take a moment.' : 'Scanning files (dry run)…');

    try {
      const res = await fetch('/prerolls/map-root', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
        throw new Error(msg);
      }
      // Summarize counts based on backend response shape
      // Dry run: { total_found, already_present, to_add }
      // Apply:   { total_found, already_present, added, added_details[] }
      let message = '';
      if (data && data.dry_run) {
        const found = Number(data.total_found ?? 0);
        const present = Number(data.already_present ?? 0);
        const toAdd = Number(data.to_add ?? Math.max(0, found - present));
        message = `Dry run complete.\nFound: ${found}\nAlready present: ${present}\nWould add: ${toAdd}`;
      } else {
        const added = Number(data.added ?? (Array.isArray(data.added_details) ? data.added_details.length : 0));
        const found = Number(data.total_found ?? 0);
        const present = Number(data.already_present ?? 0);
        message = `Mapping complete.\nAdded: ${added}\nTotal found: ${found}\nAlready present: ${present}`;
      }
      alert(message);
      if (applyNow) {
        setMapRootForm(prev => ({ ...prev, dry_run: true }));
        fetchData();
      }
    } catch (e) {
      alert('Failed to map: ' + (e && e.message ? e.message : e));
    } finally {
      setMapRootLoading(false);
      setMapRootLoadingMsg('');
    }
  };

  // Auto-load mappings at startup
  React.useEffect(() => {
    try { loadPathMappings(); } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-load genre mappings and settings when opening Settings tab
  React.useEffect(() => {
    if (activeTab === 'settings') {
      try { loadGenreMaps(); loadGenreSettings(); } catch {}
    }
  }, [activeTab]);

  const renderSettings = () => (
    <div>
      <h1 className="header">Settings</h1>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Theme</h2>
        </summary>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem' }}>
          <span>Current theme: {darkMode ? 'Dark' : 'Light'}</span>
          <button onClick={toggleTheme} className="button">
            Switch to {darkMode ? 'Light' : 'Dark'} Mode
          </button>
        </div>
      </details>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Genre-based Preroll Mapping</h2>
        </summary>

        {/* Master Toggle */}
        <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={genreSettings.genre_auto_apply}
                onChange={(e) => updateGenreSettings({ genre_auto_apply: e.target.checked })}
                disabled={genreSettingsLoading}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>Enable Genre-based Preroll Mapping</span>
          </div>
          <p style={{ fontSize: '0.9rem', color: '#666', margin: 0 }}>
            <strong>⚠️ Experimental:</strong> This feature is experimental and currently only works with certain Plex clients. It requires Windows environment variables to be set for proper functionality.
          </p>
        </div>

        <p style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>
          Map Plex genres to NeXroll categories. When a user plays a movie with a matching genre, the mapped category's prerolls will be applied to Plex.
        </p>

        {/* Setup Directions */}
        <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Setup Instructions (Windows)</h3>
          <ol style={{ fontSize: '0.9rem', color: '#666', paddingLeft: '1.5rem', margin: 0 }}>
            <li>Ensure NeXroll is running on Windows (this feature is currently Windows-only).</li>
            <li>Click the "Apply Windows Env Variables" button below to set the required environment variables.</li>
            <li>Configure your Plex server URL and connect using one of the methods in the Plex tab.</li>
            <li>Create genre mappings below and enable automatic application.</li>
            <li>Test with a supported Plex client (e.g., Plex Web, Plex for Windows).</li>
          </ol>
          <div style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              className="button"
              onClick={() => {
                // Simulate applying env vars - in real implementation, this would call a backend endpoint
                alert('Windows environment variables applied successfully!\n\nNote: This is a placeholder. In the actual implementation, this would set PLEX_GENRE_MAPPING_ENABLED=true and other required variables.');
              }}
              style={{ backgroundColor: '#17a2b8' }}
            >
              🪟 Apply Windows Env Variables
            </button>
          </div>
        </div>

        <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', opacity: genreSettings.genre_auto_apply ? 1 : 0.5 }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Automatic Genre Application</h3>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                checked={genreSettings.genre_auto_apply}
                onChange={(e) => updateGenreSettings({ genre_auto_apply: e.target.checked })}
                disabled={genreSettingsLoading || !genreSettings.genre_auto_apply}
              />
              <span>Enable automatic genre-based preroll application</span>
            </label>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  checked={genreSettings.genre_priority_mode === 'genres_override'}
                  onChange={(e) => updateGenreSettings({ genre_priority_mode: e.target.checked ? 'genres_override' : 'schedules_override' })}
                  disabled={genreSettingsLoading || !genreSettings.genre_auto_apply}
                />
                <span style={{ fontWeight: 'bold' }}>Allow genres to override active schedules</span>
              </label>
              <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>
                When checked, genre prerolls will play even if a schedule is active. When unchecked, active schedules prevent genre prerolls (default behavior).
              </p>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 'bold' }}>Genre Override TTL (seconds):</label>
              <input
                type="number"
                min="1"
                max="300"
                value={genreSettings.genre_override_ttl_seconds}
                onChange={(e) => updateGenreSettings({ genre_override_ttl_seconds: parseInt(e.target.value, 10) || 10 })}
                disabled={genreSettingsLoading || !genreSettings.genre_auto_apply}
                style={{ padding: '0.5rem', width: '100px' }}
              />
              <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>
                How long (in seconds) to prevent re-applying the same genre preroll to the same media item. Lower values allow faster genre switching.
              </p>
            </div>
          </div>
        </div>

        <div className="nx-form-grid" style={{ marginBottom: '0.75rem', opacity: genreSettings.genre_auto_apply ? 1 : 0.5 }}>
          <div className="nx-field">
            <label className="nx-label">Plex Genre</label>
            <input
              className="nx-input"
              type="text"
              placeholder="e.g., Horror"
              value={gmForm.genre}
              onChange={(e) => setGmForm({ ...gmForm, genre: e.target.value })}
              disabled={!genreSettings.genre_auto_apply}
            />
          </div>
          <div className="nx-field">
            <label className="nx-label">Target Category</label>
            <select
              className="nx-select"
              value={gmForm.category_id}
              onChange={(e) => setGmForm({ ...gmForm, category_id: e.target.value })}
              disabled={!genreSettings.genre_auto_apply}
            >
              <option value="">Select category</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
          </div>
          <div className="nx-actions" style={{ alignItems: 'flex-end', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="button" onClick={submitGenreMap} disabled={!genreSettings.genre_auto_apply}>
              {gmEditing ? 'Update Mapping' : 'Create Mapping'}
            </button>
            {gmEditing && (
              <button type="button" className="button-secondary" onClick={cancelEditGenreMap} disabled={!genreSettings.genre_auto_apply}>
                Cancel
              </button>
            )}
          </div>
        </div>

        <div style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: genreSettings.genre_auto_apply ? 1 : 0.5 }}>
          <input
            className="nx-input"
            type="text"
            placeholder="Test genres (comma or newline separated, e.g., Horror, Thriller)"
            value={genresTestInput}
            onChange={(e) => setGenresTestInput(e.target.value)}
            disabled={!genreSettings.genre_auto_apply}
            style={{ flex: 1, minWidth: 280 }}
          />
          <button type="button" className="button" onClick={resolveGenresNow} disabled={!genreSettings.genre_auto_apply}>Resolve</button>
          <button
            type="button"
            className="button"
            onClick={applyGenresNow}
            disabled={genresApplyLoading || !genreSettings.genre_auto_apply}
            style={{ backgroundColor: '#28a745' }}
          >
            {genresApplyLoading ? 'Applying…' : 'Apply Now'}
          </button>
        </div>

        {genresResolveResult && (
          <div style={{ fontSize: '0.9rem', color: 'var(--text-color)', marginBottom: '0.75rem' }}>
            {genresResolveResult.matched ? (
              <span>
                Matched: <strong>{genresResolveResult.matched_genre}</strong> → Category: <strong>{genresResolveResult.category?.name}</strong> ({genresResolveResult.category?.plex_mode === 'playlist' ? 'Sequential' : 'Random'})
              </span>
            ) : (
              <span style={{ color: '#dc3545' }}>No mapping matched.</span>
            )}
          </div>
        )}

        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem', marginTop: '0.5rem', opacity: genreSettings.genre_auto_apply ? 1 : 0.5 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>Mappings</h3>
            <button type="button" className="button-secondary" onClick={loadGenreMaps} disabled={genreMapsLoading || !genreSettings.genre_auto_apply}>↻ Reload</button>
          </div>

          {genreMaps.length === 0 ? (
            <p style={{ fontSize: '0.9rem', color: '#666', fontStyle: 'italic' }}>
              {genreMapsLoading ? 'Loading…' : 'No mappings created yet.'}
            </p>
          ) : (
            <div style={{ display: 'grid', gap: '0.4rem', marginTop: '0.5rem' }}>
              {genreMaps.map(m => (
                <div
                  key={m.id}
                  style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '0.5rem', alignItems: 'center', border: '1px solid var(--border-color)', borderRadius: 6, padding: '0.4rem 0.6rem', background: 'var(--card-bg)' }}
                >
                  <div><strong>Genre:</strong> {m.genre}</div>
                  <div><strong>Category:</strong> {m.category?.name || (categories.find(c => c.id === m.category_id)?.name) || m.category_id}</div>
                  <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'flex-end' }}>
                    <button
                      type="button"
                      className="button"
                      title="Apply this mapping now"
                      onClick={() => applyGenreRow(m.genre)}
                      disabled={!genreSettings.genre_auto_apply}
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                    >
                      🎬 Apply
                    </button>
                    <button
                      type="button"
                      className="button"
                      title="Edit mapping"
                      onClick={() => editGenreMap(m)}
                      disabled={!genreSettings.genre_auto_apply}
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                    >
                      ✏️ Edit
                    </button>
                    <button
                      type="button"
                      className="button"
                      title="Delete mapping"
                      onClick={() => deleteGenreMap(m.id)}
                      disabled={!genreSettings.genre_auto_apply}
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', backgroundColor: '#dc3545' }}
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <details className="nx-plex-help" style={{ marginTop: '0.75rem' }}>
          <summary>Webhook/Automation</summary>
          <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.25rem' }}>
            Call GET <code>/genres/apply?genres=Horror,Thriller</code> when playback starts (e.g., via Tautulli webhook) to apply the mapped category to Plex automatically.
          </div>
        </details>
      </details>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>UNC/Local → Plex Path Mappings</h2>
        </summary>
        <p style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>
          Define how local or UNC paths should be translated to Plex-readable paths when applying prerolls.
          Longest-prefix rule applies; Windows local prefixes are matched case-insensitively.
        </p>

        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {(pathMappings || []).map((m, idx) => (
            <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Local/UNC Prefix (e.g., \\\\NAS\\share\\prerolls or C:\\Media\\Prerolls)"
                value={m.local}
                onChange={(e) => updateMappingRow(idx, 'local', e.target.value)}
                style={{ flex: 1, padding: '0.5rem' }}
              />
              <span style={{ fontWeight: 'bold' }}>→</span>
              <input
                type="text"
                placeholder="Plex Prefix (e.g., /mnt/NAS/prerolls or /Volumes/Media/Prerolls)"
                value={m.plex}
                onChange={(e) => updateMappingRow(idx, 'plex', e.target.value)}
                style={{ flex: 1, padding: '0.5rem' }}
              />
              <button
                type="button"
                className="button"
                onClick={() => removeMappingRow(idx)}
                style={{ backgroundColor: '#dc3545' }}
                title="Remove this mapping"
              >
                Remove
              </button>
            </div>
          ))}

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="button" onClick={addMappingRow}>➕ Add Row</button>
            <button type="button" className="button" onClick={loadPathMappings} disabled={pathMappingsLoading}>↻ Reload</button>
            <button type="button" className="button" onClick={savePathMappings} disabled={pathMappingsLoading} style={{ backgroundColor: '#28a745' }}>
              💾 Save
            </button>
          </div>
        </div>

        <div style={{ marginTop: '0.75rem' }}>
          <h3 style={{ margin: 0, marginBottom: '0.25rem' }}>Test Translation</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
            Paste one or more local/UNC paths below to preview their translated Plex paths.
          </p>
          <textarea
            rows="4"
            value={mappingTestInput}
            onChange={(e) => setMappingTestInput(e.target.value)}
            placeholder={`Example:
\\\\NAS\\share\\prerolls\\winter\\snow.mp4
C:\\\\Media\\\\Prerolls\\\\summer\\\\beach.mp4`}
            style={{ width: '100%', padding: '0.5rem', resize: 'vertical' }}
          />
          <div style={{ marginTop: '0.5rem' }}>
            <button type="button" className="button" onClick={runMappingsTest}>🧪 Run Test</button>
          </div>
          {Array.isArray(mappingTestResults) && mappingTestResults.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <ul style={{ margin: 0, paddingLeft: '1rem' }}>
                {mappingTestResults.map((r, i) => (
                  <li key={i} style={{ fontSize: '0.9rem', color: r.matched ? 'green' : '#555' }}>
                    <code>{r.input}</code> → <code>{r.output || '(no change)'}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>


      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Backup & Restore</h2>
        </summary>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Create backups of your NeXroll data and restore from previous backups.
        </p>

        <div style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Database Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Export all schedules, categories, and preroll metadata to JSON
            </p>
            <button onClick={handleBackupDatabase} className="button">
              📥 Download Database Backup
            </button>
          </div>

          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Files Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Export all preroll video files and thumbnails to ZIP
            </p>
            <button onClick={handleBackupFiles} className="button">
              📦 Download Files Backup
            </button>
          </div>

          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Restore from Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Select a backup file to restore (JSON for database, ZIP for files)
            </p>
            <input
              type="file"
              onChange={(e) => setBackupFile(e.target.files[0])}
              accept=".json,.zip"
              style={{ marginBottom: '0.5rem' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleRestoreDatabase}
                className="button"
                disabled={!backupFile || !backupFile.name.endsWith('.json')}
              >
                🔄 Restore Database
              </button>
              <button
                onClick={handleRestoreFiles}
                className="button"
                disabled={!backupFile || !backupFile.name.endsWith('.zip')}
              >
                📂 Restore Files
              </button>
            </div>
          </div>
        </div>
        </details>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Community Templates</h2>
        </summary>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Browse and import community-created schedule templates, or create your own to share.
        </p>

        <div style={{ marginBottom: '1rem' }}>
          <button onClick={handleInitTemplates} className="button" style={{ marginRight: '0.5rem' }}>
            🔄 Load Default Templates
          </button>
          <button onClick={handleCreateTemplate} className="button">
            ➕ Create Template from Schedules
          </button>
        </div>

        {/* Schedule Selection for Template Creation */}
        {schedules.length > 0 && (
          <div style={{ marginBottom: '1rem', padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>Select Schedules for Template:</h3>
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              {schedules.map(schedule => (
                <label key={schedule.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={selectedSchedules.includes(schedule.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedSchedules([...selectedSchedules, schedule.id]);
                      } else {
                        setSelectedSchedules(selectedSchedules.filter(id => id !== schedule.id));
                      }
                    }}
                  />
                  <span>{schedule.name} ({schedule.type})</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Available Templates */}
        <div style={{ display: 'grid', gap: '1rem' }}>
          <h3>Available Templates:</h3>
          {communityTemplates.length === 0 ? (
            <p style={{ color: '#666', fontStyle: 'italic' }}>No templates available. Click "Load Default Templates" to get started.</p>
          ) : (
            communityTemplates.map(template => (
              <div key={template.id} style={{
                border: '1px solid var(--border-color)',
                padding: '1rem',
                borderRadius: '0.25rem',
                backgroundColor: 'var(--card-bg)'
              }}>
                <h4 style={{ marginBottom: '0.5rem' }}>{template.name}</h4>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                  {template.description}
                </p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: '#666' }}>
                  <span>By: {template.author} | Category: {template.category}</span>
                  <span>Downloads: {template.downloads} | Rating: {template.rating}/5</span>
                </div>
                <div style={{ marginTop: '0.5rem' }}>
                  <button
                    onClick={() => handleImportTemplate(template.id)}
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.75rem' }}
                  >
                    📥 Import Template
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </details>

      <div className="card">
        <h2>System Information</h2>
        <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.9rem' }}>
          <div><strong>Prerolls:</strong> {prerolls.length}</div>
          <div><strong>Categories:</strong> {categories.length}</div>
          <div><strong>Schedules:</strong> {schedules.length}</div>
          <div><strong>Holiday Presets:</strong> {holidayPresets.length}</div>
          <div><strong>Community Templates:</strong> {communityTemplates.length}</div>
          <div><strong>Scheduler Status:</strong> {schedulerStatus.running ? 'Running' : 'Stopped'}</div>
          <div><strong>Theme:</strong> {darkMode ? 'Dark' : 'Light'}</div>
          <div><strong>Version (API):</strong> {systemVersion?.api_version || 'unknown'}</div>
          <div><strong>Version (Installed):</strong> {systemVersion?.registry_version || 'n/a'}</div>
          {systemVersion?.install_dir && <div><strong>Install Dir:</strong> {systemVersion.install_dir}</div>}
          <div><strong>FFmpeg:</strong> {ffmpegInfo ? (ffmpegInfo.ffmpeg_present ? ffmpegInfo.ffmpeg_version : 'Not found') : 'Detecting...'}</div>
          <div><strong>FFprobe:</strong> {ffmpegInfo ? (ffmpegInfo.ffprobe_present ? ffmpegInfo.ffprobe_version : 'Not found') : 'Detecting...'}</div>
        </div>
        <div style={{ marginTop: '0.75rem' }}>
          <button onClick={recheckFfmpeg} className="button">🔎 Re-check FFmpeg</button>
          <button onClick={handleShowSystemPaths} className="button" style={{ marginLeft: '0.5rem' }}>📂 Show Resolved Paths</button>
          <button onClick={handleDownloadDiagnostics} className="button" style={{ marginLeft: '0.5rem' }}>🧰 Download Diagnostics</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="app-container">
      {/* Tab Navigation with right-aligned logo */}
      <div
        className="tab-buttons"
        style={{ alignItems: 'center', justifyContent: 'space-between', padding: '0 0.5rem' }}
      >
        <div className="tab-group">
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`tab-button ${activeTab === 'schedules' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedules')}
          >
            Schedules
          </button>
          <button
            className={`tab-button ${activeTab === 'categories' ? 'active' : ''}`}
            onClick={() => setActiveTab('categories')}
          >
            Categories
          </button>
          <button
            className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            Settings
          </button>
          <button
            className={`tab-button ${activeTab === 'plex' ? 'active' : ''}`}
            onClick={() => setActiveTab('plex')}
          >
            Plex
          </button>
        </div>
        <div className="tabbar-right" style={{ display: 'flex', alignItems: 'center', paddingRight: '48px' }}>
          <a href="https://github.com/JFLXCLOUD/NeXroll" target="_blank" rel="noopener noreferrer">
            <img
              src={darkMode ? "/NeXroll_Logo_WHT.png" : "/NeXroll_Logo_BLK.png"}
              alt="NeXroll Logo"
              style={{ height: '50px', width: 'auto', display: 'block' }}
            />
          </a>
        </div>
      </div>

      {showUpdateBanner && updateInfo && (
        <div
          className="nx-update-banner"
          style={{
            backgroundColor: 'var(--card-bg)',
            border: '1px solid var(--border-color)',
            padding: '0.5rem 0.75rem',
            borderRadius: '0.375rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.5rem',
            margin: '0.5rem 0'
          }}
        >
          <div style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
            New release available: <strong>v{updateInfo.version}</strong>
            <a
              href={updateInfo.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ marginLeft: '0.5rem', textDecoration: 'underline' }}
              title="View the latest release on GitHub"
            >
              View on GitHub
            </a>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              type="button"
              className="button-secondary"
              onClick={handleDismissUpdate}
              style={{ fontSize: '0.8rem' }}
              title="Dismiss update notice"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Install banner hidden for now - functionality preserved for future use */}
      {false && showInstallPrompt && !isInstalled && (
        <div
          className="nx-install-banner"
          style={{
            backgroundColor: '#e3f2fd',
            border: '1px solid #2196f3',
            padding: '0.75rem 1rem',
            borderRadius: '0.375rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            margin: '0.5rem 0'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>📱</span>
            <div>
              <div style={{ fontWeight: 'bold', color: '#1976d2', marginBottom: '0.25rem' }}>
                Install NeXroll
              </div>
              <div style={{ fontSize: '0.9rem', color: '#424242' }}>
                Install as an app for quick access and offline functionality
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              type="button"
              className="button"
              onClick={handleInstallPWA}
              style={{
                backgroundColor: '#2196f3',
                fontSize: '0.9rem',
                padding: '0.5rem 1rem'
              }}
              title="Install NeXroll as a PWA"
            >
              Install
            </button>
            <button
              type="button"
              className="button-secondary"
              onClick={dismissInstallPrompt}
              style={{ fontSize: '0.8rem' }}
              title="Dismiss install prompt"
            >
              Not now
            </button>
          </div>
        </div>
      )}

     <div className="dashboard">
        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'schedules' && renderSchedules()}
        {activeTab === 'categories' && renderCategories()}
        {activeTab === 'settings' && renderSettings()}
        {activeTab === 'plex' && renderPlex()}
      </div>
      <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: '#666', textAlign: 'center' }}>
        NeXroll {systemVersion?.registry_version ? `v${systemVersion.registry_version}` : (systemVersion?.api_version ? `v${systemVersion.api_version}` : '')}
      </div>
    </div>
  );
}

export default App;
