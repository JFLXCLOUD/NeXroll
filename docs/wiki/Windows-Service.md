# Windows Service

NeXroll can run as a Windows Service for background operation without user login.

## Overview

The Windows Service (`NeXrollService`) provides:

- Automatic startup on system boot
- Runs without user session
- Survives user logoff/login
- Managed by Windows Services console

## Installation

### During Initial Install

Select "Install as Windows Service" during NeXroll installation:

1. Run `NeXroll_Installer.exe` as administrator
2. Check "Install as Windows Service"
3. Complete installation

### Manual Installation

After installation, install the service manually:

```batch
cd "C:\Program Files\NeXroll"
NeXrollService.exe install
NeXrollService.exe start
```

## Service Management

### Windows Services Console

1. Press `Win + R`, type `services.msc`
2. Find "NeXroll Service"
3. Right-click for Start/Stop/Restart/Properties

### Command Line

```batch
# Install service
NeXrollService.exe install

# Start service
NeXrollService.exe start

# Stop service
NeXrollService.exe stop

# Restart service
NeXrollService.exe restart

# Remove service
NeXrollService.exe remove

# Check status
sc query NeXrollService
```

### System Tray Controls

If tray app is installed, use tray menu:
- Right-click tray icon
- Start Service / Stop Service / Restart Service

## Service Configuration

### Service Properties

- **Service Name**: NeXrollService
- **Display Name**: NeXroll Service
- **Description**: NeXroll background service
- **Startup Type**: Automatic (Delayed Start)
- **Log On**: Local System account

### Dependencies

The service depends on:
- Windows Event Log
- Network services (for Plex/Jellyfin access)

## Operation

### Startup Process

1. Windows starts service at boot
2. Service initializes NeXroll backend
3. Web UI becomes available on port 9393
4. Scheduler begins monitoring schedules

### Runtime Behavior

- Runs in background with no UI
- Monitors Plex/Jellyfin connections
- Executes scheduled preroll changes
- Handles API requests
- Logs to `%ProgramData%\NeXroll\logs\service.log`

### Shutdown

- Graceful shutdown on system shutdown
- Saves current state
- Stops scheduler cleanly

## Monitoring

### Service Status

Check service health:

```batch
sc queryex NeXrollService
```

### Logs

Service logs location:
```
%ProgramData%\NeXroll\logs\service.log
```

Monitor logs for:
- Startup messages
- Connection status
- Schedule execution
- Error conditions

### Performance

Monitor service resource usage:
- CPU: Should be <5% when idle
- Memory: ~100-200 MB typical
- Network: Minimal, mostly API calls

## Troubleshooting

### Service Won't Start

**Symptoms:** Service fails to start after boot/installation

**Solutions:**
1. Check service logs for errors
2. Verify port 9393 is not in use
3. Ensure proper permissions
4. Try starting manually: `NeXrollService.exe start`

**Common errors:**
- **Port conflict**: Another service using port 9393
- **Permission denied**: Run installer as administrator
- **Missing dependencies**: Reinstall NeXroll

### Service Crashes

**Symptoms:** Service stops unexpectedly

**Solutions:**
1. Check Windows Event Viewer → Windows Logs → System
2. Review service logs for stack traces
3. Verify database integrity
4. Check system resources (memory/disk)

### Web UI Not Accessible

**Symptoms:** http://localhost:9393 not responding

**Solutions:**
1. Verify service is running
2. Check firewall rules
3. Try restarting service
4. Check service logs

### High Resource Usage

**Symptoms:** Service using excessive CPU/memory

**Solutions:**
1. Check for runaway processes
2. Review recent schedule executions
3. Verify Plex/Jellyfin connectivity
4. Restart service

## Security

### Service Account

Runs as Local System account with:
- Full access to NeXroll installation directory
- Access to `%ProgramData%\NeXroll`
- Network access for Plex/Jellyfin
- No interactive login capability

### Permissions

Service requires:
- Read/write access to data directory
- Network access to media servers
- Windows service management rights

### Firewall

Service needs inbound rule for TCP port 9393 (created by installer).

## Backup and Recovery

### Service Configuration

Service settings are stored in Windows registry:
```
HKLM\SYSTEM\CurrentControlSet\Services\NeXrollService
```

### Data Backup

Service data includes:
- Database: `%ProgramData%\NeXroll\nexroll.db`
- Logs: `%ProgramData%\NeXroll\logs\`
- Configuration files

### Recovery

To recover from service failure:
1. Stop service
2. Backup data directory
3. Reinstall service
4. Restore data
5. Start service

## Advanced Configuration

### Service Parameters

Modify service parameters in registry or use command line:

```batch
# Set custom port
NeXrollService.exe --port 9394

# Debug mode
NeXrollService.exe --debug
```

### Environment Variables

Service inherits system environment variables. Custom variables:

```batch
set NEXROLL_PORT=9394
set NEXROLL_DEBUG=1
```

### Startup Dependencies

Configure service dependencies:

```batch
sc config NeXrollService depend= LanmanServer
```

## Integration

### With System Tray

- Tray app monitors service status
- Provides start/stop controls
- Shows service notifications

### With Task Scheduler

Can be combined with Windows Task Scheduler for additional automation.

### With Windows Event Log

Service logs important events to Windows Event Log:
- Application log
- Source: NeXrollService

## Uninstallation

### During NeXroll Uninstall

Uninstaller automatically:
- Stops service
- Removes service registration
- Cleans up registry entries

### Manual Removal

```batch
# Stop and remove service
NeXrollService.exe stop
NeXrollService.exe remove

# Clean registry (optional)
reg delete "HKLM\SYSTEM\CurrentControlSet\Services\NeXrollService" /f
```

## Development

### Service Wrapper

The service uses `pywin32` to wrap the NeXroll application:

```python
import win32serviceutil
import win32service
import win32event

class NeXrollService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NeXrollService"
    _svc_display_name_ = "NeXroll Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        # Start NeXroll application
        import subprocess
        self.process = subprocess.Popen(["NeXroll.exe", "--service"])
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
```

### Debugging Service

Debug service issues:

```batch
# Run service interactively
NeXrollService.exe debug

# Check service events
eventvwr.msc → Windows Logs → System
```

### Service Logs

Enable verbose logging:

```python
import logging
logging.basicConfig(
    filename=r'C:\ProgramData\NeXroll\logs\service.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## Performance Tuning

### Memory Management

- Service automatically manages memory
- Monitor for memory leaks
- Restart periodically if needed

### CPU Optimization

- Background processing for thumbnails
- Asynchronous API calls
- Efficient database queries

### Network Optimization

- Connection pooling for Plex/Jellyfin
- Timeout handling
- Retry logic for failed requests

## Best Practices

### Monitoring

- Regularly check service status
- Monitor log files
- Set up alerts for service failures

### Maintenance

- Keep NeXroll updated
- Regularly backup data
- Monitor disk space
- Clean old log files

### Security

- Keep Windows updated
- Use strong Plex/Jellyfin tokens
- Monitor service account permissions
- Regular security audits