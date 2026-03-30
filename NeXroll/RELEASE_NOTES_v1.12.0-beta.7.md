# NeXroll v1.12.0-beta.7 Release Notes

## Jellyfin Plugin — Compatibility Fix for Jellyfin 10.11.x

### Critical Fix

- **Jellyfin Plugin rebuilt for Jellyfin 10.11.x** — The plugin DLL was compiled against Jellyfin 10.10 libraries (net8.0). Jellyfin 10.11 moved to net9.0 and relocated the `User` type to `Jellyfin.Database.Implementations.Entities`, causing a `ReflectionTypeLoadException` that completely prevented the plugin from loading. The plugin now targets net9.0 with Jellyfin 10.11.x SDK packages. **Requires Jellyfin 10.11+.**

### Improvements

- **Plugin configure errors now logged to app.log** — Previously, when the "Configure Plugin" push to Jellyfin/Emby failed, the error details were only written to the internal event database. They now also appear in app.log, making diagnostic exports much more useful for debugging plugin connectivity issues.

- **Better error messages for plugin configure failures** — 404 responses from Jellyfin (indicating the plugin isn't loaded) now show a specific message directing users to check Jellyfin Dashboard → Plugins and restart Jellyfin. Changed HTTP status from 500 to 502 (Bad Gateway) for upstream failures to distinguish NeXroll bugs from Jellyfin-side issues.

- **Custom preroll folder mismatch warning** — If a custom preroll folder is configured in the database but the folder doesn't exist on disk at startup (e.g., a network drive not yet mounted), NeXroll now prints a clear warning instead of silently falling back to the default folder. The diagnostic export also flags this mismatch.

### Known Issue

- **Jellyfin 10.10 users**: The updated plugin DLL requires Jellyfin 10.11+. If you're still on Jellyfin 10.10, the previous plugin DLL will continue working. A future release may include multi-version support.
