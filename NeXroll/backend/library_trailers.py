"""NeX-Up Library Trailers: trailers for movies already in the library.

Separate from Coming Soon on purpose. Coming Soon trailers are about what is
*not* in the library yet and are removed once the movie arrives; these are
about what already is. They have their own settings, their own table
(LibraryTrailer) and their own folder, so neither feature can clean up the
other's files.

Where a trailer comes from, in order:
  1. A trailer file already next to the movie ("Movie-trailer.mp4", or a
     "Trailers" folder), found through Radarr's movie folder. NeXroll only
     ever reads these and never deletes them.
  2. A download from YouTube through Radarr's trailer link, into
     <NeX-Up storage>/library. Only these count toward the limits, and only
     these are ever deleted.

Changing the filters decides what is downloaded *next*; it never throws
trailers away. A trailer whose movie stops matching is kept, still plays, and
is marked outside the selection - first in line to make room when the limits
are reached, or removed on request. Only a movie leaving the library, or its
file disappearing, removes a trailer on its own.

Downloads rotate: once the limits are reached, each sync swaps a few of the
oldest downloads for movies that don't have one yet, so the selection keeps
changing.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import random
import sys
from typing import Optional

import backend.models as models

VIDEO_EXTS = (".mp4", ".mkv", ".m4v", ".mov", ".avi", ".webm")
ROTATE_PER_SYNC = 3          # downloads swapped per sync once full
ROTATE_MIN_AGE_DAYS = 7      # a download plays for at least this long first
RETRY_ERROR_DAYS = 3         # wait before retrying a failed download
PREVIEW_LIMIT = 500

PRIORITIES = ("newest", "rating", "popular", "random")
AGE_RATINGS = ("G", "PG", "PG-13", "R", "NC-17", "Unrated")

MODES = ("filters", "picked")

DEFAULT_CONFIG = {
    "enabled": False,
    # How movies are chosen: by the filters below, or hand-picked. Picks are
    # kept apart from the filters so switching modes loses neither.
    "mode": "filters",
    "picked": [],            # Radarr movie ids, in hand-pick mode
    # Which movies. Every filter is optional; an empty one doesn't narrow.
    "genres": [],            # include movies with any of these
    "exclude_genres": [],    # ...but none of these
    "certifications": [],    # age ratings, from AGE_RATINGS
    "languages": [],         # original language names
    "tags": [],              # Radarr tag ids
    "year_from": 0,
    "year_to": 0,
    "min_imdb": 0.0,         # IMDb score out of 10
    "min_rt": 0,             # Rotten Tomatoes percent
    "recent_days": 0,        # only movies added in the last N days; 0 = any
    "always_include": [],    # Radarr movie ids included whatever the filters say
    "never_include": [],     # Radarr movie ids never included
    "priority": "newest",    # which matching movies are downloaded first
    "use_local": True,       # use trailer files already next to movies
    "download": True,        # download the rest from YouTube via Radarr
    "max_downloads": 25,
    "max_gb": 5.0,
    "path_mappings": [],     # [{"radarr": "/movies", "local": "D:\\Movies"}]
}


# ---- Settings ----------------------------------------------------------

def load_config(setting) -> dict:
    config = dict(DEFAULT_CONFIG)
    raw = getattr(setting, "library_trailers_config", None) if setting else None
    if raw:
        try:
            stored = json.loads(raw)
            if isinstance(stored, dict):
                # normalize_config drops unknown keys, after reading legacy ones.
                config.update(stored)
        except Exception:
            pass
    return normalize_config(config)


def _names(value) -> list:
    seen = {}
    for item in value if isinstance(value, list) else []:
        name = str(item).strip()
        if name:
            seen.setdefault(name.lower(), name)
    return list(seen.values())


def _ids(value) -> list:
    out = []
    for item in value if isinstance(value, list) else []:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number not in out:
            out.append(number)
    return out


def normalize_config(config: dict) -> dict:
    config = dict(config or {})
    # Settings saved before the genre filter became optional said
    # include='all' to mean "ignore the genre list".
    if config.get("include") == "all":
        config["genres"] = []
    out = dict(DEFAULT_CONFIG)
    out.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    out["enabled"] = bool(out["enabled"])
    for key in ("genres", "exclude_genres", "languages"):
        out[key] = _names(out[key])
    out["certifications"] = [c for c in _names(out["certifications"]) if c in AGE_RATINGS]
    for key in ("tags", "always_include", "never_include", "picked"):
        out[key] = _ids(out[key])
    if out["mode"] not in MODES:
        out["mode"] = "filters"
    out["always_include"] = [i for i in out["always_include"] if i not in out["never_include"]]
    for key, lo, hi, cast in (("recent_days", 0, 3650, int), ("max_downloads", 0, 500, int),
                              ("max_gb", 0.0, 500.0, float), ("year_from", 0, 2200, int),
                              ("year_to", 0, 2200, int), ("min_imdb", 0.0, 10.0, float), ("min_rt", 0, 100, int)):
        try:
            out[key] = min(max(cast(out[key]), lo), hi)
        except (TypeError, ValueError):
            out[key] = DEFAULT_CONFIG[key]
    if out["priority"] not in PRIORITIES:
        out["priority"] = "newest"
    out["use_local"] = bool(out["use_local"])
    out["download"] = bool(out["download"])
    maps = []
    for m in out["path_mappings"] if isinstance(out["path_mappings"], list) else []:
        if isinstance(m, dict) and str(m.get("radarr", "")).strip() and str(m.get("local", "")).strip():
            maps.append({"radarr": str(m["radarr"]).strip(), "local": str(m["local"]).strip()})
    out["path_mappings"] = maps
    return out


def save_config(setting, updates: dict) -> dict:
    config = load_config(setting)
    config.update({k: v for k, v in (updates or {}).items() if k in DEFAULT_CONFIG})
    config = normalize_config(config)
    setting.library_trailers_config = json.dumps(config)
    return config


# ---- Radarr movies -----------------------------------------------------

def _parse_date(value) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def movie_added(movie: dict) -> Optional[datetime.datetime]:
    """When the movie joined the library: Radarr's "Added" date.

    Not the file's dateAdded, which Radarr resets whenever a file is renamed,
    upgraded or re-imported - a library-wide rename made hundreds of old
    movies look brand new. The file date is only a fallback for a movie with
    no added date."""
    return _parse_date(movie.get("added")) or _parse_date((movie.get("movieFile") or {}).get("dateAdded"))


def movie_poster(movie: dict) -> Optional[str]:
    for image in movie.get("images") or []:
        if str(image.get("coverType", "")).lower() == "poster":
            return image.get("remoteUrl") or image.get("url")
    return None


def movie_rating(movie: dict, source: str) -> Optional[float]:
    value = ((movie.get("ratings") or {}).get(source) or {}).get("value")
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def movie_certification(movie: dict) -> str:
    """The movie's age rating, with blanks and NR both reported as Unrated."""
    cert = str(movie.get("certification") or "").strip().upper()
    return cert if cert in AGE_RATINGS else "Unrated"


