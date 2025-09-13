@echo off
echo ========================================
echo    NeXroll Installation and Setup
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
    echo Current directory: %CD%
    echo Looking for: %CD%\venv\Scripts\activate.bat
    dir venv\Scripts\activate.bat 2>nul
    pause
    exit /b 1
)
echo Virtual environment activated successfully.

echo Installing/updating dependencies in virtual environment...
pushd "%CD%\venv\Scripts"
python.exe -m pip install --upgrade pip
if exist "..\..\requirements.txt" (
    python.exe -m pip install -r "..\..\requirements.txt"
) else (
    python.exe -m pip install fastapi uvicorn sqlalchemy pydantic ffmpeg-python apscheduler requests plexapi python-multipart jinja2
)
popd

if errorlevel 1 (
    echo ERROR: Failed to install dependencies in virtual environment.
    pause
    exit /b 1
)

echo.
echo ========================================
echo    PLEX STABLE TOKEN SETUP (RECOMMENDED)
echo ========================================
echo.
echo For first-time users, it's recommended to set up a stable Plex token now.
echo This will enable the "Connect with Stable Token" option in the web interface.
echo.
echo Requirements:
echo - Plex Media Server must be installed and running
echo - You must be signed into Plex on this server
echo.
echo If you skip this step, you can run it later with: python setup_plex_token.py
echo.

:plex_setup_prompt
set /p setup_token="Would you like to run the Plex stable token setup now? (y/n): "
if /i "%setup_token%"=="y" (
    echo.
    echo Running Plex stable token setup...
    echo.
    call setup_token_only.bat
    if errorlevel 1 (
        echo.
        echo WARNING: Stable token setup failed or was cancelled.
        echo.
        set /p retry_setup="Would you like to try again? (y/n): "
        if /i "%retry_setup%"=="y" goto plex_setup_prompt
        echo.
        echo You can run the setup manually later with: setup_token_only.bat
        echo.
    ) else (
        echo.
        echo SUCCESS: Stable token setup completed!
        echo.
    )
) else if /i "%setup_token%"=="n" (
    echo.
    echo Skipping stable token setup.
    echo You can run it manually later with: setup_token_only.bat
    echo.
) else (
    echo Please enter 'y' for yes or 'n' for no.
    goto plex_setup_prompt
)

echo.
echo ========================================
echo    INSTALLATION COMPLETE!
echo ========================================
echo.
echo NeXroll has been successfully installed and configured.
echo.
echo To start NeXroll:
echo 1. Run start_windows.bat
echo 2. Or manually start with: venv\Scripts\python.exe backend/main.py
echo.
echo The web interface will be available at: http://localhost:9393
echo.
echo If you skipped the stable token setup, you can run it later:
echo python setup_plex_token.py
echo.
pause