# Docker

NeXroll can be run in Docker containers for easy deployment and management. Official images are available on Docker Hub with support for both AMD64 and ARM64 architectures.

## Official Images

```bash
# Latest stable version
docker pull jbrns/nexroll:latest

# Specific version
docker pull jbrns/nexroll:1.11.0

# Beta channel (pre-release features)
docker pull jbrns/nexroll:beta
```

### Supported Architectures
- `linux/amd64` — Intel/AMD servers, most VPS
- `linux/arm64` — Raspberry Pi 4/5, Apple Silicon, ARM servers

## Quick Start

### docker-compose.yml (Recommended)

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:latest
    container_name: nexroll
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - NEXROLL_SECRETS_DIR=/data
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
      - /path/to/your/prerolls:/data/prerolls
    restart: unless-stopped
```

### With NeX-Up Trailer Storage

If using NeX-Up trailers, you may want a separate volume for trailer storage so Plex can access them:

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:latest
    container_name: nexroll
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - NEXROLL_SECRETS_DIR=/data
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
      - /path/to/your/prerolls:/data/prerolls
      - /path/to/trailers:/data/nexup_trailers    # NeX-Up trailer storage
    restart: unless-stopped
```

Then configure the **Trailer Storage Path** in NeX-Up Settings to `/data/nexup_trailers`.

### Setup

```bash
mkdir -p ./nexroll-data
docker compose up -d
# Access at http://YOUR_HOST:9393
```

## Unraid Installation

NeXroll is available in Unraid Community Applications.

1. Go to **Apps** in Unraid
2. Search for **NeXroll**
3. Click **Install**
4. Configure paths:
   - **Application Data**: `/mnt/user/appdata/nexroll`
   - **Preroll Storage**: `/mnt/user/media/prerolls` (must be accessible by Plex/Jellyfin)
5. Click **Apply**

### Unraid Template Settings

| Setting | Container Path | Host Path Example |
|---------|---------------|-------------------|
| WebUI Port | 9393 | 9393 |
| Application Data | /data | /mnt/user/appdata/nexroll |
| Preroll Storage | /data/prerolls | /mnt/user/media/prerolls |
| Trailer Storage | /data/nexup_trailers | /mnt/user/media/trailers |
| Time Zone | TZ | America/New_York |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXROLL_PORT` | Web UI port | 9393 |
| `NEXROLL_DB_DIR` | Database and config directory | /data |
| `NEXROLL_PREROLL_PATH` | Preroll storage directory | /data/prerolls |
| `NEXROLL_SECRETS_DIR` | Secrets storage directory | /data |
| `SCHEDULER_INTERVAL` | How often to check schedules (seconds) | 60 |
| `TZ` | Timezone (important for scheduling!) | UTC |
| `PUID` | User ID for file permissions | 99 |
| `PGID` | Group ID for file permissions | 100 |

## Path Mappings (Critical for Plex/Jellyfin/Emby)

For your media server to find preroll files, you must configure path mappings in Settings → Path Mappings.

For **Jellyfin and Emby**, path mappings can also be configured in the NeXroll Intros plugin settings (Path Prefix From/To), which is handled automatically when using NeXroll's **Configure Plugin** button.

### Common Examples

| Scenario | NeXroll Path | Media Server Path |
|----------|--------------|-------------------|
| Docker → Windows Plex (drive) | /data/prerolls | Z:\Prerolls |
| Docker → Windows Plex (UNC) | /data/prerolls | \\\\NAS\Prerolls |
| Docker → Linux Plex | /data/prerolls | /media/prerolls |
| Docker → Jellyfin (Docker) | /data/prerolls | /media/prerolls |
| Docker → Emby (Docker) | /data/prerolls | /media/prerolls |
| Unraid → Unraid Plex | /data/prerolls | /mnt/user/media/prerolls |

**Don't forget NeX-Up trailers!** If using a separate trailer volume, add a path mapping for that too.

### Testing Mappings

Use **Settings → Test Translation** to verify paths before applying categories to Plex.

## Linux Host Networking (Alternative)

For better LAN device discovery, use host networking (Linux only):

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:latest
    network_mode: "host"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - NEXROLL_SECRETS_DIR=/data
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
    restart: unless-stopped
```