def movie_language(movie: dict) -> Optional[str]:
    return (movie.get("originalLanguage") or {}).get("name") or None


def movie_matches(movie: dict, config: dict, now: Optional[datetime.datetime] = None) -> bool:
    """Whether a movie belongs in the library trailer selection."""
    if not movie.get("hasFile"):
        return False
    if config.get("mode") == "picked":
        return movie.get("id") in config["picked"]
    if movie.get("id") in config["never_include"]:
        return False
    if movie.get("id") in config["always_include"]:
        return True
    genres = {str(g).lower() for g in movie.get("genres") or []}
    if config["genres"] and not genres & {g.lower() for g in config["genres"]}:
        return False
    if config["exclude_genres"] and genres & {g.lower() for g in config["exclude_genres"]}:
        return False
    if config["certifications"] and movie_certification(movie) not in config["certifications"]:
        return False
    if config["languages"] and (movie_language(movie) or "").lower() not in {l.lower() for l in config["languages"]}:
        return False
    if config["tags"] and not set(movie.get("tags") or []) & set(config["tags"]):
        return False
    year = movie.get("year") or 0
    if config["year_from"] and year < config["year_from"]:
        return False
    if config["year_to"] and (not year or year > config["year_to"]):
        return False
    if config["min_imdb"] and (movie_rating(movie, "imdb") or 0) < config["min_imdb"]:
        return False
    if config["min_rt"] and (movie_rating(movie, "rottenTomatoes") or 0) < config["min_rt"]:
        return False
    if config["recent_days"]:
        added = movie_added(movie)
        cutoff = (now or datetime.datetime.utcnow()) - datetime.timedelta(days=config["recent_days"])
        if not added or added < cutoff:
            return False
    return True


