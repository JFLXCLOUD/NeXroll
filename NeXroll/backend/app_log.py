"""app.log, and the bridge from it to the Logs page.

Every writer of app.log goes through write_line(): main._file_log, the
scheduler's _scheduler_log, the stdout/stderr tee of packaged builds and the
Python logging handler. Each write opens, appends and closes under one lock, so
nothing holds the file open between writes and rotation can rename it. Before
this the tee and a RotatingFileHandler each kept the file open, so on Windows
every rename failed silently and app.log grew past its 10 MB cap.

forward() passes warnings and errors from those writers on to the database
event log that the Logs page reads (main registers log_event as the sink). They
used to be file-only: a month on a real install had 129 errors and 3,398
warnings in app.log and none of them on the Logs page.

This module must not import backend.main or backend.scheduler.
"""
import datetime
import logging
import os
import re
import shutil
import sys
import threading
import time

LOG_NAME = "app.log"
MAX_BYTES = 10 * 1024 * 1024
ROTATION_CHECK_SECONDS = 30

_lock = threading.RLock()
_dir_cache = {"dir": None}
_rotation = {"last_check": 0.0}


# ---------------------------------------------------------------------------
# Where app.log lives
# ---------------------------------------------------------------------------

def log_dir_candidates():
    """Folders to try, best first.

    NEXROLL_LOG_DIR wins when set (the test suite points it at a temp folder so
    tests never write into an installed NeXroll's log). Windows keeps
    %ProgramData%\\NeXroll\\logs. Elsewhere NEXROLL_DB_DIR/logs comes first:
    Docker sets NEXROLL_DB_DIR=/data, and the old <cwd>/logs was inside the
    container, so every image update threw the log away.
    """
    out = []
    override = (os.environ.get("NEXROLL_LOG_DIR") or "").strip()
    if override:
        out.append(override)
    if sys.platform.startswith("win"):
        base = os.environ.get("ProgramData")
        if base:
            out.append(os.path.join(base, "NeXroll", "logs"))
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local:
            out.append(os.path.join(local, "NeXroll", "logs"))
    else:
        db_dir = (os.environ.get("NEXROLL_DB_DIR") or "").strip()
        if db_dir:
            out.append(os.path.join(db_dir, "logs"))
    out.append(os.path.join(os.getcwd(), "logs"))
    return out


def _writable(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, f".nexroll_write_test_{os.getpid()}.tmp")
        with open(probe, "a", encoding="utf-8") as f:
            f.write("ok")
        try:
            os.remove(probe)
        except OSError:
            pass
        return True
    except Exception:
        return False


def log_dir():
    """The first writable candidate, remembered so a write costs no probe."""
    cached = _dir_cache["dir"]
    if cached and os.path.isdir(cached):
        return cached
    for folder in log_dir_candidates():
        if _writable(folder):
            _dir_cache["dir"] = folder
            return folder
    return os.getcwd()


def log_path():
    return os.path.join(log_dir(), LOG_NAME)


def reset_location_cache():
    """Forget the resolved folder (tests change the environment)."""
    _dir_cache["dir"] = None


# ---------------------------------------------------------------------------
# Writing and rotation
# ---------------------------------------------------------------------------

def rotate(path=None):
    """Move app.log to app.log.1, replacing the previous backup.

    Returns True when the log was rotated. If another process still holds the
    file open (an older build, or a second instance sharing the folder),
    Windows refuses the rename; the log is then copied to the backup and
    emptied so it still can't grow without limit.
    """
    path = path or log_path()
    backup = path + ".1"
    with _lock:
        if not os.path.exists(path):
            return False
        try:
            os.replace(path, backup)
            return True
        except OSError:
            pass
        try:
            shutil.copyfile(path, backup)
            with open(path, "r+", encoding="utf-8") as f:
                f.truncate(0)
            return True
        except OSError:
            return False


def rotate_if_needed(max_bytes=MAX_BYTES, path=None):
    """Rotate when app.log is over max_bytes. Returns the old size in bytes, or 0."""
    path = path or log_path()
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0
    if size <= max_bytes:
        return 0
    return size if rotate(path) else 0


