from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from reddit_manager.cli import _incomplete_sections, main  # noqa: E402


class CliTests(unittest.TestCase):
    def test_incomplete_capture_is_detected_before_apply(self) -> None:
        self.assertEqual(
            ["wiki"],
            _incomplete_sections(
                {
                    "state": {
                        "rules": [],
                        "wiki": {"_unavailable": "Forbidden"},
                    }
                }
            ),
        )

    def test_validate_is_offline(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["validate"])
        self.assertEqual(0, result)
        self.assertIn('"subreddit": "r/NeXroll"', output.getvalue())

    def test_apply_rejects_inexact_confirmation_before_network(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = main(["apply", "--confirm", "r/nexroll"])
        self.assertEqual(2, result)
        self.assertIn("exact confirmation", errors.getvalue())

    def test_posts_need_second_explicit_guard_before_network(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = main(
                [
                    "apply",
                    "--sections",
                    "posts",
                    "--confirm",
                    "r/NeXroll",
                ]
            )
        self.assertEqual(2, result)
        self.assertIn("--publish-posts", errors.getvalue())

    def test_offline_plan_rejects_sections_missing_from_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "snapshot.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "subreddit": "r/NeXroll",
                        "sections": ["rules"],
                        "state": {"rules": []},
                    }
                ),
                encoding="utf-8",
            )
            errors = io.StringIO()
            with redirect_stderr(errors):
                result = main(["plan", "--snapshot", str(snapshot)])

        self.assertEqual(2, result)
        self.assertIn("does not contain", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
