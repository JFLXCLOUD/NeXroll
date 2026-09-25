# Changelog archive

Release notes for the NeXroll betas that led to 2.2.0 (2.1.0-beta.1 through
2.2.0-beta.11), and for 2.0.0-beta.15 and earlier. These are kept for
reference only and are not shipped with the application; the current
changelog lives in [CHANGELOG.md](CHANGELOG.md).

## [2.2.0-beta.11] - 09-20-2026 (beta)

> A sequence can now decide what to play from what is actually about to happen -
> the genre of the film starting, the time of night, whether there are trailers
> worth showing at all - and you can draw it as a workflow instead of a list.
> NeXroll also keeps trailers for the movies you already own, so a sequence can
> run them the way a cinema does. Plus the reason a Radarr sync played the same
> trailer in front of every film.

### Added

- **Conditions on any block, in Advanced mode.** A switch at the top of the Sequence Builder adds a Conditions section to every block: the block plays **when** a rule holds, or **unless** it does, and you choose what plays **otherwise** - skip the block, play from a category, or play NeX-Up trailers. Four rules ship with it. **Trailers available** counts exactly what a trailer block would play, so a Coming Soon slide can drop out of the sequence when there is nothing coming. **Time of day** takes a window and optionally the days it applies to, and handles a window running past midnight the way schedules already do. **Genre** matches what is about to start against genres suggested from your own Jellyfin and Emby libraries. **Movie or episode** separates films from TV. Rules combine with **all** or **any**, and a summary reads the whole thing back in plain English. Conditions apply in the Sequence Builder, in a sequence built inside a schedule, and in filler, and they survive export, backup and restore.
- **Every rule is honest about the server it runs on.** Jellyfin and Emby ask NeXroll what to play at the moment playback starts, so every rule is checked live against the title that is actually starting. Plex is handed a list in advance and never says which film it is about to play, so genre can't be known there - and rather than guess, NeXroll treats an unanswerable rule as not met and plays the block's Otherwise. Trailer and time rules do work on Plex, re-checked every 10 minutes. Blocks using a rule only Jellyfin and Emby can answer are labelled as such in the list, in block settings and on the canvas, and the builder shows a panel spelling out what each server can check. One sequence therefore serves a household running Plex in the lounge and Jellyfin for the kids without building it twice.
- **Flow view: the sequence as a workflow.** The second switch draws the same blocks as a node canvas running left to right from playback starting to the film starting. Pan, zoom, a minimap for long sequences, and add a block from the **+** on any connection. Dragging a node moves it on the canvas and nothing else: playback order is changed deliberately, with the earlier and later arrows beside the selected step, so tidying the layout can never quietly reorder what your viewers see. Arrows on the connections show the running order, **Auto arrange** puts everything back, and where you place things is remembered with the sequence, separately for Simple and Advanced. A conditional block becomes an **IF** node with a green *true* branch to the block and a dashed orange *false* branch to its Otherwise, rejoining afterwards. It stays one sequence seen two ways, so you can switch back and forth freely, and both switches are remembered.
- **Preview shows what each viewer will actually get.** Preview checks conditions as if a film were starting now and lists every conditional block as playing, playing its alternative, or skipped, with the reason. For a sequence using genre rules, **Preview as** switches between Plex, where the genre is unknown, and each genre the sequence uses, so you can check both cases before you schedule it.
- **Library Trailers: trailers for the movies you already own.** A NeX-Up section of its own, kept deliberately apart from Coming Soon - those trailers exist until a film arrives, these exist because it has. It uses trailer files already sitting beside your movies, in the naming Plex, Jellyfin and Emby all use, and never moves or deletes them; for the rest it can download from the link Radarr holds. Choose films by hand from a poster wall of your library, or by filters that combine genres, age ratings, language, release years, IMDb and Rotten Tomatoes scores, how recently they were added and Radarr tags, with quick presets for family night, horror night, critically acclaimed and classics. Storage and count limits apply only to downloads, and once a limit is reached each sync rotates a few of the oldest out for films that have none yet. Changing your filters never deletes a trailer you already have.
- **A Library trailers block.** Play a set number, shuffled or newest first, optionally limited to certain genres, and on Jellyfin and Emby matched to **the same genre as the film that's starting** - so a horror film opens with trailers for other horror films you own. The trailer for the film about to play is never picked for it.

### Fixed

- **Trailers downloaded by the NeX-Up automatic sync never played.** The scheduler recorded each download without a status, so the row kept the database default of `pending` while the file itself downloaded perfectly. Every part of NeX-Up that picks a trailer asks for `downloaded` ones, so the scheduler's trailers were passed over: a library synced only on the schedule had a pool of nothing, and one synced by hand once played that single trailer in front of every film while dozens of valid ones sat on disk. The files were real and reachable throughout - the sync also files each one into your preroll library, which is why they looked fine everywhere except the place that chose between them. Both the movie and the TV sync now record the download properly, and NeXroll repairs the existing records on its next start, so the full pool comes back without any manual database work. The log names how many it recovered. This dates back to the release NeX-Up first shipped in, which means every automatically synced trailer since then has been inert on any install older than 2.2.0-beta.1. Thanks to @noahphex for tracking it to the line.
- **Automatically synced trailers were missing their artwork and details.** The same records were also written without a poster, backdrop, description, IMDB id or release type, all of which the manual and full-sync paths save. The generated Coming Soon list draws the poster, so an automatically synced film appeared there as an empty tile beside the ones added by hand. On the TV side the season number and network were dropped too. They are all kept now.
- **The repair for stuck trailers could promote a half-finished download.** Since 2.2.0-beta.1 NeXroll has mended these records on startup, but it swept in trailers marked as still downloading and never checked the file was really there - so an interrupted download became a trailer NeXroll considered ready to play, and a part-written file could end up in front of a film. The repair now requires the file to exist on disk and leaves an in-progress download alone.
- **An automatically synced TV trailer was never cleaned up after the show aired.** The pass that expires trailers for shows that have already premiered only looked at records marked `downloaded`, so the ones left `pending` by the bug above were skipped and accumulated. Fixing the status fixes their expiry with it.

## [2.2.0-beta.10] - 09-16-2026 (beta)

> The dashboard told Jellyfin and Emby users their server was not connected while
> the Connections page, the Servers tile and the scheduler all agreed it was. Then a
> week of automated beta testing against Jellyfin 12, Jellyfin 10.11 and Emby found
> more of the same: a plugin the app needs but never tells you how to install, a
> sequence quietly playing fewer blocks than it shows, a save that looks like a
> dropped click, and a library that counts items it then refuses to list.

### Fixed

- **The dashboard reported "No media server is connected" on a perfectly healthy Jellyfin or Emby.** The System health tile decided whether a server was connected by reading the API key column on the settings row, but nothing puts a key there: `/jellyfin/connect` and `/emby/connect` persist only the address and hand the key to the secure store, and `_migrate_legacy_api_keys()` clears the column on every startup for any older install that still had one. The check could therefore never pass. It cost 30 of the 100 health points, so an otherwise flawless install opened on a score of 70, a red banner saying prerolls could not be applied, and a Servers tile beside it naming the server, address and version it was connected to. Plex was affected too wherever the connection was made through `/plex/connect`, which nulls the token column by the same design. Connection state is now resolved from the secure store as well as the database, and a registered plugin counts on its own, so a plugin-only Emby with no stored address reads as connected rather than missing. Nothing was ever actually wrong with the affected servers: the scheduler reads its credentials from elsewhere and had been applying schedules to them throughout.
- **Links that named a setting dropped you at the top of the Settings page.** "Enable fallback filler" appears on the Schedules banner, the dashboard tile and the schedule draft; three of the four went to Settings and left you to scroll past a 400-entry timezone list to find the control you had just clicked a link for. A scroll-and-highlight helper already existed and one link used it - all four do now.
- **The schedule wizard accepted a blank start date for three steps, then refused it.** You could leave Timing empty, complete Content and Behavior, and only learn on the final Create click that a date was required - from a small toast that did not point back, on a step whose field carried no required marker. Each step is now checked as you leave it, and the date is marked required where it genuinely is (monthly schedules do not need one).
- **"Generated videos" in the Preroll Generator did nothing.** It scrolled to the Recent section, which renders nothing when the current tab has no output, so the click silently found no target. It now scrolls when there is something to show and otherwise says whether the videos are on the other tab or nothing has been generated yet.
- **"Choose storage" looked like a button and was not.** The badge naming the one thing blocking rendering was a plain label, while the control sat on another page with nothing linking to it. It now takes you there.
- **Forgetting your password could strand you with no visible way back in.** NeXroll has always been able to reset an admin password with no login, from the machine it runs on. But the "Forgot password?" link was only shown when the browser was on that same machine - and almost nobody browses to their own server that way - so a locked-out user saw a sign-in box with no recovery of any kind and reasonably concluded there was none. A beta tester lost a full day to exactly this. The link is now always shown; from another computer it explains that the reset has to run on the server and gives the exact command, including the Docker form. The reset itself stays restricted to the local machine, which is what makes it safe to describe. The wiki's Locked Out section, which previously only suggested using a second admin account, now documents it as well.
- **The Library advertised more prerolls than it would list.** The header counted every row in the database while the grid hides NeX-Up generator output by default, so a library of six with four generated items read "Total prerolls 6" above a list of two. Testers reported this three sessions running as the "All" filter undercounting. The header now counts what the list will actually show - "2 of 6" - and names the hidden ones on hover. An earlier attempt only handled the case where the list came out completely empty, which is why it survived.
- **"Last backup" always said "Ready".** Nothing recorded when a backup was taken; the value was a literal string where a date belongs, so it read as a fact and told you nothing. Producing a backup now stamps the time, and the page shows it - or "No backup yet" on an install that has never taken one.
- **The dashboard kept claiming "Gap filler active" after Fallback Filler was switched off.** The badge read a property of the category, which stays true regardless, rather than the setting that actually controls filler. On a seasonal setup that implied Halloween content could still be served in November.
- **The Connections page opened on Plex even when you run Jellyfin or Emby, hiding the plugin setup entirely.** The server tab defaulted to Plex and only changed if you clicked a card's name - and a card that is already connected shows a Disconnect button where a disconnected one shows "Setup", so nothing suggested the card was a way in. Everything behind that panel was therefore unreachable for the people who needed it most, including the NeXroll Intros plugin's detect-and-configure step, which is the only way to make prerolls play on Jellyfin or Emby. A beta tester installed the plugin successfully, saw it Active in Jellyfin, and still could not link it across two sessions with the app fully searched and the wiki checked. The page now opens on the server you actually have connected, a connected card offers "Settings & plugin" alongside Disconnect, and picking a tab yourself is never overridden.
- **Every dashboard tile told assistive technology its contents were disabled.** The tiles are drag-sortable, and dnd-kit marks a sortable `aria-disabled="true"` when sorting is off - which is the normal state, outside Arrange mode. Those attributes were spread onto the tile regardless, so a screen reader announced "Refresh data", "Scan files" and every other control inside a tile as a disabled control, and anything else honouring ARIA refused to operate the dashboard at all. A tile that merely is not draggable right now is not a disabled control, so it no longer claims to be one. Mouse users were unaffected, which is why this survived so long.
- **Connecting to Emby or Jellyfin accepted any API key at all.** Both checked only that the server answered on its public info endpoint, which needs no credentials, so an invented key returned "Connected successfully" and was saved - and the user found out when nothing ever played. Both now prove the key against an authenticated endpoint and say plainly that the server rejected it, while an unreachable server is still reported as unreachable rather than as a bad key.
- **"Clear Prerolls When Inactive" named Plex on installs that have never used Plex.** It now names your media server generically, as Coexistence Mode beside it already did.
- **Time-of-day schedules ran against UTC instead of your own clock.** A "kid-friendly before 8pm" rule stayed active all evening while the rule meant to replace it never started - on a US Eastern install the scheduler was four hours out, and further for anyone else. The cause was two `settings` rows where there should only ever be one: about twenty places create the row with a `if not setting: create` check, and on a fresh database a first page load fires enough endpoints at once that two of them can both find nothing and both insert. Startup wrote the container's `TZ` into one row; the scheduler read the other, which still held the `UTC` column default. Duplicate settings rows are now merged back into one at startup, keeping the most recently written values and recovering anything only the discarded row had, after which the existing TZ detection lands on the single surviving row. Anyone affected is repaired on the next restart, and the timezone is worth checking in Settings afterwards. A latent crash in that same TZ check - `a and not b or c` binding as `(a and not b) or c`, so an install with no settings row at all raised instead of skipping - is fixed too.
- **Jellyfin's plugin repository URL appeared nowhere in NeXroll.** beta.9 published update catalogs so the Intros plugin could keep itself current, but the URL existed only in the wiki and the repository's own README. A Jellyfin user inside the app was told they needed the plugin, offered a manual ZIP, and never told where the catalog was - so the plugin could not be installed the supported way, and prerolls never played. The Install the Plugin panel now leads with the repository URL and a copy button, picking the Jellyfin 12 or 10.11 catalog to match the server it is actually talking to, with the manual DLL steps kept as a fallback.
- **Emby said "Direct connection" while nothing could play.** Emby plays prerolls only through the NeXroll Intros plugin, so a connected server with no plugin puts nothing on screen. The Connections page called that state "Direct connection", which reads as success; it now reads "Connected - plugin not detected" and, when no plugin has checked in, explains what to install, where Emby's Cinema Mode settings are, and that "Include trailers from my movies in my library" must be ticked or Emby ignores the intros NeXroll registers.
- **The What's New dialog printed an internal release-planning note to every user.** The changelog is rendered as markdown by a renderer that does not emit raw HTML, so an HTML comment at the top of the file was displayed as ordinary prose, naming internal working files. HTML comments are now stripped before the changelog is served, which also keeps notes-to-self safe to write in the file.
- **Two red Plex error banners appeared for people with no Plex server.** `/plex/status` reports `not_configured` for anyone who has never set Plex up, and the Connections page rendered that as an error - so a working Emby connection sat directly above two failures. A never-configured Plex is the normal state on the page whose job is to configure it, and is no longer reported as a problem.
- **The sequence preview silently dropped any block it could not fill.** A NeX-Up trailers block between two fixed prerolls simply vanished from playback, renumbering the blocks after it, so a three-block sequence played as two with no error, no notice, and the block still sitting in the editor looking configured. The preview now names the blocks it skipped and why.
- **A NeX-Up trailers block claimed trailers it did not have.** The block summary showed the count it asks for as though it were the count available, so a block read "2 trailers" on an install with none downloaded - and then played as nothing. It now reads "up to 2 trailers".
- **An empty sequence reported "~1m" and "1 variation".** A floor of one was applied before checking whether there were any blocks at all.
- **"Create schedule" left you on a blank form.** The schedule was created, but the wizard cleared itself in place, which is indistinguishable from a click that did nothing - and invites a second click and a duplicate schedule. Saving now lands on My Schedules, where the new schedule is.
- **A library holding only generated prerolls looked empty.** The grid hides NeX-Up output by default while the header counts it, so a library whose only item was a generated Coming Soon list showed "1 preroll" above "No prerolls found". The empty state now says how many generated items are hidden and offers to show them.
- **"1 item need attention".**
- **A Plex that was down took Jellyfin and Emby down with it.** NeXroll reaches media servers two opposite ways: Plex is a push, where NeXroll writes paths into Plex's own preroll setting and that call can fail, while Jellyfin and Emby pull, their plugin asking NeXroll what to play at the moment of playback. Both were collapsed into one true/false answer, so an unreachable Plex reported failure and the filler, blend and sequence paths then skipped recording which category was active - the very state the plugin reads. The category marker the plugin uses was worse: it was only ever written on the branch taken when Plex was absent entirely, so a household running Plex alongside Jellyfin got a correct Plex and a Jellyfin stuck on whatever it last heard. Each channel now reports for itself, applying succeeds if any server took it, and clearing reaches both - a cleared Plex used to leave Jellyfin still advertising the old category. The scheduler log now names the server, because "apply failed" says nothing useful once more than one is configured.
- **The sequence builder invented its own numbers.** Estimated duration was two minutes per block and variations were twelve per block, regardless of what the blocks contained. Two fixed clips totalling 23 seconds were announced as "4m 10s", a single deterministic block claimed twelve variations, and an empty builder said "0 blocks / estimated 1m 0s". Both figures now come from the actual blocks and your library: an estimate resting on content chosen at playback time is marked with a tilde rather than implying a measurement, and a sequence that plays identically every time reports one variation.
- **A negative trailer count saved without complaint.** The field carried `min="1"`, which a browser treats as advice, so typing -5 stored -5 and the sequence reopened as Ready. It clamps on input now, like the blocks either side of it.
- **Path Mappings looked mislabelled to anyone not on Plex.** The page is headed "(Plex)" and genuinely is Plex-only - Plex plays prerolls from its own filesystem and needs a path it can resolve, while the plugin streams the file to Jellyfin and Emby and never sees one. Rather than relabel a correct heading, the page now says so when Plex is not connected.
- **The password reset instructions named the wrong port.** The recovery panel printed `localhost:9393` literally, so anyone whose container maps a different port was handed a command that reaches nothing on their own machine. It takes the port from the address you are already on, and says a `docker exec` needs the container's internal port instead.
- **A successful trailer download announced itself twice.** The server returns a full sentence and the toast dropped it into the slot meant for the title, producing `Downloaded trailer for "Downloaded trailer for The Love Hypothesis"`.
- **"1 blocks".**
- **A generated preroll in a sequence never played on Jellyfin or Emby.** Reported by a user whose three-block sequence - generated preroll, trailer, library preroll - always started at the trailer. The plugin endpoint that Jellyfin and Emby read resolved that block from `template` and `theme`, while the sequence builder records the `filename` of the video you pinned, so the block matched nothing and was dropped without an error; the same sequence played correctly on Plex, which reads the filename. Underneath that, the name it reconstructed was wrong in every version: the generator writes `<template>_preroll.mp4` and never puts the theme in the filename, so the older `<template>_<theme>_preroll.mp4` lookup could not match a real file even when the block did carry both. Sequences built in earlier releases therefore lost their generated block silently. Both paths now look for the filename first and the shape the generator actually produces second, and say in the log what they tried when a generated preroll is missing.
- **The Library said "2 of 7" and never explained the other five.** Generated prerolls and downloaded trailers are hidden from the list by default, which is reasonable, but the list said nothing about it unless it happened to be completely empty. With the "All" filter selected, a library of seven items showed two rows and a header counting seven - reported four times across three sessions as the All filter undercounting. The list now says "2 prerolls — 5 more hidden", and the count is a button that shows them.
- **Typing a NeXroll address without the "#" led somewhere strange.** `/dashboard` served a separate hand-written admin page with its own styling and its own path-mapping controls - a stale parallel NeXroll that people reasonably took for the product. Every other page address returned a bare JSON 404, which reads as a broken install rather than a mistyped URL. Both now land in the app.
- **NeXroll insisted on exactly one media server.** Connecting a second was refused at the button ("Disconnect Jellyfin first"), and any setup that got past that was reported as a *conflict*: the Apply button greyed out, the dashboard tile turned red, and the Connect page told you to disconnect all but one. Nothing in the backend ever required it - the scheduler pushes to Plex and serves Jellyfin and Emby through the plugin independently - so a household with Plex in the lounge and Jellyfin for the kids was being made to choose for no reason. Connect as many as you run: whatever you schedule now applies to all of them, and the pages name the servers instead of calling them a conflict.
- **Emby users had no in-app way to install the plugin they cannot play prerolls without.** Emby plays prerolls only through the NeXroll Intros plugin, and the panel that explains that linked to GitHub's raw view of the default branch - asking a media server that often has no outbound internet to fetch a DLL that tracks `main` rather than the build it is running beside. Jellyfin has been served its plugin by the running NeXroll since beta.9; Emby now is too, with the panel checking first so it falls back to the GitHub link rather than offering a download that 404s.

## [2.2.0-beta.9] - 09-11-2026 (beta)

### Added

- **A separate Jellyfin 12 plugin build.** NeXroll Intros 1.15.0.0 targets Jellyfin 12 and .NET 10. The existing 1.14.0.0 package remains available for Jellyfin 10.11. The release workflow packages both variants with distinct filenames.
- **Jellyfin plugin update repositories.** Separate catalogs for Jellyfin 12 and 10.11 support automatic plugin updates. Existing manual installs need the one-time migration described in the plugin repository guide.

### Fixed

- **Valid Jellyfin API keys could be reported as lacking permission on Jellyfin 12.** NeXroll sent the legacy token headers that Jellyfin 12 disables by default. The connector now uses the supported `Authorization` header when connecting, loading saved keys, migrating legacy keys, and saving replacement keys. This fixes connector authentication; Jellyfin 12 also requires the separate compatible plugin build for preroll playback.

### Changed

- **Updated NeXroll branding throughout the interface.** The sidebar, sign-in screen, and first-run setup now use the new icon beside the original wordmark, with matching light and dark theme logos. New asset URLs prevent old cached logos from carrying over after an update, and the fallback browser favicon now matches the app icon.
- **A refreshed GitHub README.** Updated UI screenshots, setup guidance, TypicalNerds community credit, and Ko-fi support links introduce the upcoming 2.2.0 release.

## [2.2.0-beta.8] - 09-08-2026 (beta)

> Endpoints for the NeX-Up generators, so a dynamic preroll or a Coming Soon list can be
> rendered without opening the interface. Two External API endpoints that raised 500 on
> every call are fixed. The Library's quick filters now show what clicking them will
> actually return, and Community Browse says when its filters are loading or why they
> cannot load at all. The header no longer breaks apart on a folded phone, and NeXroll
> now ships a real app icon at every size a launcher, browser tab or home screen asks for.

### Added

- **The NeX-Up generators are reachable from the External API.** `POST /external/nexup/dynamic` and `POST /external/nexup/coming-soon` render server-side through FFmpeg, so they work headless. Rendering a five second preroll takes around two minutes, well past most client and proxy timeouts, so these return `202` with a job id and `GET /external/nexup/jobs/{id}` reports progress. On success the job carries the `preroll_id` of the registered file, ready to pass to `POST /external/schedules`. `GET /external/nexup/capabilities` lists the templates, themes and limits the render endpoints accept, and `GET /external/nexup/generated` lists what has been produced.
- **One render runs at a time.** The generators write a fixed filename per template and per layout, so concurrent renders would fight over the same output file.
- **Generating over the API no longer changes the interface's saved generator settings.** The values are restored after the render unless `save_as_default=true` is passed; clicking Generate in the interface still saves them, as before.
- **A proper app icon set.** The manifest previously advertised the wide NeXroll wordmark as a square marked `any maskable`, so launchers cropped it, and the Apple touch icon tags named sizes the files did not have. The set is now exported from a glyph master: `any` and `maskable` are declared separately, the maskable art stays inside the W3C safe zone, there is a 180px Apple touch icon, and a multi-resolution ICO covers browser tabs and Windows shortcuts. Existing installed shortcuts may need removing and adding again to clear the operating system's icon cache.
- **`/docs`, `/redoc` and `/openapi.json` group the supported endpoints.** All 284 routes previously sat undifferentiated under a bare title, with the ones meant for integrators buried among the interface's own. The External API and API Keys endpoints are now tagged and described.

### Fixed

- **`GET /external/schedules` returned 500 on every call**, and `GET /external/active-schedules` did the same as soon as any schedule was active. Both read `schedule_type` and `enabled` off the database row, but those are the request-schema names; the columns are `type` and `is_active`.
- **A dynamic preroll generated through the FFmpeg path was never registered in the library**, so the file existed on disk with no library row and nothing that could schedule it. The Coming Soon generator had always registered its output.
- **The Library's "Uncategorized" quick filter counted prerolls it then refused to show.** The count came from the raw library while the grid hides NeX-Up generator output and downloaded trailers, and "uncategorized" is not one of those categories, so the exemption never applied — a library whose uncategorized files were all NeX-Up ones showed a count and then an empty grid. Every quick filter now counts through the same visibility rules the grid uses.
- **A quick filter could offer a category with nothing in it**, landing on an empty grid whatever you did. Empty categories are no longer offered.
- **"All" did not mean all.** The search box feeds the same filter state the chips do, but All neither cleared it nor accounted for it, so a search with no matches left "All" highlighted over an empty grid with nothing to say why.
- **Community Browse showed no filters until you interacted with the page.** They were loaded as a side effect of the Fair Use check, which runs at most once per page load and only if that check is still pending when Community is first opened; anything that made it miss left the card absent for the session. They now load whenever the page is open, and the card says whether it is loading, or why it cannot load — a community index past its refresh age cannot be read, which previously removed the card silently.
- **The Matched quick filter did not reset the others**, so its count described the whole library while the grid showed the intersection. It now behaves like every other chip in the row and carries a count.
- **The header came apart on a folded phone.** On a cover screen around 320 to 344 pixels wide, the account controls grew taller than the fixed header and the avatar wrapped onto a line below it, overlapping the page. The header now grows to fit on narrow screens, its controls meet the 44 pixel minimum touch target, and below 480 pixels the health badge moves to its own row with its text intact rather than being reduced to a coloured dot. Library and NeX-Up summary tiles drop to two columns on narrow screens instead of forcing the page wider than the screen.
- **"1 prerolls".**

### Changed

- **The API wiki page documented an authentication header the server does not accept.** `Authorization: Bearer` returns 401; the server reads `X-Api-Key` or an `api_key` query parameter. The Troubleshooting page gave the same wrong header as the fix for a key that will not work. The API page also documented eight endpoints that do not exist, among them `GET /version`, `GET /settings` and `POST /settings/test-plex`; each now points at the route that replaced it.

## [2.2.0-beta.7] - 09-06-2026 (beta)

> Almost every number and date the interface showed about your schedules was
> arrived at a different way in each place that showed it, and several of them
> were wrong. Conflicts are counted once, from the list the Conflicts page
> actually renders. Daily and weekly schedules work out when they next run.
> The Upcoming tile stops saying everything is playing now. Coexistence Mode
> says when it has switched filler off instead of leaving it silently
> outranked, and the faded watermark is visible again. A preroll change held
> back while Plex is playing now says so, rather than filling the log with
> warnings about a guard that is working.

### Fixed

