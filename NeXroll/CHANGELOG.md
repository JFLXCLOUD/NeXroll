# Changelog

## [1.7.4] - 11-09-2025

### Added
- **Enhanced Calendar Views**
  - Added **Week View** with timeline visualization showing schedules as continuous colored bars across 7 days
  - Added **Timeline View for Month** - alternative to grid view showing schedules as continuous spans
  - Month view now includes Display toggle button to switch between Timeline and Grid views
  - Week view includes Previous Week / This Week / Next Week navigation buttons
  - Timeline views show schedule duration with colored bars and day markers at bottom

- **New Schedule Types**
  - Added **Daily** schedule frequency option for repeating prerolls every day
  - Added **Weekly** schedule frequency option for repeating prerolls every week
  - Both options available in Create Schedule and Edit Schedule forms

- **Improved Calendar Navigation**
  - View dropdown now includes: Week, Month, Year
  - Seamless switching between different calendar perspectives
  - Timeline visualizations make it easier to see schedule overlaps and duration

### Fixed
- **Category Management Modal Issues** ([#7](https://github.com/JFLXCLOUD/NeXroll/issues/7))
  - Fixed Edit and Remove buttons not responding in Edit Category modal
  - Edit Preroll modal now properly appears on top when opened from Edit Category
  - Fixed modal overlay blocking clicks to nested modals
  - Improved modal stacking with proper z-index management

## [1.7.3] - 11-08-2025

### Fixed
- **Calendar & Schedule Issues**
  - Fixed yearly/holiday schedules not repeating annually in calendar view
  - Fixed fallback categories not displaying in calendar when no other schedule is active
  - Fixed holiday preset dates being shifted to wrong month due to timezone conversion
  - Backend now preserves naive datetime for yearly/holiday schedules (only month/day matters)
  - Fixed timezone issue where January 31st 23:59 was being stored as February 1st 04:59 UTC

### Added
- **Enhanced Calendar Visualization**
  - Year view now shows as default when opening calendar
  - Larger calendar cells with improved spacing and readability
  - Schedule name tooltips on hover showing all active schedules for each day
  - Fallback category visual indicator with dashed borders
  - Weekend shading for better day-of-week orientation
  - Today highlighting with blue border and colored badge
  - Visual legend explaining all calendar indicators
  - Smooth hover animations with elevation effects
  - Click month cards in year view to drill down to detailed month view

## [1.7.0] - 11-03-2025

### Added
- **Community Prerolls Integration**
  - Access to thousands of community-curated prerolls from prerolls.typicalnerds.uk
  - Smart search engine with synonym expansion (e.g., "turkey" → "thanksgiving")
  - Local index system with unlimited-depth directory scanning (1,327+ prerolls)
  - Dual HTML/JSON parsing for Caddy web server compatibility
  - Real-time progress bar with SSE (Server-Sent Events) during indexing
  - Platform filtering (Plex/Jellyfin)
  - One-click downloads with NO automatic tagging
  - Random preroll discovery feature
  - Fair Use Policy acceptance tracking
  - Indexing button appears automatically after Fair Use acceptance

- **Auto-Apply to Server**
  - Categories automatically reapply to Plex/Jellyfin when new prerolls are added
  - Works for all add methods: upload, community download, drag-and-drop
  - Works for both manually applied categories AND scheduled categories
  - Detects active scheduled categories and updates them automatically
  - Prevents need to manually click "Apply" after adding prerolls

- **Enhanced Plex Connection**
  - Multiple connection methods (Manual, OAuth, Saved Token, Auto-discovery)
  - Secure token storage via Windows Credential Manager
  - Automatic token migration from legacy plaintext storage
  - Enhanced status display with token source tracking
  - Docker-aware auto-discovery for containerized environments
  - Detailed error messages with actionable guidance

- **Database Migration System**
  - Automatic schema migration from v1.5.12+
  - Missing column detection and addition
  - Migration status logging with visual indicators
  - Schema validation on startup

- **GitHub Integration**
  - Bug report button with pre-filled template
  - Feature request button with template
  - Issue templates for consistent reporting
  - Before reporting checklist in Settings

- **Docker Support**
  - Dockerfile for containerized deployment
  - docker-compose.yml with examples
  - Multi-architecture support (amd64, arm64)
  - GitHub Actions workflow for automated builds
  - Docker-specific connection methods

### Changed
- **Plex Status Display**
  - Now shows actual server information instead of form inputs
  - Displays token source (secure_store vs database)
  - Shows storage provider (Windows Credential Manager)
  - Includes server name and version information
  - Color-coded error messages (yellow warnings, red errors)

- **Community Prerolls UI**
  - Search bar width reduced to 60% for better aesthetics
  - Updated search hints to reflect actual capabilities
  - Improved empty state messaging
  - Better platform filter interface

- **Error Handling**
  - Specific error codes: not_configured, missing_token, connection_failed, etc.
  - User-friendly error messages
  - Enhanced logging throughout application
  - Never crashes UI with 500 errors

- **Configuration**
  - Token storage moved to Windows Credential Manager
  - Config file location: %PROGRAMDATA%/NeXroll/
  - Config files now sanitized (no plaintext secrets)

### Fixed
- **Critical: Scheduler crash on upgrade from v1.5.12**
  - Added missing dashboard_layout column to migration
  - Fixed OperationalError when querying missing columns
  - Auto-migration now includes all 8 missing columns

- **Community Prerolls Issues**
  - Fixed indexing only finding ~200 files instead of 1,327+ (Caddy JSON parsing)
  - Fixed progress bar stopping at 95% and not completing
  - Fixed progress bar not hiding after indexing completes
  - Fixed indexing button not appearing on fresh installs after Fair Use acceptance
  - Fixed category dropdown hard to see in dark mode
  - Fixed installer packaging wrong executables (build\dist vs dist)
  - Fixed SSE connection closing before final progress update delivered

- **Plex Connection Issues**
  - Fixed token migration from plaintext to secure store
  - Fixed config file path migration
  - Fixed silent migration failures
  - Fixed status endpoint showing incorrect information

- **Database Schema**
  - Fixed missing columns causing crashes
  - Fixed auto-migration trigger
  - Fixed schema validation

- **UI Issues**
  - Fixed Plex status showing form values instead of server info
  - Fixed error messages returning generic responses
  - Fixed token source visibility
  - Fixed category dropdown using CSS variables that don't work with <select> elements

### Security
- All Plex tokens now stored in Windows Credential Manager
- Configuration files no longer contain plaintext tokens
- Automatic migration of legacy tokens to secure storage
- Sanitized config files with metadata only

## [1.6.0] - 10-XX-2025

### Added
- Genre-based preroll mapping (experimental)
- Dashboard customization options
- Enhanced timezone support

### Changed
- Improved scheduler performance
- Updated UI styling

### Fixed
- Various bug fixes and improvements

## [1.5.12] - 09-XX-2025

### Added
- Basic Plex integration
- Schedule management
- Category organization

### Changed
- UI improvements
- Performance optimizations

### Fixed
- Connection stability issues

---

## Migration Guide

### Upgrading to v1.7.0 from v1.5.12

**Automatic Migration:**
Your database and settings will be automatically migrated on first launch.

**What Gets Migrated:**
- Database schema (8 new columns added)
- Plex tokens (moved to secure storage)
- Configuration files (sanitized)
- Path settings (preserved)

**Expected Console Output:**
```
>>> UPGRADE DETECTED: Migrating database schema for Plex settings...
>>> SCHEMA MIGRATION: Added settings.dashboard_layout (TEXT)
>>> MIGRATION SUCCESS: Database schema migration completed
>>> UPGRADE STATUS: Plex connection status after migration - connected: true
```

**Post-Migration:**
1. Verify Plex connection in Connect tab
2. Check logs at %PROGRAMDATA%\NeXroll\logs\nexroll.log
3. Test scheduling functionality
4. Accept Fair Use Policy for Community Prerolls

---

## Links

- [GitHub Repository](https://github.com/JFLXCLOUD/NeXroll)
- [Release Notes](RELEASE_NOTES_1.7.0.md)
- [Docker Hub](https://hub.docker.com/r/jbrns/nexroll)
- [Issue Tracker](https://github.com/JFLXCLOUD/NeXroll/issues)
