NeXroll Windows Packaging and Installer Guide

Overview
This guide explains how to build production-ready Windows executables and the single-click installer for NeXroll. The packaging approach removes the need for a Python virtual environment on target machines by bundling the Python runtime and dependencies into self-contained executables using PyInstaller, and delivers a user-friendly installer using NSIS.

What you will build
- NeXroll app executable: dist\NeXroll.exe
- Windows Service wrapper executable: dist\NeXrollService.exe
- System Tray executable: dist\NeXrollTray.exe
- Plex Stable Token setup executable: dist\setup_plex_token.exe
- Single installer: NeXroll\NeXroll_Installer_1.0.1.exe

Source files of interest
- App spec: [NeXroll/neXroll.spec](NeXroll/neXroll.spec)
- Packaged runtime entry: [NeXroll/launcher.py](NeXroll/launcher.py)
- Runtime backend package (packaged): [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py)
- Development backend (dev mode): [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py)
- Windows service wrapper: [NeXroll/windows_service.py](NeXroll/windows_service.py)
- Service spec: [NeXroll/NeXrollService.spec](NeXroll/NeXrollService.spec)
- System tray app: [NeXroll/tray_app.py](NeXroll/tray_app.py), spec: [NeXroll/NeXrollTray.spec](NeXroll/NeXrollTray.spec)
- Plex token setup spec: [NeXroll/setup_plex_token.spec](NeXroll/setup_plex_token.spec)
- NSIS installer: [NeXroll/installer.nsi](NeXroll/installer.nsi)
- Optional helper: [NeXroll/start_windows.bat](NeXroll/start_windows.bat)

Prerequisites (Build machine only)
- Windows 10/11
- Python 3.10+ (build-time only)
- Pip packages:
  - pyinstaller
  - pywin32
- NSIS (Nullsoft Scriptable Install System) 3.x
  - Ensure makensis is on PATH
- Git (optional)

Install build-time dependencies
From a terminal in the repo root:

- Upgrade pip:
  py -m pip install --upgrade pip

- Install app requirements (optional for building exes, but useful if you test via Python):
  py -m pip install -r NeXroll/requirements.txt

- Install packaging dependencies:
  py -m pip install pyinstaller pywin32

Clean previous build artifacts (optional)
Delete dist/ and build/ if they exist to ensure a clean build:

- Using PowerShell:
  Remove-Item -Recurse -Force .\dist, .\build -ErrorAction SilentlyContinue

Build the executables
Run from repository root so relative paths match the spec files.

- Build the application EXE:
  py -m PyInstaller -y NeXroll\neXroll.spec

- Build the Windows Service EXE:
  py -m PyInstaller -y NeXroll\NeXrollService.spec

- Build the System Tray EXE:
  py -m PyInstaller -y NeXroll\NeXrollTray.spec

- Build the Plex token setup EXE:
  py -m PyInstaller -y NeXroll\setup_plex_token.spec

After these, you should have:
- dist\NeXroll.exe
- dist\NeXrollService.exe
- dist\NeXrollTray.exe
- dist\setup_plex_token.exe

Create the single installer (NSIS)
The NSIS script expects to find the executables under dist\... relative to the repository root. Run makensis from the repository root:

- Build the installer:
  makensis NeXroll\installer.nsi

Output:
- NeXroll\NeXroll_Installer_1.0.1.exe

Installer features
The installer created from [NeXroll/installer.nsi](NeXroll/installer.nsi):
- Lets the user choose:
  - Installation directory (default: C:\Program Files\NeXroll)
  - Preroll storage directory (user prompt)
- Offers optional components:
  - Install as Windows Service (NeXrollService)
  - Run Plex Stable Token setup (setup_plex_token.exe)
  - Start with Windows (Startup shortcut)
  - Install Dependencies (FFmpeg via winget)
- Writes to registry:
  - HKLM\Software\NeXroll\InstallDir
  - HKLM\Software\NeXroll\PrerollPath
- Installs only runtime files (no venv, no source)
- Uninstall removes shortcuts, service, and install folder (keeps preroll storage)

Runtime behavior (target machines)
- No Python or venv required. NeXroll.exe bundles the Python runtime and dependencies.
- FFmpeg is needed for generating thumbnails; the installer includes an optional component to install FFmpeg via winget.
- Database and logs:
  - Database: %ProgramData%\NeXroll\nexroll.db (auto-created/migrated on first run)
  - Logs: %ProgramData%\NeXroll\logs\app.log (packaged runtime), and %ProgramData%\NeXroll\logs\service.log (Windows service)
- Preroll path is read at runtime:
  - Environment variable NEXROLL_PREROLL_PATH if set, otherwise
  - HKLM\Software\NeXroll\PrerollPath from installer, otherwise
  - Falls back to {InstallDir}\data
- Frontend static assets are bundled and served directly by the backend.

Windows Service usage (optional)
If you installed the service during setup, it will be registered as NeXrollService.

Manual service commands (run as Administrator from the install directory):
- Install:
  NeXrollService.exe install

- Start:
  NeXrollService.exe start

- Stop:
  NeXrollService.exe stop

- Remove:
  NeXrollService.exe remove

Manual start without service
From the install directory, double-click NeXroll.lnk (desktop or Start Menu), or run:

- If packaged:
  NeXroll.exe

- Fallback via Python (build/testing machine only):
  py -m uvicorn nexroll_backend.main:app --host 0.0.0.0 --port 9393

Web interface
- http://localhost:9393

Plex stable token setup
- If not run during install, you can execute:
  setup_plex_token.exe

This will attempt:
- Windows Registry (preferred)
- Preferences.xml in known locations
- Manual token entry fallback

Distribution checklist
- Verify NeXroll\NeXroll_Installer.exe is produced.
- Install on a fresh Windows VM and validate:
  - App runs (service or launcher)
  - Preroll path is created/exists
  - Upload videos and confirm thumbnails (FFmpeg present)
  - Plex connection works (manual token or stable token)
- Ensure the install directory contains only:
  - NeXroll.exe
  - NeXrollService.exe
  - setup_plex_token.exe
  - start_windows.bat
  - uninstall.exe (after install)
  - No venv/, src/, build/ folders

Notes
- Code signing: Consider code-signing executables and installer for better SmartScreen reputation.
- FFmpeg distribution: If you prefer bundling FFmpeg binaries instead of winget, add them as files in [NeXroll/installer.nsi](NeXroll/installer.nsi) and adjust PATH or call them with absolute paths.
- Logs/troubleshooting: For packaged runs, tail %ProgramData%\NeXroll\logs\app.log. When installed as a service, tail %ProgramData%\NeXroll\logs\service.log. You can also run NeXroll.exe manually to observe console logs.

Rationale: Why this approach
- Shipping venv + Python scripts complicates deployment and maintenance.
- PyInstaller bundles Python and modules eliminating per-host Python setup.
- NSIS provides a cohesive UX: pick folders, optional components, registry, uninstall, and service integration.
- Service wrapper ensures NeXroll runs headless and restarts if it crashes.

End-to-End quick build
- Clean:
  Remove-Item -Recurse -Force .\dist, .\build -ErrorAction SilentlyContinue

- Build EXEs:
  py -m PyInstaller -y NeXroll\neXroll.spec
  py -m PyInstaller -y NeXroll\NeXrollService.spec
  py -m PyInstaller -y NeXroll\NeXrollTray.spec
  py -m PyInstaller -y NeXroll\setup_plex_token.spec

- Build Installer:
  makensis NeXroll\installer.nsi

- Deliver:
  NeXroll\NeXroll_Installer_1.0.1.exe