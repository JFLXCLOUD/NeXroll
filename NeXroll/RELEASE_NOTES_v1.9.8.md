# NeXroll v1.9.8 Release Notes

**Release Date:** January 8, 2026

##  What's New

### Daily Calendar View
A brand new view mode for your schedule calendar that shows an **hourly breakdown** of any day:
-  Hour-by-hour timeline (12 AM - 11 PM) showing which categories are scheduled
-  Visual conflict resolution: see which schedules win each hour
-  Exclusive schedule indicators with time ranges
-  Blend mode visualization when multiple schedules mix
-  Night hours (10 PM - 6 AM) subtly highlighted
-  Current hour indicator when viewing today
-  Click any day in Month view to jump to its hourly breakdown

Perfect for fine-tuning complex schedules and understanding exactly what plays when!

### Clear When Inactive Setting
New option to ensure **no prerolls play outside your scheduled times**:
- When enabled, NeXroll clears the Plex preroll field when no schedule is active
- Solves the issue where prerolls kept playing outside scheduled windows
- Find it in: **Settings → NeXroll Settings → Clear Prerolls When Inactive**
- Different from Coexistence Mode: this actively clears prerolls vs. leaving Plex alone

### Coexistence Mode
Run NeXroll alongside other preroll managers:
- NeXroll only manages prerolls during active schedules
- Outside scheduled times, NeXroll stays hands-off
- Allows other preroll managers (like Preroll Plus) to work when NeXroll isn't active
- Find it in: **Settings → NeXroll Settings → Coexistence Mode**

### Reddit Community
- Added r/NeXroll subreddit link to footer and README
- Join the community for support, feature requests, and discussions!

## Bug Fixes

### Critical Timezone Drift Bug
Fixed a **major bug** affecting users in GMT-7/8 timezones:
- Schedules would shift backward by 7-8 hours on each save
- **Root cause:** Timezone conversion was being applied incorrectly
- **Solution:** Schedules now stored as naive local datetimes with no timezone conversion
- What you enter is exactly what gets saved and displayed
- Scheduler uses local time for all comparisons
- **Impact:** Schedules now reliably save and execute at the times you specify

### Random Order Default Bug
Fixed new schedules defaulting to Sequential playback:
- "Random" option now correctly defaults to enabled when creating a schedule
- Visual selection now matches the actual backend default

## Changes

### Time Display Format
- Dashboard "Upcoming Schedules" now shows times without seconds
- Example: "1/1/2026, 7:00 AM" instead of "1/1/2026, 7:00:00 AM"
- Cleaner, easier to read

### Community Prerolls URL Update
- Updated community library from `prerolls.typicalnerds.uk` to `prerolls.uk`
- Same great content, shorter URL!

---

## Installation

Download `NeXroll_Installer.exe` from the releases page and run it.

**For existing users:** The installer will upgrade your current installation while preserving your database and settings.

## Support

- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions:** r/NeXroll on Reddit
- **Discord:** [Join the community](https://discord.gg/your-invite)

---

##  Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

##  Thank You

Thanks to all community members who reported bugs, suggested features, and helped test this release!
