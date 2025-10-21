# NeXroll — Docker Repository Overview

## Summary
- Official image: jbrns/nexroll (use a pinned tag like jbrns/nexroll:1.4.4)
- Purpose: Single-container web UI + API to manage prerolls for Plex and Jellyfin
- Core: FastAPI backend [nexroll_backend.main()](NeXroll/nexroll_backend/main.py:713), prebuilt React frontend, FFmpeg included, health endpoint

## Key files
- Build recipe: [Dockerfile](Dockerfile:1)
- Local example stack: [docker-compose.yml](docker-compose.yml:1)
- Full guide and best practices: [DOCKER.md](NeXroll/DOCKER.md:1)

## Default endpoints
- Web UI: http://HOST:9393
- API docs: http://HOST:9393/docs
- Health: http://HOST:9393/health

## Persistent data
- Bind-mount a host folder to /data
- Contains SQLite DB, prerolls, thumbnails, and secure token store
- Example: -v ./nexroll-data:/data (in compose: volumes: - ./nexroll-data:/data)

## Environment variables
- NEXROLL_PORT (default 9393)
- NEXROLL_DB_DIR (default /data)
- NEXROLL_PREROLL_PATH (default /data/prerolls)
- NEXROLL_SECRETS_DIR (default /data)
- TZ (default UTC)
- Optional bootstrap: PLEX_URL, PLEX_TOKEN, JELLYFIN_URL, JELLYFIN_API_KEY

## Quick start (Linux — recommended: host networking)
Use host networking so the container can reach Plex at 192.168.x.x directly. See compose example below or [docker-compose.yml](docker-compose.yml:1).

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:1.4.4
    network_mode: "host"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - NEXROLL_SECRETS_DIR=/data
      - TZ=UTC
    volumes:
      - ./nexroll-data:/data
    restart: unless-stopped
```

Then:

```bash
mkdir -p ./nexroll-data
docker compose up -d
# open http://YOUR_HOST:9393
```

## Quick start (All platforms — port mapping)
Use when host networking is unavailable (e.g., Docker Desktop on Windows/macOS):

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:1.4.4
    ports:
      - "9393:9393"
    environment:
      - NEXROLL_PORT=9393
      - NEXROLL_DB_DIR=/data
      - NEXROLL_PREROLL_PATH=/data/prerolls
      - NEXROLL_SECRETS_DIR=/data
      - TZ=UTC
    volumes:
      - ./nexroll-data:/data
    restart: unless-stopped
```

On Docker Desktop, Plex on the host is typically reachable from the container at http://host.docker.internal:32400 (allow it in your firewall).

## Media Server connection and path mappings
- In the UI, connect to Plex or Jellyfin servers. For Plex, prefer Plex.tv Authentication for reliable discovery and credential storage.
- Diagnostics endpoint: GET /plex/probe?url=http://YOUR_PLEX:32400 at [app.get()](NeXroll/nexroll_backend/main.py:1742).
- Apply-to-Plex preflight and platform checks run in [app.post()](NeXroll/nexroll_backend/main.py:3186).
- Ensure the container paths (e.g., /data/prerolls) translate to paths Plex can see on its host using Settings → “UNC/Local → Plex Path Mappings” (longest-prefix wins).
  - Examples:
    - Docker NeXroll → Windows Plex (drive): /data/prerolls → Z:\Prerolls
    - Docker NeXroll → Windows Plex (UNC): /data/prerolls → \\NAS\Prerolls
    - Docker NeXroll → Docker Plex (Linux): /data/prerolls → /media/prerolls

## Upgrade
```bash
docker compose pull
docker compose up -d
```

## References
- Build file: [Dockerfile](Dockerfile:1)
- Compose example: [docker-compose.yml](docker-compose.yml:1)
- Full deployment guide: [DOCKER.md](NeXroll/DOCKER.md:1)