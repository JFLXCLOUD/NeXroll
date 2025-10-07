# NeXroll v1.4.2 Release Notes

## Changes

### Jellyfin Integration Improvements
- **Fixed Jellyfin "Apply to Server" functionality**: The backend now sends full preroll file paths directly to the "Local Intros" plugin instead of parent directories. This ensures the plugin can properly configure intro videos.
- **Enhanced logging**: Added debug logging for Jellyfin plugin configuration updates to aid troubleshooting.
- **Updated messaging**: Success messages now reflect "paths" instead of "folders" for accuracy.

### Technical Details
- Modified `apply_category_to_jellyfin` in `main.py` to use `translated_paths` (file paths) instead of derived parent directories.
- Added `_file_log` calls for configuration payload and update results.
- Updated version numbers across build files to 1.4.2.

## Installation
Download the installer from the [Releases](https://github.com/JFLXCLOUD/NeXroll/releases) page.

## Checksums (SHA256)
```
97592B17DAFD21DD8585482247B2A7A08C3F66C04B6022C7D1774C99AEAEE6B3  NeXroll.exe
63A7E307EDE65FB535BC927D4D1848B400339FF1EE758E424E4DFB8B5768D578  NeXrollService.exe
A9DDAE49E0D136C53FCA04378A9E5CDD9CADB8FE083B73AA3758F1AB9FA69538  NeXrollTray.exe
8BF9C4E99274B1F8AC63B893D94C875560DD549EE472F623B5F6D94253136B48  setup_plex_token.exe
```

## Previous Versions
- [v1.4.1](RELEASE_NOTES_v1.4.1.md) - Frontend improvements and build optimizations
- [v1.4.0](RELEASE_NOTES_v1.4.0.md) - Jellyfin integration and UI enhancements