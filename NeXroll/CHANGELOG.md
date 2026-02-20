# Changelog

## [1.11.0] - 02-19-2026

### New Feature 1: Coming Soon List Generator

Generate dynamic video prerolls that showcase your upcoming movies and TV shows from Radarr and Sonarr.

#### Features
- **Two Layout Styles**:
  - **List Mode** - Clean text-only layout with titles and release dates
  - **Grid Mode** - Visual poster grid with movie/show artwork (220x330px posters)
- **Content Sources** - Choose from Movies only, Shows only, or Both
- **Color Customization** - Full control over background, text, and accent colors
- **Configurable Duration** - Set video length from 5 to 20 seconds
- **Max Items** - Control how many titles are displayed (4-12 items)
- **Auto-regeneration** - Automatically re-generate when NeX-Up syncs with Radarr/Sonarr
- **System Category Integration** - Videos auto-register to "Coming Soon Lists" category
- **Sequence Builder Ready** - Generated videos appear in available prerolls for sequences
- **Video Preview Modal** - Watch generated videos in a centered modal overlay

#### Technical Details
- Uses FFmpeg for video generation
- Automatically downloads poster images for grid layout
- Falls back to text layout if poster download fails
- Staggered fade-in animations for each item

---

### New Feature 2: Authentication System

Secure NeXroll access with API keys and optional username/password authentication.

#### API Key Authentication
- **Generate API Keys** - Create unique API keys for external access (nx_... format)
- **API Key Management UI** - View, create, revoke API keys in Settings > API Keys tab
- **Key Permissions** - Scoped permissions (read-only, full access)
- **Key Expiration** - Optional expiration dates (24h, 7d, 30d, 90d, 1y, never)
- **Secure Storage** - SHA256 hashed keys in database (only prefix stored for display)

#### External API Endpoints
- `GET /external/status` - System status and connection info
- `GET /external/prerolls` - List all prerolls
- `GET /external/schedules` - List all schedules
- `GET /external/now-showing` - Current active category, preroll string, active schedules
- `GET /external/active-schedules` - Detailed info on currently active schedules
- `GET /external/categories` - All categories with preroll counts
- `GET /external/coming-soon` - Upcoming movies/TV from NeX-Up (source, limit params)
- `GET /external/sequences` - All saved sequences
- `POST /external/sync-plex` - Trigger Plex sync (requires full access)
- `POST /external/categories` - Create a new category (requires full access)
- `POST /external/prerolls/register` - Register existing video as preroll (requires full access)
- `POST /external/prerolls/{id}/assign-category/{category_id}` - Assign preroll to category
- `POST /external/schedules` - Create a new schedule (requires full access)
- `DELETE /external/schedules/{id}` - Delete a schedule (requires full access)
- `PUT /external/schedules/{id}/toggle` - Enable/disable schedule (requires full access)
- `POST /external/apply-category/{id}` - Apply category to Plex immediately

#### Username/Password Authentication
- **User Accounts** - Create admin and user accounts
- **Login Page** - Login form before accessing NeXroll
- **Session Management** - Secure session tokens with expiration
- **Password Hashing** - Secure bcrypt password storage
- **Remember Me** - Optional "remember me" for longer sessions (30 days)
- **Logout** - Secure logout functionality

#### Security Features
- **HTTPS Support** - Configurable "Require HTTPS" setting in auth settings
- **CORS Configuration** - FastAPI middleware with configurable origins
- **Failed Login Protection** - Account lockout after 5 failed attempts (15 min)
- **Audit Log** - Log authentication events with viewer UI

---

### New Feature 3: Enhanced Update System

Improved update detection with configurable checking and notifications.

#### Update Detection
- **Auto-Check on Startup** - Check for updates when NeXroll starts
- **Configurable Check Interval** - How often to check (startup, hourly, daily, weekly, never)
- **Pre-release Channel** - Option to include beta/pre-release versions
- **Changelog Display** - Show what's new with markdown rendering

#### Update Notifications
- **Dashboard Notification** - Prominent update card on dashboard overview
- **Version Comparison** - Show current vs available version
- **Update Notes Summary** - Release notes with markdown support
- **Dismiss/Remind Later** - Dismiss synced to backend for persistence

---

### New Feature 4: Enhanced Logging System

Better debugging and troubleshooting capabilities.

#### Log Management
- **Log Viewer UI** - View logs directly in NeXroll web interface (Settings > Logs tab)
- **Log Level Filtering** - Filter by DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Search** - Search through log entries by message text
- **Log Export** - Download logs as JSON or CSV file
- **Log Rotation** - Automatic cleanup of old logs (configurable retention days)

