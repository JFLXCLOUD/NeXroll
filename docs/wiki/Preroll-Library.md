# Preroll Library

The library is every video NeXroll knows about: prerolls you uploaded, folders you indexed, prerolls downloaded from the community, trailers fetched by NeX-Up, and videos produced by the Generator Studio.

---

## Browsing

Switch between **grid** and **list** with the view toggle in the page header.

- **Grid** shows thumbnails. Hover a card for Preview, Edit and Delete.
- **List** is a sortable table — name, category, duration, community status, date added.

**Refresh Library** in the page header scans your storage folder for files added or deleted outside NeXroll, then reloads the library. It shows **Scanning...** while it runs and reports what it found. (Before 2.2.2 it only reloaded the page, so it seemed to do nothing after you deleted files on disk.)

Use the **Preview panel** toggle to open an inspector on the right. It plays the selected preroll inline (muted, looping) and shows category, duration, resolution and tags. Click a row to inspect it; the **Preview** button always opens the full-size player.

### Filtering

Since 2.2.0, prerolls linked to the Community library's `/AI/` directory show the same **AI-generated** badge in Library grid/list views, the preview panel and the edit modal. Existing downloads with their Community link already receive the badge; no new download is needed. Renaming or moving the local file to another category does not remove it. The label comes from the saved Community source, not an analysis of the video or its filename. Unlinking that source removes the label; files without a Community source are not automatically classified.

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

Categories are how schedules select content: a schedule points at a category, not at individual files. A preroll can belong to several categories at once, and they are all equal. A preroll can also have no category; the Library's **Uncategorized** filter finds those.

NeXroll stores an uploaded file in a folder named after the first category you choose for it. The folder only decides where the file sits on disk; which schedules play it depends on its categories alone. Removing or deleting that first category doesn't delete or strand the file.

You don't have to come here first to make a category. Wherever you put prerolls into one, you can create it on the spot:

- **Uploading, or editing a preroll:** open the **Categories** box and click **New category**, or type a name that doesn't exist yet and press Enter.
- **Import Folder, the Library's bulk bar, and Community Prerolls downloads:** choose **+ New category…** at the bottom of the category list, type the name, and click **Create**.

The new category is selected straight away. Typing the name of a category you already have selects that one instead of making a duplicate.

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
Click **Refresh Library**. When you delete prerolls from a folder that is still there, NeXroll removes their entries on the next scan, however many you deleted.

When the missing files were in folders that are now gone or empty, NeXroll can't tell a deletion from a network share or drive that is offline, so it keeps a large batch of them. The dashboard then says so and offers **I deleted them, remove entries**. Click it if you deleted them; otherwise leave them, and they relink when the storage is back. **Remove Missing Rows** under **Settings → Backup & Restore** does the same at any time.

Before 2.2.2, deleting more than about a quarter of the library at once was always treated as storage going offline, and the entries were kept until you used Remove Missing Rows.

**Everything plays except prerolls in one folder.**
Almost always a path your media server cannot open. See [Path Mappings](Path-Mappings).

---

## See also

- [Scheduling Guide](Scheduling) — putting categories on a schedule
- [Sequences](Sequences) — ordering prerolls precisely
- [Community Prerolls](Community-Prerolls) — downloading from the community library
- [NeX-Up](NeX-Up) — automatic trailers
