# NeX-Up - Trailer Integration Guide

NeX-Up brings the authentic movie theater "Coming Soon" experience to your Plex server. Automatically download trailers for upcoming movies and TV shows from Radarr and Sonarr, generate custom intro videos, and build professional sequences that play before your content.

## Overview

NeX-Up combines four powerful features:

1. **Radarr & Sonarr Integration** - Automatically discovers and downloads trailers for upcoming releases
2. **Dynamic Preroll Generator** - Creates custom "Coming Soon to [Your Server]" intro videos
3. **Sequence Builder Presets** - Quick templates for assembling trailers and intros
4. **Smart Cleanup** - Automatically removes trailers when content is released

## Getting Started

### Step 1: Navigate to NeX-Up

Click **NeX-Up** in the main navigation menu. You'll see four tabs:
- **Connections** - Configure Radarr and Sonarr
- **Your Trailers** - Manage downloaded trailers
- **Settings** - YouTube cookies, storage, and TMDB
- **Generator** - Create dynamic intros and sequences

### Step 2: Connect Radarr

1. Go to the **Connections** tab
2. In the Radarr section, enter:
   - **Radarr URL**: Your Radarr server address (e.g., `http://localhost:7878` or `http://192.168.1.100:7878`)
   - **API Key**: Found in Radarr → Settings → General → API Key
3. Click **Connect**
4. If successful, you'll see a green checkmark

### Step 3: Connect Sonarr (Optional)

1. In the Sonarr section, enter:
   - **Sonarr URL**: Your Sonarr server address (e.g., `http://localhost:8989`)
   - **API Key**: Found in Sonarr → Settings → General → API Key
2. Click **Connect**

### Step 4: Configure Settings

Go to the **Settings** tab to configure:

| Setting | Description | Recommended |
|---------|-------------|-------------|
| **Storage Path** | Where trailers are saved | Default is fine |
| **Days Ahead** | How far in the future to look for releases | 30-90 days |
| **Max Trailers** | Maximum number of trailers to keep | 10-20 |
| **Quality** | Download quality (720p, 1080p, 4K) | 1080p |
| **Auto-Cleanup** | Remove trailers when content releases | Enabled |

## Downloading Trailers

### Sync Upcoming Releases

1. Go to the **Connections** tab
2. Click **Sync** next to Radarr or Sonarr
3. NeX-Up fetches upcoming releases within your configured timeframe

### View Upcoming Content

After syncing:
- **Upcoming Movies** - Shows movies scheduled for release with trailer availability
- **Upcoming TV** - Shows TV seasons with premiere dates

Each item shows:
- Title and release date
- Trailer availability (YouTube link found or not)
- Download status (pending, downloaded, or unavailable)

### Download Individual Trailers

1. Find the movie/show you want
2. Click the **Download** button
3. NeX-Up downloads the trailer from YouTube

### Bulk Download

1. Click **Download All Available**
2. NeX-Up downloads trailers for all upcoming content that has YouTube trailers available

## YouTube Cookie Setup (Recommended)

YouTube has aggressive bot detection. For reliable downloads, export cookies from your browser:

### Why Cookies?

- Bypasses age restrictions
- Avoids region locks
- Reduces rate limiting
- More reliable downloads

### How to Export Cookies

