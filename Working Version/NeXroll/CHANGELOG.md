# Changelog

## [1.8.9] - 11-28-2025

### Added
- **Expanded Holiday Preset Library**
  - Added 26 new holiday and seasonal presets for a total of 32 comprehensive holidays
  - Winter holidays: Hanukkah, Kwanzaa
  - Spring holidays: St. Patrick's Day, Passover, Cinco de Mayo, Mother's Day
  - Summer holidays: Father's Day, Independence Day, Labor Day
  - Fall holidays: Veterans Day
  - Cultural and international: Diwali, Chinese New Year, Mardi Gras, Ramadan, Eid al-Fitr, Day of the Dead
  - Seasonal themes: Spring Season, Summer Season, Fall Season, Winter Season
  - Special events: Back to School, Black Friday, Cyber Monday, Earth Day, Pride Month, Memorial Day, Martin Luther King Jr. Day
  - Each holiday includes appropriate date ranges for optimal scheduling
  - All holidays integrate seamlessly with the existing Holiday Preset dropdown in schedule creation
  - Impact: Users can now schedule themed prerolls for a comprehensive range of holidays and events throughout the year

- **Enhanced Tag Management System**
  - Tag badge display in preroll grid view with purple pill-shaped design
  - Tag badge display in preroll list view matching grid view styling
  - Interactive tag editor in Edit Preroll modal with chip-based interface
  - Individual tag removal via X buttons on each tag chip
  - Browse button with dropdown showing all available tags for quick selection
  - Autocomplete functionality when selecting from existing tags
  - Dual format support for tags: JSON arrays and comma-separated strings
  - Impact: Users can now easily view, add, edit, and remove tags with a modern, intuitive interface

- **Backup and Restore Enhancements**
  - Sequences now included in database backup exports
  - Sequence metadata preserved: name, description, blocks structure, timestamps
  - Files backup now includes the /sequences/ directory alongside /prerolls/
  - Database restore properly deletes and recreates sequences with full data integrity
  - Sequence blocks JSON structure maintained through backup/restore cycle
  - Impact: Complete data protection for both prerolls and sequences with no data loss during backup operations

### Changed
- **Tag Display Format**
  - Removed emoji icons from tag badges for cleaner appearance
  - Implemented robust JSON parsing to handle array string format tags
  - Tag styling now uses consistent purple theme across all views
  - Badge font size optimized for readability at 0.7-0.8rem
  - Tags display as clean text without brackets or formatting artifacts

- **Holiday Preset Date Ranges**
  - Extended date ranges for better seasonal coverage
  - Christmas: Full month (December 1-31)
  - Halloween: Full month (October 1-31)
  - Thanksgiving: Full month (November 1-30)
  - New holidays use sensible date ranges matching cultural observance periods
  - Schedule form automatically populates dates when selecting holiday presets

- **Backup System Architecture**
  - Database backup endpoint updated to export sequences table
  - Files backup endpoint enhanced to traverse /sequences/ directory
  - Restore endpoint includes proper sequence deletion cascade
  - Datetime parsing with fallback handling for sequence timestamps
  - Error logging per sequence during restore operations

### Fixed
- **Tag Parsing Issues**
  - Fixed tags displaying with JSON array brackets in UI
  - Fixed emoji icons appearing alongside tag text
  - Resolved parsing errors when tags stored as JSON array strings
  - Added fallback parsing for comma-separated legacy format
  - ESLint error resolved: proper event parameter declaration in tag editor

- **Backup Data Integrity**
  - Fixed sequences not being included in database exports
  - Fixed sequence files not included in ZIP archives
  - Fixed restore operations not recreating sequence records
  - Added proper error handling for malformed sequence data during restore

## [1.8.8] - 11-25-2025

