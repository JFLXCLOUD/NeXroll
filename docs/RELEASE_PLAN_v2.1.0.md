# NeXroll 2.1.0 - Release Plan

Minor release. Two headline items: a data-loss fix in preroll deletion (done) and
the Focus Enhanced dashboard (to build), plus the usual docs refresh.

Version bumped to `2.1.0` in `NeXroll/version.py`, `NeXroll/backend/version.py`,
`NeXroll/version_info.txt`, and `Releases/installer.nsi`.
`NeXroll/frontend/package.json` stays at `2.0.0-beta.7`, as it has through the
whole 2.0.x line - it is not a version source anything reads.

---

## Status

| Track | State | Notes |
| --- | --- | --- |
| Preroll delete safety + trash | Done, uncommitted | Backend, frontend, and tests complete |
| Preroll import / thumbnail / login fixes | Done, committed | `aa883b3` |
| NeX-Up no-repeat random rotation | Done, uncommitted | Shuffle bag across sequence, filler, plugin, and direct playback paths |
| Focus Enhanced dashboard | Not started | Largest remaining item |
| Trash + restore UI | Done, uncommitted | Library > Trash page; ships in 2.1.0-beta.1 |
| Wiki + docs refresh | Not started | Blocked on the dashboard landing |
| r/NeXroll toolkit | Done, committed | `4da212c`; maintainer tooling, kept out of user-facing notes |

---

## Track 1 - Preroll delete safety (done)

The bug: deletion was gated on the `managed` flag, which the library scanner sets
on every file it indexes. Any file dropped into a category folder by hand and
picked up by a scan was therefore deleted from disk when removed in the UI, with
a confirmation dialog that never mentioned the disk.

Shipped:

