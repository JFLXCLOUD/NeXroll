# NeXroll v1.1.1 (2025-09-23)

Small UX hotfix release after v1.1.0 adding navigation, preroll management, and packaging improvements.

## Highlights
- Sticky top navigation bar across Dashboard, Schedules, Categories, Settings, and Plex for easier navigation while scrolling.
- Prerolls pagination: default 20 per page with selectable page sizes up to 50.
- Multi-select on Prerolls with a bulk action to change the primary category (moves files on disk safely).
- Inline category creation when uploading or editing prerolls (no need to visit Categories first).
- Storage usage card on the Dashboard that shows total preroll storage used.

## Fixes and polish
- Prevented Edit/Delete buttons from overflowing off the thumbnail when preroll titles are long (grid and list views).
- Updated PWA service worker cache names to v1.1.1 and removed hard-coded hashed asset pre-caching to reduce stale caches after upgrades.
- Minor UI spacing/ellipsis improvements for long titles and action buttons.

## Packaging and versioning
- Backend API version bumped to 1.1.1.
- Windows binary metadata (FileVersion/ProductVersion) set to 1.1.1.0.
- NSIS installer APP_VERSION bumped to 1.1.1; installer output: NeXroll/NeXroll_Installer_1.1.1.exe.

## Upgrade notes
- If a previous PWA tab is open, refresh the page to activate the new service worker/caches.
- For service installs, stop the service, run the new installer, then start the service again.
- FFmpeg is still required for thumbnail generation (available as an optional installer component via winget).

## Release assets
- NeXroll_Installer_1.1.1.exe (recommended for end users)
- Dist executables (advanced/portable use):
  - dist/NeXroll.exe
  - dist/NeXrollService.exe
  - dist/NeXrollTray.exe
  - dist/setup_plex_token.exe

## Checksums (optional)
Generate SHA256 checksums (Windows, PowerShell):

```
Get-FileHash ".\NeXroll\NeXroll_Installer_1.1.1.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXroll.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXrollService.exe" -Algorithm SHA256
Get-FileHash ".\dist\NeXrollTray.exe" -Algorithm SHA256
Get-FileHash ".\dist\setup_plex_token.exe" -Algorithm SHA256
```

Publish the hashes alongside this release, or commit them to a CHECKSUMS_v1.1.1.txt file in the repository.

## Acknowledgements
Thanks for the feedback that led directly to the sticky nav, bulk primary category changes, and inline category creation improvements.