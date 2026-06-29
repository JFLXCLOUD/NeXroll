# Community Prerolls

The **Community Prerolls** page lets you search, browse, and download prerolls from the **Typical Nerds** community library — a large, free collection of prerolls contributed by the community — directly into your NeXroll library.

## Overview

NeXroll indexes the community library locally so search and browse are **instant** (milliseconds), then downloads any preroll you pick straight into your collection — optionally renamed and dropped into a category.

You'll find it in the sidebar under **Community Prerolls**.

## Fair Use Policy

Before you can search or download, you must accept the **Fair Use Policy**. This protects the Typical Nerds community from abuse (excessive scraping, rehosting, etc.). You'll see a one-time prompt on the Community Prerolls page — accept it to unlock search, browse, and downloads.

## The local index

Search and browse are powered by a **local index** of the community library, so they don't hammer the source server.

- The first time you open the page, NeXroll uses the index if present.
- Click **Refresh Index** to (re)build it. This crawls the community directory and can take a couple of minutes — run it occasionally (e.g. weekly, or when you know new prerolls were added).
- Without an index, NeXroll falls back to slow, rate-limited live requests, so building the index is strongly recommended.

> The index is stored with your NeXroll data (it persists across restarts and, on Docker, across image updates).

## Searching

1. Type a term in the **search box** (matches titles and keywords, with synonym expansion — e.g. "halloween" also finds "spooky", "pumpkin").
2. Optionally pick a **platform** (Plex / Jellyfin / Emby) to narrow results.
3. Press **Enter** or click **Search**.

## Browsing

The **Browse** controls let you explore the whole library by facet instead of a search term:

- **Category** — holiday, theme, etc.
- **Platform** — Plex / Jellyfin / Emby
- **Creator** — the contributor
- **Sort** — relevance, newest, oldest, or name

Pick any combination; results update immediately.

## Pagination

Results are returned a page at a time (your **item limit** sets the page size). When there are more results than fit on one page, a pager appears beneath the list:

> **Showing 1–50 of 1774** · **← Prev** · **Page 1 of 36** · **Next →**

- **Prev / Next** move through pages, keeping your current search or browse filters.
- Changing a filter, sort, or running a new search returns you to page 1.
- Increase the **item limit** to show more per page.

## Downloading a preroll

1. Click **Download** on any result.
2. A dialog lets you **rename** the file (the community's numeric ID prefix is stripped by default) and optionally **add it to a category**.
3. Confirm — NeXroll downloads the file, generates a thumbnail, and adds it to your library.

Already-downloaded prerolls are marked so you don't grab duplicates. After a download you stay exactly where you were in the list (same page, same scroll position).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "You must accept the Fair Use Policy" | Accept the policy prompt on the Community Prerolls page |
| Search/browse returns nothing or is very slow | Build the index with **Refresh Index** (the slow fallback is rate-limited) |
| "Index build failed" right after starting | A build was already running, or the source was briefly unreachable — wait a moment and retry |
| Only the first page of results shows | That's expected — use the **Next** pager beneath the list, or raise the item limit |
| A new community preroll isn't showing | Run **Refresh Index** to re-crawl — the index is a snapshot |

## See also

- [NeX-Up (Trailers)](NeX-Up) — automatic trailers for upcoming releases
- [Getting Started](Getting-Started)
