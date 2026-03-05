# NeXroll v1.11.9 Release Notes

**Release Date:** March 5, 2026

This is the first stable release of the v1.11.x line, consolidating all changes from beta.1 through beta.9.

---

## Highlights

- **Coming Soon List Generator** — Fully customizable video prerolls showcasing upcoming movies & TV shows
- **Dynamic Preroll Generator** — Custom logo overlay support for all template styles
- **Community Preroll Server** — Multi-server support with fair-use protections
- **Critical Plex Preroll Fixes** — Eliminated destructive fallback cascade, added auto-chunking for large libraries
- **NeX-Up Calendar View** — Monthly calendar showing upcoming releases
- **Configurable Preroll Storage** — Move your preroll folder to any local or network path

---

## Coming Soon List Generator

### Video Generation
- **Two Layout Styles**: Grid mode (poster artwork) and List mode (clean text-only)
- **Background Music**: Toggle ambient audio with smooth 1.5s fade-in/out, matched to video duration
- **Custom Audio Upload**: Replace the default track with your own .mp3, .wav, .aac, .m4a, .ogg, or .flac file
- **Custom Logo Overlay**: Add a watermark or replace the server name with your logo (.png, .jpg, .webp)
- **Logo Mode Toggle**: Choose between Watermark (faded, centered) or Replace Server Name (header area)
- **Color Customization**: Full control over background, text, and accent colors (expanded by default)
- **Configurable Duration**: Set video length from 5 to 20 seconds
- **Max Items**: Control how many titles are displayed (4–12 items)

### Available Now! Feature
- Movies and TV shows display an "Available Now!" badge when downloaded
- Configurable grace period (1–30 days) before removal from the list
- Max Items setting limits how many "Available Now!" items appear
- TV shows correctly use Sonarr's `hasFile` status (not trailer download status)

### Auto-Regeneration
- Automatically regenerate when NeX-Up syncs with Radarr/Sonarr
- Respects all settings: background music, custom audio, logo, colors, layout
- Uses fresh database sessions with proper async event loop management

### Options Panel
- Clean 2×2 grid layout: Background Music | Custom Logo | Available Now! | Auto-Regenerate
- Unified dark card style with consistent `#00d4ff` accent color

### Release Date Preference
- Options: Digital First, Digital Only, Physical First, Theatrical
- Controls ordering and display of Coming Soon items

### Exclusion Filtering
- Excluded items correctly filtered from generated videos, auto-regeneration, and previews

---

## Dynamic Preroll Generator

### Custom Logo Overlay
- Upload a custom logo image for all three template styles: Coming Soon, Feature Presentation, Now Showing
- Logo replaces server name text in live preview and generated video
- Recommends landscape-oriented logos (e.g., 800×200 px) with transparent PNG backgrounds

---

## NeX-Up Enhancements

### Calendar View
- New **Calendar** tab alongside Movies and TV Shows in Upcoming Items
- Full monthly grid (Sun–Sat) with color-coded items: blue (movies), teal (TV), green (Available Now!)
- Month navigation with "Today" button; today highlighted with purple border
- Up to 3 items per day with "+N more" overflow; hover tooltips for truncated titles

### Your Trailers Page
- **Play Button**: Preview trailers directly in the browser via video player modal
- **View Mode Toggle**: Switch between compact List view and Detailed poster grid
- Movie trailers use amber accent, TV trailers use cyan accent

### Sync & Scheduling
- **Sync Timestamp Fix**: Uses local time consistently (no more future-time display)
- **Next Sync Display**: Radarr/Sonarr cards show "Last synced · Next sync" countdown
- **TMDB API Key Security**: Masked password-style input, click to reveal

### Connection Panel
- Upcoming movie and TV show counts load automatically when opening the NeX-Up tab

---

## Plex Connector — Critical Fixes

