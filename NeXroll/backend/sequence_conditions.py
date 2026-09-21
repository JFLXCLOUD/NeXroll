"""Conditions on sequence blocks - the Sequence Builder's Advanced mode.

A block may carry an optional ``condition`` and an optional ``otherwise`` block:

    {
        "type": "coming_soon_list", "layout": "grid",
        "condition": {
            "match": "all",                       # or "any"
            "rules": [
                {"kind": "trailers_available", "source": "both", "min": 1},
            ],
        },
        "otherwise": {"type": "random", "category_id": 4, "count": 1},
    }

When the condition holds the block plays as normal. When it does not, the
``otherwise`` block plays in its place, or nothing does if there is none. A
block without a condition always plays, so every sequence written before this
existed behaves exactly as it did.

A rule NeXroll cannot answer counts as not met. That matters for the rules
that depend on what is about to play (genre, media type): Jellyfin and Emby
say, Plex cannot, so on Plex such a block plays its ``otherwise`` rather than
playing before every movie.

This module only decides; it never touches the database or the filesystem.
Anything it needs to know about the outside world arrives on the
PlaybackContext, so the same rules are applied identically on the Plex push,
the Jellyfin/Emby plugin pull and the previews.

Rule kinds:
  trailers_available  source: movies|tv|both, min: int (default 1)
  media_type          value: movie|episode
  time_window         start/end: "HH:MM" (end may be past midnight),
                      days: optional list of weekday names the window opens on
  genre               values: list of genre names; met when the item has any
                      of them (Jellyfin/Emby only)
Any rule may set ``"negate": true`` to mean "not".
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional

RULE_KINDS = ("trailers_available", "media_type", "time_window", "genre")

# Rules that need to know what is about to play. Only the Jellyfin/Emby plugin
# can tell NeXroll that; Plex applies one list to every movie.
PLAYBACK_RULES = ("media_type", "genre")

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# The kinds of block an ``otherwise`` may be. Another conditional block, or a
# pause, would make the fallback harder to reason about than the block itself.
OTHERWISE_TYPES = ("random", "sequential", "fixed", "nexup_trailers", "library_trailers", "coming_soon_list", "dynamic_preroll")


@dataclass
class PlaybackContext:
    """What a condition may ask about the moment of playback.

    ``now`` is the server-local time the schedule clock uses. ``media_type`` is
    what is about to play, lower-cased ("movie", "episode"), or None when the
    caller cannot know. ``trailer_count`` answers "how many NeX-Up trailers from
    this source would actually play" using the same eligibility as the trailer
    block itself, so a condition can never disagree with the block it guards.
    """

    now: datetime.datetime
    media_type: Optional[str] = None
    trailer_count: Optional[Callable[[str], int]] = None
    genre_lookup: Optional[Callable[[], Optional[list]]] = None
    tmdb_lookup: Optional[Callable[[], Optional[str]]] = None
    _trailer_cache: dict = field(default_factory=dict, repr=False)
    _genres: Optional[list] = field(default=None, repr=False)
    _genres_known: bool = field(default=False, repr=False)

    def genres(self) -> Optional[list]:
        """Lower-cased genres of what is about to play, or None if unknown.
        Looked up at most once, and only if a genre rule asks."""
        if not self._genres_known:
            self._genres_known = True
            found = self.genre_lookup() if self.genre_lookup else None
            self._genres = None if found is None else [str(g).strip().lower() for g in found if str(g).strip()]
        return self._genres

    def tmdb_id(self) -> Optional[str]:
        """TMDB id of what is about to play, when the server reports one."""
        try:
            value = self.tmdb_lookup() if self.tmdb_lookup else None
        except Exception:
            value = None
        return str(value) if value else None

    def trailers(self, source: str) -> Optional[int]:
        if self.trailer_count is None:
            return None
        if source not in self._trailer_cache:
            self._trailer_cache[source] = self.trailer_count(source)
        return self._trailer_cache[source]


def _parse_hhmm(value) -> Optional[datetime.time]:
    try:
        hours, minutes = str(value).strip().split(":", 1)
        return datetime.time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return None


def _in_time_window(rule: dict, now: datetime.datetime) -> Optional[bool]:
    start = _parse_hhmm(rule.get("start"))
    end = _parse_hhmm(rule.get("end"))
    if start is None or end is None:
        return None
    days = [str(d).strip().lower() for d in (rule.get("days") or []) if str(d).strip()]
    t = now.time().replace(second=0, microsecond=0)

    if start <= end:
        inside = start <= t < end
        opened_on = now
    elif t >= start:
        # Overnight window, evening side: it opened today.
        inside = True
        opened_on = now
    elif t < end:
        # Overnight window, morning side: it opened yesterday. "Friday 22:00-03:00"
        # therefore still holds at 01:00 on Saturday, matching how schedules read.
        inside = True
        opened_on = now - datetime.timedelta(days=1)
    else:
        inside = False
        opened_on = now

    if not inside:
        return False
    if days:
        return _WEEKDAYS[opened_on.weekday()] in days
    return True


def evaluate_rule(rule: dict, ctx: PlaybackContext) -> Optional[bool]:
    """True/False for a rule, or None when it cannot be answered here."""
    if not isinstance(rule, dict):
        return None
    kind = str(rule.get("kind", "")).lower()
    result: Optional[bool]

    if kind == "trailers_available":
        source = str(rule.get("source", "both")).lower()
        if source not in ("movies", "tv", "both"):
            source = "both"
        try:
            minimum = max(int(rule.get("min", 1)), 1)
        except (TypeError, ValueError):
            minimum = 1
        count = ctx.trailers(source)
        result = None if count is None else count >= minimum
    elif kind == "media_type":
        wanted = str(rule.get("value", "")).lower()
        if wanted not in ("movie", "episode") or not ctx.media_type:
            result = None
        else:
            result = ctx.media_type.lower() == wanted
    elif kind == "time_window":
        result = _in_time_window(rule, ctx.now)
    elif kind == "genre":
        wanted = {str(v).strip().lower() for v in (rule.get("values") or []) if str(v).strip()}
        have = ctx.genres() if wanted else None
        result = None if have is None else bool(wanted.intersection(have))
    else:
        result = None

    if result is None:
        return None
    return (not result) if rule.get("negate") else result


def condition_holds(condition, ctx: PlaybackContext) -> bool:
    """Whether a block's condition lets it play.

    A rule that cannot be answered counts as not met, "unless" rules included:
    NeXroll only plays a conditional block when it knows the condition holds.
    Otherwise "genre is Horror" would play before every Plex movie, because
    Plex never says what is playing.
    """
    if not isinstance(condition, dict):
        return True
    rules = condition.get("rules")
    if not isinstance(rules, list) or not rules:
        return True
    answers = [evaluate_rule(r, ctx) is True for r in rules]
    if str(condition.get("match", "all")).lower() == "any":
        return any(answers)
    return all(answers)


def needs_playback_info(condition) -> bool:
    """True when a condition has a rule only the Jellyfin/Emby plugin can answer."""
    if not isinstance(condition, dict):
        return False
    return any(isinstance(r, dict) and str(r.get("kind", "")).lower() in PLAYBACK_RULES
               for r in (condition.get("rules") or []))


def block_to_play(block, ctx: PlaybackContext) -> Optional[dict]:
    """The block that should actually play in this block's slot, or None.

    Returns the block itself when it is unconditional or its condition holds,
    the ``otherwise`` block when it does not, and None when there is nothing
    to play in its place.
    """
    if not isinstance(block, dict):
        return None
    if "condition" not in block or condition_holds(block.get("condition"), ctx):
        return block
    otherwise = block.get("otherwise")
    if isinstance(otherwise, dict) and str(otherwise.get("type", "")).lower() in OTHERWISE_TYPES:
        return otherwise
    return None


def has_conditions(blocks) -> bool:
    """True when any block in a sequence is conditional.

    The scheduler uses this to keep re-applying such a sequence to Plex, which
    takes a fixed list, so a time window or a trailer count is re-checked
    rather than frozen at the moment the schedule started.
    """
    if not isinstance(blocks, list):
        return False
    return any(isinstance(b, dict) and isinstance(b.get("condition"), dict) for b in blocks)


def describe_condition(condition) -> str:
    """One-line English summary of a condition, for logs."""
    if not isinstance(condition, dict):
        return "always"
    parts = []
    for rule in condition.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        kind = str(rule.get("kind", "")).lower()
        if kind == "trailers_available":
            text = f"at least {rule.get('min', 1)} {rule.get('source', 'both')} trailer(s) available"
        elif kind == "media_type":
            text = f"playing a {rule.get('value', '?')}"
        elif kind == "time_window":
            text = f"between {rule.get('start', '?')} and {rule.get('end', '?')}"
            if rule.get("days"):
                text += " on " + ", ".join(str(d) for d in rule["days"])
        elif kind == "genre":
            values = [str(v) for v in (rule.get("values") or [])]
            text = ("genre is " + " or ".join(values)) if values else "genre is (none chosen)"
        else:
            text = f"unknown rule '{kind}'"
        parts.append(("not " + text) if rule.get("negate") else text)
    if not parts:
        return "always"
    joiner = " or " if str(condition.get("match", "all")).lower() == "any" else " and "
    return joiner.join(parts)
