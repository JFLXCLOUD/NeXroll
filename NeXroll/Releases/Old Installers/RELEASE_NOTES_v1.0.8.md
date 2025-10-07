# NeXroll v1.0.8

Release date: 2025-09-19

Highlights

- New: Dashboard "Reinitialize Thumbnails" button to rebuild or backfill thumbnails across your library. Invokes the backend bulk endpoint and shows a summary (processed/generated/skipped/failures).
- Reliability: Service/Tray startup and FFmpeg discovery hardened for mixed admin/standard contexts. Registry is checked in both 64-bit and 32-bit views; subprocess windows are suppressed.
- UI: Eliminated stale "React App" tab title via no-cache headers and a runtime document.title guard.
- Installer: Standardized output name to NeXroll_Installer.exe and bumped version metadata to 1.0.8.

What changed

Backend

- Added bulk thumbnail rebuild endpoint with on-disk atomic writes and DB updates:
  - Route: POST /thumbnails/rebuild (force, optional category filter).
  - Implementation: thumbnails_rebuild(...) at [def thumbnails_rebuild()](NeXroll/nexroll_backend/main.py:1931).
- Improved FFmpeg/FFprobe resolution in service/tray scenarios:
  - Uses env overrides (NEXROLL_FFMPEG/NEXROLL_FFPROBE), PATH, common install locations, and HKLM\Software\NeXroll registry hints in both 64/32-bit views.
  - See [_resolve_tool()](NeXroll/nexroll_backend/main.py:154) and registry lookup at [winreg.OpenKeyEx(..., KEY_WOW64_64KEY/KEY_WOW64_32KEY)](NeXroll/nexroll_backend/main.py:171).
- Suppressed flashing consoles for subprocesses (ffmpeg/ffprobe) in Windows services/tray via CREATE_NO_WINDOW. See [_run_subprocess()](NeXroll/nexroll_backend/main.py:136).
- Version bump: [FastAPI(..., version="1.0.8")](NeXroll/nexroll_backend/main.py:268).
- Removed unused python-ffmpeg import to avoid import errors in frozen builds (line removed near [import ffmpeg](NeXroll/nexroll_backend/main.py:10)).
- Index/manifest cache busting middleware to avoid stale "React App" titles: [@app.middleware("http")](NeXroll/nexroll_backend/main.py:299).

Frontend

- Dashboard "Reinitialize Thumbnails" button wired to the backend with a summary dialog:
  - Button: see Dashboard card and handler [handleReinitThumbnails()](NeXroll/frontend/src/App.js:1595).
  - Image fallback automatically calls the on-demand generator if a file is missing.
- Runtime tab-title guard to keep “NeXroll”: [useEffect title guard](NeXroll/frontend/src/App.js:109).

Tray and Service

- Tray message boxes are now task-modal/foreground/topmost to ensure they can be closed; dialogs run on a background thread (already present). See [_message_box()](NeXroll/tray_app.py:35).
- Windows Service wrapper launches the packaged NeXroll.exe and performs readiness probes; logs/failover logic unchanged. See [NeXrollService](NeXroll/windows_service.py:15).

Installer/Packaging

- NSIS: version updated and standardized installer filename:
  - [!define APP_VERSION "1.0.8"](NeXroll/installer.nsi:24)
  - [OutFile "NeXroll_Installer.exe"](NeXroll/installer.nsi:32)
- PyInstaller spec cleanup: removed unused 'ffmpeg' hidden import. See [hiddenimports block](NeXroll/neXroll.spec:55).
- Built artifacts:
  - dist\NeXroll.exe
  - dist\NeXrollService.exe
  - dist\NeXrollTray.exe
  - dist\setup_plex_token.exe
  - NeXroll\NeXroll_Installer.exe

Checksums

To compute SHA256 locally:

- Open a terminal in the project root and run:

  certutil -hashfile "NeXroll\NeXroll_Installer.exe" SHA256

Known warnings

- NSIS "unknown variable/constant COMMONAPPDATA..." are benign on some environments and do not affect installation.

Upgrade notes

- You can install v1.0.8 over an existing installation. The installer stops the service/tray and replaces binaries.
- After install, if you run as a Windows Service, allow a few seconds for the readiness probe to pass. Logs:
  - App: %ProgramData%\NeXroll\logs\app.log
  - Service: %ProgramData%\NeXroll\logs\service.log
  - Tray: %ProgramData%\NeXroll\logs\tray.log

Validation checklist

- Launch NeXroll.exe as standard user and admin; confirm UI loads and title shows “NeXroll”.
- Start NeXrollService; open http://localhost:9393 → Dashboard; verify health.
- From Dashboard, click “Reinitialize Thumbnails” and confirm the summary matches expectations.
- Confirm thumbnails appear; broken images should self-heal via on-demand generator.
- Try the tray app: About/Update dialogs must be focusable/closable.

Thank you for testing and providing feedback!