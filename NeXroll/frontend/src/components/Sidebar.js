import React, { useMemo, useState, useRef, useEffect } from 'react';
import {
  LayoutDashboard, Upload, Film, Video, Zap,
  Calendar, Plus, CalendarDays, BookOpen, GitCompare,
  Library, Sparkles, Link as LinkIcon, ClipboardList, Settings,
  Globe, ArrowRight, HardDrive, Key, FileText, Users, Download, Info, FolderTree,
  Github, Heart,
  ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen, X, Search, CornerDownLeft
} from 'lucide-react';

/**
 * NeXroll v2 Sidebar
 *
 * Collapsible, expanding-tree (Arr-style) primary navigation.
 * Drives the existing `activeTab` string state used throughout App.js — every
 * leaf `id` here matches an existing activeTab value, so no render/handler code
 * in App.js needs to change.
 *
 * Props:
 *   activeTab        current activeTab string
 *   setActiveTab     (id) => void
 *   collapsed        icon-only mode
 *   onToggleCollapse () => void
 *   mobileOpen       drawer open on small screens
 *   onCloseMobile    () => void
 *   darkMode         bool (logo variant)
 */

// Navigation model. Parents with `children` expand into a tree.
// A parent's `id` is the activeTab to select when the parent itself is clicked
// (matches the section's default landing tab).
const NAV = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    match: (t) => t === 'dashboard',
  },
  {
    id: 'library',
    label: 'Library',
    icon: Library,
    match: (t) => t === 'library' || t.startsWith('library/'),
    children: [
      { id: 'library', label: 'All Prerolls', icon: Film },
      { id: 'library/add', label: 'Add Prerolls', icon: Upload },
      { id: 'library/categories', label: 'Categories', icon: FolderTree },
      { id: 'library/scaling', label: 'Video Scaling', icon: Video },
    ],
  },
  {
    id: 'schedules',
    label: 'Schedules',
    icon: Calendar,
    match: (t) => t.startsWith('schedules'),
    children: [
      { id: 'schedules', label: 'My Schedules', icon: Calendar },
      { id: 'schedules/create', label: 'Create New', icon: Plus },
      { id: 'schedules/calendar', label: 'Calendar View', icon: CalendarDays },
      { id: 'schedules/builder', label: 'Sequence Builder', icon: Film },
      { id: 'schedules/library', label: 'Saved Sequences', icon: BookOpen },
      { id: 'schedules/conflicts', label: 'Conflicts', icon: GitCompare },
    ],
  },
  {
    id: 'nexup',
    label: 'NeX-Up',
    icon: Sparkles,
    accent: '#ffc230',
    match: (t) => t.startsWith('nexup'),
    children: [
      { id: 'nexup', label: 'Connections', icon: LinkIcon },
      { id: 'nexup/upcoming', label: 'Upcoming', icon: ClipboardList },
      { id: 'nexup/trailers', label: 'Your Trailers', icon: Film },
      { id: 'nexup/generator', label: 'Generator', icon: Sparkles },
      { id: 'nexup/settings', label: 'Settings', icon: Settings },
    ],
  },
  {
    id: 'actions',
    label: 'Quick Actions',
    icon: Zap,
    match: (t) => t === 'actions',
  },
  {
    id: 'connect',
    label: 'Connect',
    icon: LinkIcon,
    match: (t) => t === 'connect',
  },
  {
    id: 'community-prerolls',
    label: 'Community Prerolls',
    icon: Globe,
    match: (t) => t === 'community-prerolls',
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    match: (t) => t.startsWith('settings'),
    children: [
      { id: 'settings', label: 'General', icon: Settings },
      { id: 'settings/paths', label: 'Path Mappings', icon: ArrowRight },
      { id: 'settings/storage', label: 'Storage', icon: HardDrive },
      { id: 'settings/apikeys', label: 'API Keys', icon: Key },
      { id: 'settings/logs', label: 'Logs', icon: FileText },
      { id: 'settings/users', label: 'Users', icon: Users },
      { id: 'settings/backup', label: 'Backup & Restore', icon: Download },
      { id: 'settings/system', label: 'System', icon: Info },
    ],
  },
];

