import unittest

from backend.auth_gate import is_auth_gate_exempt


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


if __name__ == "__main__":
    unittest.main()
