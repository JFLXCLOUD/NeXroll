# Configuration

This guide covers all configuration options in NeXroll.

## Accessing Settings

Go to the **Settings** tab in NeXroll to configure these options. Settings are organized into sub-tabs.

---

## General Settings

### Theme

Pick how NeXroll looks under **Settings > General > Theme**. The button in the top bar steps through the themes in order. The choice is saved in your browser.

| Theme | Look |
|-------|------|
| **Midnight** (dark, default) | Neutral graphite with violet accents |
| **Daylight** (light) | Cool paper white with indigo accents |
| **Cinema** (dark) | Warm black, velvet crimson and marquee gold |
| **Nocturne** (dark) | A moonlit night: a moon behind the page header, drifting cloud, frosted panels |
| **Parchment** (light) | Warm sepia paper, no pure white |
| **Terminal** (dark) | Green phosphor on black: monospace text, DOS prompts and scanlines |
| **Neon** (dark) | Synthwave violet-black, magenta and electric cyan |
| **Carbon** (dark) | True black for OLED screens, with an amber accent |
| **Silent Film** (dark) | Black and white: title cards, a strip of film and an iris between pages |
| **VHS Rewind** (dark) | A rental tape: a VCR's on-screen display, marker labels and rainbow stripes |
| **Screenplay** (light) | A shooting script: Courier on white, scene headings, and each section on its own colored revision page |

Terminal, Silent Film, VHS Rewind and Screenplay use their own fonts, which download the first time you pick the theme. With **reduce motion** turned on in your system settings, page-change effects such as the Silent Film iris are skipped.

### Timezone

Set your local timezone to ensure schedules activate at the correct times.

1. Select your timezone from the dropdown
2. The setting saves automatically

**Important**: Schedules use this timezone for start/end times. If prerolls aren't activating when expected, check this setting first.

### Confirmation Dialogs

Control whether NeXroll asks for confirmation before deleting items.

| Setting | Behavior |
|---------|----------|
| **Enabled** | Prompts before deleting schedules, categories, prerolls |
| **Disabled** | Deletes immediately without confirmation |

### Notifications

Control success and informational notifications.

| Setting | Behavior |
|---------|----------|
| **Enabled** | Shows all notifications (success, info, errors) |
| **Disabled** | Only shows critical error messages |

### Playback Guard (Plex)

Plex reads its preroll list as the prerolls play, so changing the list while someone is watching prerolls makes Plex hang on the next one. When a schedule change, rotation or fallback would change the list, NeXroll first checks what Plex is playing and holds the change while a movie that just started may still be in its prerolls.

- A movie or episode whose position has moved on is playing the movie itself, so it stops holding the change within about a minute. A movie that was already under way when the change came up doesn't wait out the whole window.
- Music and photos never hold a change.
- Between two prerolls or trailers Plex briefly reports nothing playing; NeXroll keeps holding through that gap (up to 90 seconds) so the next trailer is still there.
- **Settings → General → Playback Guard** sets the longest a change waits on one movie: 5 to 60 minutes, 20 by default. Keep it longer than your longest preroll and trailer run.
- **Off** applies changes right away, even mid-preroll.
- The dashboard's Currently showing card says when a change is waiting.

Jellyfin and Emby ask NeXroll for prerolls when playback starts, so the guard doesn't apply to them.

---

## Filler Category

The Filler Category provides a global fallback when **no schedules are active**.

### What It Does

- Fills gaps in your schedule automatically
- Different from per-schedule fallback (which only applies when that specific schedule ends)
- Applies globally when ALL schedules are inactive

### Configuration

1. Go to **Settings → General**
2. Find the **Fallback filler** section
3. Toggle to enable/disable
4. Select your filler type:

| Filler Type | Description |
|-------------|-------------|
| **Category** | Use any category as the gap filler |
| **Sequence** | Use a saved sequence as the gap filler |
| **Fixed Preroll** | Play one preroll from your library, picked by name (search box above the list). Deleting that preroll from the Library clears the choice, and the card asks you to pick another |
| **Coming Soon List** | Use a generated Coming Soon List video |
| **Dynamic Preroll** | Use one video made in the NeX-Up Generator |

Saving a change takes effect within seconds when filler is what should be playing. While a schedule, a schedule's fallback, a manual apply, Coexistence Mode or Clear Prerolls When Inactive has the field, saving only stores the choice; filler starts when that ends.

### Priority Order

1. **Active Schedule** — Highest priority, schedule's category is applied
2. **Per-Schedule Fallback** — If a schedule has a fallback, it's used when that schedule ends
3. **Filler Category** — Global fallback when NO schedules are active
4. **Unchanged** — If filler is disabled, Plex prerolls remain unchanged

