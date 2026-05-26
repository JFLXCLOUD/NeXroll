# NeXroll Code Audit — v2.0.0 Prep

This document tracks findings from a full audit of the NeXroll codebase, performed
between v1.13.2 (shipped 2026-05-24) and v2.0.0. Findings are grouped by subsystem.
Each entry has a severity, a description, and what was done about it.

**Audit approach**: interleave — audit a subsystem, fix what's broken in it, document
the finding, move on. The aim is consistency, no half-features, no silent disconnects.

## Severity Legend

- **BUG** — a user-visible defect that produces wrong behavior
- **DISCONNECT** — same concept handled inconsistently across the codebase
- **DEAD** — code that exists but is not wired in (or wired in only one path of two)
- **UX** — friction that could be reduced without changing core behavior
- **DOC** — comment or naming that misleads a future reader

Status of each entry:
- **OPEN** — found but not yet fixed
- **FIXED** — patched in this audit pass; references the commit
- **DEFERRED** — acknowledged, intentionally not fixed in this pass (with reason)

## Driving Feedback (2026-05-25)

The audit was kicked off by user-reported issues from an external tester:

1. After deleting a category, the next promoted schedule had a sequence but Plex was
   served the full category pool instead of the sequence-defined subset.
2. Dashboard "Currently Showing" tile briefly showed "No category applied" after the
   category delete; required a manual schedule toggle to recover.
3. Could not add trailers/prerolls to a category after recreating the workflow.
4. Preview playback was not working (multiple browsers tested).
5. UX feedback: adding prerolls to a category is a "sea of thumbnails"; should
   respect Windows-side folder structure (tree picker).

These are tracked as **BUG-FEEDBACK-1..4** and **UX-FEEDBACK-1** below.

---

## Subsystems

### 1. Scheduler (`backend/scheduler.py`)
*Status: in progress*

#### SCHEDULER-1: "Already active" path does not re-apply when the winning schedule changes
**Severity:** BUG · **Status:** FIXED in this audit pass

[`scheduler.py` lines 1629–1671](NeXroll/backend/scheduler.py#L1629-L1671) is the branch
that runs when a scheduler tick determines `desired_category_id == setting.active_category`.
It currently only re-applies the schedule's sequence if the sequence has `random` blocks AND
the 10-minute rotation interval has elapsed. **It does not re-apply when a different schedule
becomes the winner but happens to share a `category_id` with the previously applied schedule.**

Failure scenario:
1. Schedule A active, `category_id = 5`, sequence `X`. Plex has sequence `X`.
2. Schedule B has `category_id = 5`, sequence `Y`, becomes the new winner (priority change,
   another schedule disabled, blend ends, etc.).
3. Tick: `desired_category_id = 5`, `setting.active_category = 5` → "already active" branch.
4. `should_rotate = False` if `Y` has no random blocks.
5. Plex keeps serving sequence `X` until the category itself changes.

This plausibly explains the user-reported "alt year round one applied the category pool, not
the sequence" symptom (BUG-FEEDBACK-1) when the previous schedule's category happened to be
identical to the new winner's category. The new schedule's sequence is never sent to Plex.

**Fix:** also re-apply when `setting.active_schedule_id != chosen_schedule.id` (the winner
identity changed). Apply via sequence path if `_has_valid_sequence` else category path.

#### SCHEDULER-3: Post-delete-category dashboard gap
**Severity:** BUG · **Status:** FIXED in this audit pass · **Resolves:** BUG-FEEDBACK-2

After `delete_category` cleared `setting.active_category` and `setting.active_schedule_id`,
the dashboard tile showed "No category applied" for up to 60 seconds (one scheduler tick)
even when other schedules were active and eligible to take over. Users had to manually
toggle a schedule to force the re-evaluation.

**Fix:** Added a public `scheduler.trigger_immediate_check()` helper that runs a single
schedule evaluation pass synchronously. `delete_category` now calls it after committing
the deletion so the winner is recomputed before the response returns. Failures are
logged but do not bubble up — the next normal tick will catch up.

This pattern can be reused for any future endpoint that invalidates the applied-state
(schedule edits that change `category_id` or `sequence`, exclusive toggles, blend
toggles). Tracked as a follow-up under cross-cutting findings.

#### SCHEDULER-6: Plex apply failure suppresses dashboard state update
**Severity:** BUG · **Status:** FIXED in this audit pass

Three places in the scheduler's apply path (sequence-only, category, and the
already-active re-apply branch introduced by SCHEDULER-1) only updated
`setting.active_category` / `setting.active_schedule_id` / `last_run` if Plex apply
returned `True`. So **any failure in Plex apply blocked dashboard sync**, including:

- Empty category (no prerolls) — `_apply_category_to_plex` returns False at line 2100
- Plex unreachable / token invalid
- File paths broken (e.g. after migration before Rescan)
- Sequence with invalid block types

User reproduction during testing:
1. Created `1135 Test` as an exclusive schedule targeting an empty category (Easter, id=8)
2. Disabled the prior winning schedules
3. Scheduler correctly logged `EXCLUSIVE: '1135 Test' wins... -> Category 8`
4. `_apply_category_to_plex(8)` returned False (no prerolls in Easter)
5. State never updated → dashboard kept saying "no category applied"
6. Every subsequent tick repeated the same failure

