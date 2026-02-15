
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

## Screenshots

### Dashboard
![Dashboard](docs/screenshots/Dashboard.png)

### Preroll Management
![Prerolls](docs/screenshots/prerolls.png)

### Schedule Management
![Schedule](docs/screenshots/schedule.png)

### Calendar Year View
![Calendar Year View](docs/screenshots/Calendar_Year.png)

### NeX-Up - Radarr & Sonarr Integration
![NeX-Up Connections](docs/screenshots/Nex-Up_Connections.png)

### Community Prerolls
![Community Prerolls](docs/screenshots/community_prerolls.png)

---

## Main Features

- **NeX-Up (NEW)** — Automatically download trailers for upcoming movies and TV shows from Radarr & Sonarr, with YouTube integration, dynamic intro generator, and sequence builder presets
- **Preroll Management** — Upload videos, auto-generate thumbnails, organize with tags and multi-category assignments
- **Smart Scheduling** — Daily, weekly, monthly, yearly schedules with recurrence patterns, fallback categories, and visual calendar views
- **Sequence Builder** — Create ordered preroll sequences with random blocks and fixed selections
- **Schedule Blend Mode** — Automatically blend prerolls from overlapping schedules (e.g., Christmas + New Year's)
- **Priority & Exclusive Mode** — Control which schedule wins with priority levels (1-10) and exclusive override
- **Holiday Browser** — Search holidays from 100+ countries and create schedules with one click
- **Holiday Presets** — 32+ built-in holidays with one-click category and schedule creation
- **Community Prerolls** — Browse and download from 1,300+ community prerolls at prerolls.uk
- **Media Server Integration** — Connect to Plex or Jellyfin with status monitoring and quick apply actions
- **Backup & Restore** — Full database and file backups with one-click restore
- **Windows Native** — One-click installer with optional Windows Service and System Tray app

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

## What 's Installed

- `NeXroll.exe`   the web application (FastAPI + bundled frontend)
- `NeXrollService.exe`   optional Windows Service wrapper
- `NeXrollTray.exe`   system tray app with quick actions
- `setup_plex_token.exe`   helper to obtain a stable Plex token

Start Menu shortcuts are created for NeXroll, NeXroll Tray, and Uninstall NeXroll. A desktop shortcut for NeXroll is also added.


---

## System Tray App

The tray icon provides quick actions:
- Open   launches http://localhost:9393 (default action)
- Start Service   attempts to start the Windows service (if installed)
- Stop Service   stops the Windows service (if installed)
- Restart Service   restarts the Windows service (if installed)
- Start App (portable)   starts the packaged app directly (non service)
- Check for updates   checks GitHub Releases and opens the latest release if a newer version is available (dialog is foreground and closable)
- About   shows app information (dialog is foreground and closable)
- GitHub   opens https://github.com/JFLXCLOUD/NeXroll
- Exit   closes the tray app

If you selected Start with Windows, the tray app launches automatically at login.

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

## First Time Setup

1. Open http://localhost:9393
2. Connect to your media server:
   - Connect to Plex or Jellyfin using URL and credentials
   - For Plex: Use your Plex URL and token; or run `setup_plex_token.exe` to create a long lived "stable token"
3. Upload prerolls, create categories, and configure schedules.

---

## Upgrade / Uninstall

- Upgrade: simply run the newer `NeXroll_Installer.exe` over the existing installation. Your configured Preroll storage path is preserved, and data is not removed.
- Uninstall: use "Uninstall NeXroll" from the Start Menu (or Apps & Features). The installer removes the service and shortcuts; your Preroll storage directory is not deleted.

---

## Building From Source

See the full packaging guide in `NeXroll/Docs/PACKAGING.md`.

Prerequisites (build machine):
- Python 3.10+ (build time only)
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

- "Service did not respond in time"
  - Ensure no other process is using port 9393; stop any `NeXroll.exe` that 's running, then start the service again.
- UI not reachable at http://localhost:9393
  - If you selected the firewall component, verify the inbound rule "NeXroll (TCP 9393)" exists. Otherwise, allow inbound TCP 9393 or re-run the installer and select the firewall option.
- Service logs location
  - Check `%ProgramData%\NeXroll\logs\service.log` for service-mode startup and health probe messages.
- Thumbnails not created
  - Install FFmpeg (choose the installer component, or install manually); re upload a preroll.
- Tray icon not shown
  - Run "NeXroll Tray" from Start Menu; pin it so it's always visible.
- Media server connection issues
  - Verify your Plex or Jellyfin server is reachable from the machine, and credentials are valid (retry `setup_plex_token.exe` for Plex if needed).

---

## License

MIT. Third party components remain under their respective licenses.


---

## Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-FF5E5B?style=for-the-badge&amp;logo=ko-fi&amp;logoColor=white)](https://ko-fi.com/j_b__)

Join the community on Discord for support, feature requests, and discussions:

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/R9eH7TbxEk)

Join the subreddit:

[![Reddit](https://img.shields.io/badge/Reddit-r%2FNeXroll-FF4500?style=for-the-badge&logo=reddit&logoColor=white)](https://www.reddit.com/r/NeXroll/)

---

## Credits

Community Prerolls powered by [Typical Nerds](https://typicalnerds.uk/) - Thank you for making thousands of prerolls available to the community!
