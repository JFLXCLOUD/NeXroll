# Frequently Asked Questions

## General

### What is NeXroll?

NeXroll is a preroll manager for Plex and Jellyfin that lets you organize, schedule, and automatically rotate preroll videos before your movies and shows.

### Is NeXroll free?

Yes, NeXroll is completely free and open source.

### Does NeXroll work with Jellyfin?

Yes, but Jellyfin requires the [Local Intros plugin](https://github.com/dkanada/jellyfin-plugin-intros) to support prerolls.

---

## Setup & Installation

### What's the easiest way to install NeXroll?

Docker is recommended for most users:
```bash
docker run -d --name nexroll -p 9393:9393 -v ./nexroll-data:/app/data jbrns/nexroll:latest
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
3. Click **Create** and name it "NeXroll"
4. Copy the generated key

---

## Prerolls

### What video formats are supported?

Any format Plex/Jellyfin can play: MP4, MKV, AVI, MOV, etc. MP4 with H.264 is recommended for best compatibility.

### How long should prerolls be?

- **Recommended**: 10-30 seconds
- **Maximum practical**: 1-2 minutes total
- Too long = viewers get frustrated waiting for their movie

### Where should I store preroll files?

Store them where both NeXroll and Plex/Jellyfin can access them:
- **Docker**: Mount a shared volume
- **Windows**: Use a shared folder or local path both can reach

### Can I use the same preroll in multiple categories?

Yes! Prerolls can be assigned to multiple categories.

---

## Schedules

### How do schedules work?

Schedules automatically change your prerolls based on dates. For example:
- Christmas category active Dec 1-25
- Halloween category active Oct 1-31
- Default category active rest of the year

### What's the difference between Exclusive and Blend?

| Mode | Behavior |
|------|----------|
| **Exclusive** | Only this schedule's prerolls play (overrides everything) |
| **Blend** | Combines prerolls with other active schedules |

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

## Path Mappings

### What are path mappings?

Path mappings translate file paths between NeXroll and Plex when they see files at different locations.

**Example**: 
- NeXroll sees: `/prerolls/christmas.mp4`
- Plex sees: `/mnt/media/prerolls/christmas.mp4`
- Mapping: `/prerolls` → `/mnt/media/prerolls`

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

1. **Check path mappings**: Most common issue - verify paths translate correctly
2. **Apply to Plex**: Did you click "Apply to Plex" after making changes?
3. **File access**: Can Plex access the preroll files?
4. **Plex settings**: Check Settings → Server → Extras in Plex

### Prerolls play but wrong ones

1. Check which schedule is currently active
2. Verify the category has the prerolls you expect
3. Check if another schedule is overriding (Exclusive mode)

### Changes aren't taking effect

- Plex caches preroll settings - restart Plex or wait a few minutes
- Click "Apply to Plex" to push changes immediately

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

Currently, NeXroll connects to one Plex server at a time. You can switch servers in the Connect tab.

### Can I use NeXroll with Plex and Jellyfin simultaneously?

You can have both connected, but you'll need to apply prerolls to each separately.

### Is there a mobile app?

No dedicated app, but the web interface works on mobile browsers.

### Does NeXroll modify my media files?

No. NeXroll only tells Plex/Jellyfin which preroll files to play. It never modifies your movies or preroll videos.

---

## Updates & Support

### How do I update NeXroll?

**Docker**:
```bash
docker pull jbrns/nexroll:latest
docker stop nexroll && docker rm nexroll
# Re-run your docker run command
```

**Windows**: Download and run the latest installer.

### Where can I get help?

- [GitHub Issues](https://github.com/jbrfrn/NeXroll/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/jbrfrn/NeXroll/discussions) - Questions and community help

### How can I support NeXroll?

- ⭐ Star the project on GitHub
- ☕ [Support on Ko-fi](https://ko-fi.com/j_b__)
- 🐛 Report bugs and suggest features
- 📖 Help improve documentation
