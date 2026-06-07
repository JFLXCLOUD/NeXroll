import React, { useMemo } from 'react';
import {
  LayoutDashboard, Upload, Film, Video, Zap,
  Calendar, Plus, CalendarDays, BookOpen, GitCompare,
  Library, Sparkles, Link as LinkIcon, ClipboardList, Settings,
  Globe, ArrowRight, HardDrive, Key, FileText, Users, Download, Info, FolderTree,
  ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen, X
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

function Sidebar({
  activeTab,
  setActiveTab,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  darkMode,
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
      </aside>
    </>
  );
}

export default Sidebar;
