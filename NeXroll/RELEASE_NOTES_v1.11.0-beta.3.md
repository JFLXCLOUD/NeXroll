# NeXroll v1.11.0-beta.3 Release Notes

**Release Date:** February 21, 2026

## Changes in Beta.3

### Your Trailers Page Improvements

**Play Button and Video Preview**
- Added Play button to each trailer on the Your Trailers page (both Movie and TV trailers)
- Play button opens a video player modal to preview trailers directly in the browser
- Video player modal displays trailer title, release date, and content type

**View Mode Toggle**
- Added view mode toggle (List / Detailed) for the Your Trailers page
- List View: Compact table layout with title, release date, status, and action buttons
- Detailed View: Poster grid layout showing movie/show posters with overlay information
- Movie trailers use amber accent color, TV trailers use cyan accent color

### Coming Soon Lists

**Last Updated Timestamp**
- Generated Coming Soon List videos now display when they were last updated
- Shows file size and update timestamp (e.g., "coming_soon_grid.mp4 - 2.5 MB - Updated 2/21/2026, 3:45:00 PM")

### NeX-Up Connection Panel

**Upcoming Count Fix**
- Upcoming movie and TV show counts now load automatically when opening the NeX-Up tab
- Previously, the count only displayed after clicking the Upcoming button

### Backend

**New API Endpoint**
- Added `/nexup/trailer/video/{trailer_type}/{trailer_id}` endpoint for streaming trailer video files
- Supports both movie and TV trailers via `trailer_type` parameter (movie/tv)

---

## Full Changelog Since v1.10.x

See [CHANGELOG.md](CHANGELOG.md) for complete v1.11.0 feature list including:
- Coming Soon List Generator
- Authentication System (API Keys and User Accounts)
- Enhanced Update System
- Enhanced Logging System
- Holiday API Browser
- And more...
