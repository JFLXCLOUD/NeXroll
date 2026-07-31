from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from reddit_manager.environment import (  # noqa: E402
    read_environment,
    write_env_secret,
)
from reddit_manager.errors import AuthorizationError  # noqa: E402
from reddit_manager.oauth import CallbackResult, validate_callback  # noqa: E402


class EnvironmentTests(unittest.TestCase):
    def test_secret_write_is_atomic_and_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".env"
            path.write_text(
                "REDDIT_CLIENT_ID=client\nREDDIT_REFRESH_TOKEN=old\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                write_env_secret(path, "REDDIT_REFRESH_TOKEN", "new-secret-token")

            self.assertEqual("", output.getvalue())
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("old", text)
            self.assertEqual(1, text.count("REDDIT_REFRESH_TOKEN="))
            credentials = read_environment(path, environ={})
            self.assertEqual("new-secret-token", credentials.refresh_token)

    def test_oauth_callback_requires_matching_state_and_code(self) -> None:
        callback = CallbackResult(
            code="authorization-code", state="expected", error=""
        )
        self.assertEqual(
            "authorization-code", validate_callback(callback, "expected")
        )
        with self.assertRaises(AuthorizationError):
            validate_callback(callback, "different")
        with self.assertRaises(AuthorizationError):
            validate_callback(
                CallbackResult(code="", state="expected", error=""), "expected"
            )
        with self.assertRaisesRegex(
            AuthorizationError, "^Reddit authorization was declined\\.$"
        ):
            validate_callback(
                CallbackResult(code="", state="expected", error="untrusted-value"),
                "expected",
            )


if __name__ == "__main__":
    unittest.main()
