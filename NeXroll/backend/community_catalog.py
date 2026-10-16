"""Tidying the Community Prerolls index for display.

Titles: the index stores a title made with ``str.title()`` after replacing
"-" and "_" with spaces, which turns "Let_s" into "Let S", "1080p" into
"1080P" and keeps 32-character upload ids on archive files. ``clean_title``
rebuilds the title from the file name in the path instead. The stored titles
are left alone because "Match Existing Prerolls" compares against them.

Duplicates: the server keeps byte-identical copies of many files in a second
folder (mostly /Archives/). ``dedupe`` keeps one copy per file and lists the
others in ``duplicate_ids`` so a download of any copy marks the row.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import unquote

_VIDEO_EXT = re.compile(r"\.(mp4|m4v|mkv|mov|webm|avi|wmv|ts)$", re.I)
_ID_PREFIX = re.compile(r"^[0-9a-f]{32}[\s._-]*", re.I)
# "Let_s", "Wouldn_t": an apostrophe the uploader's tooling turned into "_".
_CONTRACTION = re.compile(r"(?<=[A-Za-z])_(s|t|re|ll|ve|d|m)(?![A-Za-z0-9])", re.I)
_DOT_BETWEEN_WORDS = re.compile(r"(?<=[A-Za-z])\.(?=[A-Za-z])")
_UPPER_WORDS = {"hd", "sdr", "hdr", "uhd", "3d", "imax", "thx", "dts", "nye", "usa", "uk", "tv", "ai", "dvd"}


def _title_word(word: str) -> str:
    lower = word.lower()
    if re.fullmatch(r"\d+(p|i|fps|bit|st|nd|rd|th)", lower):
        return lower                      # 1080p, 60fps, 4th
    if re.fullmatch(r"\d+k", lower) or lower in _UPPER_WORDS:
        return lower.upper()              # 4K, HDR
    return word[:1].upper() + word[1:]


def _tidy(name: str) -> str:
    name = _ID_PREFIX.sub("", name) or name
    name = _CONTRACTION.sub(r"'\1", name)
    name = _DOT_BETWEEN_WORDS.sub(" ", name.replace("_", " "))
    name = re.sub(r"\s+", " ", name).strip(" .-")
    if name == name.lower():
        # All-lowercase names get title case; anything the uploader cased is kept.
        name = " ".join(_title_word(w) for w in name.split(" "))
    return name


def clean_title(path: str, fallback: str = "") -> str:
    """Readable title from the file name at the end of an index path."""
    parts = unquote(str(path or "").replace("\\", "/")).rstrip("/").split("/")
    name = _tidy(_VIDEO_EXT.sub("", parts[-1]).strip())
    if not name:
        return fallback
    if (len(name) <= 2 or name.isdigit()) and len(parts) >= 2 and parts[-2]:
        # "7" or "T" alone says nothing; the folder ("Tallies") does.
        folder = _tidy(parts[-2].rsplit(" - ", 1)[0])
        if folder:
            name = f"{folder} {name}"
    return name


def tidy_titles(entries: Iterable[dict]) -> None:
    """Replace each entry's title with clean_title, in place."""
    for entry in entries:
        entry["title"] = clean_title(entry.get("path") or entry.get("id"), entry.get("title") or "")


# ------------------------------------------------------- platform versions
#
# Many prerolls come in a Plex, a Jellyfin and an Emby version: side by side
# ("Adult Swim Plex v2.mp4", "Adult Swim Jellyfin v2.mp4") or in sibling
# folders ("/Community/_Plex/X - Creator/", "/Community/_Jellyfin/X - Creator/").
# ``group_versions`` shows each preroll once with its versions listed, so a
# user with Plex and Jellyfin can take both and a Plex-only user isn't shown
# three rows for one preroll.

PLATFORM_ORDER = ("plex", "jellyfin", "emby", "universal")
# Whole words only: "Bird Plexus" and "PleXP" are not Plex versions.
_PLATFORM_WORD = re.compile(r"(?<![A-Za-z0-9])(plex|jellyfin|emby|universal)(?![A-Za-z0-9])", re.I)


def _path_parts(entry: dict) -> list:
    return unquote(str(entry.get("path") or entry.get("id") or "").replace("\\", "/")).split("/")


def platform_of(entry: dict) -> Optional[str]:
    """The platform a file is made for, from its name, else its nearest folder."""
    for part in reversed(_path_parts(entry)):
        found = _PLATFORM_WORD.search(part)
        if found:
            return found.group(1).lower()
    return None


