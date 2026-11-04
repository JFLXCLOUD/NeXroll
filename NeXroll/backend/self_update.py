"""Install update from the web UI (Windows installer builds).

NeXroll can't replace its own files: they are in Program Files, the installer
needs administrator rights, and on most installs NeXroll.exe runs as the
signed-in user (the tray starts it). So the installer registers a "NeXroll
Updater" scheduled task that runs Releases/NeXrollUpdater.ps1 as SYSTEM, and
any signed-in user may start it. NeXroll backs up the database, leaves a
request naming the version and its port, and starts the task. The script
downloads that release from GitHub, checks it against the SHA-256 GitHub
lists, installs it with /S /UPDATE and starts NeXroll again the way it was
running. It refuses anything that isn't an official release newer than the
one installed, whoever starts it.

The request lives in ProgramData, which every user can write, so the script
reads it as untrusted input. The script's status lives in <install dir>\\update,
which only administrators can change; NeXroll reads it from there.

Docker and source installs update some other way, and installs from before
this feature have no task until one release is installed by hand.

Automatic updates (opt-in, settings.update_auto_install) use the same path.
NeXroll looks every few minutes, but only acts during the hour the user picked
(settings.update_auto_hour, local time), on the latest stable release once it
is settings.update_auto_delay_days old and has its installer, and only when
nothing is playing: no Plex session, and no Jellyfin/Emby plugin asking for
intros in the last hour (the plugins ask when a playback starts). A version is
tried once a day at most (settings.update_auto_last_attempt), so a failing
update can't take NeXroll down over and over.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from typing import Callable, Optional, Tuple

TASK_NAME = "NeXroll Updater"
SCRIPT_NAME = "NeXrollUpdater.ps1"
VERSION_RE = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}(-[A-Za-z]{1,12}(\.?\d{1,4})?)?$")

# The script's states. "running" ones mean an update is under way.
RUNNING_STATES = frozenset({"starting", "checking", "downloading", "installing", "restarting"})
FINAL_STATES = frozenset({"done", "failed", "up_to_date", "verified"})
STATUS_FIELDS = ("state", "message", "request_id", "from_version", "to_version", "started_at", "updated_at")
# A running state older than this is a script that died (the task's own limit is an hour).
STALE_AFTER = datetime.timedelta(minutes=70)
BACKUPS_KEPT = 3

LATEST_RELEASE_API = "https://api.github.com/repos/JFLXCLOUD/NeXroll/releases/latest"
AUTO_DEFAULT_HOUR = 4
AUTO_DEFAULT_DELAY_DAYS = 3
AUTO_MAX_DELAY_DAYS = 30
AUTO_RETRY_AFTER = datetime.timedelta(hours=20)
RECENT_PLAYBACK_SECONDS = 3600


class UpdateError(Exception):
    """Install update can't start; the message is for the user."""


# ---------------------------------------------------------------------------
# Versions (the order the update check uses: a stable release follows its
# pre-releases, alpha < beta < rc)
# ---------------------------------------------------------------------------

def parse_version(value) -> tuple:
    s = str(value or "").strip().lstrip("vV")
    m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[.-]([a-zA-Z]+)[.-]?(\d+))?", s)
    if not m:
        return (0, 0, 0, None, 0)
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0),
            m.group(4).lower() if m.group(4) else None, int(m.group(5) or 0))


def compare_versions(a, b) -> int:
    """1 if a is newer than b, -1 if older, 0 if the same."""
    va, vb = parse_version(a), parse_version(b)
    for i in range(3):
        if va[i] != vb[i]:
            return 1 if va[i] > vb[i] else -1
    a_pre, b_pre = va[3], vb[3]
    if a_pre is None and b_pre is None:
        return 0
    if a_pre is None:
        return 1
    if b_pre is None:
        return -1
    order = {"alpha": 0, "beta": 1, "rc": 2}
    a_rank, b_rank = order.get(a_pre, 99), order.get(b_pre, 99)
    if a_rank != b_rank:
        return 1 if a_rank > b_rank else -1
    if va[4] != vb[4]:
        return 1 if va[4] > vb[4] else -1
    return 0


# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

def install_dir() -> Optional[str]:
    """The installed NeXroll folder, or None when not running the installed NeXroll.exe."""
    if not sys.platform.startswith("win") or not getattr(sys, "frozen", False):
        return None
    return os.path.dirname(os.path.abspath(sys.executable))


def request_path() -> str:
    program_data = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(program_data, "NeXroll", "update-request.json")


def status_path(folder: Optional[str] = None) -> Optional[str]:
    folder = folder or install_dir()
    return os.path.join(folder, "update", "status.json") if folder else None


def _run(args, timeout: float = 20):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def task_exists() -> bool:
    try:
        return _run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# What the web UI shows
# ---------------------------------------------------------------------------

def support(in_docker: bool = False, folder: Optional[str] = None,
            has_task: Optional[Callable[[], bool]] = None) -> dict:
    """Whether Install update works on this install, and if not, why."""
    if in_docker:
        return {"supported": False, "reason": "docker",
                "message": "Docker installs update by pulling the new image."}
    folder = folder or install_dir()
    if not folder:
        return {"supported": False, "reason": "not_installer",
                "message": "Install update works on installs made with the Windows installer."}
    if not os.path.isfile(os.path.join(folder, SCRIPT_NAME)) or not (has_task or task_exists)():
        return {"supported": False, "reason": "updater_missing",
                "message": "This install is older than Install update. Install the new version "
                           "by hand once; after that, updates can be installed from here."}
    return {"supported": True, "reason": None, "message": None}


