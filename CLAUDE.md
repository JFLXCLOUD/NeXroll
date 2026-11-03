# NeXroll — Preroll Manager (Fork)

Forked preroll management system for Plex and Jellyfin. FastAPI backend + prebuilt React frontend, runs as a Docker container on Unraid.

## Stack

- **Backend:** FastAPI (Uvicorn), Python 3.12 — `NeXroll/backend/main.py`
- **Frontend:** Prebuilt React SPA — `NeXroll/frontend/build/`
- **Storage:** SQLite at `/data/nexroll.db`, prerolls at `/data/prerolls`
- **Image:** `ghcr.io/artic5693/nexroll:latest` (fork), `jbrns/nexroll:latest` (upstream)
- **Port:** 9393

## URLs

- Web UI: `http://192.168.1.219:9393`
- API docs: `http://192.168.1.219:9393/docs`
- Health: `http://192.168.1.219:9393/health`

## Deploy

```bash
# Build and push image (CI handles this via .github/workflows/)
docker build -t ghcr.io/artic5693/nexroll:latest .
docker push ghcr.io/artic5693/nexroll:latest

# On Unraid — pull and restart
ssh tower-root "docker pull ghcr.io/artic5693/nexroll:latest && docker restart nexroll"
```

### Local build deploy (patches/hotfixes)

When building directly on the server instead of via CI, always prune dangling images afterward
to prevent untagged layers from filling the docker.img vdisk:

```bash
ssh tower-root "cd /tmp/nexroll-build && docker build -t nexroll-patched:latest . && docker stop nexroll && docker rm nexroll && docker run <flags> nexroll-patched:latest && docker image prune -f"
```

The `docker image prune -f` at the end removes the previous untagged image. Without it, each
rebuild leaves a ~1.4GB dangling image that accumulates inside the fixed-size docker.img.

## Unraid Paths

| Container Path | Host Path | Purpose |
|---------------|-----------|---------|
| `/data` | `/mnt/user/appdata/nexroll` | DB, logs, secrets |
| `/data/prerolls` | `/mnt/user/data/media/movies/preroll` | Preroll video files |

## Environment Variables

- `NEXROLL_PORT` (9393), `NEXROLL_DB_DIR` (/data), `NEXROLL_PREROLL_PATH` (/data/prerolls)
- `PLEX_URL`, `PLEX_TOKEN` — Plex connection (or use Plex.tv auth in UI)
- `JELLYFIN_URL`, `JELLYFIN_API_KEY` — Jellyfin connection
- `RADARR_URL`, `RADARR_API_KEY`, `SONARR_URL`, `SONARR_API_KEY` — NeX-Up trailer downloads
- `PUID` (99), `PGID` (100), `TZ` (America/New_York)

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: Python 3.12-slim + FFmpeg + Deno |
| `entrypoint.sh` | PUID/PGID user setup, drops privileges via gosu |
| `docker-compose.yml` | Reference compose for standalone deploy |
| `nexroll-unraid-template.xml` | Unraid CA template (points to fork's GHCR image) |
| `NeXroll/backend/main.py` | FastAPI app — all API routes |
| `Plugins/` | Plugin system for extensibility |

## NeX-Up Trailer Sources

Trailers are downloaded in priority order (highest quality first):

| Priority | Source | Quality | Notes |
|----------|--------|---------|-------|
| -2 | **The Digital Theater** | 4K HEVC + DTS-HD MA 5.1 | Scraped from thedigitaltheater.com, downloaded via WeTransfer API |
| -1 | Radarr YouTube URL | Up to 4K (YouTube) | From Radarr's `youTubeTrailerId` field |
| 0 | Apple Trailers | 1080p | Site is dead (redirects to tv.apple.com) |
| 1 | Vimeo (via TMDB) | Varies | Rare for mainstream content |
| 2 | YouTube (via TMDB) | Up to 4K | Requires `remote_components: ejs:github` for JS challenge solving |

**Digital Theater flow**: Master list scrape → fuzzy title match → movie page scrape → score variants (resolution, codec, audio) → resolve WeTransfer short link → direct CDN download. Index cached 6 hours. Toggle: `nexup_digital_theater_enabled` setting.

**YouTube requirements**: `youtube_cookies.txt` in storage path (copied from Pinchflat) + Deno runtime for JS challenges.

## Fork Changes

This fork (`artic5693/NeXroll`) adds, on top of a rewritten upstream base
(reconciled to v2.1.0-beta.2 — the dashboard redesign, global session auth
gate, and bgutil PO-token YouTube fix are all upstream's, not fork-original):
- PUID/PGID support via `entrypoint.sh` for Unraid permission handling —
  upstream runs as root with no entrypoint at all
- CORS restriction (anchored LAN/localhost regex, not upstream's wildcard)
  + a dedicated CSRF origin-check middleware upstream doesn't have
- Radarr/Sonarr/TMDB API keys migrated into `secure_store` (upstream's
  secure_store only covers Plex/Jellyfin/Emby)
- ZipSlip/SSRF/SQL-injection guards and Jellyfin/Emby plugin XSS fixes not
  present upstream (some overlapping fixes, e.g. ZipSlip, upstream already
  had independently — checked case by case rather than blindly reapplied)
- "Recently Added" NeX-Up list — mirrors Coming Soon List, generates a
  preroll video of recently-added library content (Radarr/Sonarr `dateAdded`/
  history), with its own exclude/include toggle and Generator tab
- The Digital Theater as highest-priority (-2) trailer source (4K lossless,
  above Radarr YouTube at -1) — complementary to upstream's PO-token fix,
  not a replacement for it
- Log directory falls back to `$NEXROLL_DB_DIR/logs` before the app's cwd —
  needed because the cwd (`/app/NeXroll`) is root-owned under PUID/PGID,
  upstream never hits this since they run as root
- GHCR CI workflow (push-to-main + workflow_dispatch) and Unraid template
  pointing at the fork's registry, kept independent of upstream's Docker
  Hub / release-triggered workflow
- yt-dlp JS challenge solver integration (`remote_components: ejs:github`)
- Format string fallback for unavailable resolutions (upstream independently
  carries an equivalent/newer H.264-preferring fix)
