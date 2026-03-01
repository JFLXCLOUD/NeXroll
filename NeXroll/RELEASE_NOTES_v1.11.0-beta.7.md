# NeXroll v1.11.0-beta.7 Release Notes

**Release Date:** February 28, 2026

## Changes in Beta.7

### Dynamic Preroll Generator

**Custom Logo Overlay**
- Added the ability to upload a custom logo image (.png, .jpg, .jpeg, .webp) for Dynamic Preroll videos
- When a logo is uploaded, it replaces the server name text in the live preview and generated video
- Works with all three template styles: Coming Soon (Cinematic/Neon/Minimal), Feature Presentation, and Now Showing
- Upload, preview filename, and remove controls shown on a dedicated logo card
- Logo persists across sessions
- Includes a helpful tip recommending landscape-oriented logos (e.g. 800×200 px) with transparent PNG backgrounds

### Coming Soon List Generator

**Available Now! Settings (renamed from "Available Now! Duration")**
- Renamed the card to "Available Now! Settings" to better reflect its expanded functionality
- Added a **Max Items** setting to limit how many "Available Now!" items appear on the list
- When set (e.g., 3), only the most recently added items with "Available Now!" status are shown
- Set to 0 for no limit (default behavior)
- Setting persists across sessions and is respected by auto-regeneration

**Color Settings Expanded by Default**
- The Color Settings section (Background, Text, Accent) is now visible by default instead of collapsed

### NeX-Up Settings

**TMDB API Key Security**
- The TMDB API Key input field is now masked (password-style) once a key is configured
- Click into the field to reveal the key for editing
- Prevents accidental exposure of the API key on screen

### UI / Styling

**Generator Page Style Consistency**
- Aligned visual styles between the Dynamic Preroll and Coming Soon List generator pages
- Consistent use of Lucide icons across all labels and section headers
- Unified input/select styling (padding, border radius, font size)
- Matching option card sub-description colors
- Consistent button styles, generate button containers, and generated lists sections

---

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

**Logo Mode Toggle**
- Added a mode selector for the custom logo: **Watermark** or **Replace Server Name**
- **Watermark** (default): logo appears as a faded, centered watermark behind the text (existing behavior)
- **Replace Server Name**: logo replaces the "to {Server Name}" subtitle text in the generated video — displayed at higher opacity in the header area
- Toggle appears on the Custom Logo Overlay card when a logo is uploaded
- Mode persists across sessions and is respected by auto-regeneration
- Works with both grid and text/list layout styles

**Options Panel — 2×2 Grid Layout**
- Reorganized the four Coming Soon List option cards into a clean 2×2 grid
  - Top row: Background Music | Custom Logo Overlay
  - Bottom row: Available Now! Duration | Auto-regenerate on Sync
- All four cards now share a unified dark card style with consistent padding, border, icon treatment, and typography
- Replaced mixed cyan/green color schemes with a single subtle neutral card style
- All option icons now use a consistent `#00d4ff` accent color and uniform sizing
- Auto-Regenerate card now displays a `RefreshCw` icon for better visual clarity

**Available Now! Duration**
- Added a configurable "Available Now!" duration setting for the Coming Soon List
- When a movie or show is downloaded, it displays an "Available Now!" badge on the Coming Soon List
- Set how many days (1–30) the item stays visible before being automatically removed
- Defaults to 1 day; setting persists across sessions and is respected by auto-regeneration

### Community Preroll Server

**Community Server Selector**
- Added the ability to choose which Community Preroll Server to connect to
- Fetches available servers from a central `servers.json` endpoint
- Select from the server list or enter a custom server URL
- Custom server URL is saved per-instance and persists across sessions
- Default server: `prerolls.uk`

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
