# NeXroll Intros — Jellyfin Plugin

A Jellyfin plugin that injects preroll intros from your **NeXroll** server before movies and episodes — just like Plex Cinema Trailers, but powered by your NeXroll schedule, filler system, sequences, and Coming Soon lists.

## How It Works

1. When a user starts playing a movie or episode, Jellyfin asks all registered `IIntroProvider` plugins for intro items.
2. This plugin calls your NeXroll server's `/plugin/intros` endpoint to get the currently-active preroll paths in real time.
3. The returned video files are injected before playback — respecting your active schedule, filler category/sequence, or Coming Soon list.

## Requirements

- **Jellyfin 10.10+** (uses the `IIntroProvider` API)
- **NeXroll v1.11.12+** (with the `/plugin/intros` endpoint)
- **.NET 8 SDK** (only to build; not needed to run)
- Both servers must be able to access the same preroll video files (via shared storage, NFS mount, Docker volume, etc.)

## Installation

### Option 1: Pre-built DLL (Recommended)

1. Download the latest [`NeXroll.Jellyfin.dll`](https://github.com/JFLXCLOUD/NeXroll/raw/main/Plugins/NeXroll.Jellyfin.dll) from the repository.
2. Create a folder in your Jellyfin plugins directory:
   ```
   Jellyfin/data/plugins/NeXroll Intros/
   ```
3. Copy `NeXroll.Jellyfin.dll` into that folder.
4. Restart Jellyfin.

### Option 2: Build from Source

1. Install the [.NET 8 SDK](https://dot.net/download).
2. Run `build.bat` (Windows) or:
   ```bash
   dotnet publish -c Release -o ./publish
   ```
3. Copy the contents of the `publish/` folder to `Jellyfin/data/plugins/NeXroll Intros/`.
4. Restart Jellyfin.

## Configuration

After installing and restarting Jellyfin:

1. Go to **Dashboard → Plugins → NeXroll Intros**.
2. Enter your **NeXroll Server URL** (e.g., `http://192.168.1.50:9393`).
3. Click **Test Connection** to verify.
4. If NeXroll and Jellyfin see files at different paths, configure the **Path Mapping**:
   - **NeXroll Path Prefix**: The path as NeXroll reports it (e.g., `/data/prerolls`)
   - **Jellyfin Path Prefix**: The path as Jellyfin sees it (e.g., `/mnt/media/prerolls`)
5. Toggle Movies / Episodes as desired.
6. Click **Save**.

## Docker Example

If both NeXroll and Jellyfin are in Docker containers with shared volumes:

```yaml
# docker-compose.yml snippet
services:
  nexroll:
    image: nexroll:latest
    volumes:
      - /srv/prerolls:/data/prerolls    # NeXroll sees /data/prerolls
    ports:
      - "9393:9393"

  jellyfin:
    image: jellyfin/jellyfin
    volumes:
      - /srv/prerolls:/media/prerolls   # Jellyfin sees /media/prerolls
      - ./plugins:/config/plugins
```

In the plugin config:
- **NeXroll Path Prefix**: `/data/prerolls`
- **Jellyfin Path Prefix**: `/media/prerolls`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No intros playing | Check that NeXroll has an active category/filler set |
| "Could not reach NeXroll" | Verify the URL is correct and firewall allows port 9393 |
| Files not found | Configure path mapping if containers use different mount points |
| Plugin not visible | Ensure the DLL is in the correct plugins subfolder and restart Jellyfin |

## API Reference

The plugin calls these NeXroll endpoints:

- **`GET /plugin/intros`** — Returns the currently-active preroll paths
  - Query params: `media_type`, `item_id`
  - Response: `{ "Items": [{"Path": "...", "Name": "..."}], "TotalRecordCount": N, "Mode": "shuffle|sequential|single" }`

- **`GET /plugin/health`** — Simple health check
  - Response: `{ "status": "ok", "app": "NeXroll" }`
