"""Keep the test run away from an installed NeXroll.

Without these, tests that touch the scheduler appended SCHEDULER lines to the
real %ProgramData%\\NeXroll\\logs\\app.log, and anything importing
backend.database opened the installed nexroll.db. Importing backend.main also
picks a preroll folder (on Windows the installed one, from the registry),
creates it, and copies legacy prerolls into it when it is empty, so the tests
get a scratch folder that starts with a placeholder file. Off Windows the
secure store keeps secrets.json in NEXROLL_SECRETS_DIR. A value already in the
environment still wins (the Docker image sets NEXROLL_PREROLL_PATH and
NEXROLL_SECRETS_DIR).
"""
import os
import tempfile

import pytest

_scratch = tempfile.mkdtemp(prefix="nexroll-tests-")
os.environ.setdefault("NEXROLL_LOG_DIR", os.path.join(_scratch, "logs"))
os.environ.setdefault("NEXROLL_DB_PATH", os.path.join(_scratch, "nexroll.db"))
os.environ.setdefault("NEXROLL_SECRETS_DIR", os.path.join(_scratch, "secrets"))
if not os.environ.get("NEXROLL_PREROLL_PATH"):
    _prerolls = os.path.join(_scratch, "prerolls")
    os.makedirs(_prerolls, exist_ok=True)
    # Not empty, so main.migrate_legacy_data() never copies into it.
    open(os.path.join(_prerolls, ".nexroll-tests"), "w").close()
    os.environ["NEXROLL_PREROLL_PATH"] = _prerolls


@pytest.fixture(autouse=True)
def _fresh_media_server_probe():
    """The health summary reuses a media-server probe for a few seconds."""
    from backend import media_server_health
    media_server_health.reset_probe_cache()
    yield
