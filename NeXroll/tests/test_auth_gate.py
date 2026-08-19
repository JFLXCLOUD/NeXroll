import unittest

from backend.auth_gate import friendly_local_username, is_auth_gate_exempt


class AuthGateExemptionTests(unittest.TestCase):
    def test_login_logo_variants_are_public(self):
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
