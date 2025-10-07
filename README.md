
<div align="center">
  <img src="frontend/NeXroll_Logo_WHT.png" alt="NeXroll Logo" width="500"/>
  <br>
</div>

---

NeXroll is a Windows-ready preroll management system with a modern web UI, an optional Windows Service, and a lightweight system tray app. All executables are self‑contained (no Python required on user machines), and a single installer configures everything end‑to‑end.

Web UI: http://localhost:9393


---

## Main Features

- Preroll management
  - Upload multiple preroll videos with metadata
  - Automatic thumbnail generation (FFmpeg)
  - Tags and multi‑category assignment with improved multi‑select workflow
- Categories & Holiday Presets
  - Organize your library by categories (Default, Halloween, Christmas, etc.)
  - One‑click Holiday Presets initializer creates per‑holiday categories and date ranges
  - Apply a category to Plex as a preroll sequence
- Scheduling
  - Flexible schedules with date/time ranges and recurrence
  - Optional fallback category when no schedule is active
  - Real‑time scheduler status
- UI enhancements (v1.1.1)
  - Sticky top navigation bar for persistent access to Dashboard, Schedules, Categories, Settings, and Connect
  - Pagination for Prerolls: default 20 per page, adjustable up to 50
  - Multi-select with bulk primary category update/move
  - Inline category creation directly from Upload and Edit Preroll
  - Storage usage card on the Dashboard showing total preroll storage used
  - Long preroll title handling so Edit/Delete buttons remain visible in Grid and List views
- Media Server integration
  - Connect to Plex or Jellyfin servers
  - Connect via URL/token or Stable Token (persistent)
  - Status monitoring and quick Apply-to-Server actions
- Windows experience
  - One‑click installer with optional Windows Service and System Tray app
  - “Start with Windows,” Firewall rule (TCP 9393), and FFmpeg installation via winget
  - Self‑contained executables (no Python required on user machines)
- Observability & storage
  - Logs under %ProgramData%\NeXroll\logs
  - SQLite database storage under %ProgramData%\NeXroll
- API
  - REST API with interactive docs at http://localhost:9393/docs
## Download and Install (Users)

1. Download the latest `NeXroll_Installer.exe` from GitHub Releases:
   https://github.com/JFLXCLOUD/NeXroll/releases
2. Run `NeXroll_Installer.exe` (administrator recommended).
3. Choose:
   - Install location (default: `C:\Program Files\NeXroll`)
   - Preroll storage directory (can be on any drive)
4. Optional components you may select:
   - Install as Windows Service (`NeXrollService`)
   - Plex Stable Token setup (runs `setup_plex_token.exe`)
   - Start with Windows (adds the tray app to Startup)
   - Install FFmpeg via winget (for thumbnail generation)
   - Windows Firewall rule (Allow inbound TCP 9393 for local web UI)
5. Finish the installer and open the app from the Start Menu or tray menu.

After install, visit http://localhost:9393 to use the web UI.


---

## What’s Installed

- `NeXroll.exe` — the web application (FastAPI + bundled frontend)
- `NeXrollService.exe` — optional Windows Service wrapper
- `NeXrollTray.exe` — system tray app with quick actions
- `setup_plex_token.exe` — helper to obtain a stable Plex token

Start Menu shortcuts are created for NeXroll, NeXroll Tray, and Uninstall NeXroll. A desktop shortcut for NeXroll is also added.


---

## System Tray App

The tray icon provides quick actions:
- Open — launches http://localhost:9393 (default action)
- Start Service — attempts to start the Windows service (if installed)
- Stop Service — stops the Windows service (if installed)
- Restart Service — restarts the Windows service (if installed)
- Start App (portable) — starts the packaged app directly (non‑service)
- Check for updates — checks GitHub Releases and opens the latest release if a newer version is available (dialog is foreground and closable)
- About — shows app information (dialog is foreground and closable)
- GitHub — opens https://github.com/JFLXCLOUD/NeXroll
- Exit — closes the tray app

If you selected “Start with Windows,” the tray app launches automatically at login.

---

## Windows Service (Optional)

If chosen during installation, the `NeXrollService` Windows Service is installed. You can manage it via Services.msc or the following commands (run from `C:\Program Files\NeXroll` or your chosen InstallDir):

