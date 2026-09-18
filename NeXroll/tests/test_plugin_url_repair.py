"""When a media-server plugin is pointed somewhere it cannot reach.

The plugin runs inside Jellyfin or Emby, so `localhost` resolves to the media
server, not to NeXroll. A production install had the plugin Active with
`http://localhost:9393` configured and zero check-ins, while Plex on the same
NeXroll played prerolls perfectly - nothing reported an error, because nothing
was broken; the two halves simply never met.
"""
import unittest

from backend.plugin_url_repair import (
    is_unreachable_from_server,
    should_repair,
    describe_repair,
)

LAN = "http://192.168.1.154:9393"


class UnreachableAddressTests(unittest.TestCase):
    def test_loopback_is_unreachable_when_nexroll_is_elsewhere(self):
        for url in ("http://localhost:9393", "http://127.0.0.1:9393",
                    "http://0.0.0.0:9393", "http://[::1]:9393"):
            self.assertTrue(is_unreachable_from_server(url, LAN), url)

    def test_an_unset_address_is_unreachable(self):
        self.assertTrue(is_unreachable_from_server("", LAN))
        self.assertTrue(is_unreachable_from_server(None, LAN))
        self.assertTrue(is_unreachable_from_server("   ", LAN))

    def test_a_routable_address_is_left_alone(self):
        self.assertFalse(is_unreachable_from_server(LAN, LAN))
        self.assertFalse(is_unreachable_from_server("http://nexroll.lan:9393", LAN))
        self.assertFalse(is_unreachable_from_server("https://nexroll.example.com", LAN))

    def test_a_different_port_on_the_same_host_is_still_routable(self):
        # Not our business: the host resolves, so the plugin can reach it.
        self.assertFalse(is_unreachable_from_server("http://192.168.1.154:9999", LAN))

    def test_loopback_stays_when_nexroll_really_is_on_that_host(self):
        # A plugin running natively beside NeXroll can use loopback.
        self.assertFalse(
            is_unreachable_from_server("http://localhost:9393", "http://localhost:9393"))

    def test_a_malformed_address_is_treated_as_unreachable_only_if_empty(self):
        self.assertFalse(is_unreachable_from_server("not a url", LAN))


class ShouldRepairTests(unittest.TestCase):
    def test_repairs_a_loopback_address_that_never_checked_in(self):
        self.assertTrue(should_repair("http://localhost:9393", LAN, plugin_has_checked_in=False))

    def test_never_touches_a_plugin_that_is_working(self):
        """The decisive safety rule.

        A plugin that has checked in is reaching NeXroll somehow, possibly by a
        route this process cannot see. Repointing it would break a working
        install to fix a theoretical one.
        """
        self.assertFalse(should_repair("http://localhost:9393", LAN, plugin_has_checked_in=True))

    def test_leaves_a_good_address_alone(self):
        self.assertFalse(should_repair(LAN, LAN, plugin_has_checked_in=False))

    def test_does_nothing_without_a_suggestion_to_apply(self):
        self.assertFalse(should_repair("http://localhost:9393", "", plugin_has_checked_in=False))
        self.assertFalse(should_repair("http://localhost:9393", None, plugin_has_checked_in=False))

    def test_repairs_an_unset_address(self):
        self.assertTrue(should_repair("", LAN, plugin_has_checked_in=False))


class DescribeRepairTests(unittest.TestCase):
    def test_names_both_addresses(self):
        msg = describe_repair("http://localhost:9393", LAN)
        self.assertIn("http://localhost:9393", msg)
        self.assertIn(LAN, msg)

    def test_says_when_nothing_was_set(self):
        self.assertIn("(not set)", describe_repair("", LAN))


if __name__ == "__main__":
    unittest.main()
