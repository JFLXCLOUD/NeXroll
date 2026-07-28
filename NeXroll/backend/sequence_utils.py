"""Helpers shared by saved-sequence and schedule persistence."""

from __future__ import annotations


def representative_category_id(blocks) -> int | None:
    """Return the first valid category-backed sequence block, if any."""
    for block in blocks or []:
        if not isinstance(block, dict) or str(block.get("type", "")).lower() not in {"random", "sequential"}:
            continue
        raw_id = block.get("category_id", block.get("categoryId"))
        try:
            category_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if category_id > 0:
            return category_id
    return None
