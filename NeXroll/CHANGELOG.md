# Changelog

## [2.2.2] - 10-02-2026

> Else if chains so only the first matching block plays, NeX-Up trailers that match the film's genre, a prerolls-only setup for Plex's new Apple TV and iOS app, categories you can create where you need them, and fixes for deleted prerolls, category counts and the Upcoming list.

### Upgrading

- **NeX-Up trailers learn their genres on the next sync.** Trailers downloaded before 2.2.2 have none until then, so they don't match a genre yet. No plugin update is needed.

### Added

- **Else if: first match wins.** In Advanced mode, tick **Else if** on a block to check it only when the block above it didn't play. Chain several, for example one genre preroll per movie in your order of priority, and end with a block that has no condition to play when none match.
- **NeX-Up trailers can match the genre of the film starting** on Jellyfin and Emby, like Library trailers. **When no trailer shares its genre** chooses between trailers of any genre and none.
- **Turn off Plex trailers.** The Cinema Trailers card on the Connect page turns off Plex's own trailer sources in one click, so "Play 1 before movie" in Plex's new Apple TV and iOS app plays only your prerolls. That app's "Play Pre-roll Only" option is broken on Plex's side.
- **Create a category on the spot.** Wherever you put prerolls into a category (uploading, editing, Import Folder, the Library's bulk bar, Community downloads), you can create a new one without leaving the page.
- **Remove a server NeXroll can't reach.** A saved Plex, Jellyfin or Emby server that doesn't answer now shows **Can't connect** with a **Remove** button. Before, it could only be disconnected while it was working.

### Fixed

- **Deleted prerolls were never cleaned up.** Deleting more than a quarter of the library on disk looked like an offline share, so the entries stayed and the dashboard said not to remove them. Files deleted from folders that are still there are now removed on the next scan, and when NeXroll can't tell, the dashboard offers to remove them.
- **Refresh Library only reloaded the page.** It now scans the storage folder for added and deleted files, then reloads.
- **Upcoming schedules hid Yearly and Holiday schedules** saved with an earlier year's dates, such as a New Year holiday created last year. They ran on time; the dashboard list now shows them.
- **Categorized prerolls counted as uncategorized.** A preroll whose first category was deleted kept its other categories but showed as uncategorized in the Library's "Needs category", the edit dialog, the schedule editor's preroll picker and sequence duration estimates.
- **Removing a category in the edit dialog didn't stick.** Removing a preroll's first category left it in that category (which still played it), and removing its last category did nothing.
- **Trailers longer than Max Trailer Duration were reported as a YouTube bot block.** They are now reported as skipped for length, and the setting no longer shows "3 minutes" when set to No limit.
- **The holiday country list was in code order.** It is now alphabetical.

### Issues resolved

- [#41](https://github.com/JFLXCLOUD/NeXroll/issues/41): Prerolls didn't play in Plex's new Apple TV app. Plex's "Play Pre-roll Only" is broken there; use **Turn off Plex trailers** with "Play 1 before movie".
- [#43](https://github.com/JFLXCLOUD/NeXroll/issues/43): NeX-Up trailers can now match the playing movie's genre.
- [#44](https://github.com/JFLXCLOUD/NeXroll/issues/44): One genre preroll per movie with a default for the rest, using Else if chains.
- [#45](https://github.com/JFLXCLOUD/NeXroll/issues/45): "Needs category" counted categorized prerolls. Fixed, along with the other places that showed them as uncategorized.

## [2.2.1] - 09-27-2026

> A security update for the YouTube PO-token provider, Plex path mappings that check and set themselves up, per-server prerolls, and fixes for Jellyfin and Emby sequences, sequence sharing and backups.

### Upgrading

- **Windows:** after updating, open NeX-Up and click **Update** on the YouTube downloads card. The old PO-token provider is no longer started (see Security). Docker images already include the fixed one.
- **Jellyfin and Emby:** update the NeXroll Intros plugin (Jellyfin 10.11 1.14.1.0, Jellyfin 12 1.15.1.0, Emby 1.14.1.0). A plugin installed from the NeXroll repository updates itself; the Emby DLL is replaced by hand from the Connect page. Until then, set Max Intros to 0 on Jellyfin so sequences play in full.

### Security

- **The YouTube PO-token provider could be reached from the whole network.** NeXroll ran bgutil 1.3.1, which listened on every network interface and had a remote code execution flaw reachable that way (GHSA-qpv9-8xfj-xx9m). It now runs 2.0.0, which answers only this machine.
- **The Docker image reported fixable vulnerabilities.** They came from the PO-token provider's build tools and outdated dependencies, and from the copies of setuptools and msgpack bundled inside pip. The image now ships only what the provider runs, on patched versions, and no pip.

### Added

- **Can Plex open your prerolls?** Settings > Path Mappings asks your Plex server whether it can open each preroll it is set to play, and says why not when it can't. Plex only: Jellyfin and Emby never need a mapping.
- **Find it for me.** Searches the folders your Plex server can see for every folder NeXroll hands Plex files from (your prerolls, NeX-Up trailers stored outside the preroll folder, and the movie folders Library Trailers read trailer files from), confirms each by finding your files there, and adds the mappings in one click.
- **Browse Plex.** Pick a mapping's Plex folder from Plex's own view of its disk instead of typing it.
- **Test Translation checks with Plex** as well as showing the translated path.
- **The first-run wizard sets up the mapping too.** Its Paths step now appears whenever Plex is connected, not only on Docker, and is skipped when only Jellyfin or Emby is connected.
- **Different prerolls on each media server.** A new **Media server** condition (Advanced mode) plays a block only on the servers you choose, with its Otherwise everywhere else, so Plex and Jellyfin or Emby can each have their own category in one sequence.

### Fixed

- **On Jellyfin and Emby, Max Intros cut sequences short.** The setting that made a random category play one preroll also stopped every sequence after its first block, and on Emby it did so out of the box. NeXroll now decides how many play, as it does for Plex: one preroll from a random category (or the number set on the Connect page), working through the whole category before repeating, while sequences and in-order categories play in full. If you left Max Intros at 0 on Jellyfin and heard a whole random category before each movie, you now hear one.
- **Prerolls Plex could not open were applied anyway.** A path that matched no mapping went to Plex unchanged and nothing played, with no warning. NeXroll now checks each file with Plex before applying and leaves out what Plex can't see; if it can see none of them, Plex keeps its current prerolls. `NEXROLL_PLEX_PATH_CHECK=0` turns the check off.
- **Applying a saved sequence skipped Plex on most installs while reporting success.**
- **The External API's category apply reported success even when Plex refused the change.**
- **A mapping for `/data/pre` also caught `/data/prerolls2`.** Mappings now match whole folder names.
- **Importing a sequence into Saved Sequences never saved it.** It now saves; a sequence whose categories or prerolls aren't on this server opens in the builder to finish instead.
- **Exports left part of the sequence behind.** A fixed block with several prerolls exported only the first, and a full bundle left out the videos of in-order categories and of conditional blocks' alternatives.
- **Full bundles came back under different names.** Apostrophes and other marks were stripped from bundled names, so the imported sequence pointed at categories and prerolls that didn't exist. .m4v and .webm videos were never imported, and a sequence named with a character such as an em dash couldn't be bundled at all.
- **Backups left out your media server logins.** The Plex token and Jellyfin and Emby API keys were in neither backup. Both backups now carry them, and a restore puts them back.
- **A System Backup could miss your latest changes.** Its database copy left out the last few minutes of edits. It now takes a consistent copy.
- **Restoring a Database Backup could hide a schedule conflict.** Ignored conflicts pointed at different schedules after the restore. They now follow their schedules, and sidebar favorites are backed up too.
- **A System Restore on another machine kept the old machine's folders.** New NeX-Up downloads went to a folder that only existed there, and uploaded Generator logos, soundtracks and backdrops were not found. The restore now uses this install's folders and relinks those files, and no longer needs the whole backup to fit in memory.
- **The Path Mappings header showed invented numbers.** It now shows how many prerolls Plex can open and what Plex runs on.
- **Choosing a theme in Settings pushed its name to the edge of the button.**
- **Path Mappings was cramped on phones.**

## [2.2.0] - 09-25-2026

> The stable release of the 2.1 and 2.2 betas. A sequence can now react to the
> film that is starting and be drawn as a flow, NeXroll keeps trailers for the
> movies you already own, one install drives Plex, Jellyfin and Emby together,
> and schedules, backups and system health report what is really happening.
> Coming from 2.0.5, everything on this page is new to you.

**NeXroll 2.2.0** promotes 2.1.0-beta.1 through 2.1.0-beta.3 and 2.2.0-beta.1 through 2.2.0-beta.11, plus the work finished after beta.11 listed further down. The individual beta notes are in CHANGELOG-ARCHIVE.md. Upgrading from 2.0.x or any 2.2.0 beta keeps your library, schedules, sequences, settings and dashboard layout: new settings and tables migrate on first start, and older schedules are repaired without changing what they play. Take a backup before updating all the same.

### Highlights

- **Sequences that react to what is starting.** Turn on Advanced mode and any block can play when a rule holds, or unless it does, with an Otherwise for when it does not: trailers available, time of day, genre, movie or episode, and on Jellyfin and Emby the stored audio format. Flow view draws the same sequence as a node canvas, and Preview shows what each viewer will get, including as Plex or as a chosen genre.
- **Library Trailers.** Trailers for the movies you already own, from the files beside them or downloaded from the link Radarr holds, chosen by hand or by filters. A Library trailers block can match the genre of the film starting, trailer blocks can restrict age ratings, and the pool can keep minimum rating and genre targets.
- **Plex, Jellyfin and Emby at the same time.** Connect every server you run and one set of schedules drives them all. Jellyfin 12 has its own plugin build (1.15.0.0) alongside 1.14.0.0 for Jellyfin 10.11, both with update catalogs, and NeXroll serves the Emby plugin itself.
- **NeX-Up Generator Studio.** One workspace for animated prerolls, with Custom Message and QR Code templates, nine bundled typefaces plus your own, custom video backdrops and soundtrack-length matching. Coming Soon lists gain theme palettes, animated backdrops and an optional QR code, and both generators can be driven from the External API.
- **Eight themes and a redesigned dashboard.** Midnight, Daylight, Cinema, Nocturne, Parchment, Terminal, Neon and Carbon, across a rebuilt dashboard and one consistent layout on every page. Star any page to keep it in the sidebar; favorites follow your account.
- **Schedules that say what they will do.** Holidays land on their real next date, Yearly schedules no longer show "Not scheduled", every schedule type works out its next run from the same rules playback uses, and the calendar shows monthly schedules, filler and conflicts where they actually fall. Conflicts are counted once, from the list the Conflicts page opens.
- **Backups that restore.** Backups now carry your settings, connections and generator output, and a restore no longer drops your NeX-Up, filler and active category choices.
- **A library that is harder to lose.** Deleting a preroll's file moves it to a 30-day trash, a removed preroll stays removed after the next scan, and the Library sorts by date added, name or duration.
- **System health that checks.** The dashboard contacts every configured media server, says which one is down and why, and recovers on its own when it comes back.
- **Community Prerolls.** Multi-select and bulk download, a filter for AI-generated content, and AI badges carried through into your Library.

### Upgrading from 2.0.x

- **Genre-based preroll mapping is gone.** Its settings were removed from the interface in 1.9.10 and the code left running behind them has now been removed too. On Jellyfin and Emby, a genre rule in an Advanced sequence can do the same job.
- **Your dark or light preference carries over** as the Midnight or Daylight theme.
- **Jellyfin 12 needs the 1.15.0.0 plugin**; Jellyfin 10.11 stays on 1.14.0.0. A plugin installed by hand needs a one-time switch to the plugin repository to receive updates, described on the Jellyfin wiki page. The Connect page shows the right repository address for your server.
- **Emby plays prerolls only through the NeXroll Intros plugin**, which the Connect page can now download for you.
- **Check your timezone in Settings after the first start.** Some installs held two settings rows, which made time-of-day schedules run on UTC. The duplicate is merged on startup.

### Issues resolved

- [#36](https://github.com/JFLXCLOUD/NeXroll/issues/36): Jellyfin 12 reported a valid API key as lacking permission, and a generated preroll in a sequence never played on Jellyfin. Both fixed.
- [#38](https://github.com/JFLXCLOUD/NeXroll/issues/38): NeX-Up trailer downloads failed with HTTP 403. The installer and Docker image ship a current yt-dlp.
- [#39](https://github.com/JFLXCLOUD/NeXroll/issues/39): Trailers from the automatic sync stayed pending and never rotated. Fixed, and existing records are repaired on first start.
- [#40](https://github.com/JFLXCLOUD/NeXroll/issues/40): Yearly schedules showed "Not scheduled". Fixed, and existing Yearly schedules are normalized on upgrade.

### Added since beta.11

- **Trailer blocks can restrict age ratings.** Choose which movie or TV ratings a NeX-Up trailers or Library trailers block may play, including in an Otherwise. A restriction with no ratings selected plays no trailers, and trailers with no rating play only when you select Unrated. Existing sequences keep their current selection until you edit them. Ratings describe the film or show, not a separate rating of its trailer.
- **Availability conditions can check the right trailer pool.** Choose Upcoming, Library, or This / next trailer block. The last follows that block's own filters, count and conditions, so a Coming Soon or Now Available intro only runs when matching trailers will follow it. Existing availability conditions keep checking upcoming trailers.
- **Library Trailers can keep minimum rating and genre targets.** Ask for a mix such as two G or PG trailers and five horror trailers, within your existing download and storage limits. Trailers already beside your movies count, one trailer can satisfy two targets, and each sync reports any target it could not meet and why. A replacement only removes a trailer once its successor has downloaded. Configurations without targets behave exactly as before.
- **Sequence blocks can match the stored audio format on Jellyfin and Emby.** An Advanced condition checks the default audio track, or any audio track, of the file about to play, so a Dolby or DTS demo can run in front of films that carry it. Missing or ambiguous metadata plays the Otherwise, as does Plex, which never says what it is about to play. This reads the file's metadata: it cannot see the track a client picks or what a transcode outputs, and it does not distinguish Atmos, DTS:X or THX. Preview can simulate a format.
- **A Library Trailers dashboard card.** Local and downloaded counts, download storage, errors and live sync status, with a Sync button that uses your saved configuration. It is in the dashboard presets, and an existing custom layout gains it without being reset.
- **Favorite pages in the sidebar.** Star the page you are on to add or remove a shortcut. Favorites belong to your account and follow you to other browsers and devices; with sign-in disabled, everyone shares one list. They work in the collapsed sidebar and on phones.

### Fixed since beta.11

- **Yearly schedules showed "Not scheduled" even with a valid seasonal range.** Yearly schedules store a placeholder year, and the next-run calculation moved the start into the future while still comparing it with the stored end year, so a perfectly good season read as expired. Yearly now uses the same recurring window as playback, including ranges across New Year, leap days and optional daily hours, and the editor uses month and day controls with an explicit All year option. Existing Yearly schedules are normalized on upgrade without changing their content, boundary times, priority, enabled state or history, and linked holidays keep their first year.
- **Daily, Weekly and Monthly could disagree with themselves about when they next run.** The next run now comes from the playback rules, respecting every saved filter and first and last date, and paused or lower-priority schedules are kept up to date too. The calendar and filler gaps place an overnight window on both of the days it touches.
- **Editing an older schedule could change its meaning.** Monthly edits keep their real start and end dates and read missing filters as all months or days. Monthly and Holiday daily hours are shown and saved. Fixed-date holidays from earlier releases stay editable, and linked holidays keep their future dates through edits and refreshes. On upgrade, schedules keep their identity, content, priority, enabled state and history while their next-run dates are refreshed.
- **Malformed saved timing could crash a schedule or quietly run it all day.** A schedule with timing NeXroll cannot read now says it needs repair. It can still be paused, but not re-enabled until the timing is fixed, and the wizard catches incomplete choices before moving on.
- **System health stayed green after a media server went offline.** Health trusted saved settings rather than asking the server. It now makes an authenticated request to each configured Plex, Jellyfin and Emby server, refreshes every 30 seconds, shows Unhealthy with the reason, and clears itself when the server returns. A plugin registration with no server address to test shows as unverified.
- **A sequence restricted down to nothing could let unrelated prerolls play.** When a rating or audio rule leaves nothing to play, the Plex list is now cleared and Jellyfin and Emby no longer fall back to the active category. Older trailers pick up their ratings on the next normal Radarr or Sonarr sync, without being downloaded again.
- **Dashboard conflict counts did not take you to the conflicts.** Counts, health messages and calendar conflict badges now open Schedules > Conflicts directly, from the keyboard too.
- **The Library Trailers card flashed while the dashboard updated.** The card was being rebuilt on every dashboard change, throwing away its data. It now keeps its state and refreshes in the background.
- **The Community AI badge disappeared once a preroll was in your Library.** Prerolls downloaded from the Community `/AI/` directory now show the badge in grid and list views, the preview panel and the edit dialog, including ones downloaded before this release, and keep it through renames and category changes.
- **The Emby plugin NeXroll handed out was an old build.** Since beta.10 the Connect page, the Docker image and the installer served NeXroll Intros 1.0.0.0, a March build that predates the fix for intros failing to cache on Linux servers without a home directory, such as linuxserver.io containers. They now serve 1.14.0.0, built from the current plugin source. If you installed the Emby plugin from NeXroll, download it again from the Connect page and restart Emby.
- **The sequence canvas scrolled out of view while you edited a long block.** On desktop the List and Flow panel now stays on screen beside the settings. Smaller screens keep the normal stacked layout.
- **The sequence editor had no way out except saving it.** Opening a saved sequence from Schedules > Library put you in the builder with Save as the only exit. Leaving through the sidebar looked like it abandoned the edit, but nothing cleared it: the changed blocks stayed in memory, still pointing at the original sequence, so reopening the builder resumed an edit you thought you had dropped and the next save wrote it over the version in your library. Cancel now sits beside Import and Preview, clears the editor and returns you to the library, asking first when there is unsaved work. Moving a block on the Flow canvas counts as unsaved work, because that layout is saved with the sequence.
- **The community match suggestions were unreadable.** Picking a match by hand showed a list whose rows were wider than the panel holding them, so every title was clipped and the list scrolled sideways. The community ID is a long web address with no spaces in it, and nothing told the row it was allowed to shrink. Titles and IDs now fit the panel and give you the full value on hover.
- **Library Trailers contradicted itself about replacing trailers.** The note under the filters said trailers you already have are never deleted and in the same breath that they are the first replaced, without saying that only downloads are ever swapped out, and only when a download limit is full. With downloads switched off it now says plainly that nothing is ever swapped out, and otherwise that trailers sitting next to your movies are never removed.
- **A trailer block built in an earlier release kept its old name.** The sequence builder named a block from a label saved with it rather than from what the block is, so a sequence built before NeX-Up trailers was renamed still read "Upcoming trailers" while a new one read "NeX-Up trailers". Only the name differed; both played the same. Blocks are now named by what they are.
- **Downloaded library trailers filled up the preroll library.** The grid already holds back downloaded trailers, but it recognised them by a path under the NeX-Up storage folder in `movies/` or `tv/`, and Library Trailers download to `library/`. Unlike Coming Soon trailers they have no category of their own either, so the path was the only thing identifying them, which left them the one kind of downloaded trailer still listed by default. They now sit behind the same show-hidden control as the rest, and are counted in the library header alongside them.

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

The notes for each 2.1.0 and 2.2.0 beta, and for 2.0.0-beta.15 and earlier
back to 1.9.8, are kept in [CHANGELOG-ARCHIVE.md](CHANGELOG-ARCHIVE.md).
