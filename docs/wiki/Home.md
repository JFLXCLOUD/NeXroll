# Home

![NeXroll Logo](https://github.com/JFLXCLOUD/NeXroll/raw/main/NeXroll/frontend/NeXroll_Logo_WHT.png?raw=true)

**NeXroll** is a modern preroll management system for **Plex**, **Jellyfin**, and **Emby** with a beautiful web UI, powerful scheduling, and seamless media server integration.

**Web UI**: http://localhost:9393

[![Discord](https://img.shields.io/discord/1439077075117150313?label=Discord&logo=discord&logoColor=white)](https://discord.gg/nexroll)

## What's New in v1.12.0

- **Emby Support**: Full Emby integration with the NeXroll Intros plugin and Cinema Mode
- **Plugin Auto-Detection**: NeXroll can detect and configure Jellyfin/Emby plugins directly from the Connect tab
- **Coming Soon List Generator**: Create dynamic video prerolls showcasing upcoming movies and shows from Radarr/Sonarr with grid or list layouts
- **Authentication System**: Secure access with API keys and optional username/password login
- **Enhanced Update System**: Configurable update checking with changelog display
- **Enhanced Logging**: View, search, filter, and export logs directly in the UI
- **Filler Category**: Global fallback prerolls for when no schedules are active
- **Weekly Calendar Preview**: Mini calendar on the Dashboard showing this week's schedule

## Key Features

### Preroll Management
- Upload multiple preroll videos with metadata and tags
- Automatic thumbnail generation (FFmpeg)
- Bulk operations and multi-select workflow
- Import existing preroll folders without moving files
- Video quality dashboard with resolution breakdown
- Batch video scaling (1080p, 720p, 480p)

### Smart Scheduling
- **Date Ranges**: Set start/end dates for seasonal prerolls
- **Time Restrictions**: Limit schedules to specific hours (e.g., 10pm-3am for mature content)
- **Exclusive Mode**: One schedule takes over completely
- **Blend Mode**: Multiple schedules combine their prerolls
- **Priority & Win/Lose Logic**: Control which schedule wins during overlaps
- **Fallback Category**: Per-schedule default when a schedule ends
- **Filler Category**: Global fallback when no schedules are active
- **Conflict Detection**: Visual warnings for overlapping exclusive schedules

### Calendar Visualization
- **Year View**: See your entire preroll schedule at a glance
- **Month/Week Views**: Detailed daily breakdowns with schedule info
- **Conflict Detection**: Visual indicators for overlapping schedules
- **Today Indicator**: Always know what's currently active
- **Weekly Calendar Preview**: Dashboard mini-calendar for quick overview

### NeX-Up - Trailer Integration
- **Radarr & Sonarr Integration**: Automatically discover and download trailers for upcoming releases
- **YouTube Trailer Downloads**: With cookie file support for reliable downloads
- **Coming Soon List Generator**: Dynamic video prerolls with grid or list layouts, color customization, and poster artwork
- **Dynamic Preroll Generator**: Create custom "Coming Soon to [Your Server]" intro videos
- **Sequence Builder Presets**: Quick templates for theater-style experiences
- **Auto-Cleanup**: Automatically removes trailers when content is released

### Sequences
- **Sequence Builder**: Visually construct preroll playlists from blocks
- **Random & Fixed Blocks**: Mix randomized category picks with specific prerolls
- **Export/Import**: Share sequences as `.nexseq` files
- **Schedule Integration**: Use sequences directly in schedules

### Authentication & Security
- **API Key System**: Generate scoped API keys for external access
- **User Accounts**: Optional username/password authentication with login page
- **Session Management**: Secure sessions with configurable expiration
- **Audit Log**: Track authentication events
- **External API**: Access NeXroll data programmatically with API keys

### Holiday Presets
- 32 built-in holiday presets (Halloween, Christmas, Valentine's Day, etc.)
- One-click initialization creates categories and date ranges
- Holiday Browser to download community prerolls

### Media Server Integration
- **Plex**: Direct API integration with path translation support
- **Jellyfin**: Preroll injection via NeXroll Intros plugin with auto-detection and remote configuration
- **Emby**: Preroll injection via NeXroll Intros plugin with Cinema Mode integration
- Plugin auto-detection and configuration from the NeXroll Connect tab
- Secure credential storage with encryption
- Genre-based preroll mapping (experimental)

### System & Administration
- **Enhanced Logging**: View, search, filter, and export logs in the web UI
- **Update Notifications**: Configurable update checking with changelog display
- **System & Files Backup**: Complete backup including database, prerolls, and thumbnails
- **Video Scaling**: Batch transcode prerolls to target resolutions

### Deployment Options
- **Windows Installer**: One-click setup with optional Windows Service and System Tray
- **Docker**: Official images for AMD64 and ARM64
- **Unraid**: Community Applications template available

## Installation

### Windows
Download the latest installer from [Releases](https://github.com/JFLXCLOUD/NeXroll/releases)

### Docker
```bash
docker pull jbrns/nexroll:latest
```

### Unraid
Search for "NeXroll" in Community Applications

## Quick Links

- [Installation Guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Installation)
- [Getting Started](https://github.com/JFLXCLOUD/NeXroll/wiki/Getting-Started)
- [Docker Setup](https://github.com/JFLXCLOUD/NeXroll/wiki/Docker)
- [Configuration](https://github.com/JFLXCLOUD/NeXroll/wiki/Configuration)
- [Scheduling Guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Scheduling)
- [NeX-Up (Trailers)](https://github.com/JFLXCLOUD/NeXroll/wiki/NeX-Up)
- [Sequences](https://github.com/JFLXCLOUD/NeXroll/wiki/Sequences)
- [Path Mappings](https://github.com/JFLXCLOUD/NeXroll/wiki/Path-Mappings)
- [API Documentation](https://github.com/JFLXCLOUD/NeXroll/wiki/API)
- [Troubleshooting](https://github.com/JFLXCLOUD/NeXroll/wiki/Troubleshooting)
- [Jellyfin Setup](https://github.com/JFLXCLOUD/NeXroll/wiki/Jellyfin)
- [Emby Setup](https://github.com/JFLXCLOUD/NeXroll/wiki/Emby)
- [FAQ](https://github.com/JFLXCLOUD/NeXroll/wiki/FAQ)

## Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/j_b__)

## License

MIT License. See [LICENSE](https://github.com/JFLXCLOUD/NeXroll/blob/main/LICENSE) for details.
