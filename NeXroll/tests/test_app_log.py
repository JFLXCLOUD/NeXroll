import io
import logging
import os
import sys

import pytest

from backend import app_log


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    monkeypatch.setenv("NEXROLL_LOG_DIR", str(folder))
    app_log.reset_location_cache()
    yield folder
    app_log.reset_location_cache()


def read(folder, name="app.log"):
    return (folder / name).read_text(encoding="utf-8")


# --- where app.log lives -----------------------------------------------------

def test_log_dir_env_override_comes_first(log_dir):
    assert app_log.log_dir_candidates()[0] == str(log_dir)
    assert app_log.log_path() == os.path.join(str(log_dir), "app.log")


def test_docker_logs_live_under_the_data_volume(monkeypatch, tmp_path):
    monkeypatch.delenv("NEXROLL_LOG_DIR", raising=False)
    monkeypatch.setenv("NEXROLL_DB_DIR", "/data")
    monkeypatch.setattr(sys, "platform", "linux")
    assert app_log.log_dir_candidates()[0] == os.path.join("/data", "logs")


# --- writing and rotation ----------------------------------------------------

def test_write_line_format_and_continuation(log_dir):
    app_log.write_line("WARNING", "first line\n  second line")
    text = read(log_dir)
    assert app_log.LINE_RE.match(text.splitlines()[0]).group(2) == "WARNING"
    assert text.splitlines()[1] == "  second line"


def test_rotation_moves_the_log_aside(log_dir):
    app_log.write_line("INFO", "x" * 200)
    assert app_log.rotate_if_needed(max_bytes=100) > 100
    assert (log_dir / "app.log.1").exists()
    assert not (log_dir / "app.log").exists()
    app_log.write_line("INFO", "after")
    assert "after" in read(log_dir)


def test_rotation_falls_back_to_copy_and_truncate(log_dir, monkeypatch):
    # Windows refuses the rename while another process holds the file open.
    app_log.write_line("INFO", "kept in the backup")

    def refuse(*a, **k):
        raise PermissionError("in use")
    monkeypatch.setattr(app_log.os, "replace", refuse)
    assert app_log.rotate() is True
    assert "kept in the backup" in read(log_dir, "app.log.1")
    assert read(log_dir) == ""


def test_writes_keep_no_handle_open(log_dir):
    app_log.write_line("INFO", "one")
    os.replace(log_dir / "app.log", log_dir / "moved.log")  # fails on Windows if a handle is open
    app_log.write_line("INFO", "two")
    assert "two" in read(log_dir)


# --- reading app.log back ----------------------------------------------------

def test_parse_entries_groups_tracebacks_with_their_line():
    lines = [
        "stray line before any entry",
        "[2026-10-06 10:00:00] [INFO] Started",
        "[2026-10-06 10:00:01] [ERROR] Exception in ASGI application",
        "Traceback (most recent call last):",
        '  File "main.py", line 1, in x',
        "ValueError: boom",
        "[2026-10-06 10:00:02] [WARN] Old-style level",
    ]
    entries = app_log.parse_entries(lines)
    assert [e["level"] for e in entries] == ["INFO", "ERROR", "WARNING"]
    assert entries[1]["detail"].endswith("ValueError: boom")
    assert entries[0]["detail"] == ""


def test_read_tail_drops_the_cut_line(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("aaaa\nbbbb\ncccc\n", encoding="utf-8")
    assert app_log.read_tail(str(path), max_bytes=7) == ["cccc"]
    assert app_log.read_tail(str(path)) == ["aaaa", "bbbb", "cccc"]


# --- areas ---------------------------------------------------------------------

@pytest.mark.parametrize("message,area", [
    ("Plex connection refused", "plex"),
    ("Jellyfin plugin did not answer", "jellyfin"),
    ("Radarr sync failed", "nexup"),
    ("Holiday schedule refresh failed", "scheduler"),
    ("Disk is full", "system"),
])
def test_guess_category(message, area):
    assert app_log.guess_category(message) == area


# --- forwarding to the Logs page ---------------------------------------------

class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, level, category, message, source=None, details=None):
        self.calls.append((level, category, message))


def make_forwarder():
    fwd = app_log.Forwarder()
    fwd.sink = Recorder()
    return fwd


def item(created, level="WARNING", message="Plex refused", tid=1, category="plex"):
    return (created, tid, level, category, message, None, None)


def test_entry_paired_with_log_event_is_dropped(monkeypatch):
    fwd = make_forwarder()
    monkeypatch.setattr(app_log.threading, "get_ident", lambda: 1)
    monkeypatch.setattr(app_log.time, "monotonic", lambda: 100.5)
    fwd.note_explicit("ERROR")
    assert fwd.handle(item(100.0), now=102.5, wall=0) is None
    # Another thread's warning at the same moment is a different problem.
    assert fwd.handle(item(100.0, tid=2), now=102.5, wall=0) == "Plex refused"


