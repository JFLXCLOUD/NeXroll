import unittest

from backend.health_summary import (
    ERROR,
    OK,
    UNKNOWN,
    WARN,
    build_summary,
    community_index_check,
    conflicts_check,
    make_check,
    overall_status,
    score_checks,
    summary_note,
)


class ScoreTests(unittest.TestCase):
    def test_all_healthy_scores_full_marks(self):
        checks = [make_check("scheduler", "Scheduler", OK),
                  make_check("media_server", "Media server", OK)]

        self.assertEqual(score_checks(checks), 100)

    def test_a_warning_costs_half_that_check_s_weight(self):
        # media_server is worth 30, so a warning there costs 15.
        checks = [make_check("scheduler", "Scheduler", OK),
                  make_check("media_server", "Media server", WARN)]

        self.assertEqual(score_checks(checks), 85)

    def test_an_error_costs_the_whole_check(self):
        checks = [make_check("scheduler", "Scheduler", OK),
                  make_check("media_server", "Media server", ERROR)]

        self.assertEqual(score_checks(checks), 70)

    def test_failing_everything_bottoms_out_at_zero_not_below(self):
        checks = [make_check(key, key, ERROR) for key in
                  ("scheduler", "media_server", "library", "storage",
                   "conflicts", "community_index")]

        self.assertEqual(score_checks(checks), 0)

    def test_discovering_a_problem_never_raises_the_score(self):
        # A weighted average of credits gets this wrong: adding a half-credit
        # check pulls a below-50% score upward, so finding schedule conflicts
        # would make a badly broken system look healthier.
        broken = [make_check("scheduler", "Scheduler", ERROR),
                  make_check("media_server", "Media server", ERROR),
                  make_check("library", "Preroll library", OK),
                  make_check("storage", "Storage", OK)]

        before = score_checks(broken)
        after = score_checks(broken + [conflicts_check(4)])

        self.assertLess(after, before)

    def test_unknown_checks_are_excluded_from_the_maths(self):
        # A check that could not run must not drag the score down, or a fresh
        # install would open on an alarming number.
        with_unknown = [make_check("scheduler", "Scheduler", OK),
                        make_check("community_index", "Community index", UNKNOWN)]

        self.assertEqual(score_checks(with_unknown), 100)

    def test_all_unknown_scores_100_rather_than_0(self):
        checks = [make_check("scheduler", "Scheduler", UNKNOWN),
                  make_check("media_server", "Media server", UNKNOWN)]

        self.assertEqual(score_checks(checks), 100)

    def test_no_checks_at_all_scores_100(self):
        self.assertEqual(score_checks([]), 100)

    def test_weights_actually_differentiate(self):
        heavy = [make_check("scheduler", "Scheduler", ERROR),
                 make_check("community_index", "Community index", OK)]
        light = [make_check("scheduler", "Scheduler", OK),
                 make_check("community_index", "Community index", ERROR)]

        self.assertLess(score_checks(heavy), score_checks(light))


class OverallStatusTests(unittest.TestCase):
    def test_clean_run_is_healthy(self):
        checks = [make_check("scheduler", "Scheduler", OK)]

        self.assertEqual(overall_status(checks, 100), "healthy")

    def test_a_warning_downgrades_to_attention(self):
        checks = [make_check("storage", "Storage", WARN)]

        self.assertEqual(overall_status(checks, 95), "attention")

    def test_any_error_is_degraded_even_when_the_score_is_high(self):
        # One dead service must not be averaged away by a pile of healthy ones.
        checks = [make_check("media_server", "Media server", ERROR)] + [
            make_check("community_index", "Community index", OK) for _ in range(20)
        ]

        self.assertEqual(overall_status(checks, 95), "degraded")

    def test_unknown_alone_does_not_downgrade(self):
        checks = [make_check("community_index", "Community index", UNKNOWN)]

        self.assertEqual(overall_status(checks, 100), "healthy")


