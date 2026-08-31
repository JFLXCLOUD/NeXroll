# Changelog

## [2.2.0-beta.4] - 08-31-2026 (beta)

> Holiday schedules now land on the holiday's real next date instead of whatever
> was typed, the schedule wizard no longer saves halfway through, and the
> calendar shows conflicts and overlap behaviour rather than drawing clashing
> schedules silently. No configuration change; new settings migrate on first
> start.

### Fixed

- **A holiday schedule never ran on its holiday.** Creating one demanded a start date and kept whatever was entered, because nothing resolved the holiday on save. The daily refresh meant to correct that only ever looked at the current year — so a holiday already past resolved *backwards* to a date behind us, and the schedule neither appeared on the calendar for its next occurrence nor fired. Dates are now derived from the next upcoming occurrence when the schedule is saved, and roll into next year once this year's has gone.
- **Choosing a holiday was guesswork.** Both fields were free text, matched by exact name against what the holiday calendar publishes for that country, so a name that country does not publish silently never resolved. Easter is not a US public holiday, for instance, so "Easter" plus "US" could never match. Country and holiday are now pickers listing what will actually resolve, showing the date each will run, and a name a country does not publish is refused with an explanation.
- **The schedule wizard created the schedule when you clicked Continue.** Moving from the content step to behaviour submitted the form: the Continue and Create buttons share one slot, so the button being clicked was turned into a submit button mid-click and the browser submitted as the click finished.
- **Creating a schedule gave no clear confirmation.** It now names the schedule and confirms the form has been cleared, behind an OK button.
- **Disabled schedules stayed on the calendar** as though they would still run. Conflict detection already excluded them; the calendar now does too.
- **The "COMING SOON" heading could not be recoloured** once a theme was selected, because the colour pickers hide in that mode and the heading follows the accent colour. It has its own picker now, alongside titles, dates, and "Available Now!".

### Added

- **Conflicts are visible on the calendar.** A banner counts open conflicts in the next 30 days, names the schedules involved, and links to the Conflicts page. Conflicts you have ignored stay ignored.
- **Overlap behaviour is visible too** — whether a schedule is Exclusive or Blends, shown on the day and week views and in month cell tooltips. Two schedules on the same day previously gave no hint which would win.
- **Match a preroll's length to its soundtrack.** Both generators read an uploaded track's real length and offer to set the duration to match, so a track plays in full instead of being cut off.

## [2.2.0-beta.3] - 08-30-2026 (beta)

> Trailer downloads work again on the Windows installer, which was shipping a
> five-month-old yt-dlp that YouTube had moved past. Coming Soon lists get the
> animated theme backdrop the preview was already showing, plus text size and
> per-role colours. Several Sequence Builder features that the scheduler has
> always supported now have controls. No configuration change; new settings
> migrate automatically on first start.

### Fixed

- **Trailer downloads failed with a SABR error on the Windows installer, and updating yt-dlp yourself made no difference.** The frozen build bundles its own copy, so a system-wide update never reached it — and the bundled one was 2026.03.17, five months behind YouTube's delivery changes. This build ships 2026.8.19, verified against a trailer that previously failed partway through with a 403. Docker was never affected: it installs a current yt-dlp on every build.
- **A sequence containing a pause could not be saved.** The validator rejected `separator` as an invalid block type even though the scheduler has always played them, so any sequence with one failed on save.
- **The Coming Soon backdrop rendered as a still** while the preview animated. The Studio now records the backdrop from the same canvas the preview draws, and the finished video moves the way the preview does. Regenerating after a sync has no browser, so it keeps using a rendered still.
- **A logo placed "right of heading" overlapped the heading**, and one placed below it landed on the first title in the list layout. Both now have their own space, and the list re-fits its rows around the logo.
- **Generating both layouts previewed only the grid**, despite producing two videos. Both are previewed now, stacked.
- The failure message for a blocked download was cut off mid-sentence, losing the one line that said what to do about it.

### Added

- **Text size for Coming Soon lists.** The item font and the row spacing scale together, and the list is capped so a larger size can never overlap the next title or run off the frame. The dynamic templates gain two larger steps.
- **Colours for titles, dates, and "Available Now!"** — the last of which had no control at all. Each is an override on top of the theme or manual colours, so it works either way, and each swatch shows the colour that will actually render.
- **Sequence Builder: how many prerolls a category block plays** (1–10). The scheduler always honoured this and the validator always checked it; nothing ever set it.
- **Sequence Builder: playback order for category blocks and NeX-Up trailers** — shuffled, or in order. Both were fixed to shuffled with no way to change them.

### Changed

- Generated content is one block type in the Sequence Builder rather than two. The item picker covers both: "always the latest" tracks whatever was generated most recently for a layout, while a named file plays that exact video every time.
- The Generator Studio header drops its blurb, and the Coming Soon preview drops the GRID / LIST badge.

## [2.2.0-beta.2] - 08-30-2026 (beta)

