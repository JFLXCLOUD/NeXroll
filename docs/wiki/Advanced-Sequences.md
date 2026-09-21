# Advanced Sequences

The Sequence Builder has two optional extras on top of the usual list of blocks:

- **Advanced mode** lets a block decide *when* it plays, and what plays in its place when it doesn't. This is the builder's IF / THEN / OTHERWISE.
- **Flow view** draws your sequence as a workflow you can pan, zoom and drag, with conditions shown as branches.

Neither is required. A sequence built in Simple mode and List view works exactly as it always has. If you're new to sequences, start with [Sequences](Sequences).

---

## At a glance

Two switches sit at the top of the sequence in **Schedules → Sequence Builder**:

| Switch | Options | What it changes |
|--------|---------|-----------------|
| **Mode** | **Simple** / **Advanced** | Advanced adds a **Conditions** section to each block's settings |
| **View** | **List** / **Flow** | Flow draws the sequence as a node workflow instead of a list |

Both choices are remembered in your browser. They are independent: you can use Advanced mode in List view, or Flow view in Simple mode.

Conditions keep working if you switch back to Simple mode. Those blocks are marked **Conditional**, and the builder offers to switch back to Advanced if you want to change them.

---

## Conditions: IF / THEN / OTHERWISE

### Adding a condition

1. Switch to **Advanced**
2. Select a block
3. In **Block settings**, under **Conditions**, click **Add a condition**
4. Choose a rule and whether the block plays **when** it is true or **unless** it is true
5. Under **Otherwise**, choose what happens when the condition isn't met:
   - **Skip this block**, so the sequence moves straight on to the next block
   - **Play prerolls from a category**, choosing the category and how many
   - **Play NeX-Up trailers**, choosing movies, TV or both, and how many

Under the rules, a summary reads the condition back in plain English, for example:

> Plays only when the genre is Horror or Thriller. Otherwise, 1 preroll from House Intros plays instead.

### More than one rule

Click **Add another rule**, then choose whether the block needs **all** of the rules to hold, or **any** of them.

### When NeXroll can't tell

If NeXroll can't answer a rule, the rule counts as **not met** and the **Otherwise** plays. A conditional block only plays when NeXroll *knows* its condition holds. This matters most for the genre rule on Plex; see [What each server can check](#what-each-server-can-check).

---

## Rules

| Rule | Plays when | Works on |
|------|------------|----------|
| **Trailers available** | At least a number of NeX-Up trailers (movies, TV, or both) are downloaded and enabled | Plex, Jellyfin, Emby |
| **Time of day** | The time is inside a window, optionally only on chosen days | Plex, Jellyfin, Emby |
| **Genre** | What is about to play has any of the chosen genres | Jellyfin, Emby |
| **Movie or episode** | What is about to play is a movie, or a TV episode | Jellyfin, Emby (on Plex it is always a movie) |

### Trailers available

Counts exactly the trailers a **NeX-Up Trailers** block would play: downloaded, enabled, and with the file still on disk. Use it to keep a trailer block or a Coming Soon slide out of the sequence when there is nothing to show.

### Time of day

Pick a start and end time, and optionally the days it applies to. No days selected means every day. A window that runs past midnight, such as **22:00 to 03:00**, belongs to the day it starts on, so a Friday window still holds at 1am on Saturday. This matches how schedules treat overnight windows.

### Genre (Jellyfin & Emby)

Add one or more genres. The block plays when the title about to start has **any** of them. Matching ignores capitals.

- Suggestions come from your connected Jellyfin and Emby libraries, so they use the same names your server does. You can also type any name.
- A TV episode uses its series' genres.
- Choose **unless** to play a block for everything *except* those genres.

### Movie or episode (Jellyfin & Emby)

Plays a block only before movies, or only before TV episodes. Plex only runs prerolls before movies, so on Plex this rule always sees a movie.

---

## What each server can check

In Advanced mode, the builder shows a **What each server can check** panel. Here is what it means.

**Jellyfin and Emby** ask NeXroll what to play at the moment playback starts, through the NeXroll Intros plugin. The plugin says which title is starting, so NeXroll can check its genre and whether it is a movie or an episode. Every rule works, and every rule is checked live.

**Plex** works differently. NeXroll gives Plex one preroll list in advance, and Plex plays it before every movie. Plex never tells NeXroll which movie is starting, so:

- **Trailers available** and **Time of day** work. NeXroll re-checks them every 10 minutes and updates Plex when the answer changes.
- **Genre** is never met on Plex, so the block plays its **Otherwise**.
- **Movie or episode** always sees a movie.

Blocks that use a Jellyfin & Emby rule are labelled **Jellyfin & Emby** in the list, on the block's settings, and on Flow view's IF nodes.

### If you use Plex

Everything in Simple mode, plus **Trailers available** and **Time of day**, works fully for you. For genre-style theming on Plex, use a schedule instead: a **Halloween** category scheduled through October plays before every movie in October, on every server.

If you share a sequence that uses genre rules, give each genre block an **Otherwise** that suits a general audience. That is what your Plex viewers will see.

### If you run Plex and Jellyfin or Emby together

One sequence serves all of them. Jellyfin and Emby viewers get the genre-matched blocks, and Plex viewers get each block's Otherwise. You don't need a separate sequence for Plex.

---

## Flow view

Flow view shows the same sequence as a workflow, running left to right from **Playback starts** to **Movie starts**.

