"""Rules every NeX-Up trailer sync shares.

The Sync buttons (main.sync_nexup, main.sync_sonarr_trailers) and the
automatic syncs (scheduler._sync_radarr_trailers, _sync_sonarr_trailers) each
had their own copy of these, and the copies drifted apart: the automatic movie
sync ignored Include unmonitored movies, the release date preference, the
storage limit and deleted trailer files; a download delay of 0 meant 5
seconds; and the release dates stored with trailers were never updated, so a
movie or premiere that moved was removed by its old date.
"""
import datetime
import os
from typing import Optional

from backend.available_now import as_date as _as_date

DEFAULT_DOWNLOAD_DELAY = 5
DEFAULT_MAX_TRAILERS = 10
DEFAULT_MAX_STORAGE_GB = 5.0
# A TV trailer row still 'downloading' after this long is from a download that
# never finished (NeXroll stopped, or it failed without being recorded).
STALE_DOWNLOAD = datetime.timedelta(hours=1)


def download_delay(setting) -> int:
    """Seconds between downloads. 0 is allowed (the API takes 0-60) and used
    to be read as 5."""
    value = getattr(setting, "nexup_download_delay", None)
    if value is None:
        return DEFAULT_DOWNLOAD_DELAY
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return DEFAULT_DOWNLOAD_DELAY


def max_trailers(setting) -> int:
    """Maximum stored trailers, 0 for no limit. Movie and TV trailers each
    get this many. At the limit a sync stops downloading; nothing is removed
    to make room."""
    value = getattr(setting, "nexup_max_trailers", None)
    if value is None:
        return DEFAULT_MAX_TRAILERS
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return DEFAULT_MAX_TRAILERS


def max_storage_gb(setting) -> float:
    try:
        return float(getattr(setting, "nexup_max_storage_gb", None) or DEFAULT_MAX_STORAGE_GB)
    except (TypeError, ValueError):
        return DEFAULT_MAX_STORAGE_GB


def storage_full(downloader, setting) -> Optional[str]:
    """Why no more trailers fit: the movie and TV trailer folders together
    are at the storage limit (Library Trailers don't count). None otherwise."""
    limit = max_storage_gb(setting)
    try:
        used = float(downloader.get_storage_usage().get("total_size_gb") or 0)
    except Exception:
        return None
    if used >= limit:
        return f"Reached storage limit ({limit:g}GB)"
    return None


def movie_options(setting) -> dict:
    """The movie settings parse_upcoming_from_raw takes."""
    return {
        "include_unmonitored": bool(getattr(setting, "nexup_include_unmonitored_movies", False)),
        "release_date_preference": getattr(setting, "nexup_release_date_preference", None) or "digital_first",
    }


def file_is_gone(path) -> bool:
    """True when a trailer's file was deleted: its folder is there and the
    file isn't. A folder that can't be seen (an unplugged drive, a share that
    is down) says nothing, so the trailer is kept."""
    if not path or os.path.exists(path):
        return False
    folder = os.path.dirname(path)
    return bool(folder) and os.path.isdir(folder)


def failed_tries(rows, now) -> Optional[list]:
    """For one TV season's trailer rows: the ones earlier tries left behind
    that a sync replaces and tries again (a failed or too-long download, or
    one still 'downloading' after STALE_DOWNLOAD). None when the season
    already has its trailer, or a download for it may still be running, so
    the sync skips it. A failed row used to block its season on every later
    sync; only the Upcoming page's Download tried again."""
    replace = []
    for row in rows:
        if row.status == "downloaded" or (row.local_path and os.path.exists(row.local_path)):
            return None
        if row.status == "downloading":
            started = row.updated_at or row.created_at
            if started is not None and now - started < STALE_DOWNLOAD:
                return None
        replace.append(row)
    return replace


def drop_orphans(db, trailers, drop_prerolls, log=None) -> list:
    """Remove the rows of trailers whose file was deleted, and their prerolls,
    so a later sync can download the trailer again. Returns the removed rows;
    the caller commits."""
    removed = []
    for trailer in trailers:
        if not file_is_gone(trailer.local_path):
            continue
        if log:
            log(f"Removing the record for '{trailer.title}': its trailer file is gone ({trailer.local_path})")
        drop_prerolls(db, trailer.local_path)
        db.delete(trailer)
        removed.append(trailer)
    return removed


def _set_release(trailer, new_date, new_type=None) -> bool:
    old_date = _as_date(trailer.release_date)
    keep_type = new_type is None
    if old_date == new_date and (keep_type or (trailer.release_type or None) == new_type):
        return False
    trailer.release_date = datetime.datetime.combine(new_date, datetime.time())
    if not keep_type:
        trailer.release_type = new_type
    return True


def refresh_movie_dates(trailers, movies_by_id, preference, log=None) -> int:
    """Bring each movie trailer's stored release date (and its type) up to
    date with Radarr under the release date preference, so retention counts
    from the date the movie has now. A movie Radarr gives no date for keeps
    the stored one. Returns how many changed; the caller commits."""
    from backend.radarr_connector import movie_release_date
    changed = 0
    for trailer in trailers:
        movie = movies_by_id.get(trailer.radarr_movie_id)
        if not movie:
            continue
        new_date, new_type = movie_release_date(movie, preference)
        if new_date is None:
            continue
        old_date = _as_date(trailer.release_date)
        if _set_release(trailer, new_date, new_type):
            changed += 1
            if log and old_date != new_date:
                log(f"'{trailer.title}' now releases {new_date.isoformat()} (was {old_date.isoformat() if old_date else 'unknown'})")
    return changed


def refresh_show_dates(trailers, premieres, log=None) -> int:
    """The same for TV trailers, from Sonarr's calendar: a season's premiere
    date is updated when the calendar has its first episode. A season the
    calendar doesn't cover keeps its stored date. Returns how many changed;
    the caller commits."""
    by_slot = {(p.get("sonarr_id"), p.get("season_number")): p for p in premieres or []}
    changed = 0
    for trailer in trailers:
        premiere = by_slot.get((trailer.sonarr_series_id, trailer.season_number))
        new_date = _as_date(premiere.get("release_date")) if premiere else None
        if new_date is None:
            continue
        old_date = _as_date(trailer.release_date)
        if _set_release(trailer, new_date):
            changed += 1
            if log:
                log(f"'{trailer.title}' S{trailer.season_number} now premieres {new_date.isoformat()} (was {old_date.isoformat() if old_date else 'unknown'})")
    return changed