#### Structured Logging
- **JSON Log Format** - Structured logging with details JSON field
- **Request Logging** - Log all API requests with timing (duration_ms)
- **Category-based Logging** - Logs categorized by: system, scheduler, api, user, plex, jellyfin, nexup
- **Request ID Correlation** - Each request gets unique ID for log correlation

#### Log Settings
- **Log Level Configuration** - Set minimum log level (DEBUG, INFO, WARNING, ERROR)
- **Retention Period** - Configure how many days to keep logs (1-365)
- **Toggle Database Logging** - Enable/disable logging to database
- **Toggle Request Logging** - Enable/disable API request logging
- **Toggle Scheduler Logging** - Enable/disable scheduler activity logs
- **Toggle API Logging** - Enable/disable external API call logs

#### Log Endpoints
- `GET /logs` - Get logs with filtering (level, category, search, limit)
- `GET /logs/stats` - Get log statistics (counts by level/category)
- `GET /logs/export` - Export logs as JSON or CSV
- `DELETE /logs` - Clear old logs
- `GET /logs/settings` - Get logging settings
- `PUT /logs/settings` - Update logging settings

---

### New Feature 5: Filler Category

A global fallback system to fill gaps in your schedule when no schedules are active.

#### What It Does
- **Fills Schedule Gaps** - Automatically applies prerolls when NO schedules are active
- **Different from Per-Schedule Fallback** - Per-schedule fallback only applies when THAT schedule ends; Filler applies globally when ALL schedules are inactive
- **Three Filler Types**:
  - **Category** - Use any category as the gap filler
  - **Sequence** - Use a saved NeX-Up sequence as the gap filler
  - **Coming Soon List** - Use a generated Coming Soon List (grid or list layout) as the gap filler

#### Configuration
- Settings > General > Filler Category section
- Toggle to enable/disable
- Select filler type and configure the source
- Respects Coexistence Mode and Clear When Inactive settings

#### Priority Order
1. **Active Schedule** - Highest priority, schedule's category is applied
2. **Per-Schedule Fallback** - If schedule has a fallback, it's used when that schedule ends
3. **Filler Category** - Global fallback when NO schedules are active and no per-schedule fallback exists
4. **Unchanged** - If filler is disabled, Plex prerolls remain unchanged

#### API Endpoints
- `GET /settings/filler` - Get filler settings
- `PUT /settings/filler` - Update filler settings (enabled, type, category_id, sequence_id, coming_soon_layout)

---

### Improvements

#### Dashboard Enhancements
- **Weekly Calendar Preview** - Mini calendar on Dashboard Overview showing this week's scheduled prerolls
- **View Full Calendar Button** - Quick navigation to the full Calendar View from dashboard
- **Filler Category Display** - Shows filler category events on days with no active schedules

#### Sticky Sub-Navigation
- **All Sub-Navs Now Stick** - Dashboard, Schedules, NeX-Up, and Settings sub-navigation bars properly stick below the main header when scrolling
- **Unified Positioning** - Consistent 70px offset for all sub-navigation bars

#### Coming Soon List Generator
- **Cleaner Filenames** - Generated videos now use simpler filenames: `coming_soon_grid.mp4` and `coming_soon_list.mp4`

#### Docker & Deployment
- **Docker Beta Channel** - Added beta tag support for pre-release Docker images
- **bcrypt Dependency** - Added bcrypt>=4.0.0 to requirements.txt for password hashing
- **GitHub Workflow** - Updated docker-build.yml with automatic pre-release detection and conditional tagging

---

### Bug Fixes

- **Admin Role Fix** - Fixed issue where creating a user with Admin role would save as User instead. The RegisterRequest model was missing the `role` field.
- **View Full Calendar Navigation** - Fixed "View Full Calendar" button not switching to Calendar View properly
- **Schedule from Sequence Fix** - Fixed clicking "Schedule" on a saved sequence creating a duplicate sequence in the library. Now properly tracks the loaded sequence ID and hides the name/description fields.
- **Dashboard Data Loading** - Filler settings and NeX-Up trailer counts now load on startup so they display immediately on the Dashboard and Calendar without needing to visit Settings/NeX-Up pages first.

---

## [1.10.14] - 02-14-2026

### New Feature: NeX-Up - Radarr & Sonarr Trailer Integration

A brand new feature that brings the movie theater "Coming Soon" experience to your Plex server. Automatically download and play trailers for upcoming movies and TV shows before your content.

#### Radarr & Sonarr Connections
- **One-Click Integration** - Connect to Radarr and Sonarr with URL and API key
- **Automatic Discovery** - Fetches movies/shows scheduled to release within your configured timeframe
- **Smart Cleanup** - Automatically removes trailers when content is added to your library
- **Separate Storage** - Trailers organized in `/movies` and `/tv` subdirectories

