# NeXroll v1.11.0-beta.6 Release Notes

**Release Date:** February 26, 2026

## Changes in Beta.6

### Coming Soon List Generator

**Custom Audio Upload**
- You can now upload your own audio file (.mp3, .wav, .aac, .m4a, .ogg, .flac) for the Coming Soon List video
- Replaces the default ambient track with your chosen audio
- Audio is automatically trimmed to match the selected video duration with smooth fade-in/out (1.5s each)
- Upload, preview filename, and remove controls shown when Background Music is enabled
- Custom audio persists across sessions and is used by auto-regeneration

**Custom Logo Overlay**
- Added the ability to overlay a custom logo (watermark) on generated Coming Soon List videos
- Accepts .png, .jpg, .jpeg, and .webp image files
- Logo is rendered as a faded, centered watermark behind the text content
- Upload and remove controls with filename preview
- Logo persists across sessions and is applied during auto-regeneration

**Options Panel — 2×2 Grid Layout**
- Reorganized the four Coming Soon List option cards into a clean 2×2 grid
  - Top row: Background Music | Custom Logo Overlay
  - Bottom row: Available Now! Duration | Auto-regenerate on Sync
- All four cards now share a unified dark card style with consistent padding, border, icon treatment, and typography
- Replaced mixed cyan/green color schemes with a single subtle neutral card style
- All option icons now use a consistent `#00d4ff` accent color and uniform sizing
- Auto-Regenerate card now displays a `RefreshCw` icon for better visual clarity

### Bug Fixes

**FFmpeg Detection Error — Fixed**
- Fixed "FFmpeg Required" error that prevented the Coming Soon List Generator from working
- Root cause: a syntax error in `dynamic_preroll.py` — the opening `"""` of the `generate_coming_soon_list` docstring was accidentally removed during a prior edit, creating an unterminated string literal
- PyInstaller silently skipped the broken module, causing `ModuleNotFoundError: No module named 'backend.dynamic_preroll'` at runtime
- Fix: restored the docstring syntax and added `backend.dynamic_preroll` to PyInstaller `hiddenimports` as a safeguard
- Added a top-level import in `main.py` to ensure the module is always bundled

---

## Changes in Beta.5

### Coming Soon List Generator

**Background Music**
- Added a background music toggle for the Coming Soon List Generator
- When enabled, an ambient track plays behind the generated video (grid and list layouts)
- Audio includes smooth fade-in and fade-out (1.5 seconds each), automatically matched to the selected video duration
- Setting persists across sessions and is respected by auto-regeneration
- Audio asset bundled in both Windows installer and Docker image

**Emoji-to-Icon Cleanup**
- Replaced all emoji characters in the Coming Soon List Generator UI with proper Lucide React icons
- Layout buttons now use `LayoutGrid` and `List` icons
- Source selector uses `Film` (movies) and `Tv` (TV shows) icons
- Audio toggle uses the `Music` icon

### UI / Theming

**Header Icon Theming**
- All page header icons across the app now follow the active theme
- Dark mode: icons render in white
- Light mode: icons render in black
- Applied consistently to 26+ header icons via a new `.header-icon` CSS class

---

## Full Changelog Since v1.10.x

See [CHANGELOG.md](CHANGELOG.md) for the complete v1.11.0 feature list including:
- Coming Soon List Generator
- Authentication System (API Keys and User Accounts)
- Enhanced Update System
- Enhanced Logging System
- Holiday API Browser
- And more...
