"""Pure helpers for preserving database references across JSON restores."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any


def normalize_preroll_id(value: Any) -> int | None:
    """Return a positive integer ID without accepting lossy coercions."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _normalized_id_map(id_map: Mapping[Any, Any] | None) -> dict[int, int]:
    normalized: dict[int, int] = {}
    for old_value, new_value in (id_map or {}).items():
        old_id = normalize_preroll_id(old_value)
        new_id = normalize_preroll_id(new_value)
        if old_id is not None and new_id is not None:
            normalized[old_id] = new_id
    return normalized


def _remap_id_values(values: Any, id_map: Mapping[Any, Any] | None) -> list[int]:
    """Remap a list of old IDs, explicitly dropping invalid/unmapped values."""
    if not isinstance(values, (list, tuple)):
        return []
    normalized_map = _normalized_id_map(id_map)
    remapped: list[int] = []
    for value in values:
        old_id = normalize_preroll_id(value)
        if old_id is not None and old_id in normalized_map:
            remapped.append(normalized_map[old_id])
    return remapped


def remap_preroll_ids_json(raw_value: Any, id_map: Mapping[Any, Any] | None) -> str | None:
    """Remap a schedule's JSON preroll list, returning ``None`` when empty.

    Malformed or unmapped references are removed instead of retained. Retaining
    an old numeric ID is unsafe because SQLite may assign that ID to a different
    preroll while rebuilding the table.
    """
    if raw_value is None or raw_value == "":
        return None
    try:
        values = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    remapped = _remap_id_values(values, id_map)
    return json.dumps(remapped) if remapped else None


def remap_sequence_blocks(
    raw_blocks: Any,
    preroll_id_map: Mapping[Any, Any] | None,
    category_id_map: Mapping[Any, Any] | None = None,
) -> list[Any]:
    """Copy sequence blocks and remap their database-backed references.

    Fixed blocks use preroll IDs. Random and sequential blocks use category
    IDs (including the legacy camelCase spelling). Unknown block types and
    their data are preserved verbatim. A category-backed block with an
    unmapped numeric reference is removed entirely: leaving the block without
    that field would let schedule execution fall back to its top-level category
    and could still play the wrong content.

    ``category_id_map=None`` means category references are outside the caller's
    scope and are left untouched. Passing an empty map explicitly removes all
    numeric category references, which is the safe behavior for a legacy
    restore that supplied no usable category mappings.
    """
    if isinstance(raw_blocks, str):
        try:
            raw_blocks = json.loads(raw_blocks)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(raw_blocks, list):
        return []

    blocks = copy.deepcopy(raw_blocks)
    normalized_preroll_map = _normalized_id_map(preroll_id_map)
    normalized_category_map = (
        _normalized_id_map(category_id_map) if category_id_map is not None else None
    )
    remapped_blocks: list[Any] = []
    for block in blocks:
        if not isinstance(block, dict):
            remapped_blocks.append(block)
            continue
        block_type = str(block.get("type", "")).lower()

        if block_type == "fixed":
            if "preroll_ids" in block:
                block["preroll_ids"] = _remap_id_values(
                    block.get("preroll_ids"),
                    normalized_preroll_map,
                )

            if "preroll_id" in block:
                old_id = normalize_preroll_id(block.get("preroll_id"))
                new_id = (
                    normalized_preroll_map.get(old_id) if old_id is not None else None
                )
                if new_id is None:
                    block.pop("preroll_id", None)
                else:
                    block["preroll_id"] = new_id

        if block_type in {"random", "sequential"} and normalized_category_map is not None:
            reference_field = (
                "category_id" if "category_id" in block
                else "categoryId" if "categoryId" in block
                else None
            )
            if reference_field is not None:
                old_id = normalize_preroll_id(block.get(reference_field))
                new_id = (
                    normalized_category_map.get(old_id) if old_id is not None else None
                )
                if new_id is None:
                    continue
                block["category_id"] = new_id
                block.pop("categoryId", None)

        remapped_blocks.append(block)

    return remapped_blocks


def remap_fixed_preroll_blocks(
    raw_blocks: Any,
    id_map: Mapping[Any, Any] | None,
) -> list[Any]:
    """Backward-compatible wrapper for callers remapping only fixed blocks."""
    return remap_sequence_blocks(raw_blocks, id_map)


def remap_sequence_json(
    raw_value: Any,
    preroll_id_map: Mapping[Any, Any] | None,
    category_id_map: Mapping[Any, Any] | None = None,
) -> str | None:
    """Remap database-backed references in a schedule's sequence JSON."""
    if raw_value is None or raw_value == "":
        return None
    blocks = remap_sequence_blocks(raw_value, preroll_id_map, category_id_map)
    return json.dumps(blocks)
