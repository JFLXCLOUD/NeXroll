"""Static renders of the animated theme backdrops.

Dynamic prerolls are recorded straight from the browser canvas, so they get the
themed backdrop for free. A Coming Soon list cannot: it is assembled
server-side by FFmpeg from real posters and titles, and it also regenerates
automatically after a sync, where no browser exists. So the effects are redrawn
here with Pillow and handed to FFmpeg as a still.

Kept deliberately parallel to drawDynamicThemeBackdrop in
frontend/src/utils/dynamicPrerollMotion.js - same effect names, same layout
fractions, same colour roles - so the preview and the render agree. A frame
from mid-animation is used rather than t=0, which is what the preview settles
into and avoids a backdrop that looks like it has not started yet.
"""

import math
from typing import Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter
    PILLOW_AVAILABLE = True
except ImportError:  # Rendering falls back to the flat colour without Pillow.
    PILLOW_AVAILABLE = False

# Smooth gradients are drawn on a reduced grid and scaled up: evaluating them
# per pixel at 1080p in pure Python would dominate the render, and the falloff
# is smooth enough that the upscale is indistinguishable. Crisp elements (grid
# lines, stars, arcs) are drawn afterwards at full size.
_LOW_W, _LOW_H = 320, 180

TAU = math.pi * 2


def _rgb(value: str, fallback: str = "#000000") -> Tuple[int, int, int]:
    text = str(value or fallback).replace("0x", "").replace("#", "").strip()
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        text = str(fallback).replace("#", "")
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _seeded_unit(seed: float) -> float:
    """Mirrors seededUnit() in the preview so scattered detail lands alike."""
    value = math.sin(seed * 12.9898) * 43758.5453
    return value - math.floor(value)


def _radial(size, center, radius, color, peak_alpha):
    """A soft radial falloff as an RGBA layer, drawn small and scaled up."""
    width, height = size
    cx, cy = center
    layer = Image.new("RGBA", (_LOW_W, _LOW_H), (0, 0, 0, 0))
    sx, sy = _LOW_W / width, _LOW_H / height
    lcx, lcy = cx * sx, cy * sy
    lr = max(1.0, radius * sx)
    pixels = []
    for y in range(_LOW_H):
        dy = (y - lcy) ** 2
        for x in range(_LOW_W):
            distance = math.sqrt((x - lcx) ** 2 + dy) / lr
            alpha = 0 if distance >= 1 else int(peak_alpha * 255 * (1 - distance) ** 2)
            pixels.append((color[0], color[1], color[2], alpha))
    layer.putdata(pixels)
    return layer.resize((width, height), Image.LANCZOS)


def _vignette_mask(size, strength=0.55):
    width, height = size
    layer = Image.new("L", (_LOW_W, _LOW_H), 0)
    cx, cy = _LOW_W / 2, _LOW_H / 2
    longest = math.sqrt(cx ** 2 + cy ** 2)
    pixels = []
    for y in range(_LOW_H):
        dy = (y - cy) ** 2
        for x in range(_LOW_W):
            distance = math.sqrt((x - cx) ** 2 + dy) / longest
            pixels.append(int(min(1.0, max(0.0, (distance - 0.42) / 0.58)) * 255 * strength))
    layer.putdata(pixels)
    return layer.resize((width, height), Image.LANCZOS)


