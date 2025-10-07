# NeXroll v1.0.0 — Initial Windows Installer Release

Release date: 2025-09-17

This is the first stable release of NeXroll packaged for Windows with a single installer, self-contained executables, an optional Windows Service, and a lightweight system tray app.

---

## Highlights

- Single Windows installer (NSIS) with branded icon
- Self-contained executables (PyInstaller) — no Python required on user machines
- Optional Windows Service (NeXrollService) for background/headless operation
- New System Tray app (NeXrollTray) with quick actions: Open, About, GitHub, Exit
- Plex Stable Token setup tool (setup_plex_token.exe) with Registry and Preferences.xml detection plus manual fallback
- FFmpeg integration for thumbnail generation (offered via installer component using winget)
- Modern web UI served from the packaged backend (FastAPI + bundled frontend)
- Preroll management: upload, tags, categories, thumbnails, size/duration
- Scheduling engine with holiday presets and category-to-Plex syncing (multi-preroll)
- Consistent NeXroll icon across EXEs, tray, Start Menu shortcuts, and installer

---

## System Requirements

- Windows 10/11 x64
- Network access to your Plex server
- FFmpeg for thumbnails (installer can install it for you via winget)
- No Python required

---

## Assets (attach to GitHub Release)

Primary distribution:
- NeXroll_Installer.exe

Optional portable executables (if you want to provide them separately):
- NeXroll.exe
- NeXrollService.exe
- NeXrollTray.exe
- setup_plex_token.exe

Checksums (recommended):
- Generate SHA256 for each asset:
  - `certutil -hashfile NeXroll_Installer.exe SHA256`

---

## Install

1) Download `NeXroll_Installer.exe` from the release page.  
2) Run the installer (administrator recommended).  
3) Choose:
   - Install location (default: `C:\Program Files\NeXroll`)
   - Preroll storage directory (any drive)
4) Optional components:
   - Install as Windows Service (`NeXrollService`)
   - Run Plex Stable Token setup
   - Start with Windows (adds NeXrollTray to Startup)
   - Install FFmpeg via winget
5) Finish; use the Start Menu shortcut or open `http://localhost:9393`

PowerShell one‑liner (download + launch installer):

```powershell
$release = Invoke-RestMethod https://api.github.com/repos/JFLXCLOUD/NeXroll/releases/latest
$asset = $release.assets | Where-Object { $_.name -eq 'NeXroll_Installer.exe' } | Select-Object -First 1
$dest = Join-Path $env:TEMP $asset.name
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest
Start-Process -FilePath $dest
```

Silent install (defaults):

```powershell
& "$env:TEMP\NeXroll_Installer.exe" /S
```

Defaults: `InstallDir=C:\Program Files\NeXroll`; default Preroll path under Documents. Use interactive mode to customize.

---

## Post‑Install Verification

- Start Menu → NeXroll (launches app)
- Start Menu → NeXroll Tray (shows tray icon with menu)
- Visit `http://localhost:9393` and ensure:
  - Dashboard loads
  - Scheduler status visible
  - Plex status panel accessible

Optional service check:
- Open Services.msc and locate “NeXrollService”
- Start/Stop as needed
- Or use CLI from InstallDir:
  - `NeXrollService.exe start`
  - `NeXrollService.exe stop`

---

## First‑Time Plex Setup

- If you already have a Plex token, enter your Plex URL and token in the Plex tab.
- Otherwise run `setup_plex_token.exe` (installed with NeXroll) and follow prompts:
  - Windows Registry lookup (preferred)
  - Preferences.xml lookup from common locations
  - Manual token entry fallback
- In the app, use “Connect with Stable Token” to connect automatically.

---

## Features in v1.0.0

- Preroll uploads (single/multiple) with duration and thumbnail generation
- Tagging, categories, and descriptions
- Holiday presets and flexible schedules (monthly/yearly/custom/holiday)
- Category-to-Plex syncing, including multi-preroll concatenation
- Built-in backup/restore endpoints for data and files
- Stable Token workflow and status endpoints
- Static serving of uploaded thumbnails and packaged frontend
- Robust Windows distribution:
  - Self-contained EXEs via PyInstaller
  - NSIS installer with branded icon and components
  - Windows Service wrapper (pywin32)
  - System Tray app (pystray + Pillow) with NeXroll icon

---

## Known Issues & Workarounds

- Service may report “did not respond in time” if port 9393 is in use  
  - Ensure no other NeXroll instance is running, then start the service again.
- Thumbnails require FFmpeg  
  - Use the installer option to install FFmpeg via winget, or install manually.
- SmartScreen warnings (unsigned binaries)  
  - Click “More info” → “Run anyway” or code‑sign the binaries for production environments.
- Plex token fetch fails  
  - Make sure Plex Media Server is running and you are signed in; rerun `setup_plex_token.exe`; try manual entry.

---

## Uninstall

- Start Menu → Uninstall NeXroll, or remove from Apps & Features
- The Preroll storage directory you selected is not removed

---

## Support

If NeXroll is helpful, consider supporting development:
- Ko‑fi: https://ko-fi.com/j_b__

---

## Acknowledgements

- FastAPI, Uvicorn, SQLAlchemy, Pydantic
- Requests, ffmpeg-python
- pywin32 (Windows Service)
- pystray + Pillow (tray app)
- NSIS (installer)
- PyInstaller (packaging)

---

## SHA256 Examples

```powershell
certutil -hashfile NeXroll_Installer.exe SHA256
certutil -hashfile NeXroll.exe SHA256
certutil -hashfile NeXrollService.exe SHA256
certutil -hashfile NeXrollTray.exe SHA256
certutil -hashfile setup_plex_token.exe SHA256
```

---

## Changelog Summary

- Initial Windows installer distribution with icon branding
- Self‑contained EXEs (app, service, tray, token tool)
- Optional Windows Service and tray app
- Stable Token workflow and Plex integration
- FFmpeg thumbnailing support (optional winget install)
- UI, scheduling, category sync, and backup/restore