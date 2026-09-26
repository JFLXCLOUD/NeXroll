"""Ask Plex whether it can see a file, through Plex's own folder browser.

Plex plays a preroll by opening the path written in its "Movie pre-roll video"
preference, on the machine Plex runs on. NeXroll cannot open that machine's
filesystem, but Plex exposes one: ``/services/browse/<base64 path>`` is the
endpoint Plex Web uses when you pick a folder for a library, and with
``includeFiles=1`` it lists the files in a folder exactly as Plex sees them.
That answers the question path mappings exist for: can Plex open this path?

The same listing powers three things:

* :func:`gate_preroll_value` checks a preroll value before NeXroll writes it
  to Plex, drops files Plex cannot see and refuses to replace Plex's current
  prerolls with a list of nothing but missing files.
* :func:`find_folder` searches Plex's filesystem for the folder that holds
  NeXroll's prerolls, so a mapping can be proposed instead of typed.
* :meth:`PlexFiles.list_dir` backs the "Browse Plex" folder picker.

A missing file is only ever concluded from positive evidence: Plex listed the
folder and the file was not in it, or listed the folder above and the folder
was not in that. An empty answer can also mean the browse endpoint cannot list
that kind of path at all (a UNC share on some Windows servers, say), so when
nothing up the tree can be listed the result is "unknown" and NeXroll writes
the value exactly as it always has. The check can make a setup better but
never breaks one that works. ``NEXROLL_PLEX_PATH_CHECK=0`` turns it off.

Jellyfin and Emby are unaffected: their plugin downloads each preroll from
NeXroll over HTTP and never needs a path.
"""
from __future__ import annotations

import base64
import os
import threading
import time
import unicodedata
import urllib.parse
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

from backend.path_mapping import plex_path_module

VISIBLE = "visible"
MISSING = "missing"
UNKNOWN = "unknown"

_CACHE_TTL = 60.0
_cache: dict = {}
_cache_lock = threading.Lock()

_last_report: Optional[dict] = None
_report_lock = threading.Lock()

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".wmv", ".flv", ".ts",
    ".mpg", ".mpeg", ".m2ts", ".mts", ".vob",
})

# Folders a preroll library never lives in; skipped by the search so its
# budget goes on plausible places. Compared case-insensitively.
_SKIP_POSIX = {
    "/dev", "/proc", "/sys", "/run", "/boot", "/etc", "/usr", "/bin", "/sbin",
    "/lib", "/lib32", "/lib64", "/libx32", "/snap", "/tmp", "/var", "/root",
    "/system", "/library", "/applications", "/private", "/cores", "/lost+found",
}
_SKIP_WINDOWS_NAMES = {
    "windows", "program files", "program files (x86)", "$recycle.bin",
    "system volume information", "recovery", "perflogs", "$windows.~bt",
}


def enabled() -> bool:
    return os.environ.get("NEXROLL_PLEX_PATH_CHECK", "1").strip().lower() not in ("0", "false", "no", "off")


def _norm(name: str) -> str:
    return unicodedata.normalize("NFC", name or "")


def _names_equal(a: str, b: str) -> bool:
    """Same name for Plex's purposes.

    Exact first, then Unicode-normalised (macOS and SMB shares hand back
    decomposed accents), then ignoring case. Ignoring case can call a file
    visible on a case-sensitive Linux server when it is not; that errs toward
    writing the path, which is what NeXroll did before this check existed.
    """
    if a == b:
        return True
    na, nb = _norm(a), _norm(b)
    return na == nb or na.casefold() == nb.casefold()


@dataclass
class Listing:
    path: str
    dirs: dict = field(default_factory=dict)   # name -> full Plex path
    files: list = field(default_factory=list)  # names

    @property
    def empty(self) -> bool:
        return not self.dirs and not self.files

    def has_file(self, name: str) -> bool:
        return any(_names_equal(name, f) for f in self.files)

    def find_dir(self, name: str) -> Optional[str]:
        for d, full in self.dirs.items():
            if _names_equal(name, d):
                return full
        return None

    def find_dir_exact(self, name: str) -> Optional[str]:
        """Like :meth:`find_dir` but letter case must match."""
        target = _norm(name)
        for d, full in self.dirs.items():
            if name == d or target == _norm(d):
                return full
        return None


