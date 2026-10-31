"""Matching local prerolls to the Community Prerolls index.

One set of rules for the edit dialog's Auto-match, Match Existing Prerolls,
the startup pass for old Community downloads and sequence export's repair of
mangled IDs. Each used to have its own title rules; replayed on JB's
production library (October 30) they linked "Carrie_7340_trailer" to "Car",
"20thCenturyFox-Flute" to "Fox" and "Waldo The Movie_x264" (130 s) to
"The Core - PLEX 2 x264" (54 s).

* Same file: a local file with the byte size of an index file is that file
  (this also finds renamed ones), unless both lengths are known and differ.
* Titles: whole words, after dropping words that don't say which preroll it
  is (platform, "pre-roll", resolution, codec, "the"...). "LightSpeed" and
  "Light Speed" are the same title.
* Lengths: a title is linked only when the lengths agree within
  LENGTH_TOLERANCE. On prod, re-encoded copies of linked files differ by at
  most 0.47 s and the user's own edits by 1.3 s or more. When the lengths
  differ the entry is at most a low suggestion. With a length missing on
  either side, only an exact title that names one preroll is linked.
* NeXroll's own files (NeX-Up trailers, Coming Soon lists, generated
  prerolls, theme backdrops) are never matched: ``is_nexroll_file``.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Iterable, Optional, Union

from backend import community_catalog

LENGTH_TOLERANCE = 1.0   # seconds
LINK_TITLE = 0.8         # title score linked when the lengths agree
SUGGEST_TITLE = 0.5      # lowest title score offered as a suggestion
MAX_SUGGESTIONS = 10

# Words that don't say which preroll a file is.
FILLER = frozenset("""
    plex jellyfin emby universal pre roll preroll prerolls
    the a an of and to in on for with by at
    hd fhd uhd sdr 4k 8k 480p 720p 1080p 1440p 2160p 60fps 50fps 30fps 25fps 24fps
    x264 x265 h264 h265 hevc avc av1 aac ac3 eac3
    old final updated remastered copy
