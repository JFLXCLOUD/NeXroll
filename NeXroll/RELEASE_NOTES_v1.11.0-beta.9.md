# NeXroll v1.11.0-beta.9 Release Notes

**Release Date:** March 4, 2026

## Changes in Beta.9

### Plex Connector — Critical Preroll Fix

**Removed Destructive Fallback Cascade**
- Fixed a critical bug where `set_preroll()` would **clear all prerolls** when the real value couldn't be set
- The retry block previously cycled through fallback values: `[full_path, filename, "", "0"]`
- The empty string `""` would succeed, pass verification, and report "SUCCESS" — while actually **wiping the user's preroll configuration**
- This meant the scheduler silently cleared prerolls every cycle (e.g., every 5 minutes) while reporting success
- **Fix:** Removed `""` and `"0"` from fallback values entirely. If the real value can't be set, the function now correctly returns `False`

**Preroll String Length Protection**
- Added detection and warnings when the combined preroll path string exceeds Plex's practical limits (~20KB)
- When the encoded URL exceeds 8,000 characters, Method A (query parameter PUT) is automatically skipped to avoid guaranteed 400 errors
- Clear failure messages now explain that too many preroll files or long paths are the cause, instead of silently failing
- Logs the character count and approximate file count at the start of each `set_preroll()` call

**Auto-Chunking for Large Preroll Libraries**
- When the full preroll string is too long for Plex to accept, NeXroll now automatically selects a **random subset** of paths that fits within Plex's limits (~7,500 chars)
- The full string is always tried first — chunking only activates as a fallback when the full value fails
- The chunked subset is **cached and reused for 8 hours** before a fresh random selection is made, reducing unnecessary Plex API churn
- The cache automatically invalidates if the underlying preroll list changes (e.g., files added/removed, category switched)
- Supports both semicolon (random mode) and comma (sequential mode) delimiters
- Example: 636 files at ~44KB → auto-chunks to ~100 random files at ~7KB → succeeds
- Log output clearly shows: "Auto-chunking: randomly selected 102 of 636 paths (7,498 chars)"

**Preference Name Filtering**
- `set_preroll()` no longer iterates through non-path preferences like `CinemaTrailersType`, `CinemaTrailersFromLibrary`, `CinemaTrailersFromTheater`, `CinemaTrailersFromBluRay`, and `CinemaTrailersIncludeEnglish`
- These are boolean/integer settings, not path settings — attempting to set a file path into them was incorrect and wasted API calls
- Only actual preroll path preference names are now tried: `CinemaTrailersPrerollID`, `cinemaTrailersPrerollID`, `CinemaTrailersPreroll`, `cinemaTrailersPreroll`, `PrerollID`, `prerollID`

**Missing TLS Verify Parameter**
- Added missing `verify=self._verify` to the CinemaTrailersPrerollID retry PUT request
- Previously this could cause SSL errors for users with self-signed certificates

### Scheduler

**NeX-Up Auto-Sync SessionLocal Fix**
- Fixed `local variable 'SessionLocal' referenced before assignment` error that occurred every scheduler cycle
- Caused by a redundant `from backend.database import SessionLocal` inside `_check_nexup_auto_sync()` which shadowed the module-level import
- Python treats any `from X import Y` inside a function as making `Y` a local variable for the entire function scope, even in unreached branches
- Removed the redundant import; the module-level import at line 18 now works correctly throughout

---

## Impact

These fixes are critical for users with large preroll libraries (100+ files). Prior to this fix:
- Every scheduler cycle would fail to set the full preroll string (too long for Plex API)
- The destructive fallback would then clear all prerolls by setting the value to `""`
- The scheduler would report "SUCCESS" — a complete false positive
- Result: prerolls wiped every 5 minutes, no prerolls ever play

After this fix:
- The full string is always tried first (no behavior change for small libraries)
- If it's too long, a random subset is auto-selected that fits within Plex's limits
- Each cycle rotates to a different random subset, maintaining variety across the full library
- Prerolls are never destructively cleared as a "fallback"
- Users are given clear log messages explaining what's happening
