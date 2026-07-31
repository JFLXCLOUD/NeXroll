# Path Mappings

Path mappings translate the file path NeXroll uses into the path your media server can access.

This matters when NeXroll and Plex, Jellyfin, or Emby do not see storage through the same filesystem. A Docker container might see a preroll at `/data/prerolls/intro.mp4`, while a media server installed on the host or a NAS sees that same file at `/mnt/media/prerolls/intro.mp4`.

## The Two Paths

- **NeXroll path:** The path visible inside the NeXroll process or container.
- **Media server path:** The path visible to Plex, Jellyfin, or Emby.

Map the shared root, not each individual file. NeXroll then translates every path beneath it before applying prerolls to the media server.

## Common Symptoms

- A preroll appears in NeXroll but does not play.
- Plex reports that a file path does not exist.
- Thumbnails work in NeXroll while playback fails in the media server.
- A path beginning with `/data/` is sent to a server that cannot see the container filesystem.

The media server must either be able to read the mapped destination or use the supported Jellyfin/Emby plugin streaming behavior.

Follow the canonical [Path Mappings guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Path-Mappings) for current examples.
