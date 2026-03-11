# Frequently Asked Questions

## General

### What is NeXroll?

NeXroll is a preroll manager for **Plex**, **Jellyfin**, and **Emby** that lets you organize, schedule, and automatically rotate preroll videos before your movies and shows.

### Is NeXroll free?

Yes, NeXroll is completely free and open source.

### Does NeXroll work with Jellyfin?

Yes! Jellyfin requires the **NeXroll Intros plugin** (included with NeXroll). See the [Jellyfin Setup](Jellyfin) guide for installation.

### Does NeXroll work with Emby?

Yes! Emby requires the **NeXroll Intros plugin** and **Cinema Mode** enabled (Emby Premiere subscription required). See the [Emby Setup](Emby) guide for installation.

---

## Setup & Installation

### What's the easiest way to install NeXroll?

Docker is recommended for most users:
```bash
docker run -d --name nexroll \
  -p 9393:9393 \
  -e TZ=America/New_York \
  -v ./nexroll-data:/data \
  -v /path/to/prerolls:/data/prerolls \
  jbrns/nexroll:latest
```

See the [Installation Guide](Installation) for all options.

### What port does NeXroll use?

Default port is **9393**. Access at `http://localhost:9393` or `http://your-server-ip:9393`.

### Where do I find my Plex token?

1. Open Plex Web and sign in
2. Play any media item
3. Click the "..." menu → "Get Info" → "View XML"
4. Look for `X-Plex-Token=` in the URL

