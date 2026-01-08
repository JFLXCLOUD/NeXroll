# Home

![NeXroll Logo](https://github.com/JFLXCLOUD/NeXroll/raw/main/NeXroll/frontend/NeXroll_Logo_WHT.png?raw=true)

**NeXroll** is a modern preroll management system for Plex and Jellyfin with a beautiful web UI, powerful scheduling, and seamless media server integration.

**Web UI**: http://localhost:9393

## 🚀 What's New in v1.9.6

- **Timezone Fix**: Schedules now correctly use local time instead of UTC
- **Calendar Improvements**: Better display of exclusive vs. blend schedules with proper conflict detection
- **Holiday Browser**: Browse and download community prerolls directly from the app
- **ARM64 Support**: Docker images now support Raspberry Pi, Apple Silicon, and ARM servers
- **Security Updates**: Updated all Python dependencies to latest secure versions

## ✨ Key Features

### Preroll Management
- Upload multiple preroll videos with metadata and tags
- Automatic thumbnail generation (FFmpeg)
- Bulk operations and multi-select workflow
- Map existing preroll folders without moving files

### Smart Scheduling
- **Date Ranges**: Set start/end dates for seasonal prerolls
- **Time Restrictions**: Limit schedules to specific hours (e.g., 10pm-3am for mature content)
- **Exclusive Mode**: One schedule takes over completely
- **Blend Mode**: Multiple schedules combine their prerolls
- **Win/Lose Logic**: Control which schedule wins during overlaps
- **Fallback Category**: Default prerolls when no schedule is active

### Calendar Visualization
- **Year View**: See your entire preroll schedule at a glance
- **Month/Week Views**: Detailed daily breakdowns
- **Conflict Detection**: Visual indicators for overlapping schedules
- **Today Indicator**: Always know what's currently active

### Holiday Presets
- 32 built-in holiday presets (Halloween, Christmas, Valentine's Day, etc.)
- One-click initialization creates categories and date ranges
- Holiday Browser to download community prerolls

### Media Server Integration
- **Plex**: Direct API integration with path translation support
- **Jellyfin**: Category-based preroll management (requires Local Intros plugin)
- Secure credential storage with encryption

### Deployment Options
- **Windows Installer**: One-click setup with optional Windows Service and System Tray
- **Docker**: Official images for AMD64 and ARM64
- **Unraid**: Community Applications template available

## 📦 Installation

### Windows
Download the latest installer from [Releases](https://github.com/JFLXCLOUD/NeXroll/releases)

### Docker
```bash
docker pull jbrns/nexroll:latest
```

### Unraid
Search for "NeXroll" in Community Applications

## 📚 Quick Links

- [Installation Guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Installation)
- [Getting Started](https://github.com/JFLXCLOUD/NeXroll/wiki/Getting-Started)
- [Docker Setup](https://github.com/JFLXCLOUD/NeXroll/wiki/Docker)
- [Configuration](https://github.com/JFLXCLOUD/NeXroll/wiki/Configuration)
- [Scheduling Guide](https://github.com/JFLXCLOUD/NeXroll/wiki/Scheduling)
- [Path Mappings](https://github.com/JFLXCLOUD/NeXroll/wiki/Path-Mappings)
- [API Documentation](https://github.com/JFLXCLOUD/NeXroll/wiki/API-Documentation)
- [Troubleshooting](https://github.com/JFLXCLOUD/NeXroll/wiki/Troubleshooting)

## 💖 Support

If NeXroll is helpful, consider supporting ongoing development:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/j_b__)

## 📄 License

MIT License. See [LICENSE](https://github.com/JFLXCLOUD/NeXroll/blob/main/LICENSE) for details.