> Fixes two things beta.1 got wrong: the Library filter that was supposed to
> hide NeX-Up trailers never touched the grid, and the dashboard left a
> tile-sized hole in the top right on the Operations and Everything presets.
> Coming Soon lists gain the theme palettes and backdrops the dynamic templates
> already had, plus an optional QR code. No configuration change; the new
> settings columns migrate automatically on first start.

### Fixed

- **"Hide NeX-Up trailers" on the Library page did nothing to the grid.** It only controlled a separate read-only panel, which is invisible until NeX-Up registers downloaded trailers as real preroll rows — which it does whenever its storage path sits inside the prerolls folder, the layout NeX-Up Settings has recommended since 2.1.0-beta.3 to avoid the Docker path-mapping failure. Once that happens the trailers sit in the grid like any other preroll, and neither filter reached them: the generated-output filter looks for `dynamic_prerolls`/`coming_soon` paths and the NeX-Up Prerolls / Coming Soon Lists categories, while a downloaded trailer lands under `NeXup/movies` in NeX-Up Movie Trailers. The toggle now filters the grid, and selecting either trailer category still lists its contents.
- **The dashboard left an empty tile-sized gap in the top right.** Switching preset rebuilt the tile order from the preset's own list, which says which tiles are visible rather than how they sit — it placed two 8-column tiles back to back, and they cannot share a 12-column row, so the first sat alone. Operations and Everything both had further holes lower down. Every preset now fills whole rows: Essential 2, Operations 4, Everything 6, with nothing left over.

### Added

- **Coming Soon lists can use the theme palettes**, the same named themes the dynamic templates offer, instead of only three hand-picked colours. Choosing one hides the manual pickers it overrides.
- **Themed backdrops behind the posters and list.** Dynamic prerolls got their backdrop free by recording the browser canvas; a Coming Soon list is assembled server-side and also regenerates after a sync, where no browser exists, so the same six effects are now redrawn server-side and composited behind the content. The preview shows the live version of the same effect.
- **An optional QR code on Coming Soon lists**, rendered bottom-right on a white plate so it stays scannable on every palette — for putting a watch-party invite, a Discord link, or guest Wi-Fi on screen ahead of the feature.
- **Community preroll previews fall back through this server.** Previews load directly from the community server, so the browser has to reach that host itself — which a working download does not imply, since downloads are fetched server-side. Hotlink rules, an extension, or network filtering could therefore break every preview while downloads kept working. The player now retries once through NeXroll when the direct load fails, so the proxy costs nothing unless it is needed.
- The community preview pane stays in view while a long result list scrolls, and starts playing when a result is selected rather than waiting for a click.
- The Docker image is now built and smoke-tested on pull requests that touch how it is built, instead of only when a release is published.

### Changed

- The Coming Soon preview drops the GRID / LIST badge and matches the dynamic preview's frame.
- NeXroll reports its own version correctly. `backend/version.py` shadowed the root `version.py` on import, so 2.1.0-beta.3 described itself as 2.1.0-beta.2; the backend file now reads the root one, which stays the single source of truth.

## [2.2.0-beta.1] - 08-28-2026 (beta)

> Eight global themes replace the dark/light switch, the NeX-Up Generator Studio
> arrives with two new preroll templates (your own message, and a scannable QR
> code NeXroll generates), and a batch of controls that looked functional but
> were wired to nothing now do what they say. Also fixes a retention bug that
> quietly stopped NeX-Up from ever deleting a trailer. No configuration change;
> the new settings columns migrate automatically on first start.

### Added

- **Eight global themes, applied the same way dark and light were.** Midnight, Daylight, Cinema, Nocturne, Parchment, Terminal, Neon, and Carbon. Each declares a light or dark base, so anything that keyed off the old mode keeps working; the theme adds only color on top. Pick one from the swatch grid in Settings > General, or cycle with the topbar button. An existing dark/light preference migrates to Midnight or Daylight on first load, so nothing resets. The five section accents are re-tuned per theme so Library, Schedules, NeX-Up, Connect, and Community stay distinguishable at a glance without fighting the palette.
- **The NeX-Up Generator Studio**, a single workspace for building animated prerolls: template, timing, typography, colors, logo, soundtrack, and render profile, with a live animated preview that is the exact thing that gets rendered.
- **A Custom Message template.** Your own headline and an optional supporting line, with no fixed wording and nothing translated — for the intros the other templates cannot express ("Back in 5 minutes", a house rule, an announcement). The layout adapts to one line or two.
- **A QR Code template.** Enter a link and NeXroll generates the code, drawn on a white plate so it stays scannable on every theme, with an optional caption underneath. Useful for sharing a watch-party invite, a Discord link, or guest Wi-Fi details on screen. The preview shows the real encoded code, so you can test it with your phone before rendering.
- **A "Show NeX-Up trailers" filter on the Library page**, plus a More filters toggle that hides generator output by default, so the Library keeps showing your permanent collection rather than auto-managed files.
- **A real Filters panel on Schedules** (playback, behavior, conflicts-only), wired into the result list.

### Changed

