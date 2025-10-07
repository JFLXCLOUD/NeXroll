# NeXroll v1.3.16 (2025-10-03)

Jellyfin connectivity arrives in 1.3.16. This release adds secure Jellyfin server linking, environment bootstrap for container/CI, and a quick status surface in the built-in dashboard. No breaking changes.

Highlights:
- New Jellyfin connector and API.
- Secure storage for Jellyfin API key (no plaintext in DB).
- Runtime DB migration adds settings.jellyfin_url for legacy SQLite databases.
- Env-driven auto-connect on startup for Docker/CI.
- Dashboard “Jellyfin Status” button and JSON status endpoint.

New
1) Jellyfin connectivity
- Connector: [jellyfin_connector.JellyfinConnector()](NeXroll/nexroll_backend/jellyfin_connector.py:94) implements connectivity probes and server info using X-Emby-Token/X-MediaBrowser-Token headers with TLS verify heuristics on local/private HTTPS.
- API endpoints:
  - POST /jellyfin/connect → [main.connect_jellyfin()](NeXroll/nexroll_backend/main.py:6599)
  - GET /jellyfin/status → [main.get_jellyfin_status()](NeXroll/nexroll_backend/main.py:6652)
  - POST /jellyfin/disconnect → [main.disconnect_jellyfin()](NeXroll/nexroll_backend/main.py:6702)
- Dashboard: “Jellyfin Status” button in [main.dashboard()](NeXroll/nexroll_backend/main.py:1210) calls /jellyfin/status.

2) Secure storage
- Jellyfin API key is stored in the OS secure store (Windows Credential Manager + DPAPI file fallback) via [secure_store.py](NeXroll/nexroll_backend/secure_store.py).
- Only the URL is persisted in the DB; the API key is never stored in plaintext.

3) Environment bootstrap
- On startup, [main.startup_env_bootstrap()](NeXroll/nexroll_backend/main.py:986) invokes [main._bootstrap_jellyfin_from_env()](NeXroll/nexroll_backend/main.py:6741).
- Supported variables:
  - NEXROLL_JELLYFIN_URL
  - NEXROLL_JELLYFIN_API_KEY
  - NEXROLL_JELLYFIN_TLS_VERIFY (0/1) to override TLS verify heuristic if needed.

4) Database migration (SQLite)
- [main.ensure_schema()](NeXroll/nexroll_backend/main.py:65) and [main.ensure_settings_schema_now()](NeXroll/nexroll_backend/main.py:134) add settings.jellyfin_url on legacy databases. Idempotent and safe at runtime.

Versioning
- Backend API: [app = FastAPI()](NeXroll/nexroll_backend/main.py:817) → 1.3.16
- Windows resources: [version_info.txt](NeXroll/version_info.txt)
- Installer metadata: [installer.nsi](NeXroll/installer.nsi:25)

Usage
- Connect via API:
  curl -H "Content-Type: application/json" -X POST http://127.0.0.1:9393/jellyfin/connect -d "{\"url\":\"http://localhost:8096\",\"api_key\":\"<YOUR_API_KEY>\"}"
- Check status:
  curl http://127.0.0.1:9393/jellyfin/status

TLS notes
- Local/private HTTPS hosts automatically relax TLS verification unless NEXROLL_JELLYFIN_TLS_VERIFY=1 is set.

Packaging
- PyInstaller specs:
  - Core app: [neXroll.spec](NeXroll/neXroll.spec:1)
  - Service: [NeXroll/NeXrollService.spec](NeXroll/NeXrollService.spec:1)
  - Tray: [NeXroll/NeXrollTray.spec](NeXroll/NeXrollTray.spec:1)
  - Token tool: [setup_plex_token.spec](NeXroll/setup_plex_token.spec:1)
- NSIS build: [installer.nsi](NeXroll/installer.nsi:1) produces NeXroll_Installer_1.3.16.exe

Data/Logs
- Logs are written to %ProgramData%\NeXroll\logs (fallbacks exist); see [main._init_global_logging()](NeXroll/nexroll_backend/main.py:299) for details.
- Preroll data path resolution and migration retained; see relevant helpers around data_dir/PREROLLS_DIR in [main.py](NeXroll/nexroll_backend/main.py:4968).

Known limitations
- Jellyfin preroll application strategy is not implemented in this release. Only connectivity and status are included. See roadmap item in TODOs.
- Default service/UI port remains 9393; if occupied, use NEXROLL_PORT to override.

Upgrade guidance from 1.3.15
- Simply install NeXroll_Installer_1.3.16.exe over the existing installation.
- The runtime migration will add settings.jellyfin_url automatically.

Checksums
- Published in [CHECKSUMS_v1.3.16.txt](NeXroll/CHECKSUMS_v1.3.16.txt) after the release build is produced.

Credits
- Thanks to early testers for validating Jellyfin against local instances.