#### Automatic Trailer Downloads
- **YouTube Integration** - Downloads trailers automatically from YouTube
- **Cookie File Support** - Use exported cookies for age-restricted or region-locked content
- **Quality Settings** - Choose 720p, 1080p, 4K, or best available
- **Storage Limits** - Configure max trailers and storage allocation

#### Dynamic Preroll Generator
- **Custom Intro Videos** - Create "Coming Soon to [Your Server]" intro clips
- **Multiple Templates** - Cinematic, Neon, Minimal, Retro, Elegant styles
- **Color Themes** - 5 color themes (Midnight, Sunset, Forest, Royal, Monochrome)
- **Live Preview** - Watch your generated intro directly in the browser
- **FFmpeg Powered** - High-quality video generation

#### Sequence Builder Presets
- "Coming Soon + Movie Trailers" - Intro followed by random movie trailers
- "Coming Soon + TV Trailers" - Intro followed by random TV trailers
- "Mixed: Movies + TV" - Intro with both movie and TV trailers
- "Theater Experience" - Full cinema experience with 4 trailers

#### NeX-Up Page Organization
- **Connections Tab** - Radarr/Sonarr management with quick sync buttons
- **Your Trailers Tab** - Manage movie and TV trailers with storage info
- **Settings Tab** - YouTube cookies, storage path, TMDB API, rate limiting
- **Generator Tab** - Dynamic preroll generator and sequence builder

### Added

- **Custom Styled Confirmation Dialogs** - All browser confirmation dialogs replaced with themed modal dialogs. Supports warning, danger, info, success, and error styles with icons, smooth animations, and async/await handling.

#### System & Files Backup (Enhanced)
- **Comprehensive System Backup** - "Files Backup" renamed to "System & Files Backup" - now creates a complete system snapshot
- **Database Included** - Backup includes both SQLite database file (nexroll.db) and JSON export for cross-version compatibility
- **All Preroll Videos** - Every preroll video file is included in the backup ZIP
- **Thumbnails Included** - All generated thumbnails preserved in backup
- **Settings & Configuration** - Application settings exported with the backup
- **Streaming Download** - Large backups now use FileResponse streaming to prevent memory issues
- **Smart Restore** - Restore process handles both new comprehensive format and legacy backups
- **Progress Tracking** - Real-time progress indicators during backup creation and restore operations
- **Button Disable During Operations** - UI prevents accidental double-clicks during backup/restore

#### Video Quality Dashboard
- **New Dashboard Tile** - "Video Quality" card shows resolution distribution of your preroll library
- **Interactive Bar Chart** - Visual breakdown of 4K, 1080p, 720p, 480p, and other resolutions
- **Click to Filter** - Click any resolution bar to filter prerolls by that quality
- **Color-Coded Bars** - Each resolution has a distinct color for quick identification

#### Community Prerolls Stale Indicator
- **"Currently Showing" Tile Rename** - Currebt Category dashboard tile renamed to "Currently Showing"
- **Stale Data Warning** - Orange indicator appears when community data is older than 24 hours
- **Last Updated Timestamp** - Shows when community prerolls were last refreshed

#### YouTube Bot Detection Warning
- **New Info Box in NeX-Up Settings** - Explains YouTube's aggressive bot detection
- **VPN Guidance** - Suggests refreshing VPN IP if downloads fail
- **Rate Limiting Tips** - Wait between downloads to avoid blocks
- **Cookie Instructions** - Export from Incognito using cookies.txt extension

#### Dashboard Quick Actions
- **NeX-Up Sync Button** - One-click sync for both Radarr and Sonarr trailers
- **Real-Time Progress** - Shows which trailer is downloading with progress counter
- **Spinner Animations** - All Quick Action buttons now animate properly

#### Video Scaling Page
- **Dedicated Dashboard Sub-Page** - New "Video Scaling" page accessible from Dashboard menu
- **Resolution Stats Cards** - Visual breakdown showing count of 4K, 1080p, 720p, 480p, SD, and unknown resolution prerolls
- **Click-to-Filter** - Click any resolution card to filter the preroll list
- **Bulk Selection** - Multi-select prerolls with "Select All" and "Clear Selection" buttons
- **Batch Scaling** - Scale multiple prerolls to target resolution (1080p, 720p, or 480p) in one operation
- **Progress Tracking** - Real-time progress indicator shows current file being processed
- **Smart Filtering** - Excludes NeX-Up trailers and dynamic prerolls from scaling (they have their own workflows)
- **Scale Prerolls to Lower Resolutions** - Transcode to 1080p, 720p, or 480p
- **One-Click Scaling in Edit Modal** - Quick access to scale individual prerolls
- **High Quality Settings** - Uses FFmpeg libx264, CRF 18, slow preset
- **720p Recommended** - Ideal for remote streaming without transcoding