def order_candidates(movies: list, config: dict) -> list:
    """Matching movies in the order they should get a trailer: always-include
    first, then by the chosen priority."""
    priority = config["priority"]
    if priority == "random":
        ordered = list(movies)
        random.shuffle(ordered)
    elif priority == "rating":
        ordered = sorted(movies, key=lambda m: (movie_rating(m, "imdb") or 0, movie_rating(m, "tmdb") or 0), reverse=True)
    elif priority == "popular":
        ordered = sorted(movies, key=lambda m: float(m.get("popularity") or 0), reverse=True)
    else:
        ordered = sorted(movies, key=lambda m: movie_added(m) or datetime.datetime.min, reverse=True)
    pinned = [m for m in ordered if m.get("id") in config["always_include"]]
    return pinned + [m for m in ordered if m.get("id") not in config["always_include"]]


def facets(movies: list) -> dict:
    """What the library offers to filter on, with how many movies each covers."""
    in_library = [m for m in movies if m.get("hasFile")]
    certs, langs = {}, {}
    for m in in_library:
        cert = movie_certification(m)
        certs[cert] = certs.get(cert, 0) + 1
        lang = movie_language(m)
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
    years = [m.get("year") for m in in_library if m.get("year")]
    return {
        "genres": library_genres(movies),
        "certifications": [{"name": c, "count": certs.get(c, 0)} for c in AGE_RATINGS if certs.get(c)],
        "languages": [{"name": n, "count": c} for n, c in sorted(langs.items(), key=lambda kv: -kv[1])],
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
    }


def poster_thumb(url: Optional[str]) -> Optional[str]:
    """TMDB serves posters at several sizes; lists only need a small one."""
    return url.replace("/t/p/original/", "/t/p/w185/") if url else url


def movie_summary(movie: dict) -> dict:
    return {
        "id": movie.get("id"),
        "title": movie.get("title"),
        "year": movie.get("year"),
        "poster_url": poster_thumb(movie_poster(movie)),
        "certification": movie_certification(movie),
        "imdb": movie_rating(movie, "imdb"),
        "genres": movie.get("genres") or [],
        "has_trailer_link": bool(movie.get("youTubeTrailerId")),
    }


def library_genres(movies: list) -> list:
    """[{"name", "count"}] for every genre across movies in the library."""
    counts = {}
    names = {}
    for movie in movies:
        if not movie.get("hasFile"):
            continue
        for g in movie.get("genres") or []:
            key = str(g).lower()
            names.setdefault(key, str(g))
            counts[key] = counts.get(key, 0) + 1
    return sorted(({"name": names[k], "count": c} for k, c in counts.items()), key=lambda x: x["name"].lower())


# ---- Local trailer files -----------------------------------------------

