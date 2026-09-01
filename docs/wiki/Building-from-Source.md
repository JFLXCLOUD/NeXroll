# NeXroll Build Instructions

## Prerequisites

- Python 3.10+
- Node.js 14+ and npm
- NSIS 3+ (for installer)
- PyInstaller

## Quick Build (All-in-One)

```powershell
# From the NeXroll repository root directory
cd NeXroll

# 1. Clean up previous builds
rm -r build\dist -Force -ErrorAction SilentlyContinue
rm -r frontend\build -Force -ErrorAction SilentlyContinue

# 2. Build frontend
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..

# 3. Build Python executables
cd build
pyinstaller --clean neXroll.spec
pyinstaller --clean NeXrollService.spec
pyinstaller --clean NeXrollTray.spec
pyinstaller --clean setup_plex_token.spec
cd ..

# 4. Build installer
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```

## Detailed Build Steps

### Step 1: Build the Frontend

The frontend must be built before creating the installers because the PyInstaller specs include the compiled frontend assets.

```powershell
cd NeXroll\frontend

# Clean previous builds
rm -r build -Force -ErrorAction SilentlyContinue

# Install dependencies
npm install --legacy-peer-deps

# Build optimized production bundle
npm run build

cd ..
```

**Output:** `NeXroll/frontend/build/` directory with static assets

### Step 2: Build Python Executables

PyInstaller bundles the Python backend and frontend assets into standalone executables.

```powershell
cd NeXroll\build

# Build each executable (runs can take 2-5 minutes each)
pyinstaller --clean neXroll.spec        # Main application GUI
pyinstaller --clean NeXrollService.spec # Windows Service
pyinstaller --clean NeXrollTray.spec    # System Tray app
pyinstaller --clean setup_plex_token.spec # Plex token setup tool

cd ..
```

**Output:** `NeXroll/build/dist/` directory with:
- `NeXroll.exe` - Main application
- `NeXrollService.exe` - Windows service background component
- `NeXrollTray.exe` - System tray application
- `setup_plex_token.exe` - Plex authentication tool

### Step 3: Build the Installer

The NSIS installer must be run **from the NeXroll directory** (same location as `installer.nsi`).

```powershell
cd NeXroll

# Build the installer
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```

**Output:** `NeXroll/NeXroll_Installer_1.5.12.exe`

## Important Notes

### Working Directory Matters!

The NSIS installer script uses relative paths. **You must run makensis from the NeXroll directory:**

```powershell
# ✅ CORRECT - Run from NeXroll directory
cd C:\path\to\NeXroll
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi

# ❌ WRONG - Running from wrong directory causes "Package error" 
cd C:\path\to
& "C:\Program Files (x86)\NSIS\makensis.exe" NeXroll\installer.nsi
```

### File Structure Expected by NSIS

```
NeXroll/
├── installer.nsi
├── frontend/
│   └── build/              ← Must be built first!
│       ├── index.html
│       ├── static/
│       └── ...
├── build/
│   └── dist/               ← PyInstaller output
│       ├── NeXroll.exe
│       ├── NeXrollService.exe
│       ├── NeXrollTray.exe
│       └── setup_plex_token.exe
├── NeXroll_ICON/
│   ├── icon_1758297097_16x16.ico
│   ├── icon_1758297097_32x32.ico
│   └── ...
└── start_windows.bat
```

### PyInstaller Spec Files

The `.spec` files in `NeXroll/build/` configure how PyInstaller bundles the application. Key paths referenced:

- `frontend/build/` - Frontend assets to include
- `backend/` - Python backend modules
- `version.py` - Version information

**If you move files or change directory structure, update the spec files:**

```python
# In neXroll.spec, NeXrollService.spec, etc.
datas=[
    (os.path.join(frontend_dir, 'build'), 'frontend/build'),  # Frontend assets
    (os.path.join(neXroll_dir, 'backend'), 'backend'),         # Backend code
    (os.path.join(neXroll_dir, 'version.py'), '.'),            # Version info
],
```

## Troubleshooting

### Error: "Package error: required build artifact '.\build\dist\NeXroll.exe' not found"

**Cause:** NSIS script not run from the NeXroll directory, or PyInstaller builds haven't been created yet.

**Fix:** 
1. Ensure you're in the `NeXroll/` directory
2. Ensure all PyInstaller builds completed successfully
3. Verify `build/dist/` directory exists with all executables

```powershell
# Check current directory
pwd

# Check dist files exist
ls NeXroll\build\dist\*.exe
```

### Error: "Frontend build not found" (during PyInstaller)

**Cause:** `npm run build` was skipped or failed.

**Fix:**
```powershell
cd NeXroll\frontend
npm run build
cd ..
```

### PyInstaller Takes Very Long or Fails

**Cause:** 
- First build is slower (creating all caches)
- Antivirus interference
- Insufficient disk space

**Fix:**
- Add `NeXroll\build` directory to antivirus exclusions
- Ensure 5+ GB free disk space
- Run with `--clean` to force rebuild

## Building on Different Machines

When building on a new machine or in CI/CD:

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/JFLXCLOUD/NeXroll.git
   cd NeXroll
   ```

2. **Install Python dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Install NSIS:**
   - Windows: Download from https://nsis.sourceforge.io/
   - Make sure it's in `C:\Program Files (x86)\NSIS\`

4. **Run the build script** (use the Quick Build section above)

## Distributing Built Files

**For End Users:**
- Distribute: `NeXroll_Installer_1.5.12.exe`
- This is a self-contained installer that includes all necessary files

**For Developers (Portable):**
- Include: `build/dist/` directory contents
- Users can run `NeXroll.exe` directly without installation
- Requires Python runtime dependencies already installed

**For Docker/Containers:**
- Use: `Dockerfile` (includes all Python/Node dependencies)
- See: `DOCKER.md` for instructions

## CI/CD Integration

To automate builds in GitHub Actions or similar:

```yaml
- name: Build Frontend
  run: |
    cd NeXroll/frontend
    npm install --legacy-peer-deps
    npm run build

- name: Build Executables
  run: |
    cd NeXroll/build
    pyinstaller --clean neXroll.spec
    pyinstaller --clean NeXrollService.spec
    pyinstaller --clean NeXrollTray.spec
    pyinstaller --clean setup_plex_token.spec

- name: Build Installer
  run: |
    cd NeXroll
    & "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi

- name: Upload Artifacts
  uses: actions/upload-artifact@v3
  with:
    name: NeXroll-Installer
    path: NeXroll/NeXroll_Installer_*.exe
```

## Version Updates

To update the version number:

1. **Update `NeXroll/version.py`:**
   ```python
   __version__ = "1.5.13"
   ```

2. **Update `NeXroll/installer.nsi`:**
   ```nsis
   !define APP_VERSION "1.5.13"
   ```

3. **Update frontend if needed:**
   ```json
   // NeXroll/frontend/package.json
   "version": "1.5.13"
   ```

4. **Rebuild everything** following the Quick Build steps above

The installer output file will automatically use the new version: `NeXroll_Installer_1.5.13.exe`