## Docker Run Commands

### Linux/macOS

```bash
mkdir -p ./nexroll-data
docker run -d --name nexroll \
  -p 9393:9393 \
  -e NEXROLL_DB_DIR=/data \
  -e NEXROLL_PREROLL_PATH=/data/prerolls \
  -e NEXROLL_SECRETS_DIR=/data \
  -e TZ=America/New_York \
  -v "$(pwd)/nexroll-data:/data" \
  jbrns/nexroll:latest
```

### Windows PowerShell

```powershell
mkdir nexroll-data -Force
docker run -d --name nexroll `
  -p 9393:9393 `
  -e NEXROLL_DB_DIR=/data `
  -e NEXROLL_PREROLL_PATH=/data/prerolls `
  -e NEXROLL_SECRETS_DIR=/data `
  -e TZ=America/New_York `
  -v "${PWD}\nexroll-data:/data" `
  jbrns/nexroll:latest
```

## Connecting to Media Servers

### Plex Connection

In the web UI Connect page:

- **Method 1**: Direct URL + Token (e.g., `http://192.168.1.100:32400`)
- **Method 2**: Plex.tv Authentication (Recommended — auto-discovers servers)

For Docker environments, Plex is typically at:
- `http://host.docker.internal:32400` (Docker Desktop)
- `http://172.17.0.1:32400` (Linux bridge network)
- Use your Plex server's LAN IP for host networking

### Jellyfin Connection

Jellyfin uses a **server connection + plugin** approach for preroll injection.

1. In NeXroll, go to **Connect → Jellyfin**
2. Enter your Jellyfin server URL (e.g., `http://192.168.1.100:8096`)
3. Create an API Key in Jellyfin: **Dashboard → API Keys → Create** (the `+` button)
4. Enter the API Key in NeXroll and click **Connect**

**Plugin Setup**: Install the **NeXroll Intros** plugin in Jellyfin (see the [Jellyfin Setup](Jellyfin) wiki page for details). NeXroll can auto-detect and configure the plugin once connected:

1. In **Connect → Jellyfin**, click **Detect Plugin**
2. If detected, click **Configure Plugin** — NeXroll will automatically push the server URL, generate an API key, and set path mappings

The plugin uses Jellyfin's `IIntroProvider` interface to inject prerolls at playback time. It downloads preroll files to a local cache and registers them in Jellyfin's database.

For Docker, use the NeXroll container's service name or host IP as the URL:
- `http://nexroll:9393` (docker-compose service name)
- `http://host.docker.internal:9393` (Docker Desktop)
- `http://172.17.0.1:9393` (Linux bridge network)

### Emby Connection

Emby uses a **server connection + plugin + Cinema Mode** approach for preroll injection.

1. In NeXroll, go to **Connect → Emby**
2. Enter your Emby server URL (e.g., `http://192.168.1.100:8096`)
3. Create an API Key in Emby: **Settings → API Keys → New API Key**
4. Enter the API Key in NeXroll and click **Connect**

**Plugin Setup**: Install the **NeXroll Intros** plugin in Emby (see the [Emby Setup](Emby) wiki page for details). NeXroll can auto-detect and configure the plugin once connected:

1. In **Connect → Emby**, click **Detect Plugin**
2. If detected, click **Configure Plugin** — NeXroll will automatically push the server URL, generate an API key, and set path mappings

**Cinema Mode (Required)**: In Emby, go to **Settings → Cinema Mode** and ensure:
- Cinema Mode is **On**
- "Enable intros for Movies" and/or "Enable intros for Episodes" are checked
- **"Include trailers from my movies in my library"** is checked — without this, prerolls won't play

After initial setup, run **Scheduled Tasks → Refresh Custom Intros** in Emby to register the cached preroll files.

> **Note**: Emby Premiere is required for Cinema Mode functionality.

## Updating

```bash
# Pull latest image
docker pull jbrns/nexroll:latest

# Recreate container
docker compose up -d --force-recreate

# Or with docker run
docker stop nexroll
docker rm nexroll
# Run the docker run command again
```