def map_radarr_path(path: Optional[str], mappings: list) -> Optional[str]:
    """Translate a folder as Radarr sees it into one NeXroll can open."""
    if not path:
        return None
    best = None
    for m in mappings:
        src = m["radarr"].rstrip("/\\")
        norm = path.replace("\\", "/")
        cmp_path, cmp_src = (norm.lower(), src.replace("\\", "/").lower()) if sys.platform.startswith("win") else (norm, src.replace("\\", "/"))
        if (cmp_path == cmp_src or cmp_path.startswith(cmp_src + "/")) and (best is None or len(src) > len(best["radarr"])):
            best = m
    if not best:
        return path
    rest = path.replace("\\", "/")[len(best["radarr"].rstrip("/\\")):].lstrip("/")
    return os.path.join(best["local"], *rest.split("/")) if rest else best["local"]


def find_local_trailer(folder: Optional[str]) -> Optional[str]:
    """A trailer file next to a movie, using the naming Plex, Jellyfin and Emby
    share: "<name>-trailer.<ext>" (also ".trailer" / "_trailer"), "trailer.<ext>",
    or anything inside a "Trailers" subfolder."""
    if not folder or not os.path.isdir(folder):
        return None
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in entries:
        stem, ext = os.path.splitext(name)
        if ext.lower() in VIDEO_EXTS:
            low = stem.lower()
            if low == "trailer" or low.endswith(("-trailer", ".trailer", "_trailer")):
                return os.path.join(folder, name)
    for name in entries:
        if name.lower() == "trailers" and os.path.isdir(os.path.join(folder, name)):
            try:
                for inner in sorted(os.listdir(os.path.join(folder, name))):
                    if os.path.splitext(inner)[1].lower() in VIDEO_EXTS:
                        return os.path.join(folder, name, inner)
            except OSError:
                return None
    return None


# ---- Storage -----------------------------------------------------------

def library_dir(storage: str) -> str:
    return os.path.join(storage, "library")


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def remove_row(db, row, storage: Optional[str]) -> None:
    """Forget a library trailer. A downloaded file inside NeXroll's library
    folder is deleted with it; anything else - a trailer next to the movie -
    is never touched."""
    if row.source == "download" and row.local_path and storage and _inside(row.local_path, library_dir(storage)):
        try:
            if os.path.isfile(row.local_path):
                os.remove(row.local_path)
        except OSError:
            pass
    db.delete(row)


def eligible_library_trailers(db) -> list:
    """Every library trailer a block could play: available, enabled, on disk."""
    rows = db.query(models.LibraryTrailer).filter(
        models.LibraryTrailer.status == "available",
        models.LibraryTrailer.is_enabled == True,  # noqa: E712
    ).all()
    return [r for r in rows if r.local_path and os.path.exists(r.local_path)]


def storage_summary(db) -> dict:
    rows = db.query(models.LibraryTrailer).all()
    downloads = [r for r in rows if r.source == "download" and r.status == "available"]
    return {
        "local": sum(1 for r in rows if r.source == "local" and r.status == "available"),
        "downloaded": len(downloads),
        "downloaded_gb": round(sum((r.file_size_mb or 0) for r in downloads) / 1024, 2),
        "errors": sum(1 for r in rows if r.status == "error"),
        "outside": sum(1 for r in rows if r.status == "available" and r.in_selection is False),
    }


# ---- Sync --------------------------------------------------------------

def _upsert(db, rows_by_movie, movie, **fields):
    row = rows_by_movie.get(movie["id"])
    if row is None:
        row = models.LibraryTrailer(radarr_movie_id=movie["id"])
        db.add(row)
        rows_by_movie[movie["id"]] = row
    row.tmdb_id = movie.get("tmdbId")
    row.title = movie.get("title")
    row.year = movie.get("year")
    row.genres = json.dumps(movie.get("genres") or [])
    row.added_to_library = movie_added(movie)
    row.poster_url = movie_poster(movie)
    for key, value in fields.items():
        setattr(row, key, value)
    return row


