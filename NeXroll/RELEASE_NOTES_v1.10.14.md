# NeXroll v1.10.14 Release Notes

**Release Date:** February 15, 2026

## Highlight: NeX-Up - Radarr and Sonarr Trailer Integration

The biggest feature in this release brings the movie theater "Coming Soon" experience to your Plex server. Automatically download and play trailers for upcoming movies and TV shows before your content.

---

## New Features

### NeX-Up - Trailer Integration
Connect to your Radarr and Sonarr instances to automatically download trailers for upcoming releases:

- **One-Click Integration** - Connect with URL and API key
- **Automatic Discovery** - Fetches movies/shows scheduled to release within your configured timeframe
- **YouTube Downloads** - Trailers downloaded automatically with quality selection (720p, 1080p, 4K)
- **Cookie Support** - Use exported cookies for age-restricted or region-locked content
- **Smart Cleanup** - Automatically removes trailers when content is added to your library
- **Storage Management** - Configure max trailers and storage allocation

### Dynamic Preroll Generator
Create custom "Coming Soon to [Your Server]" intro clips:
- Multiple templates: Cinematic, Neon, Minimal, Retro, Elegant
- 5 color themes: Midnight, Sunset, Forest, Royal, Monochrome
- Live preview in browser
- FFmpeg-powered high-quality generation

### Sequence Builder Presets
Pre-built sequences for NeX-Up trailers:
- Coming Soon + Movie Trailers
- Coming Soon + TV Trailers  
- Mixed: Movies + TV
- Theater Experience (4 trailers)

### Video Quality Dashboard
New dashboard tile showing resolution distribution of your preroll library with interactive filtering.

### Video Scaling Page
Batch scale prerolls to lower resolutions (1080p, 720p, 480p) for better remote streaming compatibility.

### Schedule Conflict Detection
Visual indicators when exclusive schedules overlap, with priority visualization.

### Custom Styled Confirmation Dialogs
All browser confirmation dialogs replaced with themed modal dialogs supporting warning, danger, info, success, and error styles.

---

## Improvements

- **System Backup** - Now includes database, all preroll videos, thumbnails, and settings
- **Add Prerolls to Category** - Searchable thumbnail grid with multi-select
- **Schedules Organization** - Three sections: Currently Running, Enabled, Disabled
- **Category Management** - Organized into Scheduled, With Prerolls, and Empty sections
- **Dashboard Icons** - All cards now display lucide icons
- **yt-dlp 2026.2.4** - Latest version with improved YouTube extraction

---

## Bug Fixes

- Fixed category grid dropdown appearing behind neighboring cards
- Fixed category preroll count showing 0 for non-primary assignments
- Fixed category dropdowns not sorting alphabetically
- Fixed folder picker not saving custom preroll location
- Fixed KeyError when YouTube download fails
- Fixed dynamic preroll theme not saving after generation

### Frontend Changes
- Redesigned `renderSettingsSystem()` with Lucide icons
- Added `systemDependencies` and `dependenciesLoading` state
- Updated `recheckFfmpeg` to async function with loading state
- Enhanced NeX-Up tab styling for Create Sequence button

---

## 🔄 Upgrade Notes

Run the new installer over your existing installation. All settings and data are preserved.

### What's Changed Since v1.9.8
- NeX-Up Radarr & Sonarr integration (v1.10.0+)
- Dynamic preroll generator with templates
- Video scaling/transcoding feature
- Dashboard quick actions with NeX-Up sync
- Schedule conflict detection
- Enhanced System Information page
