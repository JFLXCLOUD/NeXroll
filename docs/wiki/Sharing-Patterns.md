# Sharing Sequences

NeXroll allows you to share your sequences with others through the **Export/Import** system. Share your preroll arrangements with friends, back them up, or move to a new server.

## Export Modes

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
- Pattern + all actual video files
- Ready to import immediately
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
5. Click **Import**

### Handling Missing Prerolls

If the imported sequence references prerolls you don't have:

**Community Prerolls**: If the export included Community IDs, NeXroll can automatically download missing prerolls from the Community Prerolls service.

**Local Prerolls**: You'll need to:
- Upload matching prerolls to your library
- Or edit the sequence after import to use different prerolls

### ZIP Bundle Import

When importing a `.zip` bundle:

1. NeXroll extracts and shows the contents
2. Map imported folders to categories:
   - Create new categories
   - Or map to existing categories
3. Preview the video files included
4. Click **Import** to extract videos and create the sequence

## File Format

### .nexseq Format

The `.nexseq` file is JSON with this structure:

```json
{
  "type": "nexseq",
  "version": "1.0",
  "metadata": {
    "name": "Holiday Mix",
    "description": "Christmas preroll sequence",
    "author": "NeXroll",
    "created": "2024-12-23T10:00:00Z",
    "exported": "2024-12-23T10:30:00Z",
    "blockCount": 3
  },
  "blocks": [
    {
      "type": "fixed",
      "preroll_ids": [12, 45]
    },
    {
      "type": "random",
      "category_id": 5,
      "count": 2
    }
  ],
  "compatibility": {
    "minVersion": "1.0",
    "features": []
  }
}
```

### What's Included

- **Sequence name and description**
- **Block configurations** (types, settings)
- **Category references** (by ID or name)
- **Preroll references** (IDs, or Community IDs if exported with that mode)
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

### Imported Sequence Doesn't Work

- Check that all prerolls are properly mapped
- Verify category references are valid
- Edit the sequence to fix any broken references
