# Emby Setup

This guide covers connecting NeXroll to **Emby Server** and setting up the NeXroll Intros plugin so prerolls play automatically before movies and episodes.

## Overview

NeXroll supports Emby through a combination of:

1. **Server Connection** — NeXroll connects to your Emby server via API key
2. **NeXroll Intros Plugin** — An Emby plugin that injects prerolls at playback time using Emby's Cinema Mode system

Unlike Plex (which uses a simple preroll path string), Emby requires a plugin to inject intros before playback. The plugin fetches your active prerolls from NeXroll and caches them locally so Emby can register them as library items.

## Requirements

- **Emby Server 4.8+** (tested on 4.9.x)
- **NeXroll v1.12.0+**
- **Emby Premiere** (Cinema Mode requires an active Emby Premiere subscription)
- Network access between NeXroll and Emby (default port: 9393)

## Step 1: Connect NeXroll to Emby

1. Open NeXroll in your browser (`http://your-server:9393`)
2. Go to the **Connect** tab
3. Select the **Emby** section
4. Enter your **Emby Server URL** (e.g., `http://192.168.1.100:8099`)
5. Enter your **Emby API Key**
   - In Emby: **Settings → API Keys → New API Key**
   - Give it a name like "NeXroll"
6. Click **Connect**

Once connected, NeXroll can communicate with your Emby server and auto-detect the plugin.

## Step 2: Install the NeXroll Intros Plugin

### Option 1: Automatic (via NeXroll UI)

If NeXroll is already connected to Emby, it can detect and configure the plugin automatically:

1. In NeXroll's **Connect → Emby** section, look for the **Plugin Detection** panel
2. Click **Detect Plugin** — NeXroll will check if the plugin is already installed
3. If detected, click **Configure Plugin** to push your NeXroll URL and settings to the plugin

### Option 2: Manual Install

