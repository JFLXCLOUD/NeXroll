# NeXroll v1.3.14 Release Notes

Date: 2025-10-01

Enhancements

- Modernized Schedule Management and Category creation UI to match the new Prerolls look-and-feel:
  - Added a compact, pill-styled toolbar on Schedules (View/Month/Year with Prev/Next controls).
  - Refined Create New Schedule form with consistent inputs/selects, accessible focus rings, and grouped checkboxes (Random/Sequential).
  - Smoothed Create New Category fields and mode selector using the same styling system for visual consistency.

Changed files

- [NeXroll/frontend/src/App.js](NeXroll/frontend/src/App.js): applied classnames and structure for:
  - Schedule toolbar and navigation
  - Create New Schedule checkboxes (as grouped pills)
  - Category Create form select classes
- [NeXroll/frontend/src/index.css](NeXroll/frontend/src/index.css): added shared styles:
  - `.nx-toolbar`, `.toolbar-group`, `.nx-checkrow`, `.nx-check` for toolbars and checkbox-pills
  - Dark-mode and responsive variants

Packaging

- Version bump:
  - [NeXroll/version_info.txt](NeXroll/version_info.txt) → 1.3.14.0
  - [NeXroll/installer.nsi](NeXroll/installer.nsi) → APP_VERSION 1.3.14 / VIProductVersion 1.3.14.0

Notes

- UI-only changes; no server or DB migration required.
- All new styles are theme-aware using existing CSS variables.

Previous version: v1.3.13