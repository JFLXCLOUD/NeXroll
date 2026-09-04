"""
NeX-Up: Dynamic Preroll Generator
Creates customizable intro videos using FFmpeg with advanced visual effects
"""

import os
import re
import subprocess
import shutil
import tempfile
import logging
import sys
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)

RENDER_RESOLUTIONS = {
    '720': (1280, 720),
    '1080': (1920, 1080),
    '2160': (3840, 2160),
}

RENDER_QUALITY_PROFILES = {
    'draft': {
        'label': 'Draft',
        'preset': 'veryfast',
        'crf': 24,
        'audio_bitrate': '128k',
    },
    'balanced': {
        'label': 'Balanced',
        'preset': 'fast',
        'crf': 20,
        'audio_bitrate': '192k',
    },
    'high': {
        'label': 'High quality',
        'preset': 'slow',
        'crf': 15,
        'audio_bitrate': '256k',
    },
    'master': {
        'label': 'Master',
        'preset': 'slower',
        'crf': 12,
        'audio_bitrate': '320k',
    },
}

RENDER_FRAME_RATES = (24, 30, 60)
DYNAMIC_FONT_SCALE_MIN = 0.85
DYNAMIC_FONT_SCALE_MAX = 1.30
DYNAMIC_AUDIO_MODES = ('none', 'default', 'custom')


# Typeface choices for the generators.
#
# The two generators render in different places: dynamic prerolls are drawn on a
# canvas in the browser and uploaded as a recording, while Coming Soon lists are
# drawn by FFmpeg on the server and regenerated headlessly after every sync. A
# font therefore has to be resolvable *on the server* to be honest about what
# will actually render, which is why the built-in list below is probed against
# the filesystem rather than simply offered.
#
# Each entry maps a stable id to the candidate filenames for that face across
# Windows, Debian/Ubuntu (DejaVu/Liberation) and macOS, plus the CSS stack the
# browser canvas uses so the preview matches the server render as closely as the
# installed fonts allow.
FONT_LIBRARY = {
    'arial': {
        'label': 'Arial', 'category': 'Sans',
        'css': 'Arial, Helvetica, "Liberation Sans", sans-serif',
        'files': ['arial.ttf', 'ArialMT.ttf', 'Arial.ttf', 'LiberationSans-Regular.ttf'],
    },
    'segoe': {
        'label': 'Segoe UI', 'category': 'Sans',
        'css': '"Segoe UI", Selawik, "DejaVu Sans", sans-serif',
        'files': ['segoeui.ttf', 'SegoeUI.ttf'],
    },
    'dejavu': {
        'label': 'DejaVu Sans', 'category': 'Sans',
        'css': '"DejaVu Sans", Verdana, sans-serif',
        'files': ['DejaVuSans.ttf'],
    },
    'verdana': {
        'label': 'Verdana', 'category': 'Sans',
        'css': 'Verdana, "DejaVu Sans", sans-serif',
        'files': ['verdana.ttf', 'Verdana.ttf'],
    },
    'tahoma': {
        'label': 'Tahoma', 'category': 'Sans',
        'css': 'Tahoma, "DejaVu Sans", sans-serif',
        'files': ['tahoma.ttf', 'Tahoma.ttf'],
    },
    'impact': {
        'label': 'Impact', 'category': 'Display',
        'css': 'Impact, Haettenschweiler, "DejaVu Sans", sans-serif',
        'files': ['impact.ttf', 'Impact.ttf'],
    },
    'times': {
        'label': 'Times New Roman', 'category': 'Serif',
        'css': '"Times New Roman", Times, "Liberation Serif", serif',
        'files': ['times.ttf', 'TimesNewRomanPSMT.ttf', 'LiberationSerif-Regular.ttf'],
    },
    'georgia': {
        'label': 'Georgia', 'category': 'Serif',
        'css': 'Georgia, "DejaVu Serif", serif',
        'files': ['georgia.ttf', 'Georgia.ttf'],
    },
    'dejavuserif': {
        'label': 'DejaVu Serif', 'category': 'Serif',
        'css': '"DejaVu Serif", Georgia, serif',
        'files': ['DejaVuSerif.ttf'],
    },
    'consolas': {
        'label': 'Consolas', 'category': 'Mono',
        'css': 'Consolas, "DejaVu Sans Mono", monospace',
        'files': ['consola.ttf', 'Consolas.ttf'],
    },
    'couriernew': {
        'label': 'Courier New', 'category': 'Mono',
        'css': '"Courier New", Courier, "Liberation Mono", monospace',
        'files': ['cour.ttf', 'CourierNew.ttf', 'LiberationMono-Regular.ttf'],
    },
}

# Typefaces that ship with NeXroll, so the picker offers the same set on every
# install rather than whatever the host happens to have. Without these a Docker
# user sees only DejaVu and Liberation. All are SIL OFL 1.1; see
# assets/fonts/licenses/ for the text and assets/fonts/README.md for provenance.
BUNDLED_FONTS = {
    'bebasneue':      {'label': 'Bebas Neue',       'category': 'Display', 'file': 'BebasNeue-Regular.ttf'},
    'anton':          {'label': 'Anton',            'category': 'Display', 'file': 'Anton-Regular.ttf'},
    'archivoblack':   {'label': 'Archivo Black',    'category': 'Display', 'file': 'ArchivoBlack-Regular.ttf'},
    'oswald':         {'label': 'Oswald',           'category': 'Sans',    'file': 'Oswald-Variable.ttf'},
    'robotocondensed':{'label': 'Roboto Condensed', 'category': 'Sans',    'file': 'RobotoCondensed-Variable.ttf'},
    'cinzel':         {'label': 'Cinzel',           'category': 'Serif',   'file': 'Cinzel-Variable.ttf'},
    'playfairdisplay':{'label': 'Playfair Display', 'category': 'Serif',   'file': 'PlayfairDisplay-Variable.ttf'},
    'lora':           {'label': 'Lora',             'category': 'Serif',   'file': 'Lora-Variable.ttf'},
    'jetbrainsmono':  {'label': 'JetBrains Mono',   'category': 'Mono',    'file': 'JetBrainsMono-Variable.ttf'},
}


def bundled_fonts_dir() -> Optional[str]:
    """Locate the shipped typefaces across dev, PyInstaller and Docker.

    Mirrors how the bundled soundtrack is found: a frozen build unpacks to
    _MEIPASS, everything else walks up from this module to the project root.
    """
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', None)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not base_dir:
        return None
    path = os.path.join(base_dir, 'assets', 'fonts')
    return path if os.path.isdir(path) else None


def bundled_font_path(font_id: Any) -> Optional[str]:
    """Absolute path to a shipped face, or None when it is not present."""
    entry = BUNDLED_FONTS.get(str(font_id or '').strip().lower())
    directory = bundled_fonts_dir()
    if not entry or not directory:
        return None
    path = os.path.join(directory, entry['file'])
    return path if os.path.isfile(path) else None


# Where a face may live. Windows first, then the Debian/Ubuntu trees the Docker
# image actually ships, then macOS.
FONT_SEARCH_DIRS = (
    os.environ.get('WINDIR', 'C:\\Windows') + os.sep + 'Fonts',
    '/usr/share/fonts/truetype/dejavu',
    '/usr/share/fonts/truetype/liberation',
    '/usr/share/fonts/truetype/liberation2',
    '/usr/share/fonts/truetype/msttcorefonts',
    '/usr/share/fonts/dejavu',
    '/usr/share/fonts',
    '/usr/local/share/fonts',
    '/Library/Fonts',
    '/System/Library/Fonts',
    os.path.expanduser('~/.fonts'),
    os.path.expanduser('~/Library/Fonts'),
)

# Uploaded faces must work in BOTH renderers, so the accepted formats are the
# intersection of what FFmpeg's drawtext can open and what a browser accepts
# through @font-face. woff/woff2 are deliberately excluded: the canvas preview
# would take them and the Coming Soon render would silently fall back to DejaVu.
FONT_UPLOAD_EXTENSIONS = ('.ttf', '.otf', '.ttc')


def find_font_file(font_id: Any) -> Optional[str]:
    """Return the on-disk path for a built-in font id, or None if absent here.

    Shipped faces win over host-installed ones: they are the same bytes on every
    install, which is the whole reason they are bundled.
    """
    shipped = bundled_font_path(font_id)
    if shipped:
        return shipped
    entry = FONT_LIBRARY.get(str(font_id or '').strip().lower())
    if not entry:
        return None
    for candidate in entry['files']:
        for directory in FONT_SEARCH_DIRS:
            try:
                path = os.path.join(directory, candidate)
                if os.path.isfile(path):
                    return path
            except Exception:
                continue
    return None


def available_builtin_fonts() -> List[Dict[str, Any]]:
    """Built-in faces this machine can actually render with.

    Probing rather than listing keeps the picker honest: on a Docker host this
    returns the two or three DejaVu/Liberation faces the image ships, not a
    dozen Windows fonts that would fall back to something else at render time.
    """
    found = []
    for font_id, entry in BUNDLED_FONTS.items():
        if not bundled_font_path(font_id):
            continue
        found.append({
            'id': f'builtin:{font_id}',
            'label': entry['label'],
            'category': entry['category'],
            # Shipped faces are not installed on the viewer's machine, so the
            # browser loads them by URL the same way an upload is loaded.
            'css': None,
            'source': 'bundled',
            'filename': entry['file'],
            'url': f"/nexup/fonts/bundled/{entry['file']}",
        })
    for font_id, entry in FONT_LIBRARY.items():
        # A shipped face of the same name already answered above; listing the
        # host copy too would put a duplicate id in the picker.
        if font_id in BUNDLED_FONTS:
            continue
        path = find_font_file(font_id)
        if path:
            found.append({
                'id': f'builtin:{font_id}',
                'label': entry['label'],
                'category': entry['category'],
                'css': entry['css'],
                'source': 'builtin',
            })
    return found


def resolve_font_selection(value: Any, custom_dir: Any = None) -> Optional[str]:
    """Resolve a stored font choice to a file path on this machine.

    Accepts 'builtin:<id>' or 'custom:<filename>'; a bare value is read as a
    built-in id so any older stored value keeps working. Returns None to mean
    "leave the template's own choice alone", which is the previous behavior.
    """
    text = str(value or '').strip()
    if not text:
        return None
    if text.startswith('custom:'):
        filename = os.path.basename(text[len('custom:'):].strip())
        if not filename or not custom_dir:
            return None
        path = os.path.join(str(custom_dir), filename)
        return path if os.path.isfile(path) else None
    if text.startswith('builtin:'):
        text = text[len('builtin:'):].strip()
    return find_font_file(text)


def ffmpeg_fontfile_param(font_path: Any) -> str:
    """Build the drawtext fontfile fragment for a path, or '' when there is none."""
    if not font_path or not os.path.isfile(str(font_path)):
        return ""
    escaped = str(font_path).replace('\\', '/').replace(':', '\\:')
    return ":fontfile='" + escaped + "'"


def resolve_dynamic_font_scale(value: Any = 1.0) -> float:
    """Normalize the shared preview/render typography scale."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(numeric):
        return 1.0
    return max(DYNAMIC_FONT_SCALE_MIN, min(DYNAMIC_FONT_SCALE_MAX, numeric))


def resolve_dynamic_text_color(value: Any = None) -> Optional[str]:
    """Return a normalized six-digit web color or None to inherit the theme."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if re.fullmatch(r'#[0-9a-f]{6}', normalized):
        return normalized
    return None


def resolve_dynamic_audio_mode(value: Any = 'none') -> str:
    """Normalize the user-facing soundtrack choice."""
    normalized = str(value or 'none').strip().lower()
    return normalized if normalized in DYNAMIC_AUDIO_MODES else 'none'


def backdrop_video_chain(width: int, height: int, dim_percent: Any = 0) -> str:
    """FFmpeg filter chain that fits arbitrary footage behind generated text.

    Two things have to happen to someone else's video before text goes on top:

    * Fit it without distorting. Scaling straight to WxH stretches a clip whose
      aspect differs from the layout, so a phone video would come out squashed.
      Scale to cover instead, then crop the overflow.
    * Darken it. The generated themes are deliberately dim so titles stay
      readable; bright, busy footage is what would make this feature look
      broken. colorchannelmixer scales each channel, which is a true darkening
      rather than a translucent overlay, and costs nothing measurable.
    """
    try:
        dim = float(dim_percent or 0)
    except (TypeError, ValueError):
        dim = 0.0
    dim = max(0.0, min(90.0, dim))
    chain = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
             f"crop={width}:{height},setsar=1")
    if dim > 0:
        k = round(1.0 - (dim / 100.0), 4)
        chain += f",colorchannelmixer=rr={k}:gg={k}:bb={k}"
    return chain


def resolve_render_settings(
    resolution: str = '1080',
    frame_rate: int = 30,
    quality: str = 'balanced',
) -> Dict[str, Any]:
    """Return a safe, concrete FFmpeg profile for user-facing render options."""
    resolution_key = str(resolution or '1080').lower().replace('p', '')
    if resolution_key == '4k':
        resolution_key = '2160'
    if resolution_key not in RENDER_RESOLUTIONS:
        resolution_key = '1080'

    try:
        normalized_frame_rate = int(frame_rate)
    except (TypeError, ValueError):
        normalized_frame_rate = 30
    if normalized_frame_rate not in RENDER_FRAME_RATES:
        normalized_frame_rate = 30

    quality_key = str(quality or 'balanced').lower()
    if quality_key not in RENDER_QUALITY_PROFILES:
        quality_key = 'balanced'

    width, height = RENDER_RESOLUTIONS[resolution_key]
    profile = RENDER_QUALITY_PROFILES[quality_key]
    return {
        'resolution': resolution_key,
        'width': width,
        'height': height,
        'frame_rate': normalized_frame_rate,
        'quality': quality_key,
        **profile,
    }

# Verbose logging callback - will be set by main.py
_verbose_log_callback: Optional[Callable[[str], None]] = None

def set_verbose_logger(callback: Callable[[str], None]):
    """Set the verbose logging callback function"""
    global _verbose_log_callback
    _verbose_log_callback = callback

def _verbose_log(message: str):
    """Log a verbose message if callback is set"""
    if _verbose_log_callback:
        _verbose_log_callback(f"[DynamicPreroll] {message}")
    logger.debug(message)

# Windows-specific: Hide console window when running FFmpeg
if sys.platform == 'win32':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    STARTUPINFO = None
    CREATE_NO_WINDOW = 0


COMMUNITY_PROBE_UA = "NeXRoll/probe (+https://github.com/JFLXCLOUD/NeXroll)"


