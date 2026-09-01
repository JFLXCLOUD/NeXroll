# NeXroll Installer - Error Resolution Guide

## Error Message

```
Package error: required build artifact '.\build\dist\NeXroll.exe' not found.
Run Pyinstaller to produce build\dist\NeXroll.exe before creating the installer.
```

## Why This Happens

This error occurs when you try to build the installer without first:

1. Building the frontend React application
2. Running PyInstaller to create the executables

**The installer is just a wrapper.** It needs the actual `.exe` files to package. If those files don't exist, the installer can't be created.

## Solution

Follow these steps in **exact order**:

### Step 1: Build the Frontend (Required!)

```powershell
cd NeXroll
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..
```

Wait for this to complete. You should see "Compiled successfully" or similar.

**Check:** Verify `NeXroll/frontend/build/` directory exists with files in it.

### Step 2: Build the Executables with PyInstaller (Required!)

```powershell
cd build
pyinstaller --clean neXroll.spec
pyinstaller --clean NeXrollService.spec
pyinstaller --clean NeXrollTray.spec
pyinstaller --clean setup_plex_token.spec
cd ..
```

Each build takes 2-5 minutes. Wait for all four to complete.

**Check:** Verify `NeXroll/build/dist/` directory exists with these files:
- NeXroll.exe (≈22 MB)
- NeXrollService.exe (≈27 MB)
- NeXrollTray.exe (≈25 MB)
- setup_plex_token.exe (≈18 MB)

### Step 3: Build the Installer

**IMPORTANT:** You must be in the `NeXroll/` directory (same directory as `installer.nsi`)

```powershell
# Make sure you're in the right directory!
cd C:\path\to\NeXroll  # ← Adjust this path to your location

# Then run NSIS
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```

You should see output like:
```
Processing script file: "installer.nsi"
...
Total size: 96128778 / 99554196 bytes (96.5%)
```

**Output:** `NeXroll_Installer_1.5.12.exe` will be created in the `NeXroll/` directory.

## Common Issues & Fixes

### Issue: "makensis.exe: command not found"

**Solution:** NSIS is not installed or not in PATH.

**Fix:**
1. Download NSIS 3+ from https://nsis.sourceforge.io/
2. Install to default location (`C:\Program Files (x86)\NSIS\`)
3. Restart terminal/PowerShell after installation

### Issue: "Frontend build not found" (PyInstaller error)

**Solution:** You skipped or the `npm run build` failed.

**Fix:**
```powershell
cd NeXroll/frontend
rm -r build -Force -ErrorAction SilentlyContinue
npm run build
```

### Issue: Still getting "build\dist\NeXroll.exe not found"

**Solution:** You're not in the `NeXroll/` directory when running NSIS.

**Fix:**
```powershell
# Verify your current directory
pwd

# Output should end with: ...NeXroll
# If not, change to the right directory:
cd C:\path\to\NeXroll

# Then try again:
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi
```

### Issue: PyInstaller fails or takes forever

**Solution:** Antivirus or insufficient resources.

**Fix:**
1. Add `NeXroll\build` to antivirus exclusions
2. Ensure you have 5+ GB free disk space
3. Close other applications
4. Try again with fresh builds:
   ```powershell
   cd build
   rm -r dist -Force -ErrorAction SilentlyContinue
   pyinstaller --clean neXroll.spec
   ```

## Full Build Script (Copy & Paste)

If you want to build everything in one go, save this as `build-all.ps1`:

```powershell
# Build All NeXroll Installers (PowerShell)

# Configuration
$NeXrollPath = "C:\path\to\NeXroll"  # ← ADJUST THIS PATH!

# Navigate to project
Set-Location $NeXrollPath

Write-Host "Step 1: Building Frontend..." -ForegroundColor Cyan
Set-Location frontend
npm install --legacy-peer-deps
npm run build
Set-Location ..

Write-Host "Step 2: Building Executables..." -ForegroundColor Cyan
Set-Location build
pyinstaller --clean neXroll.spec
pyinstaller --clean NeXrollService.spec
pyinstaller --clean NeXrollTray.spec
pyinstaller --clean setup_plex_token.spec
Set-Location ..

Write-Host "Step 3: Building Installer..." -ForegroundColor Cyan
& "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi

Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Installer created: NeXroll_Installer_1.5.12.exe" -ForegroundColor Green
```

Run with:
```powershell
powershell -ExecutionPolicy Bypass -File build-all.ps1
```

## Need More Help?

See: `BUILD_INSTRUCTIONS.md` in the NeXroll repository for detailed information.

Or open an issue on GitHub: https://github.com/JFLXCLOUD/NeXroll/issues