def write_raw(text):
    """Append text to app.log as it is. Never raises."""
    try:
        with _lock:
            path = log_path()
            now = time.monotonic()
            if now - _rotation["last_check"] >= ROTATION_CHECK_SECONDS:
                _rotation["last_check"] = now
                rotate_if_needed(path=path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
    except Exception:
        pass


def write_line(level, message):
    """Append "[time] [LEVEL] message". Later lines of a multi-line message are
    written as they are, which the Logs page reads as part of this entry."""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_raw(f"[{stamp}] [{level}] {message}\n")


# ---------------------------------------------------------------------------
# Reading app.log back for the Logs page
# ---------------------------------------------------------------------------

LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[([A-Z]+)\] ?(.*)$")
LEVEL_ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}


def parse_entries(lines):
    """Group app.log lines into entries, oldest first.

    A line that doesn't start with "[time] [LEVEL]" (a traceback line, the body
    of a multi-line message, raw output from an older build's console tee)
    belongs to the entry above it. Lines before the first entry are dropped.
    Returns dicts with timestamp, level, message (first line) and detail (the
    rest, or "").
    """
    entries = []
    current = None
    for raw in lines:
        line = raw.rstrip("\r\n")
        m = LINE_RE.match(line)
        if m:
            if current is not None:
                entries.append(current)
            stamp, level, message = m.groups()
            current = {"timestamp": stamp, "level": LEVEL_ALIASES.get(level, level),
                       "message": message, "detail": []}
        elif current is not None and line.strip():
            current["detail"].append(line)
    if current is not None:
        entries.append(current)
    for entry in entries:
        entry["detail"] = "\n".join(entry["detail"])
    return entries


