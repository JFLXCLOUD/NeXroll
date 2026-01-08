# Docker

NeXroll can be run in Docker containers for easy deployment and management. Official images are available on Docker Hub with support for both AMD64 and ARM64 architectures.

## Official Images

```bash
# Latest version
docker pull jbrns/nexroll:latest

# Specific version
docker pull jbrns/nexroll:1.9.6
```

### Supported Architectures
- `linux/amd64` - Intel/AMD servers, most VPS
- `linux/arm64` - Raspberry Pi 4/5, Apple Silicon, ARM servers

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
| Time Zone | TZ | America/New_York |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXROLL_PORT` | Web UI port | 9393 |
| `NEXROLL_DB_DIR` | Database and config directory | /data |
| `NEXROLL_PREROLL_PATH` | Preroll storage directory | /data/prerolls |
| `NEXROLL_SECRETS_DIR` | Secrets storage directory | /data |
| `TZ` | Timezone (important for scheduling!) | UTC |
| `PUID` | User ID for file permissions | 99 |
| `PGID` | Group ID for file permissions | 100 |

## Path Mappings (Critical for Plex/Jellyfin)

For Plex/Jellyfin to find your preroll files, you must configure path mappings in Settings → Path Mappings.

### Common Examples

| Scenario | NeXroll Path | Plex/Jellyfin Path |
|----------|--------------|-------------------|
| Docker → Windows Plex (drive) | /data/prerolls | Z:\Prerolls |
| Docker → Windows Plex (UNC) | /data/prerolls | \\\\NAS\Prerolls |
| Docker → Linux Plex | /data/prerolls | /media/prerolls |
| Unraid → Unraid Plex | /data/prerolls | /mnt/user/media/prerolls |

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

## Connecting to Plex/Jellyfin

### Plex Connection

In the web UI Connect page:

- **Method 1**: Direct URL + Token (e.g., `http://192.168.1.100:32400`)
- **Method 2**: Plex.tv Authentication (Recommended - auto-discovers servers)

For Docker environments, Plex is typically at:
- `http://host.docker.internal:32400` (Docker Desktop)
- `http://172.17.0.1:32400` (Linux bridge network)
- Use your Plex server's LAN IP for host networking

### Jellyfin Connection

1. Enter your Jellyfin server URL: `http://192.168.1.100:8096`
2. Create an API Key in Jellyfin: Dashboard → Advanced → API Keys
3. Enter the API Key in NeXroll

**Note**: Jellyfin requires the "Local Intros" plugin for preroll support.

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

## Troubleshooting

### Cannot Connect to Plex
- Use host networking when possible
- Try `http://host.docker.internal:32400` (Docker Desktop)
- Check Docker network settings
- Verify Plex allows connections from Docker's IP range

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
- NeXroll supports ARM64 as of v1.9.6
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

### Backup

```bash
# Stop container
docker stop nexroll

# Backup data
tar -czvf nexroll-backup.tar.gz ./nexroll-data

# Restart
docker start nexroll
```

## Full Stack Example with Plex

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
