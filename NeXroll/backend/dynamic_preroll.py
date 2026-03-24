"""
NeX-Up: Dynamic Preroll Generator
Creates customizable intro videos using FFmpeg with advanced visual effects
"""

import os
import re
import subprocess
import shutil
import logging
import sys
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)

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


class DynamicPrerollGenerator:
    """Generates dynamic preroll videos using FFmpeg with cinematic effects"""
    
    # Available templates with enhanced visual styles
    TEMPLATES = {
        'coming_soon': {
            'name': '🎬 Coming Soon',
            'description': 'Cinematic intro announcing upcoming content with glow effects and dramatic animations.',
            'duration': 5,
            'variables': ['server_name'],
            'default_values': {'server_name': 'Your Server'},
            'style': 'cinematic'
        },
        'feature_presentation': {
            'name': '🎭 Feature Presentation',
            'description': 'Classic theater-style "Feature Presentation" with elegant text and decorative elements.',
            'duration': 5,
            'variables': ['server_name'],
            'default_values': {'server_name': ''},
            'style': 'classic'
        },
        'now_showing': {
            'name': '📽️ Now Showing',
            'description': 'Retro film-style "Now Showing" with film grain effect. Warm sepia tones.',
            'duration': 4,
            'variables': ['server_name'],
            'default_values': {'server_name': ''},
            'style': 'retro'
        }
    }
    
    # Color themes - brighter backgrounds for better video quality
    COLOR_THEMES = {
        'midnight': {'bg': '0x141428', 'primary': '0x00d4ff', 'secondary': '0x7b2cbf', 'accent': '0xff006e'},
        'sunset': {'bg': '0x2a1414', 'primary': '0xff6b35', 'secondary': '0xf7c59f', 'accent': '0xef233c'},
        'forest': {'bg': '0x142a14', 'primary': '0x2ec4b6', 'secondary': '0x83c5be', 'accent': '0xedf6f9'},
        'royal': {'bg': '0x1a0040', 'primary': '0xffd700', 'secondary': '0xc77dff', 'accent': '0xe0aaff'},
        'monochrome': {'bg': '0x1a1a1a', 'primary': '0xffffff', 'secondary': '0xaaaaaa', 'accent': '0xcccccc'},
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
            'feature_presentation': 'LONG M\\u00c9TRAGE',
            'feature': 'LONG',
            'presentation': 'M\\u00c9TRAGE',
            'now_showing': "\\u00c0 L'AFFICHE",
            'at': 'sur',
            'coming_soon_to': 'PROCHAINEMENT SUR',
            'available_now': 'Maintenant disponible!',
        },
        'es': {
            'coming_soon': 'PR\\u00d3XIMAMENTE',
            'to': 'en',
            'feature_presentation': 'FUNCI\\u00d3N PRINCIPAL',
            'feature': 'FUNCI\\u00d3N',
            'presentation': 'PRINCIPAL',
            'now_showing': 'EN CARTELERA',
            'at': 'en',
            'coming_soon_to': 'PR\\u00d3XIMAMENTE EN',
            'available_now': '\\u00a1Disponible!',
        },
        'de': {
            'coming_soon': 'DEMN\\u00c4CHST',
            'to': 'auf',
            'feature_presentation': 'HAUPTFILM',
            'feature': 'HAUPT',
            'presentation': 'FILM',
            'now_showing': 'JETZT IM PROGRAMM',
            'at': 'auf',
            'coming_soon_to': 'DEMN\\u00c4CHST AUF',
            'available_now': 'Jetzt verf\\u00fcgbar!',
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
        """Get font file path and escaped version for FFmpeg"""
        if font_name in self._font_cache:
            return self._font_cache[font_name]
        
        windows_fonts = os.environ.get('WINDIR', r'C:\Windows') + r'\Fonts'
        
        # Font mappings for different styles
        font_files = {
            'arial': ['arial.ttf', 'ArialMT.ttf'],
            'arial_bold': ['arialbd.ttf', 'Arial-BoldMT.ttf'],
            'times': ['times.ttf', 'TimesNewRomanPSMT.ttf'],
            'georgia': ['georgia.ttf', 'Georgia.ttf'],
            'impact': ['impact.ttf', 'Impact.ttf'],
            'segoe': ['segoeui.ttf', 'SegoeUI.ttf'],
            'segoe_bold': ['segoeuib.ttf', 'SegoeUI-Bold.ttf'],
            'consolas': ['consola.ttf', 'Consolas.ttf'],
        }
        
        candidates = font_files.get(font_name, ['arial.ttf'])
        font_file = None
        
        for candidate in candidates:
            path = os.path.join(windows_fonts, candidate)
            if os.path.exists(path):
                font_file = path
                break
        
        if not font_file:
            # Fallback to arial
            font_file = os.path.join(windows_fonts, 'arial.ttf')
        
        if os.path.exists(font_file):
            escaped = font_file.replace('\\', '/').replace(':', '\\:')
            result = (font_file, f":fontfile='{escaped}'")
        else:
            result = (None, "")
        
        self._font_cache[font_name] = result
        return result
    
    def is_available(self) -> bool:
        """Check if FFmpeg is available"""
        return self.ffmpeg_path is not None
    
    def check_ffmpeg_available(self) -> bool:
        """Alias for is_available - check if FFmpeg is available"""
        return self.is_available()
    
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
    
    def _run_ffmpeg_vignette_fallback(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str,
                           include_audio: bool = False,
                           custom_audio_path: str = None,
                           custom_logo_path: str = None,
                           logo_mode: str = "watermark",
                           fade_duration: float = 0) -> Optional[str]:
        """Fallback: Run FFmpeg with simple vignette (no colored orbs).
        Supports optional custom logo (faded, centered, behind text) and
        custom audio with auto fade in/out.
        logo_mode: 'watermark' = faded centered behind text, 'replace' = replaces server name text.
        fade_duration: if > 0, applies video fade in/out after all overlays (logo + text fade together)."""
        _verbose_log(f"=== VIGNETTE FALLBACK ===")
        _verbose_log(f"BG color: {bg_color}, Include audio: {include_audio}, Logo: {custom_logo_path}")
        
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
            '-f', 'lavfi',
            '-i', f'color=c={bright_bg}:s={width}x{height}:d={duration}:r=30',
        ]
        
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
            if logo_mode == 'replace':
                # Replace mode: logo below "COMING SOON TO" header, higher opacity
                logo_w = int(width * 0.25)
                logo_opacity = 0.85
                logo_y_pos = 175  # Below the header text
                _verbose_log(f"Logo REPLACE mode: width={logo_w}, opacity={logo_opacity}, y={logo_y_pos}")
            else:
                # Watermark mode: faded centered behind text
                logo_w = int(width * 0.30)
                logo_opacity = 0.15
                logo_y_pos = None  # Will use centered overlay
            filter_parts.append(
                f"[{logo_index}:v]scale={logo_w}:-1,format=rgba,"
                f"colorchannelmixer=aa={logo_opacity}[logo]"
            )
            if logo_y_pos is not None:
                filter_parts.append(f"[vout][logo]overlay=(W-w)/2:{logo_y_pos}[vcomp]")
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
        
        filter_complex_str = ";".join(filter_parts)
        
        cmd.extend([
            '-filter_complex', filter_complex_str,
            '-map', video_label,
            '-map', audio_map,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '20',
            '-c:a', 'aac',
            '-b:a', '128k',
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
                timeout=120,
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
                return self._run_ffmpeg_simple_fallback(filter_str, output_path, duration, width, height, bg_color)
        except Exception as e:
            _verbose_log(f"VIGNETTE EXCEPTION: {e}")
            logger.error(f"FFmpeg vignette error: {e}")
            return self._run_ffmpeg_simple_fallback(filter_str, output_path, duration, width, height, bg_color)
    
    def _run_ffmpeg_simple_fallback(self, filter_str: str, output_path: Path, duration: float,
                           width: int, height: int, bg_color: str) -> Optional[str]:
        """Fallback: Run FFmpeg with simple solid color background"""
        _verbose_log(f"=== SIMPLE FALLBACK (solid color) ===")
        _verbose_log(f"BG color: {bg_color}")
        
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'lavfi',
            '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r=30',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=48000:cl=stereo:d={duration}',
            '-vf', filter_str,
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
        
        try:
            logger.info(f"Running FFmpeg (fallback simple): {' '.join(cmd[:10])}...")
            _verbose_log("Executing simple fallback FFmpeg command...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=90,
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
        
        return None
    
    def get_color_themes(self) -> Dict[str, Dict[str, str]]:
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
        fade_duration: float = 1.0
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
        _verbose_log(f"Duration: {duration}s, Fade: {fade_duration}s, Size: {width}x{height}")
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
                '-framerate', '30',  # 30fps for smooth playback
                '-i', temp_image,  # Input image
                '-f', 'lavfi',
                '-i', f'anullsrc=r=48000:cl=stereo',  # Silent audio
                '-filter_complex', filter_complex,
                '-map', '[v]',
                '-map', '1:a',
                '-t', str(duration),
                '-c:v', 'libx264',
                '-preset', 'slow',  # Better quality encoding
                '-crf', '15',  # High quality (lower = better, 15-18 is very good)
                '-profile:v', 'high',  # High profile for better quality
                '-level', '4.1',  # Compatibility level
                '-c:a', 'aac',
                '-b:a', '192k',  # Better audio quality
                '-movflags', '+faststart',  # Web optimization
                str(output_path)
            ]
            
            _verbose_log(f"FFmpeg command: {' '.join(cmd)}")
            
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
        language: str = 'en'
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
        _verbose_log(f"Items: {len(items)}, Layout: {layout}, Duration: {duration}s, Audio: {include_audio}")
        _verbose_log(f"Server name: '{server_name}'")
        _verbose_log(f"Colors - BG: {bg_color}, Text: {text_color}, Accent: {accent_color}")
        _verbose_log(f"Custom audio: {custom_audio_path}, Custom logo: {custom_logo_path}, Logo mode: {logo_mode}")
        
        # Limit items
        items = items[:max_items]
        
        if not items:
            logger.warning("No items to display in Coming Soon List")
            return None
        
        if layout == "grid":
            return self._generate_list_grid_layout(
                items, server_name, duration, output_filename,
                bg_color, text_color, accent_color, width, height,
                include_audio=include_audio,
                custom_audio_path=custom_audio_path,
                custom_logo_path=custom_logo_path,
                logo_mode=logo_mode,
                language=language
            )
        else:
            return self._generate_list_text_layout(
                items, server_name, duration, output_filename,
                bg_color, text_color, accent_color, width, height,
                include_audio=include_audio,
                custom_audio_path=custom_audio_path,
                custom_logo_path=custom_logo_path,
                logo_mode=logo_mode,
                language=language
            )
    
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
        language: str = 'en'
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
        
        # Available height for items: 1080 - 270 (header area) - 50 (bottom margin) = 760
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
        
        # Build filter string
        filter_parts = []
        
        # Header: "Coming Soon to [Server Name]" or "COMING SOON TO" + logo
        has_replace_logo = logo_mode == 'replace' and custom_logo_path and os.path.isfile(custom_logo_path)
        if has_replace_logo:
            # Replace mode: single-line "COMING SOON TO" header, logo below
            filter_parts.append(
                f"drawtext=text='{coming_soon_to_text}':fontsize=80:fontcolor={accent_color}{bold_font_param}:"
                f"x=(w-text_w)/2:y={header_y}:shadowcolor=black@0.6:shadowx=2:shadowy=2"
            )
        else:
            filter_parts.append(
                f"drawtext=text='{coming_soon_text}':fontsize=80:fontcolor={accent_color}{bold_font_param}:"
                f"x=(w-text_w)/2:y={header_y}:shadowcolor=black@0.6:shadowx=2:shadowy=2"
            )
            filter_parts.append(
                f"drawtext=text='{to_text} {escaped_server}':fontsize=50:fontcolor={text_color}@0.9{font_param}:"
                f"x=(w-text_w)/2:y={subtitle_y}:alpha='if(lt(t,0.5),0,if(lt(t,1),(t-0.5)/0.5,1))'"
            )
            # Divider line (only in watermark/normal mode)
            line_y = subtitle_y + 60
            filter_parts.append(
                f"drawbox=x={width//4}:y={line_y}:w={width//2}:h=3:c={accent_color}@0.6:t=fill"
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
            date_color = '0x28a745' if item.get('available_now', False) else f'{accent_color}@0.9'
            
            # Title (left-aligned with padding)
            filter_parts.append(
                f"drawtext=text='{title}':fontsize={fontsize}:fontcolor={text_color}{font_param}:"
                f"x=200:y={item_y}:alpha='if(lt(t,{fade_delay}),0,if(lt(t,{fade_delay+0.4}),"
                f"(t-{fade_delay})/0.4,1))'"
            )
            
            # Date (right-aligned)
            filter_parts.append(
                f"drawtext=text='{date_str}':fontsize={date_fontsize}:fontcolor={date_color}{font_param}:"
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
            fade_duration=0.8
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
        language: str = 'en'
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
                    language=language
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
                '-f', 'lavfi',
                '-i', f'color=c={bg_color}:s={width}x{height}:d={duration}:r=30',
            ]
            
            # Add poster inputs
            for poster_path in poster_paths:
                cmd.extend(['-i', poster_path])
            
            # Build filter
            filter_parts = []
            
            # Label base
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
                grid_date_color = '0x28a745' if item.get('available_now', False) else f'{accent_color}@0.9'
                
                # Center text under poster - only release date
                text_center_x = x + poster_width // 2
                date_y = y + poster_height + 8
                
                # Release date only (centered, accent color) - scale font based on poster size
                date_fontsize = max(18, min(28, poster_width // 10))
                text_filters.append(
                    f"drawtext=text='{date_str}':fontsize={date_fontsize}:fontcolor={grid_date_color}{font_param}:"
                    f"x={text_center_x}-(text_w/2):y={date_y}:shadowcolor=black@0.4:shadowx=1:shadowy=1"
                )
            
            # Add header text - optimized for 2-row layout with start_y=170
            # Only show "to {server_name}" when logo_mode is NOT 'replace' (or no logo available)
            has_replace_logo = logo_mode == 'replace' and custom_logo_path and os.path.isfile(custom_logo_path)
            if has_replace_logo:
                # Replace mode: "COMING SOON TO" shifted left, logo placed to its right
                # Offset text left by ~80px to leave room for logo on the right
                header_filter = (
                    f"drawtext=text='{coming_soon_to_text}':fontsize=55:fontcolor={accent_color}{bold_font_param}:"
                    f"x=(w-text_w)/2-80:y=50:shadowcolor=black@0.5:shadowx=2:shadowy=2"
                )
            else:
                header_filter = (
                    f"drawtext=text='{coming_soon_text}':fontsize=55:fontcolor={accent_color}{bold_font_param}:"
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
                if logo_mode == 'replace':
                    # Replace mode: logo to the right of "COMING SOON TO" header
                    logo_h = 120  # Prominent size next to header
                    logo_opacity = 0.85
                    # Position: right of the shifted header text, vertically centered with header
                    logo_x = f"(W/2)+200"
                    logo_y = 15  # Vertically center logo with header area
                    _verbose_log(f"Grid logo REPLACE mode: height={logo_h}, opacity={logo_opacity}, x={logo_x}, y={logo_y}")
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
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                '-c:a', 'aac', '-b:a', '128k',
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
                timeout=120,
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
                    language=language
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
                language=language
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
