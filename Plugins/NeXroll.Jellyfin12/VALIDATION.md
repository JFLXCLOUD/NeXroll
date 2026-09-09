# Jellyfin 12 build validation

Validated locally on 2026-09-09 using the official portable Windows Jellyfin
12.0.0 server, a fresh test database, and a localhost-only listener.

- Plugin: NeXroll Intros 1.15.0.0, .NET 10, target ABI 12.0.0.0.
- Build: .NET SDK 10.0.401, pinned Jellyfin packages 12.0.0. Build succeeded;
  one existing missing-XML-comment warning in the shared Plugin constructor.
- Archive: exactly `NeXroll.Jellyfin.dll`, `meta.json`, and `thumb.png` at its
  root. Metadata version agrees with the DLL assembly version.
- Jellyfin loaded the plugin as Active and served its embedded configuration
  page successfully.
- A fresh Jellyfin API key returned HTTP 401 for `/Plugins` when sent through
  both original `X-Emby-Token` and `X-MediaBrowser-Token` headers, and HTTP 200
  through the supported `Authorization` header.
  The updated production NeXroll connector passed connection and plugin-list
  requests with that same key.
- The movie intro API called a local mock NeXroll endpoint with the configured
  NeXroll API key. It registered the returned intro in Jellyfin's database and
  returned one intro item. Downloading that item's static video stream produced
  bytes identical to the test MP4.
- Eleven Python tests passed, including manual keys, saved keys, replacement
  keys, legacy-key migration, and unauthenticated UI assets.
- The GitHub Actions YAML parses and defines separate .NET 9 and .NET 10 jobs
  with exact, distinct package filenames.

Package: `NeXroll.Jellyfin12-1.15.0.0.zip`

SHA-256:
`77B0E617181BDBFC04932B011F47A631AFC2952E855CB562AA5DA89F92BDD82C`

Limits: this used a mock NeXroll intro response, not a full NeXroll scheduler.
No physical playback client or automatic preroll-to-movie handoff was tested.
The test host logged sandbox-related ASP.NET data-protection and external
plugin-update errors; plugin loading and all checks above still succeeded.
Test the complete flow on the affected user's Jellyfin client before treating
that client as confirmed compatible.
