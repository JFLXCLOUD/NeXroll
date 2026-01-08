# Configuration

This guide covers all configuration options in NeXroll.

## Accessing Settings

Go to the **Settings** tab in NeXroll to configure these options.

---

## NeXroll Settings

### Theme

Toggle between **Light Mode** and **Dark Mode** for the interface.

### Timezone

Set your local timezone to ensure schedules activate at the correct times.

1. Select your timezone from the dropdown
2. The setting saves automatically

**Important**: Schedules use this timezone for start/end times. If prerolls aren't activating when expected, check this setting.

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

### Verbose Logging

Enable detailed debug logging for troubleshooting.

When enabled:
- Detailed scheduler activity is logged
- Check browser console (F12) for frontend logs
- Check application logs for backend activity

---

## Plex Settings

### Genre-based Preroll Mapping

**⚠️ Experimental Feature**: Automatically apply prerolls based on the genre of what you're watching.

#### Enable Genre Mapping

1. Toggle **Enable Genre-based Preroll Mapping**
2. Create mappings (e.g., Horror → Halloween category)
3. When you play a horror movie, Halloween prerolls apply

#### Genre Settings

| Setting | Description |
|---------|-------------|
| **Genre Auto-Apply** | Master toggle for the feature |
| **Allow genres to override schedules** | When checked, genre prerolls play even if a schedule is active |
| **Genre Override TTL** | Seconds to wait before re-applying the same genre (prevents spam) |

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

#### Adding Path Mappings

1. Click **Add Row**
2. Enter the **Local/UNC Prefix** (how NeXroll sees the path)
3. Enter the **Plex Prefix** (how Plex sees the same files)
4. Click **Save**

#### Testing Path Mappings

1. Enter local paths in the test area
2. Click **Run Test**
3. Verify the translated paths are correct for Plex

---

## Backup & Restore

### Database Backup

Export all schedules, categories, sequences, and preroll metadata to JSON.

1. Click **Download Database Backup**
2. Save the `.json` file

This includes:
- All categories and their settings
- All schedules and sequences
- Preroll metadata (not video files)
- Genre mappings
- Path mappings

### Files Backup

Export all preroll video files and thumbnails to ZIP.

1. Click **Download Files Backup**
2. Save the `.zip` file (may be large)

### Restore from Backup

1. Click **Choose File** under Restore
2. Select your backup file:
   - `.json` for database restore
   - `.zip` for files restore
3. Click **Restore**

**Warning**: Restoring overwrites existing data. Back up current data first.

---

## Category Settings

Each category has these settings (configured in the Categories tab):

| Setting | Description |
|---------|-------------|
| **Name** | Category display name |
| **Description** | Optional description |
| **Plex Mode** | How Plex plays multiple prerolls: **Random** (shuffled) or **Sequential** (in order) |

---

## Schedule Settings

Each schedule has these options (configured in the Schedules tab):

| Setting | Description |
|---------|-------------|
| **Name** | Schedule display name |
| **Category** | Which category's prerolls to use |
| **Start/End Date** | When the schedule is active |
| **Exclusive** | When active, only this schedule's prerolls play |
| **Blend** | Combine with other active schedules |
| **Priority** | Higher priority wins during overlap (1-10) |
| **Enabled** | Toggle schedule on/off |

### Schedule Modes Explained

| Mode | Behavior |
|------|----------|
| **Exclusive** | This schedule takes over completely - no other prerolls play |
| **Blend** | Prerolls from this schedule combine with other active schedules |

---

## Environment Variables

These can be set when running NeXroll (especially useful for Docker):

| Variable | Description | Default |
|----------|-------------|---------|
| `SCHEDULER_INTERVAL` | How often to check schedules (seconds) | 60 |
| `TZ` | Container timezone (Docker) | UTC |

### Docker Example

```yaml
environment:
  - TZ=America/New_York
  - SCHEDULER_INTERVAL=60
```

---

## Data Storage Locations

### Docker

When using the recommended volume mount:
```
/app/data/
├── nexroll.db      # SQLite database
├── prerolls/       # Uploaded preroll files
└── thumbnails/     # Generated thumbnails
```

### Windows

```
C:\ProgramData\NeXroll\
├── nexroll.db
├── prerolls\
└── thumbnails\
```

### Logs

- **Docker**: View with `docker logs nexroll`
- **Windows**: `C:\ProgramData\NeXroll\logs\`

---

## Tips

### Backup Before Major Changes

Always download a database backup before:
- Updating NeXroll
- Making bulk changes
- Restoring from another backup

### Test Path Mappings

Use the Test Translation feature to verify paths before applying to Plex. Incorrect path mappings are the most common cause of "prerolls not playing" issues.

### Check Timezone

If schedules aren't activating when expected, verify your timezone setting matches your actual location.
