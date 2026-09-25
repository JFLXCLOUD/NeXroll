"""Shared, fail-closed age-rating restrictions for trailer playback."""

RATINGS = ("G", "PG", "PG-13", "R", "NC-17", "TV-Y", "TV-Y7", "TV-Y7-FV",
           "TV-G", "TV-PG", "TV-14", "TV-MA", "Unrated")


def rating_key(value):
    text = str(value or "").strip().upper()
    return "UNRATED" if text in ("", "NR", "N/A", "NOT RATED", "UNRATED") else text


def filter_trailer_ratings(rows, block):
    """Absent/empty filters preserve legacy selection. Malformed ones never broaden it.

    Certification is for the film/show, not independently verified trailer content.
    Unrecognized international ratings stay distinct from missing/Unrated metadata.
    """
    allowed = block.get("ratings", [])
    if allowed is None or not isinstance(allowed, list):
        return []
    if not allowed:
        return [] if block.get("restrict_ratings") else rows
    if any(not isinstance(r, str) or r not in RATINGS for r in allowed):
        return []
    wanted = {rating_key(r) for r in allowed}
    return [row for row in rows if rating_key(getattr(row, "certification", None)) in wanted]


def migrate_trailer_ratings(connection):
    """Add nullable metadata without modifying existing trailer/sequence content."""
    from sqlalchemy import inspect
    inspector = inspect(connection)
    for table in ("coming_soon_trailers", "coming_soon_tv_trailers", "library_trailers"):
        if inspector.has_table(table) and "certification" not in {c["name"] for c in inspector.get_columns(table)}:
            connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN certification TEXT')


def refresh_trailer_ratings(db, model, items, row_key, item_key):
    """Refresh already-downloaded records during sync, including legacy rows.

    The caller owns the transaction. Metadata updates never redownload or move media.
    """
    by_id = {str(item.get(item_key)): item for item in items if item.get(item_key) is not None}
    for row in db.query(model).all():
        item = by_id.get(str(getattr(row, row_key)))
        if item is not None and "certification" in item:
            row.certification = item.get("certification") or None


def has_trailer_policy(blocks):
    """Trailer restrictions or audio rules may intentionally produce silence.

    Keep the existing helper name; these policies must never restore an old pool.
    """
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") in ("nexup_trailers", "library_trailers") and (
                block.get("restrict_ratings") or ("ratings" in block and block["ratings"] != [])):
            return True
        condition = block.get("condition")
        if isinstance(condition, dict):
            for rule in condition.get("rules") or []:
                if isinstance(rule, dict) and str(rule.get('kind', '')).lower() == 'audio_format':
                    return True
                if isinstance(rule, dict) and rule.get("kind") == "trailers_available" and (
                        rule.get("pool") in ("library", "block") or rule.get("restrict_ratings") or rule.get("ratings")):
                    return True
        if has_trailer_policy([block.get("otherwise")]):
            return True
    return False
