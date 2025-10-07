# NeXroll v1.0.7

Release date: 2025-09-19

## Downloads

- Installer (recommended): NeXroll_Installer.exe (attached to this GitHub Release)
- Optional standalone binaries (advanced/manual setups): NeXroll.exe, NeXrollService.exe, NeXrollTray.exe, setup_plex_token.exe

## Highlights

### UI
- Browser tab consistently shows “NeXroll” in both packaged and dev modes.
- Public template title/description and PWA names updated to “NeXroll”.
- One-time runtime guard enforces document.title = "NeXroll".
- Cache-busting headers for “/”, “/index.html”, and “/manifest.json” prevent stale “React App” titles from cache.

### System Tray
- “Check for Updates” and “About” dialogs are now foreground, topmost, task-modal, and reliably closable.

### Thumbnails
- Dashboard button to Reinitialize Thumbnails across your library.
- On-demand thumbnail generation endpoint with legacy route compatibility.
- Silent ffmpeg/ffprobe execution (no flashing console windows).

### Scheduling and Presets
- Optional fallback category on schedules (no 422 on null).
- Holiday Presets initializer creates per-holiday categories and preset date ranges for easy scheduling.

### Packaging and Installer
- Windows installer updated to v1.0.7.
- Optional components: Windows Service, Stable Token setup, Startup shortcut, FFmpeg via winget, Firewall rule for TCP 9393.

## What’s Fixed

- Tab title showed “React App” for some users due to cached HTML/manifest; now corrected with updated templates and cache-busting.
- Tray “Update/About” dialogs could not be closed in some cases; now modal, foreground, and closable.
- Transient console windows during ffmpeg/ffprobe operations are suppressed.
- Schedule create/update no longer 422’s when fallback_category_id is not set (treated as optional).
- Dynamic thumbnail route and rebuild improvements cover missing or legacy thumbnail paths.

## How to Upgrade

1. Download NeXroll_Installer.exe from the Assets of this Release.
2. Run the installer over your existing installation (upgrade-in-place).
3. After install:
   - Launch NeXroll and confirm the browser tab shows “NeXroll”.
   - If upgrading from older versions, optionally run “Reinitialize Thumbnails” from the Dashboard.
   - Use “Initialize Holiday Presets” (Categories tab) to create preset categories if you have not done so.

## Checksums

- SHA256 (NeXroll_Installer.exe): `f4771ac96a3001b8568c8ab9b15f624a22b6eef2b31599c2f911b531d90270a1`

## Notes

- NSIS may emit benign warnings related to COMMONAPPDATA/Chocolatey detection; they do not affect installation.
- If FFmpeg is not installed (and you did not choose the FFmpeg component), thumbnail generation will remain unavailable until FFmpeg is present.

## Full Changelog

Compare changes: https://github.com/JFLXCLOUD/NeXroll/compare/v1.0.6...v1.0.7

## Thanks

Thanks to early users for thorough testing and feedback that helped polish title handling, tray behavior, and reliability.