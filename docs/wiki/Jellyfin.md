# Jellyfin Setup

This guide covers connecting NeXroll to **Jellyfin** and setting up the NeXroll Intros plugin so prerolls play automatically before movies and episodes.

## Overview

NeXroll supports Jellyfin through a combination of:

1. **Server Connection** — NeXroll connects to your Jellyfin server via API key
2. **NeXroll Intros Plugin** — A Jellyfin plugin that injects prerolls at playback time using Jellyfin's `IIntroProvider` system

Unlike Plex (which uses a simple preroll path string), Jellyfin requires a plugin to inject intros before playback. The plugin fetches your active prerolls from NeXroll, caches them locally, and registers them in Jellyfin's database so they can be played.

## Requirements

- **Jellyfin 10.11+** (uses the `IIntroProvider` API)
- **NeXroll v1.12.0+** — use **plugin v1.14.0+** for Docker/Unraid; it fixes preroll caching when Jellyfin can't read the files directly
- **.NET 9 SDK** (only needed if building from source)
- Network access between NeXroll and Jellyfin (default port: 9393)

## Step 1: Connect NeXroll to Jellyfin

1. Open NeXroll in your browser (`http://your-server:9393`)
2. Go to the **Connect** tab
3. Select the **Jellyfin** section
4. Enter your **Jellyfin URL** (e.g., `http://192.168.1.100:8096`)
5. Enter your **Jellyfin API Key**
   - In Jellyfin: **Dashboard → API Keys → Create** (the `+` button)
   - Give it a name like "NeXroll"
6. Click **Connect**

Once connected, NeXroll can communicate with your Jellyfin server and auto-detect the plugin.

## Step 2: Install the NeXroll Intros Plugin

### Option 1: Automatic (via NeXroll UI)

If NeXroll is already connected to Jellyfin, it can detect and configure the plugin automatically:

1. In NeXroll's **Connect → Jellyfin** section, look for the **Plugin Detection** panel
2. Click **Detect Plugin** — NeXroll will check if the plugin is already installed
3. If detected, click **Configure Plugin** to push your NeXroll URL and settings to the plugin

### Option 2: Download the plugin package (zip)

1. Download the plugin zip — either from NeXroll's **Connect → Jellyfin** page (the **Download Plugin** link, served straight from your NeXroll), or from the [GitHub releases](https://github.com/JFLXCLOUD/NeXroll/releases) (`NeXroll.Jellyfin-<version>.zip`).
   > The zip contains `NeXroll.Jellyfin.dll`, `meta.json`, and `thumb.png`. A **bare DLL won't register** — Jellyfin needs `meta.json` for the plugin's name and version.
2. Create a folder in your Jellyfin plugins directory:
   ```
   <Jellyfin Data>/plugins/NeXroll Intros/
   ```
   > **Note**: Jellyfin loads plugins from **subfolders** inside the `plugins/` directory — create a folder for the plugin.

   Common data paths:
   - **Windows**: `C:\ProgramData\Jellyfin\Server\plugins\NeXroll Intros\`
   - **Linux**: `/var/lib/jellyfin/plugins/NeXroll Intros/`
   - **Docker**: `/config/plugins/NeXroll Intros/` (inside the container)
3. Extract the contents of the zip (all three files) into the `NeXroll Intros/` folder
4. **Restart Jellyfin**
5. Verify the plugin loaded: **Dashboard → Plugins** → look for "NeXroll Intros"

### Option 3: Build from Source

1. Install the [.NET 9 SDK](https://dot.net/download)
2. Build:
   ```bash
   cd Plugins/NeXroll.Jellyfin
   dotnet publish -c Release -o ./publish
   ```
3. Copy the contents of `publish/` to `<Jellyfin Data>/plugins/NeXroll Intros/`
4. Restart Jellyfin

## Step 3: Configure the Plugin

### Via NeXroll (Recommended)

The easiest way is to use NeXroll's built-in plugin configuration:

1. Go to **Connect → Jellyfin** in NeXroll
2. Click **Detect Plugin**, then **Configure Plugin**
3. NeXroll will automatically:
   - Set the NeXroll server URL
   - Generate and assign an API key for the plugin
   - Configure path mappings if needed

   You can also set the plugin's **Playback options** right here — **Max Intros** (`0` = play the whole active sequence), **Enable for Movies / Episodes**, and the request timeout — then click **Update Plugin Configuration** to push them to Jellyfin.

### Via Jellyfin Dashboard

You can also configure the plugin directly in Jellyfin:

1. Go to **Dashboard → Plugins → NeXroll Intros**
2. Enter the **NeXroll Server URL** (e.g., `http://192.168.1.50:9393`)
3. Click **Test Connection** to verify NeXroll is reachable
4. Enter an **API Key** (generate one in NeXroll under **Settings → API Keys**)
5. Configure **Path Mapping** if NeXroll and Jellyfin see preroll files at different paths:
   - **NeXroll Path Prefix**: The path as NeXroll sees it (e.g., `/data/prerolls`)
   - **Jellyfin Path Prefix**: The path as Jellyfin sees it (e.g., `/mnt/media/prerolls`)
