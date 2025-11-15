# NeXroll v1.7.15 Release Notes

**Release Date:** November 14, 2025

## 🎨 New Feature: Custom Schedule Colors

We're excited to introduce the ability to customize individual schedule colors on your calendar! This highly-requested feature gives you complete control over your schedule visualization.

### What's New

#### Custom Color Picker
- Set unique hex colors for each schedule to make them stand out
- Beautiful color picker interface with visual selector
- Direct hex code input for precise color matching
- Quick "Clear" button to reset to category default
- Optional feature - leave blank to use category colors

#### Enhanced Calendar Views
All calendar views have been updated to support custom colors:

- **Week Timeline View** - Schedule bars display custom colors
- **Month Timeline View** - Continuous schedule bars with custom colors
- **Month Grid View** - Event boxes show custom colors (now the default view!)
- **Year Overview** - Monthly cards show schedules with custom colors

#### Smart Legend System
- Legends now show individual schedules instead of categories
- Each schedule displays with its custom color
- Easy identification of which schedules are active
- Consistent across all calendar views

### Visual Improvements

#### Grid View Default
The monthly calendar now defaults to the grid view (calendar-style) instead of the timeline view. You can still switch between views using the "Display" dropdown.

#### Fallback Schedule Colors
Even fallback schedules respect custom colors, showing dashed borders in your chosen color for consistency.

## Technical Details

### Database Migration
- Automatic migration adds `color` column to existing schedules
- No manual intervention required
- Existing schedules continue using category colors
- Fully backward compatible

### API Updates
- `POST /schedules` - Now accepts optional `color` field (hex format)
- `PUT /schedules/{id}` - Update schedule colors
- `GET /schedules` - Returns color field for all schedules

## How to Use

### Setting a Custom Color

1. **Create New Schedule:**
   - Fill in your schedule details
   - Scroll to "Calendar Color (Optional)" section
   - Click the color picker or enter a hex code
   - Click "Create Schedule"

2. **Edit Existing Schedule:**
   - Click "Edit" on any schedule
   - Find the "Calendar Color (Optional)" section
   - Choose your color
   - Click "Update Schedule"

3. **Clear Custom Color:**
   - Open schedule for editing
   - Click the "Clear Color" button
   - Schedule will revert to using category color

### Tips & Tricks

- **Seasonal Themes:** Use festive colors like light blue for winter holidays or orange for fall events
- **Priority Visual:** Assign bright colors to high-priority schedules
- **Category Organization:** Keep related schedules in similar color families
- **Test & Preview:** Colors update instantly in all calendar views

## Upgrade Instructions

### Windows Installer
1. Download `NeXroll_Installer_v1.7.15.exe`
2. Run the installer (will automatically upgrade your existing installation)
3. Your schedules and settings are preserved
4. Custom color feature is immediately available

### Docker
```bash
docker pull ghcr.io/jflxcloud/nexroll:v1.7.15
docker-compose up -d
```

## Compatibility

- ✅ Windows 10/11
- ✅ Docker (Linux/Windows containers)
- ✅ Plex Media Server
- ✅ Jellyfin Media Server
- ✅ Existing v1.7.x installations (automatic upgrade)

## Bug Fixes & Improvements

- Fixed calendar rendering for schedules with custom properties
- Improved legend performance with multiple schedules
- Enhanced color contrast for better visibility
- Optimized yearly overview card loading

## Known Issues

None reported for this release.

## Feedback & Support

We'd love to hear about your experience with custom schedule colors! Report issues or share feedback on GitHub:
- **Issues:** https://github.com/JFLXCLOUD/NeXroll/issues
- **Discussions:** https://github.com/JFLXCLOUD/NeXroll/discussions

## What's Next?

Future releases may include:
- Color templates and presets
- Dark mode optimized colors
- Bulk color assignment
- Color-based filtering

---

**Full Changelog:** See [CHANGELOG.md](CHANGELOG.md) for complete version history

**Installation Guide:** See [README.md](README.md) for setup instructions
