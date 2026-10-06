"""Thread-safe shuffle bags for no-repeat random rotation.

State lives in memory. When ``configure_persistence`` has been given a file
(main does this at startup), it is also saved there after every pick and
loaded back on start, so a restart does not begin every rotation over.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import threading
import time
from typing import Callable, Hashable, Iterable, TypeVar


T = TypeVar("T")


@dataclass
class _BagState:
    pool_signature: tuple[Hashable, ...]
    remaining: list[Hashable]
    last_selected: tuple[Hashable, ...]
    touched_at: float


_LOCK = threading.RLock()
_BAGS: dict[Hashable, _BagState] = {}
_MAX_BAGS = 256


def _default_item_key(item: T) -> Hashable:
    """Return an identity stable across fresh SQLAlchemy instances."""
    item_id = getattr(item, "id", None)
    if item_id is not None:
        item_type = type(item)
        return (item_type.__module__, item_type.__qualname__, item_id)
    try:
        hash(item)
    except TypeError:
        return id(item)
    return item  # type: ignore[return-value]


def _new_cycle(
    pool_signature: tuple[Hashable, ...],
    last_selected: tuple[Hashable, ...],
) -> list[Hashable]:
    """Shuffle a cycle while putting the most recent selection at the end."""
    recent = set(last_selected)
    fresh = [item_key for item_key in pool_signature if item_key not in recent]
    repeated = [item_key for item_key in pool_signature if item_key in recent]
    random.shuffle(fresh)
    random.shuffle(repeated)
    # Items are popped from the end, so recently selected entries go first in
    # storage and are consumed last whenever the pool is large enough.
    return repeated + fresh


def _prune_old_bags() -> None:
    overflow = len(_BAGS) - _MAX_BAGS
    if overflow <= 0:
        return
    oldest = sorted(_BAGS.items(), key=lambda pair: pair[1].touched_at)[:overflow]
    for bag_key, _state in oldest:
        _BAGS.pop(bag_key, None)


def shuffle_bag_sample(
    bag_key: Hashable,
    items: Iterable[T],
    count: int,
    *,
    item_key: Callable[[T], Hashable] | None = None,
) -> list[T]:
    """Select ``count`` items without repeating until the pool is exhausted.

    State is scoped by ``bag_key``. When the eligible pool changes, the cycle
    carries on: removed items drop out, new ones join what is left of it, and
    whatever just played still waits for the next cycle. Starting over instead
    could replay the last pick straight away whenever a preroll was added,
    removed or disabled.
    """
    candidates = list(items)
    if not candidates or count <= 0:
        return []

    identify = item_key or _default_item_key
    candidates_by_key: dict[Hashable, T] = {}
    for item in candidates:
        candidates_by_key.setdefault(identify(item), item)

    selected_count = min(int(count), len(candidates_by_key))
    if selected_count <= 0:
        return []

    pool_signature = tuple(sorted(candidates_by_key, key=repr))
    now = time.monotonic()

    with _LOCK:
        state = _BAGS.get(bag_key)
        if state is None:
            state = _BagState(
                pool_signature=pool_signature,
                remaining=_new_cycle(pool_signature, ()),
                last_selected=(),
                touched_at=now,
            )
            _BAGS[bag_key] = state
            _prune_old_bags()
        elif state.pool_signature != pool_signature:
            state = _BAGS[bag_key] = _carried_over(state, pool_signature, now)

        selected_keys: list[Hashable] = []
        deferred_keys: list[Hashable] = []
        while len(selected_keys) < selected_count:
            if not state.remaining:
                state.remaining = _new_cycle(pool_signature, state.last_selected)

            candidate_key = state.remaining.pop()
            if candidate_key in selected_keys:
                # A call can cross a cycle boundary. Do not return the same item
                # twice in one selection, and leave it available for the next call.
                deferred_keys.append(candidate_key)
                continue
            selected_keys.append(candidate_key)

        if deferred_keys:
            state.remaining = deferred_keys + state.remaining
        state.last_selected = tuple(selected_keys)
        state.touched_at = now

    _save()
    return [candidates_by_key[selected_key] for selected_key in selected_keys]


def _carried_over(state: _BagState, pool_signature: tuple, now: float) -> _BagState:
    """The bag's cycle, continued over a changed pool."""
    eligible = set(pool_signature)
    known = set(state.pool_signature)
    unplayed = [k for k in state.remaining if k in eligible]
    unplayed += [k for k in pool_signature if k not in known]
    random.shuffle(unplayed)
    return _BagState(
        pool_signature=pool_signature,
        remaining=unplayed,
        last_selected=tuple(k for k in state.last_selected if k in eligible),
        touched_at=now,
    )


# --- Persistence -----------------------------------------------------------
# Keys are tuples of strings and numbers (bag scopes, ("backend.models",
# "Preroll", 12) item identities, or file paths). JSON has no tuples, so they
# are written as {"t": [...]}; a bag whose keys can't be written is skipped.

_PERSIST_PATH: str | None = None
_SAVE_LOCK = threading.Lock()


def _encode(value):
    if isinstance(value, tuple):
        return {"t": [_encode(v) for v in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"not persistable: {type(value).__name__}")


def _decode(value):
    if isinstance(value, dict):
        return tuple(_decode(v) for v in value["t"])
    if isinstance(value, list):
        return tuple(_decode(v) for v in value)
    return value


def _snapshot() -> list:
    rows = []
    for bag_key, state in _BAGS.items():
        try:
            rows.append({
                "key": _encode(bag_key),
                "pool": [_encode(k) for k in state.pool_signature],
                "remaining": [_encode(k) for k in state.remaining],
                "last": [_encode(k) for k in state.last_selected],
            })
        except TypeError:
            continue
    return rows


def _save() -> None:
    path = _PERSIST_PATH
    if not path:
        return
    with _LOCK:
        rows = _snapshot()
    try:
        with _SAVE_LOCK:
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "bags": rows}, handle)
            os.replace(tmp, path)
    except OSError:
        # Rotation still works in memory; it just won't survive a restart.
        pass


def configure_persistence(path: str | None) -> None:
    """Save rotation state to ``path`` and load what is already there.

    Called once at startup. A missing, unreadable or foreign file starts
    empty; rotation is a convenience, never a reason to fail startup.
    """
    global _PERSIST_PATH
    _PERSIST_PATH = path
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        rows = data.get("bags") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return
    now = time.monotonic()
    with _LOCK:
        for row in rows or []:
            try:
                pool = tuple(_decode(k) for k in row["pool"])
                eligible = set(pool)
                _BAGS[_decode(row["key"])] = _BagState(
                    pool_signature=pool,
                    remaining=[k for k in (_decode(x) for x in row["remaining"]) if k in eligible],
                    last_selected=tuple(k for k in (_decode(x) for x in row["last"]) if k in eligible),
                    touched_at=now,
                )
            except (KeyError, TypeError, ValueError):
                continue
        _prune_old_bags()


def clear_shuffle_bags() -> None:
    """Clear rotation state. Exposed for focused tests and controlled resets."""
    with _LOCK:
        _BAGS.clear()