async def sync_library_trailers(db, movies: list, storage: str, config: dict, downloader=None,
                                progress: Optional[dict] = None, download_delay: float = 5.0,
                                now: Optional[datetime.datetime] = None) -> dict:
    """Bring the library trailer set in line with the settings.

    ``movies`` is Radarr's full movie list. ``downloader`` needs an async
    ``download_trailer(url, title, tmdb_id=, year=)`` returning {"path",
    "size_mb", "duration"} or None; it is only used when downloading is on.
    """
    now = now or datetime.datetime.utcnow()
    progress = progress if progress is not None else {}
    result = {"local_found": 0, "downloaded": 0, "removed": 0, "rotated": 0, "failed": 0, "candidates": 0}
    progress.setdefault("log", [])
    progress["counts"] = result

    candidates = order_candidates([m for m in movies if movie_matches(m, config, now)], config)
    wanted = {m["id"]: m for m in candidates}
    result["candidates"] = len(candidates)
    rows = db.query(models.LibraryTrailer).all()
    rows_by_movie = {r.radarr_movie_id: r for r in rows}

    # 1. Trailers already next to the movies.
    _stage(progress, "local", "Looking for trailers next to your movies...")
    local_for = {}
    if config["use_local"]:
        for index, movie in enumerate(candidates, start=1):
            if index % 50 == 0:
                progress["scanned"] = index
                await asyncio.sleep(0)  # let status requests through on a big library
            path = find_local_trailer(map_radarr_path(movie.get("path"), config["path_mappings"]))
            if path:
                local_for[movie["id"]] = path
        progress["scanned"] = len(candidates)

    # 2. Drop only what can no longer play: movies that left the library,
    #    trailer files that are gone, downloads now covered by a trailer file
    #    next to the movie, and failed attempts for movies no longer wanted.
    #    A movie that merely stopped matching the filters keeps its trailer.
    in_library = {m["id"] for m in movies if m.get("hasFile")}
    for row in list(rows_by_movie.values()):
        left_library = row.radarr_movie_id not in in_library
        superseded = row.source == "download" and row.radarr_movie_id in local_for
        file_gone = row.status == "available" and not (row.local_path and os.path.exists(row.local_path))
        stale_local = row.source == "local" and row.radarr_movie_id in wanted and row.radarr_movie_id not in local_for
        dead_attempt = row.status == "error" and row.radarr_movie_id not in wanted
        if left_library or superseded or file_gone or stale_local or dead_attempt:
            if row.status == "available":
                _event(progress, "removed", row.title, poster=row.poster_url)
                result["removed"] += 1
            remove_row(db, row, storage)
            rows_by_movie.pop(row.radarr_movie_id, None)
        else:
            row.in_selection = row.radarr_movie_id in wanted

    for movie_id, path in local_for.items():
        row = rows_by_movie.get(movie_id)
        if row is None or row.local_path != path or row.source != "local":
            _upsert(db, rows_by_movie, wanted[movie_id], source="local", status="available",
                    local_path=path, error_message=None, file_size_mb=None, in_selection=True,
                    downloaded_at=row.downloaded_at if row else now)
            result["local_found"] += 1
            _event(progress, "found", wanted[movie_id].get("title"), poster=movie_poster(wanted[movie_id]))
        else:
            _upsert(db, rows_by_movie, wanted[movie_id])
    db.commit()

    if not config["download"]:
        _stage(progress, "done", "Done")
        return result
    _stage(progress, "tidy", "Keeping downloads within your limits...")

    # 3. Downloads: keep within the limits, make room, rotate, then fill.
    #    Trailers outside the filters are always the first to go, oldest first.
    def downloads():
        return sorted((r for r in rows_by_movie.values() if r.source == "download" and r.status == "available"),
                      key=lambda r: (r.in_selection is not False, r.downloaded_at or datetime.datetime.min))

    def used_gb():
        return sum((r.file_size_mb or 0) for r in downloads()) / 1024

    def evict(row, kind):
        _event(progress, kind, row.title, poster=row.poster_url)
        remove_row(db, row, storage)
        rows_by_movie.pop(row.radarr_movie_id, None)

    while downloads() and (len(downloads()) > config["max_downloads"] or used_gb() > config["max_gb"]):
        evict(downloads()[0], "removed")
        result["removed"] += 1

    retry_before = now - datetime.timedelta(days=RETRY_ERROR_DAYS)
    # Candidates are already in priority order (always-include first).
    pool = [m for m in candidates
            if m["id"] not in rows_by_movie
            or (rows_by_movie[m["id"]].status == "error"
                and (rows_by_movie[m["id"]].last_attempt_at or datetime.datetime.min) < retry_before)]

    if pool and downloader is not None:
        # Room for movies that match: trailers outside the filters give way
        # first, as many as the new matches need.
        free = max(config["max_downloads"] - len(downloads()), 0)
        need = max(min(len(pool), config["max_downloads"]) - free, 0)
        for row in [r for r in downloads() if r.in_selection is False][:need]:
            evict(row, "replaced")
            result["rotated"] += 1
        # Then, if still full, the usual gentle rotation of matching ones -
        # except for hand-picked movies, which stay until they're unpicked.
        full = len(downloads()) >= config["max_downloads"] or used_gb() >= config["max_gb"]
        if full and config.get("mode") != "picked":
            rotate_before = now - datetime.timedelta(days=ROTATE_MIN_AGE_DAYS)
            for row in [r for r in downloads() if (r.downloaded_at or now) < rotate_before][:ROTATE_PER_SYNC]:
                evict(row, "rotated")
                result["rotated"] += 1
    db.commit()

    room = max(config["max_downloads"] - len(downloads()), 0)
    progress["to_download"] = min(room, len(pool)) if downloader is not None else 0
    progress["download_done"] = 0
    _stage(progress, "download", "Downloading trailers..." if progress["to_download"] else "Nothing new to download.")
    for movie in pool:
        if len(downloads()) >= config["max_downloads"] or used_gb() >= config["max_gb"]:
            break
        if downloader is None:
            break
        title = movie.get("title") or "Unknown"
        progress["status"] = f"Downloading trailer for {title}..."
        progress["current"] = {"title": title, "year": movie.get("year"), "poster_url": movie_poster(movie)}
        url = f"https://www.youtube.com/watch?v={movie['youTubeTrailerId']}" if movie.get("youTubeTrailerId") else None
        row = _upsert(db, rows_by_movie, movie, source="download", trailer_url=url, last_attempt_at=now, in_selection=True)
        try:
            got = await downloader.download_trailer(url, title, tmdb_id=movie.get("tmdbId"), year=movie.get("year"))
        except Exception as exc:  # the downloader reports most failures as None
            got = None
            row.error_message = str(exc)[:500]
        if got and got.get("path"):
            row.status = "available"
            row.local_path = got["path"]
            row.file_size_mb = got.get("size_mb")
            row.duration_seconds = got.get("duration")
            row.downloaded_at = now
            row.error_message = None
            result["downloaded"] += 1
            _event(progress, "downloaded", title, poster=movie_poster(movie))
        else:
            row.status = "error"
            row.error_message = row.error_message or "No trailer could be downloaded for this movie."
            result["failed"] += 1
            _event(progress, "failed", title, poster=movie_poster(movie))
        progress["download_done"] = progress.get("download_done", 0) + 1
        db.commit()
        if download_delay:
            await asyncio.sleep(download_delay)

    progress["current"] = None
    _stage(progress, "done", "Done")
    return result


