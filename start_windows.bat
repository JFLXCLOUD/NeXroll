@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Change to the directory where the batch file is located
cd /d "%~dp0"

REM Prefer packaged executable
if exist "%CD%\NeXroll.exe" (
    echo Starting NeXroll (packaged)...
    start "" /B "%CD%\NeXroll.exe"
    goto :EOF
)

REM Fallback: try virtual environment
if exist "venv\Scripts\python.exe" (
    echo Starting NeXroll via virtual environment Python...
    start "" /B "venv\Scripts\python.exe" -m uvicorn nexroll_backend.main:app --host 0.0.0.0 --port 9393
    goto :EOF
)

REM Fallback: system Python
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Starting NeXroll via system Python...
    start "" /B python -m uvicorn nexroll_backend.main:app --host 0.0.0.0 --port 9393
    goto :EOF
)

echo ERROR: Could not start NeXroll. No packaged exe or Python found.
pause
