# NeXroll v1.3.8 Release Notes

## Dashboard Enhancements
- Added "Current Category" card showing the currently applied preroll category and playback mode
- Added "Upcoming Schedules" card displaying the next 3 scheduled category changes with execution times
- Enhanced "Schedules" card to show "X of Y active" instead of just total count
- Enhanced "Prerolls" card to show how many categories have prerolls assigned
- Made all dashboard cards scrollable when content exceeds maximum height

## UI Improvements
- Improved dashboard information density with additional monitoring cards
- Better visibility into upcoming automated schedule changes
- Clear indication of current active category and storage distribution
- Enhanced schedule status display with active/total breakdown

## Technical Changes
- Updated version to 1.3.8
- Added backend endpoint `/settings/active-category` for current category information
- Frontend computes upcoming schedules and storage breakdown from existing data
- No additional backend API calls required for new dashboard features

## Bug Fixes
- Fixed dashboard refresh cycle to properly update new cards

## Known Issues
- Genre-based preroll mapping is experimental and may not work with all Plex clients
- Windows environment variable setup requires manual application

## Installation
Run the `NeXroll_Installer_1.3.8.exe` installer to upgrade from previous versions.

## Compatibility
- Windows 10/11
- Plex Media Server
- Experimental genre feature requires Windows and specific Plex clients