def _stage(progress: dict, stage: str, status: str) -> None:
    progress["stage"] = stage
    progress["status"] = status


LOG_KEEP = 40


def _event(progress: dict, kind: str, title, poster=None) -> None:
    """Add a line to the sync's activity feed (newest first, capped)."""
    log = progress.setdefault("log", [])
    log.insert(0, {"kind": kind, "title": title or "Unknown", "poster_url": poster,
                   "at": datetime.datetime.utcnow().isoformat()})
    del log[LOG_KEEP:]


class LibraryTrailerError(Exception):
    """A reason the sync can't run, worded for the user."""


# Shared by the Sync button and the NeX-Up auto-refresh so they never overlap.
sync_progress = {"running": False, "status": "", "stage": None, "result": None, "error": None,
                 "started_at": None, "finished_at": None, "log": [], "counts": None,
                 "current": None, "to_download": 0, "download_done": 0, "scanned": 0, "candidates": 0}

# Radarr's movie list, briefly cached: the filter preview asks on every change
# and a large library is a big response.
MOVIE_CACHE_SECONDS = 120
_movie_cache = {"key": None, "at": 0.0, "movies": None}


async def fetch_movies(url: str, key: str, fresh: bool = False) -> list:
    import time
    from backend.radarr_connector import RadarrConnector
    cache_key = (url, key)
    if (not fresh and _movie_cache["key"] == cache_key and _movie_cache["movies"] is not None
            and time.monotonic() - _movie_cache["at"] < MOVIE_CACHE_SECONDS):
        return _movie_cache["movies"]
    movies = await RadarrConnector(url, key).get_all_movies_raw() or []
    _movie_cache.update(key=cache_key, at=time.monotonic(), movies=movies)
    return movies


