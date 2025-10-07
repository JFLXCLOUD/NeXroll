# NeXroll v1.0.15_r4

Release date: 2025-09-20

## Downloads

- Installer (recommended): NeXroll_Installer_1.0.15_r4.exe (attached to this GitHub Release)

## Highlights

### Installer and Packaging
- Version metadata aligned with 1.0.15 across binaries and installer.
- Creates %ProgramData%\NeXroll and %ProgramData%\NeXroll\logs and grants Modify rights to standard Users for reliable logging and database writes.
- Preroll storage selection page persists to HKLM\Software\NeXroll\PrerollPath.
- Migrates legacy $INSTDIR\data\prerolls to the selected Preroll path on upgrade (best‑effort).
- Optional components: Windows Service, Stable Token setup, Start with Windows (Startup shortcut), FFmpeg via winget, and a Windows Firewall rule (TCP 9393).
- Auto‑detects ffmpeg/ffprobe in common locations and records absolute paths under HKLM\Software\NeXroll for consistent resolution by service/tray.
- Pre‑install attempts to stop/close running NeXroll processes to reduce file‑in‑use errors; uninstaller cleans up shortcuts, firewall rule, and service.

### UI
- Added modal edit dialogs across Prerolls, Schedules, and Categories for faster inline edits with validation, without navigating away.
- Enhanced “Add to Categories” workflow:
  - Multi-select UI to assign a preroll to multiple categories in one action.
  - Reliability fixes and clearer feedback when updating many items at once.
  - Consistent persistence of category assignments across views.
- Header polishing:
  - NeXroll logo is now placed in the header for consistent branding and responsive alignment across viewports.
### Backend
- Backend API version: 1.0.15.

## What’s Fixed / Improved

- Upgrade flow reliability and environment hardening via permissions, process management, and optional dependency installation.
- Packaging/listing parity: Start Menu + Desktop shortcuts, service registration, and tray startup option.

## How to Upgrade

1. Download NeXroll_Installer_1.0.15_r4.exe from the Assets of this Release.
2. Run the installer over your existing installation (upgrade‑in‑place).
3. After install:
   - Launch NeXroll and open http://localhost:9393
   - If prompted, confirm or update your Preroll storage path.
   - If you rely on the Windows Service, verify it is running (Services.msc → NeXrollService).

## Checksums

- SHA256 (NeXroll_Installer_1.0.15_r4.exe): `56517e3b2833a8026eb2cf2286f114e2702fbcf5195ba59867b8bbdac469deee`

## Known Notes

- NSIS may emit benign warnings on some environments; these do not affect installation.
- If FFmpeg is not installed (and you did not select the FFmpeg component), thumbnail generation remains unavailable until FFmpeg is present.

## Full Changelog

Compare changes: https://github.com/JFLXCLOUD/NeXroll/compare/v1.0.15_r3...v1.0.15_r4

## Assets included in this release

- NeXroll_Installer_1.0.15_r4.exe