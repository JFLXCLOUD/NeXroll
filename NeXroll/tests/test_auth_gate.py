import unittest
import json
from pathlib import Path

from backend.auth_gate import friendly_local_username, is_auth_gate_exempt


class AuthGateExemptionTests(unittest.TestCase):
    def test_manifest_icons_are_available_before_login(self):
        public = Path(__file__).resolve().parents[1] / "frontend" / "public"
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        for icon in manifest["icons"]:
            with self.subTest(icon=icon["src"]):
                self.assertTrue((public / icon["src"]).is_file())
                self.assertTrue(is_auth_gate_exempt("GET", "/" + icon["src"]))
        self.assertTrue(is_auth_gate_exempt("GET", "/icons/apple-touch-icon.png"))
        self.assertFalse(is_auth_gate_exempt("GET", "/icons-private"))

    def test_login_logo_variants_are_public(self):
        public = Path(__file__).resolve().parents[1] / "frontend" / "public"
        for name in ("nexroll-logo-black.png", "nexroll-logo-white.png"):
            with self.subTest(logo=name):
                self.assertTrue((public / "icons" / name).is_file())
                self.assertTrue(is_auth_gate_exempt("GET", "/icons/" + name))
        self.assertTrue(is_auth_gate_exempt("GET", "/NeXroll_Logo_BLK.png"))
        self.assertTrue(is_auth_gate_exempt("GET", "/NeXroll_Logo_WHT.png"))

    def test_static_assets_and_preflight_remain_public(self):
        self.assertTrue(is_auth_gate_exempt("GET", "/static/js/main.js"))
        self.assertTrue(is_auth_gate_exempt("OPTIONS", "/categories"))

    def test_api_routes_are_not_exempt(self):
        self.assertFalse(is_auth_gate_exempt("GET", "/categories"))
        self.assertFalse(is_auth_gate_exempt("POST", "/settings"))

    def test_local_username_prefers_windows_account_and_strips_domain(self):
        self.assertEqual(
            friendly_local_username({"USERNAME": "MEDIA\\JB", "USER": "ignored"}),
            "JB",
        )

    def test_local_username_suppresses_service_accounts(self):
        self.assertEqual(friendly_local_username({"USERNAME": "SYSTEM"}), "")
        self.assertEqual(friendly_local_username({"USER": "root"}), "")


if __name__ == "__main__":
    unittest.main()