- **Every page now shares the approved layout system** — Library, Schedules, NeX-Up, Connect, Community Prerolls, Settings, and their supporting pages — including the search toolbars, the schedule calendar, and the NeX-Up pages.
- **Light mode is a complete companion theme**, not a partial inversion: sidebar, headers, forms, cards, tables, status surfaces, inspectors, and dialogs all use dedicated light tokens.
- **The trailer retention setting says what it does.** It was labelled "Deleted trailer history / Keep cleanup records for diagnostics", describing a diagnostics feature that does not exist — so anyone adjusting it was scheduling deletion of their trailers while believing they were changing log retention. It now reads "Delete trailers after", states that it counts from the release date, and calls the 0 option "Never delete". The Your Trailers column reads "Deletes on" rather than "Retention", and an unscheduled trailer says "Not scheduled".
- **Failed trailer downloads now report the real cause.** The reported error used to be whichever strategy ran last, which is the browser-cookie one — so a trailer blocked for an unrelated reason surfaced "Could not copy Chrome cookie database" and sent people to fix cookies that were never the problem.
- The changelog shipped inside NeXroll now covers 2.0.0 and later. Earlier entries moved to `CHANGELOG-ARCHIVE.md` in the repo. The served file drops from 224 KB to 31 KB.
- The Generator's Render confidence panel and its Render button now derive from one list of requirements, so the panel can no longer read all-clear while the button stays disabled.

### Fixed

- **NeX-Up never deleted a trailer, so storage grew without bound.** Retention matched rows on `status == 'downloaded'`, but a completed download can sit at the model default of `pending` — with a real file, a `downloaded_at` and a `local_path`, yet invisible to every query keyed on that status, about a dozen of them. The Your Trailers page showed a removal date that silently passed and nothing happened; observed on a trailer 23 days past its window. Affected rows are repaired once at startup, and retention now keys on the download itself, excluding only in-flight transfers so nothing is deleted mid-write.
- **Failed downloads left `.part` and fragment files behind forever.** They accumulated in the storage folder, counted toward reported usage, and left yt-dlp trying to resume a partial that would only fail again. They are now cleaned up when a title exhausts every strategy, and existing leftovers are swept at the start of each sync.
- **NeXroll reported the wrong version number.** `backend/version.py` shadowed the root `version.py` on import, so 2.1.0-beta.3 shipped describing itself as 2.1.0-beta.2. The backend file now reads the root one, which is the single source of truth.
- **Themes stopped at the edge of the dashboard.** `--raised-bg` was referenced about 60 times and never declared, so every surface asking for it silently fell back to transparent, and the dashboard and sidebar each redeclared the whole palette with hardcoded values.
- **Connect and Path Mappings reported the server selected for editing rather than the one actually connected.** Path mapping counts also included the form's blank placeholder row, and Schedules counted every enabled schedule instead of the active ones.
- **Controls that did nothing now work.** Schedules' Compact/Detailed toggled a state no row read, and its Filters button navigated to the Conflicts page. NeX-Up's sync coverage bar was hardcoded to `enabled ? 5 : 2` and measured nothing (removed); the Upcoming week strip was inert divs and now filters by day; enable/disable used a three-dot menu icon instead of a toggle; the "Reconfigure sign-in" wizard existed only inside a dead render function, so the button flipped state with nothing to show; and Automatic trailer downloads always showed an ON badge even when off. On Video scaling, the row Scale button only selected the row instead of scaling it.
- **The Now Showing preview disagreed with the video it was previewing**, omitting the "on"/"at" connector between the title and the server name that the renderer has always written.
- Settings and NeX-Up Settings sat in two independent columns, so paired cards never matched height, and the Fallback Filler section used a different type scale from its neighbours.
- Save and Discard controls are gone from pages that save on change, along with the Connect page's diagnostics button, which did nothing.
- Opening category selectors for multiple Community Prerolls no longer links their choices together, its preview no longer shows a raw file path as the identifier, and its results-per-page control now refetches.
- Theme application runs before the browser paints, so the old theme no longer flashes while the app loads.

## [2.1.0-beta.3] - 08-21-2026 (beta)

> A full dashboard UI pass, plus a yt-dlp reliability fix (a startup race that could silently break every
> trailer download, plus a self-service update path so Docker users aren't
> stuck waiting on a NeXroll release to get past a YouTube change), a fix for
> the TMDB API key field, a read-only trailers view on the Library page, and
> guidance that catches a silent NeX-Up + Docker path-mapping failure before
> it reaches Plex.

### Changed

- **The approved dashboard design now spans the whole application.** Library, Schedules, NeX-Up, Connect, Community Prerolls, Settings, and their supporting pages share the dashboard's compact content frame, quieter charcoal surfaces, section-aware accents, controls, cards, tables, empty states, and responsive behavior.
- **Light mode is now a complete companion theme** rather than a partial color inversion. Sidebar navigation, page headers, forms, cards, tables, status surfaces, inspectors, and dialogs all use dedicated light tokens with readable borders and contrast.
- **Library now uses the approved hybrid layout.** The command-first search/filter/sort surface remains paired with grid and dense list views, list is the default for new browsers, and an optional persistent preview inspector can be enabled on the right without leaving the results. Existing browser view and inspector choices are remembered.
- **Schedules now use the Command Center direction with navigation kept exclusively in the sidebar.** Schedule pages use the green section identity, denser working surfaces, and page-level actions without restoring a duplicate horizontal navigation bar.
- **Modals and confirmation dialogs now share one visual system,** including the preroll editor, with consistent headers, spacing, controls, focus treatment, backdrops, responsive sizing, and dark/light presentation.
- Theme application now runs before the browser paints the app, preventing the old-theme flash while the dashboard loads.

