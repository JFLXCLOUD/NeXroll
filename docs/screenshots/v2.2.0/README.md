# Screenshots for the README

All seven are full-window browser captures (1920x1080, captured at 2x and scaled down) in the Midnight theme, taken October 4, 2026. The folder keeps its 2.2.0 name so existing links still work.

The pages were rendered by the frontend from the working tree after the 2.2.2 release. That build includes two fixes not in 2.2.2: Library Trailers no longer count as uncategorized, and the Schedules page's "Today's run" lists the running schedule first.

- `dashboard.png`, `schedules.png` and `community.png` show the maintainer's own NeXroll install, read through its API with every write request blocked. On the dashboard, the Plex server address is blurred because a plex.direct hostname contains the server's unique ID.
- `library.png` shows 20 prerolls from the same install, with their real names, categories and thumbnails, served from a mocked API so the grid shows a chosen set. Third-party footage (TV bumpers, film clips, studio logos, movie trailers) was left out.
- `calendar.png` and `generator.png` use example API responses. Schedule and server names are fictional. Generator Studio shows its actual live canvas preview.
- `sequence-flow.png` comes from the Flow view demo script (`launch-video/scripts/capture-flow-demo.cjs`), stopped at the step where NeX-Up trailers play when available and a category plays otherwise. Its sequence and category names are demonstration data.

The two `readme-preview-*` images show the local Markdown preview of the 2.2.0 draft in light and dark mode.

These captures illustrate the interface; they are not evidence of live playback, downloads or backend health. Refresh them when the interface changes.
