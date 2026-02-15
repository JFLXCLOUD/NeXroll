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
        # Check if ffmpeg is in PATH
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg:
            return ffmpeg
        
        # Common locations on Windows
        common_paths = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
            os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                return path
        
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
        """Escape text for FFmpeg drawtext filter"""
        # Escape special characters for FFmpeg
        text = text.replace("\\", "\\\\")
        text = text.replace(":", "\\:")
        text = text.replace("'", "\\'")
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
        theme: str = "midnight"
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
                bg_color, text_color, accent_color
            )
        elif style == 'minimal':
            return self._generate_minimal_coming_soon(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, accent_color
            )
        else:
            return self._generate_cinematic_coming_soon(
                server_name, duration, output_filename, width, height,
                bg_color, text_color, accent_color
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
        accent_color: str
    ) -> Optional[str]:
        """Generate cinematic style with glow effects and dramatic presentation"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        # Cinematic style: dramatic text with multiple glow layers, film grain, fades
        filter_str = (
            # Outer glow layer (creates "bloom" effect)
            f"drawtext=text='COMING SOON':fontsize=85:fontcolor={accent_color}@0.2{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.15:shadowx=8:shadowy=8,"
            # Mid glow
            f"drawtext=text='COMING SOON':fontsize=82:fontcolor={accent_color}@0.35{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.25:shadowx=5:shadowy=5,"
            # Main title
            f"drawtext=text='COMING SOON':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor=black@0.8:shadowx=3:shadowy=3,"
            # "to" text with fade-in
            f"drawtext=text='to':fontsize=42:fontcolor={text_color}@0.85{font_param}:"
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
        accent_color: str
    ) -> Optional[str]:
        """Generate neon glow style with pulsing effects"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        # Neon effect: multiple glow layers (static, since dynamic alpha expressions are complex)
        filter_str = (
            # Outer glow layer 3 (widest, faintest)
            f"drawtext=text='COMING SOON':fontsize=85:fontcolor={accent_color}@0.2{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-95:shadowcolor={accent_color}@0.15:shadowx=8:shadowy=8,"
            # Outer glow layer 2
            f"drawtext=text='COMING SOON':fontsize=82:fontcolor={accent_color}@0.35{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-97:shadowcolor={accent_color}@0.25:shadowx=5:shadowy=5,"
            # Main text with glow
            f"drawtext=text='COMING SOON':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor={accent_color}@0.6:shadowx=3:shadowy=3,"
            # "to" with fade in
            f"drawtext=text='to':fontsize=40:fontcolor={text_color}@0.8{font_param}:"
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
        accent_color: str
    ) -> Optional[str]:
        """Generate elegant minimal style"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('segoe')
        
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
            f"drawtext=text='COMING SOON':fontsize=55:fontcolor={text_color}{font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-45:alpha='if(lt(t,0.3),0,if(lt(t,1),(t-0.3)/0.7,1))',"
            # Server name
            f"drawtext=text='to {escaped_server}':fontsize=35:fontcolor={accent_color}{font_param}:"
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
        style: str = "default"
    ) -> Optional[str]:
        """Enhanced fallback that still looks good but uses simpler filters"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name)
        
        _, font_param = self._get_font_path('arial')
        _, bold_font_param = self._get_font_path('arial_bold')
        
        # Simple but visually appealing filter (no color= prefix, handled by _run_ffmpeg_simple)
        filter_str = (
            # Shadow/glow layer
            f"drawtext=text='COMING SOON':fontsize=82:fontcolor={accent_color}@0.3{bold_font_param}:"
            f"x=(w-text_w)/2+3:y=(h/2)-97:shadowcolor={accent_color}@0.2:shadowx=5:shadowy=5,"
            # Main title
            f"drawtext=text='COMING SOON':fontsize=80:fontcolor={text_color}{bold_font_param}:"
            f"x=(w-text_w)/2:y=(h/2)-100:shadowcolor=black@0.7:shadowx=3:shadowy=3,"
            # "to"
            f"drawtext=text='to':fontsize=42:fontcolor={text_color}@0.8{font_param}:"
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
                           width: int, height: int, bg_color: str) -> Optional[str]:
        """Fallback: Run FFmpeg with simple vignette (no colored orbs)"""
        _verbose_log(f"=== VIGNETTE FALLBACK ===")
        _verbose_log(f"BG color: {bg_color}")
        
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
        _verbose_log(f"Vignette filter: {vignette_filter[:100]}...")
        
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'lavfi',
            '-i', f'color=c={bright_bg}:s={width}x{height}:d={duration}:r=30',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=48000:cl=stereo:d={duration}',
            '-vf', vignette_filter,
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
            logger.info(f"Running FFmpeg vignette fallback...")
            _verbose_log("Executing vignette FFmpeg command...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
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
        theme: str = "midnight"
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
                bg_color, text_color, theme
            )
        else:
            return self._generate_classic_feature_presentation(
                server_name, duration, output_filename, width, height,
                bg_color, text_color
            )
    
    def _generate_classic_feature_presentation(
        self,
        server_name: str,
        duration: float,
        output_filename: str,
        width: int,
        height: int,
        bg_color: str,
        text_color: str
    ) -> Optional[str]:
        """Classic theater-style Feature Presentation"""
        output_path = self.output_dir / output_filename
        escaped_server = self._escape_text(server_name) if server_name else ""
        
        _, font_param = self._get_font_path('georgia')
        _, bold_font_param = self._get_font_path('arial_bold')
        
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
            f"drawtext=text='FEATURE PRESENTATION':fontsize=67:fontcolor={text_color}@0.3{bold_font_param}:x=(w-text_w)/2:y=(h/2)-55:shadowcolor={text_color}@0.2:shadowx=6:shadowy=6",
            # Main text
            f"drawtext=text='FEATURE PRESENTATION':fontsize=65:fontcolor={text_color}{bold_font_param}:x=(w-text_w)/2:y=(h/2)-55:shadowcolor=black@0.7:shadowx=3:shadowy=3",
        ]
        
        if escaped_server:
            filter_parts.extend([
                f"drawtext=text='at {escaped_server}':fontsize=32:fontcolor=white@0.8{font_param}:x=(w-text_w)/2:y=(h/2)+30:alpha='if(lt(t,1),0,if(lt(t,1.8),(t-1)/0.8,1))'"
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
        theme: str = "midnight"
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
        
        # Pre-calculate positions
        gradient_y_1 = height - 100
        gradient_y_2 = height - 80
        
        filter_parts = [
            # Gradient-like effect with multiple boxes
            f"drawbox=x=0:y={gradient_y_1}:w={width}:h=100:c={accent}@0.1:t=fill",
            f"drawbox=x=0:y={gradient_y_2}:w={width}:h=80:c={accent}@0.05:t=fill",
            # Main text with modern feel
            f"drawtext=text='FEATURE':fontsize=90:fontcolor=white{bold_font_param}:x=(w-text_w)/2:y=(h/2)-80",
            f"drawtext=text='PRESENTATION':fontsize=45:fontcolor={accent}{font_param}:x=(w-text_w)/2:y=(h/2)+10:alpha='if(lt(t,0.5),0,if(lt(t,1.2),(t-0.5)/0.7,1))'",
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
        theme: str = "midnight"
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
            f"drawtext=text='NOW SHOWING':fontsize=95:fontcolor={text_color}{font_param}:x=(w-text_w)/2:y=(h/2)-70:shadowcolor=black@0.8:shadowx=4:shadowy=4",
            # Decorative underline
            f"drawbox=x={underline_x}:y={underline_y}:w=300:h=3:c={accent}:t=fill",
        ]
        
        if escaped_server:
            filter_parts.append(
                f"drawtext=text='at {escaped_server}':fontsize=35:fontcolor={accent}{regular_font}:x=(w-text_w)/2:y=(h/2)+50"
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
        theme: str = "midnight"
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
                theme=theme
            )
        elif template_id.startswith('feature_presentation'):
            return self.generate_feature_presentation(
                server_name=server_name,
                duration=duration,
                output_filename=output_filename,
                style=style,
                theme=theme
            )
        elif template_id == 'now_showing':
            return self.generate_now_showing(
                server_name=server_name,
                duration=duration,
                output_filename=output_filename,
                theme=theme
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