Your data is preserved in the mounted volumes.

## Troubleshooting

### Cannot Connect to Plex
- Use host networking when possible
- Try `http://host.docker.internal:32400` (Docker Desktop)
- Check Docker network settings
- Verify Plex allows connections from Docker's IP range

### Cannot Connect to Jellyfin/Emby
- Try `http://host.docker.internal:8096` (Docker Desktop) or use the LAN IP
- If using docker-compose, use the service name (e.g., `http://jellyfin:8096`)
- Verify port 8096 (or your custom port) is accessible from NeXroll's container
- For plugin communication, ensure NeXroll's port 9393 is reachable from the media server container

### Jellyfin/Emby Plugin Not Working
- Verify the plugin is installed — check **Dashboard → Plugins** in your media server
- Test plugin connectivity: use **Detect Plugin** in NeXroll's Connect page
- For Emby: ensure Cinema Mode is enabled and "Include trailers from my movies in my library" is checked
- For Emby: run **Scheduled Tasks → Refresh Custom Intros** after initial setup
- Check that NeXroll is reachable from the media server at the configured URL

### Permission Errors
```bash
# Linux: Fix volume permissions
sudo chown -R 1000:1000 ./nexroll-data

# Or run as current user
docker run --user $(id -u):$(id -g) ...
```

### Schedules Running at Wrong Time
- **Set your timezone!** Use the `TZ` environment variable
- Example: `TZ=America/New_York`, `TZ=Europe/London`
- List of timezones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### ARM64 Issues
- NeXroll supports ARM64 natively
- If you see "no matching manifest for linux/arm64", update to the latest image

### Port Already in Use
- Change host port: `-p 9394:9393`
- Check for other services: `docker ps`

## Volume Management

### Persistent Data

The `/data` volume stores:
- SQLite database (`nexroll.db`)
- Preroll files (if using default path)
- Thumbnails
- Encrypted credentials
- NeX-Up trailers (if using default storage path)
- Log files

### Backup

```bash
# Stop container
docker stop nexroll

# Backup data
tar -czvf nexroll-backup.tar.gz ./nexroll-data

# Restart
docker start nexroll
```

Or use the built-in **System & Files Backup** feature in Settings.

## Full Stack Examples

### With Plex

```yaml
version: "3.8"
services:
  plex:
    image: linuxserver/plex:latest
    network_mode: "host"
    volumes:
      - ./plex-config:/config
      - ./media:/media
    environment:
      - PUID=1000
      - PGID=1000
    restart: unless-stopped

  nexroll:
    image: jbrns/nexroll:latest
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
      - ./media/prerolls:/data/prerolls
    depends_on:
      - plex
    restart: unless-stopped
```

### With Jellyfin

```yaml
version: "3.8"
services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    ports:
      - "8096:8096"
    volumes:
      - ./jellyfin-config:/config
      - ./media:/media
    environment:
      - TZ=America/New_York
    restart: unless-stopped

  nexroll:
    image: jbrns/nexroll:latest
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
      - ./media/prerolls:/data/prerolls
    depends_on:
      - jellyfin
    restart: unless-stopped
```

In the plugin config, set path mapping: **NeXroll Prefix** `/data/prerolls` → **Jellyfin Prefix** `/media/prerolls`

### With Emby

```yaml
version: "3.8"
services:
  emby:
    image: emby/embyserver:latest
    ports:
      - "8096:8096"
    volumes:
      - ./emby-config:/config
      - ./media:/media
    environment:
      - TZ=America/New_York
    restart: unless-stopped

  nexroll:
    image: jbrns/nexroll:latest
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - TZ=America/New_York
    volumes:
      - ./nexroll-data:/data
      - ./media/prerolls:/data/prerolls
    depends_on:
      - emby
    restart: unless-stopped
```

In the plugin config, set path mapping: **NeXroll Prefix** `/data/prerolls` → **Emby Prefix** `/media/prerolls`

Remember to enable **Cinema Mode** in Emby and run **Refresh Custom Intros** after setup.