### Removed Destructive Fallback Cascade
- **Fixed**: `set_preroll()` previously cycled through fallback values including `""` which would **wipe all prerolls** while reporting "SUCCESS"
- **Result**: Every scheduler cycle silently cleared prerolls for large libraries
- **Fix**: Removed `""` and `"0"` from fallback values entirely

### Auto-Chunking for Large Libraries
- When the full preroll string exceeds Plex's limits (~7,500 chars), NeXroll automatically selects a random subset that fits
- Full string is always tried first; chunking only activates as a fallback
- **8-hour rotation cache**: Chunked subset is reused for 8 hours before a fresh random selection
- Cache auto-invalidates when the preroll list changes
- Example: 636 files at ~44KB → auto-chunks to ~100 random files at ~7KB

### Preroll String Length Protection
- Warnings when combined path string exceeds Plex's practical limits
- Method A auto-skipped when URL exceeds 8,000 characters
- Clear failure messages instead of silent errors

### Preroll Path URL Encoding
- Fixed `#` characters in filenames (e.g., `Twister on VHS TV Spot #2 HD.mp4`) causing silent path truncation
- All Plex API endpoints now properly URL-encode preroll paths

### Preference Name Filtering
- Only actual preroll path preference names are tried (no more setting file paths into boolean/integer preferences)

### Missing TLS Verify Parameter
- Added missing `verify=self._verify` to retry PUT request for self-signed certificate users

---

## Community Prerolls

### Community Server Selector
- Choose which Community Preroll Server to connect to
- Fetches available servers from central `servers.json` endpoint
- Enter a custom server URL; persists across sessions
- Default server: `prerolls.uk`

### Server Load Protections
- Index building requires Fair Use Policy acceptance with global lock
- Downloads rate-limited to one every 10 seconds per IP
- Server list cached for 10 minutes; featured prerolls cached for 30 minutes
- Random preroll scrape includes 200ms delays with early bailout at 50 files

### Custom User-Agent Header
- All outbound requests include `NeXRoll/{version}` User-Agent header
- Uses shared `COMMUNITY_USER_AGENT` constant for consistency

---

## Configurable Preroll Storage Folder

- **New Storage Tab** in Settings to view and change your preroll storage path
- Move prerolls to any local or network path (e.g., `\\server\share\Prerolls`)
- Transfer existing files to the new location with one click
- Reset to default installation path
- All operations logged to the Logs page

---

## Scheduler Fixes

### SessionLocal Scoping
- Fixed `local variable 'SessionLocal' referenced before assignment` error caused by redundant import shadowing the module-level import

### PyInstaller Module Re-execution
- Fixed `from backend.main import` in scheduler.py triggering full module re-execution in frozen builds
- This spawned a second server instance that crashed on port 9393 already-in-use
- Now uses `sys.modules` to safely resolve cross-module symbols without re-importing

---

## UI / Theming

### Header Icon Theming
- All 26+ page header icons follow the active theme (white in dark mode, black in light mode)
- Applied via `.header-icon` CSS class

### Generator Page Consistency
- Unified visual styles between Dynamic Preroll and Coming Soon List generator pages
- Consistent Lucide icons, input/select styling, button styles, and option card layouts

### Emoji-to-Icon Cleanup
- All emoji characters in the Coming Soon List Generator replaced with Lucide React icons

---

## Bug Fixes

- **FFmpeg Detection**: Fixed unterminated docstring in `dynamic_preroll.py` that caused PyInstaller to silently skip the module
- **Coming Soon List Grace Period**: Items past the configured grace period now properly excluded from generated videos
- **Server URL**: Fixed community servers endpoint pointing to `test.prerolls.uk` instead of `prerolls.uk`
- **Server Name Input Width**: Adjusted from 100% to 80% for better layout

---

## Previous Release

See [RELEASE_NOTES_v1.10.14.md](RELEASE_NOTES_v1.10.14.md) for v1.10.14 changes.

See [CHANGELOG.md](CHANGELOG.md) for the full feature history.
