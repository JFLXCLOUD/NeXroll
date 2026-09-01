# Home

![NeXroll Logo](https://github.com/JFLXCLOUD/NeXroll/raw/main/NeXroll/frontend/NeXroll_Logo_WHT.png?raw=true)

**NeXroll** is a modern preroll management system for **Plex**, **Jellyfin**, and **Emby** with a beautiful web UI, powerful scheduling, and seamless media server integration.

**Web UI**: http://localhost:9393

[![Discord](https://img.shields.io/discord/1439077075117150313?label=Discord&logo=discord&logoColor=white)](https://discord.gg/nexroll)

## What's New in v2.2.0

### Scheduling

- **Holiday schedules land on the actual holiday.** Dates are derived from the next upcoming occurrence when you save, and roll into next year once this year's has passed. Country and holiday are now pickers showing what will really resolve, instead of free text matched by exact name.
- **Conflicts and overlap on the calendar.** A banner counts open conflicts in the next 30 days and links to the Conflicts page, and each schedule shows whether it is Exclusive or Blends.
- Disabled schedules no longer appear on the calendar as though they will run.

### NeX-Up and the Generator Studio

- **Poster views** for Upcoming releases and Your Trailers, alongside list and calendar.
- **Trailer storage in first-run setup**, on both Windows and Docker, with a check telling you whether your media server will actually be able to open files there.
- **Animated theme backdrops** in rendered Coming Soon lists, not just in the preview.
- **Text size and per-role colours** — heading, titles, dates, and "Available Now!" each have their own control.
- **Match a preroll's length to its soundtrack**, so an uploaded track plays in full.
- Sequence Builder gained controls for how many prerolls a category block plays and in what order; generated content is one block type instead of two.

### Community Prerolls

- **Multi-select and bulk download**, paced to stay polite to the community server.
- Duration and file size are resolved on demand instead of always reading "Unknown".

### Setup and recovery

- **Path Mappings in first-run setup** for Docker installs, with your real container mounts offered as one-click choices.
- **Sign in with Plex from inside the wizard**, rather than being sent away from it.
- **Run Setup Wizard** from Settings → System to walk through setup again without resetting anything.
- **Backups now include every setting** — connections, path mappings, NeX-Up and generator defaults, dashboard layout — so a restore on a new machine comes back configured. System backups also carry generated prerolls and brand assets.

### Fixed

- Trailer downloads on the Windows installer, which shipped a five-month-old yt-dlp that YouTube had moved past.
- The schedule wizard creating the schedule when you clicked Continue.
- The PO-token provider offering "Install" when it was already installed, and repairing itself if a previous install left it broken.

## Platform highlights (v2)

- **New "Arr-style" interface** — a collapsible sidebar with built-in search and per-section accent colors, a redesigned dashboard with quick-action tiles, and a **first-run onboarding wizard**. Every page is deep-linkable, so the URL always reflects where you are (refresh-safe, Back/Forward works).
- **Community Prerolls** — search and **Browse** the Typical Nerds community library by category, platform, creator, and upload date, with **pagination**, and download prerolls in one click (optionally straight into a category).
- **Cookie-free YouTube downloads** — NeX-Up uses a built-in **PO-token provider** to clear YouTube's "not a bot" wall, downloads trailers in a **Plex-friendly H.264** format, and keeps each trailer until its movie has actually released.
- **Factory Reset** — return NeXroll to a fresh-install state from the UI; pick exactly what to wipe.
- **Stronger security** — "Require Login" now protects the **entire API**, not just the web UI.
- **One-click plugin install** — download the Jellyfin plugin package straight from the Connect page, and set its playback options (Max Intros, movies/episodes) from NeXroll.
- **Quality-of-life** — automatic **log redaction** (API keys and IPs scrubbed on export), a **Storage Usage** view, real **Backup/Restore progress**, and reliable thumbnails.

> **Upgrading from v1.x is safe** — your data carries over and the first-run wizard is skipped automatically.

## Key Features

### Modern Interface (v2)
- **Collapsible Arr-style sidebar** with built-in search across every page and setting
- **Per-section accent colors** so you always know where you are
- **First-run onboarding wizard** that walks new installs through setup
- **Redesigned dashboard** with quick-action tiles and a weekly calendar preview
- **Deep-linkable URLs** for every page — refresh-safe, Back/Forward works

### Community Prerolls
- **Search** the Typical Nerds community preroll library (fast local index)
- **Browse** by category, platform, creator, and upload date
- **Pagination** to page through the full library, not just the first results
- **One-click download** with optional rename and add-to-category
- Fair Use Policy acceptance to protect the community source

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
- **Cookie-free YouTube downloads**: A built-in PO-token provider clears YouTube's "not a bot" wall (cookie files still supported as a fallback)
- **Plex-friendly format**: Trailers download as H.264 so they play as prerolls instead of silently failing on AV1
- **Release-date options**: Choose digital / physical / theatrical (or Digital Only), with retention measured from the release date so trailers aren't removed before the movie is out
- **Coming Soon List Generator**: Dynamic video prerolls with grid or list layouts, color customization, and poster artwork
- **Dynamic Preroll Generator**: Create custom "Coming Soon to [Your Server]" intro videos
- **Sequence Builder Presets**: Quick templates for theater-style experiences
- **Auto-Cleanup**: Automatically removes trailers once content has released and landed in your library

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
- **Jellyfin**: Preroll injection via NeXroll Intros plugin — download the plugin straight from the Connect page, auto-detect it, and push its config (URL, API key, path mapping, Max Intros, movies/episodes) remotely
- **Emby**: Preroll injection via NeXroll Intros plugin with Cinema Mode integration
- **No shared mount required**: the plugin streams and caches prerolls from NeXroll, so it works even when the media server can't see the files directly
- Secure credential storage with encryption

### System & Administration
- **Enhanced Logging**: View, search, filter, and export logs in the web UI — with **automatic redaction** of API keys and IP addresses on export/copy
- **Factory Reset**: Return NeXroll to a fresh-install state from the UI, choosing exactly what to wipe
- **Storage Usage**: See how much space prerolls, trailers, and thumbnails are using
- **Update Notifications**: Configurable update checking with changelog display
- **System & Files Backup**: Complete backup including database, prerolls, and thumbnails — with live progress on backup and restore
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
- [Connect (Plex, Jellyfin, Emby)](https://github.com/JFLXCLOUD/NeXroll/wiki/Connect)
- [Dashboard](https://github.com/JFLXCLOUD/NeXroll/wiki/Dashboard)
- [Preroll Library](https://github.com/JFLXCLOUD/NeXroll/wiki/Preroll-Library)
- [Scheduling Guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Scheduling)
- [NeX-Up (Trailers)](https://github.com/JFLXCLOUD/NeXroll/wiki/NeX-Up)
- [Community Prerolls](https://github.com/JFLXCLOUD/NeXroll/wiki/Community-Prerolls)
- [Sequences](https://github.com/JFLXCLOUD/NeXroll/wiki/Sequences)
- [Path Mappings](https://github.com/JFLXCLOUD/NeXroll/wiki/Path-Mappings)
- [Backup and Restore](https://github.com/JFLXCLOUD/NeXroll/wiki/Backup-and-Restore)
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
