import unittest

from backend.dashboard_layout import (
    NEW_IN_V2,
    SCHEMA_VERSION,
    TILE_KEYS,
    apply_preset,
    default_layout,
    preset_tiles,
    upgrade_layout,
)

# A real v1 layout, copied from a 2.0.5 database.
V1_LAYOUT = {
    "version": 1,
    "grid": {"cols": 4, "rows": 2},
    "order": ["servers", "prerolls", "storage", "schedules", "scheduler",
              "current_category", "community", "nexup", "upcoming",
              "resolution_chart", "weekly_calendar"],
    "hidden": [],
    "locked": False,
}


class DefaultLayoutTests(unittest.TestCase):
    def test_default_is_current_version_and_covers_every_tile(self):
        layout = default_layout()

        self.assertEqual(layout["version"], SCHEMA_VERSION)
        self.assertEqual(set(layout["order"]), set(TILE_KEYS))
        self.assertEqual(set(layout["tiles"]), set(TILE_KEYS))

    def test_default_hides_exactly_what_the_preset_leaves_out(self):
        layout = default_layout("essential")
        visible = [key for key in layout["order"] if key not in layout["hidden"]]

        self.assertEqual(set(visible), set(preset_tiles("essential")))

    def test_essential_matches_the_five_focus_panels_in_display_order(self):
        layout = default_layout("essential")
        visible = [key for key in layout["order"] if key not in layout["hidden"]]

        self.assertEqual(visible, [
            "now_showing", "system_health", "prerolls",
            "quick_actions", "storage_mix",
        ])
        self.assertEqual(layout["tiles"]["now_showing"]["size"], "md")
        for key in visible[1:]:
            self.assertEqual(layout["tiles"][key]["size"], "sm")

    def test_everything_preset_hides_nothing(self):
        layout = default_layout("everything")
        self.assertEqual(layout["hidden"], [])


class UpgradeFromV1Tests(unittest.TestCase):
    def test_v1_layout_is_upgraded_not_discarded(self):
        upgraded = upgrade_layout(V1_LAYOUT)

        self.assertEqual(upgraded["version"], SCHEMA_VERSION)
        self.assertIn("tiles", upgraded)
        self.assertIn("preferences", upgraded)

    def test_existing_tiles_keep_their_relative_order(self):
        upgraded = upgrade_layout(V1_LAYOUT)
        kept = [key for key in upgraded["order"] if key in V1_LAYOUT["order"]]

        self.assertEqual(kept, V1_LAYOUT["order"])

    def test_new_tiles_are_added_at_the_front_and_visible(self):
        upgraded = upgrade_layout(V1_LAYOUT)

        self.assertEqual(upgraded["order"][:len(NEW_IN_V2)], list(NEW_IN_V2))
        for key in NEW_IN_V2:
            self.assertNotIn(key, upgraded["hidden"])

    def test_a_hidden_tile_stays_hidden_through_the_upgrade(self):
        stored = dict(V1_LAYOUT, hidden=["nexup", "community"])

        upgraded = upgrade_layout(stored)

        self.assertIn("nexup", upgraded["hidden"])
        self.assertIn("community", upgraded["hidden"])

    def test_upgraded_layout_is_marked_custom_not_a_preset(self):
        # The user arranged this themselves; claiming it matches a preset would
        # make the Customize modal show the wrong preset as selected.
        self.assertEqual(upgrade_layout(V1_LAYOUT)["preset"], "custom")

    def test_lock_state_and_grid_survive(self):
        upgraded = upgrade_layout(dict(V1_LAYOUT, locked=True))

        self.assertTrue(upgraded["locked"])
        self.assertEqual(upgraded["grid"], {"cols": 4, "rows": 2})