def read_tail(path, max_bytes=MAX_BYTES + 1024 * 1024):
    """The last max_bytes of a log file as lines (the first, partial line of a
    cut is dropped)."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start and lines:
        lines = lines[1:]
    return lines


# ---------------------------------------------------------------------------
# Areas (the Logs page's categories)
# ---------------------------------------------------------------------------

_AREA_WORDS = (
    ("jellyfin", "jellyfin"),
    ("emby", "emby"),
    ("plex", "plex"),
    ("nex-up", "nexup"), ("nexup", "nexup"), ("radarr", "nexup"), ("sonarr", "nexup"),
    ("trailer", "nexup"), ("coming soon", "nexup"),
    ("schedul", "scheduler"),
)

_LOGGER_AREAS = {
    "backend.radarr_connector": "nexup",
    "backend.sonarr_connector": "nexup",
    "backend.dynamic_preroll": "nexup",
    "backend.holiday_api": "scheduler",
    "backend.jellyfin_connector": "jellyfin",
    "backend.plex_connector": "plex",
}


def guess_category(message, default="system"):
    """The Logs page area a free-text message belongs to, by the first
    server/feature word in it."""
    text = (message or "").lower()
    for word, area in _AREA_WORDS:
        if word in text:
            return area
    return default


def category_for_logger(name, message=""):
    if name in _LOGGER_AREAS:
        return _LOGGER_AREAS[name]
    if name.startswith("uvicorn"):
        return "api"
    return guess_category(message)


# ---------------------------------------------------------------------------
# Forwarding to the database event log
# ---------------------------------------------------------------------------

_SERIOUS = ("WARNING", "ERROR", "CRITICAL")


class RepeatThrottle:
    """Lets the first of a run of identical messages through, then one per
    window, saying how many were held back in between. Numbers are ignored
    when comparing, so "took 43ms" and "took 82ms" are the same message."""

    def __init__(self, window):
        self.window = window
        self._seen = {}
        self._lock = threading.Lock()

    def check(self, text, now, wall):
        """Returns (allowed, note); note is " (repeated N times since HH:MM)"
        when earlier repeats were held back, else ""."""
        key = re.sub(r"\d+", "#", text or "")[:300]
        with self._lock:
            rec = self._seen.get(key)
            if rec is not None and now - rec[0] < self.window:
                rec[1] += 1
                return False, ""
            note = ""
            if rec is not None and rec[1]:
                since = datetime.datetime.fromtimestamp(rec[2]).strftime("%H:%M")
                note = f" (repeated {rec[1]} {'time' if rec[1] == 1 else 'times'} since {since})"
            self._seen[key] = [now, 0, wall]
            if len(self._seen) > 2000:
                for k, r in list(self._seen.items()):
                    if now - r[0] > 2 * self.window:
                        self._seen.pop(k, None)
            return True, note


class Forwarder:
    """Queues app.log entries for the database event log, on a background
    thread so a write never waits on SQLite.

    Two things keep it from flooding the Logs page:

    * Pairs. Much of main.py writes a problem to both app.log and log_event()
      back to back. An entry from a thread that recorded a warning or error
      with log_event within PAIR_WINDOW seconds either side is that same
      problem and is dropped.
    * Repeats. The same message (numbers ignored) is recorded once per
      REPEAT_WINDOW; the next one after that says how many were skipped. A
      check that fails every five minutes is one line an hour, not 288 a day.
    """
    PAIR_WINDOW = 2.0
    REPEAT_WINDOW = 3600.0
    MAX_PER_MINUTE = 60
    MAX_QUEUE = 2000

    def __init__(self):
        self.sink = None
        self._items = []
        self._cv = threading.Condition()
        self._thread = None
        self._explicit = {}
        self._repeats = RepeatThrottle(self.REPEAT_WINDOW)
        self._minute = [0.0, 0]

    def note_explicit(self, level):
        """Called by log_event: this thread just recorded an event itself."""
        if str(level).upper() not in _SERIOUS:
            return
        now = time.monotonic()
        recent = self._explicit.setdefault(threading.get_ident(), [])
        recent.append(now)
        del recent[:-8]
        if len(self._explicit) > 500:
            for tid, times in list(self._explicit.items()):
                if not times or now - times[-1] > 60:
                    self._explicit.pop(tid, None)

    def submit(self, level, category, message, source=None, details=None):
        item = (time.monotonic(), threading.get_ident(), str(level).upper(), category,
                message, source, details)
        with self._cv:
            if len(self._items) >= self.MAX_QUEUE:
                return
            self._items.append(item)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="nexroll-log-forwarder", daemon=True)
                self._thread.start()
            self._cv.notify()

    def _run(self):
        while True:
            with self._cv:
                while not self._items:
                    self._cv.wait()
                wait = self._items[0][0] + self.PAIR_WINDOW - time.monotonic()
                if wait > 0:
                    self._cv.wait(wait)
                    continue
                item = self._items.pop(0)
            try:
                self.handle(item, time.monotonic(), time.time())
            except Exception:
                pass

    def handle(self, item, now, wall):
        """Record one queued entry unless it's a pair or a repeat. Returns the
        message as recorded, or None."""
        created, tid, level, category, message, source, details = item
        if self.sink is None:
            return None
        if level in _SERIOUS:
            if any(abs(seen - created) <= self.PAIR_WINDOW for seen in self._explicit.get(tid, ())):
                return None
        allowed, note = self._repeats.check(f"{level}|{category}|{message}", now, wall)
        if not allowed:
            return None
        message = f"{message}{note}"
        if now - self._minute[0] >= 60:
            self._minute = [now, 0]
        if self._minute[1] >= self.MAX_PER_MINUTE:
            return None
        self._minute[1] += 1
        self.sink(level, category, message, source=source, details=details)
        return message


forwarder = Forwarder()


def set_db_sink(fn):
    """fn(level, category, message, source=, details=) records one event."""
    forwarder.sink = fn


def forward(level, category, message, source=None, details=None):
    try:
        forwarder.submit(level, category, message, source=source, details=details)
    except Exception:
        pass


def note_explicit_event(level):
    try:
        forwarder.note_explicit(level)
    except Exception:
        pass


def caller_name(depth=2):
    """Name of the function depth frames up, for an event's source."""
    try:
        return sys._getframe(depth).f_code.co_name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Python logging and the packaged build's console streams
# ---------------------------------------------------------------------------

