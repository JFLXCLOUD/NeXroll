"""Recoverable trash for preroll media.

Deleting a preroll used to call os.remove on the user's video file, which made a
misclick in the UI unrecoverable — including for files the user had copied into
the library themselves and that the scanner had merely indexed. Media is now
moved into a trash folder and only erased once its retention window expires.

The trash lives *beside* the file whenever the file is inside the prerolls
library, so the move is a same-volume rename rather than a copy. That matters:
libraries commonly sit on a network share while the data dir is on a local disk,
and copying gigabytes over SMB just to delete something would be both slow and a
good way to fill the system drive. The folder name starts with a dot, which the
scanner already prunes (scanner._iter_preroll_files), so trashed files are never
re-indexed as prerolls.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import uuid
from typing import Optional

from backend.preroll_files import _move_to_exact_destination, move_to_unique_destination

TRASH_DIR_NAME = ".nexroll-trash"
MANIFEST_NAME = "manifest.json"
DEFAULT_RETENTION_DAYS = 30


def retention_days() -> int:
    """Days a trashed file is kept before it is erased. 0 disables auto-purge."""
    raw = os.environ.get("NEXROLL_TRASH_RETENTION_DAYS")
    if raw is None:
        return DEFAULT_RETENTION_DAYS
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS


def _norm(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))
    except Exception:
        return path


def _is_within(path: str, directory: Optional[str]) -> bool:
    if not path or not directory:
        return False
    p, d = _norm(path), _norm(directory)
    if not p or not d:
        return False
    return p == d or p.startswith(d + os.sep)


def trash_roots(prerolls_dir: Optional[str], data_dir: Optional[str]) -> list[str]:
    """Every folder that can hold trash entries, most specific first."""
    roots = []
    for base in (prerolls_dir, data_dir):
        if not base:
            continue
        root = os.path.join(os.path.abspath(base), TRASH_DIR_NAME)
        if root not in roots:
            roots.append(root)
    return roots


def resolve_trash_root(source_path: str, prerolls_dir: Optional[str],
                       data_dir: Optional[str]) -> str:
    """Trash folder to use for ``source_path`` — same volume where possible."""
    if _is_within(source_path, prerolls_dir):
        return os.path.join(os.path.abspath(prerolls_dir), TRASH_DIR_NAME)
    base = data_dir or os.path.dirname(os.path.abspath(source_path))
    return os.path.join(os.path.abspath(base), TRASH_DIR_NAME)


def _new_entry_id() -> str:
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def move_to_trash(source_path: str, prerolls_dir: Optional[str], data_dir: Optional[str],
                  metadata: Optional[dict] = None) -> Optional[dict]:
    """Move a file into the trash and return its manifest, or None if it is gone.

    The caller is responsible for reversing this (via the returned
    ``trashed_path``) if the database work that follows fails.
    """
    if not source_path or not os.path.isfile(source_path):
        return None

    original = os.path.abspath(source_path)
    entry_id = _new_entry_id()
    entry_dir = os.path.join(resolve_trash_root(original, prerolls_dir, data_dir), entry_id)
    os.makedirs(entry_dir, exist_ok=True)

    _name, trashed_path = move_to_unique_destination(
        original, entry_dir, os.path.basename(original)
    )

    manifest = {
        "entry_id": entry_id,
        "original_path": original,
        "filename": os.path.basename(original),
        "trashed_path": trashed_path,
        "deleted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "size_bytes": _safe_size(trashed_path),
    }
    if metadata:
        manifest.update(metadata)

    try:
        with open(os.path.join(entry_dir, MANIFEST_NAME), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
    except OSError:
        # A missing manifest costs the restore metadata, not the file itself —
        # never fail the deletion over it.
        pass

    return manifest


def _safe_size(path: str) -> Optional[int]:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def discard_entry_dir(manifest: Optional[dict]) -> None:
    """Remove an entry folder left behind when a trashed file was moved back."""
    if not manifest:
        return
    trashed = manifest.get("trashed_path")
    if not trashed:
        return
    entry_dir = os.path.dirname(trashed)
    if os.path.basename(os.path.dirname(entry_dir)) != TRASH_DIR_NAME:
        return  # Not ours; leave it alone.
    shutil.rmtree(entry_dir, ignore_errors=True)


def _read_manifest(entry_dir: str) -> Optional[dict]:
    manifest_path = os.path.join(entry_dir, MANIFEST_NAME)
    data: dict = {}
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}

    # Trust the folder over the manifest: an entry whose file was moved or whose
    # manifest never got written must still be listable and restorable.
    files = []
    try:
        files = [f for f in os.listdir(entry_dir) if f != MANIFEST_NAME]
    except OSError:
        return None
    if not files:
        return None

    trashed_path = os.path.join(entry_dir, files[0])
    data.setdefault("entry_id", os.path.basename(entry_dir))
    data.setdefault("filename", files[0])
    data.setdefault("original_path", None)
    data["trashed_path"] = trashed_path
    data["size_bytes"] = _safe_size(trashed_path)
    data["restorable"] = bool(data.get("original_path"))
    return data


def list_trash(prerolls_dir: Optional[str], data_dir: Optional[str]) -> list[dict]:
    """Every trash entry across both roots, newest first."""
    entries = []
    seen = set()
    for root in trash_roots(prerolls_dir, data_dir):
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            entry_dir = os.path.join(root, name)
            if not os.path.isdir(entry_dir) or name in seen:
                continue
            manifest = _read_manifest(entry_dir)
            if manifest:
                seen.add(name)
                entries.append(manifest)
    entries.sort(key=lambda e: e.get("deleted_at") or "", reverse=True)
    return entries


def find_entry(entry_id: str, prerolls_dir: Optional[str],
               data_dir: Optional[str]) -> Optional[dict]:
    if not entry_id or os.sep in entry_id or "/" in entry_id or ".." in entry_id:
        return None  # Never let a caller escape the trash roots.
    for root in trash_roots(prerolls_dir, data_dir):
        entry_dir = os.path.join(root, entry_id)
        if os.path.isdir(entry_dir):
            manifest = _read_manifest(entry_dir)
            if manifest:
                return manifest
    return None


def restore_entry(entry_id: str, prerolls_dir: Optional[str],
                  data_dir: Optional[str]) -> dict:
    """Move a trashed file back to where it came from.

    Raises ValueError when the entry is unknown or its origin was not recorded,
    and OSError when the move itself fails.
    """
    manifest = find_entry(entry_id, prerolls_dir, data_dir)
    if not manifest:
        raise ValueError("Trash entry not found")
    original = manifest.get("original_path")
    if not original:
        raise ValueError("Trash entry has no recorded original path")
    if os.path.exists(original):
        raise ValueError(f"A file already exists at {original}")

    _move_to_exact_destination(manifest["trashed_path"], original)
    discard_entry_dir(manifest)
    manifest["restored_to"] = original
    return manifest


def purge_entry(entry_id: str, prerolls_dir: Optional[str],
                data_dir: Optional[str]) -> bool:
    """Erase one trash entry for good."""
    manifest = find_entry(entry_id, prerolls_dir, data_dir)
    if not manifest:
        return False
    entry_dir = os.path.dirname(manifest["trashed_path"])
    shutil.rmtree(entry_dir, ignore_errors=True)
    return not os.path.isdir(entry_dir)


def purge_trash(prerolls_dir: Optional[str], data_dir: Optional[str],
                older_than_days: Optional[int] = None) -> dict:
    """Erase trash entries. With ``older_than_days`` only expired ones go.

    Age comes from the folder mtime rather than the manifest so an entry with a
    damaged manifest still expires instead of living forever.
    """
    removed, freed = 0, 0
    cutoff = None
    if older_than_days is not None:
        if older_than_days <= 0:
            return {"removed": 0, "bytes_freed": 0}
        cutoff = datetime.datetime.utcnow().timestamp() - (older_than_days * 86400)

    for root in trash_roots(prerolls_dir, data_dir):
        if not os.path.isdir(root):
            continue
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            entry_dir = os.path.join(root, name)
            if not os.path.isdir(entry_dir):
                continue
            if cutoff is not None:
                try:
                    if os.path.getmtime(entry_dir) > cutoff:
                        continue
                except OSError:
                    continue
            manifest = _read_manifest(entry_dir)
            freed += (manifest or {}).get("size_bytes") or 0
            shutil.rmtree(entry_dir, ignore_errors=True)
            if not os.path.isdir(entry_dir):
                removed += 1
    return {"removed": removed, "bytes_freed": freed}