| To... | Do this |
|-------|---------|
| Add a block at a point in the sequence | Click the **+** on the connection there and choose a block type |
| Position a block | Drag it anywhere on the canvas; playback order stays the same |
| Reorder playback | Select a block and use the earlier / later arrows beside its step number |
| Tidy the canvas | Click **Auto arrange** to restore the left-to-right layout and fit the sequence |
| Edit | Click a block; its settings open in **Block settings** |
| Move around | Drag the background to pan, and scroll or use the **+ / -** buttons to zoom |
| Find your place in a long sequence | Use the minimap in the corner |

In Advanced mode, a conditional block is drawn as an **IF** node with two branches:

- **true** (green) leads to the block itself
- **false** (orange, dashed) leads to its **Otherwise**, or to **Skip**

Both branches join the next block. In Simple mode a conditional block is a single node marked **Conditional**.

Flow view hides the Block library column to give the canvas more room, since the **+** on each connection adds blocks. Long sequences open at the start and continue to the right, rather than shrinking until they can't be read.

Block positions are saved with the sequence. Simple and Advanced layouts are remembered separately, including the condition branches. Switching to List and back preserves your placement. Follow the connection arrows and step numbers to see playback order; moving a block on the canvas does not change what plays next.

---

## Previewing

Click **Preview** to play the sequence as a viewer would see it right now.

- Conditions are checked as if a movie were starting at this moment.
- A panel lists each conditional block and whether it **plays**, **plays its alternative** or **is skipped**, and why.
- For a sequence with genre rules, **Preview as** switches between **Plex (genre unknown)** and each genre the sequence uses. For example, **A Horror movie on Jellyfin or Emby**. Use it to check what both kinds of viewer will get.

---

## Recipes

### Only show Coming Soon when something is coming

1. Add a **Generated preroll** block set to the latest Coming Soon grid or list
2. Add the condition **when Trailers available, at least 1**
3. Set **Otherwise** to **Skip this block**

When you have no upcoming trailers, the slide drops out instead of showing an empty list. This works on every server.

### Halloween prerolls before horror movies (Jellyfin & Emby)

1. Add a **Category** block for your Halloween category
2. Add the condition **when Genre is Horror**. Add Thriller too if you like.
3. Set **Otherwise** to **Play prerolls from a category**: your usual intros

Horror on Jellyfin and Emby opens with a Halloween preroll. Everything else, and every movie on Plex, gets your usual intro.

### Trailers for movies like the one about to play (Jellyfin & Emby)

1. Turn on [Library Trailers](NeX-Up#library-trailers) under NeX-Up
2. Add a **Library trailers** block with **2** trailers
3. Tick **Same genre as the movie that's starting**

A horror movie opens with trailers for other horror movies you own, and a comedy with comedies. On Plex, the same block plays two trailers from your whole library selection. The trailer for the movie that's starting is never picked.

### A late-night bumper at weekends

1. Add a **Fixed preroll** block with your late-night bumper
2. Add the condition **when Time of day, from 22:00 to 03:00**, with **Fri** and **Sat** selected
3. Leave **Otherwise** as **Skip this block**

### A shorter intro before TV episodes (Jellyfin & Emby)

1. Add a **Category** block for your full cinema intro
2. Add the condition **unless Movie or episode is a TV episode**
3. Set **Otherwise** to one preroll from a short bumper category

Movies get the full intro, and episodes get a quick bumper.

---

## Where conditions work

- **The Sequence Builder page**, in the Conditions section of Block settings
- **Creating or editing a schedule**, when you build a custom sequence there. Switch that builder to Advanced and edit a block.
- **Filler sequences.** A saved sequence used as filler keeps its conditions. On Plex, filler is re-checked every minute.

---

## Sharing, backups and restores

- **Export** keeps each block's conditions. An Otherwise that plays a category travels by category name and is matched to a category with the same name on import. An Otherwise made of specific prerolls isn't exported, because those files belong to your install; on another install that block is skipped when its condition isn't met.
- **Backups** keep conditions. On restore, an Otherwise whose category no longer exists is dropped, so the block is skipped rather than playing the wrong thing.

---

## Troubleshooting

**A genre block never plays on Jellyfin or Emby.**
Check that the server is connected on the [Connect](Connect) page with a working API key, and that the NeXroll Intros plugin is installed. NeXroll asks the server for the title's genres. If it can't reach the server, the rule counts as not met. Also check the genre names match your library's: pick them from the suggestions rather than typing them.

**A genre block always plays its Otherwise on Plex.**
That is expected. Plex never says which movie is starting; see [If you use Plex](#if-you-use-plex).

**A block says Conditional but I can't see any conditions.**
You are in Simple mode. Switch to **Advanced** to see and change them.

**The preview doesn't match what played.**
Preview checks conditions at the moment you open it. Time-of-day rules and trailer counts can change between then and playback, and on Plex the list is re-checked every 10 minutes. For genre rules, use **Preview as** to choose which case to preview.

---

## Related Pages

- [Sequences](Sequences) - Building sequences and block types
- [Scheduling](Scheduling) - Putting sequences on a schedule
- [NeX-Up](NeX-Up) - Trailers and generated prerolls used by trailer and Coming Soon blocks
- [Jellyfin](Jellyfin) and [Emby](Emby) - Installing the NeXroll Intros plugin
