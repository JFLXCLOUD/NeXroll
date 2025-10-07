# NeXroll v1.3.6 Release Notes

## New Features
- **Genre-based Preroll Mapping**: Added experimental feature to automatically apply prerolls based on Plex media genres
  - Master toggle with rockerswitch UI for enabling/disabling the feature
  - Map Plex genres (e.g., Horror, Comedy) to NeXroll categories
  - Automatic genre-based preroll application when media is played
  - Configurable settings for priority mode and override TTL
  - Setup instructions and Windows environment variable application button
  - **Note**: This feature is experimental and currently only works with certain Plex clients

## UI Improvements
- Enhanced Settings page with better organization
- Added visual feedback for disabled controls when features are toggled off
- Improved genre mapping interface with test and apply functionality

## Technical Changes
- Updated version to 1.3.6
- Added conditional disabling of UI controls based on feature toggles
- Enhanced CSS with rockerswitch toggle styling

## Bug Fixes
- None in this release

## Known Issues
- Genre-based preroll mapping is experimental and may not work with all Plex clients
- Windows environment variable setup requires manual application

## Installation
Run the `NeXroll_Installer_1.3.6.exe` installer to upgrade from previous versions.

## Compatibility
- Windows 10/11
- Plex Media Server
- Experimental genre feature requires Windows and specific Plex clients