#### Schedule Conflict Detection
- **Same-Priority Warnings** - Orange badges when exclusive schedules conflict
- **Calendar Indicators** - Day, Week, and Month views show conflicts
- **Priority Visualization** - Higher priority schedules shown with lock icon, lower priority greyed out

### Improved

- **Add Prerolls to Category UI** - Replaced cluttered dropdown with a searchable thumbnail grid. Multi-select prerolls with visual checkmarks and add them all at once.
- **Schedules Page Organization** - Schedules are now organized into three clear sections: "Currently Running" (active right now), "Enabled Schedules" (ready but not running), and "Disabled Schedules" (paused).
- **Category Management Styling** - Categories now organized into three sections: "Scheduled Categories", "Categories with Prerolls", and "Empty Categories". Added colored accent borders on cards, section headers with icons and counts, and a quick stats bar showing totals at a glance.
- **Dashboard Card Icons** - All dashboard cards now display lucide icons in their headers for visual consistency (Servers, Prerolls, Storage, Schedules, Scheduler, Current Category, Upcoming, Genre Prerolls, Community, NeX-Up).
- **Category Grid Condensed View** - Category cards in grid view are now more compact with reduced padding, no duplicate buttons, and clickable cards to edit. Minimum width reduced to 220px for better space efficiency.
- **Backup & Restore Overhaul** - Complete redesign of the backup/restore interface with progress indicators, card-based layout, and clearer button alignment.

#### yt-dlp & Deno Updates
- **yt-dlp 2026.2.4** - Latest version with improved YouTube extraction
- **Deno 2.6.8** - Required JavaScript runtime for YouTube extraction
- **Better Error Messages** - Clear guidance when YouTube blocks downloads

#### Installer
- **Launch Tray After Install** - Option to start NeXrollTray immediately
- **Fixed Post-Install Context** - Network drives accessible on first launch

### Fixed
- **Category Grid Dropdown Z-Index** - Fixed issue where the three-dot menu options in Category Management grid view appeared behind neighboring category cards.
- **Category Preroll Count Bug** - Fixed issue where non-primary category assignments showed 0 prerolls. The category stats now correctly count prerolls added via many-to-many associations.
- **Category Dropdown Sorting** - All category dropdown menus throughout the app now display categories in alphabetical order.
- **Fixed Folder Picker** - Custom preroll location now saves correctly

#### Schedule Management
- **Load Saved Sequences** - Dropdown loads sequences when creating schedules
- **Improved Edit Modal** - Better layout with 900px width
- **Duplicate Prevention** - No more duplicate sequences when using saved sequences

### Fixed
- Fixed KeyError when YouTube download fails (proper error dict handling)
- Fixed dynamic preroll theme not saving after generation
- Fixed gradient backgrounds to match CSS preview
- Fixed Radarr/Sonarr auto-sync KeyError with dictionary keys
- Fixed color themes working for all template types
- Fixed video preview caching issues
- Fixed sequence validator for 'sequential' block type

### Removed
- **Genre-based Preroll Mapping** - Removed experimental feature that never fully worked

---

## [1.9.8] - 01-08-2026

### Fixed
- **Timezone Drift Bug** - Fixed critical bug where schedules would shift backward by 7-8 hours on each save for users in GMT-7/8 timezones
  - Schedules are now stored as naive local datetimes with no timezone conversion
  - What you enter is exactly what gets saved and displayed
  - Scheduler now uses local time for all comparisons

- **Random Order Default** - Fixed bug where new schedules defaulted to Sequential even when Random was visually selected
  - The "Random" playback option now correctly defaults to enabled when creating a new schedule

### Changed
- **Time Display Format** - Dashboard "Upcoming Schedules" card now shows times without seconds (e.g., "1/1/2026, 7:00 AM" instead of "1/1/2026, 7:00:00 AM")

- **Community Prerolls URL** - Updated community prerolls library URL from prerolls.typicalnerds.uk to prerolls.uk

### Added
- **Reddit Community** - Added r/NeXroll subreddit link to footer and README

- **Coexistence Mode** - New setting that allows NeXroll to work alongside other preroll managers (like Preroll Plus)
  - When enabled, NeXroll only manages prerolls during active schedules
  - Outside of scheduled times, NeXroll stays hands-off, allowing other preroll managers to control Plex
  - Found in Settings → NeXroll Settings → Coexistence Mode

