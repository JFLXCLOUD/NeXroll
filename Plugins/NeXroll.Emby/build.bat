@echo off
echo ============================================================
echo   Building NeXroll Intros - Emby Plugin
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

REM Emby has no NuGet SDK - the server DLLs must be present in emby-libs\.
if not exist "%~dp0..\..\emby-libs\MediaBrowser.Common.dll" (
    echo ERROR: emby-libs not found.
    echo        Copy MediaBrowser.Common.dll, MediaBrowser.Controller.dll and
    echo        MediaBrowser.Model.dll from your Emby Server install into the
    echo        repo's emby-libs\ folder ^(see NeXroll.Emby.csproj^).
    pause
    exit /b 1
)

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
echo Packaging release zip (single DLL, icon embedded)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package.ps1" -NoBuild
if errorlevel 1 (
    echo ERROR: Packaging failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build complete!
echo   Output: %~dp0bin\Release\net8.0\NeXroll.Emby.dll
echo   Release zip: %~dp0NeXroll.Emby-^<version^>.zip
echo.
echo   To install:
echo     1. Copy NeXroll.Emby.dll into  Emby\plugins\
echo        ^(or extract the release zip there^)
echo     2. Restart Emby
echo     3. Go to Dashboard ^> Plugins ^> NeXroll Intros
echo     4. Enter your NeXroll server URL
echo ============================================================
pause
