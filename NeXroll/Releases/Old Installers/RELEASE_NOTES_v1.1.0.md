# NeXroll v1.1.0 Release Notes

Date: 2025-09-23

This release focuses on usability improvements to the Dashboard prerolls section, bulk operations, and packaging/version alignment.

Highlights
- Dashboard prerolls pagination with default 20 per page. Users can switch to 20/30/40/50 per page. Selection persists across pages.
- Multi-select prerolls on Dashboard with bulk primary category move.
- Storage usage card in top cards showing total size of all prerolls on disk.
- Version alignment across backend API, installer, service worker caches, and binary metadata to v1.1.0.

UX details
- Page size is persisted in localStorage (key: prerollPageSize).
- Filters reset the current page to 1 to keep results obvious.
- Select-all-on-page checkbox allows quick selection of currently visible prerolls; selection can span pages.

Backend/API
- No new endpoints required. Bulk operations use existing PUT /prerolls/{id} to set category_id for each selected preroll.
- API version reported by FastAPI is now v1.1.0 via application initialization.

Changed files
- [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js:1) — pagination (default 20, up to 50), multi-select with bulk primary category move, storage usage card, UI additions.
- [NeXroll/nexroll_backend/main.py](NeXroll/nexroll_backend/main.py:468) — FastAPI app version bumped to 1.1.0.
- [NeXroll/version_info.txt](NeXroll/version_info.txt:1) — binary metadata updated to 1.1.0.0.
- [NeXroll/installer.nsi](NeXroll/installer.nsi:25) — APP_VERSION and VIProductVersion updated to 1.1.0/1.1.0.0. Outfile produces NeXroll_Installer_1.1.0.exe.
- [NeXroll/frontend/public/sw.js](NeXroll/frontend/public/sw.js:2) — service worker cache keys bumped to nexroll-v1.1.0.

Upgrade/build notes
- Frontend (dev): from NeXroll/frontend run "npm start" to test, or "npm run build" to produce static assets. Clear old PWA cache if needed; the new cache names auto-invalidate prior caches.
- Backend (dev): run the API and open http://localhost:9393 to verify.
- Packaging (Windows):
  1) Build app executables (from NeXroll directory): "pyinstaller neXroll.spec"
  2) Optionally build service/tray: "pyinstaller NeXrollService.spec" and "pyinstaller NeXrollTray.spec"
  3) Build installer: "makensis installer.nsi"
- Installer writes HKLM\Software\NeXroll\Version = 1.1.0 and supports choosing a prerolls storage path.

Compatibility considerations
- Bulk operation sends sequential PUTs; for very large selections it may take time. UI shows completion via alert when done.
- Existing thumbnails and data directories remain unchanged.

Verification checklist
- Dashboard shows "Storage" card with total bytes formatted.
- "Prerolls" section shows only 20 items by default; page size control available; pagination controls show correct ranges.
- Checkboxes appear in Grid and List views; select-all-on-page works; bulk "Set Primary Category" applies to selected prerolls.
- Footer version shows "v1.1.0" under Installed or API Version.

Known limitations
- Bulk operation currently supports changing primary category only; future versions may add bulk metadata edits (tags, description).

SHA-256 checksums
- Will be published alongside the release artifacts after CI packaging completes.