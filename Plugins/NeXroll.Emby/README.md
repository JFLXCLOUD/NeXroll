# NeXroll Intros — Emby Plugin

An Emby plugin that injects preroll intros from your **NeXroll** server before movies and episodes.

## How It Works

Identical to the Jellyfin variant — the plugin implements Emby's `IIntroProvider` interface and calls your NeXroll server's `/plugin/intros` endpoint at playback time.

## Requirements

- **Emby Server 4.8+**
- **NeXroll v1.11.12+** (with the `/plugin/intros` endpoint)
- Emby server DLLs for compilation (not distributed via NuGet)
- Shared file access to preroll videos

## Building

Emby does not publish its SDK on NuGet. You need to reference the server DLLs directly:

1. Locate your Emby Server installation and find:
   - `MediaBrowser.Common.dll`
   - `MediaBrowser.Controller.dll`
   - `MediaBrowser.Model.dll`

2. Copy them to `../../emby-libs/` relative to this project (or update the paths in `NeXroll.Emby.csproj`).

3. Build:
   ```bash
   dotnet publish -c Release -o ./publish
   ```

4. Copy `publish/NeXroll.Emby.dll` to `Emby/plugins/NeXroll Intros/`.

5. Restart Emby.

## Configuration

1. Go to **Settings → Plugins → NeXroll Intros**.
2. Enter your **NeXroll Server URL** (e.g., `http://192.168.1.50:9393`).
3. Configure **Path Mapping** if NeXroll and Emby have different file system views.
4. **Save** and test.

## Notes

- The Emby `IIntroProvider` API may differ slightly between major versions. This plugin targets Emby 4.8+.
- If you experience issues, check the Emby server log for messages from "NeXroll".