def test_info_events_never_pair(monkeypatch):
    fwd = make_forwarder()
    monkeypatch.setattr(app_log.threading, "get_ident", lambda: 1)
    monkeypatch.setattr(app_log.time, "monotonic", lambda: 5.0)
    fwd.note_explicit("INFO")
    assert fwd.handle(item(5.0, level="INFO", message="Prerolls set"), now=7.0, wall=0)


def test_repeats_are_recorded_once_an_hour_with_a_count():
    fwd = make_forwarder()
    wall = 1_700_000_000
    assert fwd.handle(item(0, message="Check failed 5 times"), now=0, wall=wall)
    for minute in (5, 10, 15):
        assert fwd.handle(item(minute * 60, message="Check failed 6 times"), now=minute * 60, wall=wall) is None
    again = fwd.handle(item(3700, message="Check failed 7 times"), now=3700, wall=wall + 3700)
    assert again.startswith("Check failed 7 times (repeated 3 times since ")
    assert len(fwd.sink.calls) == 2


def test_request_throttle_ignores_timings():
    throttle = app_log.RepeatThrottle(600)
    assert throttle.check("WARNING GET /nexup/sonarr/upcoming 400", now=0, wall=0) == (True, "")
    assert throttle.check("WARNING GET /nexup/sonarr/upcoming 400", now=5, wall=5)[0] is False
    assert throttle.check("WARNING GET /schedules 400", now=6, wall=6)[0] is True
    allowed, note = throttle.check("WARNING GET /nexup/sonarr/upcoming 400", now=601, wall=601)
    assert allowed and note.startswith(" (repeated 1 time since ")


def test_storm_is_capped_per_minute():
    fwd = make_forwarder()
    # Numbers are ignored when spotting repeats, so spell each one out in letters.
    names = ["".join(chr(65 + int(d)) for d in str(i)) for i in range(fwd.MAX_PER_MINUTE + 10)]
    recorded = [fwd.handle(item(0, message=f"distinct problem {name}"), now=1, wall=0) for name in names]
    assert sum(1 for r in recorded if r) == fwd.MAX_PER_MINUTE


def test_nothing_recorded_without_a_sink():
    fwd = app_log.Forwarder()
    assert fwd.handle(item(0), now=5, wall=0) is None


# --- Python logging and the console tee --------------------------------------

@pytest.fixture
def forwarded(monkeypatch):
    calls = []
    monkeypatch.setattr(app_log, "forward", lambda *a, **k: calls.append((a, k)))
    return calls


def record(name, level, msg, exc_info=None):
    return logging.LogRecord(name, level, __file__, 1, msg, None, exc_info)


def test_handler_skips_access_log_chatter(log_dir, forwarded):
    handler = app_log.AppLogHandler()
    handler.emit(record("uvicorn.access", logging.INFO, '127.0.0.1:5 - "GET /prerolls HTTP/1.1" 200'))
    assert not (log_dir / "app.log").exists()
    assert forwarded == []


def test_handler_forwards_warnings_with_their_area(log_dir, forwarded):
    handler = app_log.AppLogHandler()
    handler.emit(record("backend.radarr_connector", logging.INFO, "Fetched 12 movies"))
    try:
        raise RuntimeError("timed out")
    except RuntimeError:
        handler.emit(record("backend.radarr_connector", logging.ERROR, "Radarr request failed", sys.exc_info()))
    text = read(log_dir)
    assert "[INFO] Fetched 12 movies" in text
    assert "RuntimeError: timed out" in text
    (args, kwargs), = forwarded
    assert args[:3] == ("ERROR", "nexup", "Radarr request failed")
    assert "RuntimeError" in kwargs["details"]["traceback"]


def test_windows_client_disconnect_is_not_an_error(log_dir, forwarded):
    handler = app_log.AppLogHandler()
    try:
        raise ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host")
    except ConnectionResetError:
        handler.emit(record("asyncio", logging.ERROR,
                            "Exception in callback _ProactorBasePipeTransport._call_connection_lost(None)",
                            sys.exc_info()))
    assert "[DEBUG] Exception in callback" in read(log_dir)
    assert forwarded == []


def test_tee_prefixes_lines_and_keeps_tracebacks_together(log_dir):
    console = io.StringIO()
    tee = app_log.StreamTee(console, "WARNING")
    tee.write("partial ")
    tee.write("line\n")
    tee.write("Traceback (most recent call last):\n")
    tee.write('  File "x.py", line 1, in y\n')
    tee.write("KeyError: 'k'\n")
    tee.write("after\n")
    assert console.getvalue().startswith("partial line\n")
    entries = app_log.parse_entries(read(log_dir).splitlines())
    assert [(e["level"], e["message"]) for e in entries] == [
        ("WARNING", "partial line"),
        ("ERROR", "Traceback (most recent call last):"),
        ("WARNING", "after"),
    ]
    assert entries[1]["detail"].endswith("KeyError: 'k'")


def test_tee_without_a_console():
    tee = app_log.StreamTee(None, "INFO")
    assert tee.isatty() is False
    tee.flush()