1. Install the "cookies.txt" browser extension:
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
   - [Chrome](https://chrome.google.com/webstore/detail/cookies-txt)
2. Open an **Incognito/Private** window
3. Go to YouTube and sign in
4. Click the extension icon → "Export cookies"
5. Save the `cookies.txt` file

### Upload to NeX-Up

1. Go to **NeX-Up → Settings**
2. Find "YouTube Cookies" section
3. Click **Upload Cookie File**
4. Select your `cookies.txt` file

### Tips for Avoiding Blocks

- **Refresh your VPN IP** if downloads fail repeatedly
- **Wait between downloads** - don't download 20 trailers at once
- **Use Incognito** when exporting cookies
- **Re-export cookies** if they expire (typically every few weeks)

## Dynamic Preroll Generator

Create custom "Coming Soon" intro videos that play before your trailers.

### Navigate to Generator

Go to **NeX-Up → Generator**

### Available Templates

| Template | Description |
|----------|-------------|
| **🎬 Coming Soon** | Cinematic intro with glow effects and dramatic animations |
| **🎭 Feature Presentation** | Classic theater-style with elegant text |
| **📽️ Now Showing** | Retro film-style with warm sepia tones |

### Color Themes

| Theme | Style |
|-------|-------|
| **Midnight** | Blue/purple cyberpunk feel |
| **Sunset** | Warm orange/red tones |
| **Forest** | Calming teal/green |
| **Royal** | Elegant gold/purple |
| **Monochrome** | Classic black and white |

### Generate an Intro

1. Select a **Template**
2. Choose a **Color Theme**
3. Enter your **Server Name** (e.g., "Smith Family Server")
4. Click **Generate**
5. Wait for FFmpeg to create the video (5-15 seconds)
6. **Preview** the result in your browser
7. Click **Save** to add it to your preroll library

### Requirements

- FFmpeg must be installed and in your PATH
- Windows: Install via `winget install ffmpeg` or download from ffmpeg.org
- Docker: FFmpeg is included in the container

## Building Sequences with Trailers

Sequences combine your dynamic intro, trailers, and other prerolls into a complete theater experience.

### Quick Sequence Presets

NeX-Up includes ready-made sequence templates:

| Preset | Content |
|--------|---------|
| **Coming Soon + Movie Trailers** | Your intro → 2-3 random movie trailers |
| **Coming Soon + TV Trailers** | Your intro → 2-3 random TV trailers |
| **Mixed: Movies + TV** | Your intro → 1 movie trailer → 1 TV trailer |
| **Theater Experience** | Your intro → 4 random trailers |

### Create a Sequence from Preset

1. Go to **NeX-Up → Generator**
2. Scroll to **Sequence Builder**
3. Select a preset
4. Click **Create Sequence**
5. The Sequence Builder opens with blocks pre-configured
6. Customize if needed
7. Save to your library

### Manual Sequence Building

For full control, use the Sequence Builder directly:

1. Go to **Schedules → Sequence Builder**
2. Click **Add Block**

#### Block Types

**Random Block**
- Pulls random prerolls from a category
- Perfect for: "Play 2 random movie trailers"
- Configure: Select category, set count

**Fixed Block**
- Specific prerolls in exact order
- Perfect for: "Always play my Coming Soon intro first"
- Configure: Select specific prerolls

### Example: Theater Experience Sequence

| Order | Type | Configuration |
|-------|------|---------------|
| 1 | Fixed | "Coming Soon to [Server Name]" dynamic intro |
| 2 | Random | 2 from "Movie Trailers" category |
| 3 | Random | 1 from "TV Trailers" category |

**Result**: Your custom intro plays, followed by 2 random movie trailers and 1 TV trailer.

### Save and Use

1. Enter a **Name**: "Theater Experience - Winter 2025"
2. Add a **Description**: "Coming soon intro + 3 trailers"
3. Click **Save**

Now use this sequence in any schedule!

## Using Sequences in Schedules

### Create a Schedule

1. Go to **Schedules → Schedules**
2. Click **Add Schedule**
3. Fill in:
   - **Name**: "Daily Theater Mode"
   - **Start/End Date**: Your desired date range
   - **Start/End Time**: When the sequence should be active (or leave blank for all day)
4. Enable **Use Sequence**
5. Select your saved sequence
6. Click **Save**

The schedule will automatically use your sequence during the configured time period.

### Schedule Examples

| Schedule Name | Use Case |
|---------------|----------|
| Coming Attractions - Weekends | Theater mode only on Sat/Sun |
| December Movie Magic | Holiday movie trailers in December |
| TV Premiere Season | September TV trailers during premiere season |

## Trailer Categories

NeX-Up automatically creates categories for your trailers:

| Category | Contents |
|----------|----------|
| **Movie Trailers** | All downloaded movie trailers from Radarr |
| **TV Trailers** | All downloaded TV trailers from Sonarr |

These categories are used by:
- Sequence Builder random blocks
- Dashboard statistics
- Storage management

## Managing Your Trailers

### View Downloaded Trailers

Go to **NeX-Up → Your Trailers**

You'll see:
- All downloaded movie trailers
- All downloaded TV trailers
- Storage usage per category
- Total storage used

### Delete Trailers

1. Find the trailer to remove
2. Click the **Delete** button
3. Confirm deletion

The trailer is removed from disk and the category.

### Automatic Cleanup

When enabled (Settings → Auto-Cleanup):
- NeX-Up checks your Radarr/Sonarr daily
- When a movie/show is added to your library, its trailer is automatically deleted
- Keeps your trailer collection fresh and relevant

## Dashboard Integration

### Quick Actions

On the Dashboard, the **Quick Actions** panel includes:
- **NeX-Up Sync** - One-click sync for both Radarr and Sonarr
- Shows real-time download progress
- No need to navigate to the NeX-Up page

### NeX-Up Tile

The Dashboard shows a NeX-Up summary:
- Number of movie trailers
- Number of TV trailers
- Connection status
- Quick link to full NeX-Up page

## Troubleshooting

### Trailers Not Downloading

1. **Check YouTube cookies** - Re-export if expired
2. **Verify VPN** - Try a different server/IP
3. **Wait between downloads** - YouTube rate limits
4. **Check the trailer URL** - Some trailers are region-locked

### No Upcoming Content Found

1. **Verify Radarr/Sonarr connection** - Re-enter URL and API key
2. **Check "Days Ahead" setting** - Increase if needed
3. **Ensure upcoming content exists** - Check Radarr/Sonarr directly

### Dynamic Preroll Generation Fails

1. **Verify FFmpeg is installed** - Run `ffmpeg -version` in terminal
2. **Check FFmpeg in PATH** - NeXroll must be able to find it
3. **Sufficient disk space** - Generation needs temporary space

### Sequence Not Playing in Plex

1. **Check the schedule** - Is it enabled and within date range?
2. **Verify path mappings** - Settings → Path Mappings
3. **Ensure files exist** - Trailers might have been cleaned up
4. **Restart Plex** - Plex caches preroll settings

## Best Practices

### Trailer Count
- **Recommended**: 2-3 trailers per sequence
- Too many trailers = long wait before your movie

### Quality Settings
- **1080p** is ideal for most setups
- **720p** if bandwidth is a concern
- **4K** only if your network supports it

### Storage Management
- Set reasonable **Max Trailers** limit (10-20)
- Enable **Auto-Cleanup** to remove released content
- Monitor storage in the NeX-Up dashboard

### Regular Maintenance
- **Sync weekly** to catch new upcoming releases
- **Check for failed downloads** and retry
- **Update cookies** if YouTube blocks downloads

### Sequence Design
- Keep total preroll time under 2 minutes
- Lead with your custom intro
- Mix movie and TV trailers for variety
- Create seasonal sequences (holiday, summer blockbusters, etc.)

## Complete Setup Walkthrough

Here's a step-by-step guide to get the full theater experience:

1. **Connect Radarr/Sonarr** (Connections tab)
2. **Upload YouTube cookies** (Settings tab)
3. **Sync upcoming releases** (Connections tab → Sync)
4. **Download trailers** (Your Trailers tab → Download All)
5. **Generate a Coming Soon intro** (Generator tab)
6. **Create a sequence** using a preset (Generator tab → Sequence Builder)
7. **Create a schedule** that uses your sequence (Schedules → Add Schedule)
8. **Enjoy!** Your Plex now has a real theater experience

---

*NeX-Up is designed to enhance your home theater experience. Trailers are downloaded from YouTube and are subject to YouTube's terms of service. Always ensure you have the right to download and use content in your jurisdiction.*
