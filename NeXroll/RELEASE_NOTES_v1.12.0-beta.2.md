# NeXroll v1.12.0-beta.2 Release Notes

**Release Date:** March 21, 2026  
**Type:** Pre-release (Beta)

Conflict Detection Wizard, yearly/holiday schedule improvements, dashboard tile overhaul, preview playback intelligence, and critical scheduler bug fixes.

---

## New Features

### Conflict Detection Wizard
- New **Conflict Detection Wizard** analyzes all active schedules for overlapping conflicts over the next 30 days
- Detects true conflicts only: same-priority exclusive schedules that overlap on the same day/time
- Intelligently skips non-conflicts: different-priority schedules (higher priority wins), non-exclusive schedules, and blend-enabled schedules
- Each conflict card displays:
  - **Severity badge** (High / Medium / Low / Info) with schedule comparison details
  - Side-by-side schedule info: name, category, priority, exclusivity, and type
  - Overlapping days count and conflict description
  - **Suggested fixes** with radio buttons — change priority, adjust time ranges, disable one schedule, or skip
- **Auto-Resolve All** button selects the recommended fix for every detected conflict in one click
- Apply button processes all selected fixes asynchronously with progress feedback
- Results view shows success/failure summary with per-conflict resolution status
- Accessible from the **Schedules** dashboard tile via the "Resolve Conflicts" button when conflicts are detected

### Dashboard — Scheduler Countdown Timer
- The **Scheduler** dashboard tile now displays a live countdown to the next schedule activation
- Shows **"Next Up: Schedule Name"** with the schedule name in blue, followed by a ticking D/H/M/S countdown
- Properly computes the next activation time for all schedule types: daily (with time ranges), weekly (with weekDay constraints), monthly (with monthDay constraints), and yearly/holiday schedules
- Skips currently active schedules — only counts down to the *next* change, not what's already showing
- Days segment auto-hides when zero (only shows H/M/S)
- Counter digits use theme-aware colors (white in dark mode, black in light mode)

### Dashboard — Schedules Tile Overhaul
- Replaced the simple "X of Y active" display with three detailed status rows:
  - **✓ Enabled** — green checkmark with count of active schedules
  - **⊘ Disabled** — grey icon with count of inactive schedules
  - **⚠ Conflicts** — orange warning with count of conflicting schedules (turns grey when 0)
- When conflicts are detected, a **"Resolve Conflicts"** button with wand icon appears to launch the Conflict Detection Wizard
- Uses `getScheduleConflicts()` logic to detect real conflicts (same-priority exclusive overlaps)

### Yearly & Holiday Schedule Improvements
- **Yearly** is now a fully supported schedule type alongside Daily, Weekly, Monthly, and Holiday
- Yearly and holiday schedules are year-agnostic — they recur across all years by comparing month+day windows
- Conflict detection for yearly schedules compares month+day overlap (ignoring year) for accurate multi-year conflict analysis
- **Holiday Auto-Update** — yearly and holiday schedules can optionally specify a holiday name and country code to automatically update their dates each year via the Holiday API
- Holiday Browser integration allows creating schedules directly from a searchable list of holidays by country and year

### Preview Playback Mode Intelligence
- The **Preview** button on the Currently Showing card now respects the playback mode of whatever is currently applied:
  - **Shuffle mode** — plays only 1 randomly selected video, shows "(Shuffle — 1 of N)" in the header
  - **Sequential/Playlist mode** — plays all prerolls in order with auto-advance and prev/next navigation
  - **Single/Coming Soon** — plays just the single video with no navigation controls
  - **Sequence** — plays all sequence items in order with full navigation
- Backend `/plex/current-preroll-details` endpoint now returns a `mode` field detected from:
  1. Filler state (coming_soon → single, sequence → sequential, category → uses category's plex_mode)
  2. Applied sequence override → sequential
  3. Active category's plex_mode setting
  4. Fallback: Plex delimiter inference (`;` = shuffle, `,` = sequential)

### Plugin Download Links
- Jellyfin and Emby connection pages now include direct download links for the NeXroll Intros plugin DLLs
- [NeXroll.Jellyfin.dll](https://github.com/JFLXCLOUD/NeXroll/raw/main/Plugins/NeXroll.Jellyfin.dll) — for Jellyfin servers
- [NeXroll.Emby.dll](https://github.com/JFLXCLOUD/NeXroll/raw/main/Plugins/NeXroll.Emby.dll) — for Emby servers

---

## UI Improvements

### Dashboard — Scheduler Tile Styling
- Start/Stop Scheduler button now matches the Preview button styling: indigo (#6366f1) background, compact padding, icons (Play for Start, Square for Stop)
- Both buttons use `justifyContent: 'center'` for properly centered text and icons

### Dashboard — Schedules Tile Text Size
- Increased font size and icon size in the Schedules tile for better readability and tile fill

---

## Bug Fixes

### Scheduler Override Blocking Active Schedules (Critical)
- **Fixed:** When a manual sequence was applied via the "Apply to Server" button, the 15-minute override would block ALL schedule evaluation — even schedules that should have been active
- The override check previously did an unconditional early `return`, preventing any schedule from being applied during the override window
- **Fix:** Active schedules now take priority over overrides. The override only blocks when no active schedules exist, and active schedules automatically clear stale overrides

### Preview Not Respecting Playback Mode
- **Fixed:** Preview button previously always showed all prerolls with full navigation regardless of the category's playback mode
- Shuffle categories would show all videos when they should only preview one random selection

---

## Backend Changes

- `GET /plex/current-preroll-details` — Now returns `mode` field (`"shuffle"`, `"sequential"`, or `"single"`) alongside prerolls and applied_sequence
- Mode detection logic inspects filler state, applied sequence, active category plex_mode, and Plex delimiter as fallback

---

## Upgrade Notes

- **No database migration required** — drop-in replacement from beta.1
- **Windows:** Run the installer or replace `NeXroll.exe`
- **Docker:** Pull the latest image

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete history.
