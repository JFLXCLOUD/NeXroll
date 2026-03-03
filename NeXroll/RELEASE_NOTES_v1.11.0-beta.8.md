# NeXroll v1.11.0-beta.8 Release Notes

**Release Date:** March 3, 2026

## Changes in Beta.8

### Community Prerolls

**Custom User-Agent Header**
- All outbound HTTP requests to the community preroll server now include a `NeXRoll/{version}` User-Agent header
- Uses a shared `COMMUNITY_USER_AGENT` constant and `_community_headers()` helper for consistency across all 10 request locations

**Server URL Fix**
- Fixed the community servers endpoint URL — was incorrectly pointing to `test.prerolls.uk` instead of `prerolls.uk`

**Server Load Protections**
- Index building now requires Fair Use Policy acceptance and uses a global lock (only one build at a time)
- Downloads are rate-limited to one every 10 seconds per IP and require Fair Use acceptance
- Server list (`servers.json`) responses are cached for 10 minutes
- Top 5 featured prerolls are cached for 30 minutes
- Random preroll fallback scrape now includes 200ms delays between requests and early bailout at 50 files
- Removed unused debug/test-scrape endpoint

### NeX-Up — Upcoming Items

**Calendar View**
- Added a new **Calendar** tab to the Upcoming Items page alongside Movies and TV Shows
- Full monthly grid layout (Sun–Sat) showing all upcoming movies and TV shows on their release dates
- Color-coded items: blue for movies (🎬), teal for TV shows (📺), green for "Available Now!"
- Navigate between months with left/right arrows and jump back with the "Today" button
- Today's date is highlighted with a purple border
- Shows up to 3 items per day with a "+N more" overflow indicator
- Hover tooltips display the full title for truncated items

### NeX-Up — Sync & Scheduling

**Sync Timestamp Fix**
- Fixed "Last synced" displaying a future time — the scheduler was storing UTC timestamps but the frontend displayed them as local time
- Both manual and auto-sync now consistently use local time (`datetime.now()`) for sync timestamps

**Next Sync Display**
- The Radarr and Sonarr connection cards now show when the next auto-sync will occur
- Displays as "Last synced: [date] · Next sync: [date]" based on `last_sync + auto_refresh_hours`
- Only shown when auto-sync is enabled and a previous sync exists

**Auto-Regen Fix**
- Fixed Coming Soon List videos not updating after auto-sync
- Root cause: stale database session after sequential Radarr/Sonarr sync calls consumed the session across event-loop boundaries
- Auto-regen now uses a fresh `SessionLocal()` database session and explicit `asyncio.new_event_loop()` with proper cleanup
- Added full traceback logging on regeneration errors

### NeX-Up — Availability Fixes

**TV Show "Available Now!" Fix**
- Fixed TV shows incorrectly showing as "Available Now!" when only their trailer had been downloaded
- The check now correctly uses only Sonarr's `hasFile` status (whether the actual episode exists in your library)

**Coming Soon List Grace Period Fix**
- Fixed movies/shows appearing as "Available Now!" in generated Coming Soon List videos long after they should have been removed
- Both manual generation and auto-regeneration now respect the user's "Available Now!" grace period setting
- Items past the configured grace period (default: 1 day) are now properly excluded from the generated video

### Plex Connector

**Preroll Path URL Encoding Fix**
- Fixed a critical bug where `#` characters in preroll filenames (e.g., `Twister on VHS TV Spot #2 HD.mp4`) caused the path to be silently truncated when sent to the Plex API
- The `#` was interpreted as a URL fragment delimiter, cutting off everything after it — resulting in prerolls failing to apply with no visible error
- All Plex API endpoints that set `CinemaTrailersPrerollID` now properly URL-encode the preroll path using `urllib.parse.quote()`
- Path separators (`:/\;, `) are preserved as safe characters; only problematic characters (`#`, `&`, `?`, etc.) are encoded
- This fix resolves the issue reported by users with large preroll libraries containing special characters in filenames

### UI

**Server Name Input Width**
- Adjusted the Coming Soon List Generator "Server Name" input field width from 100% to 80%

---

## Previous Releases

See [RELEASE_NOTES_v1.11.0-beta.7.md](RELEASE_NOTES_v1.11.0-beta.7.md) for Beta.5–Beta.7 changes.

See [CHANGELOG.md](CHANGELOG.md) for the complete v1.11.0 feature list.
