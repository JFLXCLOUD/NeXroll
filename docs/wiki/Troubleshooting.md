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

2. **Docker users — Check network:**
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
   - Dashboard → API Keys
   - Create a new key specifically for NeXroll

3. **Install NeXroll Intros plugin:**
   - The NeXroll Intros plugin is required for preroll playback
   - See [Jellyfin Setup](Jellyfin) for installation
   - NeXroll can auto-detect and configure the plugin from the Connect tab

### Cannot Connect to Emby

**Solutions:**

1. **Check URL format:**
   - Correct: `http://192.168.1.100:8096` (include port)
   
2. **Verify API Key:**
   - Settings → API Keys → New API Key

3. **Install NeXroll Intros plugin:**
   - Copy `NeXroll.Emby.dll` directly to Emby's `plugins/` folder (not a subfolder)
   - See [Emby Setup](Emby) for installation

4. **Enable Cinema Mode:**
   - Settings → Cinema Mode → Enable
   - Check "Include trailers from my movies in my library"
   - See [Emby Setup](Emby#step-4-enable-cinema-mode) for details

## Authentication Issues

### Can't Log In

1. **Check credentials** — Verify username and password
2. **Account locked** — After 5 failed attempts, wait 15 minutes
3. **Session expired** — Try logging in again
4. **Browser cookies** — Clear cookies and try again

### Locked Out of NeXroll

If you can't access the web interface due to authentication:

1. **Wait for lockout to expire** — 15-minute lockout after failed attempts
2. **Use another admin account** — If available, use a different admin to reset
3. **Check Settings → Logs** — Look for auth-related error messages

### API Key Not Working

1. **Check key format** — Keys start with `nx_`
2. **Check permissions** — Read-only keys can't make changes
3. **Check expiration** — Keys may have expired
4. **Use correct header** — `Authorization: Bearer nx_your_key`

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
5. **Check priority/conflicts**: Higher-priority exclusive schedules may override

### Prerolls Not Updating

1. **Check scheduler status** on Dashboard
2. **Verify path mappings** are correct
3. **Plex**: Manually test with "Apply to Plex" button
4. **Jellyfin/Emby**: Verify the NeXroll Intros plugin is configured with the correct NeXroll URL
5. **Emby**: Run "Refresh Custom Intros" from Scheduled Tasks after adding new prerolls
6. **Check media server connection** is still valid
7. **Check Settings → Logs** for scheduler activity

## NeX-Up Issues

### Trailers Not Downloading

1. **Upload YouTube cookies** — Export from an incognito browser session using the cookies.txt extension
2. **Check VPN** — Try a different server/IP if YouTube is blocking
3. **Rate limiting** — Wait between downloads, don't bulk-download too many
4. **Region-locked content** — Some trailers are region-restricted
5. **Check logs** — Settings → Logs for detailed error messages

### No Upcoming Content Found

1. **Verify Radarr/Sonarr connection** — Re-enter URL and API key
2. **Increase "Days Ahead"** — You may need to look further into the future
3. **Check "Include Unmonitored"** — Enable if your content is unmonitored in Radarr/Sonarr
4. **Verify upcoming content exists** — Check Radarr/Sonarr directly

### Coming Soon List Won't Generate

1. **Verify FFmpeg** — Run `ffmpeg -version` to confirm it's installed
2. **Sync first** — The generator needs upcoming content from Radarr/Sonarr
3. **Check disk space** — Video generation needs temporary space
4. **Poster download failures** — Grid mode falls back to list mode if posters can't be downloaded
5. **Check logs** — Settings → Logs for generation errors

### Dynamic Preroll Generation Fails

1. **FFmpeg required** — Must be installed and in PATH
2. **Docker**: FFmpeg is included in the container
3. **Windows**: Install via `winget install ffmpeg` or download from ffmpeg.org
4. **Check disk space** — Generation needs temporary space

## Docker Issues

### "No matching manifest for linux/arm64"

**Cause:** Using an old image that doesn't support ARM64

**Solution:** Update to the latest image:
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
2. **Verify your media server can access** the translated path
3. **Check permissions**: Can the media server read the files?
4. **NeX-Up trailers**: Don't forget to add mappings for trailer storage paths too
5. **Jellyfin/Emby**: Also check plugin-level path mapping in the NeXroll Intros plugin settings

### UNC Paths Not Working

Windows services may not access network shares.

**Solutions:**
- Use mapped drive letters (Z:\) instead of UNC (\\\\NAS\)
- Run Plex service as a user with network access
- Use local paths

## Upload Issues

### Upload Fails

1. **Check file size**: Maximum upload size is 500MB
2. **Check file extension**: Must be a supported video format (MP4, MKV, AVI, MOV, etc.)
3. **Check disk space**: Ensure adequate storage
4. **Check permissions**: NeXroll needs write access to preroll folder

### Thumbnails Not Generating

**Cause:** FFmpeg issue

**Solutions:**
- **Docker**: FFmpeg is included, check container logs
- **Windows**: Install FFmpeg and ensure it's in PATH
- **Manual**: Run `ffmpeg -version` to verify installation

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
3. **Check logs**: Settings → Logs for write errors

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

### Check the Logs

The built-in log viewer (**Settings → Logs**) shows detailed error messages, API request timings, and scheduler activity. This is the best first step for any troubleshooting.

**Docker logs:**
```bash
docker logs nexroll > nexroll-logs.txt 2>&1
```

**Windows logs:**
Logs are in: `%ProgramData%\NeXroll\logs`

### Report Issues

1. Check [existing issues](https://github.com/JFLXCLOUD/NeXroll/issues)
2. Include:
   - NeXroll version
   - Deployment type (Docker/Windows)
   - Relevant logs (from Settings → Logs or container logs)
   - Steps to reproduce

### Community Support

- [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues)
- [GitHub Discussions](https://github.com/JFLXCLOUD/NeXroll/discussions)
- [Discord](https://discord.gg/nexroll)
