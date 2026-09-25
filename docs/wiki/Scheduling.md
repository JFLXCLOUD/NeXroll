# Scheduling

NeXroll's scheduling system allows you to automatically change which prerolls play based on dates, times, and custom rules.

## Schedule Types

Choose the recurrence separately from whether a schedule is Exclusive or Blend:

| Type | When it runs |
|---|---|
| **Daily** | Each day within its saved first/last dates and optional daily hours |
| **Weekly** | Selected weekdays within its saved date limits and optional daily hours |
| **Monthly** | Selected months and days of the month, within saved date limits and optional daily hours |
| **Yearly** | A recurring month/day window each year, with optional daily hours |
| **Holiday** | A linked holiday occurrence, or the saved fixed dates of an older unlinked holiday schedule |

> **New in 2.2.0:** Next-run calculation, calendar intervals, and playback now use consistent timing rules. The following upgrade behavior includes these fixes.

### Yearly windows

Choose the first and last **month and day**, such as December 1 through December 25. A window can cross New Year, such as December 20 through January 5. The old stored year used to represent these dates does not expire the schedule. Optional daily hours restrict playback inside the seasonal window.

A February 29-only window runs in leap years. A wider season containing February 29 still runs on its valid dates in other years; the missing day does not disable the whole season. Review the next occurrence and calendar after saving. You do not need to delete and recreate an older Yearly schedule to repair its next-run date.

### Monthly and Holiday timing

Monthly keeps its actual first and last active dates. A day that does not exist in a month is skipped rather than moved to a different day. Older Monthly schedules that omitted month/day filters retain their meaning: an omitted filter means all months or all days, not an automatically selected single date.

Monthly and Holiday expose optional daily start/end hours and retain them through editing. Linked holidays keep their selected future first year as dates refresh; older fixed-date holidays remain editable.

## Exclusive and Blend behavior

### Exclusive Mode
When a schedule is **Exclusive**, it takes complete control — only prerolls from that schedule's category will play.

**Use cases:**
- Holiday-specific prerolls (only Christmas prerolls during December)
- Special events (movie premiere night)
- Time-restricted content (mature content after 10pm)

### Blend Mode
When a schedule is **Blend** (non-exclusive), its prerolls are combined with other active blend schedules.

**Use cases:**
- Seasonal additions (add fall-themed prerolls to your regular rotation)
- Category mixing (combine multiple holiday categories)

## Creating a Schedule

1. Go to **Schedules** tab
2. Click **Add Schedule**
3. Configure:
   - **Name**: Descriptive name (e.g., "Christmas 2025")
   - **Category**: Which preroll category to use
   - **Date Range**: Start and end dates
   - **Time Range** (optional): Restrict to specific hours
   - **Exclusive**: Toggle on/off
   - **Priority**: Set priority level (1-10)
   - **Use Sequence**: Optionally use a saved sequence instead of a category
   - **Enabled**: Toggle to activate/deactivate

### Using Sequences in Schedules

Instead of a simple category, you can use a saved sequence:

1. Toggle **Use Sequence** when creating/editing a schedule
2. Select a saved sequence from the dropdown
3. When active, the schedule resolves the sequence into preroll paths

This is great for theater-style experiences (e.g., Coming Soon intro → random trailers).

## Date & Time Ranges

### Date Range
- **Start Date**: When the schedule becomes active
- **End Date**: When the schedule stops (inclusive)
- Leave end date empty for ongoing schedules

### Time Range
- **Start Time**: Hour when schedule activates (24-hour format)
- **End Time**: Hour when schedule deactivates
- Supports overnight ranges (e.g., 10pm-3am = 22:00-03:00)
- **Timezone**: Uses the timezone saved in NeXroll Settings; check this even when Docker's `TZ` is configured

**Example: Adult Swim Style**
- Start Time: 22:00 (10pm)
- End Time: 03:00 (3am)
- This schedule is only active from 10pm to 3am

## Priority & Win/Lose Logic

When multiple exclusive schedules overlap, priority and **Win/Lose** determines which one takes control.

### How Priority Works
- Schedules have a priority level from 1 (lowest) to 10 (highest)
- Higher priority number schedules win when multiple schedules overlap
- Same-priority conflicts are shown with orange warning badges

### Win/Lose
- **Win**: This schedule takes priority over others
- **Lose**: This schedule yields to "Win" schedules
- **Neither**: Standard priority (first-come basis)

### Example Scenario
You have two schedules for December 25th:
1. "Christmas Day" (Win) — Christmas-specific prerolls
2. "Holiday Season" (Lose) — General winter prerolls

On December 25th, "Christmas Day" wins and its prerolls play exclusively.

## Fallback and Filler

### Per-Schedule Fallback Category

