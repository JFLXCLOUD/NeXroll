# Dashboard

The dashboard is the page NeXroll opens on. It answers one question at a glance — *what is my server playing right now, and is anything wrong?* — and gets out of the way.

Everything on it is a **tile**. You choose which tiles appear, how big they are, and in what order.

---

## Reading the dashboard

The two tiles that matter most on a normal day:

- **Current & next schedule** — what is active right now, how it plays (single preroll, shuffled category, or a sequence), and what takes over next.
- **System health** — one score covering the scheduler, your media server connection, storage, and schedule conflicts. If something needs attention, it says so here with a link straight to the fix.

If the health tile is green and the current schedule is what you expect, there is nothing else to do.

---

## Available tiles

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
