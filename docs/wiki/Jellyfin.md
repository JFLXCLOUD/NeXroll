# Jellyfin Setup

This guide covers connecting NeXroll to **Jellyfin** and setting up the NeXroll Intros plugin so prerolls play automatically before movies and episodes.

## Overview

NeXroll supports Jellyfin through a combination of:

1. **Server Connection** — NeXroll connects to your Jellyfin server via API key
2. **NeXroll Intros Plugin** — A Jellyfin plugin that injects prerolls at playback time using Jellyfin's `IIntroProvider` system

Unlike Plex (which uses a simple preroll path string), Jellyfin requires a plugin to inject intros before playback. The plugin fetches your active prerolls from NeXroll, caches them locally, and registers them in Jellyfin's database so they can be played.

## Requirements

- **Jellyfin 10.10+** (uses the `IIntroProvider` API)
- **NeXroll v1.12.0+**
- **.NET 8 SDK** (only needed if building from source)
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

### Option 2: Pre-built DLL

1. Download [`NeXroll.Jellyfin.dll`](https://github.com/JFLXCLOUD/NeXroll/raw/main/Plugins/NeXroll.Jellyfin.dll) from the repository
2. Create a folder in your Jellyfin plugins directory:
   ```
   <Jellyfin Data>/plugins/NeXroll Intros/
   ```
   > **Note**: Jellyfin loads plugins from **subfolders** inside the `plugins/` directory — create a folder for the plugin.

   Common data paths:
   - **Windows**: `C:\ProgramData\Jellyfin\Server\plugins\NeXroll Intros\`
   - **Linux**: `/var/lib/jellyfin/plugins/NeXroll Intros/`
   - **Docker**: `/config/plugins/NeXroll Intros/` (inside the container)
3. Copy `NeXroll.Jellyfin.dll` into the `NeXroll Intros/` folder
4. **Restart Jellyfin**
5. Verify the plugin loaded: **Dashboard → Plugins** → look for "NeXroll Intros"

### Option 3: Build from Source

1. Install the [.NET 8 SDK](https://dot.net/download)
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

### Via Jellyfin Dashboard

You can also configure the plugin directly in Jellyfin:

1. Go to **Dashboard → Plugins → NeXroll Intros**
2. Enter the **NeXroll Server URL** (e.g., `http://192.168.1.50:9393`)
3. Click **Test Connection** to verify NeXroll is reachable
4. Enter an **API Key** (generate one in NeXroll under **Settings → API Keys**)
5. Configure **Path Mapping** if NeXroll and Jellyfin see preroll files at different paths:
   - **NeXroll Path Prefix**: The path as NeXroll sees it (e.g., `/data/prerolls`)
   - **Jellyfin Path Prefix**: The path as Jellyfin sees it (e.g., `/mnt/media/prerolls`)
6. Set **Max Intros** (default: 1 — how many prerolls to play per session)
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
6. **Cache Location**:
   - **Windows**: `%LocalAppData%\NeXroll\intro_cache\`
   - **Linux**: `~/.local/share/NeXroll/intro_cache/`

## Docker Setup

If running both NeXroll and Jellyfin in Docker:

```yaml
services:
  nexroll:
    image: nexroll:latest
    volumes:
      - /srv/prerolls:/data/prerolls
    ports:
      - "9393:9393"

  jellyfin:
    image: jellyfin/jellyfin
    volumes:
      - /srv/prerolls:/media/prerolls
      - jellyfin-config:/config
    ports:
      - "8096:8096"
```

In the plugin config, set up path mapping:
- **NeXroll Path Prefix**: `/data/prerolls`
- **Jellyfin Path Prefix**: `/media/prerolls`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No intros playing | Verify the plugin is installed and configured with the correct NeXroll URL |
| Plugin not visible in Jellyfin | Ensure the DLL is inside a subfolder of `plugins/` (e.g., `plugins/NeXroll Intros/`). Restart Jellyfin |
| "Could not reach NeXroll" in logs | Check the NeXroll URL in plugin settings. Verify port 9393 is accessible from Jellyfin |
| Files not found | Configure path mapping if NeXroll and Jellyfin use different mount points |
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
| Max Intros | `1` | Maximum number of prerolls per playback session (0 = unlimited) |
| Timeout Seconds | `5` | Network timeout when contacting NeXroll server |