### Fixed

- **Opening category selectors for multiple Community Prerolls no longer links their choices together.** Each result now keeps its own selected destination category, and completing one download clears only that preroll's choice instead of changing or resetting the other open rows.

- **NeX-Up trailer sequences could apply to Plex successfully and then simply not play, with nothing in the logs pointing at why.** This happened whenever the trailer Storage Path lived outside the prerolls folder in a Docker setup without a matching Path Mapping — NeXroll would push a container-only path (e.g. `/data/nexup_trailers/...`) that the media server's container had no volume for, so Plex accepted the setting but couldn't find the file. NeX-Up → Settings now suggests a storage path nested inside your existing prerolls folder (already reachable, no extra mount needed) and shows a dismissible warning with a one-click fix when your configured path is Docker-only and unmapped.
- **The TMDB API key field could feel impossible to type into.** Every keystroke saved the partial value to the server and then reloaded all NeX-Up settings from the response — with no debounce, a fast typist could fire off several overlapping save+reload round trips, and an earlier keystroke's response landing after a later one would snap the field back to a shorter, stale value mid-edit. Typing is now purely local; the key saves once, when you leave the field.
- **Clearing the TMDB API key field didn't actually clear it.** The old save call dropped empty values before they ever reached the server, so backing out a key you'd entered silently left the previous one in place. Saving now sends the field's real value, so an empty field is saved as empty.
- **Trailer downloads (and the Dependencies page) could break entirely after certain restarts**, failing every attempt with `module 'yt_dlp' has no attribute 'utils'` (or `'version'`) until the next restart. This came from a startup race: yt-dlp's first import could be triggered concurrently by the background NeX-Up sync thread and a request handler, and losing that race left the module partially initialized for the rest of the process's life. yt-dlp is now imported once, eagerly, before any background thread that touches it exists.

### Added

- **An "Update yt-dlp" button** on the Dependencies page for source/dev installs, so a stale yt-dlp can be refreshed without waiting for a NeXroll release. Docker and the Windows installer build both bundle yt-dlp with no separate Python environment to upgrade in place, so they keep pointing at "pull the latest image" / "install the latest release" instead.
- **A "Test Key" button** next to the TMDB API key field that checks the key against TMDB on the spot and reports valid or invalid right there, instead of needing to dig through logs to find out.
- **A "Show NeX-Up trailers" toggle on the Library page.** NeX-Up trailers are intentionally kept out of the Library — they live in their own auto-managed table with their own retention/cleanup schedule, separate from your permanent preroll collection — but that separation was invisible, so downloaded trailers just looked missing. The toggle lets you glance at them from Library without merging the two systems; managing a trailer (enable, delete, etc.) still happens from the NeX-Up page.
- Docker images now get their `:latest` and `:beta` tags rebuilt weekly, independent of NeXroll releases, so yt-dlp doesn't sit stale for weeks between releases while YouTube keeps changing underneath it.
- The Docker build now fails outright if yt-dlp installs in a broken state, instead of shipping it and finding out from a support report.

## [2.1.0-beta.2] - 08-19-2026 (beta)

> A follow-up to beta.1: the account controls are reachable from every page,
> and the dashboard no longer ships three pairs of tiles that showed the same
> thing. No database migration, no configuration change.

### Fixed

- **The Log out button was missing from the dashboard.** It was rendered only when the active page was not the dashboard, so the page the app opens on - the one most people sit on - was the one page with no way to sign out. It now appears in the header on every page.
- **Two user icons appeared in the header on every page except the dashboard.** The initials avatar and a second name chip with its own person icon were drawn side by side. The header now carries one avatar, whose tooltip names the signed-in account, and one Log out button. The Log out button also keeps its label instead of being squeezed into the header's 29px icon-button width; below 640px it collapses to an icon.

### Changed

- **The dashboard had two tiles named "Storage."** They rendered the same storage breakdown in two different styles. The duplicate is gone; one Storage tile remains.
- **"What's next" and "Upcoming schedules" were the same list twice, and they disagreed.** One dropped any schedule whose time had passed unless it was active at that moment; the other kept ongoing schedules with a past start and no end date. The same queue could therefore read differently depending on which tile you looked at. They are now a single **Upcoming schedules** tile using the more forgiving filter, and the number of rows follows the tile's width and detail level rather than being fixed at four.
- **"Currently Showing" duplicated the left half of "Current & next schedule."** It has been retired, and the two things it showed that the surviving tile did not - the preview button for what is applied to the server, and the playback mode, blend list, and gap-filler state - have moved into it.
- The Customize dialog's descriptions for the Scheduler, Schedule counts, and Media servers tiles now say they are detailed views of what System health summarizes, rather than reading as separate features.

