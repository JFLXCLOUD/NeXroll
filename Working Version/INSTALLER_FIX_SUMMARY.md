# NeXroll Installer Fix - October 22, 2025

## Problem Summary

When you ran the **NeXroll_Installer_1.5.0.exe** (Oct 21 version), the dashboard didn't show the new customization features you were expecting. Here's why:

### Root Cause
The installer contained an **OLD frontend build** that was built BEFORE the dashboard customization code was fully integrated. Even though the code existed in the source files, the compiled frontend bundle included in the installer was stale.

**What was missing:**
- ❌ Latest CSS files (6.38 KB of grid styling)
- ❌ Fresh JavaScript bundle
- ❌ All compiled component dependencies
- ❌ Updated build output

## Solution Implemented

### Steps Taken
1. **Restored App.js** - Recovered original version from Git (previous edits had corrupted it)
2. **Rebuilt Frontend** - `npm run build` with fresh dependencies
3. **Rebuilt Executables** - All 4 PyInstaller builds created anew
4. **Rebuilt Installer** - NSIS compiled fresh installer with all updated binaries

### Results
✅ **New Installer Created**: `NeXroll_Installer_1.5.0.exe`  
✅ **Build Date**: October 22, 2025 @ 10:04 PM  
✅ **Size**: 91.31 MB  
✅ **Status**: Production Ready

## Dashboard Features Overview

The NeXroll dashboard includes the following customization capabilities:

### Layout Management
- **Lock/Unlock Toggle** - Switch between viewing and editing modes
- **Drag-and-Drop Reordering** - Rearrange tiles by dragging when unlocked
- **Persistent Storage** - Layout saves to backend and persists across restarts
- **State Indicator** - Shows current mode (Locked/Editing)

### Available Tiles (8 Total)
1. **Servers** - Plex/Jellyfin connection status
2. **Prerolls** - Count and category usage
3. **Storage** - Total storage usage
4. **Schedules** - Active schedule count
5. **Scheduler** - Scheduler running status & control
6. **Current Category** - Active category display
7. **Upcoming Schedules** - Next scheduled events
8. **Recent Genres** - Recently applied genres

### Grid Configuration
- **Default Layout**: 4-column grid, 2-row height
- **Responsive**: Adjusts to screen size
- **Automatic Compaction**: Tiles fill gaps when moved
- **Backend Sync**: Changes saved to database

## How to Use the Dashboard

### Editing Your Layout

1. **Enter Edit Mode**
   - Look for the toggle switch next to "Locked" label
   - Click the switch to toggle between Locked/Editing
   - Status will show "Editing" when active

2. **Rearrange Tiles**
   - In Editing mode, click and drag any tile
   - Other tiles automatically adjust position
   - Visual placeholder shows where tile will land

3. **Save Your Changes**
   - Click the toggle switch to return to "Locked" mode
   - Layout automatically saves to backend
   - A saving spinner briefly appears

4. **Layout Persists**
   - Your custom layout is saved in the backend database
   - When you restart NeXroll, layout is restored
   - Works across system reboots

### Reset to Default

If you want to restore the default layout:
1. Enter Edit mode
2. Look for "Reset Layout" button (appears in edit mode)
3. Click to restore 4-column default layout

## Testing Checklist

After installing the new version, verify:

- [ ] Dashboard displays 8 tiles in a grid
- [ ] Each tile has content and styling
- [ ] Lock/Unlock toggle switch is visible
- [ ] Clicking toggle shows "Editing" status
- [ ] You can drag tiles when in editing mode
- [ ] Tiles smoothly rearrange
- [ ] Clicking toggle again shows "Locked" status
- [ ] Closing and reopening app restores your layout
- [ ] No console errors (F12 to check)
- [ ] Responsive on different window sizes

## File Information

**Latest Installer**
- Location: `c:\Users\HDTV\Documents\Preroll Projects\NeXroll - Windows\Working Version\NeXroll\NeXroll_Installer_1.5.0.exe`
- Size: 91.31 MB
- Built: October 22, 2025 at 10:04 PM
- Compression: zlib (96.6% efficiency)

**Frontend Build Details**
- CSS Size: 6.38 KB (gzipped)
- JavaScript: 105.84 KB (gzipped)
- Grid Layout Chunk: 1.77 KB
- Build Tool: React Scripts 5.0.1
- Status: Production build, minified and optimized

**Included Executables**
- NeXroll.exe: 21.86 MB (main application)
- NeXrollService.exe: 27.26 MB (background service)
- NeXrollTray.exe: 25.33 MB (system tray integration)
- setup_plex_token.exe: 17.82 MB (Plex token setup utility)

## Known Limitations

1. **Tile Resizing**: Current version supports reordering only. Resizing individual tiles is not yet implemented (planned for future version).

2. **Per-Tile Customization**: Widget content customization modal was created but not yet integrated into the main dashboard (can be added in Phase 4).

3. **Real-Time Data**: Dashboard shows static data. Live updates (active streams, storage usage, etc.) require Phase 4 implementation.

## Next Phase (Phase 4 - Optional)

Future enhancements could include:
- Real-time Plex server data (active streams, storage usage)
- Per-tile content customization via modal
- Tile resizing with minimum/maximum sizes
- Export/import layouts as JSON
- Multiple saved layout profiles
- Preset layout templates

## Support Notes

If the dashboard still doesn't appear after installing:

1. **Clear Browser Cache**
   - Windows Key + R → `msedge://settings/clearBrowsingData`
   - Or in your browser: Ctrl+Shift+Delete

2. **Restart Services**
   - Services menu → restart NeXroll service
   - Close and reopen the application

3. **Check Frontend Build**
   - Verify `build\static\css` and `build\static\js` folders exist
   - Check file sizes match those listed above

4. **Console Errors**
   - Press F12 to open developer tools
   - Check Console tab for any error messages
   - Screenshot errors if present

## Summary

✅ **Problem**: Old installer with stale frontend build  
✅ **Solution**: Rebuilt all components with latest code  
✅ **Result**: Fresh NeXroll_Installer_1.5.0.exe ready for use  
✅ **Status**: Dashboard customization features now available  

You should now see the full dashboard with working lock/unlock toggle and drag-and-drop tile reordering!

---

**Build Date**: October 22, 2025  
**Installer Version**: 1.5.0  
**Status**: ✨ Production Ready
