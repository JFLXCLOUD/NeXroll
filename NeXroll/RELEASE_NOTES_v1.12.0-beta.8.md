# NeXroll v1.12.0-beta.8 Release Notes

**Release Date:** April 3, 2026  
**Type:** Pre-release (Beta)

Dedicated Conflict Resolution page, calendar conflict UX improvements, update checker fixes, and several playback/preview bug fixes.

---

## New Features

### Conflict Resolution Page
- New **Conflicts** tab in the Schedules sub-navigation bar for a dedicated conflict resolution experience
- Replaces the popup wizard modal with a full page view showing richer conflict details
- **Timeframe selector** with Weekly (7 days), Monthly (30 days), and Yearly (365 days) lookahead periods
- Each conflict card shows a side-by-side schedule comparison grid with category, priority, mode, type, and color-coded schedule dots
- Overlapping day counts are displayed per conflict within the selected timeframe
- **Suggested fixes** with radio buttons per conflict, plus Skip and Ignore options
- **Auto-Resolve All** button selects the recommended fix for every conflict in one click
- **Apply Fixes** button processes selected resolutions with success/failure results view
- **Ignored Conflicts** collapsible section with Restore buttons
- Green **"All Conflicts Resolved"** state with Shield icon when no conflicts remain in the selected timeframe

### Calendar Conflict Panel Improvements
- All calendar views (Day, Week, Month, Year) now show a green **"All Conflicts Resolved"** message with a CheckCircle icon when actionable conflicts reach zero, replacing the old "Resolve 0 Conflicts" button
- Conflict description text in all calendar views now includes a clickable **"Conflicts"** link that navigates directly to the Conflicts page
- Resolve buttons in all calendar views and the dashboard now navigate to the dedicated Conflicts page instead of opening the popup wizard

---

## Bug Fixes

- **Preview Playback Skipping** — Sequence preview (builder, editor, schedule editor) and dashboard "Currently Showing" preview would show ~1 second of a video then skip to the next. Root cause: React was destroying and recreating the `<video>` DOM element on every track change via `key`, causing browsers to fire spurious `onEnded` events during the unmount/remount transition. Both players now reuse a single stable video element, swapping the source via `useEffect` + `.load()` + `.play()` for smooth gapless transitions. Broken videos (404s) are automatically skipped.

- **Preview "Unavailable" for Semicolon-Delimited Prerolls** — Dashboard preview showed "Preview unavailable for this file" with the entire raw Plex preroll string when any filename contained a comma. The parser checked for `,` before `;`, so a comma in a filename caused the semicolon-delimited string to be split on commas instead, producing garbage entries. Fixed by checking `;` first — semicolons never appear in file paths.

- **Preview Unavailable for Unmanaged Prerolls** — Files on external/mapped drives that weren't in the NeXroll database showed "Preview unavailable" because no `preview_url` was generated. Added a `/preview/file` endpoint that serves video files by absolute path, with a fallback in the preroll details endpoint that checks if the file is accessible locally.

- **Plex Disconnect Deletes Stable Token** — Disconnecting from Plex called `secure_store.delete_plex_token()`, permanently destroying the stable token from Windows Credential Manager. Users couldn't reconnect without re-entering their token. Disconnect now only clears the DB connection state (`plex_url`, `plex_token`), preserving the stable token for one-click reconnection.

- **Update Checker Not Detecting New Versions** — Five bugs in the update check system prevented the prerelease channel from detecting newer versions:
  1. `normalizeVersionString` stripped pre-release suffixes (e.g. `1.12.0-beta.8` became `1.12.0`), making all betas appear equal
  2. Auto-check used wrong response fields from the backend
  3. Check Interval dropdown sent `interval` instead of `check_interval`
  4. Manual check button read `systemVersion?.version` which doesn't exist on the response object
  5. Second manual check button read stale React state after the async call
  - Backend now uses proper semver parsing with `_parse_semver()` and `_compare_versions()` that correctly handle pre-release ordering

---

## Docker

- **CVE Remediation** — Updated Dockerfile to upgrade pip before installing wheels, addressing CVE-2025-8869 and CVE-2026-1703. The existing `apt-get upgrade -y` step handles libpng1.6 CVEs (CVE-2026-33636, CVE-2026-33416) on rebuild.
