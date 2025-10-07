# NeXroll v1.4.1 Release Notes

Date: 2025-10-04

Enhancements

- Jellyfin "Apply to Server" now performs real configuration:
  - Integrates with Jellyfin's "Local Intros" plugin to inject preroll file paths directly
  - No longer copies plan JSON to clipboard; shows concise success dialog with applied details
  - Handles plugin discovery, configuration updates, and path translation automatically

Changed files

- [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js): Updated Jellyfin apply handler to parse backend response and show success messages instead of copying JSON
- [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py): Enhanced apply_category_to_jellyfin to configure "Local Intros" plugin, version bumped to 1.4.1
- [NeXroll/nexroll_backend/jellyfin_connector.py](NeXroll/nexroll_backend/jellyfin_connector.py): Added plugin API helpers for discovery and configuration
- [NeXroll/frontend/build/index.html](NeXroll/frontend/build/index.html): rebuilt assets for deployment
- [NeXroll/version_info.txt](NeXroll/version_info.txt): bumped to 1.4.1.0
- [NeXroll/installer.nsi](NeXroll/installer.nsi): APP_VERSION 1.4.1, VIProductVersion 1.4.1.0

Packaging

- Windows installer produced:
  - [NeXroll/NeXroll_Installer_1.4.1.exe](NeXroll/NeXroll_Installer_1.4.1.exe)
- Dist executables:
  - [NeXroll/dist/NeXroll.exe](NeXroll/dist/NeXroll.exe)
  - [NeXroll/dist/NeXrollService.exe](NeXroll/dist/NeXrollService.exe)
  - [NeXroll/dist/NeXrollTray.exe](NeXroll/dist/NeXrollTray.exe)

Checksums

- A SHA256 file will be committed at repository root as CHECKSUMS_v1.4.1.txt
- To generate/check locally (PowerShell):

```
Get-FileHash ".\NeXroll\NeXroll_Installer_1.4.1.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXroll.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXrollService.exe" -Algorithm SHA256
Get-FileHash ".\NeXroll\dist\NeXrollTray.exe" -Algorithm SHA256
```

Notes

- No database migration required
- Requires Jellyfin "Local Intros" plugin to be installed and enabled for apply functionality
- If plugin not found, backend returns available plugins for user guidance
- ESLint warnings remain unchanged and are safe for release; they do not affect runtime

Previous version: v1.4.0