// Extra keyword aliases per destination id, so natural search terms ("dark
// mode", "token", "trailers"…) land on the right page even when they don't
// appear in the visible label.
const KEYWORDS = {
  'dashboard': 'overview home stats status tiles',
  'library': 'prerolls videos files browse collection media',
  'library/add': 'upload import add new preroll video file folder',
  'library/categories': 'category tag organize group folders',
  'library/scaling': 'resolution scale transcode 1080 720 quality video size',
  'schedules': 'schedule automation rules calendar active',
  'schedules/create': 'new schedule add create wizard daily weekly monthly holiday yearly',
  'schedules/calendar': 'calendar month week view',
  'schedules/builder': 'sequence builder blocks order playlist',
  'schedules/library': 'saved sequences reusable nexseq nexbundle import export',
  'schedules/conflicts': 'conflict overlap priority exclusive blend resolve',
  'nexup': 'radarr sonarr connections integrations trailers automation',
  'nexup/upcoming': 'upcoming movies tv shows radarr sonarr releases',
  'nexup/trailers': 'trailers downloaded youtube your',
  'nexup/generator': 'generate dynamic preroll coming soon list create',
  'nexup/settings': 'nexup settings radarr sonarr tmdb youtube cookies quality',
  'actions': 'apply refresh clear bulk maintenance operations quick',
  'connect': 'plex jellyfin emby server token oauth sign in api key media server cinema trailers',
  'community-prerolls': 'community typical nerds download search index browse',
  'settings': 'general theme dark mode light timezone notifications preferences',
  'settings/paths': 'path mapping docker nas unc translate plex path',
  'settings/storage': 'storage folder preroll location auto scan disk',
  'settings/apikeys': 'api key token external integration automation',
  'settings/logs': 'logs events errors debug verbose export',
  'settings/users': 'user account login password auth require admin register',
  'settings/backup': 'backup restore export import data',
  'settings/system': 'system version diagnostics info update about',
};

// Flatten NAV into a searchable index of leaf destinations (and standalone
// top-level items), each with a breadcrumb and keyword string.
const SEARCH_INDEX = (() => {
  const out = [];
  for (const section of NAV) {
    if (section.children && section.children.length) {
      for (const child of section.children) {
        out.push({
          id: child.id,
          label: child.label,
          crumb: section.label,
          icon: child.icon,
          accent: section.accent,
          keywords: `${section.label} ${child.label} ${KEYWORDS[child.id] || ''}`.toLowerCase(),
        });
      }
    } else {
      out.push({
        id: section.id,
        label: section.label,
        crumb: null,
        icon: section.icon,
        accent: section.accent,
        keywords: `${section.label} ${KEYWORDS[section.id] || ''}`.toLowerCase(),
      });
    }
  }
  return out;
})();

function searchNav(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/\s+/);
  const scored = [];
  for (const item of SEARCH_INDEX) {
    const hay = item.keywords;
    // every term must appear somewhere
    if (!terms.every((t) => hay.includes(t))) continue;
    const label = item.label.toLowerCase();
    let score = 0;
    if (label === q) score += 100;
    else if (label.startsWith(q)) score += 60;
    else if (label.includes(q)) score += 40;
    else score += 10; // matched only via keywords/crumb
    scored.push({ item, score });
  }
  scored.sort((a, b) => b.score - a.score || a.item.label.localeCompare(b.item.label));
  return scored.slice(0, 8).map((s) => s.item);
}

