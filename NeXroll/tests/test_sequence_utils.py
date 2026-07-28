import unittest

from backend.sequence_utils import representative_category_id


class SequenceHelpersTests(unittest.TestCase):
    def test_representative_category_uses_first_category_backed_block(self):
        blocks = [
            {"type": "fixed", "preroll_ids": [1]},
            {"type": "sequential", "category_id": "12"},
            {"type": "random", "category_id": 9},
        ]
        self.assertEqual(representative_category_id(blocks), 12)

    def test_representative_category_is_none_for_sequence_only_blocks(self):
        self.assertIsNone(representative_category_id([
            {"type": "fixed", "preroll_ids": [1]},
            {"type": "coming_soon_list"},
        ]))


if __name__ == "__main__":
    unittest.main()
