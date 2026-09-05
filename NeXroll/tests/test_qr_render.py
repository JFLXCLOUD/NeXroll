"""Styling a QR code must never stop it scanning.

There is no decoder in the test environment, so these assert the property that
decides scannability: the rendered image, sampled at the centre of every module,
must reproduce segno's own matrix exactly. Colour, module shape and a logo are
all allowed to change how it looks and none of them may change what it says.
"""

import io
import unittest

import segno
from PIL import Image, ImageDraw

from backend.qr_render import (
    MAX_LOGO_FRACTION,
    QR_MODULE_STYLES,
    contrast_ratio,
    describe_contrast,
    parse_color,
    render_qr_png,
)

PAYLOAD = "https://example.com/whats-on?utm=preroll"
BORDER = 4


def read_modules(png_bytes, count):
    """Sample the centre of every module cell and report dark or light."""
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    module_px = image.width // count
    grid = []
    for row in range(count):
        line = []
        for col in range(count):
            red, green, blue, alpha = image.getpixel(
                (col * module_px + module_px // 2, row * module_px + module_px // 2))
            line.append(1 if (alpha > 128 and (red + green + blue) / 3 < 128) else 0)
        grid.append(line)
    return grid


class QrRenderTests(unittest.TestCase):
    def setUp(self):
        self.expected = [list(r) for r in segno.make(PAYLOAD, error="h").matrix_iter(border=BORDER)]
        self.count = len(self.expected)

    def assert_matrix_intact(self, png_bytes, message):
        got = read_modules(png_bytes, self.count)
        mismatches = sum(
            1 for r in range(self.count) for c in range(self.count)
            if got[r][c] != self.expected[r][c]
        )
        self.assertEqual(mismatches, 0, f"{message}: {mismatches} modules differ")

    def test_every_module_style_preserves_the_symbol(self):
        for style in QR_MODULE_STYLES:
            with self.subTest(style=style):
                self.assert_matrix_intact(
                    render_qr_png(PAYLOAD, size=740, style=style), f"style={style}")

    def test_custom_colours_preserve_the_symbol(self):
        self.assert_matrix_intact(
            render_qr_png(PAYLOAD, size=740, dark="#1a3d7c", light="#f5f0e6", style="rounded"),
            "custom colours")

    def test_transparent_background_keeps_modules_opaque(self):
        png = render_qr_png(PAYLOAD, size=740, light="transparent")
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        module_px = image.width // self.count
        # The quiet zone is clear...
        self.assertEqual(image.getpixel((module_px // 2, module_px // 2))[3], 0)
        # ...while the modules themselves stay fully opaque.
        self.assert_matrix_intact(png, "transparent background")

    def test_finder_patterns_stay_square_in_dots_mode(self):
        """Rounding the position markers is the quickest way to stop a scan."""
        png = render_qr_png(PAYLOAD, size=740, style="dots")
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        module_px = image.width // self.count
        corner = image.getpixel((BORDER * module_px + 1, BORDER * module_px + 1))
        self.assertGreater(corner[3], 128, "finder corner should be filled, not rounded away")
        self.assertLess(sum(corner[:3]) / 3, 128)

    def test_logo_stays_within_the_error_correction_budget(self):
        logo = Image.new("RGBA", (400, 400), (255, 0, 0, 255))
        buffer = io.BytesIO()
        logo.save(buffer, format="PNG")
        png = render_qr_png(PAYLOAD, size=740, logo_bytes=buffer.getvalue())
        got = read_modules(png, self.count)
        covered = sum(
            1 for r in range(self.count) for c in range(self.count)
            if got[r][c] != self.expected[r][c]
        )
        fraction = covered / (self.count * self.count)
        # Level H recovers about 30 percent; stay well inside that.
        self.assertLess(fraction, 0.15, f"logo covers {fraction:.1%} of the symbol")
        self.assertLessEqual(MAX_LOGO_FRACTION, 0.25)

    def test_an_unreadable_logo_does_not_cost_the_code(self):
        self.assert_matrix_intact(
            render_qr_png(PAYLOAD, size=740, logo_bytes=b"not an image"), "broken logo")

    def test_an_unknown_style_falls_back_to_square(self):
        self.assert_matrix_intact(
            render_qr_png(PAYLOAD, size=740, style="hexagons"), "unknown style")

    def test_contrast_reporting(self):
        self.assertTrue(describe_contrast("#000000", "#ffffff")["ok"])
        self.assertFalse(describe_contrast("#888888", "#9a9a9a")["ok"])
        # A transparent background has no verdict to give: it depends on the theme.
        self.assertIsNone(describe_contrast("#000000", "transparent")["ok"])
        self.assertAlmostEqual(contrast_ratio((0, 0, 0, 255), (255, 255, 255, 255)), 21.0, places=1)

    def test_colour_parsing(self):
        self.assertIsNone(parse_color("transparent", (1, 1, 1, 255)))
        self.assertIsNone(parse_color("", (1, 1, 1, 255)))
        self.assertEqual(parse_color("bogus", (9, 9, 9, 255)), (9, 9, 9, 255))
        self.assertEqual(parse_color("#ff8800", None), (255, 136, 0, 255))
        self.assertEqual(parse_color("ff8800", None), (255, 136, 0, 255))


if __name__ == "__main__":
    unittest.main()
