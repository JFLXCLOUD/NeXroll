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

Else if chains (first match wins). A block may set ``"else_if": true`` to
join the block above it in a chain:

    [{"type": "random", "category_id": 1, "condition": {genre Horror}},
     {"type": "random", "category_id": 2, "condition": {genre Sci-Fi}, "else_if": true},
     {"type": "random", "category_id": 3, "else_if": true}]

Only the first block in a chain whose condition holds plays; a member without
a condition always holds, so it is the chain's ELSE. A member that does not
hold plays nothing while the chain goes on, so only the last member's
``otherwise`` can play, and only when no member held. Releases before 2.2.2
ignore the flag and check every block on its own.

A rule NeXroll cannot answer counts as not met. That matters for the rules
that depend on what is about to play (genre, tag, file path, media type, stored audio): Jellyfin and Emby
say, Plex cannot, so on Plex such a block plays its ``otherwise`` rather than
playing before every movie.

This module only decides; it never touches the database or the filesystem.
Anything it needs to know about the outside world arrives on the
PlaybackContext, so the same rules are applied identically on the Plex push,
the Jellyfin/Emby plugin pull and the previews.

Rule kinds:
  trailers_available  pool: upcoming (legacy default)|library|block; source: movies|tv|both;
                      min: int (default 1), ratings/restrict_ratings, library genres.
                      block follows this/next trailer block, including its filters/count.
  media_type          value: movie|episode
  time_window         start/end: "HH:MM" (end may be past midnight),
                      days: optional list of weekday names the window opens on
  genre               values: list of genre names; met when the item has any
                      of them (Jellyfin/Emby only)
  tag                 values: list of tag names; met when the item (or an
                      episode's series) has any of them (Jellyfin/Emby only)
  file_name           values: list of text snippets; met when the item's file
                      path contains any of them, e.g. "IMAX" (Jellyfin/Emby only)
  audio_format        values: supported stored codecs; track: default|any.
                      Unknown metadata stays unknown even when negated.
Any rule may set ``"negate": true`` to mean "not".
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

RULE_KINDS = ("trailers_available", "media_type", "time_window", "genre", "tag", "file_name", "audio_format", "server")

# The media servers a "server" rule can name. Plex is known from its apply
# paths, Jellyfin and Emby from the X-Plugin-Server-Type header their plugins send.
SERVER_TYPES = ("plex", "jellyfin", "emby")


def normalize_server(value) -> Optional[str]:
    """"plex", "jellyfin" or "emby", or None when unknown."""
    name = str(value or "").strip().lower()
    return name if name in SERVER_TYPES else None

# Rules that need to know what is about to play. Only the Jellyfin/Emby plugin
# can tell NeXroll that; Plex applies one list to every movie.
PLAYBACK_RULES = ("media_type", "genre", "tag", "file_name", "audio_format")

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
    # Which media server is asking: "plex", "jellyfin", "emby", or None.
    server: Optional[str] = None
    trailer_count: Optional[Callable[[str], int]] = None
    trailer_pool_count: Optional[Callable[[dict], Optional[int]]] = None
    availability_block: Optional[dict] = None
    condition_block: Optional[dict] = None
    genre_lookup: Optional[Callable[[], Optional[list]]] = None
    tag_lookup: Optional[Callable[[], Optional[list]]] = None
    path_lookup: Optional[Callable[[], Optional[str]]] = None
    tmdb_lookup: Optional[Callable[[], Optional[str]]] = None
    audio_lookup: Optional[Callable[[], Optional[dict]]] = None
    # Where the block being checked, and its this/next trailer block, sit in
    # their sequence, so an availability rule can follow an Else if chain.
    sequence_blocks: Optional[list] = field(default=None, repr=False)
    condition_index: Optional[int] = field(default=None, repr=False)
    availability_index: Optional[int] = field(default=None, repr=False)
    # Shared by every copy made with replace(), like _trailer_cache, so each
    # chain is decided once per resolution pass.
    _chain_cache: dict = field(default_factory=dict, repr=False)
    _audio: Optional[dict] = field(default=None, repr=False)
    _audio_known: bool = field(default=False, repr=False)
    _trailer_cache: dict = field(default_factory=dict, repr=False)
    _genres: Optional[list] = field(default=None, repr=False)
    _genres_known: bool = field(default=False, repr=False)
    _tags: Optional[list] = field(default=None, repr=False)
    _tags_known: bool = field(default=False, repr=False)
    _path: Optional[str] = field(default=None, repr=False)
    _path_known: bool = field(default=False, repr=False)

    def audio(self) -> Optional[dict]:
        if not self._audio_known:
            self._audio_known = True
            try:
                self._audio = self.audio_lookup() if self.audio_lookup else None
            except Exception:
                self._audio = None
        return self._audio

    def genres(self) -> Optional[list]:
        """Lower-cased genres of what is about to play, or None if unknown.
        Looked up at most once, and only if a genre rule asks."""
        if not self._genres_known:
            self._genres_known = True
            found = self.genre_lookup() if self.genre_lookup else None
            self._genres = None if found is None else [str(g).strip().lower() for g in found if str(g).strip()]
        return self._genres

    def tags(self) -> Optional[list]:
        """Lower-cased tags of what is about to play, or None if unknown."""
        if not self._tags_known:
            self._tags_known = True
            try:
                found = self.tag_lookup() if self.tag_lookup else None
            except Exception:
                found = None
            self._tags = None if found is None else [str(t).strip().lower() for t in found if str(t).strip()]
        return self._tags

    def file_path(self) -> Optional[str]:
        """Lower-cased file path of what is about to play, with forward
        slashes, or None if unknown."""
        if not self._path_known:
            self._path_known = True
            try:
                found = self.path_lookup() if self.path_lookup else None
            except Exception:
                found = None
            self._path = str(found).replace("\\", "/").lower() if found else None
        return self._path

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
        if rule.get("pool") == "block":
            target = ctx.availability_block
            if target is not None and target is not ctx.condition_block:
                target = _availability_choice(target, ctx)
            if not target or target.get("type") not in ("nexup_trailers", "library_trailers"):
                count = 0
            elif ctx.trailer_pool_count is None:
                count = None
            else:
                criteria = {**target, "pool": "library" if target["type"] == "library_trailers" else "upcoming"}
                count = ctx.trailer_pool_count(criteria)
                try:
                    limit = max(1, int(target.get("count") or 2))
                except (ValueError, TypeError):
                    limit = 2
                count = min(count, limit) if count is not None else None
        elif ctx.trailer_pool_count is not None:
            count = ctx.trailer_pool_count(rule)
        elif rule.get("pool", "upcoming") == "upcoming" and not rule.get("restrict_ratings") and not rule.get("ratings") and not rule.get("genres") and not rule.get("match_playing"):
            count = ctx.trailers(source)
        else:
            count = None
        result = None if count is None else count >= minimum
    elif kind == "media_type":
        wanted = str(rule.get("value", "")).lower()
        if wanted not in ("movie", "episode") or not ctx.media_type:
            result = None
        else:
            result = ctx.media_type.lower() == wanted
    elif kind == "time_window":
        result = _in_time_window(rule, ctx.now)
    elif kind == "audio_format":
        from backend.media_audio import matches_audio
        result = matches_audio(ctx.audio(), rule.get('values'), rule.get('track', 'default'))
    elif kind == "genre":
        wanted = {str(v).strip().lower() for v in (rule.get("values") or []) if str(v).strip()}
        have = ctx.genres() if wanted else None
        result = None if have is None else bool(wanted.intersection(have))
    elif kind == "tag":
        wanted = {str(v).strip().lower() for v in (rule.get("values") or []) if str(v).strip()}
        have = ctx.tags() if wanted else None
        result = None if have is None else bool(wanted.intersection(have))
    elif kind == "file_name":
        # Plain text, not a pattern: "IMAX" matches "Dune (2021) - IMAX.mkv"
        # and a folder named "IMAX". Slashes are compared as forward slashes.
        wanted = [str(v).strip().replace("\\", "/").lower() for v in (rule.get("values") or []) if str(v).strip()]
        have = ctx.file_path() if wanted else None
        result = None if have is None else any(w in have for w in wanted)
    elif kind == "server":
        # An unknown server (a plugin too old to say) is not met either way,
        # so it falls to the Otherwise along with whatever it was not chosen for.
        wanted = {normalize_server(v) for v in (rule.get("values") or [])} - {None}
        result = None if not wanted or not ctx.server else ctx.server in wanted
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
            source = rule.get('source', 'both')
            if rule.get('pool') == 'library':
                source = 'library'
            elif rule.get('pool') == 'block':
                source = 'matching this/next block'
            text = f"at least {rule.get('min', 1)} {source} trailer(s) available"
            if rule.get("ratings"):
                text += " rated " + ", ".join(str(r) for r in rule["ratings"])
            if rule.get("genres"):
                text += " in " + ", ".join(str(g) for g in rule["genres"])
        elif kind == "media_type":
            text = f"playing a {rule.get('value', '?')}"
        elif kind == "time_window":
            text = f"between {rule.get('start', '?')} and {rule.get('end', '?')}"
            if rule.get("days"):
                text += " on " + ", ".join(str(d) for d in rule["days"])
        elif kind == "audio_format":
            from backend.media_audio import LABELS
            values = rule.get('values') if isinstance(rule.get('values'), list) else []
            text = ('any stored audio track' if rule.get('track') == 'any' else 'stored default audio track') + ' is ' + ' or '.join(LABELS.get(str(v), str(v)) for v in values)
        elif kind == "genre":
            values = [str(v) for v in (rule.get("values") or [])]
            text = ("genre is " + " or ".join(values)) if values else "genre is (none chosen)"
        elif kind == "tag":
            values = [str(v) for v in (rule.get("values") or [])]
            text = ("tag is " + " or ".join(values)) if values else "tag is (none chosen)"
        elif kind == "file_name":
            values = [f'"{v}"' for v in (rule.get("values") or [])]
            text = ("file path contains " + " or ".join(values)) if values else "file path contains (nothing chosen)"
        elif kind == "server":
            names = {"plex": "Plex", "jellyfin": "Jellyfin", "emby": "Emby"}
            values = [names.get(normalize_server(v) or "", str(v)) for v in (rule.get("values") or [])]
            text = ("playing on " + " or ".join(values)) if values else "playing on (no server chosen)"
        else:
            text = f"unknown rule '{kind}'"
        parts.append(("not " + text) if rule.get("negate") else text)
    if not parts:
        return "always"
    joiner = " or " if str(condition.get("match", "all")).lower() == "any" else " and "
    return joiner.join(parts)


def is_else_if(block) -> bool:
    """True when a block joins the Else if chain of the block above it."""
    return isinstance(block, dict) and block.get("else_if") is True


def chain_bounds(blocks, index) -> tuple:
    """First and last index of the Else if chain holding ``blocks[index]``.

    A block outside any chain is a chain of one: (index, index). The first
    block of a sequence starts a chain even if it is marked Else if, since
    there is nothing above it to follow.
    """
    start = index
    while start > 0 and is_else_if(blocks[start]):
        start -= 1
    end = index
    while end + 1 < len(blocks) and is_else_if(blocks[end + 1]):
        end += 1
    return start, end


def in_chain(blocks, index) -> bool:
    """True when ``blocks[index]`` belongs to an Else if chain of two or more."""
    start, end = chain_bounds(blocks, index)
    return start != end


def _bound_context(blocks, index, context):
    """The context for checking one block's condition where it sits.

    Availability binds to this/next trailer block by relative position, which
    survives save/export/reorder without a stale numeric ID.
    """
    target_index = next((j for j in range(index, len(blocks)) if isinstance(blocks[j], dict)
                         and blocks[j].get("type") in ("nexup_trailers", "library_trailers")), None)
    return replace(context,
                   availability_block=blocks[target_index] if target_index is not None else None,
                   availability_index=target_index,
                   condition_block=blocks[index],
                   condition_index=index,
                   sequence_blocks=blocks)


def _holds(blocks, index, context) -> bool:
    block = blocks[index]
    return "condition" not in block or condition_holds(block.get("condition"), _bound_context(blocks, index, context))


def _otherwise_of(block) -> Optional[dict]:
    otherwise = block.get("otherwise")
    if isinstance(otherwise, dict) and str(otherwise.get("type", "")).lower() in OTHERWISE_TYPES:
        return otherwise
    return None


def chain_choice(blocks, index, context) -> tuple:
    """(index, block) that plays for the chain holding ``blocks[index]``.

    The first member whose condition holds plays. When none does, the last
    member's ``otherwise`` plays at that member's slot, or nothing does:
    (None, None). Decided once per chain and context.
    """
    start, end = chain_bounds(blocks, index)
    # The cache keeps the list itself, so its id cannot be reused by another
    # sequence resolved with the same context.
    key = (id(blocks), start)
    cached = context._chain_cache.get(key)
    if cached is not None and cached[0] is blocks:
        return cached[1]
    # Mark the chain as undecided while it is checked. A member whose
    # availability rule follows a trailer block in this same chain does not
    # come back here (see _availability_choice), so this only guards against
    # recursion in a malformed sequence.
    context._chain_cache[key] = (blocks, (None, None))
    result = (None, None)
    for k in range(start, end + 1):
        block = blocks[k]
        if not isinstance(block, dict):
            continue
        if _holds(blocks, k, context):
            result = (k, block)
            break
        if k == end:
            otherwise = _otherwise_of(block)
            if otherwise is not None:
                result = (k, otherwise)
    context._chain_cache[key] = (blocks, result)
    return result


def _availability_choice(target, ctx):
    """What actually plays for a this/next trailer block target.

    When the target sits in an Else if chain, the chain decides: the trailer
    block that wins it (or its final Otherwise), whichever member that is. A
    condition inside that same chain checks the target on its own, as before,
    since the chain's answer would depend on that very condition.
    """
    blocks, j = ctx.sequence_blocks, ctx.availability_index
    if blocks is not None and j is not None and j < len(blocks) and blocks[j] is target:
        start, end = chain_bounds(blocks, j)
        i = ctx.condition_index
        if start != end and not (i is not None and start <= i <= end):
            return chain_choice(blocks, j, ctx)[1]
    return block_to_play(target, replace(ctx, condition_block=target))


def sequence_block_to_play(blocks, index, context):
    """The block that plays in ``blocks[index]``'s slot, or None.

    Like block_to_play, with the block's place in the sequence taken into
    account: availability rules bind to this/next trailer block, and a block
    in an Else if chain plays only if it is the chain's first match (or, as
    the chain's last member, its Otherwise when nothing matched).
    Counting never samples trailers or consumes their shuffle rotation.
    """
    if not in_chain(blocks, index):
        return block_to_play(blocks[index], _bound_context(blocks, index, context))
    chosen_index, chosen = chain_choice(blocks, index, context)
    return chosen if chosen_index == index else None


def needs_evaluation(blocks, index) -> bool:
    """True when what plays in this slot depends on a condition: its own, or
    another member's in its Else if chain."""
    block = blocks[index]
    return isinstance(block, dict) and (isinstance(block.get("condition"), dict) or in_chain(blocks, index))


def skip_reason(blocks, index, context) -> str:
    """Why ``blocks[index]`` plays nothing, in words, for logs and previews."""
    block = blocks[index]
    summary = describe_condition(block.get("condition")) if isinstance(block, dict) else "always"
    if in_chain(blocks, index):
        chosen_index, _ = chain_choice(blocks, index, context)
        if chosen_index is not None and chosen_index < index:
            return f"block {chosen_index + 1} in its Else if chain already played"
        if chosen_index is not None and chosen_index > index:
            return f"condition not met ({summary}); block {chosen_index + 1} in its Else if chain played"
    return f"condition not met ({summary})"
