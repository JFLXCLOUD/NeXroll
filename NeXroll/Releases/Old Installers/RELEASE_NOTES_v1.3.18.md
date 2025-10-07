# NeXroll v1.3.18

Release date: 2025-10-04

Download
- Installer: [NeXroll_Installer_1.3.18.exe](NeXroll/NeXroll_Installer_1.3.18.exe)
- Checksums: [CHECKSUMS_v1.3.18.txt](NeXroll/CHECKSUMS_v1.3.18.txt)

Highlights
- Jellyfin integration (initial) with connect/status/disconnect and category “apply plan”
- Unified Categories UI with a single “Apply to Server” button; removed the “Connected:” label on cards
- Dashboard “Servers” card now shows only the currently connected server
- Enforced one media server connected at a time (Plex or Jellyfin)
- Runtime API base rewrite verified so hardcoded http://localhost:9393 calls are rewritten to the active base/port at runtime (backend currently on 9494 during dev)

Details

Frontend
- Added getActiveConnectedServer and handleApplyCategoryToActiveServer in [App.js](NeXroll/frontend/src/App.js:1122)
- Categories card uses a single “Apply to Server” and “Manage Prerolls” (status text removed) in [App.js](NeXroll/frontend/src/App.js:3353)
- Edit Category modal adds “Save & Apply to Server” action in [App.js](NeXroll/frontend/src/App.js:3179)
- Connect flows guard against connecting when the other server is already connected in [App.js](NeXroll/frontend/src/App.js:3404)
- Dashboard “Servers” shows only the active server in [App.js](NeXroll/frontend/src/App.js:1805)
- Built with react-scripts; non-blocking ESLint warnings remain (effects deps; a couple of unused vars used for future wiring)

Backend
- Jellyfin endpoints added:
  - POST /categories/{id}/apply-to-jellyfin (returns a plan preview) in [main.py](NeXroll/nexroll_backend/main.py)
  - POST /categories/{id}/remove-from-jellyfin stub in [main.py](NeXroll/nexroll_backend/main.py)
  - Connect/status/disconnect routes for Jellyfin in [main.py](NeXroll/nexroll_backend/main.py)
- Notes:
  - Jellyfin currently returns a plan of translated file paths and a suggested playlist name; no global preroll setting exists in Jellyfin
  - Path mappings are honored to translate local/UNC/container paths into server-visible mounts

Packaging
- Version bump: 1.3.17 → 1.3.18 in [installer.nsi](NeXroll/installer.nsi:25) and [version_info.txt](NeXroll/version_info.txt:3)
- Built executables via PyInstaller specs:
  - [neXroll.spec](NeXroll/neXroll.spec)
  - [NeXrollService.spec](NeXroll/NeXrollService.spec)
  - [NeXrollTray.spec](NeXroll/NeXrollTray.spec)
  - [setup_plex_token.spec](NeXroll/setup_plex_token.spec)
- Output installer: [NeXroll_Installer_1.3.18.exe](NeXroll/NeXroll_Installer_1.3.18.exe)

Checksum (SHA256)
- A20F08D62B7B7A2F295B3CD6D3C891C6046E4901D170450B215B4CD5CBD35368

Upgrade Notes
- Only one media server connection is supported at a time. Disconnect Plex before connecting Jellyfin (and vice versa)
- The packaged app serves the updated frontend; no additional user-side build steps required

Known Issues
- ESLint warnings in frontend build are non-blocking and safe to ignore
- Jellyfin apply is plan/preview only at this stage; automation of playlist creation may come in a later release

Validation
- Verified Dashboard shows only the active server
- Verified Categories cards display only “Apply to Server” and “Manage Prerolls”
- Verified Jellyfin status and “apply plan” roundtrip using the packaged UI
