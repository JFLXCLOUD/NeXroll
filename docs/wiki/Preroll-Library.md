# Preroll Library

The library is every video NeXroll knows about: prerolls you uploaded, folders you indexed, prerolls downloaded from the community, trailers fetched by NeX-Up, and videos produced by the Generator Studio.

---

## Browsing

Switch between **grid** and **list** with the view toggle in the page header.

- **Grid** shows thumbnails. Hover a card for Preview, Edit and Delete.
- **List** is a sortable table — name, category, duration, community status, date added.

Use the **Preview panel** toggle to open an inspector on the right. It plays the selected preroll inline (muted, looping) and shows category, duration, resolution and tags. Click a row to inspect it; the **Preview** button always opens the full-size player.

### Filtering

The command row filters by category, tag, and free text. Two filters are worth knowing:

- **Show/hide NeX-Up trailers** — trailers can outnumber your actual prerolls, so this hides them without deleting anything.
- **Show/hide generated prerolls** — same idea for Generator Studio output.

---

## Adding prerolls

Open **Library → Add Prerolls**. There are two ways in, and they behave differently.

### Upload

Drag files in or browse for them. NeXroll copies each file into its own storage, generates a thumbnail, probes duration and resolution, and creates a library entry. Use this when the videos are not already organised on disk.

### Index an existing folder

Point NeXroll at a folder you already keep prerolls in. It records the files where they are — **nothing is copied or moved**. Subfolders become categories.

This is the right choice when your prerolls live on a NAS or a share you manage yourself. It is also the one that needs a path your media server can open: see [Path Mappings](Path-Mappings).

> Files indexed in place are never deleted by NeXroll's trash. Removing such an entry removes the database row only.

---

## Categories

Open **Library → Categories**.

Categories are how schedules select content: a schedule points at a category, not at individual files. A preroll can belong to several categories at once, with one marked primary for display.

Each category has:

- **Name and description**
- **Plex mode** — how the category is applied when a schedule uses it: **shuffle** (the server picks at random from the set) or **playlist** (the server plays them in order).
- **Apply to Plex** — whether this category is pushed to the server at all.

Categories created by NeXroll itself — *NeX-Up Movie Trailers*, *NeX-Up TV Trailers*, *NeX-Up Prerolls*, *Coming Soon Lists* — are marked as system categories. You can schedule them like any other, but NeXroll manages their membership.

---

## Video scaling

Open **Library → Video Scaling**.

Large source files (4K masters, high-bitrate exports) can make a server transcode a preroll that should have played instantly. This page lists every preroll by resolution and flags the oversized ones.

Select the ones you want and create streaming-friendly versions. The original is kept; the scaled copy is added alongside it so you can compare before removing anything.

---

## Trash

Open **Library → Trash**.

Deleting a preroll moves it here rather than removing it immediately. From the trash you can:

- **Restore** — put the file and its database entry back.
- **Delete permanently** — remove the file from disk. This cannot be undone.

Only files NeXroll manages are placed in the trash. Entries for folders you indexed in place are removed from the database without touching your files.

---

## Bulk actions

Select several prerolls with their checkboxes to get a bulk bar:

- Assign a category to all of them
- Delete them together
- Clear the selection

---

## Troubleshooting

**A preroll shows a broken thumbnail.**
Run **Rebuild thumbnails** from the dashboard's Quick actions tile.

**Entries exist but the files are gone.**
Run a rescan. NeXroll reconciles the database against disk and reports what is missing rather than deleting rows behind your back.

**Everything plays except prerolls in one folder.**
Almost always a path your media server cannot open. See [Path Mappings](Path-Mappings).

---

## See also

- [Scheduling Guide](Scheduling) — putting categories on a schedule
- [Sequences](Sequences) — ordering prerolls precisely
- [Community Prerolls](Community-Prerolls) — downloading from the community library
- [NeX-Up](NeX-Up) — automatic trailers
