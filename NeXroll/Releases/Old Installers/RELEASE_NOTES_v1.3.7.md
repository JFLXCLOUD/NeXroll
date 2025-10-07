# NeXroll v1.3.7 Release Notes

## UI Improvements
- Removed floating theme toggle button to prevent UI conflicts
- Users can now switch themes using the toggle in Settings → Theme
- Improved header layout with better spacing
- Fixed dark mode styling for text fields, buttons, and UI elements
- Enhanced readability in dark mode for all form inputs and dropdowns
- Fixed Plex server label colors in dashboard to use theme-aware colors
- Fixed preroll description text colors to adapt properly to dark/light themes
- Added proper dark mode styling for all input fields throughout the application

## Technical Changes
- Updated version to 1.3.7
- Removed unused theme toggle button component and CSS styles
- Fixed hardcoded colors in CSS to use CSS custom properties for proper theme support
- Added theme-aware CSS variables for success/error colors and text secondary colors
- Fixed Plex server status colors and preroll description colors to use CSS variables
- Added proper nx-input class to all input fields for consistent dark mode styling
- Optimized frontend bundle size

## Bug Fixes
- Fixed theme toggle button overlapping with dashboard navigation button
- Fixed text readability issues in dark mode for input fields and UI components
- Fixed rockerswitch toggle colors not adapting to dark mode
- Fixed Plex server label colors in dashboard not adapting to dark/light themes
- Fixed preroll description text colors not adapting to dark/light themes
- Fixed various input fields missing proper dark mode styling classes
- Fixed dropdown menu items not adapting to dark/light themes
- Fixed placeholder text in input fields to be lighter in dark mode for better readability

## Known Issues
- Genre-based preroll mapping is experimental and may not work with all Plex clients
- Windows environment variable setup requires manual application

## Installation
Run the `NeXroll_Installer_1.3.7.exe` installer to upgrade from previous versions.

## Compatibility
- Windows 10/11
- Plex Media Server
- Experimental genre feature requires Windows and specific Plex clients