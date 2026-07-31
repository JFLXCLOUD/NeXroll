from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from reddit_manager.constants import DEFAULT_CONFIG_PATH  # noqa: E402
from reddit_manager.environment import Credentials  # noqa: E402
from reddit_manager.gateway import PrawGateway  # noqa: E402
from reddit_manager.planner import Action  # noqa: E402
from reddit_manager.spec import load_spec  # noqa: E402


class FakeModeration:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []
        self.remote = {
            "type": "public",
            "lang": "en",
            "flair_enabled": True,
            "flair_position": "right",
            "flair_self_assign_enabled": False,
            "link_flair_position": "left",
            "link_flair_self_assign_enabled": False,
        }

    def settings(self) -> dict[str, object]:
        return dict(self.remote)

    def update(self, **settings: object) -> None:
        self.updated.append(settings)


class FakeFlair:
    def __init__(self) -> None:
        self.configured: list[dict[str, object]] = []
        self.link_templates: list[dict[str, object]] = []

    def configure(self, **settings: object) -> None:
        self.configured.append(settings)


class FakeSubreddit:
    def __init__(self) -> None:
        self.mod = FakeModeration()
        self.flair = FakeFlair()


class FakeReddit:
    def __init__(self) -> None:
        self.community = FakeSubreddit()
        self.user = SimpleNamespace(me=lambda: "nexroll_mod")

    def subreddit(self, _name: str) -> FakeSubreddit:
        return self.community


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec(DEFAULT_CONFIG_PATH)
        self.reddit = FakeReddit()
        self.gateway = PrawGateway(
            Credentials("", "", "", ""),
            self.spec,
            reddit=self.reddit,
        )

    def test_settings_capture_normalizes_api_names(self) -> None:
        captured = self.gateway._capture_settings()

        self.assertEqual("public", captured["subreddit_type"])
        self.assertEqual("en", captured["language"])
        self.assertTrue(captured["user_flair_enabled"])
        self.assertTrue(captured["post_flair_enabled"])

    def test_flair_settings_do_not_reach_native_settings_endpoint(self) -> None:
        action = Action(
            section="settings",
            operation="update",
            key="community",
            summary="Update settings",
            payload={
                "changes": {
                    "title": "NeXroll",
                    "language": "en",
                    "user_flair_enabled": True,
                    "user_flair_self_assignable": True,
                    "post_flair_enabled": True,
                    "post_flair_self_assignable": True,
                }
            },
        )

        self.gateway._apply_settings(action)

        self.assertEqual(
            [{"title": "NeXroll", "language": "en"}],
            self.reddit.community.mod.updated,
        )
        self.assertEqual(
            [
                {
                    "position": "right",
                    "self_assign": True,
                    "link_position": "left",
                    "link_self_assign": True,
                }
            ],
            self.reddit.community.flair.configured,
        )

    def test_brittle_widget_error_becomes_manual_fallback(self) -> None:
        action = Action(
            section="sidebar",
            operation="create",
            key="Example",
            summary="Create sidebar widget 'Example'",
            payload={
                "item": {
                    "kind": "unsupported",
                    "short_name": "Example",
                }
            },
        )

        report = self.gateway.apply([action])

        self.assertTrue(report.ok)
        self.assertFalse(report.applied)
        self.assertEqual(1, len(report.manual_fallbacks))

    def test_widget_snapshot_supports_praw_button_objects_and_styles(self) -> None:
        button = SimpleNamespace(text="Documentation", url="https://example.com")
        widget = SimpleNamespace(
            id="widget-id",
            kind="button",
            shortName="Get NeXroll",
            styles={
                "backgroundColor": "#1A1A1A",
                "headerColor": "#00D4FF",
            },
            buttons=[button],
        )

        captured = self.gateway._snapshot_widget(widget)

        self.assertEqual(
            [{"label": "Documentation", "url": "https://example.com"}],
            captured["buttons"],
        )
        self.assertEqual("#00D4FF", captured["styles"]["headerColor"])

    def test_flair_lookup_accepts_praw_text_key(self) -> None:
        self.reddit.community.flair.link_templates = [
            {"id": "flair-id", "text": "Announcement"}
        ]
        self.assertEqual("flair-id", self.gateway._flair_id("announcement"))

    def test_missing_configured_post_flair_fails_before_submission(self) -> None:
        action = Action(
            section="posts",
            operation="create",
            key="Launch",
            summary="Create pinned post 'Launch'",
            payload={
                "post": {
                    "title": "Launch",
                    "body": "Hello",
                    "flair": "Announcement",
                    "sticky_slot": 1,
                }
            },
        )

        report = self.gateway.apply([action])

        self.assertFalse(report.ok)
        self.assertIn("posts:Launch failed", report.errors[0])


if __name__ == "__main__":
    unittest.main()
