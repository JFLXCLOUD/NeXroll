import datetime
import unittest

from backend.settings_singleton import choose_survivor, fields_to_backfill


class Row:
    """Stand-in for a Setting row; only attribute access is needed."""

    def __init__(self, id, updated_at=None, **fields):
        self.id = id
        self.updated_at = updated_at
        for k, v in fields.items():
            setattr(self, k, v)


EARLIER = datetime.datetime(2026, 9, 12, 14, 30)
LATER = datetime.datetime(2026, 9, 12, 19, 5)


class ChooseSurvivorTests(unittest.TestCase):
    def test_no_rows_is_not_an_error(self):
        self.assertIsNone(choose_survivor([]))

    def test_a_single_row_survives_itself(self):
        row = Row(1)
        self.assertIs(choose_survivor([row]), row)

    def test_the_most_recently_updated_row_wins(self):
        stale, fresh = Row(1, EARLIER), Row(2, LATER)

        self.assertIs(choose_survivor([stale, fresh]), fresh)
        self.assertIs(choose_survivor([fresh, stale]), fresh)  # order must not matter

    def test_a_row_that_was_never_updated_loses_to_one_that_was(self):
        never, updated = Row(9, None), Row(2, EARLIER)

        self.assertIs(choose_survivor([never, updated]), updated)

    def test_with_no_timestamps_the_later_insert_wins(self):
        first, second = Row(1), Row(2)

        self.assertIs(choose_survivor([first, second]), second)


class BackfillTests(unittest.TestCase):
    def test_missing_values_are_recovered_from_the_discarded_row(self):
        survivor = Row(2, LATER, timezone=None, plex_url=None)
        other = Row(1, EARLIER, timezone="America/New_York", plex_url="http://plex:32400")

        filled = fields_to_backfill(survivor, [other], ["timezone", "plex_url"])

        self.assertEqual(filled, {"timezone": "America/New_York",
                                  "plex_url": "http://plex:32400"})

    def test_a_value_the_survivor_already_has_is_never_overwritten(self):
        # The survivor is the row the app has been writing to; a stale duplicate
        # must not clobber a real choice.
        survivor = Row(2, LATER, timezone="Europe/Berlin")
        other = Row(1, EARLIER, timezone="America/New_York")

        self.assertEqual(fields_to_backfill(survivor, [other], ["timezone"]), {})

    def test_empty_string_counts_as_missing(self):
        survivor = Row(2, LATER, jellyfin_url="")
        other = Row(1, EARLIER, jellyfin_url="http://jf:8096")

        self.assertEqual(fields_to_backfill(survivor, [other], ["jellyfin_url"]),
                         {"jellyfin_url": "http://jf:8096"})

    def test_the_most_recent_discarded_row_supplies_the_value(self):
        survivor = Row(3, LATER, timezone=None)
        old = Row(1, EARLIER, timezone="UTC")
        newer = Row(2, datetime.datetime(2026, 9, 12, 18, 0), timezone="America/New_York")

        filled = fields_to_backfill(survivor, [old, newer], ["timezone"])

        self.assertEqual(filled["timezone"], "America/New_York")

    def test_a_column_missing_everywhere_is_left_alone(self):
        survivor = Row(2, LATER, timezone=None)
        other = Row(1, EARLIER, timezone=None)

        self.assertEqual(fields_to_backfill(survivor, [other], ["timezone"]), {})

    def test_the_real_case_two_rows_one_holding_the_detected_timezone(self):
        # What was actually on disk: the row everything read still had the
        # column default, while the startup hook's TZ detection landed on the
        # other row. Merging must not lose the detected zone.
        read_by_app = Row(1, EARLIER, timezone="UTC", jellyfin_url="http://jf:8096")
        written_by_startup = Row(2, LATER, timezone="America/New_York", jellyfin_url=None)

        survivor = choose_survivor([read_by_app, written_by_startup])
        others = [r for r in (read_by_app, written_by_startup) if r is not survivor]
        filled = fields_to_backfill(survivor, others, ["timezone", "jellyfin_url"])

        self.assertIs(survivor, written_by_startup)
        self.assertEqual(survivor.timezone, "America/New_York")
        self.assertEqual(filled.get("jellyfin_url"), "http://jf:8096")


if __name__ == "__main__":
    unittest.main()
