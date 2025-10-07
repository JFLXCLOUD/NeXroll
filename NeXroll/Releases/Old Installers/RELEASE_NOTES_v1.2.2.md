# NeXroll v1.2.2 

Release Date: 9-25-2025

---

This release adds external preroll folder mapping (including UNC shares) without moving files, plus UNC/local → Plex path translation used everywhere Plex is updated. It includes a Docker image/compose flow with persistent volume and file‑based token storage on Linux.

## Highlights
- Map Existing Preroll Folder (No Move): index an existing directory; managed=false; optional thumbnails; dry‑run + apply with progress in Settings.
- UNC/local → Plex Path Mappings: longest‑prefix match; Windows source case‑insensitive; separator inferred from destination; applied in manual “Apply to Plex” and the scheduler (shuffle/playlist and sequences).
- Docker support: multi‑stage Dockerfile with FFmpeg, docker-compose with /data bind‑mount, healthcheck, and secrets.json fallback for stable tokens.
- UI/UX: theme‑aware loading indicator and disabled controls during long Map operations.
- Reliability: lightweight runtime migrations create new columns automatically on older SQLite DBs (prerolls.managed, settings.path_mappings).

## Minimal change list
- Backend: POST /prerolls/map-root; GET/PUT /settings/path-mappings; POST /settings/path-mappings/test; path translation in /categories/{id}/apply-to-plex and scheduler.
- Frontend: Settings panels for Path Mappings and Map Existing Folder; dry‑run/apply flows with summaries.
- Packaging: Windows installer and Docker image updated for 1.2.2.

## Upgrade notes
1. Configure Path Mappings in Settings. Use “Test Translation” to verify outputs.
2. Run “Map Existing Preroll Folder (No Move)” (Dry Run first), then Apply if results look correct.
3. Apply your category to Plex; verify that paths match Plex‑visible mounts or drives.
4. For Docker, use `docker compose up -d --build` with `./nexroll-data` bound to `/data`.

## Release assets
- NeXroll_Installer

## Notes
- If Plex rejects a path, double‑check mapping prefixes and Plex access to the translated path.
- FFmpeg is required for thumbnails; verify via `GET /system/ffmpeg-info`.