- **A preroll change held back during playback was logged as a failure, 246 times in one evening.** Plex resolves the next preroll from its preference as playback advances, so rewriting that preference mid-playback makes it hang; the scheduler deliberately waits for playback to finish. Every apply site reported that wait as "Failed to apply", which made a guard doing exactly its job look like a broken scheduler. A deferral is now reported as a wait, and a genuine failure still reads as one.
- **Nothing told you a preroll change was queued behind playback.** For most of two hours the dashboard alternated between "Blending" and "Nothing applied" while the truth was neither: the blend indicator is driven by `last_run`, which is only stamped on the ticks where the blend's random pick lands on the schedule already applied. The Current and next schedule tile now says a change is held until playback finishes, and how long it has been waiting.
- **The dashboard reported conflicts that the Conflicts page had nothing to open.** Four places counted conflicts using two different detectors: one analyses a whole recurrence year and only compares schedules of the same type, the other looks thirty days ahead and pairs every type. The tiles counted overlaps outside the page's window, so clicking through showed "No unresolved conflicts". Every count now comes from one list, and it is exactly what the page lists.
- **The schedules page header could read "7 schedule conflicts" while the dashboard read one.** Three summary counts included rows the Conflicts page classes as notes rather than conflicts — deterministic outcomes where one schedule always wins — and counted them as things needing attention.
- **Conflict badges stayed on schedules after the counts said zero.** The per-schedule badges were still asking the year-long detector. Nine call sites that ask about a saved schedule now read the shared list; the two that ask about a schedule being typed into the form still run detection directly, because a draft has no id and is not in the saved list yet.
- **Ignored conflicts came back on every page load.** The ignore list was only fetched when the Conflicts tab was opened through one of its buttons, so a fresh page started with an empty list, counted every ignored conflict again, and showed nothing under Ignored. It loads at startup now.
- **The System health tile never consulted the ignore list at all**, and built its pair key by sorting numerically and joining with a colon while the list is stored under the shared helper's string sort joined with a dash — so an ignored pair could not have matched even if it had looked.
- **Daily and weekly schedules never worked out when they next run.** The calculation only handled monthly, yearly and holiday types; the others fell through and returned nothing, so `next_run` stayed empty and the rows fell back to `start_date` — which on a recurring schedule is just the day it was created. A daily schedule could advertise a next run two days in the past.
- **A schedule past its end date could still name a date it would never run on.** No branch of the calculation checked `end_date`. All of them do now, and nothing in the past is displayed as a next run regardless.
- **The Upcoming schedules tile said every schedule was running now.** It decided a schedule was active by asking whether its `start_date` had passed and its `end_date` had not. Monthly, weekly and yearly schedules keep the `2000-01-01` sentinel in `start_date`, so the first half was true for all of them, and with no end date the second half never bit either. It asks the recurrence now, including ranges that run past midnight.
- **Filler could be fully configured, shown as enabled everywhere, and never play.** Filler runs in the moment no schedule is active, and Coexistence Mode claims that same moment for the other preroll manager, so the scheduler returns early. The calendar stops drawing filler it will not play, My Schedules says filler will not run and why, and the Coexistence setting explains the clash where the choice is made. Clear Prerolls When Inactive has the same relationship and is handled the same way. Filler is deliberately left switched on rather than forced off — it is outranked, not wrong.
- **The Faded Watermark option looked like it removed the logo.** The mark was overlaid after the text at fifteen percent opacity, so it was invisible while very slightly washing over the words, and choosing it also switched the header from the single-line "COMING SOON TO" back to two lines for no visible reason. The list layout now composites the watermark between the background and the text, which is where the option has always claimed it goes.
- **QR corner rounding squared itself back off.** The plate was rounded and the square code drawn straight over the top of it. The code is clipped to the plate's shape now, capped short of where a corner arc would start eating the position markers, so the plate can reach a full circle without costing a scan.

### Changed

- **Clicking a day on the calendar opens it.** The month view only responded on the small date number and the week view not at all. The whole month cell opens that day, week day headers are buttons that do the same, and empty space in a week column does too. Schedule chips still open the schedule.
- **The Upcoming tile shows when a schedule fires, not just which day.** The hour comes from the recurrence rather than from `next_run`, which carries the right date but not necessarily the right time, and each row shows its window so "All day" and "7:30 PM - 11:00 PM" are told apart at a glance.
- **Recent generated cards show when each file was last written**, relative on the face and exact in the tooltip. A regeneration that came from a sync is marked as automatic — the filesystem cannot tell you that on its own, since the modification time is the same whether a sync wrote the file or someone pressed Generate.
- **The QR panel carries a live sample of the real code**, large enough for the module style to read. The three styles looked identical because at roughly three screen pixels per module on the stage, a square, a squircle and a circle are the same shape. The sample also draws the code over the plate colour at its opacity and rounding, so it is clear that an opaque code background covers all but a rim of the plate.

## [2.2.0-beta.6] - 09-04-2026 (beta)

> The week and day calendar views never showed a monthly schedule at all, and
> both calendar views are rebuilt around that fix. Both generators gain a
> typeface picker with nine fonts that ship with NeXroll, plus custom video
> backdrops. Three faults in how random sequence blocks picked prerolls are
> fixed, including one that dropped blocks from a blended playlist entirely.
> New settings migrate on first start.

### Fixed

- **The week and day calendar views never showed a monthly schedule.** Both read the hour from `start_date`, which monthly schedules deliberately store as the sentinel `2000-01-01`, so every schedule landed at midnight — and the grid began at 08:00 and drew nothing before it, sampling only five hours in between. Both views are rebuilt on a continuous 24-hour axis driven by the recurrence pattern, with overlapping schedules in side-by-side lanes, all-day schedules in their own row, and a current-time line.
- **A Coming Soon list lost its animated background after a sync.** The moving themed backdrop exists only because the browser records it from the preview canvas and sends it with the render, and that recording was written to a temporary file and deleted. Auto-regeneration has no browser, so it fell back to the still the generator bakes itself. The recording is kept now, keyed by theme, and reused whenever no clip has been uploaded.
- **"Match length to the soundtrack" would not stay switched on, and the duration reverted with it.** Saving clamped the duration to 30 seconds and a music bed usually runs for minutes, so the value came back changed and the toggle read as off. The dynamic generator had the same fault at 20 seconds. Both now allow a matched length through.
- **A random sequence block whose count covered the whole category played in the same order every time**, falling through to the sequential path and returning prerolls in database id order.
- **Blended schedules silently dropped sequential blocks.** Blend used its own resolver that only handled random blocks, so those prerolls never reached Plex, and it had no missing-file filter, so a preroll whose file was gone was still published.
- **The dashboard preview could list prerolls that never play.** It used a third copy of the block resolver that ignored whether a preroll was enabled, ignored the block's count, and dropped sequential blocks.
- **Uploaded fonts were missing from system backups**, so a restore left the generators pointing at a typeface that was not there and quietly fell back to the template default.
- **The month calendar shifted every date by a column** once filler bars were added, because CSS grid positions explicit items before automatic ones and the day cells flowed around them.
- **The dashboard's week tile started on Sunday while the calendar page started on Monday.** Both use the same helper now, and the same arithmetic for working out what filler covers.
- **The simple schedule form's Playback selector never worked.** Choosing Sequential wrote a field nothing read and left the real one untouched, so playback stayed on random. A schedule could also be labelled Sequential while actually playing at random.
- **Jellyfin and Emby ignored a sequence block that inherited its schedule's category**, which the Plex path had always honored.
- **Jellyfin and Emby were served nothing when filler was a dynamic preroll.** The plugin resolver is a separate path from the one that writes Plex's preroll string and only understood category, sequence and Coming Soon fillers, so the branch fell through and no intro played while Plex played the preroll correctly.
- **Separator blocks were skipped inside sequences on Jellyfin and Emby.** On Plex a separator becomes a generated black gap of the configured length; through the plugins the sequence played straight through without the pauses its author put in.

### Added

- **Typeface choice for the dynamic and Coming Soon generators.** Nine fonts ship with NeXroll — Bebas Neue, Anton, Archivo Black, Oswald, Roboto Condensed, Cinzel, Playfair Display, Lora and JetBrains Mono — so the same set is available on every install rather than only what the host happens to have; a Docker container otherwise carries two. You can also upload your own TrueType or OpenType file, which works identically in the preview and in the finished video. Only fonts the server can actually render are offered, because Coming Soon lists are rebuilt without a browser.
- **Custom video backdrops for both generators**, with a dimming control and a live preview, replacing the generated theme background with your own footage.
- **The QR Code template can be styled.** Choose square, rounded or dotted modules, set the code and background colours, make the background transparent so the theme shows through, overlay your uploaded logo in the middle, and control the plate behind it with a colour, an opacity and corner rounding. The three position squares stay solid and the quiet zone is always kept, so styling on its own cannot stop a scan; a warning appears if the two colours are too close for a scanner to separate.
- **Match a preroll's length to an uploaded video clip**, alongside the existing soundtrack matching.
- **Filler is drawn on the calendar** as a continuous band across the hours it covers, a bar spanning consecutive uncovered days in month view, and its own lane on the dashboard tile — so it is clear what plays in the gaps.
- **A dynamic preroll can be used as the fallback filler**, and My Schedules links to the setting when filler is off.
- **Seasonal loading-screen quotes** that rotate through the year.

### Changed

- **Genre-based preroll mapping is gone from the documentation**, along with the code behind it. Nothing had called the resolver for some time, and the wiki still described a toggle and settings that were no longer in the app.
- **A schedule's redundant shuffle flag is removed.** Playback mode has always been decided by the playlist setting, which selects the delimiter Plex uses; the shuffle field was written and returned but read by nothing.
- **The endpoint that set NEXROLL_INTERCEPT environment variables is removed.** It required administrator rights to write four machine-level variables that nothing reads.

## [2.2.0-beta.5] - 09-01-2026 (beta)

> Backups were missing every setting you had, so restoring one on a new machine
> came back with nothing connected. The first-run wizard could send you away
> from itself with no way back. Community Prerolls gains multi-select and bulk
> download. Docker installs get a Path Mappings step and trailer-storage
> guidance during setup, and the help button now opens the wiki page for
> whatever you are looking at. New settings migrate on first start.

### Fixed

- **Database backups contained no settings at all.** Every connection, credential, path mapping, generator default and dashboard preference was absent, so a backup restored on a new machine came back with no media server, no Radarr or Sonarr, and every preference at its default — while the UI card promised it exported "settings". All of it is in the backup now.
- **Restoring destroyed five settings on every run, including on the same machine.** The restore clears the category and sequence references before deleting those tables and never put them back, silently losing your NeX-Up category, TV category, filler category, filler sequence and active category. They are restored and their ids remapped, so they follow the rows even though the numbers change.
- **System backups omitted generated prerolls and Coming Soon lists.** NeX-Up storage sits beside the prerolls folder rather than inside it, so the "comprehensive" backup never touched it — yet library entries point straight at those files. Restoring elsewhere produced entries with nothing behind them. Generated output and brand assets are included now; downloaded trailers are deliberately left out because NeX-Up re-fetches them and they are usually most of the folder.
- **The system ZIP carried a second, reduced copy of the database export** that claimed to be the current format while omitting preroll duration and hashes, category playback mode, schedule priority and blend flags, holiday date ranges, and genre rules entirely.
- **Signing in with Plex from the setup wizard left the wizard for good.** The button completed onboarding and dropped you on the Connect page, and nothing could bring the wizard back short of a factory reset. Plex sign-in now runs inside the wizard, and Settings, System has a Run Setup Wizard button that reopens it without resetting anything. A factory reset returns you to it reliably too.
- **Unticking "Require login after setup" did nothing.** Registering the first user enables authentication server-side, and the wizard only ever sent the choice when it was ticked, so login was always required afterwards. The wizard also signs the new admin in, rather than finishing onto a login screen for the password just typed.
- **Every trailer preview on the Upcoming page played the same clip.** The match compared two fields that are both empty on the Movies tab, which is true for the first row in the list, so that one was always returned. Season number is taken into account for TV as well.
- **The Show/Hide filter for NeX-Up trailers ignored freshly downloaded ones**, because it matched on category alone and a new trailer has none yet. It matches on path too.
- **Duration and file size on the community preview panel always read "Unknown".** The index carries neither; both are resolved on demand now.
- **The Preview button on library thumbnails did nothing** when the preview panel was open — it only moved the panel's focus, which clicking the row already did. It always opens the full player.
- **The Upcoming schedules tile spilled past its own edge.** A dashboard rule cancelled the list's scrolling while leaving its height capped, so every row past the cap painted outside the card.
- **Installing the PO-token provider could fail with an npm ENOENT.** A provider left running by an earlier NeXroll held its own folder open, so the cleanup before the copy quietly failed and the new files landed one directory deeper than expected. The installer stops a provider it did not start, refuses to copy onto a folder that survived removal, and repairs the nested layout left by a previous attempt.
- **The provider dependency offered "Install" when it was already installed**, because the UI checked a field the backend never returned.
- **The audio "match length to the soundtrack" option never appeared** after uploading a track — the control needs the track's length, which only arrived on a full settings reload.
- **Settings, System did not match the rest of the app** — nine different text sizes, fifty hardcoded colours that ignored your theme, and inner panels painted the same colour as the card behind them. The Theme tile also named the light or dark base rather than the theme you had chosen, so six of the eight themes displayed identically.

### Added

- **Multi-select and bulk download on Community Prerolls**, with a batch category, live progress, and a five-second gap between downloads. The server-side limiter now waits its turn rather than rejecting, and paces globally rather than per client, so two browsers cannot double the request rate the community server sees.
- **Poster views for NeX-Up**, on both Upcoming releases and Your Trailers, alongside the existing list and calendar. Missing artwork is backfilled from Radarr and Sonarr.
- **A Path Mappings step in first-run setup for Docker installs.** It explains why a container needs the translation, offers the container's real mount points as one-click choices, and translates a path so you can see the answer your media server will be given.
- **Trailer storage in first-run setup**, on Windows and Docker alike, with a check reporting whether your media server will actually be able to open files there.
- **Autoplay preview in the Preroll Library**, matching the community panel.
- **The help button opens the page you are on.** Schedules opens the scheduling guide, Connect the connection guide, and sub-pages deep-link to the right section.

### Changed

- Radarr, Sonarr and media-server credentials are masked as they are typed in the setup wizard.
- Database backups now also carry ignored paths and community templates. User accounts and API keys remain excluded by design.
- The wiki gains Dashboard, Preroll Library, Connect and Backup and Restore pages, and NeX-Up and Troubleshooting cover the 2.2.0 features.

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

## [2.0.0-beta.15] - 06-29-2026 (beta)

> Community Prerolls pagination, sticky preview volume, one-click Jellyfin plugin
> download, and plugin playback settings from the Connect page. Upgrade-safe.

### Added

- **Community Prerolls pagination.** Search and Browse now page through the
  *entire* library (the results header shows the true total) with Prev/Next and
  a page indicator, instead of only ever showing the first page.
- **Download the Jellyfin plugin from NeXroll.** The Connect page's Download
  Plugin link now serves the full plugin **zip** (DLL + meta.json + thumb.png)
  straight from your NeXroll — bundled into the app and Docker image — so it
  always matches your build and a bare DLL never fails to register.
- **Plugin playback settings from the Connect page.** Set the Jellyfin plugin's
  **Max Intros** (0 = play the whole sequence), Enable for Movies/Episodes, and
  request timeout from NeXroll and push them to the plugin.

### Fixed

- **Community Prerolls remembers your place.** Downloading an item no longer
  snaps the list back to the top — you stay on the same page and scroll position.
- **Preview volume sticks.** The preview players remember the last volume you set
  instead of resetting to max every time.

### Docs

- Refreshed the wiki for v2 (new Community Prerolls page, updated Home/Getting
  Started/NeX-Up/Jellyfin/Emby, factory reset + log redaction notes).

## [2.0.0-beta.14] - 06-26-2026 (beta)

> NeX-Up trailer retention fix, dashboard polish, and a sidebar with per-section
> colors. Upgrade-safe.

### Fixed

- **NeX-Up trailers are no longer auto-removed before the movie releases.**
  Retention was measured from a trailer's download time, so a trailer grabbed
  early for an upcoming movie could be deleted before the film was even out (and
  the "Removed" date shown on Your Trailers could fall *before* the release
  date). Retention is now measured from the later of download time and release
  date, in both the displayed removal date and the actual cleanup.

### Changed

- **Sidebar sections now have their own accent colors** for the active item
  (Library/violet, Schedules/emerald, NeX-Up/gold, Connect/sky, Community/rose,
  Settings/indigo); Dashboard is unchanged.
- **Dashboard weekly calendar:** the "Filler" fallback row is gone; when filler
  is enabled it's shown as a compact badge above the calendar instead. The empty
  state's "Create a schedule" text is now a link to the schedule creator.
- **NeX-Up Trailer Storage Path is now set via Browse only** — the field is
  read-only so a mistyped path can't silently create a stray folder.

## [2.0.0-beta.13] - 06-25-2026 (beta)

> NeX-Up release-date fixes: dates no longer drift by a day, and "Digital Only"
> now actually hides non-digital trailers. Upgrade-safe.

### Fixed

- **NeX-Up release dates no longer appear a day off.** Dates were rendered with
  the browser's timezone, so a date-only value could shift the displayed day by
  one (and disagree with Radarr). Release/air dates are now shown as a stable
  calendar date — the actual TMDB date, identical regardless of viewer timezone.
- **"Release Date to Use = Digital Only" now hides non-digital trailers.** The
  preference previously only affected which trailers got *downloaded* on the next
  sync; trailers already downloaded under another setting (e.g. a theatrical-only
  movie) kept showing in the list and playback reel. With Digital Only selected,
  those are now hidden from the trailers list and from playback (non-destructive
  — switch the preference back and they return). A note shows how many are hidden.
  Downloaded trailers now also record their release type so the filter recognizes
  them.

## [2.0.0-beta.12] - 06-25-2026 (beta)

> Thumbnails now reliably appear and stay put, plus several Community Prerolls
> and UI fixes. Upgrade-safe.

### Fixed

- **YouTube PO-token downloads now actually work in the Windows build.** The
  yt-dlp bgutil plugin was never bundled into the packaged app — only the empty
  `yt_dlp_plugins` namespace shipped — so the token provider ran but yt-dlp
  couldn't use it, and the System page reported "Components installed; provider
  not healthy yet" even when the provider was running. The plugin modules are now
  bundled, and the "is the plugin installed?" check no longer gives a false
  negative in the packaged app.
- **Preroll thumbnails reliably display.** Three issues fixed: (1) thumbnails for
  files whose name contains `...` (e.g. community prerolls) returned "Invalid
  path" and never loaded — the path-traversal guard wrongly rejected any name
  containing `..`; (2) a leftover **service worker** cached thumbnails so they
  showed stale/blank and a hard refresh couldn't clear them — the app now
  unregisters it and serves preroll media fresh from the network; (3) after
  rebuilding thumbnails the browser kept showing the old cached image — a
  cache-bust now forces the regenerated thumbnail to load.
- **"Reinitialize Thumbnails" shows its status on the Library page**, where the
  button is, instead of only in the dashboard quick-actions — with processed /
  generated / cleaned counts and a spinner while it runs.
- **Community auto-match "failed to link" fixed.** Linking a preroll to a chosen
  community match failed because the community ID (a URL path with slashes and
  encoded characters) was sent in the URL; it now goes in the request body.
- **Index-build progress shows on the Community page** regardless of where the
  rebuild was started (dashboard button or Community page), and clicking Refresh
  during a build attaches to it instead of erroring "already in progress".

### Added

- **Edit Preroll modal shows the file's full path** (under "Current file").
- **Download Diagnostics button on the Logs page** (Settings → Logs), alongside
  the JSON/CSV export — the same redacted bundle as the System page.

## [2.0.0-beta.11] - 06-23-2026 (beta)

> Fixes Community Prerolls indexing (the library moved servers) and adds a
> **Browse** view to explore it by category, platform, and creator. Upgrade-safe.

### Added

- **Browse the Community Prerolls library.** A new Browse panel filters the
  library by **category** (Holidays, Seasons, Clips, Community, Archives…),
  **platform** (Plex / Jellyfin / Emby), and **creator** — each with counts —
  and sorts by name, or by newest/oldest after a re-index. Results feed the same
  preview + download cards as search.

### Fixed

- **Community Prerolls indexing works again.** prerolls.uk became a website and
  moved its files to mirror servers (`usa`/`uk.prerolls.uk`); NeXroll's default
  still pointed at the old address, so a rebuild found nothing. It now
  auto-resolves an active mirror from the published server list, and the server
  picker shows/uses the right one — the custom-URL **Save** no longer resets your
  choice when the field is left empty.
- **The "Index build failed" false alarm.** The progress UI attached to the build
  stream *before* starting the build, so it read the previous run's end state and
  reported failure while the build actually ran fine. It now starts the build
  first, then streams progress. Capturing each file's date during the crawl also
  fixes the previously non-functional "Latest" row (after one re-index).

## [2.0.0-beta.10] - 06-20-2026 (beta)

> Makes beta.9's junk-thumbnail cleanup actually work, and teaches TV trailer
> downloads to fetch the *upcoming* season's trailer. Upgrade-safe.

### Fixed

- **Junk TypeScript thumbnails are now actually removed.** beta.9's cleanup
  missed records whose stored path was *relative* (the common case), so the
  `*.d.ts.jpg` / `*.ts.jpg` thumbnails kept coming back. Matching is now by path
  segment (catches absolute and relative paths alike), and a new sweep deletes
  orphaned thumbnail files left on disk. "Reinitialize Thumbnails" now reports
  how many junk records and orphan files it cleaned, and the same cleanup runs on
  every library scan.

### Changed

- **Smarter TV trailer search — fetches the upcoming season.** When a show's
  next season is greater than 1 and TMDB only offers the original (season-1)
  trailer, NeXroll now searches YouTube for that specific season (e.g. *"The
  Bear season 5 official trailer"*) instead of downloading the season-1 trailer.
  Falls back to the show-level trailer only if the season search finds nothing.

## [2.0.0-beta.9] - 06-19-2026 (beta)

> Adds a built-in **Factory Reset** for returning NeXroll to a fresh-install
> state — handy for clean re-testing without reinstalling. Upgrade-safe.

### Added

- **Factory Reset (Settings → System → Danger Zone).** Resets NeXroll to a
  fresh-install state: empties the database (schedules, categories, prerolls,
  settings) and clears saved connections, dropping you back at first-run
  onboarding. A confirmation modal (type `RESET` to proceed) lets you optionally
  also delete downloaded trailers, uploaded prerolls, and the PO-token provider
  from disk. Tables are emptied rather than dropped, so the full schema is
  preserved and the reset takes effect immediately without a restart.

### Fixed

- **TypeScript files no longer show up as prerolls/thumbnails.** A scan from
  before the scanner learned to skip `node_modules` could import the PO-token
  provider's `*.ts` / `*.d.ts` source files as prerolls (`.ts` doubles as the
  MPEG-TS video extension), and "Reinitialize Thumbnails" then generated a
  thumbnail for each — e.g. `index.d.ts.jpg`. NeXroll now purges these junk
  records (and their thumbnails) during any scan and at the start of a thumbnail
  rebuild, and the scanner skips `*.d.ts` outright.
- **Faster Windows install.** The installer now checks whether the Visual C++
  runtime is already present and skips the `winget` step when it is, instead of
  invoking winget on every install (which was slow to start even when it had
  nothing to do).

## [2.0.0-beta.8] - 06-19-2026 (beta)

> The headline fix: beta.7's **cookie-free YouTube downloads now actually work**.
> The PO-token provider was crashing on startup with the bundled Node, so trailer
> downloads still hit the "not a bot" wall — the bundled Node is updated and the
> provider launches correctly now. Trailers also **download in a Plex-friendly
> format (H.264)** so they play as prerolls instead of silently failing on AV1.
> Plus real **Backup/Restore progress**, a **Storage Usage** view, a clearer and
> more honest alternate-trailer + preview flow, **automatic log redaction**, and
> fixes for a PO-token install that could make the app unresponsive. Upgrade-safe.

### Added

- **Backup & Restore show real progress.** Creating a system backup now streams
  the archive as it's built and shows a live progress bar with percentage and
  MB (instead of a spinner that sat there during large exports); database backups
  stream too. Restores show a real upload percentage, then an "extracting &
  restoring" phase. A system backup also no longer sweeps in the PO-token
  provider's thousands of dependency files.
- **Storage Usage on the Storage page.** Settings → Storage now opens with a
  breakdown of disk use across prerolls, NeX-Up trailers, thumbnails, and the
  database — a segmented bar plus per-location cards showing size, share of
  total, and path. Same data as the dashboard Storage tile, expanded.
- **Scheduler tile shows "Last applied."** The dashboard Scheduler tile replaces
  the "Firing today" counter (which was always 0 for everyday schedule types)
  with the most recently applied schedule and when — a reliable confirmation that
  the scheduler is actually running and acting.
- **Logs auto-redact sensitive data.** API keys, tokens, and IP addresses are
  now stripped from logs everywhere they leave the app — the log viewer, JSON/CSV
  export, and the diagnostics bundle — so logs can be shared safely. Loopback
  addresses are kept for debugging; version numbers and timestamps are untouched.

### Fixed

- **Cookie-free YouTube downloads now work (provider no longer crashes).** In
  beta.7 the PO-token provider exited immediately on the bundled Node.js
  (`ERR_REQUIRE_ESM`), so trailer downloads still ran into YouTube's bot wall and
  the System page showed a provider error. The bundled Node is updated to a
  version that runs the provider, and existing installs launch it correctly too.
  Docker images get the same update. After updating, the **YouTube Downloads**
  status on the System page goes green and trailers download again.
- **Trailers download in a Plex-friendly format (H.264).** Downloads previously
  preferred AV1, which Plex can't direct-play as a preroll — so a trailer would
  apply but never appear before playback. Trailers now download as H.264 so they
  actually play. *Existing AV1 trailers should be re-downloaded to benefit.*
- **The alternate-trailer flow is clearer and honest.** When the default trailer
  can't be downloaded, NeXroll no longer flashes an alarming error before opening
  the picker — the picker now shows the real reason inline. And when you pick an
  alternate, it downloads **exactly that video** (it used to be able to quietly
  substitute a different one if your pick failed), so what you choose is what you
  get.
- **Older trailers preview again.** Previews now self-heal a trailer's file path
  when the storage folder moved or the file was re-downloaded with a different
  extension, and match more robustly — so older trailers play in the dashboard
  preview instead of being silently skipped. When a clip genuinely can't play
  (e.g. an older AV1 file), the preview explains why and suggests re-downloading.
- **A PO-token install could make the app unresponsive — fixed.** The provider
  now installs alongside the database rather than inside the Prerolls folder, and
  the media scanner skips dependency folders (`node_modules`, the provider dir),
  so installing it can no longer flood the library with thousands of files to
  thumbnail.
- **Installer bundles the Visual C++ runtime**, which the provider's native
  dependency can require on a bare Windows install.

## [2.0.0-beta.7] - 06-17-2026 (beta)