- **Clear When Inactive** - New setting to clear prerolls when no schedule is active
  - When enabled, NeXroll will clear the Plex preroll field outside of scheduled times
  - No prerolls will play when you don't have an active schedule
  - Found in Settings → NeXroll Settings → Clear Prerolls When Inactive

- **Daily Calendar View** - New "Day" view option in the calendar
  - Shows an hourly breakdown of the selected day with all active schedules
  - Displays schedule conflicts, exclusive schedules, and blend mode at each hour
  - Click any day in Month view to jump to that day's hourly view
  - Visual indicators for current hour when viewing today
  - Night hours (10 PM - 6 AM) are subtly highlighted


---

## [1.9.6] - 12-21-2025

### Fixed
- **Calendar Month View Conflict Detection** - Fixed false conflict indicators showing on days with exclusive schedules
  - Days with a time-restricted exclusive schedule (e.g., Adult Swim 10pm-3am) plus other schedules no longer show conflict badges
  - Orange conflict borders only appear when there's a true scheduling conflict (multiple non-exclusive schedules competing)
  - Exclusive mode properly resolves priority - no conflict exists when exclusive handles the time window

- **Blend Mode Display for Single Schedules** - Fixed single schedules incorrectly showing as "blended"
  - Single schedules with `blend_enabled` no longer display the shuffle/blend icon
  - Blend indicator now only appears when 2+ schedules are actually blending together
  - Improves calendar clarity by showing blend mode only when meaningful

### Technical
- Refactored conflict detection in `App.js` to only set `hasConflict` when multiple exclusive schedules compete
- Removed erroneous `hasBlend = true` for single-schedule scenarios
- Blend mode requires `contentSchedules.length > 1` before displaying blend indicators

---

## [1.9.5] - 12-21-2025

### Fixed
- **Critical Timezone Bug in Time Range Schedules** - Fixed bug where time range schedules (e.g., 10pm-3am) were incorrectly applying at the wrong times due to timezone mismatch
  - **Root Cause**: Time ranges stored in local time were being compared against UTC time
  - Example: 8:05pm local = 1:05am UTC, which fell inside the 10pm-3am overnight range when compared in UTC
  - Now properly converts UTC to user's configured timezone before comparing with time ranges
  - Impact: Time range schedules now correctly activate/deactivate at the specified local times

- **Calendar Week View Time-Restricted Exclusive Display** - Fixed misleading calendar display when time-restricted exclusive schedules overlap with blending schedules
  - **Issue**: When an exclusive schedule with a time range (e.g., Adult Swim 10pm-3am) overlapped with blended schedules (e.g., Christmas + New Year all day), the calendar showed the blended schedules as crossed out "losers" all day
  - **Fix**: Calendar now correctly shows:
    - Time-restricted exclusive schedules with their time range displayed (e.g., "Adult Swim (22:00-03:00)")
    - Non-exclusive blending schedules as ACTIVE (with blend icon) since they run outside the exclusive's time window
    - Day headers show both blend and exclusive icons when both modes apply at different times
    - Proper tooltips explaining when each schedule is active
  - Impact: Visual calendar now accurately reflects that blended schedules ARE active during most of the day

- **Calendar Month View Time-Restricted Exclusive Display** - Applied same fix to monthly calendar view
  - Day cells now show appropriate borders: purple for blend mode, red for exclusive, orange only for true conflicts
  - Time-restricted exclusive with blend mode shows purple border (blend is primary mode most of day)
  - Added exclusive mode badge indicator (lock icon) with clock icon for time-restricted exclusive
  - Conflict badge only shows when there's a true conflict (no blend mode, no exclusive)
  - Hover effects properly restore correct shadow color based on day status

### Technical
- Added `pytz` import to `scheduler.py`
- Updated `_is_schedule_active()` to convert UTC now to user's local timezone before time range comparison
- Updated `_matches_pattern()` with same timezone conversion fix
- Updated `_apply_schedule_win_lose_logic()` in `main.py` with same fix
- Day-of-week checks also now use local time
- Calendar week view now tracks `nonExclusiveWinner` for schedules that win outside exclusive time windows
- Added `exclusiveHasTimeRange` tracking to properly style time-restricted exclusive schedules
- Updated span rendering with differentiated borders: dashed red for time-restricted exclusive, solid red for full-day exclusive, purple for blend mode
- Monthly view calendar now includes `exclusiveHasTimeRange`, `nonExclusiveWinnerScheds`, and `nonExclusiveWinner` tracking
- Priority sorting now considers higher priority values first, then fallback to end date/start date/ID

---

## [1.9.4] - 12-20-2025