```
NeXrollService.exe install
NeXrollService.exe start
NeXrollService.exe stop
NeXrollService.exe remove
```

Logs (service mode): `%ProgramData%\NeXroll\logs\service.log`
Logs (packaged app): `%ProgramData%\NeXroll\logs\app.log`
Logs (tray): `%ProgramData%\NeXroll\logs\tray.log`
Database (packaged): `%ProgramData%\NeXroll\nexroll.db`

Tip: if a previous NeXroll instance is still running and occupying port 9393, the service may need a second start attempt after that instance is closed.

---

## Requirements (User machines)

- Windows 10/11 x64
- FFmpeg for thumbnail generation (you can install it from the installer's optional components, or manually)
- Network access to your Plex or Jellyfin server
- No Python required on user machines

---

## First‑Time Setup

1. Open http://localhost:9393
2. Connect to your media server:
   - Connect to Plex or Jellyfin using URL and credentials
   - For Plex: Use your Plex URL and token; or run `setup_plex_token.exe` to create a long‑lived "stable token"
3. Upload prerolls, create categories, and configure schedules.

---

## Upgrade / Uninstall

- Upgrade: simply run the newer `NeXroll_Installer.exe` over the existing installation. Your configured Preroll storage path is preserved, and data is not removed.
- Uninstall: use “Uninstall NeXroll” from the Start Menu (or Apps & Features). The installer removes the service and shortcuts; your Preroll storage directory is not deleted.

---

## Building From Source (Maintainers)

See the full packaging guide at `NeXroll/PACKAGING.md`.

Prerequisites (build machine):
- Python 3.10+ (build‑time only)
- pip install: `pyinstaller`, `pywin32`, `pystray`, `Pillow`
- NSIS 3.x (`makensis` on PATH)

Build commands (run from the repository root):

```
py -m PyInstaller -y NeXroll\neXroll.spec
py -m PyInstaller -y NeXroll\NeXrollService.spec
py -m PyInstaller -y NeXroll\setup_plex_token.spec
py -m PyInstaller -y NeXroll\NeXrollTray.spec

makensis NeXroll\installer.nsi
```

Outputs:
- `dist\NeXroll.exe`
- `dist\NeXrollService.exe`
- `dist\setup_plex_token.exe`
- `dist\NeXrollTray.exe`
- `NeXroll\NeXroll_Installer.exe`  (Release asset is published as a generic name)

---


## Project Structure (key files)

- Backend (FastAPI): `NeXroll/backend/`
- Packaged runtime backend: `NeXroll/backend/`
- Frontend (static build served by backend): `NeXroll/frontend/`
- Windows Service wrapper: `NeXroll/windows_service.py`
- System tray app: `NeXroll/tray_app.py`
- PyInstaller specs:
  - `NeXroll/neXroll.spec`
  - `NeXroll/NeXrollService.spec`
  - `NeXroll/NeXrollTray.spec`
  - `NeXroll/setup_plex_token.spec`
- NSIS installer: `NeXroll/installer.nsi`
- Packaging guide: `NeXroll/PACKAGING.md`

---

## Troubleshooting

- “Service did not respond in time”
  - Ensure no other process is using port 9393; stop any `NeXroll.exe` that’s running, then start the service again.
- UI not reachable at http://localhost:9393
  - If you selected the firewall component, verify the inbound rule “NeXroll (TCP 9393)” exists. Otherwise, allow inbound TCP 9393 or re-run the installer and select the firewall option.
- Service logs location
  - Check `%ProgramData%\NeXroll\logs\service.log` for service-mode startup and health probe messages.
- Thumbnails not created
  - Install FFmpeg (choose the installer component, or install manually); re‑upload a preroll.
- Tray icon not shown
  - Run “NeXroll Tray” from Start Menu; pin it so it’s always visible.
- Media server connection issues
  - Verify your Plex or Jellyfin server is reachable from the machine, and credentials are valid (retry `setup_plex_token.exe` for Plex if needed).

---

## License

MIT. Third‑party components remain under their respective licenses.


---

## Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-FF5E5B?style=for-the-badge&amp;logo=ko-fi&amp;logoColor=white)](https://ko-fi.com/j_b__)
