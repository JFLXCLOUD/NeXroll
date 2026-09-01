# System Tray

NeXroll includes a lightweight system tray application for quick access and background operation.

## Overview

The system tray app (`NeXrollTray.exe`) provides:

- Quick access to the web UI
- Service management controls
- Update checking
- Status monitoring
- Minimal resource usage

## Installation

The tray app is installed automatically with NeXroll. During installation, you can choose:

- **Start with Windows**: Auto-launch tray app on login
- **Install as Windows Service**: Enable service management features

## Tray Icon

The tray icon appears in the Windows notification area (system tray). Right-click for menu options.

### Menu Options

- **Open**: Launches http://localhost:9393 in default browser
- **Start Service**: Starts the NeXroll Windows Service (if installed)
- **Stop Service**: Stops the NeXroll Windows Service
- **Restart Service**: Restarts the NeXroll Windows Service
- **Start App (portable)**: Runs NeXroll directly (non-service mode)
- **Check for updates**: Checks GitHub for newer versions
- **About**: Shows version and system information
- **GitHub**: Opens NeXroll repository in browser
- **Exit**: Closes the tray application

## Auto-Start

When "Start with Windows" is selected during installation:

- Tray app launches automatically on user login
- Runs in background with minimal resource usage
- Survives system restarts

## Service Management

If Windows Service is installed, the tray provides service controls:

### Starting the Service

```batch
# Via tray menu
Right-click tray icon → Start Service

# Via command line
NeXrollService.exe start
```

### Stopping the Service

```batch
# Via tray menu
Right-click tray icon → Stop Service

# Via command line
NeXrollService.exe stop
```

### Service Status

The tray icon changes to indicate service status:
- **Green**: Service running
- **Red**: Service stopped
- **Yellow**: Service starting/stopping

## Update Checking

The "Check for updates" feature:

- Queries GitHub Releases API
- Compares current version with latest release
- Shows dialog with update information
- Provides direct download link

## Portable Mode

"Start App (portable)" runs NeXroll without the Windows Service:

- Useful for testing or when service isn't needed
- Runs in user context
- Can be used alongside or instead of service

## Configuration

The tray app uses minimal configuration:

- **Auto-start**: Controlled by installer option
- **Service integration**: Automatic detection
- **Update check interval**: Manual only (no background checking)

## Troubleshooting

### Tray Icon Not Visible

**Solutions:**
- Run "NeXroll Tray" from Start Menu
- Check Task Manager for running `NeXrollTray.exe`
- Restart the tray application
- Reinstall if corrupted

### Menu Not Responding

**Symptoms:** Right-click doesn't show menu

**Solutions:**
- Try left-click first
- Restart tray app
- Check for Windows theme issues
- Verify no other tray apps interfering

### Service Controls Disabled

**Symptoms:** Service menu options grayed out

**Solutions:**
- Verify Windows Service is installed
- Check service status in Services.msc
- Run installer repair
- Check user permissions

### High Resource Usage

**Symptoms:** Tray app using excessive CPU/memory

**Solutions:**
- Restart tray application
- Check for conflicts with other tray apps
- Disable Windows visual effects
- Update to latest version

## Logs

Tray app logs are written to:
```
%ProgramData%\NeXroll\logs\tray.log
```

## Advanced Usage

### Command Line Options

```batch
NeXrollTray.exe /silent    # No startup notifications
NeXrollTray.exe /debug     # Verbose logging
```

### Registry Settings

Tray settings are stored in:
```
HKCU\Software\NeXroll\Tray
```

### Custom Icons

The tray icon can be customized by replacing:
```
C:\Program Files\NeXroll\icons\tray.ico
```

## Integration

### With Windows Service

- Tray monitors service status
- Provides start/stop controls
- Shows service health

### With Web UI

- Quick launch access
- Status synchronization
- Update notifications

### With Windows

- Follows system theme
- Integrates with notification area
- Respects power management

## Security Considerations

- Runs with user privileges
- No elevated permissions required
- Secure token handling
- No network access (except for updates)

## Performance

- **Memory usage**: ~10-20 MB
- **CPU usage**: <1% when idle
- **Startup time**: <2 seconds
- **Background operation**: Minimal impact

## Uninstallation

The tray app is removed during NeXroll uninstallation:

- Removes auto-start entries
- Cleans registry settings
- Removes shortcuts

## Development

For developers working on the tray app:

```python
# Main entry point
if __name__ == "__main__":
    from NeXroll.tray_app import main
    main()
```

The tray app uses:
- `pystray` for system tray functionality
- `PIL` for icon handling
- Windows API for service management