The v1.12.18 toggle-handler fix established that state should reflect **intent** (which
schedule is the winner), not Plex apply result, because users without Plex configured
(Emby/Jellyfin-only) and users with empty categories should still see what's "active."
The scheduler itself never got the same treatment until now.

**Fix:** All three apply branches now update `setting.*` and `chosen_schedule.last_run`
unconditionally on winner selection. Plex apply failures are logged as warnings but no
longer block the dashboard. `_verify_and_reapply_if_needed` (5-minute periodic verifier)
already retries Plex sync, so the cost of "marking active even if Plex failed" is just
that the next verify pass will try again — which is what we want.

#### SCHEDULER-7: Scheduler tile countdown label flips confused users
**Severity:** UX · **Status:** FIXED

User-reported during testing: "the scheduler tile just finished a countdown for the
1135 Test schedule and when it finished it didn't apply, instead just started the
timer for 1 hour 40 mins."

Root cause: the dashboard's Scheduler tile shows the countdown to the NEXT activation
across all enabled, in-window schedules. When a schedule's window opens, the tile's
`getNextActivation` returns `null` for it (it's now currently active), so the
displayed "Next Up" jumps to the schedule with the next-soonest activation. Both
the label and the time update in the same React render — so a user watching the
countdown sees, at the transition, "label X with 1s left" → "label Y with 1h 40min."
That LOOKS like X's countdown reset without firing.

What actually happened: schedule X DID activate (its window opened), schedule Y is
the new "next up." The countdown didn't fail — it correctly switched targets.

**Fix (UX clarity):**
1. Added a "Now: <active schedule name>" line above the countdown, sourced from
   `activeCategory.active_schedule_name`. The user sees what's actually playing.
2. Added an explicit target-time stamp next to the "Next:" label
   (e.g. "Next: 1135 Test @ May 26, 08:26"). When the target flips, the timestamp
   visibly changes too — no ambiguity.
3. Renamed "Next Up:" to "Next:" for brevity now that the timestamp is on the same line.

The countdown logic itself was correct; this was a display ambiguity.

#### SCHEDULER-2: Apply-branch elif chain is hard to follow
**Severity:** DOC · **Status:** DEFERRED (no behavior change; revisit during v2.0.0 cleanup)

[`scheduler.py` lines 1564–1672](NeXroll/backend/scheduler.py#L1564-L1672) is a four-way
elif chain (sequence-only / category-changed / no-target / category-unchanged) without a
clear hierarchy. Easier to reason about as a single decision tree once the SCHEDULER-1 fix
is in. Deferred to a future pass to avoid behavior risk in the same release as a fix.

#### SCHEDULER-4: Frontend treats `sequence: "null"` as a real sequence ("0 blocks" badge regression)
**Severity:** DISCONNECT · **Status:** FIXED in this audit pass

`handleToggleSchedule` ([App.js:1774 pre-fix](NeXroll/frontend/src/App.js#L1774)) used to do
`typeof schedule.sequence === 'object' ? JSON.stringify(schedule.sequence) : (schedule.sequence || '')`
to normalize the sequence before PUT. `typeof null === 'object'` in JavaScript, so when a
simple (non-sequence) schedule had its `sequence` set to `null` in React state, the toggle
PUT sent the literal string `"null"` (4 chars) as the sequence. The backend stored it.

On the next render, the schedule-card badge ran:
```js
const hasSequence = schedule.sequence && schedule.sequence.trim();  // "null" is truthy
const scheduleMode = hasSequence ? 'sequence' : 'simple';            // → 'sequence'
sequenceBlockCount = Array.isArray(JSON.parse(...)) ? ... : 0;       // → 0
```

Result: a simple schedule that was just toggled now displays as `Sequence (0 blocks)`. This
is the user-reported "badge changes to 0 blocks after disable/enable" symptom.

Backend's `_has_valid_sequence` ([scheduler.py:74](NeXroll/backend/scheduler.py#L74)) correctly
rejects `"null"`, `"[]"`, etc., so scheduler behavior was unaffected — purely a UI regression.

**Fix (two parts):**
1. Toggle handler now explicitly handles `null`/`undefined` → empty string, only stringifies
   real objects.
2. The schedule-card "blocks" badge derives `hasSequence` from the parsed block count, not
   from the raw string truthiness. Mirrors the backend's `_has_valid_sequence` semantics.

#### SCHEDULER-5: No visible indication of why a particular schedule is the winner
**Severity:** UX · **Status:** OPEN (deferred — needs frontend work that's bigger than a fix)

The user's "1133 Test 1/2" schedules and the existing "Christmas Schedule" all targeted
the same category with equal priority. Christmas won because the winner-selection sort key
([scheduler.py:1420-1424](NeXroll/backend/scheduler.py#L1420-L1424)) is
`(-priority, end_date, start_date, id)` and Christmas had a defined end_date (2027-12-31)
while the 1133 tests had `end_date = null` (treated as `datetime.max`).

This is by-design but **invisible to users**. Symptoms:
- Users create test schedules to validate a fix and the test schedules silently never
  become the winner because some older schedule outranks them on a non-obvious tiebreaker.
- No tooltip / dashboard hint surfaces the reasoning.

Proposed v2.0.0 fix: on the Schedules page, show a "winner" badge on whichever schedule
is currently applied (we already know this — `setting.active_schedule_id`). On hover or
in a side panel, show the schedule that came second and what tiebreaker decided. Also
consider whether the "earliest end date wins" rule is actually what users expect — that
might be the wrong default.

### 2. Categories & Prerolls (m2m, `category_id` legacy column)
*Status: completed*

#### CATEGORIES-7: Primary-category UI leftovers — picker star, "Set as Primary" checkbox, bulk primary change
**Severity:** BUG (user-facing inconsistency) · **Status:** FIXED · **Resolves user complaint 2026-05-25**

The v1.13.0 work retired the user-visible primary-category concept in the *Categories
page* (deleting categories no longer requires a primary-reassignment workaround,
"Remove from Category" works for any category, etc.), but four primary-flavored UI
surfaces remained:

1. **CategoryPicker component** ([App.js:211](NeXroll/frontend/src/App.js#L211)) used
   in upload and preroll-edit modals. Rendered a special "Primary" chip with a star,
   plus a "No primary" placeholder, plus a "Make primary" star button on every
   dropdown item. Visually pushed users to designate one category as primary.
2. **"Set as Primary (moves files)" checkbox** in the Add-Prerolls-to-Category
   picker — would move the file on disk to that category's folder.
3. **Bulk "Apply to N Selected" button** in the Prerolls page bulk actions — wired
   to `handleBulkSetPrimary` which moved files on disk via `PUT /prerolls/{id}`.
4. **`handleCategoryAddPreroll`** sent `?set_primary=true|false` to the backend.

**Fix:**
1. `CategoryPicker` flattened: no Primary chip, no Star button on dropdown items.
   All selected categories render as identical chips with × to remove. The component
   still accepts `primaryId` + `secondaryIds` and emits `onChange(primary, secondary)`
   for backend-storage compatibility (the first selected becomes the legacy primary),
   but the user never sees that split.
2. "Set as Primary (moves files)" checkbox removed entirely. Layout reflows.
3. Bulk "Apply to N Selected" rewired to call `POST /categories/{id}/prerolls/{id}` —
   tags via m2m, does NOT move files. Confirm dialog text updated to clarify.
4. `handleCategoryAddPreroll` no longer sends `set_primary` query param.

The backend `POST /categories/{id}/prerolls/{id}` endpoint still accepts
`set_primary` for backward compat with any external integrators, but the NeXroll
UI never sets it.

Background: the v1.13.0 startup migration backfills the `preroll_categories` m2m
table from the legacy `Preroll.category_id` column without nulling the column.
Every preroll's primary category therefore appears in BOTH places after migration,
which means any query that filters by `category_id == X` AND adds the m2m count is
double-counting. And any query that uses ONLY `category_id == X` misses prerolls
that were tagged with X as a secondary.

Most query sites already use the safe `or_(category_id == X, m2m has X)` pattern.
The remaining pure-`category_id` filter sites were audited individually.

#### CATEGORIES-1: Diagnostics category stats double-count after migration
**Severity:** BUG · **Status:** FIXED

[`main.py:25650` (pre-fix)](NeXroll/backend/main.py#L25650) computed
`total_in_cat = primary_count + m2m_count` where `primary_count` was a `category_id == cat.id`
count and `m2m_count` was a `preroll_categories` count. After the v1.13.0 migration,
every preroll appears in both — so the displayed "preroll count" for each category was
roughly 2x the real count. Replaced with a single `or_(category_id == X, m2m has X).distinct()`
query that mirrors what `GET /categories/{id}/prerolls` already returns.

#### CATEGORIES-2 & CATEGORIES-3: Sequence export bundle misses m2m-tagged prerolls
**Severity:** BUG · **Status:** FIXED

Two locations in the sequence bundle export ([main.py:11625](NeXroll/backend/main.py#L11625)
for `with_preroll_data` / `full_bundle` mode metadata, [main.py:11769](NeXroll/backend/main.py#L11769)
for the random-block category-folder export) filtered preroll lists by `category_id == X`
only. If a user tagged a preroll with the random block's category as a SECONDARY (not
primary) tag, the export bundle would NOT include it — even though the live scheduler
WOULD include it when resolving the block (`_apply_schedule_sequence_to_plex` uses the
safe `or_()` form). The result: an exported community sequence would silently lose
m2m-tagged prerolls, and the receiving NeXroll would render the bundle differently
than the source.

Both converted to `or_(category_id == X, m2m has X).distinct()`.

#### CATEGORIES-4: Sequence import duplicate check uses only legacy category_id
**Severity:** UX (minor) · **Status:** OPEN (deferred)

[`main.py:10548`](NeXroll/backend/main.py#L10548) checks "does this preroll already
exist in the target category?" using `category_id == X` only. A preroll tagged with
the target category solely via m2m (no primary) would not be found, and the import
would add a duplicate file. Low likelihood in practice (newly imported sequences
generally land in newly created categories) and changing dedupe behavior carries
its own risk of suppressing legitimate adds. Deferred.

#### CATEGORIES-5: NeX-Up trailer counts intentionally legacy-primary-only
**Severity:** DOC · **Status:** ACKNOWLEDGED, no change

[`main.py:20536`, `20540`](NeXroll/backend/main.py#L20536) and the diagnostics
counts at [`main.py:25736`, `25738`](NeXroll/backend/main.py#L25736) count prerolls
in the dedicated NeX-Up movie/TV trailer categories. Unlike user-managed categories,
these counts intentionally answer "how many trailers does NeX-Up manage?" — a primary-
category concept, not a "what's tagged here" question. Using `or_()` would inflate
the count if the user manually m2m-tagged an unrelated preroll into the NeX-Up
category. Leaving as `category_id == X` is correct.

#### CATEGORIES-6: Frontend `filteredPrerolls` filter combines legacy + m2m correctly
**Severity:** ACKNOWLEDGED — already correct

[`App.js:4955`](NeXroll/frontend/src/App.js#L4955) checks both `p.category_id === catId`
and `p.categories.some(c => c.id === catId)`. Correct. No change.

### 3. Dashboard / "Currently Showing" State Sync (`get_active_category`, frontend tile)
*Status: in progress*

#### DASHBOARD-1 / MAIN-1: `_apply_schedule_win_lose_logic` is a 410-line parallel reimplementation of the scheduler
**Severity:** DISCONNECT (large) · **Status:** FIXED at call site; dead function flagged for removal

`main.py` defines `_apply_schedule_win_lose_logic` at line 9305 — a ~410-line function
that reimplements:
- `_is_schedule_active` (schedule window + recurrence pattern + time range checks)
- `_apply_schedule_to_plex` (sequence handling for fixed / random / nexup_trailers /
  coming_soon_list / dynamic_preroll blocks; or category pool apply)
- Winner selection (same sort key as scheduler: `(-priority, end_date, start_date, id)`)
- Blend mode detection on remaining schedules
- `_apply_filler_to_plex` (full filler handling)
- `clear_when_inactive` handling

This is functionally a second copy of `scheduler._check_and_execute_schedules`. It was
called from `PUT /schedules/{id}` to give immediate feedback without waiting for the
scheduler's 60-second loop. It is the source of subtle divergence bugs: any fix made
to the scheduler doesn't propagate here, and vice-versa.

**Fix:** the `PUT /schedules/{id}` call site now uses `scheduler.trigger_immediate_check()`
(introduced in v1.13.3 for `delete_category`) which runs one full scheduler pass
synchronously. Functionally equivalent, one source of truth. The dead function is left
in place for this release — deleting 410 lines mid-audit is too aggressive a change
to bundle with the call-site swap. Marked for removal in the cross-cutting pass.

#### DASHBOARD-2: Schedule create/delete had no immediate scheduler re-evaluation
**Severity:** BUG · **Status:** FIXED

`POST /schedules` and `DELETE /schedules/{id}` both committed their changes without
poking the scheduler. Creating a new schedule that should win immediately, or deleting
the schedule currently being applied, left a 60-second window where the dashboard and
Plex disagreed with the database. Now both call `scheduler.trigger_immediate_check()`
after commit (mirroring `delete_category` from v1.13.3).

#### DASHBOARD-3: Filler disable transition does not poke the scheduler
**Severity:** UX (minor) · **Status:** OPEN (deferred — minor case)

`PUT /settings/filler` calls `scheduler.apply_filler_now()` only when filler is being
enabled. When filler is being disabled, nothing pokes the scheduler — the dashboard
keeps showing the filler state until the next 60-second tick. Could be addressed by
also calling `trigger_immediate_check()` on the disable path. Deferred — minor gap.

### 4. Preview / Playback (file serving, path handling)
*Status: pending*

### 4. Preview / Playback (file serving, path handling)
*Status: completed*

#### PREVIEW-1: Preview URL built from `category.name` 404s for uncategorized prerolls
**Severity:** BUG · **Status:** FIXED · **Resolves:** BUG-FEEDBACK-4

The frontend "Preview" modal at [App.js:33904 (pre-fix)](NeXroll/frontend/src/App.js#L33904)
constructed the video URL as:
```js
`static/prerolls/${encodeURIComponent(previewingPreroll.category?.name || 'unknown')}/${encodeURIComponent(previewingPreroll.filename)}`
```

When the preroll had no category (legitimate post-v1.13.0 state — categories can be
deleted, prerolls become uncategorized), `category?.name` was undefined and the URL
became `static/prerolls/unknown/{filename}`. There is no `unknown` directory on disk,
the legacy backend lookup at [main.py:14918 (pre-fix)](NeXroll/backend/main.py#L14918)
used a pure `category_id == cat_obj.id` filter (no m2m), and the request 404'd.

Same bug appeared in the dashboard "Currently Showing" preview at
[main.py:12921 (pre-fix)](NeXroll/backend/main.py#L12921) which built
`preview_url` the same way.

**Fix:**
1. New backend endpoint `GET /prerolls/{id}/video` looks up the preroll by ID and
   streams its stored `path` directly. No dependency on category folder structure.
   Works for uncategorized prerolls, post-migration paths, and external/unmanaged
   prerolls.
2. Frontend simple-preview modal switched to `prerolls/{id}/video`.
3. Backend `currentPrerollPreview` `preview_url` switched to `/prerolls/{id}/video`.
   Also updated to derive `category_name` from m2m relationship instead of legacy
   `category_id` only.
4. The legacy `/static/prerolls/{category}/{filename}` endpoint still exists for
   backward compat with old thumbnail/preview URLs; its DB fallback now uses m2m
   (`or_(category_id == X, categories.any(Category.id == X))`) and filename-unique
   fallback so it does the right thing when called with a category that doesn't
   match the preroll's primary. Noisy debug `print()` statements removed.

#### PREVIEW-2: Noisy `console.log` and `print` statements in preview paths
**Severity:** DOC · **Status:** FIXED (cleaned up while fixing PREVIEW-1)

#### PREVIEW-3: Dashboard "Currently Showing" preview shows stale Plex state, not NeXroll intent
**Severity:** BUG · **Status:** FIXED

Surfaced during testing of PREVIEW-1: clicking the dashboard preview button when
the active schedule was "Adult Swim Night" (category: Adult Swim) returned a Toy
Story file from a completely different category, with "Preview unavailable" because
the file path (`/data/prerolls/Toy Story_JFLX.mp4`) didn't exist on the local
Windows install.

Root cause: the endpoint `GET /plex/current-preroll-details` always queried Plex
for the currently-applied preroll string, then tried to match each path against the
local DB and disk. If Plex had stale paths from a previous install (e.g. a Docker
container's `/data/prerolls/...` paths leftover after switching to a Windows install,
or a path NeXroll's scheduler hasn't successfully overwritten yet because Plex apply
failed — see SCHEDULER-6), the preview would render whatever Plex was holding instead
of what NeXroll actually thinks is active.

The user's mental model: "click preview on the active schedule's tile → see what
that schedule plays." Plex's stored string isn't the right source of truth here;
NeXroll's own active_schedule_id is.

**Fix:** new helper `_preview_payload_from_intent(setting, db)` resolves the preview
list from `setting.active_schedule_id` (or `setting.active_category` if no schedule
ID is recorded) — for sequence schedules it walks the blocks (fixed/random), for
category schedules it returns the category's prerolls via m2m + legacy category_id.
`/plex/current-preroll-details` now calls this first; only falls back to querying
Plex when NeXroll has no recorded active schedule (e.g. filler mode, manual Plex
preroll, fresh install with no schedules yet). Mode is derived from the schedule
shape / category's `plex_mode`.

### 5. Import & Filesystem Scanner (`map_preroll_root`, `scanner.py`)
*Status: completed (folder-picker UX added)*

#### IMPORT-1: Add-prerolls-to-category picker was a flat "sea of thumbnails"
**Severity:** UX · **Status:** FIXED · **Resolves:** UX-FEEDBACK-1

User feedback from the friend's testing: *"when choosing which prerolls to add it's just
a big list of thumbnails, whereas if it used my windows folder structure i could just
add the 'holiday' folder. ... It's just a sea of thumbnails it seems."*

The Add-Prerolls-to-Category picker had a single search input and a flat grid of all
available preroll thumbnails. With a large library, picking individual items took time
and there was no way to grab everything from a specific source folder at once.

**Fix:** added two new affordances to the picker:
1. **Folder filter dropdown** — derives the parent folder from each preroll's stored
   `path` on the fly and lists each unique folder with its item count
   (`Christmas (24)`, `Halloween (12)`, etc.). Picking a folder narrows the grid to
   that folder's items. "All folders (N)" remains the default.
2. **"Select All (N)" button** — selects every preroll currently matching the active
   filter (folder + search). Toggles to "Deselect All" once everything visible is
   selected. The user can pick the "Holiday" folder and one click grabs all of it.

Each thumbnail's secondary line now shows the source folder instead of the legacy
"category" name. The thumbnail click → select behavior is unchanged.

Implemented entirely client-side using existing preroll path data — no new backend
endpoint, no schema change.

### 6. NeX-Up Subsystem (Radarr/Sonarr trailer integration, Coming Soon Lists, Dynamic Prerolls)
*Status: in progress*

#### NEXUP-1: Trailer toggle silently failed to disable the linked Preroll record
**Severity:** BUG · **Status:** FIXED

Both the movie trailer toggle ([main.py:18788 (pre-fix)](NeXroll/backend/main.py#L18788))
and the TV trailer toggle ([main.py:17022 (pre-fix)](NeXroll/backend/main.py#L17022))
contained the line:

```python
preroll.enabled = trailer.is_enabled
```

But **`Preroll` had no `enabled` column** — see [models.py:15-32 (pre-fix)](NeXroll/backend/models.py#L15).
SQLAlchemy silently accepts assignment to an undeclared attribute as a transient
instance attribute that never persists to the database. The toggle UI looked like it
was syncing the Preroll's enable state with the trailer's, but the Preroll record was
never actually changed.

Consequence: disabling a trailer correctly excluded it from `nexup_trailers`-typed
sequence blocks (which filter via `ComingSoonTrailer.is_enabled == True`), but did
NOT exclude it from:
- `random`-type sequence blocks whose category covers the NeX-Up category
- A schedule whose `category_id` is the NeX-Up category
- The `_apply_category_to_plex` path

So a "disabled" trailer would still play when sent to Plex via any non-`nexup_trailers`
path. The dead code at the toggle endpoints made the bug invisible to anyone reading
the code — it looked correct.

**Fix:**
1. Added `enabled = Column(Boolean, default=True)` to the `Preroll` model.
2. Added a startup migration `_sqlite_add_column("prerolls", "enabled BOOLEAN DEFAULT 1")`
   so existing DBs get the column with all rows defaulted to enabled.
3. Updated five scheduler preroll-pool builders to filter
   `or_(Preroll.enabled == True, Preroll.enabled.is_(None))`:
   - `_apply_jellyfin_category`
   - `_apply_category_to_plex` (main)
   - `_apply_schedule_sequence_to_plex` random block helper
   - `_apply_blended_schedules_to_plex` random block helper
   - `_apply_saved_sequence_to_plex` filler random block helper
4. The existing trailer toggle code now actually persists the field.

The legacy `Preroll.path == trailer.local_path` lookup used by the toggles is still
fragile (case sensitivity, separator differences, normalization) — flagged as
NEXUP-2 below.

#### NEXUP-2: Trailer-to-Preroll linkage uses exact-string path match
**Severity:** UX (minor) · **Status:** OPEN (deferred — needs path normalization helper)

Several NeX-Up endpoints look up the linked Preroll record by
`Preroll.path == trailer.local_path` ([main.py:18746, 18784, 17018](NeXroll/backend/main.py#L18746)).
Any path normalization drift (case on Windows, mixed separators, trailing slash)
would cause the lookup to silently miss. The v1.12.21 scanner can rewrite Preroll
paths to canonical absolute form on rescan, but trailer rows don't get the same
treatment, so they can drift apart. Flagged for cross-cutting cleanup — needs a
small `_paths_equal(a, b)` helper used everywhere.

#### NEXUP-3: Sync race protection relies on a global module variable
**Severity:** ACKNOWLEDGED — fine for single-process FastAPI · **Status:** no change

Both `/nexup/sync` (Radarr) and `/nexup/sonarr/sync` use a module-level
`_nexup_sync_progress` dict with a `syncing` flag for in-progress detection. This
is a TOCTOU pattern (check-then-set) but is safe enough for the single-process
uvicorn deploy NeXroll ships with. A multi-worker deployment would need a real lock.
Documented for awareness; no fix needed under current deployment model. v1.12.15-16
added a startup deduplication pass that catches anything that slips through.

### 7. Sequencing Subsystem (Sequence Builder, Saved Sequences, sequence apply paths)
*Status: in progress*

#### SEQUENCING-1: Manual sequence-apply ignores enabled=False prerolls
**Severity:** BUG · **Status:** FIXED

[`apply_sequence_to_server`](NeXroll/backend/main.py) at `POST /sequences/{id}/apply`
has its own `_prerolls_for_category` helper for random-block resolution, distinct from
the scheduler's. After the NEXUP-1 fix added `enabled` filtering to the scheduler's
five preroll-pool builders, this manual-apply helper was the lone remaining path that
**still picked disabled prerolls**. So a user who toggled a NeX-Up trailer off and
then clicked "Apply Sequence" on a sequence containing a random block over the NeX-Up
category would still get the disabled trailer in the applied set.

**Fix:** added the same `or_(Preroll.enabled == True, Preroll.enabled.is_(None))` filter.

#### SEQUENCING-2: Deleting a saved sequence left dangling references
**Severity:** BUG · **Status:** FIXED

[`delete_saved_sequence`](NeXroll/backend/main.py) just deleted the row, didn't check
whether any settings still referenced it:

- `Setting.filler_sequence_id` could point at the deleted ID, and if `filler_type` was
  `"sequence"`, the filler would silently fail at apply time (sequence not found).
- `Setting.applied_sequence_id` could point at the deleted ID, leaving the dashboard's
  "applied sequence" tile showing the deleted name until `override_expires_at` elapsed
  (up to 15 minutes), or until manually overridden.

**Fix:** delete now clears both references, disables filler if it was the sole sequence
underpinning a `sequence`-type filler, and triggers `scheduler.trigger_immediate_check()`
so the dashboard re-syncs immediately. Response includes the cleanup flags
(`cleared_filler`, `cleared_applied_override`) for UI feedback.

#### SEQUENCING-3: Sequence editing while a schedule is using it
**Severity:** ACKNOWLEDGED — not a bug, documented for awareness

`PUT /sequences/{id}` just updates the row. The scheduler caches schedule sequence
data inline (each Schedule has its own `sequence` JSON column), and SavedSequence is
only used as a "filler sequence" reference and as the source of truth for the Sequence
Builder. So editing a saved sequence doesn't affect schedules that have already had
their sequence baked in. This is by design — schedules embed sequences at save time.
If users find this confusing, the future v2.0.0 refactor could move to referencing
SavedSequence by ID from schedules instead of inlining the JSON.

#### SEQUENCING-4: Preview playlist consistency
**Severity:** DOC · **Status:** ACKNOWLEDGED — fixed in v1.12.14 per CHANGELOG

CHANGELOG records a v1.12.14 fix where "Sequence Preview: Now Playing Label Desyncs"
— preview playlist was rebuilt every 30s on background poll, re-shuffling random
picks mid-playback. Fix snapshotted props at modal-open. Verified the fix is still
in place — no regression to add.

## Cross-Cutting

### MAIN-1: Dead function `_apply_schedule_win_lose_logic` (~410 lines)
**Severity:** DEAD · **Status:** FIXED

Deleted at the end of the audit. After DASHBOARD-1 (v1.13.5) rerouted the call site
to `scheduler.trigger_immediate_check()`, the function had zero callers but remained
in `main.py` as a future trap. Removed entirely (~410 lines). The stale comment in
`update_schedule` referencing the dead function was also rewritten.

### CROSS-1: Consolidated three+ parallel `_prerolls_for_category` helpers
**Severity:** DISCONNECT (architectural) · **Status:** FIXED

The audit's most architecturally dangerous finding. Seven separate places in the
codebase implemented "build the preroll pool for a category" with the same m2m
union pattern. When the v1.13.10 NeX-Up `enabled` filter needed to be added, it
had to be applied to **each one independently** — and the manual sequence-apply
helper (SEQUENCING-1, v1.13.11) and the Jellyfin/Emby plugin resolver (PLUGIN-2,
v1.13.14) were each fixed only AFTER user testing surfaced the regression. This
is the textbook drift problem.

**Fix:** added `prerolls_for_category_query(db, category_id)` at module scope in
`backend/scheduler.py`. Returns a SQLAlchemy Query (chainable; callers do `.all()`).
Single source of truth for the m2m-union + enabled-filter + distinct logic.

Replaced 7 call sites:
- `scheduler.py`: `_apply_jellyfin_category`, `_apply_category_to_plex`,
  `_apply_schedule_sequence_to_plex` random helper, `_apply_blended_schedules_to_plex`
  helper, `_apply_saved_sequence_to_plex` filler helper (5 sites)
- `main.py`: `apply_sequence_to_server`, `_resolve_current_intros` (2 sites)

Future fixes/extensions land in one place. If we ever need to add a new filter
(e.g. skip prerolls with missing files, or honor a per-preroll TTL), it's a
one-line change instead of seven.

### CROSS-2: Path-equality helper for trailer↔preroll linkage
**Severity:** UX (NEXUP-2) · **Status:** FIXED

Added `_paths_equal(a, b)` and `_find_preroll_for_trailer(db, path)` to `main.py`.
The latter tries an exact DB match first (fast path), then falls back to a
filename-keyed lookup with `_paths_equal` normalization (case + separator).
Applied to the four user-facing trailer linkage sites: movie/TV trailer delete
and movie/TV trailer toggle. Sync paths still use exact match because they
write the paths in the same process that reads them — no drift risk there.

### CROSS-3: `Setting.get_json_value`/`set_json_value` generic store remains
**Severity:** ACKNOWLEDGED · **Status:** no change

The generic `/settings/{key}` route uses a JSON-encoded value column on the
Setting model. No frontend consumer; could be useful for future integrations.
Left as-is. Specific routes correctly take precedence in the routing table.

### 6. Backup / Restore (`backup_database`, `restore_database`, `restore_files`)
*Status: completed*

#### BACKUP-1: JSON backup payload was missing most model fields
**Severity:** BUG (silent data loss) · **Status:** FIXED

The `GET /backup/database` export emitted a stripped-down subset of each table's
columns; `POST /restore/database` symmetrically read the same subset. A backup/restore
round-trip therefore **silently dropped**:

- **Categories:** `plex_mode` (shuffle/playlist), `apply_to_plex`, `is_system` —
  restoring lost the playback-mode setting AND the protection flag on NeX-Up
  system categories (so they could become user-deletable post-restore).
- **Prerolls:** `duration`, `file_size`, `enabled` (added in v1.13.10!),
  `community_preroll_id` (community-match link), `exclude_from_matching`,
  `file_hash`. The `enabled` regression was the worst — toggling a NeX-Up trailer
  off, taking a backup, restoring, would silently re-enable the trailer.
- **Schedules:** `fallback_category_id`, `sequence`, `color`, `blend_enabled`,
  `priority`, `exclusive`, `holiday_name`, `holiday_country`. Sequence schedules
  came back as plain category schedules; blend/exclusive/priority all reverted to
  defaults; holiday-API auto-update bindings (holiday_name/country) were lost.
- **Holiday presets:** `start_month` / `start_day` / `end_month` / `end_day`
  (date-range fields used by multi-day holidays), `is_recurring`. Date-range
  holidays collapsed to a single point.

**Fix:** export now emits every field the model defines; restore reads every field
defensively (`get(...)` with sensible defaults so older-payload backups still
restore). Added `schema_version: 2` to the export payload for future migrations.
Also added `exported_by_version` for diagnostic purposes.

#### BACKUP-2: Schedule.preroll_ids stores stale IDs after restore
**Severity:** ACKNOWLEDGED — open question · **Status:** OPEN (flagged for v2.0.0)

`Schedule.preroll_ids` is a comma-separated string of preroll IDs (used by some
legacy schedule types). Backup includes the string verbatim, but restore re-issues
new preroll IDs, so the references in the restored Schedule are stale. Few schedules
use this field today — most use the inline `sequence` JSON instead — but it's a real
data-fidelity gap. Fixing it would require either a preroll-ID remap pass during
restore (similar to the category-ID remap that already exists) or moving to
filename-based references at backup time. Flagged for v2.0.0.

#### BACKUP-3: File-bundle backup is unaudited
**Severity:** ACKNOWLEDGED · **Status:** OPEN (separate audit)

`POST /backup/files` and `POST /restore/files` produce/consume a ZIP that bundles
the SQLite DB plus the preroll files. The audit covered only the JSON export path
that the user-facing "Download Database Backup" button creates. The ZIP path is
used less frequently and uses its own serialization (SQLite file copy + tar of
prerolls). Deferred for a future pass — same pattern of "make sure every column
makes it through."

### 7. Plex / Jellyfin / Emby Plugin Endpoints (`_resolve_current_intros`, etc.)
*Status: completed*

#### PLUGIN-1: `/plugin/intros` allows unauthenticated access
**Severity:** ACKNOWLEDGED — intentional · **Status:** no change

The `/plugin/intros` endpoint accepts an optional `X-Api-Key`; missing/empty key
returns the active preroll list anyway. This is **by design** for backward
compatibility with plugins from before the API key system existed. Anyone on the
LAN could enumerate the active preroll paths and (via the time-limited HMAC-signed
`/plugin/stream` URLs) stream them. Low sensitivity content; acceptable.

#### PLUGIN-2: `_resolve_current_intros` did not filter by `Preroll.enabled`
**Severity:** BUG · **Status:** FIXED

The Jellyfin/Emby plugin path resolves prerolls through `_resolve_current_intros`
which has its own `_prerolls_for_category` helper, distinct from the scheduler's
five copies fixed in NEXUP-1 (v1.13.10) and the manual sequence-apply helper
fixed in SEQUENCING-1 (v1.13.11). This was the third parallel implementation,
and it was still picking disabled prerolls. Disabling a NeX-Up trailer correctly
removed it from Plex playback but **the trailer would still play through
Jellyfin/Emby**. Same `or_(enabled == True, enabled.is_(None))` filter added.

#### PLUGIN-3: Plex webhook signature verification is optional
**Severity:** ACKNOWLEDGED — documented trade-off · **Status:** no change

The `/plex/webhook` endpoint verifies an HMAC signature only when
`NEXROLL_PLEX_WEBHOOK_SECRET` env var is set. Without it, anyone who can reach
NeXroll could forge webhook events. The webhook only triggers genre-mapping
preroll application (a transient action with TTL), so the impact is bounded.
Documented in the code; users can opt into stricter verification by setting
the env var. Acceptable as-is.

### 8. Settings & Config Flow
*Status: completed*

#### SETTINGS-1: Duplicate `/settings/dashboard-tile-order` registration (dead code)
**Severity:** DEAD · **Status:** FIXED

`/settings/dashboard-tile-order` was registered **twice** — at
[main.py:15863/15880](NeXroll/backend/main.py#L15863) and again at
[main.py:15919/15935 (pre-fix)](NeXroll/backend/main.py#L15919). The two pairs
returned different response shapes (`{dashboard_tile_order: ...}` vs
`{tile_order: ...}` / `{saved: true, tile_order: ...}`). FastAPI's routing uses
first-match, so the later registrations were unreachable dead code with the
potential to mislead future readers. Removed the duplicates.

The frontend doesn't currently call this endpoint either way; the cleanup is
purely a maintenance win.

#### SETTINGS-2: Filler disable transition didn't poke the scheduler
**Severity:** UX · **Status:** FIXED · **Resolves DASHBOARD-3**

`PUT /settings/filler` called `scheduler.apply_filler_now()` only when filler
was being enabled. When filler was being disabled, the response returned but
the scheduler wasn't notified — so the dashboard tile kept showing filler state
for up to 60 seconds until the next normal tick caught up. Now also calls
`scheduler.trigger_immediate_check()` on the disable path.

#### SETTINGS-3: Generic `/settings/{key}` JSON store
**Severity:** ACKNOWLEDGED — no current consumer · **Status:** no change

Generic `GET/PUT /settings/{key}` route uses `Setting.get_json_value(key)` /
`set_json_value(key, value)` for a key-value JSON store. No current frontend
consumer; appears to be anticipated for future use. Specific routes (e.g.
`/settings/dashboard-layout`) are registered first so they win over the
catch-all. Acceptable.

### 9. Auth / Sessions
*Status: completed*

#### AUTH-1: Login flow review
**Severity:** ACKNOWLEDGED — solid · **Status:** no change needed

Reviewed `POST /auth/login`, `_validate_session`, `require_auth`,
`get_current_user_optional`:

- ✓ Username comparison normalizes lowercase
- ✓ Password verification via secure hash compare
- ✓ IP-based rate limiting prevents credential spraying across accounts
- ✓ Account lockout after 5 failed attempts (15-minute lockout)
- ✓ Session token: random raw token sent in cookie, SHA-256 hash stored in DB
- ✓ Cookie flags: `httponly`, `samesite=lax`, `secure` gated on `auth_require_https`
- ✓ Periodic cleanup (1-in-50) of expired sessions on validate
- ✓ Audit-log entries for login_success / login_failed / account_locked / logout
- ✓ `require_auth` returns None when auth is disabled (and endpoints that consume
  the dependency check `is_active` redundantly via the user object when present)

`samesite="lax"` is the right choice for an admin web app (allows top-level nav
cookies; blocks third-party POST CSRF). `samesite="strict"` would break legitimate
external-link navigation. Acceptable.

No bugs found in this subsystem.

### 10. Cross-Cutting (error handling, naming, dead code)
*Status: pending*
