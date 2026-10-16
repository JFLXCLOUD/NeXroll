import unittest
import json
from pathlib import Path

from backend.auth_gate import (
    friendly_local_username,
    is_auth_gate_exempt,
    is_cross_site_blocked,
    is_direct_local,
    is_open_cors_path,
)


def site(value, mode=None):
    headers = {"sec-fetch-site": value}
    if mode:
        headers["sec-fetch-mode"] = mode
    return headers


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

    def test_plugin_routes_stay_public_but_plugin_setup_routes_do_not(self):
        for path in ("/plugin/intros", "/plugin/stream", "/plugin/register", "/plugin/health"):
            with self.subTest(path=path):
                self.assertTrue(is_auth_gate_exempt("GET", path))
        # Only NeXroll's own (signed-in) pages call these; configure writes a
        # NeXroll URL and a new API key into the Jellyfin/Emby plugin.
        for path in ("/jellyfin/plugin/configure", "/emby/plugin/configure",
                     "/jellyfin/plugin/detect", "/emby/plugin/download"):
            with self.subTest(path=path):
                self.assertFalse(is_auth_gate_exempt("POST", path))


class CrossOriginTests(unittest.TestCase):
    def test_open_cors_only_for_plugin_and_external_api(self):
        self.assertTrue(is_open_cors_path("/plugin/intros"))
        self.assertTrue(is_open_cors_path("/external/status"))
        for path in ("/settings", "/auth/login", "/jellyfin/plugin/configure", "/pluginx", "/externals"):
            with self.subTest(path=path):
                self.assertFalse(is_open_cors_path(path))

    def test_cross_site_changes_and_api_reads_are_refused(self):
        self.assertTrue(is_cross_site_blocked("POST", "/settings", site("cross-site", "cors")))
        self.assertTrue(is_cross_site_blocked("POST", "/prerolls/upload", site("cross-site", "navigate")))  # a form post
        self.assertTrue(is_cross_site_blocked("DELETE", "/prerolls/1", site("cross-site", "cors")))
        self.assertTrue(is_cross_site_blocked("POST", "/auth/register", site("cross-site", "no-cors")))
        self.assertTrue(is_cross_site_blocked("GET", "/backup/database", site("cross-site", "cors")))

    def test_links_embeds_and_own_pages_are_allowed(self):
        self.assertFalse(is_cross_site_blocked("GET", "/", site("cross-site", "navigate")))
        self.assertFalse(is_cross_site_blocked("GET", "/static/thumbnails/a.jpg", site("cross-site", "no-cors")))
        self.assertFalse(is_cross_site_blocked("POST", "/settings", site("same-origin", "cors")))
        self.assertFalse(is_cross_site_blocked("POST", "/settings", site("same-site", "cors")))  # dev UI on :3000
        self.assertFalse(is_cross_site_blocked("GET", "/", site("none", "navigate")))  # typed or bookmarked

    def test_scripts_plugins_and_api_key_routes_are_never_refused(self):
        self.assertFalse(is_cross_site_blocked("POST", "/settings", {}))  # curl, plugins, other servers
        self.assertFalse(is_cross_site_blocked("GET", "/plugin/intros", site("cross-site", "cors")))
        self.assertFalse(is_cross_site_blocked("POST", "/external/schedules", site("cross-site", "cors")))
        self.assertFalse(is_cross_site_blocked("GET", "/health", site("cross-site", "cors")))
        self.assertFalse(is_cross_site_blocked("OPTIONS", "/settings", site("cross-site", "cors")))


class DirectLocalTests(unittest.TestCase):
    def test_local_curl_and_browser_count_as_local(self):
        self.assertTrue(is_direct_local("127.0.0.1", {"host": "localhost:9393"}))
        self.assertTrue(is_direct_local("127.0.0.1", {"host": "127.0.0.1:9393"}))
        self.assertTrue(is_direct_local("::1", {"host": "[::1]:9393"}))
        self.assertTrue(is_direct_local("127.0.0.1", {"host": "localhost"}))
        self.assertTrue(is_direct_local("127.0.0.1", {}))  # HTTP/1.0, no Host

    def test_other_machines_are_not_local(self):
        self.assertFalse(is_direct_local("192.168.1.20", {"host": "localhost:9393"}))
        self.assertFalse(is_direct_local("", {"host": "localhost:9393"}))

    def test_relayed_requests_are_not_local(self):
        # A reverse proxy or tunnel on this machine connects from 127.0.0.1 too.
        for header in ("x-forwarded-for", "x-real-ip", "forwarded", "cf-connecting-ip", "x-forwarded-host"):
            with self.subTest(header=header):
                self.assertFalse(is_direct_local("127.0.0.1", {"host": "localhost:9393", header: "203.0.113.5"}))
        self.assertFalse(is_direct_local("127.0.0.1", {"host": "nexroll.example.com"}))
        self.assertFalse(is_direct_local("127.0.0.1", {"host": "192.168.1.5:9393"}))

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
