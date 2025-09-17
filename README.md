# NeXroll
<div align="center">
  <img src="frontend/NeXroll_Logo_WHT.png" alt="NeXroll Logo" width="400"/>
  <br>
</div>

NeXroll is a Windows-ready Plex preroll management system with a modern web UI, an optional Windows Service, and a lightweight system tray app. All executables are self‑contained (no Python required on user machines), and a single installer configures everything end‑to‑end.

Web UI: http://localhost:9393

Repository layout lives under `NeXroll/`, and the single installer is built from the repo using PyInstaller + NSIS.

---

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
5. Finish the installer and open the app from the Start Menu or tray menu.

After install, visit http://localhost:9393 to use the web UI.
### PowerShell one‑liner (download + launch installer)

```powershell
$release = Invoke-RestMethod https://api.github.com/repos/JFLXCLOUD/NeXroll/releases/latest
$asset = $release.assets | Where-Object { $_.name -eq 'NeXroll_Installer.exe' } | Select-Object -First 1
$dest = Join-Path $env:TEMP $asset.name
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest
Start-Process -FilePath $dest
```

### Silent install (defaults)

```powershell
&amp; "$env:TEMP\NeXroll_Installer.exe" /S
```

Silent mode installs to `C:\Program Files\NeXroll` and uses the default Preroll path. Use interactive mode to customize components or directories.

---

## What’s Installed

- `NeXroll.exe` — the web application (FastAPI + bundled frontend)
- `NeXrollService.exe` — optional Windows Service wrapper
- `NeXrollTray.exe` — system tray app with quick actions
- `setup_plex_token.exe` — helper to obtain a stable Plex token
- `favicon.ico` — NeXroll icon used across executables and the installer

Start Menu shortcuts are created for NeXroll, NeXroll Tray, and Uninstall NeXroll. A desktop shortcut for NeXroll is also added.

---

## System Tray App

The tray icon provides quick actions:
- Open — launches http://localhost:9393
- About — shows app information
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

Tip: if a previous NeXroll instance is still running and occupying port 9393, the service may need a second start attempt after that instance is closed.

---

## Requirements (User machines)

- Windows 10/11 x64
- FFmpeg for thumbnail generation (you can install it from the installer’s optional components, or manually)
- Network access to your Plex server
- No Python required on user machines

---

## First‑Time Setup

1. Open http://localhost:9393
2. Connect to Plex:
   - Use your Plex URL and token; or
   - Run `setup_plex_token.exe` to create a long‑lived “stable token,” then connect using that token.
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
- `NeXroll\NeXroll_Installer.exe`

---


## Project Structure (key files)

- Backend (FastAPI): `NeXroll/backend/`
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
- Thumbnails not created
  - Install FFmpeg (choose the installer component, or install manually); re‑upload a preroll.
- Tray icon not shown
  - Run “NeXroll Tray” from Start Menu; pin it so it’s always visible.
- Plex connection issues
  - Verify Plex is reachable from the machine, and the token is valid (retry `setup_plex_token.exe` if needed).

---

## License

MIT. Third‑party components remain under their respective licenses.


---

## Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-FF5E5B?style=for-the-badge&amp;logo=ko-fi&amp;logoColor=white)](https://ko-fi.com/j_b__)


