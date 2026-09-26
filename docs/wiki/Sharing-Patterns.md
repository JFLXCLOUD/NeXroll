# Sharing Sequences

NeXroll allows you to share your sequences with others through the **Export/Import** system. Share your preroll arrangements with friends, back them up, or move to a new server.

## Export Modes

### Rating and availability compatibility

Since 2.2.0, exports preserve trailer age-rating restrictions and availability-pool choices, including trailer alternatives under **Otherwise**. Import into 2.2.0 or later; an older release cannot be relied upon to enforce the restrictions.

**This / next trailer block** follows playback order on the receiving install. Each install checks its own enabled trailers, files, and rating metadata, so matching availability can differ. A pattern does not supply missing trailer ratings or guarantee that the recipient has matching trailers. See [NeX-Up upgrade metadata](NeX-Up#rating-metadata-after-upgrading).

When exporting a sequence, choose the export format:

### Pattern Only (~5KB)
- Block structure only (types, counts, category references)
- Smallest file size
- Recipient must have matching prerolls in their library

### With Community IDs (~7KB) ⭐ RECOMMENDED
- Includes Community Preroll IDs for any community prerolls used
- Enables **automatic download** on import
- Best for sharing sequences that use community prerolls

### With Preroll Metadata (~50KB)
- Full metadata (names, tags, durations, descriptions)
- Helps recipients find equivalent prerolls
- Good for documentation

### Full Bundle (ZIP) - 100MB-5GB
- Pattern + the video files it plays: every category the sequence draws from (random and in-order blocks, and the alternatives of conditional blocks) and every preroll in its fixed blocks
- Ready to import immediately, even on a server that has none of the prerolls
- Perfect for archiving or offline sharing
- Large file size warning

## Exporting a Sequence

### From the Sequence Library

1. Go to **Schedules → Saved Sequences**
2. Find the sequence you want to export
3. Click the **Export** button on the sequence card
4. Choose your export mode
5. Click **Export**
6. Save the `.nexseq` file (or `.zip` for full bundle)

### Export All Sequences

To export your entire sequence library:

1. Go to **Schedules → Saved Sequences**
2. Click **Export All**
3. All sequences are bundled into one file

## Importing a Sequence

### Supported File Types

- `.nexseq` - NeXroll sequence pattern
- `.json` - Legacy JSON format
- `.zip` - Full bundle with video files
- `.nexbundle` - Multi-sequence bundle

### Import Process

1. Go to **Schedules → Saved Sequences**
2. Click **Import**
3. Select your file
4. **Preview** what will be imported:
   - Block configuration
   - Required prerolls
   - Missing prerolls (highlighted)
5. Click **Import Pattern**

Categories and prerolls are matched by name (ignoring case), and prerolls also by Community ID. When everything matches, the sequence is saved to your library. When a category or preroll is not on this server, the sequence opens in the **Sequence Builder** instead, with those blocks empty: choose a category or preroll for each, then save. Importing from the Sequence Builder's own **Import** button always loads the sequence into the builder.

### Handling Missing Prerolls

If the imported sequence references prerolls you don't have:

**Community Prerolls**: If the export included Community IDs, NeXroll can download missing prerolls from the Community Prerolls service. They go into the category they came from when you have a category with that name.

**Local Prerolls**: You'll need to:
- Upload matching prerolls to your library, then import again
- Or choose different prerolls for those blocks in the builder

### ZIP Bundle Import

When importing a `.zip` bundle:

1. NeXroll extracts and shows the contents
2. Map imported folders to categories:
   - Create new categories
   - Or map to existing categories (a category with the same name is picked for you)
3. Preview the video files included
4. Click **Import with Mappings** to copy the videos, then **Import Pattern** to create the sequence

Category and preroll names come back exactly as they were exported. A preroll that is already in the chosen category is skipped, and a preroll that was in several categories is imported once and added to each. A category name this server cannot use as a folder (for example one with a colon, from Linux or macOS) is created with the bundle's folder name instead.

## File Format

### .nexseq Format

The `.nexseq` file is JSON. Categories and prerolls are named rather than referred to by this server's database ids, so the file means the same thing on any server:

```json
{
  "pattern_name": "Holiday Mix",
  "pattern_description": "Christmas preroll sequence",
  "created_by": "NeXroll",
  "export_mode": "with_community_ids",
  "nexroll_version": "2.2.1",
  "exported_at": "2026-12-01T10:30:00Z",
  "blocks": [
    {
      "type": "fixed",
      "preroll_name": "Welcome.mp4",
      "category_names": ["Christmas"],
      "prerolls": [
        { "name": "Welcome.mp4", "category_names": ["Christmas"] },
        { "name": "Snow Globe.mp4", "community_id": "/Holidays/Christmas/Snow Globe.mp4" }
      ]
    },
    {
      "type": "random",
      "category_name": "Christmas",
      "count": 2
    }
  ]
}
```

A fixed block with several prerolls lists them all under `prerolls` (2.2.1 and later). The first is also written as `preroll_name`, which is what earlier releases read, so they still import the block with its first preroll.

### What's Included

- **Sequence name and description**
- **Block configurations** (types, settings, conditions and their alternatives)
- **Category references** (by name)
- **Preroll references** (by name, and Community ID when there is one)
- **Export metadata** (date, version)

### What's NOT Included (Pattern Only)

- Actual video files
- Media server credentials
- System-specific paths

## Sharing Tips

### For Sharing with Others

1. Use **With Community IDs** mode if your sequence uses community prerolls
2. Use descriptive names and add a description
3. Test import your own export before sharing

### For Personal Backup

1. Use **Full Bundle** for complete archives
2. Store bundles separately from your NeXroll installation
3. Include dates in filenames: `Holiday_2024_backup.zip`

### For Migration

When moving to a new server:

1. Export all sequences as a bundle
2. Copy your preroll video files
3. Install NeXroll on new server
4. Import sequences
5. Update path mappings if needed

## Troubleshooting

### Import Shows "Missing Prerolls"

- The sequence references prerolls not in your library
- Upload matching prerolls, or
- Enable auto-download if Community IDs are available

### ZIP Import Fails

- Check the ZIP isn't corrupted
- Ensure adequate disk space
- Very large bundles may timeout - try smaller exports

### Imported Sequence Opens in the Builder

- Some of its categories or prerolls are not on this server
- Pick a category or preroll for each empty block, then **Save sequence**
- Or add the missing category or prerolls first and import again