class SummaryNoteTests(unittest.TestCase):
    def test_healthy_system_gets_a_plain_statement(self):
        checks = [make_check("scheduler", "Scheduler", OK)]

        self.assertEqual(summary_note(checks, "healthy"), "Your preroll system is healthy.")

    def test_the_note_names_the_most_important_problem_first(self):
        checks = [
            make_check("community_index", "Community index", WARN, "Community index is 40 days old"),
            make_check("scheduler", "Scheduler", ERROR, "The scheduler is stopped"),
        ]

        self.assertTrue(summary_note(checks, "degraded").startswith("The scheduler is stopped"))

    def test_errors_outrank_warnings_regardless_of_weight(self):
        checks = [
            make_check("scheduler", "Scheduler", WARN, "Scheduler is slow"),
            make_check("community_index", "Community index", ERROR, "Index is corrupt"),
        ]

        self.assertTrue(summary_note(checks, "degraded").startswith("Index is corrupt"))

    def test_remaining_problems_are_counted_not_listed(self):
        checks = [
            make_check("scheduler", "Scheduler", ERROR, "The scheduler is stopped"),
            make_check("storage", "Storage", WARN, "2 missing files"),
            make_check("conflicts", "Schedule conflicts", WARN, "4 conflicts"),
        ]

        self.assertEqual(
            summary_note(checks, "degraded"),
            "The scheduler is stopped (2 more items to review)",
        )

    def test_a_single_extra_problem_is_singular(self):
        checks = [
            make_check("scheduler", "Scheduler", ERROR, "The scheduler is stopped"),
            make_check("storage", "Storage", WARN, "2 missing files"),
        ]

        self.assertTrue(summary_note(checks, "degraded").endswith("(1 more item to review)"))

    def test_a_problem_without_a_detail_still_reads_as_a_sentence(self):
        checks = [make_check("storage", "Storage", WARN)]

        self.assertEqual(summary_note(checks, "attention"), "Storage needs attention")


class IndividualCheckTests(unittest.TestCase):
    def test_missing_community_index_is_unknown_not_a_failure(self):
        check = community_index_check(None)

        self.assertEqual(check["status"], UNKNOWN)

    def test_fresh_community_index_is_ok(self):
        self.assertEqual(community_index_check(8.2)["status"], OK)

    def test_stale_community_index_warns(self):
        check = community_index_check(45.0)

        self.assertEqual(check["status"], WARN)
        self.assertIn("45 days old", check["detail"])

    def test_index_age_is_pluralized_correctly(self):
        self.assertEqual(community_index_check(1.0)["value"], "1 day old")
        self.assertEqual(community_index_check(2.0)["value"], "2 days old")

    def test_conflicts_not_supplied_is_unknown(self):
        self.assertEqual(conflicts_check(None)["status"], UNKNOWN)

    def test_zero_conflicts_is_ok(self):
        self.assertEqual(conflicts_check(0)["status"], OK)

    def test_conflicts_warn_and_are_pluralized(self):
        self.assertIn("1 schedule conflict ", conflicts_check(1)["detail"])
        self.assertIn("4 schedule conflicts ", conflicts_check(4)["detail"])
        self.assertEqual(conflicts_check(4)["status"], WARN)
        self.assertEqual(conflicts_check(4)["value"], 4)


class BuildSummaryTests(unittest.TestCase):
    def test_summary_carries_score_status_note_and_checks(self):
        checks = [make_check("scheduler", "Scheduler", OK),
                  make_check("storage", "Storage", WARN, "2 missing files")]

        summary = build_summary(checks)

        self.assertEqual(summary["status"], "attention")
        self.assertEqual(summary["attention_count"], 1)
        self.assertEqual(summary["note"], "2 missing files")
        self.assertEqual(len(summary["checks"]), 2)
        self.assertIsInstance(summary["score"], int)

    def test_a_clean_system_reports_nothing_to_review(self):
        summary = build_summary([make_check("scheduler", "Scheduler", OK)])

        self.assertEqual(summary["score"], 100)
        self.assertEqual(summary["status"], "healthy")
        self.assertEqual(summary["attention_count"], 0)


if __name__ == "__main__":
    unittest.main()