### Added
- **Sequence Builder Visual Enhancements**
  - Timeline visualization with thumbnail strips showing preroll previews
  - Full-screen preview modal with playback simulator
  - Sequence statistics dashboard showing total duration, preroll count, and block breakdown
  - View toggle between Card View and Timeline View for different workflow preferences
  - Duration markers and color-coded block types for easy visual identification
  - **Impact**: Users can now visualize and understand their entire sequence before applying it

- **Pattern Export/Import System (.nexseq files)**
  - Export sequences as lightweight JSON pattern files (.nexseq format)
  - Import patterns with automatic Community Preroll matching
  - Smart conflict detection and resolution during import
  - Preview import results before applying changes
  - Missing preroll warnings with download suggestions
  - Community Preroll ID mapping for seamless sharing between NeXroll instances
  - **Impact**: Share sequence patterns without needing to transfer large video files

- **Full Sequence Pack System (.nexpack files)**
  - Export complete sequence packs as ZIP files (.nexpack format) containing videos, thumbnails, and pattern
  - Import sequence packs with automatic category creation and video extraction
  - Progress tracking for large pack imports with real-time status updates
  - Category conflict resolution with merge or create new options
  - File size validation and warnings for very large packs
  - Automatic video file organization and thumbnail generation
  - **Impact**: Share complete, ready-to-use sequences with all media files included

### Changed
- **Sequence Builder Interface**
  - Enhanced block cards with thumbnail previews
  - Improved drag-and-drop visualization with live preview
  - Better mobile responsiveness for sequence building on tablets
  - Statistics panel now shows real-time updates as blocks are added/removed
  - Export options grouped into organized menu (Pattern Only / With Videos)

- **Sequence Data Model**
  - Added `exported_metadata` JSON field to Sequence model for tracking original creator and source
  - Enhanced block validation to support nested sequences and complex patterns
  - Improved JSON schema with versioning for backward compatibility

### Fixed
- **Sequence Preview Accuracy**
  - Fixed duration calculations not accounting for video file metadata
  - Fixed thumbnail generation for videos without embedded thumbnails
  - Fixed preview modal not scrolling properly for very long sequences (20+ blocks)

### Technical
- **Pattern Export/Import (.nexseq)**
  - POST `/api/sequences/{id}/export` - Export sequence pattern as JSON
  - POST `/api/sequences/import` - Import sequence pattern with validation
  - Auto-matching algorithm: matches by Community Preroll ID first, falls back to fuzzy title matching
  - Schema includes: name, description, version, created_by, blocks array with Community Preroll ID mapping
  
- **Sequence Pack Export/Import (.nexpack)**
  - POST `/api/sequences/{id}/export-pack` - Generate .nexpack.zip with videos and pattern
  - POST `/api/sequences/import-pack` - Extract and import complete sequence pack
  - ZIP structure: `sequence.json`, `videos/`, `thumbnails/` directories
  - Automatic category creation with conflict resolution
  - Progress tracking via Server-Sent Events (SSE) for real-time updates
  
- **New Database Fields**
  - `sequences.exported_metadata` (JSON) - Stores original creator, source URL, export timestamp
  - `sequence_imports` table - Tracks import history with match statistics
  
- **New React Components**
  - `SequenceTimeline.js` - Timeline visualization with thumbnail strips
  - `SequencePreviewModal.js` - Full-screen preview with playback simulator
  - `SequenceStats.js` - Statistics dashboard with visual charts
  - `PatternExportModal.js` - Export pattern dialog with download options
  - `PatternImportModal.js` - Import pattern with preview and validation
  - `PackExportModal.js` - Export full pack with progress tracking
  - `PackImportModal.js` - Import pack with category conflict resolution

## [1.8.5] - 11-25-2025

### Fixed
- **Category Management Search Bar Layout**
  - Fixed search bar width to display at correct 65% width instead of full width
  - Simplified layout structure by removing nested wrapper divs
  - Search input now has direct `width: 65%` styling for precise control
  - Filter dropdown set to direct `width: 20%` for consistent sizing
  - View toggle buttons properly aligned to right with `marginLeft: auto`
  - Improved vertical alignment with `alignItems: center` in flex container
  - **Impact**: Cleaner, more maintainable layout code with predictable width behavior