""".split())

_VIDEO_EXT = re.compile(r"\.(mp4|m4v|mkv|mov|webm|avi|wmv|ts)$", re.I)
_ID_PREFIX = re.compile(r"^[0-9a-f]{32}[\s._-]*", re.I)
_CONTRACTION = re.compile(r"(?<=[A-Za-z])_(s|t|re|ll|ve|d|m)(?![A-Za-z0-9])", re.I)
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_WORD = re.compile(r"[a-z0-9]+")

# NeX-Up trailers are saved as Title_<tmdb id>_trailer.ext (TV: _tvdb<id>_);
# yt-dlp leaves Title_<id>_trailer.f137.mp4 while it works.
_TRAILER_FILE = re.compile(r"_(?:tvdb)?\d+_trailer(?:\.f\d+)?\.[a-z0-9]+$", re.I)
# Coming Soon lists, generated prerolls and theme backdrops (in its assets/).
_GENERATED_FOLDER = "dynamic_prerolls"


def is_nexroll_file(path: Optional[str], filename: Optional[str] = None) -> bool:
    """A file NeXroll made itself, wherever its NeX-Up folder was at the time."""
    parts = str(path or "").replace("\\", "/").split("/")
    name = filename or parts[-1]
    if _TRAILER_FILE.search(name or ""):
        return True
    return any(part.lower() == _GENERATED_FOLDER for part in parts[:-1])


# Filler glued to a word ("stpatrickplex", "HBOPLEX") comes off its ends.
_GLUED = ("preroll", "jellyfin", "plex", "emby")


def _all_words(name: Optional[str]) -> list:
    text = _VIDEO_EXT.sub("", str(name or "").strip())
    text = _ID_PREFIX.sub("", text) or text
    text = _CONTRACTION.sub(r"\1", text)        # "Let_s" -> "Lets"
    text = re.sub(r"['’`]", "", text)     # "Let's" -> "Lets"
    text = _CAMEL.sub(" ", text)
    return _WORD.findall(text.lower())


def _stem(word: str) -> str:
    """Plural and possessive alike: "Valentines" / "Valentine's", "Lights"."""
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is", "mas")):
        return word[:-1]
    return word


def _key_words(found: list) -> list:
    return [w for w in found if w not in FILLER] or found


def words(name: Optional[str]) -> tuple:
    """The words of a title or file name that say which preroll it is."""
    return tuple(_stem(w) for w in _key_words(_all_words(name)))


def joined(name: Optional[str]) -> str:
    """The title as one string, so "LightSpeed" and "Light Speed" are equal."""
    text = "".join(_key_words(_all_words(name)))
    trimmed = True
    while trimmed:
        trimmed = False
        for word in _GLUED:
            if text.endswith(word) and len(text) > len(word) + 2:
                text, trimmed = text[:-len(word)], True
            if text.startswith(word) and len(text) > len(word) + 2:
                text, trimmed = text[len(word):], True
    return text


def _dice(a, b) -> float:
    first, second = set(a), set(b)
    return 2 * len(first & second) / (len(first) + len(second)) if first and second else 0.0


def title_score(a: tuple, b: tuple, a_joined: str = "", b_joined: str = "") -> float:
    """1.0 for the same title; else the share of words in common (Dice),
    0 unless they share a real word (three letters or more)."""
    if not a or not b:
        return 0.0
    if set(a) == set(b) or (a_joined and a_joined == b_joined):
        return 1.0
    if not any(len(w) >= 3 and not w.isdigit() for w in set(a) & set(b)):
        return 0.0
    return _dice(a, b)


def lengths_agree(a: Optional[float], b: Optional[float]) -> Optional[bool]:
    """None when either length is unknown."""
    if not a or not b:
        return None
    return abs(float(a) - float(b)) <= LENGTH_TOLERANCE


class _Entry:
    __slots__ = ("raw", "id", "title", "words", "joined", "all_words", "size", "seconds", "platform", "item", "rank", "order")

    def __init__(self, raw: dict, order: int, seconds: Optional[float]):
        key = raw.get("path") or raw.get("id")
        self.raw = raw
        self.id = raw.get("id")
        self.title = community_catalog.clean_title(key, raw.get("title") or "")
        self.words = words(self.title)
        self.joined = joined(self.title)
        self.all_words = _all_words(self.title)
        self.size = int(raw["size_bytes"]) if raw.get("size_bytes") else None
        self.seconds = seconds
        self.platform = community_catalog.platform_of(raw)
        self.item = community_catalog._version_key(raw)   # equal for Plex/Jellyfin/Emby versions
        self.rank = community_catalog._folder_rank(raw)   # copies outside /Archives/ first
        self.order = order


class Matcher:
    """The index entries, ready to match local prerolls against.

    ``durations`` is {path or id: seconds}, as DurationStore.durations gives it.
    """

    def __init__(self, entries: Iterable[dict], durations: Optional[dict] = None):
        durations = durations or {}
        self._entries = []
        self._by_size: dict = {}
        self._by_word: dict = {}
        self._by_joined: dict = {}
        for order, raw in enumerate(entries or ()):
            if not raw.get("id"):
                continue
            entry = _Entry(raw, order, durations.get(raw.get("path") or raw.get("id")))
            self._entries.append(entry)
            if entry.size:
                self._by_size.setdefault(entry.size, []).append(entry)
            for word in set(entry.words):
                self._by_word.setdefault(word, []).append(entry)
            if entry.joined:
                self._by_joined.setdefault(entry.joined, []).append(entry)

    def __len__(self):
        return len(self._entries)

    def match(self, names: Iterable[Optional[str]], size: Optional[int] = None,
              seconds: Union[None, float, Callable[[], Optional[float]]] = None,
              platform: Optional[str] = None) -> dict:
        """The entry to link a local preroll to, if any, and suggestions.

        ``names``: its display name, file name (best of them counts).
        ``seconds``: its length, or a function that measures it; called at most
        once, and only when a title candidate has a length to compare.
        ``platform``: "plex" / "jellyfin" / "emby"; equal matches take its version.
        Returns {"entry", "id", "title", "how", "confidence", "suggestions"}
        with how = "file" | "title_length" | "title" | None.
        """
        names = [n for n in names if n]
        local = [(words(n), joined(n), _all_words(n)) for n in names]
        local = [l for l in local if l[0]]
        known = seconds if isinstance(seconds, (int, float)) and seconds > 0 else None
        measure = seconds if callable(seconds) else None

        def title_of(entry):
            return max((title_score(w, entry.words, j, entry.joined) for w, j, _ in local), default=0.0)

        def platform_bonus(entry):
            return 1 if platform and entry.platform == platform else 0

        def closeness(entry):
            # Ties go to the version the full name points at ("... 4K", "... Jellyfin").
            return max((_dice(a, entry.all_words) for _, _, a in local), default=0.0)

        # Same file: a renamed copy is found too.
        if size:
            copies = [e for e in self._by_size.get(int(size), ()) if lengths_agree(known, e.seconds) is not False]
            if copies:
                # Copies of one file: the one the Community page shows (outside /Archives/).
                best = min(copies, key=lambda e: (e.rank, -title_of(e), -platform_bonus(e), -closeness(e), e.order))
                return self._result(best, "file", 100, [])

        candidates = {}
        for local_words, local_joined, _ in local:
            for word in set(local_words):
                for entry in self._by_word.get(word, ()):
                    candidates[id(entry)] = entry
            for entry in self._by_joined.get(local_joined, ()):
                candidates[id(entry)] = entry
        scored = [(e, title_of(e)) for e in candidates.values()]
        scored = [(e, t) for e, t in scored if t >= SUGGEST_TITLE]

        if known is None and measure and any(e.seconds for e, _ in scored):
            try:
                value = measure()
            except Exception:
                value = None
            known = value if isinstance(value, (int, float)) and value > 0 else None

        rows = []
        for entry, title in scored:
            agree = lengths_agree(known, entry.seconds)
            if agree is True:
                confidence = round(100 * (0.6 + 0.4 * title)) if title >= LINK_TITLE else round(100 * (0.2 + 0.6 * title))
                reason = "title and length" if title >= LINK_TITLE else "similar title, same length"
            elif agree is None:
                confidence = round((90 if self._specific(entry.words) else 60) * title)
                reason = "title, length unknown"
            elif title >= LINK_TITLE:
                confidence = min(39, round(40 * title))
                reason = "title, different length"
            else:
                continue
            gap = abs(known - entry.seconds) if agree is not None else float("inf")
            rows.append((entry, title, agree, confidence, reason, gap))
        # Equal matches: the user's platform, then a copy outside /Archives/,
        # then the version the full name points at, then the closest length.
        rows.sort(key=lambda r: (-r[3], -platform_bonus(r[0]), r[0].rank, -closeness(r[0]), r[5], r[0].order))

        linked = next((r for r in rows if r[2] is True and r[1] >= LINK_TITLE), None)
        if linked:
            return self._result(linked[0], "title_length", linked[3], [])
        # No length to check: only a title specific enough to name one preroll.
        exact = [r for r in rows if r[1] == 1.0 and r[2] is None and self._specific(r[0].words)]
        if exact and not any(r[2] is True for r in rows) and self._one_preroll([r[0] for r in exact]):
            return self._result(exact[0][0], "title", exact[0][3], [])

        suggestions, seen_sizes = [], set()
        for entry, title, agree, confidence, reason, _ in rows:
            if entry.size and entry.size in seen_sizes:
                continue  # a copy of a file already listed
            if entry.size:
                seen_sizes.add(entry.size)
            suggestions.append({
                "id": entry.id,
                "title": entry.title,
                "confidence": confidence,
                "score": confidence / 100,
                "reason": reason,
                "video_url": entry.raw.get("url"),
                "seconds": entry.seconds,
                "local_seconds": known,
            })
            if len(suggestions) >= MAX_SUGGESTIONS:
                break
        return {"entry": None, "id": None, "title": None, "how": None, "confidence": 0, "suggestions": suggestions}

    @staticmethod
    def _specific(title_words: tuple) -> bool:
        """Two words or more, or one of six letters or more: "Grinchmas", not "HBO"."""
        return len(title_words) >= 2 or len("".join(title_words)) >= 6

    @staticmethod
    def _one_preroll(entries: list) -> bool:
        """True when the entries are versions (same path but for the platform)
        or copies (same size) of one preroll."""
        items, sizes = {entries[0].item}, {entries[0].size}
        rest = entries[1:]
        grew = True
        while rest and grew:
            grew = False
            for entry in list(rest):
                if entry.item in items or (entry.size and entry.size in sizes):
                    items.add(entry.item)
                    sizes.add(entry.size)
                    rest.remove(entry)
                    grew = True
        return not rest

    @staticmethod
    def _result(entry: _Entry, how: str, confidence: int, suggestions: list) -> dict:
        return {"entry": entry.raw, "id": entry.id, "title": entry.title, "how": how,
                "confidence": confidence, "suggestions": suggestions}


def local_platform(*names: Optional[str]) -> Optional[str]:
    """The platform a local file is made for, from its names or path."""
    for name in names:
        if name:
            found = community_catalog.platform_of({"path": str(name).replace("\\", "/")})
            if found and found != "universal":
                return found
    return None