class Budget(Exception):
    """The call or time budget for one operation ran out."""


class PlexFiles:
    """Read-only view of the Plex server's filesystem."""

    def __init__(self, url: str, token: str, verify=True, timeout=(3, 8),
                 max_calls: int = 120, time_budget: float = 25.0):
        self.url = (url or "").rstrip("/")
        self.headers = {"X-Plex-Token": token or "", "Accept": "application/json"}
        self.verify = verify
        self.timeout = timeout
        self.max_calls = max_calls
        self.deadline = time.monotonic() + time_budget
        self.calls = 0
        self._platform: Optional[str] = None

    @classmethod
    def from_connector(cls, connector, **kwargs) -> Optional["PlexFiles"]:
        url = getattr(connector, "url", None)
        token = getattr(connector, "token", None)
        if not url or not token:
            return None
        return cls(url, token, verify=getattr(connector, "_verify", True), **kwargs)

    def _get(self, path: str, **params):
        if self.calls >= self.max_calls or time.monotonic() > self.deadline:
            raise Budget()
        self.calls += 1
        return requests.get(f"{self.url}{path}", headers=self.headers, params=params or None,
                            timeout=self.timeout, verify=self.verify, allow_redirects=False)

    def platform(self) -> Optional[str]:
        """Plex's host OS as it reports it ("Linux", "Windows", "MacOSX")."""
        if self._platform is None:
            try:
                r = self._get("/")
                if r.status_code == 200:
                    self._platform = (r.json().get("MediaContainer") or {}).get("platform") or ""
            except Exception:
                self._platform = ""
        return self._platform or None

    def roots(self) -> Optional[list]:
        """The starting points Plex's folder picker offers."""
        try:
            r = self._get("/services/browse")
        except Budget:
            raise
        except Exception:
            return None
        if r.status_code != 200:
            return None
        mc = (r.json() or {}).get("MediaContainer") or {}
        return [p.get("path") for p in (mc.get("Path") or []) if p.get("path")]

    def list_dir(self, path: str, fresh: bool = False) -> Optional[Listing]:
        """Folders and files in ``path`` as Plex sees them.

        ``None`` means Plex did not answer usefully (refused, errored, timed
        out); an empty :class:`Listing` means Plex answered with nothing.
        """
        key = (self.url, path)
        now = time.monotonic()
        if not fresh:
            with _cache_lock:
                hit = _cache.get(key)
            if hit and now - hit[0] < _CACHE_TTL:
                return hit[1]
        encoded = urllib.parse.quote(base64.b64encode(path.encode("utf-8")).decode("ascii"), safe="")
        try:
            r = self._get(f"/services/browse/{encoded}", includeFiles=1)
        except Budget:
            raise
        except Exception:
            return None
        if r.status_code != 200:
            return None
        try:
            mc = (r.json() or {}).get("MediaContainer") or {}
        except ValueError:
            return None
        listing = Listing(path=path)
        for p in mc.get("Path") or []:
            full = p.get("path")
            if full:
                listing.dirs[p.get("title") or plex_path_module(full).basename(full.rstrip("/\\"))] = full
        for f in mc.get("File") or []:
            name = f.get("title") or plex_path_module(f.get("path") or "").basename(f.get("path") or "")
            if name:
                listing.files.append(name)
        with _cache_lock:
            _cache[key] = (time.monotonic(), listing)
        return listing

    # -- checking paths -------------------------------------------------

    def _parent(self, path: str) -> tuple[str, str]:
        mod = plex_path_module(path)
        trimmed = path.rstrip("/\\") or path
        return mod.dirname(trimmed), mod.basename(trimmed)

    def status(self, path: str) -> tuple[str, str]:
        """(``visible`` | ``missing`` | ``unknown``, reason) for one file."""
        parent, name = self._parent(path)
        if not parent or not name:
            return UNKNOWN, "Not a full path, so Plex cannot open it."
        try:
            if plex_path_module(path).__name__ == "ntpath":
                host = (self.platform() or "").lower()
                if host and "windows" not in host:
                    return MISSING, (f"This is a Windows path, but Plex runs on {self.platform()}, which cannot "
                                     "open it. Add a path mapping to the folder as Plex sees it.")
            listing = self.list_dir(parent)
            if listing is not None and not listing.empty and listing.has_file(name):
                return VISIBLE, ""
            # A cached listing can predate a file NeXroll just placed; ask again.
            listing = self.list_dir(parent, fresh=True)
            if listing is None:
                return UNKNOWN, "Plex did not answer the folder check."
            if not listing.empty:
                if listing.has_file(name):
                    return VISIBLE, ""
                return MISSING, f"Plex can open {parent} but there is no {name} in it."
            # Nothing listed: find the nearest folder Plex can list.
            child = parent
            while True:
                up, child_name = self._parent(child)
                if not up or not child_name or up == child:
                    return UNKNOWN, "Plex could not list any folder on this path, so it could not be checked."
                above = self.list_dir(up, fresh=True)
                if above is None:
                    return UNKNOWN, "Plex did not answer the folder check."
                if not above.empty:
                    if above.find_dir_exact(child_name) is not None:
                        return MISSING, (f"Plex can see the folder {child} but cannot read anything in it. "
                                         "On macOS, allow Plex Media Server to access network volumes; "
                                         "otherwise check the share's permissions for the account Plex runs as.")
                    near = above.find_dir(child_name)
                    if near is not None:
                        # Listed empty under this spelling but present under another:
                        # the server's filenames are case-sensitive.
                        return MISSING, (f"Plex has {near}, not {child}. Letter case matters on this server, "
                                         "so the path mapping must match it exactly.")
                    return MISSING, (f"Plex has no folder {child}. Add a path mapping for this folder, "
                                     "or correct the one that points here.")
                child = up
        except Budget:
            return UNKNOWN, "The check ran out of time before reaching this file."

    def check(self, paths: Iterable[str]) -> list[dict]:
        out = []
        for p in paths:
            state, reason = self.status(p)
            out.append({"path": p, "status": state, "reason": reason})
        return out