1. Download [`NeXroll.Emby.dll`](https://github.com/JFLXCLOUD/NeXroll/raw/main/Plugins/NeXroll.Emby.dll) from the repository
2. Copy the DLL to your Emby plugins directory:
   ```
   <Emby Data>/plugins/NeXroll.Emby.dll
   ```
   > **Note**: Emby loads plugins as individual DLLs directly in the `plugins/` folder — do **not** place it in a subfolder.

   Common plugin paths:
   - **Windows**: `C:\Users\<user>\AppData\Roaming\Emby-Server\plugins\`
   - **Linux**: `/var/lib/emby/plugins/`
   - **Docker**: `/config/plugins/` (inside the container)
3. **Restart Emby Server**
4. Verify the plugin loaded: **Settings → Plugins** → look for "NeXroll Intros"

### Building from Source

If you prefer to build the plugin yourself:

1. Clone the NeXroll repository
2. Copy the following DLLs from your Emby Server installation to the `emby-libs/` folder:
   - `MediaBrowser.Common.dll`
   - `MediaBrowser.Controller.dll`
   - `MediaBrowser.Model.dll`
3. Build:
   ```bash
   cd Plugins/NeXroll.Emby
   dotnet publish -c Release -o ./publish
   ```
4. Copy `publish/NeXroll.Emby.dll` to Emby's plugins folder
5. Restart Emby

## Step 3: Configure the Plugin

### Via NeXroll (Recommended)

The easiest way is to use NeXroll's built-in plugin configuration:

1. Go to **Connect → Emby** in NeXroll
2. Click **Detect Plugin**, then **Configure Plugin**
3. NeXroll will automatically:
   - Set the NeXroll server URL
   - Generate and assign an API key for the plugin
   - Configure path mappings if needed

### Via Emby Dashboard

You can also configure the plugin directly in Emby:

1. Go to **Settings → Plugins → NeXroll Intros**
2. Enter the **NeXroll Server URL** (e.g., `http://192.168.1.50:9393`)
3. Enter an **API Key** (generate one in NeXroll under **Settings → API Keys**)
4. Configure **Path Mapping** if NeXroll and Emby see preroll files at different paths:
   - **NeXroll Path Prefix**: The path as NeXroll sees it (e.g., `\\server\prerolls`)
   - **Emby Path Prefix**: The path as Emby sees it (e.g., `/mnt/prerolls`)
5. Set **Max Intros** (default: 1 — how many prerolls to play per session)
6. Toggle **Enable for Movies** / **Enable for Episodes**
7. Click **Save**

## Step 4: Enable Cinema Mode

Emby's Cinema Mode is what actually plays intros before content. The NeXroll plugin hooks into this system.

1. In Emby, go to **Settings → Cinema Mode**
2. Ensure **Cinema Mode** is turned **On**
3. Check **Enable intros for Movies** and/or **Enable intros for Episodes**
4. **Important**: Enable **"Include trailers from my movies in my library"** — this is required for the plugin's locally-cached intros to be recognized and played
5. Save your settings

> **Without this setting enabled, prerolls will not play** even if the plugin is installed and configured correctly. This is because Emby only plays intros that are registered as library items, and this setting controls whether locally-registered intro files are included.

## Step 5: Refresh Custom Intros

After the plugin is configured and Cinema Mode is enabled, Emby needs to scan and register the cached intro files:

1. Go to **Emby Dashboard → Scheduled Tasks**
2. Find **"Refresh Custom Intros"** under the **Library** section
3. Click the play button to run it immediately

This task tells Emby to call the plugin's `GetAllIntroFiles()` method, which returns all cached preroll files. Emby then registers them as playable library items.

> This task runs automatically on a schedule, but you should trigger it manually the first time or whenever you add new prerolls in NeXroll.

## Step 6: Test Playback

1. Play any movie in Emby
2. A preroll should play before the movie starts
3. Check the Emby server log for messages like:
   ```
   NeXroll: Injecting 1 intro(s) before Movie 'Movie Name'
   ```

## How It Works (Technical)

The NeXroll Emby plugin uses Emby's `IIntroProvider` interface:

1. **Cache Sync**: The plugin periodically fetches all available prerolls from NeXroll's `/plugin/intros` endpoint and downloads them to a local cache directory
2. **File Registration**: `GetAllIntroFiles()` returns all cached file paths so Emby can register them as library items during the "Refresh Custom Intros" task
3. **Playback Selection**: When a user starts a movie/episode, `GetIntros()` is called — the plugin fetches the current active prerolls from NeXroll, selects up to `MaxIntros` from the cache, and returns them for playback
4. **Cache Location**: Files are cached at:
   - **Windows**: `%LocalAppData%\NeXroll\intro_cache\`
   - **Linux**: `~/.local/share/NeXroll/intro_cache/`

The cache syncs every 10 minutes to pick up schedule changes in NeXroll.

## Docker Setup

If running both NeXroll and Emby in Docker:

```yaml
services:
  nexroll:
    image: nexroll:latest
    volumes:
      - /srv/prerolls:/data/prerolls
    ports:
      - "9393:9393"

  emby:
    image: emby/embyserver
    volumes:
      - /srv/prerolls:/media/prerolls
      - emby-config:/config
    ports:
      - "8096:8096"
```

In the plugin config, set up path mapping:
- **NeXroll Path Prefix**: `/data/prerolls`
- **Emby Path Prefix**: `/media/prerolls`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No intros playing | Ensure Cinema Mode is **On** and **"Include trailers from my movies in my library"** is checked |
| Plugin not visible in Emby | Verify `NeXroll.Emby.dll` is directly in the `plugins/` folder (not a subfolder). Restart Emby |
| "Could not reach NeXroll" in logs | Check the NeXroll URL in plugin settings. Verify port 9393 is accessible |
| Intros not updating | Run "Refresh Custom Intros" from Scheduled Tasks. The cache syncs every 10 minutes |
| Files not found after schedule change | Wait for the next cache sync (10 min) or restart Emby to force a fresh sync |
| Plugin detected but 0 intros returned | Make sure you have an active category or filler set in NeXroll |
| Prerolls play for movies but not episodes | Check that "Enable for Episodes" is turned on in both Cinema Mode and the plugin config |

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| NeXroll Server URL | *(empty)* | Full URL to your NeXroll server (e.g., `http://192.168.1.50:9393`) |
| API Key | *(empty)* | API key for authenticating with NeXroll |
| Path Prefix From | *(empty)* | Path prefix as NeXroll sees it |
| Path Prefix To | *(empty)* | Path prefix as Emby sees it |
| Enable for Movies | `true` | Play intros before movies |
| Enable for Episodes | `true` | Play intros before TV episodes |
| Max Intros | `1` | Maximum number of prerolls per playback session (0 = 1) |
| Timeout Seconds | `5` | Network timeout when contacting NeXroll server |
