# NeXroll v1.3.13 Release Notes

Date: 2025-10-01

Enhancements

- Modernized Prerolls UI while matching existing theme:
  - Refined buttons (view toggle, Apply CTA, bulk action buttons)
  - Updated selects and inputs with accessible focus rings and rounded corners
  - Search input with inline icon and subtle shadows
  - Reworked bulk actions bar and layout spacing
  - Dark/Light theme harmony via CSS variables

Changed files

- [NeXroll/frontend/src/index.css](NeXroll/frontend/src/index.css): new “Modernized Prerolls UI” block appended (classes: .prerolls-control-bar, .view-toggle, .view-btn, .filter-select, .page-size-select, .bulk-category-select, .search-input, .filter-btn, .bulk-actions-bar, .action-btn).
- [NeXroll/installer.nsi](NeXroll/installer.nsi): bumped APP_VERSION to 1.3.13 and VIProductVersion to 1.3.13.0.
- [NeXroll/version_info.txt](NeXroll/version_info.txt): updated FileVersion/ProductVersion to 1.3.13.0.

Build artifacts

- [NeXroll/NeXroll_Installer_1.3.13.exe](NeXroll/NeXroll_Installer_1.3.13.exe)
- [NeXroll/CHECKSUMS_v1.3.13.txt](NeXroll/CHECKSUMS_v1.3.13.txt)
- [dist/NeXroll.exe](dist/NeXroll.exe)
- [dist/NeXrollService.exe](dist/NeXrollService.exe)
- [dist/NeXrollTray.exe](dist/NeXrollTray.exe)
- [dist/setup_plex_token.exe](dist/setup_plex_token.exe)

Notes

- UI-only change; no API or DB migrations required.
- Dev server warnings (eslint) are unchanged and safe for release; they do not affect runtime.
- If needed, these styles can be tuned via CSS variables in [NeXroll/frontend/src/index.css](NeXroll/frontend/src/index.css).

Previous version: v1.3.12