Sixteen dashboard tiles become thirteen. Stored layouts that still name a retired
tile drop it on the next load, in the backend, in the browser's saved copy, and
at render time; no layout needs to be rebuilt by hand.

## [2.1.0-beta.1] - 08-18-2026 (beta)

> A redesigned dashboard, a data-loss fix in preroll deletion with a recoverable
> trash, an end to Plex hanging mid-preroll, no-repeat random NeX-Up rotation,
> and the removal of the dormant genre subsystem. Upgrade-safe: existing dashboard
> layouts, categories, schedules, and sequences are preserved.

### Fixed

- **A failed Community Prerolls scan could replace the local catalog with an empty index that still appeared current.** Empty scans now leave the previous index intact and report the build failure instead.
- **Plex could hang partway through your prerolls, failing to load the next trailer or preroll.** Plex does not take a snapshot of the preroll list when playback starts - it re-reads the setting as it advances through the list. NeXroll rewrote that setting on a timer with no idea whether you were mid-playback, so Plex would reach for an entry that no longer existed. This affected four separate paths: the 10-minute random-block rotation, schedule transitions, the 5-minute verification re-apply, and NeX-Up trailer retention deleting a file that was still in the active list. NeXroll now waits for playback to finish before changing prerolls, and never deletes a trailer that is currently in Plex's list. Since prerolls only take effect at the start of the next playback, waiting costs nothing. Set `NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES=1` to restore the old behaviour.
- **`GET /stats` always returned 404.** It was declared after the frontend catch-all mount, which shadowed it. Moved above the mount.
- **Deleting a preroll could permanently erase the original video file from your disk, with no warning and no way to get it back.** NeXroll decided whether a file was its own to destroy using the `managed` flag - but the library scanner sets that flag on everything it finds, so a file you copied into a category folder yourself and let NeXroll index was treated exactly like one NeXroll had created. The single-preroll confirmation only asked "Are you sure you want to delete this preroll?" and never mentioned your disk. Removing a preroll now leaves the file alone unless you explicitly ask for it, and files you do ask to delete are recoverable (see Added). `managed` keeps its real job of governing category moves and renames.
- **Importing the same folder a second time under a different category did nothing.** Files already in the library were skipped outright instead of being tagged with the category being imported.
- **The logo was missing from the login screen**, because its image assets sat behind the authentication gate that the login page itself has to get past. Static assets, plugin endpoints, and CORS preflight requests are now correctly exempt from the gate.
- **Files moved into a category folder outside NeXroll stayed uncategorized after a scan.** The scanner now assigns a category from the folder name when a row has none of its own, and never replaces a category you set deliberately.
- Thumbnails failed to resolve for prerolls whose stored path carried Docker's `prerolls/` prefix.
- The login and registration forms now say why a submission was rejected (password mismatch, length, character, and connection errors) instead of failing silently, and their fields are properly labelled for screen readers.

### Added

- **A redesigned dashboard.** The page now opens on what is actually happening
  rather than a wall of counters.
  - *Now showing* leads with the active schedule, its mode, preroll count, and
    timezone, plus a progress bar to the next change.
  - *What's next* lays the coming activations out on a timeline with Active,
    Next, and Upcoming badges.
  - *System health* scores the install out of 100 across the scheduler, media
    server, library, storage, schedule conflicts, and community index age. A
    check that could not be measured is reported as unknown and costs no points,
    so a fresh install does not open on an alarming number. Any hard failure
    holds the overall status at "degraded" rather than letting a pile of healthy
    checks average it away.
  - *Storage mix* breaks your disk use down across prerolls, NeX-Up trailers,
    thumbnails, and the database.
  - *Quick actions* puts refresh, scan files, NeX-Up sync, and rebuild
    thumbnails one click from the dashboard.
  - A new **Customize dashboard** dialog replaces the old inline edit mode. It
    carries three presets - Essential, Operations, Everything - along with
    per-tile width and detail level, visibility and reordering, tile density,
    and toggles for the greeting, the health note, and the date line.
  - `GET /system/health/summary` backs the health tile. Schedule-conflict counts
    are passed in by the frontend, which owns conflict detection; omitting them
    reports that one check as unknown instead of guessing.
  - **Upgrading keeps your layout.** Stored dashboard layouts are migrated from
    the old schema in place: your tile order, hidden tiles, per-tile sizes, and
    lock state all survive, with the new tiles inserted ahead of them. Nothing
    you previously hid is un-hidden. New installs start on the Essential preset.