> A new **cookie-free YouTube download method** (a PO-token provider clears the
> "not a bot" wall, with a pick-an-alternate-trailer flow when one's unavailable)
> and Backup & Restore hardening (restores no longer fail partway, nothing goes
> missing on the round-trip, bundle previews play, two archive path-traversal
> holes closed), plus schedule-time, dashboard, and NeX-Up trailer-retention
> fixes. Upgrade-safe.

### Added

- **New YouTube download method — browser cookies are no longer the default.**
  Trailer downloads now use a Proof-of-Origin (PO) token provider (bgutil) that
  automatically clears YouTube's "Sign in to confirm you're not a bot" challenge,
  so trailers download — on request *and* during sync — **without exporting any
  browser cookies**. Cookies / sign-in are now an **Advanced** option, used only
  for the occasional age-restricted trailer; previously they were the primary
  (and frequently-broken) method. The old "YouTube Authentication" panel is now a
  **"YouTube Downloads"** card that shows a live **Installed / Enabled / Working**
  status with a one-click **Test** that mints a real token. Docker images bundle
  the provider; on Windows it installs in one click from the System page (sets up
  Node.js + the provider). Internally, the previous ~30-strategy yt-dlp cascade —
  much of it player clients YouTube has since disabled — was replaced with a lean,
  token-aware path.
- **Pick an alternate trailer when the default can't be downloaded.** If a
  movie/show's trailer is unavailable (region-blocked, removed, age-restricted,
  …), NeXroll now offers the **top 3 YouTube alternatives** to **preview** in an
  in-app player and choose from — nothing downloads automatically. Download
  errors now explain the real reason (e.g. "this video is unavailable in your
  country") instead of a generic "try again," and a candidate that fails is
  flagged so you can try another.
- **NeX-Up Trailer Retention is now enforced.** The Trailer Retention (days)
  setting was saved but never acted on — downloaded trailers were only removed
  once their movie/show arrived in your library. The scheduler now runs a
  time-based cleanup (at most hourly) that deletes downloaded movie and TV
  trailers older than the retention window, based on when they were downloaded
  (0 = keep forever). The **Your Trailers** page now also shows each trailer's
  removal date on movie and TV cards, in both detailed and list views.

### Fixed

- **Schedule start/end times no longer drift.** Enabling or disabling a
  schedule, or picking a holiday from the holiday browser, could shift its
  start/end time by your timezone's offset every time (e.g. 9:00 AM creeping to
  1:00 PM, and occasionally rolling to the next day). The times you set now stay
  put until you change them.
- **A schedule you turned off no longer stays pinned as "Currently Showing."**
  A disabled or expired schedule could remain displayed as the active one while
  your genuinely-active schedules didn't appear. Turning a schedule off now
  clears it immediately, and the dashboard re-checks that what it shows is
  actually active (self-healing a stale pointer).
- **Restoring a database backup no longer fails when a filler sequence is set.**
  If you'd configured a filler *sequence* (not just a category), restore aborted
  with a foreign-key error and rolled back the whole import. That reference is
  now cleared before the restore proceeds.
- **Genre → category mappings now survive backup and restore.** They were
  dropped during every restore (never written to the backup and deleted on the
  way in), silently losing your genre-based preroll routing. They're now
  included in the backup and re-linked to the restored categories.
- **One bad row in a backup no longer discards the good ones.** A single
  problem entry (e.g. a duplicate category name) used to wipe out everything
  already restored in that batch; each row is now restored independently, so the
  rest comes through.
- **Restoring a full system (ZIP) backup reliably replaces the database.** The
  old database's leftover write-ahead files could mask the restored data, and on
  Windows an open database handle could block the swap. The restore now releases
  the database and clears those leftovers first.
- **Bundle import preview now plays.** Preview videos stored in category
  subfolders always failed to load (the player looked in the wrong place); they
  now play correctly during the import preview.
- **Security: archive imports can no longer write outside NeXroll's folders.**
  Restoring a crafted system ZIP or importing a crafted sequence bundle could
  drop files elsewhere on disk via `..` paths; such entries are now rejected.
- **Exporting a sequence while editing a schedule now exports that sequence.**
  From the schedule editor, Export could fail or download an unrelated sequence
  because it looked one up by the schedule's ID. It now exports the blocks you're
  actually editing. (A missing sequence also returns a proper "not found" instead
  of a generic failure.)

## [2.0.0-beta.6] - 06-16-2026 (beta)

> Sequence-and-schedule fixes: scheduled sequences now display correctly,
> editing a saved sequence updates the schedules built from it, and the
> Coming Soon List generator fails gracefully. Upgrade-safe.

### Added

- **Editing a saved sequence now updates the schedules built from it.**
  Schedules created from a saved sequence are linked to it, so changing the
  sequence's blocks propagates into those schedules automatically. (Schedules
  created before this update aren't linked yet — recreate them from the
  sequence to enable propagation.)

### Fixed

- **Scheduled sequences now show in the Currently Showing tile.** A schedule
  that runs a sequence (rather than a category) showed nothing — or showed its
  category as "0 prerolls". The tile now recognizes a sequence-based active
  schedule and labels it "Sequence (Scheduled)".
- **The Random/Sequential mode is preserved** when a sequence is saved into a
  schedule (it was silently reverting to Random).
- **The Saved Sequences cards show the correct preroll count** — trailer,
  coming-soon, and dynamic blocks were counted as 0; now they match the editor.
- **Coming Soon List generation gives a clear error** instead of the cryptic
  "Unexpected token 'I'… is not valid JSON" when something fails (e.g. the
  storage path is on an unreachable drive) — it now names the actual problem.

## [2.0.0-beta.5] - 06-15-2026 (beta)

> URL routing for every page, a NeX-Up sequence upgrade, and a batch of
> NeX-Up trailer/cookie fixes. Upgrade-safe — existing sequences keep working
> unchanged.

### Added

- **Real URL routing.** Every page now has its own address
  (`#/settings/storage`, `#/nexup/trailers`, ...), so pages are bookmarkable
  and shareable, the browser Back/Forward buttons work, and refreshing keeps
  you on the page you were viewing instead of bouncing to the Dashboard.
- **NeX-Up trailer sequence blocks now have a Mode: Random or Sequential.**
  Random shuffles the chosen source (Movies / TV / Both); Sequential plays the
  soonest-releasing trailers in order — a proper coming-attractions reel.
  Existing trailer blocks default to Random (their current behavior), so
  nothing changes for sequences you already built.
- **Install Deno from the System page.** If the Deno runtime (used for
  YouTube/NeX-Up extraction) is missing, a one-click install is offered on
  Windows. In Docker it shows a note instead (Deno ships in the image).

### Fixed

- **NeX-Up trailer sequences now include all your trailers.** A sequence set
  to a small count could show only one trailer because the pool excluded
  trailers with a blank or already-passed release date. The pool is now every
  downloaded, enabled trailer you have, refreshed live as you add/remove them.
- **Trailers that exist on YouTube no longer fail with a misleading "No
  trailer source available."** Downloads use a more forgiving video-format
  selection, and when a download genuinely fails the message now explains the
  real reason instead of blaming a missing source.
- **YouTube cookie test fixed** — it reported failure even when your cookies
  were valid (it called a yt-dlp CLI that doesn't exist in the packaged build,
  and it misread a harmless "format not available" as an error). It now tests
  through the real download engine and can also check a specific trailer URL.
- **Trailer download errors no longer always blame expired cookies** — a
  transient YouTube failure used to tell you to re-export cookies that were
  fine. The cookie advice now appears only for genuine sign-in/bot blocks;
  other failures report the real reason and suggest retrying.
- **YouTube cookie setup opens the browser you actually picked** (selecting
  Firefox previously opened the default browser on Windows). If the chosen
  browser isn't installed, it now says so instead of silently using another.
- **Deno that was already installed is now detected** even if it isn't on the
  service's PATH yet (this is why a freshly-installed Deno could still show
  "not found").
- **Trailers move with the storage path** — changing the NeX-Up storage
  location now relocates existing trailer files into the new folder.
- **Dashboard "Full Calendar" button** opens the calendar page (it was opening
  the schedules list).
- **Saved Sequences cards** — the Delete button is aligned with the other
  action buttons and no longer floats off on its own line.

## [2.0.0-beta.4] - 06-13-2026 (beta)

> Fixes the YouTube trailer "Test" button (it was misreporting failures),
> the weekly calendar getting cut off, and a sidebar scroll glitch. Plus a
> bit of fun on the loading screen. Upgrade-safe.

### Fixed

- **YouTube "Test Download" was unreliable.** It invoked a `yt-dlp`
  command-line binary that doesn't exist in the Docker image or the Windows
  build (yt-dlp is bundled as a Python module), so the test failed and showed
  a confusing error even when your cookies were valid. The test now runs
  through the same engine real downloads use, checks a known-good control
  video to confirm sign-in works, and lets you paste a specific trailer URL —
  so it can tell you "authentication is working, but that one video is
  unavailable" instead of wrongly blaming your cookies.
- **Browser-cookie downloads were silently broken** — the
  `--cookies-from-browser` option was passed to yt-dlp in the wrong form, so
  that authentication path never worked. Fixed (uploaded `youtube_cookies.txt`
  files were unaffected).
- **Clearer trailer error messages** — NeXroll now distinguishes stale/missing
  cookies from a video that is simply private, removed, members-only, or
  age-restricted, so you are not told to re-export cookies when the cookies
  are fine.
- **"This Week's Schedule" tile no longer cuts off** — it now expands to show
  every active schedule for the week.
- **Sidebar no longer drifts when scrolling** a long page.

### Changed

- The loading screen now shows a rotating set of dry, theater-themed quips.

## [2.0.0-beta.3] - 06-12-2026 (beta)

> Docker feedback fixes plus a major dashboard refinement round: unified
> tile design with quick actions built into the dashboard, big performance
> fixes, and a rebuilt tile height system. Upgrade-safe.

### Fixed

