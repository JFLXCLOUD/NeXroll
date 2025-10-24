# NeXroll v1.5.12 Docker Quick Start

Your Docker setup is already configured correctly. Just follow these steps to get v1.5.12 running.

## Prerequisites

- Docker 20.10+ and Docker Compose v2
- Host directory for persistent data (`./nexroll-data`)
- Network access to your Plex or Jellyfin server

## Updated for v1.5.12

The `docker-compose.yml` has been updated to build with version 1.5.12:

```yaml
services:
  nexroll:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        APP_VERSION: "1.5.12"
```

## Quick Start

### 1. Create data directory
```bash
mkdir -p ./nexroll-data
```

### 2. Build and run the container

**Linux (recommended - uses host networking):**
```bash
docker compose up -d
```

**Windows/macOS (Docker Desktop - uses port mapping):**
```bash
docker compose up -d
```

The compose file automatically selects the right mode based on your OS.

### 3. Access NeXroll

Open your browser to: **http://localhost:9393**

You should see the NeXroll dashboard with the new features:
- Dashboard customization (drag-and-drop card reordering)
- Timezone selector in Settings
- Improved UI with fixed dropdown arrows and consistent card spacing
- Working preroll deletion

## What's New in v1.5.12

- Dashboard card rearrangement with drag-and-drop
- Timezone configuration for accurate scheduling
- Improved button placement and UI consistency
- Fixed dropdown arrow styling
- Fixed preroll deletion (no more 500 errors)

## Environment Variables (Optional)

You can override these in your `.env` file or directly in `docker-compose.yml`:

```bash
# Media server connections (leave empty initially, set in UI)
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your-token-here
JELLYFIN_URL=http://your-jellyfin-server:8096
JELLYFIN_API_KEY=your-key-here

# Application settings
NEXROLL_PORT=9393
TZ=UTC  # Set to your timezone
```

## Volumes

- `/data` - Persistent storage for database, prerolls, and configuration
  - Maps to `./nexroll-data` on your host

## Health Check

The container includes a health check that runs every 30 seconds:
```bash
curl -fsS http://localhost:9393/health
```

## First-Time Setup

1. Open http://localhost:9393
2. Go to **Plex** or **Jellyfin** tab
3. Connect to your media server using one of these methods:
   - **Plex.tv Authentication** (recommended) - most reliable
   - **URL + Token** - direct connection
   - **Stable Token** - persistent authentication

4. Create categories and upload prerolls
5. Configure schedules
6. Apply to your media server

## Stopping the Container

```bash
docker compose down
```

## Updating to a New Version

1. Edit `docker-compose.yml` and update `APP_VERSION`
2. Run `docker compose up -d --build`
3. Your data persists in `./nexroll-data`

## Troubleshooting

**Container won't start:**
- Check logs: `docker compose logs -f nexroll`
- Ensure port 9393 is not in use: `netstat -an | grep 9393` (Windows) or `lsof -i :9393` (Linux)

**Can't connect to Plex/Jellyfin:**
- Verify network connectivity from container to media server
- Use internal LAN IP (e.g., 192.168.x.x) not localhost
- Check firewall rules on media server

**Prerolls not showing:**
- Ensure preroll directory is mounted: check `/data/prerolls` inside container
- Use container paths in UI (e.g., `/data/prerolls` not host paths)

**Thumbnails not generating:**
- FFmpeg is included in the image
- Re-upload prerolls to generate thumbnails

## API Documentation

Interactive API docs available at: **http://localhost:9393/docs**

## File Locations (Inside Container)

- Database: `/data/nexroll.db`
- Prerolls: `/data/prerolls`
- Logs: `/data/logs` (if enabled)
- Config: `/data` (contains secure token store)

---

**Version**: 1.5.12 | **Status**: Ready to deploy
