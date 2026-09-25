# Sequences

Sequences let you build custom preroll playlists by combining different preroll sources. Use the **Sequence Builder** to visually construct reusable preroll arrangements.

## What is a Sequence?

A sequence is a reusable preroll playlist that you build from blocks. Each block defines what prerolls to play:

- **Random blocks** — Pick random prerolls from a category
- **Fixed blocks** — Specific prerolls in a specific order
- **NeX-Up trailers** — Downloaded upcoming movie or TV trailers
- **Library trailers** — Trailers for movies you already own
- **Generated preroll** — A generated intro or Coming Soon list

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

### Trailer blocks and age ratings

> **New in 2.2.0:** Age-rating restrictions are available in the builder.

Add a **NeX-Up trailers** or **Library trailers** block from the block library. Choose the trailer count and order; NeX-Up also lets you choose movies, TV, or both. Library trailers can filter by genre and prefer the genre of the movie starting on Jellyfin/Emby.

To restrict the block:

1. Enable **Restrict age ratings** under **Age ratings**.
2. Select every allowed rating, such as **G** and **PG**.
3. Save the sequence. The choices remain when you reopen it or switch between List and Flow.

The filter applies before trailers are selected. Fewer matching trailers means fewer play; NeXroll does not fill the remainder with disallowed ratings. An enabled restriction with no ratings selected plays no trailers. Turn the restriction off to allow every rating again.

Missing ratings are excluded unless you select **Unrated**. Older trailers receive available ratings from Radarr/Sonarr on their next normal NeX-Up sync. Manual uploads or titles no longer present in their provider may remain unrated. Other international certifications are not relabeled Unrated and will not match the built-in rating choices.

Ratings describe the film or show, not an independent review of the trailer. This setting restricts the trailer pool; it does not automatically match the rating of the feature being played. Plex uses one applied list for all movies.

To show a Coming Soon or Now Available intro only when matching trailers follow, use [source-specific availability conditions](Advanced-Sequences#trailers-available).

Existing sequences remain unrestricted until you add a rating restriction. Export/import retains restrictions, including those on an **Otherwise** trailer block. Import into a version that supports these controls; older releases cannot enforce them.

To keep enough matching trailers in your library pool, configure [minimum trailer targets](NeX-Up#minimum-trailer-targets). Targets guide which trailers NeX-Up downloads; this block's rating restriction still decides which of them may play.

### Step 1: Add Blocks

1. Click **Add Block** 
2. Choose the block type from the block library
3. Configure the block settings

### Step 2: Arrange Blocks

- In List view, **drag and drop** blocks to reorder them
- In Flow view, dragging changes layout only; use the step arrows to change playback order
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
- Used as a Filler Category source
- Exported and shared
- Edited later

## Advanced Mode and Flow View

Two optional switches at the top of the sequence add more control:

- **Advanced** mode lets any block decide *when* it plays, such as only when trailers are available, only late at night, or only before horror movies on Jellyfin and Emby, and what plays in its place when it doesn't.
- **Flow** view draws the sequence as a workflow you can pan, zoom and drag, with conditions shown as branches.

See [Advanced Sequences](Advanced-Sequences) for the full guide, including what Plex, Jellyfin and Emby can each check.

## NeX-Up Preset Sequences

If you're using NeX-Up, preset sequence templates are available in the **NeX-Up → Generator** tab:

| Preset | Content |
|--------|---------|
| **Coming Soon + Movie Trailers** | Your intro → 2-3 random movie trailers |
| **Coming Soon + TV Trailers** | Your intro → 2-3 random TV trailers |
| **Mixed: Movies + TV** | Your intro → 1 movie trailer → 1 TV trailer |
| **Theater Experience** | Your intro → 4 random trailers |

These presets auto-create sequences with the right blocks pre-configured. See [NeX-Up Guide](NeX-Up#building-sequences-with-trailers) for details.

## Using Saved Sequences

### In Schedules

When creating or editing a schedule:

1. Enable **Use Sequence** option
2. Select a saved sequence from the dropdown
3. Save the schedule

The schedule will use that sequence during its active dates.

### As Filler Category

Sequences can be used as the global filler when no schedules are active:

1. Go to **Settings → General → Filler Category**
2. Set filler type to **Sequence**
3. Select a saved sequence

### Saved Sequences Library

Go to **Schedules → Saved Sequences** to:
- View all saved sequences
- Edit existing sequences
- Delete sequences
- Export sequences
- Click **Schedule** to create a schedule from a sequence

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

See [Sharing Sequences](Sharing-Patterns) for detailed export/import options.

## How Sequences Work with Plex

When a sequence is applied:

1. NeXroll processes each block in order
2. Random blocks select prerolls from the specified category
3. Fixed blocks include the exact prerolls specified
4. All resolved preroll paths are combined
5. The path string is sent to Plex via the API

**Plex receives**: A comma-separated list of preroll file paths for sequential playback. Semicolons represent random alternatives in Plex and would not play the full sequence in order.

Example:
```
/prerolls/logo.mp4,/prerolls/christmas/snow.mp4,/prerolls/christmas/tree.mp4
```

## Example Sequences

### Holiday Mix

| Block | Type | Configuration |
|-------|------|---------------|
| 1 | Fixed | Studio Logo preroll |
| 2 | Random | 2 from Christmas category |
| 3 | Fixed | Outro clip |

**Result**: Logo plays first, then 2 random Christmas prerolls, then the outro.

### Theater Experience

| Block | Type | Configuration |
|-------|------|---------------|
| 1 | Fixed | "Coming Soon" dynamic intro |
| 2 | NeX-Up trailers | Movies only, count 2, optional rating restriction |
| 3 | NeX-Up trailers | TV only, count 1, optional rating restriction |

**Result**: Your custom intro, followed by 2 random movie trailers and 1 TV trailer.

## Tips & Best Practices

### Keep It Short
- 1-3 prerolls is typical
- Too many prerolls delays your movie

### Use Categories Effectively
- Organize prerolls into categories first
- Reference categories in random blocks
- Well-organized categories = better sequences

### Name Clearly
- Use descriptive names: "Holiday 2025 - 2 Random"
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

- Plex caches prerolls — wait or restart Plex
- Re-apply the schedule to refresh

### Empty Sequence Error

- Each sequence needs at least one block
- Random blocks need a valid category selected
- Fixed blocks need at least one preroll selected

### A restricted trailer block plays nothing

Check that at least one rating is selected, then sync the relevant NeX-Up trailer pool to refresh older metadata. Matching trailers must be enabled, ready, and present on disk. See [NeX-Up](NeX-Up#rating-metadata-after-upgrading).

An intentionally empty restricted sequence clears the old Plex list and does not fall back to the active category on Jellyfin/Emby. Other explicit blocks or blend schedules can still provide content.

## Audio demo conditions

From 2.2.0, switch the builder to Advanced and add **Stored audio format** to a demo block. Jellyfin/Emby can check the default/only stored track or any stored track; Plex and unknown metadata use Otherwise. See [the full workflow and playback limits](Advanced-Sequences#stored-audio-format-jellyfin--emby).
