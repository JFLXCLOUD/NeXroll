# NeXroll - Unraid Installation Guide

## Quick Start (Community Applications)

### Method 1: Via Community Applications (Recommended)

1. **Open Unraid Web Interface**
2. **Go to Apps tab**
3. **Search for "NeXroll"**
4. **Click "Install"**
5. **Configure paths and settings** (see Configuration Guide below)
6. **Click "Apply"**
7. **Access at:** `http://[YOUR-UNRAID-IP]:9393`

---

### Method 2: Manual Template Installation (If Not Yet in CA)

1. **Go to Docker tab** in Unraid
2. **Click "Add Container"**
3. **Toggle "Advanced View"** at top right
4. **Click "Template repositories"**
5. **Add this URL:**
   ```
   https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
   ```
6. **Save and refresh**
7. **Select "NeXroll" from template dropdown**
8. **Configure and Apply**

---

## Configuration Guide

### Required Settings

#### **Port Mapping**
- **Port:** `9393` (or your preferred port)
- **Description:** Web interface access
- **Example:** `http://192.168.1.100:9393`

#### **Application Data Path**
- **Container Path:** `/data`
- **Host Path:** `/mnt/user/appdata/nexroll`
- **Description:** Database, logs, thumbnails
- **Permissions:** Will be created automatically

#### **Preroll Storage Path**
- **Container Path:** `/data/prerolls`
- **Host Path:** `/mnt/user/media/prerolls` (or your choice)
- **Description:** Where your preroll videos are stored
- **Important:** This path must be accessible by Plex/Jellyfin!

### Optional Settings

#### **Time Zone**
- **Variable:** `TZ`
- **Default:** `America/New_York`
- **Examples:** 
  - `America/Los_Angeles`
  - `Europe/London`
  - `Asia/Tokyo`
- **Purpose:** Accurate schedule timing

#### **User/Group IDs (Advanced)**
- **PUID:** `99` (default Unraid nobody user)
- **PGID:** `100` (default Unraid users group)
- **When to change:** If you have custom permission requirements

---

## Plex Integration on Unraid

### Connecting NeXroll to Plex

1. **Access NeXroll:** `http://[UNRAID-IP]:9393`
2. **Go to Plex tab**
3. **Choose connection method:**

#### **Option A: Plex.tv Authentication (Recommended)**
- Click "Method 3: Plex.tv Authentication"
- Follow login prompts
- NeXroll will auto-discover your Plex server

#### **Option B: Manual Connection**
- **Plex Server URL:** `http://[UNRAID-IP]:32400`
- **Plex Token:** Get from: `https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/`

### Setting Up Prerolls in Plex

1. **Upload videos to:** `/mnt/user/media/prerolls/` (or your configured path)
2. **In NeXroll:** Create categories and add prerolls
3. **In NeXroll:** Create a schedule and apply it
4. **In Plex Settings:**
   - Go to: Settings → Extras → Cinema Trailers
   - Enable "Cinema Trailers"
   - The preroll path is automatically updated by NeXroll

---

## Jellyfin Integration on Unraid

### Connecting NeXroll to Jellyfin

1. **Access NeXroll:** `http://[UNRAID-IP]:9393`
2. **Go to Jellyfin tab**
3. **Enter connection details:**
   - **URL:** `http://[UNRAID-IP]:8096`
   - **API Key:** Get from Jellyfin Dashboard → Advanced → API Keys

### Setting Up Prerolls in Jellyfin

1. **Upload videos to:** `/mnt/user/media/prerolls/`
2. **In NeXroll:** Create categories and apply schedule
3. **Paths are automatically managed**

---

## Path Mapping Examples

### Example 1: Standard Setup
```
Container → Host
/data → /mnt/user/appdata/nexroll
/data/prerolls → /mnt/user/media/prerolls
```

### Example 2: Shared with Plex Container
If your Plex container has `/mnt/user/media` mapped to `/media`:
```
NeXroll: /mnt/user/media/prerolls
Plex can access: /media/prerolls
```

### Example 3: Custom Drive
```
Container → Host
/data → /mnt/user/appdata/nexroll
/data/prerolls → /mnt/disk2/prerolls
```

---

## Accessing the Web Interface