class DynamicPrerollGenerator:
    """Generates dynamic preroll videos using FFmpeg with cinematic effects"""
    
    # Available templates with enhanced visual styles
    TEMPLATES = {
        'coming_soon': {
            'name': 'Coming Soon',
            'description': 'Cinematic intro announcing upcoming content with glow effects and dramatic animations.',
            'duration': 5,
            'variables': ['server_name'],
            'default_values': {'server_name': 'Your Server'},
            'style': 'cinematic'
        },
        'feature_presentation': {
            'name': 'Feature Presentation',
            'description': 'Classic theater-style "Feature Presentation" with elegant text and decorative elements.',
            'duration': 5,
            'variables': ['server_name'],
            'default_values': {'server_name': ''},
            'style': 'classic'
        },
        'now_showing': {
            'name': 'Now Showing',
            'description': 'Retro film-style "Now Showing" with film grain effect. Warm sepia tones.',
            'duration': 4,
            'variables': ['server_name'],
            'default_values': {'server_name': ''},
            'style': 'retro'
        },
        'custom_text': {
            'name': 'Custom Message',
            'description': 'Your own headline and supporting line, on the theme background. No fixed wording.',
            'duration': 5,
            'variables': ['custom_headline', 'custom_subtext'],
            'default_values': {'custom_headline': 'COMING SOON', 'custom_subtext': ''},
            'style': 'custom'
        },
        'qr_share': {
            'name': 'QR Code',
            'description': 'A scannable QR code with a caption, for sharing a link with viewers.',
            'duration': 8,
            'variables': ['qr_data', 'qr_caption'],
            'default_values': {'qr_data': '', 'qr_caption': 'SCAN TO LEARN MORE'},
            'style': 'utility'
        }
    }
    
    # Visual themes. Legacy FFmpeg renderers consume the four color keys while
    # the shared browser canvas also uses label/description/effect metadata.
    COLOR_THEMES = {
        'midnight': {'label': 'Midnight', 'description': 'Cool cinematic glow', 'effect': 'orbital', 'bg': '0x141428', 'primary': '0x00d4ff', 'secondary': '0x7b2cbf', 'accent': '0xff006e'},
        'sunset': {'label': 'Sunset', 'description': 'Warm orange cinema light', 'effect': 'orbital', 'bg': '0x2a1414', 'primary': '0xff6b35', 'secondary': '0xf7c59f', 'accent': '0xef233c'},
        'forest': {'label': 'Forest', 'description': 'Deep natural teal', 'effect': 'orbital', 'bg': '0x142a14', 'primary': '0x2ec4b6', 'secondary': '0x83c5be', 'accent': '0xedf6f9'},
        'royal': {'label': 'Royal', 'description': 'Gold and violet premiere', 'effect': 'orbital', 'bg': '0x1a0040', 'primary': '0xffd700', 'secondary': '0xc77dff', 'accent': '0xe0aaff'},
        'monochrome': {'label': 'Monochrome', 'description': 'Clean black and silver', 'effect': 'orbital', 'bg': '0x1a1a1a', 'primary': '0xffffff', 'secondary': '0xaaaaaa', 'accent': '0xcccccc'},
        'aurora_drift': {'label': 'Aurora Drift', 'description': 'Flowing arctic light ribbons', 'effect': 'aurora', 'featured': True, 'bg': '0x061522', 'primary': '0x59f8e8', 'secondary': '0x8b5cf6', 'accent': '0xb8ff7a'},
        'neon_city': {'label': 'Neon City', 'description': 'Animated synthwave horizon', 'effect': 'cyber_grid', 'featured': True, 'bg': '0x090014', 'primary': '0x37f5ff', 'secondary': '0xf72585', 'accent': '0xf9c74f'},
        'solar_flare': {'label': 'Solar Flare', 'description': 'Rotating cinematic light rays', 'effect': 'solar', 'featured': True, 'bg': '0x1e0805', 'primary': '0xffd166', 'secondary': '0xff6b35', 'accent': '0xef233c'},
        'deep_space': {'label': 'Deep Space', 'description': 'Twinkling stars and orbital rings', 'effect': 'starfield', 'featured': True, 'bg': '0x050816', 'primary': '0xdff6ff', 'secondary': '0x6c63ff', 'accent': '0xffcc66'},
        'velvet_gold': {'label': 'Velvet Gold', 'description': 'Elegant gold arcs and shimmer', 'effect': 'luxe', 'featured': True, 'bg': '0x180b18', 'primary': '0xf4d58d', 'secondary': '0xc084fc', 'accent': '0xffffff'},
    }
    
    # Language translations for static text in generated videos
    TRANSLATIONS = {
        'en': {
            'coming_soon': 'COMING SOON',
            'to': 'to',
            'feature_presentation': 'FEATURE PRESENTATION',
            'feature': 'FEATURE',
            'presentation': 'PRESENTATION',
            'now_showing': 'NOW SHOWING',
            'at': 'at',
            'coming_soon_to': 'COMING SOON TO',
            'available_now': 'Available Now!',
        },
        'fr': {
            'coming_soon': 'PROCHAINEMENT',
            'to': 'sur',
            'feature_presentation': 'LONG MÉTRAGE',
            'feature': 'LONG',
            'presentation': 'MÉTRAGE',
            'now_showing': "À L'AFFICHE",
            'at': 'sur',
            'coming_soon_to': 'PROCHAINEMENT SUR',
            'available_now': 'Maintenant disponible!',
        },
        'es': {
            'coming_soon': 'PRÓXIMAMENTE',
            'to': 'en',
            'feature_presentation': 'FUNCIÓN PRINCIPAL',
            'feature': 'FUNCIÓN',
            'presentation': 'PRINCIPAL',
            'now_showing': 'EN CARTELERA',
            'at': 'en',
            'coming_soon_to': 'PRÓXIMAMENTE EN',
            'available_now': '¡Disponible!',
        },
        'de': {
            'coming_soon': 'DEMNÄCHST',
            'to': 'auf',
            'feature_presentation': 'HAUPTFILM',
            'feature': 'HAUPT',
            'presentation': 'FILM',
            'now_showing': 'JETZT IM PROGRAMM',
            'at': 'auf',
            'coming_soon_to': 'DEMNÄCHST AUF',
            'available_now': 'Jetzt verfügbar!',
        },
    }
    
    def _get_text(self, key: str, language: str = 'en') -> str:
        """Get translated text for a given key and language."""
        lang = self.TRANSLATIONS.get(language, self.TRANSLATIONS['en'])
        return lang.get(key, self.TRANSLATIONS['en'].get(key, key))
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the generator.
        
        Args:
            output_dir: Directory to save generated prerolls (optional for template listing)
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = None
        self.ffmpeg_path = self._find_ffmpeg()
        self._font_cache = {}
        # When set, every drawtext in every template uses this face instead of
        # the per-template default. One file has one weight, so the bold styles
        # collapse onto it too -- FFmpeg cannot synthesize a bold anyway.
        self._font_override = None

    def set_font_override(self, font_path: Any) -> bool:
        """Use one font file for every text layer. Returns whether it took."""
        path = str(font_path).strip() if font_path else ''
        self._font_override = path if path and os.path.isfile(path) else None
        self._font_cache = {}
        return self._font_override is not None
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable"""
        logger.info("[FFmpeg] Starting FFmpeg detection...")
        
        # Check if ffmpeg is in PATH
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg:
            logger.info(f"[FFmpeg] Found via shutil.which: {ffmpeg}")
            return ffmpeg
        
        logger.info("[FFmpeg] Not found in PATH via shutil.which, checking common locations...")
        
        # Common locations on Windows
        common_paths = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\ffmpeg\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
            os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
            os.path.expanduser(r'~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'),
            r'C:\Windows\System32\ffmpeg.exe',
        ]
        
        # Also check next to the running executable (bundled/portable installs)
        try:
            import sys
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                logger.info(f"[FFmpeg] PyInstaller frozen exe dir: {exe_dir}")
                common_paths.insert(0, os.path.join(exe_dir, 'ffmpeg.exe'))
                common_paths.insert(1, os.path.join(exe_dir, 'bin', 'ffmpeg.exe'))
        except Exception:
            pass
        
        for path in common_paths:
            exists = os.path.isfile(path)
            if exists:
                logger.info(f"[FFmpeg] Found at: {path}")
                return path
        
        logger.info(f"[FFmpeg] Not found in common paths. Checked: {common_paths}")
        
        # Last resort: try running ffmpeg directly
        try:
            import subprocess
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True, timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            if result.returncode == 0:
                logger.info("[FFmpeg] Found via subprocess fallback")
                return 'ffmpeg'
        except Exception as e:
            logger.info(f"[FFmpeg] Subprocess fallback failed: {e}")
        
        logger.warning("[FFmpeg] NOT FOUND anywhere")
        return None
    
    def _get_font_path(self, font_name: str = 'arial') -> tuple:
        """Get font file path and escaped version for FFmpeg drawtext.

        Searches Windows fonts first, then Linux/Docker font directories. This
        matters because FFmpeg's drawtext, when given no fontfile, falls back to
        a built-in font with poor extended-Latin coverage — so glyphs like the
        German umlauts (ä/ö/ü), accented characters, etc. render as garbage.
        On Linux/Docker we resolve to DejaVu (broad Unicode coverage) or
        Liberation as a fallback. Each logical style maps to candidate filenames
        across platforms; we return the first that exists.
        """
        # The override answers for every style, so cache it once rather than
        # re-stat-ing the same file for each of arial/arial_bold/impact/...
        if self._font_override:
            cached = self._font_cache.get('__override__')
            if cached is None:
                cached = (self._font_override, ffmpeg_fontfile_param(self._font_override))
                self._font_cache['__override__'] = cached
            return cached

        if font_name in self._font_cache:
            return self._font_cache[font_name]

        # Per-style candidate filenames (Windows + Linux DejaVu/Liberation).
        font_files = {
            'arial':       ['arial.ttf', 'ArialMT.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf'],
            'arial_bold':  ['arialbd.ttf', 'Arial-BoldMT.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'],
            'times':       ['times.ttf', 'TimesNewRomanPSMT.ttf', 'DejaVuSerif.ttf', 'LiberationSerif-Regular.ttf'],
            'georgia':     ['georgia.ttf', 'Georgia.ttf', 'DejaVuSerif.ttf', 'LiberationSerif-Regular.ttf'],
            'impact':      ['impact.ttf', 'Impact.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'],
            'segoe':       ['segoeui.ttf', 'SegoeUI.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf'],
            'segoe_bold':  ['segoeuib.ttf', 'SegoeUI-Bold.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'],
            'consolas':    ['consola.ttf', 'Consolas.ttf', 'DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf'],
        }

        # Directories to search, in order. Windows fonts dir + common Linux paths
        # (Debian/Ubuntu Docker base ships fonts under /usr/share/fonts/truetype).
        search_dirs = [
            os.environ.get('WINDIR', r'C:\Windows') + os.sep + 'Fonts',
            '/usr/share/fonts/truetype/dejavu',
            '/usr/share/fonts/truetype/liberation',
            '/usr/share/fonts/truetype/liberation2',
            '/usr/share/fonts/dejavu',
            '/usr/share/fonts',
            '/usr/local/share/fonts',
            '/Library/Fonts',
            '/System/Library/Fonts',
        ]

        candidates = font_files.get(font_name, font_files['arial'])
        # Always allow DejaVu as a final universal fallback.
        for fb in ('DejaVuSans-Bold.ttf' if 'bold' in font_name else 'DejaVuSans.ttf', 'DejaVuSans.ttf'):
            if fb not in candidates:
                candidates.append(fb)

        font_file = None
        for candidate in candidates:
            for d in search_dirs:
                path = os.path.join(d, candidate)
                if os.path.exists(path):
                    font_file = path
                    break
            if font_file:
                break

        # Last resort: recursively scan the Linux fonts tree for a DejaVu Sans.
        if not font_file:
            want = 'DejaVuSans-Bold.ttf' if 'bold' in font_name else 'DejaVuSans.ttf'
            for base in ('/usr/share/fonts', '/usr/local/share/fonts'):
                if os.path.isdir(base):
                    for root, _dirs, files in os.walk(base):
                        if want in files:
                            font_file = os.path.join(root, want)
                            break
                        if 'DejaVuSans.ttf' in files:
                            font_file = os.path.join(root, 'DejaVuSans.ttf')
                    if font_file:
                        break

        if font_file and os.path.exists(font_file):
            # FFmpeg fontfile path: forward slashes, escape the Windows drive colon.
            escaped = font_file.replace('\\', '/').replace(':', '\\:')
            result = (font_file, f":fontfile='{escaped}'")
        else:
            # No fontfile found — drawtext will use its built-in default. Log so
            # the umlaut-rendering cause is diagnosable.
            try:
                logger.warning(f"[Font] No font file found for '{font_name}'; FFmpeg will use its default (extended-Latin glyphs may not render)")
            except Exception:
                pass
            result = (None, "")

        self._font_cache[font_name] = result
        return result
    
    def is_available(self) -> bool:
        """Check if FFmpeg is available"""
        return self.ffmpeg_path is not None
    
    def check_ffmpeg_available(self) -> bool:
        """Alias for is_available - check if FFmpeg is available"""
        return self.is_available()

    def generate_blank_video(self, duration: float, resolution: str = '1080', frame_rate: int = 30) -> Optional[str]:
        """Generate (or reuse a cached) silent black video, used as a timed
        pause between blocks in a sequence. Cached by duration/resolution so
        repeated use after the first generation is free."""
        if not self.output_dir:
            logger.error("Cannot generate blank video: no output directory configured")
            return None
        if not self.ffmpeg_path:
            logger.error("Cannot generate blank video: FFmpeg not found")
            return None

        duration = max(0.5, float(duration))
        width, height = RENDER_RESOLUTIONS.get(str(resolution), RENDER_RESOLUTIONS['1080'])
        output_filename = f"blank_{duration:g}s_{resolution}.mp4"
        output_path = self.output_dir / output_filename

        if output_path.exists() and output_path.stat().st_size > 0:
            return str(output_path)

        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s={width}x{height}:d={duration}:r={frame_rate}',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=48000:cl=stereo:d={duration}',
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '24',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            if result.returncode == 0 and output_path.exists():
                logger.info(f"Generated blank pause video: {output_path} ({duration}s)")
                return str(output_path)
            logger.error(f"Failed to generate blank video: {result.stderr[:500] if result.stderr else 'no error'}")
            return None
        except Exception as e:
            logger.error(f"Exception generating blank video: {e}")
            return None

    def get_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available templates"""
        return self.TEMPLATES.copy()
    
    def get_available_templates(self) -> list:
        """Get list of available templates for UI"""
        return [
            {
                'id': key,
                'name': val['name'],
                'description': val['description'],
                'variables': val['variables']
            }
            for key, val in self.TEMPLATES.items()
        ]
    
    def _escape_text(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter.
        
        Apostrophes (') are replaced with the typographic right single quote
        (\u2019) instead of backslash-escaping because FFmpeg's filter graph
        parser uses ' as the option-value delimiter and \\' is unreliable.
        The replacement character is visually identical and cp1252-safe.
        """
        text = text.replace("\\", "\\\\")
        text = text.replace(":", "\\:")
        text = text.replace("'", "\u2019")  # typographic right single quote
        text = text.replace(";", "\\;")     # filter separator
        return text
    
    def _build_glow_text(self, text: str, fontsize: int, color: str, font_param: str,
                         x: str, y: str, glow_color: str = None, glow_layers: int = 3) -> str:
        """Build text with glow effect using multiple shadow layers"""
        if glow_color is None:
            glow_color = color
        
        # Build glow layers (multiple blurred shadows create glow effect)
        filters = []
        for i in range(glow_layers, 0, -1):
            offset = i * 2
            alpha = 0.3 / i  # Decreasing alpha for outer layers
            filters.append(
                f"drawtext=text='{text}':"
                f"fontsize={fontsize}:fontcolor={glow_color}@{alpha}{font_param}:"
                f"x={x}:y={y}:"
                f"shadowcolor={glow_color}@{alpha}:shadowx={offset}:shadowy={offset}"
            )
        
        # Main text on top
        filters.append(
            f"drawtext=text='{text}':"
            f"fontsize={fontsize}:fontcolor={color}{font_param}:"
            f"x={x}:y={y}:"
            f"shadowcolor=black@0.8:shadowx=2:shadowy=2"
        )
        
        return ','.join(filters)
    
    def _build_animated_text(self, text: str, fontsize: int, color: str, font_param: str,
                             x: str, y: str, start_time: float, fade_duration: float = 0.5,
                             animation: str = 'fade') -> str:
        """Build text with animation effect"""
        escaped_text = self._escape_text(text)
        
        if animation == 'fade':
            return (
                f"drawtext=text='{escaped_text}':"
                f"fontsize={fontsize}:fontcolor={color}{font_param}:"
                f"x={x}:y={y}:"
                f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
                f"alpha='if(lt(t,{start_time}),0,if(lt(t,{start_time + fade_duration}),(t-{start_time})/{fade_duration},1))'"
            )
        elif animation == 'zoom':
            # Zoom in effect using font size interpolation
            return (
                f"drawtext=text='{escaped_text}':"
                f"fontsize='if(lt(t,{start_time}),1,if(lt(t,{start_time + fade_duration}),{fontsize}*(t-{start_time})/{fade_duration},{fontsize}))':"
                f"fontcolor={color}{font_param}:"
                f"x={x}:y={y}:"
                f"shadowcolor=black@0.8:shadowx=2:shadowy=2"
            )
        elif animation == 'slide_up':
            return (
                f"drawtext=text='{escaped_text}':"
                f"fontsize={fontsize}:fontcolor={color}{font_param}:"
                f"x={x}:"
                f"y='if(lt(t,{start_time}),h,if(lt(t,{start_time + fade_duration}),h-(h-({y}))*(t-{start_time})/{fade_duration},{y}))':"
                f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
                f"alpha='if(lt(t,{start_time}),0,1)'"
            )
        
        return f"drawtext=text='{escaped_text}':fontsize={fontsize}:fontcolor={color}{font_param}:x={x}:y={y}"
    
    def generate_coming_soon(
        self,
        server_name: str = "Your Server",
        duration: float = 5.0,
        output_filename: str = "coming_soon_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        bg_color: str = "0x1a1a2e",
        text_color: str = "white",
        accent_color: str = "0x00d4ff",
        style: str = "cinematic",
        theme: str = "midnight",
        language: str = 'en'
    ) -> Optional[str]:
        """
        Generate a "Coming Soon to [Server Name]" intro video with advanced effects.
        
        Styles:
        - cinematic: Epic zoom with particles and dramatic lighting
        - neon: Vibrant glowing neon text with color pulses
        - minimal: Clean, elegant fade with subtle motion
        """
        if not self.is_available():
            logger.error("FFmpeg not available")
            return None
        
        if not self.output_dir:
            logger.error("Output directory not set")
            return None
        
        # Apply theme colors if specified
        _verbose_log(f"=== generate_coming_soon ===")
        _verbose_log(f"Theme: {theme}, Style: {style}")
        
        if theme in self.COLOR_THEMES:
            colors = self.COLOR_THEMES[theme]
            bg_color = colors['bg']
            text_color = colors['primary']
            accent_color = colors['secondary']
            _verbose_log(f"Applied theme colors - BG: {bg_color}, Text: {text_color}, Accent: {accent_color}")
        else:
            _verbose_log(f"Theme '{theme}' not found, using defaults - BG: {bg_color}, Text: {text_color}")
        
        if style == 'neon':
            return self._generate_neon_coming_soon(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, accent_color, language
            )
        elif style == 'minimal':
            return self._generate_minimal_coming_soon(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, accent_color, language
            )
        else:
            return self._generate_cinematic_coming_soon(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, accent_color, language
            )
    
    def _generate_cinematic_coming_soon(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str,
        accent_color: str,
        language: str = 'en'
    ) -> Optional[str]:
        """Generate cinematic style with glow effects and dramatic presentation"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Cinematic style: dramatic text with multiple glow layers, film grain, fades
        filter_str = (
            # Outer glow layer (creates "bloom" effect)
            f"drawtext=text='{coming_soon_text}':fontsize=85:fontcolor={accent_color}@0.2{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.15:shadowx=8:shadowy=8,"
            # Mid glow
            f"drawtext=text='{coming_soon_text}':fontsize=82:fontcolor={accent_color}@0.35{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.25:shadowx=5:shadowy=5,"
            # Main title
            f"drawtext=text='{coming_soon_text}':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor=black@0.8:shadowx=3:shadowy=3,"
            # "to" text with fade-in
            f"drawtext=text='{to_text}':fontsize=42:fontcolor={text_color}@0.85{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-15:alpha='if(lt(t,0.8),0,if(lt(t,1.5),(t-0.8)/0.7,1))',"
            # Server name outer glow
            f"drawtext=text='{escaped_server}':fontsize=65:fontcolor={accent_color}@0.25{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+45:shadowcolor={accent_color}@0.2:shadowx=6:shadowy=6:"
            f"alpha='if(lt(t,1.2),0,if(lt(t,2),(t-1.2)/0.8,1))',"
            # Server name main
            f"drawtext=text='{escaped_server}':fontsize=62:fontcolor={accent_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+45:shadowcolor=black@0.6:shadowx=2:shadowy=2:"
            f"alpha='if(lt(t,1.2),0,if(lt(t,2),(t-1.2)/0.8,1))',"
            # Film grain effect
            f"noise=c0s=6:c0f=t+u,"
            # Fades
            f"fade=t=in:st=0:d=1.2,fade=t=out:st={duration-1}:d=1"
        )
        
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent_color)
    
    def _generate_neon_coming_soon(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str,
        accent_color: str,
        language: str = 'en'
    ) -> Optional[str]:
        """Generate neon glow style with pulsing effects"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Neon effect: multiple glow layers (static, since dynamic alpha expressions are complex)
        filter_str = (
            # Outer glow layer 3 (widest, faintest)
            f"drawtext=text='{coming_soon_text}':fontsize=85:fontcolor={accent_color}@0.2{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-95:shadowcolor={accent_color}@0.15:shadowx=8:shadowy=8,"
            # Outer glow layer 2
            f"drawtext=text='{coming_soon_text}':fontsize=82:fontcolor={accent_color}@0.35{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-97:shadowcolor={accent_color}@0.25:shadowx=5:shadowy=5,"
            # Main text with glow
            f"drawtext=text='{coming_soon_text}':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.6:shadowx=3:shadowy=3,"
            # "to" with fade in
            f"drawtext=text='{to_text}':fontsize=40:fontcolor={text_color}@0.8{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-15:alpha='if(lt(t,0.8),0,if(lt(t,1.3),(t-0.8)/0.5,1))',"
            # Server name glow layer
            f"drawtext=text='{escaped_server}':fontsize=65:fontcolor={accent_color}@0.3{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+35:shadowcolor={accent_color}@0.25:shadowx=6:shadowy=6:"
            f"alpha='if(lt(t,1),0,if(lt(t,1.7),(t-1)/0.7,1))',"
            # Server name main text
            f"drawtext=text='{escaped_server}':fontsize=62:fontcolor=white{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+37:shadowcolor={accent_color}@0.5:shadowx=0:shadowy=0:"
            f"alpha='if(lt(t,1),0,if(lt(t,1.7),(t-1)/0.7,1))',"
            # Fades
            f"fade=t=in:st=0:d=0.8,fade=t=out:st={duration-0.8}:d=0.8"
        )
        
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent_color)
    
    def _generate_minimal_coming_soon(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str,
        accent_color: str,
        language: str = 'en'
    ) -> Optional[str]:
        """Generate elegant minimal style"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('segoe')
        
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Calculate positions based on actual dimensions
        line_x = width // 4
        line_w = width // 2
        line_y_top = (height // 2) - 70
        line_y_bottom = (height // 2) + 70
        
        # Minimal: clean typography with subtle animations
        filter_str = (
            # Thin decorative line
            f"drawbox=x={line_x}:y={line_y_top}:w={line_w}:h=1:c={accent_color}@0.5:t=fill,"
            # Main text - elegant fade in
            f"drawtext=text='{coming_soon_text}':fontsize=55:fontcolor={text_color}{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-45:alpha='if(lt(t,0.3),0,if(lt(t,1),(t-0.3)/0.7,1))',"
            # Server name
            f"drawtext=text='{to_text} {escaped_server}':fontsize=35:fontcolor={accent_color}{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+20:alpha='if(lt(t,0.8),0,if(lt(t,1.5),(t-0.8)/0.7,1))',"
            # Bottom decorative line
            f"drawbox=x={line_x}:y={line_y_bottom}:w={line_w}:h=1:c={accent_color}@0.5:t=fill,"
            # Fades
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.7}:d=0.7"
        )
        
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent_color)
    
    def _generate_enhanced_simple(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str,
        accent_color: str,
        style: str = "default",
        language: str = 'en'
    ) -> Optional[str]:
        """Enhanced fallback that still looks good but uses simpler filters"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Simple but visually appealing filter (no color= prefix, handled by _run_ffmpeg_simple)
        filter_str = (
            # Shadow/glow layer
            f"drawtext=text='{coming_soon_text}':fontsize=82:fontcolor={accent_color}@0.3{bold_font_param}:"
            f"x=(w-text_w)/2+3:y=(h/2)-97:shadowcolor={accent_color}@0.2:shadowx=5:shadowy=5,"
            # Main title
            f"drawtext=text='{coming_soon_text}':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor=black@0.7:shadowx=3:shadowy=3,"
            # "to"
            f"drawtext=text='{to_text}':fontsize=42:fontcolor={text_color}@0.8{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-10,"
            # Server name glow
            f"drawtext=text='{escaped_server}':fontsize=62:fontcolor={accent_color}@0.4{bold_font_param}:"
            f"x=(w-text_w)/2+2:y=(h/2)+47:shadowcolor={accent_color}@0.3:shadowx=4:shadowy=4,"
            # Server name
            f"drawtext=text='{escaped_server}':fontsize=60:fontcolor={accent_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)+45:shadowcolor=black@0.5:shadowx=2:shadowy=2,"
            # Fades
            f"fade=t=in:st=0:d=0.8,fade=t=out:st={duration-0.8}:d=0.8"
        )
        
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent_color)
    
    def _run_ffmpeg_with_gradient(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str, 
                           primary_color: str = None, secondary_color: str = None) -> Optional[str]:
        """Run FFmpeg with cinematic multi-layer gradient background matching CSS preview"""
        _verbose_log(f"=== Starting FFmpeg with Gradient Background ===")
        _verbose_log(f"Output path: {output_path}")
        _verbose_log(f"Duration: {duration}s, Resolution: {width}x{height}")
        _verbose_log(f"Colors - BG: {bg_color}, Primary: {primary_color}, Secondary: {secondary_color}")
        
        # Parse colors
        bg_hex = bg_color.replace('0x', '').replace('#', '')
        primary_hex = (primary_color or 'ffffff').replace('0x', '').replace('#', '')
        secondary_hex = (secondary_color or '00d4ff').replace('0x', '').replace('#', '')
        
        _verbose_log(f"Parsed hex - BG: {bg_hex}, Primary: {primary_hex}, Secondary: {secondary_hex}")
        
        try:
            # Background color (slightly brightened for center glow)
            r = int(bg_hex[0:2], 16)
            g = int(bg_hex[2:4], 16)
            b = int(bg_hex[4:6], 16)
            r2 = min(255, int(r * 1.8) + 20)
            g2 = min(255, int(g * 1.8) + 20)
            b2 = min(255, int(b * 1.8) + 20)
            bright_bg = f"0x{r2:02x}{g2:02x}{b2:02x}"
            
            # Parse secondary color for accent orbs (like CSS radial-gradient spots)
            sr = int(secondary_hex[0:2], 16)
            sg = int(secondary_hex[2:4], 16)
            sb = int(secondary_hex[4:6], 16)
            
            _verbose_log(f"Brightened BG: {bright_bg} (from RGB {r},{g},{b} to {r2},{g2},{b2})")
            _verbose_log(f"Secondary RGB for orbs: {sr},{sg},{sb}")
        except Exception as color_err:
            _verbose_log(f"Color parsing error: {color_err}, using fallbacks")
            bright_bg = bg_color
            sr, sg, sb = 0, 212, 255  # fallback cyan
        
        # Create gradient with colored orbs using geq filter
        # This simulates the CSS: radial-gradient(circle at 20% 30%, color 0%, transparent 50%)
        # Using soft radial falloff formulas
        geq_r = f"r(X,Y)*0.9 + {sr}*0.12*exp(-((X-W*0.2)*(X-W*0.2)+(Y-H*0.3)*(Y-H*0.3))/(W*W*0.08)) + {sr}*0.08*exp(-((X-W*0.8)*(X-W*0.8)+(Y-H*0.7)*(Y-H*0.7))/(W*W*0.1))"
        geq_g = f"g(X,Y)*0.9 + {sg}*0.12*exp(-((X-W*0.2)*(X-W*0.2)+(Y-H*0.3)*(Y-H*0.3))/(W*W*0.08)) + {sg}*0.08*exp(-((X-W*0.8)*(X-W*0.8)+(Y-H*0.7)*(Y-H*0.7))/(W*W*0.1))"
        geq_b = f"b(X,Y)*0.9 + {sb}*0.12*exp(-((X-W*0.2)*(X-W*0.2)+(Y-H*0.3)*(Y-H*0.3))/(W*W*0.08)) + {sb}*0.08*exp(-((X-W*0.8)*(X-W*0.8)+(Y-H*0.7)*(Y-H*0.7))/(W*W*0.1))"
        
        # Build filter: colored orbs → vignette → text
        gradient_filter = f"geq=r='{geq_r}':g='{geq_g}':b='{geq_b}',vignette=PI/4:0.5,{filter_str}"
        
        _verbose_log(f"Filter chain length: {len(gradient_filter)} chars")
        _verbose_log(f"Filter preview: {gradient_filter[:200]}...")
        
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'lavfi',
            '-i', f'color=c={bright_bg}:s={width}x{height}:d={duration}:r=30',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=48000:cl=stereo:d={duration}',
            '-vf', gradient_filter,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '20',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
        
        _verbose_log(f"FFmpeg command: {' '.join(cmd[:8])}... (truncated)")
        
        try:
            logger.info(f"Running FFmpeg with multi-layer gradient background...")
            _verbose_log("Executing FFmpeg gradient command...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            
            _verbose_log(f"FFmpeg return code: {result.returncode}")
            if result.stdout:
                _verbose_log(f"FFmpeg stdout: {result.stdout[:500]}")
            if result.stderr:
                _verbose_log(f"FFmpeg stderr: {result.stderr[:500]}")
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                _verbose_log(f"SUCCESS! Generated file: {output_path} ({file_size} bytes)")
                logger.info(f"Successfully generated with gradient: {output_path}")
                return str(output_path)
            else:
                _verbose_log(f"FAILED! Gradient method failed, trying vignette fallback...")
                logger.warning(f"Gradient method failed: {result.stderr[:500] if result.stderr else 'no error'}")
                # Try simpler vignette-only fallback
                return self._run_ffmpeg_vignette_fallback(filter_str, output_path, duration, width, height, bg_color)
        except Exception as e:
            _verbose_log(f"EXCEPTION: {e}")
            logger.error(f"FFmpeg gradient error: {e}")
            return self._run_ffmpeg_vignette_fallback(filter_str, output_path, duration, width, height, bg_color)
    
    def _render_theme_backdrop_png(self, theme_id: str, palette: dict, width: int, height: int):
        """Bake the theme's own backdrop to a still for FFmpeg to loop.

        The effect is drawn by backend/theme_backdrop.py, which mirrors the
        preview's renderer, so a themed list sits on the same aurora / grid /
        orbital treatment the preview shows rather than a flat wash. Returns
        None when Pillow is unavailable, and the caller falls back to the plain
        background colour.
        """
        try:
            from backend import theme_backdrop
        except ImportError:
            try:
                import theme_backdrop
            except ImportError:
                return None
        out = self.output_dir / f"_backdrop_{theme_id}_{width}x{height}.png"
        return theme_backdrop.render_backdrop(
            out,
            effect=palette.get('effect', 'orbital'),
            bg=palette.get('bg'),
            primary=palette.get('primary'),
            secondary=palette.get('secondary'),
            accent=palette.get('accent'),
            width=width,
            height=height,
        )

    def _run_ffmpeg_vignette_fallback(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str,
                           include_audio: bool = False,
                           custom_audio_path: str = None,
                           custom_logo_path: str = None,
                           logo_mode: str = "watermark",
                           fade_duration: float = 0,
                           output_width: int = None,
                           output_height: int = None,
                           frame_rate: int = 30,
                           video_preset: str = 'fast',
                           video_crf: int = 20,
                           audio_bitrate: str = '192k',
                           background_image: str = None,
                           background_video: str = None,
                           backdrop_dim: Any = 0) -> Optional[str]:
        """Fallback: Run FFmpeg with simple vignette (no colored orbs).
        Supports optional custom logo (faded, centered, behind text) and
        custom audio with auto fade in/out.
        logo_mode: 'watermark' = faded centered behind text, 'replace' = replaces server name text.
        fade_duration: if > 0, applies video fade in/out after all overlays (logo + text fade together)."""
        _verbose_log(f"=== VIGNETTE FALLBACK ===")
        _verbose_log(f"BG color: {bg_color}, Include audio: {include_audio}, Logo: {custom_logo_path}")
        output_width = output_width or width
        output_height = output_height or height
        
        bg_hex = bg_color.replace('0x', '').replace('#', '')
        try:
            r = int(bg_hex[0:2], 16)
            g = int(bg_hex[2:4], 16)
            b = int(bg_hex[4:6], 16)
            r2 = min(255, int(r * 2.0) + 25)
            g2 = min(255, int(g * 2.0) + 25)
            b2 = min(255, int(b * 2.0) + 25)
            bright_bg = f"0x{r2:02x}{g2:02x}{b2:02x}"
            _verbose_log(f"Brightened BG: {bright_bg}")
        except Exception as e:
            _verbose_log(f"Color parse error: {e}, using original")
            bright_bg = bg_color
        
        # A themed backdrop already carries its own vignette from the Pillow
        # render; applying FFmpeg's on top darkens the corners twice and eats
        # the effect's detail at the edges.
        if background_video and os.path.isfile(str(background_video)):
            # A backdrop can arrive at any resolution or aspect: a recorded theme
            # matches the layout, someone's own footage very often does not.
            vignette_filter = f"{backdrop_video_chain(width, height, backdrop_dim)},{filter_str}"
        elif background_image and os.path.isfile(str(background_image)):
            vignette_filter = filter_str
        else:
            vignette_filter = f"vignette=PI/3.5:0.6,{filter_str}"
        
        # Determine audio source
        audio_file = None
        if include_audio:
            audio_file = self._get_coming_soon_audio_path(custom_audio_path=custom_audio_path)
        
        # Determine if we have a logo
        has_logo = custom_logo_path and os.path.isfile(custom_logo_path)
        
        cmd = [
            self.ffmpeg_path,
            '-y',
        ]
        if background_video and os.path.isfile(str(background_video)):
            # The animated backdrop recorded in the browser. Looped in case it
            # is shorter than the clip, and trimmed to length either way.
            cmd.extend(['-stream_loop', '-1', '-t', str(duration), '-i', str(background_video)])
        elif background_image and os.path.isfile(str(background_image)):
            # A themed backdrop still, looped for the clip's length.
            cmd.extend(['-loop', '1', '-t', str(duration), '-r', str(frame_rate), '-i', str(background_image)])
        else:
            cmd.extend(['-f', 'lavfi',
                        '-i', f'color=c={bright_bg}:s={width}x{height}:d={duration}:r={frame_rate}'])
        
        # Track input indices: 0 = color background
        next_input = 1
        logo_index = None
        audio_index = None
        
        if has_logo:
            logo_index = next_input
            cmd.extend(['-i', custom_logo_path])
            next_input += 1
        
        if audio_file:
            audio_index = next_input
            cmd.extend(['-i', audio_file])
            next_input += 1
        else:
            # Silent audio fallback
            audio_index = next_input
            cmd.extend(['-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo:d={duration}'])
            next_input += 1
        
        # Build filter_complex
        filter_parts = []
        
        # Apply vignette + text to background
        filter_parts.append(f"[0:v]{vignette_filter}[vout]")

        if has_logo:
            if logo_mode == 'right':
                # Right mode: the logo sits in the right quarter and the heading
                # is centred in the left two thirds (see the drawtext x below),
                # so the two occupy separate bands. The old fixed (W/2)+200 put
                # a 25%-wide logo at x=1160 while the 80px heading ran to about
                # x=1295, overlapping it -- and worse for longer translations.
                logo_w = int(width * 0.20)
                logo_opacity = 0.85
                logo_y_pos = 50  # Same height as header text
                logo_x_expr = f'{int(width * 0.60)}'
                _verbose_log(f"Logo RIGHT mode: width={logo_w}, opacity={logo_opacity}, x={int(width * 0.60)}")
            elif logo_mode in ('below', 'replace'):
                # Below mode: logo below "COMING SOON TO" header, higher opacity
                logo_w = int(width * 0.25)
                logo_opacity = 0.85
                logo_y_pos = 175  # Below the header text
                logo_x_expr = '(W-w)/2'  # Centered
                _verbose_log(f"Logo BELOW mode: width={logo_w}, opacity={logo_opacity}, y={logo_y_pos}")
            else:
                # Watermark mode: faded centered behind text
                logo_w = int(width * 0.30)
                logo_opacity = 0.15
                logo_y_pos = None  # Will use centered overlay
                logo_x_expr = '(W-w)/2'
            filter_parts.append(
                f"[{logo_index}:v]scale={logo_w}:-1,format=rgba,"
                f"colorchannelmixer=aa={logo_opacity}[logo]"
            )
            if logo_y_pos is not None:
                filter_parts.append(f"[vout][logo]overlay={logo_x_expr}:{logo_y_pos}[vcomp]")
            else:
                filter_parts.append(f"[vout][logo]overlay=(W-w)/2:(H-h)/2[vcomp]")
            # Apply fade after overlay so logo + video fade together
            if fade_duration > 0:
                filter_parts.append(f"[vcomp]fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration-fade_duration}:d={fade_duration}[vfinal]")
                video_label = "[vfinal]"
            else:
                video_label = "[vcomp]"
        else:
            # No logo — apply fade directly to vout if needed
            if fade_duration > 0:
                filter_parts.append(f"[vout]fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration-fade_duration}:d={fade_duration}[vfinal]")
                video_label = "[vfinal]"
            else:
                video_label = "[vout]"
        
        if audio_file:
            # Real audio with fade in/out
            fade_duration = 1.5
            fade_out_start = max(0, duration - fade_duration)
            filter_parts.append(
                f"[{audio_index}:a]atrim=0:{duration},"
                f"afade=t=in:d={fade_duration},"
                f"afade=t=out:st={fade_out_start}:d={fade_duration},"
                f"asetpts=PTS-STARTPTS[aout]"
            )
            audio_map = "[aout]"
        else:
            audio_map = f"{audio_index}:a"

        if output_width != width or output_height != height:
            filter_parts.append(
                f"{video_label}scale={output_width}:{output_height}:flags=lanczos,"
                "format=yuv420p[vscaled]"
            )
            video_label = "[vscaled]"
        
        filter_complex_str = ";".join(filter_parts)
        
        cmd.extend([
            '-filter_complex', filter_complex_str,
            '-map', video_label,
            '-map', audio_map,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', video_preset,
            '-crf', str(video_crf),
            '-profile:v', 'high',
            '-level', '5.2' if output_width >= 3840 or frame_rate >= 60 else '4.1',
            '-c:a', 'aac',
            '-b:a', audio_bitrate,
            '-shortest',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ])
        
        try:
            logger.info(f"Running FFmpeg vignette fallback...")
            _verbose_log("Executing vignette FFmpeg command...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300 if output_width >= 3840 else 180,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            
            _verbose_log(f"Vignette return code: {result.returncode}")
            if result.stderr:
                _verbose_log(f"Vignette stderr: {result.stderr[:300]}")
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                _verbose_log(f"VIGNETTE SUCCESS! File: {output_path} ({file_size} bytes)")
                logger.info(f"Successfully generated with vignette: {output_path}")
                return str(output_path)
            else:
                _verbose_log(f"VIGNETTE FAILED! Trying simple fallback...")
                logger.warning(f"Vignette fallback failed: {result.stderr[:300] if result.stderr else 'no error'}")
                return self._run_ffmpeg_simple_fallback(
                    filter_str, output_path, duration, width, height, bg_color,
                    output_width=output_width,
                    output_height=output_height,
                    frame_rate=frame_rate,
                    video_preset=video_preset,
                    video_crf=video_crf,
                    audio_bitrate=audio_bitrate,
                )
        except Exception as e:
            _verbose_log(f"VIGNETTE EXCEPTION: {e}")
            logger.error(f"FFmpeg vignette error: {e}")
            return self._run_ffmpeg_simple_fallback(
                filter_str, output_path, duration, width, height, bg_color,
                output_width=output_width,
                output_height=output_height,
                frame_rate=frame_rate,
                video_preset=video_preset,
                video_crf=video_crf,
                audio_bitrate=audio_bitrate,
            )
    
    def _run_ffmpeg_simple_fallback(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str,
                           output_width: int = None,
                           output_height: int = None,
                           frame_rate: int = 30,
                           video_preset: str = 'fast',
                           video_crf: int = 20,
                           audio_bitrate: str = '192k') -> Optional[str]:
        """Fallback: Run FFmpeg with simple solid color background"""
        _verbose_log(f"=== SIMPLE FALLBACK (solid color) ===")
        _verbose_log(f"BG color: {bg_color}")
        output_width = output_width or width
        output_height = output_height or height
        output_filter = filter_str
        if output_width != width or output_height != height:
            output_filter += f",scale={output_width}:{output_height}:flags=lanczos"
        
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'lavfi',
            '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r={frame_rate}',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=48000:cl=stereo:d={duration}',
            '-vf', output_filter,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', video_preset,
            '-crf', str(video_crf),
            '-profile:v', 'high',
            '-level', '5.2' if output_width >= 3840 or frame_rate >= 60 else '4.1',
            '-c:a', 'aac',
            '-b:a', audio_bitrate,
            '-shortest',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
        
        try:
            logger.info(f"Running FFmpeg (fallback simple): {' '.join(cmd[:10])}...")
            _verbose_log("Executing simple fallback FFmpeg command...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300 if output_width >= 3840 else 180,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            
            _verbose_log(f"Simple fallback return code: {result.returncode}")
            if result.stderr:
                _verbose_log(f"Simple fallback stderr: {result.stderr[:300]}")
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                _verbose_log(f"SIMPLE FALLBACK SUCCESS! File: {output_path} ({file_size} bytes)")
                logger.info(f"Successfully generated (fallback): {output_path}")
                return str(output_path)
            else:
                _verbose_log(f"SIMPLE FALLBACK FAILED!")
                logger.error(f"FFmpeg fallback error: {result.stderr}")
        except Exception as e:
            _verbose_log(f"SIMPLE FALLBACK EXCEPTION: {e}")
            logger.error(f"FFmpeg fallback execution error: {e}")
        
        return None
    
    def _run_ffmpeg_simple(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str) -> Optional[str]:
        """Compatibility wrapper - uses vignette fallback for calls without accent colors"""
        return self._run_ffmpeg_vignette_fallback(filter_str, output_path, duration, width, height, bg_color)
    
    def generate_feature_presentation(
        self,
        server_name: str = "",
        duration: float = 5.0,
        output_filename: str = "feature_presentation_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        bg_color: str = "0x0a0a0a",
        text_color: str = "0xffd700",  # Gold
        style: str = "classic",
        theme: str = "midnight",
        language: str = 'en'
    ) -> Optional[str]:
        """Generate "Feature Presentation" intro with different styles"""
        if not self.is_available():
            return None
        
        if not self.output_dir:
            return None
        
        # Apply theme colors if specified
        if theme in self.COLOR_THEMES:
            colors = self.COLOR_THEMES[theme]
            bg_color = colors['bg']
            text_color = colors['primary']
        
        if style == 'modern':
            return self._generate_modern_feature_presentation(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, theme, language
            )
        else:
            return self._generate_classic_feature_presentation(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, language
            )
    
    def _generate_classic_feature_presentation(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str,
        language: str = 'en'
    ) -> Optional[str]:
        """Classic theater-style Feature Presentation"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name) if server_name else ""
        
        _, font_param = self._get_font_path('georgia')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        feature_presentation_text = self._escape_text(self._get_text('feature_presentation', language))
        at_text = self._escape_text(self._get_text('at', language))
        
        # Pre-calculate positions
        line_x = width // 5
        line_w = (width * 3) // 5
        top_line_y = (height // 2) - 120
        top_diamond_y = (height // 2) - 125
        bottom_line_y = (height // 2) + 80
        bottom_diamond_y = (height // 2) + 75
        right_diamond_x = (width * 4) // 5 + 2
        
        # Classic style with curtain-like feel and golden text
        filter_parts = [
            # Decorative top line
            f"drawbox=x={line_x}:y={top_line_y}:w={line_w}:h=2:c={text_color}@0.6:t=fill",
            # Decorative star/diamond shapes (using boxes)
            f"drawbox=x={line_x - 10}:y={top_diamond_y}:w=8:h=8:c={text_color}@0.8:t=fill",
            f"drawbox=x={right_diamond_x}:y={top_diamond_y}:w=8:h=8:c={text_color}@0.8:t=fill",
            # Outer glow for main text
            f"drawtext=text='{feature_presentation_text}':fontsize=67:fontcolor={text_color}@0.3{bold_font_param}:x=(w-text_w)/2:y=(h/2)-55:shadowcolor={text_color}@0.2:shadowx=6:shadowy=6",
            # Main text
            f"drawtext=text='{feature_presentation_text}':fontsize=65:fontcolor={text_color}{bold_font_param}:x=(w-text_w)/2:y=(h/2)-55:shadowcolor=black@0.7:shadowx=3:shadowy=3",
        ]
        
        if escaped_server:
            filter_parts.extend([
                f"drawtext=text='{at_text} {escaped_server}':fontsize=32:fontcolor=white@0.8{font_param}:x=(w-text_w)/2:y=(h/2)+30:alpha='if(lt(t,1),0,if(lt(t,1.8),(t-1)/0.8,1))'"
            ])
        
        # Bottom decorative line
        filter_parts.append(f"drawbox=x={line_x}:y={bottom_line_y}:w={line_w}:h=2:c={text_color}@0.6:t=fill")
        filter_parts.append(f"drawbox=x={line_x - 10}:y={bottom_diamond_y}:w=8:h=8:c={text_color}@0.8:t=fill")
        filter_parts.append(f"drawbox=x={right_diamond_x}:y={bottom_diamond_y}:w=8:h=8:c={text_color}@0.8:t=fill")
        
        # Fade effects
        filter_parts.append(f"fade=t=in:st=0:d=1,fade=t=out:st={duration-1}:d=1")
        
        filter_str = ','.join(filter_parts)
        # Use gradient with text_color as accent for the orbs
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, text_color)
    
    def _generate_modern_feature_presentation(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str = "0x0d0d1a",
        text_color: str = "0xffffff",
        theme: str = "midnight",
        language: str = 'en'
    ) -> Optional[str]:
        """Modern sleek Feature Presentation style"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name) if server_name else ""
        
        _, font_param = self._get_font_path('segoe')
        _, bold_font_param = self._get_font_path('segoe_bold')
        
        # Apply theme colors
        if theme in self.COLOR_THEMES:
            colors = self.COLOR_THEMES[theme]
            bg_color = colors['bg']
            accent = colors['primary']
            text_color = colors.get('secondary', '0xffffff')
        else:
            accent = "0x6366f1"  # Indigo default
        
        feature_text = self._escape_text(self._get_text('feature', language))
        presentation_text = self._escape_text(self._get_text('presentation', language))
        
        # Pre-calculate positions
        gradient_y_1 = height - 100
        gradient_y_2 = height - 80
        
        filter_parts = [
            # Gradient-like effect with multiple boxes
            f"drawbox=x=0:y={gradient_y_1}:w={width}:h=100:c={accent}@0.1:t=fill",
            f"drawbox=x=0:y={gradient_y_2}:w={width}:h=80:c={accent}@0.05:t=fill",
            # Main text with modern feel
            f"drawtext=text='{feature_text}':fontsize=90:fontcolor=white{bold_font_param}:x=(w-text_w)/2:y=(h/2)-80",
            f"drawtext=text='{presentation_text}':fontsize=45:fontcolor={accent}{font_param}:x=(w-text_w)/2:y=(h/2)+10:alpha='if(lt(t,0.5),0,if(lt(t,1.2),(t-0.5)/0.7,1))'",
        ]
        
        if escaped_server:
            filter_parts.append(
                f"drawtext=text='{escaped_server}':fontsize=28:fontcolor=white@0.6{font_param}:x=(w-text_w)/2:y=(h/2)+70:alpha='if(lt(t,1.2),0,if(lt(t,2),(t-1.2)/0.8,1))'"
            )
        
        filter_parts.append(f"fade=t=in:st=0:d=0.7,fade=t=out:st={duration-0.7}:d=0.7")
        
        filter_str = ','.join(filter_parts)
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent)
    
    def generate_now_showing(
        self,
        server_name: str = "",
        duration: float = 4.0,
        output_filename: str = "now_showing_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        theme: str = "midnight",
        language: str = 'en'
    ) -> Optional[str]:
        """Generate retro "Now Showing" style with film grain"""
        if not self.is_available() or not self.output_dir:
            return None
        
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name) if server_name else ""
        
        _, font_param = self._get_font_path('impact')
        _, regular_font = self._get_font_path('arial')
        
        # Default colors (retro sepia style)
        bg_color = "0x1a1208"  # Warm sepia-ish
        text_color = "0xf4e8c1"  # Cream/tan
        accent = "0xd4a574"  # Copper/bronze
        
        # Apply theme colors if specified
        if theme in self.COLOR_THEMES:
            colors = self.COLOR_THEMES[theme]
            bg_color = colors['bg']
            text_color = colors['primary']
            accent = colors['secondary']
        
        now_showing_text = self._escape_text(self._get_text('now_showing', language))
        at_text = self._escape_text(self._get_text('at', language))
        
        # Pre-calculate positions
        vignette_right_x = width - 100
        underline_x = (width // 2) - 150
        underline_y = (height // 2) + 20
        
        filter_parts = [
            # Film grain effect
            "noise=c0s=15:c0f=t+u",
            # Vignette-like darkening at edges (using overlapping boxes)
            f"drawbox=x=0:y=0:w=100:h={height}:c=black@0.3:t=fill",
            f"drawbox=x={vignette_right_x}:y=0:w=100:h={height}:c=black@0.3:t=fill",
            # Main "NOW SHOWING" text
            f"drawtext=text='{now_showing_text}':fontsize=95:fontcolor={text_color}{font_param}:x=(w-text_w)/2:y=(h/2)-70:shadowcolor=black@0.8:shadowx=4:shadowy=4",
            # Decorative underline
            f"drawbox=x={underline_x}:y={underline_y}:w=300:h=3:c={accent}:t=fill",
        ]
        
        if escaped_server:
            filter_parts.append(
                f"drawtext=text='{at_text} {escaped_server}':fontsize=35:fontcolor={accent}{regular_font}:x=(w-text_w)/2:y=(h/2)+50"
            )
        
        # Fades (removed flicker effect that was causing issues)
        filter_parts.append(f"fade=t=in:st=0:d=0.6,fade=t=out:st={duration-0.6}:d=0.6")
        
        filter_str = ','.join(filter_parts)
        return self._run_ffmpeg_with_gradient(filter_str, output_path, duration, width, height, bg_color, text_color, accent)
    
    def generate_custom_text(
        self,
        headline: str,
        subtext: str = "",
        duration: float = 5,
        output_filename: str = "custom_text_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        theme: str = "midnight",
    ) -> Optional[str]:
        """Generate a preroll carrying the operator's own wording.

        Unlike the other templates there is no fixed phrase and nothing to
        translate — whatever is typed is what renders, so this covers the cases
        the fixed templates cannot ("Back in 5 minutes", a house rule, an
        announcement).
        """
        if not self.is_available() or not self.output_dir:
            return None

        output_path = self.output_dir / output_filename

        colors = self.COLOR_THEMES.get(theme, self.COLOR_THEMES['midnight'])
        bg_color = colors['bg']
        text_color = colors['primary']
        accent = colors['secondary']

        headline_text = self._escape_text((headline or '').strip())
        subtext_text = self._escape_text((subtext or '').strip())
        if not headline_text and not subtext_text:
            logger.error("custom_text: nothing to render (no headline or subtext)")
            return None

        _, font_param = self._get_font_path('impact')
        _, regular_font = self._get_font_path('arial')

        # One line centres; two lines straddle the centre so the block stays
        # optically balanced either way. drawtext y is the top of the glyph box,
        # so the headline needs its full 96px clear of the divider rule.
        filter_parts = []
        if headline_text and subtext_text:
            headline_y, subtext_y = "(h/2)-135", "(h/2)+40"
        else:
            headline_y, subtext_y = "(h-text_h)/2", "(h-text_h)/2"

        if headline_text:
            filter_parts.append(
                f"drawtext=text='{headline_text}':fontsize=96:fontcolor={text_color}{font_param}"
                f":x=(w-text_w)/2:y={headline_y}:shadowcolor=black@0.8:shadowx=4:shadowy=4"
            )
        if subtext_text:
            filter_parts.append(
                f"drawtext=text='{subtext_text}':fontsize=44:fontcolor={accent}{regular_font}"
                f":x=(w-text_w)/2:y={subtext_y}"
            )
        if headline_text and subtext_text:
            rule_x = (width // 2) - 160
            filter_parts.append(f"drawbox=x={rule_x}:y={(height // 2) - 5}:w=320:h=3:c={accent}:t=fill")

        filter_parts.append(f"fade=t=in:st=0:d=0.6,fade=t=out:st={duration - 0.6}:d=0.6")
        filter_str = ','.join(filter_parts)
        return self._run_ffmpeg_with_gradient(
            filter_str, output_path, duration, width, height, bg_color, text_color, accent
        )

    def _render_qr_png(self, data: str, target_px: int = 620) -> Optional[Path]:
        """Render `data` to a QR PNG and return its path, or None on failure.

        Written with a quiet zone and no anti-aliasing so it survives video
        compression — a blurred QR is an unscannable QR.
        """
        try:
            import segno
        except ImportError:
            logger.error("QR template needs the 'segno' package (see requirements.txt)")
            return None
        if not (data or '').strip():
            logger.error("QR template: no data to encode")
            return None
        try:
            qr_path = self.output_dir / f"_qr_{abs(hash(data)) & 0xFFFFFFFF:08x}.png"
            qr = segno.make(data.strip(), error='h')
            # scale is per module; derive it so the finished image lands near
            # target_px regardless of how dense the payload made the matrix.
            modules = qr.symbol_size(border=4)[0]
            scale = max(2, int(target_px / max(1, modules)))
            qr.save(str(qr_path), scale=scale, border=4, dark='#000000', light='#ffffff')
            return qr_path
        except Exception as e:
            logger.error(f"QR render failed: {e}")
            return None

    def generate_qr_share(
        self,
        qr_data: str,
        caption: str = "",
        duration: float = 8,
        output_filename: str = "qr_share_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        theme: str = "midnight",
    ) -> Optional[str]:
        """Generate a preroll showing a scannable QR code plus a caption.

        Defaults to a longer duration than the other templates because a viewer
        has to notice it, reach for a phone, and focus before it disappears.
        """
        if not self.is_available() or not self.output_dir:
            return None

        qr_path = self._render_qr_png(qr_data)
        if not qr_path:
            return None

        output_path = self.output_dir / output_filename
        colors = self.COLOR_THEMES.get(theme, self.COLOR_THEMES['midnight'])
        bg_color = colors['bg']
        text_color = colors['primary']

        caption_text = self._escape_text((caption or '').strip())
        _, font_param = self._get_font_path('impact')

        bg_hex = str(bg_color).replace('0x', '').replace('#', '')
        qr_size = 620
        qr_y = (height - qr_size) // 2 - 60
        # A white plate behind the QR keeps quiet-zone contrast on dark themes,
        # which scanners need.
        plate_pad = 26
        plate_x = (width - qr_size) // 2 - plate_pad
        plate_y = qr_y - plate_pad
        plate_size = qr_size + plate_pad * 2

        filters = [
            f"[0:v]drawbox=x={plate_x}:y={plate_y}:w={plate_size}:h={plate_size}:c=white:t=fill[plate]",
            f"[1:v]scale={qr_size}:{qr_size}:flags=neighbor[qr]",
            f"[plate][qr]overlay=(W-w)/2:{qr_y}[withqr]",
        ]
        last = "withqr"
        if caption_text:
            filters.append(
                f"[{last}]drawtext=text='{caption_text}':fontsize=64:fontcolor={text_color}{font_param}"
                f":x=(w-text_w)/2:y={qr_y + plate_size + 40}:shadowcolor=black@0.8:shadowx=3:shadowy=3[capped]"
            )
            last = "capped"
        filters.append(f"[{last}]fade=t=in:st=0:d=0.6,fade=t=out:st={duration - 0.6}:d=0.6[vout]")

        cmd = [
            self.ffmpeg_path, '-y',
            '-f', 'lavfi', '-i', f"color=c=0x{bg_hex}:s={width}x{height}:d={duration}:r=30",
            '-i', str(qr_path),
            '-f', 'lavfi', '-i', f"anullsrc=r=48000:cl=stereo:d={duration}",
            '-filter_complex', ';'.join(filters),
            '-map', '[vout]', '-map', '2:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-c:a', 'aac', '-b:a', '128k', '-shortest',
            '-pix_fmt', 'yuv420p', '-t', str(duration),
            str(output_path)
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=180,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            if result.returncode != 0 or not output_path.exists():
                logger.error(f"QR preroll FFmpeg failed: {(result.stderr or '')[-500:]}")
                return None
            return str(output_path)
        except Exception as e:
            logger.error(f"QR preroll generation failed: {e}")
            return None
        finally:
            try:
                qr_path.unlink()
            except Exception:
                pass

    def generate_from_template(
        self,
        template_id: str,
        variables: Dict[str, str],
        duration: float = None,
        output_filename: Optional[str] = None,
        theme: str = "midnight",
        language: str = 'en'
    ) -> Optional[str]:
        """
        Generate a preroll from a template with variables.
        
        Args:
            template_id: Template identifier (e.g., 'coming_soon_cinematic')
            variables: Dict of variable values
            duration: Video duration in seconds (optional, uses template default)
            output_filename: Optional custom filename
            theme: Color theme to use
        """
        if template_id not in self.TEMPLATES:
            logger.error(f"Unknown template: {template_id}")
            return None
        
        template = self.TEMPLATES[template_id]
        
        # Merge default values with provided variables
        final_vars = template['default_values'].copy()
        final_vars.update(variables)
        
        # Use provided duration or template default
        if duration is None:
            duration = template.get('duration', 5)
        
        if output_filename is None:
            output_filename = f"{template_id}_preroll.mp4"
        
        server_name = final_vars.get('server_name', 'Your Server')
        style = template.get('style', 'cinematic')
        
        # Route to appropriate generator based on template
        if template_id.startswith('coming_soon'):
            return self.generate_coming_soon(
                server_name=server_name,
                duration=duration,
                output_filename=output_filename,
                style=style,
                theme=theme,
                language=language
            )
        elif template_id.startswith('feature_presentation'):
            return self.generate_feature_presentation(
                server_name=server_name,
                duration=duration,
                output_filename=output_filename,
                style=style,
                theme=theme,
                language=language
            )
        elif template_id == 'now_showing':
            return self.generate_now_showing(
                server_name=server_name,
                duration=duration,
                output_filename=output_filename,
                theme=theme,
                language=language
            )
        elif template_id == 'custom_text':
            return self.generate_custom_text(
                headline=final_vars.get('custom_headline', ''),
                subtext=final_vars.get('custom_subtext', ''),
                duration=duration,
                output_filename=output_filename,
                theme=theme
            )
        elif template_id == 'qr_share':
            return self.generate_qr_share(
                qr_data=final_vars.get('qr_data', ''),
                caption=final_vars.get('qr_caption', ''),
                duration=duration,
                output_filename=output_filename,
                theme=theme
            )

        return None
    
    def get_color_themes(self) -> Dict[str, Dict[str, Any]]:
        """Get available color themes"""
        return self.COLOR_THEMES.copy()
    
    def delete_generated(self, filename: str) -> bool:
        """Delete a generated preroll file"""
        file_path = self.output_dir / filename
        try:
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception as e:
            logger.error(f"Failed to delete {filename}: {e}")
        return False
    
    def generate_from_image(
        self,
        image_data: bytes,
        duration: float = 5.0,
        output_filename: str = "preview_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        fade_duration: float = 1.0,
        frame_rate: int = 30,
        video_preset: str = 'slow',
        video_crf: int = 15,
        audio_bitrate: str = '192k',
        audio_path: str = None,
    ) -> Optional[str]:
        """
        Generate a video from a still image with fade in/out effects.
        
        This is the "CSS preview to video" approach - takes a captured screenshot
        of the live CSS preview and turns it into a video with smooth fades.
        
        Args:
            image_data: PNG/JPEG image bytes (from canvas capture or screenshot)
            duration: Total video duration in seconds
            output_filename: Output filename
            width: Output video width (image will be scaled)
            height: Output video height (image will be scaled)
            fade_duration: Duration of fade in and fade out effects
            frame_rate: Output frames per second
            video_preset: FFmpeg x264 encoding preset
            video_crf: FFmpeg constant-rate-factor quality value
            audio_bitrate: AAC bitrate for the compatibility audio track
            
        Returns:
            Path to generated video or None on failure
        """
        if not self.is_available():
            logger.error("FFmpeg not available")
            return None
        
        if not self.output_dir:
            logger.error("Output directory not set")
            return None
        
        import tempfile
        import uuid
        
        _verbose_log(f"=== generate_from_image ===")
        _verbose_log(
            f"Duration: {duration}s, Fade: {fade_duration}s, Size: {width}x{height}, "
            f"FPS: {frame_rate}, Preset: {video_preset}, CRF: {video_crf}"
        )
        _verbose_log(f"Image data size: {len(image_data)} bytes")
        
        output_path = self.output_dir / output_filename
        
        # Save image to temp file
        temp_image = None
        try:
            # Create temp file for the input image
            temp_fd, temp_image = tempfile.mkstemp(suffix='.png')
            os.close(temp_fd)
            
            with open(temp_image, 'wb') as f:
                f.write(image_data)
            
            _verbose_log(f"Saved temp image: {temp_image}")
            
            # Calculate fade out start time (give some display time before fading out)
            fade_out_start = max(0, duration - fade_duration)
            
            # Build FFmpeg command:
            # - Loop the image for the duration
            # - Scale to exact target resolution with high-quality scaling
            # - Apply smooth fade in at start, fade out at end
            # - Use high-quality encoding settings
            
            # High-quality scaling and fade filter
            filter_complex = (
                f"[0:v]scale={width}:{height}:flags=lanczos,"  # High-quality Lanczos scaling
                f"format=yuv420p,"  # Ensure proper pixel format
                f"fade=t=in:st=0:d={fade_duration}:color=black,"  # Fade in from black
                f"fade=t=out:st={fade_out_start}:d={fade_duration}:color=black[v]"  # Fade out to black
            )
            
            cmd = [
                self.ffmpeg_path,
                '-y',  # Overwrite output
                '-loop', '1',  # Loop the image
                '-framerate', str(frame_rate),
                '-i', temp_image,  # Input image
            ]

            has_audio = bool(audio_path and os.path.isfile(audio_path))
            if has_audio:
                audio_fade = max(0.2, min(1.0, duration * 0.15))
                audio_fade_out = max(0, duration - audio_fade)
                cmd.extend(['-stream_loop', '-1', '-i', audio_path])
                filter_complex += (
                    f";[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d={audio_fade},"
                    f"afade=t=out:st={audio_fade_out}:d={audio_fade}[a]"
                )

            cmd.extend(['-filter_complex', filter_complex, '-map', '[v]'])
            if has_audio:
                cmd.extend(['-map', '[a]', '-c:a', 'aac', '-b:a', audio_bitrate, '-shortest'])
            else:
                cmd.append('-an')
            cmd.extend([
                '-t', str(duration),
                '-c:v', 'libx264',
                '-preset', video_preset,
                '-crf', str(video_crf),
                '-profile:v', 'high',  # High profile for better quality
                '-level', '5.2' if width >= 3840 or frame_rate >= 60 else '4.1',
                '-movflags', '+faststart',  # Web optimization
                str(output_path)
            ])
            
            _verbose_log(f"FFmpeg command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=240 if width >= 3840 else 120,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            
            _verbose_log(f"FFmpeg return code: {result.returncode}")
            if result.stderr:
                _verbose_log(f"FFmpeg stderr: {result.stderr[:500]}")
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                _verbose_log(f"SUCCESS! Generated: {output_path} ({file_size} bytes)")
                logger.info(f"Generated video from image: {output_path}")
                return str(output_path)
            else:
                _verbose_log(f"FAILED! Return code: {result.returncode}")
                logger.error(f"FFmpeg failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            _verbose_log("FFmpeg timed out!")
            logger.error("FFmpeg command timed out")
            return None
        except Exception as e:
            _verbose_log(f"Exception: {e}")
            logger.error(f"Error generating video from image: {e}")
            return None
        finally:
            # Clean up temp image
            if temp_image and os.path.exists(temp_image):
                try:
                    os.unlink(temp_image)
                    _verbose_log(f"Cleaned up temp image: {temp_image}")
                except:
                    pass

    def generate_from_video(
        self,
        video_data: bytes,
        duration: float = 5.0,
        output_filename: str = "preview_preroll.mp4",
        width: int = 1920,
        height: int = 1080,
        frame_rate: int = 30,
        video_preset: str = 'slow',
        video_crf: int = 15,
        audio_bitrate: str = '192k',
        audio_path: str = None,
    ) -> Optional[str]:
        """Transcode an animated browser-canvas recording into a delivery MP4."""
        if not self.is_available():
            logger.error("FFmpeg not available")
            return None
        if not self.output_dir:
            logger.error("Output directory not set")
            return None

        import tempfile

        output_path = self.output_dir / output_filename
        temp_video = None
        try:
            temp_fd, temp_video = tempfile.mkstemp(suffix='.webm')
            os.close(temp_fd)
            with open(temp_video, 'wb') as stream:
                stream.write(video_data)

            _verbose_log("=== generate_from_video ===")
            _verbose_log(
                f"Duration: {duration}s, Size: {width}x{height}, FPS: {frame_rate}, "
                f"Preset: {video_preset}, CRF: {video_crf}, Input: {len(video_data)} bytes"
            )

            # The browser recording already contains the exact shared preview motion.
            # Normalize its dimensions/cadence and pad the last frame if the recorder
            # finishes a fraction early, without layering a second animation over it.
            filter_complex = (
                f"[0:v]scale={width}:{height}:flags=lanczos,"
                f"fps={frame_rate},"
                f"tpad=stop_mode=clone:stop_duration=2,"
                f"trim=duration={duration},setpts=PTS-STARTPTS,"
                f"format=yuv420p[v]"
            )
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-i', temp_video,
            ]

            has_audio = bool(audio_path and os.path.isfile(audio_path))
            if has_audio:
                audio_fade = max(0.2, min(1.0, duration * 0.15))
                audio_fade_out = max(0, duration - audio_fade)
                cmd.extend(['-stream_loop', '-1', '-i', audio_path])
                filter_complex += (
                    f";[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d={audio_fade},"
                    f"afade=t=out:st={audio_fade_out}:d={audio_fade}[a]"
                )

            cmd.extend(['-filter_complex', filter_complex, '-map', '[v]'])
            if has_audio:
                cmd.extend(['-map', '[a]', '-c:a', 'aac', '-b:a', audio_bitrate, '-shortest'])
            else:
                cmd.append('-an')
            cmd.extend([
                '-t', str(duration),
                '-c:v', 'libx264',
                '-preset', video_preset,
                '-crf', str(video_crf),
                '-profile:v', 'high',
                '-level', '5.2' if width >= 3840 or frame_rate >= 60 else '4.1',
                '-movflags', '+faststart',
                str(output_path),
            ])
            _verbose_log(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300 if width >= 3840 else 180,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and output_path.exists():
                _verbose_log(f"SUCCESS! Generated animated preview: {output_path} ({output_path.stat().st_size} bytes)")
                logger.info(f"Generated video from animated canvas: {output_path}")
                return str(output_path)

            _verbose_log(f"FAILED! Return code: {result.returncode}")
            logger.error(f"FFmpeg animated preview transcode failed: {result.stderr}")
            return None
        except subprocess.TimeoutExpired:
            _verbose_log("Animated preview transcode timed out")
            logger.error("FFmpeg animated preview transcode timed out")
            return None
        except Exception as exc:
            _verbose_log(f"Animated preview transcode exception: {exc}")
            logger.error(f"Error generating video from animated preview: {exc}")
            return None
        finally:
            if temp_video and os.path.exists(temp_video):
                try:
                    os.unlink(temp_video)
                    _verbose_log(f"Cleaned up temp video: {temp_video}")
                except OSError:
                    pass

    # =========================================================================
    # COMING SOON LIST GENERATOR
    # =========================================================================
    
    def _get_coming_soon_audio_path(self, custom_audio_path: str = None) -> Optional[str]:
        """Get the path to the Coming Soon audio file. Prefers custom_audio_path if provided."""
        # 1) User-uploaded custom audio takes priority
        if custom_audio_path and os.path.isfile(custom_audio_path):
            _verbose_log(f"Using custom Coming Soon audio file: {custom_audio_path}")
            return custom_audio_path

        # 2) Bundled default
        # When running from PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            # When running from source - go up from backend/ to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        audio_path = os.path.join(base_dir, 'docs', 'lefty-blue-wednesday-main-version-36162-02-38.mp3')
        if os.path.isfile(audio_path):
            _verbose_log(f"Found Coming Soon audio file: {audio_path}")
            return audio_path
        
        _verbose_log(f"Coming Soon audio file not found at: {audio_path}")
        return None

    def _overlay_corner_qr(self, video_path: str, qr_data: str, corner: str = "bottom-right") -> Optional[str]:
        """Composite a QR code into a corner of an already-rendered video.

        Done as a second pass rather than inside the layout filter graphs: the
        grid and text layouts each build a long chain with their own optional
        poster and logo inputs, and threading another image through both is far
        more fragile than one short re-encode of the finished file.
        """
        if not (qr_data or '').strip():
            return video_path
        source = Path(video_path)
        if not source.exists():
            return video_path

        qr_path = self._render_qr_png(qr_data, target_px=420)
        if not qr_path:
            logger.warning("Coming Soon list: QR could not be rendered, leaving the video unchanged")
            return video_path

        probe = self._probe_dimensions(str(source))
        width, height = probe if probe else (1920, 1080)
        # Keep the code a consistent fraction of the frame so it stays scannable
        # at 720p and does not dominate a 4K render.
        qr_size = max(120, int(min(width, height) * 0.16))
        pad = max(8, int(qr_size * 0.07))
        margin = max(16, int(min(width, height) * 0.035))
        plate = qr_size + pad * 2
        plate_x = width - margin - plate if 'right' in corner else margin
        plate_y = height - margin - plate if 'bottom' in corner else margin

        out_path = source.with_name(source.stem + '_qr' + source.suffix)
        filters = [
            f"[0:v]drawbox=x={plate_x}:y={plate_y}:w={plate}:h={plate}:c=white:t=fill[plate]",
            f"[1:v]scale={qr_size}:{qr_size}:flags=neighbor[qr]",
            f"[plate][qr]overlay={plate_x + pad}:{plate_y + pad}[vout]",
        ]
        cmd = [
            self.ffmpeg_path, '-y', '-i', str(source), '-i', str(qr_path),
            '-filter_complex', ';'.join(filters),
            '-map', '[vout]', '-map', '0:a?',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-c:a', 'copy', '-pix_fmt', 'yuv420p', str(out_path),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=300, startupinfo=STARTUPINFO, creationflags=CREATE_NO_WINDOW
            )
            if result.returncode != 0 or not out_path.exists():
                logger.error(f"Coming Soon list QR overlay failed: {(result.stderr or '')[-400:]}")
                return video_path
            # Replace the original so callers keep the filename they asked for.
            source.unlink(missing_ok=True)
            out_path.replace(source)
            return str(source)
        except Exception as e:
            logger.error(f"Coming Soon list QR overlay error: {e}")
            return video_path
        finally:
            try:
                qr_path.unlink()
            except Exception:
                pass

    def probe_media_duration(self, media_path: str) -> Optional[float]:
        """Length of an audio or video file in seconds, or None if unreadable.

        Used to offer "match the preroll length to the soundtrack" so a track
        plays whole instead of being cut off by a fixed duration.
        """
        # Accepts a local path or an http(s) URL: ffprobe reads a remote
        # container header over range requests without fetching the whole file.
        if not media_path:
            return None
        is_remote = str(media_path).lower().startswith(('http://', 'https://'))
        if not is_remote and not os.path.isfile(media_path):
            return None
        probe = (self.ffmpeg_path or '').replace('ffmpeg.exe', 'ffprobe.exe').replace('ffmpeg.EXE', 'ffprobe.exe')
        if probe == self.ffmpeg_path:
            probe = str(Path(self.ffmpeg_path).with_name('ffprobe' + Path(self.ffmpeg_path).suffix))
        if not os.path.isfile(probe):
            return None
        try:
            result = subprocess.run(
                [probe, '-v', 'error']
                + (['-user_agent', COMMUNITY_PROBE_UA] if is_remote else [])
                + ['-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', str(media_path)],
                capture_output=True, text=True, timeout=45 if is_remote else 30,
                startupinfo=STARTUPINFO, creationflags=CREATE_NO_WINDOW
            )
            value = float(result.stdout.strip())
            return value if value > 0 else None
        except Exception:
            return None

    def _probe_dimensions(self, video_path: str):
        """Return (width, height) for a rendered file, or None if ffprobe can't."""
        probe = (self.ffmpeg_path or '').replace('ffmpeg.exe', 'ffprobe.exe').replace('ffmpeg.EXE', 'ffprobe.exe')
        if probe == self.ffmpeg_path:
            probe = str(Path(self.ffmpeg_path).with_name('ffprobe' + Path(self.ffmpeg_path).suffix))
        if not os.path.isfile(probe):
            return None
        try:
            result = subprocess.run(
                [probe, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                 'stream=width,height', '-of', 'csv=p=0:s=x', video_path],
                capture_output=True, text=True, timeout=30,
                startupinfo=STARTUPINFO, creationflags=CREATE_NO_WINDOW
            )
            w, h = result.stdout.strip().split('x')[:2]
            return int(w), int(h)
        except Exception:
            return None

    def generate_coming_soon_list(
        self,
        items: List[Dict[str, Any]],
        server_name: str = "Your Server",
        duration: float = 10.0,
        output_filename: str = "coming_soon_list.mp4",
        layout: str = "list",  # "list" or "grid"
        bg_color: str = "0x141428",
        text_color: str = "0xffffff",
        accent_color: str = "0x00d4ff",
        width: int = 1920,
        height: int = 1080,
        max_items: int = 8,
        include_audio: bool = False,
        custom_audio_path: str = None,
        custom_logo_path: str = None,
        logo_mode: str = "watermark",
        language: str = 'en',
        frame_rate: int = 30,
        video_preset: str = 'fast',
        video_crf: int = 20,
        audio_bitrate: str = '192k',
        theme: str = None,
        qr_data: str = None,
        backdrop_video: str = None,
        backdrop_dim: Any = 0,
        font_scale: float = 1.0,
        title_color: str = None,
        date_color: str = None,
        available_color: str = None,
        heading_color: str = None,
    ) -> Optional[str]:
        """Generate a Coming Soon List video.
        
        Args:
            items: List of dicts with 'title', 'release_date', 'poster_url' (optional)
            server_name: Server name to display in header
            duration: Total video duration in seconds
            output_filename: Output filename
            layout: "list" for text-only, "grid" for poster grid
            bg_color: Background color (hex)
            text_color: Main text color (hex)
            accent_color: Accent/highlight color (hex)
            width: Video width
            height: Video height
            max_items: Maximum number of items to show
            include_audio: Whether to include background music
            frame_rate: Output frames per second
            video_preset: FFmpeg x264 encoding preset
            video_crf: FFmpeg constant-rate-factor quality value
            audio_bitrate: AAC bitrate when music is enabled
            
        Returns:
            Path to generated video or None on failure
        """
        if not self.is_available():
            logger.error("FFmpeg not available")
            return None
        
        if not self.output_dir:
            logger.error("Output directory not set")
            return None
        
        _verbose_log(f"=== generate_coming_soon_list ===")
        _verbose_log(
            f"Items: {len(items)}, Layout: {layout}, Duration: {duration}s, Audio: {include_audio}, "
            f"Output: {width}x{height}@{frame_rate}, Preset: {video_preset}, CRF: {video_crf}"
        )
        _verbose_log(f"Server name: '{server_name}'")
        _verbose_log(f"Colors - BG: {bg_color}, Text: {text_color}, Accent: {accent_color}")
        _verbose_log(f"Custom audio: {custom_audio_path}, Custom logo: {custom_logo_path}, Logo mode: {logo_mode}")
        
        # A named theme fills in the three colours, so Coming Soon lists can use
        # the same palettes as the dynamic templates instead of only hand-picked
        # hex values. Explicit colours still win when no theme is chosen.
        backdrop_image = None
        if theme and theme in self.COLOR_THEMES:
            palette = self.COLOR_THEMES[theme]
            bg_color, text_color, accent_color = palette['bg'], palette['primary'], palette['secondary']
            _verbose_log(f"Theme '{theme}' applied - BG: {bg_color}, Text: {text_color}, Accent: {accent_color}")
            # Give the list the same layered backdrop the dynamic templates get,
            # rather than a flat wash behind the posters.
            backdrop_image = self._render_theme_backdrop_png(theme, palette, 1920, 1080)

        # Limit items
        items = items[:max_items]
        
        if not items:
            logger.warning("No items to display in Coming Soon List")
            return None
        
        if layout == "grid":
            rendered = self._generate_list_grid_layout(
                items, server_name, duration, output_filename,
                bg_color, text_color, accent_color, 1920, 1080,
                include_audio=include_audio,
                custom_audio_path=custom_audio_path,
                custom_logo_path=custom_logo_path,
                logo_mode=logo_mode,
                language=language,
                output_width=width,
                output_height=height,
                frame_rate=frame_rate,
                video_preset=video_preset,
                video_crf=video_crf,
                audio_bitrate=audio_bitrate,
                background_image=str(backdrop_image) if backdrop_image else None,
                background_video=backdrop_video,
                backdrop_dim=backdrop_dim,
                font_scale=font_scale,
                title_color=title_color,
                date_color=date_color,
                available_color=available_color,
                heading_color=heading_color,
            )
        else:
            rendered = self._generate_list_text_layout(
                items, server_name, duration, output_filename,
                bg_color, text_color, accent_color, 1920, 1080,
                include_audio=include_audio,
                custom_audio_path=custom_audio_path,
                custom_logo_path=custom_logo_path,
                logo_mode=logo_mode,
                language=language,
                output_width=width,
                output_height=height,
                frame_rate=frame_rate,
                video_preset=video_preset,
                video_crf=video_crf,
                audio_bitrate=audio_bitrate,
                background_image=str(backdrop_image) if backdrop_image else None,
                background_video=backdrop_video,
                backdrop_dim=backdrop_dim,
                font_scale=font_scale,
                title_color=title_color,
                date_color=date_color,
                available_color=available_color,
                heading_color=heading_color,
            )

        if rendered and qr_data:
            rendered = self._overlay_corner_qr(rendered, qr_data)
        # The baked backdrop is scratch, and output_dir is a folder the user
        # browses, so it does not get left behind.
        if backdrop_image:
            try:
                Path(backdrop_image).unlink(missing_ok=True)
            except Exception:
                pass
        return rendered
    
    def _generate_list_text_layout(
        self,
        items: List[Dict[str, Any]],
        server_name: str,
        duration: float,
        output_filename: str,
        bg_color: str,
        text_color: str,
        accent_color: str,
        width: int,
        height: int,
        include_audio: bool = False,
        custom_audio_path: str = None,
        custom_logo_path: str = None,
        logo_mode: str = "watermark",
        language: str = 'en',
        output_width: int = 1920,
        output_height: int = 1080,
        frame_rate: int = 30,
        video_preset: str = 'fast',
        video_crf: int = 20,
        audio_bitrate: str = '192k',
        background_image: str = None,
        background_video: str = None,
        backdrop_dim: Any = 0,
        font_scale: float = 1.0,
        title_color: str = None,
        date_color: str = None,
        available_color: str = None,
        heading_color: str = None,
    ) -> Optional[str]:
        """Generate text-only list layout (no posters)"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        _verbose_log(f"Text layout - Server name: '{server_name}' -> escaped: '{escaped_server}', logo_mode: {logo_mode}")
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        coming_soon_to_text = self._escape_text(self._get_text('coming_soon_to', language))
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Calculate layout - dynamically adjust for item count
        header_y = 80
        subtitle_y = 175
        list_start_y = 270
        # A below/replace logo is drawn at y=175 and a wide mark reaches roughly
        # y=315, which landed on top of the first title. Start the list clear of
        # it; available_height is derived from this, so the rows re-fit
        # themselves rather than running off the bottom.
        _below_logo = (logo_mode in ('below', 'replace')
                       and custom_logo_path and os.path.isfile(custom_logo_path))
        if _below_logo:
            list_start_y = 350

        # Available height for items, after the header area and a bottom margin.
        available_height = height - list_start_y - 50
        num_items = len(items)
        
        # Calculate line height based on item count
        if num_items <= 6:
            line_height = 90
            fontsize = 42
        elif num_items <= 8:
            line_height = 75
            fontsize = 38
        elif num_items <= 10:
            line_height = 65
            fontsize = 34
        else:
            line_height = 55
            fontsize = 30

        # Scale the item text, and the row pitch with it, so a larger font does
        # not overlap the next title. If the scaled rows would run past the
        # bottom of the frame, the pitch is capped and the text follows it down
        # -- better a slightly smaller font than a list that overflows.
        scale = max(0.85, min(1.6, float(font_scale or 1.0)))
        if scale != 1.0:
            fontsize = int(round(fontsize * scale))
            line_height = int(round(line_height * scale))
            max_line_height = int(available_height // max(1, num_items))
            if line_height > max_line_height:
                line_height = max_line_height
                fontsize = min(fontsize, max(18, int(max_line_height * 0.55)))

        # Build filter string
        filter_parts = []
        
        # The heading colour is separable from Accent: with a theme selected the
        # manual Accent picker is hidden, which left no way to recolour
        # "COMING SOON" at all.
        head_color = heading_color or accent_color

        # Header: "Coming Soon to [Server Name]" or "COMING SOON TO" + logo
        has_replace_logo = logo_mode in ('right', 'below', 'replace') and custom_logo_path and os.path.isfile(custom_logo_path)
        if has_replace_logo:
            # Right/Below mode: single-line "COMING SOON TO" header, logo positioned separately.
            # Right mode centres the heading inside the left band so the logo,
            # which occupies the right quarter, has clear space beside it.
            header_x = "(w*0.78-text_w)/2" if logo_mode == 'right' else "(w-text_w)/2"
            header_size = 70 if logo_mode == 'right' else 80
            filter_parts.append(
                f"drawtext=text='{coming_soon_to_text}':fontsize={header_size}:fontcolor={head_color}{bold_font_param}:"
                f"x={header_x}:y={header_y}:shadowcolor=black@0.6:shadowx=2:shadowy=2"
            )
        else:
            filter_parts.append(
                f"drawtext=text='{coming_soon_text}':fontsize=80:fontcolor={head_color}{bold_font_param}:"
                f"x=(w-text_w)/2:y={header_y}:shadowcolor=black@0.6:shadowx=2:shadowy=2"
            )
            filter_parts.append(
                f"drawtext=text='{to_text} {escaped_server}':fontsize=50:fontcolor={text_color}@0.9{font_param}:"
                f"x=(w-text_w)/2:y={subtitle_y}:alpha='if(lt(t,0.5),0,if(lt(t,1),(t-0.5)/0.5,1))'"
            )
            # Divider line (only in watermark/normal mode)
            line_y = subtitle_y + 60
            filter_parts.append(
                f"drawbox=x={width//4}:y={line_y}:w={width//2}:h=3:c={head_color}@0.6:t=fill"
            )
        
        # Item list with staggered fade-in
        for i, item in enumerate(items):
            title = self._escape_text(item.get('title', 'Unknown'))[:40]  # Truncate long titles
            
            # Format release date or "Available Now!" status
            release_date = item.get('release_date', '')
            if item.get('available_now', False):
                date_str = self._get_text('available_now', language)
            elif release_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%b %d %Y')
                except:
                    date_str = release_date[:10] if len(release_date) >= 10 else release_date
            else:
                date_str = "TBA"
            date_str = self._escape_text(date_str)
            
            item_y = list_start_y + (i * line_height)
            fade_delay = 0.8 + (i * 0.15)  # Staggered fade-in
            date_fontsize = int(fontsize * 0.85)  # Slightly smaller for date
            
            # Use green color for "Available Now!" items
            # Each role falls back to the colour it always used, so an
            # untouched list renders exactly as before.
            _avail = available_color or '0x28a745'
            _date = f"{date_color}" if date_color else f'{accent_color}@0.9'
            date_color_used = _avail if item.get('available_now', False) else _date
            
            # Title (left-aligned with padding)
            filter_parts.append(
                f"drawtext=text='{title}':fontsize={fontsize}:fontcolor={title_color or text_color}{font_param}:"
                f"x=200:y={item_y}:alpha='if(lt(t,{fade_delay}),0,if(lt(t,{fade_delay+0.4}),"
                f"(t-{fade_delay})/0.4,1))'"
            )
            
            # Date (right-aligned)
            filter_parts.append(
                f"drawtext=text='{date_str}':fontsize={date_fontsize}:fontcolor={date_color_used}{font_param}:"
                f"x=w-text_w-200:y={item_y+5}:alpha='if(lt(t,{fade_delay}),0,if(lt(t,{fade_delay+0.4}),"
                f"(t-{fade_delay})/0.4,1))'"
            )
            
            # Subtle dot separator (ASCII-safe for Windows cp1252 compatibility)
            filter_parts.append(
                f"drawtext=text='>':fontsize=20:fontcolor={accent_color}@0.5{font_param}:"
                f"x=165:y={item_y+8}:alpha='if(lt(t,{fade_delay}),0,if(lt(t,{fade_delay+0.4}),"
                f"(t-{fade_delay})/0.4,1))'"
            )
        
        # Note: fade is NOT included here — it's applied after logo overlay in vignette_fallback
        
        filter_str = ",".join(filter_parts)
        
        # Use vignette fallback for list (gradient + many drawtext elements causes FFmpeg issues)
        return self._run_ffmpeg_vignette_fallback(
            filter_str, output_path, duration, width, height, bg_color,
            include_audio=include_audio,
            custom_audio_path=custom_audio_path,
            custom_logo_path=custom_logo_path,
            logo_mode=logo_mode,
            fade_duration=0.8,
            output_width=output_width,
            output_height=output_height,
            frame_rate=frame_rate,
            video_preset=video_preset,
            video_crf=video_crf,
            audio_bitrate=audio_bitrate,
            background_image=background_image,
            background_video=background_video,
            backdrop_dim=backdrop_dim,
        )
    
    def _generate_list_grid_layout(
        self,
        items: List[Dict[str, Any]],
        server_name: str,
        duration: float,
        output_filename: str,
        bg_color: str,
        text_color: str,
        accent_color: str,
        width: int,
        height: int,
        include_audio: bool = False,
        custom_audio_path: str = None,
        custom_logo_path: str = None,
        logo_mode: str = "watermark",
        language: str = 'en',
        output_width: int = 1920,
        output_height: int = 1080,
        frame_rate: int = 30,
        video_preset: str = 'fast',
        video_crf: int = 20,
        audio_bitrate: str = '192k',
        background_image: str = None,
        background_video: str = None,
        backdrop_dim: Any = 0,
        font_scale: float = 1.0,
        title_color: str = None,
        date_color: str = None,
        available_color: str = None,
        heading_color: str = None,
    ) -> Optional[str]:
        """
        Generate grid layout with poster images.
        Downloads posters, overlays them in a grid, adds titles.
        """
        import tempfile
        import httpx
        import asyncio
        
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        _verbose_log(f"Grid layout - Server name: '{server_name}' -> escaped: '{escaped_server}'")
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        coming_soon_to_text = self._escape_text(self._get_text('coming_soon_to', language))
        coming_soon_text = self._escape_text(self._get_text('coming_soon', language))
        to_text = self._escape_text(self._get_text('to', language))
        
        # Create temp directory for poster images
        temp_dir = tempfile.mkdtemp(prefix="nexroll_posters_")
        poster_paths = []
        valid_items = []
        
        try:
            # Download poster images synchronously
            _verbose_log(f"Downloading posters to {temp_dir}")
            _verbose_log(f"Items to process: {len(items)}")
            
            for i, item in enumerate(items):  # Use all items (already limited by max_items)
                poster_url = item.get('poster_url')
                _verbose_log(f"Item {i}: {item.get('title', 'Unknown')} - poster_url: {poster_url[:50] if poster_url else 'None'}...")
                
                if poster_url:
                    try:
                        # Use synchronous httpx for simplicity
                        import httpx
                        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                            response = client.get(poster_url)
                            if response.status_code == 200:
                                # Save poster to temp file
                                content_type = response.headers.get('content-type', '')
                                ext = '.jpg' if 'jpeg' in content_type or 'jpg' in content_type else '.png'
                                poster_path = os.path.join(temp_dir, f"poster_{i}{ext}")
                                with open(poster_path, 'wb') as f:
                                    f.write(response.content)
                                poster_paths.append(poster_path)
                                valid_items.append(item)
                                _verbose_log(f"Downloaded poster {i}: {poster_path} ({len(response.content)} bytes)")
                            else:
                                _verbose_log(f"Failed to download poster {i}: HTTP {response.status_code}")
                    except Exception as e:
                        _verbose_log(f"Error downloading poster {i}: {e}")
                else:
                    _verbose_log(f"No poster URL for item {i}: {item.get('title', 'Unknown')}")
            
            _verbose_log(f"Downloaded {len(poster_paths)} posters successfully")
            
            if not valid_items:
                _verbose_log("No valid posters downloaded, falling back to text layout")
                return self._generate_list_text_layout(
                    items, server_name, duration, output_filename,
                    bg_color, text_color, accent_color, width, height,
                    include_audio=include_audio,
                    custom_audio_path=custom_audio_path,
                    custom_logo_path=custom_logo_path,
                    logo_mode=logo_mode,
                    language=language,
                    output_width=output_width,
                    output_height=output_height,
                    frame_rate=frame_rate,
                    video_preset=video_preset,
                    video_crf=video_crf,
                    audio_bitrate=audio_bitrate,
                )
            
            # Build grid layout with FFmpeg
            # Calculate grid layout: <=6 items = single row, >6 = two rows
            num_items = len(valid_items)
            if num_items <= 6:
                # Single row - all posters side by side
                cols = num_items
                rows = 1
            else:
                # Two rows - distribute evenly (top row gets extra if odd)
                cols = (num_items + 1) // 2
                rows = 2
            
            # Poster sizes optimized for 1920x1080
            if rows == 1:
                # Single row sizing - posters can be larger with full vertical space
                spacing_y = 0  # No vertical spacing needed for single row
                if cols <= 1:
                    poster_width, poster_height = 350, 525
                    spacing_x, start_y, date_spacing = 0, 200, 40
                elif cols == 2:
                    poster_width, poster_height = 320, 480
                    spacing_x, start_y, date_spacing = 120, 200, 40
                elif cols == 3:
                    poster_width, poster_height = 300, 450
                    spacing_x, start_y, date_spacing = 80, 200, 40
                elif cols == 4:
                    poster_width, poster_height = 270, 405
                    spacing_x, start_y, date_spacing = 65, 200, 38
                elif cols == 5:
                    poster_width, poster_height = 240, 360
                    spacing_x, start_y, date_spacing = 55, 210, 35
                else:  # 6
                    poster_width, poster_height = 220, 330
                    spacing_x, start_y, date_spacing = 50, 220, 32
            else:
                # Two row sizing - sized to fit within 1080px height
                # Constraint: start_y + 2*poster_h + spacing_y + date_spacing + date_text(~36) <= 1080
                if cols <= 4:  # 7-8 items
                    poster_width, poster_height = 240, 360
                    spacing_x, spacing_y = 60, 20
                    start_y, date_spacing = 190, 35
                elif cols == 5:  # 9-10 items
                    poster_width, poster_height = 210, 315
                    spacing_x, spacing_y = 50, 15
                    start_y, date_spacing = 190, 32
                else:  # 6 cols, 11-12 items
                    poster_width, poster_height = 200, 300
                    spacing_x, spacing_y = 42, 12
                    start_y, date_spacing = 190, 30
            
            # Shift grid down when logo is placed below the header to avoid overlap
            if logo_mode in ('below', 'replace') and custom_logo_path and os.path.isfile(custom_logo_path):
                start_y += 40
            
            grid_width = cols * poster_width + (cols - 1) * spacing_x
            grid_height = rows * poster_height + (rows - 1) * spacing_y
            
            start_x = (width - grid_width) // 2
            
            # Build complex filterchain
            inputs = [f'-i "{p}"' for p in poster_paths]
            
            # Base: create background
            filter_complex = []
            
            # Scale each poster and overlay
            overlay_chain = f"[base]"
            for i, poster_path in enumerate(poster_paths):
                col = i % cols
                row = i // cols
                x = start_x + col * (poster_width + spacing_x)
                y = start_y + row * (poster_height + spacing_y + date_spacing)  # Extra for title
                
                # Scale poster
                filter_complex.append(f"[{i+1}:v]scale={poster_width}:{poster_height}[p{i}]")
                # Overlay with fade-in
                fade_delay = 0.5 + i * 0.1
                filter_complex.append(
                    f"{overlay_chain}[p{i}]overlay=x={x}:y={y}:"
                    f"enable='gte(t,{fade_delay})'[tmp{i}]"
                )
                overlay_chain = f"[tmp{i}]"
            
            # Add text overlays for titles (simpler approach - skip for now, use text directly)
            # For now, generate simpler version without embedded titles
            
            # Build FFmpeg command for grid with poster overlays
            cmd = [
                self.ffmpeg_path,
                '-y',
            ]
            if background_video and os.path.isfile(str(background_video)):
                cmd.extend(['-stream_loop', '-1', '-t', str(duration), '-i', str(background_video)])
            elif background_image and os.path.isfile(str(background_image)):
                # Themed backdrop behind the posters, matching the preview.
                cmd.extend(['-loop', '1', '-t', str(duration), '-r', str(frame_rate), '-i', str(background_image)])
            else:
                cmd.extend(['-f', 'lavfi',
                            '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r={frame_rate}'])
            
            # Add poster inputs
            for poster_path in poster_paths:
                cmd.extend(['-i', poster_path])
            
            # Build filter
            filter_parts = []
            
            # Label base
            # A recorded backdrop may not match the layout resolution, so
            # normalise it before posters are positioned on top.
            if background_video and os.path.isfile(str(background_video)):
                filter_parts.append(f"[0:v]{backdrop_video_chain(width, height, backdrop_dim)}[base]")
            else:
                filter_parts.append(f"[0:v]null[base]")
            
            current_label = "[base]"
            for i, poster_path in enumerate(poster_paths):
                col = i % cols
                row = i // cols
                x = start_x + col * (poster_width + spacing_x)
                y = start_y + row * (poster_height + spacing_y + date_spacing)  # Space for date below
                
                # Scale poster
                filter_parts.append(f"[{i+1}:v]scale={poster_width}:{poster_height},format=rgba[p{i}]")
                
                # Overlay (simplified - no enable expression to avoid escaping issues)
                next_label = f"[ovr{i}]"
                filter_parts.append(
                    f"{current_label}[p{i}]overlay=x={x}:y={y}{next_label}"
                )
                current_label = next_label
            
            # Build text overlays for release dates only
            text_filters = []
            for i, item in enumerate(valid_items):
                col = i % cols
                row = i // cols
                x = start_x + col * (poster_width + spacing_x)
                y = start_y + row * (poster_height + spacing_y + date_spacing)
                
                # Format release date or "Available Now!" status
                release_date = item.get('release_date', '')
                if item.get('available_now', False):
                    date_str = self._get_text('available_now', language)
                elif release_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
                        date_str = dt.strftime('%b %d')
                    except:
                        date_str = release_date[:10] if len(release_date) >= 10 else release_date
                else:
                    date_str = "TBA"
                date_str = self._escape_text(date_str)
                
                # Use green color for "Available Now!" items
                _g_avail = available_color or '0x28a745'
                _g_date = f"{date_color}" if date_color else f'{accent_color}@0.9'
                grid_date_color = _g_avail if item.get('available_now', False) else _g_date
                
                # Center text under poster - only release date
                text_center_x = x + poster_width // 2
                date_y = y + poster_height + 8
                
                # Release date only (centered, accent color) - scale font based on poster size
                date_fontsize = max(14, min(40, int((poster_width // 10) * max(0.85, min(1.6, float(font_scale or 1.0))))))
                text_filters.append(
                    f"drawtext=text='{date_str}':fontsize={date_fontsize}:fontcolor={grid_date_color}{font_param}:"
                    f"x={text_center_x}-(text_w/2):y={date_y}:shadowcolor=black@0.4:shadowx=1:shadowy=1"
                )
            
            # Same heading override as the list layout.
            head_color = heading_color or accent_color

            # Add header text - optimized for 2-row layout with start_y=170
            # Only show "to {server_name}" when logo_mode is watermark (or no logo available)
            has_replace_logo = logo_mode in ('right', 'below', 'replace') and custom_logo_path and os.path.isfile(custom_logo_path)
            if has_replace_logo:
                if logo_mode == 'right':
                    # Right mode: "COMING SOON TO" shifted left, logo placed to its right
                    header_filter = (
                        f"drawtext=text='{coming_soon_to_text}':fontsize=55:fontcolor={head_color}{bold_font_param}:"
                        f"x=(w-text_w)/2-80:y=50:shadowcolor=black@0.5:shadowx=2:shadowy=2"
                    )
                else:
                    # Below mode: "COMING SOON TO" centered, logo placed below
                    header_filter = (
                        f"drawtext=text='{coming_soon_to_text}':fontsize=55:fontcolor={head_color}{bold_font_param}:"
                        f"x=(w-text_w)/2:y=50:shadowcolor=black@0.5:shadowx=2:shadowy=2"
                    )
            else:
                header_filter = (
                    f"drawtext=text='{coming_soon_text}':fontsize=55:fontcolor={head_color}{bold_font_param}:"
                    f"x=(w-text_w)/2:y=50:shadowcolor=black@0.5:shadowx=2:shadowy=2,"
                    f"drawtext=text='{to_text} {escaped_server}':fontsize=30:fontcolor={text_color}@0.9{font_param}:"
                    f"x=(w-text_w)/2:y=115"
                )
            
            # Combine: poster overlays + text overlays + header (NO fade yet — applied after logo overlay)
            all_text = ",".join(text_filters)
            final_filter = f"{header_filter},{all_text}"
            
            filter_parts.append(f"{current_label}{final_filter}[out]")
            
            filter_complex_str = ";".join(filter_parts)
            
            # --- Logo overlay (inserted as extra input) ---
            logo_input_index = None
            if custom_logo_path and os.path.isfile(custom_logo_path):
                logo_input_index = len(poster_paths) + 1  # Next input after posters
                cmd.extend(['-i', custom_logo_path])
                if logo_mode == 'right':
                    # Right mode: logo to the right of "COMING SOON TO" header
                    logo_h = 120  # Prominent size next to header
                    logo_opacity = 0.85
                    logo_x = f"(W/2)+200"
                    logo_y = 15
                    _verbose_log(f"Grid logo RIGHT mode: height={logo_h}, opacity={logo_opacity}, x={logo_x}, y={logo_y}")
                    logo_filter = (
                        f"[{logo_input_index}:v]scale=-2:{logo_h},format=rgba,"
                        f"colorchannelmixer=aa={logo_opacity}[logo];"
                    )
                    logo_filter += f"[out][logo]overlay={logo_x}:{logo_y}[outcomp]"
                elif logo_mode in ('below', 'replace'):
                    # Below mode: logo centered below the header
                    logo_h = 100
                    logo_opacity = 0.85
                    logo_x = "(W-w)/2"
                    logo_y = 115  # Below the header text
                    _verbose_log(f"Grid logo BELOW mode: height={logo_h}, opacity={logo_opacity}, x={logo_x}, y={logo_y}")
                    logo_filter = (
                        f"[{logo_input_index}:v]scale=-2:{logo_h},format=rgba,"
                        f"colorchannelmixer=aa={logo_opacity}[logo];"
                    )
                    logo_filter += f"[out][logo]overlay={logo_x}:{logo_y}[outcomp]"
                else:
                    # Watermark mode: faded centered behind text
                    logo_w = int(width * 0.30)
                    logo_opacity = 0.15
                    logo_filter = (
                        f"[{logo_input_index}:v]scale={logo_w}:-1,format=rgba,"
                        f"colorchannelmixer=aa={logo_opacity}[logo];"
                    )
                    logo_filter += f"[out][logo]overlay=(W-w)/2:(H-h)/2[outcomp]"
                filter_complex_str = filter_complex_str + ';' + logo_filter
                # Apply fade AFTER overlay so logo + video fade together
                filter_complex_str += f";[outcomp]fade=t=in:st=0:d=0.6,fade=t=out:st={duration-0.6}:d=0.6[outl]"
                _verbose_log(f"Added logo overlay from {custom_logo_path} (input {logo_input_index})")
            else:
                # No logo — apply fade directly
                filter_complex_str += f";[out]fade=t=in:st=0:d=0.6,fade=t=out:st={duration-0.6}:d=0.6[outl]"
            
            # Determine final video output label
            video_out_label = '[outl]'

            if output_width != width or output_height != height:
                filter_complex_str += (
                    f";{video_out_label}scale={output_width}:{output_height}:flags=lanczos,"
                    "format=yuv420p[outscaled]"
                )
                video_out_label = '[outscaled]'
            
            # Add audio source — this becomes the next input after posters (and optional logo)
            audio_index = len(poster_paths) + 1 + (1 if logo_input_index else 0)
            
            # Determine audio source
            audio_file = None
            if include_audio:
                audio_file = self._get_coming_soon_audio_path(custom_audio_path=custom_audio_path)
            
            if audio_file:
                # Use real audio file with fade in/out
                fade_duration = 1.5
                fade_out_start = max(0, duration - fade_duration)
                cmd.extend(['-i', audio_file])
                audio_filter = f'[{audio_index}:a]atrim=0:{duration},afade=t=in:d={fade_duration},afade=t=out:st={fade_out_start}:d={fade_duration},asetpts=PTS-STARTPTS[aout]'
                filter_complex_str = filter_complex_str + ';' + audio_filter
                audio_map = '[aout]'
            else:
                # Silent audio fallback
                cmd.extend(['-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo:d={duration}'])
                audio_map = f'{audio_index}:a'
            
            _verbose_log(f"Audio input index: {audio_index}, using file: {audio_file is not None}")
            
            cmd.extend([
                '-filter_complex', filter_complex_str,
                '-map', video_out_label,
                '-map', audio_map,
                '-c:v', 'libx264', '-preset', video_preset, '-crf', str(video_crf),
                '-profile:v', 'high',
                '-level', '5.2' if output_width >= 3840 or frame_rate >= 60 else '4.1',
                '-c:a', 'aac', '-b:a', audio_bitrate,
                '-shortest',
                '-pix_fmt', 'yuv420p',
                str(output_path)
            ])
            
            _verbose_log(f"FFmpeg command (grid): {' '.join(str(c) for c in cmd[:20])}... (truncated)")
            _verbose_log(f"Filter complex: {filter_complex_str[:300]}...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300 if output_width >= 3840 else 180,
                startupinfo=STARTUPINFO,
                creationflags=CREATE_NO_WINDOW
            )
            
            _verbose_log(f"FFmpeg return code: {result.returncode}")
            if result.stderr:
                _verbose_log(f"FFmpeg stderr: {result.stderr[:500]}")
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                _verbose_log(f"SUCCESS! Generated grid video: {output_path} ({file_size} bytes)")
                return str(output_path)
            else:
                _verbose_log(f"Grid generation failed, falling back to text layout")
                return self._generate_list_text_layout(
                    items, server_name, duration, output_filename,
                    bg_color, text_color, accent_color, width, height,
                    include_audio=include_audio,
                    custom_audio_path=custom_audio_path,
                    custom_logo_path=custom_logo_path,
                    logo_mode=logo_mode,
                    language=language,
                    output_width=output_width,
                    output_height=output_height,
                    frame_rate=frame_rate,
                    video_preset=video_preset,
                    video_crf=video_crf,
                    audio_bitrate=audio_bitrate,
                )
                
        except Exception as e:
            _verbose_log(f"Error in grid layout: {e}")
            logger.error(f"Error generating grid layout: {e}")
            # Fallback to text layout
            return self._generate_list_text_layout(
                items, server_name, duration, output_filename,
                bg_color, text_color, accent_color, width, height,
                include_audio=include_audio,
                custom_audio_path=custom_audio_path,
                custom_logo_path=custom_logo_path,
                logo_mode=logo_mode,
                language=language,
                output_width=output_width,
                output_height=output_height,
                frame_rate=frame_rate,
                video_preset=video_preset,
                video_crf=video_crf,
                audio_bitrate=audio_bitrate,
            )
        finally:
            # Clean up temp directory
            try:
                import shutil as sh
                sh.rmtree(temp_dir, ignore_errors=True)
                _verbose_log(f"Cleaned up temp directory: {temp_dir}")
            except:
                pass


def check_ffmpeg_available() -> Dict[str, Any]:
    """Check if FFmpeg is available and get version info"""
    ffmpeg = shutil.which('ffmpeg')
    
    if not ffmpeg:
        # Check common locations
        common_paths = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        ]
        for path in common_paths:
            if os.path.isfile(path):
                ffmpeg = path
                break
    
    if not ffmpeg:
        return {
            'available': False,
            'path': None,
            'version': None,
            'message': 'FFmpeg not found. Install FFmpeg to enable dynamic preroll generation.'
        }
    
    try:
        result = subprocess.run(
            [ffmpeg, '-version'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10,
            startupinfo=STARTUPINFO,
            creationflags=CREATE_NO_WINDOW
        )
        version_line = result.stdout.split('\n')[0] if result.stdout else 'Unknown'
        
        return {
            'available': True,
            'path': ffmpeg,
            'version': version_line,
            'message': 'FFmpeg is available'
        }
    except Exception as e:
        return {
            'available': False,
            'path': ffmpeg,
            'version': None,
            'message': f'FFmpeg found but error checking version: {e}'
        }