Or use the [Plex Token Finder](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

### How do I get a Jellyfin API key?

1. Open Jellyfin Dashboard
2. Go to **API Keys**
3. Click the **+** button and name it "NeXroll"
4. Copy the generated key

### How do I get an Emby API key?

1. Open Emby Dashboard
2. Go to **Settings → API Keys**
3. Click **New API Key** and name it "NeXroll"
4. Copy the generated key

---

## Authentication

### Do I need to set up authentication?

No, authentication is optional. If you're running NeXroll on a private network, you can skip it. Enable it if NeXroll is accessible from the internet or you want user accounts.

### What's the difference between API keys and user accounts?

- **API Keys** are for programmatic/external access to the `/external/*` API endpoints
- **User Accounts** add a login page to the web interface with username/password

### I forgot my password. How do I reset it?

If you can't log in, you can reset authentication by deleting the auth-related tables from the database or using the admin account to reset passwords.

### What happens if my account gets locked?

After 5 failed login attempts, accounts are locked for 15 minutes. Wait and try again, or use another admin account to unlock.

---

## Prerolls

### What video formats are supported?

Supported formats: MP4, MKV, AVI, MOV, WMV, FLV, WebM, M4V, TS, MPG, MPEG. MP4 with H.264 is recommended for best compatibility.

### How long should prerolls be?

- **Recommended**: 10-30 seconds
- **Maximum practical**: 1-2 minutes total
- Too long = viewers get frustrated waiting for their movie

### Where should I store preroll files?

Store them where both NeXroll and your media server (Plex/Jellyfin/Emby) can access them:
- **Docker**: Mount a shared volume
- **Windows**: Use a shared folder or local path both can reach

### Can I use the same preroll in multiple categories?

Yes! Prerolls can be assigned to multiple categories.

### Can I import existing preroll folders?

Yes! Go to **Dashboard → Add Prerolls** and use the **Import Folder** feature to register existing files without moving them.

---

## Schedules

### How do schedules work?

Schedules automatically change your prerolls based on dates. For example:
- Christmas category active Dec 1-25
- Halloween category active Oct 1-31
- Default category via Filler for the rest of the year

### What's the difference between Exclusive and Blend?

| Mode | Behavior |
|------|----------|
| **Exclusive** | Only this schedule's prerolls play (overrides everything) |
| **Blend** | Combines prerolls with other active schedules |

### What's the difference between Fallback and Filler?

- **Fallback Category**: Per-schedule — activates when that specific schedule ends
- **Filler Category**: Global — activates when NO schedules are active at all

### Why isn't my schedule activating?

Check these common issues:
1. **Timezone**: Is your timezone set correctly in Settings?
2. **Date range**: Is today within the start/end dates?
3. **Enabled**: Is the schedule toggled on?
4. **Path mappings**: Can Plex access the preroll files?

### Can I have overlapping schedules?

Yes! Use **Priority** (1-10) to control which schedule wins, or enable **Blend** to combine them.

---

## Sequences

### What's a sequence?

A sequence is a custom preroll playlist built from blocks:
- **Random blocks**: Pick X random prerolls from a category
- **Fixed blocks**: Specific prerolls in a specific order

### How do I create a sequence?

1. Go to **Schedules → Sequence Builder**
2. Add blocks (random or fixed)
3. Arrange the order
4. Save with a name

See [Sequences](Sequences) for details.

### Can I share sequences with others?

Yes! Export sequences as `.nexseq` files and share them. Others can import and use them.

---

## NeX-Up

### What is NeX-Up?

NeX-Up is NeXroll's trailer integration feature. It connects to Radarr and Sonarr to discover upcoming movies/shows and automatically downloads their trailers from YouTube.

### Do I need Radarr/Sonarr to use NeX-Up?

Yes, at least one of them. NeX-Up fetches upcoming release information from these services.

### Why are my trailer downloads failing?

YouTube has aggressive bot detection. Try:
1. **Upload YouTube cookies** — Export from an incognito browser session
2. **Try a different VPN IP** — YouTube may have blocked your current IP
3. **Wait between downloads** — Don't bulk-download too many at once
4. See [NeX-Up Troubleshooting](NeX-Up#troubleshooting) for more details

### What is the Coming Soon List Generator?

It generates video prerolls that showcase your upcoming movies and TV shows with a visual poster grid or text list. It uses data from Radarr/Sonarr and generates the video using FFmpeg.

### How do I keep my Coming Soon List updated?

Enable **Auto-regeneration** in the Generator settings. When NeX-Up syncs with Radarr/Sonarr, the Coming Soon List automatically regenerates with updated content.

---

## Path Mappings

### What are path mappings?

Path mappings translate file paths between NeXroll and Plex when they see files at different locations.

**Example**: 
- NeXroll sees: `/data/prerolls/christmas.mp4`
- Plex sees: `/mnt/media/prerolls/christmas.mp4`
- Mapping: `/data/prerolls` → `/mnt/media/prerolls`

### When do I need path mappings?

You need them when:
- NeXroll runs in Docker and Plex runs on the host (or vice versa)
- NeXroll and Plex are on different machines
- Using NAS storage with different mount points

### How do I test path mappings?

1. Go to **Settings → Path Mappings**
2. Enter a local path in the test area
3. Click **Run Test**
4. Verify the translated path matches what Plex expects

See [Path Mappings](Path-Mappings) for detailed examples.

---

## Troubleshooting

### Prerolls aren't playing in Plex

1. **Check path mappings**: Most common issue — verify paths translate correctly
2. **Apply to Plex**: Did you click "Apply to Plex" after making changes?
3. **File access**: Can Plex access the preroll files?
4. **Plex settings**: Check Settings → Server → Extras in Plex

### Prerolls aren't playing in Jellyfin

1. **Plugin installed?**: Verify the NeXroll Intros plugin is in Dashboard → Plugins
2. **Plugin configured?**: Check that the NeXroll URL is set in the plugin settings
3. **Active prerolls?**: Ensure you have an active category, filler, or schedule
4. See [Jellyfin Setup — Troubleshooting](Jellyfin#troubleshooting) for more

### Prerolls aren't playing in Emby

1. **Cinema Mode enabled?**: Must be turned ON in Emby Settings → Cinema Mode
2. **"Include trailers from my movies in my library"**: This must be checked
3. **Refresh Custom Intros**: Run this task from Scheduled Tasks → Library
4. See [Emby Setup — Troubleshooting](Emby#troubleshooting) for more

### Prerolls play but wrong ones

1. Check which schedule is currently active
2. Verify the category has the prerolls you expect
3. Check if another schedule is overriding (Exclusive mode)

### Changes aren't taking effect

- **Plex**: Caches preroll settings — restart Plex or wait a few minutes. Click "Apply to Plex" to push changes immediately
- **Jellyfin/Emby**: The plugin fetches fresh preroll lists at each playback. For Emby, run "Refresh Custom Intros" after adding new prerolls

### NeXroll can't connect to Plex

1. Verify Plex URL is correct (include port, e.g., `http://192.168.1.100:32400`)
2. Check your Plex token is valid
3. Ensure network connectivity between NeXroll and Plex
4. If using HTTPS with self-signed cert, there may be SSL issues

### Docker container won't start

1. Check port 9393 isn't already in use
2. Verify volume mount paths exist
3. Check logs: `docker logs nexroll`

See [Troubleshooting](Troubleshooting) for more solutions.

---

## Features

### Does NeXroll support multiple Plex servers?

Currently, NeXroll connects to one server per media platform (one Plex, one Jellyfin, one Emby). You can have all three connected simultaneously.

### Can I use NeXroll with Plex, Jellyfin, and Emby simultaneously?

Yes! You can connect all three at once. Plex prerolls are applied directly via the API. Jellyfin and Emby prerolls are served through the NeXroll Intros plugin installed on each server.

### Is there a mobile app?

No dedicated app, but the web interface works on mobile browsers.

### Does NeXroll modify my media files?

No. NeXroll only tells Plex/Jellyfin/Emby which preroll files to play. It never modifies your movies or preroll videos (except when using the Video Scaling feature to transcode prerolls you specifically select).

### Can I access NeXroll programmatically?

Yes! NeXroll has a full REST API with optional API key authentication. Generate keys in Settings → API Keys and use the `/external/*` endpoints. See [API Documentation](API).

---

## Updates & Support

### How do I update NeXroll?

**Docker**:
```bash
docker pull jbrns/nexroll:latest
docker compose up -d --force-recreate
```

**Windows**: Download and run the latest installer.

NeXroll can also check for updates automatically — configure in Settings.

### Where can I get help?

- [GitHub Issues](https://github.com/JFLXCLOUD/NeXroll/issues) — Bug reports and feature requests
- [GitHub Discussions](https://github.com/JFLXCLOUD/NeXroll/discussions) — Questions and community help
- [Discord](https://discord.gg/nexroll) — Community chat

### How can I support NeXroll?

- Star the project on GitHub
- [Support on Ko-fi](https://ko-fi.com/j_b__)
- Report bugs and suggest features
- Help improve documentation
