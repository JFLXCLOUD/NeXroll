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
function Get-NeXrollFile($url, $output) {
    try {
        Invoke-WebRequest -Uri $url -OutFile $output -ErrorAction Stop
        Write-Host "Downloaded: $output" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to download $url" -ForegroundColor Red
        throw
    }
}

# Function to extract ZIP
function Expand-NeXrollArchive($zipPath, $extractPath) {
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
Get-NeXrollFile $releaseUrl $zipPath

Write-Host "Extracting NeXroll..." -ForegroundColor Yellow
Expand-NeXrollArchive $zipPath $extractPath

# Find the actual NeXroll directory (ZIP contains a folder)
Write-Host "Looking for NeXroll directory in: $extractPath" -ForegroundColor Yellow
$neXrollDir = Get-ChildItem -Path $extractPath -Directory | Where-Object { $_.Name -like "NeXroll*" } | Select-Object -First 1
if (-not $neXrollDir) {
    Write-Host "ERROR: Could not find NeXroll directory after extraction" -ForegroundColor Red
    Write-Host "Contents of ${extractPath}:" -ForegroundColor Yellow
    Get-ChildItem -Path $extractPath | Format-Table Name, PSIsContainer
    exit 1
}
$actualPath = $neXrollDir.FullName
Write-Host "Found NeXroll directory: $actualPath" -ForegroundColor Green

# Change to NeXroll directory
Set-Location $actualPath
Write-Host "Changed to directory: $(Get-Location)" -ForegroundColor Green

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

# Run Plex token setup (optional)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    PLEX STABLE TOKEN SETUP (RECOMMENDED)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "For first-time users, it's recommended to set up a stable Plex token now." -ForegroundColor White
Write-Host "This will enable the 'Connect with Stable Token' option in the web interface." -ForegroundColor White
Write-Host ""
Write-Host "Requirements:" -ForegroundColor Yellow
Write-Host "- Plex Media Server must be installed and running" -ForegroundColor Yellow
Write-Host "- You must be signed into Plex on this server" -ForegroundColor Yellow
Write-Host ""
Write-Host "If you skip this step, you can run it later with: python setup_plex_token.py" -ForegroundColor Cyan
Write-Host ""

$setupToken = Read-Host "Would you like to run the Plex stable token setup now? (y/n)"
if ($setupToken -eq "y" -or $setupToken -eq "Y") {
    Write-Host ""
    Write-Host "Running Plex stable token setup..." -ForegroundColor Green
    Write-Host ""
    try {
        if (Test-Path "setup_plex_token.py") {
            python setup_plex_token.py
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "SUCCESS: Stable token has been configured!" -ForegroundColor Green
                Write-Host "You can now use the 'Connect with Stable Token' option in NeXroll." -ForegroundColor Green
            } elseif ($LASTEXITCODE -eq 1) {
                Write-Host ""
                Write-Host "WARNING: Stable token setup failed or was cancelled." -ForegroundColor Yellow
                Write-Host "You can run it manually later with: python setup_plex_token.py" -ForegroundColor Cyan
            } else {
                Write-Host ""
                Write-Host "WARNING: Setup script exited with unexpected code: $LASTEXITCODE" -ForegroundColor Yellow
                Write-Host "The setup may or may not have been successful." -ForegroundColor Yellow
            }
        } else {
            Write-Host "ERROR: setup_plex_token.py not found" -ForegroundColor Red
        }
    } catch {
        Write-Host ""
        Write-Host "ERROR: Failed to run Plex token setup" -ForegroundColor Red
        Write-Host "You can run it manually later with: python setup_plex_token.py" -ForegroundColor Cyan
        Write-Host "Make sure Plex Media Server is installed and signed in first." -ForegroundColor Cyan
    }
} else {
    Write-Host ""
    Write-Host "Skipping stable token setup." -ForegroundColor Yellow
    Write-Host "You can run it manually later with: python setup_plex_token.py" -ForegroundColor Cyan
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

# Start NeXroll automatically
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "    Starting NeXroll Application..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$startScript = Join-Path $actualPath "start_windows.bat"
if (Test-Path $startScript) {
    Write-Host "Starting NeXroll..." -ForegroundColor Green
    try {
        # Start NeXroll in a new window
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$startScript`"" -WindowStyle Normal
        Write-Host "NeXroll started successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host "    NeXroll Installation & Startup Complete!" -ForegroundColor Cyan
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🎉 Installation Summary:" -ForegroundColor Green
        Write-Host "✓ Python installed and configured" -ForegroundColor Green
        Write-Host "✓ FFmpeg installed" -ForegroundColor Green
        Write-Host "✓ NeXroll downloaded and extracted" -ForegroundColor Green
        Write-Host "✓ Python dependencies installed" -ForegroundColor Green
        Write-Host "✓ Plex token configured" -ForegroundColor Green
        Write-Host "✓ Desktop shortcut created" -ForegroundColor Green
        Write-Host "✓ NeXroll application started" -ForegroundColor Green
        Write-Host ""
        Write-Host "🌐 Web Interface:" -ForegroundColor Cyan
        Write-Host "   The application will be available at: http://localhost:9393" -ForegroundColor White
        Write-Host ""
        Write-Host "📝 Next Steps:" -ForegroundColor Yellow
        Write-Host "   1. Wait for the NeXroll window to appear" -ForegroundColor White
        Write-Host "   2. Open http://localhost:9393 in your web browser" -ForegroundColor White
        Write-Host "   3. Configure your Plex connection if needed" -ForegroundColor White
        Write-Host "   4. Upload your preroll videos and create schedules" -ForegroundColor White
        Write-Host ""
        Write-Host "📂 Installation directory: $actualPath" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "💡 Tips:" -ForegroundColor Magenta
        Write-Host "   - Keep Plex Media Server running for full functionality" -ForegroundColor White
        Write-Host "   - Use the desktop shortcut for easy access" -ForegroundColor White
        Write-Host "   - Check the web interface for configuration options" -ForegroundColor White
    } catch {
        Write-Host "WARNING: Failed to start NeXroll automatically." -ForegroundColor Yellow
        Write-Host "You can start it manually:" -ForegroundColor Cyan
        Write-Host "1. Double-click the 'NeXroll' shortcut on your desktop" -ForegroundColor Cyan
        Write-Host "2. Or run: $startScript" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Installation directory: $actualPath" -ForegroundColor Cyan
    }
} else {
    Write-Host "WARNING: Could not find start_windows.bat script" -ForegroundColor Yellow
    Write-Host "Installation directory: $actualPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can start NeXroll manually by running start_windows.bat from:" -ForegroundColor Cyan
    Write-Host "$actualPath" -ForegroundColor Cyan
}