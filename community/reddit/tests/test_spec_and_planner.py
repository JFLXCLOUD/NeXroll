from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from reddit_manager.constants import DEFAULT_CONFIG_PATH, SAFE_SECTIONS  # noqa: E402
from reddit_manager.errors import ConfigurationError, ConfirmationError  # noqa: E402
from reddit_manager.managed_content import (  # noqa: E402
    AUTOMOD_BEGIN,
    AUTOMOD_END,
    SIDEBAR_BEGIN,
    SIDEBAR_END,
)
from reddit_manager.planner import (  # noqa: E402
    build_plan,
    resolve_sections,
    validate_confirmation,
)
from reddit_manager.spec import load_spec  # noqa: E402
from reddit_manager.state import sha256_file  # noqa: E402


class SpecTests(unittest.TestCase):
    def test_real_community_package_hydrates(self) -> None:
        spec = load_spec(DEFAULT_CONFIG_PATH)

        self.assertEqual("r/NeXroll", spec.subreddit)
        self.assertEqual("en", spec.data["settings"]["language"])
        self.assertEqual("#00D4FF", spec.data["settings"]["key_color"])
        self.assertNotIn("lang", spec.data["settings"])
        self.assertTrue(spec.data["settings"]["post_flair_enabled"])
        self.assertTrue(spec.data["settings"]["post_flair_self_assignable"])
        self.assertEqual("text_area", spec.data["sidebar"]["widgets"][0]["kind"])
        self.assertEqual(
            {
                "backgroundColor": "#1A1A1A",
                "headerColor": "#00D4FF",
            },
            spec.data["sidebar"]["widgets"][0]["styles"],
        )
        self.assertEqual("button", spec.data["sidebar"]["widgets"][1]["kind"])
        self.assertIn("body", spec.data["pinned_posts"][0])


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = load_spec(DEFAULT_CONFIG_PATH)

    def snapshot(self, **state: object) -> dict[str, object]:
        return {"subreddit": "r/NeXroll", "state": state}

    def test_safe_defaults_exclude_publishing_sections(self) -> None:
        self.assertEqual(SAFE_SECTIONS, resolve_sections(None))
        self.assertNotIn("posts", resolve_sections(None))
        self.assertNotIn("automoderator", resolve_sections(None))
        self.assertEqual(
            ("post_flair", "user_flair", "removal_reasons"),
            resolve_sections(["flair"]),
        )

    def test_plans_never_contain_delete_operations(self) -> None:
        state = {
            "settings": {},
            "branding": {"_managed_hashes": {}},
            "rules": [],
            "post_flair": [],
            "user_flair": [],
            "removal_reasons": [],
            "sidebar": {"widgets": [], "legacy_markdown": None},
            "wiki": {},
            "posts": [],
            "automoderator": {"content": None},
        }
        plan = build_plan(
            self.spec,
            {"subreddit": "r/NeXroll", "state": state},
            resolve_sections(["all"]),
        )
        self.assertNotIn("delete", {action.operation for action in plan.actions})

    def test_apply_confirmation_is_exact(self) -> None:
        validate_confirmation("r/NeXroll", "r/NeXroll")
        for invalid in ("nexroll", "r/nexroll", "R/NeXroll", ""):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ConfirmationError):
                    validate_confirmation(invalid, "r/NeXroll")

    def test_first_branding_apply_replaces_unknown_remote_assets(self) -> None:
        snapshot = self.snapshot(
            branding={
                "community_icon": "https://example.invalid/icon.png",
                "banner_background_image": "https://example.invalid/banner.png",
                "mobile_banner_image": "https://example.invalid/mobile.png",
                "_managed_hashes": {},
            }
        )

        plan = build_plan(self.spec, snapshot, ("branding",))

        self.assertEqual(3, len(plan.actions))
        self.assertTrue(
            all(action.operation == "upload" for action in plan.actions)
        )
        self.assertEqual(3, len(plan.warnings))

    def test_matching_branding_hashes_are_idempotent(self) -> None:
        hashes = {
            key: sha256_file(
                self.spec.resolve_path(
                    self.spec.data["branding"][key], field=f"branding.{key}"
                )
            )
            for key in ("icon", "banner", "mobile_banner")
        }
        plan = build_plan(
            self.spec,
            self.snapshot(branding={"_managed_hashes": hashes}),
            ("branding",),
        )

        self.assertFalse(plan.actions)
        self.assertEqual(
            ["branding:icon", "branding:banner", "branding:mobile_banner"],
            plan.unchanged,
        )

    def test_unavailable_section_is_never_planned(self) -> None:
        plan = build_plan(
            self.spec,
            self.snapshot(rules={"_unavailable": "Forbidden"}),
            ("rules",),
        )
        self.assertFalse(plan.actions)
        self.assertEqual(1, len(plan.warnings))

    def test_unmanaged_post_title_collision_is_never_changed(self) -> None:
        title = self.spec.data["pinned_posts"][0]["title"]
        plan = build_plan(
            self.spec,
            self.snapshot(posts=[{"title": title, "managed": False}]),
            ("posts",),
        )

        self.assertNotIn(title, {action.key for action in plan.actions})
        self.assertIn("owned by another account", plan.warnings[0])

    def test_automoderator_plan_preserves_unmanaged_content(self) -> None:
        unmanaged = "# Hand-maintained rule\n---\nrule: keep-me\n"
        plan = build_plan(
            self.spec,
            self.snapshot(automoderator={"content": unmanaged}),
            ("automoderator",),
        )

        merged = plan.actions[0].payload["content"]
        self.assertTrue(merged.startswith(unmanaged.rstrip()))
        self.assertIn(AUTOMOD_BEGIN, merged)
        self.assertIn(AUTOMOD_END, merged)
        second_plan = build_plan(
            self.spec,
            self.snapshot(automoderator={"content": merged}),
            ("automoderator",),
        )
        self.assertFalse(second_plan.actions)

    def test_legacy_sidebar_plan_preserves_unmanaged_content(self) -> None:
        unmanaged = "## Hand-maintained links\n\n- [Keep](https://example.com)\n"
        plan = build_plan(
            self.spec,
            self.snapshot(
                sidebar={
                    "widgets": [],
                    "legacy_markdown": unmanaged,
                }
            ),
            ("sidebar",),
        )

        legacy_action = next(action for action in plan.actions if action.key == "legacy")
        merged = legacy_action.payload["legacy_markdown"]
        self.assertTrue(merged.startswith(unmanaged.rstrip()))
        self.assertIn(SIDEBAR_BEGIN, merged)
        self.assertIn(SIDEBAR_END, merged)

    def test_malformed_managed_markers_stop_planning(self) -> None:
        malformed = f"unmanaged\n{AUTOMOD_BEGIN}\nmanaged without end\n"
        with self.assertRaises(ConfigurationError):
            build_plan(
                self.spec,
                self.snapshot(automoderator={"content": malformed}),
                ("automoderator",),
            )


if __name__ == "__main__":
    unittest.main()