## [1.8.0-beta.2][Unreleased] - 11-23-2025

### Added
- **Category Management Search**
  - Added search bar to Category Management section (matching Schedules section)
  - Search filters categories by name or description in real-time
  - Works in both grid view and list view modes
  - Case-insensitive matching for easier discovery
  - **Impact**: Easier navigation and management of large category collections

- **Category Management List/Grid View Toggle**
  - Added view toggle to Category Management (matching Prerolls section)
  - Grid view: Card-based layout with hover effects, badges, and action buttons
  - List view: Compact table showing Name, Description, Prerolls, Status, Actions columns
  - View preference persisted in localStorage across sessions
  - **Impact**: Users can choose optimal view density based on workflow preference

- **Category Management Sortable Columns**
  - List view columns now support click-to-sort functionality
  - Sortable columns: Name (alphabetical), Prerolls (count), Status (active/inactive)
  - Click column header to sort ascending, click again to toggle descending
  - Visual sort indicator (▲/▼) shows current sort field and direction
  - **Impact**: Quickly organize categories by most used, active schedules, or alphabetically

### Changed
- **Category Management Layout Overhaul**
  - Removed standalone "Create New Category" section for cleaner page layout
  - Added green "+ Create Category" button above search bar for quick access
  - Added "🎄 Load Holiday Categories" button next to create button
  - Create category now opens in modal popup with name and description fields
  - Modal includes helpful tip about playback mode configuration
  - **Impact**: Cleaner, more compact interface with modal-based category creation workflow

### Fixed
- **Verification Loop Error**
  - Fixed infinite verification loop that logged "name 'mode' is not defined" error every 30 seconds
  - Updated verification query to include many-to-many category associations (prerolls assigned as secondary categories)
  - Fixed undefined variable in debug print statements when reapplying category after verification mismatch
  - Verification now correctly counts all prerolls (both primary and associated categories) when checking Plex settings
  - **Impact**: Eliminates recurring error messages and ensures verification accurately reflects expected preroll configuration

### Added
- **Video Preview for Similar Matches**
  - Added preview/play button (▶) next to each similar match result in Edit Preroll modal
  - Users can now preview community preroll videos before confirming a match
  - Preview opens in modal with video player, allowing full video playback
  - Helps users verify correct match and avoid false positives from fuzzy matching
  - **Beta Tester Impact**: Increased confidence in match selection with visual confirmation

### Fixed
- **Calendar View Filter Bug**
  - Fixed disabled schedules still appearing in weekly and yearly calendar views
  - Disabled schedules now properly hidden from week view timeline
  - Disabled schedules now properly hidden from month timeline view
  - Disabled schedules now properly hidden from upcoming schedules dashboard widget
  - When a schedule is disabled, it immediately disappears from all calendar views
  - When re-enabled, schedule appears again in calendar views
  - **Beta Tester Impact**: Prevents confusion from seeing inactive schedules in calendar

- **UI Text Correction**
  - Fixed placeholder "N" text in Random block button description
  - Changed from "Select N random prerolls from category" to "Select random prerolls from a category"
  - **Beta Tester Impact**: Clearer block description in Sequence Builder

## [1.8.0-beta.1] - 11-20-2025