- **AI-generated Community Prerolls filter.** Content under the community server's `/AI/` directory is excluded by default and can be included with a clearly labelled toggle. The preference applies consistently to search, browse facets, latest additions, and random selection.
- **Preroll trash.** When you do ask for a preroll's file to be deleted, it moves into a `.nexroll-trash` folder instead of being erased, and can be restored for 30 days. Set `NEXROLL_TRASH_RETENTION_DAYS` to change that, or `0` to keep trashed files indefinitely. The trash sits inside your preroll library, so trashing is an instant same-volume rename rather than a copy across a network share, and the library scanner never indexes it. Expired entries are cleared during the regular scan.
  - `GET /prerolls/trash`, `POST /prerolls/trash/{entry_id}/restore`, `DELETE /prerolls/trash/{entry_id}`, `DELETE /prerolls/trash?expired_only=true`
  - **Library > Trash** lists what is recoverable with each file's original location, when it was deleted, its size, and how many days remain before it is cleared. Restore puts the file back where it came from and re-indexes it; Delete erases one entry for good; Empty Trash and Clear Expired handle the whole folder. Files whose record of origin was lost are still listed, with restore disabled and a note to move them back by hand.
  - The delete dialog quotes your configured retention window rather than assuming 30 days, and a delete that takes the file now says the file is recoverable from Library > Trash.
- **Removals stay removed.** A preroll removed from the library while its file stays on disk is added to an ignore list, so the next scan does not re-import it and undo your change. Deliberately re-importing the file clears the entry automatically.
  - `GET /prerolls/ignored`, `DELETE /prerolls/ignored/{id}`, `DELETE /prerolls/ignored`
- **Library sorting.** The Library filter bar can now sort by Last added, Name, or Duration, in either direction. The direction control is labelled for the field it applies to - "Newest first", "A to Z", "Longest first" - rather than a bare arrow. Names sort in natural order, so `bumper2` comes before `bumper10` instead of after it. Prerolls whose duration was never probed sort to the bottom rather than appearing to be the shortest videos in the library. Your choice is remembered per browser, alongside the existing grid/list and page-size preferences.

### Removed

- **The genre-based preroll feature is fully gone.** Its settings UI was removed in v1.9.10, but the backend stayed live: a playback monitor ran every 60 seconds, twelve API endpoints remained callable, and the Plex webhook existed only to drive it. It also wrote prerolls at the worst possible moment - the instant a movie started - which is the same hang described above. Now removed: the scheduler's playback monitor, all `/genres/*` and `/settings/genre` endpoints, the `/plex/webhook` and `/webhooks/plex` receivers, the leftover "Recent Genre Prerolls" dashboard tile, and the dead frontend state. The `genre_maps` table and its settings columns are left untouched, so no data disappears and older backups still restore cleanly.

### Changed

- **Random NeX-Up trailer selections now cycle through the eligible pool before repeating.** Independent random draws could repeatedly choose the same one or two trailers even when many were available. Random sequence blocks now use a no-repeat shuffle bag during normal operation; when the pool is exhausted, NeXroll reshuffles it and begins a new pass. Plex continues to refresh its selected set on the safe periodic rotation, while Jellyfin and Emby advance the bag on each intro request. The sequence builder now describes that behavior accurately instead of promising a different trailer on every Plex playback.
- The dashboard greeting now includes the current NeXroll profile name, with a local desktop-account fallback when authentication is disabled.
- Fresh installations now start in dark mode. Existing browser theme choices are preserved.
- `DELETE /prerolls/{id}` no longer removes the file by default. Pass `delete_file=true` to move it to the trash. Externally mapped files are never deleted from disk even then, matching what the import screen has always promised.
- The delete confirmation now names the preroll and the folder it lives in, and carries an unchecked "Also delete the video file from disk" option. The confirm button only becomes "Remove and Delete File" once that box is ticked. If you have confirmations turned off in Settings, a delete never takes the file - skipping the prompt is not treated as consent to destroy it.
- Bulk delete uses the same dialog and reports how many files were moved to the trash.
- The Priority (1-10) note on the schedule form now reads "Higher priority number schedules win when multiple schedules overlap," making it explicit that a larger number is the stronger one. Applied to both the create and edit forms, and to the priority documentation in the wiki.
- The Library now opens sorted newest-first instead of in the order prerolls happened to be added to the database. Change it with the new sort control; your choice sticks.

## [2.0.5] - 07-28-2026

### Fixed

