"""Translate NeXroll's own file paths into the paths a Plex server uses.

NeXroll and Plex often see the same file under different names: a Docker
container mounts the preroll share at ``/data/prerolls`` while the Plex host
knows it as ``/Volumes/Plex/PreRoll`` or ``\\\\NAS\\PreRoll``. A path mapping
records one such pair of prefixes. Plex needs the full path to each file in
its own terms, so every value written to Plex's preroll preference passes
through :func:`translate`.

This logic used to be repeated at every place NeXroll writes to Plex. The
copies agreed with each other but shared one fault: a prefix matched any path
that merely began with the same characters, so ``/data/pre`` also claimed
``/data/prerolls2``. Matching now requires a whole folder name.

Jellyfin and Emby never use these mappings. Their NeXroll Intros plugin
downloads each preroll from NeXroll over HTTP, so no file path crosses over.
"""
from __future__ import annotations

import json
import ntpath
import os
import posixpath
import sys
from typing import Any, Iterable, Optional


def _host_is_windows() -> bool:
    return sys.platform.startswith("win")


def load_mappings(raw: Any) -> list[dict]:
    """Return the saved ``[{local, plex}]`` pairs, ignoring anything malformed.

    ``raw`` is the JSON text stored on the settings row, or an already parsed
    list. Entries missing either side are dropped rather than failing the
    whole set, matching how the individual copies behaved.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and item.get("local") and item.get("plex"):
            out.append({"local": str(item["local"]), "plex": str(item["plex"])})
    return out


def mappings_from_setting(setting: Any) -> list[dict]:
    """Mappings stored on a ``Setting`` row (or an empty list)."""
    return load_mappings(getattr(setting, "path_mappings", None) if setting is not None else None)


def _is_under(path: str, prefix: str, windows: bool) -> bool:
    """Whether ``path`` is ``prefix`` itself or lies inside it.

    Both arguments are already normalised for the host. A prefix that ends in a
    separator (a filesystem root such as ``/`` or ``C:\\``) covers everything
    beneath it; otherwise the next character must be a separator, so that
    ``/data/pre`` does not claim ``/data/prerolls``.
    """
    if windows:
        path, prefix = path.lower(), prefix.lower()
    if not path.startswith(prefix):
        return False
    if len(path) == len(prefix) or prefix.endswith(("/", "\\")):
        return True
    return path[len(prefix)] in ("/", "\\")


def _join_plex(prefix: str, rest: str) -> str:
    """Append ``rest`` to a Plex-side prefix using the separator it implies.

    An empty ``rest`` still gains the separator, as the original copies did,
    so a folder translates to ``/Volumes/Plex/PreRoll/``.
    """
    if ("/" in prefix) and ("\\" not in prefix):
        return prefix.rstrip("/") + "/" + rest.replace("\\", "/")
    if "\\" in prefix:
        return prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
    return prefix.rstrip("/") + "/" + rest.replace("\\", "/")


def translate_detail(local_path: str, mappings: Iterable[dict], windows: Optional[bool] = None) -> dict:
    """Translate one path and say which mapping, if any, did it.

    The longest matching local prefix wins. Case is ignored when NeXroll runs
    on Windows, where the filesystem ignores it too. An unmatched path is
    returned unchanged with ``matched`` False, because some setups genuinely
    share one path on both sides.
    """
    if windows is None:
        windows = _host_is_windows()
    lp = os.path.normpath(local_path)
    best = None
    best_src = ""
    for m in mappings or []:
        src = os.path.normpath(str(m.get("local")))
        if _is_under(lp, src, windows) and len(src) > len(best_src):
            best, best_src = m, src
    if best is None:
        return {"input": local_path, "output": local_path, "matched": False}
    rest = lp[len(best_src):].lstrip("\\/")
    out = _join_plex(str(best.get("plex")), rest)
    return {
        "input": local_path,
        "output": out,
        "matched": True,
        "matched_local_prefix": best_src,
        "mapping": best,
    }


def translate(local_path: str, mappings: Iterable[dict], windows: Optional[bool] = None) -> str:
    """The Plex-side path for ``local_path`` (unchanged when nothing matches)."""
    try:
        return translate_detail(local_path, mappings, windows)["output"]
    except Exception:
        return local_path


def plex_path_module(path: str):
    """``ntpath`` for a Windows-style Plex path, ``posixpath`` otherwise.

    Plex reports paths in its own host's style, which need not match the
    machine NeXroll runs on, so the style is read from the path itself.
    """
    p = path or ""
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        return ntpath
    if p.startswith("\\\\") or ("\\" in p and "/" not in p):
        return ntpath
    return posixpath
