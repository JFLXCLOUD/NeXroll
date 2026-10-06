import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from backend.shuffle_bag import clear_shuffle_bags, configure_persistence, shuffle_bag_sample


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

    def test_adding_an_item_keeps_the_cycle_going(self):
        pool = [SimpleNamespace(id=i) for i in range(1, 5)]
        first = shuffle_bag_sample("p", pool, 1)[0].id
        grown = pool + [SimpleNamespace(id=5)]
        rest = [shuffle_bag_sample("p", grown, 1)[0].id for _ in range(4)]
        # The one that already played waits until everything else has.
        self.assertEqual(sorted(rest), sorted({1, 2, 3, 4, 5} - {first}))

    def test_a_pool_change_never_replays_the_last_pick_straight_away(self):
        for _ in range(30):
            clear_shuffle_bags()
            pool = [SimpleNamespace(id=i) for i in range(1, 4)]
            shuffle_bag_sample("p", pool, 1)
            shuffle_bag_sample("p", pool, 1)
            last = shuffle_bag_sample("p", pool, 1)[0].id  # cycle used up
            grown = pool + [SimpleNamespace(id=4)]
            self.assertNotEqual(shuffle_bag_sample("p", grown, 1)[0].id, last)

    def test_removed_items_are_not_returned(self):
        pool = [SimpleNamespace(id=i) for i in range(1, 6)]
        shuffle_bag_sample("p", pool, 1)
        smaller = pool[:2]
        picks = {shuffle_bag_sample("p", smaller, 1)[0].id for _ in range(4)}
        self.assertTrue(picks <= {1, 2})


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        clear_shuffle_bags()
        handle, self.path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        os.remove(self.path)

    def tearDown(self):
        configure_persistence(None)
        clear_shuffle_bags()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_rotation_survives_a_restart(self):
        configure_persistence(self.path)
        pool = [SimpleNamespace(id=i) for i in range(1, 5)]
        first = {item.id for item in shuffle_bag_sample(("plex", "schedule", 7), pool, 2)}
        clear_shuffle_bags()                      # the restart
        configure_persistence(self.path)
        second = {item.id for item in shuffle_bag_sample(("plex", "schedule", 7), pool, 2)}
        self.assertFalse(first & second)
        self.assertEqual(first | second, {1, 2, 3, 4})

    def test_paths_and_nested_keys_round_trip(self):
        configure_persistence(self.path)
        pool = ["/p/a.mp4", "/p/b.mp4", "/p/c.mp4"]
        first = shuffle_bag_sample(("plugin", "random-category", "blend", 3, 9), pool, 1)
        clear_shuffle_bags()
        configure_persistence(self.path)
        rest = [shuffle_bag_sample(("plugin", "random-category", "blend", 3, 9), pool, 1)[0] for _ in range(2)]
        self.assertEqual(sorted(first + rest), sorted(pool))

    def test_a_damaged_file_starts_empty(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        configure_persistence(self.path)          # must not raise
        self.assertEqual(len(shuffle_bag_sample("p", ["a", "b"], 1)), 1)

    def test_bags_that_cannot_be_written_are_skipped(self):
        configure_persistence(self.path)
        shuffle_bag_sample(object(), ["a", "b"], 1)
        shuffle_bag_sample("ok", ["a", "b"], 1)
        with open(self.path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual([row["key"] for row in saved["bags"]], ["ok"])

    def test_nothing_is_written_without_a_path(self):
        shuffle_bag_sample("p", ["a", "b"], 1)
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
