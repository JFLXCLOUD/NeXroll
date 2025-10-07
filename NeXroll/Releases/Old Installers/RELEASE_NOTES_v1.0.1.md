# NeXroll v1.0.1 — Stability and UX Polish

Release date: 2025-09-17

This release focuses on improving Windows service robustness, adding diagnostics and update checks, and enhancing install/upgrade ergonomics.

Updated files:
- [NeXroll/windows_service.py](NeXroll/windows_service.py)
- [NeXroll/tray_app.py](NeXroll/tray_app.py)
- [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py)
- [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js)
- [NeXroll/installer.nsi](NeXroll/installer.nsi)
- [NeXroll/PACKAGING.md](NeXroll/PACKAGING.md)
- [NeXroll/neXroll.spec](NeXroll/neXroll.spec)
- [NeXroll/launcher.py](NeXroll/launcher.py)
- [README.md](README.md) and [NeXroll/README.md](NeXroll/README.md)

Highlights:
- Windows Service now starts more reliably with readiness probing and retry.
- Tray app gains a “Check for updates” action and ensures the backend is reachable at startup.
- Backend exposes diagnostics endpoints and reports API version 1.0.1.
- Frontend Settings surfaces version and FFmpeg availability, with a Re-check action and footer version display.
- Installer writes Version to registry, adds version metadata, and offers an optional Windows Firewall rule for TCP 9393.
- v1.1.0 scaffolding started (cron-like validation endpoint).

1. Windows Service robustness

The service wrapper was enhanced to improve startup reliability and observability.

- Readiness loop:
  - Keeps SCM state at START_PENDING while probing http://127.0.0.1:9393/health.
  - Falls back to a port-open check (TCP 9393) if the health endpoint is not yet available.
  - If the first attempt fails readiness within the wait window, the child is terminated and a second attempt is made.
- SCM status transitions:
  - Reports START_PENDING during readiness checks and transitions to SERVICE_RUNNING afterward to prevent timeout.
- Supervision:
  - If the backend child process exits unexpectedly while not stopping, the service attempts a restart.
- Logging:
  - Writes to the Windows Event Log and to a rolling file at:
    - %ProgramData%\NeXroll\logs\service.log
- Launch behavior:
  - Prefers the packaged NeXroll.exe; falls back to system Python or venv only for developer layouts.

See implementation: [NeXroll/windows_service.py](NeXroll/windows_service.py)

2. System tray improvements

- Backend availability on start:
  - Attempts to start the Windows service and waits for readiness.
  - If unavailable (e.g., insufficient privileges), falls back to launching NeXroll.exe and waits until http://localhost:9393 is reachable.
- Service controls:
  - Start Service, Stop Service, Restart Service, and Start App (portable) actions.
- Update checks:
  - New “Check for updates” menu item queries GitHub Releases for the latest tag and compares with HKLM\Software\NeXroll\Version.
  - Opens the latest releases page when a newer version is available.

See implementation: [NeXroll/tray_app.py](NeXroll/tray_app.py)

3. Backend diagnostics and version

- API version bumped to 1.0.1 via FastAPI initialization.
- New endpoints:
  - GET /system/ffmpeg-info
    - Returns ffmpeg_present, ffmpeg_version, ffprobe_present, ffprobe_version.
  - GET /system/version
    - Returns api_version, registry_version (from HKLM\Software\NeXroll\Version), and install_dir.
- v1.1.0 scaffolding:
  - POST /schedules/validate-cron (syntax-only validation; to be expanded in 1.1.0).

See implementation: [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py)

4. Frontend updates

- Settings page now includes “System Information”:
  - Shows API version and installed version (from registry).
  - Displays FFmpeg and FFprobe detection results and versions.
  - Adds “Re-check FFmpeg” button to refresh detection.
- Footer:
  - Shows NeXroll version (registry version when installed, otherwise API version).

See implementation: [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js)

5. Installer changes

- Upgrade-friendly defaults:
  - InstallDir is now initialized from HKLM\Software\NeXroll\InstallDir when present.
- Versioning:
  - Writes HKLM\Software\NeXroll\Version = 1.0.1 on install.
  - Embeds version metadata in the installer binary.
- Optional firewall rule:
  - New component “Windows Firewall Rule (Allow TCP 9393)” adds an inbound rule, and the uninstaller removes it.
- Shortcuts:
  - Start Menu shortcuts for NeXroll, NeXroll Tray, and Uninstall are preserved.

See script: [NeXroll/installer.nsi](NeXroll/installer.nsi)

6. Packaging notes

- Packaging was hardened to fix ModuleNotFoundError in frozen builds:
  - Renamed runtime package folder from `backend` to `nexroll_backend`.
  - Switched the app entry to a dedicated `launcher.py` that imports `nexroll_backend.main`; server auto-starts when frozen.
  - Updated `neXroll.spec` to use `collect_all('nexroll_backend')`, include datas for `nexroll_backend/data` and `frontend`, and bundle `favicon.ico`.
- Outputs (one-file EXEs under `dist\`):
  - `dist\NeXroll.exe`
  - `dist\NeXrollService.exe`
  - `dist\NeXrollTray.exe`
  - `dist\setup_plex_token.exe`
- Installer output:
  - `NeXroll\NeXroll_Installer_1.0.1.exe`

See guide: [NeXroll/PACKAGING.md](NeXroll/PACKAGING.md)

7. Upgrade instructions

- Simply run the new NeXroll_Installer.exe over an existing installation.
- Your configured Preroll storage path remains unchanged.
- If you installed the service previously, it will be restarted; the readiness loop minimizes “service did not respond” errors.
- If you selected the firewall component, verify the rule exists once; duplicates are not created by NSIS.

8. Troubleshooting

- Can’t reach http://localhost:9393:
  - If you installed the firewall component, verify the inbound rule for TCP 9393 exists.
  - Check that another process is not using port 9393.
  - Review logs at %ProgramData%\NeXroll\logs\service.log when running as a service.
- FFmpeg not detected:
  - Re-run the installer and select the “Install Dependencies (FFmpeg via winget)” component, or install FFmpeg manually and use “Re-check FFmpeg” in Settings.
- Tray cannot start the service:
  - Use “Start App (portable)” from the tray menu; service control may require elevation.

9. Checksums and signing

- SHA-256 checksums for v1.0.1 artifacts:
  - NeXroll.exe — 304EEBE8449D5E046F4CF8789B07D97CE425BBEFB9DD73B8ED44250305011228
  - NeXrollService.exe — 5B94A51593FFC07FA709687D7AF42FBA4CAA3F7AB6823BA8217FDE48B120188B
  - NeXrollTray.exe — 7EDC016CDD2E93D9F184461BEB59BE1513CC5DF53B3766CBF8724BEB4418AAB1
  - setup_plex_token.exe — 718EB136FA3E60FB2E63DC5BBAEF8A2C60DCCED82AD2BFCE6CFFD082F2CBBD66
  - NeXroll_Installer_1.0.1.exe — 34CA7A9DD4E3FA6D2BAEA2048686D40543B6BFC9300187BA76C3FFC8D17BD4F2
- The complete list is also saved in CHECKSUMS_v1.0.1.txt.
- Consider code signing the executables and installer to improve SmartScreen trust.

Thank you for using NeXroll and for your feedback driving these improvements.