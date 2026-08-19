"""Dashboard layout schema and migration.

The stored layout lives in `settings.dashboard_layout` as JSON. Version 1 tracked
only tile order, hidden tiles, and a lock flag. Version 2 adds the Focus Enhanced
controls: per-tile width and detail level, plus page-level preferences.

Kept out of main.py so the migration can be tested directly - getting it wrong
silently resets a user's customized dashboard, which is the kind of bug nobody
reports and everybody notices.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

SCHEMA_VERSION = 2

# Tile widths keep the grid's established sm/md/lg storage vocabulary. The Focus
# renderer maps those stable values to third, two-thirds, and full-width spans;
# `detail` remains the per-tile compact/detailed control.
SIZES = ("sm", "md", "lg")
DETAILS = ("compact", "detailed")
DENSITIES = ("compact", "comfortable")

# Tiles introduced by the Focus Enhanced dashboard. Existing installs get these
# at the top of their layout so the new dashboard is what they actually see,
# while everything they already arranged keeps its relative order underneath.
NEW_IN_V2 = ("now_showing", "whats_next", "system_health", "storage_mix", "quick_actions")

# Every tile the dashboard knows about, in default display order.
#
# Retired in 2.1 and deliberately absent: "storage" (a second rendering of the
# same breakdown "storage_mix" shows), "current_category" (the active-schedule
# half of "now_showing"), and "upcoming" (a second upcoming list whose filter
# disagreed with "whats_next"). Because _clean_key_list keeps only known keys,
# a stored layout naming any of them simply drops it on the next load.
TILE_KEYS = (
    "now_showing",
    "system_health",
    "prerolls",
    "quick_actions",
    "storage_mix",
    "whats_next",
    "schedules",
    "servers",
    "scheduler",
    "resolution_chart",
    "nexup",
    "community",
    "weekly_calendar",
)

# Per-tile defaults. Anything unlisted falls back to a small, detailed tile.
TILE_DEFAULTS = {
    "now_showing": {"size": "md", "detail": "detailed"},
    "whats_next": {"size": "md", "detail": "detailed"},
    "system_health": {"size": "sm", "detail": "detailed"},
    "storage_mix": {"size": "sm", "detail": "detailed"},
    "quick_actions": {"size": "sm", "detail": "detailed"},
    "resolution_chart": {"size": "md", "detail": "detailed"},
    "weekly_calendar": {"size": "lg", "detail": "detailed"},
}

DEFAULT_PREFERENCES = {
    "greeting": True,
    "healthNote": True,
    "dateTime": True,
    "density": "comfortable",
}

# Preset visible-tile sets. "everything" is derived from TILE_KEYS at call time
# so a newly added tile never has to be registered in two places.
PRESETS = {
    "essential": (
        "now_showing", "system_health", "prerolls", "quick_actions", "storage_mix",
    ),
    "operations": (
        "now_showing", "whats_next", "system_health",
        "prerolls", "schedules", "servers", "storage_mix",
        "quick_actions", "scheduler", "nexup",
    ),
}


def preset_tiles(preset: str) -> tuple:
    if preset == "everything":
        return tuple(TILE_KEYS)
    return PRESETS.get(preset, PRESETS["essential"])


def tile_defaults(key: str) -> dict:
    return dict(TILE_DEFAULTS.get(key, {"size": "sm", "detail": "detailed"}))


def default_layout(preset: str = "essential") -> dict:
    """A complete v2 layout. Hidden tiles are the ones the preset leaves out."""
    visible = preset_tiles(preset)
    return {
        "version": SCHEMA_VERSION,
        "preset": preset,
        "grid": {"cols": 4, "rows": 2},
        "order": list(TILE_KEYS),
        "hidden": [key for key in TILE_KEYS if key not in visible],
        "locked": True,
        "tiles": {key: tile_defaults(key) for key in TILE_KEYS},
        "preferences": dict(DEFAULT_PREFERENCES),
        # `sizes` mirrors tiles[key].size in the flat shape the grid reads, and
        # `layouts` is the grid's own cached geometry. Both are round-tripped so
        # saving a v2 layout never discards an arrangement made in 2.0.x.
        "sizes": {key: tile_defaults(key)["size"] for key in TILE_KEYS},
        "layouts": {},
    }


def _clean_str(value: Any, allowed: tuple, fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _clean_key_list(value: Any) -> list:
    """Known tile keys only, in the given order, without duplicates."""
    if not isinstance(value, list):
        return []
    seen, out = set(), []
    for item in value:
        if isinstance(item, str) and item in TILE_KEYS and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def upgrade_layout(stored: Optional[dict]) -> dict:
    """Normalize any stored layout - v1, v2, or damaged - into a valid v2 layout.

    A v1 layout keeps its tile order and its hidden set. The tiles new in v2 are
    inserted at the front so the user lands on the new dashboard, but nothing
    they previously hid is un-hidden and nothing they arranged is reshuffled
    relative to its neighbours.
    """
    if not isinstance(stored, dict) or not stored:
        return default_layout()

    result = default_layout()
    was_v1 = int(stored.get("version") or 1) < SCHEMA_VERSION

    stored_order = _clean_key_list(stored.get("order"))
    stored_hidden = _clean_key_list(stored.get("hidden"))

    if stored_order or stored_hidden:
        if was_v1:
            # New tiles first, then everything the user already had.
            known = [key for key in stored_order if key not in NEW_IN_V2]
            order = [key for key in NEW_IN_V2] + known
        else:
            order = list(stored_order)
        # Any tile missing from the stored order (added in a later build) lands
        # at the end rather than vanishing.
        order += [key for key in TILE_KEYS if key not in order]
        result["order"] = order
        result["hidden"] = [key for key in stored_hidden if key in order]
        result["preset"] = "custom" if was_v1 else _clean_str(
            stored.get("preset"), tuple(PRESETS) + ("everything", "custom"), "custom"
        )

    grid = stored.get("grid")
    if isinstance(grid, dict):
        cols = grid.get("cols")
        rows = grid.get("rows")
        result["grid"] = {
            "cols": cols if isinstance(cols, int) and 1 <= cols <= 6 else 4,
            "rows": rows if isinstance(rows, int) and 1 <= rows <= 12 else 2,
        }

    if isinstance(stored.get("locked"), bool):
        result["locked"] = stored["locked"]

    # A v1 layout carries per-tile sizes only in the flat `sizes` map, so seed
    # from that first. A v2 payload's `tiles` is canonical and overwrites it
    # below - otherwise a stale `sizes` entry would undo a size the user just
    # changed through the tiles map.
    stored_sizes = stored.get("sizes")
    if isinstance(stored_sizes, dict):
        for key, value in stored_sizes.items():
            if key in TILE_KEYS and isinstance(value, str) and value in SIZES:
                result["tiles"][key]["size"] = value

    stored_tiles = stored.get("tiles")
    if isinstance(stored_tiles, dict):
        for key, value in stored_tiles.items():
            if key not in TILE_KEYS or not isinstance(value, dict):
                continue
            current = result["tiles"][key]
            result["tiles"][key] = {
                "size": _clean_str(value.get("size"), SIZES, current["size"]),
                "detail": _clean_str(value.get("detail"), DETAILS, current["detail"]),
            }

    # Keep the flat mirror in step with the canonical tiles map.
    result["sizes"] = {key: result["tiles"][key]["size"] for key in TILE_KEYS}

    # The grid's own cached geometry. Opaque to us; preserved verbatim.
    if isinstance(stored.get("layouts"), dict):
        result["layouts"] = stored["layouts"]

    stored_prefs = stored.get("preferences")
    if isinstance(stored_prefs, dict):
        prefs = result["preferences"]
        for flag in ("greeting", "healthNote", "dateTime"):
            if isinstance(stored_prefs.get(flag), bool):
                prefs[flag] = stored_prefs[flag]
        prefs["density"] = _clean_str(
            stored_prefs.get("density"), DENSITIES, DEFAULT_PREFERENCES["density"]
        )

    return result


def apply_preset(layout: Optional[dict], preset: str) -> dict:
    """Switch to a preset's composition while keeping per-tile settings.

    Presets own the visible panels and their leading order. Optional panels keep
    their previous relative order after that, so returning to a custom layout is
    still predictable.
    """
    result = copy.deepcopy(upgrade_layout(layout))
    visible = preset_tiles(preset)
    result["preset"] = preset if preset in tuple(PRESETS) + ("everything",) else "custom"
    result["order"] = list(visible) + [
        key for key in result["order"] if key not in visible
    ]
    result["hidden"] = [key for key in result["order"] if key not in visible]
    return result
