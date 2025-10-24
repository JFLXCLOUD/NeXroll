# Changelog

All notable changes to this project will be documented in this file.

## [1.5.12] - 2025-10-23

### 🎨 New Features

#### Dashboard Customization
- **Card Rearrangement**: Implemented full drag-and-drop support for dashboard cards using `@dnd-kit`. Users can now reorder dashboard sections (Plex Integration, Preroll Management, Schedules, Categories, Holiday Presets, File Management) by dragging them to new positions
- **Section Visibility Toggle**: Added "Customize Dashboard" button with a visibility menu to show/hide individual dashboard sections
- **Persistent Layout**: Dashboard layout preferences are automatically saved to browser localStorage and restored on next session

#### Timezone Management
- **Timezone Selection**: New timezone picker in settings allowing users to select their local timezone
- **Schedule Accuracy**: Timezone selection ensures all schedule times and date-based prerolls are calculated correctly based on the user's location
- **Backend Support**: Full timezone-aware scheduling backend integration

### 🔧 UI/UX Improvements

#### Button Relocations
- **Dashboard Header Reorganization**: Moved "Customize Dashboard" button to dashboard header for better visibility and accessibility
- **Settings Layout**: Improved button placement and spacing throughout the application for better UX flow
- **Action Button Consolidation**: Streamlined action buttons for clearer user interactions

#### Visual Fixes
- **Dropdown Arrow Styling**: Fixed duplicate/misaligned dropdown arrows by correcting CSS background property usage
- **List View Background**: Restored missing background styling for preroll list views
- **Card Height Consistency**: Reduced dashboard card min-height from 200px to 140px for uniform card heights across all dashboard sections
- **Line Spacing Optimization**: Fixed Current Category card line spacing by implementing compact line-height (1.2) and reduced margins for better visual hierarchy
- **Dashboard Card Spacing**: Standardized paragraph spacing and margins across all dashboard cards for consistent appearance

#### Dashboard Updates
- **Genre Card Removal**: Removed "Recent Genres" card from default dashboard display for cleaner interface
- **Card Count**: Dashboard now displays 7 primary information cards instead of 8

### 🐛 Bug Fixes

#### Preroll Management
- **Delete Preroll Function**: Fixed 500 error when attempting to delete prerolls with foreign key constraints
  - Solution: Implemented raw SQL deletion with temporary foreign key constraint disabling
  - Cleanup: Automatically removes preroll references from all schedule JSON fields before deletion
  - Robustness: Added comprehensive error handling and transaction management

#### Database Operations
- **Foreign Key Constraint Handling**: Properly manages SQLite foreign key constraints during deletion operations
- **Transaction Integrity**: Improved database transaction handling to prevent orphaned records

### 📦 Build & Deployment

- Frontend: Compiled successfully with clean build
- PyInstaller: All 4 executables built successfully
  - `neXroll.exe` (Main Application)
  - `NeXrollService.exe` (Background Service)
  - `NeXrollTray.exe` (System Tray Integration)
  - `setup_plex_token.exe` (Plex Setup Utility)
- NSIS Installer: `NeXroll_Installer_1.5.12.exe` created (96.5% compression, ~91.67 MB)

### 🔐 Security & Stability

- Enhanced error handling for preroll deletion with detailed logging
- Improved database constraint management
- Transaction rollback support for failed operations
- Proper connection cleanup and resource management

### 📝 Technical Details

**Key Changes:**
- Added `@dnd-kit/core`, `@dnd-kit/sortable`, and `@dnd-kit/utilities` for drag-and-drop functionality
- Enhanced CSS with compact line-height rules and improved spacing calculations
- Implemented localStorage persistence for dashboard layout configuration
- Improved backend delete endpoint with raw DBAPI connection access
- Added PRAGMA foreign_keys temporary disabling for safe preroll deletion

**Files Modified:**
- `frontend/src/index.css` - CSS styling improvements
- `frontend/src/App.js` - Dashboard customization and drag-and-drop logic
- `backend/main.py` - Delete preroll endpoint with improved constraint handling
- `package.json` - Added drag-and-drop dependencies

### ⚠️ Known Limitations

- Dashboard card maximum height is 140px with compact spacing (by design for dashboard density)
- Foreign key constraints are temporarily disabled only during preroll deletion operations
- Timezone changes require application restart to take full effect

### 🙏 Credits

This release includes improvements to the dashboard user experience, critical bug fixes for preroll deletion, and enhanced timezone support for accurate schedule management.

---

For previous versions, please refer to GitHub releases page.
