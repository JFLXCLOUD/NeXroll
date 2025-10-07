# NeXroll v1.4.0 Release Notes

Date: 2025-10-04

Enhancements

- Jellyfin integration and unified Connect page:
  - New Connect view with Plex/Jellyfin tabs, live status chips, and an active-server banner
  - One-server-at-a-time model with conflict/none guards and clear guidance
  - Server-agnostic category actions: “Apply to Server” and “Manage Prerolls” adapt to the active server

- Jellyfin category operations:
  - Apply/Remove category to Jellyfin libraries via backend endpoints
  - Plan summary presented in UI before execution; no global preroll in Jellyfin (category-based only)

- Settings restructure (Plex Settings):
  - Moved Genre-based Preroll Mapping under Plex Settings
  - Merged UNC/Local → Plex Path Mappings editor and tester into Plex Settings
  - Longest-prefix translation with case-insensitive handling for Windows locals

- Runtime API base resolver:
  - Patched fetch and EventSource to rewrite hard-coded localhost:9393 to current origin/config at runtime
  - More reliable behind proxies, Docker, and alternate ports

Changed files

- [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js): Connect page, server-agnostic category actions, Settings restructure, runtime API base patches
- [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py): Jellyfin endpoints and surface/system endpoints used by UI
- [NeXroll/frontend/build/index.html](NeXroll/frontend/build/index.html): rebuilt assets for deployment
- [NeXroll/version_info.txt](NeXroll/version_info.txt): bumped to 1.4.0.0
- [NeXroll/installer.nsi](NeXroll/installer.nsi): APP_VERSION 1.4.0, VIProductVersion 1.4.0.0

Packaging

- Windows installer produced:
  - [NeXroll/NeXroll_Installer_1.4.0.exe](NeXroll/NeXroll_Installer_1.4.0.exe)
- Dist executables:
  - [NeXroll/dist/NeXroll.exe](NeXroll/dist/NeXroll.exe)
  - [NeXroll/dist/NeXrollService.exe](NeXroll/dist/NeXrollService.exe)
  - [NeXroll/dist/NeXrollTray.exe](NeXroll/dist/NeXrollTray.exe)

Checksums

- A SHA256 file will be committed at repository root as CHECKSUMS_v1.4.0.txt
- To generate/check locally (PowerShell):

```
Get-FileHash ".\NeXroll\NeXroll_Installer_1.4.0.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXroll.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXrollService.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXrollTray.exe" -Algorithm SHA256
```

Notes

- No database migration required
- When both servers are connected at once, the UI shows a “conflict” state and server-agnostic actions are guarded
- If neither server is connected, actions that require a server are disabled with guidance
- ESLint warnings remain unchanged and are safe for release; they do not affect runtime

Previous version: v1.3.14