def _plain(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _version_key(entry: dict) -> tuple:
    """Path with platform words taken out: equal for versions of one preroll."""
    parts = _path_parts(entry)
    folders = tuple(_plain(_PLATFORM_WORD.sub(" ", p)) for p in parts[:-1])
    stem = _ID_PREFIX.sub("", _VIDEO_EXT.sub("", parts[-1]))
    return folders, _plain(_PLATFORM_WORD.sub(" ", stem))


def strip_platform(title: str) -> str:
    """'Adult Swim Plex v2' -> 'Adult Swim v2'; 'Sky Showtime - Jellyfin' -> 'Sky Showtime'."""
    text = _PLATFORM_WORD.sub(" ", title or "")
    text = re.sub(r"\(\s*\)|\[\s*\]", " ", text)
    text = re.sub(r"\s*-\s*(?:-\s*)+", " - ", text)        # "X -  - Y" -> "X - Y"
    text = re.sub(r"\s+-\s*(?=\(|$)|^\s*-\s+", " ", text)   # dangling " -"
    return re.sub(r"\s+", " ", text).strip(" -_.") or (title or "")


def group_versions(entries: list, prefer: Iterable[str] = ()) -> list:
    """Fold platform versions of one preroll into one row, in input order.

    The row is the preferred version (the first platform in ``prefer`` it
    has, then Plex, Jellyfin, Emby, Universal) with the platform word taken out
    of its title and ``versions``: [{id, platform, title, path, url,
    size_bytes, duplicate_ids?}] in that same order. Entries with no
    counterpart, or whose counterparts are all the same platform, pass through
    unchanged. A second file for a platform already in the group stays a row of
    its own.
    """
    prefer = [p for p in prefer if p in PLATFORM_ORDER]
    order = prefer + [p for p in PLATFORM_ORDER if p not in prefer]
    rank = {p: i for i, p in enumerate(order)}
    groups: dict = {}
    for entry in entries:
        groups.setdefault(_version_key(entry), []).append(entry)

    rows_for: dict = {}   # id(first member) -> rows replacing the group there
    for members in groups.values():
        by_platform: dict = {}
        extras = []
        for member in members:
            platform = platform_of(member) or "universal"
            if platform in by_platform:
                extras.append(member)
            else:
                by_platform[platform] = member
        if len(by_platform) < 2:
            rows_for[id(members[0])] = members
            continue
        ordered = sorted(by_platform.items(), key=lambda kv: rank[kv[0]])
        primary = ordered[0][1]
        versions = []
        for platform, member in ordered:
            version = {k: member.get(k) for k in ("id", "path", "url", "size_bytes") if member.get(k) is not None}
            version.update(platform=platform, title=member.get("title") or "")
            if member.get("duplicate_ids"):
                version["duplicate_ids"] = member["duplicate_ids"]
            versions.append(version)
        row = dict(primary,
                   title=strip_platform(primary.get("title") or ""),
                   versions=versions,
                   modified_time=max((m.get("modified_time") or 0) for _, m in ordered))
        rows_for[id(members[0])] = [row] + extras

    out = []
    for entry in entries:
        out.extend(rows_for.get(id(entry), ()))
    return out


def _folder_rank(entry: dict) -> int:
    """Copies outside /Archives/ are the ones to show."""
    return 1 if str(entry.get("category") or "").strip().lower() == "archives" else 0


def _ext(entry: dict) -> str:
    path = str(entry.get("path") or entry.get("id") or "")
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def _same_length(a: Optional[float], b: Optional[float]) -> bool:
    return a is None or b is None or abs(a - b) < 0.05


def dedupe(entries: list, durations: Optional[dict] = None, key=lambda e: e.get("path") or e.get("id")) -> list:
    """One entry per file, in the input order.

    Two entries are the same file when their byte size and extension match and
    their lengths match (or a length is not known yet). The copy kept is the
    first one outside /Archives/, else the first one. Kept entries that had
    copies come back as new dicts with ``duplicate_ids``; the others are
    returned as they are.
    """
    durations = durations or {}
    preferred = sorted(range(len(entries)), key=lambda i: (_folder_rank(entries[i]), i))
    by_size: dict = {}
    copies_of: dict = {}   # kept index -> [duplicate ids]
    hidden = set()
    for i in preferred:
        entry = entries[i]
        size = entry.get("size_bytes")
        if not size:
            continue
        seconds = durations.get(key(entry))
        bucket = by_size.setdefault((size, _ext(entry)), [])
        for kept in bucket:
            if _same_length(durations.get(key(entries[kept])), seconds):
                copies_of.setdefault(kept, []).append(entry.get("id") or key(entry))
                hidden.add(i)
                break
        else:
            bucket.append(i)
    out = []
    for i, entry in enumerate(entries):
        if i in hidden:
            continue
        out.append(dict(entry, duplicate_ids=copies_of[i]) if i in copies_of else entry)
    return out