def read_status(folder: Optional[str] = None, now: Optional[datetime.datetime] = None) -> Optional[dict]:
    """The script's last status, or None if it has never run."""
    path = status_path(folder)
    if not path or not os.path.isfile(path):
        return None
    try:
        if os.path.getsize(path) > 64 * 1024:
            return None
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    status = {}
    for key in STATUS_FIELDS:
        value = raw.get(key)
        status[key] = str(value)[:500] if value is not None else None
    if status["state"] not in RUNNING_STATES | FINAL_STATES:
        return None
    # A script that died mid-update never writes a final state.
    if status["state"] in RUNNING_STATES:
        updated = _parse_time(status.get("updated_at"))
        now = now or datetime.datetime.now(datetime.timezone.utc)
        if updated and now - updated > STALE_AFTER:
            status["state"] = "failed"
            status["message"] = "The updater stopped without finishing. See update.log in the NeXroll install folder."
    return status


def _parse_time(value) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        # PowerShell writes seven fractional digits; Python takes six.
        text = re.sub(r"(\.\d{6})\d+", r"\1", str(value)).replace("Z", "+00:00")
        parsed = datetime.datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def update_running(folder: Optional[str] = None) -> bool:
    status = read_status(folder)
    return bool(status and status["state"] in RUNNING_STATES)


# ---------------------------------------------------------------------------
# Starting an update
# ---------------------------------------------------------------------------

def backup_database(db_path: str, version: str, snapshot: Callable[[str], Optional[str]]) -> str:
    """A copy of the database beside it, made before the update; keeps the newest few."""
    copy = snapshot(db_path)
    if not copy:
        raise UpdateError("Could not back up the database, so the update was not started.")
    folder = os.path.join(os.path.dirname(db_path), "update-backups")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(folder, f"nexroll-before-{version}-{stamp}.db")
    os.replace(copy, target)
    backups = sorted((n for n in os.listdir(folder) if n.startswith("nexroll-before-") and n.endswith(".db")),
                     key=lambda n: os.path.getmtime(os.path.join(folder, n)), reverse=True)
    for old in backups[BACKUPS_KEPT:]:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return target


def start_update(version: str, port: int, path: Optional[str] = None,
                 run: Optional[Callable] = None) -> str:
    """Leave the request and start the task. Returns the request id the status will carry."""
    request_id = uuid.uuid4().hex
    path = path or request_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "version": version,
        "port": int(port),
        "request_id": request_id,
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, path)
    try:
        result = (run or _run)(["schtasks", "/Run", "/TN", TASK_NAME])
    except Exception as e:
        raise UpdateError(f"Windows would not start the {TASK_NAME} task: {e}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise UpdateError(f"Windows would not start the {TASK_NAME} task: {detail or 'no reason given'}")
    return request_id


# ---------------------------------------------------------------------------
# Automatic updates
# ---------------------------------------------------------------------------

def auto_hour(value) -> int:
    try:
        hour = int(value)
    except (TypeError, ValueError):
        return AUTO_DEFAULT_HOUR
    return hour if 0 <= hour <= 23 else AUTO_DEFAULT_HOUR


def auto_delay_days(value) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return AUTO_DEFAULT_DELAY_DAYS
    return min(max(days, 0), AUTO_MAX_DELAY_DAYS)


_last_playback = 0.0


def note_playback(now: Optional[float] = None) -> None:
    """A Jellyfin/Emby plugin asked for intros: a playback is starting."""
    global _last_playback
    _last_playback = time.time() if now is None else now


def recent_playback(now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    return _last_playback > 0 and now - _last_playback < RECENT_PLAYBACK_SECONDS


def fetch_latest_release(url: str = LATEST_RELEASE_API, timeout: float = 15) -> dict:
    """GitHub's latest stable release (drafts and pre-releases are never "latest")."""
    req = urllib.request.Request(url, headers={"User-Agent": "NeXroll-AutoUpdate",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def format_attempt(version: str, when: datetime.datetime) -> str:
    return f"{version}|{when.isoformat()}"


def auto_candidate(release: Optional[dict], current_version: str, delay_days: int,
                   last_attempt: Optional[str], now: datetime.datetime) -> Tuple[Optional[str], str]:
    """The version to install automatically now, or None and why not. ``now`` is UTC."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None, "no stable release"
    version = str(release.get("tag_name") or "").strip().lstrip("vV")
    if not VERSION_RE.match(version):
        return None, "no stable release"
    if compare_versions(version, current_version) <= 0:
        return None, f"{current_version} is the latest"
    names = {str(a.get("name")) for a in release.get("assets") or [] if isinstance(a, dict)}
    if f"NeXroll_Installer_v{version}.exe" not in names:
        return None, f"{version} has no Windows installer yet"
    published = _parse_time(release.get("published_at"))
    if published is None:
        return None, f"{version} has no publish date"
    ready = published + datetime.timedelta(days=delay_days)
    if now < ready:
        return None, f"{version} waits until {ready.date().isoformat()} ({delay_days} days after release)"
    tried_version, _, tried_at = str(last_attempt or "").partition("|")
    tried = _parse_time(tried_at)
    if tried_version == version and tried and now - tried < AUTO_RETRY_AFTER:
        return None, f"{version} was tried at {tried_at}; trying again tomorrow"
    return version, f"{version} is due"
