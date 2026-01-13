import React, { useState, useEffect, useRef, useCallback } from 'react';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import ReactMarkdown from 'react-markdown';
import RetroProgressBar from './components/RetroProgressBar';
import TestSequenceBuilder from './TestSequenceBuilder';
import SequenceBuilder from './components/SequenceBuilder';
import PatternImport from './components/PatternImport';
import PatternExport from './components/PatternExport';
import SequencePreviewModal from './components/SequencePreviewModal';
import { validateSequence, stringifySequence, parseSequence, cloneSequenceWithIds } from './utils/sequenceValidator';
import { 
    Calendar, CalendarDays, Clock, Play, Edit, Save, Trash, Upload, 
    Search, Folder, Film, BookOpen, Star, Plus, Settings, Target, CheckCircle, Link,
    Sun, Moon, RefreshCw, Download, AlertTriangle, Ban, Crown, Shuffle, Lock,
    ListOrdered, Palette, Lightbulb, Inbox, FolderOpen, Wrench, FileText, 
    Bug, Zap, Loader2, Package, FlaskConical, TreePine, Check, XCircle, Video, ChevronRight,
    Library, Clapperboard, Sparkles, PartyPopper, Users2, Theater, Eye, X, User, RefreshCcw, Menu
  } from 'lucide-react';// API helpers that resolve the backend base dynamically (works in Docker and behind proxies)
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
            <Star size={14} style={{ marginRight: '4px' }} /> {primaryItem.name}
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
              <Star size={14} />
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
                <Plus size={14} style={{ marginRight: '6px' }} /> Create "{normalizedQuery}"{creating ? '…' : ''}
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
                    <Star size={14} />
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false); // Mobile navigation menu
  const [openDropdown, setOpenDropdown] = useState(null); // For dropdown navigation
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
  // File upload ref for clearing input
  const fileInputRef = React.useRef(null);
  const [stableTokenInput, setStableTokenInput] = useState('');
  const [systemVersion, setSystemVersion] = useState(null);
  const [ffmpegInfo, setFfmpegInfo] = useState(null);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [showUpdateBanner, setShowUpdateBanner] = useState(false);
  const [activeCategory, setActiveCategory] = useState(null);
  const [activeScheduleIds, setActiveScheduleIds] = useState([]);
  
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
  
  const [categoryView, setCategoryView] = useState(() => {
    try { return localStorage.getItem('categoryView') || 'list'; } catch { return 'list'; }
  });
  const [categorySearchQuery, setCategorySearchQuery] = useState('');
  const [categorySortField, setCategorySortField] = useState('name');
  const [categorySortDirection, setCategorySortDirection] = useState('asc');
  const [showCreateCategoryModal, setShowCreateCategoryModal] = useState(false);
  
  // Bulk selection state
  const [selectedCategoryIds, setSelectedCategoryIds] = useState([]);
  const [bulkActionMode, setBulkActionMode] = useState(false);
  
  // Advanced filters
  const [categoryFilter, setCategoryFilter] = useState('all'); // 'all', 'active', 'hasPrerolls', 'empty'
  
  // Category colors (like schedules)
  const [categoryColors, setCategoryColors] = useState({}); // {categoryId: '#hexcolor'}
  
  // Templates
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [categoryTemplates, setCategoryTemplates] = useState([]);
  
  // Quick actions menu
  const [categoryMenuOpen, setCategoryMenuOpen] = useState(null); // categoryId or null
  
  // Export/Import
  const [showExportModal, setShowExportModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

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
  const [mapRootProgress, setMapRootProgress] = useState({ found: 0, processed: 0, phase: '' });
  const [mapRootResult, setMapRootResult] = useState(null); // Stores dry run or import result for inline display
  const [mapRootCategoryError, setMapRootCategoryError] = useState(false); // Highlight category selector when missing
  
  // Folder browser state for Import feature
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);
  const [folderBrowserPath, setFolderBrowserPath] = useState('');
  const [folderBrowserItems, setFolderBrowserItems] = useState([]);
  const [folderBrowserParent, setFolderBrowserParent] = useState(null);
  const [folderBrowserLoading, setFolderBrowserLoading] = useState(false);
  const [folderBrowserVideoCount, setFolderBrowserVideoCount] = useState(0);
  const [recentImportPaths, setRecentImportPaths] = useState(() => {
    try {
      const saved = localStorage.getItem('nexroll_recent_import_paths');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

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
  // Verbose logging state
  const [verboseLogging, setVerboseLogging] = useState(false);
  const [verboseLoggingLoading, setVerboseLoggingLoading] = useState(false);

  // Passive mode (coexistence mode) state
  const [passiveMode, setPassiveMode] = useState(false);
  const [passiveModeLoading, setPassiveModeLoading] = useState(false);

  // Clear when inactive state
  const [clearWhenInactive, setClearWhenInactive] = useState(false);
  const [clearWhenInactiveLoading, setClearWhenInactiveLoading] = useState(false);

  // UI Preferences state (stored in localStorage)
  const [confirmDeletions, setConfirmDeletions] = useState(() => {
    try { return JSON.parse(localStorage.getItem('confirmDeletions') || 'true'); } catch { return true; }
  });
  const [showNotifications, setShowNotifications] = useState(() => {
    try { return JSON.parse(localStorage.getItem('showNotifications') || 'true'); } catch { return true; }
  });
  const [weekStartsOnSunday, setWeekStartsOnSunday] = useState(() => {
    try { return JSON.parse(localStorage.getItem('weekStartsOnSunday') || 'true'); } catch { return true; }
  });
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
const [calendarMode, setCalendarMode] = useState('year'); // 'day' | 'month' | 'week' | 'year' - default to year view
const [calendarMonthView, setCalendarMonthView] = useState('grid'); // 'grid' | 'timeline' - default to grid view
const [calendarWeekStart, setCalendarWeekStart] = useState(() => {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day; // Get to Sunday
  return new Date(d.getFullYear(), d.getMonth(), diff);
});
const [calendarDay, setCalendarDay] = useState(() => new Date()); // For daily view - which day to show

// Calendar filter state
const [calendarFilterSchedules, setCalendarFilterSchedules] = useState([]); // Empty = show all, otherwise filter by schedule IDs
const [calendarFilterType, setCalendarFilterType] = useState('all'); // 'all', 'daily', 'weekly', 'monthly', 'yearly', 'holiday'
const [calendarShowConflictsOnly, setCalendarShowConflictsOnly] = useState(false); // Show only days with conflicts
const [calendarShowInactive, setCalendarShowInactive] = useState(false); // Show inactive schedules too

// Holiday Browser state
const [showHolidayBrowser, setShowHolidayBrowser] = useState(false);
const [holidayCountries, setHolidayCountries] = useState([]);
const [holidaySelectedCountry, setHolidaySelectedCountry] = useState('US');
const [holidaySelectedYear, setHolidaySelectedYear] = useState(() => new Date().getFullYear());
const [holidays, setHolidays] = useState([]);
const [holidaysLoading, setHolidaysLoading] = useState(false);
const [holidayApiStatus, setHolidayApiStatus] = useState(null);
const [holidaySearchQuery, setHolidaySearchQuery] = useState('');

// Date/time helpers: treat backend datetimes as naive local times
// The backend stores dates exactly as entered by the user (no timezone conversion)
// so we can use them directly without any timezone manipulation
const toLocalInputValue = (isoOrNaive) => {
  if (!isoOrNaive) return '';
  // Handle ISO string - just take the date and time portion (YYYY-MM-DDTHH:MM)
  // Remove any timezone info if present (shouldn't be with new backend, but be safe)
  let s = isoOrNaive;
  if (s.endsWith('Z')) {
    s = s.slice(0, -1);
  }
  // Remove timezone offset like +00:00 or -07:00
  const offsetMatch = s.match(/[+-]\d{2}:\d{2}$/);
  if (offsetMatch) {
    s = s.slice(0, -6);
  }
  // Remove seconds if present (datetime-local input doesn't need them)
  if (s.length > 16 && s[16] === ':') {
    s = s.slice(0, 16);
  }
  return s;
};
const toLocalDisplay = (isoOrNaive) => {
  if (!isoOrNaive) return 'N/A';
  try {
    // Parse the naive datetime string and display it
    // Since it's stored as local time, we create a date without timezone conversion
    let s = isoOrNaive;
    if (s.endsWith('Z')) {
      s = s.slice(0, -1);
    }
    const offsetMatch = s.match(/[+-]\d{2}:\d{2}$/);
    if (offsetMatch) {
      s = s.slice(0, -6);
    }
    // Parse as local time by treating the string as a local datetime
    const [datePart, timePart] = s.split('T');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hour, minute] = (timePart || '00:00').split(':').map(Number);
    const d = new Date(year, month - 1, day, hour, minute);
    // Format without seconds: "1/1/2026, 7:00 AM"
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
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

// Parse a naive ISO datetime string into a Date object
// Since schedules are stored as naive local time, we parse them directly
// without any timezone conversion
const parseNaiveDatetime = (isoOrNaive) => {
  if (!isoOrNaive) return null;
  // Remove any timezone info if present
  let s = isoOrNaive;
  if (s.endsWith('Z')) {
    s = s.slice(0, -1);
  }
  const offsetMatch = s.match(/[+-]\d{2}:\d{2}$/);
  if (offsetMatch) {
    s = s.slice(0, -6);
  }
  // Parse as local time
  const [datePart, timePart] = s.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = (timePart || '00:00').split(':').map(Number);
  return new Date(year, month - 1, day, hour || 0, minute || 0);
};

// Helper function to check if a schedule is active on a specific day
const isScheduleActiveOnDay = (schedule, dayTime, normalizeDay) => {
  if (!schedule.start_date) return false;
  const dayDate = new Date(dayTime);
  
  // For yearly/holiday schedules, skip the year-based date range check
  // These schedules repeat every year based on month/day only
  if (schedule.type === 'yearly' || schedule.type === 'holiday') {
    const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
    const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
    const [, startMonth, startDay] = startDateStr.split('-').map(Number);
    const [, endMonth, endDay] = endDateStr.split('-').map(Number);
    const schedStartMonth = startMonth - 1;
    const schedStartDay = startDay;
    const schedEndMonth = endMonth - 1;
    const schedEndDay = endDay;
    const dayMonth = dayDate.getMonth();
    const dayDay = dayDate.getDate();
    
    // Handle same-month range (e.g., Dec 1-31)
    if (schedStartMonth === schedEndMonth) {
      return dayMonth === schedStartMonth && dayDay >= schedStartDay && dayDay <= schedEndDay;
    }
    
    // Handle year-wrapping range (e.g., Dec 15 - Jan 15)
    if (schedStartMonth > schedEndMonth) {
      // Schedule wraps around year end
      return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
             (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
             (dayMonth > schedStartMonth) ||  // After start month in same year
             (dayMonth < schedEndMonth);       // Before end month in next year
    }
    
    // Handle multi-month range within same year (e.g., Oct 15 - Dec 31)
    return (dayMonth === schedStartMonth && dayDay >= schedStartDay) ||
           (dayMonth === schedEndMonth && dayDay <= schedEndDay) ||
           (dayMonth > schedStartMonth && dayMonth < schedEndMonth);
  }
  
  // For non-yearly schedules, check if the day is within the schedule's overall date range
  const sDay = normalizeDay(schedule.start_date);
  const eDay = schedule.end_date ? normalizeDay(schedule.end_date) : Infinity;
  if (dayTime < sDay || dayTime > eDay) return false;
  
  // Check recurrence pattern for monthly, weekly, daily schedules
  if (schedule.recurrence_pattern) {
    try {
      const pattern = JSON.parse(schedule.recurrence_pattern);
      
      // Monthly: Check if day of month matches
      if (schedule.type === 'monthly' && pattern.monthDays && pattern.monthDays.length > 0) {
        const dayOfMonth = dayDate.getDate();
        return pattern.monthDays.includes(dayOfMonth);
      }
      
      // Weekly: Check if day of week matches
      if (schedule.type === 'weekly' && pattern.weekDays && pattern.weekDays.length > 0) {
        const dayOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'][dayDate.getDay()];
        return pattern.weekDays.includes(dayOfWeek);
      }
      
      // Daily: Always true if within date range (time-of-day check would be backend's job)
      if (schedule.type === 'daily') {
        return true;
      }
    } catch (e) {
      console.error('Failed to parse recurrence pattern:', e);
    }
  }
  
  // Default: schedule is active if day is within start/end date range
  return true;
};

  // Schedule form state
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    type: 'monthly',
    start_date: '',
    end_date: '',
    category_id: '',
    shuffle: true,
    playlist: false,
    fallback_category_id: '',
    color: '',
    blend_enabled: false,
    priority: 5,
    exclusive: false
  });

  // Sequence Builder state
  const [scheduleMode, setScheduleMode] = useState('simple'); // 'simple' or 'advanced'
  const [sequenceBlocks, setSequenceBlocks] = useState([]);
  const [savedSequences, setSavedSequences] = useState([]);
  const [sequencesLoading, setSequencesLoading] = useState(false);
  const [showSequenceImportModal, setShowSequenceImportModal] = useState(false);
  const [showSequenceExportModal, setShowSequenceExportModal] = useState(false);
  const [exportingSequence, setExportingSequence] = useState(null); // Sequence being exported
  const [showSequencePreviewModal, setShowSequencePreviewModal] = useState(false);
  const [previewingSequence, setPreviewingSequence] = useState(null); // Sequence being previewed
  const [editingSequenceId, setEditingSequenceId] = useState(null); // Track which sequence is being edited
  const [editingSequenceName, setEditingSequenceName] = useState(''); // Track sequence name when editing
  const [editingSequenceDescription, setEditingSequenceDescription] = useState(''); // Track description when editing

  // Recurrence pattern state
  const [weekDays, setWeekDays] = useState([]);  // For weekly: ['monday', 'wednesday', 'friday']
  const [monthDays, setMonthDays] = useState([]); // For monthly: [1, 15, 30]
  const [timeRange, setTimeRange] = useState({ start: '', end: '' }); // For daily time ranges

  // Active Schedules display state
  const [scheduleSearchQuery, setScheduleSearchQuery] = useState('');
  const [scheduleFilterType, setScheduleFilterType] = useState('all'); // 'all', 'daily', 'weekly', 'monthly', 'yearly', 'holiday'
  const [scheduleViewMode, setScheduleViewMode] = useState('compact'); // 'compact' or 'detailed'
  const [scheduleCurrentPage, setScheduleCurrentPage] = useState(1);
  const schedulesPerPage = 10;

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
    description: '',
    exclude_from_matching: false
  });

  // Auto-match state
  const [autoMatchLoading, setAutoMatchLoading] = useState(false);
  const [similarMatches, setSimilarMatches] = useState([]);

  // Filter state
  const [filterTags, setFilterTags] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterMatchStatus, setFilterMatchStatus] = useState(''); // Filter by community match status
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
  
  useEffect(() => {
    try { localStorage.setItem('categoryView', categoryView); } catch {}
  }, [categoryView]);

  // Persist and clamp preroll pagination
  useEffect(() => {
    try { localStorage.setItem('prerollPageSize', String(pageSize)); } catch {}
  }, [pageSize]);

  // Persist UI preferences
  useEffect(() => {
    try { localStorage.setItem('confirmDeletions', JSON.stringify(confirmDeletions)); } catch {}
  }, [confirmDeletions]);

  useEffect(() => {
    try { localStorage.setItem('showNotifications', JSON.stringify(showNotifications)); } catch {}
  }, [showNotifications]);

  useEffect(() => {
    try { localStorage.setItem('weekStartsOnSunday', JSON.stringify(weekStartsOnSunday)); } catch {}
  }, [weekStartsOnSunday]);

  // Helper functions that respect user preferences
  const showConfirm = (message) => {
    if (!confirmDeletions) return true; // Skip confirmation if disabled
    return window.confirm(message);
  };

  // Store original alert function to avoid recursion
  const originalAlert = useRef(window.alert).current;
  
  const showAlert = (message, type = 'info') => {
    // Determine if this is an error message
    const isError = type === 'error' || 
                    (typeof message === 'string' && (
                      message.toLowerCase().includes('error') ||
                      message.toLowerCase().includes('failed') ||
                      message.toLowerCase().includes('cannot')
                    ));
    
    // Always show errors, but respect showNotifications for success/info messages
    if (isError || showNotifications) {
      originalAlert(message);
    }
  };

  // Override global alert to respect notifications setting
  useEffect(() => {
    const origAlert = window.alert;
    window.alert = (message) => {
      showAlert(message, 'info');
    };
    return () => {
      window.alert = origAlert;
    };
  }, [showNotifications]); // Re-bind when setting changes

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

  // Close category menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (categoryMenuOpen !== null) {
        setCategoryMenuOpen(null);
      }
    };
    
    if (categoryMenuOpen !== null) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [categoryMenuOpen]);

  // Close dropdown menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (openDropdown !== null) {
        setOpenDropdown(null);
      }
    };
    
    if (openDropdown !== null) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [openDropdown]);

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

  // === Holiday Browser API Functions ===
  const loadHolidayCountries = async () => {
    try {
      const res = await fetch(apiUrl('/holiday-api/countries'));
      const data = await safeJson(res);
      if (res.ok && data?.countries && Array.isArray(data.countries)) {
        setHolidayCountries(data.countries);
      } else if (res.ok && Array.isArray(data)) {
        setHolidayCountries(data);
      }
    } catch (e) {
      console.error('Load holiday countries error:', e);
    }
  };

  const loadHolidays = async (countryCode, year) => {
    setHolidaysLoading(true);
    try {
      const res = await fetch(apiUrl(`/holiday-api/holidays/${countryCode}/${year}`));
      const data = await safeJson(res);
      if (res.ok && data?.holidays && Array.isArray(data.holidays)) {
        setHolidays(data.holidays);
      } else if (res.ok && Array.isArray(data)) {
        setHolidays(data);
      } else {
        setHolidays([]);
      }
    } catch (e) {
      console.error('Load holidays error:', e);
      setHolidays([]);
    } finally {
      setHolidaysLoading(false);
    }
  };

  const checkHolidayApiStatus = async () => {
    try {
      const res = await fetch(apiUrl('/holiday-api/status'));
      const data = await safeJson(res);
      setHolidayApiStatus(data);
    } catch (e) {
      setHolidayApiStatus({ status: 'offline', error: e.message });
    }
  };

  const createScheduleFromHoliday = async (holiday, categoryId) => {
    try {
      const res = await fetch(apiUrl('/holiday-api/create-schedule'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          holiday_name: holiday.name,
          holiday_date: holiday.date,
          country_code: holidaySelectedCountry,
          category_id: categoryId,
          multi_year: true,
          years_ahead: 5
        })
      });
      const data = await safeJson(res);
      if (res.ok) {
        alert(`✅ Schedule "${holiday.name}" created successfully!`);
        // Refresh schedules
        const schedRes = await fetch(apiUrl('/schedules'));
        const schedData = await safeJson(schedRes);
        if (schedRes.ok) setSchedules(schedData);
        setShowHolidayBrowser(false);
      } else {
        alert(`❌ Failed to create schedule: ${data?.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Create holiday schedule error:', e);
      alert(`❌ Error: ${e.message}`);
    }
  };

  // === Shared toggle schedule handler (DRY - used by both compact and detailed views) ===
  const handleToggleSchedule = React.useCallback(async (schedule, viewName = '') => {
    console.log(`Toggle clicked (${viewName}) - Current is_active:`, schedule.is_active, 'Schedule ID:', schedule.id);
    
    // Store the original state for reverting if needed
    const originalActiveState = schedule.is_active;
    const newActiveState = !originalActiveState;
    
    // Optimistically update the UI
    setSchedules(prevSchedules => 
      prevSchedules.map(s => 
        s.id === schedule.id ? { ...s, is_active: newActiveState } : s
      )
    );
    
    try {
      // Format dates correctly for backend
      const formatDateForBackend = (dateStr) => {
        if (!dateStr) return '';
        try {
          const d = new Date(dateStr);
          return d.toISOString().slice(0, 16);
        } catch {
          return '';
        }
      };
      
      const requestData = {
        name: schedule.name,
        type: schedule.type,
        start_date: formatDateForBackend(schedule.start_date),
        end_date: formatDateForBackend(schedule.end_date),
        category_id: schedule.category_id,
        shuffle: schedule.shuffle || false,
        playlist: schedule.playlist || false,
        recurrence_pattern: schedule.recurrence_pattern || '',
        preroll_ids: schedule.preroll_ids || '',
        fallback_category_id: schedule.fallback_category_id || null,
        sequence: typeof schedule.sequence === 'object' ? JSON.stringify(schedule.sequence) : (schedule.sequence || ''),
        color: schedule.color || '',
        is_active: newActiveState
      };
      
      console.log(`Toggle request (${viewName}):`, requestData);
      
      const response = await fetch(apiUrl(`schedules/${schedule.id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });
      
      if (response.ok) {
        console.log('Toggle success! State updated.');
        // Give backend a moment to persist, then sync
        setTimeout(() => fetchData(), 500);
      } else {
        // Revert optimistic update on failure
        setSchedules(prevSchedules => 
          prevSchedules.map(s => 
            s.id === schedule.id ? { ...s, is_active: originalActiveState } : s
          )
        );
        const errorText = await response.text();
        console.error('Toggle failed - Status:', response.status);
        console.error('Toggle failed - Response:', errorText);
        alert('Failed to update schedule: ' + errorText);
      }
    } catch (err) {
      // Revert optimistic update on error
      setSchedules(prevSchedules => 
        prevSchedules.map(s => 
          s.id === schedule.id ? { ...s, is_active: originalActiveState } : s
        )
      );
      console.error('Error toggling schedule:', err);
      alert('Error updating schedule: ' + err.message);
    }
  }, []);

  // eslint-disable-next-line no-use-before-define
  const fetchData = React.useCallback(() => {
    // Always fetch all prerolls (no filter) for global state, filter in dashboard UI only
    return Promise.all([
      fetch(apiUrl('plex/status')),
      fetch(apiUrl('jellyfin/status')),
      fetch(apiUrl('prerolls')),
      fetch(apiUrl('schedules')),
      fetch(apiUrl('categories')),
      fetch(apiUrl('holiday-presets')),
      fetch(apiUrl('scheduler/status')),
      fetch(apiUrl('tags')),
      fetch(apiUrl('community-templates')),
      fetch(apiUrl('plex/stable-token/status')),
      fetch(apiUrl('system/version')),
      fetch(apiUrl('system/ffmpeg-info')),
      fetch(apiUrl('genres/recent-applications')),
      fetch(apiUrl('settings/active-category')),
      fetch(apiUrl('scheduler/active-schedule-ids')),
      fetch(apiUrl('community-prerolls/index-status')),
      fetch(apiUrl('community-prerolls/downloaded-ids'))
    ]).then(responses => Promise.all(responses.map(safeJson)))
      .then(([plex, jellyfin, prerolls, schedules, categories, holidays, scheduler, tags, templates, stableToken, sysVersion, ffmpeg, recentGenreApps, activeCat, activeScheduleIdsData, communityIndex, communityDownloaded]) => {
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
        // Set active category
        if (activeCat?.__error) {
          setActiveCategory(null);
        } else if (activeCat?.active_category) {
          setActiveCategory(activeCat.active_category);
        } else {
          setActiveCategory(null);
        }
        // Set active schedule IDs
        if (activeScheduleIdsData?.active_schedule_ids) {
          setActiveScheduleIds(activeScheduleIdsData.active_schedule_ids);
        } else {
          setActiveScheduleIds([]);
        }
        // Set community preroll index status (for dashboard tile)
        if (communityIndex && !communityIndex.__error) {
          setCommunityIndexStatus(communityIndex);
        }
        // Set community matched count (for dashboard tile)
        if (communityDownloaded?.downloaded_ids) {
          setCommunityMatchedCount(communityDownloaded.downloaded_ids.length);
          setDownloadedCommunityIds(communityDownloaded.downloaded_ids);
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
        const response = await fetch(apiUrl('system/changelog'));
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

    // Check for duplicates first
    const duplicateChecks = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const checkFormData = new FormData();
      checkFormData.append('file', file);
      
      try {
        const checkResponse = await fetch(apiUrl('prerolls/check-duplicate'), {
          method: 'POST',
          body: checkFormData
        });
        const checkData = await checkResponse.json();
        duplicateChecks.push({
          file,
          isDuplicate: checkData.is_duplicate,
          existingPreroll: checkData.existing_preroll,
          fileHash: checkData.file_hash
        });
      } catch (error) {
        console.error(`Duplicate check error for ${file.name}:`, error);
        // If check fails, assume not duplicate and continue
        duplicateChecks.push({
          file,
          isDuplicate: false,
          fileHash: null
        });
      }
    }

    // Find duplicates
    const duplicates = duplicateChecks.filter(check => check.isDuplicate);
    
    // If there are duplicates, ask user what to do
    let duplicateAction = 'allow'; // Default: allow duplicates
    if (duplicates.length > 0) {
      const duplicateNames = duplicates.map(d => `  • ${d.file.name}`).join('\n');
      const message = `⚠️ DUPLICATE FILES DETECTED ⚠️\n\nThe following ${duplicates.length} file(s) already exist in your library:\n\n${duplicateNames}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\nClick OK to SKIP these duplicates\nClick Cancel to UPLOAD them anyway`;
      
      const userChoice = window.confirm(message);
      
      if (userChoice) {
        duplicateAction = 'skip';
        alert(`✓ Skipping ${duplicates.length} duplicate file(s). Only new files will be uploaded.`);
      } else {
        alert(`✓ Allowing duplicates. All ${files.length} file(s) will be uploaded.`);
      }
    }

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const checkInfo = duplicateChecks[i];
      
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
        
        // Add duplicate action and hash
        if (checkInfo.isDuplicate && duplicateAction === 'skip') {
          formData.append('duplicate_action', 'skip');
        }
        if (checkInfo.fileHash) {
          formData.append('file_hash', checkInfo.fileHash);
        }

        const response = await fetch(apiUrl('prerolls/upload'), {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.skipped) {
          results.push({ file: file.name, success: true, skipped: true, data });
          setUploadProgress(prev => ({
            ...prev,
            [file.name]: { status: 'skipped', progress: 100 }
          }));
        } else {
          results.push({ file: file.name, success: true, data });
          setUploadProgress(prev => ({
            ...prev,
            [file.name]: { status: 'completed', progress: 100 }
          }));
        }

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
    const successful = results.filter(r => r.success && !r.skipped).length;
    const skippedResults = results.filter(r => r.success && r.skipped);
    const skipped = skippedResults.length;
    const failed = results.filter(r => !r.success).length;

    let message = '';
    if (failed === 0 && skipped === 0) {
      message = `✓ All ${totalFiles} files uploaded successfully!`;
    } else if (successful === 0 && skipped > 0 && failed === 0) {
      const skippedNames = skippedResults.map(r => `  • ${r.file}`).join('\n');
      message = `ℹ️ All ${totalFiles} file(s) were skipped (duplicates):\n\n${skippedNames}`;
    } else if (successful === 0 && failed > 0) {
      message = `❌ Failed to upload any files. Please check the errors.`;
    } else {
      const parts = [];
      if (successful > 0) parts.push(`${successful} uploaded`);
      if (skipped > 0) parts.push(`${skipped} skipped (duplicates)`);
      if (failed > 0) parts.push(`${failed} failed`);
      message = `Upload complete: ${parts.join(', ')}.`;
      
      if (skipped > 0) {
        const skippedNames = skippedResults.map(r => r.file).join(', ');
        message += `\n\nSkipped: ${skippedNames}`;
      }
    }
    alert(message);

    // Clear files and form
    setFiles([]);
    setUploadForm({ tags: '', category_id: '', category_ids: [], description: '' });
    // Clear the file input element
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    fetchData();
  };

  const handleCreateSchedule = async (e) => {
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

    // Validate recurrence patterns
    if (scheduleForm.type === 'daily' && !timeRange.start) {
      alert('Please select at least a start time for daily schedules');
      return;
    }
    if (scheduleForm.type === 'weekly' && weekDays.length === 0) {
      alert('Please select at least one day of the week for weekly schedules');
      return;
    }
    if (scheduleForm.type === 'monthly' && monthDays.length === 0) {
      alert('Please select at least one day of the month for monthly schedules');
      return;
    }

    // Advanced mode: validate sequence and save to library
    if (scheduleMode === 'advanced') {
      // Ensure sequenceBlocks is an array
      const blocks = Array.isArray(sequenceBlocks) ? sequenceBlocks : [];
      console.log('Schedule Mode:', scheduleMode);
      console.log('Sequence Blocks (raw):', sequenceBlocks);
      console.log('Sequence Blocks (validated):', blocks);
      console.log('Blocks length:', blocks.length);
      
      if (blocks.length === 0) {
        alert('Please add at least one block to the sequence before creating the schedule.\n\nUse the "Add Random Block" or "Add Fixed Block" buttons in the Sequence Builder section above to create your sequence.');
        return;
      }
      const validation = validateSequence(blocks, categories, prerolls);
      console.log('Validation result:', validation);
      
      if (!validation.valid) {
        alert('Sequence validation failed:\n' + validation.errors.join('\n'));
        return;
      }

      // Save sequence to library
      try {
        const sequenceName = scheduleForm.name.trim() + ' Sequence';
        const sequenceDescription = `Sequence for schedule "${scheduleForm.name.trim()}"`;
        console.log('Saving sequence to library:', sequenceName);
        await saveSequence(sequenceName, sequenceDescription);
      } catch (error) {
        console.error('Failed to save sequence to library:', error);
        // Continue anyway - sequence will still be saved in the schedule
      }
    } else {
      // Simple mode: validate category
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
    }

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist,
      blend_enabled: scheduleForm.blend_enabled,
      priority: scheduleForm.priority,
      exclusive: scheduleForm.exclusive
    };

    // Only add end_date if it has a value
    if (scheduleForm.end_date && scheduleForm.end_date.trim()) {
      scheduleData.end_date = scheduleForm.end_date;
    }

    // Only add color if it has a value
    if (scheduleForm.color && scheduleForm.color.trim()) {
      scheduleData.color = scheduleForm.color;
    }

    // Add recurrence pattern based on schedule type
    const recurrencePattern = {};
    if (scheduleForm.type === 'daily' && timeRange.start) {
      recurrencePattern.timeRange = timeRange;
    }
    if (scheduleForm.type === 'weekly' && weekDays.length > 0) {
      recurrencePattern.weekDays = weekDays;
    }
    if (scheduleForm.type === 'monthly' && monthDays.length > 0) {
      recurrencePattern.monthDays = monthDays;
    }
    if (Object.keys(recurrencePattern).length > 0) {
      scheduleData.recurrence_pattern = JSON.stringify(recurrencePattern);
    }

    // Add category_id for simple mode, sequence for advanced mode
    if (scheduleMode === 'simple') {
      scheduleData.category_id = parseInt(scheduleForm.category_id);
    } else {
      // Use validated blocks array
      const blocks = Array.isArray(sequenceBlocks) ? sequenceBlocks : [];
      scheduleData.sequence = stringifySequence(blocks);
      // Backend expects category_id, so we'll use first category from sequence or null
      const firstCategory = blocks.find(b => b.type === 'random')?.category_id;
      scheduleData.category_id = firstCategory || null;
    }

    if (scheduleForm.fallback_category_id) {
      scheduleData.fallback_category_id = parseInt(scheduleForm.fallback_category_id);
    }

    fetch(apiUrl('schedules'), {
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
          category_id: '', shuffle: true, playlist: false, fallback_category_id: '', color: '',
          holiday_name: '', holiday_country: '', blend_enabled: false, priority: 5, exclusive: false
        });
        setScheduleMode('simple');
        setSequenceBlocks([]);
        setWeekDays([]);
        setMonthDays([]);
        setTimeRange({ start: '', end: '' });
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
    fetch(apiUrl('holiday-presets/init'), { method: 'POST' })
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            throw new Error(err.detail || 'Failed to initialize holiday presets');
          });
        }
        return res.json();
      })
      .then(data => {
        const msg = data.categories_created > 0 
          ? `Holiday categories created successfully!\n\n✓ ${data.categories_created} new categories\n✓ ${data.presets_created} new presets\n✓ ${data.total_categories} total categories available\n\nThe categories should now appear in your list.`
          : `Holiday categories already exist!\n\n✓ ${data.total_categories} categories available\n\nNo new categories were created.`;
        alert(msg);
        fetchData();
      })
      .catch(error => {
        console.error('Holiday preset initialization error:', error);
        alert('Failed to initialize holiday presets: ' + error.message);
      });
  };

  // Refresh variable-date holiday schedules (Thanksgiving, Easter, etc.)
  const handleRefreshHolidayDates = async () => {
    try {
      const res = await fetch(apiUrl('holiday-api/refresh-dates'), { method: 'POST' });
      const data = await safeJson(res);
      
      if (res.ok) {
        if (data.updated_count > 0) {
          const updates = data.updated_schedules.map(s => 
            `• ${s.name}: ${s.old_date} → ${s.new_date}`
          ).join('\n');
          alert(`✅ Holiday dates refreshed for ${data.year}!\n\n${data.updated_count} schedule(s) updated:\n${updates}`);
        } else {
          alert(`✅ All holiday schedules are up to date for ${data.year}.\n\n${data.total_holiday_schedules} holiday-linked schedule(s) checked.`);
        }
        fetchData();
      } else {
        alert(`❌ Failed to refresh: ${data?.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Refresh holiday dates error:', e);
      alert(`❌ Error: ${e.message}`);
    }
  };

  const handleCategorySortChange = (field) => {
    if (categorySortField === field) {
      // Toggle direction if clicking the same field
      setCategorySortDirection(categorySortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // New field, default to ascending
      setCategorySortField(field);
      setCategorySortDirection('asc');
    }
  };

  const handleApplyCategoryToPlex = (categoryId, categoryName) => {
    const message = `Apply category "${categoryName}" to Plex?\n\nThis will send ALL prerolls from this category to Plex.`;
    if (window.confirm(message)) {
      fetch(apiUrl(`categories/${categoryId}/apply-to-plex`), { method: 'POST' })
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
      fetch(apiUrl(`categories/${categoryId}/remove-from-plex`), { method: 'POST' })
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

  // ========== Category Management Advanced Features ==========
  
  // Calculate category statistics
  const getCategoryStats = (category) => {
    const categoryPrerollsList = prerolls.filter(p => p.category_id === category.id);
    const associatedPrerolls = prerolls.filter(p => 
      p.category_associations && 
      p.category_associations.some(assoc => assoc.category_id === category.id)
    );
    const totalPrerolls = categoryPrerollsList.length + associatedPrerolls.length;
    
    // Calculate total duration
    const totalDuration = [...categoryPrerollsList, ...associatedPrerolls].reduce((sum, p) => {
      return sum + (p.duration || 0);
    }, 0);
    
    // Check if category has active schedules
    const activeSchedules = schedules.filter(s => s.category_id === category.id);
    const hasActiveSchedules = activeSchedules.length > 0;
    
    // Last used (most recent schedule start_date)
    const lastUsed = activeSchedules.length > 0 
      ? new Date(Math.max(...activeSchedules.map(s => new Date(s.start_date))))
      : null;
    
    return {
      totalPrerolls,
      totalDuration,
      activeSchedules: activeSchedules.length,
      hasActiveSchedules,
      lastUsed,
      scheduleNames: activeSchedules.map(s => s.name)
    };
  };

  // Bulk selection handlers
  const toggleSelectCategory = (categoryId) => {
    setSelectedCategoryIds(prev => 
      prev.includes(categoryId) 
        ? prev.filter(id => id !== categoryId)
        : [...prev, categoryId]
    );
  };

  const toggleSelectAll = () => {
    const filteredIds = getFilteredCategories().map(c => c.id);
    if (selectedCategoryIds.length === filteredIds.length) {
      setSelectedCategoryIds([]);
    } else {
      setSelectedCategoryIds(filteredIds);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedCategoryIds.length === 0) {
      alert('No categories selected');
      return;
    }
    
    const confirmMsg = `Delete ${selectedCategoryIds.length} selected categories?\n\nThis will also remove all associated schedules and preroll assignments.`;
    if (!window.confirm(confirmMsg)) return;
    
    try {
      await Promise.all(
        selectedCategoryIds.map(id => 
          fetch(apiUrl(`categories/${id}`), { method: 'DELETE' })
        )
      );
      alert(`Successfully deleted ${selectedCategoryIds.length} categories!`);
      setSelectedCategoryIds([]);
      setBulkActionMode(false);
      fetchData();
    } catch (error) {
      alert('Failed to delete some categories: ' + error.message);
    }
  };

  const handleBulkApplyToPlex = async () => {
    if (selectedCategoryIds.length === 0) {
      alert('No categories selected');
      return;
    }
    
    const server = getActiveConnectedServer();
    if (!server || server === 'conflict') {
      alert('No media server connected or multiple servers connected');
      return;
    }
    
    const confirmMsg = `Apply ${selectedCategoryIds.length} selected categories to ${server === 'plex' ? 'Plex' : 'Jellyfin'}?`;
    if (!window.confirm(confirmMsg)) return;
    
    try {
      const endpoint = server === 'plex' ? 'apply-to-plex' : 'apply-to-jellyfin';
      await Promise.all(
        selectedCategoryIds.map(id => 
          fetch(apiUrl(`categories/${id}/${endpoint}`), { method: 'POST' })
        )
      );
      alert(`Successfully applied ${selectedCategoryIds.length} categories!`);
      setSelectedCategoryIds([]);
      setBulkActionMode(false);
      fetchData();
    } catch (error) {
      alert('Failed to apply some categories: ' + error.message);
    }
  };

  // Get filtered categories based on active filter
  const getFilteredCategories = () => {
    let filtered = categories;
    
    // Apply category filter
    switch (categoryFilter) {
      case 'active':
        filtered = filtered.filter(c => {
          const hasSchedules = schedules.some(s => s.category_id === c.id);
          return hasSchedules;
        });
        break;
      case 'hasPrerolls':
        filtered = filtered.filter(c => {
          const stats = getCategoryStats(c);
          return stats.totalPrerolls > 0;
        });
        break;
      case 'empty':
        filtered = filtered.filter(c => {
          const stats = getCategoryStats(c);
          return stats.totalPrerolls === 0;
        });
        break;
      default: // 'all'
        break;
    }
    
    // Apply search query
    if (categorySearchQuery) {
      const query = categorySearchQuery.toLowerCase();
      filtered = filtered.filter(c => 
        c.name.toLowerCase().includes(query) || 
        (c.description && c.description.toLowerCase().includes(query))
      );
    }
    
    return filtered;
  };

  // Format duration helper
  const formatDuration = (seconds) => {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
      return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
  };

  const toggleScheduler = () => {
    const action = schedulerStatus.running ? 'stop' : 'start';
    fetch(apiUrl(`scheduler/${action}`), { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert(`Scheduler ${action}ed!`);
        fetchData();
      });
  };

  const handleBackupDatabase = () => {
    fetch(apiUrl('backup/database'))
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
    fetch(apiUrl('backup/files'), {
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
        fetch(apiUrl('restore/database'), {
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
    fetch(apiUrl('restore/files'), {
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
    fetch(apiUrl('community-templates/init'), { method: 'POST' })
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
    fetch(apiUrl(`community-templates/${templateId}/import`), { method: 'POST' })
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

    fetch(apiUrl('community-templates'), {
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
    if (!showConfirm('Are you sure you want to delete this schedule?')) return;

    fetch(apiUrl(`schedules/${scheduleId}`), {
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
      color: schedule.color || '',
      blend_enabled: schedule.blend_enabled || false,
      priority: schedule.priority ?? 5,
      exclusive: schedule.exclusive || false
    });

    // Parse recurrence pattern
    if (schedule.recurrence_pattern && typeof schedule.recurrence_pattern === 'string') {
      try {
        const pattern = JSON.parse(schedule.recurrence_pattern);
        if (pattern.timeRange) setTimeRange(pattern.timeRange);
        if (pattern.weekDays) setWeekDays(pattern.weekDays);
        if (pattern.monthDays) setMonthDays(pattern.monthDays);
      } catch (error) {
        console.error('Failed to parse recurrence pattern:', error);
        setTimeRange({ start: '', end: '' });
        setWeekDays([]);
        setMonthDays([]);
      }
    } else {
      setTimeRange({ start: '', end: '' });
      setWeekDays([]);
      setMonthDays([]);
    }

    // Check if schedule has a sequence
    console.log('Editing schedule:', schedule);
    console.log('Schedule sequence:', schedule.sequence);
    console.log('Sequence type:', typeof schedule.sequence);
    
    if (schedule.sequence && typeof schedule.sequence === 'string' && schedule.sequence.trim()) {
      try {
        console.log('Attempting to parse sequence...');
        const parsedSequence = parseSequence(schedule.sequence);
        console.log('Parsed sequence:', parsedSequence);
        if (parsedSequence && parsedSequence.length > 0) {
          console.log('Setting advanced mode with sequence blocks');
          // Add unique IDs to blocks for the UI
          const blocksWithIds = cloneSequenceWithIds(parsedSequence);
          console.log('Blocks with IDs:', blocksWithIds);
          setScheduleMode('advanced');
          setSequenceBlocks(blocksWithIds);
          // Reset dashboard filters when opening Sequence Builder
          setFilterCategory('');
          setFilterTags('');
        } else {
          console.log('No sequence blocks, setting simple mode');
          setScheduleMode('simple');
          setSequenceBlocks([]);
        }
      } catch (error) {
        console.error('Failed to parse sequence:', error);
  setScheduleMode('simple');
  setSequenceBlocks([]);
  // Reset dashboard filters when switching back to simple mode
  setFilterCategory('');
  setFilterTags('');
      }
    } else {
      console.log('No sequence found, setting simple mode');
      setScheduleMode('simple');
      setSequenceBlocks([]);
    }
 };

  const handleUpdateSchedule = (e) => {
    e.preventDefault();
    console.log('Update schedule clicked');
    console.log('Editing schedule:', editingSchedule);
    console.log('Schedule mode:', scheduleMode);
    console.log('Sequence blocks:', sequenceBlocks);
    
    if (!editingSchedule) return;

    // Validate recurrence patterns
    if (scheduleForm.type === 'daily' && !timeRange.start) {
      alert('Please select at least a start time for daily schedules');
      return;
    }
    if (scheduleForm.type === 'weekly' && weekDays.length === 0) {
      alert('Please select at least one day of the week for weekly schedules');
      return;
    }
    if (scheduleForm.type === 'monthly' && monthDays.length === 0) {
      alert('Please select at least one day of the month for monthly schedules');
      return;
    }

    // Validate based on mode
    if (scheduleMode === 'advanced') {
      console.log('In advanced mode, validating sequence...');
      
      // Ensure sequenceBlocks is an array
      const blocks = Array.isArray(sequenceBlocks) ? sequenceBlocks : [];
      console.log('Sequence blocks to validate:', blocks);
      
      if (blocks.length === 0) {
        alert('Please add at least one block to the sequence before creating the schedule.');
        return;
      }
      const validation = validateSequence(blocks, categories, prerolls);
      console.log('Validation result:', validation);
      if (!validation.valid) {
        alert('Sequence validation failed:\n' + validation.errors.join('\n'));
        return;
      }
    }

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist,
      blend_enabled: scheduleForm.blend_enabled,
      priority: scheduleForm.priority,
      exclusive: scheduleForm.exclusive
    };

    // Only add end_date if it has a value
    if (scheduleForm.end_date && scheduleForm.end_date.trim()) {
      scheduleData.end_date = scheduleForm.end_date;
    }

    // Only add color if it has a value
    if (scheduleForm.color && scheduleForm.color.trim()) {
      scheduleData.color = scheduleForm.color;
    }

    // Add recurrence pattern based on schedule type
    const recurrencePattern = {};
    if (scheduleForm.type === 'daily' && timeRange.start) {
      recurrencePattern.timeRange = timeRange;
    }
    if (scheduleForm.type === 'weekly' && weekDays.length > 0) {
      recurrencePattern.weekDays = weekDays;
    }
    if (scheduleForm.type === 'monthly' && monthDays.length > 0) {
      recurrencePattern.monthDays = monthDays;
    }
    if (Object.keys(recurrencePattern).length > 0) {
      scheduleData.recurrence_pattern = JSON.stringify(recurrencePattern);
    } else {
      scheduleData.recurrence_pattern = null; // Clear if not applicable
    }

    // Add category_id for simple mode, sequence for advanced mode
    if (scheduleMode === 'simple') {
      scheduleData.category_id = parseInt(scheduleForm.category_id);
      scheduleData.sequence = ''; // Clear sequence if switching to simple
      scheduleData.preroll_ids = '';
    } else {
      // Use validated blocks array
      const blocks = Array.isArray(sequenceBlocks) ? sequenceBlocks : [];
      scheduleData.sequence = stringifySequence(blocks);
      console.log('Stringified sequence:', scheduleData.sequence);
      // Backend expects category_id, so we'll use first category from sequence or keep existing
      const firstCategory = blocks.find(b => b.type === 'random')?.category_id;
      scheduleData.category_id = firstCategory || parseInt(scheduleForm.category_id) || editingSchedule.category_id || 1;
      scheduleData.preroll_ids = '';
    }

    if (scheduleForm.fallback_category_id) {
      scheduleData.fallback_category_id = parseInt(scheduleForm.fallback_category_id);
    }

    console.log('Sending schedule data:', scheduleData);
    console.log('Making fetch request to:', apiUrl(`schedules/${editingSchedule.id}`));

    fetch(apiUrl(`schedules/${editingSchedule.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(async response => {
        console.log('Received response!');
        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);
        
        if (!response.ok) {
          const errorText = await response.text();
          console.log('Error response:', errorText);
          try {
            const errorData = JSON.parse(errorText);
            console.log('Error detail:', errorData.detail);
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
          } catch(e) {
            if (e.message && !e.message.startsWith('HTTP error')) {
              throw e;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
          }
        }
        
        // Response is OK, parse the JSON
        return response.json();
      })
      .then(data => {
        console.log('Update successful, response data:', data);
        alert('Schedule updated successfully!');
        setEditingSchedule(null);
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: true, playlist: false, fallback_category_id: '', color: '',
          blend_enabled: false, priority: 5, exclusive: false
        });
        setScheduleMode('simple');
        setSequenceBlocks([]);
        setWeekDays([]);
        setMonthDays([]);
        setTimeRange({ start: '', end: '' });
        fetchData();
      })
      .catch(error => {
        console.error('Update schedule error:', error);
        alert('Failed to update schedule: ' + error.message);
      });
  };

  const handleDeletePreroll = (prerollId) => {
    if (!showConfirm('Are you sure you want to delete this preroll?')) return;

    fetch(apiUrl(`prerolls/${prerollId}`), {
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
      description: preroll.description || '',
      exclude_from_matching: preroll.exclude_from_matching || false
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
    payload.exclude_from_matching = editForm.exclude_from_matching;

    console.log('[RENAME] Submitting preroll update with payload:', payload);
    if (payload.new_filename) {
      console.log('[RENAME] New filename requested:', payload.new_filename);
    }

    fetch(apiUrl(`prerolls/${editingPreroll.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(handleFetchResponse)
      .then((result) => {
        console.log('[RENAME] Preroll update response:', result);
        if (payload.new_filename) {
          console.log('[RENAME] File rename completed successfully');
        }
        
        // Show warning if present (e.g., for external file renames)
        if (result.warning) {
          alert('⚠️ ' + result.warning + '\n\nPreroll updated successfully.');
        } else {
          alert('Preroll updated successfully!');
        }
        
        setEditingPreroll(null);
        setEditForm({ display_name: '', new_filename: '', tags: '', category_id: '', category_ids: [], description: '', exclude_from_matching: false });
        fetchData();
      })
      .catch(error => {
        console.error('[RENAME] Update preroll error:', error);
        alert('Failed to update preroll: ' + error.message);
      });
  };

  const handleAutoMatchPreroll = async () => {
    if (!editingPreroll || autoMatchLoading) return;
    
    const confirmed = window.confirm(
      `Attempt to automatically match "${editingPreroll.display_name || editingPreroll.filename}" to the Community Prerolls library?\n\n` +
      'This will search for a matching title using fuzzy matching.\n\n' +
      'Continue?'
    );
    
    if (!confirmed) return;
    
    setAutoMatchLoading(true);
    setSimilarMatches([]);
    
    try {
      const response = await fetch(apiUrl(`prerolls/${editingPreroll.id}/auto-match`), {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.excluded) {
        alert(`⊘ This preroll is excluded from community matching\n\n${data.message || 'This preroll has been marked to be excluded from automatic matching.'}`);
        return;
      }
      
      if (data.matched) {
        if (data.already_matched) {
          alert(`✓ This preroll is already matched to the Community Prerolls library!\n\nCommunity ID: ${data.community_preroll_id}`);
        } else {
          const matchInfo = data.match_type === 'exact' 
            ? '(exact match)' 
            : `(fuzzy match - ${data.match_score * 100}% confidence)`;
          
          alert(`✓ Successfully matched!\n\nMatched to: ${data.matched_title}\n${matchInfo}\n\nThe preroll will now show the community match indicator.`);
          
          // Update the editing preroll state to reflect the new match
          setEditingPreroll({
            ...editingPreroll,
            community_preroll_id: data.community_preroll_id
          });
          
          // Refresh the preroll list
          await fetchData();
        }
      } else {
        // No confident match - show similar matches if available
        console.log('Auto-match response data:', data);
        console.log('Similar matches:', data.similar_matches);
        console.log('Similar matches length:', data.similar_matches?.length);
        
        if (data.similar_matches && data.similar_matches.length > 0) {
          console.log('Setting similar matches:', data.similar_matches);
          setSimilarMatches(data.similar_matches);
        } else {
          console.log('No similar matches found');
          alert(
            `✗ No match found\n\n` +
            `Could not find any matching prerolls in the Community Prerolls library.\n\n` +
            `Suggestions:\n` +
            `• Try adjusting the filename to match the community title\n` +
            `• Check if the preroll exists in the Community Prerolls library`
          );
        }
      }
    } catch (error) {
      console.error('Auto-match error:', error);
      alert(`Failed to auto-match preroll: ${error.message}`);
    } finally {
      setAutoMatchLoading(false);
    }
  };

  const handleSelectSimilarMatch = async (communityId, title) => {
    if (!editingPreroll) return;
    
    const confirmed = window.confirm(
      `Link this preroll to:\n\n"${title}"\n\nFrom the Community Prerolls library?`
    );
    
    if (!confirmed) return;
    
    try {
      const response = await fetch(apiUrl(`prerolls/${editingPreroll.id}/link-community/${communityId}`), {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        alert(`✓ Successfully linked to: ${title}\n\nThe preroll will now show the community match indicator.`);
        
        // Update the editing preroll state
        setEditingPreroll({
          ...editingPreroll,
          community_preroll_id: communityId
        });
        
        // Clear similar matches
        setSimilarMatches([]);
        
        // Refresh the preroll list
        await fetchData();
      }
    } catch (error) {
      console.error('Link error:', error);
      alert(`Failed to link preroll: ${error.message}`);
    }
  };

  const handleDeleteCategory = (categoryId) => {
    if (!showConfirm('Are you sure you want to delete this category? This may affect associated schedules and prerolls.')) return;

    fetch(apiUrl(`categories/${categoryId}`), {
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
    setNewCategory({ name: category.name, description: category.description || '' });
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
      const res = await fetch(apiUrl(`categories/${editingCategory.id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
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
      const res = await fetch(apiUrl(`categories/${editingCategory.id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
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
        const resApply = await fetch(apiUrl(`categories/${idToApply}/apply-to-plex`), { method: 'POST' });
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
      const res = await fetch(apiUrl(`categories/${categoryId}/prerolls`));
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
      showAlert('Cannot remove the primary category here. Use "Edit Preroll" to change the primary category.', 'error');
      return;
    }
    if (!showConfirm(`Remove "${preroll.display_name || preroll.filename}" from this category?`)) return;
    try {
      const res = await fetch(apiUrl(`categories/${categoryId}/prerolls/${preroll.id}`), { method: 'DELETE' });
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
      const res = await fetch(apiUrl(`categories/${categoryId}/prerolls/${prerollId}?set_primary=${sel.setPrimary ? 'true' : 'false'}`), { method: 'POST' });
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

  // Apply client-side filters in order: category/tags first, then match status
  const filteredPrerolls = React.useMemo(() => {
    let filtered = prerolls;
    
    // 1. Filter by category
    if (filterCategory) {
      const catId = parseInt(filterCategory);
      filtered = filtered.filter(p => {
        if (p.category_id === catId) return true;
        if (p.categories && p.categories.some(c => c.id === catId)) return true;
        return false;
      });
    }
    
    // 2. Filter by tags
    if (filterTags && filterTags.trim()) {
      const searchTerms = filterTags.split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
      filtered = filtered.filter(p => {
        const prerollTags = (p.tags || '').toLowerCase();
        const filename = (p.filename || '').toLowerCase();
        const displayName = (p.display_name || '').toLowerCase();
        return searchTerms.some(term => 
          prerollTags.includes(term) || filename.includes(term) || displayName.includes(term)
        );
      });
    }
    
    // 3. Filter by match status
    if (filterMatchStatus === 'matched') {
      filtered = filtered.filter(p => p.community_preroll_id);
    } else if (filterMatchStatus === 'unmatched') {
      filtered = filtered.filter(p => !p.community_preroll_id);
    }
    
    return filtered;
  }, [prerolls, filterCategory, filterTags, filterMatchStatus]);

  const totalPrerolls = filteredPrerolls.length;
  const totalPages = Math.max(1, Math.ceil(totalPrerolls / pageSize));
  const currentPageClamped = Math.min(currentPage, totalPages);
  const pageStartIndex = (currentPageClamped - 1) * pageSize;
  const pageEndIndex = Math.min(pageStartIndex + pageSize, totalPrerolls);
  const visiblePrerolls = filteredPrerolls.slice(pageStartIndex, pageEndIndex);
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
    if (!cid || isNaN(cid)) { showAlert('Select a target category', 'error'); return; }
    if (selectedPrerollIds.length === 0) { showAlert('No prerolls selected', 'error'); return; }
    if (!showConfirm(`Change primary category for ${selectedPrerollIds.length} preroll(s)? This will move files on disk.`)) return;
    let ok = 0, fail = 0;
    for (const id of selectedPrerollIds) {
      try {
        const res = await fetch(apiUrl(`prerolls/${id}`), {
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
    if (count === 0) { showAlert('No prerolls selected', 'error'); return; }
    if (!showConfirm(`Delete ${count} selected preroll(s)?\n\nManaged files may be deleted from disk. External mapped files are protected and will not be removed.`)) return;
    let ok = 0, fail = 0;
    for (const id of selectedPrerollIds) {
      try {
        const res = await fetch(apiUrl(`prerolls/${id}`), { method: 'DELETE' });
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
      const res = await fetch(apiUrl('categories'), {
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
const DASH_KEYS = ["servers","prerolls","storage","schedules","scheduler","current_category","upcoming","community"];

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
        // Get all schedules that haven't ended yet (excluding past schedules and disabled schedules)
        const upcomingSchedules = schedules
          .filter(s => {
            // Must be active/enabled
            if (!s.is_active) return false;
            
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
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            {upcomingSchedules.map(schedule => {
              const category = categories.find(c => c.id === schedule.category_id);
              const displayTime = schedule.next_run || schedule.start_date;
              return (
                <div key={schedule.id} style={{ fontSize: '0.8rem', padding: '0.35rem 0.5rem', backgroundColor: 'var(--card-bg)', borderRadius: '4px' }}>
                  <div style={{ fontWeight: 'bold', color: '#007bff', fontSize: '0.85rem' }}>
                    {schedule.name}
                  </div>
                  <div style={{ color: 'var(--text-secondary, #666)', fontSize: '0.75rem', marginTop: '0.1rem' }}>
                    {toLocalDisplay(displayTime)} → {category?.name || 'Unknown'}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #666)', margin: 0 }}>No upcoming schedules</p>
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
  community: () => {
    const indexedCount = communityIndexStatus?.total_prerolls || 0;
    const matchedCount = communityMatchedCount || 0;
    
    return (
      <div className="card">
        <h2>Community Prerolls</h2>
        {indexedCount > 0 || matchedCount > 0 ? (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {indexedCount > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <BookOpen size={14} /> Indexed:
                </span>
                <span style={{ fontWeight: 'bold', color: '#22c55e' }}>{indexedCount}</span>
              </div>
            )}
            {matchedCount > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Link size={14} /> Matched:
                </span>
                <span style={{ fontWeight: 'bold', color: '#3b82f6' }}>{matchedCount}</span>
              </div>
            )}
          </div>
        ) : (
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #666)' }}>
            No community files indexed yet
          </p>
        )}
      </div>
    );
  },
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
              {darkMode ? <><Sun size={14} style={{marginRight: '0.35rem'}} /> Light</> : <><Moon size={14} style={{marginRight: '0.35rem'}} /> Dark</>}
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
            <Upload size={16} style={{marginRight: '6px'}} /> Upload Files
          </button>
          <button
            type="button"
            className={`button ${uploadMode === 'import' ? '' : 'button-secondary'}`}
            onClick={() => setUploadMode('import')}
            style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
          >
            <Folder size={16} /> Import Folder
          </button>
        </div>

        {uploadMode === 'upload' && (
          <form onSubmit={handleUpload}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files))}
                accept="video/*"
                required
                className="nx-input"
                style={{ width: '100%' }}
              />
              {files.length > 0 && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--text-color)' }}>
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
            <p style={{ marginBottom: '0.75rem', color: 'var(--text-color)', fontSize: '0.9rem' }}>
              Index files from an existing folder into NeXroll without moving them on disk. These files are marked as external (managed=false).
            </p>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {/* Path input with Browse button */}
              <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
                <div style={{ width: '50%' }}>
                  <input
                    type="text"
                    placeholder="Root path (e.g., C:\\Prerolls or \\\\NAS\\share\\prerolls)"
                    value={mapRootForm.root_path}
                    onChange={(e) => setMapRootForm({ ...mapRootForm, root_path: e.target.value })}
                    disabled={mapRootLoading}
                    className="nx-input"
                    style={{ padding: '0.5rem', width: '97%' }}
                  />
                </div>
                {/* Recent paths dropdown - separate element */}
                {recentImportPaths.length > 0 && !mapRootLoading && (
                  <select
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        setMapRootForm({ ...mapRootForm, root_path: e.target.value });
                      }
                    }}
                    className="nx-select"
                    style={{ 
                      padding: '0.5rem',
                      width: '360px',
                      cursor: 'pointer',
                      flexShrink: 0
                    }}
                    title="Recent paths"
                  >
                    <option value="">Recent</option>
                    {recentImportPaths.map((p, i) => (
                      <option key={i} value={p}>{p.length > 20 ? '...' + p.slice(-20) : p}</option>
                    ))}
                  </select>
                )}
                <button 
                  type="button" 
                  className="button button-secondary"
                  onClick={openFolderBrowser}
                  disabled={mapRootLoading}
                  title="Browse folders"
                  style={{ padding: '0.5rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                >
                  <FolderOpen size={16} /> Browse
                </button>
              </div>

              {/* Category selector */}
              <select
                value={mapRootForm.category_id}
                onChange={(e) => {
                  setMapRootForm({ ...mapRootForm, category_id: e.target.value });
                  setMapRootCategoryError(false); // Clear error when user selects
                  if (mapRootResult?.type === 'error') setMapRootResult(null); // Clear error message
                }}
                className="nx-select"
                disabled={mapRootLoading}
                style={{ 
                  padding: '0.5rem', 
                  width: '50%',
                  borderColor: mapRootCategoryError ? '#dc3545' : undefined,
                  boxShadow: mapRootCategoryError ? '0 0 0 2px rgba(220, 53, 69, 0.25)' : undefined
                }}
              >
                <option value="">Select Category</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              {mapRootCategoryError && (
                <div style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '-0.5rem' }}>
                  ↑ Please select a category first
                </div>
              )}

              {/* Options row */}
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!!mapRootForm.recursive}
                    onChange={(e) => setMapRootForm({ ...mapRootForm, recursive: e.target.checked })}
                    disabled={mapRootLoading}
                  />
                  <span>Recurse subfolders</span>
                </label>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!!mapRootForm.generate_thumbnails}
                    onChange={(e) => setMapRootForm({ ...mapRootForm, generate_thumbnails: e.target.checked })}
                    disabled={mapRootLoading}
                  />
                  <span>Generate thumbnails</span>
                </label>
              </div>

              {/* Extensions and Tags in a row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <input
                  type="text"
                  placeholder="Extensions: mp4,mkv,avi,mov"
                  value={mapRootForm.extensions}
                  onChange={(e) => setMapRootForm({ ...mapRootForm, extensions: e.target.value })}
                  disabled={mapRootLoading}
                  className="nx-input"
                  style={{ padding: '0.5rem' }}
                />
                <input
                  type="text"
                  placeholder="Tags (optional, comma-separated)"
                  value={mapRootForm.tags}
                  onChange={(e) => setMapRootForm({ ...mapRootForm, tags: e.target.value })}
                  disabled={mapRootLoading}
                  className="nx-input"
                  style={{ padding: '0.5rem', width : '60%' }}
                />
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button 
                  type="button" 
                  className="button button-secondary" 
                  onClick={() => submitMapRoot(false)} 
                  disabled={mapRootLoading || !mapRootForm.root_path}
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}
                >
                  <FlaskConical size={14} /> Dry Run (Preview)
                </button>
                <button 
                  type="button" 
                  className="button" 
                  onClick={() => submitMapRoot(true)} 
                  disabled={mapRootLoading || !mapRootForm.root_path} 
                  style={{ flex: 1, backgroundColor: '#28a745', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}
                >
                  <Download size={14} /> Import Now
                </button>
              </div>

              {/* Enhanced Progress indicator */}
              {mapRootLoading && (
                <div className="nx-import-progress" style={{ 
                  marginTop: '0.5rem', 
                  padding: '1rem', 
                  background: 'var(--card-bg)', 
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <Loader2 size={20} className="spin" style={{ color: 'var(--button-bg)' }} />
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-color)' }}>
                        {mapRootLoadingMsg || 'Working…'}
                      </div>
                      {mapRootProgress.phase && (
                        <div style={{ fontSize: '0.85rem', color: '#888', marginTop: '0.25rem' }}>
                          {mapRootProgress.phase}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="nx-progress" style={{ height: '8px' }}>
                    <div className="bar"></div>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '0.5rem', textAlign: 'center' }}>
                    Please wait while files are being scanned and indexed...
                  </div>
                </div>
              )}

              {/* Inline Results Display */}
              {mapRootResult && !mapRootLoading && (
                <div style={{ 
                  marginTop: '0.5rem', 
                  padding: '1rem', 
                  background: mapRootResult.type === 'error' ? 'rgba(220, 53, 69, 0.1)' : 
                              mapRootResult.type === 'dryrun' ? 'var(--card-bg)' : 'rgba(40, 167, 69, 0.1)', 
                  borderRadius: '8px',
                  border: `1px solid ${mapRootResult.type === 'error' ? '#dc3545' : 
                                       mapRootResult.type === 'dryrun' ? 'var(--border-color)' : '#28a745'}`
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: mapRootResult.type === 'error' ? '0' : '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      {mapRootResult.type === 'error' ? (
                        <AlertTriangle size={18} style={{ color: '#dc3545' }} />
                      ) : mapRootResult.type === 'dryrun' ? (
                        <FlaskConical size={18} style={{ color: 'var(--button-bg)' }} />
                      ) : (
                        <CheckCircle size={18} style={{ color: '#28a745' }} />
                      )}
                      <span style={{ fontWeight: 600, color: mapRootResult.type === 'error' ? '#dc3545' : 'var(--text-color)' }}>
                        {mapRootResult.type === 'error' ? mapRootResult.message :
                         mapRootResult.type === 'dryrun' ? 'Dry Run Results' : 'Import Complete'}
                      </span>
                    </div>
                    <button 
                      onClick={() => setMapRootResult(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888', padding: '0.25rem' }}
                      title="Dismiss"
                    >
                      <X size={16} />
                    </button>
                  </div>
                  {mapRootResult.type !== 'error' && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', textAlign: 'center' }}>
                    <div style={{ padding: '0.5rem', background: 'var(--bg-color)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--button-bg)' }}>
                        {mapRootResult.found}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#888' }}>Files Found</div>
                    </div>
                    <div style={{ padding: '0.5rem', background: 'var(--bg-color)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#888' }}>
                        {mapRootResult.present}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#888' }}>Already Present</div>
                    </div>
                    <div style={{ padding: '0.5rem', background: 'var(--bg-color)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#28a745' }}>
                        {mapRootResult.type === 'dryrun' ? mapRootResult.toAdd : mapRootResult.added}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#888' }}>
                        {mapRootResult.type === 'dryrun' ? 'Would Add' : 'Added'}
                      </div>
                    </div>
                  </div>
                  )}
                  {mapRootResult.type === 'dryrun' && mapRootResult.toAdd > 0 && (
                    <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
                      <button 
                        className="button"
                        onClick={() => { setMapRootResult(null); submitMapRoot(true); }}
                        style={{ backgroundColor: '#28a745' }}
                      >
                        <Download size={14} style={{ marginRight: '0.35rem' }} />
                        Import {mapRootResult.toAdd} File{mapRootResult.toAdd !== 1 ? 's' : ''} Now
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Folder Browser Modal */}
            {showFolderBrowser && (
              <div className="nx-modal-overlay" onClick={() => setShowFolderBrowser(false)}>
                <div 
                  className="nx-modal" 
                  onClick={(e) => e.stopPropagation()}
                  style={{ maxWidth: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
                >
                  <div className="nx-modal-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                    <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <FolderOpen size={20} /> Browse Folders
                    </h3>
                    <button 
                      onClick={() => setShowFolderBrowser(false)} 
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-color)' }}
                    >
                      <X size={20} />
                    </button>
                  </div>
                  
                  {/* Current path breadcrumb */}
                  <div style={{ padding: '0.75rem 1rem', background: 'var(--header-bg)', borderBottom: '1px solid var(--border-color)', fontSize: '0.9rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontWeight: 500 }}>Path:</span>
                      <code style={{ 
                        background: 'var(--bg-color)', 
                        padding: '0.25rem 0.5rem', 
                        borderRadius: '4px',
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {folderBrowserPath || '(Select a drive or root)'}
                      </code>
                    </div>
                    {folderBrowserVideoCount > 0 && (
                      <div style={{ marginTop: '0.5rem', color: '#28a745', fontSize: '0.85rem' }}>
                        <Film size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} />
                        {folderBrowserVideoCount} video file{folderBrowserVideoCount !== 1 ? 's' : ''} in this folder
                      </div>
                    )}
                  </div>

                  {/* Folder list */}
                  <div style={{ flex: 1, overflow: 'auto', padding: '0.5rem' }}>
                    {folderBrowserLoading ? (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', gap: '0.5rem' }}>
                        <Loader2 size={20} className="spin" />
                        <span>Loading folders...</span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        {/* Go up button */}
                        {folderBrowserParent !== null && (
                          <button
                            onClick={() => browseFolders(folderBrowserParent)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              padding: '0.5rem 0.75rem',
                              background: 'var(--header-bg)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              color: 'var(--text-color)',
                              textAlign: 'left'
                            }}
                          >
                            <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
                            <span>..</span>
                            <span style={{ color: '#888', fontSize: '0.85rem' }}>(Go up)</span>
                          </button>
                        )}
                        
                        {/* Folder items */}
                        {folderBrowserItems.map((item, i) => (
                          <button
                            key={i}
                            onClick={() => browseFolders(item.path)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              padding: '0.5rem 0.75rem',
                              background: 'var(--card-bg)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              color: 'var(--text-color)',
                              textAlign: 'left',
                              transition: 'background 0.15s'
                            }}
                            onMouseEnter={(e) => e.target.style.background = 'var(--header-bg)'}
                            onMouseLeave={(e) => e.target.style.background = 'var(--card-bg)'}
                          >
                            {item.type === 'drive' ? (
                              <span style={{ fontSize: '1.1rem' }}>💾</span>
                            ) : (
                              <Folder size={16} style={{ color: '#f0c000' }} />
                            )}
                            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {item.name}
                            </span>
                            <ChevronRight size={14} style={{ color: '#888' }} />
                          </button>
                        ))}
                        
                        {folderBrowserItems.length === 0 && !folderBrowserLoading && (
                          <div style={{ padding: '1rem', textAlign: 'center', color: '#888' }}>
                            No subfolders found
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Footer with Select button */}
                  <div style={{ 
                    padding: '1rem', 
                    borderTop: '1px solid var(--border-color)', 
                    display: 'flex', 
                    gap: '0.5rem',
                    justifyContent: 'flex-end'
                  }}>
                    <button 
                      className="button button-secondary"
                      onClick={() => setShowFolderBrowser(false)}
                    >
                      Cancel
                    </button>
                    <button 
                      className="button"
                      onClick={() => selectFolderFromBrowser(folderBrowserPath)}
                      disabled={!folderBrowserPath}
                      style={{ backgroundColor: '#28a745' }}
                    >
                      <Check size={14} style={{ marginRight: '0.35rem' }} />
                      Select This Folder
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Help section - collapsible */}
            <details style={{ marginTop: '0.75rem' }}>
              <summary style={{ 
                cursor: 'pointer', 
                padding: '0.5rem 0.75rem', 
                background: 'var(--header-bg)', 
                borderRadius: '6px',
                color: 'var(--text-color)',
                fontSize: '0.9rem',
                fontWeight: 500
              }}>
                💡 Docker/NAS Help & Tips
              </summary>
              <div style={{ padding: '0.75rem', border: '1px dashed var(--border-color)', borderTop: 'none', borderRadius: '0 0 6px 6px', background: 'var(--card-bg)' }}>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
                  <li>If NeXroll runs in Docker, the container cannot see Windows mapped drives or UNC paths by default. Mount your NAS/host folder into the container and use the container path in "Root path".</li>
                  <li style={{ marginTop: '0.5rem' }}>UNC paths like \\NAS\share aren't usable inside Linux containers. Mount the SMB share on the host (e.g., /mnt/nas) and map it into the container.</li>
                  <li style={{ marginTop: '0.5rem' }}>Example docker run: <code>docker run -d -p 9393:9393 -v /mnt/nas/prerolls:/nas/prerolls jbrns/nexroll:latest</code></li>
                </ul>
              </div>
            </details>
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
              <RefreshCw size={14} style={{marginRight: '0.35rem'}} /> Reinitialize Thumbnails
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
              <select
                value={filterMatchStatus}
                onChange={(e) => setFilterMatchStatus(e.target.value)}
                className="filter-select"
                title="Filter by community match status"
              >
                <option value="">All Prerolls</option>
                <option value="matched">✅ Matched Only</option>
                <option value="unmatched">⚠️ Unmatched Only</option>
              </select>
              <div className="search-input-wrapper">
                <input
                  type="text"
                  placeholder="Search prerolls (tags, filenames, titles)..."
                  value={inputTagsValue}
                  onChange={(e) => handleTagsChange(e.target.value)}
                  className="search-input"
                />
                <span className="search-icon"><Search size={18} /></span>
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
              <Trash size={16} style={{ marginRight: '6px' }} /> Delete {selectedPrerollIds.length > 0 && `(${selectedPrerollIds.length})`}
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
                  <p className="preroll-title" style={{ fontWeight: 'bold', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>{preroll.display_name || preroll.filename}</span>
                  </p>
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
                    <Play size={16} />
                  </button>
                  <button
                    onClick={() => handleEditPreroll(preroll)}
                    className="nx-iconbtn"
                    title="Edit preroll"
                  >
                    <Edit size={16} />
                  </button>
                  <button
                    onClick={() => handleDeletePreroll(preroll.id)}
                    className="nx-iconbtn nx-iconbtn--danger"
                    title="Delete preroll"
                  >
                    <Trash size={16} />
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
              {preroll.community_preroll_id && (
                <p style={{ 
                  fontSize: '0.75rem', 
                  color: 'var(--text-color)',
                  display: 'inline-block',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px',
                  fontWeight: '500',
                  marginBottom: '0.5rem'
                }}>
                  ✅ Matched to Community
                </p>
              )}
              {preroll.exclude_from_matching && (
                <p style={{ 
                  fontSize: '0.75rem', 
                  color: 'var(--text-color)',
                  display: 'inline-block',
                  backgroundColor: 'rgba(20, 184, 166, 0.15)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px',
                  fontWeight: '500',
                  marginBottom: '0.5rem',
                  marginLeft: '0.5rem'
                }}>
                  🚫 Excluded from Matching
                </p>
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
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginTop: '0.5rem' }}>
                  {(() => {
                    let tagList = [];
                    try {
                      // Handle JSON array strings like '["Halloween", "ghost"]'
                      if (typeof preroll.tags === 'string' && preroll.tags.trim().startsWith('[')) {
                        tagList = JSON.parse(preroll.tags);
                      } else if (Array.isArray(preroll.tags)) {
                        tagList = preroll.tags;
                      } else {
                        tagList = preroll.tags.split(',');
                      }
                    } catch (e) {
                      // Fallback to comma split if JSON parse fails
                      tagList = typeof preroll.tags === 'string' ? preroll.tags.split(',') : [];
                    }
                    
                    return tagList.filter(t => t && String(t).trim()).map((tag, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.7rem',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '12px',
                          backgroundColor: 'rgba(99, 102, 241, 0.15)',
                          color: 'var(--text-color)',
                          border: '1px solid rgba(99, 102, 241, 0.3)',
                          fontWeight: '500',
                          display: 'inline-flex',
                          alignItems: 'center'
                        }}
                      >
                        {String(tag).trim()}
                      </span>
                    ));
                  })()}
                </div>
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
             <div className="preroll-row-title" style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
               <span>{preroll.display_name || preroll.filename}</span>
             </div>
             {preroll.community_preroll_id && (
               <div style={{ 
                 fontSize: '0.75rem', 
                 color: 'var(--text-color)',
                 display: 'inline-block',
                 backgroundColor: 'rgba(16, 185, 129, 0.15)',
                 padding: '0.2rem 0.5rem',
                 borderRadius: '4px',
                 fontWeight: '500',
                 marginBottom: '0.5rem'
               }}>
                 ✅ Matched to Community
               </div>
             )}
             {preroll.exclude_from_matching && (
               <div style={{ 
                 fontSize: '0.75rem', 
                 color: 'var(--text-color)',
                 display: 'inline-block',
                 backgroundColor: 'rgba(20, 184, 166, 0.15)',
                 padding: '0.2rem 0.5rem',
                 borderRadius: '4px',
                 fontWeight: '500',
                 marginBottom: '0.5rem',
                 marginLeft: '0.5rem'
               }}>
                 🚫 Excluded from Matching
               </div>
             )}
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
               <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginTop: '0.5rem' }}>
                 {(() => {
                   let tagList = [];
                   try {
                     // Handle JSON array strings like '["Halloween", "ghost"]'
                     if (typeof preroll.tags === 'string' && preroll.tags.trim().startsWith('[')) {
                       tagList = JSON.parse(preroll.tags);
                     } else if (Array.isArray(preroll.tags)) {
                       tagList = preroll.tags;
                     } else {
                       tagList = preroll.tags.split(',');
                     }
                   } catch (e) {
                     // Fallback to comma split if JSON parse fails
                     tagList = typeof preroll.tags === 'string' ? preroll.tags.split(',') : [];
                   }
                   
                   return tagList.filter(t => t && String(t).trim()).map((tag, idx) => (
                     <span
                       key={idx}
                       style={{
                         fontSize: '0.7rem',
                         padding: '0.2rem 0.5rem',
                         borderRadius: '12px',
                         backgroundColor: 'rgba(99, 102, 241, 0.15)',
                         color: 'var(--text-color)',
                         border: '1px solid rgba(99, 102, 241, 0.3)',
                         fontWeight: '500',
                         display: 'inline-flex',
                         alignItems: 'center'
                       }}
                     >
                       {String(tag).trim()}
                     </span>
                   ));
                 })()}
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
               <Play size={16} />
             </button>
             <button
               onClick={() => handleEditPreroll(preroll)}
               className="nx-iconbtn"
               title="Edit preroll"
             >
               <Edit size={16} />
             </button>
             <button
               onClick={() => handleDeletePreroll(preroll.id)}
               className="nx-iconbtn nx-iconbtn--danger"
               title="Delete preroll"
             >
               <Trash size={16} />
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

  // Persistent sub-navigation for all schedule pages
  const renderScheduleSubNav = () => {
    const tabs = [
      { 
        id: 'schedules', 
        icon: <Calendar size={16} />, 
        label: 'My Schedules', 
        description: 'View and manage all your schedules'
      },
      { 
        id: 'schedules/create', 
        icon: <Plus size={16} />, 
        label: 'Create New', 
        description: 'Schedule a category or custom sequence'
      },
      { 
        id: 'schedules/calendar', 
        icon: <CalendarDays size={16} />, 
        label: 'Calendar View', 
        description: 'Visual calendar of active schedules'
      },
      { 
        id: 'schedules/builder', 
        icon: <Film size={16} />, 
        label: 'Sequence Builder', 
        description: 'Create custom preroll sequences'
      },
      { 
        id: 'schedules/library', 
        icon: <BookOpen size={16} />, 
        label: 'Saved Sequences', 
        description: 'Your sequence library'
      }
    ];

    return (
      <>
        {/* Main Tab Bar */}
        <div style={{ 
          borderBottom: '2px solid var(--border-color)',
          display: 'flex',
          gap: '0.25rem',
          marginBottom: '0.75rem'
        }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '0.875rem 1.25rem',
                border: 'none',
                borderBottom: activeTab === tab.id ? '3px solid var(--button-bg)' : '3px solid transparent',
                backgroundColor: activeTab === tab.id ? 'var(--bg-color)' : 'transparent',
                color: activeTab === tab.id ? 'var(--button-bg)' : 'var(--text-color)',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: activeTab === tab.id ? 600 : 400,
                transition: 'all 0.2s',
                marginBottom: '-2px',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                borderRadius: '8px 8px 0 0'
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.backgroundColor = 'var(--bg-color)';
                  e.currentTarget.style.color = 'var(--button-bg)';
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'var(--text-color)';
                }
              }}
              title={tab.description}
            >
              <span style={{ display: 'flex', alignItems: 'center' }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Context Bar - Shows description of current tab */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.75rem 1rem',
          backgroundColor: 'var(--bg-color)',
          borderRadius: '8px',
          border: '1px solid var(--border-color)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>
              {tabs.find(t => t.id === activeTab)?.icon || <Calendar size={20} />}
            </span>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                {tabs.find(t => t.id === activeTab)?.label || 'My Schedules'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                {tabs.find(t => t.id === activeTab)?.description || ''}
              </div>
            </div>
          </div>

          {/* Quick Action Buttons based on active tab */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {activeTab === 'schedules' && (
              <button
                onClick={() => setActiveTab('schedules/create')}
                className="button"
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  backgroundColor: '#28a745',
                  borderColor: '#28a745',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <span>+</span> New Schedule
              </button>
            )}
            {activeTab === 'schedules/library' && (
              <button
                onClick={() => setActiveTab('schedules/builder')}
                className="button"
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  backgroundColor: '#28a745',
                  borderColor: '#28a745',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <span>+</span> New Sequence
              </button>
            )}
            {(activeTab === 'schedules/builder' || activeTab === 'schedules/create') && (
              <button
                onClick={() => setActiveTab('schedules')}
                className="button"
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  backgroundColor: '#6c757d',
                  borderColor: '#6c757d'
                }}
              >
                ← Back to Schedules
              </button>
            )}
          </div>
        </div>
      </>
    );
  };

  // Calendar page - separate view
  const renderCalendarPage = () => (
    <div>
      <div className="card nx-toolbar">
  <div className="toolbar-group">
    <label className="control-label">View</label>
    <select className="nx-select" value={calendarMode} onChange={(e) => setCalendarMode(e.target.value)}>
      <option value="day">Day</option>
      <option value="week">Week</option>
      <option value="month">Month</option>
      <option value="year">Year</option>
    </select>
  </div>

  {calendarMode === 'day' && (
    <>
      <div className="toolbar-group">
        <div className="view-toggle">
          <button
            type="button"
            className="view-btn"
            onClick={() => { 
              const prev = new Date(calendarDay);
              prev.setDate(prev.getDate() - 1);
              setCalendarDay(prev);
            }}
            title="Previous Day"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            <span className="view-icon">◀</span>
            Previous
          </button>
          <button
            type="button"
            className="button"
            onClick={() => setCalendarDay(new Date())}
            title="Go to Today"
            style={{ padding: '0.5rem 1.5rem', fontWeight: 600, minWidth: '120px' }}
          >
            Today
          </button>
          <button
            type="button"
            className="view-btn"
            onClick={() => { 
              const next = new Date(calendarDay);
              next.setDate(next.getDate() + 1);
              setCalendarDay(next);
            }}
            title="Next Day"
            style={{ padding: '0.5rem 1rem', fontWeight: 500 }}
          >
            Next
            <span className="view-icon">▶</span>
          </button>
        </div>
      </div>
      <div className="toolbar-group">
        <input
          type="date"
          className="nx-input"
          value={calendarDay.toISOString().split('T')[0]}
          onChange={(e) => {
            const d = new Date(e.target.value + 'T00:00:00');
            if (!isNaN(d.getTime())) setCalendarDay(d);
          }}
          style={{ padding: '0.5rem' }}
        />
      </div>
    </>
  )}

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

{/* Calendar Filters Panel */}
<div className="card" style={{ 
  marginTop: '0.5rem', 
  padding: '1rem', 
  display: 'flex', 
  flexWrap: 'wrap', 
  gap: '1rem', 
  alignItems: 'center',
  backgroundColor: darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)'
}}>
  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
    <Search size={16} />
    <span>Filters:</span>
  </div>
  
  {/* Schedule Type Filter */}
  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
    <label className="control-label" style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase' }}>Type</label>
    <select 
      className="nx-select" 
      value={calendarFilterType} 
      onChange={(e) => setCalendarFilterType(e.target.value)}
      style={{ minWidth: '120px', padding: '0.4rem' }}
    >
      <option value="all">All Types</option>
      <option value="daily">Daily</option>
      <option value="weekly">Weekly</option>
      <option value="monthly">Monthly</option>
      <option value="yearly">Yearly</option>
      <option value="holiday">Holiday</option>
    </select>
  </div>
  
  {/* Schedule Filter */}
  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
    <label className="control-label" style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase' }}>Schedule</label>
    <select 
      className="nx-select" 
      value={calendarFilterSchedules.length === 0 ? 'all' : calendarFilterSchedules[0]} 
      onChange={(e) => {
        if (e.target.value === 'all') {
          setCalendarFilterSchedules([]);
        } else {
          setCalendarFilterSchedules([parseInt(e.target.value, 10)]);
        }
      }}
      style={{ minWidth: '180px', padding: '0.4rem' }}
    >
      <option value="all">All Schedules</option>
      {(schedules || []).map(s => (
        <option key={s.id} value={s.id}>{s.name} {!s.is_active ? '(Inactive)' : ''}</option>
      ))}
    </select>
  </div>
  
  {/* Quick Toggles */}
  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginLeft: 'auto' }}>
    <label style={{ 
      display: 'flex', 
      alignItems: 'center', 
      gap: '0.5rem', 
      cursor: 'pointer',
      padding: '0.4rem 0.75rem',
      borderRadius: '6px',
      backgroundColor: calendarShowConflictsOnly ? 'rgba(255, 152, 0, 0.15)' : 'transparent',
      border: calendarShowConflictsOnly ? '1px solid #ff9800' : '1px solid var(--border-color)',
      transition: 'all 0.2s ease'
    }}>
      <input 
        type="checkbox" 
        checked={calendarShowConflictsOnly} 
        onChange={(e) => setCalendarShowConflictsOnly(e.target.checked)}
        style={{ width: 16, height: 16 }}
      />
      <AlertTriangle size={14} style={{ color: '#ff9800' }} />
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Conflicts Only</span>
    </label>
    
    <label style={{ 
      display: 'flex', 
      alignItems: 'center', 
      gap: '0.5rem', 
      cursor: 'pointer',
      padding: '0.4rem 0.75rem',
      borderRadius: '6px',
      backgroundColor: calendarShowInactive ? 'rgba(108, 117, 125, 0.15)' : 'transparent',
      border: calendarShowInactive ? '1px solid #6c757d' : '1px solid var(--border-color)',
      transition: 'all 0.2s ease'
    }}>
      <input 
        type="checkbox" 
        checked={calendarShowInactive} 
        onChange={(e) => setCalendarShowInactive(e.target.checked)}
        style={{ width: 16, height: 16 }}
      />
      <Ban size={14} style={{ color: '#6c757d' }} />
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Show Inactive</span>
    </label>
    
    {(calendarFilterSchedules.length > 0 || calendarFilterType !== 'all' || calendarShowConflictsOnly || calendarShowInactive) && (
      <button
        type="button"
        className="button"
        onClick={() => {
          setCalendarFilterSchedules([]);
          setCalendarFilterType('all');
          setCalendarShowConflictsOnly(false);
          setCalendarShowInactive(false);
        }}
        style={{ 
          padding: '0.4rem 0.75rem', 
          fontSize: '0.85rem',
          backgroundColor: 'transparent',
          border: '1px solid var(--border-color)',
          color: 'var(--text-color)'
        }}
      >
        <XCircle size={14} style={{ marginRight: '4px' }} />
        Clear Filters
      </button>
    )}
  </div>
</div>

{/* Breadcrumb Navigation */}
<div style={{ 
  display: 'flex', 
  alignItems: 'center', 
  gap: '0.5rem', 
  padding: '0.75rem 0',
  fontSize: '0.9rem',
  color: 'var(--text-secondary)'
}}>
  <button 
    type="button"
    onClick={() => {
      if (calendarMode === 'day') {
        setCalendarYear(calendarDay.getFullYear());
      }
      setCalendarMode('year');
    }}
    style={{ 
      background: 'none', 
      border: 'none', 
      cursor: 'pointer', 
      color: calendarMode === 'year' ? 'var(--button-bg)' : 'var(--text-secondary)',
      fontWeight: calendarMode === 'year' ? 600 : 400,
      padding: '0.25rem 0.5rem',
      borderRadius: '4px',
      transition: 'all 0.2s ease'
    }}
  >
    {calendarMode === 'day' ? calendarDay.getFullYear() : calendarYear}
  </button>
  {(calendarMode === 'month' || calendarMode === 'week' || calendarMode === 'day') && (
    <>
      <span style={{ color: 'var(--text-muted)' }}>/</span>
      <button 
        type="button"
        onClick={() => {
          if (calendarMode === 'day') {
            setCalendarMonth(calendarDay.getMonth() + 1);
            setCalendarYear(calendarDay.getFullYear());
          }
          setCalendarMode('month');
        }}
        style={{ 
          background: 'none', 
          border: 'none', 
          cursor: 'pointer', 
          color: calendarMode === 'month' ? 'var(--button-bg)' : 'var(--text-secondary)',
          fontWeight: calendarMode === 'month' ? 600 : 400,
          padding: '0.25rem 0.5rem',
          borderRadius: '4px',
          transition: 'all 0.2s ease'
        }}
      >
        {calendarMode === 'day' 
          ? calendarDay.toLocaleString(undefined, { month: 'long' })
          : new Date(calendarYear, calendarMonth - 1, 1).toLocaleString(undefined, { month: 'long' })}
      </button>
    </>
  )}
  {calendarMode === 'week' && (
    <>
      <span style={{ color: 'var(--text-muted)' }}>/</span>
      <span style={{ fontWeight: 600, color: 'var(--button-bg)' }}>
        Week of {calendarWeekStart.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
      </span>
    </>
  )}
  {calendarMode === 'day' && (
    <>
      <span style={{ color: 'var(--text-muted)' }}>/</span>
      <span style={{ fontWeight: 600, color: 'var(--button-bg)' }}>
        {calendarDay.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric' })}
      </span>
    </>
  )}
</div>

  {calendarMode === 'day' ? (() => {
    // Day view with hourly breakdown showing scheduled categories
    const selectedDay = new Date(calendarDay.getFullYear(), calendarDay.getMonth(), calendarDay.getDate());
    const dayTime = selectedDay.getTime();
    const todayTime = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime();
    const isToday = dayTime === todayTime;
    const currentHour = new Date().getHours();
    
    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = parseNaiveDatetime(iso);
      return d ? new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() : null;
    };

    // Get all schedules active on this day
    const daySchedules = (schedules || [])
      .filter(s => calendarShowInactive ? true : s.is_active)
      .filter(s => calendarFilterType === 'all' ? true : s.type === calendarFilterType)
      .filter(s => calendarFilterSchedules.length === 0 ? true : calendarFilterSchedules.includes(s.id))
      .filter(s => {
        if (!s.start_date) return false;
        return isScheduleActiveOnDay(s, dayTime, normalizeDay);
      })
      .map(s => ({
        ...s,
        cat: catMap.get(s.category_id) || { name: (s.sequence ? s.name : (s.category?.name || 'Unknown')), color: s.color || (s.category?.color || '#6c757d') }
      }));

    // Parse time range for a schedule
    const getTimeRange = (schedule) => {
      if (!schedule.recurrence_pattern) return { start: 0, end: 24 }; // All day
      try {
        const pattern = JSON.parse(schedule.recurrence_pattern);
        if (pattern.timeRange?.start) {
          const [startH, startM] = pattern.timeRange.start.split(':').map(Number);
          const [endH, endM] = (pattern.timeRange.end || '23:59').split(':').map(Number);
          // Handle overnight ranges (e.g., 22:00 to 03:00)
          const startDecimal = startH + (startM || 0) / 60;
          let endDecimal = endH + (endM || 0) / 60;
          // If end is smaller than start, it wraps to next day - for display, treat as extending to midnight
          const wrapsOvernight = endDecimal < startDecimal;
          return { start: startDecimal, end: wrapsOvernight ? 24 : endDecimal, wrapsOvernight, rawEnd: endDecimal };
        }
      } catch (e) {}
      return { start: 0, end: 24 }; // All day
    };

    // Build hour-by-hour breakdown
    const hours = [];
    for (let h = 0; h < 24; h++) {
      const hourSchedules = daySchedules.filter(s => {
        const range = getTimeRange(s);
        // Check if this hour falls within the schedule's time range
        if (range.start <= h && h < range.end) return true;
        // For overnight schedules, also check the morning portion (0 to rawEnd)
        if (range.wrapsOvernight && h < range.rawEnd) return true;
        return false;
      });
      
      // Determine winner for this hour (same logic as week view)
      const contentScheds = hourSchedules.filter(s => s.category_id || s.sequence);
      const exclusiveScheds = contentScheds.filter(s => s.exclusive);
      const hasExclusive = exclusiveScheds.length > 0;
      const blendScheds = contentScheds.filter(s => s.blend_enabled && !s.exclusive);
      const hasBlend = blendScheds.length > 1;
      const hasConflict = contentScheds.length > 1;
      
      let winner = null;
      if (contentScheds.length > 0) {
        if (hasExclusive) {
          // Exclusive schedule wins
          const sorted = [...exclusiveScheds].sort((a, b) => (b.priority ?? 5) - (a.priority ?? 5));
          winner = sorted[0];
        } else if (hasBlend) {
          winner = 'blend';
        } else {
          const sorted = [...contentScheds].sort((a, b) => {
            const priorityA = a.priority ?? 5;
            const priorityB = b.priority ?? 5;
            if (priorityA !== priorityB) return priorityB - priorityA;
            const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (endA !== endB) return endA - endB;
            return a.id - b.id;
          });
          winner = sorted[0];
        }
      }
      
      hours.push({
        hour: h,
        schedules: hourSchedules,
        contentScheds,
        winner,
        hasConflict,
        hasBlend,
        hasExclusive
      });
    }

    // Format hour for display
    const formatHour = (h) => {
      if (h === 0) return '12 AM';
      if (h === 12) return '12 PM';
      if (h < 12) return `${h} AM`;
      return `${h - 12} PM`;
    };

    // Check if any conflicts exist
    const hasAnyConflicts = hours.some(h => h.hasConflict && !h.hasBlend && !h.hasExclusive);
    const hasAnyBlends = hours.some(h => h.hasBlend);
    const hasAnyExclusives = hours.some(h => h.hasExclusive);

    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '8px'
        }}>
          <h2 style={{ 
            margin: 0,
            fontSize: '1.8rem',
            fontWeight: 600,
            color: 'var(--text-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            {calendarDay.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
            {isToday && (
              <span style={{
                fontSize: '0.75rem',
                padding: '4px 10px',
                backgroundColor: 'var(--button-bg)',
                color: '#fff',
                borderRadius: '12px',
                fontWeight: 600
              }}>
                TODAY
              </span>
            )}
          </h2>
          
          <div style={{ display: 'flex', gap: '8px' }}>
            {hasAnyBlends && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                border: '1px solid rgba(139, 92, 246, 0.5)',
                borderRadius: '8px',
                color: '#8b5cf6'
              }}>
                <Shuffle size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Blend Mode</span>
              </div>
            )}
            {hasAnyExclusives && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(20, 184, 166, 0.15)',
                border: '1px solid rgba(20, 184, 166, 0.5)',
                borderRadius: '8px',
                color: '#14B8A6'
              }}>
                <Lock size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Exclusive Schedule</span>
              </div>
            )}
            {hasAnyConflicts && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(255, 152, 0, 0.15)',
                border: '1px solid rgba(255, 152, 0, 0.5)',
                borderRadius: '8px',
                color: '#ff9800'
              }}>
                <AlertTriangle size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Conflicts</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Summary of active schedules */}
        {daySchedules.length > 0 && (
          <div style={{
            marginBottom: '1.5rem',
            padding: '12px 16px',
            backgroundColor: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
            borderRadius: '8px'
          }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px', color: 'var(--text-color)' }}>
              Active Schedules ({daySchedules.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {daySchedules.map((sched, idx) => {
                const range = getTimeRange(sched);
                const isAllDay = range.start === 0 && range.end === 24;
                const timeStr = isAllDay ? 'All Day' : `${formatHour(Math.floor(range.start))} - ${range.wrapsOvernight ? formatHour(Math.floor(range.rawEnd)) + ' (next day)' : formatHour(Math.floor(range.end))}`;
                return (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 10px',
                    backgroundColor: sched.color || sched.cat.color,
                    borderRadius: '6px',
                    color: '#fff',
                    fontSize: '0.8rem',
                    fontWeight: 500
                  }}>
                    {sched.exclusive && <Lock size={12} />}
                    {sched.blend_enabled && !sched.exclusive && <Shuffle size={12} />}
                    <span>{sched.name}</span>
                    <span style={{ opacity: 0.8, fontSize: '0.75rem' }}>({timeStr})</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Hourly timeline */}
        <div style={{ 
          display: 'flex',
          flexDirection: 'column',
          gap: '2px',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          {hours.map((hourData, idx) => {
            const isCurrentHour = isToday && hourData.hour === currentHour;
            const hasSchedules = hourData.contentScheds.length > 0;
            
            return (
              <div 
                key={idx}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '80px 1fr',
                  minHeight: '48px',
                  borderBottom: idx < 23 ? '1px solid var(--border-color)' : 'none',
                  backgroundColor: isCurrentHour 
                    ? 'rgba(59, 130, 246, 0.1)' 
                    : (hourData.hour >= 6 && hourData.hour < 22) 
                      ? 'transparent' 
                      : (darkMode ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.03)')
                }}
              >
                {/* Hour label */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '8px',
                  fontWeight: isCurrentHour ? 700 : 500,
                  fontSize: '0.85rem',
                  color: isCurrentHour ? 'var(--button-bg)' : 'var(--text-secondary)',
                  borderRight: '1px solid var(--border-color)',
                  backgroundColor: isCurrentHour ? 'rgba(59, 130, 246, 0.15)' : 'transparent'
                }}>
                  {formatHour(hourData.hour)}
                  {isCurrentHour && <span style={{ marginLeft: '4px', color: 'var(--button-bg)' }}>●</span>}
                </div>
                
                {/* Schedule blocks for this hour */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '4px 8px',
                  gap: '6px',
                  flexWrap: 'wrap'
                }}>
                  {!hasSchedules && (
                    <span style={{ 
                      fontSize: '0.8rem', 
                      color: 'var(--text-muted)',
                      fontStyle: 'italic'
                    }}>
                      No scheduled prerolls
                    </span>
                  )}
                  {hourData.contentScheds.map((sched, sIdx) => {
                    const isWinner = hourData.winner === sched || (hourData.hasBlend && sched.blend_enabled);
                    const isExclusive = sched.exclusive;
                    const isBlending = hourData.hasBlend && sched.blend_enabled;
                    const isLoser = hourData.hasConflict && !isWinner && !isBlending && !isExclusive;
                    
                    // Get category/sequence info
                    const categoryName = sched.category_id 
                      ? (categories.find(c => c.id === sched.category_id)?.name || 'Unknown')
                      : (sched.sequence ? 'Sequence' : 'Unknown');
                    
                    return (
                      <div 
                        key={sIdx}
                        title={`${sched.name}\nCategory: ${categoryName}\nType: ${sched.type}${isExclusive ? '\n🔒 Exclusive - overrides other schedules' : ''}${isBlending ? '\n🔀 Blending with other schedules' : ''}${isLoser ? '\n⚠️ Overridden by higher priority schedule' : ''}`}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 12px',
                          backgroundColor: sched.color || sched.cat.color,
                          borderRadius: '6px',
                          color: '#fff',
                          fontSize: '0.8rem',
                          fontWeight: 500,
                          opacity: isLoser ? 0.5 : 1,
                          textDecoration: isLoser ? 'line-through' : 'none',
                          border: isExclusive 
                            ? '2px solid rgba(20, 184, 166, 0.8)' 
                            : isWinner && hourData.hasConflict && !isBlending
                              ? '2px solid rgba(255, 215, 0, 0.8)'
                              : isBlending
                                ? '2px solid rgba(139, 92, 246, 0.8)'
                                : 'none',
                          boxShadow: isExclusive 
                            ? '0 0 8px rgba(20, 184, 166, 0.4)' 
                            : isWinner && hourData.hasConflict 
                              ? '0 0 8px rgba(255, 215, 0, 0.4)'
                              : 'none'
                        }}
                      >
                        {isExclusive && <Lock size={12} />}
                        {isWinner && hourData.hasConflict && !isExclusive && !isBlending && <Crown size={12} />}
                        {isBlending && <Shuffle size={12} />}
                        {isLoser && <AlertTriangle size={12} />}
                        <span>{sched.name}</span>
                        <span style={{ 
                          opacity: 0.8, 
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          backgroundColor: 'rgba(0,0,0,0.2)',
                          borderRadius: '4px'
                        }}>
                          {categoryName}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ 
          marginTop: '1rem',
          padding: '12px',
          backgroundColor: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
          borderRadius: '8px',
          fontSize: '0.8rem',
          color: 'var(--text-muted)'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--text-color)' }}>Legend:</div>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Lock size={14} style={{ color: '#14B8A6' }} />
              <span>Exclusive (overrides all)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Crown size={14} style={{ color: '#ffd700' }} />
              <span>Winner (highest priority)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Shuffle size={14} style={{ color: '#8b5cf6' }} />
              <span>Blending</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ opacity: 0.5, textDecoration: 'line-through' }}>⚠️ Overridden</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ 
                width: '20px', 
                height: '20px', 
                backgroundColor: darkMode ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.03)',
                borderRadius: '4px'
              }} />
              <span>Night hours (10 PM - 6 AM)</span>
            </div>
          </div>
        </div>
        
        {daySchedules.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '3rem',
            color: 'var(--text-muted)'
          }}>
            <Calendar size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
            <div style={{ fontSize: '1.1rem', fontWeight: 500 }}>No schedules active on this day</div>
            <div style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
              Create a schedule in the Schedules tab to see it here
            </div>
          </div>
        )}
      </div>
    );
  })() : calendarMode === 'week' ? (() => {
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
      const d = parseNaiveDatetime(iso);
      return d ? new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() : null;
    };

    const scheds = (schedules || [])
      .filter(s => calendarShowInactive ? true : s.is_active) // Active filter
      .filter(s => calendarFilterType === 'all' ? true : s.type === calendarFilterType) // Type filter
      .filter(s => calendarFilterSchedules.length === 0 ? true : calendarFilterSchedules.includes(s.id)) // Schedule filter
      .map(s => ({
      ...s,
      cat: catMap.get(s.category_id) || { name: (s.sequence ? s.name : (s.category?.name || 'Unknown')), color: s.color || (s.category?.color || '#6c757d') }
    }));

    const todayTime = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime();

    // Build conflict map for each day
    const dayConflicts = new Map(); // dayTime -> { schedules: [], hasConflict: boolean, hasBlend: boolean, hasExclusive: boolean, winner: schedule }
    days.forEach(day => {
      const t = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
      const activeScheds = scheds.filter(s => {
        if (!s.start_date) return false;
        return isScheduleActiveOnDay(s, t, normalizeDay);
      });
      
      // Filter to schedules that have actual content (category or sequence) - exclude pure fallback-only schedules
      // A schedule is "fallback-only" if it has NO category_id AND NO sequence, only a fallback_category_id
      const contentScheds = activeScheds.filter(s => s.category_id || s.sequence);
      
      // Check for exclusive schedules first (they override everything)
      const exclusiveScheds = contentScheds.filter(s => s.exclusive);
      const hasExclusive = exclusiveScheds.length > 0;
      
      // Check if all exclusive schedules have time restrictions (meaning they don't win all day)
      // If ANY exclusive schedule has a time range, the "exclusive" styling should be toned down
      // because other schedules will be active during the non-exclusive hours
      const exclusiveHasTimeRange = hasExclusive && exclusiveScheds.every(s => {
        if (!s.recurrence_pattern) return false;
        try {
          const pattern = JSON.parse(s.recurrence_pattern);
          return pattern.timeRange?.start ? true : false;
        } catch (e) {
          return false;
        }
      });
      
      // Non-exclusive schedules (schedules that run when the exclusive is NOT in its time window)
      const nonExclusiveScheds = contentScheds.filter(s => !s.exclusive);
      
      // Check for blend mode among non-exclusive schedules
      // When exclusive has time range, blending happens during non-exclusive hours
      const blendScheds = nonExclusiveScheds.filter(s => s.blend_enabled);
      // Blend mode is active if:
      // - No exclusive (original logic), OR
      // - Exclusive has time range AND 2+ non-exclusive schedules with blend enabled
      const hasBlend = (!hasExclusive && blendScheds.length >= 2) || 
                       (exclusiveHasTimeRange && blendScheds.length >= 2);
      
      // Conflict exists if 2+ schedules overlap but NOT all in blend mode and not exclusive taking over
      // When exclusive has time range, there's no "conflict" during non-exclusive hours if blending
      const hasConflict = contentScheds.length > 1 && !hasBlend && !(exclusiveHasTimeRange && blendScheds.length >= 2);
      
      // Determine winner using the same logic as backend:
      // 1. If exclusive schedules exist AND they don't have time ranges, exclusive wins all day
      // 2. If exclusive has time range, it wins during its window, but non-exclusive schedules also win during their time
      // 3. Otherwise, highest priority wins, then earliest end date, then earliest start, then lowest ID
      let winner = null;
      let nonExclusiveWinner = null; // Winner among non-exclusive schedules (active outside exclusive's time range)
      
      if (contentScheds.length > 0) {
        if (hasExclusive && !exclusiveHasTimeRange) {
          // Full-day exclusive: highest priority exclusive wins all day
          const sorted = [...exclusiveScheds].sort((a, b) => {
            const priorityA = a.priority ?? 5;
            const priorityB = b.priority ?? 5;
            if (priorityA !== priorityB) return priorityB - priorityA; // Higher priority first
            
            const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (endA !== endB) return endA - endB;
            
            return a.id - b.id;
          });
          winner = sorted[0];
        } else if (hasExclusive && exclusiveHasTimeRange) {
          // Time-restricted exclusive: wins during its time window
          const sorted = [...exclusiveScheds].sort((a, b) => {
            const priorityA = a.priority ?? 5;
            const priorityB = b.priority ?? 5;
            if (priorityA !== priorityB) return priorityB - priorityA;
            const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (endA !== endB) return endA - endB;
            return a.id - b.id;
          });
          winner = sorted[0]; // Exclusive wins during its time
          
          // Also determine winner among non-exclusive schedules (for the rest of the day)
          if (nonExclusiveScheds.length > 0) {
            if (hasBlend) {
              // All blending schedules are "winners" during non-exclusive hours
              nonExclusiveWinner = 'blend'; // Special marker for blend mode
            } else {
              const nonExSorted = [...nonExclusiveScheds].sort((a, b) => {
                const priorityA = a.priority ?? 5;
                const priorityB = b.priority ?? 5;
                if (priorityA !== priorityB) return priorityB - priorityA;
                const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
                const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
                if (endA !== endB) return endA - endB;
                const startA = new Date(a.start_date).getTime();
                const startB = new Date(b.start_date).getTime();
                if (startA !== startB) return startA - startB;
                return a.id - b.id;
              });
              nonExclusiveWinner = nonExSorted[0];
            }
          }
        } else {
          // Normal: highest priority wins
          const sorted = [...contentScheds].sort((a, b) => {
            const priorityA = a.priority ?? 5;
            const priorityB = b.priority ?? 5;
            if (priorityA !== priorityB) return priorityB - priorityA; // Higher priority first
            
            const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (endA !== endB) return endA - endB;
            
            const startA = new Date(a.start_date).getTime();
            const startB = new Date(b.start_date).getTime();
            if (startA !== startB) return startA - startB;
            
            return a.id - b.id;
          });
          winner = sorted[0];
        }
      }
      
      dayConflicts.set(t, { 
        schedules: activeScheds, 
        hasConflict, 
        hasBlend, 
        hasExclusive, 
        exclusiveHasTimeRange, 
        blendScheds, 
        exclusiveScheds, 
        nonExclusiveScheds,
        winner,
        nonExclusiveWinner // New: winner among non-exclusive schedules when exclusive has time range
      });
    });
    
    // Check if any day has conflicts or blend mode or exclusive
    const hasAnyConflicts = Array.from(dayConflicts.values()).some(d => d.hasConflict);
    const hasAnyBlends = Array.from(dayConflicts.values()).some(d => d.hasBlend);
    const hasAnyExclusives = Array.from(dayConflicts.values()).some(d => d.hasExclusive);

    return (
      <div className="card" style={{ padding: '1.5rem' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '8px'
        }}>
          <h2 style={{ 
            margin: 0,
            fontSize: '1.8rem',
            fontWeight: 600,
            color: 'var(--text-color)'
          }}>
            Week of {days[0].toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
          </h2>
          
          <div style={{ display: 'flex', gap: '8px' }}>
            {hasAnyBlends && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                border: '1px solid rgba(139, 92, 246, 0.5)',
                borderRadius: '8px',
                color: '#8b5cf6'
              }}>
                <Shuffle size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Blend Mode Active</span>
              </div>
            )}
            {hasAnyExclusives && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(20, 184, 166, 0.15)',
                border: '1px solid rgba(20, 184, 166, 0.5)',
                borderRadius: '8px',
                color: '#14B8A6'
              }}>
                <Lock size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Exclusive Schedule Active</span>
              </div>
            )}
            {hasAnyConflicts && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'rgba(255, 152, 0, 0.15)',
                border: '1px solid rgba(255, 152, 0, 0.5)',
                borderRadius: '8px',
                color: '#ff9800'
              }}>
                <AlertTriangle size={16} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Schedule Conflicts Detected</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Day headers with conflict/blend indicators */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '158px repeat(7, 1fr)', 
          gap: '4px',
          marginBottom: '8px'
        }}>
          <div></div>
          {days.map((day, idx) => {
            const t = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
            const isToday = t === todayTime;
            const dayData = dayConflicts.get(t);
            const hasConflict = dayData?.hasConflict;
            const hasBlend = dayData?.hasBlend;
            const hasExclusive = dayData?.hasExclusive;
            const exclusiveHasTimeRange = dayData?.exclusiveHasTimeRange;
            // Full-day exclusive gets bold red styling; time-restricted exclusive gets subtle styling
            const isFullDayExclusive = hasExclusive && !exclusiveHasTimeRange;
            // Time-restricted exclusive + blend = show blend styling (purple) since blending happens most of the day
            const hasTimeRestrictedExclusiveWithBlend = exclusiveHasTimeRange && hasBlend;
            
            return (
              <div key={idx} style={{ 
                textAlign: 'center',
                fontWeight: isToday ? 700 : 500,
                fontSize: '0.85rem',
                color: isFullDayExclusive 
                  ? '#ef4444' 
                  : (hasTimeRestrictedExclusiveWithBlend || hasBlend) 
                    ? '#8b5cf6' 
                    : (hasConflict ? '#ff9800' : (isToday ? 'var(--button-bg)' : 'var(--text-color)')),
                padding: '8px 4px',
                borderRadius: '4px',
                backgroundColor: isFullDayExclusive 
                  ? 'rgba(239, 68, 68, 0.15)'
                  : ((hasTimeRestrictedExclusiveWithBlend || hasBlend)
                    ? 'rgba(139, 92, 246, 0.15)'
                    : (hasConflict 
                      ? 'rgba(255, 152, 0, 0.15)' 
                      : (isToday ? (darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)') : 'transparent'))),
                border: isFullDayExclusive 
                  ? '1px solid rgba(239, 68, 68, 0.5)' 
                  : ((hasTimeRestrictedExclusiveWithBlend || hasBlend)
                    ? '1px solid rgba(139, 92, 246, 0.5)' 
                    : (hasConflict ? '1px solid rgba(255, 152, 0, 0.5)' : 'none'))
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', flexWrap: 'wrap' }}>
                  {day.toLocaleDateString(undefined, { weekday: 'short' })}
                  {hasTimeRestrictedExclusiveWithBlend && (
                    <>
                      <Shuffle size={12} title="Blend mode active outside exclusive time" />
                      <Lock size={10} style={{ opacity: 0.6 }} title="Exclusive during specific hours" />
                    </>
                  )}
                  {isFullDayExclusive && <Lock size={12} />}
                  {hasBlend && !hasExclusive && <Shuffle size={12} />}
                  {hasConflict && !hasBlend && !hasExclusive && <AlertTriangle size={12} />}
                </div>
                <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>{day.getDate()}</div>
              </div>
            );
          })}
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {scheds.map((sched, idx) => {
            // Find continuous spans for this schedule across the week
            const spans = [];
            let currentSpan = null;
            
            days.forEach((day, dayIdx) => {
              const t = new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
              const isActive = isScheduleActiveOnDay(sched, t, normalizeDay);
              const dayData = dayConflicts.get(t);
              const isWinner = dayData?.winner?.id === sched.id;
              const hasConflict = dayData?.hasConflict;
              const hasBlend = dayData?.hasBlend;
              const hasExclusive = dayData?.hasExclusive;
              const exclusiveHasTimeRange = dayData?.exclusiveHasTimeRange;
              const isInBlend = hasBlend && sched.blend_enabled;
              const isExclusive = hasExclusive && sched.exclusive;
              
              // Check if this non-exclusive schedule wins during non-exclusive hours
              const nonExWinner = dayData?.nonExclusiveWinner;
              const isNonExclusiveWinner = !sched.exclusive && (
                nonExWinner === 'blend' ? sched.blend_enabled : nonExWinner?.id === sched.id
              );
              
              if (isActive) {
                if (!currentSpan) {
                  currentSpan = { 
                    start: dayIdx, 
                    end: dayIdx, 
                    conflicts: [], 
                    isWinner: [], 
                    blends: [], 
                    exclusives: [],
                    exclusiveHasTimeRange: [],
                    isNonExclusiveWinner: []
                  };
                } else {
                  currentSpan.end = dayIdx;
                }
                currentSpan.conflicts.push(hasConflict);
                currentSpan.isWinner.push(isWinner);
                currentSpan.blends.push(isInBlend);
                currentSpan.exclusives.push(isExclusive);
                currentSpan.exclusiveHasTimeRange.push(exclusiveHasTimeRange);
                currentSpan.isNonExclusiveWinner.push(isNonExclusiveWinner);
              } else {
                if (currentSpan) {
                  spans.push(currentSpan);
                  currentSpan = null;
                }
              }
            });
            if (currentSpan) spans.push(currentSpan);
            
            if (spans.length === 0) return null;
            
            // Determine overall status for this schedule in the week
            const hasAnyWins = spans.some(span => span.isWinner.some(w => w));
            // Check if this schedule wins during non-exclusive hours (when there's a time-restricted exclusive)
            const hasAnyNonExclusiveWins = spans.some(span => span.isNonExclusiveWinner.some(w => w));
            // A schedule is only a "loser" if it loses during ALL its active hours
            // If there's a time-restricted exclusive and this schedule wins during non-exclusive hours, it's not a loser
            const hasTimeRestrictedExclusiveOverlap = spans.some(span => span.exclusiveHasTimeRange.some(e => e));
            const hasAnyLosses = spans.some(span => span.conflicts.some((c, i) => c && !span.isWinner[i]));
            // Not a real loser if we win during non-exclusive hours
            const isActualLoser = hasAnyLosses && !hasAnyWins && !hasAnyNonExclusiveWins && !hasTimeRestrictedExclusiveOverlap;
            const hasAnyConflictsForSched = spans.some(span => span.conflicts.some(c => c));
            const hasAnyBlends = spans.some(span => span.blends.some(b => b));
            const hasAnyExclusivesForSched = spans.some(span => span.exclusives.some(e => e));
            
            // Get time range info for this schedule if it's exclusive
            let schedTimeRange = null;
            if (sched.exclusive && sched.recurrence_pattern) {
              try {
                const pattern = JSON.parse(sched.recurrence_pattern);
                if (pattern?.timeRange?.start) {
                  schedTimeRange = `${pattern.timeRange.start}-${pattern.timeRange.end || '23:59'}`;
                }
              } catch (e) {}
            }
            
            return (
              <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div style={{ 
                  minWidth: '150px', 
                  fontWeight: 500, 
                  fontSize: '0.9rem',
                  color: 'var(--text-color)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {hasAnyExclusivesForSched ? (() => {
                    // Get time range if available
                    let timeRangeStr = schedTimeRange ? ` (${schedTimeRange})` : '';
                    return <Lock size={14} style={{ color: '#14B8A6', flexShrink: 0 }} title={`Exclusive - wins over other schedules${timeRangeStr ? ' during ' + timeRangeStr : ''}`} />;
                  })() : hasAnyBlends ? (
                    <Shuffle size={14} style={{ color: '#8b5cf6', flexShrink: 0 }} title={hasTimeRestrictedExclusiveOverlap 
                      ? "Blending with other schedules (outside exclusive schedule's time window)" 
                      : "Blending with other schedules"} />
                  ) : hasAnyConflictsForSched && (
                    (hasAnyWins || hasAnyNonExclusiveWins) ? (
                      <Crown size={14} style={{ color: '#ffd700', flexShrink: 0 }} title="Wins conflict (active)" />
                    ) : (
                      <AlertTriangle size={14} style={{ color: '#ff9800', flexShrink: 0 }} title="Loses conflict (overridden)" />
                    )
                  )}
                  <span style={{ 
                    opacity: isActualLoser ? 0.5 : 1,
                    textDecoration: isActualLoser ? 'line-through' : 'none'
                  }}>
                    {sched.name}
                    {schedTimeRange && <span style={{ fontSize: '0.75rem', opacity: 0.7, marginLeft: '4px' }}>({schedTimeRange})</span>}
                  </span>
                </div>
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
                    const spanHasConflict = span.conflicts.some(c => c);
                    const spanIsWinner = span.isWinner.some(w => w);
                    const spanIsNonExclusiveWinner = span.isNonExclusiveWinner.some(w => w);
                    const spanHasTimeRestrictedExclusive = span.exclusiveHasTimeRange.some(e => e);
                    const spanIsInBlend = span.blends.some(b => b);
                    const spanIsExclusive = span.exclusives.some(e => e);
                    
                    // A span is only a "loser" if it doesn't win anywhere
                    // If there's a time-restricted exclusive and this schedule wins during non-exclusive hours, it's not a loser
                    const spanIsLoser = spanHasConflict && !spanIsWinner && !spanIsNonExclusiveWinner && !spanHasTimeRestrictedExclusive && !spanIsInBlend;
                    
                    // Determine visual style based on status
                    let borderStyle = 'none';
                    let shadowStyle = '0 2px 4px rgba(0,0,0,0.2)';
                    let opacityStyle = 1;
                    let textDecorationStyle = 'none';
                    
                    if (spanIsExclusive) {
                      // Exclusive schedule - gold lock border
                      borderStyle = schedTimeRange 
                        ? '2px dashed rgba(20, 184, 166, 0.8)' // Time-restricted exclusive
                        : '2px solid rgba(20, 184, 166, 0.8)'; // Full-day exclusive
                      shadowStyle = '0 0 8px rgba(20, 184, 166, 0.4), 0 2px 4px rgba(0,0,0,0.2)';
                    } else if (spanIsWinner) {
                      // Winner - gold crown border
                      borderStyle = '2px solid rgba(255, 215, 0, 0.8)';
                      shadowStyle = '0 0 8px rgba(255, 215, 0, 0.6), 0 2px 4px rgba(0,0,0,0.2)';
                    } else if (spanIsInBlend || spanIsNonExclusiveWinner) {
                      // Blending or wins during non-exclusive hours - purple border
                      borderStyle = '2px solid rgba(139, 92, 246, 0.8)';
                      shadowStyle = '0 0 6px rgba(139, 92, 246, 0.4), 0 2px 4px rgba(0,0,0,0.2)';
                    } else if (spanHasTimeRestrictedExclusive && !spanIsExclusive) {
                      // Has time-restricted exclusive on same day but this is a non-exclusive schedule
                      // Show as active (it runs outside the exclusive's time window)
                      borderStyle = '2px solid rgba(139, 92, 246, 0.6)';
                      shadowStyle = '0 0 4px rgba(139, 92, 246, 0.3), 0 2px 4px rgba(0,0,0,0.2)';
                    } else if (spanIsLoser) {
                      // True loser - dimmed with strikethrough
                      borderStyle = '2px dashed rgba(255, 152, 0, 0.8)';
                      opacityStyle = 0.5;
                      textDecorationStyle = 'line-through';
                    }
                    
                    // Build tooltip
                    let tooltipText = sched.name;
                    if (spanIsExclusive) {
                      tooltipText = `🔒 ${sched.name} - EXCLUSIVE${schedTimeRange ? ` (${schedTimeRange})` : ''}\nWins over all other schedules${schedTimeRange ? ' during this time window' : ''}`;
                    } else if (spanIsWinner) {
                      tooltipText = `👑 ${sched.name} - ACTIVE (wins conflict)\nPriority: Ends soonest → Started earliest → Lowest ID`;
                    } else if (spanIsInBlend) {
                      tooltipText = spanHasTimeRestrictedExclusive
                        ? `🔀 ${sched.name} - BLENDING\nActive outside exclusive schedule's time window`
                        : `🔀 ${sched.name} - BLENDING\nPlays together with other blend-enabled schedules`;
                    } else if (spanHasTimeRestrictedExclusive && !spanIsExclusive) {
                      tooltipText = `✓ ${sched.name} - ACTIVE\nRuns outside the exclusive schedule's time window`;
                    } else if (spanIsLoser) {
                      tooltipText = `⚠️ ${sched.name} - OVERRIDDEN\nAnother schedule has higher priority`;
                    }
                    
                    return (
                      <div 
                        key={spanIdx} 
                        title={tooltipText}
                        style={{
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
                          gap: '4px',
                          boxShadow: shadowStyle,
                          border: borderStyle,
                          opacity: opacityStyle,
                          textDecoration: textDecorationStyle
                        }}
                      >
                        {spanIsExclusive && <Lock size={12} style={{ flexShrink: 0 }} />}
                        {spanIsWinner && !spanIsExclusive && <Crown size={12} style={{ flexShrink: 0 }} />}
                        {(spanIsInBlend || (spanHasTimeRestrictedExclusive && !spanIsExclusive && !spanIsLoser)) && !spanIsWinner && <Shuffle size={12} style={{ flexShrink: 0 }} />}
                        {spanIsLoser && <span>⚠️</span>}
                        {sched.name}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }).filter(Boolean)}
        </div>
        
        {/* Legend */}
        {hasAnyConflicts && (
          <div style={{ 
            marginTop: '1rem',
            padding: '12px',
            backgroundColor: darkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: 'var(--text-muted)'
          }}>
            <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--text-color)' }}>Conflict Resolution Rules:</div>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Crown size={14} style={{ color: '#ffd700' }} />
                <span>Winner (active) - Ends soonest, started earliest, or lowest ID</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ opacity: 0.5, textDecoration: 'line-through' }}>⚠️ Overridden</span>
                <span>- Lower priority schedule</span>
              </div>
            </div>
          </div>
        )}
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
      const d = parseNaiveDatetime(iso);
      return d ? new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() : null;
    };

    const scheds = (schedules || [])
      .filter(s => calendarShowInactive ? true : s.is_active) // Active filter
      .filter(s => calendarFilterType === 'all' ? true : s.type === calendarFilterType) // Type filter
      .filter(s => calendarFilterSchedules.length === 0 ? true : calendarFilterSchedules.includes(s.id)) // Schedule filter
      .map(s => ({
      ...s,
      cat: catMap.get(s.category_id) || { name: (s.sequence ? s.name : (s.category?.name || 'Unknown')), color: s.color || (s.category?.color || '#6c757d') }
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
              const isActive = isScheduleActiveOnDay(sched, t, normalizeDay);
              
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
                        {sched.name}
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
      const d = parseNaiveDatetime(iso);
      return d ? new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() : null;
    };

    // Filter schedules based on calendar filter settings
    const scheds = (schedules || [])
      .filter(s => calendarShowInactive ? true : s.is_active) // Active filter
      .filter(s => calendarFilterType === 'all' ? true : s.type === calendarFilterType) // Type filter
      .filter(s => calendarFilterSchedules.length === 0 ? true : calendarFilterSchedules.includes(s.id)) // Schedule filter
      .map(s => ({
        ...s,
        cat: catMap.get(s.category_id) || { name: (s.sequence ? s.name : (s.category?.name || 'Unknown')), color: s.color || (s.category?.color || '#6c757d') }
      }));

    // Track both schedules and their categories per day
    const byDay = new Map(); // dayTime -> { schedules: Set<schedule>, isFallback: boolean, hasConflict: boolean, hasBlend: boolean, hasExclusive: boolean, exclusiveHasTimeRange: boolean, blendScheds: [], exclusiveScheds: [], nonExclusiveWinner: null }
    days.forEach(d => {
      const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      byDay.set(t, { schedules: new Set(), isFallback: false, hasConflict: false, hasBlend: false, hasExclusive: false, exclusiveHasTimeRange: false, blendScheds: [], exclusiveScheds: [], nonExclusiveWinner: null });
    });

    // Map schedules to days, accounting for yearly repeats
    for (const s of scheds) {
      if (!s.start_date) continue;
      for (const d of days) {
        const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
        if (isScheduleActiveOnDay(s, t, normalizeDay)) {
          const dayData = byDay.get(t);
          if (dayData) dayData.schedules.add(s);
        }
      }
    }
    
    // Detect conflicts, blend mode, and exclusive schedules - multiple schedules with content on same day
    for (const [dayTime, dayData] of byDay.entries()) {
      // Filter to schedules that have actual content (category or sequence) - exclude pure fallback-only schedules
      const contentSchedules = Array.from(dayData.schedules).filter(s => s.category_id || s.sequence);
      
      // Check for exclusive schedules first (they override everything)
      const exclusiveScheds = contentSchedules.filter(s => s.exclusive);
      const hasExclusive = exclusiveScheds.length > 0;
      
      // Check if all exclusive schedules have time restrictions
      const exclusiveHasTimeRange = hasExclusive && exclusiveScheds.every(s => {
        if (!s.recurrence_pattern) return false;
        try {
          const pattern = JSON.parse(s.recurrence_pattern);
          return pattern.timeRange?.start ? true : false;
        } catch (e) {
          return false;
        }
      });
      
      // Non-exclusive schedules
      const nonExclusiveScheds = contentSchedules.filter(s => !s.exclusive);
      
      // Check for blend mode among non-exclusive schedules
      const blendScheds = nonExclusiveScheds.filter(s => s.blend_enabled);
      
      if (hasExclusive) {
        dayData.hasExclusive = true;
        dayData.exclusiveScheds = exclusiveScheds;
        dayData.exclusiveHasTimeRange = exclusiveHasTimeRange;
        
        // Multiple exclusive schedules competing = conflict (only case that matters)
        if (exclusiveScheds.length > 1) {
          dayData.hasConflict = true;
        }
        
        // When there's an exclusive schedule, it handles priority resolution
        // Non-exclusive schedules are either blending or have clear priority - NOT a conflict
        
        // Check blend mode among non-exclusive schedules
        if (blendScheds.length >= 2) {
          dayData.hasBlend = true;
          dayData.blendScheds = blendScheds;
          dayData.nonExclusiveWinner = 'blend';
        } else if (nonExclusiveScheds.length === 1) {
          // Single non-exclusive schedule - no blend display needed
          dayData.nonExclusiveWinner = nonExclusiveScheds[0];
        } else if (nonExclusiveScheds.length > 1) {
          // Multiple non-exclusive schedules
          // NOT a conflict - exclusive handles its window, rest have clear priority
          // Determine winner among non-exclusive schedules for display purposes
          const sorted = [...nonExclusiveScheds].sort((a, b) => {
            const priorityA = a.priority ?? 5;
            const priorityB = b.priority ?? 5;
            if (priorityA !== priorityB) return priorityB - priorityA;
            const endA = a.end_date ? new Date(a.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            const endB = b.end_date ? new Date(b.end_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (endA !== endB) return endA - endB;
            const startA = new Date(a.start_date).getTime();
            const startB = new Date(b.start_date).getTime();
            if (startA !== startB) return startA - startB;
            return a.id - b.id;
          });
          dayData.nonExclusiveWinner = sorted[0];
        }
      } else {
        // No exclusive schedules
        if (blendScheds.length >= 2) {
          // Multiple blending schedules - blend mode, no conflict
          dayData.hasBlend = true;
          dayData.blendScheds = blendScheds;
        } else if (contentSchedules.length > 1) {
          // Multiple schedules - check if it's a blend scenario or conflict
          if (blendScheds.length === contentSchedules.length) {
            // All schedules have blend enabled - show as blend
            dayData.hasBlend = true;
            dayData.blendScheds = blendScheds;
          } else {
            // Not all schedules are blending - true conflict
            dayData.hasConflict = true;
          }
        }
        // Single schedule case: no hasBlend, no hasConflict - just show normally
      }
    }
    
    // Show fallback category on days with no active schedules
    // Pick the fallback from the schedule that is closest to the given day
    const fallbackSchedules = (schedules || []).filter(s => s.fallback_category_id && s.is_active);
    
    // Helper to get year-agnostic date for yearly schedules
    const getYearAgnosticDates = (schedule, targetYear) => {
      const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
      const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
      const [, startMonth, startDay] = startDateStr.split('-').map(Number);
      const [, endMonth, endDay] = endDateStr.split('-').map(Number);
      
      // Handle year-wrap schedules (e.g., Dec 1 to Jan 15)
      if (startMonth > endMonth || (startMonth === endMonth && startDay > endDay)) {
        // Schedule wraps around year - return two ranges
        return [
          { start: new Date(targetYear - 1, startMonth - 1, startDay), end: new Date(targetYear, endMonth - 1, endDay) },
          { start: new Date(targetYear, startMonth - 1, startDay), end: new Date(targetYear + 1, endMonth - 1, endDay) }
        ];
      }
      return [{ start: new Date(targetYear, startMonth - 1, startDay), end: new Date(targetYear, endMonth - 1, endDay) }];
    };
    
    // Find the closest fallback schedule for a given day
    const findClosestFallback = (dayTime) => {
      if (fallbackSchedules.length === 0) return null;
      if (fallbackSchedules.length === 1) return fallbackSchedules[0];
      
      const dayDate = new Date(dayTime);
      const targetYear = dayDate.getFullYear();
      let closestSchedule = null;
      let closestDistance = Infinity;
      
      for (const s of fallbackSchedules) {
        const ranges = (s.type === 'yearly' || s.type === 'holiday') 
          ? getYearAgnosticDates(s, targetYear)
          : [{ start: new Date(normalizeDay(s.start_date)), end: s.end_date ? new Date(normalizeDay(s.end_date)) : new Date(normalizeDay(s.start_date)) }];
        
        for (const range of ranges) {
          // Check if day is within or near this range
          const rangeStart = range.start.getTime();
          const rangeEnd = range.end.getTime();
          
          // Calculate distance: 0 if within range, otherwise distance to nearest edge
          let distance;
          if (dayTime >= rangeStart && dayTime <= rangeEnd) {
            distance = 0; // Within range
          } else if (dayTime < rangeStart) {
            distance = rangeStart - dayTime; // Before range
          } else {
            distance = dayTime - rangeEnd; // After range
          }
          
          if (distance < closestDistance) {
            closestDistance = distance;
            closestSchedule = s;
          }
        }
      }
      
      return closestSchedule;
    };
    
    for (const [dayTime, dayData] of byDay.entries()) {
      if (dayData.schedules.size === 0) {
        const closestFallback = findClosestFallback(dayTime);
        if (closestFallback) {
          // No active schedules on this day, show the closest fallback
          dayData.isFallback = true;
          const fallbackSched = {
            ...closestFallback,
            category_id: closestFallback.fallback_category_id,
            name: `${closestFallback.name} (Fallback)`,
            cat: catMap.get(closestFallback.fallback_category_id) || { name: 'Fallback', color: '#6c757d' },
            isFallbackDisplay: true
          };
          dayData.schedules.add(fallbackSched);
        }
      }
    }

    const monthName = startOfMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' });
    const today = new Date();
    const todayTime = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
    
    // Calculate conflict and blend statistics for the month
    const conflictDays = Array.from(byDay.values()).filter(d => d.hasConflict);
    const totalConflicts = conflictDays.length;
    const blendDays = Array.from(byDay.values()).filter(d => d.hasBlend);
    const totalBlends = blendDays.length;

    return (
      <div className="card" style={{ marginBottom: '1rem', padding: '1.5rem' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '1.5rem',
          borderBottom: '2px solid var(--border-color)',
          paddingBottom: '0.75rem'
        }}>
          <h2 style={{ 
            margin: 0,
            fontSize: '1.8rem',
            fontWeight: 600,
            color: 'var(--text-color)'
          }}>{monthName}</h2>
          
          {/* Quick Stats */}
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
              border: '1px solid var(--border-color)'
            }}>
              <CalendarDays size={16} style={{ color: 'var(--button-bg)' }} />
              <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>
                {scheds.length} schedule{scheds.length !== 1 ? 's' : ''}
              </span>
            </div>
            
            {totalConflicts > 0 && (
              <div 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(255, 152, 0, 0.1)',
                  border: '1px solid rgba(255, 152, 0, 0.3)',
                  cursor: 'pointer'
                }}
                onClick={() => setCalendarShowConflictsOnly(!calendarShowConflictsOnly)}
                title="Click to filter to conflict days only"
              >
                <AlertTriangle size={16} style={{ color: '#ff9800' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ff9800' }}>
                  {totalConflicts} conflict{totalConflicts !== 1 ? 's' : ''}
                </span>
              </div>
            )}
            
            {totalBlends > 0 && (
              <div 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(139, 92, 246, 0.1)',
                  border: '1px solid rgba(139, 92, 246, 0.3)'
                }}
                title="Days with blended schedules"
              >
                <Shuffle size={16} style={{ color: '#8b5cf6' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#8b5cf6' }}>
                  {totalBlends} day{totalBlends !== 1 ? 's' : ''} blending
                </span>
              </div>
            )}
          </div>
        </div>
        
        {/* Conflict Summary Panel - shows when there are conflicts */}
        {totalConflicts > 0 && !calendarShowConflictsOnly && (
          <div style={{
            marginBottom: '1rem',
            padding: '1rem',
            borderRadius: '8px',
            backgroundColor: 'rgba(255, 152, 0, 0.08)',
            border: '1px solid rgba(255, 152, 0, 0.25)'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem', 
              marginBottom: '0.75rem',
              fontWeight: 600,
              color: '#ff9800'
            }}>
              <AlertTriangle size={18} />
              <span>Schedule Conflicts Detected</span>
            </div>
            <p style={{ 
              margin: '0 0 0.75rem 0', 
              fontSize: '0.85rem', 
              color: 'var(--text-secondary)',
              lineHeight: 1.5
            }}>
              <strong>{totalConflicts} day{totalConflicts !== 1 ? 's' : ''}</strong> have overlapping schedules. 
              The schedule that ends soonest takes priority. Look for the <Crown size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> crown icon.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.8rem' }}>
              <span style={{ 
                padding: '0.25rem 0.5rem', 
                borderRadius: '4px',
                backgroundColor: 'rgba(255, 215, 0, 0.2)',
                border: '1px solid rgba(255, 215, 0, 0.5)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                <Crown size={12} /> = Active
              </span>
              <span style={{ 
                padding: '0.25rem 0.5rem', 
                borderRadius: '4px',
                backgroundColor: 'rgba(0,0,0,0.1)',
                opacity: 0.6
              }}>
                Faded = Overridden
              </span>
            </div>
          </div>
        )}
        
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
            const dayData = byDay.get(t) || { schedules: new Set(), isFallback: false, hasConflict: false, hasBlend: false, hasExclusive: false, exclusiveHasTimeRange: false };
            const schedArray = Array.from(dayData.schedules);
            const isToday = t === todayTime;
            
            // If "Conflicts Only" filter is active, dim non-conflict days
            const isFilteredOut = calendarShowConflictsOnly && !dayData.hasConflict;
            const isWeekend = d.getDay() === 0 || d.getDay() === 6;
            
            // Determine day status for border styling
            // - Full-day exclusive: red border
            // - Time-restricted exclusive: dashed red border
            // - Time-restricted exclusive + blend: purple border (blend mode active most of day)
            // - Blend mode: purple border
            // - Conflict (no blend, no exclusive): orange border
            // - Normal: default border
            const hasTimeRestrictedExclusiveWithBlend = dayData.hasExclusive && dayData.exclusiveHasTimeRange && dayData.hasBlend;
            const isFullDayExclusive = dayData.hasExclusive && !dayData.exclusiveHasTimeRange;
            const isTimeRestrictedExclusive = dayData.hasExclusive && dayData.exclusiveHasTimeRange;
            
            let dayBorderColor = 'var(--border-color)';
            let dayBorderWidth = '1px';
            let dayBorderStyle = 'solid';
            let dayShadow = 'none';
            
            if (isToday) {
              dayBorderColor = 'var(--button-bg)';
              dayBorderWidth = '2px';
              dayShadow = '0 0 12px rgba(59, 130, 246, 0.3)';
            } else if (isFullDayExclusive) {
              dayBorderColor = '#14B8A6';
              dayBorderWidth = '2px';
              dayShadow = '0 0 8px rgba(20, 184, 166, 0.3)';
            } else if (hasTimeRestrictedExclusiveWithBlend || dayData.hasBlend) {
              dayBorderColor = '#8b5cf6';
              dayBorderWidth = '2px';
              dayShadow = '0 0 8px rgba(139, 92, 246, 0.3)';
            } else if (isTimeRestrictedExclusive) {
              // Time-restricted exclusive without blend - show dashed gold border
              dayBorderColor = '#14B8A6';
              dayBorderWidth = '2px';
              dayBorderStyle = 'dashed';
              dayShadow = '0 0 8px rgba(20, 184, 166, 0.2)';
            } else if (dayData.hasConflict) {
              dayBorderColor = '#ff9800';
              dayBorderWidth = '2px';
              dayShadow = '0 0 8px rgba(255, 152, 0, 0.3)';
            }
            
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
              // Sort by: priority (higher wins), then ends soonest, then started earliest, then lowest ID
              const sorted = [...nonFallbackSchedules].sort((a, b) => {
                const priorityA = a.priority ?? 5;
                const priorityB = b.priority ?? 5;
                if (priorityA !== priorityB) return priorityB - priorityA; // Higher priority first
                
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
                border: `${dayBorderWidth} ${dayBorderStyle} ${dayBorderColor}`,
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
                cursor: inMonth ? 'pointer' : 'default',
                boxShadow: dayShadow,
                opacity: isFilteredOut ? 0.3 : 1,
                pointerEvents: isFilteredOut ? 'none' : 'auto'
              }}
              onClick={() => {
                if (inMonth && !isFilteredOut) {
                  // Navigate to day view for the clicked date
                  setCalendarDay(new Date(d));
                  setCalendarMode('day');
                }
              }}
              onMouseEnter={(e) => {
                if (inMonth && !isFilteredOut) {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 4px 12px var(--shadow)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                // Restore the appropriate shadow based on day status
                let restoreShadow = 'none';
                if (isToday) {
                  restoreShadow = '0 0 12px rgba(59, 130, 246, 0.3)';
                } else if (isFullDayExclusive) {
                  restoreShadow = '0 0 8px rgba(20, 184, 166, 0.3)';
                } else if (hasTimeRestrictedExclusiveWithBlend || dayData.hasBlend) {
                  restoreShadow = '0 0 8px rgba(139, 92, 246, 0.3)';
                } else if (isTimeRestrictedExclusive) {
                  restoreShadow = '0 0 8px rgba(20, 184, 166, 0.2)';
                } else if (dayData.hasConflict) {
                  restoreShadow = '0 0 8px rgba(255, 152, 0, 0.3)';
                }
                e.currentTarget.style.boxShadow = restoreShadow;
              }}>
                {/* Blend Mode indicator - shown when 2+ schedules have blend enabled */}
                {dayData.hasBlend && !dayData.hasConflict && (
                  <div 
                    title={dayData.hasExclusive 
                      ? `🔀 BLEND + EXCLUSIVE\n\n${dayData.blendScheds.length} blending schedule${dayData.blendScheds.length > 1 ? 's' : ''}:\n${dayData.blendScheds.map((s, i) => `${i + 1}. ${s.name}`).join('\n')}\n\n${dayData.exclusiveScheds?.length || 0} exclusive schedule${(dayData.exclusiveScheds?.length || 0) > 1 ? 's' : ''}:\n${(dayData.exclusiveScheds || []).map((s, i) => `${i + 1}. ${s.name}`).join('\n')}\n\nExclusive runs during its time window.\nBlend schedules mix prerolls outside that window.`
                      : `🔀 BLEND MODE ACTIVE\n\n${dayData.blendScheds.length} schedules blending:\n${dayData.blendScheds.map((s, i) => `${i + 1}. ${s.name}`).join('\n')}\n\nPrerolls from all blending schedules are mixed together!\nNo conflicts - all schedules contribute.`}
                    style={{ 
                      position: 'absolute', 
                      top: 6, 
                      left: 6, 
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(139, 92, 246, 0.15)',
                      border: '1px solid rgba(139, 92, 246, 0.5)',
                      cursor: 'help',
                      zIndex: 1
                    }}>
                    <Shuffle size={12} style={{ color: '#8b5cf6' }} />
                    {dayData.hasExclusive && <Lock size={10} style={{ color: '#8b5cf6', opacity: 0.7 }} />}
                    <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#8b5cf6' }}>{dayData.blendScheds.length}{dayData.hasExclusive ? '+1' : ''}</span>
                  </div>
                )}
                
                {/* Exclusive Mode indicator - shown when exclusive schedule is active WITHOUT blend */}
                {dayData.hasExclusive && !dayData.hasBlend && !dayData.hasConflict && (
                  <div 
                    title={dayData.exclusiveHasTimeRange 
                      ? `🔒 TIME-RESTRICTED EXCLUSIVE\n\n${(dayData.exclusiveScheds || []).map(s => s.name).join(', ')}\n\nExclusive during specific hours only.\nOther schedules may run outside this window.`
                      : `🔒 EXCLUSIVE MODE\n\n${(dayData.exclusiveScheds || []).map(s => s.name).join(', ')}\n\nThis schedule takes priority all day.\nOther schedules on this day are overridden.`}
                    style={{ 
                      position: 'absolute', 
                      top: 6, 
                      left: 6, 
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: dayData.exclusiveHasTimeRange ? 'rgba(20, 184, 166, 0.1)' : 'rgba(20, 184, 166, 0.15)',
                      border: dayData.exclusiveHasTimeRange ? '1px dashed rgba(20, 184, 166, 0.5)' : '1px solid rgba(20, 184, 166, 0.5)',
                      cursor: 'help',
                      zIndex: 1
                    }}>
                    <Lock size={12} style={{ color: '#14B8A6' }} />
                    {dayData.exclusiveHasTimeRange && <Clock size={10} style={{ color: '#14B8A6', opacity: 0.7 }} />}
                  </div>
                )}
                
                {/* Enhanced Conflict warning indicator with Lucide icon - only show for true conflicts */}
                {dayData.hasConflict && (
                  <div 
                    title={dayData.hasExclusive 
                      ? `⚠️ MULTIPLE EXCLUSIVE SCHEDULES\n\n${dayData.exclusiveScheds?.length || 0} exclusive schedules competing:\n${(dayData.exclusiveScheds || []).map((s, i) => `${i + 1}. ${s.name}`).join('\n')}\n\nOnly one exclusive schedule can be active at a time.`
                      : `⚠️ SCHEDULE CONFLICT\n\n${schedArray.length} schedules active on this day:\n${schedArray.map((s, i) => `${i + 1}. ${s.name}${s === winningSchedule ? ' ← ACTIVE' : ' (overridden)'}`).join('\n')}\n\nTip: Enable "Blend Mode" on schedules to mix their prerolls together!\n\nPriority Rules:\n1. Higher priority value\n2. Ends soonest\n3. Started earliest\n4. Lowest ID`}
                    style={{ 
                      position: 'absolute', 
                      top: 6, 
                      left: 6, 
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(255, 152, 0, 0.15)',
                      border: '1px solid rgba(255, 152, 0, 0.5)',
                      cursor: 'help',
                      zIndex: 1
                    }}>
                    <AlertTriangle size={12} style={{ color: '#ff9800' }} />
                    <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#ff9800' }}>{dayData.hasExclusive ? dayData.exclusiveScheds?.length : schedArray.length}</span>
                  </div>
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
                    
                    let tooltipText = `${scheduleNames}${dayData.isFallback ? ' (Fallback)' : ''}\nCategory: ${data.cat.name}\nType: ${data.schedObjs[0]?.type || 'unknown'}`;
                    
                    // Check if this schedule is part of blend mode or exclusive
                    const isInBlend = dayData.hasBlend && data.schedObjs.some(s => s.blend_enabled);
                    const isExclusive = dayData.hasExclusive && data.schedObjs.some(s => s.exclusive);
                    
                    // Check if this exclusive schedule has a time range (not full-day exclusive)
                    let exclusiveTimeRange = '';
                    let isTimeRestrictedExclusive = false;
                    if (isExclusive) {
                      const exclusiveSched = data.schedObjs.find(s => s.exclusive);
                      if (exclusiveSched && exclusiveSched.recurrence_pattern) {
                        try {
                          const pattern = JSON.parse(exclusiveSched.recurrence_pattern);
                          if (pattern.timeRange?.start) {
                            exclusiveTimeRange = `${pattern.timeRange.start}-${pattern.timeRange.end || '23:59'}`;
                            isTimeRestrictedExclusive = true;
                          }
                        } catch (e) {}
                      }
                    }
                    
                    // Full-day exclusive gets bold red styling; time-restricted exclusive gets subtle styling
                    const isFullDayExclusive = isExclusive && !isTimeRestrictedExclusive;
                    
                    if (isExclusive) {
                      const timeRangeStr = exclusiveTimeRange ? ` during ${exclusiveTimeRange}` : '';
                      tooltipText += `\n\nEXCLUSIVE - Wins over other schedules${timeRangeStr}`;
                    } else if (isInBlend) {
                      tooltipText += '\n\nBLENDING - Prerolls mixed with other schedules';
                    } else if (dayData.hasConflict && isWinner) {
                      tooltipText += '\n\nACTIVE - This schedule takes priority';
                    } else if (dayData.hasConflict && !dayData.isFallback) {
                      tooltipText += '\n\nOVERRIDDEN - Higher priority schedule is active';
                    }
                    
                    // Show first schedule name, or combined names if multiple
                    const displayName = data.schedules.length === 1 ? data.schedules[0] : scheduleNames;
                    
                    // Check if schedule is inactive (greyed out)
                    const isInactive = data.schedObjs.some(s => !s.is_active);
                    
                    return (
                      <div 
                        key={catId + '_' + i} 
                        title={tooltipText} 
                        style={{
                        backgroundColor: dayData.isFallback ? 'transparent' : (isInactive ? '#6c757d' : scheduleColor),
                        border: dayData.isFallback 
                          ? `2px dashed ${scheduleColor}` 
                          : (isFullDayExclusive
                            ? '2px solid rgba(239, 68, 68, 0.8)'
                            : (isTimeRestrictedExclusive
                              ? '1px dashed rgba(239, 68, 68, 0.5)'
                              : (isInBlend 
                                ? '2px solid rgba(139, 92, 246, 0.8)' 
                                : (isWinner && dayData.hasConflict ? '2px solid rgba(255, 215, 0, 0.8)' : 'none')))),
                        color: dayData.isFallback ? scheduleColor : '#fff', 
                        borderRadius: '4px',
                        padding: '3px 6px', 
                        fontSize: '0.7rem',
                        fontWeight: isWinner || isInBlend ? 600 : 500,
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis',
                        boxShadow: dayData.isFallback 
                          ? 'none' 
                          : (isFullDayExclusive
                              ? '0 2px 8px rgba(239, 68, 68, 0.4)'
                              : (isInBlend
                                  ? '0 2px 8px rgba(139, 92, 246, 0.4)'
                                  : (isWinner && dayData.hasConflict 
                                      ? '0 2px 8px rgba(255, 215, 0, 0.4)' 
                                      : '0 1px 3px rgba(0,0,0,0.2)'))),
                        opacity: dayData.isFallback 
                          ? 0.8 
                          : (dayData.hasConflict && !isWinner && !isInBlend && !isExclusive ? 0.5 : (isInactive ? 0.6 : 1)),
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px'
                      }}>
                        {isExclusive && <Lock size={10} style={{ flexShrink: 0, opacity: isTimeRestrictedExclusive ? 0.7 : 1 }} />}
                        {isExclusive && exclusiveTimeRange && (
                          <span style={{ fontSize: '0.55rem', opacity: 0.8, flexShrink: 0 }}>({exclusiveTimeRange})</span>
                        )}
                        {!isExclusive && isInBlend && <Shuffle size={10} style={{ flexShrink: 0 }} />}
                        {!isExclusive && !isInBlend && isWinner && dayData.hasConflict && <Crown size={10} style={{ flexShrink: 0 }} />}
                        {isInactive && <Ban size={10} style={{ flexShrink: 0, opacity: 0.8 }} />}
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{displayName}</span>
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
    const counts = Array.from({ length: 12 }, (_, m) => ({ month: m, cats: new Map(), conflictDays: 0, uniqueScheduledDays: 0 }));
    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = parseNaiveDatetime(iso);
      return d ? new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() : null;
    };
    
    // Iterate through each day of the year using proper date construction
    for (let month = 0; month < 12; month++) {
      const daysInMonth = new Date(calendarYear, month + 1, 0).getDate();
      const map = counts[month].cats;
      
      for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(calendarYear, month, day);
        const t = d.getTime();
        
        let activeSchedulesForDay = 0;
        let dayHasAnySchedule = false;
        
        // Check each schedule to see if it's active on this day
        // Apply calendar filters
        for (const s of (schedules || [])) {
          // Apply filters
          if (!s.start_date || !s.category_id) continue;
          if (!calendarShowInactive && !s.is_active) continue; // Active filter
          if (calendarFilterType !== 'all' && s.type !== calendarFilterType) continue; // Type filter
          if (calendarFilterSchedules.length > 0 && !calendarFilterSchedules.includes(s.id)) continue; // Schedule filter
          
          const isActive = isScheduleActiveOnDay(s, t, normalizeDay);
          
          if (isActive) {
            map.set(s.category_id, (map.get(s.category_id) || 0) + 1);
            dayHasAnySchedule = true;
            // Only count non-fallback schedules for conflicts
            if (!s.fallback_category_id) {
              activeSchedulesForDay++;
            }
          }
        }
        
        // Track unique days that have at least one schedule
        if (dayHasAnySchedule) {
          counts[month].uniqueScheduledDays++;
        }
        
        // Track if this day has conflicts (multiple active non-fallback schedules)
        if (activeSchedulesForDay > 1) {
          counts[month].conflictDays++;
        }
      }
    }
    
    // Add fallback category for days with no active schedules
    // Use the closest fallback schedule for each empty day
    const fallbackSchedules = (schedules || []).filter(s => s.fallback_category_id && s.is_active);
    
    // Helper to get year-agnostic dates for yearly schedules
    const getYearAgnosticDatesForYear = (schedule, targetYear) => {
      const startDateStr = schedule.start_date.includes('T') ? schedule.start_date.split('T')[0] : schedule.start_date;
      const endDateStr = schedule.end_date ? (schedule.end_date.includes('T') ? schedule.end_date.split('T')[0] : schedule.end_date) : startDateStr;
      const [, startMonth, startDay] = startDateStr.split('-').map(Number);
      const [, endMonth, endDay] = endDateStr.split('-').map(Number);
      
      // Handle year-wrap schedules (e.g., Dec 1 to Jan 15)
      if (startMonth > endMonth || (startMonth === endMonth && startDay > endDay)) {
        return [
          { start: new Date(targetYear - 1, startMonth - 1, startDay), end: new Date(targetYear, endMonth - 1, endDay) },
          { start: new Date(targetYear, startMonth - 1, startDay), end: new Date(targetYear + 1, endMonth - 1, endDay) }
        ];
      }
      return [{ start: new Date(targetYear, startMonth - 1, startDay), end: new Date(targetYear, endMonth - 1, endDay) }];
    };
    
    // Find the closest fallback schedule for a given day
    const findClosestFallbackForDay = (dayTime) => {
      if (fallbackSchedules.length === 0) return null;
      if (fallbackSchedules.length === 1) return fallbackSchedules[0];
      
      const dayDate = new Date(dayTime);
      const targetYear = dayDate.getFullYear();
      let closestSchedule = null;
      let closestDistance = Infinity;
      
      for (const s of fallbackSchedules) {
        const ranges = (s.type === 'yearly' || s.type === 'holiday') 
          ? getYearAgnosticDatesForYear(s, targetYear)
          : [{ start: new Date(normalizeDay(s.start_date)), end: s.end_date ? new Date(normalizeDay(s.end_date)) : new Date(normalizeDay(s.start_date)) }];
        
        for (const range of ranges) {
          const rangeStart = range.start.getTime();
          const rangeEnd = range.end.getTime();
          
          let distance;
          if (dayTime >= rangeStart && dayTime <= rangeEnd) {
            distance = 0;
          } else if (dayTime < rangeStart) {
            distance = rangeStart - dayTime;
          } else {
            distance = dayTime - rangeEnd;
          }
          
          if (distance < closestDistance) {
            closestDistance = distance;
            closestSchedule = s;
          }
        }
      }
      
      return closestSchedule;
    };
    
    // Re-iterate through days to add fallback categories based on proximity
    for (let m = 0; m < 12; m++) {
      const daysInMonth = new Date(calendarYear, m + 1, 0).getDate();
      const map = counts[m].cats;
      
      for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(calendarYear, m, day);
        const t = d.getTime();
        
        // Check if this day has any active schedule
        let dayHasSchedule = false;
        for (const s of (schedules || [])) {
          if (!s.start_date || !s.category_id) continue;
          if (!calendarShowInactive && !s.is_active) continue;
          if (calendarFilterType !== 'all' && s.type !== calendarFilterType) continue;
          if (calendarFilterSchedules.length > 0 && !calendarFilterSchedules.includes(s.id)) continue;
          
          if (isScheduleActiveOnDay(s, t, normalizeDay)) {
            dayHasSchedule = true;
            break;
          }
        }
        
        // If no schedule, add the closest fallback
        if (!dayHasSchedule) {
          const closestFallback = findClosestFallbackForDay(t);
          if (closestFallback) {
            map.set(closestFallback.fallback_category_id, (map.get(closestFallback.fallback_category_id) || 0) + 1);
          }
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
            const totalDays = entry.uniqueScheduledDays; // Use unique scheduled days count
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
                            // Apply same filters as main year view
                            if (!calendarShowInactive && !s.is_active) continue;
                            if (calendarFilterType !== 'all' && s.type !== calendarFilterType) continue;
                            if (calendarFilterSchedules.length > 0 && !calendarFilterSchedules.includes(s.id)) continue;
                            
                            if (isScheduleActiveOnDay(s, t, normalizeDay)) {
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
                        // Count total schedules active in this month (with filters)
                        const totalScheds = (schedules || []).filter(s => {
                          if (!s.start_date || !s.category_id) return false;
                          // Apply same filters
                          if (!calendarShowInactive && !s.is_active) return false;
                          if (calendarFilterType !== 'all' && s.type !== calendarFilterType) return false;
                          if (calendarFilterSchedules.length > 0 && !calendarFilterSchedules.includes(s.id)) return false;
                          
                          for (let day = 1; day <= daysInMonth; day++) {
                            const d = new Date(calendarYear, entry.month, day);
                            if (isScheduleActiveOnDay(s, d.getTime(), normalizeDay)) return true;
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
  );

  // Create Schedule page - separate view  
  const renderCreateSchedulePage = () => (
    <div>
      <div className="upload-section" style={{ maxWidth: '1200px', margin: '30px auto' }}>
        {/* Header with Progress Steps */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.8rem', fontWeight: 700 }}>Create New Schedule</h2>
          </div>
          
          {/* Visual Step Progress Indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            padding: '1rem',
            backgroundColor: 'var(--bg-color)',
            borderRadius: '8px',
            border: '1px solid var(--border-color)'
          }}>
            {[
              { num: 1, label: 'Mode', icon: <Target size={16} /> },
              { num: 2, label: 'Details', icon: <Edit size={16} /> },
              { num: 3, label: scheduleMode === 'simple' ? 'Category' : 'Sequence', icon: scheduleMode === 'simple' ? <Folder size={16} /> : <Film size={16} /> },
              { num: 4, label: 'Review', icon: <CheckCircle size={16} /> }
            ].map((step, index, arr) => (
              <React.Fragment key={step.num}>
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--button-bg)',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 600,
                    fontSize: '0.9rem'
                  }}>
                    {step.num}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Step {step.num}</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-color)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <span>{step.icon}</span>
                      {step.label}
                    </div>
                  </div>
                </div>
                {index < arr.length - 1 && (
                  <div style={{
                    width: '40px',
                    height: '2px',
                    backgroundColor: 'var(--border-color)'
                  }} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
        
        <form onSubmit={handleCreateSchedule}>
          {/* Step 1: Mode Selection */}
          <div style={{ 
            marginBottom: '2rem', 
            padding: '1.5rem', 
            backgroundColor: 'var(--card-bg)', 
            borderRadius: '12px', 
            border: '2px solid var(--border-color)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '32px', 
                height: '32px', 
                borderRadius: '50%', 
                backgroundColor: 'var(--button-bg)',
                color: 'white',
                fontWeight: 700,
                fontSize: '1rem'
              }}>1</div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Schedule Mode</h3>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <label style={{ 
                display: 'flex', 
                flexDirection: 'column',
                cursor: 'pointer', 
                padding: '1.25rem', 
                backgroundColor: scheduleMode === 'simple' ? 'var(--button-bg)' : 'var(--bg-color)', 
                color: scheduleMode === 'simple' ? 'white' : 'var(--text-color)', 
                borderRadius: '8px', 
                border: '3px solid ' + (scheduleMode === 'simple' ? 'var(--button-bg)' : 'var(--border-color)'), 
                transition: 'all 0.2s',
                position: 'relative'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <input
                    type="radio"
                    value="simple"
                    checked={scheduleMode === 'simple'}
                    onChange={(e) => setScheduleMode(e.target.value)}
                    style={{ marginRight: '0.75rem', width: '18px', height: '18px' }}
                  />
                  <span style={{ display: 'flex', alignItems: 'center', marginRight: '0.5rem' }}><Folder size={24} /></span>
                  <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>Simple Mode</span>
                </div>
                <p style={{ margin: '0 0 0 2.25rem', fontSize: '0.9rem', opacity: 0.9 }}>
                  Select a single category with random or sequential playback. Perfect for basic scheduling needs.
                </p>
              </label>
              
              <label style={{ 
                display: 'flex', 
                flexDirection: 'column',
                cursor: 'pointer', 
                padding: '1.25rem', 
                backgroundColor: scheduleMode === 'advanced' ? 'var(--button-bg)' : 'var(--bg-color)', 
                color: scheduleMode === 'advanced' ? 'white' : 'var(--text-color)', 
                borderRadius: '8px', 
                border: '3px solid ' + (scheduleMode === 'advanced' ? 'var(--button-bg)' : 'var(--border-color)'), 
                transition: 'all 0.2s',
                position: 'relative'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <input
                    type="radio"
                    value="advanced"
                    checked={scheduleMode === 'advanced'}
                    onChange={(e) => setScheduleMode(e.target.value)}
                    style={{ marginRight: '0.75rem', width: '18px', height: '18px' }}
                  />
                  <span style={{ display: 'flex', alignItems: 'center', marginRight: '0.5rem' }}><Film size={24} /></span>
                  <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>Sequence Mode</span>
                </div>
                <p style={{ margin: '0 0 0 2.25rem', fontSize: '0.9rem', opacity: 0.9 }}>
                  Build custom sequences with multiple categories and fixed prerolls. Full creative control.
                </p>
              </label>
            </div>

            {/* Helpful comparison guide */}
            <div style={{
              marginTop: '1rem',
              padding: '1rem',
              backgroundColor: 'rgba(59, 130, 246, 0.05)',
              borderRadius: '8px',
              border: '1px solid rgba(59, 130, 246, 0.2)'
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.25rem' }}>ℹ️</span>
                <div style={{ flex: 1 }}>
                  <strong style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>When to use each mode:</strong>
                  <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.25rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                    <li><strong>Simple Mode:</strong> Quick setup for basic needs - "Play all prerolls from my Holiday category during December"</li>
                    <li><strong>Sequence Mode:</strong> Advanced control - "Play Studio Logo + Random Trailer + Holiday Message in that exact order"</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Holiday Browser Banner - Between Steps 1 & 2 */}
          <div 
            onClick={() => {
              loadHolidayCountries();
              loadHolidays(holidaySelectedCountry, holidaySelectedYear);
              checkHolidayApiStatus();
              setShowHolidayBrowser(true);
            }}
            style={{ 
              marginBottom: '2rem', 
              padding: '1rem 1.5rem', 
              backgroundColor: darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.08)', 
              borderRadius: '12px', 
              border: '2px dashed rgba(59, 130, 246, 0.4)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = darkMode ? 'rgba(59, 130, 246, 0.25)' : 'rgba(59, 130, 246, 0.12)';
              e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.6)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = darkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.08)';
              e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.4)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ fontSize: '2rem' }}>🌍</span>
              <div>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)', marginBottom: '0.25rem' }}>
                  Quick Start: Browse Holidays
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  Select from 100+ countries to auto-fill your schedule with holiday dates
                </div>
              </div>
            </div>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem',
              padding: '0.5rem 1rem',
              backgroundColor: 'var(--button-bg)',
              color: 'white',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '0.9rem'
            }}>
              Browse <ChevronRight size={16} />
            </div>
          </div>

          {/* Step 2: Basic Information */}
          <div style={{ 
            marginBottom: '2rem', 
            padding: '1.5rem', 
            backgroundColor: 'var(--card-bg)', 
            borderRadius: '12px', 
            border: '2px solid var(--border-color)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '32px', 
                height: '32px', 
                borderRadius: '50%', 
                backgroundColor: 'var(--button-bg)',
                color: 'white',
                fontWeight: 700,
                fontSize: '1rem'
              }}>2</div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Basic Information</h3>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Schedule Name <span style={{ color: '#dc3545' }}>*</span>
                </label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="e.g., Weekend Movie Night"
                  value={scheduleForm.name}
                  onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
                  required
                  style={{ 
                    padding: '0.75rem', 
                    fontSize: '1rem',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    width: '90%'
                  }}
                />
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Schedule Type <span style={{ color: '#dc3545' }}>*</span>
                </label>
                <select
                  className="nx-select"
                  value={scheduleForm.type}
                  onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
                  style={{ 
                    padding: '0.75rem', 
                    fontSize: '1rem',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    width: '95%'
                  }}
                >
                  <option value="daily">📅 Daily</option>
                  <option value="weekly">📆 Weekly</option>
                  <option value="monthly">🗓️ Monthly</option>
                  <option value="yearly">📋 Yearly</option>
                  <option value="holiday">🎉 Holiday</option>
                  <option value="custom">⚙️ Custom</option>
                </select>
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Start Date & Time <span style={{ color: '#dc3545' }}>*</span>
                </label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.start_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, start_date: e.target.value})}
                  required
                  style={{ 
                    padding: '0.75rem', 
                    fontSize: '1rem',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    width: '90%'
                  }}
                />
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  End Date & Time <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>(Optional)</span>
                </label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.end_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                  style={{ 
                    padding: '0.75rem', 
                    fontSize: '1rem',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    width: '90%'
                  }}
                />
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                  Leave blank for indefinite schedule
                </p>
              </div>
            </div>
          </div>

          {/* Step 3: Recurrence Pattern - Daily */}
          {scheduleForm.type === 'daily' && (
            <div style={{ 
              marginBottom: '2rem', 
              padding: '1.5rem', 
              backgroundColor: 'var(--card-bg)', 
              borderRadius: '12px', 
              border: '2px solid var(--border-color)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '50%', 
                  backgroundColor: 'var(--button-bg)',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '1rem'
                }}>3</div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>⏰ Daily Recurrence</h3>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                    Start Time <span style={{ color: '#dc3545' }}>*</span>
                  </label>
                  <input
                    type="time"
                    className="nx-input"
                    value={timeRange.start || ''}
                    onChange={(e) => setTimeRange({...timeRange, start: e.target.value})}
                    style={{ 
                      padding: '0.75rem', 
                      fontSize: '1rem',
                      border: '2px solid var(--border-color)',
                      borderRadius: '6px',
                      width: '100%'
                    }}
                  />
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                    When should this schedule activate?
                  </p>
                </div>
                
                <div>
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                    End Time <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>(Optional)</span>
                  </label>
                  <input
                    type="time"
                    className="nx-input"
                    value={timeRange.end || ''}
                    onChange={(e) => setTimeRange({...timeRange, end: e.target.value})}
                    style={{ 
                      padding: '0.75rem', 
                      fontSize: '1rem',
                      border: '2px solid var(--border-color)',
                      borderRadius: '6px',
                      width: '100%'
                    }}
                  />
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                    Leave blank for specific time trigger
                  </p>
                </div>
              </div>
              
              <div style={{ 
                marginTop: '1rem', 
                padding: '0.75rem 1rem', 
                backgroundColor: timeRange.start ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)', 
                borderRadius: '6px',
                border: '1px solid ' + (timeRange.start ? 'rgba(40, 167, 69, 0.3)' : 'rgba(220, 53, 69, 0.3)')
              }}>
                <p style={{ fontSize: '0.9rem', color: timeRange.start ? '#28a745' : '#dc3545', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.2rem' }}>{timeRange.start ? '✓' : '⚠️'}</span>
                  {timeRange.start 
                    ? `Schedule will run daily ${timeRange.end ? `from ${timeRange.start} to ${timeRange.end}` : `at ${timeRange.start}`}`
                    : 'Please select at least a start time to continue'}
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Recurrence Pattern - Weekly */}
          {scheduleForm.type === 'weekly' && (
            <div style={{ 
              marginBottom: '2rem', 
              padding: '1.5rem', 
              backgroundColor: 'var(--card-bg)', 
              borderRadius: '12px', 
              border: '2px solid var(--border-color)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '50%', 
                  backgroundColor: 'var(--button-bg)',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '1rem'
                }}>3</div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}><CalendarDays size={20} style={{marginRight: '0.5rem', verticalAlign: 'middle'}} /> Weekly Recurrence</h3>
              </div>
              
              <label style={{ display: 'block', marginBottom: '1rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                Select Days of the Week <span style={{ color: '#dc3545' }}>*</span>
              </label>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
                {['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map((day, index) => {
                  const dayLower = day.toLowerCase();
                  const isSelected = weekDays.includes(dayLower);
                  const dayEmojis = ['☀️', '🌙', '💼', '📚', '⚡', '🎉', '🌟'];
                  return (
                    <label
                      key={day}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '1rem',
                        backgroundColor: isSelected ? 'var(--button-bg)' : 'var(--bg-color)',
                        color: isSelected ? 'white' : 'var(--text-color)',
                        borderRadius: '8px',
                        border: '3px solid ' + (isSelected ? 'var(--button-bg)' : 'var(--border-color)'),
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        userSelect: 'none',
                        fontWeight: isSelected ? 600 : 500
                      }}
                      onMouseEnter={(e) => !isSelected && (e.currentTarget.style.borderColor = 'var(--button-bg)', e.currentTarget.style.transform = 'translateY(-2px)')}
                      onMouseLeave={(e) => !isSelected && (e.currentTarget.style.borderColor = 'var(--border-color)', e.currentTarget.style.transform = 'translateY(0)')}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setWeekDays([...weekDays, dayLower]);
                          } else {
                            setWeekDays(weekDays.filter(d => d !== dayLower));
                          }
                        }}
                        style={{ position: 'absolute', opacity: 0 }}
                      />
                      <span style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>{dayEmojis[index]}</span>
                      <span style={{ fontSize: '0.95rem' }}>{day.substring(0, 3)}</span>
                    </label>
                  );
                })}
              </div>
              
              <div style={{ 
                marginTop: '1rem', 
                padding: '0.75rem 1rem', 
                backgroundColor: weekDays.length > 0 ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)', 
                borderRadius: '6px',
                border: '1px solid ' + (weekDays.length > 0 ? 'rgba(40, 167, 69, 0.3)' : 'rgba(220, 53, 69, 0.3)')
              }}>
                <p style={{ fontSize: '0.9rem', color: weekDays.length > 0 ? '#28a745' : '#dc3545', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.2rem' }}>{weekDays.length > 0 ? '✓' : '⚠️'}</span>
                  {weekDays.length > 0 
                    ? `Schedule will run every ${weekDays.map(d => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ')}`
                    : 'Please select at least one day of the week'}
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Recurrence Pattern - Monthly */}
          {scheduleForm.type === 'monthly' && (
            <div style={{ 
              marginBottom: '2rem', 
              padding: '1.5rem', 
              backgroundColor: 'var(--card-bg)', 
              borderRadius: '12px', 
              border: '2px solid var(--border-color)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '50%', 
                  backgroundColor: 'var(--button-bg)',
                  color: 'white',
                  fontWeight: 700,
                  fontSize: '1rem'
                }}>3</div>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}><Calendar size={20} style={{marginRight: '0.5rem', verticalAlign: 'middle'}} /> Monthly Recurrence</h3>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <label style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Select Days of the Month <span style={{ color: '#dc3545' }}>*</span>
                </label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => setMonthDays(Array.from({length: 31}, (_, i) => i + 1))}
                    style={{
                      padding: '0.5rem 1rem',
                      fontSize: '0.85rem',
                      backgroundColor: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: 600,
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#218838'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#28a745'}
                  >
                    ✓ Select All
                  </button>
                  <button
                    type="button"
                    onClick={() => setMonthDays([])}
                    style={{
                      padding: '0.5rem 1rem',
                      fontSize: '0.85rem',
                      backgroundColor: '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: 600,
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#5a6268'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#6c757d'}
                  >
                    ✗ Clear All
                  </button>
                </div>
              </div>
              
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(7, 1fr)', 
                gap: '0.5rem',
                padding: '1rem',
                backgroundColor: 'var(--bg-color)',
                borderRadius: '8px',
                border: '2px solid var(--border-color)'
              }}>
                {Array.from({length: 31}, (_, i) => i + 1).map((day) => {
                  const isSelected = monthDays.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => {
                        if (isSelected) {
                          setMonthDays(monthDays.filter(d => d !== day));
                        } else {
                          setMonthDays([...monthDays, day].sort((a, b) => a - b));
                        }
                      }}
                      style={{
                        padding: '0.75rem',
                        backgroundColor: isSelected ? 'var(--button-bg)' : 'var(--card-bg)',
                        color: isSelected ? 'white' : 'var(--text-color)',
                        border: '2px solid ' + (isSelected ? 'var(--button-bg)' : 'var(--border-color)'),
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '1rem',
                        fontWeight: isSelected ? 700 : 500,
                        transition: 'all 0.2s',
                        minHeight: '45px'
                      }}
                      onMouseEnter={(e) => !isSelected && (e.currentTarget.style.borderColor = 'var(--button-bg)', e.currentTarget.style.transform = 'scale(1.05)')}
                      onMouseLeave={(e) => !isSelected && (e.currentTarget.style.borderColor = 'var(--border-color)', e.currentTarget.style.transform = 'scale(1)')}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>
              
              <div style={{ 
                marginTop: '1rem', 
                padding: '0.75rem 1rem', 
                backgroundColor: monthDays.length > 0 ? 'rgba(40, 167, 69, 0.1)' : 'rgba(220, 53, 69, 0.1)', 
                borderRadius: '6px',
                border: '1px solid ' + (monthDays.length > 0 ? 'rgba(40, 167, 69, 0.3)' : 'rgba(220, 53, 69, 0.3)')
              }}>
                <p style={{ fontSize: '0.9rem', color: monthDays.length > 0 ? '#28a745' : '#dc3545', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.2rem' }}>{monthDays.length > 0 ? '✓' : '⚠️'}</span>
                  {monthDays.length > 0 
                    ? `Schedule will run on day${monthDays.length > 1 ? 's' : ''} ${monthDays.join(', ')} of each month`
                    : 'Please select at least one day of the month'}
                </p>
              </div>
            </div>
          )}

          {/* Step 4: Content Configuration */}
          <div style={{ 
            marginBottom: '2rem', 
            padding: '1.5rem', 
            backgroundColor: 'var(--card-bg)', 
            borderRadius: '12px', 
            border: '2px solid var(--border-color)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '32px', 
                height: '32px', 
                borderRadius: '50%', 
                backgroundColor: 'var(--button-bg)',
                color: 'white',
                fontWeight: 700,
                fontSize: '1rem'
              }}>4</div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {scheduleMode === 'simple' ? <><Folder size={20} /> Content Selection</> : <><Film size={20} /> Sequence Builder</>}
              </h3>
            </div>
            
            {/* Simple Mode: Category Selection */}
            {scheduleMode === 'simple' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                      Category <span style={{ color: '#dc3545' }}>*</span>
                    </label>
                    <select
                      className="nx-select"
                      value={scheduleForm.category_id}
                      onChange={(e) => setScheduleForm({...scheduleForm, category_id: e.target.value})}
                      required
                      style={{ 
                        padding: '0.75rem', 
                        fontSize: '1rem',
                        border: '2px solid var(--border-color)',
                        borderRadius: '6px',
                        width: '100%'
                      }}
                    >
                      <option value="">Select a Category</option>
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                      Holiday Preset <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>(Optional)</span>
                    </label>
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
                      style={{ 
                        padding: '0.75rem', 
                        fontSize: '1rem',
                        border: '2px solid var(--border-color)',
                        borderRadius: '6px',
                        width: '100%'
                      }}
                    >
                      <option value="">🎉 Choose Holiday Preset</option>
                      {holidayPresets.map(preset => (
                        <option key={preset.id} value={preset.id}>
                          {preset.name} ({preset.start_month ? `${preset.start_month}/${preset.start_day} - ${preset.end_month}/${preset.end_day}` : `${preset.month}/${preset.day}`})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                
                <div>
                  <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                    Playback Mode <span style={{ color: '#dc3545' }}>*</span>
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <label style={{
                      display: 'flex',
                      flexDirection: 'column',
                      cursor: 'pointer',
                      padding: '1rem',
                      backgroundColor: (scheduleForm.shuffle || (!scheduleForm.shuffle && !scheduleForm.playlist)) ? 'var(--button-bg)' : 'var(--bg-color)',
                      color: (scheduleForm.shuffle || (!scheduleForm.shuffle && !scheduleForm.playlist)) ? 'white' : 'var(--text-color)',
                      borderRadius: '8px',
                      border: '3px solid ' + ((scheduleForm.shuffle || (!scheduleForm.shuffle && !scheduleForm.playlist)) ? 'var(--button-bg)' : 'var(--border-color)'),
                      transition: 'all 0.2s'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <input
                          type="radio"
                          name="playback"
                          checked={scheduleForm.shuffle || (!scheduleForm.shuffle && !scheduleForm.playlist)}
                          onChange={() => setScheduleForm({
                            ...scheduleForm,
                            shuffle: true,
                            playlist: false
                          })}
                          style={{ marginRight: '0.75rem', width: '18px', height: '18px' }}
                        />
                        <span style={{ fontSize: '1.5rem', marginRight: '0.5rem' }}><Shuffle size={24} /></span>
                        <span style={{ fontSize: '1.05rem', fontWeight: 600 }}>Random</span>
                      </div>
                      <p style={{ margin: '0 0 0 2.25rem', fontSize: '0.85rem', opacity: 0.9 }}>
                        Shuffle prerolls in random order
                      </p>
                    </label>
                    
                    <label style={{
                      display: 'flex',
                      flexDirection: 'column',
                      cursor: 'pointer',
                      padding: '1rem',
                      backgroundColor: scheduleForm.playlist ? 'var(--button-bg)' : 'var(--bg-color)',
                      color: scheduleForm.playlist ? 'white' : 'var(--text-color)',
                      borderRadius: '8px',
                      border: '3px solid ' + (scheduleForm.playlist ? 'var(--button-bg)' : 'var(--border-color)'),
                      transition: 'all 0.2s'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <input
                          type="radio"
                          name="playback"
                          checked={scheduleForm.playlist}
                          onChange={() => setScheduleForm({
                            ...scheduleForm,
                            shuffle: false,
                            playlist: true
                          })}
                          style={{ marginRight: '0.75rem', width: '18px', height: '18px' }}
                        />
                        <span style={{ fontSize: '1.5rem', marginRight: '0.5rem' }}><Edit size={24} /></span>
                        <span style={{ fontSize: '1.05rem', fontWeight: 600 }}>Sequential</span>
                      </div>
                      <p style={{ margin: '0 0 0 2.25rem', fontSize: '0.85rem', opacity: 0.9 }}>
                        Play prerolls in order
                      </p>
                    </label>
                  </div>
                </div>
              </>
            )}

            {/* Advanced Mode: Load Saved Sequence or Build New */}
            {scheduleMode === 'advanced' && (
              <>
                {/* Saved Sequences Dropdown */}
                <div style={{ 
                  marginBottom: '1.5rem',
                  padding: '1.25rem',
                  backgroundColor: 'var(--hover-bg)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)'
                }}>
                  <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
                    <BookOpen size={14} style={{marginRight: '0.35rem'}} /> Load Saved Sequence (Optional)
                  </label>
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <select
                      className="nx-select"
                      value=""
                      onChange={(e) => {
                        if (e.target.value) {
                          const selectedSeq = savedSequences.find(s => s.id === parseInt(e.target.value));
                          if (selectedSeq) {
                            setSequenceBlocks(selectedSeq.blocks || []);
                            showAlert(`Loaded sequence: ${selectedSeq.name}`, 'success');
                            e.target.value = ''; // Reset dropdown
                          }
                        }
                      }}
                      style={{ 
                        flex: 1,
                        padding: '0.75rem', 
                        fontSize: '0.95rem',
                        border: '2px solid var(--border-color)',
                        borderRadius: '6px'
                      }}
                    >
                      <option value="">-- Select a saved sequence --</option>
                      {savedSequences.map(seq => (
                        <option key={seq.id} value={seq.id}>
                          {seq.name} ({seq.blocks?.length || 0} blocks)
                        </option>
                      ))}
                    </select>
                    {sequenceBlocks.length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          setSequenceBlocks([]);
                          showAlert('Sequence cleared', 'info');
                        }}
                        className="button"
                        style={{ 
                          padding: '0.75rem 1.25rem',
                          backgroundColor: '#dc3545',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        <Trash size={16} style={{ marginRight: '6px' }} /> Clear Sequence
                      </button>
                    )}
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>
                    {savedSequences.length === 0 ? (
                      <>No saved sequences. Go to <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('schedules/builder'); }} style={{ color: 'var(--button-bg)', textDecoration: 'underline' }}>Sequence Builder</a> to create one.</>
                    ) : (
                      `Select a sequence from your library or build a custom one below. Current: ${sequenceBlocks.length} blocks`
                    )}
                  </p>
                </div>

                {/* Sequence Builder */}
                <SequenceBuilder
                  blocks={sequenceBlocks}
                  categories={categories}
                  prerolls={prerolls}
                  scheduleId={null}
                  apiUrl={apiUrl}
                  onBlocksChange={setSequenceBlocks}
                  onSave={(name, description) => {
                    console.log('Sequence info:', name, description);
                  }}
                  onCancel={() => {
                    console.log('Sequence builder cancelled');
                  }}
                />
              </>
            )}
          </div>
          {/* Step 5: Optional Settings */}
          <div style={{ 
            marginBottom: '2rem', 
            padding: '1.5rem', 
            backgroundColor: 'var(--card-bg)', 
            borderRadius: '12px', 
            border: '2px solid var(--border-color)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                width: '32px', 
                height: '32px', 
                borderRadius: '50%', 
                backgroundColor: '#6c757d',
                color: 'white',
                fontWeight: 700,
                fontSize: '1rem'
              }}>5</div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Settings size={20} /> Optional Settings</h3>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Fallback Category
                </label>
                <select
                  className="nx-select"
                  value={scheduleForm.fallback_category_id || ''}
                  onChange={(e) => setScheduleForm({...scheduleForm, fallback_category_id: e.target.value})}
                  style={{ 
                    padding: '0.75rem', 
                    fontSize: '1rem',
                    border: '2px solid var(--border-color)',
                    borderRadius: '6px',
                    width: '100%'
                  }}
                >
                  <option value="">No Fallback</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                  Used when no schedule is active
                </p>
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  Calendar Color
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <input
                    type="color"
                    value={scheduleForm.color || '#3b82f6'}
                    onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                    style={{ 
                      width: '60px', 
                      height: '48px', 
                      border: '2px solid var(--border-color)', 
                      borderRadius: '6px', 
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                  />
                  <input
                    className="nx-input"
                    type="text"
                    placeholder="#3b82f6"
                    value={scheduleForm.color || ''}
                    onChange={(e) => setScheduleForm({...scheduleForm, color: e.target.value})}
                    style={{ 
                      padding: '0.75rem', 
                      flex: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.95rem',
                      border: '2px solid var(--border-color)',
                      borderRadius: '6px'
                    }}
                  />
                  {scheduleForm.color && (
                    <button
                      type="button"
                      className="button"
                      onClick={() => setScheduleForm({...scheduleForm, color: ''})}
                      style={{ 
                        padding: '0.75rem 1rem', 
                        backgroundColor: '#dc3545',
                        borderRadius: '6px',
                        fontWeight: 600
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0 0' }}>
                  Custom color for calendar display
                </p>
              </div>
            </div>
          </div>
          
          {/* Submit Button */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'flex-end', 
            gap: '1rem',
            paddingTop: '1rem',
            borderTop: '2px solid var(--border-color)'
          }}>
            <button 
              type="button" 
              className="button"
              onClick={() => {
                setScheduleForm({
                  name: '', type: 'monthly', start_date: '', end_date: '',
                  category_id: '', shuffle: true, playlist: false, fallback_category_id: ''
                });
                setScheduleMode('simple');
                setSequenceBlocks([]);
                setWeekDays([]);
                setMonthDays([]);
                setTimeRange({ start: '', end: '' });
              }}
              style={{ 
                padding: '1rem 2rem', 
                backgroundColor: '#6c757d',
                fontSize: '1.05rem',
                fontWeight: 600,
                borderRadius: '8px',
                minWidth: '150px'
              }}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="button"
              style={{ 
                padding: '1rem 2rem', 
                backgroundColor: 'var(--button-bg)',
                fontSize: '1.05rem',
                fontWeight: 600,
                borderRadius: '8px',
                minWidth: '200px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {editingSchedule 
                  ? <><Save size={18} /> Update Schedule</> 
                  : scheduleMode === 'advanced' 
                    ? <><CheckCircle size={18} /> Create Custom Schedule</> 
                    : <><CheckCircle size={18} /> Create Schedule</>}
              </span>
            </button>
          </div>
          {/* edit handled via modal */}
        </form>
      </div>
    </div>
  );

  // Schedule List page (default view)
  const renderScheduleListPage = () => (
    <div>
      {/* Quick Start Guide - Show only when no schedules exist */}
      {schedules.length === 0 && (
        <div style={{
          marginBottom: '2rem',
          padding: '2rem',
          backgroundColor: 'var(--card-bg)',
          borderRadius: '12px',
          border: '2px solid var(--button-bg)',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <span style={{ fontSize: '3rem', marginBottom: '0.5rem', display: 'flex', justifyContent: 'center' }}><Film size={48} /></span>
            <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.5rem', fontWeight: 700 }}>
              Welcome to NeXroll Scheduling!
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', margin: 0 }}>
              Get started by creating your first schedule in just a few clicks
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{
              padding: '1.5rem',
              backgroundColor: 'var(--bg-color)',
              borderRadius: '8px',
              border: '1px solid var(--border-color)'
            }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}><Folder size={32} /></div>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', fontWeight: 600 }}>
                Simple Scheduling
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: '1.5' }}>
                Perfect for beginners. Select a category and set when it should play. NeXroll handles the rest!
              </p>
              <button
                onClick={() => {
                  setScheduleMode('simple');
                  setActiveTab('schedules/create');
                }}
                className="button"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  fontSize: '0.95rem',
                  backgroundColor: '#28a745',
                  borderColor: '#28a745'
                }}
              >
                Create Simple Schedule →
              </button>
            </div>

            <div style={{
              padding: '1.5rem',
              backgroundColor: 'var(--bg-color)',
              borderRadius: '8px',
              border: '1px solid var(--border-color)'
            }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}><Palette size={32} /></div>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', fontWeight: 600 }}>
                Custom Sequences
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: '1.5' }}>
                For advanced users. Build custom playlists mixing categories and specific prerolls in any order.
              </p>
              <button
                onClick={() => {
                  setScheduleMode('advanced');
                  setActiveTab('schedules/create');
                }}
                className="button"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  fontSize: '0.95rem'
                }}
              >
                Build Custom Sequence →
              </button>
            </div>
          </div>

          <div style={{
            padding: '1rem',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderRadius: '8px',
            border: '1px solid rgba(59, 130, 246, 0.3)'
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
              <span style={{ fontSize: '1.5rem' }}><Lightbulb size={24} /></span>
              <div>
                <strong style={{ fontSize: '0.95rem' }}>Pro Tip:</strong>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  Start with a simple schedule to get familiar, then explore the Sequence Builder for advanced customization. 
                  You can always switch between modes later!
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '1.5rem',
          paddingBottom: '1rem',
          borderBottom: '2px solid var(--border-color)'
        }}>
          <h2 style={{ margin: 0 }}>Active Schedules</h2>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {/* View Mode Toggle */}
            <div style={{ 
              display: 'flex', 
              gap: '0.25rem', 
              backgroundColor: 'var(--bg-color)', 
              padding: '0.25rem', 
              borderRadius: '0.375rem',
              border: '1px solid var(--border-color)'
            }}>
              <button
                onClick={() => setScheduleViewMode('compact')}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: scheduleViewMode === 'compact' ? 'var(--button-bg)' : 'transparent',
                  color: scheduleViewMode === 'compact' ? 'white' : 'var(--text-color)',
                  border: 'none',
                  borderRadius: '0.25rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
              >
                <FileText size={14} /> Compact
              </button>
              <button
                onClick={() => setScheduleViewMode('detailed')}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: scheduleViewMode === 'detailed' ? 'var(--button-bg)' : 'transparent',
                  color: scheduleViewMode === 'detailed' ? 'white' : 'var(--text-color)',
                  border: 'none',
                  borderRadius: '0.25rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
              >
                <Edit size={14} /> Detailed
              </button>
            </div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              {schedules.length} schedule{schedules.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Search and Filter */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '2fr 1fr', 
          gap: '1rem', 
          marginBottom: '1.5rem'
        }}>
          <div>
            <input
              type="text"
              placeholder="🔍 Search schedules by name..."
              value={scheduleSearchQuery}
              onChange={(e) => {
                setScheduleSearchQuery(e.target.value);
                setScheduleCurrentPage(1); // Reset to first page on search
              }}
              style={{
                width: '70%',
                padding: '0.75rem 1rem',
                fontSize: '0.95rem',
                border: '2px solid var(--border-color)',
                borderRadius: '0.5rem',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-color)'
              }}
            />
          </div>
          <div>
            <select
              value={scheduleFilterType}
              onChange={(e) => {
                setScheduleFilterType(e.target.value);
                setScheduleCurrentPage(1); // Reset to first page on filter change
              }}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                fontSize: '0.95rem',
                border: '2px solid var(--border-color)',
                borderRadius: '0.5rem',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-color)',
                cursor: 'pointer'
              }}
            >
              <option value="all">All Types</option>
              <option value="daily">📅 Daily Only</option>
              <option value="weekly">📆 Weekly Only</option>
              <option value="monthly">🗓️ Monthly Only</option>
              <option value="yearly">📋 Yearly Only</option>
              <option value="holiday">🎉 Holiday Only</option>
              <option value="custom">⚙️ Custom Only</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gap: '1rem' }}>
          {(() => {
            // Filter schedules based on search query and filter type
            let filteredSchedules = schedules.filter(schedule => {
              const matchesSearch = schedule.name.toLowerCase().includes(scheduleSearchQuery.toLowerCase());
              const matchesType = scheduleFilterType === 'all' || schedule.type === scheduleFilterType;
              return matchesSearch && matchesType;
            });

            // Calculate pagination
            const totalPages = Math.ceil(filteredSchedules.length / schedulesPerPage);
            const startIndex = (scheduleCurrentPage - 1) * schedulesPerPage;
            const endIndex = startIndex + schedulesPerPage;
            const paginatedSchedules = filteredSchedules.slice(startIndex, endIndex);

            // Show message if no schedules found
            if (filteredSchedules.length === 0) {
              return (
                <div style={{ 
                  textAlign: 'center', 
                  padding: '3rem', 
                  color: 'var(--text-secondary)',
                  backgroundColor: 'var(--bg-color)',
                  borderRadius: '0.5rem',
                  border: '2px dashed var(--border-color)'
                }}>
                  <div style={{ fontSize: '3rem', marginBottom: '1rem' }}><Inbox size={48} /></div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                    No schedules found
                  </div>
                  <div style={{ fontSize: '0.9rem' }}>
                    {scheduleSearchQuery ? `Try adjusting your search or filter` : `Create your first schedule above`}
                  </div>
                </div>
              );
            }

            return (
              <>
                {paginatedSchedules.map(schedule => {
            // Check if schedule is currently active using server-determined IDs
            // This ensures accuracy since the server knows exactly which schedules are active
            const isCurrentlyActive = activeScheduleIds.includes(schedule.id);
            
            const hasSequence = schedule.sequence && schedule.sequence.trim();
            const scheduleMode = hasSequence ? 'sequence' : 'simple';
            
            // Parse sequence to count blocks
            let sequenceBlockCount = 0;
            if (hasSequence) {
              try {
                const parsed = JSON.parse(schedule.sequence);
                sequenceBlockCount = Array.isArray(parsed) ? parsed.length : 0;
              } catch (e) {
                sequenceBlockCount = 0;
              }
            }

            // Parse recurrence pattern for display
            let recurrenceText = '';
            if (schedule.recurrence_pattern) {
              try {
                const pattern = JSON.parse(schedule.recurrence_pattern);
                if (pattern.timeRange) {
                  const formatTime = (time) => {
                    if (!time) return '';
                    const [hours, minutes] = time.split(':');
                    const hour = parseInt(hours);
                    const ampm = hour >= 12 ? 'PM' : 'AM';
                    const displayHour = hour % 12 || 12;
                    return `${displayHour}:${minutes} ${ampm}`;
                  };
                  if (pattern.timeRange.start && pattern.timeRange.end) {
                    recurrenceText = `Time: ${formatTime(pattern.timeRange.start)} - ${formatTime(pattern.timeRange.end)}`;
                  } else if (pattern.timeRange.start) {
                    recurrenceText = `Time: ${formatTime(pattern.timeRange.start)}`;
                  }
                }
                if (pattern.weekDays && pattern.weekDays.length > 0) {
                  const days = pattern.weekDays.map(d => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ');
                  recurrenceText = `Repeats: ${days}`;
                }
                if (pattern.monthDays && pattern.monthDays.length > 0) {
                  const days = pattern.monthDays.join(', ');
                  recurrenceText = `Days: ${days}`;
                }
              } catch (e) {
                recurrenceText = '';
              }
            }

            // Render Compact or Detailed View
            if (scheduleViewMode === 'compact') {
              return (
                <div 
                  key={schedule.id} 
                  style={{ 
                    border: isCurrentlyActive ? '2px solid #4CAF50' : '1px solid var(--border-color)', 
                    padding: '0.75rem 1rem', 
                    borderRadius: '0.375rem', 
                    backgroundColor: isCurrentlyActive ? 'rgba(76, 175, 80, 0.1)' : 'var(--card-bg)',
                    boxShadow: isCurrentlyActive ? '0 2px 8px rgba(76, 175, 80, 0.15)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-color)' }}>
                          {schedule.name}
                        </h4>
                        {isCurrentlyActive && (
                          <span style={{
                            backgroundColor: '#4CAF50',
                            color: 'white',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '0.75rem',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            textTransform: 'uppercase'
                          }}>
                            ● Active
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', fontSize: '0.75rem' }}>
                        <span style={{
                          backgroundColor: scheduleMode === 'sequence' ? '#3b82f6' : '#6366f1',
                          color: 'white',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '0.25rem',
                          fontWeight: 600
                        }}>
                          {scheduleMode === 'sequence' ? <><Film size={14} style={{marginRight: '4px'}} /> {sequenceBlockCount} blocks</> : <><Folder size={14} style={{marginRight: '4px'}} /> Simple</>}
                        </span>
                        <span style={{
                          color: 'var(--text-secondary)',
                          fontWeight: 500,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}>
                          <Calendar size={14} /> {schedule.type.charAt(0).toUpperCase() + schedule.type.slice(1)}
                        </span>
                        {recurrenceText && (
                          <span style={{ color: '#3b82f6', fontWeight: 500 }}>{recurrenceText}</span>
                        )}
                        {schedule.blend_enabled && (
                          <span style={{
                            backgroundColor: '#a855f7',
                            color: 'white',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '0.25rem',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem'
                          }}>
                            <Shuffle size={12} /> Blend
                          </span>
                        )}
                        {schedule.exclusive && (
                          <span style={{
                            backgroundColor: '#14B8A6',
                            color: 'white',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '0.25rem',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem'
                          }}>
                            <Lock size={12} /> Exclusive
                          </span>
                        )}
                        {(schedule.priority ?? 5) !== 5 && (
                          <span style={{
                            backgroundColor: (schedule.priority ?? 5) >= 8 ? '#ef4444' : (schedule.priority ?? 5) >= 5 ? '#14B8A6' : '#6b7280',
                            color: 'white',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '0.25rem',
                            fontWeight: 600,
                            fontSize: '0.75rem'
                          }}>
                            P{schedule.priority ?? 5}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <label 
                      className="nx-rockerswitch" 
                      title={schedule.is_active ? 'Disable schedule' : 'Enable schedule'}
                      style={{ margin: 0 }}
                      key={`toggle-compact-${schedule.id}-${schedule.is_active}`}
                    >
                      <input
                        type="checkbox"
                        checked={schedule.is_active}
                        onChange={() => handleToggleSchedule(schedule, 'compact view')}
                        aria-label={schedule.is_active ? 'Disable schedule' : 'Enable schedule'}
                      />
                      <span className="nx-rockerswitch-slider"></span>
                    </label>
                    <button
                      onClick={() => handleEditSchedule(schedule)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        backgroundColor: 'var(--button-bg)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      <Edit size={14} style={{marginRight: '6px'}} /> Edit
                    </button>
                    <button
                      onClick={() => handleDeleteSchedule(schedule.id)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        backgroundColor: '#dc3545',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                    >
                      <Trash size={14} />
                    </button>
                  </div>
                </div>
              );
            }

            // Detailed View
            return (
              <div 
                key={schedule.id} 
                style={{ 
                  border: isCurrentlyActive ? '2px solid #4CAF50' : '1px solid var(--border-color)', 
                  padding: '1.25rem', 
                  borderRadius: '0.5rem', 
                  backgroundColor: isCurrentlyActive ? 'rgba(76, 175, 80, 0.1)' : 'var(--card-bg)',
                  boxShadow: isCurrentlyActive ? '0 4px 12px rgba(76, 175, 80, 0.2)' : '0 2px 4px rgba(0,0,0,0.1)',
                  position: 'relative',
                  transition: 'all 0.2s ease'
                }}
              >
                {/* Status Badge - Top Right */}
                <div style={{ position: 'absolute', top: '1rem', right: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  {isCurrentlyActive && (
                    <span style={{
                      backgroundColor: '#4CAF50',
                      color: 'white',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '1rem',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                    }}>
                      ● Active Now
                    </span>
                  )}
                  {!schedule.is_active && (
                    <span style={{
                      backgroundColor: '#999',
                      color: 'white',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '1rem',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      Paused
                    </span>
                  )}
                </div>

                {/* Title & Badges */}
                <div style={{ marginBottom: '1rem', marginRight: '140px' }}>
                  <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '1.3rem', fontWeight: 600, color: 'var(--text-color)' }}>
                    {schedule.name}
                  </h3>
                  
                  {/* Badge Row */}
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    {/* Mode Badge */}
                    <span style={{
                      backgroundColor: scheduleMode === 'sequence' ? '#3b82f6' : '#6366f1',
                      color: 'white',
                      padding: '0.25rem 0.75rem',
                      borderRadius: '0.25rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem'
                    }}>
                      {scheduleMode === 'sequence' ? <><Film size={14} style={{marginRight: '4px'}} /> Sequence ({sequenceBlockCount} blocks)</> : <><Folder size={14} style={{marginRight: '4px'}} /> Simple</>}
                    </span>

                    {/* Type Badge */}
                    <span style={{
                      backgroundColor: 'var(--card-bg)',
                      color: 'var(--text-color)',
                      padding: '0.25rem 0.75rem',
                      borderRadius: '0.25rem',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                      border: '1px solid var(--border-color)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem'
                    }}>
                      <Calendar size={14} /> {schedule.type.charAt(0).toUpperCase() + schedule.type.slice(1)}
                    </span>

                    {/* Category Badge - Only for Simple Mode */}
                    {scheduleMode === 'simple' && schedule.category && (
                      <span style={{
                        backgroundColor: schedule.color || schedule.category.color || '#6366f1',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500
                      }}>
                        {schedule.category.name}
                      </span>
                    )}

                    {/* Playback Mode Badge */}
                    {schedule.shuffle && (
                      <span style={{
                        backgroundColor: '#14B8A6',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500
                      }}>
                        <Shuffle size={14} style={{marginRight: '0.35rem'}} /> Random
                      </span>
                    )}
                    {schedule.playlist && (
                      <span style={{
                        backgroundColor: '#8b5cf6',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500
                      }}>
                        <ListOrdered size={14} style={{marginRight: '0.35rem'}} /> Sequential
                      </span>
                    )}

                    {/* Blend Mode Badge */}
                    {schedule.blend_enabled && (
                      <span style={{
                        backgroundColor: '#a855f7',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}>
                        <Shuffle size={14} /> Blend Mode
                      </span>
                    )}

                    {/* Exclusive Badge */}
                    {schedule.exclusive && (
                      <span style={{
                        backgroundColor: '#14B8A6',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}>
                        <Lock size={14} /> Exclusive
                      </span>
                    )}

                    {/* Priority Badge (only show if not default) */}
                    {(schedule.priority ?? 5) !== 5 && (
                      <span style={{
                        backgroundColor: (schedule.priority ?? 5) >= 8 ? '#ef4444' : (schedule.priority ?? 5) >= 5 ? '#14B8A6' : '#6b7280',
                        color: 'white',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.8rem',
                        fontWeight: 500
                      }}>
                        Priority {schedule.priority ?? 5}
                      </span>
                    )}
                  </div>
                </div>

                {/* Schedule Details */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                  gap: '0.75rem', 
                  marginBottom: '1rem',
                  fontSize: '0.9rem',
                  color: '#666'
                }}>
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-color)', marginBottom: '0.25rem' }}><CalendarDays size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Schedule</div>
                    <div>Start: {new Date(schedule.start_date).toLocaleDateString()} {new Date(schedule.start_date).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
                    {schedule.end_date && (
                      <div>End: {new Date(schedule.end_date).toLocaleDateString()} {new Date(schedule.end_date).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
                    )}
                    {recurrenceText && (
                      <div style={{ color: '#3b82f6', fontWeight: 500, marginTop: '0.25rem' }}>{recurrenceText}</div>
                    )}
                  </div>

                  {schedule.next_run && (
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-color)', marginBottom: '0.25rem' }}><Clock size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Next Run</div>
                      <div>{new Date(schedule.next_run).toLocaleDateString()} {new Date(schedule.next_run).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
                    </div>
                  )}

                  {schedule.last_run && (
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-color)', marginBottom: '0.25rem' }}><Check size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Last Run</div>
                      <div>{new Date(schedule.last_run).toLocaleDateString()} {new Date(schedule.last_run).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
                    </div>
                  )}

                  {schedule.fallback_category && (
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-color)', marginBottom: '0.25rem' }}><RefreshCw size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Fallback</div>
                      <div>{schedule.fallback_category.name}</div>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <label 
                      key={`toggle-detailed-${schedule.id}-${schedule.is_active}`}
                      className="nx-rockerswitch" 
                      title={schedule.is_active ? 'Disable schedule' : 'Enable schedule'}
                      style={{ margin: 0 }}
                    >
                      <input
                        type="checkbox"
                        checked={schedule.is_active}
                        onChange={() => handleToggleSchedule(schedule, 'detailed view')}
                        aria-label={schedule.is_active ? 'Disable schedule' : 'Enable schedule'}
                      />
                      <span className="nx-rockerswitch-slider"></span>
                    </label>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                      {schedule.is_active ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <button
                    onClick={() => handleEditSchedule(schedule)}
                    style={{
                      flex: 1,
                      padding: '0.6rem 1rem',
                      backgroundColor: 'var(--button-bg)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '0.25rem',
                      fontSize: '0.9rem',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.5rem'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Edit size={16} /> Edit Schedule
                  </button>
                  <button
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    style={{
                      padding: '0.6rem 1rem',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '0.25rem',
                      fontSize: '0.9rem',
                      fontWeight: 500,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Trash size={16} /> Delete
                  </button>
                </div>
              </div>
            );
          })}

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'center', 
                    alignItems: 'center', 
                    gap: '0.5rem',
                    marginTop: '2rem',
                    paddingTop: '1.5rem',
                    borderTop: '1px solid var(--border-color)'
                  }}>
                    <button
                      onClick={() => setScheduleCurrentPage(p => Math.max(1, p - 1))}
                      disabled={scheduleCurrentPage === 1}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: scheduleCurrentPage === 1 ? 'var(--bg-color)' : 'var(--button-bg)',
                        color: scheduleCurrentPage === 1 ? 'var(--text-secondary)' : 'white',
                        border: '1px solid var(--border-color)',
                        borderRadius: '0.375rem',
                        fontSize: '0.9rem',
                        fontWeight: 600,
                        cursor: scheduleCurrentPage === 1 ? 'not-allowed' : 'pointer',
                        opacity: scheduleCurrentPage === 1 ? 0.5 : 1
                      }}
                    >
                      ← Previous
                    </button>
                    
                    <div style={{ display: 'flex', gap: '0.25rem' }}>
                      {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                        <button
                          key={page}
                          onClick={() => setScheduleCurrentPage(page)}
                          style={{
                            padding: '0.5rem 0.75rem',
                            backgroundColor: scheduleCurrentPage === page ? 'var(--button-bg)' : 'var(--bg-color)',
                            color: scheduleCurrentPage === page ? 'white' : 'var(--text-color)',
                            border: '1px solid var(--border-color)',
                            borderRadius: '0.375rem',
                            fontSize: '0.9rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            minWidth: '40px'
                          }}
                        >
                          {page}
                        </button>
                      ))}
                    </div>
                    
                    <button
                      onClick={() => setScheduleCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={scheduleCurrentPage === totalPages}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: scheduleCurrentPage === totalPages ? 'var(--bg-color)' : 'var(--button-bg)',
                        color: scheduleCurrentPage === totalPages ? 'var(--text-secondary)' : 'white',
                        border: '1px solid var(--border-color)',
                        borderRadius: '0.375rem',
                        fontSize: '0.9rem',
                        fontWeight: 600,
                        cursor: scheduleCurrentPage === totalPages ? 'not-allowed' : 'pointer',
                        opacity: scheduleCurrentPage === totalPages ? 0.5 : 1
                      }}
                    >
                      Next →
                    </button>
                    
                    <div style={{ 
                      marginLeft: '1rem', 
                      fontSize: '0.9rem', 
                      color: 'var(--text-secondary)',
                      fontWeight: 500
                    }}>
                      Page {scheduleCurrentPage} of {totalPages} ({filteredSchedules.length} total)
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );

  // Main renderSchedules with routing logic
  const renderSchedules = () => {
    // Route based on activeTab
    if (activeTab === 'schedules/create') {
      return (
        <div>
          {renderCreateSchedulePage()}
        </div>
      );
    }

    if (activeTab === 'schedules/calendar') {
      return (
        <div>
          {renderCalendarPage()}
        </div>
      );
    }

    if (activeTab === 'schedules/builder') {
      return (
        <div>
          {renderSequenceBuilder()}
        </div>
      );
    }

    if (activeTab === 'schedules/library') {
      return (
        <div>
          {renderSequenceLibrary()}
        </div>
      );
    }

    // Default: Schedule List
    return (
      <div>
        {renderScheduleListPage()}
      </div>
    );
  };

  const [newCategory, setNewCategory] = useState({ name: '', description: '' });

  const handleCreateCategory = async (e) => {
    e.preventDefault();

    const name = (newCategory.name || '').trim();
    const description = (newCategory.description || '').trim();
    if (!name) {
      alert('Category name is required');
      return;
    }

    try {
      const res = await fetch(apiUrl('categories'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
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
                              <Trash size={14} style={{marginRight: '0.35rem'}} /> Remove
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
                      <Plus size={14} style={{marginRight: '0.35rem'}} /> Add to Category
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
        
        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          <button 
            type="button"
            onClick={() => setShowCreateCategoryModal(true)} 
            className="button" 
            style={{ 
              backgroundColor: '#28a745', 
              borderColor: '#28a745',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>+</span>
            Create Category
          </button>
          <button 
            type="button"
            onClick={handleInitHolidays} 
            className="button" 
            style={{ 
              backgroundColor: '#dc3545', 
              borderColor: '#dc3545',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <TreePine size={14} style={{marginRight: '0.35rem'}} /> Load Holiday Categories
          </button>
          <button 
            type="button"
            onClick={handleRefreshHolidayDates} 
            className="button" 
            style={{ 
              backgroundColor: '#17a2b8', 
              borderColor: '#17a2b8',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
            title="Update dates for variable holidays (Thanksgiving, Easter, etc.)"
          >
            <RefreshCw size={14} style={{marginRight: '0.35rem'}} /> Refresh Holiday Dates
          </button>
          <button 
            type="button"
            onClick={() => setBulkActionMode(!bulkActionMode)} 
            className="button" 
            style={{ 
              backgroundColor: bulkActionMode ? '#ffc107' : '#6c757d', 
              borderColor: bulkActionMode ? '#ffc107' : '#6c757d',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            {bulkActionMode ? '✓' : '☑'} {bulkActionMode ? 'Exit' : 'Bulk Select'}
          </button>
          {bulkActionMode && selectedCategoryIds.length > 0 && (
            <>
              <button 
                type="button"
                onClick={handleBulkApplyToPlex} 
                className="button" 
                style={{ 
                  backgroundColor: '#007bff', 
                  borderColor: '#007bff',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <Upload size={14} style={{marginRight: '0.35rem'}} /> Apply Selected ({selectedCategoryIds.length})
              </button>
              <button 
                type="button"
                onClick={handleBulkDelete} 
                className="button" 
                style={{ 
                  backgroundColor: '#dc3545', 
                  borderColor: '#dc3545',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                <Trash size={14} style={{marginRight: '0.35rem'}} /> Delete Selected ({selectedCategoryIds.length})
              </button>
            </>
          )}
        </div>
        
        {/* Search, Filter and View Controls */}
        <div style={{ 
          display: 'flex', 
          gap: '1rem', 
          marginBottom: '1.5rem', 
          alignItems: 'center',
          backgroundColor: 'var(--card-bg)',
          padding: '1rem',
          borderRadius: '0.5rem',
          border: '1px solid var(--border-color)'
        }}>
          {/* Search Bar - 65% width */}
          <input
            type="text"
            placeholder="🔍 Search categories by name or description..."
            value={categorySearchQuery}
            onChange={(e) => setCategorySearchQuery(e.target.value)}
            style={{
              width: '65%',
              padding: '0.75rem 1rem',
              fontSize: '0.95rem',
              border: '2px solid var(--border-color)',
              borderRadius: '0.5rem',
              backgroundColor: 'var(--bg-color)',
              color: 'var(--text-color)',
              boxSizing: 'border-box'
            }}
          />

          {/* Filter Dropdown - 20% width */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            style={{
              width: '20%',
              padding: '0.75rem',
              fontSize: '0.95rem',
              border: '2px solid var(--border-color)',
              borderRadius: '0.5rem',
              backgroundColor: 'var(--bg-color)',
              color: 'var(--text-color)',
              cursor: 'pointer',
              boxSizing: 'border-box'
            }}
          >
            <option value="all">All Categories</option>
            <option value="active">Active Only</option>
            <option value="hasPrerolls">Has Prerolls</option>
            <option value="empty">Empty</option>
          </select>

          {/* View Toggle */}
          <div className="view-toggle" style={{ marginLeft: 'auto' }}>
              <button
                type="button"
                className={`view-btn ${categoryView === 'grid' ? 'active' : ''}`}
                onClick={() => setCategoryView('grid')}
                title="Grid view"
              >
                <span className="view-icon">⊞</span>
                Grid
              </button>
              <button
                type="button"
                className={`view-btn ${categoryView === 'list' ? 'active' : ''}`}
                onClick={() => setCategoryView('list')}
                title="List view"
              >
                <span className="view-icon">☰</span>
                List
              </button>
            </div>
        </div>
        
        {/* Bulk Selection Info */}
        {bulkActionMode && (
          <div style={{
            backgroundColor: '#fff3cd',
            border: '1px solid #ffc107',
            borderRadius: '0.5rem',
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            color: '#856404',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <span>
                          <Lightbulb size={16} style={{marginRight: '0.35rem', verticalAlign: 'middle', color: '#14B8A6'}} /> <strong>Bulk Selection Mode:</strong> Click categories to select them, then use the action buttons above.
              {selectedCategoryIds.length > 0 && ` (${selectedCategoryIds.length} selected)`}
            </span>
            {getFilteredCategories().length > 0 && (
              <button
                type="button"
                onClick={toggleSelectAll}
                className="button"
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  backgroundColor: '#6c757d',
                  borderColor: '#6c757d'
                }}
              >
                {selectedCategoryIds.length === getFilteredCategories().length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>
        )}
        
        {/* Grid View */}
        <div style={{ display: categoryView === 'grid' ? 'grid' : 'none', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
          {(() => {
            const filtered = getFilteredCategories();
            
            if (filtered.length === 0) {
              return (
                <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-secondary)' }}>
                  {categorySearchQuery ? (
                    <>
                      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}><Search size={48} /></div>
                      <div style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: 'var(--text-color)' }}>
                        No categories found matching "{categorySearchQuery}"
                      </div>
                      <div style={{ fontSize: '0.9rem' }}>
                        Try adjusting your search or create a new category below
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}><Folder size={48} /></div>
                      <div style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: 'var(--text-color)' }}>
                        No categories yet
                      </div>
                      <div style={{ fontSize: '0.9rem' }}>
                        Create your first category below to organize your prerolls
                      </div>
                    </>
                  )}
                </div>
              );
            }
            
            return filtered.map(category => {
            // Calculate statistics for this category
            const stats = getCategoryStats(category);
            const isSelected = selectedCategoryIds.includes(category.id);
            
            return (
            <div 
              key={category.id} 
              onClick={() => bulkActionMode && toggleSelectCategory(category.id)}
              style={{ 
                border: `2px solid ${isSelected && bulkActionMode ? '#ffc107' : 'var(--border-color)'}`, 
                padding: '1.25rem', 
                borderRadius: '8px', 
                backgroundColor: isSelected && bulkActionMode ? 'rgba(255, 193, 7, 0.1)' : 'var(--card-bg)',
                boxShadow: isSelected && bulkActionMode ? '0 4px 12px rgba(255, 193, 7, 0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
                transition: 'all 0.2s',
                cursor: bulkActionMode ? 'pointer' : 'default',
                position: 'relative'
              }}
              onMouseEnter={(e) => {
                if (!bulkActionMode) {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                }
              }}
              onMouseLeave={(e) => {
                if (!bulkActionMode) {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                }
              }}
            >
              {/* Bulk Selection Checkbox */}
              {bulkActionMode && (
                <div style={{
                  position: 'absolute',
                  top: '0.5rem',
                  left: '0.5rem',
                  width: '1.5rem',
                  height: '1.5rem',
                  borderRadius: '4px',
                  backgroundColor: isSelected ? '#ffc107' : 'var(--bg-color)',
                  border: '2px solid ' + (isSelected ? '#ffc107' : 'var(--border-color)'),
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                  color: isSelected ? 'white' : 'transparent'
                }}>
                  ✓
                </div>
              )}
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: 'var(--text-color)' }}>{category.name}</h3>
                  
                  {/* Statistics Badges */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.5rem' }}>
                    <div style={{ 
                      display: 'inline-block',
                      fontSize: '0.75rem', 
                      padding: '0.2rem 0.5rem',
                      borderRadius: '12px',
                      backgroundColor: stats.totalPrerolls > 0 ? '#28a745' : '#6c757d',
                      color: 'white',
                      fontWeight: '600'
                    }}>
                      <Video size={14} style={{marginRight: '0.35rem'}} /> {stats.totalPrerolls} preroll{stats.totalPrerolls !== 1 ? 's' : ''}
                    </div>
                    {stats.totalDuration > 0 && (
                      <div style={{ 
                        display: 'inline-block',
                        fontSize: '0.75rem', 
                        padding: '0.2rem 0.5rem',
                        borderRadius: '12px',
                        backgroundColor: '#17a2b8',
                        color: 'white',
                        fontWeight: '600'
                      }}>
                        ⏱️ {formatDuration(stats.totalDuration)}
                      </div>
                    )}
                    {stats.hasActiveSchedules && (
                      <div style={{ 
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        fontSize: '0.75rem', 
                        padding: '0.2rem 0.5rem',
                        borderRadius: '12px',
                        backgroundColor: '#ffc107',
                        color: '#000',
                        fontWeight: '600'
                      }}
                      title={`Active Schedules: ${stats.scheduleNames.join(', ')}`}
                      >
                        <Calendar size={12} /> {stats.activeSchedules} schedule{stats.activeSchedules !== 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Quick Actions Menu */}
                {!bulkActionMode && (
                  <div style={{ position: 'relative' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCategoryMenuOpen(categoryMenuOpen === category.id ? null : category.id);
                      }}
                      className="nx-iconbtn"
                      title="More actions"
                      style={{ fontSize: '1.2rem' }}
                    >
                      ⋮
                    </button>
                    
                    {/* Dropdown Menu */}
                    {categoryMenuOpen === category.id && (
                      <div
                        style={{
                          position: 'absolute',
                          right: 0,
                          top: '100%',
                          marginTop: '0.25rem',
                          backgroundColor: 'var(--card-bg)',
                          border: '2px solid var(--border-color)',
                          borderRadius: '8px',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                          zIndex: 1000,
                          minWidth: '180px',
                          overflow: 'hidden'
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => {
                            handleEditCategory(category);
                            setCategoryMenuOpen(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.75rem 1rem',
                            border: 'none',
                            backgroundColor: 'transparent',
                            textAlign: 'left',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            color: 'var(--text-color)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--hover-bg)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <Edit size={16} /> Edit
                        </button>
                        <button
                          onClick={() => {
                            handleApplyCategoryToActiveServer(category.id, category.name);
                            setCategoryMenuOpen(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.75rem 1rem',
                            border: 'none',
                            backgroundColor: 'transparent',
                            textAlign: 'left',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            color: 'var(--text-color)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--hover-bg)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <Film size={16} /> Apply to Server
                        </button>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(JSON.stringify({
                              name: category.name,
                              description: category.description,
                              plex_mode: category.plex_mode
                            }, null, 2));
                            alert('Category details copied to clipboard!');
                            setCategoryMenuOpen(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.75rem 1rem',
                            border: 'none',
                            backgroundColor: 'transparent',
                            textAlign: 'left',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            color: 'var(--text-color)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--hover-bg)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <FileText size={14} style={{marginRight: '0.35rem'}} /> Copy Details
                        </button>
                        <div style={{ borderTop: '1px solid var(--border-color)', margin: '0.25rem 0' }} />
                        <button
                          onClick={() => {
                            handleDeleteCategory(category.id);
                            setCategoryMenuOpen(null);
                          }}
                          style={{
                            width: '100%',
                            padding: '0.75rem 1rem',
                            border: 'none',
                            backgroundColor: 'transparent',
                            textAlign: 'left',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            color: '#dc3545',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(220, 53, 69, 0.1)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <Trash size={16} /> Delete
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              <p style={{ fontSize: '0.9rem', marginBottom: '0.75rem', color: 'var(--text-secondary)', minHeight: '1.2em' }}>
                {category.description || <em style={{ opacity: 0.6 }}>No description</em>}
              </p>

              {/* Apply to Server */}
              <div style={{ 
                borderTop: '1px solid var(--border-color)', 
                paddingTop: '0.75rem', 
                marginTop: '0.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem'
              }}>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleApplyCategoryToActiveServer(category.id, category.name)}
                    className="button"
                    style={{ 
                      fontSize: '0.8rem', 
                      padding: '0.4rem 0.75rem',
                      flex: '1 1 auto',
                      minWidth: 'fit-content'
                    }}
                    disabled={(() => { const s = getActiveConnectedServer(); return !s || s === 'conflict'; })() || applyingToServer}
                    title={applyingToServer ? "Applying to server..." : "Apply this category to the connected server"}
                  >
                    {applyingToServer ? <><Clock size={14} style={{marginRight: '6px'}} /> Applying...</> : <><Film size={14} style={{marginRight: '6px'}} /> Apply to Server</>}
                  </button>
                  {plexStatus === 'Connected' && category.apply_to_plex && (
                    <button
                      onClick={() => handleRemoveCategoryFromPlex(category.id, category.name)}
                      className="button"
                      style={{ 
                        fontSize: '0.8rem', 
                        padding: '0.4rem 0.75rem', 
                        backgroundColor: '#6c757d',
                        flex: '0 1 auto'
                      }}
                      title="Remove from Plex"
                    >
                      <XCircle size={14} style={{marginRight: '0.35rem'}} /> Remove
                    </button>
                  )}
                </div>

                {/* Manage Prerolls */}
                <button
                  onClick={() => handleEditCategory(category)}
                  className="button"
                  style={{ 
                    fontSize: '0.8rem', 
                    padding: '0.4rem 0.75rem', 
                    backgroundColor: '#17a2b8',
                    width: '100%'
                  }}
                  title="Manage prerolls in this category"
                >
                  <Folder size={14} style={{marginRight: '0.35rem'}} /> Manage Prerolls
                </button>
              </div>
            </div>
          );
            });
          })()}
        </div>
        
        {/* List View */}
        <div style={{ display: categoryView === 'list' ? 'block' : 'none' }}>
          <table className="preroll-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {bulkActionMode && (
                  <th style={{ textAlign: 'center', padding: '0.75rem', borderBottom: '2px solid var(--border-color)', width: '50px' }}>
                    <input
                      type="checkbox"
                      checked={selectedCategoryIds.length === getFilteredCategories().length && getFilteredCategories().length > 0}
                      onChange={toggleSelectAll}
                      style={{ cursor: 'pointer', width: '18px', height: '18px' }}
                    />
                  </th>
                )}
                <th 
                  style={{ 
                    textAlign: 'left', 
                    padding: '0.75rem', 
                    borderBottom: '2px solid var(--border-color)',
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                  onClick={() => handleCategorySortChange('name')}
                  title="Click to sort by name"
                >
                  Name {categorySortField === 'name' && (categorySortDirection === 'asc' ? '▲' : '▼')}
                </th>
                <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '2px solid var(--border-color)' }}>Description</th>
                <th 
                  style={{ 
                    textAlign: 'center', 
                    padding: '0.75rem', 
                    borderBottom: '2px solid var(--border-color)',
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                  onClick={() => handleCategorySortChange('prerolls')}
                  title="Click to sort by preroll count"
                >
                  Prerolls {categorySortField === 'prerolls' && (categorySortDirection === 'asc' ? '▲' : '▼')}
                </th>
                <th style={{ textAlign: 'center', padding: '0.75rem', borderBottom: '2px solid var(--border-color)' }}>Duration</th>
                <th 
                  style={{ 
                    textAlign: 'center', 
                    padding: '0.75rem', 
                    borderBottom: '2px solid var(--border-color)',
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                  onClick={() => handleCategorySortChange('status')}
                  title="Click to sort by status"
                >
                  Status {categorySortField === 'status' && (categorySortDirection === 'asc' ? '▲' : '▼')}
                </th>
                <th style={{ textAlign: 'center', padding: '0.75rem', borderBottom: '2px solid var(--border-color)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                let filtered = getFilteredCategories();
                
                // Apply sorting
                filtered = filtered.sort((a, b) => {
                  let compareA, compareB;
                  
                  switch(categorySortField) {
                    case 'name':
                      compareA = a.name.toLowerCase();
                      compareB = b.name.toLowerCase();
                      break;
                    case 'prerolls':
                      // Calculate actual preroll counts including primary and secondary associations
                      const aPrimaryCount = prerolls.filter(p => p.category_id === a.id).length;
                      const aSecondaryCount = prerolls.filter(p => 
                        p.category_associations && 
                        p.category_associations.some(assoc => assoc.category_id === a.id)
                      ).length;
                      compareA = aPrimaryCount + aSecondaryCount;
                      
                      const bPrimaryCount = prerolls.filter(p => p.category_id === b.id).length;
                      const bSecondaryCount = prerolls.filter(p => 
                        p.category_associations && 
                        p.category_associations.some(assoc => assoc.category_id === b.id)
                      ).length;
                      compareB = bPrimaryCount + bSecondaryCount;
                      break;
                    case 'status':
                      // Sort by active status (has schedules)
                      const aHasSchedule = schedules.some(s => s.category_id === a.id);
                      const bHasSchedule = schedules.some(s => s.category_id === b.id);
                      compareA = aHasSchedule ? 1 : 0;
                      compareB = bHasSchedule ? 1 : 0;
                      break;
                    default:
                      return 0;
                  }
                  
                  if (compareA < compareB) return categorySortDirection === 'asc' ? -1 : 1;
                  if (compareA > compareB) return categorySortDirection === 'asc' ? 1 : -1;
                  return 0;
                });
                
                if (filtered.length === 0) {
                  return (
                    <tr>
                      <td colSpan="5" style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-secondary)' }}>
                        {categorySearchQuery ? (
                          <>
                            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}><Search size={32} /></div>
                            <div style={{ fontSize: '1rem', marginBottom: '0.5rem', color: 'var(--text-color)' }}>
                              No categories found matching "{categorySearchQuery}"
                            </div>
                            <div style={{ fontSize: '0.85rem' }}>
                              Try adjusting your search or create a new category below
                            </div>
                          </>
                        ) : (
                          <>
                            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}><Folder size={32} /></div>
                            <div style={{ fontSize: '1rem', marginBottom: '0.5rem', color: 'var(--text-color)' }}>
                              No categories yet
                            </div>
                            <div style={{ fontSize: '0.85rem' }}>
                              Create your first category below to organize your prerolls
                            </div>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                }
                
                return filtered.map(category => {
                // Calculate statistics for this category
                const stats = getCategoryStats(category);
                const isSelected = selectedCategoryIds.includes(category.id);
                
                return (
                  <tr 
                    key={category.id} 
                    onClick={() => bulkActionMode && toggleSelectCategory(category.id)}
                    style={{ 
                      borderBottom: '1px solid var(--border-color)',
                      backgroundColor: isSelected && bulkActionMode ? 'rgba(255, 193, 7, 0.1)' : 'transparent',
                      cursor: bulkActionMode ? 'pointer' : 'default'
                    }}
                  >
                    {bulkActionMode && (
                      <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectCategory(category.id)}
                          onClick={(e) => e.stopPropagation()}
                          style={{ cursor: 'pointer', width: '18px', height: '18px' }}
                        />
                      </td>
                    )}
                    <td style={{ padding: '0.75rem', fontWeight: '600', color: 'var(--text-color)' }}>
                      {category.name}
                      {stats.hasActiveSchedules && (
                        <span 
                          style={{ marginLeft: '0.5rem', fontSize: '0.85rem' }}
                          title={`Active Schedules: ${stats.scheduleNames.join(', ')}`}
                        >
                          📅
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>
                      {category.description || <em style={{ opacity: 0.6 }}>No description</em>}
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                      <span style={{ 
                        display: 'inline-block',
                        fontSize: '0.75rem', 
                        padding: '0.2rem 0.5rem',
                        borderRadius: '12px',
                        backgroundColor: stats.totalPrerolls > 0 ? '#28a745' : '#6c757d',
                        color: 'white',
                        fontWeight: '600'
                      }}>
                        <Video size={14} style={{marginRight: '0.35rem'}} /> {stats.totalPrerolls}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                      {stats.totalDuration > 0 ? (
                        <span style={{ 
                          display: 'inline-block',
                          fontSize: '0.75rem', 
                          padding: '0.2rem 0.5rem',
                          borderRadius: '12px',
                          backgroundColor: '#17a2b8',
                          color: 'white',
                          fontWeight: '600'
                        }}>
                          ⏱️ {formatDuration(stats.totalDuration)}
                        </span>
                      ) : '-'}
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                      {stats.hasActiveSchedules ? (
                        <span style={{ 
                          display: 'inline-block',
                          fontSize: '0.75rem', 
                          padding: '0.2rem 0.5rem',
                          borderRadius: '12px',
                          backgroundColor: '#ffc107',
                          color: '#000',
                          fontWeight: '600'
                        }}
                        title={stats.scheduleNames.join(', ')}
                        >
                          ✓ {stats.activeSchedules} schedule{stats.activeSchedules !== 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Inactive</span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                      {!bulkActionMode && (
                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApplyCategoryToActiveServer(category.id, category.name);
                            }}
                            className="button"
                            style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                            disabled={(() => { const s = getActiveConnectedServer(); return !s || s === 'conflict'; })() || applyingToServer}
                            title="Apply to Server"
                          >
                            <Film size={14} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditCategory(category);
                            }}
                            className="nx-iconbtn"
                            title="Edit category"
                            style={{ fontSize: '0.9rem' }}
                          >
                            ✏️
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteCategory(category.id);
                            }}
                            className="nx-iconbtn nx-iconbtn--danger"
                            title="Delete category"
                            style={{ fontSize: '0.9rem' }}
                          >
                            <Trash size={14} />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
                });
              })()}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Category Modal */}
      {showCreateCategoryModal && (
        <Modal
          title="Create New Category"
          onClose={() => {
            setShowCreateCategoryModal(false);
            setNewCategory({ name: '', description: '' });
          }}
          width={600}
          zIndex={1000}
        >
          <form onSubmit={(e) => {
            e.preventDefault();
            handleCreateCategory(e);
            setShowCreateCategoryModal(false);
          }}>
            <div className="nx-form-grid">
              <div className="nx-field nx-span-2">
                <label className="nx-label">Category Name *</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Enter category name"
                  value={newCategory.name}
                  onChange={(e) => setNewCategory({...newCategory, name: e.target.value})}
                  required
                  autoFocus
                />
              </div>
              <div className="nx-field nx-span-2">
                <label className="nx-label">Description (Optional)</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Enter category description"
                  value={newCategory.description}
                  onChange={(e) => setNewCategory({...newCategory, description: e.target.value})}
                />
              </div>
            </div>
            <div style={{ 
              backgroundColor: 'var(--info-bg)', 
              border: '1px solid var(--info-border)', 
              borderRadius: '0.5rem', 
              padding: '1rem', 
              marginTop: '1rem',
              marginBottom: '1rem'
            }}>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-color)', margin: 0 }}>
                            <Lightbulb size={16} style={{marginRight: '0.35rem', verticalAlign: 'middle', color: '#14B8A6'}} /> <strong>Tip:</strong> Playback mode (Random/Sequential) is controlled by individual schedules, not categories.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => {
                  setShowCreateCategoryModal(false);
                  setNewCategory({ name: '', description: '' });
                }}
                className="button"
                style={{ backgroundColor: '#6c757d', borderColor: '#6c757d' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="button"
                style={{ backgroundColor: '#28a745', borderColor: '#28a745' }}
              >
                Create Category
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );

  const handleConnectPlex = (e) => {
    e.preventDefault();
    if (jellyfinStatus === 'Connected') {
      alert('Disconnect Jellyfin first (only one media server connection at a time).');
      return;
    }
    fetch(apiUrl('plex/connect'), {
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
    fetch(apiUrl('plex/connect/stable-token'), {
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
      fetch(apiUrl('plex/disconnect'), {
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
    fetch(apiUrl('jellyfin/connect'), {
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
    fetch(apiUrl('jellyfin/disconnect'), {
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
      const res = await fetch(apiUrl(`plex/stable-token/save?token=${encodeURIComponent(tok)}`), { method: 'POST' });
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
      const res = await fetch(apiUrl('plex/tv/start'), { method: 'POST' });
      const data = await res.json();
      if (!res.ok || !data?.id || !data?.url) {
        throw new Error(data?.detail || 'Failed to start Plex.tv login');
      }
      setPlexOAuth({ id: data.id, url: data.url, status: 'pending', error: null });
      try { window.open(data.url, '_blank', 'noopener,noreferrer'); } catch {}

      clearOAuthPoll();
      oauthPollRef.current = setInterval(async () => {
        try {
          const r = await fetch(apiUrl(`plex/tv/status/${data.id}`));
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
      const res = await fetch(apiUrl('plex/tv/connect'), {
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
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}><Star size={18} style={{marginRight: '0.5rem', verticalAlign: 'middle', color: '#14B8A6'}} /> Method 1: Stable Token (Recommended)</h3>
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
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}><Wrench size={18} style={{marginRight: '0.5rem', verticalAlign: 'middle'}} /> Method 2: Manual X-Plex-Token</h3>
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
      const res = await fetch(apiUrl('diagnostics/bundle'));
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
    fetch(apiUrl('system/ffmpeg-info'))
      .then(res => res.json())
      .then(data => setFfmpegInfo(data))
      .catch(() => setFfmpegInfo(null));
  };

  const handleViewChangelog = async () => {
    try {
      const response = await fetch(apiUrl('system/changelog'));
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
      const res = await fetch(apiUrl('thumbnails/rebuild?force=true'), { method: 'POST' });
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
      const res = await fetch(apiUrl('system/paths'));
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
      const res = await fetch(apiUrl('settings/path-mappings'));
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
    const res = await fetch(apiUrl('settings/path-mappings'), {
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

  const loadVerboseLogging = React.useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/settings/verbose-logging'));
      const data = await safeJson(res);
      if (data && typeof data === 'object') {
        setVerboseLogging(data.verbose_logging || false);
      }
    } catch (err) {
      console.error('Load verbose logging error:', err);
    }
  }, []);

  const updateVerboseLogging = async (enabled) => {
    setVerboseLoggingLoading(true);
    try {
      const res = await fetch(apiUrl('/settings/verbose-logging?verbose_logging=' + enabled), {
        method: 'PUT'
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setVerboseLogging(enabled);
      alert(`Verbose logging ${enabled ? 'enabled' : 'disabled'}. Check console logs for detailed information.`);
    } catch (err) {
      alert('Failed to update verbose logging: ' + (err?.message || err));
    } finally {
      setVerboseLoggingLoading(false);
    }
  };

  const loadPassiveMode = React.useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/settings/passive-mode'));
      const data = await safeJson(res);
      if (data && typeof data === 'object') {
        setPassiveMode(data.passive_mode || false);
      }
    } catch (err) {
      console.error('Load passive mode error:', err);
    }
  }, []);

  const updatePassiveMode = async (enabled) => {
    setPassiveModeLoading(true);
    try {
      const res = await fetch(apiUrl('/settings/passive-mode?passive_mode=' + enabled), {
        method: 'PUT'
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setPassiveMode(enabled);
      alert(`Coexistence mode ${enabled ? 'enabled' : 'disabled'}. ${enabled ? 'NeXroll will only manage prerolls during active schedules.' : 'NeXroll will manage prerolls at all times.'}`);
    } catch (err) {
      alert('Failed to update coexistence mode: ' + (err?.message || err));
    } finally {
      setPassiveModeLoading(false);
    }
  };

  const loadClearWhenInactive = React.useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/settings/clear-when-inactive'));
      const data = await safeJson(res);
      if (data && typeof data === 'object') {
        setClearWhenInactive(data.clear_when_inactive || false);
      }
    } catch (err) {
      console.error('Load clear-when-inactive error:', err);
    }
  }, []);

  const updateClearWhenInactive = async (enabled) => {
    setClearWhenInactiveLoading(true);
    try {
      const res = await fetch(apiUrl('/settings/clear-when-inactive?clear_when_inactive=' + enabled), {
        method: 'PUT'
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setClearWhenInactive(enabled);
      alert(`Clear when inactive ${enabled ? 'enabled' : 'disabled'}. ${enabled ? 'Prerolls will be cleared from Plex when no schedule is active.' : 'Prerolls will remain in Plex when no schedule is active.'}`);
    } catch (err) {
      alert('Failed to update clear when inactive: ' + (err?.message || err));
    } finally {
      setClearWhenInactiveLoading(false);
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

  // Folder browser functions for Import feature
  const browseFolders = async (path = '') => {
    setFolderBrowserLoading(true);
    try {
      const res = await fetch(apiUrl('/browse-folders'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try { detail = JSON.parse(text).detail || text; } catch {}
        throw new Error(detail);
      }
      const data = await res.json();
      setFolderBrowserPath(data.path || '');
      setFolderBrowserItems(data.folders || []);
      setFolderBrowserParent(data.parent);
      setFolderBrowserVideoCount(data.video_count || 0);
    } catch (e) {
      alert('Error browsing folders: ' + (e.message || e));
    } finally {
      setFolderBrowserLoading(false);
    }
  };

  const openFolderBrowser = () => {
    setShowFolderBrowser(true);
    browseFolders(mapRootForm.root_path || '');
  };

  const selectFolderFromBrowser = (folderPath) => {
    setMapRootForm(prev => ({ ...prev, root_path: folderPath }));
    setShowFolderBrowser(false);
    // Save to recent paths
    const newRecent = [folderPath, ...recentImportPaths.filter(p => p !== folderPath)].slice(0, 5);
    setRecentImportPaths(newRecent);
    try { localStorage.setItem('nexroll_recent_import_paths', JSON.stringify(newRecent)); } catch {}
  };

  const saveRecentImportPath = (path) => {
    if (!path) return;
    const newRecent = [path, ...recentImportPaths.filter(p => p !== path)].slice(0, 5);
    setRecentImportPaths(newRecent);
    try { localStorage.setItem('nexroll_recent_import_paths', JSON.stringify(newRecent)); } catch {}
  };

  const submitMapRoot = async (applyNow) => {
    const root = (mapRootForm.root_path || '').trim();
    if (!root) {
      setMapRootResult({ type: 'error', message: 'Please enter a root path to import from.' });
      return;
    }
    const cid = parseInt(mapRootForm.category_id, 10);
    if (!cid || isNaN(cid)) {
      setMapRootCategoryError(true); // Highlight the category selector
      setMapRootResult({ type: 'error', message: 'Please select a category before performing a dry run or import.' });
      return;
    }

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
    setMapRootResult(null); // Clear previous results

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
      if (data && data.dry_run) {
        const found = Number(data.total_found ?? 0);
        const present = Number(data.already_present ?? 0);
        const toAdd = Number(data.to_add ?? Math.max(0, found - present));
        // Show dry run results inline instead of alert
        setMapRootResult({
          type: 'dryrun',
          found,
          present,
          toAdd
        });
      } else {
        const added = Number(data.added ?? (Array.isArray(data.added_details) ? data.added_details.length : 0));
        const found = Number(data.total_found ?? 0);
        const present = Number(data.already_present ?? 0);
        // Show import results inline
        setMapRootResult({
          type: 'import',
          added,
          found,
          present
        });
      }
      if (applyNow) {
        // Save to recent paths on successful import
        saveRecentImportPath(root);
        setMapRootForm(prev => ({ ...prev, dry_run: true }));
        fetchData();
      }
    } catch (e) {
      alert('Failed to map: ' + (e && e.message ? e.message : e));
    } finally {
      setMapRootLoading(false);
      setMapRootLoadingMsg('');
      setMapRootProgress({ found: 0, processed: 0, phase: '' });
    }
  };

  // Auto-load mappings at startup
  React.useEffect(() => {
    try { loadPathMappings(); } catch {}
  }, [loadPathMappings]);

  // Auto-load genre mappings and settings when opening Settings tab
  React.useEffect(() => {
    if (activeTab === 'settings') {
      try { loadGenreMaps(); loadGenreSettings(); loadVerboseLogging(); loadPassiveMode(); loadClearWhenInactive(); } catch {}
    }
  }, [activeTab, loadGenreMaps, loadGenreSettings, loadVerboseLogging, loadPassiveMode, loadClearWhenInactive]);

  const renderSettings = () => (
    <div>
      <h1 className="header">Settings</h1>

      <details className="card" open>
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>NeXroll Settings</h2>
        </summary>
        
        {/* Theme Settings */}
        <div style={{ marginTop: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Theme</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            Choose between light and dark themes for the interface.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={darkMode}
                onChange={toggleTheme}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {darkMode ? 'Dark Mode' : 'Light Mode'}
            </span>
          </div>
        </div>

        {/* Timezone Settings */}
        <div style={{ marginTop: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Timezone</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
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
        </div>

        {/* Confirmation Dialogs */}
        <div style={{ marginTop: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Confirmation Dialogs</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            Control whether you see confirmation prompts before deleting items.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={confirmDeletions}
                onChange={(e) => setConfirmDeletions(e.target.checked)}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {confirmDeletions ? 'Show Confirmation Prompts' : 'Skip Confirmation Prompts'}
            </span>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem' }}>
            When enabled, you'll be asked to confirm before deleting schedules, categories, or prerolls.
          </p>
        </div>

        {/* Notification Preferences */}
        <div style={{ marginTop: '1rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Notifications</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            Control success and informational alert notifications.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={showNotifications}
                onChange={(e) => setShowNotifications(e.target.checked)}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {showNotifications ? 'Show Notifications' : 'Hide Notifications'}
            </span>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem' }}>
            When disabled, only critical error messages will be shown. Success and info messages will be suppressed.
          </p>
        </div>

        {/* Verbose Logging */}
        <div style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Verbose Logging (Beta Testing)</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            Enable verbose logging to see detailed debug information in the console. This helps troubleshoot issues during beta testing.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={verboseLogging}
                onChange={(e) => updateVerboseLogging(e.target.checked)}
                disabled={verboseLoggingLoading}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {verboseLogging ? 'Verbose Logging Enabled' : 'Verbose Logging Disabled'}
            </span>
          </div>
          {verboseLogging && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#4CAF50' }}>
                ✓ Verbose logging is active. Check the console (F12) and application logs for detailed information.
              </p>
            </div>
          )}
        </div>

        {/* Coexistence Mode (Passive Mode) */}
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Coexistence Mode</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            Enable this if you use another preroll manager (like Preroll Plus) alongside NeXroll. When enabled, NeXroll will <strong>only</strong> manage prerolls during active schedules and stay hands-off at all other times, allowing your other preroll manager to control prerolls outside scheduled times.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={passiveMode}
                onChange={(e) => updatePassiveMode(e.target.checked)}
                disabled={passiveModeLoading}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {passiveMode ? 'Coexistence Mode Enabled' : 'Coexistence Mode Disabled'}
            </span>
          </div>
          {passiveMode && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid #2196F3', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#2196F3' }}>
                ✓ Coexistence mode is active. NeXroll will only apply prerolls during active schedules. Outside of scheduled times, your other preroll manager can control Plex's preroll settings.
              </p>
            </div>
          )}
          {!passiveMode && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#888' }}>
                ℹ️ Standard mode: NeXroll manages prerolls at all times, including applying fallback categories when no schedules are active.
              </p>
            </div>
          )}
        </div>

        {/* Clear When Inactive */}
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Clear Prerolls When Inactive</h3>
          <p style={{ marginBottom: '1rem', color: '#888', fontSize: '0.9rem' }}>
            When enabled, NeXroll will <strong>clear</strong> the Plex preroll field when no schedules are active. This means no prerolls will play outside of your scheduled times.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="nx-rockerswitch">
              <input
                type="checkbox"
                checked={clearWhenInactive}
                onChange={(e) => updateClearWhenInactive(e.target.checked)}
                disabled={clearWhenInactiveLoading || passiveMode}
              />
              <span className="nx-rockerswitch-slider"></span>
            </label>
            <span style={{ fontWeight: 'bold', color: 'var(--text-color)' }}>
              {clearWhenInactive ? 'Clear When Inactive Enabled' : 'Clear When Inactive Disabled'}
            </span>
          </div>
          {passiveMode && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid #ff9800', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#ff9800' }}>
                ⚠️ This setting is disabled while Coexistence Mode is active. Coexistence Mode already keeps NeXroll hands-off outside of schedules.
              </p>
            </div>
          )}
          {!passiveMode && clearWhenInactive && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid #2196F3', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#2196F3' }}>
                ✓ Prerolls will be cleared from Plex when no schedules are active. Movies will play without any preroll outside of scheduled times.
              </p>
            </div>
          )}
          {!passiveMode && !clearWhenInactive && (
            <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#888' }}>
                ℹ️ Prerolls will remain in Plex when no schedules are active (either using a fallback category or leaving the current preroll unchanged).
              </p>
            </div>
          )}
        </div>
      </details>

      <details className="card">
        <summary style={{ cursor: 'pointer' }}>
          <h2 style={{ display: 'inline' }}>Plex Settings</h2>
        </summary>
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
            <button type="button" className="button" onClick={addMappingRow}><Plus size={14} style={{marginRight: '0.35rem'}} /> Add Row</button>
            <button type="button" className="button" onClick={loadPathMappings} disabled={pathMappingsLoading}>↻ Reload</button>
            <button type="button" className="button" onClick={savePathMappings} disabled={pathMappingsLoading} style={{ backgroundColor: '#28a745' }}>
              <Save size={14} style={{marginRight: '0.35rem'}} /> Save
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
            <button type="button" className="button" onClick={runMappingsTest}><FlaskConical size={14} style={{marginRight: '0.35rem'}} /> Run Test</button>
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
              <Download size={14} style={{marginRight: '0.35rem'}} /> Download Database Backup
            </button>
          </div>

          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Files Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Export all preroll video files and thumbnails to ZIP
            </p>
            <button onClick={handleBackupFiles} className="button">
              <Package size={14} style={{marginRight: '0.35rem'}} /> Download Files Backup
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
                <RefreshCw size={14} style={{marginRight: '0.35rem'}} /> Restore Database
              </button>
              <button
                onClick={handleRestoreFiles}
                className="button"
                disabled={!backupFile || !backupFile.name.endsWith('.zip')}
              >
                <FolderOpen size={14} style={{marginRight: '0.35rem'}} /> Restore Files
              </button>
            </div>
          </div>
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
          <button onClick={recheckFfmpeg} className="button"><Search size={14} style={{marginRight: '0.35rem'}} /> Re-check FFmpeg</button>
          <button onClick={handleShowSystemPaths} className="button" style={{ marginLeft: '0.5rem' }}><FolderOpen size={14} style={{marginRight: '0.35rem'}} /> Show Resolved Paths</button>
          <button onClick={handleDownloadDiagnostics} className="button" style={{ marginLeft: '0.5rem' }}><Wrench size={14} style={{marginRight: '0.35rem'}} /> Download Diagnostics</button>
          <button onClick={handleViewChangelog} className="button" style={{ marginLeft: '0.5rem' }}><FileText size={14} style={{marginRight: '0.35rem'}} /> View Changelog</button>
        </div>
      </div>

      {/* GitHub Issues Section */}
      <div className="card">
        <h2><Bug size={20} style={{marginRight: '0.5rem', verticalAlign: 'middle'}} /> Report Issues & Request Features</h2>
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
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem' }}><FileText size={16} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Before Reporting</h3>
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
            <Bug size={14} style={{marginRight: '0.35rem'}} /> Report a Bug
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

  // Render function for Create Schedule page
  const renderCreateSchedule = () => {
    return (
      <div className="upload-section" style={{ maxWidth: '1200px', margin: '30px auto' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '2rem',
          paddingBottom: '1rem',
          borderBottom: '2px solid var(--border-color)'
        }}>
          <h2 style={{ margin: 0, fontSize: '1.8rem', fontWeight: 700 }}>
            {editingSchedule ? 'Edit Schedule' : 'Create New Schedule'}
          </h2>
          <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            {editingSchedule ? 'Modify your existing schedule' : 'Step-by-step guide to create your perfect schedule'}
          </div>
        </div>
        
        <form onSubmit={handleCreateSchedule}>
          {/* Form content will render from renderSchedules - this is the dedicated page version */}
          {/* Using inline form reference to maintain state */}
          {(() => {
            // This renders the same form that's in renderSchedules but on its own page
            // We'll keep this simple for now and use a navigation approach
            return (
              <div style={{ textAlign: 'center', padding: '3rem', opacity: 0.7 }}>
                <p style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>
                  The schedule form is currently embedded in the Schedule List page.
                </p>
                <button 
                  type="button"
                  className="button button-primary"
                  onClick={() => setActiveTab('schedules')}
                  style={{ padding: '1rem 2rem', fontSize: '1rem' }}
                >
                  Go to Schedule List to Create Schedule
                </button>
              </div>
            );
          })()}
        </form>
      </div>
    );
  };

  // Render function for Sequence Builder page
  const renderSequenceBuilder = () => {
    return (
      <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ 
          marginBottom: '1.5rem',
          paddingBottom: '1rem',
          borderBottom: '2px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h1 className="header" style={{ margin: '0 0 0.5rem 0', fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Clapperboard size={28} /> {editingSequenceId ? `Editing: ${editingSequenceName}` : 'Sequence Builder'}
            </h1>
            <p style={{ opacity: 0.7, margin: 0, fontSize: '1rem' }}>
              {editingSequenceId 
                ? 'Update your sequence and save changes to the library' 
                : 'Build custom preroll sequences with full creative control. Combine categories, fixed prerolls, and randomized blocks.'}
            </p>
          </div>
          {editingSequenceId && (
            <button
              onClick={() => {
                // Clear editing state to create a new sequence
                setSequenceBlocks([]);
                setEditingSequenceId(null);
                setEditingSequenceName('');
                setEditingSequenceDescription('');
              }}
              className="button"
              style={{
                padding: '0.75rem 1.5rem',
                backgroundColor: '#28a745',
                borderColor: '#28a745',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
              title="Start building a new sequence from scratch"
            >
              <span style={{ fontSize: '1.2rem' }}>+</span>
              New Sequence
            </button>
          )}
        </div>

        {/* Full-page Sequence Builder */}
        <div style={{ 
          backgroundColor: 'var(--card-bg)', 
          borderRadius: '12px',
          padding: '1.5rem',
          border: '1px solid var(--border-color)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
        }}>
          <SequenceBuilder
            blocks={sequenceBlocks}
            categories={categories}
            prerolls={prerolls}
            apiUrl={apiUrl}
            onBlocksChange={setSequenceBlocks}
            isEditing={editingSequenceId !== null}
            initialName={editingSequenceName}
            initialDescription={editingSequenceDescription}
            onSave={async (name, description) => {
              try {
                await saveSequence(name, description);
              } catch (error) {
                console.error('Save failed:', error);
              }
            }}
            onCancel={() => {
              // Clear the sequence, editing state, and return to library
              setSequenceBlocks([]);
              setEditingSequenceId(null);
              setEditingSequenceName('');
              setEditingSequenceDescription('');
              setActiveTab('schedules/library');
            }}
            onExport={() => {
              // Export sequence as .nexseq format
              const nexseq = {
                type: 'nexseq',
                version: '1.0',
                metadata: {
                  name: editingSequenceName || 'Custom Sequence',
                  description: editingSequenceDescription || '',
                  author: 'NeXroll',
                  created: new Date().toISOString(),
                  exported: new Date().toISOString(),
                  blockCount: sequenceBlocks.length
                },
                blocks: sequenceBlocks,
                compatibility: {
                  minVersion: '1.0',
                  features: []
                }
              };
              
              const blob = new Blob([JSON.stringify(nexseq, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              const safeName = (editingSequenceName || 'sequence').replace(/[^a-z0-9]/gi, '_').toLowerCase();
              a.download = `${safeName}.nexseq`;
              a.click();
              URL.revokeObjectURL(url);
              
              showAlert('Sequence exported as .nexseq file', 'success');
            }}
            onImport={() => {
              // Import sequence from .nexseq or legacy .json
              const input = document.createElement('input');
              input.type = 'file';
              input.accept = '.nexseq,.json';
              input.onchange = async (e) => {
                const file = e.target.files[0];
                if (file) {
                  try {
                    const text = await file.text();
                    const data = JSON.parse(text);
                    
                    // Validate format
                    let blocks = null;
                    let name = '';
                    let description = '';
                    
                    if (data.type === 'nexseq' && data.blocks) {
                      // New .nexseq format
                      blocks = data.blocks;
                      name = data.metadata?.name || '';
                      description = data.metadata?.description || '';
                      
                      // Check compatibility
                      if (data.compatibility?.minVersion && data.compatibility.minVersion > '1.0') {
                        if (!window.confirm(`This sequence requires version ${data.compatibility.minVersion}. Import anyway?`)) {
                          return;
                        }
                      }
                    } else if (data.blocks && Array.isArray(data.blocks)) {
                      // Legacy format
                      blocks = data.blocks;
                      name = data.name || '';
                      description = data.description || '';
                    }
                    
                    if (blocks && Array.isArray(blocks)) {
                      setSequenceBlocks(blocks);
                      if (name) setEditingSequenceName(name);
                      if (description) setEditingSequenceDescription(description);
                      showAlert(`Sequence imported: ${blocks.length} blocks loaded`, 'success');
                    } else {
                      showAlert('Invalid sequence file format', 'error');
                    }
                  } catch (error) {
                    showAlert(`Failed to import: ${error.message}`, 'error');
                  }
                }
              };
              input.click();
            }}
          />
        </div>

        {/* Helper Cards */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '1rem',
          marginTop: '1.5rem'
        }}>
          <div style={{ 
            backgroundColor: 'var(--card-bg)', 
            padding: '1rem',
            borderRadius: '8px',
            border: '1px solid var(--border-color)'
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', fontWeight: 600 }}>💡 Quick Tips</h3>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem', opacity: 0.8 }}>
              <li>Use category blocks for randomized prerolls</li>
              <li>Use fixed blocks for specific prerolls in order</li>
              <li>Drag blocks to reorder your sequence</li>
              <li>Preview your sequence before saving</li>
            </ul>
          </div>
          
          <div style={{ 
            backgroundColor: 'var(--card-bg)', 
            padding: '1rem',
            borderRadius: '8px',
            border: '1px solid var(--border-color)'
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', fontWeight: 600 }}><Package size={16} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> Save & Share</h3>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem', opacity: 0.8 }}>
              <li>Save sequences to your library for reuse</li>
              <li>Export as <code>.nexseq</code> files to share</li>
              <li>Import <code>.nexseq</code> files from others</li>
              <li>Use <code>.zip bundle</code> to export with prerolls included</li>
            </ul>
          </div>
        </div>
      </div>
    );
  };

  // Sequence Library Functions
  const loadSavedSequences = async () => {
    setSequencesLoading(true);
    try {
      const response = await fetch(apiUrl('sequences'));
      const data = await response.json();
      setSavedSequences(data);
    } catch (error) {
      console.error('Failed to load saved sequences:', error);
      showAlert('Failed to load sequences', 'error');
    } finally {
      setSequencesLoading(false);
    }
  };

  const saveSequence = async (name, description) => {
    try {
      // Clean the blocks data before sending to ensure it's properly serializable
      // Validate we have blocks to save
      if (!sequenceBlocks || sequenceBlocks.length === 0) {
        throw new Error('Cannot save empty sequence. Please add at least one block.');
      }
      
      const cleanedBlocks = sequenceBlocks.map(block => {
        const cleaned = {
          type: block.type,
          id: block.id
        };
        
        // Add type-specific fields
        if (block.type === 'random') {
          cleaned.category_id = block.category_id;
          cleaned.count = block.count || 1;
        } else if (block.type === 'fixed') {
          cleaned.preroll_ids = block.preroll_ids || [];
        }
        
        return cleaned;
      });
      
      // Determine if we're updating an existing sequence or creating a new one
      const isUpdating = editingSequenceId !== null;
      const method = isUpdating ? 'PUT' : 'POST';
      const url = isUpdating ? `sequences/${editingSequenceId}` : 'sequences';
      
      console.log(isUpdating ? 'Updating' : 'Creating', 'sequence with data:', { 
        name: name, 
        description: description, 
        blocksCount: cleanedBlocks.length,
        blocks: cleanedBlocks,
        sequenceId: editingSequenceId
      });
      
      const response = await fetch(apiUrl(url), {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          blocks: cleanedBlocks
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Server error response:', errorData);
        
        // Extract meaningful error message from various error response formats
        let errorMessage = isUpdating ? 'Failed to update sequence' : 'Failed to save sequence';
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // FastAPI validation errors format: [{loc: [...], msg: "...", type: "..."}]
          errorMessage = errorData.detail.map(err => {
            const location = err.loc?.join(' -> ') || 'unknown';
            return `${location}: ${err.msg}`;
          }).join('; ');
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }
        
        throw new Error(errorMessage);
      }
      
      const savedSeq = await response.json();
      showAlert(`Sequence "${name}" ${isUpdating ? 'updated' : 'saved'} successfully!`, 'success');
      
      // Clear ALL editing state after successful save/update
      setSequenceBlocks([]);
      setEditingSequenceId(null);
      setEditingSequenceName('');
      setEditingSequenceDescription('');
      
      loadSavedSequences(); // Reload list
      
      // Navigate back to library to show the updated list
      setActiveTab('schedules/library');
      
      return savedSeq;
    } catch (error) {
      console.error('Failed to save sequence:', error);
      const errorMsg = error.message || String(error);
      showAlert(`Failed to save sequence: ${errorMsg}`, 'error');
      throw error;
    }
  };

  const deleteSequence = async (sequenceId, sequenceName) => {
    try {
      const response = await fetch(apiUrl(`sequences/${sequenceId}`), {
        method: 'DELETE'
      });
      
      if (!response.ok) throw new Error('Failed to delete sequence');
      
      showAlert(`Sequence "${sequenceName}" deleted`, 'success');
      loadSavedSequences(); // Reload list
    } catch (error) {
      console.error('Failed to delete sequence:', error);
      showAlert('Failed to delete sequence', 'error');
    }
  };

  const loadSequenceIntoBuilder = (sequence) => {
    setSequenceBlocks(sequence.blocks || []);
    setEditingSequenceId(sequence.id); // Track which sequence we're editing
    setEditingSequenceName(sequence.name || ''); // Load sequence name
    setEditingSequenceDescription(sequence.description || ''); // Load sequence description
    setActiveTab('schedules/builder');
  };

  // Load saved sequences when viewing library
  React.useEffect(() => {
    if (activeTab === 'schedules/library') {
      loadSavedSequences();
    }
  }, [activeTab]);

  // Render function for My Sequences (Library) page
  const renderSequenceLibrary = () => {
    
    return (
      <>
      <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ 
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem',
          paddingBottom: '1rem',
          borderBottom: '2px solid var(--border-color)'
        }}>
          <div>
            <h1 className="header" style={{ margin: '0 0 0.5rem 0', fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Library size={28} /> Saved Sequences</h1>
            <p style={{ opacity: 0.7, margin: 0, fontSize: '1rem' }}>
              Reusable custom sequences you can schedule anytime
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button 
              className="button"
              onClick={loadSavedSequences}
              disabled={sequencesLoading}
              style={{ 
                padding: '0.75rem 1.25rem', 
                fontSize: '0.95rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <RefreshCw size={16} /> {sequencesLoading ? 'Loading...' : 'Refresh'}
            </button>
            
            {/* Import Button - Opens PatternImport Modal */}
            <button 
              className="button"
              onClick={() => setShowSequenceImportModal(true)}
              style={{ 
                padding: '0.75rem 1.25rem', 
                fontSize: '0.95rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: '#17a2b8',
                borderColor: '#17a2b8'
              }}
              title="Import .nexseq or .nexbundle files"
            >
              <Download size={16} /> Import
            </button>
            
            {/* Export All Button */}
            {savedSequences.length > 0 && (
              <button 
                className="button"
                onClick={() => {
                  // Build a map of preroll IDs to their info for quick lookup
                  const prerollMap = {};
                  prerolls.forEach(p => {
                    prerollMap[p.id] = {
                      name: p.name,
                      community_preroll_id: p.community_preroll_id || null
                    };
                  });
                  
                  console.log('[NEXBUNDLE EXPORT] prerolls count:', prerolls.length);
                  console.log('[NEXBUNDLE EXPORT] prerollMap keys:', Object.keys(prerollMap));
                  
                  // Export all sequences as .nexbundle with enriched block data
                  const bundle = {
                    type: 'nexbundle',
                    version: '1.0',
                    exported: new Date().toISOString(),
                    count: savedSequences.length,
                    sequences: savedSequences.map(seq => ({
                      name: seq.name,
                      description: seq.description || '',
                      blocks: seq.blocks.map(block => {
                        if (block.type === 'fixed' && block.preroll_ids) {
                          // Enrich fixed blocks with preroll names and community IDs
                          const enrichedInfo = block.preroll_ids.map(pid => {
                            const info = prerollMap[pid];
                            console.log(`[NEXBUNDLE EXPORT] Preroll ${pid} lookup:`, info);
                            return info ? {
                              id: pid,
                              name: info.name,
                              community_id: info.community_preroll_id
                            } : { 
                              id: pid, 
                              name: null, 
                              community_id: null
                            };
                          });
                          return {
                            ...block,
                            preroll_info: enrichedInfo
                          };
                        }
                        return block;
                      }),
                      created_at: seq.created_at
                    }))
                  };
                  
                  console.log('[NEXBUNDLE EXPORT] Final bundle:', JSON.stringify(bundle, null, 2));
                  
                  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `nexroll-sequences-${Date.now()}.nexbundle`;
                  a.click();
                  URL.revokeObjectURL(url);
                  
                  showAlert(`Exported ${savedSequences.length} sequences as bundle`, 'success');
                }}
                style={{ 
                  padding: '0.75rem 1.25rem', 
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  backgroundColor: '#6c757d',
                  borderColor: '#6c757d'
                }}
                title="Export all sequences as .nexbundle"
              >
                <Upload size={16} /> Export All ({savedSequences.length})
              </button>
            )}
            
            <button 
              className="button button-primary"
              onClick={() => setActiveTab('schedules/builder')}
              style={{ 
                padding: '0.75rem 1.5rem', 
                fontSize: '0.95rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <Plus size={16} /> New Sequence
            </button>
          </div>
        </div>

        {/* Loading State */}
        {sequencesLoading ? (
          <div style={{
            backgroundColor: 'var(--card-bg)',
            borderRadius: '12px',
            padding: '4rem 2rem',
            textAlign: 'center',
            border: '1px solid var(--border-color)'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem', display: 'flex', justifyContent: 'center' }}><Loader2 size={48} className="spin" /></div>
            <p style={{ fontSize: '1.1rem', opacity: 0.7 }}>Loading sequences...</p>
          </div>
        ) : savedSequences.length === 0 ? (
          <div style={{
            backgroundColor: 'var(--card-bg)',
            borderRadius: '12px',
            padding: '3rem 2rem',
            textAlign: 'center',
            border: '2px dashed var(--border-color)'
          }}>
            <div style={{ fontSize: '4rem', marginBottom: '1rem', display: 'flex', justifyContent: 'center' }}><Clapperboard size={64} strokeWidth={1.5} /></div>
            <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.5rem', fontWeight: 600 }}>
              No Saved Sequences Yet
            </h2>
            <p style={{ 
              margin: '0 0 2rem 0', 
              fontSize: '1rem', 
              color: 'var(--text-secondary)',
              maxWidth: '600px',
              marginLeft: 'auto',
              marginRight: 'auto',
              lineHeight: '1.6'
            }}>
              Sequences let you create custom preroll playlists that play in a specific order. 
              Build once, reuse in multiple schedules!
            </p>

            {/* Example Use Cases */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1rem',
              marginBottom: '2rem',
              textAlign: 'left'
            }}>
              {[
                { icon: <Theater size={24} />, title: 'Theater Experience', desc: 'Theater intro → Trailers → Feature announcement' },
                { icon: <TreePine size={24} />, title: 'Holiday Special', desc: 'Holiday greeting → Seasonal trailer → Classic intro' },
                { icon: <Users2 size={24} />, title: 'Family Movie Night', desc: 'Welcome message → Kid-friendly trailer → Safety reminder' }
              ].map((example, idx) => (
                <div key={idx} style={{
                  padding: '1rem',
                  backgroundColor: 'var(--bg-color)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)'
                }}>
                  <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem', color: '#667eea' }}>{example.icon}</div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.25rem' }}>{example.title}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{example.desc}</div>
                </div>
              ))}
            </div>

            <button 
              className="button button-primary"
              onClick={() => setActiveTab('schedules/builder')}
              style={{ 
                padding: '1rem 2rem', 
                fontSize: '1rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <Clapperboard size={18} /> Create Your First Sequence
            </button>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
            gap: '1.5rem'
          }}>
            {savedSequences.map((sequence, index) => (
              <div 
                key={index}
                style={{
                  backgroundColor: 'var(--card-bg)',
                  borderRadius: '12px',
                  padding: '1.25rem',
                  border: '1px solid var(--border-color)',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-4px)';
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
                }}
              >
                {/* Header: Title */}
                <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '1.2rem', fontWeight: 600, lineHeight: 1.3 }}>
                  {sequence.name}
                </h3>
                
                {/* Stats Row */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                  <span style={{ 
                    fontSize: '0.75rem',
                    padding: '0.3rem 0.6rem',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    color: '#6366f1',
                    borderRadius: '4px',
                    fontWeight: 600,
                    whiteSpace: 'nowrap'
                  }}>
                    {sequence.blocks?.length || 0} blocks
                  </span>
                  <span style={{ 
                    fontSize: '0.75rem',
                    padding: '0.3rem 0.6rem',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    color: '#10b981',
                    borderRadius: '4px',
                    fontWeight: 600,
                    whiteSpace: 'nowrap'
                  }}>
                    {(sequence.blocks || []).reduce((total, block) => {
                      if (block.type === 'random') return total + (block.count || 1);
                      if (block.type === 'fixed') return total + (block.preroll_ids?.length || 0);
                      return total;
                    }, 0)} prerolls
                  </span>
                  <span style={{ 
                    fontSize: '0.75rem',
                    padding: '0.3rem 0.6rem',
                    backgroundColor: 'rgba(107, 114, 128, 0.1)',
                    color: 'var(--text-secondary)',
                    borderRadius: '4px',
                    whiteSpace: 'nowrap'
                  }}>
                    {sequence.created_at ? new Date(sequence.created_at).toLocaleDateString() : 'Unknown date'}
                  </span>
                </div>
                
                {/* Description */}
                {sequence.description && (
                  <p style={{ 
                    margin: '0 0 0.75rem 0', 
                    fontSize: '0.85rem', 
                    opacity: 0.7,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    lineHeight: 1.5,
                    flex: 1
                  }}>
                    {sequence.description}
                  </p>
                )}
                
                {/* Spacer if no description */}
                {!sequence.description && <div style={{ flex: 1 }} />}
                
                {/* Action Buttons */}
                <div style={{ 
                  display: 'flex', 
                  gap: '0.5rem',
                  marginTop: '0.75rem',
                  paddingTop: '0.75rem',
                  borderTop: '1px solid var(--border-color)',
                  flexWrap: 'wrap'
                }}>
                  <button 
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPreviewingSequence(sequence);
                      setShowSequencePreviewModal(true);
                    }}
                    style={{ 
                      padding: '0.4rem 0.75rem', 
                      fontSize: '0.8rem',
                      backgroundColor: '#10b981',
                      borderColor: '#10b981',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                    title="Preview sequence playback"
                  >
                    <Play size={13} /> Play
                  </button>
                  <button 
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setExportingSequence(sequence);
                      setShowSequenceExportModal(true);
                    }}
                    style={{ 
                      padding: '0.4rem 0.75rem', 
                      fontSize: '0.8rem',
                      backgroundColor: '#17a2b8',
                      borderColor: '#17a2b8',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                    title="Export sequence"
                  >
                    <Save size={13} /> Export
                  </button>
                  <button 
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      loadSequenceIntoBuilder(sequence);
                    }}
                    style={{ 
                      padding: '0.4rem 0.75rem', 
                      fontSize: '0.8rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                    title="Edit sequence"
                  >
                    <Edit size={13} /> Edit
                  </button>
                  <button 
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Delete sequence "${sequence.name}"?`)) {
                        deleteSequence(sequence.id, sequence.name);
                      }
                    }}
                    style={{ 
                      padding: '0.4rem 0.75rem', 
                      fontSize: '0.8rem',
                      backgroundColor: '#dc3545',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      marginLeft: 'auto'
                    }}
                    title="Delete sequence"
                  >
                    <Trash size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Pattern Import Modal */}
      <PatternImport
        isOpen={showSequenceImportModal}
        onClose={() => setShowSequenceImportModal(false)}
        onImport={async (importedBlocks, metadata) => {
          // Check if this was a bundle import (already saved in backend)
          if (importedBlocks && importedBlocks.bundle_import && importedBlocks.success) {
            // Bundle sequences already saved by backend - just refresh the list
            showAlert(`Successfully imported ${importedBlocks.imported_count} sequences from bundle!`, 'success');
            loadSavedSequences();
            setShowSequenceImportModal(false);
            return;
          }
          
          // Save the imported sequence to database
          try {
            const response = await fetch(apiUrl('sequences'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: metadata?.name || 'Imported Sequence',
                description: metadata?.description || '',
                blocks: importedBlocks
              })
            });
            
            if (response.ok) {
              showAlert(`Successfully imported "${metadata?.name || 'Imported Sequence'}"!`, 'success');
              loadSavedSequences();
            } else {
              const error = await response.json();
              // Handle various error detail formats
              let errorMsg = 'Unknown error';
              if (typeof error.detail === 'string') {
                errorMsg = error.detail;
              } else if (Array.isArray(error.detail)) {
                errorMsg = error.detail.map(err => err.msg || String(err)).join('; ');
              } else if (error.detail) {
                errorMsg = JSON.stringify(error.detail);
              }
              showAlert(`Failed to save sequence: ${errorMsg}`, 'error');
            }
          } catch (error) {
            showAlert(`Error saving sequence: ${error.message}`, 'error');
          }
          setShowSequenceImportModal(false);
        }}
        existingFiles={prerolls.map(p => p.full_path)}
        showCommunityDownload={true}
      />
      
      {/* Pattern Export Modal */}
      {exportingSequence && (
        <PatternExport
          isOpen={showSequenceExportModal}
          onClose={() => {
            setShowSequenceExportModal(false);
            setExportingSequence(null);
          }}
          scheduleId={exportingSequence.id}
          scheduleName={exportingSequence.name}
        />
      )}
      
      {/* Sequence Preview Modal */}
      {previewingSequence && (
        <SequencePreviewModal
          isOpen={showSequencePreviewModal}
          onClose={() => {
            setShowSequencePreviewModal(false);
            setPreviewingSequence(null);
          }}
          blocks={previewingSequence.blocks || []}
          categories={categories}
          prerolls={prerolls}
          sequenceName={previewingSequence.name}
          apiUrl={apiUrl}
        />
      )}
      </>
    );
  };

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
                <Download size={14} style={{marginRight: '0.35rem'}} /> Download
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
                <Check size={14} style={{marginRight: '0.35rem'}} /> Accept & Continue
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
              <FileText size={14} style={{marginRight: '0.35rem'}} /> Fair Use Policy
            </button>
          </div>
          
          {/* Index Status & Build Button */}
          {communityIndexStatus && (
            <div style={{
              padding: '0.75rem',
              backgroundColor: communityIndexStatus.exists 
                ? (communityIndexStatus.is_stale ? 'rgba(20, 184, 166, 0.1)' : 'rgba(34, 197, 94, 0.1)')
                : 'rgba(239, 68, 68, 0.1)',
              border: `1px solid ${communityIndexStatus.exists 
                ? (communityIndexStatus.is_stale ? 'rgba(20, 184, 166, 0.3)' : 'rgba(34, 197, 94, 0.3)')
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
                        <span><AlertTriangle size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle', color: '#14B8A6'}} /> <strong>Index is stale</strong> (last updated {Math.round(communityIndexStatus.age_days)} days ago)</span>
                      ) : (
                        <span><Sparkles size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle', color: '#10b981'}} /> <strong>Fast search enabled</strong></span>
                      )}
                    </>
                  ) : (
                    <span><Lightbulb size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle', color: '#14B8A6'}} /> <strong>Build local index for instant searches</strong></span>
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
                    whiteSpace: 'nowrap',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem'
                  }}>
                    <Library size={14} /> <strong>{communityIndexStatus.total_prerolls}</strong> indexed
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
                    whiteSpace: 'nowrap',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem'
                  }}>
                    <Link size={14} /> <strong>{communityMatchedCount}</strong> matched
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
                  {communityIsBuilding ? <><Loader2 size={14} style={{marginRight: '0.35rem'}} className="animate-spin" /> Building...</> : (communityIndexStatus.exists ? <><RefreshCw size={14} style={{marginRight: '0.35rem'}} /> Refresh Index</> : <><Zap size={14} style={{marginRight: '0.35rem'}} /> Build Index</>)}
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
                  {communityIsMigrating ? <><Loader2 size={14} style={{marginRight: '0.35rem'}} className="animate-spin" /> Matching...</> : <><Link size={14} style={{marginRight: '0.35rem'}} /> Match Existing Prerolls</>}
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
                      backgroundColor: darkMode ? 'rgba(20, 184, 166, 0.1)' : 'rgba(20, 184, 166, 0.15)',
                      border: darkMode ? '1px solid rgba(20, 184, 166, 0.3)' : '1px solid rgba(20, 184, 166, 0.4)',
                      color: darkMode ? 'rgba(20, 184, 166, 0.9)' : '#b45309'
                    }}
                    title="Clear all existing matches and rematch with improved algorithm"
                  >
                    {communityIsMigrating ? <><Loader2 size={14} style={{marginRight: '0.35rem'}} className="animate-spin" /> Rematching...</> : <><RefreshCcw size={14} style={{marginRight: '0.35rem'}} /> Rematch All</>}
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
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem'
              }}>
                <Link size={14} /> Matching Prerolls to Community Library
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
                  zIndex: 1,
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  <Search size={18} />
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
                {communityIsSearching ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
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
              <div style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Search size={14} /> Searching Typical Nerds library...
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
                    color: 'var(--text-secondary)'
                  }}>
                    <Film size={28} />
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
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><User size={14} /> {cleanDisplayText(preroll.creator)}</span>
                      )}
                      {preroll.category && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><FolderOpen size={14} /> {cleanDisplayText(preroll.category)}</span>
                      )}
                      {preroll.duration && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Clock size={14} /> {preroll.duration}s</span>
                      )}
                      {preroll.file_size && preroll.file_size !== 'Unknown' && (
                        <span><Package size={14} style={{marginRight: '0.35rem', verticalAlign: 'middle'}} /> {preroll.file_size}</span>
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
                        <Play size={14} style={{marginRight: '0.25rem'}} /> Preview
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
                          <CheckCircle size={14} style={{marginRight: '0.25rem'}} /> Downloaded
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
                          {communityIsDownloading[preroll.id] === 'downloading' ? <><Loader2 size={14} style={{marginRight: '0.35rem'}} /> Downloading...</> : 
                           communityIsDownloading[preroll.id] === 'processing' ? <><Settings size={14} style={{marginRight: '0.35rem'}} /> Processing...</> : 
                           <><Download size={14} style={{marginRight: '0.35rem'}} /> Download</>}
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
                        {communityShowAddToCategory[preroll.id] ? <><CheckCircle size={14} style={{marginRight: '0.25rem'}} /> Category</> : <><Plus size={14} style={{marginRight: '0.25rem'}} /> Category</>}
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
            <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}><Film size={48} /></div>
            <p style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)' }}>
              {communityTotalResults === 0 && communitySearchQuery ? 
                `No results found for "${communitySearchQuery}". Try different keywords or browse by category.` :
                'No results yet. Start searching or browse by category and platform!'}
            </p>
            <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)', opacity: 0.7, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}>
              <Lightbulb size={14} /> Tip: Search by theme, holiday, genre, or franchise (e.g., "halloween", "thanksgiving", "christmas", "marvel", "star wars")
            </p>
          </div>
        )}

        {/* Random Preroll Section - Always Visible */}
        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Shuffle size={14} style={{marginRight: '0.35rem'}} /> Random Preroll
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
                <Shuffle size={24} />
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
                justifyContent: 'center'
              }}>
                <Film size={36} style={{ color: '#9333ea' }} />
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
                    <Eye size={14} style={{marginRight: '0.35rem'}} /> Preview
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
                    <Download size={14} style={{marginRight: '0.35rem'}} /> Download
                  </button>
                  <button
                    onClick={() => setCommunityRandomPreroll(null)}
                    className="button"
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#6b7280'
                    }}
                  >
                    <X size={14} style={{marginRight: '0.35rem'}} /> Clear
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
                      {communityIsDownloading[communityRandomPreroll.id] === 'downloading' ? <><Loader2 size={14} style={{marginRight: '0.35rem'}} /> Downloading...</> : 
                       communityIsDownloading[communityRandomPreroll.id] === 'success' ? <><CheckCircle size={14} style={{marginRight: '0.35rem'}} /> Downloaded!</> : 
                       <><Download size={14} style={{marginRight: '0.35rem'}} /> Confirm Download</>}
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

  // Test route for Sequence Builder
  if (window.location.pathname === '/test-sequence') {
    return <TestSequenceBuilder />;
  }

  return (
    <div className="app-container">
      {/* Tab Navigation with right-aligned logo */}
      <div
        className="tab-buttons"
        style={{ alignItems: 'center', justifyContent: 'space-between', padding: '0 0.5rem' }}
      >
        {/* Mobile hamburger menu button */}
        <button 
          className="mobile-menu-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
        
        <div className={`tab-group ${mobileMenuOpen ? 'mobile-open' : ''}`}>
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => { setActiveTab('dashboard'); setMobileMenuOpen(false); }}
          >
            Dashboard
          </button>
          
          <button
            className={`tab-button ${activeTab.startsWith('schedules') ? 'active' : ''}`}
            onClick={() => { setActiveTab('schedules'); setMobileMenuOpen(false); }}
          >
            Schedules
          </button>
          
          <button
            className={`tab-button ${activeTab === 'categories' ? 'active' : ''}`}
            onClick={() => { setActiveTab('categories'); setMobileMenuOpen(false); }}
          >
            Categories
          </button>
          <button
            className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => { setActiveTab('settings'); setMobileMenuOpen(false); }}
          >
            Settings
          </button>
          <button
            className={`tab-button ${activeTab === 'connect' ? 'active' : ''}`}
            onClick={() => { setActiveTab('connect'); setMobileMenuOpen(false); }}
          >
            Connect
          </button>
          <button
            className={`tab-button ${activeTab === 'community-prerolls' ? 'active' : ''}`}
            onClick={() => { setActiveTab('community-prerolls'); setMobileMenuOpen(false); }}
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
       {/* Schedule Sub-Nav Tab Bar - Rendered at dashboard level for proper sticky behavior */}
       {activeTab.startsWith('schedules') && (
         <div style={{ 
           position: 'sticky',
           top: '38px',
           zIndex: 800,
           backgroundColor: 'var(--bg-color)',
           paddingTop: '1rem',
           borderBottom: '2px solid var(--border-color)',
           display: 'flex',
           gap: '0.25rem'
         }}>
           {[
             { id: 'schedules', icon: <Calendar size={16} />, label: 'My Schedules' },
             { id: 'schedules/create', icon: <Plus size={16} />, label: 'Create New' },
             { id: 'schedules/calendar', icon: <CalendarDays size={16} />, label: 'Calendar View' },
             { id: 'schedules/builder', icon: <Film size={16} />, label: 'Sequence Builder' },
             { id: 'schedules/library', icon: <BookOpen size={16} />, label: 'Saved Sequences' }
           ].map(tab => (
             <button
               key={tab.id}
               onClick={() => setActiveTab(tab.id)}
               style={{
                 padding: '0.875rem 1.25rem',
                 border: 'none',
                 borderBottom: activeTab === tab.id ? '3px solid var(--button-bg)' : '3px solid transparent',
                 backgroundColor: activeTab === tab.id ? 'var(--bg-color)' : 'transparent',
                 color: activeTab === tab.id ? 'var(--button-bg)' : 'var(--text-color)',
                 cursor: 'pointer',
                 fontSize: '0.9rem',
                 fontWeight: activeTab === tab.id ? 600 : 400,
                 transition: 'all 0.2s',
                 marginBottom: '-2px',
                 display: 'flex',
                 alignItems: 'center',
                 gap: '0.5rem',
                 borderRadius: '8px 8px 0 0'
               }}
               onMouseEnter={(e) => {
                 if (activeTab !== tab.id) {
                   e.currentTarget.style.backgroundColor = 'var(--bg-color)';
                   e.currentTarget.style.color = 'var(--button-bg)';
                 }
               }}
               onMouseLeave={(e) => {
                 if (activeTab !== tab.id) {
                   e.currentTarget.style.backgroundColor = 'transparent';
                   e.currentTarget.style.color = 'var(--text-color)';
                 }
               }}
             >
               <span style={{ display: 'flex', alignItems: 'center' }}>{tab.icon}</span>
               <span>{tab.label}</span>
             </button>
           ))}
         </div>
       )}
       {activeTab === 'dashboard' && renderDashboard()}
       {activeTab.startsWith('schedules') && renderSchedules()}
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
         width={1000}
         zIndex={1100}
         allowBackgroundInteraction={false}
       >
         <form onSubmit={handleUpdatePreroll}>
           {/* Community Match Status Section */}
           {editingPreroll && (
             <div style={{ 
               marginBottom: '1rem', 
               padding: '0.75rem', 
               backgroundColor: editingPreroll.community_preroll_id 
                 ? 'rgba(16, 185, 129, 0.1)'
                 : 'rgba(251, 191, 36, 0.1)',
               border: `1px solid ${editingPreroll.community_preroll_id 
                 ? 'rgba(16, 185, 129, 0.3)' 
                 : 'rgba(251, 191, 36, 0.3)'}`,
               borderRadius: '6px'
             }}>
               <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                 <span style={{ fontSize: '1.2rem' }}>
                   {editingPreroll.community_preroll_id ? '✅' : '⚠️'}
                 </span>
                 <strong style={{ color: 'var(--text-color)' }}>
                   {editingPreroll.community_preroll_id 
                     ? 'Community Match Found' 
                     : 'No Community Match'}
                 </strong>
               </div>
               
               {editingPreroll.community_preroll_id ? (
                 <div>
                   <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                     This preroll is linked to the Community Prerolls library (ID: {editingPreroll.community_preroll_id}).
                   </div>
                   <button
                     type="button"
                     onClick={async () => {
                       if (!window.confirm('Are you sure you want to unmatch this preroll from the Community Prerolls library?')) {
                         return;
                       }
                       try {
                         const res = await fetch(apiUrl(`prerolls/${editingPreroll.id}/unmatch-community`), {
                           method: 'POST'
                         });
                         const result = await handleFetchResponse(res);
                         alert(result.message || 'Unmatched successfully!');
                         setEditingPreroll({ ...editingPreroll, community_preroll_id: null });
                         fetchData();
                       } catch (error) {
                         console.error('Unmatch error:', error);
                         alert('Failed to unmatch: ' + error.message);
                       }
                     }}
                     className="button"
                     style={{
                       backgroundColor: '#ef4444',
                       color: 'white',
                       fontSize: '0.85rem',
                       padding: '0.5rem 0.75rem',
                       display: 'flex',
                       alignItems: 'center',
                       gap: '0.5rem'
                     }}
                     title="Remove the link to Community Prerolls library"
                   >
                     <span>❌</span>
                     Unmatch
                   </button>
                 </div>
               ) : (
                 <div>
                   <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                     This preroll hasn't been matched to the Community Prerolls library yet.
                   </div>
                   <button
                     type="button"
                     onClick={handleAutoMatchPreroll}
                     className="button"
                     disabled={autoMatchLoading}
                     style={{
                       backgroundColor: autoMatchLoading ? '#999' : '#2196f3',
                       color: 'white',
                       fontSize: '0.85rem',
                       padding: '0.5rem 0.75rem',
                       display: 'flex',
                       alignItems: 'center',
                       gap: '0.5rem',
                       cursor: autoMatchLoading ? 'not-allowed' : 'pointer'
                     }}
                     title="Attempt to automatically match this preroll to Community Prerolls library"
                   >
                     {autoMatchLoading ? (
                       <>
                         <span className="nx-spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></span>
                         Searching...
                       </>
                     ) : (
                       <>
                         <span>🔍</span>
                         Auto-Match Now
                       </>
                     )}
                   </button>
                   
                   {/* Similar Matches List */}
                   {similarMatches.length > 0 && (
                     <div style={{ 
                       marginTop: '1rem',
                       padding: '0.75rem',
                       backgroundColor: 'var(--card-bg, #f9f9f9)',
                       border: '1px solid var(--border-color, #ddd)',
                       borderRadius: '6px'
                     }}>
                       <div style={{ 
                         fontSize: '0.9rem', 
                         fontWeight: 'bold', 
                         marginBottom: '0.75rem',
                         color: 'var(--text-color)'
                       }}>
                         Similar Matches Found ({similarMatches.length})
                       </div>
                       <div style={{ 
                         fontSize: '0.8rem', 
                         color: 'var(--text-secondary)',
                         marginBottom: '0.75rem'
                       }}>
                         No exact match was found, but here are some similar prerolls. Click one to link it:
                       </div>
                       <div style={{ 
                         display: 'flex', 
                         flexDirection: 'column', 
                         gap: '0.5rem',
                         maxHeight: '300px',
                         overflowY: 'auto'
                       }}>
                         {similarMatches.map((match, index) => (
                           <div
                             key={match.id}
                             style={{
                               padding: '0.75rem',
                               backgroundColor: 'var(--input-bg, white)',
                               border: '1px solid var(--border-color, #ddd)',
                               borderRadius: '4px',
                               display: 'flex',
                               justifyContent: 'space-between',
                               alignItems: 'center',
                               gap: '0.5rem'
                             }}
                           >
                             <button
                               type="button"
                               onClick={() => handleSelectSimilarMatch(match.id, match.title)}
                               style={{
                                 flex: 1,
                                 padding: '0',
                                 backgroundColor: 'transparent',
                                 border: 'none',
                                 textAlign: 'left',
                                 cursor: 'pointer',
                                 display: 'flex',
                                 justifyContent: 'space-between',
                                 alignItems: 'center',
                                 gap: '0.5rem'
                               }}
                             >
                               <div style={{ flex: 1 }}>
                                 <div style={{ 
                                   fontSize: '0.9rem', 
                                   fontWeight: '500',
                                   color: 'var(--text-color)',
                                   marginBottom: '0.25rem'
                                 }}>
                                   {match.title}
                                 </div>
                                 <div style={{ 
                                   fontSize: '0.75rem', 
                                   color: 'var(--text-secondary)'
                                 }}>
                                   Confidence: {match.confidence}% • ID: {match.id}
                                 </div>
                               </div>
                               <div style={{
                                 padding: '0.25rem 0.5rem',
                                 backgroundColor: match.confidence >= 70 ? 'rgba(16, 185, 129, 0.15)' : 
                                                 match.confidence >= 40 ? 'rgba(251, 191, 36, 0.15)' : 
                                                 'rgba(239, 68, 68, 0.15)',
                                 color: match.confidence >= 70 ? '#059669' : 
                                        match.confidence >= 40 ? '#d97706' : 
                                        '#dc2626',
                                 borderRadius: '3px',
                                 fontSize: '0.75rem',
                                 fontWeight: 'bold'
                               }}>
                                 {match.confidence}%
                               </div>
                             </button>
                             {match.video_url && (
                               <button
                                 type="button"
                                 onClick={() => setCommunityPreviewingPreroll({ id: match.id, title: match.title, url: match.video_url })}
                                 style={{
                                   padding: '0.5rem',
                                   backgroundColor: 'rgba(33, 150, 243, 0.1)',
                                   border: '1px solid rgba(33, 150, 243, 0.3)',
                                   borderRadius: '4px',
                                   color: '#2196f3',
                                   cursor: 'pointer',
                                   fontSize: '1rem',
                                   transition: 'all 0.2s',
                                   display: 'flex',
                                   alignItems: 'center',
                                   justifyContent: 'center',
                                   width: '36px',
                                   height: '36px',
                                   flexShrink: 0
                                 }}
                                 onMouseEnter={(e) => {
                                   e.currentTarget.style.backgroundColor = 'rgba(33, 150, 243, 0.2)';
                                   e.currentTarget.style.borderColor = '#2196f3';
                                 }}
                                 onMouseLeave={(e) => {
                                   e.currentTarget.style.backgroundColor = 'rgba(33, 150, 243, 0.1)';
                                   e.currentTarget.style.borderColor = 'rgba(33, 150, 243, 0.3)';
                                 }}
                                 title="Preview video"
                               >
                                 ▶
                               </button>
                             )}
                           </div>
                         ))}
                       </div>
                       <button
                         type="button"
                         onClick={() => setSimilarMatches([])}
                         style={{
                           marginTop: '0.75rem',
                           padding: '0.5rem',
                           fontSize: '0.8rem',
                           backgroundColor: 'transparent',
                           border: '1px solid var(--border-color)',
                           borderRadius: '4px',
                           color: 'var(--text-secondary)',
                           cursor: 'pointer',
                           width: '100%'
                         }}
                       >
                         ✕ Close Suggestions
                       </button>
                     </div>
                   )}
                 </div>
               )}
             </div>
           )}

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
             <div className="nx-field nx-span-2">
               <label className="nx-label">Tags</label>
               {/* Display current tags as badges */}
               {editForm.tags && (
                 <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                   {(() => {
                     // Parse tags - handle both comma-separated strings and JSON array strings
                     let tagList = [];
                     try {
                       // Try parsing as JSON array first (e.g., '["halloween", "christmas"]')
                       if (editForm.tags.trim().startsWith('[')) {
                         tagList = JSON.parse(editForm.tags);
                       } else {
                         // Otherwise split by comma
                         tagList = editForm.tags.split(',');
                       }
                     } catch (e) {
                       // If JSON parse fails, fall back to comma split
                       tagList = editForm.tags.split(',');
                     }
                     
                     return tagList.filter(t => t && String(t).trim()).map((tag, idx) => {
                       const cleanTag = String(tag).trim();
                       return (
                         <span
                           key={idx}
                           style={{
                             fontSize: '0.8rem',
                             padding: '0.3rem 0.6rem',
                             borderRadius: '12px',
                             backgroundColor: 'rgba(99, 102, 241, 0.15)',
                             color: 'var(--text-color)',
                             border: '1px solid rgba(99, 102, 241, 0.3)',
                             fontWeight: '500',
                             display: 'inline-flex',
                             alignItems: 'center',
                             gap: '0.4rem'
                           }}
                         >
                           {cleanTag}
                           <button
                             type="button"
                             onClick={() => {
                               let tagList = [];
                               try {
                                 if (editForm.tags.trim().startsWith('[')) {
                                   tagList = JSON.parse(editForm.tags);
                                 } else {
                                   tagList = editForm.tags.split(',');
                                 }
                               } catch (e) {
                                 tagList = editForm.tags.split(',');
                               }
                               const filteredTags = tagList.filter(t => t && String(t).trim() !== cleanTag);
                               setEditForm({ ...editForm, tags: filteredTags.join(', ') });
                             }}
                             style={{
                               background: 'none',
                               border: 'none',
                               color: 'rgba(239, 68, 68, 0.8)',
                               cursor: 'pointer',
                               padding: '0',
                               fontSize: '1rem',
                               lineHeight: '1',
                               display: 'flex',
                               alignItems: 'center'
                             }}
                             title={`Remove "${cleanTag}" tag`}
                           >
                             ×
                           </button>
                         </span>
                       );
                     });
                   })()}
                 </div>
               )}
               {/* Tag input with autocomplete */}
               <div style={{ position: 'relative' }}>
                 <input
                   className="nx-input"
                   type="text"
                   placeholder="Type to add tags (comma separated) or select from suggestions"
                   value={editForm.tags}
                   onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                   style={{ paddingRight: '80px' }}
                 />
                 {/* Quick add button for available tags */}
                 {availableTags.length > 0 && (
                   <div style={{
                     position: 'absolute',
                     right: '8px',
                     top: '50%',
                     transform: 'translateY(-50%)',
                     display: 'flex',
                     gap: '4px'
                   }}>
                     <button
                       type="button"
                       onClick={(e) => {
                         const currentTags = editForm.tags.split(',').map(t => t.trim()).filter(Boolean);
                         const dropdown = document.createElement('div');
                         dropdown.style.cssText = `
                           position: fixed;
                           background: var(--card-bg);
                           border: 2px solid var(--border-color);
                           borderRadius: 8px;
                           boxShadow: 0 4px 12px rgba(0,0,0,0.15);
                           padding: 0.5rem;
                           maxHeight: 300px;
                           overflowY: auto;
                           zIndex: 10000;
                         `;
                         const rect = e.target.getBoundingClientRect();
                         dropdown.style.top = rect.bottom + 5 + 'px';
                         dropdown.style.right = window.innerWidth - rect.right + 'px';
                         
                         const title = document.createElement('div');
                         title.textContent = 'Available Tags';
                         title.style.cssText = 'font-weight: 600; margin-bottom: 0.5rem; color: var(--text-color); font-size: 0.9rem;';
                         dropdown.appendChild(title);
                         
                         availableTags.forEach(tag => {
                           const isAdded = currentTags.includes(tag);
                           const btn = document.createElement('button');
                           btn.type = 'button';
                           btn.textContent = isAdded ? `✓ ${tag}` : `+ ${tag}`;
                           btn.style.cssText = `
                             display: block;
                             width: 100%;
                             text-align: left;
                             padding: 0.5rem;
                             margin: 0.2rem 0;
                             background: ${isAdded ? 'rgba(99, 102, 241, 0.15)' : 'transparent'};
                             border: 1px solid ${isAdded ? 'rgba(99, 102, 241, 0.3)' : 'var(--border-color)'};
                             borderRadius: 4px;
                             cursor: pointer;
                             color: var(--text-color);
                             font-size: 0.85rem;
                           `;
                           btn.onmouseover = () => btn.style.backgroundColor = 'rgba(99, 102, 241, 0.25)';
                           btn.onmouseout = () => btn.style.backgroundColor = isAdded ? 'rgba(99, 102, 241, 0.15)' : 'transparent';
                           btn.onclick = () => {
                             if (!isAdded) {
                               const newTags = [...currentTags, tag].join(', ');
                               setEditForm({ ...editForm, tags: newTags });
                             } else {
                               const newTags = currentTags.filter(t => t !== tag).join(', ');
                               setEditForm({ ...editForm, tags: newTags });
                             }
                             document.body.removeChild(dropdown);
                           };
                           dropdown.appendChild(btn);
                         });
                         
                         const closeBtn = document.createElement('button');
                         closeBtn.type = 'button';
                         closeBtn.textContent = 'Close';
                         closeBtn.style.cssText = `
                           width: 100%;
                           padding: 0.5rem;
                           margin-top: 0.5rem;
                           background: var(--button-bg);
                           color: white;
                           border: none;
                           borderRadius: 4px;
                           cursor: pointer;
                           font-size: 0.85rem;
                         `;
                         closeBtn.onclick = () => document.body.removeChild(dropdown);
                         dropdown.appendChild(closeBtn);
                         
                         document.body.appendChild(dropdown);
                       }}
                       className="button"
                       style={{
                         padding: '0.25rem 0.5rem',
                         fontSize: '0.75rem',
                         backgroundColor: '#6366f1',
                         color: 'white',
                         border: 'none',
                         borderRadius: '4px',
                         cursor: 'pointer'
                       }}
                       title="Browse and add from existing tags"
                     >
                       📋 Browse
                     </button>
                   </div>
                 )}
               </div>
               <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                 💡 Separate multiple tags with commas. Click × on badges to remove tags quickly.
               </div>
             </div>
             <div className="nx-field nx-span-2">
               <label style={{ 
                 display: 'flex', 
                 alignItems: 'center', 
                 gap: '0.5rem',
                 cursor: 'pointer',
                 userSelect: 'none'
               }}>
                 <input
                   type="checkbox"
                   checked={editForm.exclude_from_matching}
                   onChange={(e) => setEditForm({ ...editForm, exclude_from_matching: e.target.checked })}
                   style={{ cursor: 'pointer' }}
                 />
                 <span style={{ fontWeight: '600', color: 'var(--text-color)' }}>
                   Exclude from Community Matching
                 </span>
               </label>
               <div style={{ 
                 fontSize: '0.8rem', 
                 color: 'var(--text-secondary)', 
                 marginTop: '0.25rem',
                 marginLeft: '1.5rem'
               }}>
                 Prevent this preroll from being automatically matched to the Community Prerolls library
               </div>
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
             await fetch(apiUrl('system/changelog/mark-seen'), {
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
                 await fetch(apiUrl('system/changelog/mark-seen'), {
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
              href="https://discord.gg/R9eH7TbxEk"
              target="_blank"
              rel="noopener noreferrer"
              title="Join our Discord server"
              style={{ color: 'var(--text-secondary, #666)', textDecoration: 'none' }}
            >
              Discord
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
            <span className="nx-footer-sep" aria-hidden="true" style={{ color: 'var(--text-muted, #999)' }}>•</span>
            <a
              href="https://www.reddit.com/r/NeXroll/"
              target="_blank"
              rel="noopener noreferrer"
              title="Join our subreddit"
              style={{ color: 'var(--text-secondary, #666)', textDecoration: 'none' }}
            >
              Reddit
            </a>
          </div>
        </div>
      </footer>

      {/* Edit Schedule Modal - Available Globally */}
      {editingSchedule && (
        <Modal
          title="Edit Schedule"
          onClose={() => {
            setEditingSchedule(null);
            setScheduleForm({
              name: '', type: 'monthly', start_date: '', end_date: '',
              category_id: '', shuffle: true, playlist: false, fallback_category_id: ''
            });
            setScheduleMode('simple');
            setSequenceBlocks([]);
            setWeekDays([]);
            setMonthDays([]);
            setTimeRange({ start: '', end: '' });
          }}
        >
          <form onSubmit={handleUpdateSchedule}>
            {/* Mode Toggle */}
            <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.5rem', border: '1px solid var(--border-color)' }}>
              <label style={{ display: 'block', marginBottom: '0.75rem', fontWeight: 600, fontSize: '1rem' }}>Schedule Mode</label>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', padding: '0.5rem 1rem', backgroundColor: scheduleMode === 'simple' ? 'var(--button-bg)' : 'var(--bg-color)', color: scheduleMode === 'simple' ? 'white' : 'var(--text-color)', borderRadius: '0.25rem', border: '2px solid var(--border-color)', transition: 'all 0.2s' }}>
                  <input
                    type="radio"
                    value="simple"
                    checked={scheduleMode === 'simple'}
                    onChange={(e) => setScheduleMode(e.target.value)}
                    style={{ marginRight: '0.5rem' }}
                  />
                  <span>Simple (Single Category)</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', padding: '0.5rem 1rem', backgroundColor: scheduleMode === 'advanced' ? 'var(--button-bg)' : 'var(--bg-color)', color: scheduleMode === 'advanced' ? 'white' : 'var(--text-color)', borderRadius: '0.25rem', border: '2px solid var(--border-color)', transition: 'all 0.2s' }}>
                  <input
                    type="radio"
                    value="advanced"
                    checked={scheduleMode === 'advanced'}
                    onChange={(e) => setScheduleMode(e.target.value)}
                    style={{ marginRight: '0.5rem' }}
                  />
                  <span>Advanced (Sequence Builder)</span>
                </label>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>
                {scheduleMode === 'simple' 
                  ? 'Select a single category with random or sequential playback.' 
                  : 'Build a custom sequence with multiple categories and fixed prerolls.'}
              </p>
            </div>

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

              {/* Daily Schedule: Time Selector */}
              {scheduleForm.type === 'daily' && (
                <div className="nx-field nx-span-2" style={{ padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.5rem', border: '1px solid var(--border-color)' }}>
                  <label className="nx-label" style={{ marginBottom: '0.75rem', fontWeight: 600 }}>Run At Time</label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#666' }}>Start Time</label>
                      <input
                        type="time"
                        className="nx-input"
                        value={timeRange.start || ''}
                        onChange={(e) => setTimeRange({...timeRange, start: e.target.value})}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#666' }}>End Time (Optional)</label>
                      <input
                        type="time"
                        className="nx-input"
                        value={timeRange.end || ''}
                        onChange={(e) => setTimeRange({...timeRange, end: e.target.value})}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem', marginBottom: 0 }}>
                    💡 Leave end time empty to run at a specific time, or set both to create a time window
                  </p>
                  {!timeRange.start && (
                    <p style={{ fontSize: '0.85rem', color: '#dc3545', marginTop: '0.5rem', marginBottom: 0 }}>
                      ⚠️ Please select at least a start time
                    </p>
                  )}
                </div>
              )}

              {/* Weekly Schedule: Day of Week Selector */}
              {scheduleForm.type === 'weekly' && (
                <div className="nx-field nx-span-2">
                  <label className="nx-label">Repeat On</label>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                    {['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map((day) => {
                      const dayLower = day.toLowerCase();
                      const isSelected = weekDays.includes(dayLower);
                      return (
                        <label
                          key={day}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: isSelected ? 'var(--button-bg)' : 'var(--bg-color)',
                            color: isSelected ? 'white' : 'var(--text-color)',
                            borderRadius: '0.25rem',
                            border: '2px solid ' + (isSelected ? 'var(--button-bg)' : 'var(--border-color)'),
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            transition: 'all 0.2s',
                            userSelect: 'none'
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setWeekDays([...weekDays, dayLower]);
                              } else {
                                setWeekDays(weekDays.filter(d => d !== dayLower));
                              }
                            }}
                            style={{ marginRight: '0.5rem' }}
                          />
                          <span>{day.substring(0, 3)}</span>
                        </label>
                      );
                    })}
                  </div>
                  {weekDays.length === 0 && (
                    <p style={{ fontSize: '0.85rem', color: '#dc3545', marginTop: '0.5rem', marginBottom: 0 }}>
                      ⚠️ Select at least one day
                    </p>
                  )}
                </div>
              )}

              {/* Monthly Schedule: Day of Month Selector */}
              {scheduleForm.type === 'monthly' && (
                <div className="nx-field nx-span-2">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label className="nx-label" style={{ margin: 0 }}>On Day(s) of Month</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        type="button"
                        onClick={() => setMonthDays(Array.from({length: 31}, (_, i) => i + 1))}
                        style={{
                          padding: '0.35rem 0.75rem',
                          fontSize: '0.8rem',
                          backgroundColor: 'var(--button-bg)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '0.25rem',
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        onClick={() => setMonthDays([])}
                        style={{
                          padding: '0.35rem 0.75rem',
                          fontSize: '0.8rem',
                          backgroundColor: '#6c757d',
                          color: 'white',
                          border: 'none',
                          borderRadius: '0.25rem',
                          cursor: 'pointer',
                          fontWeight: 500
                        }}
                      >
                        Deselect All
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.5rem', marginTop: '0.5rem' }}>
                    {Array.from({length: 31}, (_, i) => i + 1).map((day) => {
                      const isSelected = monthDays.includes(day);
                      return (
                        <button
                          key={day}
                          type="button"
                          onClick={() => {
                            if (isSelected) {
                              setMonthDays(monthDays.filter(d => d !== day));
                            } else {
                              setMonthDays([...monthDays, day].sort((a, b) => a - b));
                            }
                          }}
                          style={{
                            padding: '0.5rem',
                            backgroundColor: isSelected ? 'var(--button-bg)' : 'var(--bg-color)',
                            color: isSelected ? 'white' : 'var(--text-color)',
                            border: '2px solid ' + (isSelected ? 'var(--button-bg)' : 'var(--border-color)'),
                            borderRadius: '0.25rem',
                            cursor: 'pointer',
                            fontSize: '0.85rem',
                            fontWeight: isSelected ? 600 : 400,
                            transition: 'all 0.2s'
                          }}
                        >
                          {day}
                        </button>
                      );
                    })}
                  </div>
                  {monthDays.length === 0 && (
                    <p style={{ fontSize: '0.85rem', color: '#dc3545', marginTop: '0.5rem', marginBottom: 0 }}>
                      ⚠️ Select at least one day
                    </p>
                  )}
                </div>
              )}
              
              {/* Simple Mode: Category Selection */}
              {scheduleMode === 'simple' && (
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
              )}
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
              
              {/* Blend Mode Toggle */}
              <div className="nx-field nx-span-2">
                <label className="nx-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={scheduleForm.blend_enabled}
                    onChange={(e) => setScheduleForm({...scheduleForm, blend_enabled: e.target.checked})}
                    style={{ width: 'auto' }}
                  />
                  <span>🔀 Blend Mode</span>
                </label>
                <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>
                  When enabled, this schedule's prerolls will be mixed with other overlapping schedules that also have Blend Mode enabled. 
                  Great for combining holiday themes (e.g., Hanukkah + Christmas).
                </p>
              </div>
              
              {/* Priority and Exclusive Controls */}
              <div className="nx-field">
                <label className="nx-label">Priority (1-10)</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={scheduleForm.priority}
                    onChange={(e) => setScheduleForm({...scheduleForm, priority: parseInt(e.target.value)})}
                    style={{ flex: 1 }}
                  />
                  <span style={{ 
                    minWidth: '2rem', 
                    textAlign: 'center', 
                    fontWeight: 'bold',
                    color: scheduleForm.priority >= 8 ? '#ef4444' : scheduleForm.priority >= 5 ? '#14B8A6' : '#6b7280'
                  }}>
                    {scheduleForm.priority}
                  </span>
                </div>
                <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>
                  Higher priority schedules win when multiple schedules overlap.
                </p>
              </div>
              
              <div className="nx-field">
                <label className="nx-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={scheduleForm.exclusive}
                    onChange={(e) => setScheduleForm({...scheduleForm, exclusive: e.target.checked})}
                    style={{ width: 'auto' }}
                  />
                  <Lock size={16} style={{ color: '#14B8A6' }} />
                  <span>Exclusive</span>
                </label>
                <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>
                  When active, this schedule wins exclusively (no blending with other schedules).
                </p>
              </div>
              
              {/* Simple Mode: Playback Mode */}
              {scheduleMode === 'simple' && (
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
              )}

              {/* Advanced Mode: Sequence Builder */}
              {scheduleMode === 'advanced' && (
                <div className="nx-field nx-span-2" style={{ marginTop: '1rem' }}>
                  <SequenceBuilder
                    initialSequence={sequenceBlocks}
                    categories={categories}
                    prerolls={prerolls}
                    scheduleId={editingSchedule?.id || null}
                    apiUrl={apiUrl}
                    onSave={(blocks) => {
                      setSequenceBlocks(blocks);
                      console.log('Sequence updated:', blocks);
                    }}
                    onCancel={() => {
                      console.log('Sequence builder cancelled');
                    }}
                  />
                </div>
              )}
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
                    category_id: '', shuffle: true, playlist: false, fallback_category_id: '', color: ''
                  });
                  setScheduleMode('simple');
                  setSequenceBlocks([]);
                  setWeekDays([]);
                  setMonthDays([]);
                  setTimeRange({ start: '', end: '' });
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Holiday Browser Modal */}
      {showHolidayBrowser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000
        }} onClick={(e) => { if (e.target === e.currentTarget) setShowHolidayBrowser(false); }}>
          <div style={{
            backgroundColor: 'var(--card-bg)',
            borderRadius: '12px',
            width: '90%',
            maxWidth: '1200px',
            maxHeight: '90vh',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
            border: '1px solid var(--border-color)'
          }}>
            {/* Modal Header - NeXroll Style */}
            <div style={{
              padding: '1.25rem 1.5rem',
              borderBottom: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'var(--card-bg)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.5rem' }}>🌍</span>
                <div>
                  <h2 style={{ margin: 0, color: 'var(--text-color)', fontSize: '1.25rem', fontWeight: 700 }}>
                    Holiday Browser
                  </h2>
                  <p style={{ margin: '0.15rem 0 0 0', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                    Browse international holidays and create schedules
                  </p>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                {holidayApiStatus && (
                  <span style={{
                    padding: '0.3rem 0.6rem',
                    borderRadius: '4px',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    backgroundColor: holidayApiStatus.available ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: holidayApiStatus.available ? '#22c55e' : '#ef4444',
                    border: `1px solid ${holidayApiStatus.available ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                  }}>
                    {holidayApiStatus.available ? '● Online' : '○ Offline'}
                  </span>
                )}
                <button
                  onClick={() => setShowHolidayBrowser(false)}
                  style={{
                    background: 'var(--bg-color)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-color)',
                    width: '32px',
                    height: '32px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '1.1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--border-color)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-color)'}
                >×</button>
              </div>
            </div>

            {/* Controls Bar */}
            <div style={{
              padding: '1rem 2rem',
              borderBottom: '1px solid var(--border-color)',
              display: 'flex',
              gap: '1rem',
              alignItems: 'center',
              flexWrap: 'wrap',
              backgroundColor: darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)'
            }}>
              {/* Country Selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Country</label>
                <select
                  value={holidaySelectedCountry}
                  onChange={(e) => {
                    setHolidaySelectedCountry(e.target.value);
                    loadHolidays(e.target.value, holidaySelectedYear);
                  }}
                  className="nx-select"
                  style={{ minWidth: '200px', padding: '0.5rem' }}
                >
                  {holidayCountries.length === 0 ? (
                    <option value="US">United States</option>
                  ) : (
                    holidayCountries.map(c => (
                      <option key={c.countryCode} value={c.countryCode}>
                        {c.name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Year Selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Year</label>
                <select
                  value={holidaySelectedYear}
                  onChange={(e) => {
                    setHolidaySelectedYear(parseInt(e.target.value, 10));
                    loadHolidays(holidaySelectedCountry, parseInt(e.target.value, 10));
                  }}
                  className="nx-select"
                  style={{ minWidth: '100px', padding: '0.5rem' }}
                >
                  {[0, 1, 2, 3, 4].map(offset => {
                    const year = new Date().getFullYear() + offset;
                    return <option key={year} value={year}>{year}</option>;
                  })}
                </select>
              </div>

              {/* Search */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Search</label>
                <input
                  type="text"
                  placeholder="Search holidays..."
                  value={holidaySearchQuery}
                  onChange={(e) => setHolidaySearchQuery(e.target.value)}
                  className="nx-input"
                  style={{ padding: '0.5rem 1rem' }}
                />
              </div>
            </div>

            {/* Holiday List */}
            <div style={{
              flex: 1,
              overflow: 'auto',
              padding: '1.5rem 2rem'
            }}>
              {holidaysLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⏳</div>
                  <p>Loading holidays...</p>
                </div>
              ) : holidays.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📅</div>
                  <p>No holidays found for this country/year</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
                  {holidays
                    .filter(h => {
                      if (!holidaySearchQuery) return true;
                      const query = holidaySearchQuery.toLowerCase();
                      return h.name?.toLowerCase().includes(query) || h.localName?.toLowerCase().includes(query);
                    })
                    .map((holiday, idx) => {
                      const holidayDate = new Date(holiday.date + 'T00:00:00');
                      const isPast = holidayDate < new Date();
                      const isPublic = holiday.types?.includes('Public');
                      
                      return (
                        <div key={idx} style={{
                          padding: '1.25rem',
                          borderRadius: '12px',
                          border: '1px solid var(--border-color)',
                          backgroundColor: isPast ? (darkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)') : 'var(--card-bg)',
                          opacity: isPast ? 0.6 : 1,
                          transition: 'all 0.2s ease'
                        }}>
                          {/* Holiday Header */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                            <div style={{ flex: 1 }}>
                              <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-color)' }}>
                                {holiday.name}
                              </h4>
                              {holiday.localName && holiday.localName !== holiday.name && (
                                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                  {holiday.localName}
                                </p>
                              )}
                            </div>
                            {isPublic && (
                              <span style={{
                                padding: '0.25rem 0.5rem',
                                borderRadius: '4px',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                                color: '#3b82f6',
                                textTransform: 'uppercase'
                              }}>Public</span>
                            )}
                          </div>

                          {/* Date Display */}
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            marginBottom: '1rem',
                            padding: '0.75rem',
                            borderRadius: '8px',
                            backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'
                          }}>
                            <span style={{ fontSize: '1.5rem' }}>📅</span>
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text-color)' }}>
                                {holidayDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
                              </div>
                              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                {holiday.fixed ? '📌 Fixed date' : '🔄 Variable date'}
                              </div>
                            </div>
                          </div>

                          {/* Select Holiday Button */}
                          <button
                            type="button"
                            onClick={() => {
                              // Parse the holiday date
                              const holidayDate = new Date(holiday.date + 'T00:00:00');
                              const formattedDate = holidayDate.toISOString().slice(0, 16);
                              
                              // Prefill the schedule form with holiday metadata for auto-updating
                              setScheduleForm(prev => ({
                                ...prev,
                                name: holiday.name,
                                type: 'holiday',
                                start_date: formattedDate,
                                end_date: formattedDate.slice(0, 10) + 'T23:59',
                                // Store holiday metadata for variable-date tracking
                                holiday_name: holiday.name,
                                holiday_country: holidaySelectedCountry
                              }));
                              
                              // Close the holiday browser
                              setShowHolidayBrowser(false);
                              
                              // Show success message with variable date note
                              const variableNote = !holiday.fixed ? '\n\n🔄 This is a variable-date holiday - NeXroll will auto-update the date each year!' : '';
                              showAlert(`✅ Form prefilled with "${holiday.name}" - ${holidayDate.toLocaleDateString()}${variableNote}`, 'success');
                            }}
                            style={{
                              width: '100%',
                              padding: '0.6rem 1rem',
                              borderRadius: '6px',
                              border: 'none',
                              backgroundColor: 'var(--button-bg)',
                              color: 'white',
                              fontWeight: 600,
                              cursor: 'pointer',
                              fontSize: '0.9rem',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.5rem',
                              transition: 'all 0.2s ease'
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                            onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                          >
                            <CheckCircle size={16} /> Select Holiday
                          </button>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
