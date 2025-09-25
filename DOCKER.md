# NeXroll – Docker Deployment

This document explains how to run NeXroll in a Docker container with persistent storage, FFmpeg support, and a Linux-friendly token store.

NeXroll inside the container:
- Backend: FastAPI (Uvicorn) from `nexroll_backend`
- Frontend: prebuilt assets served from `frontend/build`
- Storage: single bind-mounted volume at `/data` for DB, prerolls, thumbnails, and secrets
- FFmpeg: installed in the image for thumbnail generation

URLs:
- Web UI: http://localhost:9393
- API docs: http://localhost:9393/docs
- Health: http://localhost:9393/health


## Prerequisites

- Docker (20.10+ recommended)
- Docker Compose v2 (optional but recommended)
- Host directory for persistent data (e.g., `./nexroll-data`)


## Quick Start (docker compose)

From the repository root:

```bash
docker compose up -d --build
# then open http://localhost:9393
```

Default settings when using the provided `docker-compose.yml`:
- Port: 9393 (host) → 9393 (container)
- Volume: `./nexroll-data` → `/data`
- Env:
  - `NEXROLL_DB_DIR=/data`
  - `NEXROLL_PREROLL_PATH=/data/prerolls`
  - `NEXROLL_SECRETS_DIR=/data`
  - `PLEX_URL` (optional; blank by default, set via `.env` or environment)
  - `PLEX_TOKEN` (optional; blank by default, set via `.env` or environment)
  - `TZ=UTC` (override via environment or `.env`)

To stop:
```bash
docker compose down
```

To view logs:
```bash
docker compose logs -f
```


## Build and Run (docker CLI)

Build the image:
```bash
docker build -t nexroll:local .
```

Run with a persistent volume (Linux/macOS):
```bash
mkdir -p ./nexroll-data
docker run --name nexroll --rm -p 9393:9393 \
  -e NEXROLL_DB_DIR=/data \
  -e NEXROLL_PREROLL_PATH=/data/prerolls \
  -e NEXROLL_SECRETS_DIR=/data \
  -e TZ=UTC \
  # Optional Plex bootstrap envs (if used by your deployment flow):
  # -e PLEX_URL=http://your-plex-server:32400 \
  # -e PLEX_TOKEN=your-plex-token \
  -v "$(pwd)/nexroll-data:/data" \
  nexroll:local
```

Run with a persistent volume (Windows PowerShell):
```powershell
mkdir nexroll-data | Out-Null
docker run --name nexroll --rm -p 9393:9393 `
  -e NEXROLL_DB_DIR=/data `
  -e NEXROLL_PREROLL_PATH=/data/prerolls `
  -e NEXROLL_SECRETS_DIR=/data `
  -e TZ=UTC `
  # Optional Plex bootstrap envs (if used by your deployment flow):
  # -e PLEX_URL=http://your-plex-server:32400 `
  # -e PLEX_TOKEN=your-plex-token `
  -v "${PWD}\nexroll-data:/data" `
  nexroll:local
```


## Persistent Data Layout

Mounted volume: `/data`

Runtime structure:
```
/data
├── nexroll.db                # SQLite database
├── prerolls/                 # Uploaded preroll videos (by category)
│   └── thumbnails/           # Generated thumbnails
└── secrets.json              # Linux file-based secret store (see below)
```

To migrate existing prerolls and database from a prior setup, copy your content into the corresponding folders under your host `./nexroll-data` before starting the container.


## Environment Variables

- NEXROLL_PORT
  - Default: 9393
  - Container port the app listens on
- NEXROLL_DB_DIR
  - Default (compose): `/data`
  - Directory where `nexroll.db` will reside
- NEXROLL_PREROLL_PATH
  - Default (compose): `/data/prerolls`
  - Directory for prerolls and thumbnails
- NEXROLL_SECRETS_DIR (optional)
  - Default: `/data` (via compose) or falls back based on the logic below
  - Directory to store `secrets.json`
- PLEX_URL (optional)
  - Example: `http://your-plex-server:32400`
  - Exposed for deployments that bootstrap Plex configuration via environment variables
- PLEX_TOKEN (optional)
  - Plex auth token string (do not commit to VCS)
  - Exposed for deployments that bootstrap Plex configuration via environment variables
- TZ
  - Default: UTC
  - Container timezone, affects timestamps and scheduler logic

### Build arguments

- APP_VERSION
  - Injects a version label into the image metadata
  - docker build: `docker build --build-arg APP_VERSION=1.2.2 -t nexroll:1.2.2 .`
  - docker compose: already set to `1.2.2` in `build.args` for convenience


## Token Storage on Linux (Containers)

For Linux-based containers, NeXroll provides a plain file-based secure store fallback so persistent tokens work without Windows-specific providers:

- File: `/data/secrets.json`
- Format: JSON with base64-encoded values
- Scope: shared for the container and survives restarts (bound to the host volume)
- Note: this approach is not encrypted; protect the host path with proper file-system permissions

No extra configuration is required when using the provided `docker-compose.yml`. If you want to move the secret store elsewhere, set:
```
NEXROLL_SECRETS_DIR=/some/other/path
```

The app uses the following priority to choose where to place `secrets.json` (non-Windows):
1) `NEXROLL_SECRETS_DIR`
2) `NEXROLL_DB_DIR`
3) Parent directory of `NEXROLL_PREROLL_PATH` if it ends with `prerolls`
4) `./data` inside current working directory

Stable token workflow works via the UI and is persisted to this file store.


## FFmpeg

The container includes FFmpeg for thumbnail generation. You can verify FFmpeg presence and version from:
- API: `GET /system/ffmpeg-info`
- UI: Dashboard → “FFmpeg Info”


## Health Check

The image and compose file include a health check that polls:
```
GET http://localhost:9393/health
```

You can also watch logs during startup for resolved paths and directory info.


## Uploads, Thumbnails, and Categories

- Uploads go into `/data/prerolls/<Category>/...`
- Thumbnails are generated into `/data/prerolls/thumbnails/<Category>/...`
- The backend generates thumbnails using FFmpeg; placeholders are used if generation fails


## Troubleshooting

- Permissions / Ownership:
  - Ensure the host’s `./nexroll-data` is writable by Docker
  - On Linux, you may need to adjust ownership or run with a specific user. This image runs as root by default.
- Thumbnails not generating:
  - Check `/system/ffmpeg-info` and logs
  - Use `/thumbnails/rebuild?force=true` to regenerate
- Plex connection:
  - Use the Plex tab in the UI; tokens will persist in `/data/secrets.json` in containers
- Stale frontend files:
  - Browser cache may keep old assets; try hard refresh
  - The backend implements cache-busting headers for key endpoints


## Production Notes

- Reverse proxy (optional): Put Nginx/Traefik/Caddy in front and proxy to the container’s `9393`
- Backups:
  - Backup `/data/nexroll.db` and your `/data/prerolls` directory
  - Optionally backup `/data/secrets.json`
- Updates:
  - Pull/build latest, then `docker compose up -d --build` (your data persists in the bind mount)