6. Set **Max Intros** (default: `0` = unlimited — plays the whole active sequence; set a number only if you want to cap how many play)
7. Toggle **Enable for Movies** / **Enable for Episodes**
8. Click **Save**

## Step 4: Test Playback

1. Play any movie in Jellyfin
2. A preroll should play before the movie starts
3. Check the Jellyfin server log for messages like:
   ```
   [NeXroll] Injecting 1 intro(s) before Movie 'Movie Name'
   ```

## How It Works (Technical)

The NeXroll Jellyfin plugin uses Jellyfin's `IIntroProvider` interface:

1. **Preroll Fetch**: When a user presses play, Jellyfin calls the plugin's `GetIntros()` method
2. **NeXroll API Call**: The plugin calls NeXroll's `/plugin/intros` endpoint to get the currently-active preroll list (respecting your schedules, fillers, and sequences)
3. **Local Cache**: Preroll files are downloaded to a local cache directory via NeXroll's `/plugin/stream` endpoint
4. **Database Registration**: Cached files are resolved via Jellyfin's `ILibraryManager` and saved as `Video` items in the database so Jellyfin can play them
5. **Playback Injection**: The plugin returns `IntroInfo` items with the registered `ItemId` — Jellyfin plays them before the main content
6. **Cache Location** (plugin v1.14.0+): Jellyfin's own plugin data folder (under the server config dir), falling back to the system temp directory. Older versions cached to `%LocalAppData%\NeXroll\intro_cache` / `~/.local/share/NeXroll`, which **failed on Docker/Unraid** — the service has no `HOME`, so the path collapsed to `/NeXroll` at the container root and threw `Access to the path '/NeXroll' is denied`. Update to **v1.14.0+** if you hit that error.

## Docker Setup

If running both NeXroll and Jellyfin in Docker:

```yaml
services:
  nexroll:
    image: nexroll:latest
    volumes:
      - /srv/prerolls:/data/prerolls
      - /srv/nexup-trailers:/data/nexup_trailers
    ports:
      - "9393:9393"

  jellyfin:
    image: jellyfin/jellyfin
    volumes:
      - /srv/prerolls:/media/prerolls
      - /srv/nexup-trailers:/data/nexup_trailers:ro
      - jellyfin-config:/config
    ports:
      - "8096:8096"
```

In the plugin config, set up path mapping:
- **NeXroll Path Prefix**: `/data/prerolls`
- **Jellyfin Path Prefix**: `/media/prerolls`

> **No shared mount? Path mapping is optional.** If Jellyfin can't see the preroll files directly (e.g. you don't mount the prerolls share into the Jellyfin container), the plugin **streams** each preroll from NeXroll over HTTP and caches it locally — so prerolls still play with no path mapping at all. Just make sure the plugin's **NeXroll Server URL** is reachable from the Jellyfin container, and you're on **plugin v1.14.0+**.

### Normal prerolls play, but NeX-Up trailers do not

Normal prerolls and NeX-Up trailers can live in different directories. A typical NeXroll container returns paths like:

```text
/data/prerolls/seasons/summer/intro.mp4
/data/nexup_trailers/tv/example_trailer.mp4
```

If Jellyfin can read `/data/prerolls` but cannot read `/data/nexup_trailers`, the normal preroll may play while the trailers are skipped. The most reliable fix is to mount the NeX-Up trailer host directory into **both** containers, using the same container path:

```yaml
# NeXroll
- /path/on/host/trailers:/data/nexup_trailers

# Jellyfin (read-only is sufficient)
- /path/on/host/trailers:/data/nexup_trailers:ro
```

For Unraid, add the same host share (for example, `/mnt/user/media/trailers`) to both containers with the container path `/data/nexup_trailers`. Set the Jellyfin mapping to **Read Only** if Jellyfin does not need to modify the files. Then:

1. In NeXroll, set **NeX-Up → Settings → Storage Path** to `/data/nexup_trailers`.
2. Confirm the Jellyfin container can read the directory and its `.mp4` files.
3. Restart both containers after changing their volume mappings.
4. Start a new movie playback test.

If Jellyfin uses a different internal path, configure the plugin mapping instead. For example:

- **NeXroll Path Prefix**: `/data/nexup_trailers`
- **Jellyfin Path Prefix**: `/media/trailers`

The plugin can also fall back to downloading each trailer from NeXroll into Jellyfin's local `intro_cache`. If a shared mount or path mapping does not resolve the problem:

1. Update or reinstall the latest NeXroll Intros plugin and restart Jellyfin.
2. Make sure the configured NeXroll URL is reachable **from inside the Jellyfin container**. Use the NeXroll container/service name or the server's LAN IP; do not use `localhost` unless NeXroll runs in the same container.
3. Confirm Jellyfin's config/plugin-data directory is writable so the plugin can create `intro_cache`.
4. Reproduce the problem once, then search the Jellyfin server log for `NeXroll`, `Failed to download intro`, `ResolvePath`, `intro_cache`, or `/data/nexup_trailers`.

If NeXroll's event log says it is returning the full sequence, including trailer paths, but only the normal preroll plays, that normally points to a Jellyfin-side mount, path-translation, HTTP fallback, or cache-permission problem rather than a NeX-Up selection problem.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No intros playing | Verify the plugin is installed and configured with the correct NeXroll URL |
| Plugin not visible in Jellyfin | Ensure all three files (`NeXroll.Jellyfin.dll`, `meta.json`, `thumb.png`) are inside a subfolder of `plugins/` (e.g., `plugins/NeXroll Intros/`) — a bare DLL won't register. Restart Jellyfin |
| "Could not reach NeXroll" in logs | Check the NeXroll URL in plugin settings. Verify port 9393 is accessible from Jellyfin |
| Files not found | Set up path mapping (shared mount) **or** rely on streaming — make sure the plugin's NeXroll URL is reachable and you're on v1.14.0+ |
| `Access to the path '/NeXroll' is denied` (Docker/Unraid) | Update the plugin to **v1.14.0+** — older versions cached prerolls to an unwritable path |
| Only the first preroll plays / sequence items skipped | Set **Max Intros** to `0` (unlimited). Compare the Jellyfin log's `Injecting N intro(s)` line to your sequence length |
| Normal prerolls play, but NeX-Up trailers do not | Mount the NeX-Up storage directory into Jellyfin at `/data/nexup_trailers` (read-only is sufficient), or map `/data/nexup_trailers` to Jellyfin's actual trailer path. Restart Jellyfin and check its log for `NeXroll` or `Failed to download intro` |
| Plugin detected but 0 intros | Make sure you have an active category or filler set in NeXroll |
| Prerolls play for movies but not episodes | Check that "Enable for Episodes" is turned on in the plugin config |
| Test Connection fails | Ensure NeXroll is running and the URL includes the port (e.g., `http://192.168.1.50:9393`) |

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| NeXroll Server URL | *(empty)* | Full URL to your NeXroll server (e.g., `http://192.168.1.50:9393`) |
| API Key | *(empty)* | API key for authenticating with NeXroll |
| Path Prefix From | *(empty)* | Path prefix as NeXroll sees it |
| Path Prefix To | *(empty)* | Path prefix as Jellyfin sees it |
| Enable for Movies | `true` | Play intros before movies |
| Enable for Episodes | `true` | Play intros before TV episodes |
| Max Intros | `0` | Maximum number of prerolls per playback session (`0` = unlimited — plays the whole active sequence) |
| Timeout Seconds | `5` | Network timeout when contacting NeXroll server |
