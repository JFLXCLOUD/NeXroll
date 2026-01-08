# Scheduling

NeXroll's scheduling system allows you to automatically change which prerolls play based on dates, times, and custom rules.

## Schedule Types

### Exclusive Mode
When a schedule is **Exclusive**, it takes complete control - only prerolls from that schedule's category will play.

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
   - **Name**: Descriptive name (e.g., "Christmas 2024")
   - **Category**: Which preroll category to use
   - **Date Range**: Start and end dates
   - **Time Range** (optional): Restrict to specific hours
   - **Exclusive**: Toggle on/off
   - **Enabled**: Toggle to activate/deactivate

## Date & Time Ranges

### Date Range
- **Start Date**: When the schedule becomes active
- **End Date**: When the schedule stops (inclusive)
- Leave end date empty for ongoing schedules

### Time Range (v1.9.6+)
- **Start Time**: Hour when schedule activates (24-hour format)
- **End Time**: Hour when schedule deactivates
- Supports overnight ranges (e.g., 10pm-3am = 22:00-03:00)
- **Timezone**: Uses your server's local timezone (set via `TZ` environment variable)

**Example: Adult Swim Style**
- Start Time: 22:00 (10pm)
- End Time: 03:00 (3am)
- This schedule is only active from 10pm to 3am

## Win/Lose Logic

When multiple exclusive schedules overlap, **Win/Lose** determines which one takes priority.

### How it Works
- **Win**: This schedule takes priority over others
- **Lose**: This schedule yields to "Win" schedules
- **Neither**: Standard priority (first-come basis)

### Example Scenario
You have two schedules for December 25th:
1. "Christmas Day" (Win) - Christmas-specific prerolls
2. "Holiday Season" (Lose) - General winter prerolls

On December 25th, "Christmas Day" wins and its prerolls play exclusively.

## Fallback Category

When no schedules are active, the **Fallback Category** provides default prerolls.

**Configure in Settings:**
1. Go to **Settings**
2. Find **Fallback Category**
3. Select a category (e.g., "Default" or "General")

## Calendar View

The Calendar provides a visual overview of your schedule:

### Color Coding
- **Teal** (🟢): Exclusive schedule active
- **Purple** (🟣): Blend mode (multiple schedules mixing)
- **Orange** (🟠): Conflict detected (overlapping exclusives)
- **Blue** (🔵): Today indicator

### Views
- **Year**: Full year overview
- **Month**: Detailed monthly view
- **Week**: Day-by-day breakdown

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
**Critical for Docker users!** Set the `TZ` environment variable to your local timezone:
```yaml
environment:
  - TZ=America/New_York
```

### 5. Use Win/Lose for Overlaps
When schedules must overlap (e.g., "Holiday Season" spans multiple specific holidays), use Win/Lose to control priority.

## Scheduler Status

The Dashboard shows real-time scheduler status:
- **Active Schedules**: Currently running schedules
- **Next Change**: When the next schedule change occurs
- **Current Prerolls**: What's currently being sent to Plex/Jellyfin

## Troubleshooting

### Schedule Not Activating
1. Check **Enabled** is toggled on
2. Verify date range includes today
3. If using time range, check current time is within range
4. Verify timezone is set correctly (`TZ` environment variable)

### Wrong Time Activation
- **Docker users**: Set `TZ` environment variable
- **Windows users**: Check system timezone
- v1.9.6 fixed a UTC/local time bug - update if on older version

### Overlapping Schedules Conflict
- Use Win/Lose logic to set priorities
- Consider converting one to Blend mode
- Check Calendar view for conflicts (orange indicators)

### Prerolls Not Updating in Plex
1. Check scheduler status on Dashboard
2. Verify path mappings are correct
3. Test with "Apply to Plex" button manually
4. Check Plex server is reachable
