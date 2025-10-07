# NeXroll v1.2.0 (2025-09-24)

This release introduces external preroll directory mapping (including UNC shares) without moving files, and automated local-to-Plex path translation. You can now point NeXroll at an existing media directory and apply categories to Plex while ensuring Plex receives paths it accepts.

Highlights:
- Map existing preroll directories (local or UNC) with zero data movement
- New managed=false mode for externally-managed files (no moves/deletes)
- Local→Plex path prefix mappings with longest-prefix matching
- UNC path support with conversion to Plex-visible drive/path
- Path translation applied everywhere Plex is updated (manual and scheduler)
- PWA cache bust: service worker cache names bumped

## New Features

1) External Directory Mapping
- Endpoint: POST /prerolls/map-root
- Scans a root path (recursively optional), adds videos as Preroll rows with managed=false, and optionally generates thumbnails.
- Supports dry-run mode to preview how many items will be added.
- No files are copied, moved, or deleted from user storage.

2) Local→Plex Path Translation
- Endpoints:
  - GET /settings/path-mappings
  - PUT /settings/path-mappings?merge=true|false
  - POST /settings/path-mappings/test
- Configure a list of mappings: { local: "C:\or\UNC\prefix", plex: "Z:\or\posix\prefix" }
- Longest-prefix wins; case-insensitive on Windows.
- Separator-preserving join: builds Plex paths using the separator implied by the mapping’s plex prefix.
- Translation is applied when:
  - Applying a category to Plex: POST /categories/{id}/apply-to-plex
  - Scheduler updates prerolls in Plex (shuffle/playlist and sequences)

3) Managed Flag for Prerolls
- New DB column: prerolls.managed (default true)
- When managed=false:
  - Update/rename operations will not move the source file on disk
  - Deletion will not remove the video file (thumbnail still cleaned)
  - Primary category changes only affect metadata and thumbnail location

## API Additions

- POST /prerolls/map-root
  - Body:
    {
      "root_path": "\\\\NAS\\PreRolls",
      "category_id": 5,
      "recursive": true,
      "extensions": ["mp4","mkv","mov"],
      "dry_run": true,
      "generate_thumbnails": true,
      "tags": ["mapped","external"]
    }
- GET /settings/path-mappings
- PUT /settings/path-mappings?merge=true
  - Body:
    {
      "mappings": [
        { "local": "\\\\NAS\\PreRolls", "plex": "Z:\\PreRolls" },
        { "local": "D:\\Media\\Prerolls", "plex": "D:\\Media\\Prerolls" }
      ]
    }
- POST /settings/path-mappings/test
  - Body:
    { "paths": ["\\\\NAS\\PreRolls\\Holiday\\intro.mp4"] }

## Behavior Changes

- Category Apply to Plex
  - When building the multi-preroll string, each local path is translated using the configured mappings.
  - Delimiter selection:
    - ";" when plex_mode is "shuffle" (random rotation)
    - "," when plex_mode is "playlist" (Plex plays in order)
- Scheduler
  - The same translation logic is used when it sets prerolls in Plex.

## Database and Migrations

- Lightweight runtime migration adds new columns if missing:
  - settings.path_mappings (TEXT)
  - prerolls.managed (BOOLEAN DEFAULT 1)
  - prerolls.display_name (TEXT) retained from recent releases
- Existing installs will auto-detect and add columns at startup; no manual steps required.

## Upgrade Notes

- If you plan to map existing media:
  1) Configure Local→Plex mappings first
     - PUT /settings/path-mappings
     - Test them with POST /settings/path-mappings/test
  2) Map your directory with POST /prerolls/map-root (dry_run first)
  3) Apply your category to Plex and verify playback

- UNC Paths:
  - Plex may not accept raw UNC paths directly.
  - Use a mapping from your UNC prefix (e.g., "\\\\NAS\\Share") to a Plex-visible path (e.g., "Z:\\Share").
  - For Linux Plex servers, map to POSIX-style prefixes (e.g., "/mnt/prerolls").

## Packaging and Versioning

- Backend API version: 1.2.0 (see [`nexroll_backend.main:app = FastAPI(...)`](NeXroll/nexroll_backend/main.py:494))
- Windows binary metadata: 1.2.0.0 (see [`version_info.txt`](NeXroll/version_info.txt))
  - FileVersion/ProductVersion updated to 1.2.0.0
- Installer:
  - NSIS APP_VERSION set to 1.2.0 (see [`installer.nsi`](NeXroll/installer.nsi:25))
  - Output: NeXroll/NeXroll_Installer_1.2.0.exe
- PWA cache bust:
  - Updated SW cache names to v1.2.0 in [`frontend/public/sw.js`](NeXroll/frontend/public/sw.js:2) and [`frontend/build/sw.js`](NeXroll/frontend/build/sw.js:2)

## Release Assets

- NeXroll_Installer_1.2.0.exe (recommended)
- Dist executables (portable/testing):
  - dist/NeXroll.exe
  - dist/NeXrollService.exe
  - dist/NeXrollTray.exe
  - dist/setup_plex_token.exe

### Example checksum commands (PowerShell):

```powershell
Get-FileHash ".\NeXroll\NeXroll_Installer_1.2.0.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXroll.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXrollService.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXrollTray.exe" -Algorithm SHA256
Get-FileHash ".\dist\setup_plex_token.exe" -Algorithm SHA256
```

## Known Issues / Notes

- If Plex still rejects paths:
  - Double-check mappings and ensure Plex has access to the translated path.
  - Use test endpoint to verify translation output.
  - Ensure proper permissions and mounted drives for the Plex server OS.
- Thumbnails depend on FFmpeg; use Installer’s optional FFmpeg install or configure paths in registry.
- Service worker cache names were bumped; if you see stale UI, force-refresh/reload the app.

## Acknowledgements

Thanks to the community for feedback guiding external directory mapping and cross-platform path handling for Plex.