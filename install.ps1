# NeXroll Installation and Setup One-Liner
# Run this in PowerShell with admin privileges if needed

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    NeXroll v1.0.1 Installation Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check command availability
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Function to download file
function Download-File($url, $output) {
    try {
        Invoke-WebRequest -Uri $url -OutFile $output -ErrorAction Stop
        Write-Host "Downloaded: $output" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to download $url" -ForegroundColor Red
        throw
    }
}

# Function to extract ZIP
function Extract-Zip($zipPath, $extractPath) {
    try {
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force -ErrorAction Stop
        Write-Host "Extracted to: $extractPath" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to extract $zipPath" -ForegroundColor Red
        throw
    }
}

# Check and install winget if needed
if (-not (Test-Command "winget")) {
    Write-Host "Installing winget..." -ForegroundColor Yellow
    # winget is part of App Installer, install it
    try {
        Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction Stop
        Write-Host "winget installed successfully" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to install winget. Please install App Installer manually." -ForegroundColor Red
        exit 1
    }
}

# Check and install Python
if (-not (Test-Command "python")) {
    Write-Host "Python not found. Installing Python..." -ForegroundColor Yellow
    try {
        winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements -e
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-Host "Python installed successfully" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to install Python. Please install manually from https://python.org" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Python found: $(python --version)" -ForegroundColor Green
}

# Check and install FFmpeg
if (-not (Test-Command "ffmpeg")) {
    Write-Host "FFmpeg not found. Installing FFmpeg..." -ForegroundColor Yellow
    try {
        winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements -e
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-Host "FFmpeg installed successfully" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to install FFmpeg. Please install manually from https://ffmpeg.org" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "FFmpeg found: $(ffmpeg -version | Select-Object -First 1)" -ForegroundColor Green
}

# Download NeXroll release
$releaseUrl = "https://github.com/JFLXCLOUD/NeXroll/releases/download/v1.0.1/NeXroll_v1.0.1_20250912_2120.zip"
$zipPath = "$env:TEMP\NeXroll_v1.0.1.zip"
$extractPath = "$env:USERPROFILE\NeXroll"

Write-Host "Downloading NeXroll v1.0.1..." -ForegroundColor Yellow
Download-File $releaseUrl $zipPath

Write-Host "Extracting NeXroll..." -ForegroundColor Yellow
Extract-Zip $zipPath $extractPath

# Find the actual NeXroll directory (ZIP contains a folder)
$neXrollDir = Get-ChildItem -Path $extractPath -Directory | Where-Object { $_.Name -like "NeXroll*" } | Select-Object -First 1
if (-not $neXrollDir) {
    Write-Host "ERROR: Could not find NeXroll directory after extraction" -ForegroundColor Red
    exit 1
}
$actualPath = $neXrollDir.FullName

# Change to NeXroll directory
Set-Location $actualPath

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
try {
    python -m pip install --upgrade pip
    if (Test-Path "requirements.txt") {
        python -m pip install -r requirements.txt
    } else {
        Write-Host "WARNING: requirements.txt not found, installing core dependencies..." -ForegroundColor Yellow
        python -m pip install fastapi uvicorn sqlalchemy pydantic ffmpeg-python apscheduler requests plexapi python-multipart jinja2
    }
    Write-Host "Dependencies installed successfully" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to install Python dependencies" -ForegroundColor Red
    exit 1
}

# Run Plex token setup
Write-Host "Setting up Plex token..." -ForegroundColor Yellow
try {
    if (Test-Path "setup_plex_token.py") {
        python setup_plex_token.py
        Write-Host "Plex token setup completed" -ForegroundColor Green
    } else {
        Write-Host "WARNING: setup_plex_token.py not found, skipping Plex token setup" -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERROR: Plex token setup failed. Please ensure Plex Media Server is installed and signed in." -ForegroundColor Red
    exit 1
}

# Create desktop shortcut for start script
$startScript = Join-Path $actualPath "start_windows.bat"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "NeXroll.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $startScript
$shortcut.WorkingDirectory = $actualPath
$shortcut.Description = "Start NeXroll Application"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    NeXroll Installation Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start NeXroll:" -ForegroundColor Green
Write-Host "1. Double-click the 'NeXroll' shortcut on your desktop" -ForegroundColor Green
Write-Host "2. Or run: $startScript" -ForegroundColor Green
Write-Host ""
Write-Host "The application will be available at http://localhost:9393" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Ensure Plex Media Server is running and signed in for full functionality." -ForegroundColor Yellow
Write-Host "Installation directory: $actualPath" -ForegroundColor Cyan