### Added
- **Community Match Status Feature (Phase 1 & 2)**
  - Visual indicators showing which prerolls match Community Prerolls library
  - Edit Preroll modal displays match status with green ✅ (matched) or amber ⚠️ (unmatched) status box
  - Dashboard list and grid views show ✅ icons for matched prerolls
  - "Matched to Community" badge in preroll card descriptions
  - Filter dropdown in Prerolls section to sort by match status (All/Matched/Unmatched)
  - **Auto-Match Functionality**: "Auto-Match Now" button in Edit modal with loading spinner
  - Fuzzy matching algorithm with confidence scoring (exact, substring, word overlap)
  - Similar matches list when no confident match found (50%+ confidence threshold)
  - Automatically filters out community prerolls with hash-like prefixes (e.g., "1740Bdd395C04C5Ea7843Da12858C2B4.Title")
  - Manual selection from similar matches with color-coded confidence badges (green ≥70%, amber 40-69%, red <40%)
  - Auto-match only applies for very confident matches (≥80% similarity)
  - **Unmatch Functionality**: Red "Unmatch" button to remove incorrect community matches
  - **Exclude from Matching**: Checkbox option to prevent specific prerolls from being auto-matched to Community Prerolls library
  - Dark mode compatible styling for similar matches interface

- **Advanced Sequence Builder**
  - Complete overhaul of sequence creation interface with visual building blocks
  - Added 6 new sequence block types:
    - **Preroll Block**: Select individual prerolls with thumbnail previews
    - **Random Block**: Select X random prerolls from a category
    - **Sequential Block**: Play all prerolls from a category in order
    - **Queue Block**: Add all prerolls from the current queue
    - **Sequence Block**: Nest existing sequences within sequences
    - **Separator Block**: Visual dividers to organize complex sequences
  - Real-time sequence preview with drag-and-drop reordering
  - Live playback duration calculation for entire sequence
  - Expandable/collapsible blocks for better organization of large sequences
  - Visual indicators for block types with emoji icons
  - Improved validation with clear error messages
  - One-click block duplication for rapid sequence building

- **Queue Management Integration**
  - Queue block allows adding all queued prerolls to sequences
  - Simplifies workflow: queue multiple prerolls → add all to sequence at once
  - Queue items displayed with thumbnails in sequence preview

### Changed
- **Sequence Creation UI**
  - Moved from simple multi-select list to sophisticated block-based builder
  - Enhanced visual hierarchy with card-based layout
  - Improved mobile responsiveness for sequence building
  - Better feedback for block operations (add, remove, reorder)

