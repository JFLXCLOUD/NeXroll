"""Classification helpers for Community Prerolls index entries."""

from urllib.parse import unquote, urlparse


def is_ai_preroll(preroll: dict) -> bool:
    """Return True when an entry belongs to the top-level /AI/ directory.

    Older indexes do not have an ``is_ai`` field, so path/category inference is
    intentionally retained for backwards compatibility.
    """
    if preroll.get("is_ai") is True:
        return True

    category = unquote(str(preroll.get("category") or "")).strip().casefold()
    if category == "ai":
        return True

    raw_path = str(preroll.get("path") or preroll.get("id") or "")
    if not raw_path and preroll.get("url"):
        raw_path = urlparse(str(preroll["url"])).path

    parts = [
        unquote(part).strip().casefold()
        for part in raw_path.replace("\\", "/").split("/")
        if part.strip()
    ]
    return bool(parts and parts[0] == "ai")


def filter_ai_prerolls(prerolls, include_ai: bool = False) -> list:
    """Return entries allowed by the AI-directory preference."""
    entries = list(prerolls or [])
    if include_ai:
        return entries
    return [entry for entry in entries if not is_ai_preroll(entry)]
