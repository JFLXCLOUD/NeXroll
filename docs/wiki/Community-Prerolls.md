# Community Prerolls

The **Community Prerolls** page lets you search, browse, and download prerolls from the **Typical Nerds** community library — a large, free collection of prerolls contributed by the community — directly into your NeXroll library.

## Overview

NeXroll indexes the community library locally so search and browse are **instant** (milliseconds), then downloads any preroll you pick straight into your collection — optionally renamed and dropped into a category.

You'll find it in the sidebar under **Community Prerolls**.

The top of the page works like the rest of NeXroll: **Change Server** and **Refresh Index** at the top right, then four tiles showing the server, how many prerolls are indexed, how many are in your library, and the index's age.

## Fair Use Policy

Before you can search or download, you must accept the **Fair Use Policy**. This protects the Typical Nerds community from abuse (excessive scraping, rehosting, etc.). You'll see a one-time prompt on the Community Prerolls page — accept it to unlock search, browse, and downloads.

## The local index

Search and browse are powered by a **local index** of the community library, so they don't hammer the source server.

- The first time you open the page, NeXroll uses the index if present.
- Click **Refresh Index** (top right of the page) to (re)build it. This crawls the community directory and can take a couple of minutes — run it occasionally (e.g. weekly, or when you know new prerolls were added).
- An index older than a week keeps working; it just won't include newer uploads. The page shows its age with **refresh recommended**. (Before 2.2.7 an index older than a week stopped working until it was rebuilt.)
- Without an index, NeXroll falls back to slow, rate-limited live requests, so building the index is strongly recommended.

> The index is stored with your NeXroll data (it persists across restarts and, on Docker, across image updates).

### Weekly refresh

**Weekly refresh** (under the summary tiles, off by default) rebuilds the index on its own once it is a week old. A rebuild is about 600 small requests to the community server over a couple of minutes, plus reading the length of any new prerolls — the same as pressing **Refresh Index** once a week. It only refreshes an index you have already built, waits a random few hours past the week so installs don't all refresh at once, and if a rebuild fails it tries again a day later.

## How results are listed

- **One row per preroll, not per platform.** Many prerolls come in a Plex, a Jellyfin and an Emby version. They're listed once, with the versions shown as chips (**Plex**, **Jellyfin**, **Emby**) next to the length. See [Platform versions](#platform-versions).
- **Copies are listed once.** The community server keeps some files in two folders (usually an extra copy under Archives). The copy outside Archives is the one shown, and downloading any copy marks the preroll as downloaded. Pick the **Archives** category to see the copies stored there.
- **Readable titles.** Titles come from the file name with upload codes, file extensions and underscores removed ("Let's All Go to the Lobby!", "Fallout 01 Plex Pre-Roll (1080p)").

## Searching

