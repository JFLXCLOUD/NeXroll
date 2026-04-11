# NeXroll v1.12.0-beta.9 Release Notes

**Release Date:** April 11, 2026  
**Type:** Pre-release (Beta)

Drag & drop file uploads and authentication UX improvements.

---

## New Features

### Drag & Drop Upload
- The **Add Prerolls** upload area now supports drag & drop for video files
- Drop zone highlights with an accent-colored border and tinted background when dragging files over it
- Only video files are accepted on drop (non-video files are silently ignored)
- Multiple drops are cumulative, appending to the current file selection
- Click-to-browse still works alongside drag & drop
- Updated instruction text: "Drag & drop video files here, or click to browse"

---

## Bug Fixes

- **"Require Login" Toggle Enabled Without Users** — The Require Login switch on the Settings page could be toggled on before any user accounts existed, locking the user out with a login screen that had no working "Create Account" button. The toggle is now disabled (greyed out at 40% opacity with `cursor: not-allowed`) when no users exist, with helper text: "Create a user account below before enabling login."

- **Toggle Stays Greyed After Creating User** — After creating the first user account (via either the registration form or the admin Create User modal), the Require Login toggle remained greyed out because `authStatus.users_exist` was not refreshed. Both `handleRegister` and `createUser` now call `checkAuthStatus()` on success, immediately re-enabling the toggle.

- **Undefined `logger` Crashes in Plugin Config Endpoints** — Four `logger.warning()` calls in the Jellyfin and Emby plugin configuration endpoints (`/jellyfin/configure-plugin`, `/emby/configure-plugin`) referenced an undefined `logger` variable that would have caused a `NameError` at runtime if those error paths were hit. Each was a duplicate of an adjacent `log_event()` call and has been removed.