### Fixed
- **Daily Schedule Time Range Bug** - Fixed critical bug where daily schedules with time ranges (e.g., 10pm-3am) remained active outside their time window
  - Schedules with `timeRange` in recurrence pattern now properly check current time
  - Overnight ranges (e.g., 22:00-03:00) are handled correctly
  - Schedules now correctly become inactive when outside their time window
  - Impact: Exclusive nightly schedules (like Adult Swim 10pm-3am) now properly switch back to other active schedules when their time window ends

### Technical
- Enhanced `_is_schedule_active()` method to check `recurrence_pattern.timeRange` in addition to date range
- Implemented proper overnight time range detection (start > end means overnight wraparound)
- Updated `_matches_pattern()` to actually check time ranges (was always returning True)
- Verbose logging added for schedule time window checks

---

## [1.9.3] - 12-20-2025

### Added
- **Schedule Priority System** (1-10)
  - New priority slider in schedule creation/editing form
  - Higher priority schedules win when multiple schedules overlap
  - Priority badge (P6, P7, etc.) shown in schedule list views when not default (5)
  - Color-coded badges: red (8-10), orange (5-7), gray (1-4)
  - Tie-breaking: highest priority → earliest end date → earliest start → lowest ID
  - Impact: Fine-grained control over which schedule takes precedence during overlaps

- **Exclusive Schedule Mode** 🔒
  - New "Exclusive" checkbox in schedule creation/editing form
  - When active, the schedule wins exclusively (no blending with other schedules)
  - Overrides blend mode - exclusive schedules never blend, even if other schedules have blend enabled
  - Multiple exclusive schedules: highest priority exclusive wins
  - Red "Exclusive" badge shown in schedule list views
  - Perfect for time-specific prerolls (e.g., nightly schedule 10pm-3am) that should override holiday schedules
  - Impact: Guaranteed schedule control for time-sensitive preroll needs

### Fixed
- **Blend Mode Delimiter** - Changed from comma (sequential/all) to semicolon (random pick one) so Plex plays 1 random preroll from the blended pool instead of all prerolls

### Technical
- Added `priority` (INTEGER DEFAULT 5) and `exclusive` (BOOLEAN DEFAULT 0) fields to Schedule model
- Database migration automatically adds columns to existing databases
- Scheduler logic updated: exclusive schedules checked first, then blend mode, then normal priority-based winner selection
- API endpoints (create/update schedule) now accept priority and exclusive parameters
- Frontend form includes priority slider and exclusive checkbox with helpful descriptions
- Visual badges for priority and exclusive in both compact and detailed schedule list views

---

## [1.9.2] - 12-19-2025

### Added
- **Schedule Blend Mode** 🔀
  - New "Blend Mode" toggle in schedule creation/editing form
  - When enabled, overlapping schedules with blend mode will mix their prerolls together
  - Perfect for combining holiday themes (e.g., Hanukkah + Christmas prerolls playing together)
  - Prerolls are interleaved from each schedule in round-robin fashion
  - Uses playlist mode (sequential) to maintain the blended order
  - For sequences: respects the count setting for random blocks
  - For categories: takes up to 3 random prerolls from each to keep playlist manageable
  - Blend mode only activates when 2+ overlapping schedules have it enabled
  - Single blend-enabled schedule falls back to normal winner-takes-all behavior
  - Impact: Create rich, multi-theme preroll experiences during overlapping holiday periods

### Technical
- Added `blend_enabled` boolean field to Schedule model
- Database migration automatically adds column to existing databases
- New `_apply_blended_schedules_to_plex()` method in scheduler for blend logic
- API endpoints (create/update schedule) now accept blend_enabled parameter
- Frontend form includes blend mode checkbox with helpful description

---

## [1.9.0] - 12-16-2025

### Added
- **Calendar Week View Conflict Detection**
  - Full conflict detection for the Week view showing when multiple schedules overlap
  - Winner/loser logic using backend priority rules: ends soonest → started earliest → lowest ID
  - Visual indicators: Crown icon (👑) for winning schedule, strikethrough for overridden schedules
  - Day headers highlight conflict days with orange warning indicators
  - "Schedule Conflicts Detected" banner when any day has conflicts
  - Legend explaining conflict resolution rules
  - Tooltips show "ACTIVE (wins conflict)" or "OVERRIDDEN" status on hover
  - Impact: Users can now clearly see which schedule takes priority when conflicts occur

- **Smart Fallback Category Selection**
  - Fallback categories now pick the closest schedule based on date proximity
  - Calendar days without active schedules show the fallback from the nearest schedule
  - Properly handles year-wrapping schedules (e.g., Christmas Dec 1 - Jan 15)
  - Fixed issue where Christmas fallback would show in February instead of Valentine's fallback
  - Both month view and yearly overview use the same smart proximity-based logic
  - Impact: Fallback categories are now contextually appropriate for each time period

