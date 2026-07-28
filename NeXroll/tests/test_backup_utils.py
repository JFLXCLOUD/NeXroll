import json
import unittest

from backend.backup_utils import (
    normalize_preroll_id,
    remap_fixed_preroll_blocks,
    remap_preroll_ids_json,
    remap_sequence_blocks,
    remap_sequence_json,
)


class BackupReferenceRemapTests(unittest.TestCase):
    def test_normalize_preroll_id_rejects_lossy_or_invalid_values(self):
        self.assertEqual(normalize_preroll_id(" 12 "), 12)
        for value in (None, True, 0, -1, 1.5, "", "1.5", "not-an-id"):
            with self.subTest(value=value):
                self.assertIsNone(normalize_preroll_id(value))

    def test_schedule_preroll_ids_drop_unmapped_values_without_retargeting(self):
        # Old ID 2 disappears. New ID 2 belongs to old ID 9, so retaining the
        # raw 2 would silently select the wrong preroll after restore.
        result = remap_preroll_ids_json("[2, 5, 9, \"5\", null]", {5: 1, 9: 2})
        self.assertEqual(json.loads(result), [1, 2, 1])

    def test_schedule_preroll_ids_return_none_for_invalid_or_empty_references(self):
        self.assertIsNone(remap_preroll_ids_json("not-json", {1: 10}))
        self.assertIsNone(remap_preroll_ids_json("[1, 2]", {}))
        self.assertIsNone(remap_preroll_ids_json(None, {1: 10}))

    def test_fixed_blocks_remap_single_and_array_ids_without_mutating_input(self):
        original = [
            {"type": "fixed", "preroll_id": "5", "label": "single"},
            {"type": "fixed", "preroll_ids": [9, 2, "5"], "label": "array"},
            {"type": "fixed", "preroll_id": 2, "preroll_ids": [2]},
            {"type": "random", "category_id": 4, "preroll_ids": [2]},
        ]

        result = remap_fixed_preroll_blocks(original, {5: 101, 9: 102})

        self.assertEqual(result[0]["preroll_id"], 101)
        self.assertEqual(result[1]["preroll_ids"], [102, 101])
        self.assertNotIn("preroll_id", result[2])
        self.assertEqual(result[2]["preroll_ids"], [])
        self.assertEqual(result[3]["preroll_ids"], [2])
        self.assertEqual(original[0]["preroll_id"], "5")
        self.assertEqual(original[1]["preroll_ids"], [9, 2, "5"])

    def test_schedule_sequence_json_uses_same_fixed_block_remapping(self):
        raw = json.dumps([
            {"type": "fixed", "preroll_ids": [7, 8]},
            {"type": "fixed", "preroll_id": 8},
        ])
        result = json.loads(remap_sequence_json(raw, {7: 70}))
        self.assertEqual(result, [
            {"type": "fixed", "preroll_ids": [70]},
            {"type": "fixed"},
        ])

    def test_category_backed_blocks_remap_both_supported_types_and_key_styles(self):
        original = [
            {"type": "random", "category_id": 5, "count": 2},
            {"type": "sequential", "categoryId": "9", "count": 1},
            {"type": "sequential", "category_id": 2, "category_name": "Missing"},
            {"type": "fixed", "category_id": 2, "preroll_ids": [7]},
            {"type": "dynamic_preroll", "category_id": 2},
        ]

        result = remap_sequence_blocks(original, {7: 70}, {5: 101, 9: 102})

        self.assertEqual(result[0]["category_id"], 101)
        self.assertEqual(result[1]["category_id"], 102)
        self.assertNotIn("categoryId", result[1])
        self.assertEqual(result[2]["category_id"], 2)
        self.assertEqual(result[2]["preroll_ids"], [70])
        self.assertEqual(result[3]["category_id"], 2)
        self.assertEqual(len(result), 4)
        self.assertEqual(original[0]["category_id"], 5)

    def test_category_reference_cannot_retarget_to_recycled_new_id(self):
        # Old category 2 is missing; new category 2 belongs to old category 9.
        raw = json.dumps([
            {"type": "random", "category_id": 2},
            {"type": "sequential", "category_id": 9},
        ])
        result = json.loads(remap_sequence_json(raw, {}, {9: 2}))
        self.assertEqual(result, [{"type": "sequential", "category_id": 2}])


if __name__ == "__main__":
    unittest.main()
