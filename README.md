
<div align="center">
  <img src="NeXroll/frontend/NeXroll_Logo_WHT.png#gh-dark-mode-only" alt="NeXroll Logo" width="500"/>
  <img src="NeXroll/frontend/NeXroll_Logo_BLK.png#gh-light-mode-only" alt="NeXroll Logo" width="500"/>
  <br>
 <a href="https://hub.docker.com/r/jbrns/nexroll"><img src="https://img.shields.io/docker/pulls/jbrns/nexroll" alt="Docker Pulls"/></a> - <a href="https://github.com/JFLXCLOUD/NeXroll/releases/latest"><img src="https://img.shields.io/github/v/release/jflxcloud/nexroll?style=flat&color=DEDB16" alt="Latest Release"/></a>
    -  <a href="https://github.com/JFLXCLOUD/NeXroll/releases/latest"><img src="https://img.shields.io/github/downloads/jflxcloud/nexroll/total?color=DE7716" alt="Downloads"/></a>

</div>

---

NeXroll is a preroll manager for Plex and Jellyfin that makes setup effortless. It runs natively on Windows and works in Docker, featuring a clean web interface, optional background service, and lightweight tray app. Everything is self-contained, and a single installer gets you up and running in minutes.

---

## Main Features

- Preroll management
  - Upload multiple preroll videos with metadata
  - Automatic thumbnail generation (FFmpeg)
  - Tags and multiâ€‘category assignment with improved multiâ€‘select workflow
- Categories & Holiday Presets
  - Organize your library by categories (Default, Halloween, Christmas, etc.)
  - Oneâ€‘click Holiday Presets initializer creates perâ€‘holiday categories and date ranges
  - Apply a category to Plex as a preroll sequence
- Scheduling
  - Flexible schedules with date/time ranges and recurrence
  - Optional fallback category when no schedule is active
  - Realâ€‘time scheduler status

- Media Server integration
  - Connect to Plex or Jellyfin servers
  - Connect via URL/token or Stable Token (persistent)
  - Status monitoring and quick Apply-to-Server actions
- Community Prerolls
  - Access thousands of community-curated prerolls from prerolls.typicalnerds.uk
  - Smart search with synonym expansion and category filtering
  - Platform filtering (Plex/Jellyfin/Emby)
  - Local indexing for instant searches across 1,300+ prerolls
  - One-click downloads with no automatic tagging
  - Random preroll discovery
  - Fair Use Policy protection
- Windows experience
  - Oneâ€‘click installer with optional Windows Service and System Tray app
  - â€œStart with Windows,â€ Firewall rule (TCP 9393), and FFmpeg installation via winget
  - Selfâ€‘contained executables (no Python required on user machines)
- Observability & storage
  - Logs under %ProgramData%\NeXroll\logs
  - SQLite database storage under %ProgramData%\NeXroll
- API
  - REST API with interactive docs at http://localhost:9393/docs
## Download and Install

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

## Whatâ€™s Installed

- `NeXroll.exe` â€” the web application (FastAPI + bundled frontend)
- `NeXrollService.exe` â€” optional Windows Service wrapper
- `NeXrollTray.exe` â€” system tray app with quick actions
- `setup_plex_token.exe` â€” helper to obtain a stable Plex token

Start Menu shortcuts are created for NeXroll, NeXroll Tray, and Uninstall NeXroll. A desktop shortcut for NeXroll is also added.


---

## System Tray App

The tray icon provides quick actions:
- Open â€” launches http://localhost:9393 (default action)
- Start Service â€” attempts to start the Windows service (if installed)
- Stop Service â€” stops the Windows service (if installed)
- Restart Service â€” restarts the Windows service (if installed)
- Start App (portable) â€” starts the packaged app directly (nonâ€‘service)
- Check for updates â€” checks GitHub Releases and opens the latest release if a newer version is available (dialog is foreground and closable)
- About â€” shows app information (dialog is foreground and closable)
- GitHub â€” opens https://github.com/JFLXCLOUD/NeXroll
- Exit â€” closes the tray app

