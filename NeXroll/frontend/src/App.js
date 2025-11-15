import React, { useState, useEffect, useRef, useCallback } from 'react';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import ReactMarkdown from 'react-markdown';
import RetroProgressBar from './components/RetroProgressBar';

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
  
// Version helpers (module-scope) - stable across renders
const normalizeVersionString = (input) => {
  try {
    if (!input) return '0.0.0';
    let s = String(input).trim();
    s = s.replace(/^v+/i, '');
    s = s.replace(/[_-]/g, '.');
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

const Modal = ({ title, onClose, children, width = 700, zIndex = 1000, allowBackgroundInteraction = false }) => {
  React.useEffect(() => {
    const onEsc = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    document.addEventListener('keydown', onEsc);
    return () => document.removeEventListener('keydown', onEsc);
  }, [onClose]);

  return (
    <div 
      className="nx-modal-overlay" 
      style={{ 
        zIndex, 
        pointerEvents: allowBackgroundInteraction ? 'none' : 'auto',
        backgroundColor: allowBackgroundInteraction ? 'transparent' : undefined
      }} 
      onClick={(e) => { if (e.target.classList.contains('nx-modal-overlay')) onClose && onClose(); }}
    >
      <div className="nx-modal" style={{ maxWidth: width, position: 'relative', zIndex: 1, pointerEvents: 'auto' }} onClick={(e) => e.stopPropagation()}>
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
  console.log('App component rendering');
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
  const [previewingPreroll, setPreviewingPreroll] = useState(null);

  // Debug: Log when previewingPreroll state changes
  React.useEffect(() => {
    console.log('previewingPreroll state changed to:', previewingPreroll);
  }, [previewingPreroll]);
  // Media server selection for Connect page
  const [activeServer, setActiveServer] = useState(() => {
    try { return localStorage.getItem('activeServer') || 'plex'; } catch { return 'plex'; }
  });
  useEffect(() => {
    try { localStorage.setItem('activeServer', activeServer); } catch {}
  }, [activeServer]);

  // Jellyfin connection UI state
  const [jellyfinStatus, setJellyfinStatus] = useState('Disconnected');
  const [jellyfinServerInfo, setJellyfinServerInfo] = useState(null);
  const [jellyfinConfig, setJellyfinConfig] = useState({
    url: '',
    api_key: ''
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
  const [activeCategory, setActiveCategory] = useState(null);
  
  // Changelog modal state
  const [showChangelogModal, setShowChangelogModal] = useState(false);
  const [changelogContent, setChangelogContent] = useState('');
  const [changelogCurrentVersion, setChangelogCurrentVersion] = useState('');
  
  // Community Prerolls UI state
  const [communityFairUseStatus, setCommunityFairUseStatus] = useState(null);
  const [communityPolicyText, setCommunityPolicyText] = useState(null);
  const [communitySearchQuery, setCommunitySearchQuery] = useState('');
  const [communitySearchCategory, setCommunitySearchCategory] = useState('');
  const [communitySearchPlatform, setCommunitySearchPlatform] = useState('');
  const [communitySearchResults, setCommunitySearchResults] = useState([]);
  const [communityIsSearching, setCommunityIsSearching] = useState(false);
  const [communityIsDownloading, setCommunityIsDownloading] = useState({});
  const [communityBuildProgress, setCommunityBuildProgress] = useState(null);
  const [communitySelectedCategory, setCommunitySelectedCategory] = useState(null);
  const [communityShowAddToCategory, setCommunityShowAddToCategory] = useState({});
  const [communityResultLimit, setCommunityResultLimit] = useState(50);
  const [communityTotalResults, setCommunityTotalResults] = useState(0);
  const [communityPreviewingPreroll, setCommunityPreviewingPreroll] = useState(null);
  const [communityTop5Prerolls, setCommunityTop5Prerolls] = useState([]);
  const [communityRandomPreroll, setCommunityRandomPreroll] = useState(null);
  const [communityIsLoadingRandom, setCommunityIsLoadingRandom] = useState(false);
  const [communityIsLoadingTop5, setCommunityIsLoadingTop5] = useState(false);
  const [communityLatestPrerolls, setCommunityLatestPrerolls] = useState([]);
  const [communityIsLoadingLatest, setCommunityIsLoadingLatest] = useState(false);
  // Rename preroll before download
  const [communityRenamingPreroll, setCommunityRenamingPreroll] = useState(null);
  const [communityNewPrerollName, setCommunityNewPrerollName] = useState('');
  // Index status for local fast search
  const [communityIndexStatus, setCommunityIndexStatus] = useState(null);
  const [communityIsBuilding, setCommunityIsBuilding] = useState(false);
  // Downloaded community preroll IDs (for marking as "Downloaded")
  const [downloadedCommunityIds, setDownloadedCommunityIds] = useState([]);
  // Migration state
  const [communityIsMigrating, setCommunityIsMigrating] = useState(false);
  const [communityMigrationResult, setCommunityMigrationResult] = useState(null);
  const [communityMigrationProgress, setCommunityMigrationProgress] = useState(null);
  const [communityMatchedCount, setCommunityMatchedCount] = useState(0);
  
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

  // Timezone settings state
  const [currentTimezone, setCurrentTimezone] = useState('UTC');
  const [availableTimezones, setAvailableTimezones] = useState([]);
  const [timezoneLoading, setTimezoneLoading] = useState(false);
  const [timezoneSaving, setTimezoneSaving] = useState(false);

// Genre mapping UI state
const [genreMaps, setGenreMaps] = useState([]);
const [genreMapsLoading, setGenreMapsLoading] = useState(false);
const [gmForm, setGmForm] = useState({ genre: '', category_id: '' });
const [gmEditing, setGmEditing] = useState(null);
const [genresTestInput, setGenresTestInput] = useState('');
const [genresResolveResult, setGenresResolveResult] = useState(null);
const [genresApplyLoading, setGenresApplyLoading] = useState(false);
const [genreSettingsCollapsed, setGenreSettingsCollapsed] = useState(true); // Collapsed by default
const [genreSettings, setGenreSettings] = useState({
genre_auto_apply: true,
genre_priority_mode: 'schedules_override',
genre_override_ttl_seconds: 10
});
const [recentGenreApplications, setRecentGenreApplications] = useState([]);
const [genreSettingsLoading, setGenreSettingsLoading] = useState(false);
const [applyingToServer, setApplyingToServer] = useState(false);
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
const [calendarMode, setCalendarMode] = useState('year'); // 'month' | 'week' | 'year' - default to year view
const [calendarMonthView, setCalendarMonthView] = useState('grid'); // 'grid' | 'timeline' - default to grid view
const [calendarWeekStart, setCalendarWeekStart] = useState(() => {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day; // Get to Sunday
  return new Date(d.getFullYear(), d.getMonth(), diff);
});

// Date/time helpers: treat backend datetimes as UTC and format for local display/inputs
const ensureUtcIso = (s) => {
  if (!s || typeof s !== 'string') return s;
  // Check if already has timezone info (Z, +offset, or -offset)
  // Must check for timezone offset pattern to avoid matching negative years or times
  const hasTimezone = s.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(s);
  return hasTimezone ? s : (s + 'Z');
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
    fallback_category_id: '',
    color: ''
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
  const [inputTagsValue, setInputTagsValue] = useState(''); // Local state for immediate input feedback

  // Keep latest filter values for stable fetchData callback
  const filterCategoryRef = React.useRef(filterCategory);
  const filterTagsRef = React.useRef(filterTags);
  React.useEffect(() => { filterCategoryRef.current = filterCategory; }, [filterCategory]);
  React.useEffect(() => { filterTagsRef.current = filterTags; }, [filterTags]);

  // Debounce hook for tag search (300ms delay to reduce unnecessary state updates)
  const filterTagsDebounceRef = useRef(null);
  
  const handleTagsChange = useCallback((value) => {
    // Show typed value immediately in input
    setInputTagsValue(value);
    
    // Clear any existing debounce timer
    if (filterTagsDebounceRef.current) {
      clearTimeout(filterTagsDebounceRef.current);
    }
    
    // Set a new debounce timer (300ms) before updating filter state
    filterTagsDebounceRef.current = setTimeout(() => {
      setFilterTags(value);
    }, 300);
  }, []);

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

  // Helper function to handle fetch errors with proper error message extraction
  const handleFetchResponse = async (response) => {
    if (!response.ok) {
      try {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      } catch (e) {
        if (e.message && e.message !== `HTTP error! status: ${response.status}`) {
          throw e;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    }
    return response.json();
  };

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

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil((prerolls || []).length / pageSize));
    setCurrentPage(prev => Math.min(prev, totalPages));
  }, [prerolls, pageSize]);

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
  // moved version helpers to module scope for stable callbacks

  const checkForUpdates = React.useCallback(async (installedVersion) => {
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
  }, [compareVersions, extractVersionFromRelease, normalizeVersionString]);

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

  // === Timezone settings helpers (must be before useEffect) ===
  const loadTimezone = React.useCallback(async () => {
    setTimezoneLoading(true);
    try {
      const res = await fetch(apiUrl('/settings/timezone'));
      const data = await safeJson(res);
      if (data && data.timezone) {
        setCurrentTimezone(data.timezone);
      }
    } catch (e) {
      console.error('Load timezone error:', e);
      setCurrentTimezone('UTC');
    } finally {
      setTimezoneLoading(false);
    }
  }, []);

  const loadAvailableTimezones = React.useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/settings/timezones'));
      const data = await safeJson(res);
      if (data && Array.isArray(data.timezones)) {
        setAvailableTimezones(data.timezones);
      }
    } catch (e) {
      console.error('Load available timezones error:', e);
      setAvailableTimezones([]);
    }
  }, []);

  const saveTimezone = async (tz) => {
    setTimezoneSaving(true);
    try {
      const res = await fetch(apiUrl('/settings/timezone'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timezone: tz })
      });
      const data = await safeJson(res);
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setCurrentTimezone(tz);
      alert('Timezone updated successfully!');
    } catch (e) {
      console.error('Save timezone error:', e);
      alert('Failed to update timezone: ' + (e?.message || e));
    } finally {
      setTimezoneSaving(false);
    }
  };

  // eslint-disable-next-line no-use-before-define
  const fetchData = React.useCallback(() => {
    const fc = String(filterCategoryRef.current || '');
    const ft = String(filterTagsRef.current || '');
    // Fetch all data
    Promise.all([
      fetch('http://localhost:9393/plex/status'),
      fetch('http://localhost:9393/jellyfin/status'),
      fetch(`http://localhost:9393/prerolls?category_id=${fc}&search=${ft}`),
      fetch('http://localhost:9393/schedules'),
      fetch('http://localhost:9393/categories'),
      fetch('http://localhost:9393/holiday-presets'),
      fetch('http://localhost:9393/scheduler/status'),
      fetch('http://localhost:9393/tags'),
      fetch('http://localhost:9393/community-templates'),
      fetch('http://localhost:9393/plex/stable-token/status'),
      fetch('http://localhost:9393/system/version'),
      fetch('http://localhost:9393/system/ffmpeg-info'),
      fetch('http://localhost:9393/genres/recent-applications'),
      fetch('http://localhost:9393/settings/active-category')
    ]).then(responses => Promise.all(responses.map(safeJson)))
      .then(([plex, jellyfin, prerolls, schedules, categories, holidays, scheduler, tags, templates, stableToken, sysVersion, ffmpeg, recentGenreApps, activeCat]) => {
        setPlexStatus(plex.connected ? 'Connected' : 'Disconnected');
        setPlexServerInfo(plex);
        setJellyfinStatus(jellyfin.connected ? 'Connected' : 'Disconnected');
        setJellyfinServerInfo(jellyfin);
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
        // Debug: Log active category response
        console.log('Active category API response:', activeCat);
        console.log('Full response details:', JSON.stringify(activeCat));
        if (activeCat?.__error) {
          console.warn('Active category API error:', activeCat.status);
          setActiveCategory(null);
        } else if (activeCat?.active_category) {
          console.log('Setting active category to:', activeCat.active_category);
          setActiveCategory(activeCat.active_category);
        } else {
          console.warn('Active category response missing active_category property');
          setActiveCategory(null);
        }
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
        setActiveCategory(null);
      });
  }, []);

  // Check for changelog on first load
  useEffect(() => {
    const checkChangelog = async () => {
      try {
        const response = await fetch('http://localhost:9393/system/changelog');
        const data = await response.json();
        
        if (data.show_changelog && data.changelog) {
          setChangelogContent(data.changelog);
          setChangelogCurrentVersion(data.current_version);
          setShowChangelogModal(true);
        }
      } catch (err) {
        console.error('Failed to check changelog:', err);
      }
    };
    
    // Check changelog after a short delay to let the app load
    setTimeout(checkChangelog, 1000);
  }, []);

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
  }, [fetchData]);

  // Check GitHub for latest release once system version is known
  useEffect(() => {
    if (!systemVersion) return;
    const installed = normalizeVersionString(
      (systemVersion.registry_version || systemVersion.api_version || '').toString()
    );
    checkForUpdates(installed);
  }, [systemVersion, checkForUpdates]);

  // Load timezone settings on component mount
  useEffect(() => {
    loadTimezone();
    loadAvailableTimezones();
  }, [loadTimezone, loadAvailableTimezones]);

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
 
  // Check Community Prerolls Fair Use status when tab is active
  useEffect(() => {
    if (activeTab === 'community-prerolls' && communityFairUseStatus === null) {
      const checkFairUseStatus = async () => {
        try {
          console.log('Checking Community Fair Use status...');
          const response = await fetch(apiUrl('community-prerolls/fair-use/status'));
          const data = await response.json();
          console.log('Fair Use status response:', data);
          setCommunityFairUseStatus(data);
          
          // If not accepted, fetch the policy text
          if (!data.accepted) {
            console.log('Not accepted - fetching policy text...');
            try {
              const policyResponse = await fetch(apiUrl('community-prerolls/fair-use-policy'));
              const policyData = await policyResponse.json();
              console.log('Policy text fetched, length:', policyData.policy?.length);
              setCommunityPolicyText(policyData.policy);
            } catch (policyError) {
              console.error('Failed to fetch policy text:', policyError);
            }
          } else {
            // If accepted, load Top 5 prerolls and index status
            console.log('Fair Use accepted - loading Top 5 prerolls...');
            
            try {
              console.log('About to call loadTop5Prerolls');
              loadTop5Prerolls();
              console.log('After loadTop5Prerolls');
            } catch (e) {
              console.error('Error calling loadTop5Prerolls:', e);
            }
            
            try {
              console.log('About to call loadLatestPrerolls');
              loadLatestPrerolls();
              console.log('After loadLatestPrerolls');
            } catch (e) {
              console.error('Error calling loadLatestPrerolls:', e);
            }
            
            try {
              console.log('About to call loadDownloadedCommunityIds');
              loadDownloadedCommunityIds();
              console.log('After loadDownloadedCommunityIds');
            } catch (e) {
              console.error('Error calling loadDownloadedCommunityIds:', e);
            }
            
            // Load index status for fast search feature (inline to avoid hoisting issues)
            console.log('About to load index status...');
            (async () => {
              try {
                console.log('Inside async IIFE - Loading index status...');
                const indexResponse = await fetch(apiUrl('community-prerolls/index-status'));
                console.log('Index status response status:', indexResponse.status);
                const indexData = await indexResponse.json();
                console.log('Index status data:', indexData);
                setCommunityIndexStatus(indexData);
                console.log('Index status state set!');
              } catch (indexError) {
                console.error('Failed to load index status:', indexError);
              }
            })();
            console.log('After defining async IIFE');
          }
        } catch (error) {
          console.error('Failed to check Community Fair Use status:', error);
          setCommunityFairUseStatus({ accepted: false, accepted_at: null });
        }
      };
      
      checkFairUseStatus();
    }
  }, [activeTab, communityFairUseStatus]);

  // Function to load Top 5 prerolls
  const loadTop5Prerolls = async () => {
    if (communityTop5Prerolls.length > 0) return; // Already loaded
    
    setCommunityIsLoadingTop5(true);
    try {
      const response = await fetch(apiUrl('community-prerolls/top5'));
      const data = await response.json();
      
      if (data.found && data.results) {
        setCommunityTop5Prerolls(data.results);
      }
    } catch (error) {
      console.error('Failed to load Top 5 prerolls:', error);
    } finally {
      setCommunityIsLoadingTop5(false);
    }
  };

  // Function to load downloaded community preroll IDs
  const loadDownloadedCommunityIds = async () => {
    try {
      const response = await fetch(apiUrl('community-prerolls/downloaded-ids'));
      const data = await response.json();
      
      if (data.downloaded_ids) {
        setDownloadedCommunityIds(data.downloaded_ids);
        // Update the matched count (IDs with community_preroll_id)
        setCommunityMatchedCount(data.downloaded_ids.length);
      }
    } catch (error) {
      console.error('Failed to load downloaded community IDs:', error);
    }
  };

  // Function to load Latest prerolls for Discovery section
  const loadLatestPrerolls = async () => {
    if (communityLatestPrerolls.length > 0) return; // Already loaded
    
    setCommunityIsLoadingLatest(true);
    try {
      const response = await fetch(apiUrl('community-prerolls/latest?limit=6'));
      const data = await response.json();
      
      if (data.found && data.results) {
        setCommunityLatestPrerolls(data.results);
      }
    } catch (error) {
      console.error('Failed to load latest prerolls:', error);
    } finally {
      setCommunityIsLoadingLatest(false);
    }
  };
 
  // fetchData moved above initial effect

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
      playlist: scheduleForm.playlist,
      color: scheduleForm.color || null
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
          category_id: '', shuffle: false, playlist: false, fallback_category_id: '', color: ''
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
          
          // Immediately update the active category in the UI
          const appliedCategory = categories.find(cat => cat.id === categoryId);
          if (appliedCategory) {
            setActiveCategory(appliedCategory);
            console.log(`[DEBUG] Immediately set activeCategory to: ${appliedCategory.name}`);
          }
          
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

    // Jellyfin Category Apply/Remove (real apply via Local Intros plugin)
    const handleApplyCategoryToJellyfin = async (categoryId, categoryName) => {
      if (jellyfinStatus !== 'Connected') {
        alert('Jellyfin is not connected.');
        return;
      }
      setApplyingToServer(true);
      try {
        const res = await fetch(apiUrl(`/categories/${categoryId}/apply-to-jellyfin`), { method: 'POST' });
        const text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch {}
  
        if (!res.ok) {
          const msg = (data && (data.detail || data.message)) || text || `HTTP ${res.status}`;
          throw new Error(msg);
        }
  
        const plan = (data && data.plan) || null;
        const applied = !!(data && data.applied);
        const supported = (data && data.supported);
        const message = (data && data.message) || '';
        const details = (data && data.details) || null;
  
        if (applied) {
          const cnt = (details && typeof details.value_count === 'number')
            ? details.value_count
            : (plan && Array.isArray(plan.translated_paths) ? plan.translated_paths.length : 0);
          const pluginName = (details && details.plugin && (details.plugin.name || details.plugin.Name)) || 'Local Intros';
          const updatedKey = details && details.updated_key ? ` (${details.updated_key})` : '';
          const previewList = ((details && Array.isArray(details.paths_preview) ? details.paths_preview : (plan?.translated_paths || [])) || [])
            .slice(0, 5).join('\n');
  
          alert(
            `Applied to Jellyfin: "${categoryName}".\n` +
            `${message || `Injected ${cnt} folder${cnt === 1 ? '' : 's'} into ${pluginName}${updatedKey}.`}` +
            (previewList ? `\n\nPreview:\n${previewList}` : '')
          );
          
          // Immediately update the active category in the UI
          const appliedCategory = categories.find(cat => cat.id === categoryId);
          if (appliedCategory) {
            setActiveCategory(appliedCategory);
            console.log(`[DEBUG] Immediately set activeCategory to: ${appliedCategory.name}`);
          }
          
          try { fetchData(); } catch {}
          return;
        }
  
        // Not applied; show concise status with plan preview fallback
        const planCount = plan && Array.isArray(plan.translated_paths) ? plan.translated_paths.length : 0;
        const previewList = plan ? (plan.translated_paths || []).slice(0, 5).join('\n') : '';
        const header = supported === false ? 'Jellyfin apply not completed' : 'Jellyfin status';

        // Copy paths to clipboard for manual configuration
        if (previewList) {
          navigator.clipboard.writeText(previewList).catch(err => console.warn('Failed to copy to clipboard:', err));
        }

        alert(
          `${header}: ${message || 'Operation did not change plugin configuration. Paths copied to clipboard for manual configuration in Jellyfin Local Intros plugin.'}` +
          (plan ? `\nItems: ${planCount}` : '') +
          (previewList ? `\n\nPreview:\n${previewList}` : '')
        );
      } catch (e) {
        alert('Failed to apply to Jellyfin: ' + (e && e.message ? e.message : e));
      } finally {
        setApplyingToServer(false);
      }
    };


  // Determine which server is actively connected (enforce single-server UX)
  const getActiveConnectedServer = () => {
    const plexConnected = plexStatus === 'Connected';
    const jellyConnected = jellyfinStatus === 'Connected';
    if (plexConnected && !jellyConnected) return 'plex';
    if (!plexConnected && jellyConnected) return 'jellyfin';
    if (plexConnected && jellyConnected) return 'conflict';
    return null;
  };

  const handleApplyCategoryToActiveServer = (categoryId, categoryName) => {
    const server = getActiveConnectedServer();
    if (server === 'plex') {
      return handleApplyCategoryToPlex(categoryId, categoryName);
    }
    if (server === 'jellyfin') {
      return handleApplyCategoryToJellyfin(categoryId, categoryName);
    }
    if (server === 'conflict') {
      alert('Both Plex and Jellyfin are connected. Only one media server connection is allowed. Disconnect one on the Connect tab, then try again.');
      return;
    }
    alert('No media server connected. Connect to Plex or Jellyfin first.');
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
          .then(res => {
            if (!res.ok) {
              return res.json().then(error => {
                throw new Error(error.detail || `HTTP ${res.status}: Restore failed`);
              });
            }
            return res.json();
          })
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
      .then(handleFetchResponse)
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
      fallback_category_id: schedule.fallback_category_id || '',
      color: schedule.color || ''
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
      playlist: scheduleForm.playlist,
      color: scheduleForm.color || null
    };
    if (scheduleForm.fallback_category_id) {
      scheduleData.fallback_category_id = parseInt(scheduleForm.fallback_category_id);
    }

    fetch(`http://localhost:9393/schedules/${editingSchedule.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(handleFetchResponse)
      .then(data => {
        alert('Schedule updated successfully!');
        setEditingSchedule(null);
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: false, playlist: false, fallback_category_id: '', color: ''
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
      .then(handleFetchResponse)
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
      display_name: preroll.display_name || preroll.filename || '',
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
      .then(handleFetchResponse)
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
          // Try to extract error detail from response
          return res.json().then(errData => {
            throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
          }).catch(() => {
            throw new Error(`HTTP error! status: ${res.status}`);
          });
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

      const server = getActiveConnectedServer();
      if (server === 'plex') {
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
      } else if (server === 'jellyfin') {
        await handleApplyCategoryToJellyfin(idToApply, nameToApply);
        setEditingCategory(null);
        setNewCategory({ name: '', description: '' });
        try { fetchData(); } catch {}
      } else if (server === 'conflict') {
        alert('Saved. Both Plex and Jellyfin are connected. Disconnect one on the Connect tab, then apply from the category card.');
        setEditingCategory(null);
        setNewCategory({ name: '', description: '' });
      } else {
        alert('Saved. No media server is connected. Connect on the Connect tab, then use "Apply to Server" on the category.');
        setEditingCategory(null);
        setNewCategory({ name: '', description: '' });
      }
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
// === Dashboard Customization (Drag &amp; Drop, 4x2 grid) ===
const DASH_KEYS = ["servers","prerolls","storage","schedules","scheduler","current_category","upcoming"];

const [dashLayout, setDashLayout] = useState({
  grid: { cols: 4, rows: 2 },
  order: DASH_KEYS.slice(),
  hidden: [],
  locked: false
});
const [dashSaving, setDashSaving] = useState(false);

const visibleOrder = React.useMemo(
  () => (dashLayout?.order || DASH_KEYS),
  [dashLayout]
);

const dashSensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

const loadDashLayout = React.useCallback(async () => {
  try {
    // Try loading from localStorage first (primary storage)
    const stored = localStorage.getItem('dashLayout');
    if (stored) {
      try {
        const data = JSON.parse(stored);
        if (data && data.grid && Array.isArray(data.order)) {
          setDashLayout(data);
          return;
        }
      } catch (e) {
        console.warn('Failed to parse stored dashboard layout:', e);
      }
    }
  } catch {}

  // Fall back to backend if localStorage is empty or corrupted
  try {
    const res = await fetch(apiUrl('/settings/dashboard-layout'));
    const data = await safeJson(res);
    if (data && data.grid && Array.isArray(data.order)) {
      const cols = Math.max(1, Math.min(8, parseInt(data.grid.cols || 4, 10) || 4));
      const rows = Math.max(1, Math.min(8, parseInt(data.grid.rows || 2, 10) || 2));
      const capacity = cols * rows;
      const canonical = DASH_KEYS.slice();
      const order = (data.order || [])
        .map(String)
        .filter(k => canonical.includes(k));
      for (const k of canonical) if (!order.includes(k)) order.push(k);
      const hidden = Array.isArray(data.hidden) ? data.hidden.map(String).filter(k => canonical.includes(k)) : [];
      setDashLayout({
        grid: { cols, rows },
        order: order.slice(0, capacity),
        hidden,
        locked: !!data.locked
      });
      return;
    }
  } catch {}
  
  // Use default layout if all else fails
  setDashLayout({ grid: { cols: 4, rows: 2 }, order: DASH_KEYS.slice(), hidden: [], locked: false });
}, []);

React.useEffect(() => { try { loadDashLayout(); } catch {} }, [loadDashLayout]);

// Save to localStorage as primary storage (immediate persistence)
const saveDashLayoutToStorage = React.useCallback((layout) => {
  try {
    localStorage.setItem('dashLayout', JSON.stringify(layout));
  } catch (e) {
    console.warn('Failed to save dashboard layout to localStorage:', e);
  }
}, []);

const persistDashLayout = React.useCallback(async (next) => {
  // First, save to localStorage for immediate persistence
  saveDashLayoutToStorage(next);
  
  // Then try to sync to backend (non-blocking, doesn't affect user experience)
  setDashSaving(true);
  try {
    await fetch(apiUrl('/settings/dashboard-layout'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version: 1,
        grid: next.grid,
        order: next.order,
        hidden: next.hidden,
        locked: next.locked
      })
    });
  } catch (e) {
    console.warn('Failed to persist dashboard layout to backend:', e);
    // Not critical - localStorage is our fallback
  }
  setDashSaving(false);
}, [saveDashLayoutToStorage]);

// Auto-persist dashboard layout changes with debounce (500ms delay)
React.useEffect(() => {
  const timer = setTimeout(() => {
    persistDashLayout(dashLayout);
  }, 500);
  return () => clearTimeout(timer);
}, [dashLayout, persistDashLayout]);

const handleDashDragEnd = (event) => {
  if (dashLayout?.locked) return;
  const { active, over } = event || {};
  if (!active || !over || active.id === over.id) return;

  const cur = visibleOrder;
  const oldIndex = cur.indexOf(active.id);
  const newIndex = cur.indexOf(over.id);
  if (oldIndex < 0 || newIndex < 0) return;

  const newVisible = arrayMove(cur, oldIndex, newIndex);

  // Merge with any trimmed/missing items to keep full canonical order
  const canonical = DASH_KEYS;
  const newOrder = [];
  for (const k of newVisible) newOrder.push(k);
  for (const k of canonical) {
    if (!newOrder.includes(k)) newOrder.push(k);
  }

  const next = { ...dashLayout, order: newOrder };
  setDashLayout(next);
};

/* Visibility toggling removed: dashboard no longer supports hiding widgets (v1.5.0) */

const toggleDashLock = () => {
  const next = { ...dashLayout, locked: !dashLayout.locked };
  setDashLayout(next);
};

const SortableTile = ({ id, disabled, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id, disabled });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    cursor: disabled ? 'default' : 'grab',
    zIndex: isDragging ? 5 : 1
  };
  return (
    <div ref={setNodeRef} style={style} className={`nx-tile ${isDragging ? 'dragging' : ''}`} {...attributes} {...listeners}>
      {children}
    </div>
  );
};

// Tile renderers: content mirrors the original dashboard cards
const DashboardTiles = {
  servers: () => (
    <div className="card">
      <h2>Servers</h2>
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        {(() => {
          const s = getActiveConnectedServer();
          if (s === 'plex') {
            return (
              <div>
                <strong>Plex:</strong>
                <span className={`nx-chip nx-status ok`} style={{ marginLeft: '0.35rem' }}>Connected</span>
                {plexServerInfo?.name && (
                  <span style={{ fontSize: '0.9rem', marginLeft: '0.5rem', color: 'var(--text-color)' }}>
                    - {plexServerInfo.name}{plexServerInfo.version ? ` (${plexServerInfo.version})` : ''}
                  </span>
                )}
              </div>
            );
          }
          if (s === 'jellyfin') {
            return (
              <div>
                <strong>Jellyfin:</strong>
                <span className={`nx-chip nx-status ok`} style={{ marginLeft: '0.35rem' }}>Connected</span>
                {jellyfinServerInfo?.name && (
                  <span style={{ fontSize: '0.9rem', marginLeft: '0.5rem', color: 'var(--text-color)' }}>
                    - {jellyfinServerInfo.name}{jellyfinServerInfo.version ? ` (${jellyfinServerInfo.version})` : ''}
                  </span>
                )}
              </div>
            );
          }
          if (s === 'conflict') {
            return (
              <div style={{ fontSize: '0.9rem', color: '#dc3545' }}>
                Conflict: Both Plex and Jellyfin are connected. Disconnect one on the Connect tab.
              </div>
            );
          }
          return (
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)' }}>
              No media server connected. Connect to Plex or Jellyfin on the Connect tab.
            </div>
          );
        })()}
      </div>
    </div>
  ),
  prerolls: () => (
    <div className="card">
      <h2>Prerolls</h2>
      <p>{prerolls.length} uploaded</p>
      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)' }}>
        {categories.filter(cat => prerolls.some(p => p.category_id === cat.id)).length} categories used
      </p>
    </div>
  ),
  storage: () => (
    <div className="card">
      <h2>Storage</h2>
      <p>{formatBytes(totalStorageBytes)} used</p>
    </div>
  ),
  schedules: () => (
    <div className="card">
      <h2>Schedules</h2>
      <p>{schedules.filter(s => s.is_active).length} of {schedules.length} active</p>
    </div>
  ),
  scheduler: () => (
    <div className="card">
      <h2>Scheduler</h2>
      <p style={{ color: schedulerStatus.running ? 'var(--success-color, #28a745)' : 'var(--error-color, #dc3545)' }}>
        {schedulerStatus.running ? 'Running' : 'Stopped'}
      </p>
      <button onClick={toggleScheduler} className="button" style={{ marginTop: '0.5rem' }}>
        {schedulerStatus.running ? 'Stop' : 'Start'} Scheduler
      </button>
    </div>
  ),
  current_category: () => (
    <div className="card">
      <h2>Current Category</h2>
      {activeCategory ? (
        <div>
          <p style={{ fontWeight: 'bold', color: 'var(--success-color, #28a745)' }}>
            {activeCategory.name}
          </p>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)' }}>
            Mode: {activeCategory.plex_mode === 'playlist' ? 'Sequential' : 'Shuffle'}
          </p>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)' }}>
            Prerolls: {prerolls.filter(p => p.category_id === activeCategory.id).length}
          </p>
        </div>
      ) : (
        <p style={{ color: 'var(--text-secondary, #666)' }}>No category applied</p>
      )}
    </div>
  ),
  upcoming: () => (
    <div className="card">
      <h2>Upcoming Schedules</h2>
      {(() => {
        const now = new Date();
        // Get all schedules that haven't ended yet (excluding past schedules)
        const upcomingSchedules = schedules
          .filter(s => {
            // Must have a next_run or start_date
            const runTime = s.next_run ? new Date(s.next_run) : (s.start_date ? new Date(s.start_date) : null);
            if (!runTime) return false;
            
            // If schedule has end_date, it must not have passed yet
            if (s.end_date) {
              return new Date(s.end_date) > now;
            }
            // If no end_date, it's an ongoing schedule - include it
            return true;
          })
          .sort((a, b) => {
            const aTime = a.next_run ? new Date(a.next_run) : new Date(a.start_date);
            const bTime = b.next_run ? new Date(b.next_run) : new Date(b.start_date);
            return aTime - bTime;
          })
          .slice(0, 2);
        
        return upcomingSchedules.length > 0 ? (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {upcomingSchedules.map(schedule => {
              const category = categories.find(c => c.id === schedule.category_id);
              const displayTime = schedule.next_run || schedule.start_date;
              return (
                <div key={schedule.id} style={{ fontSize: '0.9rem', padding: '0.5rem', backgroundColor: 'var(--card-bg)', borderRadius: '4px' }}>
                  <div style={{ fontWeight: 'bold', color: '#007bff' }}>
                    {schedule.name}
                  </div>
                  <div style={{ color: 'var(--text-secondary, #666)' }}>
                    {toLocalDisplay(displayTime)} → {category?.name || 'Unknown'}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: 'var(--text-secondary, #666)' }}>No upcoming schedules</p>
        );
      })()}
    </div>
  ),
  recent_genres: () => (
    <div className="card">
      <h2>Recent Genre Prerolls</h2>
      {recentGenreApplications.length > 0 ? (
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
      ) : (
        <p style={{ color: 'var(--text-secondary, #666)' }}>No recent genre prerolls</p>
      )}
    </div>
  ),
};

  const renderDashboard = () => (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <h1 className="header" style={{ margin: 0 }}>NeXroll Dashboard</h1>
        <a 
          href="https://github.com/JFLXCLOUD/NeXroll/stargazers" 
          target="_blank" 
          rel="noopener noreferrer"
          style={{ textDecoration: 'none' }}
        >
          <img 
            src="https://img.shields.io/github/stars/jflxcloud/nexroll?style=flat&color=grey&logo=github" 
            alt="GitHub Stars"
            style={{ height: '26px' }}
          />
        </a>
      </div>

 
      <div className="card nx-dashboard-controls" style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <label className="nx-rockerswitch" title={dashLayout.locked ? 'Unlock to rearrange' : 'Lock to finish'}>
            <input
              type="checkbox"
              checked={dashLayout.locked}
              onChange={toggleDashLock}
              aria-label={dashLayout.locked ? 'Unlock layout' : 'Lock layout'}
            />
            <span className="nx-rockerswitch-slider"></span>
          </label>
          <span
            className={`nx-lockstate ${dashLayout.locked ? 'is-locked' : 'is-editing'}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 8px',
              border: '1px solid var(--border-color)',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              lineHeight: 1,
              background: 'var(--header-bg)',
              color: dashLayout.locked ? 'var(--text-secondary)' : 'var(--text-color)',
              opacity: dashLayout.locked ? 0.9 : 1
            }}
            aria-live="polite"
          >
            {dashLayout.locked ? 'Locked' : 'Editing'}
          </span>
          {dashSaving && <span className="nx-spinner" aria-hidden="true" title="Saving layout…"></span>}
          {!dashLayout.locked && (
            <span
              className="nx-dash-hint"
              style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', opacity: 0.72 }}
            >
              Drag to rearrange — lock to save
            </span>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <button
              onClick={toggleTheme}
              className="button"
              title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              style={{
                padding: '6px 12px',
                fontSize: '0.85rem',
                minWidth: 'auto'
              }}
            >
              {darkMode ? '☀️ Light' : '🌙 Dark'}
            </button>
          </div>
        </div>
      </div>

      <DndContext sensors={dashSensors} collisionDetection={closestCenter} onDragEnd={handleDashDragEnd}>
        <SortableContext items={visibleOrder} strategy={rectSortingStrategy}>
          <div className={`grid nx-dash-grid ${dashLayout.locked ? '' : 'editing'}`} style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${dashLayout?.grid?.cols || 4}, 1fr)`,
            gap: '1rem'
          }}>
            {visibleOrder.map((key) => (
              <SortableTile key={key} id={key} disabled={dashLayout.locked}>
                {DashboardTiles[key] ? DashboardTiles[key]() : null}
              </SortableTile>
            ))}
          </div>
        </SortableContext>
      </DndContext>

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
                style={{ width: '100%' }}
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
                style={{ width: '100%' }}
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

      <div className="card">
        <div className="prerolls-header">
          <h2>Prerolls</h2>
          <div className="prerolls-stats">
            <span className="stat-item">{prerolls.length} total</span>
            <span className="stat-item">{selectedPrerollIds.length} selected</span>
            <button onClick={handleReinitThumbnails} className="button" style={{ marginLeft: '1rem' }} title="Reinitialize all preroll thumbnails">
              🔄 Reinitialize Thumbnails
            </button>
          </div>
        </div>

        {/* Enhanced Control Bar */}
        <div className="prerolls-control-bar">
          {/* View Toggle */}
          <div className="control-group">
            <label className="control-label">View</label>
            <div className="view-toggle">
              <button
                type="button"
                className={`view-btn ${prerollView === 'grid' ? 'active' : ''}`}
                onClick={() => setPrerollView('grid')}
                title="Grid view"
              >
                <span className="view-icon">⊞</span>
                Grid
              </button>
              <button
                type="button"
                className={`view-btn ${prerollView === 'list' ? 'active' : ''}`}
                onClick={() => setPrerollView('list')}
                title="List view"
              >
                <span className="view-icon">☰</span>
                List
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="control-group">
            <label className="control-label">Filters</label>
            <div className="filter-controls">
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="filter-select"
              >
                <option value="">All Categories</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              <div className="search-input-wrapper">
                <input
                  type="text"
                  placeholder="Search prerolls (tags, filenames, titles)..."
                  value={inputTagsValue}
                  onChange={(e) => handleTagsChange(e.target.value)}
                  className="search-input"
                />
                <span className="search-icon">🔍</span>
              </div>
              <button
                onClick={() => { setCurrentPage(1); fetchData(); }}
                className="filter-btn"
                title="Apply filters"
              >
                Apply
              </button>
            </div>
          </div>

          {/* Pagination */}
          <div className="control-group">
            <label className="control-label">Items per page</label>
            <select
              value={pageSize}
              onChange={(e) => { const v = parseInt(e.target.value, 10); setPageSize(v); setCurrentPage(1); }}
              className="page-size-select"
            >
              {[20, 30, 40, 50].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        {/* Bulk Actions Bar */}
        <div className="bulk-actions-bar">
          <div className="bulk-actions-left">
            <label className="select-all-wrapper">
              <input
                type="checkbox"
                checked={allSelectedOnPage}
                onChange={(e) => selectAllVisible(visibleIds, e.target.checked)}
                className="select-all-checkbox"
              />
              <span className="select-all-label">Select all ({visibleIds.length})</span>
            </label>
            <button
              type="button"
              className="action-btn secondary"
              onClick={clearSelection}
              disabled={selectedPrerollIds.length === 0}
              title="Clear selected prerolls"
            >
              Clear Selection
            </button>
          </div>

          <div className="bulk-actions-right">
            <div className="bulk-category-wrapper">
              <select
                value={bulkCategoryId}
                onChange={(e) => setBulkCategoryId(e.target.value)}
                className="bulk-category-select"
                disabled={selectedPrerollIds.length === 0}
              >
                <option value="">Set Category...</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              <button
                type="button"
                className="action-btn primary"
                onClick={() => handleBulkSetPrimary(bulkCategoryId)}
                disabled={!bulkCategoryId || selectedPrerollIds.length === 0}
                title="Change primary category for selected prerolls"
              >
                Apply to {selectedPrerollIds.length} Selected
              </button>
            </div>
            <button
              type="button"
              className="action-btn danger"
              onClick={handleBulkDeleteSelected}
              disabled={selectedPrerollIds.length === 0}
              title="Delete all selected prerolls"
            >
              🗑️ Delete {selectedPrerollIds.length > 0 && `(${selectedPrerollIds.length})`}
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
                    onClick={() => {
                      console.log('List preview button clicked for preroll:', preroll);
                      console.log('Current previewingPreroll state:', previewingPreroll);
                      setPreviewingPreroll(preroll);
                      console.log('Setting previewingPreroll to:', preroll);
                    }}
                    className="nx-iconbtn"
                    title="Preview video"
                  >
                    ▶️
                  </button>
                  <button
                    onClick={() => handleEditPreroll(preroll)}
                    className="nx-iconbtn"
                    title="Edit preroll"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeletePreroll(preroll.id)}
                    className="nx-iconbtn nx-iconbtn--danger"
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
               onClick={() => {
                 console.log('Grid preview button clicked for preroll:', preroll);
                 console.log('Current previewingPreroll state:', previewingPreroll);
                 setPreviewingPreroll(preroll);
                 console.log('Setting previewingPreroll to:', preroll);
               }}
               className="nx-iconbtn"
               title="Preview video"
             >
               ▶️
             </button>
             <button
               onClick={() => handleEditPreroll(preroll)}
               className="nx-iconbtn"
               title="Edit preroll"
             >
               ✏️
             </button>
             <button
               onClick={() => handleDeletePreroll(preroll.id)}
               className="nx-iconbtn nx-iconbtn--danger"
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
<div className="card nx-toolbar">
  <div className="toolbar-group">
    <button className="button" onClick={() => setShowCalendar(!showCalendar)}>
      {showCalendar ? 'Hide Calendar' : 'Show Calendar'}
    </button>
  </div>

  <div className="toolbar-group">
    <label className="control-label">View</label>
    <select className="nx-select" value={calendarMode} onChange={(e) => setCalendarMode(e.target.value)}>
      <option value="week">Week</option>
      <option value="month">Month</option>
      <option value="year">Year</option>
    </select>
  </div>

  {calendarMode === 'week' && (
    <>
      <div className="toolbar-group">
        <div className="view-toggle">
          <button
            type="button"
            className="view-btn"
            onClick={() => { 
              const prev = new Date(calendarWeekStart);
              prev.setDate(prev.getDate() - 7);
              setCalendarWeekStart(prev);
            }}
            title="Previous Week"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            <span className="view-icon">◀</span>
            Previous
          </button>
          <button
            type="button"
            className="button"
            onClick={() => { 
              const now = new Date();
              const day = now.getDay();
              const diff = now.getDate() - day;
              setCalendarWeekStart(new Date(now.getFullYear(), now.getMonth(), diff));
            }}
            title="Go to Current Week"
            style={{ padding: '0.5rem 1.5rem', fontWeight: 600, minWidth: '120px' }}
          >
            This Week
          </button>
          <button
            type="button"
            className="view-btn"
            onClick={() => { 
              const next = new Date(calendarWeekStart);
              next.setDate(next.getDate() + 7);
              setCalendarWeekStart(next);
            }}
            title="Next Week"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            Next
            <span className="view-icon">▶</span>
          </button>
        </div>
      </div>
    </>
  )}

  {calendarMode === 'month' && (
    <>
      <div className="toolbar-group">
        <div className="view-toggle">
          <button
            type="button"
            className="view-btn"
            onClick={() => { let m = calendarMonth - 1; let y = calendarYear; if (m < 1) { m = 12; y--; } setCalendarMonth(m); setCalendarYear(y); }}
            title="Previous Month"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            <span className="view-icon">◀</span>
            Previous
          </button>
          <button
            type="button"
            className="button"
            onClick={() => { 
              const now = new Date(); 
              setCalendarMonth(now.getMonth() + 1); 
              setCalendarYear(now.getFullYear()); 
            }}
            title="Go to Current Month"
            style={{ padding: '0.5rem 1.5rem', fontWeight: 600, minWidth: '120px' }}
          >
            Today
          </button>
          <button
            type="button"
            className="view-btn"
            onClick={() => { let m = calendarMonth + 1; let y = calendarYear; if (m > 12) { m = 1; y++; } setCalendarMonth(m); setCalendarYear(y); }}
            title="Next Month"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            Next
            <span className="view-icon">▶</span>
          </button>
        </div>
      </div>

      <div className="toolbar-group" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label className="control-label" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Month</label>
          <select 
            className="nx-select" 
            value={calendarMonth} 
            onChange={(e) => setCalendarMonth(parseInt(e.target.value, 10))}
            style={{ minWidth: '150px', padding: '0.5rem' }}
          >
            {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
              <option key={m} value={m}>{new Date(2000, m - 1, 1).toLocaleString(undefined, { month: 'long' })}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label className="control-label" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Year</label>
          <input
            className="nx-input"
            type="number"
            value={calendarYear}
            onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)}
            style={{ width: 110, padding: '0.5rem' }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label className="control-label" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Display</label>
          <select 
            className="nx-select" 
            value={calendarMonthView} 
            onChange={(e) => setCalendarMonthView(e.target.value)}
            style={{ minWidth: '120px', padding: '0.5rem' }}
          >
            <option value="timeline">Timeline</option>
            <option value="grid">Grid</option>
          </select>
        </div>
      </div>
    </>
  )}

  {calendarMode === 'year' && (
    <div className="toolbar-group" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
      <div className="view-toggle">
        <button
          type="button"
          className="view-btn"
          onClick={() => setCalendarYear(calendarYear - 1)}
          title="Previous Year"
          style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
        >
          <span className="view-icon">◀</span>
          {calendarYear - 1}
        </button>
        <button
          type="button"
          className="button"
          onClick={() => setCalendarYear(new Date().getFullYear())}
          title="Go to Current Year"
          style={{ padding: '0.5rem 1.5rem', fontWeight: 600, minWidth: '120px' }}
        >
          {new Date().getFullYear()}
        </button>
        <button
          type="button"
          className="view-btn"
          onClick={() => setCalendarYear(calendarYear + 1)}
          title="Next Year"
          style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
        >
          {calendarYear + 1}
          <span className="view-icon">▶</span>
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <label className="control-label" style={{ fontSize: '0.75rem', fontWeight: 600 }}>Custom Year</label>
        <input
          className="nx-input"
          type="number"
          value={calendarYear}
          onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)}
          style={{ width: 110, padding: '0.5rem' }}
        />
      </div>
    </div>
  )}
</div>
<div style={{ display: showCalendar ? 'block' : 'none' }}>
  {calendarMode === 'week' ? (() => {
    // Week view with continuous schedule bars
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(calendarWeekStart);
      d.setDate(calendarWeekStart.getDate() + i);
      days.push(d);
    }

    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };

    const isScheduleActiveOnDay = (schedule, dayTime) => {
      if (!schedule.start_date) return false;
      const dayDate = new Date(dayTime);
      
      if (schedule.type === 'yearly' || schedule.type === 'holiday') {
        const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
        const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
        const [startYear, startMonth, startDay] = startDateStr.split('-').map(Number);
        const [endYear, endMonth, endDay] = endDateStr.split('-').map(Number);
        const schedStartMonth = startMonth - 1;
        const schedStartDay = startDay;
        const schedEndMonth = endMonth - 1;
        const schedEndDay = endDay;
        const dayMonth = dayDate.getMonth();
        const dayDay = dayDate.getDate();
        
        if (schedStartMonth === schedEndMonth) {
          return dayMonth === schedStartMonth && dayDay >= schedStartDay && dayDay <= schedEndDay;
        } else {
          return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
                 (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
                 (schedStartMonth < schedEndMonth && dayMonth > schedStartMonth && dayMonth < schedEndMonth) ||
                 (schedStartMonth > schedEndMonth && (dayMonth > schedStartMonth || dayMonth < schedEndMonth));
        }
      }
      
      const sDay = normalizeDay(schedule.start_date);
      const eDay = schedule.end_date ? normalizeDay(schedule.end_date) : sDay;
      return dayTime >= sDay && dayTime <= eDay;
    };

    const scheds = (schedules || []).map(s => ({
      ...s,
      cat: catMap.get(s.category_id) || { name: (s.category?.name || 'Unknown'), color: '#6c757d' }
    }));

    const todayTime = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime();

    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <h2 style={{ 
          marginTop: 0, 
          marginBottom: '1.5rem',
          fontSize: '1.8rem',
          fontWeight: 600,
          color: 'var(--text-color)'
        }}>
          Week of {days[0].toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
        </h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {scheds.map((sched, idx) => {
            // Find continuous spans for this schedule across the week
            const spans = [];
            let currentSpan = null;
            
            days.forEach((day, dayIdx) => {
              const t = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
              const isActive = isScheduleActiveOnDay(sched, t);
              
              if (isActive) {
                if (!currentSpan) {
                  currentSpan = { start: dayIdx, end: dayIdx };
                } else {
                  currentSpan.end = dayIdx;
                }
              } else {
                if (currentSpan) {
                  spans.push(currentSpan);
                  currentSpan = null;
                }
              }
            });
            if (currentSpan) spans.push(currentSpan);
            
            if (spans.length === 0) return null;
            
            return (
              <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div style={{ 
                  minWidth: '150px', 
                  fontWeight: 500, 
                  fontSize: '0.9rem',
                  color: 'var(--text-color)'
                }}>{sched.name}</div>
                <div style={{ flex: 1, position: 'relative', height: '32px', display: 'flex' }}>
                  {days.map((day, dayIdx) => (
                    <div key={dayIdx} style={{ 
                      flex: 1, 
                      borderLeft: dayIdx === 0 ? 'none' : '1px solid var(--border-color)',
                      position: 'relative'
                    }} />
                  ))}
                  {spans.map((span, spanIdx) => {
                    const width = ((span.end - span.start + 1) / 7) * 100;
                    const left = (span.start / 7) * 100;
                    return (
                      <div key={spanIdx} style={{
                        position: 'absolute',
                        left: `${left}%`,
                        width: `${width}%`,
                        height: '100%',
                        backgroundColor: sched.color || sched.cat.color,
                        borderRadius: '4px',
                        padding: '4px 8px',
                        color: '#fff',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                      }}>
                        {sched.cat.name}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }).filter(Boolean)}
        </div>
        
        {/* Day labels at bottom */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(7, 1fr)', 
          gap: '8px', 
          marginTop: '1rem',
          marginLeft: '158px'
        }}>
          {days.map((day, idx) => {
            const isToday = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime() === todayTime;
            return (
              <div key={idx} style={{ 
                textAlign: 'center',
                fontWeight: isToday ? 700 : 500,
                fontSize: '0.85rem',
                color: isToday ? 'var(--button-bg)' : 'var(--text-color)',
                padding: '8px',
                borderRadius: '4px',
                backgroundColor: isToday ? (darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)') : 'transparent'
              }}>
                <div>{day.toLocaleDateString(undefined, { weekday: 'short' })}</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>{day.getDate()}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  })() : calendarMode === 'month' ? (calendarMonthView === 'timeline' ? (() => {
    // Timeline view for month - shows continuous bars like week view
    const monthIndex = calendarMonth - 1;
    const daysInMonth = new Date(calendarYear, monthIndex + 1, 0).getDate();
    const days = [];
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(calendarYear, monthIndex, i));
    }

    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };

    const isScheduleActiveOnDay = (schedule, dayTime) => {
      if (!schedule.start_date) return false;
      const dayDate = new Date(dayTime);
      
      if (schedule.type === 'yearly' || schedule.type === 'holiday') {
        const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
        const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
        const [startYear, startMonth, startDay] = startDateStr.split('-').map(Number);
        const [endYear, endMonth, endDay] = endDateStr.split('-').map(Number);
        const schedStartMonth = startMonth - 1;
        const schedStartDay = startDay;
        const schedEndMonth = endMonth - 1;
        const schedEndDay = endDay;
        const dayMonth = dayDate.getMonth();
        const dayDay = dayDate.getDate();
        
        if (schedStartMonth === schedEndMonth) {
          return dayMonth === schedStartMonth && dayDay >= schedStartDay && dayDay <= schedEndDay;
        } else {
          return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
                 (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
                 (schedStartMonth < schedEndMonth && dayMonth > schedStartMonth && dayMonth < schedEndMonth) ||
                 (schedStartMonth > schedEndMonth && (dayMonth > schedStartMonth || dayMonth < schedEndMonth));
        }
      }
      
      const sDay = normalizeDay(schedule.start_date);
      const eDay = schedule.end_date ? normalizeDay(schedule.end_date) : sDay;
      return dayTime >= sDay && dayTime <= eDay;
    };

    const scheds = (schedules || []).map(s => ({
      ...s,
      cat: catMap.get(s.category_id) || { name: (s.category?.name || 'Unknown'), color: '#6c757d' }
    }));

    const todayTime = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime();
    const monthName = new Date(calendarYear, monthIndex, 1).toLocaleString(undefined, { month: 'long' });

    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <h2 style={{ 
          marginTop: 0, 
          marginBottom: '1.5rem',
          fontSize: '1.8rem',
          fontWeight: 600,
          color: 'var(--text-color)'
        }}>
          {monthName} {calendarYear}
        </h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {scheds.map((sched, idx) => {
            // Find continuous spans for this schedule across the month
            const spans = [];
            let currentSpan = null;
            
            days.forEach((day, dayIdx) => {
              const t = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
              const isActive = isScheduleActiveOnDay(sched, t);
              
              if (isActive) {
                if (!currentSpan) {
                  currentSpan = { start: dayIdx, end: dayIdx };
                } else {
                  currentSpan.end = dayIdx;
                }
              } else {
                if (currentSpan) {
                  spans.push(currentSpan);
                  currentSpan = null;
                }
              }
            });
            if (currentSpan) spans.push(currentSpan);
            
            if (spans.length === 0) return null;
            
            return (
              <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div style={{ 
                  minWidth: '150px', 
                  fontWeight: 500, 
                  fontSize: '0.9rem',
                  color: 'var(--text-color)'
                }}>{sched.name}</div>
                <div style={{ flex: 1, position: 'relative', height: '32px', display: 'flex', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                  {days.map((day, dayIdx) => (
                    <div key={dayIdx} style={{ 
                      flex: 1, 
                      borderLeft: dayIdx === 0 ? 'none' : '1px solid var(--border-color)',
                      position: 'relative'
                    }} />
                  ))}
                  {spans.map((span, spanIdx) => {
                    const width = ((span.end - span.start + 1) / daysInMonth) * 100;
                    const left = (span.start / daysInMonth) * 100;
                    return (
                      <div key={spanIdx} style={{
                        position: 'absolute',
                        left: `${left}%`,
                        width: `${width}%`,
                        height: '100%',
                        backgroundColor: sched.color || sched.cat.color,
                        borderRadius: '4px',
                        padding: '4px 8px',
                        color: '#fff',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                      }}>
                        {sched.cat.name}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }).filter(Boolean)}
        </div>
        
        {/* Day labels at bottom - show every 5th day */}
        <div style={{ 
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '1rem',
          marginLeft: '158px',
          paddingRight: '8px'
        }}>
          {[1, 5, 10, 15, 20, 25, daysInMonth].map((dayNum) => {
            const day = new Date(calendarYear, monthIndex, dayNum);
            const isToday = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime() === todayTime;
            return (
              <div key={dayNum} style={{ 
                textAlign: 'center',
                fontWeight: isToday ? 700 : 500,
                fontSize: '0.75rem',
                color: isToday ? 'var(--button-bg)' : 'var(--text-secondary)',
                padding: '4px',
                borderRadius: '4px',
                backgroundColor: isToday ? (darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)') : 'transparent'
              }}>
                {dayNum}
              </div>
            );
          })}
        </div>
      </div>
    );
  })() : (() => {
    // Grid view for month - original implementation with conflict indicators
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

    // Helper to check if a day matches a schedule, accounting for yearly repeats
    const isScheduleActiveOnDay = (schedule, dayTime) => {
      if (!schedule.start_date) return false;
      
      const dayDate = new Date(dayTime);
      
      // For yearly/holiday schedules, check if the month/day matches
      if (schedule.type === 'yearly' || schedule.type === 'holiday') {
        // Parse dates using UTC to avoid timezone issues
        const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
        const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
        
        const [startYear, startMonth, startDay] = startDateStr.split('-').map(Number);
        const [endYear, endMonth, endDay] = endDateStr.split('-').map(Number);
        
        // Use 0-indexed months for comparison (JavaScript Date uses 0-11)
        const schedStartMonth = startMonth - 1;
        const schedStartDay = startDay;
        const schedEndMonth = endMonth - 1;
        const schedEndDay = endDay;
        
        const dayMonth = dayDate.getMonth();
        const dayDay = dayDate.getDate();
        
        // Check if day falls within the recurring month/day range
        if (schedStartMonth === schedEndMonth) {
          // Same month: simple day range check
          return dayMonth === schedStartMonth && dayDay >= schedStartDay && dayDay <= schedEndDay;
        } else {
          // Cross-month range (e.g., Dec 20 - Jan 5)
          return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
                 (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
                 (schedStartMonth < schedEndMonth && dayMonth > schedStartMonth && dayMonth < schedEndMonth) ||
                 (schedStartMonth > schedEndMonth && (dayMonth > schedStartMonth || dayMonth < schedEndMonth));
        }
      }
      
      // For non-repeating schedules, use standard date range check
      const sDay = normalizeDay(schedule.start_date);
      const eDay = schedule.end_date ? normalizeDay(schedule.end_date) : sDay;
      return dayTime >= sDay && dayTime <= eDay;
    };

    const scheds = (schedules || []).map(s => ({
      ...s,
      cat: catMap.get(s.category_id) || { name: (s.category?.name || 'Unknown'), color: '#6c757d' }
    }));

    // Track both schedules and their categories per day
    const byDay = new Map(); // dayTime -> { schedules: Set<schedule>, isFallback: boolean, hasConflict: boolean }
    days.forEach(d => {
      const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      byDay.set(t, { schedules: new Set(), isFallback: false, hasConflict: false });
    });

    // Map schedules to days, accounting for yearly repeats
    for (const s of scheds) {
      if (!s.start_date) continue;
      for (const d of days) {
        const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
        if (isScheduleActiveOnDay(s, t)) {
          const dayData = byDay.get(t);
          if (dayData) dayData.schedules.add(s);
        }
      }
    }
    
    // Detect conflicts - multiple non-fallback schedules on same day
    for (const [dayTime, dayData] of byDay.entries()) {
      const nonFallbackSchedules = Array.from(dayData.schedules).filter(s => !s.fallback_category_id);
      if (nonFallbackSchedules.length > 1) {
        dayData.hasConflict = true;
      }
    }
    
    // Show fallback categories on days with no active schedules
    const fallbackSchedules = (schedules || []).filter(s => s.fallback_category_id);
    
    for (const [dayTime, dayData] of byDay.entries()) {
      if (dayData.schedules.size === 0 && fallbackSchedules.length > 0) {
        // No active schedules on this day, show fallbacks
        dayData.isFallback = true;
        fallbackSchedules.forEach(s => {
          // Create pseudo-schedule for fallback
          const fallbackSched = {
            ...s,
            category_id: s.fallback_category_id,
            name: `${s.name} (Fallback)`,
            cat: catMap.get(s.fallback_category_id) || { name: 'Fallback', color: '#6c757d' }
          };
          dayData.schedules.add(fallbackSched);
        });
      }
    }

    const monthName = startOfMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' });
    const today = new Date();
    const todayTime = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();

    return (
      <div className="card" style={{ marginBottom: '1rem', padding: '1.5rem' }}>
        <h2 style={{ 
          marginTop: 0, 
          marginBottom: '1.5rem',
          fontSize: '1.8rem',
          fontWeight: 600,
          color: 'var(--text-color)',
          borderBottom: '2px solid var(--border-color)',
          paddingBottom: '0.75rem'
        }}>{monthName}</h2>
        
        {/* Day of week headers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px', marginBottom: '8px' }}>
          {['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map(dow => (
            <div key={dow} style={{ 
              fontWeight: 600, 
              textAlign: 'center', 
              padding: '10px 0',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>{dow.slice(0, 3)}</div>
          ))}
        </div>
        
        {/* Calendar grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px' }}>
          {days.map((d, idx) => {
            const inMonth = d.getMonth() === monthIndex;
            const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
            const dayData = byDay.get(t) || { schedules: new Set(), isFallback: false, hasConflict: false };
            const schedArray = Array.from(dayData.schedules);
            const isToday = t === todayTime;
            const isWeekend = d.getDay() === 0 || d.getDay() === 6;
            
            // Get unique categories for this day
            const uniqueCats = new Map();
            schedArray.forEach(s => {
              if (!uniqueCats.has(s.category_id)) {
                uniqueCats.set(s.category_id, { cat: s.cat, schedules: [], schedObjs: [] });
              }
              uniqueCats.get(s.category_id).schedules.push(s.name);
              uniqueCats.get(s.category_id).schedObjs.push(s);
            });
            const catEntries = Array.from(uniqueCats.entries());
            
            // Determine which schedule would win in a conflict (mimics backend logic)
            const nonFallbackSchedules = schedArray.filter(s => !s.fallback_category_id && s.start_date);
            let winningSchedule = null;
            if (nonFallbackSchedules.length > 0) {
              // Sort by: ends soonest, then started earliest, then lowest ID
              const sorted = [...nonFallbackSchedules].sort((a, b) => {
                const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
                const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
                if (endA !== endB) return endA - endB;
                
                const startA = new Date(a.start_date).getTime();
                const startB = new Date(b.start_date).getTime();
                if (startA !== startB) return startA - startB;
                
                return a.id - b.id;
              });
              winningSchedule = sorted[0];
            }
            
            return (
              <div key={idx} style={{
                border: isToday 
                  ? '2px solid var(--button-bg)' 
                  : (dayData.hasConflict 
                      ? '2px solid #ff9800' 
                      : '1px solid var(--border-color)'),
                backgroundColor: inMonth 
                  ? (isWeekend 
                      ? (darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)') 
                      : 'var(--card-bg)')
                  : (darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)'),
                minHeight: 100,
                padding: '8px',
                borderRadius: '8px',
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.2s ease',
                cursor: 'default',
                boxShadow: isToday 
                  ? '0 0 12px rgba(59, 130, 246, 0.3)' 
                  : (dayData.hasConflict ? '0 0 8px rgba(255, 152, 0, 0.3)' : 'none')
              }}
              onMouseEnter={(e) => {
                if (inMonth) {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 4px 12px var(--shadow)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = isToday ? '0 0 12px rgba(59, 130, 246, 0.3)' : 'none';
              }}>
                {/* Conflict warning indicator */}
                {dayData.hasConflict && (
                  <div 
                    title={`⚠️ Schedule Conflict\nMultiple schedules active on this day.\nWinning schedule: ${winningSchedule?.name || 'Unknown'}`}
                    style={{ 
                      position: 'absolute', 
                      top: 8, 
                      left: 8, 
                      fontSize: '1rem',
                      color: '#ff9800',
                      fontWeight: 700,
                      cursor: 'help',
                      textShadow: darkMode ? '0 1px 3px rgba(0,0,0,0.5)' : '0 1px 2px rgba(0,0,0,0.3)'
                    }}>⚠️</div>
                )}
                
                <div style={{ 
                  position: 'absolute', 
                  top: 8, 
                  right: 8, 
                  fontSize: '0.95rem', 
                  fontWeight: isToday ? 700 : 600,
                  color: isToday ? 'var(--button-bg)' : (inMonth ? 'var(--text-color)' : 'var(--text-muted)'),
                  backgroundColor: isToday ? (darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)') : 'transparent',
                  padding: isToday ? '4px 8px' : '0',
                  borderRadius: isToday ? '12px' : '0',
                  minWidth: isToday ? '28px' : 'auto',
                  textAlign: 'center'
                }}>{d.getDate()}</div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '32px' }}>
                  {catEntries.slice(0, 3).map(([catId, data], i) => {
                    const scheduleNames = data.schedules.join(', ');
                    // Check if any of these schedules is the winning one
                    const isWinner = winningSchedule && data.schedules.some(name => 
                      name === winningSchedule.name || name === `${winningSchedule.name} (Fallback)`
                    );
                    
                    // Determine schedule color - use winning schedule's color if available, otherwise first schedule's color
                    let scheduleColor = data.cat.color; // Default to category color
                    if (data.schedObjs && data.schedObjs.length > 0) {
                      if (winningSchedule) {
                        const winner = data.schedObjs.find(s => s.name === winningSchedule.name);
                        if (winner && winner.color) {
                          scheduleColor = winner.color;
                        }
                      } else if (data.schedObjs[0].color) {
                        scheduleColor = data.schedObjs[0].color;
                      }
                    }
                    
                    let tooltipText = `${data.cat.name}${dayData.isFallback ? ' (Fallback)' : ''}\nSchedules: ${scheduleNames}`;
                    if (dayData.hasConflict && isWinner) {
                      tooltipText += '\n👑 This schedule takes priority';
                    } else if (dayData.hasConflict && !dayData.isFallback) {
                      tooltipText += '\n⚠️ Overridden by higher priority schedule';
                    }
                    
                    return (
                      <div 
                        key={catId + '_' + i} 
                        title={tooltipText} 
                        style={{
                        backgroundColor: dayData.isFallback ? 'transparent' : scheduleColor,
                        border: dayData.isFallback ? `2px dashed ${scheduleColor}` : 'none',
                        color: dayData.isFallback ? scheduleColor : '#fff', 
                        borderRadius: '4px',
                        padding: '4px 6px', 
                        fontSize: '0.75rem',
                        fontWeight: isWinner ? 600 : 500,
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis',
                        boxShadow: dayData.isFallback 
                          ? 'none' 
                          : (isWinner && dayData.hasConflict 
                              ? '0 2px 6px rgba(0,0,0,0.3), 0 0 0 2px rgba(255, 215, 0, 0.4)' 
                              : '0 1px 3px rgba(0,0,0,0.2)'),
                        opacity: dayData.isFallback 
                          ? 0.8 
                          : (dayData.hasConflict && !isWinner ? 0.6 : 1),
                        position: 'relative'
                      }}>
                        {isWinner && dayData.hasConflict && <span style={{ marginRight: '4px' }}>👑</span>}
                        {data.cat.name}
                      </div>
                    );
                  })}
                  {catEntries.length > 3 && (
                    <div style={{ 
                      fontSize: '0.7rem', 
                      color: 'var(--text-muted)',
                      fontWeight: 500,
                      padding: '2px 6px',
                      textAlign: 'center'
                    }}>+{catEntries.length - 3} more</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Legend */}
        <div style={{ 
          marginTop: '1.5rem', 
          paddingTop: '1.5rem',
          borderTop: '1px solid var(--border-color)'
        }}>
          <div style={{ 
            fontSize: '0.75rem', 
            fontWeight: 600, 
            textTransform: 'uppercase', 
            letterSpacing: '0.5px',
            color: 'var(--text-secondary)',
            marginBottom: '0.75rem'
          }}>Schedule Legend</div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {(schedules || []).filter(s => {
              // Only show schedules active in this month
              const monthStart = new Date(calendarYear, monthIndex, 1);
              const monthEnd = new Date(calendarYear, monthIndex + 1, 0);
              return Array.from(byDay.values()).some(dayData => 
                Array.from(dayData.schedules).some(sched => sched.id === s.id || sched.name === s.name)
              );
            }).map((s) => {
              const cat = catMap.get(s.category_id) || { name: 'Unknown', color: '#6c757d' };
              const schedColor = s.color || cat.color;
              return (
                <span key={s.id} style={{ 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '8px', 
                  fontSize: '0.875rem',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
                  border: '1px solid var(--border-color)'
                }}>
                  <span style={{ 
                    width: 14, 
                    height: 14, 
                    backgroundColor: schedColor, 
                    display: 'inline-block', 
                    borderRadius: 3,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
                  }} />
                  <span style={{ fontWeight: 500 }}>{s.name}</span>
                </span>
              );
            })}
          </div>
          
          {/* Legend indicators */}
          <div style={{ marginTop: '1rem', display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: 40, 
                height: 16, 
                backgroundColor: palette[0],
                borderRadius: 3
              }} />
              <span>Active Schedule</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: 40, 
                height: 16, 
                border: `2px dashed ${palette[0]}`,
                borderRadius: 3,
                backgroundColor: 'transparent'
              }} />
              <span>Fallback Category</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: 16, 
                height: 16, 
                backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                borderRadius: 3
              }} />
              <span>Weekend</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: 16, 
                height: 16, 
                border: '2px solid var(--button-bg)',
                borderRadius: 3,
                backgroundColor: darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)'
              }} />
              <span>Today</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: 16, 
                height: 16, 
                border: '2px solid #ff9800',
                borderRadius: 3,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.7rem'
              }}>⚠️</div>
              <span>Schedule Conflict (👑 = Active)</span>
            </div>
          </div>
        </div>
      </div>
    );
  })()) : (() => {
    // Year view
    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    // Count scheduled days per month and track conflicts
    const counts = Array.from({ length: 12 }, (_, m) => ({ month: m, cats: new Map(), conflictDays: 0 }));
    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    
    // Helper to check if a day matches a schedule (handles yearly repeats)
    const isScheduleActiveOnDay = (schedule, dayTime) => {
      if (!schedule.start_date) return false;
      
      const dayDate = new Date(dayTime);
      
      // For yearly/holiday schedules, check if the month/day matches
      if (schedule.type === 'yearly' || schedule.type === 'holiday') {
        // Parse dates using UTC to avoid timezone issues
        const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
        const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
        
        const [startYear, startMonth, startDay] = startDateStr.split('-').map(Number);
        const [endYear, endMonth, endDay] = endDateStr.split('-').map(Number);
        
        // Use 0-indexed months for comparison (JavaScript Date uses 0-11)
        const schedStartMonth = startMonth - 1;
        const schedStartDay = startDay;
        const schedEndMonth = endMonth - 1;
        const schedEndDay = endDay;
        
        const dayMonth = dayDate.getMonth();
        const dayDay = dayDate.getDate();
        
        // Check if day falls within the recurring month/day range
        if (schedStartMonth === schedEndMonth) {
          // Same month: simple day range check
          return dayMonth === schedStartMonth && dayDay >= schedStartDay && dayDay <= schedEndDay;
        } else {
          // Cross-month range (e.g., Dec 20 - Jan 5)
          return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
                 (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
                 (schedStartMonth < schedEndMonth && dayMonth > schedStartMonth && dayMonth < schedEndMonth) ||
                 (schedStartMonth > schedEndMonth && (dayMonth > schedStartMonth || dayMonth < schedEndMonth));
        }
      }
      
      // For non-repeating schedules, use standard date range check
      const sDay = normalizeDay(schedule.start_date);
      const eDay = schedule.end_date ? normalizeDay(schedule.end_date) : sDay;
      return dayTime >= sDay && dayTime <= eDay;
    };
    
    // Iterate through each day of the year using proper date construction
    for (let month = 0; month < 12; month++) {
      const daysInMonth = new Date(calendarYear, month + 1, 0).getDate();
      const map = counts[month].cats;
      
      for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(calendarYear, month, day);
        const t = d.getTime();
        
        let activeSchedulesForDay = 0;
        
        // Check each schedule to see if it's active on this day
        for (const s of (schedules || [])) {
          if (!s.start_date || !s.category_id) continue;
          
          const isActive = isScheduleActiveOnDay(s, t);
          
          if (isActive) {
            map.set(s.category_id, (map.get(s.category_id) || 0) + 1);
            // Only count non-fallback schedules for conflicts
            if (!s.fallback_category_id) {
              activeSchedulesForDay++;
            }
          }
        }
        
        // Track if this day has conflicts (multiple active non-fallback schedules)
        if (activeSchedulesForDay > 1) {
          counts[month].conflictDays++;
        }
      }
    }
    
    // Add fallback categories for days with no active schedules
    const fallbackCats = new Set((schedules || [])
      .map(s => s.fallback_category_id)
      .filter(Boolean));
    
    if (fallbackCats.size > 0) {
      for (let m = 0; m < 12; m++) {
        const monthStart = new Date(calendarYear, m, 1).getTime();
        const monthEnd = new Date(calendarYear, m + 1, 0).getTime();
        const map = counts[m].cats;
        
        let daysWithSchedules = 0;
        for (const [catId, count] of map.entries()) {
          if (!fallbackCats.has(catId)) {
            daysWithSchedules += count;
          }
        }
        
        const daysInMonth = new Date(calendarYear, m + 1, 0).getDate();
        const fallbackDays = daysInMonth - daysWithSchedules;
        
        if (fallbackDays > 0) {
          fallbackCats.forEach(fcid => {
            map.set(fcid, (map.get(fcid) || 0) + fallbackDays);
          });
        }
      }
    }

    const currentMonth = new Date().getMonth();
    const isCurrentYear = calendarYear === new Date().getFullYear();

    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <h2 style={{ 
          marginTop: 0, 
          marginBottom: '1.5rem',
          fontSize: '1.8rem',
          fontWeight: 600,
          color: 'var(--text-color)',
          borderBottom: '2px solid var(--border-color)',
          paddingBottom: '0.75rem'
        }}>{calendarYear} Overview</h2>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
          {counts.map((entry) => {
            const monthName = new Date(calendarYear, entry.month, 1).toLocaleString(undefined, { month: 'long' });
            const topCats = Array.from(entry.cats.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4);
            const isCurrentMonth = isCurrentYear && entry.month === currentMonth;
            const totalDays = Array.from(entry.cats.values()).reduce((sum, count) => sum + count, 0);
            const daysInMonth = new Date(calendarYear, entry.month + 1, 0).getDate();
            
            return (
              <div key={entry.month} 
                style={{ 
                  border: isCurrentMonth ? '2px solid var(--button-bg)' : '1px solid var(--border-color)', 
                  borderRadius: 8, 
                  padding: '16px', 
                  background: 'var(--card-bg)',
                  transition: 'all 0.2s ease',
                  cursor: 'pointer',
                  boxShadow: isCurrentMonth ? '0 0 12px rgba(59, 130, 246, 0.3)' : 'none'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-4px)';
                  e.currentTarget.style.boxShadow = '0 6px 20px var(--shadow)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = isCurrentMonth ? '0 0 12px rgba(59, 130, 246, 0.3)' : 'none';
                }}
                onClick={() => {
                  setCalendarMonth(entry.month + 1);
                  setCalendarMode('month');
                }}
              >
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: 12
                }}>
                  <div style={{ 
                    fontWeight: 700, 
                    fontSize: '1.1rem',
                    color: isCurrentMonth ? 'var(--button-bg)' : 'var(--text-color)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    {monthName}
                    {entry.conflictDays > 0 && (
                      <span 
                        title={`⚠️ ${entry.conflictDays} day${entry.conflictDays > 1 ? 's' : ''} with schedule conflicts`}
                        style={{ 
                          fontSize: '0.9rem',
                          color: '#ff9800',
                          cursor: 'help'
                        }}>⚠️</span>
                    )}
                  </div>
                  {isCurrentMonth && (
                    <div style={{
                      fontSize: '0.65rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      backgroundColor: 'var(--button-bg)',
                      color: '#fff',
                      padding: '3px 8px',
                      borderRadius: '12px',
                      letterSpacing: '0.5px'
                    }}>Current</div>
                  )}
                </div>
                
                {topCats.length === 0 ? (
                  <div style={{ 
                    fontSize: '0.85rem', 
                    color: 'var(--text-muted)',
                    textAlign: 'center',
                    padding: '20px 0',
                    fontStyle: 'italic'
                  }}>No scheduled days</div>
                ) : (
                  <>
                    <div style={{ 
                      fontSize: '0.75rem', 
                      color: 'var(--text-secondary)',
                      marginBottom: 10,
                      fontWeight: 500
                    }}>{totalDays} of {daysInMonth} days scheduled</div>
                    <div style={{ display: 'grid', gap: 8 }}>
                      {/* Show schedules with their custom colors instead of categories */}
                      {(() => {
                        // Count days per schedule for this month
                        const schedCounts = new Map();
                        const monthStart = new Date(calendarYear, entry.month, 1).getTime();
                        const monthEnd = new Date(calendarYear, entry.month + 1, 0).getTime();
                        
                        for (let day = 1; day <= daysInMonth; day++) {
                          const d = new Date(calendarYear, entry.month, day);
                          const t = d.getTime();
                          
                          for (const s of (schedules || [])) {
                            if (!s.start_date || !s.category_id) continue;
                            if (isScheduleActiveOnDay(s, t)) {
                              schedCounts.set(s.id, {
                                schedule: s,
                                count: (schedCounts.get(s.id)?.count || 0) + 1
                              });
                            }
                          }
                        }
                        
                        // Sort by count and take top 4
                        const topScheds = Array.from(schedCounts.values())
                          .sort((a, b) => b.count - a.count)
                          .slice(0, 4);
                        
                        return topScheds.map(({ schedule: s, count: cnt }) => {
                          const cat = catMap.get(s.category_id) || { name: 'Unknown', color: '#6c757d' };
                          const schedColor = s.color || cat.color;
                          const percentage = Math.round((cnt / daysInMonth) * 100);
                          return (
                            <div key={s.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem' }}>
                                <span style={{ 
                                  width: 14, 
                                  height: 14, 
                                  backgroundColor: schedColor, 
                                  display: 'inline-block', 
                                  borderRadius: 3,
                                  boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                                  flexShrink: 0
                                }} />
                                <span style={{ 
                                  flex: 1, 
                                  overflow: 'hidden', 
                                  textOverflow: 'ellipsis', 
                                  whiteSpace: 'nowrap',
                                  fontWeight: 500,
                                  color: 'var(--text-color)'
                                }}>{s.name}</span>
                                <span style={{ 
                                  color: 'var(--text-secondary)',
                                  fontSize: '0.8rem',
                                  fontWeight: 600,
                                  minWidth: '45px',
                                  textAlign: 'right'
                                }}>{cnt}d ({percentage}%)</span>
                              </div>
                              <div style={{
                                height: 4,
                                backgroundColor: darkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                                borderRadius: 2,
                                overflow: 'hidden'
                              }}>
                                <div style={{
                                  height: '100%',
                                  width: `${percentage}%`,
                                  backgroundColor: schedColor,
                                  transition: 'width 0.3s ease'
                                }} />
                              </div>
                            </div>
                          );
                        });
                      })()}
                      {(() => {
                        // Count total schedules active in this month
                        const totalScheds = (schedules || []).filter(s => {
                          if (!s.start_date || !s.category_id) return false;
                          for (let day = 1; day <= daysInMonth; day++) {
                            const d = new Date(calendarYear, entry.month, day);
                            if (isScheduleActiveOnDay(s, d.getTime())) return true;
                          }
                          return false;
                        }).length;
                        
                        return totalScheds > 4 && (
                          <div style={{ 
                            fontSize: '0.75rem', 
                            color: 'var(--text-muted)',
                            fontStyle: 'italic',
                            marginTop: 4
                          }}>+{totalScheds - 4} more schedules</div>
                        );
                      })()}
                    </div>
                  </>
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
              className="nx-input"
              type="text"
              placeholder="Schedule Name"
              value={scheduleForm.name}
              onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            />
            <select
              className="nx-select"
              value={scheduleForm.type}
              onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
              style={{ padding: '0.5rem' }}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
              <option value="holiday">Holiday</option>
              <option value="custom">Custom</option>
            </select>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Start Date & Time</label>
              <input
                className="nx-input"
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
                className="nx-input"
                type="datetime-local"
                value={scheduleForm.end_date}
                onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <select
              className="nx-select"
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
                className="nx-select"
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
                      end_date: toLocalInputFromDate(endDate),
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
          <div className="nx-field">
            <label className="nx-label">Playback Mode</label>
            <select
              className="nx-select"
              value={scheduleForm.shuffle ? 'random' : 'sequential'}
              onChange={(e) => setScheduleForm({
                ...scheduleForm,
                shuffle: e.target.value === 'random',
                playlist: e.target.value === 'sequential'
              })}
            >
              <option value="random">Random</option>
              <option value="sequential">Sequential</option>
            </select>
          </div>
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Fallback Category</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              When no schedule is active, this category will be used as the default for preroll selection.
            </p>
            <select
              className="nx-select"
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
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Calendar Color (Optional)</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Choose a custom color for this schedule on the calendar. If not set, the category's color will be used.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <input
                type="color"
                value={scheduleForm.color || '#3b82f6'}
                onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                style={{ width: '60px', height: '40px', border: '1px solid var(--border-color)', borderRadius: '4px', cursor: 'pointer' }}
              />
              <input
                className="nx-input"
                type="text"
                placeholder="#3b82f6"
                value={scheduleForm.color || ''}
                onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                style={{ padding: '0.5rem', width: '120px', fontFamily: 'monospace' }}
              />
              {scheduleForm.color && (
                <button
                  type="button"
                  className="button"
                  onClick={() => setScheduleForm({...scheduleForm, color: ''})}
                  style={{ padding: '0.5rem 1rem', backgroundColor: '#dc3545' }}
                >
                  Clear
                </button>
              )}
            </div>
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
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
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
                <label className="nx-label">Playback Mode</label>
                <select
                  className="nx-select"
                  value={scheduleForm.shuffle ? 'random' : 'sequential'}
                  onChange={(e) => setScheduleForm({
                    ...scheduleForm,
                    shuffle: e.target.value === 'random',
                    playlist: e.target.value === 'sequential'
                  })}
                >
                  <option value="random">Random</option>
                  <option value="sequential">Sequential</option>
                </select>
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">Calendar Color (Optional)</label>
                <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.5rem' }}>
                  Custom color for calendar display. Leave empty to use category color.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="color"
                    value={scheduleForm.color || '#3b82f6'}
                    onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                    style={{ width: '50px', height: '35px', border: '1px solid var(--border-color)', borderRadius: '4px', cursor: 'pointer' }}
                  />
                  <input
                    className="nx-input"
                    type="text"
                    placeholder="#3b82f6"
                    value={scheduleForm.color || ''}
                    onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                    style={{ flex: 1, fontFamily: 'monospace' }}
                  />
                  {scheduleForm.color && (
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => setScheduleForm({...scheduleForm, color: ''})}
                      style={{ padding: '0.5rem 0.75rem' }}
                    >
                      Clear
                    </button>
                  )}
                </div>
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
                    category_id: '', shuffle: false, playlist: false, fallback_category_id: '', color: ''
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
          {schedules.map(schedule => {
            const isCurrentlyActive = activeCategory && schedule.category_id === activeCategory.id;
            return (
              <div 
                key={schedule.id} 
                style={{ 
                  border: isCurrentlyActive ? '2px solid #4CAF50' : '1px solid var(--border-color)', 
                  padding: '1rem', 
                  borderRadius: '0.25rem', 
                  backgroundColor: isCurrentlyActive ? 'rgba(76, 175, 80, 0.1)' : 'var(--card-bg)',
                  boxShadow: isCurrentlyActive ? '0 0 10px rgba(76, 175, 80, 0.3)' : 'none',
                  position: 'relative'
                }}
              >
                {isCurrentlyActive && (
                  <div style={{
                    position: 'absolute',
                    top: '0.5rem',
                    right: '0.5rem',
                    backgroundColor: '#4CAF50',
                    color: 'white',
                    padding: '0.25rem 0.5rem',
                    borderRadius: '0.25rem',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    textTransform: 'uppercase'
                  }}>
                    Currently Running
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem', marginTop: isCurrentlyActive ? '1.5rem' : '0' }}>
                  <h3 style={{ margin: 0 }}>{schedule.name}</h3>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => handleEditSchedule(schedule)}
                      className="nx-iconbtn"
                    >
                      ✏️ Edit
                    </button>
                    <button
                      onClick={() => handleDeleteSchedule(schedule.id)}
                      className="nx-iconbtn nx-iconbtn--danger"
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
            );
          })}
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
              className="nx-select"
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
          zIndex={1000}
          allowBackgroundInteraction={!!editingPreroll}
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
                title="Save changes and apply to connected server"
              >
                Save & Apply to Server
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
                              type="button"
                              onClick={() => handleEditPreroll(p)}
                              className="nx-iconbtn"
                              style={{ marginRight: '0.25rem' }}
                              title="Edit preroll"
                            >
                              ✏️
                            </button>
                            <button
                              type="button"
                              onClick={() => handleCategoryRemovePreroll(editingCategory.id, p)}
                              className={`nx-iconbtn ${p.category_id === editingCategory.id ? 'nx-iconbtn--muted' : 'nx-iconbtn--danger'}`}
                              disabled={p.category_id === editingCategory.id}
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
                    className="nx-iconbtn"
                    title="Edit category"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeleteCategory(category.id)}
                    className="nx-iconbtn nx-iconbtn--danger"
                    title="Delete category"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>{category.description || 'No description'}</p>
              <p style={{ fontSize: '0.8rem', color: '#666' }}>Preroll Mode: {category.plex_mode === 'playlist' ? 'Sequential' : 'Random'}</p>

              {/* Apply to Server */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem', marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  {/* Status indicator removed per UX simplification */}
                  <div style={{ display: 'flex', gap: '0.25rem' }}>
                    <button
                      onClick={() => handleApplyCategoryToActiveServer(category.id, category.name)}
                      className="button"
                      style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
                      disabled={(() => { const s = getActiveConnectedServer(); return !s || s === 'conflict'; })() || applyingToServer}
                      title={applyingToServer ? "Applying to server..." : "Apply this category to the connected server"}
                    >
                      {applyingToServer ? '⏳ Applying...' : '🎬 Apply to Server'}
                    </button>
                    {plexStatus === 'Connected' && category.apply_to_plex && (
                      <button
                        onClick={() => handleRemoveCategoryFromPlex(category.id, category.name)}
                        className="button"
                        style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem', backgroundColor: '#6c757d' }}
                        title="Remove from Plex"
                      >
                        ❌ Remove
                      </button>
                    )}
                  </div>
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
    if (jellyfinStatus === 'Connected') {
      alert('Disconnect Jellyfin first (only one media server connection at a time).');
      return;
    }
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
    if (jellyfinStatus === 'Connected') {
      alert('Disconnect Jellyfin first (only one media server connection at a time).');
      return;
    }
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

  // Jellyfin connect/disconnect handlers
  const handleConnectJellyfin = (e) => {
    e.preventDefault();
    if (plexStatus === 'Connected') {
      alert('Disconnect Plex first (only one media server connection at a time).');
      return;
    }
    fetch('http://localhost:9393/jellyfin/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: jellyfinConfig.url,
        api_key: jellyfinConfig.api_key
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data && data.connected) {
          alert('Successfully connected to Jellyfin!');
          fetchData();
        } else {
          alert('Failed to connect to Jellyfin. Please check your URL and API key.');
        }
      })
      .catch(error => {
        console.error('Jellyfin connection error:', error);
        alert('Failed to connect to Jellyfin: ' + error.message);
      });
  };

  const handleDisconnectJellyfin = () => {
    if (!window.confirm('Are you sure you want to disconnect from Jellyfin? This will clear all stored connection settings.')) return;
    fetch('http://localhost:9393/jellyfin/disconnect', {
      method: 'POST'
    })
      .then(res => res.json())
      .then(() => {
        alert('Successfully disconnected from Jellyfin!');
        setJellyfinConfig({ url: '', api_key: '' });
        setJellyfinStatus('Disconnected');
        setJellyfinServerInfo(null);
        fetchData();
      })
      .catch(error => {
        console.error('Jellyfin disconnect error:', error);
        alert('Failed to disconnect from Jellyfin: ' + error.message);
      });
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
      if (jellyfinStatus === 'Connected') {
        alert('Disconnect Jellyfin first (only one media server connection at a time).');
        return;
      }
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
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)', marginBottom: '1rem' }}>
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
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)', marginBottom: '1rem' }}>
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
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)', marginBottom: '0.75rem' }}>
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
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
            When running NeXroll in Docker, use <strong>Method 3: Plex.tv Authentication</strong> above to connect.
            After connecting, configure <em>UNC/Local → Plex Path Mappings</em> in Settings to translate container/local paths
            (e.g., <code>/data/prerolls</code>) to the path Plex can see on its host
            (e.g., <code>Z:\Prerolls</code> or <code>\\NAS\share\Prerolls</code> on Windows, or <code>/mnt/prerolls</code> on Linux).
          </p>
        </div>

        {/* Remote Server Setup Guide */}
        <div style={{ marginTop: '2rem', padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>Connecting to Remote Plex Servers</h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)', marginBottom: '1rem' }}>
            If your Plex server is not on the same machine as NeXroll, you'll need to ensure remote access is configured:
          </p>
          <ul style={{ fontSize: '0.9rem', color: 'var(--text-color)', paddingLeft: '1.5rem', marginBottom: '1rem' }}>
            <li>Enable remote access in your Plex server settings</li>
            <li>Ensure your router forwards port 32400 to your Plex server</li>
            <li>Use your external IP address or domain name in the Server URL field</li>
            <li>If using HTTPS, include 'https://' in the URL</li>
          </ul>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>
            <strong>Example URLs:</strong><br/>
            Local: http://192.168.1.100:32400<br/>
            Remote: https://my-plex-server.example.com:32400<br/>
            Plex Cloud: https://app.plex.tv/desktop (use your server's URL)
          </p>
        </div>
      </div>

      <div className="card">
        <h2>Plex Status</h2>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div><strong>Connection:</strong> <span className={`nx-chip nx-status ${plexStatus === 'Connected' ? 'ok' : 'bad'}`}>{plexStatus}</span></div>
          <div><strong>Server URL:</strong> {plexServerInfo?.url || 'Not configured'}</div>
          <div><strong>Token:</strong> {plexServerInfo?.has_token ? '••••••••' : 'Not configured'}</div>
          {plexServerInfo?.token_source && (
            <div><strong>Token Source:</strong> {plexServerInfo.token_source === 'secure_store' ? 'Secure Store (Windows Credential Manager)' : plexServerInfo.token_source === 'database' ? 'Database' : plexServerInfo.token_source}</div>
          )}
          {plexServerInfo?.provider && (
            <div><strong>Storage Provider:</strong> {plexServerInfo.provider}</div>
          )}
          {plexServerInfo?.friendlyName && (
            <div><strong>Server Name:</strong> {plexServerInfo.friendlyName}</div>
          )}
          {plexServerInfo?.version && (
            <div><strong>Server Version:</strong> {plexServerInfo.version}</div>
          )}
          {plexServerInfo?.message && !plexServerInfo.connected && (
            <div style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'rgba(255, 193, 7, 0.1)', borderRadius: '8px', border: '1px solid rgba(255, 193, 7, 0.3)' }}>
              <strong>⚠️ Status:</strong> {plexServerInfo.message}
            </div>
          )}
          {plexServerInfo?.error && (
            <div style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'rgba(244, 67, 54, 0.1)', borderRadius: '8px', border: '1px solid rgba(244, 67, 54, 0.3)' }}>
              <strong>Error Type:</strong> {plexServerInfo.error}<br />
              {plexServerInfo.message && <span>{plexServerInfo.message}</span>}
            </div>
          )}
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

  const handleViewChangelog = async () => {
    try {
      const response = await fetch('http://localhost:9393/system/changelog');
      const data = await response.json();
      if (data.changelog) {
        setChangelogContent(data.changelog);
        setChangelogCurrentVersion(data.current_version);
        setShowChangelogModal(true);
      } else {
        alert('No changelog available');
      }
    } catch (err) {
      console.error('Failed to fetch changelog:', err);
      alert('Failed to load changelog');
    }
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

  const loadPathMappings = React.useCallback(async () => {
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
  }, []);

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

  const loadGenreMaps = React.useCallback(async () => {
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
  }, []);

  const loadGenreSettings = React.useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/settings/genre'));
      const data = await safeJson(res);
      if (data && typeof data === 'object') {
        setGenreSettings(data);
      }
    } catch (err) {
      console.error('Load genre settings error:', err);
    }
  }, []);


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
  }, [loadPathMappings]);

  // Auto-load genre mappings and settings when opening Settings tab
  React.useEffect(() => {
    if (activeTab === 'settings') {
      try { loadGenreMaps(); loadGenreSettings(); } catch {}
    }
  }, [activeTab, loadGenreMaps, loadGenreSettings]);

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
          <h2 style={{ display: 'inline' }}>Plex Settings</h2>
        </summary>
        <details className="card" open={!genreSettingsCollapsed} onToggle={(e) => setGenreSettingsCollapsed(!e.target.open)}>
          <summary style={{ cursor: 'pointer' }}>
            <h3 style={{ display: 'inline', margin: 0 }}>Genre-based Preroll Mapping {genreSettingsCollapsed ? '▶' : '▼'}</h3>
          </summary>

        {/* Master Toggle */}
        <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', marginTop: '1rem' }}>
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
                fetch(apiUrl('/system/apply-env-vars'), { method: 'POST' })
                  .then(res => res.json())
                  .then(data => {
                    if (data.success) {
                      alert('Windows environment variables applied successfully!');
                    } else {
                      alert('Failed to apply environment variables: ' + (data.detail || 'Unknown error'));
                    }
                  })
                  .catch(err => {
                    alert('Failed to apply environment variables: ' + err.message);
                  });
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
      {/* Path Mappings moved under Plex Settings */}
      <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem' }}>
        <h3 style={{ marginTop: 0 }}>Path Mappings (Plex)</h3>
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
      </div>
      </details>



      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Timezone Settings</h2>
        </summary>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Set your timezone to ensure schedules run at the correct local time.
        </p>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: 'var(--text-color)' }}>
              Current Timezone:
            </label>
            <select
              value={currentTimezone}
              onChange={(e) => saveTimezone(e.target.value)}
              disabled={timezoneLoading || timezoneSaving}
              style={{
                width: '100%',
                padding: '0.5rem',
                borderRadius: '0.25rem',
                border: '2px solid var(--border-color)',
                backgroundColor: darkMode ? '#2a2a2a' : '#ffffff',
                color: darkMode ? '#ffffff' : '#000000',
                cursor: timezoneSaving ? 'not-allowed' : 'pointer',
                fontSize: '1rem',
                opacity: timezoneLoading || timezoneSaving ? 0.6 : 1
              }}
            >
              {availableTimezones.length === 0 ? (
                <option value="UTC">Loading timezones...</option>
              ) : (
                availableTimezones.map((tz) => (
                  <option key={tz.value} value={tz.value} style={{ backgroundColor: darkMode ? '#2a2a2a' : '#ffffff', color: darkMode ? '#ffffff' : '#000000' }}>
                    {tz.label}
                  </option>
                ))
              )}
            </select>
            <p style={{ fontSize: '0.85rem', color: darkMode ? '#999' : '#666', marginTop: '0.25rem' }}>
              {timezoneLoading && 'Loading timezones...'}
              {timezoneSaving && 'Saving...'}
              {!timezoneLoading && !timezoneSaving && `Selected: ${currentTimezone}`}
            </p>
          </div>
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
          <div><strong>Installed Version:</strong> {systemVersion?.api_version || 'unknown'}</div>
          {systemVersion?.install_dir && <div><strong>Install Dir:</strong> {systemVersion.install_dir}</div>}
          <div><strong>FFmpeg:</strong> {ffmpegInfo ? (ffmpegInfo.ffmpeg_present ? ffmpegInfo.ffmpeg_version : 'Not found') : 'Detecting...'}</div>
          <div><strong>FFprobe:</strong> {ffmpegInfo ? (ffmpegInfo.ffprobe_present ? ffmpegInfo.ffprobe_version : 'Not found') : 'Detecting...'}</div>
        </div>
        <div style={{ marginTop: '0.75rem' }}>
          <button onClick={recheckFfmpeg} className="button">🔎 Re-check FFmpeg</button>
          <button onClick={handleShowSystemPaths} className="button" style={{ marginLeft: '0.5rem' }}>📂 Show Resolved Paths</button>
          <button onClick={handleDownloadDiagnostics} className="button" style={{ marginLeft: '0.5rem' }}>🧰 Download Diagnostics</button>
          <button onClick={handleViewChangelog} className="button" style={{ marginLeft: '0.5rem' }}>📋 View Changelog</button>
        </div>
      </div>

      {/* GitHub Issues Section */}
      <div className="card">
        <h2>🐛 Report Issues & Request Features</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Found a bug or have a feature request? Please submit it to our GitHub Issues page.
        </p>
        <div style={{ 
          padding: '1rem', 
          backgroundColor: 'var(--card-bg)', 
          border: '1px solid var(--border-color)', 
          borderRadius: '8px',
          marginBottom: '1rem'
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem' }}>📋 Before Reporting</h3>
          <ol style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', paddingLeft: '1.5rem', margin: 0 }}>
            <li>Download diagnostics using the button above (🧰 Download Diagnostics)</li>
            <li>Check existing issues to avoid duplicates</li>
            <li>Include your NeXroll version: <strong>{systemVersion?.api_version || 'unknown'}</strong></li>
            <li>Attach the diagnostics bundle to your issue</li>
            <li>Describe steps to reproduce the problem</li>
          </ol>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <a 
            href="https://github.com/JFLXCLOUD/NeXroll/issues/new?template=bug_report.md&labels=bug" 
            target="_blank" 
            rel="noopener noreferrer"
            className="button"
            style={{ textDecoration: 'none', backgroundColor: '#dc3545' }}
          >
            🐛 Report a Bug
          </a>
          <a 
            href="https://github.com/JFLXCLOUD/NeXroll/issues/new?template=feature_request.md&labels=enhancement" 
            target="_blank" 
            rel="noopener noreferrer"
            className="button"
            style={{ textDecoration: 'none', backgroundColor: '#28a745' }}
          >
            💡 Request a Feature
          </a>
          <a 
            href="https://github.com/JFLXCLOUD/NeXroll/issues" 
            target="_blank" 
            rel="noopener noreferrer"
            className="button"
            style={{ textDecoration: 'none' }}
          >
            📖 View All Issues
          </a>
        </div>
      </div>
    </div>
  );

  const renderJellyfin = () => (
    <div>
      <h1 className="header">Jellyfin Integration</h1>

      <div className="card">
        <h2>Connect to Jellyfin Server</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Connect your Jellyfin server to enable preroll management for Jellyfin.
        </p>
        <form onSubmit={handleConnectJellyfin}>
          <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                Jellyfin Server URL
              </label>
              <input
                type="url"
                placeholder="http://127.0.0.1:8096"
                value={jellyfinConfig.url}
                onChange={(e) => setJellyfinConfig({ ...jellyfinConfig, url: e.target.value })}
                required
                style={{ width: '100%', padding: '0.5rem' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                API Key
              </label>
              <input
                type="password"
                placeholder="Enter your Jellyfin API key"
                value={jellyfinConfig.api_key}
                onChange={(e) => setJellyfinConfig({ ...jellyfinConfig, api_key: e.target.value })}
                required
                style={{ width: '100%', padding: '0.5rem' }}
              />
              <details className="nx-plex-help" style={{ marginTop: '0.5rem' }}>
                <summary>How to create a Jellyfin API key</summary>
                <ol style={{ marginTop: '0.5rem' }}>
                  <li>Open Jellyfin Web</li>
                  <li>Go to Dashboard → Advanced → API Keys</li>
                  <li>Create a new API key and copy it</li>
                </ol>
              </details>
            </div>
          </div>
          <button type="submit" className="button button-success">
            Connect to Jellyfin
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Jellyfin Status</h2>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div><strong>Connection:</strong> <span className={`nx-chip nx-status ${jellyfinStatus === 'Connected' ? 'ok' : 'bad'}`}>{jellyfinStatus}</span></div>
          {jellyfinServerInfo && (
            <>
              {jellyfinServerInfo.name && <div><strong>Server:</strong> {jellyfinServerInfo.name}</div>}
              {jellyfinServerInfo.version && <div><strong>Version:</strong> {jellyfinServerInfo.version}</div>}
            </>
          )}
        </div>
        {jellyfinStatus === 'Connected' && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button onClick={handleDisconnectJellyfin} className="button button-danger">
              Disconnect from Jellyfin
            </button>
          </div>
        )}
      </div>
    </div>
  );

  const renderConnect = () => (
    <div className="nx-connect">
      <h1 className="header">Connections</h1>

      {/* Secondary tabs for media servers */}
      <div
        className="nx-tabs"
        role="tablist"
        aria-label="Media server"
        style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1rem' }}
      >
        <button
          type="button"
          role="tab"
          id="tab-plex"
          aria-selected={activeServer === 'plex'}
          aria-controls="panel-plex"
          className={`nx-tab ${activeServer === 'plex' ? 'active' : ''}`}
          onClick={() => setActiveServer('plex')}
          style={{
            padding: '0.5rem 0.75rem',
            border: 'none',
            borderBottom: activeServer === 'plex' ? '3px solid #f6685e' : '3px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--text-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontWeight: activeServer === 'plex' ? 'bold' : 'normal'
          }}
        >
          Plex
          <span
            className={`nx-chip nx-status ${plexStatus === 'Connected' ? 'ok' : 'bad'}`}
            style={{ fontSize: '0.75rem' }}
          >
            {plexStatus}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          id="tab-jellyfin"
          aria-selected={activeServer === 'jellyfin'}
          aria-controls="panel-jellyfin"
          className={`nx-tab ${activeServer === 'jellyfin' ? 'active' : ''}`}
          onClick={() => setActiveServer('jellyfin')}
          style={{
            padding: '0.5rem 0.75rem',
            border: 'none',
            borderBottom: activeServer === 'jellyfin' ? '3px solid #6c5ce7' : '3px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--text-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontWeight: activeServer === 'jellyfin' ? 'bold' : 'normal'
          }}
        >
          Jellyfin
          <span
            className={`nx-chip nx-status ${jellyfinStatus === 'Connected' ? 'ok' : 'bad'}`}
            style={{ fontSize: '0.75rem' }}
          >
            {jellyfinStatus}
          </span>
        </button>
      </div>

      {/* Context banner */}
      {(() => {
        const s = getActiveConnectedServer();
        if (s === 'conflict') {
          return (
            <div
              role="alert"
              style={{
                marginBottom: '1rem',
                padding: '0.75rem',
                border: '1px solid #dc3545',
                background: 'rgba(220,53,69,0.08)',
                color: '#dc3545',
                borderRadius: '6px'
              }}
            >
              Conflict detected: both Plex and Jellyfin are connected. Disconnect one before proceeding.
            </div>
          );
        }
        if (s === null) {
          return (
            <div
              role="note"
              style={{
                marginBottom: '1rem',
                padding: '0.75rem',
                border: '1px solid var(--border-color)',
                background: 'var(--card-bg)',
                borderRadius: '6px',
                color: 'var(--text-secondary, #666)'
              }}
            >
              No media server is connected. Choose a tab above and configure your server.
            </div>
          );
        }
        return (
          <div
            role="status"
            style={{
              marginBottom: '1rem',
              padding: '0.75rem',
              border: '1px solid var(--border-color)',
              background: 'var(--card-bg)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <span style={{ fontWeight: 'bold' }}>Active server:</span> {s === 'plex' ? 'Plex' : 'Jellyfin'}
          </div>
        );
      })()}

      {/* Active panel */}
      <div id={`panel-${activeServer}`} role="tabpanel" aria-labelledby={`tab-${activeServer}`}>
        {activeServer === 'plex' ? renderPlex() : renderJellyfin()}
      </div>
    </div>
  );

  const renderCommunityPrerolls = () => {
    // Handle Fair Use acceptance
    const handleAcceptFairUse = async () => {
      try {
        const response = await fetch(apiUrl('community-prerolls/fair-use/accept'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        setCommunityFairUseStatus(data);
        // Load initial data after accepting policy
        loadTop5Prerolls();
        loadLatestPrerolls();
        loadIndexStatus();
      } catch (error) {
        alert(`Failed to accept Fair Use Policy: ${error.message}`);
      }
    };

    // Load index status
    const loadIndexStatus = async () => {
      try {
        const response = await fetch(apiUrl('community-prerolls/index-status'));
        const data = await response.json();
        setCommunityIndexStatus(data);
      } catch (error) {
        console.error('Failed to load index status:', error);
      }
    };

    // Build/Refresh index with real-time progress
    const handleBuildIndex = async () => {
      if (communityIsBuilding) return;
      
      const confirmed = window.confirm(
        'Building the index will take 3-5 minutes and scan the entire Typical Nerds library.\n\n' +
        'This will make future searches MUCH faster (milliseconds instead of seconds).\n\n' +
        'Continue?'
      );
      
      if (!confirmed) return;
      
      setCommunityIsBuilding(true);
      setCommunityBuildProgress({
        progress: 0,
        current_dir: '',
        files_found: 0,
        dirs_visited: 0,
        message: 'Starting...'
      });
      
      // Start listening to progress updates via SSE
      const eventSource = new EventSource(apiUrl('community-prerolls/build-progress'));
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setCommunityBuildProgress(data);
        
        // Close connection when done and hide progress bar after showing 100%
        if (!data.building && data.progress === 100) {
          eventSource.close();
          // Show 100% briefly, then hide the progress bar
          setTimeout(() => {
            setCommunityBuildProgress(null);
          }, 1000);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        setCommunityBuildProgress(null);
        setCommunityIsBuilding(false);
      };
      
      try {
        // Trigger the build (this will run async on the server)
        const response = await fetch(apiUrl('community-prerolls/build-index'));
        
        if (response.status === 429) {
          const error = await response.json();
          alert(error.detail || 'Please wait before rebuilding the index.');
          eventSource.close();
          setCommunityBuildProgress(null);
          setCommunityIsBuilding(false);
          return;
        }
        
        const data = await response.json();
        
        // Wait for progress bar to finish displaying, then show alert
        setTimeout(() => {
          setCommunityIsBuilding(false);
          alert(
            `Index built successfully!\n\n` +
            `Total prerolls: ${data.total_prerolls}\n` +
            `Directories scanned: ${data.directories_visited}\n\n` +
            `Searches will now be instant!`
          );
          loadIndexStatus();
        }, 1500);
        
      } catch (error) {
        alert(`Failed to build index: ${error.message}`);
        setCommunityBuildProgress(null);
        eventSource.close();
        setCommunityIsBuilding(false);
      }
    };

    // Handle rematching all prerolls (clears existing matches first)
    const handleRematchAll = async () => {
      if (communityIsMigrating) return;
      
      const confirmMessage = 
        '⚠️ This will CLEAR all existing community preroll links and rematch them with the improved matching algorithm.\n\n' +
        'Use this if:\n' +
        '• Previous matches were incorrect\n' +
        '• You want to take advantage of improved matching\n' +
        '• You have many mismatched prerolls\n\n' +
        '⚠️ WARNING: This will reset ALL community preroll connections!\n\n' +
        'Your preroll files will NOT be modified or deleted.\n\n' +
        'Continue?';
      
      const confirmed = window.confirm(confirmMessage);
      if (!confirmed) return;
      
      setCommunityIsMigrating(true);
      setCommunityMigrationResult(null);
      setCommunityMigrationProgress({ status: 'Clearing existing matches...', scanned: 0, matched: 0 });
      
      try {
        // First, clear all existing matches
        const clearResponse = await fetch(apiUrl('community-prerolls/clear-matches'), {
          method: 'POST'
        });
        
        if (!clearResponse.ok) {
          throw new Error('Failed to clear existing matches');
        }
        
        setCommunityMigrationProgress({ status: 'Rematching prerolls...', scanned: 0, matched: 0 });
        
        // Then rematch with match_all=true
        const params = new URLSearchParams();
        params.append('match_all', 'true');
        
        const response = await fetch(apiUrl(`community-prerolls/migrate-legacy?${params.toString()}`), {
          method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success !== false) {
          setCommunityMigrationResult(data);
          setCommunityMigrationProgress({ 
            status: 'Complete!', 
            scanned: data.total_scanned, 
            matched: data.matched 
          });
          
          setCommunityMatchedCount(data.matched);
          await loadDownloadedCommunityIds();
          
          const message = data.matched > 0
            ? `✓ Successfully rematched ${data.matched} out of ${data.total_scanned} prerolls!\n\n` +
              (data.failed > 0 ? `${data.failed} prerolls couldn't be matched automatically.` : 'All scanned prerolls were matched!')
            : `No matches found.\n\nScanned ${data.total_scanned} prerolls but couldn't find matching titles in the community library.`;
          
          alert(message);
          
          setTimeout(() => setCommunityMigrationProgress(null), 5000);
        } else {
          alert(data.message || 'Rematch failed');
          setCommunityMigrationProgress(null);
        }
      } catch (error) {
        alert(`Failed to rematch prerolls: ${error.message}`);
        setCommunityMigrationProgress(null);
      } finally {
        setCommunityIsMigrating(false);
      }
    };

    // Handle matching existing prerolls to community library
    const handleMatchExisting = async (matchAll = false) => {
      if (communityIsMigrating) return;
      
      const confirmMessage = matchAll
        ? 'This will attempt to match ALL your existing prerolls to the community library.\n\n' +
          'This is useful if you manually downloaded community prerolls before using NeXroll.\n\n' +
          'Note: Only prerolls with matching titles will be marked as downloaded.\n\n' +
          'Continue?'
        : 'This will match prerolls that were downloaded from the community library but don\'t have tracking IDs yet.\n\n' +
          'This is a safe operation and won\'t modify your preroll files.\n\n' +
          'Continue?';
      
      const confirmed = window.confirm(confirmMessage);
      if (!confirmed) return;
      
      setCommunityIsMigrating(true);
      setCommunityMigrationResult(null);
      setCommunityMigrationProgress({ status: 'Starting...', scanned: 0, matched: 0 });
      
      try {
        const params = new URLSearchParams();
        if (matchAll) params.append('match_all', 'true');
        
        const response = await fetch(apiUrl(`community-prerolls/migrate-legacy?${params.toString()}`), {
          method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success !== false) {
          setCommunityMigrationResult(data);
          setCommunityMigrationProgress({ 
            status: 'Complete!', 
            scanned: data.total_scanned, 
            matched: data.matched 
          });
          
          // Update matched count for persistent display
          setCommunityMatchedCount(data.matched);
          
          // Refresh downloaded IDs to update UI
          await loadDownloadedCommunityIds();
          
          // Show success message
          const message = data.matched > 0
            ? `✓ Successfully matched ${data.matched} out of ${data.total_scanned} prerolls!\n\n` +
              (data.failed > 0 ? `${data.failed} prerolls couldn't be matched automatically.` : 'All scanned prerolls were matched!')
            : `No matches found.\n\nScanned ${data.total_scanned} prerolls but couldn't find matching titles in the community library.`;
          
          alert(message);
          
          // Clear progress after a delay
          setTimeout(() => setCommunityMigrationProgress(null), 5000);
        } else {
          alert(data.message || 'Migration failed');
          setCommunityMigrationProgress(null);
        }
      } catch (error) {
        alert(`Failed to match existing prerolls: ${error.message}`);
        setCommunityMigrationProgress(null);
      } finally {
        setCommunityIsMigrating(false);
      }
    };

    // Clean up display text - remove URL encoding and file extensions
    const cleanDisplayText = (text) => {
      if (!text) return text;
      
      // Decode URL encoding (%20 -> space, etc.)
      let cleaned = decodeURIComponent(text);
      
      // Remove leading ./ if present
      cleaned = cleaned.replace(/^\.\//, '');
      
      // Remove file extensions
      cleaned = cleaned.replace(/\.(mp4|mkv|avi|mov)$/i, '');
      
      // Clean up common patterns
      cleaned = cleaned
        .replace(/%2C/g, ',')  // Decode commas
        .replace(/%20/g, ' ')  // Decode spaces (backup)
        .replace(/,\s*The\s*-\s*AwesomeAustn/gi, '') // Remove "The - AwesomeAustn"
        .replace(/\s*-\s*AwesomeAustn/gi, '') // Remove "- AwesomeAustn"
        .replace(/_/g, ' ')    // Replace underscores with spaces
        .replace(/\s+/g, ' ')  // Collapse multiple spaces
        .trim();
      
      return cleaned;
    };

    // Handle search submission
    const handleSearch = async () => {
      if (!communitySearchQuery.trim() && !communitySearchPlatform.trim()) {
        alert('Please enter a search query or choose a platform');
        return;
      }

      setCommunityIsSearching(true);
      try {
        const params = new URLSearchParams();
        if (communitySearchQuery.trim()) params.append('query', communitySearchQuery.trim());
        if (communitySearchPlatform.trim()) params.append('platform', communitySearchPlatform.trim());
        params.append('limit', communityResultLimit);

        const response = await fetch(apiUrl(`community-prerolls/search?${params.toString()}`));
        
        if (response.status === 429) {
          const error = await response.json();
          alert(error.detail || 'Rate limit exceeded. Please wait before searching again.');
          return;
        }
        
        const data = await response.json();
        
        setCommunitySearchResults(data.results || []);
        setCommunityTotalResults(data.total || 0);
        
        // Show message if available (even with results)
        if (data.message) {
          console.log(`Community Prerolls: ${data.message}`);
        }
      } catch (error) {
        alert(`Search failed: ${error.message}`);
        setCommunitySearchResults([]);
      } finally {
        setCommunityIsSearching(false);
      }
    };

    // Handle random preroll fetch
    const handleRandomPreroll = async () => {
      setCommunityIsLoadingRandom(true);
      setCommunityRandomPreroll(null);
      try {
        const params = new URLSearchParams();
        if (communitySearchPlatform.trim()) params.append('platform', communitySearchPlatform.trim());

        const response = await fetch(apiUrl(`community-prerolls/random?${params.toString()}`));
        const data = await response.json();
        
        if (data.found && data.result) {
          setCommunityRandomPreroll(data.result);
        } else {
          alert(data.message || 'No random preroll found');
        }
      } catch (error) {
        alert(`Random fetch failed: ${error.message}`);
      } finally {
        setCommunityIsLoadingRandom(false);
      }
    };

    // Handle top 5 prerolls fetch
    const handleTop5Prerolls = async () => {
      setCommunityIsLoadingTop5(true);
      try {
        const params = new URLSearchParams();
        if (communitySearchPlatform.trim()) params.append('platform', communitySearchPlatform.trim());

        const response = await fetch(apiUrl(`community-prerolls/top5?${params.toString()}`));
        const data = await response.json();
        
        if (data.found && data.results) {
          setCommunityTop5Prerolls(data.results);
        } else {
          setCommunityTop5Prerolls([]);
        }
      } catch (error) {
        console.error('Top 5 fetch failed:', error);
        setCommunityTop5Prerolls([]);
      } finally {
        setCommunityIsLoadingTop5(false);
      }
    };

    // Check if a community preroll is already downloaded
    const isPrerollAlreadyDownloaded = (communityPreroll) => {
      if (!communityPreroll || !communityPreroll.id) return false;
      
      // Method 1: Check if this community preroll's ID is in our downloaded IDs list (for new downloads)
      if (downloadedCommunityIds.includes(String(communityPreroll.id))) {
        return true;
      }
      
      // Method 2: Check by title matching for legacy downloads (before ID tracking was implemented)
      if (!prerolls || prerolls.length === 0) return false;
      
      // Clean the community title (remove bug number prefix, normalize separators, remove extensions)
      const communityTitle = communityPreroll.title
        .replace(/^\d+\s*-\s*/, '')  // Remove bug number prefix
        .replace(/\.(mp4|mkv|avi|mov|webm)$/i, '')  // Remove extension if present
        .replace(/[_\-]/g, ' ')  // Normalize underscores and dashes to spaces
        .replace(/\s+/g, ' ')  // Normalize multiple spaces to single space
        .trim()
        .toLowerCase();
      
      // Check if any local preroll with "Downloaded from Community Prerolls" has a similar title
      return prerolls.some(p => {
        // Only check prerolls that were downloaded from community (legacy ones without ID)
        const isCommunityPreroll = p.description && p.description.includes('Downloaded from Community Prerolls');
        if (!isCommunityPreroll) return false;
        
        // Clean local title the same way
        const localTitle = (p.display_name || p.filename || '')
          .replace(/\.(mp4|mkv|avi|mov|webm)$/i, '')
          .replace(/[_\-]/g, ' ')
          .replace(/\s+/g, ' ')
          .trim()
          .toLowerCase();
        
        if (!localTitle) return false;
        
        // Only use exact match or very strict substring match
        // Method A: Exact match after normalization
        if (localTitle === communityTitle) return true;
        
        // Method B: STRICT substring match - only if one FULLY contains the other AND they're very similar in length
        if (localTitle.length >= 5 && communityTitle.length >= 5) {
          const lengthRatio = Math.min(localTitle.length, communityTitle.length) / Math.max(localTitle.length, communityTitle.length);
          
          // Must be >90% similar in length to avoid false positives (e.g., "Christmas" matching "Christmas Marvel Studios 2024")
          if (lengthRatio >= 0.9) {
            if (localTitle.includes(communityTitle) || communityTitle.includes(localTitle)) {
              return true;
            }
          }
        }
        
        return false;
      });
    };

    // Handle preroll download and import
    const handleDownload = async (preroll) => {
      if (!communitySelectedCategory && communityShowAddToCategory[preroll.id]) {
        alert('Please select a category');
        return;
      }

      // Show rename dialog
      setCommunityRenamingPreroll(preroll);
      // Default name removes the bug number prefix if present
      const defaultName = preroll.title.replace(/^\d+\s*-\s*/, '').trim();
      setCommunityNewPrerollName(defaultName);
    };

    const handleConfirmDownload = async () => {
      const preroll = communityRenamingPreroll;
      if (!preroll) return;

      const customName = communityNewPrerollName.trim() || preroll.title.replace(/^\d+\s*-\s*/, '').trim();

      setCommunityIsDownloading(prev => ({ ...prev, [preroll.id]: 'downloading' }));
      setCommunityRenamingPreroll(null);
      setCommunityNewPrerollName('');

      try {
        const response = await fetch(apiUrl('community-prerolls/download'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preroll_id: preroll.id,
            title: customName,
            url: preroll.url || preroll.download_url,
            category_id: communitySelectedCategory || null,
            add_to_category: communityShowAddToCategory[preroll.id] || false,
            tags: '',  // Always send empty tags - no auto-tagging
            description: `Community Preroll ID: ${preroll.id}`  // Add bug number to description
          })
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Download failed');
        }

        const result = await response.json();
        
        // Show processing status
        setCommunityIsDownloading(prev => ({ ...prev, [preroll.id]: 'processing' }));
        await new Promise(resolve => setTimeout(resolve, 500)); // Brief pause to show processing
        
        alert(`✅ Successfully downloaded "${result.display_name || result.filename}"!`);
        
        // Refresh downloaded IDs to update the UI
        await loadDownloadedCommunityIds();
        
        // Reset form
        setCommunityShowAddToCategory(prev => ({ ...prev, [preroll.id]: false }));
        setCommunitySelectedCategory(null);
        
      } catch (error) {
        alert(`❌ Download failed: ${error.message}`);
      } finally {
        setCommunityIsDownloading(prev => ({ ...prev, [preroll.id]: false }));
      }
    };

    // Rename modal before download
    if (communityRenamingPreroll) {
      return (
        <Modal
          title="Name Your Preroll"
          onClose={() => {
            setCommunityRenamingPreroll(null);
            setCommunityNewPrerollName('');
          }}
          width={600}
        >
          <div style={{ marginBottom: '1rem' }}>
            <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
              Customize the name for this preroll before downloading:
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Preroll Name:
              </label>
              <input
                type="text"
                value={communityNewPrerollName}
                onChange={(e) => setCommunityNewPrerollName(e.target.value)}
                placeholder="Enter custom name"
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  borderRadius: '4px',
                  border: '1px solid var(--border-color)',
                  backgroundColor: 'var(--input-bg)',
                  color: 'var(--text-color)',
                  fontSize: '1rem'
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleConfirmDownload();
                  }
                }}
                autoFocus
              />
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                Original: <strong>{communityRenamingPreroll.title}</strong>
                <br />
                Community ID #{communityRenamingPreroll.id} will be added to description for reference.
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                className="button"
                onClick={handleConfirmDownload}
                style={{ padding: '0.5rem 1.5rem' }}
              >
                ⬇️ Download
              </button>
              <button
                className="button-secondary"
                onClick={() => {
                  setCommunityRenamingPreroll(null);
                  setCommunityNewPrerollName('');
                }}
                style={{ padding: '0.5rem 1.5rem' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      );
    }

    // If Fair Use policy not accepted, show modal
    if (communityFairUseStatus && !communityFairUseStatus.accepted && communityPolicyText) {
      return (
        <Modal title="Community Prerolls - Fair Use Agreement Required" onClose={() => setActiveTab('dashboard')}>
          <div style={{ marginBottom: '1rem' }}>
            <p style={{ marginBottom: '1rem', fontWeight: '500' }}>
              Before accessing the Community Prerolls library, please read and accept the Fair Use Policy:
            </p>
            
            <div style={{
              backgroundColor: 'var(--card-bg)',
              color: 'var(--text-color)',
              padding: '1rem',
              borderRadius: '4px',
              maxHeight: '400px',
              overflow: 'auto',
              border: '1px solid var(--border-color)',
              fontSize: '0.9rem',
              lineHeight: '1.6',
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word'
            }}>
              {communityPolicyText}
            </div>

            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                className="button"
                onClick={handleAcceptFairUse}
                style={{ padding: '0.5rem 1rem' }}
              >
                ✓ Accept & Continue
              </button>
              <button
                className="button-secondary"
                onClick={() => setActiveTab('dashboard')}
                style={{ padding: '0.5rem 1rem' }}
              >
                ✕ Decline
              </button>
            </div>
          </div>
        </Modal>
      );
    }

    // Loading state
    if (communityFairUseStatus === null) {
      return (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <p>Loading Community Prerolls...</p>
        </div>
      );
    }

    // Main Community Prerolls interface
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ marginTop: 0, marginBottom: 0 }}>Search Community Prerolls Library</h2>
            <button
              onClick={async () => {
                // Re-show Fair Use Policy - fetch policy text if not already loaded
                if (!communityPolicyText) {
                  try {
                    const policyResponse = await fetch(apiUrl('community-prerolls/fair-use-policy'));
                    const policyData = await policyResponse.json();
                    setCommunityPolicyText(policyData.policy);
                  } catch (error) {
                    console.error('Failed to fetch policy text:', error);
                  }
                }
                setCommunityFairUseStatus({ accepted: false });
              }}
              className="button-secondary"
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
              title="View Fair Use Policy"
            >
              📋 Fair Use Policy
            </button>
          </div>
          
          {/* Index Status & Build Button */}
          {communityIndexStatus && (
            <div style={{
              padding: '0.75rem',
              backgroundColor: communityIndexStatus.exists 
                ? (communityIndexStatus.is_stale ? 'rgba(245, 158, 11, 0.1)' : 'rgba(34, 197, 94, 0.1)')
                : 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${communityIndexStatus.exists 
                ? (communityIndexStatus.is_stale ? 'rgba(245, 158, 11, 0.3)' : 'rgba(34, 197, 94, 0.3)')
                : 'rgba(239, 68, 68, 0.3)'}`,
              borderRadius: '4px',
              marginBottom: '1rem',
              fontSize: '0.9rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                {/* Status Message */}
                <div>
                  {communityIndexStatus.exists ? (
                    <>
                      {communityIndexStatus.is_stale ? (
                        <span>⚠️ <strong>Index is stale</strong> (last updated {Math.round(communityIndexStatus.age_days)} days ago)</span>
                      ) : (
                        <span>✨ <strong>Fast search enabled</strong></span>
                      )}
                    </>
                  ) : (
                    <span>💡 <strong>Build local index for instant searches</strong></span>
                  )}
                </div>
                
                {/* Indexed Prerolls Badge */}
                {communityIndexStatus.exists && communityIndexStatus.total_prerolls > 0 && (
                  <div style={{
                    padding: '0.3rem 0.6rem',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    border: '1px solid rgba(34, 197, 94, 0.3)',
                    borderRadius: '4px',
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap'
                  }}>
                    📚 <strong>{communityIndexStatus.total_prerolls}</strong> indexed
                  </div>
                )}
                
                {/* Matched Prerolls Badge */}
                {communityMatchedCount > 0 && (
                  <div style={{
                    padding: '0.3rem 0.6rem',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                    borderRadius: '4px',
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap'
                  }}>
                    🔗 <strong>{communityMatchedCount}</strong> matched
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  onClick={handleBuildIndex}
                  disabled={communityIsBuilding}
                  className="button-secondary"
                  style={{ 
                    padding: '0.4rem 0.8rem', 
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap'
                  }}
                  title={communityIndexStatus.exists ? 'Refresh index to get latest prerolls' : 'Build index for instant searches'}
                >
                  {communityIsBuilding ? '⏳ Building...' : (communityIndexStatus.exists ? '🔄 Refresh Index' : '⚡ Build Index')}
                </button>
                <button
                  onClick={() => handleMatchExisting(true)}
                  disabled={communityIsMigrating}
                  className="button-secondary"
                  style={{ 
                    padding: '0.4rem 0.8rem', 
                    fontSize: '0.85rem',
                    whiteSpace: 'nowrap'
                  }}
                  title="Match your existing prerolls to the community library"
                >
                  {communityIsMigrating ? '⏳ Matching...' : '🔗 Match Existing Prerolls'}
                </button>
                {communityIndexStatus.exists && (
                  <button
                    onClick={handleRematchAll}
                    disabled={communityIsMigrating}
                    className="button-secondary"
                    style={{ 
                      padding: '0.4rem 0.8rem', 
                      fontSize: '0.85rem',
                      whiteSpace: 'nowrap',
                      backgroundColor: darkMode ? 'rgba(245, 158, 11, 0.1)' : 'rgba(245, 158, 11, 0.15)',
                      border: darkMode ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(245, 158, 11, 0.4)',
                      color: darkMode ? 'rgba(245, 158, 11, 0.9)' : '#b45309'
                    }}
                    title="Clear all existing matches and rematch with improved algorithm"
                  >
                    {communityIsMigrating ? '⏳ Rematching...' : '🔄 Rematch All'}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Retro Progress Bar */}
          {communityBuildProgress && (
            <RetroProgressBar
              progress={communityBuildProgress.progress}
              currentDir={communityBuildProgress.current_dir}
              filesFound={communityBuildProgress.files_found}
              dirsVisited={communityBuildProgress.dirs_visited}
              message={communityBuildProgress.message}
            />
          )}

          {/* Match Existing Progress Bar */}
          {communityMigrationProgress && (
            <div style={{
              marginBottom: '1rem',
              padding: '1rem',
              backgroundColor: 'var(--card-bg, #f0f0f0)',
              border: '2px solid var(--border-color, #ddd)',
              borderRadius: '8px',
              fontFamily: "'Courier New', monospace"
            }}>
              <div style={{ 
                fontSize: '0.9rem', 
                marginBottom: '0.5rem',
                color: 'var(--text-color, #333)',
                fontWeight: 'bold'
              }}>
                🔗 Matching Prerolls to Community Library
              </div>
              <div style={{
                backgroundColor: 'var(--bg-color, #fff)',
                border: '1px solid var(--border-color, #ddd)',
                borderRadius: '4px',
                padding: '0.5rem',
                fontSize: '0.85rem',
                color: 'var(--text-color, #333)'
              }}>
                <div>Status: {communityMigrationProgress.status}</div>
                <div>Scanned: {communityMigrationProgress.scanned} prerolls</div>
                <div>Matched: {communityMigrationProgress.matched} prerolls</div>
              </div>
            </div>
          )}

          {/* Search Controls */}
          <div style={{ marginBottom: '1.5rem' }}>
            {/* Search Bar - 60% Width */}
            <div style={{ marginBottom: '1rem', width: '60%' }}>
              <div style={{ position: 'relative' }}>
                <div style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#888',
                  pointerEvents: 'none',
                  fontSize: '18px',
                  zIndex: 1
                }}>
                  🔍
                </div>
                <input
                  type="text"
                  placeholder="Search for prerolls... (e.g., Halloween, Christmas, Scary, Turkey)"
                  value={communitySearchQuery}
                  onChange={(e) => setCommunitySearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !communityIsSearching && handleSearch()}
                  style={{
                    width: '100%',
                    padding: '16px 16px 16px 48px',
                    border: '2px solid transparent',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-color)',
                    fontSize: '16px',
                    transition: 'all 0.2s ease',
                    outline: 'none',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#4f46e5';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
                    e.target.style.boxShadow = '0 4px 12px rgba(79, 70, 229, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'transparent';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                    e.target.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
                  }}
                />
              </div>
            </div>

            {/* Filters and Search Button Row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 200px',
              gap: '12px',
              alignItems: 'end'
            }}>
              {/* Platform Dropdown */}
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '13px', color: '#aaa' }}>
                  Platform
                </label>
                <select
                  value={communitySearchPlatform}
                  onChange={(e) => setCommunitySearchPlatform(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '14px',
                    border: '2px solid transparent',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-color)',
                    fontSize: '15px',
                    cursor: 'pointer',
                    outline: 'none',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                    transition: 'all 0.2s ease'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#4f46e5';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
                    e.target.style.boxShadow = '0 4px 12px rgba(79, 70, 229, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'transparent';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                    e.target.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
                  }}
                >
                  <option value="" style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>All Platforms</option>
                  <option value="plex" style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>Plex</option>
                  <option value="jellyfin" style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>Jellyfin</option>
                  <option value="emby" style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>Emby</option>
                </select>
              </div>

              {/* Limit Dropdown */}
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '13px', color: '#aaa' }}>
                  Results Limit
                </label>
                <select
                  value={communityResultLimit}
                  onChange={(e) => setCommunityResultLimit(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '14px',
                    border: '2px solid transparent',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-color)',
                    fontSize: '15px',
                    cursor: 'pointer',
                    outline: 'none',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                    transition: 'all 0.2s ease'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#4f46e5';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
                    e.target.style.boxShadow = '0 4px 12px rgba(79, 70, 229, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'transparent';
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                    e.target.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
                  }}
                >
                  <option value={10} style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>10 Results</option>
                  <option value={20} style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>20 Results</option>
                  <option value={50} style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>50 Results</option>
                  <option value={100} style={{ backgroundColor: '#2a2a2a', color: '#ffffff' }}>100 Results</option>
                </select>
              </div>

              {/* Search Button */}
              <button
                onClick={handleSearch}
                disabled={communityIsSearching}
                style={{
                  padding: '14px 24px',
                  border: 'none',
                  borderRadius: '12px',
                  backgroundColor: '#4f46e5',
                  color: '#ffffff',
                  fontSize: '15px',
                  fontWeight: '600',
                  cursor: communityIsSearching ? 'not-allowed' : 'pointer',
                  outline: 'none',
                  boxShadow: '0 2px 8px rgba(79, 70, 229, 0.3)',
                  transition: 'all 0.2s ease',
                  opacity: communityIsSearching ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  height: '52px'
                }}
                onMouseEnter={(e) => {
                  if (!communityIsSearching) {
                    e.target.style.backgroundColor = '#4338ca';
                    e.target.style.boxShadow = '0 4px 12px rgba(79, 70, 229, 0.4)';
                    e.target.style.transform = 'translateY(-1px)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = '#4f46e5';
                  e.target.style.boxShadow = '0 2px 8px rgba(79, 70, 229, 0.3)';
                  e.target.style.transform = 'translateY(0)';
                }}
              >
                <span style={{ fontSize: '18px' }}>{communityIsSearching ? '⏳' : '🔍'}</span>
                <span>{communityIsSearching ? 'Searching...' : 'Search'}</span>
              </button>
            </div>
          </div>

          {/* Search progress bar */}
          {communityIsSearching && (
            <div style={{
              marginBottom: '1rem',
              padding: '1rem',
              backgroundColor: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px'
            }}>
              <div style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                🔍 Searching Typical Nerds library...
              </div>
              <div style={{
                width: '100%',
                height: '4px',
                backgroundColor: 'var(--input-bg)',
                borderRadius: '2px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: '100%',
                  height: '100%',
                  background: 'linear-gradient(90deg, #3b82f6, #10b981, #3b82f6)',
                  backgroundSize: '200% 100%',
                  animation: 'progressSlide 1.5s ease-in-out infinite'
                }} />
              </div>
            </div>
          )}

          {/* Results count */}
          {communityTotalResults > 0 && (
            <div style={{
              padding: '0.5rem',
              backgroundColor: 'rgba(102, 200, 145, 0.1)',
              borderRadius: '4px',
              marginBottom: '1rem',
              fontSize: '0.9rem',
              color: 'var(--text-secondary)'
            }}>
              Found {communityTotalResults} preroll{communityTotalResults !== 1 ? 's' : ''} • Showing {communitySearchResults.length} results
            </div>
          )}
        </div>

        {/* Results List */}
        {communitySearchResults.length > 0 && (
          <div className="card">
            <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>
              Results ({communitySearchResults.length})
            </h3>

            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              {communitySearchResults.map(preroll => (
                <div
                  key={preroll.id}
                  style={{
                    backgroundColor: 'var(--card-bg)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'row',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    padding: '0.75rem',
                    alignItems: 'center',
                    gap: '1rem'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateX(2px)';
                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateX(0)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  {/* Icon */}
                  <div style={{
                    width: '60px',
                    height: '60px',
                    flexShrink: 0,
                    backgroundColor: 'rgba(100,100,100,0.2)',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-secondary)',
                    fontSize: '2rem'
                  }}>
                    🎬
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <h4 style={{
                      margin: '0 0 0.25rem 0',
                      fontSize: '1rem',
                      fontWeight: '600',
                      lineHeight: '1.3',
                      color: 'var(--text-color)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {cleanDisplayText(preroll.title)}
                    </h4>

                    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {preroll.creator && (
                        <span>👤 {cleanDisplayText(preroll.creator)}</span>
                      )}
                      {preroll.category && (
                        <span>📁 {cleanDisplayText(preroll.category)}</span>
                      )}
                      {preroll.duration && (
                        <span>⏱️ {preroll.duration}s</span>
                      )}
                      {preroll.file_size && preroll.file_size !== 'Unknown' && (
                        <span>📦 {preroll.file_size}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions column */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', minWidth: '200px' }}>
                    {/* Category selector */}
                    {communityShowAddToCategory[preroll.id] && (
                      <select
                        value={communitySelectedCategory || ''}
                        onChange={(e) => setCommunitySelectedCategory(e.target.value || null)}
                        style={{
                          width: '100%',
                          padding: '0.4rem',
                          fontSize: '0.85rem',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          backgroundColor: darkMode ? '#2a2a2a' : 'white',
                          color: darkMode ? '#ffffff' : '#333',
                          cursor: 'pointer'
                        }}
                      >
                        <option value="" style={{ backgroundColor: darkMode ? '#2a2a2a' : 'white', color: darkMode ? '#ffffff' : '#333' }}>Select category...</option>
                        {categories.map(cat => (
                          <option key={cat.id} value={cat.id} style={{ backgroundColor: darkMode ? '#2a2a2a' : 'white', color: darkMode ? '#ffffff' : '#333' }}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    )}

                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setCommunityPreviewingPreroll(preroll)}
                        className="button-secondary"
                        style={{
                          padding: '0.5rem',
                          fontSize: '0.8rem',
                          minWidth: '60px'
                        }}
                        title="Preview video"
                      >
                        ▶️ Preview
                      </button>
                      {isPrerollAlreadyDownloaded(preroll) ? (
                        <div
                          className="button"
                          style={{
                            flex: 1,
                            padding: '0.5rem',
                            fontSize: '0.8rem',
                            backgroundColor: 'rgba(102, 200, 145, 0.2)',
                            border: '1px solid rgba(102, 200, 145, 0.4)',
                            color: '#66c891',
                            cursor: 'default',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '0.3rem'
                          }}
                          title="This preroll is already in your collection"
                        >
                          ✓ Downloaded
                        </div>
                      ) : (
                        <button
                          onClick={() => handleDownload(preroll)}
                          disabled={communityIsDownloading[preroll.id] || (communityShowAddToCategory[preroll.id] && !communitySelectedCategory)}
                          className="button"
                          style={{
                            flex: 1,
                            padding: '0.5rem',
                            fontSize: '0.8rem',
                            opacity: communityIsDownloading[preroll.id] ? 0.6 : 1
                          }}
                        >
                          {communityIsDownloading[preroll.id] === 'downloading' ? '⬇️ Downloading...' : 
                           communityIsDownloading[preroll.id] === 'processing' ? '⚙️ Processing...' : 
                           '⬇️ Download'}
                        </button>
                      )}
                      <button
                        onClick={() => setCommunityShowAddToCategory(prev => ({
                          ...prev,
                          [preroll.id]: !prev[preroll.id]
                        }))}
                        className="button-secondary"
                        style={{
                          padding: '0.5rem',
                          fontSize: '0.8rem',
                          minWidth: '80px',
                          backgroundColor: communityShowAddToCategory[preroll.id] ? 'rgba(102, 200, 145, 0.2)' : undefined,
                          border: communityShowAddToCategory[preroll.id] ? '1px solid rgba(102, 200, 145, 0.4)' : undefined,
                          color: communityShowAddToCategory[preroll.id] ? '#66c891' : 'white'
                        }}
                      >
                        {communityShowAddToCategory[preroll.id] ? '✓ Category' : '+ Category'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {communitySearchResults.length === 0 && !communityIsSearching && (
          <div className="card" style={{
            textAlign: 'center',
            padding: '3rem 1rem',
            backgroundColor: 'var(--input-bg)',
            borderRadius: '6px'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎬</div>
            <p style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)' }}>
              {communityTotalResults === 0 && communitySearchQuery ? 
                `No results found for "${communitySearchQuery}". Try different keywords or browse by category.` :
                'No results yet. Start searching or browse by category and platform!'}
            </p>
            <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)', opacity: 0.7 }}>
              💡 Tip: Search by theme, holiday, genre, or franchise (e.g., "halloween", "thanksgiving", "christmas", "marvel", "star wars")
            </p>
          </div>
        )}

        {/* Discovery: Latest Prerolls Section */}
        <div className="card">
          <h3 style={{ 
            marginTop: 0, 
            marginBottom: '1rem', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem',
            fontSize: '1.3rem'
          }}>
            ✨ Discovery: Latest Prerolls
          </h3>
          
          {communityIsLoadingLatest ? (
            <div style={{ 
              textAlign: 'center', 
              padding: '2rem',
              color: 'var(--text-secondary)'
            }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⏳</div>
              <p>Loading latest prerolls...</p>
            </div>
          ) : communityLatestPrerolls.length > 0 ? (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '1.5rem',
              marginBottom: '1rem'
            }}>
              {communityLatestPrerolls.map((preroll, idx) => (
                <div
                  key={preroll.id}
                  style={{
                    backgroundColor: 'var(--card-bg)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-4px)';
                    e.currentTarget.style.boxShadow = '0 8px 16px rgba(0,0,0,0.2)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  {/* Thumbnail */}
                  <div style={{
                    width: '100%',
                    height: '160px',
                    backgroundColor: '#1a1a1a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    overflow: 'hidden'
                  }}>
                    <img
                      src={preroll.thumbnail}
                      alt={preroll.title}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover'
                      }}
                    />
                    {/* NEW badge overlay */}
                    <div style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      backgroundColor: '#10b981',
                      color: '#ffffff',
                      padding: '4px 12px',
                      borderRadius: '12px',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                    }}>
                      NEW
                    </div>
                  </div>
                  
                  {/* Content */}
                  <div style={{ padding: '1rem' }}>
                    <h4 style={{
                      margin: '0 0 0.5rem 0',
                      fontSize: '0.95rem',
                      fontWeight: '600',
                      lineHeight: '1.3',
                      color: 'var(--text-color)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      minHeight: '2.6em'
                    }}>
                      {cleanDisplayText(preroll.title)}
                    </h4>

                    <div style={{ 
                      display: 'flex', 
                      gap: '0.75rem', 
                      flexWrap: 'wrap', 
                      fontSize: '0.8rem', 
                      color: 'var(--text-secondary)',
                      marginBottom: '0.75rem'
                    }}>
                      {preroll.category && (
                        <span>📁 {cleanDisplayText(preroll.category)}</span>
                      )}
                      {preroll.duration && (
                        <span>⏱️ {preroll.duration}s</span>
                      )}
                    </div>

                    {/* Category selector */}
                    {communityShowAddToCategory[preroll.id] && (
                      <select
                        value={communitySelectedCategory || ''}
                        onChange={(e) => setCommunitySelectedCategory(e.target.value || null)}
                        className="category-select"
                        style={{
                          width: '100%',
                          padding: '0.4rem',
                          fontSize: '0.85rem',
                          border: '2px solid var(--border-color)',
                          borderRadius: '4px',
                          backgroundColor: darkMode ? '#2d2d2d' : 'white',
                          color: darkMode ? '#e0e0e0' : '#333',
                          cursor: 'pointer',
                          marginBottom: '0.5rem',
                          outline: 'none'
                        }}
                      >
                        <option value="" style={{backgroundColor: darkMode ? '#2d2d2d' : 'white', color: darkMode ? '#e0e0e0' : '#333'}}>Select category...</option>
                        {categories.map(cat => (
                          <option key={cat.id} value={cat.id} style={{backgroundColor: darkMode ? '#2d2d2d' : 'white', color: darkMode ? '#e0e0e0' : '#333'}}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    )}

                    {/* Action buttons */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          onClick={() => setCommunityPreviewingPreroll(preroll)}
                          className="button-secondary"
                          style={{
                            flex: 1,
                            padding: '0.5rem',
                            fontSize: '0.8rem'
                          }}
                        >
                          ▶️ Preview
                        </button>
                        {isPrerollAlreadyDownloaded(preroll) ? (
                          <div
                            className="button"
                            style={{
                              flex: 1,
                              padding: '0.5rem',
                              fontSize: '0.8rem',
                              backgroundColor: 'rgba(102, 200, 145, 0.2)',
                              border: '1px solid rgba(102, 200, 145, 0.4)',
                              color: '#66c891',
                              cursor: 'default',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.3rem'
                            }}
                            title="This preroll is already in your collection"
                          >
                            ✓ Downloaded
                          </div>
                        ) : (
                          <button
                            onClick={() => handleDownload(preroll)}
                            disabled={communityIsDownloading[preroll.id] || (communityShowAddToCategory[preroll.id] && !communitySelectedCategory)}
                            className="button"
                            style={{
                              flex: 1,
                              padding: '0.5rem',
                              fontSize: '0.8rem',
                              opacity: communityIsDownloading[preroll.id] ? 0.6 : 1
                            }}
                          >
                            {communityIsDownloading[preroll.id] === 'downloading' ? '⬇️ Downloading...' : 
                             communityIsDownloading[preroll.id] === 'processing' ? '⚙️ Processing...' : 
                             '⬇️ Download'}
                          </button>
                        )}
                      </div>
                      <button
                        onClick={() => setCommunityShowAddToCategory(prev => ({
                          ...prev,
                          [preroll.id]: !prev[preroll.id]
                        }))}
                        className="button-secondary"
                        style={{
                          padding: '0.5rem',
                          fontSize: '0.8rem',
                          backgroundColor: communityShowAddToCategory[preroll.id] ? 'rgba(102, 200, 145, 0.3)' : undefined,
                          border: communityShowAddToCategory[preroll.id] ? '1px solid rgba(102, 200, 145, 0.6)' : undefined,
                          color: darkMode ? undefined : (communityShowAddToCategory[preroll.id] ? '#047857' : undefined)
                        }}
                      >
                        {communityShowAddToCategory[preroll.id] ? '✓ Category Selected' : '+ Add to Category'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ 
              textAlign: 'center', 
              padding: '2rem',
              backgroundColor: 'var(--input-bg)',
              borderRadius: '6px'
            }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📦</div>
              <p style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)' }}>
                No latest prerolls available yet
              </p>
              <p style={{ margin: '0', fontSize: '0.85rem', color: 'var(--text-secondary)', opacity: 0.7 }}>
                💡 Build the local index to see the newest prerolls
              </p>
            </div>
          )}
        </div>

        {/* Random Preroll Section - Always Visible */}
        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            🎲 Random Preroll
          </h3>
          
          {/* Random Button */}
          <div style={{ marginBottom: '1rem', textAlign: 'center' }}>
            <button
              onClick={handleRandomPreroll}
              disabled={communityIsLoadingRandom}
              className="button"
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '1rem',
                backgroundColor: '#9333ea',
                minWidth: '200px'
              }}
            >
              <span style={{
                display: 'inline-block',
                animation: communityIsLoadingRandom ? 'diceRoll 0.8s ease-in-out infinite' : 'none'
              }}>
                🎲
              </span>
              {' '}
              {communityIsLoadingRandom ? 'Finding...' : 'Random Preroll'}
            </button>
          </div>

          {/* Dice Roll Animation CSS */}
          <style>{`
            @keyframes diceRoll {
              0% {
                transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg);
              }
              25% {
                transform: rotateX(180deg) rotateY(90deg) rotateZ(45deg);
              }
              50% {
                transform: rotateX(360deg) rotateY(180deg) rotateZ(90deg);
              }
              75% {
                transform: rotateX(540deg) rotateY(270deg) rotateZ(135deg);
              }
              100% {
                transform: rotateX(720deg) rotateY(360deg) rotateZ(180deg);
              }
            }
          `}</style>

          {/* Show result if exists, placeholder if not */}
          {communityRandomPreroll ? (
            <div style={{
              backgroundColor: 'var(--card-bg)',
              border: '2px solid #9333ea',
              borderRadius: '8px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'row',
              gap: '1.5rem',
              alignItems: 'center'
            }}>
              <div style={{
                width: '80px',
                height: '80px',
                flexShrink: 0,
                backgroundColor: 'rgba(147,51,234,0.2)',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '3rem'
              }}>
                🎬
              </div>
              
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text-color)' }}>
                  {cleanDisplayText(communityRandomPreroll.title)}
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  {cleanDisplayText(communityRandomPreroll.category)}
                </div>
                
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button
                    onClick={() => setCommunityPreviewingPreroll(communityRandomPreroll)}
                    className="button"
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#3b82f6'
                    }}
                  >
                    👁️ Preview
                  </button>
                  <button
                    onClick={() => {
                      setCommunityShowAddToCategory(prev => ({ ...prev, [communityRandomPreroll.id]: true }));
                    }}
                    className="button"
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#10b981'
                    }}
                  >
                    ⬇️ Download
                  </button>
                  <button
                    onClick={() => setCommunityRandomPreroll(null)}
                    className="button"
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#6b7280'
                    }}
                  >
                    ✕ Clear
                  </button>
                </div>
                
                {/* Download section */}
                {communityShowAddToCategory[communityRandomPreroll.id] && (
                  <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                    <select
                      value={communitySelectedCategory || ''}
                      onChange={(e) => setCommunitySelectedCategory(e.target.value ? Number(e.target.value) : null)}
                      className="form-select"
                      style={{
                        width: '100%',
                        padding: '0.5rem',
                        marginBottom: '0.75rem',
                        borderRadius: '4px',
                        fontSize: '1rem'
                      }}
                    >
                      <option value="">Select Category</option>
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleDownload(communityRandomPreroll)}
                      disabled={communityIsDownloading[communityRandomPreroll.id]}
                      className="button"
                      style={{
                        width: '100%',
                        padding: '0.5rem',
                        backgroundColor: '#10b981',
                        opacity: communityIsDownloading[communityRandomPreroll.id] ? 0.6 : 1
                      }}
                    >
                      {communityIsDownloading[communityRandomPreroll.id] === 'downloading' ? '⏳ Downloading...' : 
                       communityIsDownloading[communityRandomPreroll.id] === 'success' ? '✅ Downloaded!' : 
                       '⬇️ Confirm Download'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{
              textAlign: 'center',
              padding: '2rem',
              color: 'var(--text-secondary)',
              backgroundColor: 'rgba(147,51,234,0.1)',
              borderRadius: '8px',
              border: '1px dashed rgba(147,51,234,0.3)'
            }}>
              Click the button above to discover a random preroll from the community library!
            </div>
          )}
        </div>

        {/* Attribution Footer */}
        <div style={{
          padding: '1rem',
          backgroundColor: 'var(--card-bg)',
          border: '1px solid var(--border-color)',
          borderRadius: '6px',
          textAlign: 'center',
          fontSize: '0.85rem',
          color: 'var(--text-secondary)'
        }}>
          <p style={{ margin: '0.25rem 0' }}>
            Community prerolls powered by{' '}
            <a
              href="https://typicalnerds.uk/"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#f6685e',
                textDecoration: 'none',
                fontWeight: '600',
                transition: 'opacity 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.opacity = '0.8'}
              onMouseLeave={(e) => e.target.style.opacity = '1'}
            >
              Typical Nerds
            </a>
          </p>
          <p style={{ margin: '0.25rem 0', fontSize: '0.8rem' }}>
            Fair Use Policy applies. See above for details.
          </p>
        </div>
      </div>
    );
  };

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
            className={`tab-button ${activeTab === 'connect' ? 'active' : ''}`}
            onClick={() => setActiveTab('connect')}
          >
            Connect
          </button>
          <button
            className={`tab-button ${activeTab === 'community-prerolls' ? 'active' : ''}`}
            onClick={() => setActiveTab('community-prerolls')}
          >
            Community Prerolls
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
       {activeTab === 'connect' && renderConnect()}
       {activeTab === 'community-prerolls' && renderCommunityPrerolls()}
     </div>

     {/* Edit Preroll Modal - Global (can be triggered from any tab) */}
     {editingPreroll && (
       <Modal
         title="Edit Preroll"
         onClose={() => { setEditingPreroll(null); setEditForm({ display_name: '', new_filename: '', tags: '', category_id: '', category_ids: [], description: '' }); }}
         zIndex={1100}
         allowBackgroundInteraction={false}
       >
         <form onSubmit={handleUpdatePreroll}>
           {editingPreroll.filename && (
             <div style={{ 
               marginBottom: '1rem', 
               padding: '0.75rem', 
               backgroundColor: 'var(--card-bg, #f0f0f0)', 
               border: '1px solid var(--border-color, #ddd)',
               borderRadius: '4px', 
               fontSize: '0.9rem',
               color: 'var(--text-color, #333)'
             }}>
               <div><strong>Current file:</strong> {editingPreroll.filename}</div>
               {editingPreroll.category?.name && (
                 <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', opacity: 0.8 }}>
                   <strong>Category:</strong> {editingPreroll.category.name}
                 </div>
               )}
             </div>
           )}
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

     {/* Video Preview Modal */}
     {previewingPreroll && (
       <div style={{
         position: 'fixed',
         top: 0,
         left: 0,
         right: 0,
         bottom: 0,
         backgroundColor: 'rgba(0,0,0,0.5)',
         display: 'flex',
         alignItems: 'center',
         justifyContent: 'center',
         zIndex: 9999
       }}>
         <div style={{
           backgroundColor: 'white',
           padding: '20px',
           borderRadius: '8px',
           maxWidth: '80%',
           maxHeight: '80%'
         }}>
           <h3>Preview: {previewingPreroll.display_name || previewingPreroll.filename}</h3>
           <button onClick={() => setPreviewingPreroll(null)} style={{ float: 'right' }}>✕</button>
           <div>
             {(() => {
               console.log('Rendering simple modal for preroll:', previewingPreroll);
               console.log('Category info:', previewingPreroll.category);
               console.log('Category name:', previewingPreroll.category?.name);
               console.log('Filename:', previewingPreroll.filename);
               const videoUrl = apiUrl(`static/prerolls/${encodeURIComponent(previewingPreroll.category?.name || 'unknown')}/${encodeURIComponent(previewingPreroll.filename)}`);
               console.log('Video URL:', videoUrl);
               return (
                 <video
                   controls
                   autoPlay
                   muted
                   style={{ width: '100%', maxHeight: '400px' }}
                   onLoadStart={() => console.log('Video load started')}
                   onLoadedData={() => console.log('Video loaded data')}
                   onError={(e) => console.error('Video error:', e)}
                   onCanPlay={() => console.log('Video can play')}
                   onCanPlayThrough={() => console.log('Video can play through')}
                 >
                   <source src={videoUrl} type="video/mp4" />
                   Your browser does not support the video tag.
                 </video>
               );
             })()}
           </div>
         </div>
       </div>
     )}

     {/* Community Prerolls Video Preview Modal */}
     {communityPreviewingPreroll && (
       <div 
         style={{
           position: 'fixed',
           top: 0,
           left: 0,
           right: 0,
           bottom: 0,
           backgroundColor: 'rgba(0,0,0,0.8)',
           display: 'flex',
           alignItems: 'center',
           justifyContent: 'center',
           zIndex: 9999
         }}
         onClick={() => setCommunityPreviewingPreroll(null)}
       >
         <div 
           style={{
             backgroundColor: 'var(--card-bg)',
             padding: '20px',
             borderRadius: '8px',
             maxWidth: '90%',
             maxHeight: '90%',
             position: 'relative'
           }}
           onClick={(e) => e.stopPropagation()}
         >
           <div style={{ 
             display: 'flex', 
             justifyContent: 'space-between', 
             alignItems: 'center',
             marginBottom: '1rem'
           }}>
             <h3 style={{ margin: 0, color: 'var(--text-color)' }}>
               {communityPreviewingPreroll.title}
             </h3>
             <button 
               onClick={() => setCommunityPreviewingPreroll(null)}
               style={{
                 background: 'transparent',
                 border: 'none',
                 fontSize: '1.5rem',
                 cursor: 'pointer',
                 color: 'var(--text-color)',
                 padding: '0.25rem 0.5rem'
               }}
               title="Close preview"
             >
               ✕
             </button>
           </div>
           <div>
             <video
               controls
               autoPlay
               style={{ 
                 width: '100%', 
                 maxHeight: '70vh',
                 borderRadius: '4px'
               }}
               onError={(e) => {
                 console.error('Community preroll video error:', e);
                 alert('Failed to load video. The file may not be accessible.');
               }}
             >
               <source src={communityPreviewingPreroll.url} type="video/mp4" />
               Your browser does not support the video tag.
             </video>
           </div>
           <div style={{ 
             marginTop: '1rem', 
             fontSize: '0.85rem', 
             color: 'var(--text-secondary)',
             display: 'flex',
             gap: '1rem',
             flexWrap: 'wrap'
           }}>
             {communityPreviewingPreroll.creator && (
               <span>👤 Creator: {communityPreviewingPreroll.creator}</span>
             )}
             {communityPreviewingPreroll.category && (
               <span>📁 Category: {communityPreviewingPreroll.category}</span>
             )}
             {communityPreviewingPreroll.duration && (
               <span>⏱️ Duration: {communityPreviewingPreroll.duration}s</span>
             )}
           </div>
         </div>
       </div>
     )}

     {/* Changelog Modal - shown on first launch after update */}
     {showChangelogModal && (
       <Modal
         title={`What's New in NeXroll ${changelogCurrentVersion}`}
         onClose={async () => {
           setShowChangelogModal(false);
           // Mark this version as seen
           try {
             await fetch('http://localhost:9393/system/changelog/mark-seen', {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' }
             });
           } catch (err) {
             console.error('Failed to mark changelog as seen:', err);
           }
         }}
         width={900}
       >
         <div style={{
           maxHeight: '70vh',
           overflowY: 'auto',
           padding: '1rem',
           fontSize: '0.95rem',
           lineHeight: '1.6',
           backgroundColor: 'var(--bg-secondary)',
           borderRadius: '4px'
         }}>
           <ReactMarkdown
             components={{
               h1: ({node, ...props}) => <h1 style={{ fontSize: '1.8rem', marginBottom: '1rem', color: 'var(--text-primary)' }} {...props} />,
               h2: ({node, ...props}) => <h2 style={{ fontSize: '1.5rem', marginTop: '1.5rem', marginBottom: '0.75rem', color: 'var(--text-primary)', borderBottom: '2px solid var(--primary-color)' }} {...props} />,
               h3: ({node, ...props}) => <h3 style={{ fontSize: '1.2rem', marginTop: '1rem', marginBottom: '0.5rem', color: 'var(--primary-color)' }} {...props} />,
               ul: ({node, ...props}) => <ul style={{ marginLeft: '1.5rem', marginBottom: '0.75rem' }} {...props} />,
               li: ({node, ...props}) => <li style={{ marginBottom: '0.25rem' }} {...props} />,
               code: ({node, inline, ...props}) => inline 
                 ? <code style={{ backgroundColor: 'rgba(0,0,0,0.3)', padding: '0.2rem 0.4rem', borderRadius: '3px', fontFamily: 'monospace' }} {...props} />
                 : <code style={{ display: 'block', backgroundColor: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '4px', fontFamily: 'monospace', overflow: 'auto' }} {...props} />
             }}
           >
             {changelogContent}
           </ReactMarkdown>
         </div>
         <div style={{ marginTop: '1rem', textAlign: 'right' }}>
           <button
             onClick={async () => {
               setShowChangelogModal(false);
               try {
                 await fetch('http://localhost:9393/system/changelog/mark-seen', {
                   method: 'POST',
                   headers: { 'Content-Type': 'application/json' }
                 });
               } catch (err) {
                 console.error('Failed to mark changelog as seen:', err);
               }
             }}
             className="button"
             style={{ padding: '0.5rem 1.5rem' }}
           >
             Got it!
           </button>
         </div>
       </Modal>
     )}

     <footer
        className="nx-footer"
        aria-label="Site footer"
        style={{
          marginTop: '1rem',
          padding: '0.75rem 0.5rem',
          borderTop: '1px solid var(--border-color, #e0e0e0)',
          color: 'var(--text-secondary, #666)'
        }}
      >
        <div
          className="nx-footer-inner"
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.75rem',
            flexWrap: 'wrap'
          }}
        >
          <div className="nx-footer-left" style={{ fontSize: '0.85rem', color: 'var(--text-muted, #888)' }}>
            NeXroll {systemVersion?.api_version ? `v${systemVersion.api_version}` : ''}
          </div>
          <div className="nx-footer-links" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <a
              href="https://github.com/JFLXCLOUD/NeXroll"
              target="_blank"
              rel="noopener noreferrer"
              title="GitHub repository"
              style={{ color: 'var(--text-secondary, #666)', textDecoration: 'none' }}
            >
              GitHub
            </a>
            <span className="nx-footer-sep" aria-hidden="true" style={{ color: 'var(--text-muted, #999)' }}>•</span>
            <a
              href="https://ko-fi.com/j_b__"
              target="_blank"
              rel="noopener noreferrer"
              title="Support on Ko‑fi"
              style={{ color: 'var(--text-secondary, #666)', textDecoration: 'none' }}
            >
              Ko‑fi
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;