- **Sequence Cards Playback & Preroll Count**
  - Added Play button to Saved Sequences cards for quick preview
  - Preroll count badge shows total number of prerolls in each sequence
  - SequencePreviewModal integration for full playback preview
  - Improved card layout with better spacing and visual hierarchy
  - Updated tips box: ".nexbundle" changed to ".zip bundle" for clarity

- **Modern SequenceTimeline Component**
  - Complete visual overhaul with lucide-react icons
  - Gradient background colors for different block types
  - Header stats badges showing blocks, prerolls, and total duration
  - Film icon for fixed blocks, Shuffle for random, ListOrdered for sequential
  - Play icon for preroll blocks, Layers for queue/sequence
  - Clock icon for separators, improved number badges
  - Better visual distinction between block types

- **Community Prerolls Icon Modernization**
  - Replaced all emoji icons with lucide-react components
  - FileText icon for Fair Use Policy button
  - AlertTriangle/Sparkles/Lightbulb for status indicators
  - Library icon for indexed count, Link icon for matched count
  - Search icon in search bar and buttons
  - Film icon for preroll cards and empty states
  - User/FolderOpen/Clock icons for metadata display
  - Play/Eye icons for preview buttons
  - CheckCircle/Plus icons for category toggle
  - Loader2 spinner for loading states
  - Impact: Consistent, professional appearance across all platforms

- **Holiday Browser Feature**
  - Browse holidays from 100+ countries powered by Nager.Date API
  - Search holidays by name across all available countries
  - Filter by country with dropdown selector (200+ countries available)
  - View holidays by year with past/future year navigation
  - Holiday cards display: name, local name, date, holiday types
  - One-click "Use This Holiday" button to populate schedule creation form
  - Impact: Simplifies holiday schedule creation with accurate international holiday data

### Changed
- **UI/UX Enhancements**
  - All icons now use lucide-react for consistent rendering across platforms
  - Improved spacing and layout in sequence cards
  - Better visual hierarchy in calendar conflict displays
  - Modernized Community Prerolls interface with proper icon alignment

### Fixed
- **Calendar Fallback Display Bug**
  - Fixed yearly overview showing ALL fallback categories on empty days
  - Now correctly shows only ONE fallback from the nearest relevant schedule
  - February days now show Valentine's fallback instead of Christmas fallback

- **Week View Missing Conflict Indicators**
  - Week view now properly detects and displays schedule conflicts
  - Added winner/loser visual states matching month view behavior

### Technical
- **Dependencies**
  - Added Eye, X, User, RefreshCcw to lucide-react imports
  - Tree-shakeable imports ensure minimal bundle impact

---

## [1.8.9] - 12-11-2025

### Added
- **Holiday Browser Feature**
  - Browse holidays from 100+ countries powered by Nager.Date API
  - Search holidays by name across all available countries
  - Filter by country with dropdown selector (200+ countries available)
  - View holidays by year with past/future year navigation
  - Holiday cards display: name, local name, date, holiday types (Public/Bank/School/Observance)
  - Fixed/Variable date indicators for recurring holidays
  - Color-coded badges for holiday types (green for Public holidays)
  - One-click "Use This Holiday" button to populate schedule creation form
  - Integrated help section explaining all features and workflow
  - Past holidays automatically disabled to prevent scheduling expired dates
  - **Workflow**: Click holiday → Form pre-fills with name, yearly type, dates → Select category → Adjust dates if needed → Create schedule
  - Impact: Simplifies holiday schedule creation with accurate international holiday data

- **Professional Icon System**
  - Replaced all emojis with Lucide Icons for consistent, professional appearance
  - 27 unique icon components integrated across the entire application
  - Icons include: Calendar, CalendarDays, CalendarPlus, Clock, Play, Edit, Save, Trash, Upload, Download, Search, and more
  - Scalable SVG icons ensure perfect rendering at any size and resolution
  - Icons automatically adapt to light/dark mode themes
  - Impact: Eliminates emoji rendering inconsistencies across different operating systems and browsers

- **Enhanced Verbose Logging System**
  - Structured log levels: DEBUG, INFO, WARNING, ERROR
  - Cached verbose setting with 5-second TTL to reduce database queries
  - Startup banner showing version, platform, paths, and environment details
  - Scheduler-specific logging functions with configurable verbosity
  - Consistent timestamp format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
  - Impact: Better debugging capabilities and cleaner log organization

