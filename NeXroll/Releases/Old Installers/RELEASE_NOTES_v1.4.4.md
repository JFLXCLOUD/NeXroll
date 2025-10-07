# NeXroll v1.4.4 Release Notes

## What's New

### Video Preview Feature
- **Preroll Video Preview**: Added the ability to preview preroll videos directly within NeXroll. Click the "Preview" button located under each preroll in both grid and list views to open a modal window with an HTML5 video player that automatically plays the video.
- **Auto-Play Videos**: Videos now automatically start playing when the preview modal opens, providing immediate visual feedback for preroll content.
- **Modal Video Player**: Implemented a responsive modal with overlay, keyboard controls (Escape to close), and proper video controls for user interaction.

## Technical Changes
- Updated React frontend with video preview modal component
- Enhanced video serving endpoint to support externally managed prerolls
- Added autoPlay and muted attributes to video element for better user experience
- Improved frontend build process with updated video player controls

## Bug Fixes
- Fixed video serving issues for externally managed prerolls by enhancing the backend endpoint to fall back to database-stored paths
- Resolved 500 Internal Server Errors in frozen executables by properly bundling React frontend assets

## Installation
Download `NeXroll_Installer_1.4.4.exe` and run as administrator. The installer will guide you through the setup process.

## Checksums
See `CHECKSUMS_v1.4.4.txt` for SHA256 verification of the installer.

## Previous Versions
- [v1.4.3](RELEASE_NOTES_v1.4.3.md) - Loading indicators for server application operations
- [v1.4.2](RELEASE_NOTES_v1.4.2.md) - Jellyfin integration improvements and selective preroll application
- [v1.4.1](RELEASE_NOTES_v1.4.1.md) - Jellyfin Local Intros plugin integration
- [v1.4.0](RELEASE_NOTES_v1.4.0.md) - Major Jellyfin support release