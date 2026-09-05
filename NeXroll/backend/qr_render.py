"""Styled QR rendering for the generator's QR Code template.

segno draws a plain black-on-white grid. The generator wants the code to sit in
a designed frame, so this module takes segno's module matrix and paints it with
PIL: colours, a transparent background, rounded or dotted modules, and a logo in
the middle.

Every option here can hurt scannability if pushed, so the rules that protect it
are enforced in code rather than left to the caller:

  - The three finder patterns are always drawn as solid squares. Rounding or
    dotting them is the fastest way to stop a scanner locking on, and they are
    only three of the code's several hundred modules, so nothing is lost
    visually by keeping them crisp.
  - The quiet zone is never dropped. Four modules of clear space is part of the
    spec, not decoration.
  - A logo is capped at a share of the code that stays inside what the error
    correction can rebuild. The code is always encoded at error level H, which
    recovers roughly 30 percent, and the cap leaves headroom under that.
"""

from __future__ import annotations

import io
import re
from typing import Any, Optional, Tuple

QR_MODULE_STYLES = ("square", "rounded", "dots")

# Level H recovers ~30% of the symbol. A logo covering a fifth of the area
# leaves comfortable headroom for print, screens and awkward angles.
MAX_LOGO_FRACTION = 0.22

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_color(value: Any, fallback: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    """Return an RGBA tuple for a #RRGGBB string, or the fallback.

    The string 'transparent' (or an empty value) yields None, which the renderer
    reads as "leave this fully clear" rather than "paint it white".
    """
    text = str(value or "").strip().lower()
    if not text or text in ("transparent", "none"):
        return None
    match = _HEX.match(text)
    if not match:
        return fallback
    raw = match.group(1)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)


def relative_luminance(rgb: Tuple[int, int, int, int]) -> float:
    """WCAG relative luminance, used to judge module-to-background contrast."""
    channels = []
    for value in rgb[:3]:
        srgb = value / 255.0
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def contrast_ratio(one: Tuple[int, int, int, int], two: Tuple[int, int, int, int]) -> float:
    """Contrast between two colours, 1.0 (identical) to 21.0 (black on white)."""
    first, second = relative_luminance(one), relative_luminance(two)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _finder_regions(count: int, border: int) -> list:
    """Module ranges covering the three position-detection patterns.

    Each is 7x7 in the corners of the symbol, inside the quiet zone.
    """
    inner = count - (2 * border)
    return [
        (border, border, border + 7, border + 7),
        (border + inner - 7, border, border + inner, border + 7),
        (border, border + inner - 7, border + 7, border + inner),
    ]


def render_qr_png(
    payload: str,
    size: int = 620,
    dark: Any = "#000000",
    light: Any = "#ffffff",
    style: str = "square",
    logo_bytes: Optional[bytes] = None,
) -> bytes:
    """Encode `payload` and paint it, returning PNG bytes with an alpha channel."""
    import segno
    from PIL import Image, ImageDraw

    style = str(style or "square").lower()
    if style not in QR_MODULE_STYLES:
        style = "square"

    dark_rgba = parse_color(dark, (0, 0, 0, 255)) or (0, 0, 0, 255)
    light_rgba = parse_color(light, (255, 255, 255, 255))

    qr = segno.make(payload, error="h")
    border = 4
    rows = [list(row) for row in qr.matrix_iter(border=border)]
    count = len(rows)

    target = max(120, min(1600, int(size)))
    module_px = max(2, target // count)
    edge = module_px * count

    image = Image.new("RGBA", (edge, edge), light_rgba or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    finders = _finder_regions(count, border)

    def in_finder(col: int, row: int) -> bool:
        return any(x0 <= col < x1 and y0 <= row < y1 for x0, y0, x1, y1 in finders)

    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            if not value:
                continue
            x0 = col_index * module_px
            y0 = row_index * module_px
            x1 = x0 + module_px
            y1 = y0 + module_px
            # Finder patterns stay square whatever the style, so scanners keep
            # the sharp corners they lock onto.
            if style == "square" or in_finder(col_index, row_index):
                draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=dark_rgba)
            elif style == "rounded":
                radius = max(1, module_px // 3)
                draw.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius, fill=dark_rgba)
            else:  # dots
                draw.ellipse([x0, y0, x1 - 1, y1 - 1], fill=dark_rgba)

    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            box = int(edge * MAX_LOGO_FRACTION)
            logo.thumbnail((box, box), Image.LANCZOS)
            pad = max(4, module_px)
            plate_w = logo.width + (pad * 2)
            plate_h = logo.height + (pad * 2)
            plate_x = (edge - plate_w) // 2
            plate_y = (edge - plate_h) // 2
            # A knockout behind the logo keeps its edges legible against the
            # modules. It follows the background colour so a transparent code
            # stays transparent around the mark.
            if light_rgba:
                draw.rounded_rectangle(
                    [plate_x, plate_y, plate_x + plate_w, plate_y + plate_h],
                    radius=max(2, module_px), fill=light_rgba)
            image.paste(logo, ((edge - logo.width) // 2, (edge - logo.height) // 2), logo)
        except Exception:
            # A broken logo must never cost the caller the code itself.
            pass

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def describe_contrast(dark: Any, light: Any) -> dict:
    """Report whether the chosen colours are safe for a scanner.

    A transparent background is reported as unknown rather than good or bad:
    what sits behind it is whatever the preroll theme draws.
    """
    dark_rgba = parse_color(dark, (0, 0, 0, 255)) or (0, 0, 0, 255)
    light_rgba = parse_color(light, (255, 255, 255, 255))
    if light_rgba is None:
        return {"ratio": None, "ok": None,
                "note": "Background is transparent, so contrast depends on the theme behind it."}
    ratio = contrast_ratio(dark_rgba, light_rgba)
    return {
        "ratio": round(ratio, 2),
        "ok": ratio >= 7.0,
        "note": ("Good contrast for scanning." if ratio >= 7.0
                 else "Low contrast; some scanners may struggle with this pairing."),
    }