- **Community prerolls index survived Docker updates** (#Docker feedback) —
  the index was stored inside the container filesystem and wiped on every
  image update ("No index" after each upgrade). It now lives on the /data
  volume; a one-time migration adopts an existing copy where present.
- **NeX-Up trailers no longer appear twice** (once Uncategorized) — the
  library scanner also indexed the trailer storage folder and created
  duplicate rows. The scanner now leaves NeX-Up's tree alone and cleans up
  the duplicates it created on the next scan.
- **Six icon buttons rendered as empty boxes** (Edit category, Edit preroll,
  and four Close buttons) — leftovers from the emoji removal; restored with
  proper icons.
- **Dashboard scroll position and text selection reset every few seconds** —
  two background updaters (a leftover countdown timer and the status
  heartbeat) re-rendered the entire app once per second / per heartbeat.
  Both now update only when something actually changed.
- **Tile heights were content- and position-dependent** (feature tiles grew
  when moved in edit mode; later, tile content clipped or overflowed). The
  height measurement system never actually ran due to a mount-order bug; it
  now measures correctly — small tiles fit their content exactly, the wide
  tiles (Video Quality, Upcoming) match the same height, identical in
  locked and edit mode at any position.
- Native time/date pickers, dropdowns, and scrollbars now follow dark mode
  (the app never declared color-scheme).
- Plex server name now shows on the Servers tile (Plex reports it under a
  different field than Jellyfin/Emby).

### Changed

- **Dashboard tiles unified and enriched** — every stat tile shares one
  detail-row design; added: server address row (Servers), external/mapped
  count and last-added (Prerolls), timezone, firing-today, and Now/Next
  rows (Scheduler — countdown boxes removed), per-state icon rows
  (Currently Showing), response time, index freshness and size (Community),
  trailer storage bar (NeX-Up).
- **Every tile header has an action button** — navigation arrows to the
  relevant page, Stop/Start on Scheduler, Preview on Currently Showing.
- **Quick Actions moved into the dashboard** — the separate page is gone;
  a toolbar above the tiles offers Rebuild Thumbs, Refresh Data, NeX-Up
  Sync, Scan Files, Rebuild Index, Backup DB, and Check Updates alongside
  the layout controls.
- **Video Quality tile redesigned** — a segmented distribution bar with a
  count/percentage legend replaces the old chart, and the charting library
  was dropped entirely: **the app bundle is 21% (98 kB) smaller**.
- **Upcoming Schedules** lists up to 30 entries, scrolling past ~4 with a
  fade hint instead of stretching the tile.
- **Schedule time pickers** gained one-click preset chips (9:00 AM, 12:00
  PM, 6:00 PM, 9:00 PM; end-of-day and Clear for end fields) in both the
  create form and edit modal.
- **Loading screen** now shows a random theater pre-show line ("And now...
  our feature presentation").

## [2.0.0-beta.2] - 06-11-2026 (beta)

> Security and polish round for the v2 beta: **Require Login now protects the
> entire API**, the dashboard and Categories pages got a responsive/density
> pass, and the German-umlaut rendering bug (#31) is fixed. Upgrade-safe.

### Security

- **Global auth gate.** With Require Login enabled, every endpoint now requires
  a valid session or API key — previously only a handful of routes enforced
  auth, leaving uploads, deletes, schedules, and settings callable without
  logging in. Exempt: the login screen surface, `/health`, static assets, and
  the Jellyfin/Emby plugin endpoints (which keep their own API-key auth).
  Preroll thumbnails are gated too. **Note for automation users:** external
  scripts hitting the API now need an API key (read scope for GET, write for
  changes) when Require Login is on.

### Added

- **Update indicator in the sidebar footer** — a quiet pill (icon when
  collapsed) linking to the new release; replaces the old top-of-page banners.
- **NeX-Up dashboard tile** shows trailer storage used vs the configured cap
  with a usage bar (turns red at 90%).
- **Add Prerolls > Import Folder** now explains how Automatic Folder Monitoring
  (Settings > Storage) keeps an imported folder in sync, with a direct link.

### Changed

- **Dashboard tiles condensed** — tighter padding, smaller headers, reduced
  min-height and grid gap. The Video Quality tile is now half-height (Medium)
  and sized to its content; existing saved layouts migrate once automatically.
- **Page title/description headers removed app-wide** for a cleaner,
  content-first layout (the sidebar already labels every page).
- **Categories page refresh** — standard v2 button styles, a responsive
  search/filter toolbar that stacks on phones, theme-aware bulk-selection
  banner (was unreadable in dark mode), and a list view that converts to
  stacked cards on mobile.
- Dashboard edit-mode hint no longer references the removed S/M/L size
  controls.
- Removed an unused grid library from the frontend bundle (~23 kB smaller).

### Fixed

- **German umlauts and accented characters** rendered as garbage in Coming Soon
  lists and dynamic prerolls (#31) — FFmpeg drawtext now resolves a real
  Unicode font on Windows, Linux, and Docker (DejaVu/Liberation fonts added to
  the Docker image), and the German/Spanish/French preset labels were
  corrected.
- **Right edge of every page was cut off below ~1700px** window width with the
  sidebar expanded (page frame exceeded its column by its own padding).
- **Dashboard tiles on phones** — wide feature tiles crushed the stat tiles
  into a thin sliver and overflowed the screen; tiles now stack cleanly in one
  column.
- **Categories page overflowed on phones** (had to zoom out): the toolbar used
  fixed percentage widths, and the list view forced a table min-width that
  defeated its own mobile card layout.
- Consistent spacing between stacked cards on Settings pages.
- Logging in now reloads the app so all data loads under the auth gate instead
  of showing empty pages until a manual refresh.

### Internal

- `scripts/bump_version.py` bumps all four version locations in one shot
  (they had drifted when bumped by hand).
- PR-validation CI workflow (frontend build + backend syntax check).
- Dropped unused `alembic` and `APScheduler` from requirements.

## [2.0.0-beta.1] - 06-09-2026 (beta)

> First beta of the NeXroll v2 line — a top-to-bottom modern "Arr-style"
> interface overhaul, built on top of 1.14. **Upgrade-safe:** existing installs
> keep all their data and skip the new first-run wizard automatically.

### Added

- **Collapsible Arr-style sidebar** replaces the top tab bar — an expanding tree
  of sections/sub-pages, collapsible to an icon-only rail (remembered across
  sessions), off-canvas drawer on narrow screens. Status/theme/user move to a
  slim top bar; the logo is centered in the sidebar header.
- **Sidebar footer resource links** as icons (GitHub, Discord, Reddit, Ko-fi as
  a heart) with the version.
- **Sticky page headers** that stay pinned under the top bar while scrolling.
- **First-run onboarding wizard** — guided setup for media server
  (Plex/Jellyfin/Emby), optional Radarr/Sonarr, storage folder, and admin
  account; every step skippable, Plex can hand off to full OAuth.
- **Toasts** for non-blocking success/info feedback (errors/confirms keep the
  dialog).
- **Reusable empty-state** pattern across Library, Categories, Video Scaling,
  NeX-Up Trailers, Logs, Schedules, and Community.
- **Standardized button system** (primary/secondary/success/danger/info/outline).

### Changed

- **Page reorganization:** Dashboard standalone; new Library section (All
  Prerolls, Add Prerolls, Categories, Video Scaling); Quick Actions promoted to
  top-level. Section nav is driven entirely by the sidebar tree.
- **Connect page redesigned** (Plex/Jellyfin/Emby) with branded status heroes;
  Plex leads with the recommended Stable Token method plus a Docker/remote hint.
- **Community Prerolls redesigned** — status hero, unified search toolbar,
  refined result rows, cleaned-up random section.
- **Create New Schedule reorganized** into numbered section cards with themed
  fields and a sticky create bar.
- **My Schedules / Saved Sequences** refreshed; Edit Schedule and sequence
  import/export modals brought in line.
- **All emojis removed** UI-wide (replaced with lucide icons or words); stray
  Unicode control glyphs swapped for icons.
- Dark/light theming fixes throughout (whole viewport follows the theme), themed
  scrollbars, keyboard focus rings, smoother sidebar animation.

### Fixed

- **Community index build no longer hangs** — runs on a background thread and
  reports real, gradual progress (asymptotic curve) via a smooth animated bar,
  instead of blocking the request and racing to "done."

### Migration / upgrade notes

- A new `settings.onboarding_complete` column is added automatically on first
  launch. Existing databases are detected (a configured server, or any
  prerolls/categories present) and marked complete, so upgraders go straight to
  the new UI. Only genuinely fresh installs see onboarding.
- New endpoints: `GET /onboarding/status`, `POST /onboarding/complete`.

## [1.14.0] - 06-09-2026 (stable)

> Stable release of the 1.14 line, promoting 1.14.0-beta.1 and 1.14.0-beta.2.
> No code changes from beta.2 — version bump and stable promotion only.

Rolls up the 1.14 betas: the **Connections UI overhaul** plus scheduler/plugin/
Plex-OAuth fixes (beta.1), and the **Dashboard layout overhaul** (beta.2). See
those entries below for full details.

## [1.14.0-beta.2] - 06-05-2026 (beta)

> Dashboard layout overhaul. Builds on beta.1; no backend or plugin changes.

### Changed

- **Dashboard reworked into a uniform, aligned grid (DASH-UI-1).** The overview
  now uses a fixed 4-column grid in which every stat tile is the same size and
  the rows line up. Per-tile S/M/L resizing was removed in favor of fixed sizes
  by tile type: stat tiles take one cell; **Video Quality** and **Upcoming
  Schedules** span two columns with extra height for their content; the weekly
  calendar spans the full width. Tile heights are measured so the grid stays
  aligned regardless of how much content a tile shows. The dashboard width is
  capped so the columns stay a comfortable size instead of stretching.
- **Weekly calendar is now a dashboard tile.** Previously pinned below the
  overview, it's a full-width, move-only tile you can reorder anywhere in the
  grid. Tiles can still be dragged to reorder and hidden/re-added — they just
  can't be resized.

## [1.14.0-beta.1] - 06-02-2026 (beta)

> First public beta of the 1.14.0 line. Rolls up everything developed under the
> previously-unreleased 1.13.20: automatic folder monitoring, Plex Cinema Trailers
> controls, the scheduler/auto-scan duplicate-module fix (SCHED-DUP-1), the Cinema
> Trailers false-rejection fix (PLEX-CT-2), and the Jellyfin/Emby plugin cache-path
> fix (issue #30) plus dashboard icon. Windows binaries and plugin assemblies are
> versioned 1.14.0.0.

### Features

- **Automatic preroll folder monitoring (SCAN-1).** Previously NeXroll only
  scanned the preroll folders on startup, after a JSON restore, or via the
  manual "Rescan Files Now" button — files dropped into category folders weren't
  picked up until a restart or manual rescan. NeXroll now re-scans on a
  configurable interval (default every 15 minutes) so new/removed files are
  picked up automatically. It's optional — configure or disable it under
  Settings → Storage ("Automatic Folder Monitoring"); env override
  `NEXROLL_AUTO_SCAN_MINUTES`. Reuses the idempotent reconcile (no duplicate
  rows thanks to DEDUPE-1). New endpoints `GET`/`PUT /prerolls/auto-scan`.
  The scan runs in its own dedicated background thread, fully isolated from the
  scheduler loop, so a slow or failing scan (it walks the disk and can spawn
  ffmpeg for thumbnails) can never block or stop scheduling.
- **Control Plex Cinema Trailers from NeXroll (PLEX-CT-1).** New "Cinema Trailers"
  card on the Connections → Plex tab (shown when connected) exposes Plex's own
  trailer settings and writes them straight to the Plex server: choose trailers
  from all/unwatched movies, include trailers from movies in your library,
  include new/upcoming in theaters and on Blu-ray (Plex Pass), and always
  include English-language trailers for movies not in your library. Values are
  read live from the server's `/:/prefs`, so the card reflects real state and
  hides Plex Pass-only options the server doesn't advertise. Changes save
  immediately. New endpoints `GET`/`PUT /plex/cinema-trailers`; PlexConnector
  gained `get_cinema_trailer_prefs()` and a generic `set_pref()`.

### UI

- **Connections page redesign (CONN-2).** A cohesive, more professional pass over
  the whole Connections page while keeping the NeXroll aesthetic:
  - The Plex / Jellyfin / Emby switcher is now a **segmented pill selector** —
    the active server lifts onto a card surface with its brand-colored accent
    (Plex coral, Jellyfin violet, Emby green) and a connection **status dot**.
  - The context banner, form fields, card section headers, inline `code`, and
    disclosure summaries are unified via shared, theme-aware classes (no more
    scattered inline styles); fields get consistent padding, radius, and a focus
    ring instead of bare browser defaults.
  - Status **badges** are now semantic chip variants (`success`, `info`,
    `accent`, `recommend`) and the tinted **info panels** (download hints,
    detection results, "plugin not found") share one `.nx-notice` component, so
    everything reads as a set in light and dark.
  - Redundant per-panel headers removed; Plex now has a matching **"Connect to
    Plex Server"** title like Jellyfin/Emby.
  - Simpler wording: the Plex connection methods are now plain **"Option 1:
    Stable Token / Option 2: Manual Token / Option 3: Sign in with Plex."**
- **Connections → Plex tab decluttered (CONN-1).** The recommended Stable Token
  method stays front and center; the Docker and remote-server help (previously
  two always-open blocks) now collapses into a single "Help: Docker & remote
  servers" section. Manual-token and Plex.tv methods remain collapsible.
- **Modal polish.** Refreshed the Create User and Add API Key dialogs (and shared
  modal text-field styling) for a less bland look.
- **Verbose Logging toggle now also on the Logs page (UX-5).** Previously it lived
  only on General settings; mirrored it into Settings → Logs alongside the other
  log controls (same backend toggle).

### Bug Fixes

- **Plex.tv sign-in failed with "We were unable to complete this request"
  (PLEX-OAUTH-1).** Connecting via the Plex.tv account method opened an auth
  window that errored out and never connected. The OAuth URL was being built
  with `code=None` — Plex had no PIN to link, so it rejected the login. Cause:
  plexapi 4.17 moved the PIN-code fetch out of `MyPlexPinLogin.__init__` into
  `run()`, but NeXroll called `oauthUrl()` *before* `run()`, so the code wasn't
  populated yet. Reordered to call `run()` first (it fetches the PIN
  synchronously, before starting the poll thread) and added a guard that surfaces
  a clear error if Plex returns no PIN code. (Stable Token and manual-token
  methods were unaffected.)
- **Cinema Trailers toggles showed a false "Plex rejected the change" error
  (PLEX-CT-2).** Toggling a Cinema Trailers setting applied correctly on the
  Plex server but still surfaced "Plex rejected the change to X — if this is a
  Plex Pass-only setting, it requires an active Plex Pass," even with an active
  Plex Pass. The write succeeded; the post-write verification was wrong: Plex
  accepts `true`/`false` on the `/:/prefs` PUT but stores booleans as `1`/`0`,
  and `set_pref` compared the re-read value as a raw string (`'1' == 'true'`),
  which never matched. The verification now compares booleans semantically
  (treating `1`/`true`/`on`/`yes` as true), so a successful toggle no longer
  reports a phantom rejection.
- **Scheduler tile flashing "stopped" and auto-scan never running — fixed the
  true root cause: a duplicate `Scheduler` object in the frozen build
  (SCHED-DUP-1).** This supersedes the earlier SINGLE-1 / SCHED-RESIL-1 theories
  (the "two `NeXroll.exe`" they chased is just the normal PyInstaller onefile
  bootloader+child pair — one logical server). Diagnosed live: the scheduler
  loop was genuinely running, yet `/scheduler/status` reported `running:false`,
  because the HTTP route handlers and the FastAPI `startup_event` were holding
  **two different `Scheduler` instances**. Cause: in frozen builds `main.py`
  runs as `__main__`, but the auto-scan loop and the log-cleanup helper still did
  `from backend.main import ...`, which loads `main.py` a *second* time as
  `backend.main` and re-executes the whole module. That re-execution (a) tripped
  the frozen startup block, whose `sys.exit(0)` raised `SystemExit` — not caught
  by `except Exception` — and **killed the auto-scan thread on its first run**
  (so deleted files never dropped from the count), and (b) created the duplicate
  module/scheduler state behind the false "stopped" indicator. Fixes: (1) the
  global `scheduler` singleton is now anchored on the `sys` module, so every
  copy of the module — however it's imported — shares the exact same instance;
  (2) the auto-scan loop and `_maybe_cleanup_logs` now resolve `main` helpers via
  `sys.modules` instead of re-importing (matching the existing NeX-Up sync
  pattern); (3) the auto-scan loop catches `BaseException` so nothing can tear
  the thread down again; (4) the frozen auto-start block is guarded with
  `__name__ == "__main__"` so re-importing `main` is completely inert. Verified:
  `/scheduler/status` holds `running:true` across sustained polling, a deleted
  file is auto-pruned on the next scan, and `POST /scheduler/start` is now a
  no-op against the already-running loop.
- **Deletions in Explorer now self-heal — no more "Remove Missing Rows" prompt
  for the common case (SCAN-3).** When a preroll file is deleted or moved
  outside the app, scans (startup, the periodic auto-scan, and Scan Now / Rescan
  Files Now) now automatically remove the stale DB row instead of showing the
  "Remove Missing Rows" banner and making the user fix it. Critically, this is
  guarded against storage outages: if no files are found on disk at all, or a
  large fraction of rows (>25%, min 10) suddenly go missing in one scan, NeXroll
  treats it as a likely offline network share / unmounted drive and does NOT
  delete anything — it leaves the rows so they relink when storage returns, and
  the dashboard shows a "storage may be offline" notice instead of advising
  removal. The manual "Remove Missing Rows" button still force-removes without
  the threshold. (JSON restore is unaffected — it never auto-prunes.)
- **Scheduler "stops" after an update — fixed the real cause: duplicate
  instances (SINGLE-1).** Diagnosed from a user's service log: installing an
  update while the previous NeXroll was still running left two `NeXroll.exe`
  processes fighting over port 9393. The second failed to bind (WinError 10048)
  and shut down mid-startup, taking its scheduler with it — so the dashboard
  showed the scheduler "started then stopped." (The earlier SCHED-RESIL-1 work
  hardened the status reporting, but the underlying trigger was the port
  collision, not a scheduler crash.) Two fixes: (1) `NeXroll.exe` is built from
  `backend/main.py`, which had no single-instance check — the existing mutex
  guard in `scripts/launcher.py` was never reached. Added a `Global\` named
  mutex check before the frozen build starts uvicorn, so a second backend exits
  cleanly instead of half-starting. (2) The NSIS installer now stops the running
  service and force-kills any `NeXroll.exe` / `NeXrollTray.exe` / service
  process *before* copying files and starting the new service, so updates no
  longer overlap with the old instance.
- **"Failed to update auto-scan setting" fixed (SCAN-2).** The auto-scan interval
  endpoints were registered at `/prerolls/auto-scan`, but `PUT /prerolls/{preroll_id}`
  is defined earlier and shadowed it — `PUT /prerolls/auto-scan` matched
  "auto-scan" as a preroll id and 422'd (the GET worked, so loading the value
  was fine but saving failed). Moved both endpoints to `/settings/auto-scan`.
  Also added a **Scan Now** button to the Automatic Folder Monitoring card.
- **Dashboard no longer falsely shows the scheduler "stopped" (SCHED-RESIL-1).**
  The batched dashboard poll reset *all* UI state to defaults — including the
  scheduler tile to "stopped" and empty preroll/category lists — whenever any
  single request in the batch failed or the backend was briefly busy (e.g.
  during a folder scan). The scheduler thread was actually fine. Now a transient
  poll failure keeps the last known state, and the scheduler tile only updates
  from a valid status response. Backend hardening too: `/scheduler/status`
  reports liveness from the actual thread (not just a flag) and never throws on
  the active-schedule count; `scheduler.start()` revives a thread that has
  genuinely died instead of being a no-op; and the scheduler loop logs loudly
  if it ever exits unexpectedly.
- **Log retention is now actually enforced (LOG-5).** `cleanup_old_logs()` existed
  but was never called anywhere, so the "Log Retention" setting did nothing and
  the log table grew without bound (a user's DB held thousands of entries dating
  back months). Retention is now applied on startup and again ~once per day from
  the scheduler loop, pruning entries older than the configured window. This is
  what the Log Retention dropdown's "automatically purge logs older than this"
  description always promised.

- **Can't enable "Require Login" without an admin account (AUTH-2).** Toggling
  Require Login on with zero user accounts was a lockout risk — `PUT
  /auth/settings` flipped `auth_enabled` with no guard. The endpoint now rejects
  enabling auth unless at least one active admin user exists (clear 400
  otherwise). The frontend toggle was already disabled in this state; this is
  the authoritative server-side guard. (Recovery was already safe: the login
  screen shows "Create the first admin account" when no users exist.)
- **"Clear All Logs" option added; plain "clear" no longer leaves recent entries
  behind (LOG-4).** The log panel only had "Clear Logs Older Than 30 Days,"
  which (correctly) keeps anything inside the retention window — so users trying
  to wipe a backlog of old error spam saw the count only partially drop and
  assumed clearing was broken. Added an explicit **Clear All Logs** button
  (with confirmation) backed by a new `clear_all=true` parameter on
  `DELETE /logs` that bypasses the retention cutoff.
- **Library-health banner uses plain language (UX-4).** "duplicate rows" /
  "preroll rows point at..." confused users who don't think in database terms.
  Reworded to "N prerolls are listed more than once (the same video file has
  duplicate entries)" and "N preroll entries point to files that no longer
  exist on disk."
- **Duplicate preroll rows no longer regenerate after Dedupe (DEDUPE-1).** The
  scanner's orphan-file pass created a new DB row for any on-disk file it
  didn't match to an existing row via the category-folder + filename
  heuristic. But a row could already point at that exact file and still fail
  the heuristic (e.g. a filename like `intro.mp4` that exists in several
  category folders, so the unique-filename fallback gives up) — so the scan
  created a second row with the same path. Running Dedupe removed the
  duplicates, but the very next startup scan re-created them, so the dashboard
  health banner kept reappearing. The orphan pass now skips any path a DB row
  already owns, so duplicates stop regenerating and Dedupe sticks. (Most common
  on Docker instances migrated from Windows.)

### Plugins (Jellyfin / Emby)

- **Prerolls failed to play in Docker with "Access to the path '…/NeXroll' is
  denied" (issue #30).** The intro provider cached downloaded prerolls under a
  folder derived from `Environment.GetFolderPath(LocalApplicationData)`. On
  Linux/.NET that resolves via `$XDG_DATA_HOME` / `$HOME/.local/share` and
  returns an **empty string when `HOME` is unset** — which is the case for the
  Jellyfin/Emby service under s6-overlay (linuxserver.io Docker on Unraid, etc.).
  An empty base collapsed the cache path to a **relative** one, so
  `Directory.CreateDirectory` resolved it against the process working directory
  (the read-only s6 service dir, `/run/s6-rc.../svc-jellyfin/`) and threw
  `UnauthorizedAccessException` on every intro download. The provider now
  resolves its cache directory from the plugin's own data folder
  (`Plugin.Instance.DataFolderPath` — always absolute and writable, under the
  server config dir) and falls back to the OS temp directory if that is ever
  empty or not rooted, so the path can never collapse to a relative one again.
  Affects both the Jellyfin and Emby plugins. (Workaround on older builds: set
  `HOME=/config` or `XDG_DATA_HOME=/config` on the container.)
- **Plugin now shows the NeXroll icon in the dashboard.** Emby surfaces it via
  `IHasThumbImage` (embedded PNG); Jellyfin 10.11 (which dropped
  `IHasThumbImage`) gets it from a bundled `meta.json` + `thumb.png` in the
  plugin folder.
- **Plugin version stamped to 1.14.0** (both Jellyfin and Emby) so the installed
  version is visible in the dashboard instead of a default `1.0.0.0`.
- **Jellyfin plugin pinned to the 10.11.0 SDK floor (PLUGIN-ABI-1).** The csproj
  referenced `Jellyfin.* 10.11.*`, a floating version that resolved to whatever
  patch was newest on NuGet at build time (e.g. 10.11.10). Jellyfin refuses to
  load a plugin that references a higher `MediaBrowser.*` assembly version than
  the host provides ("Failed to load assembly … references an incompatible
  version of one of the shared libraries"), so a build made against 10.11.10
  silently broke every server on an earlier 10.11.x. Pinned to `[10.11.0]` so the
  DLL references `10.11.0.0` and loads on any 10.11.x server. (Kept in lockstep
  with `meta.json` `targetAbi`.)

## [1.13.19] - 05-28-2026

### Bug Fixes

- **JSON restore no longer fails with "FOREIGN KEY constraint failed [DELETE FROM
  categories]" on Docker (RESTORE-1).** The restore clears category references
  before deleting categories, but only NULLed `settings.active_category` — it
  missed the three other category FKs on the settings table:
  `nexup_category_id`, `nexup_tv_category_id`, and `filler_category_id`. On
  Windows this went unnoticed because SQLite defaults `foreign_keys=OFF`; Docker
  enforces them, so any backup with filler or NeX-Up categories configured (and
  a fresh Docker instance auto-creates a NeX-Up category) aborted the restore.
  All four are now NULLed (each independently, so schema drift on one column
  can't abort the restore). These settings columns aren't re-populated by the
  restore, so they stay empty and are re-selected in the target instance.

## [1.13.18] - 05-27-2026

### Bug Fixes (from 2026-05-27 user diagnostic bundle)

- **Sequence editor now plays the final preroll (PREVIEW-2).** `SequencePreviewModal`
  was constructing video URLs as `static/prerolls/<category-name>/<filename>` —
  the same broken pattern fixed for the simple preview modal in PREVIEW-1. When
  a sequence item's resolved category-folder + filename didn't match the actual
  on-disk location (uncategorized prerolls, files in folders that don't share
  the category name, sequence items whose category was renamed), the request
  404'd and playback silently stopped before reaching the last item. Switched
  to the canonical `GET /prerolls/{id}/video` endpoint, which streams directly
  by row id and is independent of the file's folder layout. Legacy items without
  an `id` still fall back to the static path.
- **Inflated preroll totals fixable from the UI (SCANNER-1).** When external
  tooling deletes files from disk or historical sync races create duplicate
  rows pointing at the same path, the dashboard count drifts off the actual
  file count. The rescan endpoint already detected these (`missing_files`
  stat) but couldn't act on them. Added two opt-in cleanup actions:
  1. `POST /prerolls/rescan?delete_missing=true` — drops DB rows whose `path`
     no longer resolves to a file on disk. Returns `deleted_missing` count.
  2. `POST /prerolls/rescan?dedupe=true` — groups remaining rows by normalized
     path, keeps the lowest-id row, deletes the rest. Carries m2m category tags
     from the duplicates to the keeper. Returns `deduped_rows` count.
  Both surfaced as separate buttons in Settings → Backup → Rescan Preroll Files
  ("Remove Missing Rows", "Dedupe Duplicates") with browser-level confirmation
  before either runs.
- **Dashboard banner prompts the user when cleanup is needed (HEALTH-1).** The
  startup scan now also counts duplicate DB rows (non-destructive) alongside
  the existing `missing_files` count and caches both in memory. New endpoint
  `GET /system/health/storage` exposes the snapshot. The dashboard fetches
  it on load and, when either count is > 0, shows a warning banner naming the
  exact count and the button to click. A "Take Me There" action deep-links to
  Settings → Backup, scrolls the Rescan card into view, and briefly highlights
  the recommended button (red ring for Remove Missing Rows, amber for Dedupe).
  Banner is dismissible per session so users can defer until they're ready.
  Counts are recomputed from current DB state after each cleanup pass, so the
  banner reflects post-cleanup reality immediately — no second rescan needed.
- **Dashboard "random" sequence block plays ONE preroll, not the whole pool
  (PREVIEW-3).** When a schedule's sequence contained a `random` block,
  `_preview_payload_from_intent` was appending every preroll in the source
  category to the preview list, and `mode='sequential'` then played them all
  in order. Plex's actual behavior is to pick one at playback time, so the
  dashboard's preview contradicted what Plex was doing (and what the user
  expected: "one random from the category"). Now picks one at preview-build
  time to mirror Plex.
- **Update check no longer spams red ERROR rows when GitHub is unreachable
  (LOG-2).** Transient network failures (Windows firewall block / WinError
  10013, DNS failure, GitHub timeout, no internet) used to log at ERROR every
  hour for users with hourly update checks — even though there's nothing to
  fix in NeXroll itself. Now those are classified as WARNING with a "Update
  check skipped (network unavailable)" message, and only genuine
  response-parsing or unexpected exceptions still log at ERROR. The endpoint
  also returns a `network_error: true` flag so the frontend can react.
- **Update check backs off after consecutive network failures (LOG-3).** The
  frontend was scheduling a fresh check every hour regardless of whether the
  previous attempts succeeded, which meant a firewall-blocked install logged a
  warning 24 times a day. After 3 consecutive network failures the next
  attempt is deferred 6 hours; after 6, deferred 24 hours. Counter resets on
  the first successful round-trip with GitHub.
- **This Week's Schedule header surfaces filler days (UI-1).** When gap-filler
  was enabled, days with no active schedules just showed "none" in the column
  header — the user had to scan down to the bottom filler row to see that
  filler would be playing. The header now reads "Filler" in cyan with a small
  glowing dot, matching the existing filler-row treatment, so it's clear at a
  glance which days will run filler content all day.
- **Rescan buttons show "Rescanning..." instead of "Restoring..." (UI-2).** The
  progress banner on Settings → Backup hard-coded a two-state label (Creating
  Backup / Restoring) and defaulted any non-backup action to "Restoring..." —
  clicking Rescan Files Now / Remove Missing Rows / Dedupe Duplicates therefore
  looked like a restore was in progress. Banner now picks a label that matches
  the action type.
- **Yearly calendar month boxes no longer overflow (UI-3).** Schedule names in
  the year view used `flex: 1` + `text-overflow: ellipsis` but were missing
  `min-width: 0` — flex items default to `min-width: auto`, which prevents
  shrinking below content width, so long names pushed past the right edge of
  the month card. Added `min-width: 0` on the row + name span and `overflow:
  hidden` on the card so the rounded border clips anything that still drifts.
- **Dashboard preview now resolves trailer / Coming Soon / dynamic-preroll
  blocks (PREVIEW-5).** `_preview_payload_from_intent` was only handling
  `fixed` and `random` blocks. When a sequence contained `nexup_trailers`,
  `coming_soon_list`, or `dynamic_preroll` blocks (the modern Coming Soon
  setup), those segments were silently dropped from the dashboard's
  "Currently Playing" preview — the user saw the random preroll play and
  thought "the last block didn't play" because the surrounding context was
  missing. The sequence editor modal already handled these block types via
  `/sequences/resolve-preview-blocks`; the dashboard now mirrors that logic
  inline so the preview matches what plays in Plex.
- **Sequence builder preview no longer skips preroll blocks for m2m-tagged
  prerolls (PREVIEW-4).** `SequencePreviewModal.getBlockPrerolls` filtered the
  pool for `random` / `sequential` blocks by the legacy `category_id` column
  only. After the v1.13.2 category overhaul, many prerolls live in their
  category via the m2m `categories` relationship instead — those were
  invisible to the preview, so the block resolved to an empty list and the
  preroll segment was silently skipped (user saw Coming Soon + trailers and
  no preroll). Filter now mirrors the backend rule: matches either
  `category_id` or any entry in `categories[]`.
- **Yearly schedule with no `end_date` now means "all year" (SCHEDULER-8).**
  Previous behavior treated it as a single-day-per-year schedule active only on
  the exact month/day of `start_date`. A user who created "Omega- Year Round
  Schedule" without setting `end_date` got a one-day yearly that never applied
  on any day except the start_date. The frontend's "is this active now?" check
  didn't share the same single-day limitation, so the Upcoming tile said the
  schedule was active while the scheduler silently rejected it every tick —
  the dashboard's Currently Showing box stayed empty. Yearly schedules with
  `end_date` set keep their existing date-range behavior. Also added support
  for year-boundary-crossing ranges (e.g. Dec 18 → Jan 3).
- **`/static/<full-URL>` errors eliminated (LOG-1).** NeX-Up trailers store TMDB
  poster URLs in their preroll `thumbnail` field. The frontend was building
  `apiUrl(\`static/${preroll.thumbnail}\`)` which concatenated the full external
  URL onto the local static path, then the backend tried to serve it as a file
  and crashed with WinError 123 (the colon in `https:` is invalid in Windows
  paths). The user's diagnostic log had **2791 such errors**. Fixed in two places:
  1. New `thumbnailUrl()` frontend helper detects values starting with `http(s)://`
     and uses them as-is. Replaced 4 preroll-card sites.
  2. Defensive backend HTTP middleware rejects any `/static/...://...` request
     with a clean 404 before it reaches the StaticFiles mount. Catches stragglers
     from old cached frontend bundles.
- **Long preroll titles readable in the Add-Prerolls picker (IMPORT-2).** The
  filename label used `whiteSpace: nowrap` + ellipsis, so anything longer than
  the thumbnail width was unreadable until added. Now wraps to two lines
  (`-webkit-line-clamp: 2`) with the full title on hover.

## [1.13.17] - 05-26-2026

### UX (post-audit testing fix)

- **Scheduler tile countdown is now unambiguous.** During testing, the user
  observed the countdown labeled "1135 Test" finish and jump to a new "1h 40min"
  countdown without 1135 Test ever applying. Root cause: at the moment one
  schedule's window opens, that schedule becomes "currently active" and gets
  excluded from the "next up" list, so the tile's label and countdown both
  switch to the next schedule on the same frame — looking like a reset rather
  than a transition. The countdown logic itself was correct.

  Two UI clarifications:
  1. **"Now: <schedule name>"** line shows what's actually playing right now
     (sourced from `activeCategory.active_schedule_name`).
  2. **Target timestamp** next to "Next:" shows when the upcoming schedule will
     fire (e.g. `Next: 1135 Test @ May 26, 08:26`). When the target flips to a
     different schedule, the timestamp visibly changes too — no ambiguity.

## [1.13.16] - 05-26-2026

### Cleanup (final cross-cutting audit pass for v2.0.0 prep)

- **Deleted ~410-line dead `_apply_schedule_win_lose_logic`.** This function was a
  parallel reimplementation of the scheduler's logic, used to be called from
  `update_schedule` until v1.13.5 rerouted that call site to
  `scheduler.trigger_immediate_check()`. It had zero callers since then but lingered
  in `main.py` as a future trap. Removed entirely; stale comment in `update_schedule`
  rewritten.
- **Consolidated 7 parallel `_prerolls_for_category` implementations** behind a single
  `prerolls_for_category_query(db, category_id)` helper in `backend/scheduler.py`.
  This was the audit's most architecturally dangerous finding — when the NeX-Up
  `enabled` filter needed to be added (v1.13.10), it had to be applied to each of
  the seven duplicates independently. The manual sequence-apply helper (SEQUENCING-1,
  v1.13.11) and the Jellyfin/Emby plugin resolver (PLUGIN-2, v1.13.14) were each
  caught only AFTER user testing surfaced the regression. Future fixes/extensions
  now land in one place. Replaced call sites:
  - `scheduler.py`: 5 sites — `_apply_jellyfin_category`, `_apply_category_to_plex`,
    `_apply_schedule_sequence_to_plex` random helper, `_apply_blended_schedules_to_plex`
    helper, `_apply_saved_sequence_to_plex` filler helper
  - `main.py`: 2 sites — `apply_sequence_to_server`, `_resolve_current_intros`
- **Added `_paths_equal` and `_find_preroll_for_trailer` helpers** for trailer↔preroll
  linkage lookups (NEXUP-2). Tolerant of case and forward-vs-backslash separator
  drift on Windows. Applied to the four user-facing trailer linkage sites:
  movie/TV trailer delete and movie/TV trailer toggle. Without this, a tiny path
  formatting mismatch (`C:\\NeXroll\\file.mp4` vs `c:/nexroll/file.mp4`) could
  silently miss the linked Preroll, so the v1.13.10 enabled-field sync would skip
  it. Sync paths still use exact match — they write the paths they read so drift
  isn't a risk there.

### Audit complete

11 subsystems audited:
1. Scheduler (4 fixes)
2. Dashboard state sync (2 fixes)
3. Preview/playback (3 fixes)
4. Categories/m2m surface (3 fixes + primary-UI removal)
5. NeX-Up (1 fix)
6. Sequencing (2 fixes)
7. Import/folder-picker UX (1 improvement)
8. Backup/restore (1 fix — many fields)
9. Plex/Jellyfin/Emby plugin endpoints (1 fix)
10. Settings/config flow (2 fixes)
11. Auth/sessions (clean)

Plus cross-cutting: dead-code removal, helper consolidation, path-equality helper.

Total: **~20 bug fixes, 1 UX improvement, 1 dead-code removal**, ranging from
silent data loss (BACKUP-1) to user-visible regressions (multiple). Tracked
findings remain in `AUDIT.md` with their status (FIXED / OPEN / ACKNOWLEDGED /
DEFERRED) for v2.0.0 planning.

## [1.13.15] - 05-26-2026

### Bug Fixes (settings/config audit)

- **Removed duplicate `/settings/dashboard-tile-order` registration.** The endpoint
  was registered twice with different response shapes; FastAPI's first-match
  routing meant the second pair was unreachable dead code. Removed.
- **Filler disable transition now triggers an immediate scheduler check.** Disabling
  filler used to leave the dashboard tile showing the filler state for up to 60
  seconds. `PUT /settings/filler` now calls `scheduler.trigger_immediate_check()`
  on the disable path so the next winner (or "nothing") shows up immediately.
  Resolves DASHBOARD-3 from the v2.0.0 audit.

### Audit Findings (no change needed)

- **AUTH-1** — Full review of `/auth/login`, `_validate_session`, `require_auth`,
  `get_current_user_optional`: IP rate limiting, account lockout (5 attempts,
  15-minute lock), session token hashing in DB (raw token only in the cookie),
  `httponly` + `samesite=lax` + secure-when-https cookie flags, periodic expired-
  session cleanup, and audit logging are all in good shape. No bugs found.
- **SETTINGS-3** — Generic `/settings/{key}` JSON store is unused by the frontend
  but is harmless and could be useful for future integrations. Specific routes
  win over the catch-all. Left as-is.

## [1.13.14] - 05-25-2026

### Bug Fixes (Plex/Jellyfin/Emby plugin endpoint audit)

- **Disabled NeX-Up trailers still played through the Jellyfin/Emby plugin.**
  `_resolve_current_intros` — the function the `/plugin/intros` endpoint uses to
  decide what to serve plugins — has its own `_prerolls_for_category` helper,
  distinct from the scheduler's five copies and the manual sequence-apply helper
  fixed earlier. After v1.13.10 (scheduler) and v1.13.11 (manual sequence apply)
  taught those paths to skip `enabled=False` prerolls, this **third parallel
  implementation** was still picking disabled trailers, so disabling a trailer
  worked for Plex but silently failed on Jellyfin/Emby. Same filter added.

### Acknowledged, no change
- **PLUGIN-1** — `/plugin/intros` accepts unauthenticated requests (optional
  X-Api-Key for backward compat with old plugins). Anyone on the LAN can list
  active preroll paths. Documented in code; acceptable for low-sensitivity
  content.
- **PLUGIN-3** — `/plex/webhook` signature verification is gated on
  `NEXROLL_PLEX_WEBHOOK_SECRET` env var. Without it, webhook events can be
  forged. Impact bounded (transient genre-mapping action); opt-in stricter
  verification documented.

## [1.13.13] - 05-25-2026

### Bug Fixes — primary-category UI cleanup (CATEGORIES-7)

The v1.13.0 work retired primary category from the Categories page, but four
primary-flavored UI surfaces remained. All now removed:

- **CategoryPicker** (used in upload + preroll-edit modals) no longer renders a
  "Primary" chip, a "No primary" placeholder, or a "Make primary" star on each
  dropdown item. All selected categories render as identical chips with × to
  remove. The component still emits `onChange(primary, secondary)` for backend
  storage compatibility — the user just never sees that split.
- **"Set as Primary (moves files)" checkbox** in the Add-Prerolls-to-Category
  picker is gone. Adding a preroll to a category just attaches the tag — does
  not move files on disk.
- **Bulk "Apply to N Selected" button** in the Prerolls page now POSTs to the
  m2m endpoint instead of PUT-updating `category_id`. Files are not moved.
  Confirm dialog text updated to reflect the new behavior.
- `handleCategoryAddPreroll` no longer sends `?set_primary=true|false`.

### Bug Fixes — backup/restore field gaps (BACKUP-1)

The JSON backup payload was missing most model fields, so a backup/restore
round-trip silently dropped feature configuration. Now lossless. Restored fields:

- **Categories**: `plex_mode`, `apply_to_plex`, `is_system` (the last protecting
  NeX-Up system categories from being deleted post-restore).
- **Prerolls**: `duration`, `file_size`, `enabled` (added in v1.13.10!),
  `community_preroll_id`, `exclude_from_matching`, `file_hash`. The `enabled`
  field was the worst regression — disabling a NeX-Up trailer, backing up, and
  restoring would silently re-enable it.
- **Schedules**: `fallback_category_id`, `sequence`, `color`, `blend_enabled`,
  `priority`, `exclusive`, `holiday_name`, `holiday_country`. Sequence schedules
  came back as plain category schedules; blend/exclusive/priority/holiday-API
  bindings were all lost.
- **Holiday presets**: `start_month` / `start_day` / `end_month` / `end_day`
  (date-range fields), `is_recurring`. Date-range holidays collapsed to a
  single point.

Backup payload now carries `schema_version: 2` and `exported_by_version` for
diagnostics. Restore reads every field defensively — older v1 backups still
restore (missing fields fall back to model defaults).

### Acknowledged, deferred
- **BACKUP-2** — `Schedule.preroll_ids` (comma-separated preroll-ID string used
  by some legacy schedule types) doesn't get its IDs remapped during restore.
  Few schedules use this field; most use inline `sequence` JSON. Flagged for v2.0.0.
- **BACKUP-3** — The file-bundle ZIP backup (`POST /backup/files`) is unaudited.
  Same pattern of "make sure every column makes it through" applies; deferred to
  a future pass.

## [1.13.12] - 05-25-2026

### UX (resolving user feedback)

- **Add-Prerolls-to-Category picker now groups by source folder.** Previous behavior:
  a flat grid of every available preroll thumbnail. With a large library this was a
  "sea of thumbnails" — there was no way to grab everything from a specific source
  folder without clicking each item individually. Picker now has:
  - **Folder filter dropdown** derived from each preroll's stored `path` on the fly.
    Each option shows the folder name and item count (e.g. `Christmas (24)`). Picking
    a folder narrows the grid; "All folders" is the default.
  - **Select All (N) button** that selects every preroll currently matching the active
    filter (folder + search). Toggles to "Deselect All" once everything visible is
    selected. Pick a folder, click once, you've grabbed it all.
  - Each thumbnail's secondary line now shows the source folder name instead of the
    legacy "category" name.

  Resolves UX-FEEDBACK-1 from the v2.0.0 audit ("It's just a sea of thumbnails... if
  it used my windows folder structure i could just add the 'holiday' folder").

## [1.13.11] - 05-25-2026

### Bug Fixes (sequencing subsystem audit)

- **Manual sequence-apply ignored the `enabled` field on prerolls.** `POST /sequences/{id}/apply`
  has its own random-block helper (separate from the scheduler's). After the v1.13.10
  fix taught the scheduler to skip `enabled=False` prerolls, this manual-apply path
  was the lone remaining hole — clicking "Apply Sequence" on a sequence with a random
  block over the NeX-Up category would still include trailers the user had toggled off.
  Now uses the same filter as the scheduler.
- **Deleting a saved sequence left dangling references.** The delete endpoint just
  removed the row, didn't check whether settings still referenced it:
  - `Setting.filler_sequence_id` could point at the deleted ID, and filler would
    silently fail at apply time when filler_type was "sequence".
  - `Setting.applied_sequence_id` could point at the deleted ID, so the dashboard
    "applied sequence" tile showed the deleted name for up to 15 minutes.
  
  Delete now clears both references, disables filler if it was the sole sequence
  underpinning a `sequence`-type filler, and triggers an immediate scheduler check
  so the dashboard re-syncs. Response includes `cleared_filler` and
  `cleared_applied_override` flags for UI feedback.

## [1.13.10] - 05-25-2026

### Bug Fixes (NeX-Up subsystem audit)

- **Trailer toggle was only half-disabling trailers.** Toggling a NeX-Up trailer off
  (movie or TV) ran the line `preroll.enabled = trailer.is_enabled` — but the
  `Preroll` model had **no `enabled` column**. SQLAlchemy silently accepted the
  assignment as a transient attribute that never persisted. So:
  - The trailer was correctly excluded from `nexup_trailers`-typed sequence blocks
    (which filter via `ComingSoonTrailer.is_enabled == True`).
  - But it was NOT excluded from `random`-typed sequence blocks over the NeX-Up
    category, from a schedule whose `category_id` is the NeX-Up category, or from
    `_apply_category_to_plex`. A "disabled" trailer would still play.
  - The dead `preroll.enabled = ...` line made the bug invisible to anyone reading
    the code — it looked correct.

  Fixed by adding the `enabled` Boolean column to `Preroll` (default True), an
  idempotent SQLite migration on startup, and adding
  `or_(Preroll.enabled == True, Preroll.enabled.is_(None))` to every scheduler
  preroll-pool builder (5 sites). The toggle endpoints' existing
  `preroll.enabled = trailer.is_enabled` lines now actually persist.

### Acknowledged, deferred

- **NEXUP-2** — Trailer-to-Preroll linkage uses exact-string path match. Path
  normalization drift (case on Windows, separators) could silently miss the linked
  Preroll. Needs a `_paths_equal(a, b)` helper used everywhere. Flagged for the
  cross-cutting cleanup pass.
- **NEXUP-3** — Sync in-progress detection uses a module-level dict (TOCTOU). Fine
  for single-process uvicorn. Multi-worker deploys would need a real lock.

## [1.13.9] - 05-25-2026

### Bug Fixes (categories / m2m surface audit)

- **Diagnostics page double-counted prerolls in every category.** The category stats
  block in the `/system/diagnostics` payload computed `total_in_cat = primary_count + m2m_count`
  where `primary_count` counted `category_id == X` and `m2m_count` counted
  `preroll_categories` rows. After the v1.13.0 migration backfilled m2m from the
  legacy column without nulling it, every preroll appeared in both counts — so the
  displayed count for each category was roughly 2x the real number. Replaced with a
  single distinct `or_(legacy, m2m)` query.
- **Sequence export bundle missed m2m-tagged prerolls in two places.** The
  `with_preroll_data` / `full_bundle` metadata block and the random-block
  category-folder export both filtered by `category_id == X` only. A preroll with
  the bundle's category as a SECONDARY (m2m) tag wouldn't ship in the bundle, even
  though the live scheduler would resolve it correctly. Exported community sequences
  therefore rendered differently on the receiving side. Both converted to the
  m2m-aware form used by the scheduler.

### Acknowledged, no change
- NeX-Up trailer counts (movie / TV) intentionally remain legacy-primary-only — they
  answer "what does NeX-Up manage?", not "what is tagged here", so an `or_()` would
  inflate the number if a user manually tagged an unrelated preroll into the NeX-Up
  category.

## [1.13.8] - 05-25-2026

### Bug Fixes (preview/playback subsystem follow-up)

- **Dashboard "Currently Showing" preview showed Plex's stale state instead of the
  active schedule's actual content.** Surfaced during testing of v1.13.7: clicking
  the dashboard preview when "Adult Swim Night" was the active schedule returned a
  Toy Story file from a completely different category, with "Preview unavailable"
  because the file path (`/data/prerolls/Toy Story_JFLX.mp4`) didn't exist on the
  local Windows install — it was a leftover Docker container path from a previous
  setup. The endpoint `GET /plex/current-preroll-details` always queried Plex for
  the currently-applied preroll string and matched paths to local files; if Plex's
  state was stale, behind, or pointed at paths from a different host, the preview
  would not match the user's mental model ("show me what the active schedule plays").
- **Fix:** new helper resolves the preview list from NeXroll's intent —
  `setting.active_schedule_id` for sequence schedules walks the sequence blocks,
  category schedules pull the m2m preroll list. Endpoint only falls back to Plex
  query when NeXroll has no recorded active schedule (filler mode, manual Plex
  preroll application, fresh install with no schedules yet).
- Imports `_has_valid_sequence` from `backend.scheduler` so main.py and scheduler.py
  share one definition of "is this a real sequence" instead of drifting.

## [1.13.7] - 05-25-2026

### Bug Fixes (continuing v2.0.0 prep audit — preview/playback subsystem)

- **Preview broke for uncategorized prerolls.** The simple-preview modal built its
  video URL as `static/prerolls/{category.name}/{filename}` and fell back to the literal
  string `"unknown"` when the preroll had no primary category — a legitimate state after
  v1.13.0's category retirement. The "unknown" path 404'd on the backend, and the backend's
  fallback DB lookup used a pure `category_id == X` filter that couldn't find the preroll
  either. Same bug appeared in the dashboard "Currently Showing" preview URL builder.
- **New endpoint `GET /prerolls/{id}/video`** streams a preroll's file by ID, looking up
  the stored `path` directly. No dependency on category folder structure. Works for
  uncategorized prerolls, post-migration paths, and external/unmanaged prerolls.
- **Frontend simple-preview modal and backend `currentPrerollPreview` `preview_url` now
  use the ID endpoint.** Category name is still shown in the modal title (derived from
  the m2m list now, falling back to "Uncategorized" instead of "Unknown").
- **Legacy `/static/prerolls/{category}/{filename}` endpoint hardened.** DB fallback now
  uses `or_(category_id == X, m2m has X)` and a filename-unique fallback, so old URLs
  still resolve when the category-folder match fails. Noisy `print` debug statements
  removed.

## [1.13.6] - 05-25-2026

### Bug Fixes (continuing v2.0.0 prep audit — scheduler state sync)

- **Dashboard never updated when the scheduler's Plex apply failed.** All three apply
  branches in the scheduler (sequence-only, category, and the v1.13.3 re-apply branch
  for winner changes) only updated `setting.active_category` / `setting.active_schedule_id`
  / `last_run` if Plex apply returned True. When apply failed — empty category, Plex
  unreachable, broken paths, invalid sequence blocks — the dashboard kept showing the
  old (or null) state forever, even though the scheduler had correctly determined the
  active winner. Reproduced during testing when an exclusive schedule targeted an empty
  category: scheduler logged "EXCLUSIVE: '1135 Test' wins... -> Category 8", apply
  failed (no prerolls), state never updated, dashboard reported "no category applied"
  indefinitely. The v1.12.18 toggle-handler fix already established that state should
  reflect intent (which schedule is the winner), not Plex apply result; the scheduler
  itself never got the same treatment until now. All three branches now update state
  unconditionally on winner selection and log Plex failures as warnings. The 5-minute
  `_verify_and_reapply_if_needed` pass already retries Plex sync, so the cost is just
  that the verifier tries again on the next pass — which is the desired behavior.

## [1.13.5] - 05-25-2026

### Bug Fixes (continuing v2.0.0 prep audit — dashboard state sync subsystem)

- **Schedule create/delete now triggers immediate dashboard re-sync.** Both endpoints
  committed their changes without poking the scheduler, leaving the dashboard tile and
  Plex up to 60 seconds out of sync with the database. Creating a schedule that should
  immediately be the winner, or deleting the schedule currently being applied, now
  calls `scheduler.trigger_immediate_check()` after commit — matching the v1.13.3 fix
  for `delete_category`.
- **Schedule update endpoint switched from parallel reimplementation to scheduler call.**
  `PUT /schedules/{id}` was calling `_apply_schedule_win_lose_logic` — a ~410-line
  function in main.py that reimplemented `_is_schedule_active`, sequence/category
  apply, winner selection, blend detection, filler handling, and clear_when_inactive
  in parallel with the scheduler's own logic. Any fix made to the scheduler (including
  the v1.13.3 SCHEDULER-1 fix) did NOT propagate to this code path, so toggling a
  schedule could produce subtly different results than the scheduler's normal tick.
  The call site now uses `scheduler.trigger_immediate_check()` for one source of truth.
  The dead 410-line function is left in place this release — flagged in AUDIT.md as
  MAIN-1 for removal in the cross-cutting cleanup pass.

## [1.13.4] - 05-25-2026

### Bug Fixes (continuing v2.0.0 prep audit)

- **Schedule list badge flipped a "Simple" schedule to "Sequence (0 blocks)" after
  disable/enable.** The toggle handler was running `typeof schedule.sequence === 'object'`
  to detect parsed-array vs raw-string sequences. Because `typeof null === 'object'` in
  JavaScript, a `null` sequence took the `JSON.stringify(null)` branch and the literal
  string `"null"` (4 chars) was sent to the backend as the schedule's sequence. The
  backend stored it; the next render saw a non-empty sequence string and the badge
  flipped from "Simple" to "Sequence (0 blocks)". Backend scheduler behavior was
  unaffected because `_has_valid_sequence` correctly rejects `"null"`, so this was a
  pure UI regression. Toggle handler now explicitly normalizes `null`/`undefined` to
  empty string, and the schedule-card badge now derives `hasSequence` from the parsed
  block count (mirroring backend semantics) rather than the raw-string truthiness.

### Audit Findings (documented, deferred)

- **SCHEDULER-5 (UX, deferred):** No visible indication of why one schedule is the active
  winner when multiple schedules target the same category. Winner selection sorts by
  `(-priority, end_date, start_date, id)`, so a schedule with a defined `end_date` will
  outrank one with `end_date = null` (treated as `datetime.max`) even at equal priority.
  This caught a tester off-guard during validation of the v1.13.3 SCHEDULER-1 fix:
  "Christmas Schedule" with `end=2027-12-31` beat two test schedules that had no
  `end_date`, so the test scenario for the fix wasn't actually being exercised. Tracked
  for v2.0.0 — needs a frontend "winner" badge on the Schedules page and a hover/side
  panel explaining the tiebreaker, plus consideration of whether the "earliest end date
  wins" default is the right one.

## [1.13.3] - 05-25-2026

### Bug Fixes (first slice of the v2.0.0 prep audit)

- **Scheduler did not re-apply when the winning schedule changed but the category did not.**
  If two schedules shared a `category_id` and the winner flipped from one to the other
  (priority change, another schedule toggled off, blend partner dropped out, etc.), the
  scheduler took the "already active" code path and never sent the new schedule's
  sequence to Plex. This is the most likely cause of the user-reported "alt year-round
  schedule applied the category pool instead of its sequence" symptom. The fix detects
  `active_schedule_id != chosen_schedule.id` and forces a re-apply via the sequence
  path (or category path) depending on the new schedule's shape.

- **"Currently Showing" dashboard tile briefly showed "No category applied" after
  deleting a category.** `delete_category` correctly cleared the applied state but the
  next scheduler tick was up to 60 seconds away, leaving the dashboard empty in the
  interim and forcing users to manually toggle a schedule to recover. Added a new
  `scheduler.trigger_immediate_check()` helper that runs one scheduler pass synchronously;
  `DELETE /categories/{id}` now calls it after committing so the next winner is recomputed
  before the response returns.

### Internal

- Added `AUDIT.md` at the repo root tracking the in-progress v2.0.0 code audit. Each
  finding has a severity (BUG / DISCONNECT / DEAD / UX / DOC) and a status (OPEN /
  FIXED / DEFERRED). Subsystems still pending: categories/m2m surface area, dashboard
  state sync, preview/playback, import & scanner, backup/restore, Plex/Jellyfin/Emby
  plugin endpoints, settings flow, auth/sessions, cross-cutting consistency.

## [1.13.2] - 05-24-2026

### UI Polish
- **Preroll Library Filter Bar Redesign** — The Library page's filter row had dated styling (uppercase letter-spaced labels above every field, awkward sizing with a 70 px wide "Per Page" selector next to 140 px filters, emoji prefixes on Status options) and required a manual "Apply" click for filters that were already applying client-side. v1.13.2 reworks it:
  - **Search is now the dominant top-row element** with a wider input, larger placeholder copy, and the search icon inside the field. The View toggle (Grid/List) sits at the right edge of the same row, visually separated from filtering since it controls display, not what is shown.
  - **Filters move to a second row** with consistent sizing: Category (220 px min, enough to fit "Christmas/New Years" and "Test External Category"), Status (170 px min), and a per-page selector inline-grouped with its label ("Show 20 per page") pushed to the right.
  - **Apply button removed.** Filters auto-apply (they already did — the button was an artifact). Pagination automatically resets to page 1 when any filter changes, including Status which was previously not in the reset trigger.
  - **Active filter chips** render below the bar when filters are set: e.g. `Category: Christmas ×`, `Matched only ×`, `Search: "alien" ×`. Each chip has an inline × to remove just that filter, and a `Clear all` link removes everything.
  - **Status options lose the ✅ / ⚠️ emoji prefixes** in favor of plain text labels that match the rest of the app's Lucide-icon look.
  - **Labels gone** — fields are self-describing through placeholders and the pill of the View toggle. Reduces visual noise without losing affordance.

## [1.13.1] - 05-24-2026

### New Features
- **Import Folder: Optional Category + Subfolder Inference** — Previously the Import Folder workflow forced the user to pick a single category before doing anything, and silently dropped every imported file into that one category (or auto-created and used "Default" if none was selected). v1.13.1 aligns this with the v1.13.0 categories-as-labels model:
  - **Category is now optional.** The picker shows *"— Auto / leave uncategorized —"* by default. Pick a specific category only if you want every imported file forced into one label.
  - **Auto-categorize from subfolders** (on by default). Each file's immediate parent folder name is used as its category. A file at `/import/Christmas/intro.mp4` lands in the "Christmas" category if one exists; a file at the root of the import path has no folder hint and lands uncategorized.
  - **Create missing categories** (off by default, opt-in checkbox). When a subfolder name does not match an existing category, NeXroll creates a new category with that name and tags the file with it. Useful for first-time setup with an already-organized folder tree.
  - **Files NeXroll cannot resolve a category for are left uncategorized** — no more silent "Default" bucket. They appear in the new Prerolls page Uncategorized filter (v1.13.0) so you can tag them later.
  - **Per-category preview in dry-run.** The result panel now shows pill-style chips like `Christmas: 12`, `Halloween: 8`, `(uncategorized): 3` so you can see exactly where everything will land before you click Import.
  - The forced "Please select a category" validation error and the red-bordered category picker are gone.

### API Changes
- `POST /prerolls/map-root` accepts two new fields:
  - `auto_categorize_from_folders` (bool, default `true`) — derive category from parent folder
  - `create_missing_categories` (bool, default `false`) — create new categories on the fly when a folder name does not match an existing one
- Response now includes a `per_category` array (`{category, to_add}` for dry-runs, `{category, added}` for actual imports). The legacy single `category` field on the response is replaced by `forced_category` (the explicit override, or `null` if none was given).

## [1.13.0] - 05-24-2026

### New Features
- **Retire User-Visible "Primary Category" Concept (Issue #29, Phase 1)** — The primary/secondary distinction on a preroll's category memberships caused real friction: the "Remove from Category" button was permanently disabled for whichever category was a preroll's "primary", and deleting a category required either manually reassigning every preroll first or going through a multi-step workaround. v1.13.0 changes the user-facing model so categories are simple labels:
  - **"Remove from Category" is now always enabled.** Any preroll can be removed from any of its categories. The button no longer greys out and no longer shows the misleading "Cannot remove primary here" tooltip. If the removed category happened to be the legacy primary, the backend clears that column too.
  - **Deleting a category is one step.** Previous behavior required manually reassigning every preroll to a new "primary" first. v1.13.0 simplifies it: deleting a category removes the grouping from every preroll that had it, disables any schedules that targeted it (the user picks a new category before re-enabling), clears schedule fallback references, deletes holiday presets that pointed at it, and clears setting fields — all in one transaction. Prerolls that lose their last category become **uncategorized** and remain in NeXroll; their files on disk are never touched.
  - **New "Uncategorized" filter** on the Prerolls page (in the Category dropdown) surfaces prerolls with zero categories. Useful for cleaning up after a category delete, or for finding files that the v1.12.21 filesystem scanner picked up but couldn't categorize.
  - **The category-delete confirmation dialog** now shows what will actually happen ("Remove this category from N prerolls; X of those will become uncategorized") instead of a generic warning.
- **Startup Migration: Backfill Many-to-Many** — On first launch, every preroll's legacy `category_id` is also added to the `preroll_categories` m2m table if it was not already there. This makes the m2m table the canonical source of category memberships going forward and is a no-op on subsequent launches. The `category_id` column is kept populated for backward compatibility with the rest of the codebase; it will be retired in a future release.

### Deferred to Future Release
Per Issue #29, the full structural refactor includes additional work that is **not in v1.13.0**:
- Flat file storage (new uploads still go to per-category subfolders for now)
- Removal of the `category_id` column from the `prerolls` table
- Conversion of every remaining backend filter query from `category_id == X` to m2m
- Removal of the "primary" star picker from the preroll edit modal (the picker still appears but no longer affects the "Remove from Category" UX described above)

These will land in v1.13.x once v1.13.0 has been validated in the field.

## [1.12.21] - 05-24-2026

### New Features
- **Preroll Filesystem Scanner / Cross-Platform Migration Fix** — Restoring a JSON backup from one platform to another (e.g. Windows -> Docker) used to leave every preroll row pointing at a path that does not exist on the target machine (`C:\Users\...` on a Linux container). Thumbnails 404'd, Plex apply failed, and the user had to manually rebuild everything. NeXroll now ships a filesystem scanner that walks `PREROLLS_DIR`, matches files to existing database rows by category folder + filename, and rewrites the `path` field to the real on-disk location. Missing thumbnails are regenerated. Files that exist on disk but have no corresponding database row are added automatically and assigned to a category when their parent folder name matches an existing category (otherwise they are left uncategorized). The scanner runs:
  - At startup (set `NEXROLL_SCAN_ON_STARTUP=0` to disable on huge libraries)
  - Automatically after a successful JSON database restore — the restore response now includes a `rescan` summary that the UI surfaces in its success toast
  - On demand via the new **Rescan Files** button on the Backup & Restore page, backed by `POST /prerolls/rescan`
  
  This means a Windows -> Docker migration is now: install Docker NeXroll, restore the JSON backup, copy your prerolls into the mounted volume, click Rescan. The endpoint also reports counts of paths relinked, thumbnails generated, new files found, and files still missing so users can verify the migration succeeded.

## [1.12.20] - 05-23-2026

### Bug Fixes
- **Currently Showing Tile Shows Category Name Instead of Schedule Name After Upgrade** — Users upgrading from versions before v1.12.17 had `active_category` populated in their database but no `active_schedule_id` (the column didn't exist on the older version). On first launch of the new version, the dashboard tile briefly displayed the category name (e.g. "Christmas") instead of the schedule name (e.g. "Christmas Schedule") until the next scheduler tick (up to 60 seconds later), or longer if the schedule happened to be out of its active window. The `/settings/active-category` endpoint now adds a fallback: when `active_schedule_id` is unset but `active_category` is populated, it looks up the most recently run active schedule whose primary category matches and uses its name. This eliminates the post-upgrade race window without changing any scheduler behavior.

### New Features
- **Delete Category Without Manually Clearing Prerolls and Schedules** — Previously, deleting a category required removing or reassigning every preroll and schedule that referenced it first, and the UI just showed "Category must be empty before deleting." The delete flow now handles reassignment automatically:
  - Prerolls with the category as their PRIMARY category are reassigned to the built-in `Default` category. Video files on disk are NOT touched.
  - Secondary (many-to-many) category tags pointing at the deleted category are removed.
  - Schedules that reference the category are DISABLED and reassigned to `Default`, so they don't accidentally apply unintended prerolls when re-enabled.
  - Schedule fallback references (`fallback_category_id`) are cleared.
  - Holiday presets that point at the category are removed (the column is NOT NULL on this table).
  - Setting fields that point at the category (`active_category`, `filler_category_id`, `last_schedule_fallback`, `active_schedule_id`) are cleared.
  
  A new `GET /categories/{id}/delete-impact` endpoint returns counts of everything that would be affected, and the delete confirmation dialog now shows a detailed preview ("This will reassign N prerolls to Default and disable M schedules") before the user confirms. System categories (NeX-Up Trailers, NeX-Up TV) and the `Default` category itself remain protected from deletion.

## [1.12.18] - 05-15-2026

### Bug Fixes
- **Sequence Blend Interleaves Instead of Randomly Picking One Sequence** — When two or more blend-enabled sequence schedules were active simultaneously, the scheduler collected prerolls from both sequences and interleaved them into a combined playlist. Sequences are ordered and should not be mixed. The scheduler now detects when all blend candidates have sequences and randomly picks one per tick, applying it as a complete sequence. `active_schedule_id` is set to the chosen schedule so the preview button and Emby/Jellyfin plugin serve the correct sequence. On the next tick a different sequence may be randomly selected.
- **Currently Showing Tile Displays Category Name Instead of Schedule Name** — When a schedule with a sequence was active, the "Currently Showing" tile displayed the category name (e.g. "Christmas") rather than the schedule name. The `/settings/active-category` endpoint now includes `active_schedule_name` from the `active_schedule_id` tracking field, and the frontend uses it as the primary title with the category name shown beneath as secondary context.
- **Blend Mode Sets Wrong active_category, Showing First Schedule's Category as "Currently Showing"** — During blend mode the scheduler wrote the first blend schedule's category ID to `active_category` as a tracking shortcut. This caused the "Currently Showing" tile to display that category name (e.g. "Adult Swim") even though blend was active. The scheduler now sets `active_category` to null during blend mode, matching the intent of the `get_active_category` blend detection which expects null to signal blend state.
- **Disabled Schedule Leaves Stale Category in Dashboard and Plex** — When a schedule was disabled, the "Currently Showing" dashboard tile and Plex's preroll field continued to show the old category. The toggle handler only updated `active_category` and `active_schedule_id` when the Plex API call succeeded. Users without Plex configured (Emby/Jellyfin-only) or with Plex temporarily unreachable never got the state update. Settings state is now always updated regardless of Plex reachability — Plex apply remains best-effort.
- **Blend Mode Not Detected in Toggle Disable Path** — When a schedule was disabled and the remaining active schedules were configured for blend mode, the toggle handler selected a single winner and set `active_schedule_id` to that schedule's ID, leaving the scheduler in an inconsistent state until its next tick. The toggle now detects blend mode among the remaining schedules and clears `active_schedule_id` so the scheduler re-evaluates cleanly.
- **Toggle Applies Wrong Winner When Day-of-Week Restriction Not Met** — When disabling a schedule, the toggle handler selected the next "winner" from all `is_active=True` schedules by priority, without checking whether each candidate was within its current day-of-week, month, or monthDay window. A Friday-only schedule could be incorrectly applied on a Thursday. The handler now applies the same weekDays, months, and monthDays checks as the scheduler when evaluating candidates.
- **Blend Mode Indicator Not Shown During Active Blend** — The "Currently Showing" tile showed nothing during active blend because the blend detection logic in `/settings/active-category` only ran inside the `active_category != null` branch. During blend, the scheduler sets `active_category` to null, so the detection never fired. Blend detection now runs unconditionally before the null check and returns a synthetic blend category object when two or more blend-enabled schedules are in their active windows.
- **Mixed Blend (Sequence + Standard Category) Shows "No Category Applied"** — When a sequence schedule and a standard category schedule were both blend-enabled and active at the same time, the "Currently Showing" tile showed "No category applied". The scheduler correctly entered category blend mode and applied prerolls to Plex, but blend detection in `get_active_category` used a `_schedule_in_date_window` check that diverges from the scheduler's own `_is_schedule_active` logic for overnight and yearly-type schedules. Unified blend detection to rely solely on `last_run` timestamps: the scheduler stamps `last_run` on all blend partners each tick for all blend types (sequence+sequence, category+category, and mixed), and the endpoint now identifies active blend by finding two or more blend-enabled schedules with `last_run` within the last three minutes.
- **Sequence Blend last_run Staleness When Same Sequence Picked Twice** — When sequence blend randomly selected the same sequence on consecutive ticks, `last_run` was not refreshed on the blend partners, causing the three-minute blend detection window to eventually expire and the tile to revert to "No category applied". The scheduler now refreshes `last_run` on all blend partners every tick regardless of whether a different sequence was chosen.
- **Mixed Blend Only Applies Standard Category, Ignores Sequence Schedule** — When a sequence schedule and a standard category schedule were both blend-enabled, only the standard category's prerolls were applied to Plex. The blend path used an interleave approach that tried to extract individual prerolls from sequence blocks, but block types not explicitly handled in that path silently contributed zero paths, dropping the sequence schedule from the result. The blend logic now uses a unified "randomly pick one per tick" approach whenever any blend partner has a sequence: the chosen schedule is applied in full (complete sequence or full category), which preserves sequence ordering and ensures both schedules get turns.
- **Pure Category Blend Shows "No Category Applied" and No "Playing:" Indicator** — When two or more plain category schedules were blend-enabled, the scheduler interleaved their prerolls into a single pool and set both `active_category` and `active_schedule_id` to null. The "Currently Showing" tile relied on the `last_run` proxy to detect blend mode, but had no `active_schedule_name` to display, leaving the tile with no "Playing:" line. Interleaving is also inconsistent with how sequence and mixed blend work. The pure category blend path now uses the same "randomly pick one per tick" pattern as all other blend types: one schedule is chosen each tick, its full category pool is applied, and both `active_category` and `active_schedule_id` are set — giving the tile the same "Playing: Mother's Day Schedule" indicator it shows for other blend types.
- **Schedule Settings (Blend, Exclusive, Priority) Reset When Toggling Enable/Disable** — When toggling a schedule on or off using the enable/disable switch, the schedule's `blend_enabled`, `exclusive`, `priority`, `holiday_name`, and `holiday_country` settings were reset to their defaults (false/false/5/null/null). The toggle handler sent a PUT request that omitted these fields entirely, causing the backend to overwrite them with Pydantic model defaults. The toggle handler now includes all schedule fields in the request body.

### New Features
- **Blend Mode Indicator in Currently Showing Tile** — When two or more schedules are blending, the "Currently Showing" tile now displays the blending schedule names (e.g., "Blending: Christmas Schedule + Holiday Extras") instead of the playback mode. The indicator is computed live from the active schedule state so it updates automatically when blend conditions change.

## [1.12.17] - 05-09-2026

### Bug Fixes
- **Emby/Jellyfin Plugin Ignores Configured Sequence, Plays All Prerolls** — When a schedule with a sequence was active, the `/plugin/intros` endpoint returned all prerolls from the active category instead of the sequence-defined subset. The scheduler correctly applied the sequence to Plex but had no way to communicate the active schedule to the plugin endpoint. Added `active_schedule_id` tracking to the settings table so the scheduler writes which schedule is currently active on every tick. The plugin endpoint now reads `active_schedule_id`, resolves the schedule's sequence blocks, and returns only those paths — in order — instead of the full category pool. Affects sequence-only and category+sequence schedules. Filler and fallback category behavior is unchanged.

## [1.12.16] - 05-08-2026

### Bug Fixes
- **UI Returns {"detail":"Not Found"} After Running for a While (Windows)** — On Windows, PyInstaller extracts the bundled frontend into a _MEI* temp folder on startup. Windows Disk Cleanup, Storage Sense, and tools like CCleaner delete temp folders while the service is still running, wiping the static files. The FastAPI backend survives but can no longer serve the UI, returning {"detail":"Not Found"} for every page load until the machine is rebooted. Fixed by copying the frontend from the temp extraction directory to C:\ProgramData\NeXroll\frontend on every startup. ProgramData is never cleaned by temp tools, so the UI remains available even after Windows clears the temp directory.

## [1.12.15] - 04-30-2026

### Bug Fixes
- **Sequence Schedule Blending** — Sequence schedules with NeX-Up Trailers, Coming Soon List, or Dynamic Preroll blocks were silently contributing zero prerolls when blended, causing them to drop out of the blend. All three block types are now handled in the blend path identically to the normal sequence executor.
- **Duplicate Trailers in NeX-Up** — Concurrent sync calls (Radarr and Sonarr) could race and insert multiple records for the same movie/show. Sync endpoints now reject a second call while one is already in progress. Startup deduplication removes any existing duplicate records on boot.
- **Disabled Trailer Still Playing** — Disabling a movie trailer in Your Trailers did not update the linked Preroll record, so random category blocks continued to serve it. The movie trailer toggle now mirrors the TV trailer toggle and keeps both records in sync.
- **Duplicate Log Lines** — Every log entry was written twice because the same file handler was attached to both the root logger and each child module logger. Removed the redundant per-module handler registrations.
- **Startup Hash Migration Crash** — `calculate_file_hash` was defined after the background thread that called it was started, causing a `NameError` on first run. Moved the definition above the migration function.
- **"No Browser Detected" Log Spam** — Browser cookie detection logged an INFO message on every NeX-Up settings request. Downgraded to DEBUG.
- **Max Trailers Limit Counting Duplicates** — `current_count` was a raw row count, so duplicate records could exhaust the trailer limit before unique movies were reached. Now counts distinct `radarr_movie_id` values.

## [1.12.14] - 04-24-2026

### New Features
- **Sequence Block Types: NeX-Up Trailers, Coming Soon List, Dynamic Preroll** — Three new block types in the Sequence Builder. NeX-Up Trailers pulls downloaded trailers (movies/TV/both) with configurable count. Coming Soon List inserts a generated compilation video (grid or list layout). Dynamic Preroll inserts a generated preroll video with template + theme selection. Full support across block editor, timeline, statistics, preview, export/import, scheduler, and Plex apply.
- **Emby Server Support** — Full Emby integration as a first-class media server alongside Plex and Jellyfin. Includes the NeXroll Intros Plugin for Emby implementing `IIntroProvider` for Cinema Mode preroll injection.
- **Plugin Auto-Detection & Remote Configuration** — Detect Plugin and Configure Plugin buttons on Jellyfin and Emby connection pages. Configure pushes NeXroll URL, auto-generated API key, and path mappings directly to the plugin. Keys are scoped read-only and rotated on each configure.
- **Conflict Resolution Page** — Dedicated Conflicts tab in Schedules sub-navigation with Weekly/Monthly/Yearly timeframe selector, side-by-side schedule comparison cards, suggested fixes, Auto-Resolve All, Apply Fixes with results view, and ignored conflicts management.
- **Yearly Schedule Type** — Fully supported schedule type alongside Daily, Weekly, Monthly, and Holiday. Year-agnostic recurrence compares month+day windows across all years. Supports optional Holiday API auto-update.
- **Monthly Schedule: Month Selector** — Monthly schedules now use a Jan-Dec month selector instead of date pickers. Pick which months of the year the schedule is active. Includes optional Start Time / End Time window for the selected days.
- **Dashboard Scheduler Countdown Timer** — Scheduler tile shows a live D/H/M/S countdown to the next schedule activation with schedule name.
- **Forgot Password / Local Password Reset** — Forgot password link on the login page when accessed from localhost. Resets admin password, clears lockouts, and invalidates all sessions. Restricted to local requests only.
- **Drag & Drop Upload** — Prerolls upload area supports drag & drop for video files alongside the existing click-to-browse.
- **Language Options for NeX-Up Generators** — Dynamic Preroll and Coming Soon List generators support English, French, Spanish, and German. Language preference saved per generator and respected on auto-regeneration.
- **Coming Soon List: Logo Position Options** — Custom logo overlay supports Watermark, Right of Title, and Below Title placement with live preview.
- **NeX-Up: Expanded Max Trailers** — Max Trailers to Keep expanded to 50, plus a No Limit option for large libraries (still bounded by Max Storage GB).
- **Ignore Conflicts** — Ignore option on each conflict card hides it from future scans. Show Ignored toggle reveals them with one-click Restore.
- **API Keys: Multi-Select Bulk Delete** — Select All and per-row checkboxes on the API Keys list. Delete Selected (N) bulk-deletes in a single operation.
- **Sequence Random Block Rotation** — Random blocks in sequences now rotate on a 10-minute interval (was 5 minutes).

### Bug Fixes
- **Sequence Schedule Blending** — Sequence schedules with NeX-Up Trailers, Coming Soon List, or Dynamic Preroll blocks were silently contributing zero prerolls when blended, causing them to drop out of the blend. All three block types are now handled in the blend path identically to the normal sequence executor.
- **Jellyfin Plugin: Fails to Load on Jellyfin 10.11.x** — Plugin DLL rebuilt against the current 10.11.x SDK (`Jellyfin.Database.Implementations.Entities.User`). Resolves `ReflectionTypeLoadException` / `GetIntros has no implementation` on startup.
- **NeX-Up: Radarr / Sonarr Connection Fails with HTTP 307** — `httpx` defaulted to not following redirects. In Docker, Radarr/Sonarr commonly issue 307s when a Base URL or reverse proxy is in use. All API client calls now set `follow_redirects=True` with an actionable error message if a redirect still cannot be resolved.
- **Event Log: Per-Row Horizontal Scrollbars** — Long error messages generated individual horizontal scrollbars per row. Log entries now wrap within the terminal panel.
- **Scheduler Not Applying Correct Schedule** — Schedules with `sequence` stored as the string `"null"` were treated as having a valid sequence, causing silent apply failures. Added `_has_valid_sequence()` validation across all 8 sequence checks.
- **NeX-Up: Orphan Preroll Records in Sequence Random Pools** — Deleted/expired trailer files left orphan preroll records that silently 404'd when picked by random blocks. All sequence resolution paths now filter random pools to prerolls with existing files via `os.path.exists()`. Radarr sync and trailer expiry also delete the corresponding preroll record.
- **Sequence Preview: Now Playing Label Desyncs** — Preview playlist was rebuilt every 30 seconds on background poll, re-shuffling random picks mid-playback. Props are now snapshotted at modal-open; playlist is built once and immune to background refreshes.
- **Plugin Detect: API Key Leak** — Detect endpoints were auto-creating API keys on every call when NexrollUrl was empty, generating thousands of orphaned keys on repeated page loads. Detect is now read-only; key creation is reserved for explicit `/configure` endpoints only.
- **Plugin Configure: Silent Failure & Key Accumulation** — Configure endpoints silently swallowed exceptions and created a fresh key on every call without deleting old ones. Now returns detailed diagnostics, deletes inactive auto-generated keys before creating a new one, and rolls back the new key if the config push fails.
- **Plugin Detect: 30-Second Polling** — Plugin detect calls were embedded in `fetchData()` (runs every 30s), generating ~2,700 API calls per day. Detection now only fires on connection status changes.
- **Preview Playback Skipping** — Sequence and dashboard preview players skipped after ~1 second due to spurious `onEnded` events from `key`-based video remounting. Both players now reuse a single stable `<video>` element with source swaps via `useEffect`.
- **Plex Disconnect Deletes Stable Token** — Disconnecting from Plex permanently destroyed the Windows Credential Manager token. Disconnect now only clears DB state, preserving the stored token.
- **Update Checker Not Detecting New Versions** — Five bugs fixed: version string normalization stripping pre-release suffixes, wrong response fields in auto-check, wrong field name in interval check, stale state in second check button. Backend now uses proper semver parsing with pre-release ordering.
- **NeX-Up YouTube Status: Access Denied** — `GET /nexup/youtube/status` crashed with `[WinError 5]` using a relative `'temp'` path resolving to the unwritable Program Files directory. Now uses `PREROLLS_DIR/nexup_temp`.
- **Require Login Toggle Enabled Without Users** — Toggle could lock users out if enabled before any accounts existed. Now greyed out until at least one user exists. Toggle state also refreshes correctly after first user creation.
- **Sequence Builder: Random Block Preview Count** — Preview modal now respects the `count` field on random blocks instead of always picking 1.
- **Yearly Schedule: False Validation Error** — Yearly schedule validation was incorrectly flagging valid schedules as missing date ranges.
- **Schedule Creation: is_active Not Preserved** — `buildScheduleData()` now preserves the `is_active` field so toggling a schedule on/off is not lost when saving.
- **Log Rotation: Multiple Writers** — Fixed log rotation creating 3 concurrent file writers; consolidated to a single handler.
- **Docker CVE Remediation** — Upgraded pip in Dockerfile to address CVE-2025-8869 and CVE-2026-1703.

### Build
- Version bumped to 1.12.14 (stable release, no beta suffix).
- Windows installer, NeXroll.exe, NeXrollService.exe, NeXrollTray.exe rebuilt.

---
## [1.11.12] - 03-09-2026

Hotfix release addressing Coming Soon List generation failures, grid layout clipping, and adding comprehensive database logging.

### Bug Fixes
- **Sequence Schedule Blending** — Sequence schedules with NeX-Up Trailers, Coming Soon List, or Dynamic Preroll blocks were silently contributing zero prerolls when blended, causing them to drop out of the blend. All three block types are now handled in the blend path identically to the normal sequence executor.
- **Coming Soon List: Unicode Character Fix** — Fixed `●` (U+25CF) bullet character causing FFmpeg `EINVAL` failure and `UnicodeDecodeError` on Windows (replaced with ASCII `>`)
- **Coming Soon List: Apostrophe Escaping** — Fixed ASCII apostrophe `'` breaking FFmpeg's `drawtext` option-value delimiter (replaced with typographic `'` U+2019 in text escaping)
- **Coming Soon List: Auto-Regen Max Items** — Fixed `_auto_regenerate_coming_soon_list()` ignoring the user's max items setting (always defaulting to 8)
- **Coming Soon List: Grid Layout Poster Clipping** — Redesigned grid layout so ≤6 items use a single row and >6 items use two rows, preventing bottom-row posters from being clipped below 1080px

### Improvements
- **Comprehensive Database Logging** — Added `log_event()` calls across all major areas of the application so warnings and errors now appear in the Settings > Logs UI (previously only written to `app.log` file)
  - Covers: Plex/Jellyfin connect/disconnect, community prerolls, external API, preroll management, scheduler, sequences, holidays, backup/restore, thumbnails, NeX-Up sync, trailer downloads, dynamic preroll generation, system settings, and more

---

## [1.11.9] - 03-05-2026

First stable release of the v1.11.x line (consolidates beta.1–beta.9).

### Coming Soon List Generator
- **Background Music** — Toggleable ambient audio with smooth fade-in/out
- **Custom Audio Upload** — Replace default track with .mp3, .wav, .aac, .m4a, .ogg, .flac
- **Custom Logo Overlay** — Watermark or Replace Server Name mode (.png, .jpg, .webp)
- **Available Now! Feature** — Badge for downloaded items with configurable grace period (1–30 days) and max items limit
- **Release Date Preference** — Digital First, Digital Only, Physical First, Theatrical
- **Exclusion Filtering** — Excluded items correctly filtered from generated videos and auto-regeneration
- **Options Panel** — Reorganized into clean 2×2 grid with unified card style
- **Color Settings** — Expanded by default instead of collapsed
- **Auto-Regeneration** — Regenerates on Radarr/Sonarr sync with fresh DB sessions and proper async handling

### Dynamic Preroll Generator
- **Custom Logo Overlay** — Upload logo for Coming Soon, Feature Presentation, and Now Showing templates

### NeX-Up Enhancements
- **Calendar View** — Full monthly grid with color-coded movies/TV/Available Now items
- **Your Trailers Page** — Play button for browser preview, List/Detailed view toggle
- **Sync Timestamp Fix** — Uses local time consistently (no future-time display)
- **Next Sync Display** — Radarr/Sonarr cards show "Last synced · Next sync" countdown
- **TMDB API Key Security** — Masked password-style input field
- **Upcoming Counts** — Load automatically when opening NeX-Up tab

### Plex Connector — Critical Fixes
- **Removed Destructive Fallback Cascade** — `set_preroll()` no longer clears all prerolls via `""` fallback
- **Auto-Chunking for Large Libraries** — Random subset selection when preroll string exceeds Plex limits (~7,500 chars)
- **8-Hour Rotation Cache** — Chunked subset cached and rotated every 8 hours; auto-invalidates on list changes
- **Preroll String Length Protection** — Warnings and Method A auto-skip when URL exceeds 8,000 chars
- **Preroll Path URL Encoding** — Fixed `#` characters in filenames causing silent path truncation
- **Preference Name Filtering** — Only actual preroll path preference names are tried
- **Missing TLS Verify Parameter** — Added `verify=self._verify` to retry PUT request

### Community Prerolls
- **Community Server Selector** — Choose from available servers or enter custom URL
- **Server Load Protections** — Rate limiting, global locks, caching (10min/30min)
- **Custom User-Agent Header** — `NeXRoll/{version}` on all outbound requests
- **Server URL Fix** — Corrected endpoint from `test.prerolls.uk` to `prerolls.uk`

### Configurable Preroll Storage
- **New Storage Tab** in Settings — Move prerolls to any local or network path
- **File Transfer** — Transfer existing files to new location with one click
- **Reset to Default** — Return to installation path

### Scheduler Fixes
- **SessionLocal Scoping** — Fixed redundant import shadowing module-level import
- **PyInstaller Module Re-execution** — Uses `sys.modules` instead of `from backend.main import` to avoid spawning second server instance

### UI / Theming
- **Header Icon Theming** — All 26+ icons follow active theme (white/black)
- **Generator Page Consistency** — Unified styles between Dynamic Preroll and Coming Soon generators
- **Emoji-to-Icon Cleanup** — All emoji characters replaced with Lucide React icons

### Bug Fixes
- **Sequence Schedule Blending** — Sequence schedules with NeX-Up Trailers, Coming Soon List, or Dynamic Preroll blocks were silently contributing zero prerolls when blended, causing them to drop out of the blend. All three block types are now handled in the blend path identically to the normal sequence executor.
- **FFmpeg Detection** — Fixed unterminated docstring in `dynamic_preroll.py`
- **Coming Soon List Grace Period** — Items past grace period properly excluded
- **Server Name Input Width** — Adjusted from 100% to 80%

---

## [1.11.0] - 02-19-2026

### New Feature 1: Coming Soon List Generator

Generate dynamic video prerolls that showcase your upcoming movies and TV shows from Radarr and Sonarr.

#### Features
- **Two Layout Styles**:
  - **List Mode** - Clean text-only layout with titles and release dates
  - **Grid Mode** - Visual poster grid with movie/show artwork (220x330px posters)
- **Content Sources** - Choose from Movies only, Shows only, or Both
- **Color Customization** - Full control over background, text, and accent colors
- **Configurable Duration** - Set video length from 5 to 20 seconds
- **Max Items** - Control how many titles are displayed (4-12 items)
- **Auto-regeneration** - Automatically re-generate when NeX-Up syncs with Radarr/Sonarr
- **System Category Integration** - Videos auto-register to "Coming Soon Lists" category
- **Sequence Builder Ready** - Generated videos appear in available prerolls for sequences
- **Video Preview Modal** - Watch generated videos in a centered modal overlay

#### Technical Details
- Uses FFmpeg for video generation
- Automatically downloads poster images for grid layout
- Falls back to text layout if poster download fails
- Staggered fade-in animations for each item

---

### New Feature 2: Authentication System

Secure NeXroll access with API keys and optional username/password authentication.

#### API Key Authentication
- **Generate API Keys** - Create unique API keys for external access (nx_... format)
- **API Key Management UI** - View, create, revoke API keys in Settings > API Keys tab
- **Key Permissions** - Scoped permissions (read-only, full access)
- **Key Expiration** - Optional expiration dates (24h, 7d, 30d, 90d, 1y, never)
- **Secure Storage** - SHA256 hashed keys in database (only prefix stored for display)

#### External API Endpoints
- `GET /external/status` - System status and connection info
- `GET /external/prerolls` - List all prerolls
- `GET /external/schedules` - List all schedules
- `GET /external/now-showing` - Current active category, preroll string, active schedules
- `GET /external/active-schedules` - Detailed info on currently active schedules
- `GET /external/categories` - All categories with preroll counts
- `GET /external/coming-soon` - Upcoming movies/TV from NeX-Up (source, limit params)
- `GET /external/sequences` - All saved sequences
- `POST /external/sync-plex` - Trigger Plex sync (requires full access)
- `POST /external/categories` - Create a new category (requires full access)
- `POST /external/prerolls/register` - Register existing video as preroll (requires full access)
- `POST /external/prerolls/{id}/assign-category/{category_id}` - Assign preroll to category
- `POST /external/schedules` - Create a new schedule (requires full access)
- `DELETE /external/schedules/{id}` - Delete a schedule (requires full access)
- `PUT /external/schedules/{id}/toggle` - Enable/disable schedule (requires full access)
- `POST /external/apply-category/{id}` - Apply category to Plex immediately

#### Username/Password Authentication
- **User Accounts** - Create admin and user accounts
- **Login Page** - Login form before accessing NeXroll
- **Session Management** - Secure session tokens with expiration
- **Password Hashing** - Secure bcrypt password storage
- **Remember Me** - Optional "remember me" for longer sessions (30 days)
- **Logout** - Secure logout functionality

#### Security Features
- **HTTPS Support** - Configurable "Require HTTPS" setting in auth settings
- **CORS Configuration** - FastAPI middleware with configurable origins
- **Failed Login Protection** - Account lockout after 5 failed attempts (15 min)
- **Audit Log** - Log authentication events with viewer UI

---

### New Feature 3: Enhanced Update System

Improved update detection with configurable checking and notifications.

#### Update Detection
- **Auto-Check on Startup** - Check for updates when NeXroll starts
- **Configurable Check Interval** - How often to check (startup, hourly, daily, weekly, never)
- **Pre-release Channel** - Option to include beta/pre-release versions
- **Changelog Display** - Show what's new with markdown rendering

#### Update Notifications
- **Dashboard Notification** - Prominent update card on dashboard overview
- **Version Comparison** - Show current vs available version
- **Update Notes Summary** - Release notes with markdown support
- **Dismiss/Remind Later** - Dismiss synced to backend for persistence

---

### New Feature 4: Enhanced Logging System

Better debugging and troubleshooting capabilities.

#### Log Management
- **Log Viewer UI** - View logs directly in NeXroll web interface (Settings > Logs tab)
- **Log Level Filtering** - Filter by DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Search** - Search through log entries by message text
- **Log Export** - Download logs as JSON or CSV file
- **Log Rotation** - Automatic cleanup of old logs (configurable retention days)

#### Structured Logging
- **JSON Log Format** - Structured logging with details JSON field
- **Request Logging** - Log all API requests with timing (duration_ms)
- **Category-based Logging** - Logs categorized by: system, scheduler, api, user, plex, jellyfin, nexup
- **Request ID Correlation** - Each request gets unique ID for log correlation

#### Log Settings
- **Log Level Configuration** - Set minimum log level (DEBUG, INFO, WARNING, ERROR)
- **Retention Period** - Configure how many days to keep logs (1-365)
- **Toggle Database Logging** - Enable/disable logging to database
- **Toggle Request Logging** - Enable/disable API request logging
- **Toggle Scheduler Logging** - Enable/disable scheduler activity logs
- **Toggle API Logging** - Enable/disable external API call logs

#### Log Endpoints
- `GET /logs` - Get logs with filtering (level, category, search, limit)
- `GET /logs/stats` - Get log statistics (counts by level/category)
- `GET /logs/export` - Export logs as JSON or CSV
- `DELETE /logs` - Clear old logs
- `GET /logs/settings` - Get logging settings
- `PUT /logs/settings` - Update logging settings

---

### New Feature 5: Filler Category

A global fallback system to fill gaps in your schedule when no schedules are active.

#### What It Does
- **Fills Schedule Gaps** - Automatically applies prerolls when NO schedules are active
- **Different from Per-Schedule Fallback** - Per-schedule fallback only applies when THAT schedule ends; Filler applies globally when ALL schedules are inactive
- **Three Filler Types**:
  - **Category** - Use any category as the gap filler
  - **Sequence** - Use a saved NeX-Up sequence as the gap filler
  - **Coming Soon List** - Use a generated Coming Soon List (grid or list layout) as the gap filler

#### Configuration
- Settings > General > Filler Category section
- Toggle to enable/disable
- Select filler type and configure the source
- Respects Coexistence Mode and Clear When Inactive settings

#### Priority Order
1. **Active Schedule** - Highest priority, schedule's category is applied
2. **Per-Schedule Fallback** - If schedule has a fallback, it's used when that schedule ends
3. **Filler Category** - Global fallback when NO schedules are active and no per-schedule fallback exists
4. **Unchanged** - If filler is disabled, Plex prerolls remain unchanged

#### API Endpoints
- `GET /settings/filler` - Get filler settings
- `PUT /settings/filler` - Update filler settings (enabled, type, category_id, sequence_id, coming_soon_layout)

---

### Improvements

#### Dashboard Enhancements
- **Weekly Calendar Preview** - Mini calendar on Dashboard Overview showing this week's scheduled prerolls
- **View Full Calendar Button** - Quick navigation to the full Calendar View from dashboard
- **Filler Category Display** - Shows filler category events on days with no active schedules

#### Sticky Sub-Navigation
- **All Sub-Navs Now Stick** - Dashboard, Schedules, NeX-Up, and Settings sub-navigation bars properly stick below the main header when scrolling
- **Unified Positioning** - Consistent 70px offset for all sub-navigation bars

#### Coming Soon List Generator
- **Cleaner Filenames** - Generated videos now use simpler filenames: `coming_soon_grid.mp4` and `coming_soon_list.mp4`

#### Docker & Deployment
- **Docker Beta Channel** - Added beta tag support for pre-release Docker images
- **bcrypt Dependency** - Added bcrypt>=4.0.0 to requirements.txt for password hashing
- **GitHub Workflow** - Updated docker-build.yml with automatic pre-release detection and conditional tagging

---

### Bug Fixes
- **Sequence Schedule Blending** — Sequence schedules with NeX-Up Trailers, Coming Soon List, or Dynamic Preroll blocks were silently contributing zero prerolls when blended, causing them to drop out of the blend. All three block types are now handled in the blend path identically to the normal sequence executor.

- **Admin Role Fix** - Fixed issue where creating a user with Admin role would save as User instead. The RegisterRequest model was missing the `role` field.
- **View Full Calendar Navigation** - Fixed "View Full Calendar" button not switching to Calendar View properly
- **Schedule from Sequence Fix** - Fixed clicking "Schedule" on a saved sequence creating a duplicate sequence in the library. Now properly tracks the loaded sequence ID and hides the name/description fields.
- **Dashboard Data Loading** - Filler settings and NeX-Up trailer counts now load on startup so they display immediately on the Dashboard and Calendar without needing to visit Settings/NeX-Up pages first.

---

## [1.10.14] - 02-14-2026

### New Feature: NeX-Up - Radarr & Sonarr Trailer Integration

A brand new feature that brings the movie theater "Coming Soon" experience to your Plex server. Automatically download and play trailers for upcoming movies and TV shows before your content.

#### Radarr & Sonarr Connections
- **One-Click Integration** - Connect to Radarr and Sonarr with URL and API key
- **Automatic Discovery** - Fetches movies/shows scheduled to release within your configured timeframe
- **Smart Cleanup** - Automatically removes trailers when content is added to your library
- **Separate Storage** - Trailers organized in `/movies` and `/tv` subdirectories

#### Automatic Trailer Downloads
- **YouTube Integration** - Downloads trailers automatically from YouTube
- **Cookie File Support** - Use exported cookies for age-restricted or region-locked content
- **Quality Settings** - Choose 720p, 1080p, 4K, or best available
- **Storage Limits** - Configure max trailers and storage allocation

#### Dynamic Preroll Generator
- **Custom Intro Videos** - Create "Coming Soon to [Your Server]" intro clips
- **Multiple Templates** - Cinematic, Neon, Minimal, Retro, Elegant styles
- **Color Themes** - 5 color themes (Midnight, Sunset, Forest, Royal, Monochrome)
- **Live Preview** - Watch your generated intro directly in the browser
- **FFmpeg Powered** - High-quality video generation

#### Sequence Builder Presets
- "Coming Soon + Movie Trailers" - Intro followed by random movie trailers
- "Coming Soon + TV Trailers" - Intro followed by random TV trailers
- "Mixed: Movies + TV" - Intro with both movie and TV trailers
- "Theater Experience" - Full cinema experience with 4 trailers

#### NeX-Up Page Organization
- **Connections Tab** - Radarr/Sonarr management with quick sync buttons
- **Your Trailers Tab** - Manage movie and TV trailers with storage info
- **Settings Tab** - YouTube cookies, storage path, TMDB API, rate limiting
- **Generator Tab** - Dynamic preroll generator and sequence builder

### Added

- **Custom Styled Confirmation Dialogs** - All browser confirmation dialogs replaced with themed modal dialogs. Supports warning, danger, info, success, and error styles with icons, smooth animations, and async/await handling.

#### System & Files Backup (Enhanced)
- **Comprehensive System Backup** - "Files Backup" renamed to "System & Files Backup" - now creates a complete system snapshot
- **Database Included** - Backup includes both SQLite database file (nexroll.db) and JSON export for cross-version compatibility
- **All Preroll Videos** - Every preroll video file is included in the backup ZIP
- **Thumbnails Included** - All generated thumbnails preserved in backup
- **Settings & Configuration** - Application settings exported with the backup
- **Streaming Download** - Large backups now use FileResponse streaming to prevent memory issues
- **Smart Restore** - Restore process handles both new comprehensive format and legacy backups
- **Progress Tracking** - Real-time progress indicators during backup creation and restore operations
- **Button Disable During Operations** - UI prevents accidental double-clicks during backup/restore

#### Video Quality Dashboard
- **New Dashboard Tile** - "Video Quality" card shows resolution distribution of your preroll library
- **Interactive Bar Chart** - Visual breakdown of 4K, 1080p, 720p, 480p, and other resolutions
- **Click to Filter** - Click any resolution bar to filter prerolls by that quality
- **Color-Coded Bars** - Each resolution has a distinct color for quick identification

#### Community Prerolls Stale Indicator
- **"Currently Showing" Tile Rename** - Currebt Category dashboard tile renamed to "Currently Showing"
- **Stale Data Warning** - Orange indicator appears when community data is older than 24 hours
- **Last Updated Timestamp** - Shows when community prerolls were last refreshed

#### YouTube Bot Detection Warning
- **New Info Box in NeX-Up Settings** - Explains YouTube's aggressive bot detection
- **VPN Guidance** - Suggests refreshing VPN IP if downloads fail
- **Rate Limiting Tips** - Wait between downloads to avoid blocks
- **Cookie Instructions** - Export from Incognito using cookies.txt extension

#### Dashboard Quick Actions
- **NeX-Up Sync Button** - One-click sync for both Radarr and Sonarr trailers
- **Real-Time Progress** - Shows which trailer is downloading with progress counter
- **Spinner Animations** - All Quick Action buttons now animate properly

#### Video Scaling Page
- **Dedicated Dashboard Sub-Page** - New "Video Scaling" page accessible from Dashboard menu
- **Resolution Stats Cards** - Visual breakdown showing count of 4K, 1080p, 720p, 480p, SD, and unknown resolution prerolls
- **Click-to-Filter** - Click any resolution card to filter the preroll list
- **Bulk Selection** - Multi-select prerolls with "Select All" and "Clear Selection" buttons
- **Batch Scaling** - Scale multiple prerolls to target resolution (1080p, 720p, or 480p) in one operation
- **Progress Tracking** - Real-time progress indicator shows current file being processed
- **Smart Filtering** - Excludes NeX-Up trailers and dynamic prerolls from scaling (they have their own workflows)
- **Scale Prerolls to Lower Resolutions** - Transcode to 1080p, 720p, or 480p
- **One-Click Scaling in Edit Modal** - Quick access to scale individual prerolls
- **High Quality Settings** - Uses FFmpeg libx264, CRF 18, slow preset
- **720p Recommended** - Ideal for remote streaming without transcoding

#### Schedule Conflict Detection
- **Same-Priority Warnings** - Orange badges when exclusive schedules conflict
- **Calendar Indicators** - Day, Week, and Month views show conflicts
- **Priority Visualization** - Higher priority schedules shown with lock icon, lower priority greyed out

### Improved

- **Add Prerolls to Category UI** - Replaced cluttered dropdown with a searchable thumbnail grid. Multi-select prerolls with visual checkmarks and add them all at once.
- **Schedules Page Organization** - Schedules are now organized into three clear sections: "Currently Running" (active right now), "Enabled Schedules" (ready but not running), and "Disabled Schedules" (paused).
- **Category Management Styling** - Categories now organized into three sections: "Scheduled Categories", "Categories with Prerolls", and "Empty Categories". Added colored accent borders on cards, section headers with icons and counts, and a quick stats bar showing totals at a glance.
- **Dashboard Card Icons** - All dashboard cards now display lucide icons in their headers for visual consistency (Servers, Prerolls, Storage, Schedules, Scheduler, Current Category, Upcoming, Genre Prerolls, Community, NeX-Up).
- **Category Grid Condensed View** - Category cards in grid view are now more compact with reduced padding, no duplicate buttons, and clickable cards to edit. Minimum width reduced to 220px for better space efficiency.
- **Backup & Restore Overhaul** - Complete redesign of the backup/restore interface with progress indicators, card-based layout, and clearer button alignment.

#### yt-dlp & Deno Updates
- **yt-dlp 2026.2.4** - Latest version with improved YouTube extraction
- **Deno 2.6.8** - Required JavaScript runtime for YouTube extraction
- **Better Error Messages** - Clear guidance when YouTube blocks downloads

#### Installer
- **Launch Tray After Install** - Option to start NeXrollTray immediately
- **Fixed Post-Install Context** - Network drives accessible on first launch

### Fixed
- **Category Grid Dropdown Z-Index** - Fixed issue where the three-dot menu options in Category Management grid view appeared behind neighboring category cards.
- **Category Preroll Count Bug** - Fixed issue where non-primary category assignments showed 0 prerolls. The category stats now correctly count prerolls added via many-to-many associations.
- **Category Dropdown Sorting** - All category dropdown menus throughout the app now display categories in alphabetical order.
- **Fixed Folder Picker** - Custom preroll location now saves correctly

#### Schedule Management
- **Load Saved Sequences** - Dropdown loads sequences when creating schedules
- **Improved Edit Modal** - Better layout with 900px width
- **Duplicate Prevention** - No more duplicate sequences when using saved sequences

### Fixed
- Fixed KeyError when YouTube download fails (proper error dict handling)
- Fixed dynamic preroll theme not saving after generation
- Fixed gradient backgrounds to match CSS preview
- Fixed Radarr/Sonarr auto-sync KeyError with dictionary keys
- Fixed color themes working for all template types
- Fixed video preview caching issues
- Fixed sequence validator for 'sequential' block type

### Removed
- **Genre-based Preroll Mapping** - Removed experimental feature that never fully worked

---

## [1.9.8] - 01-08-2026

### Fixed
- **Timezone Drift Bug** - Fixed critical bug where schedules would shift backward by 7-8 hours on each save for users in GMT-7/8 timezones
  - Schedules are now stored as naive local datetimes with no timezone conversion
  - What you enter is exactly what gets saved and displayed
  - Scheduler now uses local time for all comparisons

- **Random Order Default** - Fixed bug where new schedules defaulted to Sequential even when Random was visually selected
  - The "Random" playback option now correctly defaults to enabled when creating a new schedule

### Changed
- **Time Display Format** - Dashboard "Upcoming Schedules" card now shows times without seconds (e.g., "1/1/2026, 7:00 AM" instead of "1/1/2026, 7:00:00 AM")

- **Community Prerolls URL** - Updated community prerolls library URL from prerolls.typicalnerds.uk to prerolls.uk

### Added
- **Reddit Community** - Added r/NeXroll subreddit link to footer and README

- **Coexistence Mode** - New setting that allows NeXroll to work alongside other preroll managers (like Preroll Plus)
  - When enabled, NeXroll only manages prerolls during active schedules
  - Outside of scheduled times, NeXroll stays hands-off, allowing other preroll managers to control Plex
  - Found in Settings → NeXroll Settings → Coexistence Mode

- **Clear When Inactive** - New setting to clear prerolls when no schedule is active
  - When enabled, NeXroll will clear the Plex preroll field outside of scheduled times
  - No prerolls will play when you don't have an active schedule
  - Found in Settings → NeXroll Settings → Clear Prerolls When Inactive

- **Daily Calendar View** - New "Day" view option in the calendar
  - Shows an hourly breakdown of the selected day with all active schedules
  - Displays schedule conflicts, exclusive schedules, and blend mode at each hour
  - Click any day in Month view to jump to that day's hourly view
  - Visual indicators for current hour when viewing today
  - Night hours (10 PM - 6 AM) are subtly highlighted


---

## [1.9.6] - 12-21-2025

### Fixed
- **Calendar Month View Conflict Detection** - Fixed false conflict indicators showing on days with exclusive schedules
  - Days with a time-restricted exclusive schedule (e.g., Adult Swim 10pm-3am) plus other schedules no longer show conflict badges
  - Orange conflict borders only appear when there's a true scheduling conflict (multiple non-exclusive schedules competing)
  - Exclusive mode properly resolves priority - no conflict exists when exclusive handles the time window

- **Blend Mode Display for Single Schedules** - Fixed single schedules incorrectly showing as "blended"
  - Single schedules with `blend_enabled` no longer display the shuffle/blend icon
  - Blend indicator now only appears when 2+ schedules are actually blending together
  - Improves calendar clarity by showing blend mode only when meaningful

### Technical
- Refactored conflict detection in `App.js` to only set `hasConflict` when multiple exclusive schedules compete
- Removed erroneous `hasBlend = true` for single-schedule scenarios
- Blend mode requires `contentSchedules.length > 1` before displaying blend indicators

---

## [1.9.5] - 12-21-2025

### Fixed
- **Critical Timezone Bug in Time Range Schedules** - Fixed bug where time range schedules (e.g., 10pm-3am) were incorrectly applying at the wrong times due to timezone mismatch
  - **Root Cause**: Time ranges stored in local time were being compared against UTC time
  - Example: 8:05pm local = 1:05am UTC, which fell inside the 10pm-3am overnight range when compared in UTC
  - Now properly converts UTC to user's configured timezone before comparing with time ranges
  - Impact: Time range schedules now correctly activate/deactivate at the specified local times

- **Calendar Week View Time-Restricted Exclusive Display** - Fixed misleading calendar display when time-restricted exclusive schedules overlap with blending schedules
  - **Issue**: When an exclusive schedule with a time range (e.g., Adult Swim 10pm-3am) overlapped with blended schedules (e.g., Christmas + New Year all day), the calendar showed the blended schedules as crossed out "losers" all day
  - **Fix**: Calendar now correctly shows:
    - Time-restricted exclusive schedules with their time range displayed (e.g., "Adult Swim (22:00-03:00)")
    - Non-exclusive blending schedules as ACTIVE (with blend icon) since they run outside the exclusive's time window
    - Day headers show both blend and exclusive icons when both modes apply at different times
    - Proper tooltips explaining when each schedule is active
  - Impact: Visual calendar now accurately reflects that blended schedules ARE active during most of the day

- **Calendar Month View Time-Restricted Exclusive Display** - Applied same fix to monthly calendar view
  - Day cells now show appropriate borders: purple for blend mode, red for exclusive, orange only for true conflicts
  - Time-restricted exclusive with blend mode shows purple border (blend is primary mode most of day)
  - Added exclusive mode badge indicator (lock icon) with clock icon for time-restricted exclusive
  - Conflict badge only shows when there's a true conflict (no blend mode, no exclusive)
  - Hover effects properly restore correct shadow color based on day status

### Technical
- Added `pytz` import to `scheduler.py`
- Updated `_is_schedule_active()` to convert UTC now to user's local timezone before time range comparison
- Updated `_matches_pattern()` with same timezone conversion fix
- Updated `_apply_schedule_win_lose_logic()` in `main.py` with same fix
- Day-of-week checks also now use local time
- Calendar week view now tracks `nonExclusiveWinner` for schedules that win outside exclusive time windows
- Added `exclusiveHasTimeRange` tracking to properly style time-restricted exclusive schedules
- Updated span rendering with differentiated borders: dashed red for time-restricted exclusive, solid red for full-day exclusive, purple for blend mode
- Monthly view calendar now includes `exclusiveHasTimeRange`, `nonExclusiveWinnerScheds`, and `nonExclusiveWinner` tracking
- Priority sorting now considers higher priority values first, then fallback to end date/start date/ID

---

## [1.9.4] - 12-20-2025

### Fixed
- **Daily Schedule Time Range Bug** - Fixed critical bug where daily schedules with time ranges (e.g., 10pm-3am) remained active outside their time window
  - Schedules with `timeRange` in recurrence pattern now properly check current time
  - Overnight ranges (e.g., 22:00-03:00) are handled correctly
  - Schedules now correctly become inactive when outside their time window
  - Impact: Exclusive nightly schedules (like Adult Swim 10pm-3am) now properly switch back to other active schedules when their time window ends

### Technical
- Enhanced `_is_schedule_active()` method to check `recurrence_pattern.timeRange` in addition to date range
- Implemented proper overnight time range detection (start > end means overnight wraparound)
- Updated `_matches_pattern()` to actually check time ranges (was always returning True)
- Verbose logging added for schedule time window checks

---

## [1.9.3] - 12-20-2025

### Added
- **Schedule Priority System** (1-10)
  - New priority slider in schedule creation/editing form
  - Higher priority schedules win when multiple schedules overlap
  - Priority badge (P6, P7, etc.) shown in schedule list views when not default (5)
  - Color-coded badges: red (8-10), orange (5-7), gray (1-4)
  - Tie-breaking: highest priority → earliest end date → earliest start → lowest ID
  - Impact: Fine-grained control over which schedule takes precedence during overlaps

- **Exclusive Schedule Mode** 🔒
  - New "Exclusive" checkbox in schedule creation/editing form
  - When active, the schedule wins exclusively (no blending with other schedules)
  - Overrides blend mode - exclusive schedules never blend, even if other schedules have blend enabled
  - Multiple exclusive schedules: highest priority exclusive wins
  - Red "Exclusive" badge shown in schedule list views
  - Perfect for time-specific prerolls (e.g., nightly schedule 10pm-3am) that should override holiday schedules
  - Impact: Guaranteed schedule control for time-sensitive preroll needs

### Fixed
- **Blend Mode Delimiter** - Changed from comma (sequential/all) to semicolon (random pick one) so Plex plays 1 random preroll from the blended pool instead of all prerolls

### Technical
- Added `priority` (INTEGER DEFAULT 5) and `exclusive` (BOOLEAN DEFAULT 0) fields to Schedule model
- Database migration automatically adds columns to existing databases
- Scheduler logic updated: exclusive schedules checked first, then blend mode, then normal priority-based winner selection
- API endpoints (create/update schedule) now accept priority and exclusive parameters
- Frontend form includes priority slider and exclusive checkbox with helpful descriptions
- Visual badges for priority and exclusive in both compact and detailed schedule list views

---

## [1.9.2] - 12-19-2025

### Added
- **Schedule Blend Mode** 🔀
  - New "Blend Mode" toggle in schedule creation/editing form
  - When enabled, overlapping schedules with blend mode will mix their prerolls together
  - Perfect for combining holiday themes (e.g., Hanukkah + Christmas prerolls playing together)
  - Prerolls are interleaved from each schedule in round-robin fashion
  - Uses playlist mode (sequential) to maintain the blended order
  - For sequences: respects the count setting for random blocks
  - For categories: takes up to 3 random prerolls from each to keep playlist manageable
  - Blend mode only activates when 2+ overlapping schedules have it enabled
  - Single blend-enabled schedule falls back to normal winner-takes-all behavior
  - Impact: Create rich, multi-theme preroll experiences during overlapping holiday periods

### Technical
- Added `blend_enabled` boolean field to Schedule model
- Database migration automatically adds column to existing databases
- New `_apply_blended_schedules_to_plex()` method in scheduler for blend logic
- API endpoints (create/update schedule) now accept blend_enabled parameter
- Frontend form includes blend mode checkbox with helpful description

---

## [1.9.0] - 12-16-2025

### Added
- **Calendar Week View Conflict Detection**
  - Full conflict detection for the Week view showing when multiple schedules overlap
  - Winner/loser logic using backend priority rules: ends soonest → started earliest → lowest ID
  - Visual indicators: Crown icon (👑) for winning schedule, strikethrough for overridden schedules
  - Day headers highlight conflict days with orange warning indicators
  - "Schedule Conflicts Detected" banner when any day has conflicts
  - Legend explaining conflict resolution rules
  - Tooltips show "ACTIVE (wins conflict)" or "OVERRIDDEN" status on hover
  - Impact: Users can now clearly see which schedule takes priority when conflicts occur

- **Smart Fallback Category Selection**
  - Fallback categories now pick the closest schedule based on date proximity
  - Calendar days without active schedules show the fallback from the nearest schedule
  - Properly handles year-wrapping schedules (e.g., Christmas Dec 1 - Jan 15)
  - Fixed issue where Christmas fallback would show in February instead of Valentine's fallback
  - Both month view and yearly overview use the same smart proximity-based logic
  - Impact: Fallback categories are now contextually appropriate for each time period

- **Sequence Cards Playback & Preroll Count**
  - Added Play button to Saved Sequences cards for quick preview
  - Preroll count badge shows total number of prerolls in each sequence
  - SequencePreviewModal integration for full playback preview
  - Improved card layout with better spacing and visual hierarchy
  - Updated tips box: ".nexbundle" changed to ".zip bundle" for clarity

- **Modern SequenceTimeline Component**
  - Complete visual overhaul with lucide-react icons
  - Gradient background colors for different block types
  - Header stats badges showing blocks, prerolls, and total duration
  - Film icon for fixed blocks, Shuffle for random, ListOrdered for sequential
  - Play icon for preroll blocks, Layers for queue/sequence
  - Clock icon for separators, improved number badges
  - Better visual distinction between block types

- **Community Prerolls Icon Modernization**
  - Replaced all emoji icons with lucide-react components
  - FileText icon for Fair Use Policy button
  - AlertTriangle/Sparkles/Lightbulb for status indicators
  - Library icon for indexed count, Link icon for matched count
  - Search icon in search bar and buttons
  - Film icon for preroll cards and empty states
  - User/FolderOpen/Clock icons for metadata display
  - Play/Eye icons for preview buttons
  - CheckCircle/Plus icons for category toggle
  - Loader2 spinner for loading states
  - Impact: Consistent, professional appearance across all platforms

- **Holiday Browser Feature**
  - Browse holidays from 100+ countries powered by Nager.Date API
  - Search holidays by name across all available countries
  - Filter by country with dropdown selector (200+ countries available)
  - View holidays by year with past/future year navigation
  - Holiday cards display: name, local name, date, holiday types
  - One-click "Use This Holiday" button to populate schedule creation form
  - Impact: Simplifies holiday schedule creation with accurate international holiday data

### Changed
- **UI/UX Enhancements**
  - All icons now use lucide-react for consistent rendering across platforms
  - Improved spacing and layout in sequence cards
  - Better visual hierarchy in calendar conflict displays
  - Modernized Community Prerolls interface with proper icon alignment

### Fixed
- **Calendar Fallback Display Bug**
  - Fixed yearly overview showing ALL fallback categories on empty days
  - Now correctly shows only ONE fallback from the nearest relevant schedule
  - February days now show Valentine's fallback instead of Christmas fallback

- **Week View Missing Conflict Indicators**
  - Week view now properly detects and displays schedule conflicts
  - Added winner/loser visual states matching month view behavior

### Technical
- **Dependencies**
  - Added Eye, X, User, RefreshCcw to lucide-react imports
  - Tree-shakeable imports ensure minimal bundle impact

---

## [1.8.9] - 12-11-2025

### Added
- **Holiday Browser Feature**
  - Browse holidays from 100+ countries powered by Nager.Date API
  - Search holidays by name across all available countries
  - Filter by country with dropdown selector (200+ countries available)
  - View holidays by year with past/future year navigation
  - Holiday cards display: name, local name, date, holiday types (Public/Bank/School/Observance)
  - Fixed/Variable date indicators for recurring holidays
  - Color-coded badges for holiday types (green for Public holidays)
  - One-click "Use This Holiday" button to populate schedule creation form
  - Integrated help section explaining all features and workflow
  - Past holidays automatically disabled to prevent scheduling expired dates
  - **Workflow**: Click holiday → Form pre-fills with name, yearly type, dates → Select category → Adjust dates if needed → Create schedule
  - Impact: Simplifies holiday schedule creation with accurate international holiday data

- **Professional Icon System**
  - Replaced all emojis with Lucide Icons for consistent, professional appearance
  - 27 unique icon components integrated across the entire application
  - Icons include: Calendar, CalendarDays, CalendarPlus, Clock, Play, Edit, Save, Trash, Upload, Download, Search, and more
  - Scalable SVG icons ensure perfect rendering at any size and resolution
  - Icons automatically adapt to light/dark mode themes
  - Impact: Eliminates emoji rendering inconsistencies across different operating systems and browsers

- **Enhanced Verbose Logging System**
  - Structured log levels: DEBUG, INFO, WARNING, ERROR
  - Cached verbose setting with 5-second TTL to reduce database queries
  - Startup banner showing version, platform, paths, and environment details
  - Scheduler-specific logging functions with configurable verbosity
  - Consistent timestamp format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
  - Impact: Better debugging capabilities and cleaner log organization

### Changed
- **UI/UX Enhancements**
  - Floating help button now uses CircleHelp icon instead of emoji
  - All navigation tabs feature professional icons (Folder, Calendar, Film, Package)
  - Schedule type indicators use Calendar/CalendarDays icons
  - Action buttons (Edit, Delete, Save, Create) display icon + text for clarity
  - Help modal sections use contextual icons (Target, Edit, CheckCircle)
  - Community preroll buttons use Clock/RefreshCw icons for loading states
  - Settings buttons use appropriate icons (Search, Download, BookOpen)

### Improved
- **Visual Consistency**
  - Uniform icon sizing: 14-20px for buttons, 28px for floating help button
  - Flex layouts ensure proper icon-text alignment throughout the app
  - Star icon for primary category markers
  - CheckCircle badges for "Matched to Community" status
  - Play icons for video preview buttons
  - Package bundle size increased by only ~4KB for comprehensive icon system

### Fixed
- **Holiday Schedule Creation Bugs**
  - Fixed `TypeError: 'description' is an invalid keyword argument for Schedule` when creating holiday schedules
  - Fixed `TypeError: SQLite DateTime type only accepts Python datetime objects` by converting date strings to proper datetime objects
  - Fixed `AttributeError: 'Schedule' object has no attribute 'description'` in API response
  - Fixed error logging function name (`_error_log` → `_file_log`) that was masking actual errors
  - Impact: Holiday schedule creation now works correctly end-to-end

- **Critical: Yearly/Holiday Schedule Date Shifting Bug**
  - Fixed issue where yearly and holiday schedules were incorrectly converted to UTC timezone
  - Problem: Schedules created for Jan 1-3 would appear as Dec 31-Jan 2 due to timezone conversion (UTC-5)
  - Solution: Yearly and holiday schedules now stored as naive datetime (no timezone) since they are date-based, not time-based
  - Affected endpoints: POST `/schedules` (create), PUT `/schedules/{id}` (update), GET `/schedules` (retrieve)
  - GET endpoint now checks schedule type before applying timezone conversion
  - Time-based schedules (daily, weekly, monthly) still correctly convert to UTC
  - Impact: Calendar views now display yearly/holiday schedules on the correct dates without timezone shifting

- **Schedule Fallback Persistence Bug**
  - Fixed issue where a schedule's fallback category would persist indefinitely after the schedule ended
  - Problem: Christmas schedule fallback continued applying even after New Year's schedule became active
  - Solution: Fallback categories are now tied to the active schedule and cleared when a new schedule takes over
  - New behavior: When a schedule is active, its fallback is "armed" for when it ends. When a new schedule starts, that schedule's fallback (or none) replaces the previous one
  - Added `last_schedule_fallback` column to settings table to track fallback from most recently active schedule
  - Impact: Fallbacks now correctly transition between schedules instead of persisting indefinitely

- **Scheduler Logging and Start Issues**
  - Fixed scheduler failing to start due to circular import issues in logging functions
  - Problem: Scheduler thread would crash immediately on start, showing as "stopped" in UI
  - Solution: Replaced runtime imports with direct file writes for scheduler logging
  - Scheduler logging now writes directly to app.log without depending on main.py imports
  - Impact: Scheduler now starts reliably and logs all activity correctly

### Technical
- **Dependencies**
  - Added lucide-react ^0.560.0 for icon components
  - Tree-shakeable imports ensure minimal bundle impact
  - All icons are MIT licensed and production-ready

- **Holiday API Integration**
  - Backend endpoint: GET `/holiday-api/countries` - Returns list of 100+ countries
  - Backend endpoint: GET `/holiday-api/holidays/{country_code}/{year}` - Returns holidays for specific country/year
  - Backend endpoint: GET `/holiday-api/status` - Checks Nager.Date API availability
  - LRU cache (128 entries, 1-hour TTL) for API responses to minimize external requests
  - Nager.Date API: Free, no authentication required, JSON responses
  - Frontend: 8 state variables for modal, countries, holidays, search, loading, API status
  - Modal size: 1200px width for optimal holiday card layout (3 columns at 275px each)
  
- **Logging Functions**
  - `_file_log(message)` - Direct file logging to app.log
  - `_verbose_log(message)` - Logs with [DEBUG] prefix when verbose enabled
  - `_scheduler_log(msg, level)` - Scheduler-specific logging with level support
  - `_scheduler_verbose(msg)` - Scheduler debug logging only when verbose enabled
  - Verbose setting cached for 5 seconds to reduce database overhead
  - Startup banner logs: version, Python version, platform, frozen state, paths, environment

## [1.8.9] - 11-28-2025

### Added
- **Expanded Holiday Preset Library**
  - Added 26 new holiday and seasonal presets for a total of 32 comprehensive holidays
  - Winter holidays: Hanukkah, Kwanzaa
  - Spring holidays: St. Patrick's Day, Passover, Cinco de Mayo, Mother's Day
  - Summer holidays: Father's Day, Independence Day, Labor Day
  - Fall holidays: Veterans Day
  - Cultural and international: Diwali, Chinese New Year, Mardi Gras, Ramadan, Eid al-Fitr, Day of the Dead
  - Seasonal themes: Spring Season, Summer Season, Fall Season, Winter Season
  - Special events: Back to School, Black Friday, Cyber Monday, Earth Day, Pride Month, Memorial Day, Martin Luther King Jr. Day
  - Each holiday includes appropriate date ranges for optimal scheduling
  - All holidays integrate seamlessly with the existing Holiday Preset dropdown in schedule creation
  - Impact: Users can now schedule themed prerolls for a comprehensive range of holidays and events throughout the year

- **Enhanced Tag Management System**
  - Tag badge display in preroll grid view with purple pill-shaped design
  - Tag badge display in preroll list view matching grid view styling
  - Interactive tag editor in Edit Preroll modal with chip-based interface
  - Individual tag removal via X buttons on each tag chip
  - Browse button with dropdown showing all available tags for quick selection
  - Autocomplete functionality when selecting from existing tags
  - Dual format support for tags: JSON arrays and comma-separated strings
  - Impact: Users can now easily view, add, edit, and remove tags with a modern, intuitive interface

- **Backup and Restore Enhancements**
  - Sequences now included in database backup exports
  - Sequence metadata preserved: name, description, blocks structure, timestamps
  - Files backup now includes the /sequences/ directory alongside /prerolls/
  - Database restore properly deletes and recreates sequences with full data integrity
  - Sequence blocks JSON structure maintained through backup/restore cycle
  - Impact: Complete data protection for both prerolls and sequences with no data loss during backup operations

### Changed
- **Tag Display Format**
  - Removed emoji icons from tag badges for cleaner appearance
  - Implemented robust JSON parsing to handle array string format tags
  - Tag styling now uses consistent purple theme across all views
  - Badge font size optimized for readability at 0.7-0.8rem
  - Tags display as clean text without brackets or formatting artifacts

- **Holiday Preset Date Ranges**
  - Extended date ranges for better seasonal coverage
  - Christmas: Full month (December 1-31)
  - Halloween: Full month (October 1-31)
  - Thanksgiving: Full month (November 1-30)
  - New holidays use sensible date ranges matching cultural observance periods
  - Schedule form automatically populates dates when selecting holiday presets

- **Backup System Architecture**
  - Database backup endpoint updated to export sequences table
  - Files backup endpoint enhanced to traverse /sequences/ directory
  - Restore endpoint includes proper sequence deletion cascade
  - Datetime parsing with fallback handling for sequence timestamps
  - Error logging per sequence during restore operations

### Fixed
- **Tag Parsing Issues**
  - Fixed tags displaying with JSON array brackets in UI
  - Fixed emoji icons appearing alongside tag text
  - Resolved parsing errors when tags stored as JSON array strings
  - Added fallback parsing for comma-separated legacy format
  - ESLint error resolved: proper event parameter declaration in tag editor

- **Backup Data Integrity**
  - Fixed sequences not being included in database exports
  - Fixed sequence files not included in ZIP archives
  - Fixed restore operations not recreating sequence records
  - Added proper error handling for malformed sequence data during restore

## [1.8.8] - 11-25-2025

### Added
- **Sequence Builder Visual Enhancements**
  - Timeline visualization with thumbnail strips showing preroll previews
  - Full-screen preview modal with playback simulator
  - Sequence statistics dashboard showing total duration, preroll count, and block breakdown
  - View toggle between Card View and Timeline View for different workflow preferences
  - Duration markers and color-coded block types for easy visual identification
  - **Impact**: Users can now visualize and understand their entire sequence before applying it

- **Pattern Export/Import System (.nexseq files)**
  - Export sequences as lightweight JSON pattern files (.nexseq format)
  - Import patterns with automatic Community Preroll matching
  - Smart conflict detection and resolution during import
  - Preview import results before applying changes
  - Missing preroll warnings with download suggestions
  - Community Preroll ID mapping for seamless sharing between NeXroll instances
  - **Impact**: Share sequence patterns without needing to transfer large video files

- **Full Sequence Pack System (.nexpack files)**
  - Export complete sequence packs as ZIP files (.nexpack format) containing videos, thumbnails, and pattern
  - Import sequence packs with automatic category creation and video extraction
  - Progress tracking for large pack imports with real-time status updates
  - Category conflict resolution with merge or create new options
  - File size validation and warnings for very large packs
  - Automatic video file organization and thumbnail generation
  - **Impact**: Share complete, ready-to-use sequences with all media files included

### Changed
- **Sequence Builder Interface**
  - Enhanced block cards with thumbnail previews
  - Improved drag-and-drop visualization with live preview
  - Better mobile responsiveness for sequence building on tablets
  - Statistics panel now shows real-time updates as blocks are added/removed
  - Export options grouped into organized menu (Pattern Only / With Videos)

- **Sequence Data Model**
  - Added `exported_metadata` JSON field to Sequence model for tracking original creator and source
  - Enhanced block validation to support nested sequences and complex patterns
  - Improved JSON schema with versioning for backward compatibility

### Fixed
- **Sequence Preview Accuracy**
  - Fixed duration calculations not accounting for video file metadata
  - Fixed thumbnail generation for videos without embedded thumbnails
  - Fixed preview modal not scrolling properly for very long sequences (20+ blocks)

### Technical
- **Pattern Export/Import (.nexseq)**
  - POST `/api/sequences/{id}/export` - Export sequence pattern as JSON
  - POST `/api/sequences/import` - Import sequence pattern with validation
  - Auto-matching algorithm: matches by Community Preroll ID first, falls back to fuzzy title matching
  - Schema includes: name, description, version, created_by, blocks array with Community Preroll ID mapping
  
- **Sequence Pack Export/Import (.nexpack)**
  - POST `/api/sequences/{id}/export-pack` - Generate .nexpack.zip with videos and pattern
  - POST `/api/sequences/import-pack` - Extract and import complete sequence pack
  - ZIP structure: `sequence.json`, `videos/`, `thumbnails/` directories
  - Automatic category creation with conflict resolution
  - Progress tracking via Server-Sent Events (SSE) for real-time updates
  
- **New Database Fields**
  - `sequences.exported_metadata` (JSON) - Stores original creator, source URL, export timestamp
  - `sequence_imports` table - Tracks import history with match statistics
  
- **New React Components**
  - `SequenceTimeline.js` - Timeline visualization with thumbnail strips
  - `SequencePreviewModal.js` - Full-screen preview with playback simulator
  - `SequenceStats.js` - Statistics dashboard with visual charts
  - `PatternExportModal.js` - Export pattern dialog with download options
  - `PatternImportModal.js` - Import pattern with preview and validation
  - `PackExportModal.js` - Export full pack with progress tracking
  - `PackImportModal.js` - Import pack with category conflict resolution

## [1.8.5] - 11-25-2025

### Fixed
- **Category Management Search Bar Layout**
  - Fixed search bar width to display at correct 65% width instead of full width
  - Simplified layout structure by removing nested wrapper divs
  - Search input now has direct `width: 65%` styling for precise control
  - Filter dropdown set to direct `width: 20%` for consistent sizing
  - View toggle buttons properly aligned to right with `marginLeft: auto`
  - Improved vertical alignment with `alignItems: center` in flex container
  - **Impact**: Cleaner, more maintainable layout code with predictable width behavior

## [1.8.0-beta.2][Unreleased] - 11-23-2025

### Added
- **Category Management Search**
  - Added search bar to Category Management section (matching Schedules section)
  - Search filters categories by name or description in real-time
  - Works in both grid view and list view modes
  - Case-insensitive matching for easier discovery
  - **Impact**: Easier navigation and management of large category collections

- **Category Management List/Grid View Toggle**
  - Added view toggle to Category Management (matching Prerolls section)
  - Grid view: Card-based layout with hover effects, badges, and action buttons
  - List view: Compact table showing Name, Description, Prerolls, Status, Actions columns
  - View preference persisted in localStorage across sessions
  - **Impact**: Users can choose optimal view density based on workflow preference

- **Category Management Sortable Columns**
  - List view columns now support click-to-sort functionality
  - Sortable columns: Name (alphabetical), Prerolls (count), Status (active/inactive)
  - Click column header to sort ascending, click again to toggle descending
  - Visual sort indicator (▲/▼) shows current sort field and direction
  - **Impact**: Quickly organize categories by most used, active schedules, or alphabetically

### Changed
- **Category Management Layout Overhaul**
  - Removed standalone "Create New Category" section for cleaner page layout
  - Added green "+ Create Category" button above search bar for quick access
  - Added "🎄 Load Holiday Categories" button next to create button
  - Create category now opens in modal popup with name and description fields
  - Modal includes helpful tip about playback mode configuration
  - **Impact**: Cleaner, more compact interface with modal-based category creation workflow

### Fixed
- **Verification Loop Error**
  - Fixed infinite verification loop that logged "name 'mode' is not defined" error every 30 seconds
  - Updated verification query to include many-to-many category associations (prerolls assigned as secondary categories)
  - Fixed undefined variable in debug print statements when reapplying category after verification mismatch
  - Verification now correctly counts all prerolls (both primary and associated categories) when checking Plex settings
  - **Impact**: Eliminates recurring error messages and ensures verification accurately reflects expected preroll configuration

### Added
- **Video Preview for Similar Matches**
  - Added preview/play button (▶) next to each similar match result in Edit Preroll modal
  - Users can now preview community preroll videos before confirming a match
  - Preview opens in modal with video player, allowing full video playback
  - Helps users verify correct match and avoid false positives from fuzzy matching
  - **Beta Tester Impact**: Increased confidence in match selection with visual confirmation

### Fixed
- **Calendar View Filter Bug**
  - Fixed disabled schedules still appearing in weekly and yearly calendar views
  - Disabled schedules now properly hidden from week view timeline
  - Disabled schedules now properly hidden from month timeline view
  - Disabled schedules now properly hidden from upcoming schedules dashboard widget
  - When a schedule is disabled, it immediately disappears from all calendar views
  - When re-enabled, schedule appears again in calendar views
  - **Beta Tester Impact**: Prevents confusion from seeing inactive schedules in calendar

- **UI Text Correction**
  - Fixed placeholder "N" text in Random block button description
  - Changed from "Select N random prerolls from category" to "Select random prerolls from a category"
  - **Beta Tester Impact**: Clearer block description in Sequence Builder

## [1.8.0-beta.1] - 11-20-2025

### Added
- **Community Match Status Feature (Phase 1 & 2)**
  - Visual indicators showing which prerolls match Community Prerolls library
  - Edit Preroll modal displays match status with green ✅ (matched) or amber ⚠️ (unmatched) status box
  - Dashboard list and grid views show ✅ icons for matched prerolls
  - "Matched to Community" badge in preroll card descriptions
  - Filter dropdown in Prerolls section to sort by match status (All/Matched/Unmatched)
  - **Auto-Match Functionality**: "Auto-Match Now" button in Edit modal with loading spinner
  - Fuzzy matching algorithm with confidence scoring (exact, substring, word overlap)
  - Similar matches list when no confident match found (50%+ confidence threshold)
  - Automatically filters out community prerolls with hash-like prefixes (e.g., "1740Bdd395C04C5Ea7843Da12858C2B4.Title")
  - Manual selection from similar matches with color-coded confidence badges (green ≥70%, amber 40-69%, red <40%)
  - Auto-match only applies for very confident matches (≥80% similarity)
  - **Unmatch Functionality**: Red "Unmatch" button to remove incorrect community matches
  - **Exclude from Matching**: Checkbox option to prevent specific prerolls from being auto-matched to Community Prerolls library
  - Dark mode compatible styling for similar matches interface

- **Advanced Sequence Builder**
  - Complete overhaul of sequence creation interface with visual building blocks
  - Added 6 new sequence block types:
    - **Preroll Block**: Select individual prerolls with thumbnail previews
    - **Random Block**: Select X random prerolls from a category
    - **Sequential Block**: Play all prerolls from a category in order
    - **Queue Block**: Add all prerolls from the current queue
    - **Sequence Block**: Nest existing sequences within sequences
    - **Separator Block**: Visual dividers to organize complex sequences
  - Real-time sequence preview with drag-and-drop reordering
  - Live playback duration calculation for entire sequence
  - Expandable/collapsible blocks for better organization of large sequences
  - Visual indicators for block types with emoji icons
  - Improved validation with clear error messages
  - One-click block duplication for rapid sequence building

- **Queue Management Integration**
  - Queue block allows adding all queued prerolls to sequences
  - Simplifies workflow: queue multiple prerolls → add all to sequence at once
  - Queue items displayed with thumbnails in sequence preview

### Changed
- **Sequence Creation UI**
  - Moved from simple multi-select list to sophisticated block-based builder
  - Enhanced visual hierarchy with card-based layout
  - Improved mobile responsiveness for sequence building
  - Better feedback for block operations (add, remove, reorder)

### Fixed
- **File Rename Functionality**
  - Fixed "New File Name" feature not renaming files on disk
  - Root cause: External/mapped files (managed=False) were silently skipped during rename
  - Added support for renaming external/mapped files with warning message
  - Warning alerts users: "This is an external/mapped file. Renaming may affect other systems that reference this file."
  - Added comprehensive error handling with user-facing messages (404 for missing source, 409 for existing target, 500 for other failures)
  - Enhanced logging with [RENAME] prefix for debugging
  - Added pre-flight validation (source exists, target doesn't exist)
  - Fallback mechanism: tries os.replace() first, then copy+delete if atomic rename fails

- **Community Match Backend Bug**
  - Fixed match indicators not showing despite prerolls being matched in database
  - Root cause: /prerolls endpoint was missing community_preroll_id field in response
  - Added community_preroll_id to API serialization

- **Filter Combination Bug**
  - Fixed match status filter overriding category filter instead of combining with it
  - Example: "Christmas > Matched" now correctly shows only matched Christmas prerolls, not all matched prerolls
  - Rewrote filtering logic to apply filters in cascading order: category → tags → match status

### Removed
- **Community Prerolls Cleanup**
  - Removed "Calendar Week Start" setting from NeXroll Settings (unused feature)
  - Removed "Community Templates" section from Settings page (feature not active)
  - Removed "✨ Discovery: Latest Prerolls" section from Community Prerolls page
  - Frontend bundle size reduced by ~1.3 KB total

### Technical
- **Community Match System**
  - POST /prerolls/{id}/auto-match endpoint for fuzzy matching (skips excluded prerolls)
  - POST /prerolls/{id}/link-community/{community_id} endpoint for manual linking
  - POST /prerolls/{id}/unmatch-community endpoint to remove incorrect matches
  - Fuzzy matching algorithm: title normalization, exact match, substring match, word overlap
  - Returns top 10 similar matches with confidence scores when no exact match (≥50% threshold)
  - Hash prefix filter: excludes community prerolls with 20+ character alphanumeric prefixes
  - Very confident matches (≥80%) automatically linked, lower confidence shown for manual selection
  - Added exclude_from_matching Boolean column to Preroll model (default: False)
  
- **File Rename Enhancement**
  - Removed managed=True restriction on file renames
  - Added rename_warning tracking for external/mapped files
  - Enhanced error handling with HTTPException for all failure cases
  - Detailed [RENAME] logging throughout rename process
  - Response includes warning field when renaming external files
  
- **Sequence Builder**
  - Refactored sequence data model to support heterogeneous block types
  - Backend now handles 6 block types: 'preroll', 'random', 'sequential', 'queue', 'sequence', 'separator'
  - Added frontend validation for block configuration before submission
  - Improved sequence playback logic to handle nested sequences and dynamic blocks
  - Updated API endpoints to support new block structure

## [1.7.16] - 11-16-2025

### Fixed
- **Docker Upload Bug** 
  - Fixed file uploads failing in Docker environments due to hardcoded localhost URLs
  - Converted 40+ fetch() calls to use dynamic API URL resolution via apiUrl() helper
  - Upload now works correctly in Docker, remote deployments, and localhost

- **Scheduler Interval**
  - Fixed scheduler logging every 1 second causing log spam
  - Changed default scheduler check interval from 1 second to 60 seconds
  - Added configurable SCHEDULER_INTERVAL environment variable (default: 60 seconds)
  - Genre-based auto-switching still responds quickly (separate check)

- **Timezone Auto-Detection**
  - Added support for TZ environment variable in Docker deployments
  - Timezone now auto-detected on first startup from TZ environment variable
  - Eliminates need for manual timezone configuration in Docker
  - Validates timezone using pytz before applying to database

- **Secondary Category Auto-Apply**
  - Fixed prerolls added to secondary categories not being auto-applied to Plex
  - When adding preroll to non-primary category with active schedule, Plex now updates immediately
  - Added db.expire_all() to clear SQLAlchemy session cache before querying for prerolls
  - Ensures newly committed associations are visible in subsequent queries

### Technical
- Created automated script (`scripts/fix_hardcoded_urls.py`) for URL conversion
- Updated `testing/backend/scheduler.py` with configurable interval support
- Updated `testing/backend/main.py` with TZ environment variable detection
- All executables rebuilt with fixes (NeXroll.exe, NeXrollTray.exe, NeXrollService.exe)

## [1.7.15] - 11-14-2025

### Changed
- **Calendar View Default**
  - Monthly calendar now defaults to grid view instead of timeline view
  - Provides immediate visual overview of schedule distribution across the month

### Fixed
- **Custom Schedule Colors Display**
  - Fixed grid view legend to show individual schedules with custom colors instead of categories
  - Fixed yearly overview to display schedules with custom colors instead of categories
  - Fallback schedule borders now respect custom colors for better visual consistency

## [1.7.12] - 11-14-2025

### Added
- **Custom Schedule Colors** 
  - Users can now assign custom hex colors to individual schedules
  - Color picker UI with visual selector, hex input field, and clear button
  - Custom colors override category colors in all calendar views (Week, Month, Year)
  - Optional feature - schedules without custom colors continue using category colors

- **Preroll Matching & Verification**
  - "Match Existing Prerolls" button to associate uploaded prerolls with categories based on tags/keywords
  - "Rematch Prerolls" button to re-run matching algorithm on existing prerolls
  - Automatic matching suggestions when uploading new prerolls
  - Improved matching accuracy with keyword-based category association

### Fixed
- **Plex Preroll Verification**
  - Fixed verification system to properly confirm prerolls were applied to Plex
  - Added retry logic when verification fails on first attempt
  - Improved error reporting when preroll application fails
  - Better handling of Plex API response validation

### Technical
- Added `color` column to schedules table with automatic migration
- Updated schedule API endpoints (POST/PUT/GET) to handle color field
- Enhanced calendar rendering logic across all calendar modes
- Seamless database migration for existing installations

## [1.7.11] - 11-13-2025

### Fixed
- **Additional Docker Query Fixes**
  - Fixed `get_downloaded_community_preroll_ids` endpoint crashing when `community_preroll_id` column doesn't exist
  - Fixed legacy migration functions querying non-existent columns in old databases
  - Added column existence checks before all database queries involving `community_preroll_id`
  - Resolves remaining 500 errors when using Docker with pre-v1.7.9 databases

## [1.7.10] - 11-13-2025

### Fixed
- **Docker Compatibility**
  - Fixed `'community_preroll_id' is an invalid keyword argument for Preroll` error when downloading community prerolls
  - Added conditional kwargs handling for databases created before v1.7.9 column migration
  - Now gracefully handles both old and new database schemas
  
- **Changelog Display in Docker**
  - Fixed "No changelog available" message in Docker containers
  - Added Docker-specific paths (`/app/CHANGELOG.md`, `/app/NeXroll/CHANGELOG.md`)
  - Improved path search with logging across 10+ possible locations
  - Now works correctly in PyInstaller bundles, Docker, and development environments

## [1.7.9] - 11-13-2025

### Added
- **Enhanced Community Prerolls Search**
  - Search now includes tags, filenames, AND display names (previously only tags)
  - More comprehensive search results across all preroll metadata
  
- **Download Tracking System**
  - "✓ Downloaded" indicator on community prerolls you already have in your collection
  - Green checkmark replaces download button for prerolls you've already downloaded
  - ID-based tracking ensures 100% accuracy for new downloads
  - Automatic background migration attempts to detect legacy downloaded prerolls
  
- **Legacy Preroll Support**
  - Hybrid matching system supports prerolls downloaded before tracking was implemented
  - Title-based detection with strict 90% similarity threshold prevents false positives
  - Manual migration endpoint available: `/community-prerolls/migrate-legacy`

### Changed
- **Strict Matching Algorithm**
  - Tightened legacy preroll matching from 70% to 90% length similarity threshold
  - Removed word-based matching to eliminate false positives
  - Only exact matches or near-identical titles (90%+ similar) qualify as matches

- **System Tray Menu Improvements**
  - Removed "Start App (portable)" option as it was redundant
  - Added separator lines between menu sections for better organization
  - Menu now grouped into logical sections: Main Action, Service Controls, Maintenance, Info & Links, and Exit

### Fixed
- **False Positive Prevention**
  - Fixed issue where searching terms like "Christmas" incorrectly marked all prerolls as downloaded
  - Word-based matching removed - no longer matches prerolls sharing common words
  - Significantly improved accuracy for legacy preroll detection

## [1.7.7] - 11-10-2025

### Fixed
- **Schedule Date/Time Shifting** ([#9](https://github.com/JFLXCLOUD/NeXroll/issues/9))
  - Fixed schedule dates/times randomly shifting when saving or updating
  - Schedule dates are now stored as naive datetime (local time) instead of UTC
  - Eliminated 6-hour time jumps caused by incorrect timezone conversion
  - Dates entered in schedules now remain exactly as set (e.g., Oct 31 5am stays Oct 31 5am)
- **Backup Restore Foreign Key Error** ([#10](https://github.com/JFLXCLOUD/NeXroll/issues/10))
  - Fixed database restore failing with "FOREIGN KEY constraint failed" error
  - Corrected deletion order to clear junction tables before dependent tables
  - Restore now deletes: preroll_categories → schedules → prerolls → categories → holidays
  - Backup restore operations now complete successfully without constraint violations

## [1.7.4] - 11-09-2025

### Added
- **Enhanced Calendar Views**
  - Added **Week View** with timeline visualization showing schedules as continuous colored bars across 7 days
  - Added **Timeline View for Month** - alternative to grid view showing schedules as continuous spans
  - Month view now includes Display toggle button to switch between Timeline and Grid views
  - Week view includes Previous Week / This Week / Next Week navigation buttons
  - Timeline views show schedule duration with colored bars and day markers at bottom

- **New Schedule Types**
  - Added **Daily** schedule frequency option for repeating prerolls every day
  - Added **Weekly** schedule frequency option for repeating prerolls every week
  - Both options available in Create Schedule and Edit Schedule forms

- **Improved Calendar Navigation**
  - View dropdown now includes: Week, Month, Year
  - Seamless switching between different calendar perspectives
  - Timeline visualizations make it easier to see schedule overlaps and duration

### Fixed
- **Category Management Modal Issues** ([#7](https://github.com/JFLXCLOUD/NeXroll/issues/7))
  - Fixed Edit and Remove buttons not responding in Edit Category modal
  - Edit Preroll modal now properly appears on top when opened from Edit Category
  - Fixed modal overlay blocking clicks to nested modals
  - Improved modal stacking with proper z-index management

## [1.7.3] - 11-08-2025

### Fixed
- **Calendar & Schedule Issues**
  - Fixed yearly/holiday schedules not repeating annually in calendar view
  - Fixed fallback categories not displaying in calendar when no other schedule is active
  - Fixed holiday preset dates being shifted to wrong month due to timezone conversion
  - Backend now preserves naive datetime for yearly/holiday schedules (only month/day matters)
  - Fixed timezone issue where January 31st 23:59 was being stored as February 1st 04:59 UTC

### Added
- **Enhanced Calendar Visualization**
  - Year view now shows as default when opening calendar
  - Larger calendar cells with improved spacing and readability
  - Schedule name tooltips on hover showing all active schedules for each day
  - Fallback category visual indicator with dashed borders
  - Weekend shading for better day-of-week orientation
  - Today highlighting with blue border and colored badge
  - Visual legend explaining all calendar indicators
  - Smooth hover animations with elevation effects
  - Click month cards in year view to drill down to detailed month view

## [1.7.0] - 11-03-2025

### Added
- **Community Prerolls Integration**
  - Access to thousands of community-curated prerolls from prerolls.uk
  - Smart search engine with synonym expansion (e.g., "turkey" → "thanksgiving")
  - Local index system with unlimited-depth directory scanning (1,327+ prerolls)
  - Dual HTML/JSON parsing for Caddy web server compatibility
  - Real-time progress bar with SSE (Server-Sent Events) during indexing
  - Platform filtering (Plex/Jellyfin)
  - One-click downloads with NO automatic tagging
  - Random preroll discovery feature
  - Fair Use Policy acceptance tracking
  - Indexing button appears automatically after Fair Use acceptance

- **Auto-Apply to Server**
  - Categories automatically reapply to Plex/Jellyfin when new prerolls are added
  - Works for all add methods: upload, community download, drag-and-drop
  - Works for both manually applied categories AND scheduled categories
  - Detects active scheduled categories and updates them automatically
  - Prevents need to manually click "Apply" after adding prerolls

- **Enhanced Plex Connection**
  - Multiple connection methods (Manual, OAuth, Saved Token, Auto-discovery)
  - Secure token storage via Windows Credential Manager
  - Automatic token migration from legacy plaintext storage
  - Enhanced status display with token source tracking
  - Docker-aware auto-discovery for containerized environments
  - Detailed error messages with actionable guidance

- **Database Migration System**
  - Automatic schema migration from v1.5.12+
  - Missing column detection and addition
  - Migration status logging with visual indicators
  - Schema validation on startup

- **GitHub Integration**
  - Bug report button with pre-filled template
  - Feature request button with template
  - Issue templates for consistent reporting
  - Before reporting checklist in Settings

- **Docker Support**
  - Dockerfile for containerized deployment
  - docker-compose.yml with examples
  - Multi-architecture support (amd64, arm64)
  - GitHub Actions workflow for automated builds
  - Docker-specific connection methods

### Changed
- **Plex Status Display**
  - Now shows actual server information instead of form inputs
  - Displays token source (secure_store vs database)
  - Shows storage provider (Windows Credential Manager)
  - Includes server name and version information
  - Color-coded error messages (yellow warnings, red errors)

- **Community Prerolls UI**
  - Search bar width reduced to 60% for better aesthetics
  - Updated search hints to reflect actual capabilities
  - Improved empty state messaging
  - Better platform filter interface

- **Error Handling**
  - Specific error codes: not_configured, missing_token, connection_failed, etc.
  - User-friendly error messages
  - Enhanced logging throughout application
  - Never crashes UI with 500 errors

- **Configuration**
  - Token storage moved to Windows Credential Manager
  - Config file location: %PROGRAMDATA%/NeXroll/
  - Config files now sanitized (no plaintext secrets)

### Fixed
- **Critical: Scheduler crash on upgrade from v1.5.12**
  - Added missing dashboard_layout column to migration
  - Fixed OperationalError when querying missing columns
  - Auto-migration now includes all 8 missing columns

- **Community Prerolls Issues**
  - Fixed indexing only finding ~200 files instead of 1,327+ (Caddy JSON parsing)
  - Fixed progress bar stopping at 95% and not completing
  - Fixed progress bar not hiding after indexing completes
  - Fixed indexing button not appearing on fresh installs after Fair Use acceptance
  - Fixed category dropdown hard to see in dark mode
  - Fixed installer packaging wrong executables (build\dist vs dist)
  - Fixed SSE connection closing before final progress update delivered

- **Plex Connection Issues**
  - Fixed token migration from plaintext to secure store
  - Fixed config file path migration
  - Fixed silent migration failures
  - Fixed status endpoint showing incorrect information

- **Database Schema**
  - Fixed missing columns causing crashes
  - Fixed auto-migration trigger
  - Fixed schema validation

- **UI Issues**
  - Fixed Plex status showing form values instead of server info
  - Fixed error messages returning generic responses
  - Fixed token source visibility
  - Fixed category dropdown using CSS variables that don't work with <select> elements

### Security
- All Plex tokens now stored in Windows Credential Manager
- Configuration files no longer contain plaintext tokens
- Automatic migration of legacy tokens to secure storage
- Sanitized config files with metadata only

## [1.6.0] - 10-XX-2025

### Added
- Genre-based preroll mapping (experimental)
- Dashboard customization options
- Enhanced timezone support

### Changed
- Improved scheduler performance
- Updated UI styling

### Fixed
- Various bug fixes and improvements

## [1.5.12] - 09-XX-2025

### Added
- Basic Plex integration
- Schedule management
- Category organization

### Changed
- UI improvements
- Performance optimizations

### Fixed
- Connection stability issues

---

## Migration Guide

### Upgrading to v1.7.0 from v1.5.12

**Automatic Migration:**
Your database and settings will be automatically migrated on first launch.

**What Gets Migrated:**
- Database schema (8 new columns added)
- Plex tokens (moved to secure storage)
- Configuration files (sanitized)
- Path settings (preserved)

**Expected Console Output:**
```
>>> UPGRADE DETECTED: Migrating database schema for Plex settings...
>>> SCHEMA MIGRATION: Added settings.dashboard_layout (TEXT)
>>> MIGRATION SUCCESS: Database schema migration completed
>>> UPGRADE STATUS: Plex connection status after migration - connected: true
```

**Post-Migration:**
1. Verify Plex connection in Connect tab
2. Check logs at %PROGRAMDATA%\NeXroll\logs\nexroll.log
3. Test scheduling functionality
4. Accept Fair Use Policy for Community Prerolls

---

## Links

- [GitHub Repository](https://github.com/JFLXCLOUD/NeXroll)
- [Release Notes](RELEASE_NOTES_1.7.0.md)
- [Docker Hub](https://hub.docker.com/r/jbrns/nexroll)
- [Issue Tracker](https://github.com/JFLXCLOUD/NeXroll/issues)