// Brand glyphs lucide doesn't ship. Sized/colored via currentColor to match
// the lucide icons in the footer row.
const DiscordIcon = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M20.317 4.369A19.79 19.79 0 0 0 15.885 3c-.196.35-.423.82-.58 1.193a18.27 18.27 0 0 0-5.61 0A12.6 12.6 0 0 0 9.11 3a19.74 19.74 0 0 0-4.432 1.369C1.86 8.59 1.094 12.7 1.476 16.752a19.9 19.9 0 0 0 6.073 3.078c.49-.669.927-1.38 1.302-2.126a12.9 12.9 0 0 1-2.05-.984c.172-.127.34-.26.502-.397a14.2 14.2 0 0 0 12.196 0c.164.14.332.27.502.397-.654.388-1.343.72-2.052.985.375.745.81 1.456 1.3 2.125a19.86 19.86 0 0 0 6.075-3.078c.448-4.694-.766-8.767-3.207-12.383ZM8.02 14.331c-1.183 0-2.157-1.085-2.157-2.42 0-1.334.955-2.42 2.157-2.42 1.21 0 2.176 1.095 2.157 2.42 0 1.335-.955 2.42-2.157 2.42Zm7.96 0c-1.183 0-2.157-1.085-2.157-2.42 0-1.334.955-2.42 2.157-2.42 1.21 0 2.176 1.095 2.157 2.42 0 1.335-.946 2.42-2.157 2.42Z" />
  </svg>
);
const RedditIcon = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 0a12 12 0 1 0 0 24 12 12 0 0 0 0-24Zm5.01 12.74c.06.22.09.45.09.68 0 2.32-2.7 4.2-6.03 4.2-3.34 0-6.04-1.88-6.04-4.2 0-.24.03-.47.09-.69a1.32 1.32 0 0 1 .51-2.55c.36 0 .68.14.92.37a6.6 6.6 0 0 1 3.6-1.14l.69-3.23a.27.27 0 0 1 .32-.21l2.27.48a.94.94 0 1 1-.12.5l-2-.42-.62 2.91a6.6 6.6 0 0 1 3.55 1.14c.24-.23.56-.37.92-.37a1.32 1.32 0 0 1 .51 2.55Zm-7.62.96a.94.94 0 1 0 1.32-1.34.94.94 0 0 0-1.32 1.34Zm5.46.55a3.5 3.5 0 0 1-2.85 1c-1.27 0-2.3-.38-2.85-1a.27.27 0 0 0-.38.38c.7.7 1.9 1.13 3.23 1.13 1.33 0 2.53-.43 3.23-1.13a.27.27 0 0 0-.38-.38Zm-.08-1.5a.94.94 0 1 0 1.32 1.34.94.94 0 0 0-1.32-1.34Z" />
  </svg>
);

const RESOURCE_LINKS = [
  { key: 'github', label: 'GitHub', href: 'https://github.com/JFLXCLOUD/NeXroll', Icon: Github },
  { key: 'discord', label: 'Discord', href: 'https://discord.gg/R9eH7TbxEk', Icon: DiscordIcon },
  { key: 'reddit', label: 'Reddit', href: 'https://www.reddit.com/r/NeXroll/', Icon: RedditIcon },
  { key: 'kofi', label: 'Support on Ko-fi', href: 'https://ko-fi.com/j_b__', Icon: Heart, accent: '#ff5e5b' },
];