# -- the write gate -------------------------------------------------------------

def split_preroll_value(value: str) -> tuple[Optional[str], Optional[list]]:
    """Split a preroll preference into its paths, as Plex will.

    Returns ``(delimiter, paths)``; ``paths`` is ``None`` when the value cannot
    be split safely (a piece without a video extension usually means a comma
    inside a filename), in which case nothing is filtered.
    """
    v = (value or "").strip()
    if not v:
        return None, []
    delim = ";" if ";" in v else ("," if "," in v else None)
    pieces = [p.strip() for p in v.split(delim)] if delim else [v]
    pieces = [p for p in pieces if p]
    for p in pieces:
        ext = os.path.splitext(p)[1].lower()
        if ext not in VIDEO_EXTENSIONS:
            return delim, None
    return delim, pieces


@dataclass
class GateResult:
    action: str               # ok | filtered | withheld | unverified | skipped
    value: str                # what to write (unchanged unless filtered)
    results: list = field(default_factory=list)
    message: str = ""

    @property
    def missing(self) -> list:
        return [r for r in self.results if r["status"] == MISSING]


def gate_preroll_value(files: Optional[PlexFiles], value: str, retry_delay: float = 2.0) -> GateResult:
    """Decide what NeXroll should actually write to Plex's preroll preference.

    * every file visible, or nothing could be checked: write ``value`` as is;
    * some files missing: write the rest, in their original order;
    * all files missing: write nothing, leaving Plex's current prerolls.

    Missing files are re-checked once after ``retry_delay`` seconds, because a
    network share can take a few seconds to show a file NeXroll just wrote.
    """
    if not enabled():
        return GateResult("skipped", value, message="Plex path check is turned off (NEXROLL_PLEX_PATH_CHECK=0).")
    if files is None:
        return GateResult("skipped", value, message="Plex is not connected.")
    delim, paths = split_preroll_value(value)
    if not paths:
        return GateResult("skipped", value)
    results = files.check(paths)
    if any(r["status"] == MISSING for r in results) and retry_delay:
        time.sleep(retry_delay)
        for r in results:
            if r["status"] == MISSING:
                r["status"], r["reason"] = files.status(r["path"])
    keep = [r["path"] for r in results if r["status"] != MISSING]
    missing = [r for r in results if r["status"] == MISSING]
    if not missing:
        action = "ok" if any(r["status"] == VISIBLE for r in results) else "unverified"
        result = GateResult(action, value, results)
    elif not keep:
        result = GateResult("withheld", value, results,
                            f"Plex cannot see any of the {len(paths)} preroll file(s), so NeXroll left Plex's "
                            "current prerolls in place. Check Settings > Path Mappings.")
    else:
        result = GateResult("filtered", (delim or ";").join(keep), results,
                            f"Plex cannot see {len(missing)} of {len(paths)} preroll file(s); "
                            f"NeXroll sent Plex the other {len(keep)}.")
    _record(files.url, result)
    return result


