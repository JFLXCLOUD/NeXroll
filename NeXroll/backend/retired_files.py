"""Trailer files removed while Plex may still play them.

Plex doesn't take a copy of its preroll list when a movie starts; it reads the
next entry from CinemaTrailersPrerollID as it goes. A file deleted while its
path is in that list leaves Plex an entry with nothing behind it, and the
trailer fails to play (user report, November 6: "after the coming soon grid it
failed to play the 1st trailer"). Retention cleanup already kept such files,
but NeX-Up's cleanup when a movie arrives, both syncs, Sonarr expiry, Library
Trailers rotation and the delete buttons removed them at once.

retire() deletes a file that isn't in Plex's list. A file that is (or might
be: Plex couldn't be asked) is kept, the scheduler rewrites Plex's list from
the database, which no longer has the trailer, and purge() deletes the file
once Plex's list has moved on. Kept paths are saved beside the database, so a
restart can't leave them on disk for good.
"""

from __future__ import annotations

import json
import os
import threading
import xml.etree.ElementTree as ET
from typing import Callable, Iterable, Optional

import requests

from backend import path_mapping
from backend.plex_visibility import split_preroll_value

_LOCK = threading.Lock()
_PATHS: set = set()
_PERSIST_PATH: Optional[str] = None


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def configure(path: Optional[str]) -> None:
    """Save kept paths to ``path`` and load the ones already there (startup)."""
    global _PERSIST_PATH
    _PERSIST_PATH = path
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            rows = json.load(handle).get("paths") or []
    except (OSError, ValueError, AttributeError):
        return
    with _LOCK:
        _PATHS.update(os.path.abspath(p) for p in rows if isinstance(p, str) and p)


def _save() -> None:
    if not _PERSIST_PATH:
        return
    try:
        tmp = _PERSIST_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"paths": sorted(_PATHS)}, handle, indent=1)
        os.replace(tmp, _PERSIST_PATH)
    except OSError:
        pass


def pending() -> list:
    """Kept files still waiting for Plex's list to move on."""
    with _LOCK:
        return sorted(_PATHS)


def reset() -> None:
    """Forget everything (tests)."""
    with _LOCK:
        _PATHS.clear()


def read_plex_list(setting) -> Optional[str]:
    """Plex's preroll preference as it is now, or None if Plex couldn't be asked."""
    url = str(getattr(setting, "plex_url", None) or "").rstrip("/")
    if not url:
        return None
    try:
        from backend.plex_connector import PlexConnector
        connector = PlexConnector(url, getattr(setting, "plex_token", None))
        response = requests.get(f"{url}/:/prefs", headers=connector.headers, timeout=10,
                                verify=getattr(connector, "_verify", True))
        if response.status_code != 200 or not response.content:
            return None
        root = ET.fromstring(response.content)
    except Exception:
        return None
    for element in root.iter("Setting"):
        if element.get("id") == "CinemaTrailersPrerollID":
            return element.get("value") or ""
    return None


def in_plex_list(paths: Iterable[str], setting,
                 reader: Optional[Callable] = None) -> Optional[set]:
    """Which of ``paths`` (local paths) Plex's list holds now.

    An empty set without Plex configured; None when Plex couldn't be asked,
    so callers keep the files. Paths are compared as Plex sees them (through
    the path mappings), whole entry first and then, when the list can't be
    split cleanly (a comma in a filename), as text, which can only keep a file
    longer, never delete one Plex still has.
    """
    paths = list(paths)
    if not str(getattr(setting, "plex_url", None) or "").strip():
        return set()
    value = (reader or read_plex_list)(setting)
    if value is None:
        return None
    mappings = []
    try:
        raw = getattr(setting, "path_mappings", None)
        data = json.loads(raw) if raw else []
        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
    except (TypeError, ValueError):
        mappings = []
    _, entries = split_preroll_value(value)
    folded = {e.casefold() for e in (entries or [])}
    text = value.casefold()
    present = set()
    for path in paths:
        plex_path = path_mapping.translate(os.path.abspath(path), mappings).casefold()
        if plex_path in folded or (entries is None and plex_path in text):
            present.add(path)
    return present


def _delete(path: str) -> bool:
    try:
        if os.path.isfile(path):
            os.remove(path)
        return True
    except OSError:
        return False


def retire(paths: Iterable[str], setting, reader: Optional[Callable] = None) -> dict:
    """Delete each file now, or keep it while Plex's list may still hold it."""
    unique = list(dict.fromkeys(os.path.abspath(p) for p in paths if p))
    if not unique:
        return {"deleted": [], "kept": []}
    present = in_plex_list(unique, setting, reader)
    deleted, kept = [], []
    for path in unique:
        if present is None or path in present:
            kept.append(path)
        elif _delete(path):
            deleted.append(path)
    if kept:
        with _LOCK:
            _PATHS.update(kept)
            _save()
    return {"deleted": deleted, "kept": kept}


def purge(setting, in_use: Callable[[list], set], reader: Optional[Callable] = None) -> dict:
    """Delete kept files Plex's list no longer holds.

    ``in_use`` returns the paths the library refers to again (a trailer
    downloaded anew to the same path); those are dropped, not deleted.
    Returns what was deleted and what Plex still holds.
    """
    waiting = pending()
    if not waiting:
        return {"deleted": [], "held": [], "reused": []}
    reused = in_use(waiting)
    rest = [p for p in waiting if p not in reused]
    present = in_plex_list(rest, setting, reader) if rest else set()
    if present is None:
        held, deleted = rest, []
    else:
        held = [p for p in rest if p in present]
        deleted = [p for p in rest if p not in present and _delete(p)]
    with _LOCK:
        _PATHS.difference_update(reused)
        _PATHS.difference_update(deleted)
        _save()
    return {"deleted": deleted, "held": held, "reused": sorted(reused)}


def referenced_paths(db, paths: list) -> set:
    """Which of ``paths`` a preroll or trailer row still points at."""
    import backend.models as models
    wanted = {_key(p): p for p in paths}
    found = set()
    for column in (models.Preroll.path, models.ComingSoonTrailer.local_path,
                   models.ComingSoonTVTrailer.local_path, models.LibraryTrailer.local_path):
        for (value,) in db.query(column).filter(column.isnot(None)).all():
            hit = wanted.get(_key(value))
            if hit:
                found.add(hit)
    return found