- `DELETE /prerolls/{id}` takes `delete_file` (default `false`); the file is kept
  unless explicitly requested - [main.py:9497](../NeXroll/backend/main.py#L9497)
- Requested deletions move to a recoverable trash rather than `os.remove` -
  [preroll_trash.py](../NeXroll/backend/preroll_trash.py)
- An `ignored_paths` table stops the scanner re-importing a preroll that was
  removed from the library but kept on disk - [models.py](../NeXroll/backend/models.py),
  [scanner.py](../NeXroll/backend/scanner.py)
- Delete dialog names the file and folder, with an unchecked opt-in for disk
  deletion - [App.js:5153](../NeXroll/frontend/src/App.js#L5153)
- 20 new tests across `test_preroll_trash.py`, `test_scanner.py`, and
  `test_preroll_delete_integrity.py`; suite is 76 passing

Design note worth keeping: the trash lives at `<prerolls>/.nexroll-trash` rather
than under the data dir. Libraries are commonly on a network share while the data
dir is local, so a data-dir trash would copy gigabytes over SMB on every delete
and fill the system drive. Same-volume means the move is a rename. The scanner
already prunes dot-directories, so the trash is skipped for free.

**Before release:** commit this work. It is currently uncommitted in the working
tree along with a rebuilt `frontend/build`.

---

## Track 2 - NeX-Up no-repeat random rotation (done)

Random trailer blocks previously made an independent random draw on each
rotation. That is mathematically random, but it can repeatedly select the same
one or two trailers and make a larger library look stuck.

For 2.1.0, random category and NeX-Up trailer blocks use a shared, thread-safe
shuffle bag keyed to the playback context. Every eligible trailer is consumed
before that bag starts a new shuffled pass, and a changed eligible pool resets
the bag safely. Plex still publishes a fixed selection and refreshes it on the
existing safe periodic rotation; Jellyfin and Emby advance their selection when
the plugin requests intros. UI copy now states this instead of promising a new
selection on every Plex playback.

Acceptance:

- No trailer repeats before every eligible trailer in the same bag has appeared
- A trailer being enabled, disabled, added, or removed resets the affected bag
- Separate schedules, sequence blocks, fillers, and plugin delivery paths do not
  consume each other's rotation state
- Existing sequential and fixed block behavior is unchanged

---

## Track 3 - Focus Enhanced dashboard

Concept and prototypes: [docs/dashboard-concepts/](dashboard-concepts/)
(`focus-enhanced.html`, `focus-enhanced.css`, `focus-enhanced.js`). These are
standalone demos that do not import production React.

### What already exists

More groundwork is in place than the concept README implies:

- `dashLayout` state - `{ grid, order[], hidden[], locked }` -
  [App.js:5917](../NeXroll/frontend/src/App.js#L5917)
- 11 tiles in `DASH_KEYS`: servers, prerolls, storage, schedules, scheduler,
  current_category, upcoming, resolution_chart, nexup, community, weekly_calendar
- Drag-to-reorder, hide/show, lock toggle, and `TILE_SPANS` for wide tiles
- Persistence to both localStorage and the backend via `persistDashLayout`
- `GET`/`PUT /settings/dashboard-layout` backed by `settings.dashboard_layout`
  (plus an unused `settings.dashboard_tile_order` column) -
  [main.py:3496](../NeXroll/backend/main.py#L3496)

Data endpoints for most new tiles already exist too: `/plex/current-preroll-details`
(Now showing), `/scheduler/status`, `/system/storage/breakdown` (Storage mix),
`/system/health/storage`, `/stats`, `/dashboard`.

### The delta to build

1. **New tiles**
   - *Now showing* - hero tile: active schedule, mode, preroll count, timezone,
     applied-at, and a progress bar to the next change. Data from
     `/plex/current-preroll-details` and `/scheduler/status`.
   - *What's next* - timeline of the next few activations with Active / Next /
     Upcoming badges. Reuses the existing `upcoming` tile's data.
   - *System health* - a score ring plus per-service rows (scheduler, media
     server, schedule conflicts, community index age). **New aggregate endpoint
     required**; nothing today computes a composite score.
   - *Storage mix* - stacked bar over prerolls / NeX-Up trailers / database /
     thumbnails, from `/system/storage/breakdown`.
   - *Quick actions* - refresh, scan files, NeX-Up sync, rebuild thumbnails.
     All four already have endpoints.

2. **Page header** - greeting, date line, and a one-line health summary
   ("Your preroll system is healthy. Four schedule conflicts need a look.").

3. **Customize modal** - replaces today's inline edit mode. Presets (Essential /
   Operations / Everything), per-tile size, per-tile detail level, visibility
   toggles, reorder controls, tile spacing, and the greeting/health-note/date
   toggles. See `focus-enhanced-customize.png`.

4. **Layout schema extension.** A real stored layout today looks like this - note
   it already carries a `version`, so the migration has a clean hook:

   ```json
   {"version": 1, "grid": {"cols": 4, "rows": 2},
    "order": ["servers", "prerolls", "storage", "schedules", "scheduler",
              "current_category", "community", "nexup", "upcoming",
              "resolution_chart", "weekly_calendar"],
    "hidden": [], "locked": false}
   ```

   Focus Enhanced needs per-tile size and detail plus page preferences, as
   `version: 2`:

   ```
   {
     version: 2,
     grid, order[], hidden[], locked,        // existing, unchanged
     preset: "essential" | "operations" | "everything" | "custom",
     tiles: { <key>: { span: "third"|"twoThirds"|"full", detail: "compact"|"detailed" } },
     preferences: { greeting: bool, healthNote: bool, dateTime: bool, density: "compact"|"comfortable" }
   }
   ```

   `GET /settings/dashboard-layout` should upgrade a `version: 1` payload in
   place - fill the new keys with defaults, keep `order`/`hidden`/`locked` as
   they are - rather than discarding it. A user who customized their dashboard
   in 2.0.x must not be reset by upgrading. The endpoint's hardcoded default
   layout (two places in `get_dashboard_layout`) needs the same treatment; it
   currently lists only 8 of the 11 tiles in `DASH_KEYS`.

### Suggested order

1. Layout schema + migration, with the new keys defaulted and old layouts upgraded
2. System health aggregate endpoint (the only genuinely missing data)
3. New tile components, behind the existing grid
4. Customize modal, replacing inline edit mode
5. Presets and density last - they are compositions of the above

### Acceptance

- A 2.0.x user upgrading keeps their tile order and hidden set
- Every preset renders without a layout shift at 1280px and 1920px
- Layout survives a reload and a different browser (backend persistence, not just
  localStorage)
- No new network calls on tiles that are hidden

---

## Track 4 - Wiki and docs refresh

Follows the `docs: refresh wiki for v2.0.4` pattern (`9d86dbb`). Do this after
the dashboard lands so screenshots are not taken twice.

- [docs/wiki/Home.md](wiki/Home.md) - version references
- [docs/wiki/Getting-Started.md](wiki/Getting-Started.md) - dashboard walkthrough
- [docs/wiki/API.md](wiki/API.md) - **must** document the new endpoints:
  `delete_file` on `DELETE /prerolls/{id}`, the four trash routes, and the three
  ignore-list routes
- [docs/wiki/FAQ.md](wiki/FAQ.md) - add "I deleted a preroll, where did the file
  go?" covering the trash, its 30-day retention, and `NEXROLL_TRASH_RETENTION_DAYS`
- [docs/wiki/Troubleshooting.md](wiki/Troubleshooting.md) - recovering a file from
  `.nexroll-trash` by hand while there is no UI
- `docs/screenshots/Dashboard.png` and `N_Dashboard.png` - reshoot for the new
  dashboard. Note `Dashboard.png`, `Nex-Up_Connections.png`, and `prerolls.png`
  already have uncommitted modifications in the working tree.

---

## Release checklist

- [ ] Commit the delete-safety work (backend, frontend, tests, rebuilt `frontend/build`)
- [ ] Commit the NeX-Up no-repeat random rotation and rebuilt frontend
- [x] Bump version to 2.1.0 in the four version sources
- [x] Draft the 2.1.0 changelog entry
- [ ] Build the dashboard (Track 2)
- [ ] Refresh wiki and screenshots (Track 3)
- [ ] Date the changelog heading - currently `## [2.1.0][Unreleased]`
- [ ] `python -m pytest tests` from `NeXroll/` - 76 passing as of this draft
- [ ] `npx react-scripts build` in `NeXroll/frontend`, commit the build output
- [ ] Build the installer via `Releases/installer.nsi` (`APP_VERSION` already 2.1.0)
- [x] Verify a 2.0.5 to 2.1.0 upgrade - tested against a copy of a real 2.0.5
      database: `ignored_paths` is created by `create_all` on first run, all 62
      prerolls / 17 categories / schedules / sequences survive, and the stored
      `dashboard_layout` is preserved intact
- [ ] Tag and publish release notes

---

## Deferred

- **Primary category refactor** (issue #29) - explicitly out of scope.

## Risks

- The dashboard rewrite touches `App.js`, which is ~36k lines and holds all
  dashboard state. Land it incrementally rather than as one commit.
- Existing users have persisted dashboard layouts in both localStorage and the
  database. The two can disagree; decide which wins before writing the migration.
- `Releases/CHANGELOG.md` is stale at `1.12.0-beta.3` while `NeXroll/CHANGELOG.md`
  is current. Either sync them at release or delete the stale copy - right now it
  is a trap for anyone reading release history.