class UpgradeRobustnessTests(unittest.TestCase):
    def test_empty_or_missing_layout_yields_the_default(self):
        for stored in (None, {}, [], "not a layout", 42):
            with self.subTest(stored=stored):
                self.assertEqual(upgrade_layout(stored), default_layout())

    def test_unknown_tile_keys_are_dropped(self):
        stored = dict(V1_LAYOUT, order=["prerolls", "recent_genres", "made_up_tile"])

        upgraded = upgrade_layout(stored)

        self.assertNotIn("recent_genres", upgraded["order"])
        self.assertNotIn("made_up_tile", upgraded["order"])
        self.assertIn("prerolls", upgraded["order"])

    def test_duplicate_keys_are_collapsed(self):
        stored = dict(V1_LAYOUT, order=["prerolls", "prerolls", "storage"])

        order = upgrade_layout(stored)["order"]

        self.assertEqual(order.count("prerolls"), 1)

    def test_every_known_tile_is_present_even_if_the_stored_order_omits_it(self):
        stored = dict(V1_LAYOUT, order=["prerolls"])

        upgraded = upgrade_layout(stored)

        self.assertEqual(set(upgraded["order"]), set(TILE_KEYS))

    def test_hidden_entries_for_unknown_tiles_are_dropped(self):
        stored = dict(V1_LAYOUT, hidden=["made_up_tile", "nexup"])

        self.assertEqual(upgrade_layout(stored)["hidden"], ["nexup"])

    def test_invalid_span_detail_and_density_fall_back_to_defaults(self):
        stored = {
            "version": 2,
            "order": list(TILE_KEYS),
            "hidden": [],
            "tiles": {"system_health": {"size": "enormous", "detail": "cinematic"}},
            "preferences": {"density": "airy", "greeting": "yes"},
        }

        upgraded = upgrade_layout(stored)

        self.assertEqual(upgraded["tiles"]["system_health"]["size"], "sm")
        self.assertEqual(upgraded["tiles"]["system_health"]["detail"], "detailed")
        self.assertEqual(upgraded["preferences"]["density"], "comfortable")
        self.assertTrue(upgraded["preferences"]["greeting"])  # non-bool ignored

    def test_valid_v2_values_are_preserved(self):
        stored = {
            "version": 2,
            "preset": "operations",
            "order": list(TILE_KEYS),
            "hidden": ["community"],
            "locked": False,
            "tiles": {"now_showing": {"size": "lg", "detail": "compact"}},
            "preferences": {"greeting": False, "healthNote": False,
                            "dateTime": True, "density": "compact"},
        }

        upgraded = upgrade_layout(stored)

        self.assertEqual(upgraded["preset"], "operations")
        self.assertEqual(upgraded["tiles"]["now_showing"], {"size": "lg", "detail": "compact"})
        self.assertFalse(upgraded["preferences"]["greeting"])
        self.assertEqual(upgraded["preferences"]["density"], "compact")
        self.assertEqual(upgraded["hidden"], ["community"])

    def test_upgrade_is_idempotent(self):
        once = upgrade_layout(V1_LAYOUT)
        twice = upgrade_layout(once)

        self.assertEqual(once, twice)

    def test_upgrade_does_not_mutate_the_stored_dict(self):
        stored = dict(V1_LAYOUT)
        snapshot = dict(stored)

        upgrade_layout(stored)

        self.assertEqual(stored, snapshot)


class PresetTests(unittest.TestCase):
    def test_applying_a_preset_sets_composition_and_keeps_tile_settings(self):
        layout = upgrade_layout(V1_LAYOUT)
        layout["tiles"]["now_showing"] = {"size": "lg", "detail": "compact"}

        applied = apply_preset(layout, "essential")

        self.assertEqual(applied["tiles"]["now_showing"], {"size": "lg", "detail": "compact"})
        visible = [key for key in applied["order"] if key not in applied["hidden"]]
        self.assertEqual(visible, list(preset_tiles("essential")))
        optional_before = [key for key in layout["order"] if key not in visible]
        optional_after = [key for key in applied["order"] if key not in visible]
        self.assertEqual(optional_after, optional_before)

    def test_applying_a_preset_records_which_preset_is_active(self):
        self.assertEqual(apply_preset(V1_LAYOUT, "operations")["preset"], "operations")

    def test_unknown_preset_is_recorded_as_custom(self):
        self.assertEqual(apply_preset(V1_LAYOUT, "bespoke")["preset"], "custom")

    def test_apply_preset_does_not_mutate_its_input(self):
        layout = upgrade_layout(V1_LAYOUT)
        snapshot = dict(layout)
        snapshot_hidden = list(layout["hidden"])

        apply_preset(layout, "essential")

        self.assertEqual(layout["hidden"], snapshot_hidden)
        self.assertEqual(layout["preset"], snapshot["preset"])


class SizePreservationTests(unittest.TestCase):
    """A v1 layout keeps per-tile sizes in a flat `sizes` map, and the grid keeps
    its own cached `layouts`. Dropping either on upgrade would silently reset an
    arrangement the user built in 2.0.x."""

    def test_v1_sizes_are_folded_into_tiles_and_kept_flat(self):
        stored = dict(V1_LAYOUT, sizes={"resolution_chart": "md", "upcoming": "lg"})

        upgraded = upgrade_layout(stored)

        self.assertEqual(upgraded["tiles"]["resolution_chart"]["size"], "md")
        self.assertEqual(upgraded["tiles"]["upcoming"]["size"], "lg")
        self.assertEqual(upgraded["sizes"]["resolution_chart"], "md")

    def test_grid_layouts_are_round_tripped_untouched(self):
        geometry = {"lg": [{"i": "prerolls", "x": 0, "y": 0, "w": 1, "h": 3}]}
        upgraded = upgrade_layout(dict(V1_LAYOUT, layouts=geometry))

        self.assertEqual(upgraded["layouts"], geometry)

    def test_sizes_and_tiles_never_disagree(self):
        upgraded = upgrade_layout(dict(V1_LAYOUT, sizes={"storage_mix": "lg"}))

        for key, tile in upgraded["tiles"].items():
            self.assertEqual(upgraded["sizes"][key], tile["size"], key)

    def test_an_invalid_size_falls_back_to_the_tile_default(self):
        upgraded = upgrade_layout(dict(V1_LAYOUT, sizes={"prerolls": "gigantic"}))

        self.assertEqual(upgraded["tiles"]["prerolls"]["size"], "sm")


if __name__ == "__main__":
    unittest.main()