### Default Access
```
http://[UNRAID-IP]:9393
```

### Common Unraid IPs
- Check your router or Unraid dashboard
- Example: `http://192.168.1.100:9393`
- Or use hostname: `http://tower:9393` (if configured)

---

## Features Overview

### Core Features
- **Web Interface:** Clean, modern UI accessible from any device
- **Automatic Thumbnails:** FFmpeg generates thumbnails from videos
- **Scheduling:** Date ranges, time ranges, recurrence patterns
- **Categories:** Organize by theme (Christmas, Halloween, Action, etc.)
- **Holiday Presets:** 32 pre-configured holidays with date ranges
- **Fallback Categories:** Automatic fallback when no schedule active

### Advanced Features
- **Visual Sequence Builder:** Create complex preroll sequences
- **Block-Based Design:** Mix single videos, random selections, categories
- **Pattern Export/Import:** Share sequences between systems
- **Community Prerolls:** Browse 1,300+ prerolls from community
- **Backup & Restore:** Full database and file backups
- **Tag System:** Organize with custom tags

### Media Server Support
- **Plex:** Full integration with stable token support
- **Jellyfin:** Complete API integration
- **Status Monitoring:** Real-time server connection status
- **Quick Actions:** Apply categories directly from dashboard

---

## Troubleshooting

### Container Won't Start
1. **Check logs:** Docker tab → NeXroll → Logs
2. **Verify paths exist:** `/mnt/user/appdata/nexroll`
3. **Check port conflicts:** Port 9393 not used by another container

### Can't Access Web Interface
1. **Verify container is running:** Green play icon
2. **Check firewall:** Unraid allows port 9393
3. **Try IP instead of hostname:** `http://192.168.1.100:9393`

### Plex Can't Find Prerolls
1. **Path must be accessible to both containers**
2. **Check Plex container paths:** Match your NeXroll preroll path
3. **Verify permissions:** Files should be readable
4. **Example fix:**
   ```
   NeXroll: /mnt/user/media/prerolls → /data/prerolls
   Plex: /mnt/user/media → /media
   Result: Plex sees files at /media/prerolls
   ```

### Thumbnails Not Generating
1. **FFmpeg is included in the Docker image** (automatic)
2. **Check video formats:** MP4, MKV, AVI supported
3. **Wait a moment:** Generation happens in background
4. **Check logs:** Look for FFmpeg errors

---

## Updating NeXroll

### Via Community Applications
1. **Apps tab → Check for Updates**
2. **Click "Update" on NeXroll**
3. **Wait for pull and restart**
4. **Data is preserved** (in `/mnt/user/appdata/nexroll`)

### Manual Update
1. **Docker tab → NeXroll → Force Update**
2. **Or:** Delete and reinstall (data persists)

---

## Backup Your Data

### What to Backup
```
/mnt/user/appdata/nexroll/
  ├── nexroll.db           ← SQLite database
  ├── nexroll.db-wal       ← Database write-ahead log
  ├── nexroll.db-shm       ← Database shared memory
  ├── logs/                ← Application logs
  └── secrets.json         ← Encrypted tokens
```

### Backup Methods
1. **Unraid CA Backup plugin** (recommended)
2. **Manual copy** to another location
3. **NeXroll built-in backup:**
   - Settings → Backup & Restore
   - Database Backup (creates ZIP)
   - Files Backup (backs up videos)

---

## Uninstalling

1. **Docker tab → NeXroll → Remove**
2. **Optional:** Delete data folder
   ```
   /mnt/user/appdata/nexroll
   ```
3. **Preroll videos are NOT deleted** (stored separately)

---

## Support & Resources

- **GitHub Issues:** https://github.com/JFLXCLOUD/NeXroll/issues
- **Documentation:** https://github.com/JFLXCLOUD/NeXroll
- **Docker Hub:** https://hub.docker.com/r/jbrns/nexroll
- **Version:** Check in NeXroll UI (bottom right)

---

## Version Information

- **Current Version:** 1.11.0
- **Docker Image:** `jbrns/nexroll:latest`
- **Platform:** linux/amd64, linux/arm64
- **Base:** Python 3.12 + prebuilt frontend

---

**Enjoy managing your prerolls with NeXroll on Unraid!**