---

## Authentication

NeXroll supports optional authentication to secure access to the web interface and API.

### API Keys

Generate API keys for external programmatic access:

1. Go to **Settings → API Keys**
2. Click **Generate New Key**
3. Configure:
   - **Name**: Descriptive label
   - **Permissions**: Read-only or Full Access
   - **Expiration**: 24h, 7d, 30d, 90d, 1 year, or Never
4. Copy the generated key (starts with `nx_`) — it's only shown once

API keys are used with the `/external/*` API endpoints. See [API Documentation](API) for details.

### Username/Password Authentication

Enable login-based access control:

1. Go to **Settings → Authentication**
2. Enable **Username/Password Authentication**
3. Create user accounts:
   - **Admin** — Full access to all settings and configuration
   - **User** — Standard access (view and manage prerolls)

### Security Features

| Feature | Description |
|---------|-------------|
| **Session Tokens** | Secure session management with expiration |
| **Password Hashing** | bcrypt-based password storage |
| **Remember Me** | Optional 30-day persistent login |
| **Account Lockout** | Locks account after 5 failed login attempts (15 min) |
| **Audit Log** | View authentication events in Settings |
| **HTTPS Support** | Configurable "Require HTTPS" setting |

---

## Update System

NeXroll can automatically check for new versions.

### Settings

| Setting | Description |
|---------|-------------|
| **Check Interval** | How often to check: startup, hourly, daily, weekly, or never |
| **Pre-release Channel** | Include beta/pre-release versions in update checks |

### Notifications

When an update is available:
- A notification card appears on the Dashboard
- Shows current version vs. available version
- Displays release notes with markdown rendering
- Can be dismissed (persists across sessions)

---

## Logging

NeXroll includes a built-in logging system for debugging and monitoring.

### Log Viewer

**Settings → Logs** has two views:

- **Events**: what NeXroll did and what went wrong. Prerolls applied or cleared, changes held back while something plays, settings changes, warnings and errors from every part of the app. Filter by level and area (System, Scheduler, API, User, Plex, Jellyfin, Emby, Plugin, NeX-Up), search messages, sources and request IDs, and click an entry for its details, including the error trace when there is one. Export the events that match as JSON or CSV.
- **App log**: `app.log` itself, newest first. Everything NeXroll writes, including scheduler detail and full error traces, which stay attached to their entry. Filter by level, search, and download `app.log` (or the previous file, `app.log.1`).

The cards at the top count stored events and the warnings and errors from the last 24 hours. **API keys, tokens and IP addresses are redacted** wherever logs are viewed, copied, exported or downloaded, so logs are safe to share. **Diagnostics bundle** downloads a ZIP of both logs and system details to attach to a bug report.

New in 2.2.3: scheduler and background warnings used to be in `app.log` only and now appear under Events too. The same message repeating (a check that fails every five minutes, say) is recorded once an hour with a count instead of hundreds of times.

### Log Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Minimum level** | Events below this level aren't recorded. Debug also records Verbose Logging's detail | Info |
| **Keep events for** | Days to keep events (7 days to 1 year). A shorter period applies straight away | 30 days |
| **Log API changes and failures** | Settings changes, uploads and deletes, failed requests and anything slower than 5 seconds. Page loads aren't recorded | On |
| **Log scheduler activity** | Prerolls applied or cleared, changes held while something plays, and scheduler warnings | On |
| **Verbose Logging** | Detailed debug lines in `app.log` | Off |

Before 2.2.3, request logging recorded every page load, which buried everything else. Those old entries are hidden unless you tick **Page loads**, and **Clear page loads** deletes them.

`app.log` rotates at 10 MB and keeps the previous file as `app.log.1`.

---

## Factory Reset

Return NeXroll to a fresh-install state from **Settings → System → Factory Reset**. You choose exactly what to wipe via checkboxes — settings, prerolls, schedules, NeX-Up trailers, the community index, the PO-token provider — so you can do a clean re-test without reinstalling. The action is confirmed before anything is removed and **cannot be undone**, so back up first if you might want the data back.

---

## Plex Settings

### Path Mappings

Configure path translation between NeXroll and Plex. Essential when they see files at different paths (common with Docker, NAS, or remote servers).

See [Path Mappings](Path-Mappings) for detailed configuration.

---

## Backup & Restore

### System & Files Backup

Creates a comprehensive backup including:
- SQLite database (`nexroll.db`) and JSON export for cross-version compatibility
- All preroll video files
- Generated thumbnails
- Application settings

Steps:
1. Click **Download System & Files Backup**
2. Save the `.zip` file (may be large depending on preroll count)
3. Uses streaming download to prevent memory issues with large backups

### Database Backup

