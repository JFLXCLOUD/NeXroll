# Getting Started

Welcome to NeXroll! This guide walks you through setting up NeXroll for the first time.

## Step 1: Install NeXroll

If you haven't installed NeXroll yet, see the [Installation Guide](Installation).

Once installed, open NeXroll in your browser:
- **Local**: `http://localhost:9393`
- **Remote**: `http://your-server-ip:9393`

## Step 2: Connect to Your Media Server

### Connecting to Plex

1. Go to the **Connect** tab
2. Enter your **Plex URL** (e.g., `http://192.168.1.100:32400`)
3. Enter your **Plex Token**
   - Find your token: Open Plex Web → View XML → Look for `X-Plex-Token` in the URL
   - Or use the [Plex Token Finder](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
4. Click **Test Connection**
5. If successful, click **Save**

### Connecting to Jellyfin

1. Go to the **Connect** tab
2. Enter your **Jellyfin URL** (e.g., `http://192.168.1.100:8096`)
3. Enter your **API Key**
   - In Jellyfin: Dashboard → API Keys → Create
4. Click **Test Connection**
5. If successful, click **Save**

**Note**: Jellyfin requires the [Local Intros plugin](https://github.com/dkanada/jellyfin-plugin-intros) for preroll support.

## Step 3: Configure Path Mappings

If NeXroll and your media server see files at different paths (common with Docker), set up path mappings:

1. Go to **Settings → Path Mappings**
2. Add a mapping:
   - **NeXroll Path**: Where NeXroll sees prerolls (e.g., `/prerolls`)
   - **Plex Path**: Where Plex sees the same files (e.g., `/media/prerolls`)
3. Click **Save**

See [Path Mappings](Path-Mappings) for detailed examples.

## Step 4: Add Your Prerolls

### Upload Prerolls

1. Go to the **Prerolls** tab
2. Click **Upload**
3. Select video files (MP4, MKV, etc.)
4. Optionally assign to a category
5. Click **Upload**

### Organize with Categories

Categories help organize prerolls by theme:

1. Go to the **Categories** tab
2. Click **New Category**
3. Enter a name (e.g., "Christmas", "Halloween", "General")
4. Save the category
5. Assign prerolls to categories

## Step 5: Apply Prerolls

### Quick Apply (Manual)

Apply a category's prerolls to Plex immediately:

1. Go to **Categories**
2. Find your category
3. Click **Apply to Plex** (or Jellyfin)

Plex will now use those prerolls!

### Scheduled (Automatic)

Set up schedules to automatically change prerolls:

1. Go to **Schedules**
2. Click **New Schedule**
3. Configure:
   - **Name**: "Christmas 2024"
   - **Category**: Select the category
   - **Date Range**: Dec 1 - Dec 25
   - **Mode**: Exclusive or Blend
4. Save the schedule

NeXroll automatically applies the right prerolls based on your schedules.

## Step 6: Verify It Works

1. Open Plex and play any movie
2. Your preroll should play before the movie starts

If it doesn't work:
- Check [Troubleshooting](Troubleshooting)
- Verify path mappings
- Ensure Plex can access the preroll files

## What's Next?

Now that you're set up, explore more features:

- **[Sequences](Sequences)** - Build custom preroll playlists with random selection
- **[Scheduling](Scheduling)** - Automate preroll changes for holidays and seasons
- **[Sharing Sequences](Sharing-Patterns)** - Export and share your sequences
- **[Configuration](Configuration)** - All settings and options

## Quick Tips

### Keep Prerolls Short
- 10-30 seconds is ideal
- Max 2-3 prerolls per viewing

### Use Descriptive Names
- Name prerolls clearly: `Christmas_Snow_2024.mp4`
- Makes organizing easier

### Test Before Holidays
- Set up schedules early
- Test that prerolls play correctly

### Back Up Your Config
- Export your sequences regularly
- Especially before major changes