def check_value(files: Optional[PlexFiles], value: str) -> GateResult:
    """Check a preroll value without changing it, such as the one already in
    Plex's preference, and record the outcome for the health tile.

    The action says what the gate would have done with this value; nothing is
    written anywhere.
    """
    if files is None:
        return GateResult("skipped", value, message="Plex is not connected.")
    delim, paths = split_preroll_value(value)
    if not paths:
        return GateResult("skipped", value, message=("Plex has no preroll set." if not (value or "").strip()
                                                      else "This value cannot be split into files safely."))
    results = files.check(paths)
    missing = [r for r in results if r["status"] == MISSING]
    if not missing:
        action = "ok" if any(r["status"] == VISIBLE for r in results) else "unverified"
        result = GateResult(action, value, results)
    elif len(missing) == len(results):
        result = GateResult("withheld", value, results,
                            f"Plex cannot see any of the {len(results)} preroll file(s) it is set to play.")
    else:
        result = GateResult("filtered", value, results,
                            f"Plex cannot see {len(missing)} of the {len(results)} preroll file(s) it is set to play.")
    _record(files.url, result)
    return result


def library_locations(files: PlexFiles) -> list:
    """Every library folder on the Plex server, as Plex names them."""
    try:
        r = files._get("/library/sections")
        if r.status_code != 200:
            return []
        dirs = ((r.json() or {}).get("MediaContainer") or {}).get("Directory") or []
        return [loc.get("path") for d in dirs for loc in (d.get("Location") or []) if loc.get("path")]
    except Exception:
        return []


def _record(url: str, result: GateResult) -> None:
    global _last_report
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "server": url,
        "action": result.action,
        "total": len(result.results),
        "visible": sum(1 for r in result.results if r["status"] == VISIBLE),
        "unknown": sum(1 for r in result.results if r["status"] == UNKNOWN),
        "missing": [{"path": r["path"], "reason": r["reason"]} for r in result.missing][:25],
        "missing_count": len(result.missing),
        "message": result.message,
    }
    with _report_lock:
        _last_report = report


def last_report() -> Optional[dict]:
    with _report_lock:
        return dict(_last_report) if _last_report else None


def clear_listing_cache() -> None:
    """Forget cached folder listings (the next check asks Plex again)."""
    with _cache_lock:
        _cache.clear()


def reset_state() -> None:
    """Forget cached listings and the last report (tests, disconnects)."""
    global _last_report
    with _cache_lock:
        _cache.clear()
    with _report_lock:
        _last_report = None


# -- finding NeXroll's folder on the Plex side ---------------------------------