If you selected â€œStart with Windows,â€ the tray app launches automatically at login.

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

## Requirements

- Windows 10/11 x64
- FFmpeg for thumbnail generation (you can install it from the installer's optional components, or manually)
- Network access to your Plex or Jellyfin server
- No Python required on user machines

---

## Firstâ€‘Time Setup

1. Open http://localhost:9393
2. Connect to your media server:
   - Connect to Plex or Jellyfin using URL and credentials
   - For Plex: Use your Plex URL and token; or run `setup_plex_token.exe` to create a longâ€‘lived "stable token"
3. Upload prerolls, create categories, and configure schedules.

---

## Upgrade / Uninstall

- Upgrade: simply run the newer `NeXroll_Installer.exe` over the existing installation. Your configured Preroll storage path is preserved, and data is not removed.
- Uninstall: use â€œUninstall NeXrollâ€ from the Start Menu (or Apps & Features). The installer removes the service and shortcuts; your Preroll storage directory is not deleted.

---

## Building From Source

See the full packaging guide in `NeXroll/Docs/PACKAGING.md`.

Prerequisites (build machine):
- Python 3.10+ (buildâ€‘time only)
- pip install: `pyinstaller`, `pywin32`, `pystray`, `Pillow`
- NSIS 3.x (`makensis` on PATH)

Build commands (run from the repository root):

```
py -m PyInstaller -y NeXroll\build\neXroll.spec
py -m PyInstaller -y NeXroll\build\NeXrollService.spec
py -m PyInstaller -y NeXroll\build\setup_plex_token.spec
py -m PyInstaller -y NeXroll\build\NeXrollTray.spec

makensis NeXroll\build\installer.nsi
```

Outputs:
- `dist\NeXroll.exe`
- `dist\NeXrollService.exe`
- `dist\setup_plex_token.exe`
- `dist\NeXrollTray.exe`
- `NeXroll\build\NeXroll_Installer.exe`  (Release asset is published as a generic name)

---


## Project Structure

- Backend (FastAPI): `NeXroll/backend/`
- Packaged runtime backend: `NeXroll/backend/`
- Frontend (static build served by backend): `NeXroll/frontend/`
- Windows Service wrapper: `NeXroll/scripts/windows_service.py`
- System tray app: `NeXroll/scripts/tray_app.py`
- PyInstaller specs:
  - `NeXroll/build/neXroll.spec`
  - `NeXroll/build/NeXrollService.spec`
  - `NeXroll/build/NeXrollTray.spec`
  - `NeXroll/build/setup_plex_token.spec`
- NSIS installer: `NeXroll/build/installer.nsi`

---

## Troubleshooting

- â€œService did not respond in timeâ€
  - Ensure no other process is using port 9393; stop any `NeXroll.exe` thatâ€™s running, then start the service again.
- UI not reachable at http://localhost:9393
  - If you selected the firewall component, verify the inbound rule â€œNeXroll (TCP 9393)â€ exists. Otherwise, allow inbound TCP 9393 or re-run the installer and select the firewall option.
- Service logs location
  - Check `%ProgramData%\NeXroll\logs\service.log` for service-mode startup and health probe messages.
- Thumbnails not created
  - Install FFmpeg (choose the installer component, or install manually); reâ€‘upload a preroll.
- Tray icon not shown
  - Run â€œNeXroll Trayâ€ from Start Menu; pin it so itâ€™s always visible.
- Media server connection issues
  - Verify your Plex or Jellyfin server is reachable from the machine, and credentials are valid (retry `setup_plex_token.exe` for Plex if needed).

---

## License

MIT. Thirdâ€‘party components remain under their respective licenses.


---

## Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-FF5E5B?style=for-the-badge&amp;logo=ko-fi&amp;logoColor=white)](https://ko-fi.com/j_b__)



---

## Credits

Community Prerolls powered by [Typical Nerds](https://typicalnerds.uk/) - Thank you for making thousands of prerolls available to the community!
