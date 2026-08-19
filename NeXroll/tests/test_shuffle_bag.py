import unittest
from types import SimpleNamespace

from backend.shuffle_bag import clear_shuffle_bags, shuffle_bag_sample


class ShuffleBagTests(unittest.TestCase):
    def setUp(self):
        clear_shuffle_bags()

    def tearDown(self):
        clear_shuffle_bags()

    def test_each_item_is_selected_before_any_item_repeats(self):
        pool = [SimpleNamespace(id=item_id) for item_id in range(1, 5)]

        first = shuffle_bag_sample("trailers", pool, 2)
        second = shuffle_bag_sample("trailers", pool, 2)

        first_ids = {item.id for item in first}
        second_ids = {item.id for item in second}
        self.assertEqual(len(first_ids), 2)
        self.assertEqual(len(second_ids), 2)
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(first_ids | second_ids, {1, 2, 3, 4})

    def test_new_cycle_avoids_the_immediately_previous_selection(self):
        pool = [SimpleNamespace(id=item_id) for item_id in range(1, 5)]

        shuffle_bag_sample("trailers", pool, 2)
        previous = shuffle_bag_sample("trailers", pool, 2)
        next_selection = shuffle_bag_sample("trailers", pool, 2)

        self.assertFalse(
            {item.id for item in previous} & {item.id for item in next_selection}
        )

    def test_pool_change_resets_the_bag_and_returns_only_eligible_items(self):
        original = [SimpleNamespace(id=item_id) for item_id in (1, 2, 3)]
        shuffle_bag_sample("trailers", original, 2)

        changed = [SimpleNamespace(id=item_id) for item_id in (2, 3, 4)]
        selected = shuffle_bag_sample("trailers", changed, 3)

        self.assertEqual({item.id for item in selected}, {2, 3, 4})

    def test_bag_keys_keep_independent_rotations(self):
        pool = [SimpleNamespace(id=item_id) for item_id in range(1, 5)]

        first_a = shuffle_bag_sample("a", pool, 2)
        first_b = shuffle_bag_sample("b", pool, 2)
        second_a = shuffle_bag_sample("a", pool, 2)

        self.assertEqual(len(first_b), 2)
        self.assertFalse(
            {item.id for item in first_a} & {item.id for item in second_a}
        )


if __name__ == "__main__":
    unittest.main()
