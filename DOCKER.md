# NeXroll – Docker Deployment

This guide explains how to deploy NeXroll with Docker on Linux, Windows, or macOS, connect it to Plex reliably, and ensure Plex can see your preroll paths regardless of where NeXroll runs.

Key components in the image:
- Backend: FastAPI (Uvicorn) package [nexroll_backend.main()](NeXroll/nexroll_backend/main.py:713)
- Frontend: prebuilt static assets served from /app/NeXroll/frontend/build
- Storage: a single bind-mounted volume at /data (DB, prerolls, thumbnails, secure token store)
- FFmpeg included for thumbnail generation

URLs (default):
- Web UI: http://HOST:9393
- API health: http://HOST:9393/health
- API docs: http://HOST:9393/docs


## 1) Prerequisites

- Docker 20.10+ and (optionally) Docker Compose v2
- A host directory for persistent data (for example ./nexroll-data)


## 2) Quick Start (Linux – Recommended: host networking)

Host networking avoids container-to-LAN routing issues and makes it easy for NeXroll to reach Plex at 192.168.x.x. On Linux only:

docker-compose.yml

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:1.2.3
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

Then run:

```bash
mkdir -p ./nexroll-data
docker compose up -d
# open http://YOUR_HOST:9393
```

Notes:
- Do not publish ports when using network_mode: host.
- The UI remains on port 9393 (NEXROLL_PORT).


## 3) Quick Start (All platforms – port mapping)

If you cannot use host networking (e.g., Docker Desktop on Windows/macOS), use normal port publishing:

```yaml
version: "3.8"
services:
  nexroll:
    image: jbrns/nexroll:1.2.3
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

On Docker Desktop, the container can usually reach the host at http://host.docker.internal. Ensure firewalls allow Plex port 32400 for the Docker/WSL networks.


## 4) Connect NeXroll to Plex (recommended: Plex.tv Authentication)

In the UI, go to the Plex tab and use “Method 3: Plex.tv Authentication.” NeXroll discovers a reachable server and saves credentials into the secure store:
- On Linux containers the secure store is a plain JSON file under /data/secrets.json
- On Windows packaged builds the token is stored in the Windows Credential Manager or DPAPI-backed file

You can also use a stable token or manual URL + token, but Plex.tv auth is the most reliable across Docker and mixed networks.


## 5) Map existing preroll folders (no move)

Settings → “Map Existing Preroll Folder (No Move)” indexes an existing folder (local or UNC/NAS mount) into NeXroll without copying or moving files:
- Supports recursive scanning, extension filters, tags, and optional thumbnail generation
- Files are added with managed=false so NeXroll never moves or deletes them on disk

For containers, ensure the folder is mounted into the container (e.g., /data/prerolls or /nas/prerolls) and use that container path as the Root path.


## 6) Make Plex paths work everywhere (UNC/Local → Plex Path Mappings)

When you apply a category to Plex, NeXroll translates local or container paths to the path Plex can see on its host using the mappings you define in Settings → “UNC/Local → Plex Path Mappings”. The longest source prefix wins; on Windows, source matching is case-insensitive, and the output separator is inferred from the destination.

Common examples:
- Docker NeXroll → Windows Plex (drive letter):
  - local: /data/prerolls
  - plex:  Z:\Prerolls
- Docker NeXroll → Windows Plex (UNC):
  - local: /data/prerolls
  - plex:  \\NAS\Prerolls
- Docker NeXroll → Docker Plex (Linux):
  - local: /data/prerolls
  - plex:  /media/prerolls
- Windows NeXroll → Windows Plex (same host):
  - local: C:\Prerolls
  - plex:  C:\Prerolls
- Windows NeXroll → Windows Plex (different host or service):
  - local: \\NAS\Prerolls
  - plex:  \\NAS\Prerolls

Use “Test Translation” in Settings to verify that a sample input path maps to the exact Plex-visible path you expect.

Platform preflight: Before sending paths to Plex, NeXroll verifies that translated paths match the Plex server platform (Windows vs POSIX). If they don’t match (for example, “/data/…” sent to a Windows Plex), Apply-to-Plex is refused with a clear instruction describing the mapping to add. This logic runs inside [app.post()](NeXroll/nexroll_backend/main.py:3186).


## 7) NAS mounts and container paths

- Linux hosts: mount your NAS (e.g., /mnt/nas/prerolls) and bind-mount it into the container (e.g., -v /mnt/nas/prerolls:/data/prerolls)
- Windows hosts: Linux containers cannot see Windows mapped drives; use a bind of a real path or run Plex on a path available to both. For Windows Plex, prefer UNC (\\NAS\share) when the Plex service cannot see a drive letter.


## 8) Connectivity diagnostics

If you can’t connect to Plex, open:

- GET /plex/probe?url=http://YOUR_PLEX:32400 at [app.get()](NeXroll/nexroll_backend/main.py:1742)

It checks DNS, reachability, token validity, and suggests fixes (TLS verify, DNS, firewall). On Docker Desktop, try http://host.docker.internal:32400.


## 9) Environment variables

- NEXROLL_PORT (default 9393)
- NEXROLL_DB_DIR (default /data)
- NEXROLL_PREROLL_PATH (default /data/prerolls)
- NEXROLL_SECRETS_DIR (default /data in compose)
- PLEX_URL / PLEX_TOKEN (optional bootstrap)
- TZ (default UTC)

Build arg:
- APP_VERSION (labels the image)


## 10) Health, FFmpeg, and logs

- Health check: GET /health
- FFmpeg info: GET /system/ffmpeg-info or from the Dashboard
- Logs and resolved paths are visible in the container logs on startup


## 11) Upgrades

Pull the latest image and recreate the container. Your data persists in the bind mount:

```bash
docker compose pull
docker compose up -d
```


## 12) Troubleshooting

- Container cannot reach Plex on 192.168.x.x:
  - On Linux, prefer network_mode: "host"
  - On Docker Desktop, use http://host.docker.internal and allow port 32400 in your host firewall for Docker/WSL subnets
- Plex doesn’t play preroll after Apply:
  - Your Plex host cannot see the path you sent. Add a mapping under Settings → “UNC/Local → Plex Path Mappings” so the translated output matches the Plex host platform and mount point (see section 6). The backend now validates platform and will refuse to send unusable paths.
- Thumbnails not generating:
  - Check GET /system/ffmpeg-info and the logs, or use POST /thumbnails/rebuild?force=true from the Dashboard


## 13) Image metadata

Images include OCI labels with title, description, version, and license. CI builds push to Docker Hub and GHCR. See the GitHub Actions workflows at:
- [docker-image.yml](.github/workflows/docker-image.yml:1)
- [docker-publish.yml](.github/workflows/docker-publish.yml:1)


---

If you run into issues or have an environment not covered here, open an issue with details about:
- Your platform (Linux distro, Docker Desktop, etc.)
- Where Plex runs (Windows/Docker/Linux)
- Your compose/docker run snippet
- A sample input path and the translated output you expect