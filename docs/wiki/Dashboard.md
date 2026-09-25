# Dashboard

The dashboard is the page NeXroll opens on. It answers one question at a glance — *what is my server playing right now, and is anything wrong?* — and gets out of the way.

Everything on it is a **tile**. You choose which tiles appear, how big they are, and in what order.

---

## Reading the dashboard

The two tiles that matter most on a normal day:

- **Current & next schedule** — what is active right now, how it plays (single preroll, shuffled category, or a sequence), and what takes over next.
- **System health** — one score covering the scheduler, your media server connection, storage, and schedule conflicts. If something needs attention, it says so here with a link straight to the fix.

Connection health confirms NeXroll can reach the server. It does not prove the media server can open a preroll file or that a client played it; see [Path Mappings](Path-Mappings) if playback still fails.

### Media-server health in 2.2.0

System health checks each configured Plex, Jellyfin, and Emby connection with an authenticated request. Saved connection settings alone do not count as a healthy connection. The tile refreshes every **30 seconds** and when you return focus to the window.

If Jellyfin is shut down or unreachable, for example, the tile shows **Unhealthy** and **No connection to media server (Jellyfin)**. Rejected credentials, certificate problems, and other server failures have their own explanations. A healthy second server does not hide the failed connection. Health recovers automatically when connectivity returns.

A plugin registration without a direct, testable server connection appears as **unverified / Needs attention**. Configure the direct connection under [Connect](Connect) to monitor it. A historical plugin registration cannot establish whether that server is currently online.

If the health refresh itself fails, the tile stops presenting a stale healthy result. Recheck the NeXroll connection as well as the media server.

---

## Available tiles

### Conflict shortcuts

Click the dashboard's conflict count, conflict health row/message, Schedule counts conflict row, or weekly-calendar conflict badge/icon to open **Schedules > Conflicts** directly. Use that page to review and resolve overlaps. These shortcuts also work with keyboard navigation and while arranging tiles.

### Library Trailers card

The **Library Trailers** card shows available local trailers and downloads for movies already in your library. Detailed view adds download storage use, errors and trailers outside your selection. **Open** leads to [NeX-Up > Library Trailers](NeX-Up#library-trailers); **Sync Library Trailers** runs the same sync as that page, using your saved filters, targets and limits. Enable Library Trailers and configure Radarr first.

The card refreshes status every five seconds while visible, disables sync while a run is active and reports failures. The last-sync time is the last completed run since the server restarted. This sync is separate from rescanning your preroll files or syncing Upcoming movie/TV trailers.

Once loaded, the card keeps its current counts visible while refreshing status in the background.

The card is included in Essential and Operations presets and can be hidden, resized or reordered through Customize. Upgrading preserves existing custom tile order, hidden choices and geometry while adding the new card.

| Tile | Shows |
|---|---|
| Current & next schedule | What is active now, how it plays, and what follows it |
| Upcoming schedules | The full queue of what activates next |
| System health | Scheduler, server, storage, conflicts |
| Storage | Space used by content type |
| Quick actions | Common maintenance commands |
| Library | Prerolls, categories, and trailers |
| Schedule counts | Enabled, disabled, and conflicts in detail |
| Media servers | Plex, Jellyfin, and Emby connections in detail |
| Scheduler | Run state, timezone, and last activation in detail |
| Community prerolls | Matched and downloaded prerolls |
| NeX-Up | Trailer sync status |
| Library Trailers | Local trailers, downloads, storage, errors and Library Trailers sync |
| Video quality | Resolution and codec analysis |
| Weekly calendar | This week at a glance |

---

## Rearranging the dashboard

Click **Edit layout** in the page header to unlock the grid. While editing:

- **Drag any tile** by its handle to reorder.
- **Click the size chip** on a tile to cycle it through small, medium and large. Small spans a third of the row, medium two thirds, large the full width.
- **Hide a tile** with the X in its corner. Hidden tiles can be brought back from the same menu.
- Some tiles offer a **compact / detailed** toggle, which changes how many rows they show rather than how much space they take.

Click **Done** to lock the grid again. The layout is saved per install, not per browser, so it follows you to another device.

### Presets

If you would rather not arrange tiles by hand, the layout menu offers presets — a minimal set, an operations-focused set, and the full grid. Applying one replaces your current arrangement; you can still adjust afterwards.

---

## Quick actions

The Quick actions tile collects the maintenance commands you would otherwise hunt for in Settings:

- **Rescan library** — reconcile the database against the files on disk.
- **Rebuild thumbnails** — regenerate missing preview images.
- **Re-apply current schedule** — push the active selection to your media server again, useful after a server restart.

---

## Troubleshooting

**A tile is empty or says "not connected".**
That tile depends on something that is not set up yet — most often a media server connection. Open [Connect](Connect) and finish the connection.

**The dashboard shows a schedule that is not playing.**
NeXroll shows what it has told the server to play. If the server is playing something else, the usual cause is a path the server cannot open — see [Path Mappings](Path-Mappings).

**Upcoming schedules runs past the edge of its tile.**
Fixed in 2.2.0-beta.5. Update if you are on an earlier build.

---

## See also

- [Scheduling Guide](Scheduling) — how the schedule queue is built
- [Preroll Library](Preroll-Library) — managing the content the dashboard counts
- [Troubleshooting](Troubleshooting) — when the health tile is unhappy
