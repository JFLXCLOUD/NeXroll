"""Shared, fail-closed age-rating restrictions for trailer playback."""

import json
import re

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


# Genre names differ between sources: TMDB files TV under "Action & Adventure"
# and "Sci-Fi & Fantasy" while movies say "Action" and "Science Fiction".
_GENRE_ALIASES = {"sci-fi": "science fiction", "scifi": "science fiction",
                  "science-fiction": "science fiction"}


def genre_keys(names) -> set:
    """Lower-cased genre names, with compound names also split into their parts,
    so "Sci-Fi & Fantasy" matches both "Science Fiction" and "Fantasy"."""
    keys = set()
    for name in names or []:
        text = re.sub(r"\s+", " ", str(name or "")).strip().lower()
        if not text:
            continue
        keys.add(_GENRE_ALIASES.get(text, text))
        parts = [p.strip() for p in re.split(r"[&/]", text) if p.strip()]
        if len(parts) > 1:
            keys.update(_GENRE_ALIASES.get(p, p) for p in parts)
    return keys


def genre_json(names):
    """Genres as stored on a trailer row: a JSON list, or None when unknown."""
    if not isinstance(names, list):
        return None
    return json.dumps([str(g) for g in names if str(g).strip()])


def match_playing_genre(rows, block, context):
    """Apply a trailer block's "same genre as the movie that's starting".

    Off, or no playback to ask about (a preview without a simulated genre):
    rows unchanged. Otherwise the trailers sharing a genre with what is about
    to play. When none do, or the genre is unknown (Plex never says what is
    playing), match_playing_only decides: no trailers, or the whole pool.
    """
    if context is None or not block.get("match_playing"):
        return rows
    only = bool(block.get("match_playing_only"))
    playing = context.genres()
    if not playing:
        return [] if only else rows
    wanted = genre_keys(playing)
    matched = [r for r in rows if genre_keys(r.genre_list()) & wanted]
    return matched if matched or only else rows


def genre_rotation_key(rotation_key, block, context):
    """A separate shuffle bag per playing genre. The bag resets whenever its
    pool changes, so sharing one across genres would reset it on nearly every
    movie and let the same trailers repeat."""
    if rotation_key is None or context is None or not block.get("match_playing"):
        return rotation_key
    playing = context.genres()
    if not playing:
        return rotation_key
    return (rotation_key, "genre", tuple(sorted(genre_keys(playing))))


def migrate_trailer_ratings(connection):
    """Add nullable metadata without modifying existing trailer/sequence content."""
    from sqlalchemy import inspect
    inspector = inspect(connection)
    for table in ("coming_soon_trailers", "coming_soon_tv_trailers", "library_trailers"):
        if not inspector.has_table(table):
            continue
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "certification" not in columns:
            connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN certification TEXT')
        # library_trailers has always had genres; NeX-Up rows gained them in
        # 2.2.2 and stay unknown (NULL) until their next sync fills them in.
        if "genres" not in columns:
            connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN genres TEXT')


def refresh_trailer_ratings(db, model, items, row_key, item_key):
    """Refresh already-downloaded records during sync, including legacy rows.

    Covers the certification and, where the row stores them, the genres. The
    caller owns the transaction. Metadata updates never redownload or move media.
    """
    by_id = {str(item.get(item_key)): item for item in items if item.get(item_key) is not None}
    has_genres = hasattr(model, "genres")
    for row in db.query(model).all():
        item = by_id.get(str(getattr(row, row_key)))
        if item is None:
            continue
        if "certification" in item:
            row.certification = item.get("certification") or None
        if has_genres and isinstance(item.get("genres"), list):
            row.genres = genre_json(item["genres"])


def has_trailer_policy(blocks):
    """Trailer restrictions or audio rules may intentionally produce silence.

    Keep the existing helper name; these policies must never restore an old pool.
    """
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") in ("nexup_trailers", "library_trailers") and (
                block.get("restrict_ratings") or ("ratings" in block and block["ratings"] != [])
                or (block.get("match_playing") and block.get("match_playing_only"))):
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