async def fetch_tags(url: str, key: str) -> list:
    """Radarr's tags as [{"id", "label"}]; empty if they can't be read."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(f"{url.rstrip('/')}/api/v3/tag", headers={"X-Api-Key": key})
            r.raise_for_status()
            return [{"id": t.get("id"), "label": t.get("label")} for t in r.json() if t.get("id") is not None]
    except Exception:
        return []


async def run_sync(db) -> dict:
    """Sync library trailers from Radarr using the saved settings."""
    if sync_progress["running"]:
        raise LibraryTrailerError("A library trailer sync is already running.")
    setting = db.query(models.Setting).first()
    config = load_config(setting)
    if not config["enabled"]:
        raise LibraryTrailerError("Library Trailers is turned off.")
    url = getattr(setting, "nexup_radarr_url", None)
    key = getattr(setting, "nexup_radarr_api_key", None)
    storage = getattr(setting, "nexup_storage_path", None)
    if not (url and key):
        raise LibraryTrailerError("Connect Radarr under NeX-Up > Connections first.")
    if not storage:
        raise LibraryTrailerError("Set a NeX-Up storage folder in NeX-Up > Settings first.")

    sync_progress.update(running=True, stage="read", status="Reading your library from Radarr...", result=None,
                         error=None, started_at=datetime.datetime.utcnow().isoformat(), finished_at=None,
                         log=[], counts=None, current=None, to_download=0, download_done=0, scanned=0, candidates=0)
    try:
        from backend.radarr_connector import TrailerDownloader
        movies = await fetch_movies(url, key, fresh=True)
        sync_progress["candidates"] = sum(1 for m in movies if movie_matches(m, config))
        downloader = None
        if config["download"]:
            os.makedirs(library_dir(storage), exist_ok=True)
            downloader = TrailerDownloader(
                library_dir(storage),
                getattr(setting, "nexup_quality", "1080") or "1080",
                max_duration=getattr(setting, "nexup_max_trailer_duration", 0) or 0,
            )
        delay = getattr(setting, "nexup_download_delay", 5) or 0
        result = await sync_library_trailers(db, movies or [], storage, config, downloader,
                                             progress=sync_progress, download_delay=delay)
        sync_progress["result"] = result
        return result
    except LibraryTrailerError:
        raise
    except Exception as exc:
        sync_progress["error"] = str(exc)
        sync_progress["stage"] = "error"
        raise
    finally:
        sync_progress["running"] = False
        sync_progress["finished_at"] = datetime.datetime.utcnow().isoformat()
