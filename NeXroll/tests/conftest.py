"""Keep the test run away from an installed NeXroll.

Without these, tests that touch the scheduler appended SCHEDULER lines to the
real %ProgramData%\\NeXroll\\logs\\app.log, and anything importing
backend.database opened the installed nexroll.db. An explicit
NEXROLL_DB_PATH / NEXROLL_LOG_DIR from the environment still wins.
"""
import os
import tempfile

_scratch = tempfile.mkdtemp(prefix="nexroll-tests-")
os.environ.setdefault("NEXROLL_LOG_DIR", os.path.join(_scratch, "logs"))
os.environ.setdefault("NEXROLL_DB_PATH", os.path.join(_scratch, "nexroll.db"))