Each schedule can have a **Fallback Category** that activates when that specific schedule ends.

### Filler Category (Global)

The **Filler Category** fills gaps when **no schedules are active at all**:

1. Configure in **Settings → General → Filler Category**
2. Choose a filler type:
   - **Category** — Use any category as the gap filler
   - **Sequence** — Use a saved sequence
   - **Coming Soon List** — Use a generated Coming Soon List video
3. Toggle to enable/disable

**Priority Order:**
1. Active Schedule → per-schedule fallback → Filler Category → Unchanged

See [Configuration - Filler Category](Configuration#filler-category) for details.

## Schedule Conflict Detection

NeXroll automatically detects potential conflicts:

- **Orange badges** appear when exclusive schedules overlap at the same priority
- **Calendar indicators** show conflicts in Day, Week, and Month views
- **Lock icon** on higher-priority schedules, greyed-out on lower-priority ones

## Schedule Organization

Schedules are organized into three sections:
- **Currently Running** — Active right now
- **Enabled Schedules** — Ready but not currently running
- **Disabled Schedules** — Paused/inactive

## Calendar View

The Calendar provides a visual overview of your schedule:

### Color Coding
- **Teal**: Exclusive schedule active
- **Purple**: Blend mode (multiple schedules mixing)
- **Orange**: Conflict detected (overlapping exclusives)
- **Blue**: Today indicator
- **Filler**: Shows filler category events on days with no active schedules

### Views
- **Year**: Full year overview
- **Month**: Detailed monthly view
- **Week**: Day-by-day breakdown

### Weekly Calendar Preview

The Dashboard Overview includes a mini calendar showing this week's scheduled prerolls with a **View Full Calendar** button.

### Hovering/Clicking
- Hover over a day to see active schedules
- Click for detailed breakdown of what's playing

## Best Practices

### 1. Use Exclusive Sparingly
Only use Exclusive mode when you truly want one category to dominate. For most cases, Blend mode provides better variety.

### 2. Set Proper Date Ranges
Don't leave schedules active indefinitely. Set clear end dates, especially for holidays.

### 3. Test with Calendar
Before a schedule goes live, check the Calendar view to ensure it appears when expected.

### 4. Configure Timezone
Set the timezone in **NeXroll Settings**. Docker users can also set `TZ` for the container, but it does not replace checking NeXroll's saved timezone:
```yaml
environment:
  - TZ=America/New_York
```

### 5. Use Priority for Overlaps
When schedules must overlap (e.g., "Holiday Season" spans multiple specific holidays), use priority levels and Win/Lose to control behavior.

### 6. Use Filler for Gaps
Configure a Filler Category to ensure something always plays, even when no schedules are active.

## Scheduler Status

The Dashboard shows real-time scheduler status:
- **Active Schedules**: Currently running schedules
- **Next Change**: When the next schedule change occurs
- **Currently Showing**: What category is currently applied to Plex/Jellyfin

## Upgrading existing schedules to 2.2.0

Take a [backup](Backup-and-Restore#before-you-upgrade) before upgrading. Startup migration refreshes compatible recurrence representations and next-run metadata while retaining schedule identity, content, priority, enabled state, and history. It does not require recreating schedules. Imported/restored schedules also receive refreshed next-run dates.

First/last date limits and daily hours remain in force. Overnight occurrences belong to the day they start and appear across both calendar days. Next-run metadata is refreshed for paused and lower-priority schedules too; a computed next occurrence does not enable a paused schedule or make it win a conflict.

Malformed saved timing is retained for repair and reported instead of silently becoming an all-day schedule. You can pause it, correct the timing in the editor, then save and re-enable it. Review any repair warning and the calendar after upgrading.

Saved sequences keep their existing behavior unless you add the new [rating restrictions and availability conditions](Advanced-Sequences#trailers-available). When a new restricted sequence has no matches, NeXroll does not substitute unrelated category prerolls; explicitly configured other blocks and blend partners can still play.

## Troubleshooting

### Schedule Not Activating
1. Check **Enabled** is toggled on
2. Verify date range includes today
3. If using time range, check current time is within range
4. Verify timezone is set correctly

### Wrong Time Activation
- Check the timezone saved in **NeXroll Settings** on either platform
- Check Docker `TZ` or the Windows timezone separately if other timestamps also look wrong
- Check **Settings → Logs** for scheduler activity

### Overlapping Schedules Conflict
- Use priority levels and Win/Lose logic
- Consider converting one to Blend mode
- Check Calendar view for conflicts (orange indicators)

### Prerolls Not Updating in Plex
1. Check scheduler status on Dashboard
2. Verify path mappings are correct
3. Test with "Apply to Plex" button manually
4. Check Plex server is reachable
