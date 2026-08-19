"""Thread-safe, process-local shuffle bags for no-repeat random rotation."""

from __future__ import annotations

from dataclasses import dataclass
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

    State is scoped by ``bag_key`` and reset automatically when the eligible
    pool changes. It intentionally lives only for the process lifetime: this is
    playback rotation state, not user data that needs a schema migration.
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
        if state is None or state.pool_signature != pool_signature:
            state = _BagState(
                pool_signature=pool_signature,
                remaining=_new_cycle(pool_signature, ()),
                last_selected=(),
                touched_at=now,
            )
            _BAGS[bag_key] = state
            _prune_old_bags()

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

    return [candidates_by_key[selected_key] for selected_key in selected_keys]


def clear_shuffle_bags() -> None:
    """Clear rotation state. Exposed for focused tests and controlled resets."""
    with _LOCK:
        _BAGS.clear()
