@echo off
echo ========================================
echo    NeXroll Setup and Startup Script
echo ========================================
echo.

REM Change to the script's directory to ensure we can find the executable
cd /d "%~dp0"

echo Working directory: %CD%
echo.

echo Checking Python installation...

REM Try multiple ways to find Python
set PYTHON_CMD=
set PYTHON_FOUND=0

echo Trying 'python' command...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    set PYTHON_FOUND=1
    echo Found Python via 'python' command
) else (
    echo 'python' command not found, trying alternatives...
)

if %PYTHON_FOUND% equ 0 (
    echo Trying 'python3' command...
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3
        set PYTHON_FOUND=1
        echo Found Python via 'python3' command
    )
)

if %PYTHON_FOUND% equ 0 (
    echo Trying 'py' launcher...
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        set PYTHON_FOUND=1
        echo Found Python via 'py' launcher
    )
)

if %PYTHON_FOUND% equ 0 (
    echo Checking common Python installation locations...
    if exist "C:\Python38\python.exe" (
        set PYTHON_CMD=C:\Python38\python.exe
        set PYTHON_FOUND=1
        echo Found Python 3.8 in C:\Python38\
    ) else if exist "C:\Python39\python.exe" (
        set PYTHON_CMD=C:\Python39\python.exe
        set PYTHON_FOUND=1
        echo Found Python 3.9 in C:\Python39\
    ) else if exist "C:\Python310\python.exe" (
        set PYTHON_CMD=C:\Python310\python.exe
        set PYTHON_FOUND=1
        echo Found Python 3.10 in C:\Python310\
    ) else if exist "C:\Python311\python.exe" (
        set PYTHON_CMD=C:\Python311\python.exe
        set PYTHON_FOUND=1
        echo Found Python 3.11 in C:\Python311\
    ) else if exist "C:\Python312\python.exe" (
        set PYTHON_CMD=C:\Python312\python.exe
        set PYTHON_FOUND=1
        echo Found Python 3.12 in C:\Python312\
    )
)

if %PYTHON_FOUND% equ 0 (
    echo.
    echo ========================================
    echo    PYTHON NOT FOUND - INSTALLATION REQUIRED
    echo ========================================
    echo.
    echo NeXroll requires Python 3.8 or higher to run.
    echo.
    echo To fix this issue:
    echo.
    echo 1. Download Python from: https://python.org/downloads/
    echo 2. Run the installer
    echo 3. IMPORTANT: Check "Add Python to PATH" during installation
    echo 4. Restart this script after installation
    echo.
    echo If Python is already installed:
    echo - Check that it's added to your PATH environment variable
    echo - Try running 'python --version' in a new Command Prompt
    echo - Or manually add Python to PATH in System Properties
    echo.
    echo For help with PATH setup, see:
    echo https://docs.python.org/3/using/windows.html#finding-the-python-executable
    echo.
    pause
    exit /b 1
)

echo Python found! Using: %PYTHON_CMD%

echo Checking for requirements.txt...
if not exist requirements.txt (
    echo WARNING: requirements.txt not found. Installing basic dependencies...
    %PYTHON_CMD% -m pip install fastapi uvicorn
    if errorlevel 1 (
        echo ERROR: Failed to install basic dependencies.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
) else (
    echo Installing Python dependencies from requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo WARNING: Some dependencies may have failed to install.
        echo Trying to install core dependencies...
        %PYTHON_CMD% -m pip install fastapi uvicorn
        if errorlevel 1 (
            echo ERROR: Failed to install core dependencies.
            echo Please check your internet connection and try again.
            pause
            exit /b 1
        )
    )
)

echo.
echo Setting up virtual environment...
if not exist venv (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Installing/updating dependencies in virtual environment...
python -m pip install --upgrade pip
if exist requirements.txt (
    python -m pip install -r requirements.txt
) else (
    python -m pip install fastapi uvicorn sqlalchemy pydantic ffmpeg-python apscheduler requests plexapi python-multipart jinja2
)

if errorlevel 1 (
    echo ERROR: Failed to install dependencies in virtual environment.
    pause
    exit /b 1
)

echo.
echo Starting NeXroll Backend...
start /B python -m uvicorn backend.main:app --host 0.0.0.0 --port 9393 --reload
echo Backend started. Opening frontend...
timeout /t 3 /nobreak > nul
start http://localhost:9393
echo.
echo ========================================
echo NeXroll is running at http://localhost:9393
echo ========================================
echo.
echo Note: Backend is running in virtual environment.
echo To stop the backend, close the command window or press Ctrl+C.
echo.
pause
