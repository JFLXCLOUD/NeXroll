# Sequences

Sequences let you build custom preroll playlists by combining different preroll sources. Use the **Sequence Builder** to visually construct reusable preroll arrangements.

## What is a Sequence?

A sequence is a reusable preroll playlist that you build from blocks. Each block defines what prerolls to play:

- **Random blocks** - Pick random prerolls from a category
- **Fixed blocks** - Specific prerolls in a specific order

When a sequence is applied to Plex (or used by a schedule), NeXroll resolves the blocks into actual preroll paths.

## Accessing the Sequence Builder

Navigate to **Schedules → Sequence Builder** in NeXroll.

You'll see:
- The main builder area for adding and arranging blocks
- Quick tips and help cards
- Save, Export, and Import options

## Block Types

### Random Block (Category)

Pull prerolls randomly from an existing category:

| Setting | Description |
|---------|-------------|
| **Category** | Which category to pull prerolls from |
| **Count** | How many random prerolls to select (1+) |

**Example**: "Select 2 random prerolls from my Christmas category"

### Fixed Block

Add specific prerolls that always play in a set order:

| Setting | Description |
|---------|-------------|
| **Prerolls** | Select specific prerolls from your library |

The prerolls play in the exact order you add them.

**Example**: "Always play my Studio Logo first, then my Sponsor clip"

## Building a Sequence

### Step 1: Add Blocks

1. Click **Add Block** 
2. Choose the block type (Random or Fixed)
3. Configure the block settings

### Step 2: Arrange Blocks

- **Drag and drop** blocks to reorder them
- Use the **up/down arrows** to move blocks
- Click the **trash icon** to delete a block
- Click a block to **edit** its settings

### Step 3: Preview

Click **Preview** to see what your sequence would look like:
- Shows which prerolls would be selected
- For random blocks, run multiple previews to see variation
- Great for testing before saving

### Step 4: Save to Library

1. Enter a **Name** for your sequence
2. Add an optional **Description**
3. Click **Save**

Your sequence is now in your library and can be:
- Used in schedules
- Exported and shared
- Edited later

## Using Saved Sequences

### In Schedules

When creating or editing a schedule:

1. Enable **Use Sequence** option
2. Select a saved sequence from the dropdown
3. Save the schedule

The schedule will use that sequence during its active dates.

### Saved Sequences Library

Go to **Schedules → Saved Sequences** to:
- View all saved sequences
- Edit existing sequences
- Delete sequences
- Export sequences

## Exporting & Importing

### Export a Sequence

1. Open a sequence in the builder (or select from library)
2. Click **Export**
3. Save as a `.nexseq` file

The file contains:
- Sequence name and description
- All block configurations
- Version and export metadata

### Import a Sequence

1. Click **Import** in the builder or library
2. Select a `.nexseq` or `.json` file
3. The blocks are loaded into the builder
4. Review and save to your library

### Export All Sequences

From the Saved Sequences library, click **Export All** to bundle all sequences into one file for backup or sharing.

## How Sequences Work with Plex

When a sequence is applied:

1. NeXroll processes each block in order
2. Random blocks select prerolls from the specified category
3. Fixed blocks include the exact prerolls specified
4. All resolved preroll paths are combined
5. The path string is sent to Plex via the API

**Plex receives**: A semicolon-separated list of preroll file paths

Example:
```
/prerolls/logo.mp4;/prerolls/christmas/snow.mp4;/prerolls/christmas/tree.mp4
```

## Example Sequence

**"Holiday Mix"** sequence:

| Block | Type | Configuration |
|-------|------|---------------|
| 1 | Fixed | Studio Logo preroll |
| 2 | Random | 2 from Christmas category |
| 3 | Fixed | Outro clip |

**Result**: Logo plays first, then 2 random Christmas prerolls, then the outro.

## Tips & Best Practices

### Keep It Short
- 1-3 prerolls is typical
- Too many prerolls delays your movie

### Use Categories Effectively
- Organize prerolls into categories first
- Reference categories in random blocks
- Well-organized categories = better sequences

### Name Clearly
- Use descriptive names: "Holiday 2024 - 2 Random"
- Add descriptions for complex sequences

### Preview Before Saving
- Test randomization with multiple previews
- Verify the sequence looks right

### Combine with Schedules
- Create sequences for different occasions
- Use schedules to activate them automatically
- Christmas sequence active Dec 1-25, etc.

## Troubleshooting

### Sequence Not Playing

1. Verify the schedule using the sequence is active
2. Check path mappings are correct (Settings → Path Mappings)
3. Ensure preroll files are accessible to Plex
4. Check Plex's preroll setting was updated

### Random Blocks Always Same

- Plex caches prerolls - wait or restart Plex
- Re-apply the schedule to refresh

### Empty Sequence Error

- Each sequence needs at least one block
- Random blocks need a valid category selected
- Fixed blocks need at least one preroll selected
