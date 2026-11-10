"""Titles left off the Coming Soon list by hand.

The Upcoming page's list switch used to set ``excluded_from_list`` on the
title's trailer row, and the list builders matched that by title. So the
exclusion went with the trailer: once the arrival window, retention or a
delete removed the trailer, the title was back on the list, and a title
without a trailer couldn't be excluded at all.

Exclusions now live in ``coming_soon_exclusions``, one row per title: movies
by TMDB id, shows by TVDB id (every season of a show, as before), and the
title when there is no id. The trailer flag is still written, and flags set by
an older version count until ``backfill`` copies them over at startup.
"""
from typing import List, Optional

from sqlalchemy import inspect

from backend import models

MOVIE = "movie"
SHOW = "show"
KINDS = (MOVIE, SHOW)


def _title_key(title) -> str:
    return " ".join(str(title or "").split()).lower()


def _id(value) -> Optional[int]:
    """An id, or None for a missing one (Radarr and Sonarr send 0 for none)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number or None


def _trailer_model(kind):
    return models.ComingSoonTrailer if kind == MOVIE else models.ComingSoonTVTrailer


def _trailer_id(kind, trailer) -> Optional[int]:
    return _id(trailer.tmdb_id if kind == MOVIE else trailer.tvdb_id)


def _same_title(kind_id, title_key, other_id, other_title) -> bool:
    """Whether a stored exclusion or trailer is the given title: by id when
    both have one, otherwise by title."""
    if kind_id and other_id:
        return kind_id == other_id
    return bool(title_key) and _title_key(other_title) == title_key


class Exclusions:
    """The excluded titles, to ask "is this one excluded?"."""

    def __init__(self):
        self.ids = {MOVIE: set(), SHOW: set()}
        self.titles = {MOVIE: set(), SHOW: set()}       # exclusions without an id
        self.any_titles = {MOVIE: set(), SHOW: set()}   # all of them, for titles without an id

    def add(self, kind, external_id, title) -> None:
        external_id, key = _id(external_id), _title_key(title)
        if external_id:
            self.ids[kind].add(external_id)
        elif key:
            self.titles[kind].add(key)
        if key:
            self.any_titles[kind].add(key)

    def excludes(self, kind, external_id, title) -> bool:
        external_id, key = _id(external_id), _title_key(title)
        if external_id:
            return external_id in self.ids[kind] or key in self.titles[kind]
        return bool(key) and key in self.any_titles[kind]

    def excludes_item(self, item) -> bool:
        """For a Coming Soon list item (see main._coming_soon_list_items)."""
        if item.get("type") == "show":
            return self.excludes(SHOW, item.get("tvdb_id"), item.get("series_title") or item.get("title"))
        return self.excludes(MOVIE, item.get("tmdb_id"), item.get("title"))


def _table_ready(db) -> bool:
    """False on a database restored from before the table, until the next
    start creates it."""
    try:
        return inspect(db.get_bind()).has_table(models.ComingSoonExclusion.__tablename__)
    except Exception:
        return False


def _ensure_table(db) -> None:
    models.ComingSoonExclusion.__table__.create(bind=db.connection(), checkfirst=True)


def _stored(db) -> list:
    if not _table_ready(db):
        return []
    return [row for row in db.query(models.ComingSoonExclusion).all() if row.kind in KINDS]


def load(db) -> Exclusions:
    found = Exclusions()
    for row in _stored(db):
        found.add(row.kind, row.external_id, row.title)
    for kind in KINDS:
        model = _trailer_model(kind)
        for trailer in db.query(model).filter(model.excluded_from_list == True).all():  # noqa: E712
            found.add(kind, _trailer_id(kind, trailer), trailer.title)
    return found


def set_excluded(db, kind: str, external_id, title, excluded: bool) -> bool:
    """Leave a title off the Coming Soon list, or put it back, and set the
    flag on its trailer rows to match. The caller commits."""
    if kind not in KINDS:
        raise ValueError("kind must be 'movie' or 'show'")
    external_id, key = _id(external_id), _title_key(title)
    if not external_id and not key:
        raise ValueError("A title or an id is needed")
    _ensure_table(db)
    model = models.ComingSoonExclusion
    for row in db.query(model).filter(model.kind == kind).all():
        if _same_title(external_id, key, _id(row.external_id), row.title):
            db.delete(row)
    if excluded:
        db.add(model(kind=kind, external_id=external_id, title=str(title or "").strip() or None))
    for trailer in db.query(_trailer_model(kind)).all():
        if _same_title(external_id, key, _trailer_id(kind, trailer), trailer.title):
            trailer.excluded_from_list = bool(excluded)
    return bool(excluded)


def backfill(db) -> int:
    """Copy exclusions an older version stored on trailer rows into the
    table, so they outlive their trailer. Returns how many were added; the
    caller commits."""
    _ensure_table(db)
    known = Exclusions()
    for row in db.query(models.ComingSoonExclusion).all():
        if row.kind in KINDS:
            known.add(row.kind, row.external_id, row.title)
    added = 0
    for kind in KINDS:
        model = _trailer_model(kind)
        for trailer in db.query(model).filter(model.excluded_from_list == True).all():  # noqa: E712
            external_id = _trailer_id(kind, trailer)
            if known.excludes(kind, external_id, trailer.title):
                continue
            db.add(models.ComingSoonExclusion(kind=kind, external_id=external_id, title=trailer.title))
            known.add(kind, external_id, trailer.title)
            added += 1
    return added


def listed(db) -> List[dict]:
    """Every stored exclusion, for the API."""
    return [{"id": row.id, "kind": row.kind, "external_id": row.external_id, "title": row.title,
             "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in sorted(_stored(db), key=lambda r: (r.kind, _title_key(r.title)))]
