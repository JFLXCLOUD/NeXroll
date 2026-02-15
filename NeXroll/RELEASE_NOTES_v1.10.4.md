# NeXroll v1.10.4 Release Notes

**Release Date:** January 18, 2026

## 🎬 What's New: NeX-Up

This release introduces **NeX-Up**, a comprehensive Radarr integration that brings the authentic movie theater "Coming Soon" experience to your Plex server!

### Radarr Integration
Connect NeXroll to your Radarr instance and let it automatically:
- Discover upcoming movies in your collection
- Download trailers from YouTube
- Remove trailers when movies are released to your library

### Dynamic Preroll Generator
Create stunning "Coming Soon" intro videos with:
- **5 Templates:** Cinematic, Neon, Minimal, Retro, Elegant
- **20+ Color Themes:** From Midnight to Sunset to Ocean
- **Customizable Duration:** 3-15 seconds
- **Server Branding:** Shows "Coming Soon to [Your Server Name]"

*Requires FFmpeg to be installed*

### Automatic Trailer Management
- Configurable quality (720p, 1080p, 4K)
- Smart storage limits (max trailers, max GB)
- Automatic cleanup of expired trailers
- Manual trailer addition via YouTube URL or TMDB ID

### Sequence Builder Presets
One-click presets to get started:
- **🎬 Coming Soon + Trailers** - Your intro followed by random trailers
- **🎞️ Trailers Only** - Just the trailers
- **🎭 Feature Presentation** - Classic theater style with intro + single trailer

### Settings & Configuration
- Storage path for trailers
- Days ahead to look (7-365)
- Max trailers to keep (1-50)
- Max storage space (1-50 GB)
- Trailers per playback (1-5)
- Playback order (release date, random, download date)
- Auto-refresh interval (1-168 hours)

---

## 🚀 Getting Started with NeX-Up

1. Navigate to the new **NeX-Up** tab
2. Enter your Radarr URL and API key
3. Click **Connect to Radarr**
4. Set your storage path for trailers
5. Configure your preferences
6. Click **Sync Now** to download trailers
7. (Optional) Generate a Dynamic Preroll intro
8. Use the **Sequence Builder** to create a preroll sequence
9. Schedule your NeX-Up sequence like any other preroll!

---

## Installation

Download `NeXroll_Installer_v1.10.4.exe` from the releases page and run it.

**For existing users:** The installer will upgrade your current installation while preserving your database and settings.

## Requirements

- **Radarr** (v3 or v4) for automatic trailer discovery
- **FFmpeg** (optional) for dynamic preroll generation
- **yt-dlp** (bundled) for YouTube trailer downloads

## Support

- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions:** r/NeXroll on Reddit
- **Discord:** [Join the community](https://discord.gg/your-invite)

---

## 📋 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

## 🙏 Thank You

Thanks to all community members who requested this feature! The "Coming Soon" experience has been one of the most requested additions, and we're excited to finally deliver it.