def render_backdrop(path, effect: str, bg: str, primary: str, secondary: str,
                    accent: str, width: int = 1920, height: int = 1080) -> Optional[str]:
    """Draw `effect` at `width`x`height` and save it to `path`.

    Returns the path on success, or None so the caller can fall back to a flat
    background rather than failing the whole render.
    """
    if not PILLOW_AVAILABLE:
        return None
    try:
        effect = str(effect or "orbital").lower()
        bg_rgb = _rgb(bg, "#141428")
        pri = _rgb(primary, "#00d4ff")
        sec = _rgb(secondary, "#7b2cbf")
        acc = _rgb(accent, "#ff006e")
        size = (width, height)
        scale = height / 720.0
        # A representative moment in the loop, matching the preview's feel.
        elapsed = 3.0
        drift_x = math.sin(elapsed / 7 * TAU)
        drift_y = math.cos(elapsed / 8.5 * TAU)

        base = Image.new("RGBA", size, bg_rgb + (255,))

        def over(layer):
            base.alpha_composite(layer)

        if effect == "aurora":
            ribbons = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(ribbons)
            for ribbon in range(4):
                colour = sec if ribbon % 2 else pri
                points = []
                for step in range(17):
                    x = (step / 16) * width
                    wave = math.sin((step * 0.68) + (elapsed * 0.6) + ribbon) * height * (0.035 + ribbon * 0.006)
                    points.append((x, height * (0.25 + ribbon * 0.105) + wave + drift_y * 8 * scale))
                draw.line(points, fill=colour + (90,),
                          width=max(1, int(height * (0.075 - ribbon * 0.008))), joint="curve")
            over(ribbons.filter(ImageFilter.GaussianBlur(radius=max(1, height * 0.03))))

        elif effect == "cyber_grid":
            horizon = height * 0.59
            over(_radial(size, (width * 0.5, horizon), height * 0.23, acc, 0.30))
            grid = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(grid)
            travel = (elapsed * 0.65) % 1
            for row in range(13):
                depth = ((row + travel) / 13) ** 2.15
                y = horizon + depth * (height - horizon)
                draw.line([(0, y), (width, y)], fill=pri + (72,), width=max(1, int(scale)))
            for column in range(-10, 11):
                draw.line([(width * 0.5 + column * width * 0.012, horizon),
                           (width * 0.5 + column * width * 0.09, height)],
                          fill=pri + (72,), width=max(1, int(scale)))
            for index in range(7):
                block_w = width * (0.035 + _seeded_unit(index + 20) * 0.075)
                x = _seeded_unit(index + 40) * width
                y = height * (0.14 + _seeded_unit(index + 60) * 0.3)
                draw.rectangle([x, y, x + block_w, y + max(1, 2 * scale)], fill=acc + (60,))
            over(grid)

        elif effect == "solar":
            fx = width * (0.78 + drift_x * 0.012)
            fy = height * (0.32 + drift_y * 0.01)
            over(_radial(size, (fx, fy), height * 0.54, pri, 0.34))
            over(_radial(size, (fx, fy), height * 0.22, acc, 0.28))
            rays = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(rays)
            for ray in range(18):
                angle = (TAU / 18) * ray + elapsed * 0.025
                draw.line([(fx, fy), (fx + math.cos(angle) * height * 0.75,
                                      fy + math.sin(angle) * height * 0.75)],
                          fill=acc + (26,), width=max(1, int(3 * scale)))
            over(rays.filter(ImageFilter.GaussianBlur(radius=max(1, height * 0.012))))

        elif effect == "starfield":
            stars = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(stars)
            for index in range(150):
                x = _seeded_unit(index + 1) * width
                y = _seeded_unit(index + 101) * height
                depth = _seeded_unit(index + 201)
                radius = max(1.0, (0.6 + depth * 1.7) * scale)
                twinkle = 0.25 + 0.65 * abs(math.sin(elapsed * (0.7 + depth) + index))
                colour = acc if index % 7 == 0 else pri
                draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                             fill=colour + (int(twinkle * 255),))
            for ring in range(3):
                rx = width * (0.17 + ring * 0.1)
                ry = height * (0.06 + ring * 0.035)
                draw.ellipse([width * 0.5 - rx, height * 0.49 - ry,
                              width * 0.5 + rx, height * 0.49 + ry],
                             outline=sec + (40,), width=max(1, int(1.2 * scale)))
            over(stars)

        elif effect == "luxe":
            over(_radial(size, (width * 0.48, height * 0.4), height * 0.75, pri, 0.20))
            arcs = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(arcs)
            for arc in range(5):
                cx = width * (0.12 + arc * 0.2)
                rx = width * 0.28
                ry = height * (0.42 + arc * 0.025)
                draw.arc([cx - rx, height * 0.55 - ry, cx + rx, height * 0.55 + ry],
                         200, 340, fill=pri + (52,), width=max(1, int(1.2 * scale)))
            for fleck in range(28):
                x = _seeded_unit(fleck + 501) * width
                y = _seeded_unit(fleck + 601) * height
                alpha = int((0.12 + 0.28 * abs(math.sin(elapsed * 0.8 + fleck))) * 255)
                draw.rectangle([x, y, x + max(1, scale), y + max(1, scale)], fill=pri + (alpha,))
            over(arcs)

        else:  # orbital, and anything unrecognised
            over(_radial(size, (width * (0.10 + drift_x * 0.025), height * (0.10 + drift_y * 0.018)),
                         height * 0.46, sec, 0.16))
            over(_radial(size, (width * (0.91 - drift_x * 0.022), height * (0.91 - drift_y * 0.02)),
                         height * 0.42, acc, 0.16))

        # Centre glow and scanlines, exactly as the preview layers them.
        over(_radial(size, (width * 0.5, height * 0.45), height * 0.34, pri, 0.16))
        lines = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(lines)
        line_alpha = 8 if effect == "cyber_grid" else 5
        for y in range(0, height, max(3, int(3 * scale))):
            draw.line([(0, y), (width, y)], fill=(255, 255, 255, line_alpha), width=max(1, int(scale)))
        over(lines)

        flat = base.convert("RGB")
        flat = Image.composite(Image.new("RGB", size, (0, 0, 0)), flat, _vignette_mask(size))
        flat.save(str(path), "PNG")
        return str(path)
    except Exception:
        return None