- **Overnight schedules (e.g. Friday 10 PM - 3 AM) could be attributed to the wrong day**, dropping out of their window right at midnight or activating a day early. Schedule-active checks now anchor to the occurrence's actual starting day for every recurrence type, not just yearly.
- **"Next run" could be wrong, or the app could error, for monthly schedules on days 29-31 and for yearly/holiday schedules landing on Feb 29.** The next-run calculation now searches forward using the real recurrence pattern (or the Holiday API for holiday-linked schedules) and skips invalid dates instead of assuming every month has the stored day.
- **A schedule made of only a sequence (no category) was wrongly logged as broken and never applied.** Sequence-only schedules are now recognized as valid.
- **Sequential-type blocks in a sequence were silently skipped everywhere** (schedule apply, filler apply, manual "Apply to Server", and the dashboard's current-intro resolution) - only "random" blocks ever resolved to a preroll. Sequential blocks now resolve correctly, in stable ascending order.
- **The scheduler's background verification loop used the host/container clock instead of your configured Settings > Timezone**, which could falsely flag disabled prerolls as "expected" in a permanent mismatch loop, and always assumed non-playlist mode - silently flipping a playlist-mode category back to random roughly every 5 minutes. All three are fixed; verification now respects your timezone and the category's actual playlist setting.
- Fixed a race condition where an API-triggered schedule check and the background scheduler loop could evaluate schedules at the same time and step on each other.
- Fixed a crash and stale dashboard state that could occur when a schedule transitioned to "no active schedule" or left a filler category.
- Holiday-linked schedule dates now refresh daily from the Holiday API instead of only resolving at evaluation time, and random-mode NeX-Up trailer blocks now rotate the same way random category blocks do.
- **Restoring a backup could silently break the links between schedules/sequences and the prerolls they reference**, since SQLite reassigns row IDs on restore. Backups now export preroll/sequence IDs and remap every reference on restore so schedules and fixed-sequence blocks keep pointing at the right prerolls (backup schema bumped to v3).
- **Deleting a preroll could leave dangling references** in saved sequences and schedule sequence blocks (previously only the schedule's direct preroll list was cleaned up). The delete path also no longer uses a raw `PRAGMA foreign_keys=OFF` query, closing a narrow window where a crash mid-delete could corrupt references.
- **Uploading a file as a "replace duplicate" deleted and recreated the preroll row**, breaking any schedule or sequence that referenced the old ID. Replacing a duplicate now updates the existing row in place instead.
- Preroll uploads, renames, and category moves are now race-safe under concurrent requests and roll back cleanly if a file operation fails partway through; renaming to a filename that already exists now returns a conflict instead of silently overwriting it; Windows-reserved/invalid filenames are rejected; case-only renames (e.g. `Movie.mp4` to `movie.mp4`) now work correctly.
- File hashes are now always recomputed on the server during upload, closing a duplicate-detection bypass where a client could supply a fake hash.
- Dashboard active/upcoming/inactive schedule counts and the `/scheduler/debug` view now use the same evaluation logic as the scheduler itself - previously they could miscount yearly, holiday, and recurring schedules.
- **The Conflict Detection Wizard could miss real conflicts and offer bad "quick fixes"**: it didn't always account for a lower-priority exclusive schedule still winning, its one-click blend fix could enable blending on only one side of a pair (which doesn't actually blend anything), and its priority-bump suggestion could push a schedule's priority above the max of 10. The wizard's logic has been rewritten to match the backend's conflict evaluation exactly.
- Escape key, focus handling, and background scroll-lock are now consistent across all dialogs (block editor, pattern import/export, sequence preview, and the ~18 modals in the main app), with a defined stacking order when more than one is open.
- Fixed a race in the Holiday Browser where rapidly switching country or year could display stale results from an earlier, slower request.

### Changed

- Editing a saved sequence now propagates to any schedule built from it and re-triggers the scheduler immediately, instead of leaving the schedule stale until its next natural evaluation.
- Schedule create/update validation is stricter: type and priority (1-10) are checked, a start date is required, end dates must fall after start dates (except for yearly/holiday schedules), and referenced categories/sequences must actually exist.

## [2.0.4] - 07-04-2026

### Fixed

- **Independence Day (and other fixed-date holidays) could show/schedule on the
  wrong day.** The Holiday Browser and holiday-linked schedules pull dates from
  an external calendar API, which reports the government's "observed" date
  instead of the real one when a fixed holiday falls on a weekend (e.g.
  Independence Day 2026 falls on a Saturday, so the API reports July 3rd with
  no way to recover the real July 4th). Known fixed-calendar holidays
  (Independence Day, Christmas, New Year's Day, Juneteenth, Veterans Day, and a
  few others for US/CA) are now corrected back to their true date, and now
  correctly show "Fixed date" instead of "Variable date."
- **A brief outage in the external Holiday API could permanently blank out
  holiday data for the rest of the app's uptime.** Holiday lookups were cached
  forever with no expiry, so a single failed request (e.g. right after
  container start, before networking is ready) locked in an empty/fallback
  result until the next restart - affecting the Holiday Browser, the
  scheduler's per-tick holiday resolution, and both the automatic and manual
  "Refresh Holiday Dates" paths. Holiday data now refreshes every 24 hours and,
  if a refresh fails, keeps serving the last known-good data instead.
- **A holiday schedule could resolve to the wrong holiday if its name was a
  substring of another** (e.g. "Christmas" silently matching "Christmas Eve"
  instead of "Christmas Day", depending on API list order). Matching now tries
  an exact name match first, only falling back to substring matching as a last
  resort.
- **Manually clicking "Refresh Holiday Dates" could roll back a schedule
  you'd deliberately pre-configured for next year's holiday** back to the
  current year's date - the automatic startup refresh already skipped
  future-dated schedules, but the manual button didn't. Both now share one
  implementation.
- Removed a dead, broken "create schedule from holiday" API path that never
  linked the schedule for yearly auto-updates and used a field name the
  frontend didn't actually send.
- **Manually-applied sequences (the Apply button, including ones that mix in
  NeX-Up trailers) never reached Jellyfin or Emby.** Applying a sequence wrote
  the resolved paths straight into Plex's preroll field, but for Jellyfin/Emby
  it only recorded that the apply "succeeded" without storing which sequence
  was applied anywhere the plugin could read — so the plugin's per-playback
  `/plugin/intros` request fell through to whatever category/schedule was
  already active, silently dropping the sequence (and any NeX-Up trailers in
  it). The plugin resolver now honors the manually-applied sequence for the
  same 15-minute window Plex respects.
- **Diagnostics bundles were missing scheduler activity and plugin/NeX-Up
  events.** The scheduler wrote its log lines to a different fallback
  directory than the rest of the app on Linux/Docker, so bundled `app.log`
  silently excluded every `SCHEDULER:` line; a bundle now also includes
  `logs/events.log`, dumped from the database-backed event log (plugin
  requests, scheduler decisions, NeX-Up activity) that the file log never
  captured to begin with.
- **Calendar text could become unreadable in dark mode** when a schedule's
  color was white, yellow, or another light color — every schedule chip and
  bar across the day/week/month calendar views (and the dashboard's "This
  Week" tile) hardcoded white text on top of the schedule's own color.
  Text color is now chosen for contrast against each schedule's actual color.

## [2.0.3] - 07-04-2026

### Fixed

- **Schedules could silently stop activating, with the dashboard's "Last Applied"
  time, "Currently Running", and "Currently Showing" all going stale.** The
  scheduler determined "is it time for this schedule to run" using the
  container/OS clock's own notion of local time instead of the app's configured
  Settings > Timezone — so if the two ever diverged (for example a container
  whose `TZ` is set but not actually honored by its base image), the scheduler
  could evaluate schedules against the wrong hour and even the wrong day, while
  the Calendar view (rendered in the browser) kept showing the correct day. All
  schedule-activity checks, `last_run`/`next_run`, and the manual "apply
  sequence/category" protection window now consistently derive "now" from
  Settings > Timezone instead of the ambient system clock.
- **Dashboard showed prerolls as "Uncategorized" even after tagging them with a
  category.** The Prerolls tile's "Uncategorized" count and "X of Y categories
  used" stat only checked a preroll's legacy single-category field, not the
  multi-category assignments used since v1.13.0 — so prerolls categorized only
  through the multi-category picker were counted as uncategorized on the
  dashboard even though Library > All Prerolls > Uncategorized correctly showed
  them as categorized. The dashboard tile now checks both.

## [2.0.2] - 07-01-2026

### Fixed

- **Thumbnails now work with a custom preroll folder outside the data directory.**
  When the Preroll Folder pointed at a path that isn't under NeXroll's data
  directory (common in Docker when aiming it at an existing library), thumbnail
  URLs resolved to a relative `..` path that the browser collapsed into an
  unmapped location — so every preroll showed a blank thumbnail even though the
  images existed on disk, and re-initializing didn't help. Thumbnails are now
  served through a resolver that works no matter where the preroll folder lives.
- **Log timestamps show in your local time.** The Logs page displayed timestamps
  shifted by your UTC offset (a few hours ahead, sometimes the wrong day) because
  the stored UTC time wasn't marked as UTC. Timestamps are now labeled UTC and
  rendered in the viewer's local timezone.

## [2.0.1] - 06-30-2026

### Fixed

- **Holiday-linked schedules no longer flip on and off when the Holiday API is
  briefly unavailable.** A holiday/yearly schedule resolved its date live on
  every scheduler tick, and a transient lookup failure made the schedule count
  as inactive for that tick — so the scheduler would fall back to another
  schedule/category and the wrong prerolls would play, alternating between
  correct and incorrect from one playback to the next (on Plex and the
  Jellyfin/Emby plugin alike). The active-check now falls back to the schedule's
  stored date when the live lookup fails, so a flaky API can't toggle it.

## [2.0.0] - 06-29-2026

**NeXroll v2.0.0** — the stable release of the v2 line, a top-to-bottom modernization of the app. Promotes beta.1 through beta.15; their individual notes are in CHANGELOG-ARCHIVE.md. Upgrading from v1.x is safe — your data carries over and the first-run wizard is skipped automatically.

### Highlights

- **All-new "Arr-style" interface** — a collapsible sidebar with built-in search and per-section colors, a redesigned dashboard with quick-action tiles, a first-run onboarding wizard, and deep-linkable (refresh-safe) URLs for every page.
- **Community Prerolls** — search and browse the community library by category, platform, creator, and upload date, with pagination, and one-click downloads.
- **NeX-Up** — trailers for upcoming Radarr/Sonarr releases with **cookie-free YouTube downloads** (a built-in PO-token provider) in a Plex-friendly H.264 format, plus a Coming Soon List generator and release-date-aware retention.
- **Plex, Jellyfin & Emby** — download and remotely configure the Jellyfin/Emby plugin from the Connect page; no shared mount required (the plugin streams and caches).
- **Security & operations** — Require Login now protects the entire API, logs auto-redact API keys/IPs on export, plus a built-in Factory Reset, a Storage Usage view, and Backup/Restore with live progress.

---

Older releases (2.0.0-beta.15 and earlier, back to 1.9.8) are kept in
[CHANGELOG-ARCHIVE.md](CHANGELOG-ARCHIVE.md).
