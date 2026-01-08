# Troubleshooting

Common issues and solutions for NeXroll.

## Connection Issues

### Cannot Connect to Plex

**Symptoms:**
- "Connection failed" error
- Timeout when trying to connect

**Solutions:**

1. **Check Plex URL format:**
   - Correct: `http://192.168.1.100:32400`
   - Wrong: `http://192.168.1.100:32400/` (trailing slash)
   - Wrong: `192.168.1.100:32400` (missing http://)

2. **Docker users - Check network:**
   - Try `http://host.docker.internal:32400` (Docker Desktop)
   - Try `http://172.17.0.1:32400` (Linux bridge)
   - Use host's LAN IP: `http://192.168.1.X:32400`

3. **Verify Plex is running:**
   ```bash
   curl http://YOUR_PLEX_IP:32400/identity
   ```

4. **Check firewall:**
   - Ensure port 32400 is accessible
   - Windows Firewall may block connections

5. **Token issues:**
   - Re-authenticate via Plex.tv method
   - Generate a new token from Plex settings

### Cannot Connect to Jellyfin

**Solutions:**

1. **Check URL format:**
   - Correct: `http://192.168.1.100:8096`
   
2. **Verify API Key:**
   - Dashboard → Advanced → API Keys
   - Create a new key specifically for NeXroll

3. **Install Local Intros plugin:**
   - Jellyfin requires this plugin for preroll support
   - Dashboard → Plugins → Catalog → Local Intros

## Scheduling Issues

### Schedules Running at Wrong Time

**Cause:** Timezone mismatch (especially in Docker)

**Solution:**

Set the `TZ` environment variable:

```yaml
environment:
  - TZ=America/New_York
```

Common timezone values:
- `America/New_York`
- `America/Los_Angeles`
- `America/Chicago`
- `Europe/London`
- `Europe/Paris`
- `Asia/Tokyo`
- `Australia/Sydney`

Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### Schedule Not Activating

1. **Check Enabled toggle**: Must be ON
2. **Verify date range**: Current date must be within range
3. **Check time range**: If set, current time must be within range
4. **Verify timezone**: See above

### Prerolls Not Updating in Plex

1. **Check scheduler status** on Dashboard
2. **Verify path mappings** are correct
3. **Manually test** with "Apply to Plex" button
4. **Check Plex connection** is still valid

## Docker Issues

### "No matching manifest for linux/arm64"

**Cause:** Using an old image that doesn't support ARM64

**Solution:** Update to v1.9.6 or later:
```bash
docker pull jbrns/nexroll:latest
```

### Permission Denied Errors

**Solution (Linux):**
```bash
sudo chown -R 1000:1000 ./nexroll-data
```

**Or run as current user:**
```bash
docker run --user $(id -u):$(id -g) ...
```

### Container Keeps Restarting

Check logs:
```bash
docker logs nexroll
```

Common causes:
- Port already in use
- Volume mount permissions
- Missing environment variables

### Old Version Still Running After Pull

Docker caches images locally. Force a fresh pull:

```bash
docker compose down
docker image rm jbrns/nexroll:latest
docker pull jbrns/nexroll:latest
docker compose up -d
```

## Path Mapping Issues

### Prerolls Not Playing

1. **Test translation**: Settings → Test Translation
2. **Verify Plex can access** the translated path
3. **Check permissions**: Can Plex read the files?

### UNC Paths Not Working

Windows services may not access network shares.

**Solutions:**
- Use mapped drive letters (Z:\) instead of UNC (\\\\NAS\)
- Run Plex service as a user with network access
- Use local paths

## Upload Issues

### Upload Fails

1. **Check file size**: Very large files may timeout
2. **Check disk space**: Ensure adequate storage
3. **Check permissions**: NeXroll needs write access to preroll folder

### Thumbnails Not Generating

**Cause:** FFmpeg issue

**Solutions:**
- **Docker**: FFmpeg is included, check container logs
- **Windows**: Installer should install FFmpeg via winget
- **Manual**: Install FFmpeg and ensure it's in PATH

## UI Issues

### Page Not Loading

1. **Check NeXroll is running**: 
   - Docker: `docker ps`
   - Windows: Check Services or System Tray

2. **Check port**: Default is 9393
   - Try http://localhost:9393
   - Try http://YOUR_IP:9393

3. **Clear browser cache**: Hard refresh (Ctrl+Shift+R)

### Settings Not Saving

1. **Check permissions**: Can NeXroll write to data directory?
2. **Check disk space**: Database needs room to grow
3. **Check logs**: Look for write errors

## Windows-Specific Issues

### Service Won't Start

1. **Check Event Viewer**: Windows Logs → Application
2. **Run as Administrator**: Installer requires admin rights
3. **Check port availability**: `netstat -an | findstr 9393`

### Firewall Blocking Access

The installer creates a firewall rule, but if missing:

```powershell
New-NetFirewallRule -DisplayName "NeXroll" -Direction Inbound -Port 9393 -Protocol TCP -Action Allow
```

### System Tray Not Appearing

1. **Check hidden icons**: Click the arrow in system tray
2. **Verify tray app is running**: Check Task Manager
3. **Restart tray app**: From Start Menu or reinstall

## Getting Help

### Collect Logs

**Docker:**
```bash
docker logs nexroll > nexroll-logs.txt 2>&1
```

**Windows:**
Logs are in: `%ProgramData%\NeXroll\logs`

### Report Issues

1. Check [existing issues](https://github.com/JFLXCLOUD/NeXroll/issues)
2. Include:
   - NeXroll version
   - Deployment type (Docker/Windows)
   - Relevant logs
   - Steps to reproduce

### Community Support

- [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues)
- [GitHub Discussions](https://github.com/JFLXCLOUD/NeXroll/discussions)