### Changed
- **UI/UX Enhancements**
  - Floating help button now uses CircleHelp icon instead of emoji
  - All navigation tabs feature professional icons (Folder, Calendar, Film, Package)
  - Schedule type indicators use Calendar/CalendarDays icons
  - Action buttons (Edit, Delete, Save, Create) display icon + text for clarity
  - Help modal sections use contextual icons (Target, Edit, CheckCircle)
  - Community preroll buttons use Clock/RefreshCw icons for loading states
  - Settings buttons use appropriate icons (Search, Download, BookOpen)

### Improved
- **Visual Consistency**
  - Uniform icon sizing: 14-20px for buttons, 28px for floating help button
  - Flex layouts ensure proper icon-text alignment throughout the app
  - Star icon for primary category markers
  - CheckCircle badges for "Matched to Community" status
  - Play icons for video preview buttons
  - Package bundle size increased by only ~4KB for comprehensive icon system

### Fixed
- **Holiday Schedule Creation Bugs**
  - Fixed `TypeError: 'description' is an invalid keyword argument for Schedule` when creating holiday schedules
  - Fixed `TypeError: SQLite DateTime type only accepts Python datetime objects` by converting date strings to proper datetime objects
  - Fixed `AttributeError: 'Schedule' object has no attribute 'description'` in API response
  - Fixed error logging function name (`_error_log` → `_file_log`) that was masking actual errors
  - Impact: Holiday schedule creation now works correctly end-to-end

- **Critical: Yearly/Holiday Schedule Date Shifting Bug**
  - Fixed issue where yearly and holiday schedules were incorrectly converted to UTC timezone
  - Problem: Schedules created for Jan 1-3 would appear as Dec 31-Jan 2 due to timezone conversion (UTC-5)
  - Solution: Yearly and holiday schedules now stored as naive datetime (no timezone) since they are date-based, not time-based
  - Affected endpoints: POST `/schedules` (create), PUT `/schedules/{id}` (update), GET `/schedules` (retrieve)
  - GET endpoint now checks schedule type before applying timezone conversion
  - Time-based schedules (daily, weekly, monthly) still correctly convert to UTC
  - Impact: Calendar views now display yearly/holiday schedules on the correct dates without timezone shifting

- **Schedule Fallback Persistence Bug**
  - Fixed issue where a schedule's fallback category would persist indefinitely after the schedule ended
  - Problem: Christmas schedule fallback continued applying even after New Year's schedule became active
  - Solution: Fallback categories are now tied to the active schedule and cleared when a new schedule takes over
  - New behavior: When a schedule is active, its fallback is "armed" for when it ends. When a new schedule starts, that schedule's fallback (or none) replaces the previous one
  - Added `last_schedule_fallback` column to settings table to track fallback from most recently active schedule
  - Impact: Fallbacks now correctly transition between schedules instead of persisting indefinitely

- **Scheduler Logging and Start Issues**
  - Fixed scheduler failing to start due to circular import issues in logging functions
  - Problem: Scheduler thread would crash immediately on start, showing as "stopped" in UI
  - Solution: Replaced runtime imports with direct file writes for scheduler logging
  - Scheduler logging now writes directly to app.log without depending on main.py imports
  - Impact: Scheduler now starts reliably and logs all activity correctly

### Technical
- **Dependencies**
  - Added lucide-react ^0.560.0 for icon components
  - Tree-shakeable imports ensure minimal bundle impact
  - All icons are MIT licensed and production-ready

- **Holiday API Integration**
  - Backend endpoint: GET `/holiday-api/countries` - Returns list of 100+ countries
  - Backend endpoint: GET `/holiday-api/holidays/{country_code}/{year}` - Returns holidays for specific country/year
  - Backend endpoint: GET `/holiday-api/status` - Checks Nager.Date API availability
  - LRU cache (128 entries, 1-hour TTL) for API responses to minimize external requests
  - Nager.Date API: Free, no authentication required, JSON responses
  - Frontend: 8 state variables for modal, countries, holidays, search, loading, API status
  - Modal size: 1200px width for optimal holiday card layout (3 columns at 275px each)
  
- **Logging Functions**
  - `_file_log(message)` - Direct file logging to app.log
  - `_verbose_log(message)` - Logs with [DEBUG] prefix when verbose enabled
  - `_scheduler_log(msg, level)` - Scheduler-specific logging with level support
  - `_scheduler_verbose(msg)` - Scheduler debug logging only when verbose enabled
  - Verbose setting cached for 5 seconds to reduce database overhead
  - Startup banner logs: version, Python version, platform, frozen state, paths, environment

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
  - Access to thousands of community-curated prerolls from prerolls.uk
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