### Fixed
- **File Rename Functionality**
  - Fixed "New File Name" feature not renaming files on disk
  - Root cause: External/mapped files (managed=False) were silently skipped during rename
  - Added support for renaming external/mapped files with warning message
  - Warning alerts users: "This is an external/mapped file. Renaming may affect other systems that reference this file."
  - Added comprehensive error handling with user-facing messages (404 for missing source, 409 for existing target, 500 for other failures)
  - Enhanced logging with [RENAME] prefix for debugging
  - Added pre-flight validation (source exists, target doesn't exist)
  - Fallback mechanism: tries os.replace() first, then copy+delete if atomic rename fails

- **Community Match Backend Bug**
  - Fixed match indicators not showing despite prerolls being matched in database
  - Root cause: /prerolls endpoint was missing community_preroll_id field in response
  - Added community_preroll_id to API serialization

- **Filter Combination Bug**
  - Fixed match status filter overriding category filter instead of combining with it
  - Example: "Christmas > Matched" now correctly shows only matched Christmas prerolls, not all matched prerolls
  - Rewrote filtering logic to apply filters in cascading order: category → tags → match status

### Removed
- **Community Prerolls Cleanup**
  - Removed "Calendar Week Start" setting from NeXroll Settings (unused feature)
  - Removed "Community Templates" section from Settings page (feature not active)
  - Removed "✨ Discovery: Latest Prerolls" section from Community Prerolls page
  - Frontend bundle size reduced by ~1.3 KB total

### Technical
- **Community Match System**
  - POST /prerolls/{id}/auto-match endpoint for fuzzy matching (skips excluded prerolls)
  - POST /prerolls/{id}/link-community/{community_id} endpoint for manual linking
  - POST /prerolls/{id}/unmatch-community endpoint to remove incorrect matches
  - Fuzzy matching algorithm: title normalization, exact match, substring match, word overlap
  - Returns top 10 similar matches with confidence scores when no exact match (≥50% threshold)
  - Hash prefix filter: excludes community prerolls with 20+ character alphanumeric prefixes
  - Very confident matches (≥80%) automatically linked, lower confidence shown for manual selection
  - Added exclude_from_matching Boolean column to Preroll model (default: False)
  
- **File Rename Enhancement**
  - Removed managed=True restriction on file renames
  - Added rename_warning tracking for external/mapped files
  - Enhanced error handling with HTTPException for all failure cases
  - Detailed [RENAME] logging throughout rename process
  - Response includes warning field when renaming external files
  
- **Sequence Builder**
  - Refactored sequence data model to support heterogeneous block types
  - Backend now handles 6 block types: 'preroll', 'random', 'sequential', 'queue', 'sequence', 'separator'
  - Added frontend validation for block configuration before submission
  - Improved sequence playback logic to handle nested sequences and dynamic blocks
  - Updated API endpoints to support new block structure

## [1.7.16] - 11-16-2025

### Fixed
- **Docker Upload Bug** 
  - Fixed file uploads failing in Docker environments due to hardcoded localhost URLs
  - Converted 40+ fetch() calls to use dynamic API URL resolution via apiUrl() helper
  - Upload now works correctly in Docker, remote deployments, and localhost

- **Scheduler Interval**
  - Fixed scheduler logging every 1 second causing log spam
  - Changed default scheduler check interval from 1 second to 60 seconds
  - Added configurable SCHEDULER_INTERVAL environment variable (default: 60 seconds)
  - Genre-based auto-switching still responds quickly (separate check)

- **Timezone Auto-Detection**
  - Added support for TZ environment variable in Docker deployments
  - Timezone now auto-detected on first startup from TZ environment variable
  - Eliminates need for manual timezone configuration in Docker
  - Validates timezone using pytz before applying to database

- **Secondary Category Auto-Apply**
  - Fixed prerolls added to secondary categories not being auto-applied to Plex
  - When adding preroll to non-primary category with active schedule, Plex now updates immediately
  - Added db.expire_all() to clear SQLAlchemy session cache before querying for prerolls
  - Ensures newly committed associations are visible in subsequent queries

### Technical
- Created automated script (`scripts/fix_hardcoded_urls.py`) for URL conversion
- Updated `testing/backend/scheduler.py` with configurable interval support
- Updated `testing/backend/main.py` with TZ environment variable detection
- All executables rebuilt with fixes (NeXroll.exe, NeXrollTray.exe, NeXrollService.exe)

## [1.7.15] - 11-14-2025

### Changed
- **Calendar View Default**
  - Monthly calendar now defaults to grid view instead of timeline view
  - Provides immediate visual overview of schedule distribution across the month

### Fixed
- **Custom Schedule Colors Display**
  - Fixed grid view legend to show individual schedules with custom colors instead of categories
  - Fixed yearly overview to display schedules with custom colors instead of categories
  - Fallback schedule borders now respect custom colors for better visual consistency

## [1.7.12] - 11-14-2025

### Added
- **Custom Schedule Colors** 
  - Users can now assign custom hex colors to individual schedules
  - Color picker UI with visual selector, hex input field, and clear button
  - Custom colors override category colors in all calendar views (Week, Month, Year)
  - Optional feature - schedules without custom colors continue using category colors

- **Preroll Matching & Verification**
  - "Match Existing Prerolls" button to associate uploaded prerolls with categories based on tags/keywords
  - "Rematch Prerolls" button to re-run matching algorithm on existing prerolls
  - Automatic matching suggestions when uploading new prerolls
  - Improved matching accuracy with keyword-based category association

### Fixed
- **Plex Preroll Verification**
  - Fixed verification system to properly confirm prerolls were applied to Plex
  - Added retry logic when verification fails on first attempt
  - Improved error reporting when preroll application fails
  - Better handling of Plex API response validation

### Technical
- Added `color` column to schedules table with automatic migration
- Updated schedule API endpoints (POST/PUT/GET) to handle color field
- Enhanced calendar rendering logic across all calendar modes
- Seamless database migration for existing installations

## [1.7.11] - 11-13-2025

### Fixed
- **Additional Docker Query Fixes**
  - Fixed `get_downloaded_community_preroll_ids` endpoint crashing when `community_preroll_id` column doesn't exist
  - Fixed legacy migration functions querying non-existent columns in old databases
  - Added column existence checks before all database queries involving `community_preroll_id`
  - Resolves remaining 500 errors when using Docker with pre-v1.7.9 databases

## [1.7.10] - 11-13-2025

### Fixed
- **Docker Compatibility**
  - Fixed `'community_preroll_id' is an invalid keyword argument for Preroll` error when downloading community prerolls
  - Added conditional kwargs handling for databases created before v1.7.9 column migration
  - Now gracefully handles both old and new database schemas
  
- **Changelog Display in Docker**
  - Fixed "No changelog available" message in Docker containers
  - Added Docker-specific paths (`/app/CHANGELOG.md`, `/app/NeXroll/CHANGELOG.md`)
  - Improved path search with logging across 10+ possible locations
  - Now works correctly in PyInstaller bundles, Docker, and development environments

## [1.7.9] - 11-13-2025

### Added
- **Enhanced Community Prerolls Search**
  - Search now includes tags, filenames, AND display names (previously only tags)
  - More comprehensive search results across all preroll metadata
  
- **Download Tracking System**
  - "✓ Downloaded" indicator on community prerolls you already have in your collection
  - Green checkmark replaces download button for prerolls you've already downloaded
  - ID-based tracking ensures 100% accuracy for new downloads
  - Automatic background migration attempts to detect legacy downloaded prerolls
  
- **Legacy Preroll Support**
  - Hybrid matching system supports prerolls downloaded before tracking was implemented
  - Title-based detection with strict 90% similarity threshold prevents false positives
  - Manual migration endpoint available: `/community-prerolls/migrate-legacy`

### Changed
- **Strict Matching Algorithm**
  - Tightened legacy preroll matching from 70% to 90% length similarity threshold
  - Removed word-based matching to eliminate false positives
  - Only exact matches or near-identical titles (90%+ similar) qualify as matches

- **System Tray Menu Improvements**
  - Removed "Start App (portable)" option as it was redundant
  - Added separator lines between menu sections for better organization
  - Menu now grouped into logical sections: Main Action, Service Controls, Maintenance, Info & Links, and Exit

### Fixed
- **False Positive Prevention**
  - Fixed issue where searching terms like "Christmas" incorrectly marked all prerolls as downloaded
  - Word-based matching removed - no longer matches prerolls sharing common words
  - Significantly improved accuracy for legacy preroll detection

## [1.7.7] - 11-10-2025

### Fixed
- **Schedule Date/Time Shifting** ([#9](https://github.com/JFLXCLOUD/NeXroll/issues/9))
  - Fixed schedule dates/times randomly shifting when saving or updating
  - Schedule dates are now stored as naive datetime (local time) instead of UTC
  - Eliminated 6-hour time jumps caused by incorrect timezone conversion
  - Dates entered in schedules now remain exactly as set (e.g., Oct 31 5am stays Oct 31 5am)
- **Backup Restore Foreign Key Error** ([#10](https://github.com/JFLXCLOUD/NeXroll/issues/10))
  - Fixed database restore failing with "FOREIGN KEY constraint failed" error
  - Corrected deletion order to clear junction tables before dependent tables
  - Restore now deletes: preroll_categories → schedules → prerolls → categories → holidays
  - Backup restore operations now complete successfully without constraint violations

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
