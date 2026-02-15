# NeXroll v1.10.9 Release Notes

**Release Date:** February 3, 2026

## ⭐ Highlight: NeX-Up Dashboard Quick Sync

Sync your Radarr and Sonarr trailers directly from the Dashboard with a single click!

### One-Click Trailer Sync
The new **NeX-Up Sync** button in Dashboard Quick Actions makes keeping your trailers up-to-date effortless:
- **Combined Sync** - Syncs both Radarr and Sonarr in one operation
- **Real-time Progress** - Spinner animation shows sync in progress
- **Results Summary** - See downloaded/skipped counts when complete
- **Smart Detection** - Only shows if Radarr or Sonarr is connected

💡 *Perfect for daily maintenance without navigating to the NeX-Up page!*

---

## 🎬 New Features

### Video Scaling / Transcoding
Scale prerolls to lower resolutions directly from the web interface:
- Located in Edit Preroll modal under "Video Scaling" section
- Support for **1080p** (Full HD), **720p** (HD), and **480p** (SD)
- Shows current resolution and codec information
- High-quality FFmpeg settings (libx264, CRF 18, slow preset)
- Replaces original file to save disk space

💡 *720p is recommended for remote family streaming - plays smoothly without server transcoding*

### Dynamic Preroll Theme Files
Each template + color theme combination now creates its own unique video file:
- `coming_soon_midnight_preroll.mp4`, `coming_soon_forest_preroll.mp4`, etc.
- Eliminates browser caching issues when switching themes
- No more page refresh needed after regenerating with different theme

---

## 🔧 Improvements

### Dashboard Quick Actions
- **Fixed Spinner Animations** - All Quick Action buttons now properly show spinning progress indicators
- Sync Library, NeX-Up Sync, Check for Updates, Community Index all animate correctly

### Schedule Management
- **Load Saved Sequences on Create** - Dropdown now loads saved sequences immediately when creating a new schedule
- **Smart Sequence Name Handling** - Selecting a saved sequence greys out the name field (uses saved sequence name)
- **No More Duplicates** - Creating schedule from saved sequence no longer creates duplicate in library

### Edit Schedule Modal
- **Better Layout** - Modal width increased to 900px to fit all options
- **Responsive Buttons** - Action buttons wrap properly on smaller screens
- **Cleaner UI** - Hidden redundant Sequence Name section when editing existing schedules

---

## 🐛 Bug Fixes

- **Video Preview Caching** - Regenerated prerolls now play correctly without page refresh
- **Duplicate Sequence Prevention** - Fixed sequences being duplicated when creating schedules from saved sequences
- **CSS Animation Class** - Fixed spinner animation class from non-existent `animate-spin` to working `spin` class

---

## 📋 Quick Start: NeX-Up Sync

Already have NeX-Up configured? Just:
1. Go to **Dashboard**
2. Find the **NeX-Up Sync** card in Quick Actions
3. Click the button
4. Watch as both Radarr and Sonarr sync automatically!

---

## 🔗 Related Versions

- **v1.10.8** - yt-dlp bundled build support, Radarr brand colors, dynamic preroll fixes
- **v1.10.7** - NeX-Up auto-sync bug fixes, page redesign with sub-navigation
- **v1.10.4** - Initial NeX-Up release with Radarr integration