The **Include AI-generated** option controls whether Community content from `/AI/` appears while browsing. Since 2.2.0, downloaded AI entries also display the **AI-generated** badge in [your Library](Preroll-Library#filtering) and its edit modal, using their saved Community source. Hiding AI in Community browsing does not hide or disable files you already downloaded.

1. Type a term in the **search box**. It matches titles and folder names, including inside longer words ("hallow" finds Halloween). Common themes also find related prerolls — "halloween" also finds "spooky" and "pumpkin", "turkey" finds Thanksgiving and autumn — but related words only count as whole words, and with **Best match** they're listed after the prerolls that contain your term.
2. Optionally pick a **platform** (Plex / Jellyfin / Emby) and a **length** to narrow results, and a **sort** (best match, shortest first, longest first).
3. Press **Enter** or click **Search**.

A length on its own is enough to search: pick **30 seconds or less** with an empty search box to list every short preroll.

## Browsing

The **Browse** controls let you explore the whole library by facet instead of a search term:

- **Category** — holiday, theme, etc.
- **Platform** — Plex / Jellyfin / Emby
- **Creator** — the contributor
- **Length** — see [Filtering by length](#filtering-by-length)
- **Sort** — name, newest, oldest, shortest first, or longest first

Pick any combination; results update immediately.

## Filtering by length

The **Length** filter (on both Search and Browse) keeps prerolls of a given running time:

| Choice | Keeps |
|--------|-------|
| 15 seconds or less | 0:15 and shorter |
| 30 seconds or less | 0:30 and shorter |
| 1 minute or less | 1:00 and shorter |
| 1 to 2 minutes | 1:00 to 2:00 |
| Over 2 minutes | 2:01 and longer |
| Custom range… | your own **Min** / **Max** in seconds (either can be blank); press **Enter** or **Show results** / **Search** to apply |

Lengths are compared as shown in the list, rounded to whole seconds, so a 30.4-second preroll (shown as 0:30) counts as "30 seconds or less". Each result shows its length next to the creator and category.

### Where lengths come from

The community server's directory listing has no running times, so NeXroll reads each file's length itself. After every **Refresh Index**, a background pass reads only the start (or end) of each file — one or two 4 KB requests per file, one file at a time — instead of downloading or probing whole videos. The first pass over the full library takes about 10 minutes; after that, only new or replaced files are read. Indexes built before this feature get their lengths the first time you open Community Prerolls.

While the pass runs, a line under the filters shows how many lengths are known so far. Until a preroll's length is known it is left out of length filters and sorted last by **Shortest first** / **Longest first**; the page tells you how many were left out. A few files can't be read this way (for example fragmented MP4s); they're tried again a week later, and opening one in the preview panel measures it individually.

Lengths are stored in `community_durations.json` beside the index and are kept across restarts and index rebuilds.

## Pagination

Results are returned a page at a time (your **item limit** sets the page size). When there are more results than fit on one page, a pager appears beneath the list:

> **Showing 1–50 of 1774** · **← Prev** · **Page 1 of 36** · **Next →**

- **Prev / Next** move through pages, keeping your current search or browse filters.
- Changing a filter, sort, or running a new search returns you to page 1.
- Increase the **item limit** to show more per page.

## Downloading a preroll

1. Click **Download** on any result.
2. A dialog lets you **rename** the file (the community's numeric ID prefix is stripped by default) and optionally **add it to a category**. If the category doesn't exist yet, choose **+ New category…** in the list to create it there.
3. Confirm — NeXroll downloads the file, generates a thumbnail, and adds it to your library.

Already-downloaded prerolls are marked so you don't grab duplicates. After a download you stay exactly where you were in the list (same page, same scroll position).

## Platform versions

When a preroll has Plex, Jellyfin and Emby versions, the row shows one chip per version, and a chip turns green with a check once you have that version.

- **Download** opens the dialog with a **Versions** list. The versions for the media servers you have connected are ticked: Plex only ticks the Plex version; Plex and Jellyfin tick both. With no server connected, the first version is ticked. Tick or untick any of them.
- With one version ticked you can rename it as usual. With several, each keeps its own name ("Adult Swim Plex", "Adult Swim Jellyfin") and they all go into the category you pick.
- Click a chip for a version you don't have yet to download just that one.
- **Previews** start on the version for your server. The preview panel and the full preview have a **Plex / Jellyfin / Emby** switch to watch the others; the length and file size follow the version playing, and both previews remember the choice. The preview panel's button downloads the version you're watching ("Download Jellyfin version").
- **Bulk download** gets the versions for your connected servers.
- The row counts as downloaded once you have the versions for your servers.

**Running more than one media server?** A category's prerolls play on every server, so a Plex-branded and a Jellyfin-branded version in one category would both play on both. To play each version only on its own server, download each server's versions into their own category (tick one version at a time) and use a sequence with a [Media server rule](Advanced-Sequences#media-server).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "You must accept the Fair Use Policy" | Accept the policy prompt on the Community Prerolls page |
| Search/browse returns nothing or is very slow | Build the index with **Refresh Index** (the slow fallback is rate-limited) |
| "Index build failed" right after starting | A build was already running, or the source was briefly unreachable — wait a moment and retry |
| Only the first page of results shows | That's expected — use the **Next** pager beneath the list, or raise the item limit |
| A new community preroll isn't showing | Run **Refresh Index** to re-crawl — the index is a snapshot — or turn on **Weekly refresh** |
| The hero says "refresh recommended" | The index is over a week old. It still works; refresh it to see newer uploads |
| I want a version a row doesn't tick | Tick it in the download dialog, or click its chip on the row |
| A length filter shows fewer prerolls than expected | Lengths may still be being read — check the progress line under the filters and search again when it finishes |

## See also

- [NeX-Up (Trailers)](NeX-Up) — automatic trailers for upcoming releases
- [Getting Started](Getting-Started)
