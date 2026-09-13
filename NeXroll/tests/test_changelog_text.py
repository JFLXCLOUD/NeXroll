import pathlib
import unittest

from backend.changelog_text import strip_html_comments


class StripHtmlCommentsTests(unittest.TestCase):
    """A beta tester opened a fresh install and read the maintainer's own
    release-planning note in the What's New dialog, above the real entries."""

    def test_the_note_that_shipped_is_removed(self):
        shipped = (
            "# Changelog\n\n"
            "<!-- Stable 2.2.0 release preparation: use the user-approved "
            "README-2.2.0-draft.md and refreshed screenshots. Complete "
            "docs/RELEASE_PLAN_v2.2.0.md before tagging stable; keep this "
            "pending during beta. -->\n\n"
            "## [2.2.0-beta.9] - 09-11-2026 (beta)\n"
        )

        out = strip_html_comments(shipped)

        self.assertNotIn("RELEASE_PLAN", out)
        self.assertNotIn("<!--", out)
        self.assertIn("## [2.2.0-beta.9]", out)

    def test_the_real_changelog_file_has_nothing_left_to_leak(self):
        # Guards the actual shipped file, not just a sample of it.
        path = pathlib.Path(__file__).resolve().parents[1] / "CHANGELOG.md"
        out = strip_html_comments(path.read_text(encoding="utf-8-sig"))

        self.assertNotIn("<!--", out)
        self.assertTrue(out.startswith("# Changelog"))

    def test_a_multi_line_comment_goes_too(self):
        text = "a\n\n<!--\nline one\nline two\n-->\n\nb\n"

        out = strip_html_comments(text)

        self.assertNotIn("line one", out)
        self.assertIn("a", out)
        self.assertIn("b", out)

    def test_several_comments_are_all_removed(self):
        text = "<!-- one -->\n# Title\n<!-- two -->\ntext\n<!-- three -->\n"

        out = strip_html_comments(text)

        self.assertNotIn("one", out)
        self.assertNotIn("two", out)
        self.assertNotIn("three", out)
        self.assertIn("# Title", out)

    def test_the_gap_left_behind_is_closed_up(self):
        # Otherwise the dialog opens on blank space where the note used to be.
        text = "# Changelog\n\n<!-- note -->\n\n## Entry\n"

        self.assertEqual(strip_html_comments(text), "# Changelog\n\n## Entry\n")

    def test_ordinary_changelog_text_is_untouched(self):
        text = "# Changelog\n\n## [1.0.0]\n\n- **Fixed.** `a < b` and `x --> y` survive.\n"

        self.assertEqual(strip_html_comments(text), text)

    def test_empty_and_missing_input_do_not_raise(self):
        self.assertEqual(strip_html_comments(""), "")
        self.assertIsNone(strip_html_comments(None))


if __name__ == "__main__":
    unittest.main()