def is_system_folder(path: str) -> bool:
    """A folder no preroll library lives in (/dev, C:\Windows, ...)."""
    mod = plex_path_module(path)
    if mod.__name__ == "ntpath":
        name = mod.basename(path.rstrip("\\/")).lower()
        return name in _SKIP_WINDOWS_NAMES
    p = path.rstrip("/").lower()
    return any(p == s or p.startswith(s + "/") for s in _SKIP_POSIX)


def _priority(path: str, hint: str) -> tuple:
    base = plex_path_module(path).basename(path.rstrip("/\\")).casefold()
    score = 0 if (hint and base == hint) else (1 if ("roll" in base or "intro" in base) else 2)
    return (score, path.count("/") + path.count("\\"))


def find_folder(files: PlexFiles, known: list, local_root_name: str = "",
                library_locations: Iterable[str] = (), max_depth: int = 5) -> dict:
    """Search Plex's filesystem for the folder holding NeXroll's prerolls.

    ``known`` lists preroll paths relative to NeXroll's folder, with ``/``
    separators. A candidate must contain the first part of some of them and
    then hold up to three of them, subfolders included, before it is
    accepted, so two folders that merely share a few filenames are not
    confused. Library folders are listed but not walked, since a movie
    library can hold thousands of folders.
    """
    known = [k.replace("\\", "/").strip("/") for k in known if k]
    # Only paths inside the folder describe it; "../x" is a file elsewhere.
    known = [k for k in known if k and k != ".." and not k.startswith("../")]
    if not known:
        return {"found": False, "reason": "NeXroll has no prerolls in this folder to look for.", "calls": 0}
    tops = {k.split("/")[0] for k in known}
    need = max(1, min(2, len(tops)))
    hint = (local_root_name or "").casefold()
    libs = {l for l in library_locations if l}
    samples = sorted(known, key=lambda k: (-k.count("/"), k))[:3]
    checked: set = set()

    def confirm(candidate: str) -> bool:
        mod = plex_path_module(candidate)
        for rel in samples:
            parent_rel, _, name = rel.rpartition("/")
            folder = candidate
            for part in [p for p in parent_rel.split("/") if p]:
                listing = files.list_dir(folder)
                nxt = listing.find_dir(part) if listing else None
                if not nxt:
                    return False
                folder = nxt
            listing = files.list_dir(folder)
            if not listing or not listing.has_file(name):
                return False
        return True

    try:
        roots = files.roots()
        if roots is None:
            return {"found": False, "reason": "Plex would not list its folders. The Plex account NeXroll uses must be the server owner.",
                    "calls": files.calls}
        starts = set(r for r in roots if not is_system_folder(r))
        for loc in libs:
            parent = plex_path_module(loc).dirname(loc.rstrip("/\\"))
            if parent:
                starts.add(parent)
        queue = deque(sorted(starts, key=lambda p: _priority(p, hint)))
        seen: set = set()
        while queue:
            path = queue.popleft()
            if path in seen or is_system_folder(path):
                continue
            seen.add(path)
            listing = files.list_dir(path)
            if not listing or listing.empty:
                continue
            names = list(listing.dirs) + listing.files
            score = sum(1 for t in tops if any(_names_equal(t, n) for n in names))
            if score >= need and path not in checked:
                checked.add(path)
                if confirm(path):
                    return {"found": True, "plex_path": path, "verified": samples, "calls": files.calls}
            depth = path.count("/") + path.count("\\")
            if path in libs or depth >= max_depth:
                continue
            for child in sorted(listing.dirs.values(), key=lambda p: _priority(p, hint)):
                queue.append(child)
    except Budget:
        return {"found": False, "calls": files.calls, "reason": (
            f"NeXroll looked through {files.calls} folders on the Plex server without finding its prerolls. "
            "Use Browse Plex to pick the folder yourself, or check that the Plex server can reach the share.")}
    return {"found": False, "calls": files.calls, "reason": (
        "No folder the Plex server can see contains NeXroll's prerolls. Check that the Plex server can reach "
        "the share, and on macOS that Plex Media Server is allowed to access network volumes.")}
