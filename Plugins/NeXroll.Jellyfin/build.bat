@echo off
echo ============================================================
echo   Building NeXroll Intros - Jellyfin Plugin
echo ============================================================
echo.

REM Requires .NET 8 SDK
dotnet --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: .NET SDK not found. Install from https://dot.net/download
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Restoring packages...
dotnet restore
if errorlevel 1 (
    echo ERROR: Package restore failed.
    pause
    exit /b 1
)

echo.
echo Building Release...
dotnet build -c Release --no-restore
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
echo Publishing...
dotnet publish -c Release --no-build -o "%~dp0publish"
if errorlevel 1 (
    echo ERROR: Publish failed.
    pause
    exit /b 1
)

echo.
echo Packaging release zip (plugin DLL + meta.json + thumb.png)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package.ps1" -NoPublish
if errorlevel 1 (
    echo ERROR: Packaging failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build complete!
echo   Output: %~dp0publish\NeXroll.Jellyfin.dll
echo   Release zip: %~dp0NeXroll.Jellyfin-^<version^>.zip
echo.
echo   To install (folder):
echo     1. Copy these files into  Jellyfin\plugins\NeXroll Intros\ :
echo          NeXroll.Jellyfin.dll, meta.json, thumb.png
echo        (or just extract the release zip there)
echo     2. Restart Jellyfin
echo     3. Go to Dashboard ^> Plugins ^> NeXroll Intros
echo     4. Enter your NeXroll server URL
echo ============================================================
pause