# INFO chatter from these loggers isn't worth a line: uvicorn's access log was
# 65% of a real install's app.log, one line per dashboard poll.
_QUIET_BELOW_WARNING = ("uvicorn.access", "httpx", "httpcore")


_DISCONNECTS = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


def _is_client_disconnect(record):
    """asyncio's "Exception in callback _ProactorBasePipeTransport._call_
    connection_lost" on Windows: a browser closed its connection first. A
    known, harmless Python quirk, not a NeXroll error."""
    exc = record.exc_info[1] if record.exc_info else None
    return record.name == "asyncio" and isinstance(exc, _DISCONNECTS)


class AppLogHandler(logging.Handler):
    """Python logging (radarr_connector, sonarr_connector, dynamic_preroll,
    holiday_api, uvicorn's errors) into app.log, with warnings and errors
    passed on to the Logs page."""

    def emit(self, record):
        try:
            if record.levelno < logging.WARNING and record.name.startswith(_QUIET_BELOW_WARNING):
                return
            message = record.getMessage()
            trace = ""
            if record.exc_info:
                trace = logging.Formatter().formatException(record.exc_info)
            elif record.exc_text:
                trace = record.exc_text
            if _is_client_disconnect(record):
                write_line("DEBUG", message + ("\n" + trace if trace else ""))
                return
            write_line(record.levelname, message + ("\n" + trace if trace else ""))
            if record.levelno >= logging.WARNING:
                forward(record.levelname, category_for_logger(record.name, message), message,
                        source=record.name, details={"traceback": trace[-4000:]} if trace else None)
        except Exception:
            # Not handleError(): it prints to stderr, which the packaged build
            # copies back into app.log.
            pass


def install_logging_handler(level=logging.INFO):
    root = logging.getLogger()
    if any(isinstance(h, AppLogHandler) for h in root.handlers):
        return
    handler = AppLogHandler(level=level)
    root.addHandler(handler)
    root.setLevel(level)


_TRACE_STARTS = ("Traceback (most recent call last)", "Exception Group Traceback")
_TRACE_LINKS = ("During handling of the above exception", "The above exception was the direct cause")


class StreamTee:
    """Copies stdout or stderr into app.log a line at a time.

    Each line gets the "[time] [LEVEL]" prefix so the Logs page can read it.
    Indented lines and the body of a traceback are written as they are, so
    they read as part of the line above instead of as separate entries.
    """

    def __init__(self, original, level):
        self._orig = original
        self._level = level
        self._buf = ""
        self._in_traceback = False
        self._tlock = threading.Lock()
        self.nexroll_tee = True

    def write(self, s):
        try:
            if self._orig is not None:
                self._orig.write(s)
        except Exception:
            pass
        try:
            with self._tlock:
                self._buf += s
                if "\n" not in self._buf:
                    return len(s)
                *lines, self._buf = self._buf.split("\n")
                for line in lines:
                    self._emit(line)
        except Exception:
            pass
        return len(s)

    def _emit(self, line):
        line = line.rstrip("\r")
        if not line.strip():
            return
        if line.startswith(_TRACE_STARTS):
            self._in_traceback = True
            write_line("ERROR", line)
        elif line[:1] in (" ", "\t") or line.startswith(_TRACE_LINKS):
            write_raw(line + "\n")
        elif self._in_traceback:
            # The exception's own line ("ValueError: ...") ends the traceback.
            self._in_traceback = False
            write_raw(line + "\n")
        else:
            write_line(self._level, line)

    def flush(self):
        try:
            if self._orig is not None:
                self._orig.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return bool(self._orig is not None and self._orig.isatty())
        except Exception:
            return False

    def __getattr__(self, name):
        orig = self.__dict__.get("_orig")
        if orig is None:
            raise AttributeError(name)
        return getattr(orig, name)


def install_std_tee():
    """Copy stdout and stderr into app.log (packaged builds, where there's no
    console to read). Safe to call twice."""
    if getattr(sys.stdout, "nexroll_tee", False):
        return
    sys.stdout = StreamTee(sys.stdout, "INFO")
    sys.stderr = StreamTee(sys.stderr, "WARNING")


def tee_active():
    return bool(getattr(sys.stdout, "nexroll_tee", False))
