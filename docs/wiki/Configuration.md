# Configuration

This guide covers all configuration options in NeXroll.

## Accessing Settings

Go to the **Settings** tab in NeXroll to configure these options. Settings are organized into sub-tabs.

---

## General Settings

### Theme

Toggle between **Light Mode** and **Dark Mode** for the interface.

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

---

## Filler Category

The Filler Category provides a global fallback when **no schedules are active**.

### What It Does

- Fills gaps in your schedule automatically
- Different from per-schedule fallback (which only applies when that specific schedule ends)
- Applies globally when ALL schedules are inactive

### Configuration

1. Go to **Settings → General**
2. Find the **Filler Category** section
3. Toggle to enable/disable
4. Select your filler type:

| Filler Type | Description |
|-------------|-------------|
| **Category** | Use any category as the gap filler |
| **Sequence** | Use a saved sequence as the gap filler |
| **Coming Soon List** | Use a generated Coming Soon List video |

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

Go to **Settings → Logs** to:
- View logs in real-time
- Filter by level: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Filter by category: system, scheduler, api, user, plex, jellyfin, emby, nexup
- Search through log entries
- Export logs as JSON or CSV

### Log Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Log Level** | Minimum level to capture | INFO |
| **Retention Period** | Days to keep logs (1-365) | 30 |
| **Database Logging** | Log to database for UI viewing | Enabled |
| **Request Logging** | Log API requests with timing | Enabled |
| **Scheduler Logging** | Log scheduler activity | Enabled |
| **API Logging** | Log external API calls | Enabled |

---

## Plex Settings

### Genre-based Preroll Mapping

**Experimental Feature**: Automatically apply prerolls based on the genre of what you're watching.

#### Enable Genre Mapping

1. Toggle **Enable Genre-based Preroll Mapping**
2. Create mappings (e.g., Horror → Halloween category)
3. When you play a horror movie, Halloween prerolls apply

#### Genre Settings

| Setting | Description |
|---------|-------------|
| **Genre Auto-Apply** | Master toggle for the feature |
| **Allow genres to override schedules** | Genre prerolls play even if a schedule is active |
| **Genre Override TTL** | Seconds to wait before re-applying the same genre |

#### Creating Genre Mappings

1. Enter a **Plex Genre** (e.g., "Horror", "Comedy", "Christmas")
2. Select the **Target Category**
3. Click **Create Mapping**

#### Testing Genre Mappings

- Enter genres in the test field
- Click **Resolve** to see which category would match
- Click **Apply Now** to immediately apply the matched category

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

Categories are organized into three sections: Scheduled Categories, Categories with Prerolls, and Empty Categories.

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
| **Priority** | Higher priority wins during overlap (1-10) |
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
| `TZ` | Container timezone (Docker) | UTC |
| `PUID` | User ID for file permissions (Docker) | 99 |
| `PGID` | Group ID for file permissions (Docker) | 100 |

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

- **Docker**: View with `docker logs nexroll` or use the built-in **Log Viewer** in Settings → Logs
- **Windows**: Use the built-in **Log Viewer** in Settings → Logs, or check `C:\ProgramData\NeXroll\logs\`

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
