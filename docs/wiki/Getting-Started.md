# Getting Started

Welcome to NeXroll! This guide walks you through setting up NeXroll for the first time.

## Step 1: Install NeXroll

If you haven't installed NeXroll yet, see the [Installation Guide](Installation).

Once installed, open NeXroll in your browser:
- **Local**: `http://localhost:9393`
- **Remote**: `http://your-server-ip:9393`

## Step 2: Set Up Authentication (Optional)

If you want to secure access to NeXroll:

1. Go to **Settings → Authentication**
2. Enable **Username/Password Authentication**
3. Create an **Admin** account
4. From now on, a login page will appear before accessing NeXroll

You can also generate **API Keys** for external integrations. See [Configuration - Authentication](Configuration#authentication) for details.

## Step 3: Connect to Your Media Server

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

## Step 4: Configure Path Mappings

If NeXroll and your media server see files at different paths (common with Docker), set up path mappings:

1. Go to **Settings → Path Mappings**
2. Add a mapping:
   - **NeXroll Path**: Where NeXroll sees prerolls (e.g., `/data/prerolls`)
   - **Plex Path**: Where Plex sees the same files (e.g., `/media/prerolls`)
3. Click **Save**

See [Path Mappings](Path-Mappings) for detailed examples.

## Step 5: Add Your Prerolls

### Upload Prerolls

1. Go to the **Dashboard → Add Prerolls** page
2. Click **Upload**
3. Select video files (MP4, MKV, etc.)
4. Optionally assign to a category
5. Click **Upload**

### Import an Existing Folder

If you already have a folder of preroll videos:

1. Go to **Dashboard → Add Prerolls**
2. Use the **Import Folder** section
3. Browse to or enter the path of your preroll folder
4. NeXroll will register the existing files without moving them

### Organize with Categories

Categories help organize prerolls by theme:

1. Go to **Dashboard → Categories**
2. Click **New Category**
3. Enter a name (e.g., "Christmas", "Halloween", "General")
4. Save the category
5. Assign prerolls to categories using the searchable thumbnail grid

## Step 6: Apply Prerolls

### Quick Apply (Manual)

Apply a category's prerolls to Plex immediately:

1. Go to **Dashboard → Categories**
2. Find your category
3. Click **Apply to Plex** (or Jellyfin)

Plex will now use those prerolls!

### Scheduled (Automatic)

Set up schedules to automatically change prerolls:

1. Go to **Schedules**
2. Click **New Schedule**
3. Configure:
   - **Name**: "Christmas 2025"
   - **Category**: Select the category
   - **Date Range**: Dec 1 - Dec 25
   - **Mode**: Exclusive or Blend
4. Save the schedule

NeXroll automatically applies the right prerolls based on your schedules.

## Step 7: Set Up NeX-Up (Optional)

NeX-Up brings a movie theater "Coming Soon" experience to your server:

1. Go to **NeX-Up → Connections**
2. Connect **Radarr** and/or **Sonarr** with their URL and API key
3. Click **Sync** to discover upcoming releases
4. Go to **NeX-Up → Settings** to upload YouTube cookies for reliable downloads
5. Download trailers for upcoming content
6. Use the **Generator** tab to create Coming Soon intro videos or Coming Soon Lists

See [NeX-Up Guide](NeX-Up) for the full setup.

## Step 8: Verify It Works

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
- **[NeX-Up](NeX-Up)** - Download trailers and create Coming Soon lists
- **[Sharing Sequences](Sharing-Patterns)** - Export and share your sequences
- **[Configuration](Configuration)** - All settings and options
- **[API Documentation](API)** - Programmatic access to NeXroll

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
- Use **Settings → System & Files Backup** for a complete backup
- Includes database, prerolls, and thumbnails