Export schedules, categories, sequences, and preroll metadata to JSON:

1. Click **Download Database Backup**
2. Save the `.json` file

### Restore from Backup

1. Click **Choose File** under Restore
2. Select your backup file (`.json` for database, `.zip` for full backup)
3. Click **Restore**
4. Progress indicators show real-time status

**Warning**: Restoring overwrites existing data. Back up current data first.

---

## Category Settings

Each category has these settings (configured in the Categories page):

| Setting | Description |
|---------|-------------|
| **Name** | Category display name |
| **Description** | Optional description |
| **Plex Mode** | How Plex plays multiple prerolls: **Random** (shuffled) or **Sequential** (in order) |

The Categories page lists your categories, then the system categories NeX-Up manages, in a grid or a list. See [The Categories page](Preroll-Library#the-categories-page).

---

## Schedule Settings

Each schedule has these options (configured in the Schedules tab):

| Setting | Description |
|---------|-------------|
| **Name** | Schedule display name |
| **Category** | Which category's prerolls to use |
| **Start/End Date** | When the schedule is active |
| **Start/End Time** | Optional time restriction (24-hour format) |
| **Exclusive** | When active, only this schedule's prerolls play |
| **Blend** | Combine with other active schedules |
| **Priority** | 1-10; the higher priority number wins during overlap |
| **Use Sequence** | Use a saved sequence instead of a category |
| **Fallback Category** | Default prerolls when this schedule ends |
| **Enabled** | Toggle schedule on/off |

### Schedule Modes Explained

| Mode | Behavior |
|------|----------|
| **Exclusive** | This schedule takes over completely — no other prerolls play |
| **Blend** | Prerolls from this schedule combine with other active schedules |

---

## Environment Variables

These can be set when running NeXroll (especially useful for Docker):

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXROLL_PORT` | Web UI port | 9393 |
| `NEXROLL_DB_DIR` | Database and config directory | /data |
| `NEXROLL_PREROLL_PATH` | Preroll storage directory | /data/prerolls |
| `NEXROLL_SECRETS_DIR` | Secrets storage directory | /data |
| `SCHEDULER_INTERVAL` | How often to check schedules (seconds) | 60 |
| `NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES` | `1` turns the Plex playback guard off, whatever the setting says | unset |
| `TZ` | Container timezone (Docker) | UTC |
| `NEXROLL_RUN_AS_PUID` | `true` runs NeXroll as `PUID`:`PGID` instead of root (Docker; see [Running as a non-root user](Docker#running-as-a-non-root-user)) | false |
| `PUID` | User NeXroll runs as when `NEXROLL_RUN_AS_PUID` is true (Docker) | 99 |
| `PGID` | Group NeXroll runs as when `NEXROLL_RUN_AS_PUID` is true (Docker) | 100 |

### Docker Example

```yaml
environment:
  - TZ=America/New_York
  - NEXROLL_PORT=9393
  - NEXROLL_DB_DIR=/data
  - NEXROLL_PREROLL_PATH=/data/prerolls
  - NEXROLL_SECRETS_DIR=/data
  - SCHEDULER_INTERVAL=60
```

---

## Data Storage Locations

### Docker

When using the recommended volume mount (`/data`):
```
/data/
├── nexroll.db          # SQLite database
├── prerolls/           # Uploaded preroll files
├── thumbnails/         # Generated thumbnails
├── nexup_trailers/     # Downloaded NeX-Up trailers
│   ├── movies/
│   └── tv/
├── logs/               # app.log (2.2.3 and later)
└── secrets/            # Encrypted credentials
```

### Windows

```
C:\ProgramData\NeXroll\
├── nexroll.db
├── prerolls\
├── thumbnails\
├── nexup_trailers\
└── logs\
```

### Logs

- **Docker**: Use the built-in **Log Viewer** in Settings → Logs, or read `/data/logs/app.log`. `docker logs nexroll` shows the console output. Before 2.2.3, `app.log` was kept inside the container and lost on every update.
- **Windows**: Use the built-in **Log Viewer** in Settings → Logs, or check `C:\ProgramData\NeXroll\logs\`
- Set `NEXROLL_LOG_DIR` to keep `app.log` somewhere else.

---

## Tips

### Backup Before Major Changes

Always download a backup before:
- Updating NeXroll
- Making bulk changes
- Restoring from another backup

### Test Path Mappings

Use the Test Translation feature to verify paths before applying to Plex. Incorrect path mappings are the most common cause of "prerolls not playing" issues.

### Check Timezone

If schedules aren't activating when expected, verify your timezone setting matches your actual location. Docker users must set the `TZ` environment variable.

### Use the Log Viewer

When troubleshooting issues, check **Settings → Logs** for detailed error messages and request timings.