function Sidebar({
  activeTab,
  setActiveTab,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  darkMode,
  version,
}) {
  // Which top-level section is currently active (for auto-expanding its tree).
  const activeSectionId = useMemo(() => {
    const sec = NAV.find((n) => n.match(activeTab));
    return sec ? sec.id : null;
  }, [activeTab]);

  const go = (id) => {
    setActiveTab(id);
    if (onCloseMobile) onCloseMobile();
  };

  // ---- Sidebar search (command-palette style) ----
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const searchInputRef = useRef(null);
  const results = useMemo(() => searchNav(query), [query]);

  // Keep the highlighted result in range as the list changes.
  useEffect(() => { setHighlight(0); }, [query]);

  const goToResult = (item) => {
    if (!item) return;
    go(item.id);
    setQuery('');
  };

  const onSearchKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight((h) => Math.min(h + 1, results.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight((h) => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); goToResult(results[highlight]); }
    else if (e.key === 'Escape') { setQuery(''); searchInputRef.current?.blur(); }
  };

  // In collapsed mode the search icon expands the sidebar, then focuses the box.
  const onCollapsedSearchClick = () => {
    if (onToggleCollapse) onToggleCollapse();
    setTimeout(() => searchInputRef.current?.focus(), 180);
  };

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div className="nx-sidebar-backdrop" onClick={onCloseMobile} />
      )}

      <aside
        className={`nx-sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' mobile-open' : ''}`}
        aria-label="Primary navigation"
      >
        {/* Brand / collapse header */}
        <div className="nx-sidebar-head">
          <a
            href="https://github.com/JFLXCLOUD/NeXroll"
            target="_blank"
            rel="noopener noreferrer"
            className="nx-sidebar-brand"
            title="NeXroll on GitHub"
          >
            <img
              src={darkMode ? '/NeXroll_Logo_WHT.png' : '/NeXroll_Logo_BLK.png'}
              alt="NeXroll"
              className="nx-sidebar-logo"
            />
          </a>
          <button
            type="button"
            className="nx-sidebar-collapse"
            onClick={onToggleCollapse}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          {/* Mobile close */}
          <button
            type="button"
            className="nx-sidebar-mobile-close"
            onClick={onCloseMobile}
            aria-label="Close navigation menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search */}
        {collapsed ? (
          <button
            type="button"
            className="nx-sidebar-search-icon"
            onClick={onCollapsedSearchClick}
            title="Search"
            aria-label="Search"
          >
            <Search size={18} />
          </button>
        ) : (
          <div className="nx-sidebar-search">
            <div className="nx-sidebar-search-box">
              <Search size={16} className="nx-sidebar-search-glyph" />
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onSearchKeyDown}
                placeholder="Search settings & pages…"
                aria-label="Search settings and pages"
                spellCheck={false}
              />
              {query && (
                <button type="button" className="nx-sidebar-search-clear" onClick={() => { setQuery(''); searchInputRef.current?.focus(); }} aria-label="Clear search">
                  <X size={14} />
                </button>
              )}
            </div>

            {query && (
              <div className="nx-sidebar-search-results" role="listbox">
                {results.length === 0 ? (
                  <div className="nx-sidebar-search-empty">No matches for “{query}”</div>
                ) : (
                  results.map((item, i) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.id + ':' + item.label}
                        type="button"
                        role="option"
                        aria-selected={i === highlight}
                        className={`nx-sidebar-search-item${i === highlight ? ' active' : ''}`}
                        onMouseEnter={() => setHighlight(i)}
                        onClick={() => goToResult(item)}
                        style={item.accent ? { '--nx-accent': item.accent } : undefined}
                      >
                        <span className="nx-sidebar-search-item-icon"><Icon size={15} /></span>
                        <span className="nx-sidebar-search-item-text">
                          <span className="nx-sidebar-search-item-label">{item.label}</span>
                          {item.crumb && <span className="nx-sidebar-search-item-crumb">{item.crumb}</span>}
                        </span>
                        {i === highlight && <CornerDownLeft size={13} className="nx-sidebar-search-item-enter" />}
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>
        )}

        <nav className="nx-sidebar-nav">
          {NAV.map((section) => {
            const SectionIcon = section.icon;
            const isActiveSection = activeSectionId === section.id;
            const hasChildren = Array.isArray(section.children) && section.children.length > 0;
            // Expand the section's tree when it's the active section (and not collapsed).
            const expanded = hasChildren && isActiveSection && !collapsed;
            const accent = section.accent || 'var(--button-bg)';

            return (
              <div key={section.id} className="nx-sidebar-section">
                <button
                  type="button"
                  className={`nx-sidebar-item nx-sidebar-parent${isActiveSection ? ' active' : ''}`}
                  onClick={() => go(section.id)}
                  title={collapsed ? section.label : undefined}
                  style={isActiveSection ? { '--nx-accent': accent } : undefined}
                >
                  <span className="nx-sidebar-icon"><SectionIcon size={18} /></span>
                  <span className="nx-sidebar-label">{section.label}</span>
                  {hasChildren && !collapsed && (
                    <span className="nx-sidebar-caret">
                      {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </span>
                  )}
                </button>

                {expanded && (
                  <div className="nx-sidebar-children">
                    {section.children.map((child) => {
                      const ChildIcon = child.icon;
                      const childActive = activeTab === child.id;
                      return (
                        <button
                          key={child.id}
                          type="button"
                          className={`nx-sidebar-item nx-sidebar-child${childActive ? ' active' : ''}`}
                          onClick={() => go(child.id)}
                          style={childActive ? { '--nx-accent': accent } : undefined}
                        >
                          <span className="nx-sidebar-icon"><ChildIcon size={15} /></span>
                          <span className="nx-sidebar-label">{child.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Footer: resource links (icon-only) + version */}
        <div className="nx-sidebar-footer">
          <div className="nx-sidebar-resources">
            {RESOURCE_LINKS.map(({ key, label, href, Icon, accent }) => (
              <a
                key={key}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="nx-sidebar-resource"
                title={label}
                aria-label={label}
                style={accent ? { '--nx-resource-accent': accent } : undefined}
              >
                <Icon size={18} />
              </a>
            ))}
          </div>
          {version && (
            <div className="nx-sidebar-version" title={`NeXroll v${version}`}>
              v{version}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
