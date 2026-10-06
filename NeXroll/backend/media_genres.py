"""Genres, tags and file path of the item a Jellyfin or Emby server is about to play.

The NeXroll Intros plugin sends the item's id with every intros request. A
sequence block conditioned on genre, tag or file path asks here about that item.
Plex cannot take part: it plays one preroll list, set in advance, before every
movie, so there is never a "this movie" to ask about.

Lookups sit in the playback path, so they are short, cached, and only made when
the active sequence actually has a genre rule. A failed lookup returns None
("don't know"), which a condition treats as not met.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import requests

import backend.models as models
from backend import secure_store
from backend.jellyfin_auth import jellyfin_auth_headers

LOOKUP_TIMEOUT = 2.5          # seconds; the plugin itself gives up after ~5
CACHE_TTL = 6 * 60 * 60       # genres rarely change; re-ask after six hours
CACHE_MAX = 4000
GENRE_LIST_TTL = 10 * 60

_cache: dict = {}
_cache_lock = threading.Lock()
_genre_list_cache: dict = {}


def _servers(db, server_type: Optional[str]):
    """(kind, base_url, headers, items_path) for the server(s) to ask, most
    likely first. The plugin names its server type in a request header."""
    setting = db.query(models.Setting).first()
    found = []
    jf_url = getattr(setting, "jellyfin_url", None) if setting else None
    if jf_url:
        try:
            key = secure_store.get_jellyfin_api_key()
        except Exception:
            key = None
        if key:
            found.append(("jellyfin", jf_url.rstrip("/"), jellyfin_auth_headers(key), ""))
    emby_url = getattr(setting, "emby_url", None) if setting else None
    if emby_url:
        try:
            key = secure_store.get_emby_api_key()
        except Exception:
            key = None
        if key:
            found.append(("emby", emby_url.rstrip("/"), {"X-Emby-Token": key}, "/emby"))
    wanted = str(server_type or "").lower()
    found.sort(key=lambda s: 0 if s[0] == wanted else 1)
    return found


def _fetch_item(base, headers, prefix, item_id) -> Optional[dict]:
    # /Items?Ids= works on Emby and on Jellyfin 10.9+, unlike /Items/{id},
    # which Emby does not serve. Emby lists tags as TagItems; Jellyfin rejects
    # field names it doesn't know, so it is only asked for its own.
    fields = "Genres,SeriesId,ProviderIds,Tags,Path" + (",TagItems" if prefix else "")
    r = requests.get(
        f"{base}{prefix}/Items",
        params={"Ids": item_id, "Fields": fields, "Recursive": "true"},
        headers=headers,
        timeout=LOOKUP_TIMEOUT,
    )
    if r.status_code != 200:
        return None
    items = (r.json() or {}).get("Items") or []
    return items[0] if items else None


def _tags_of(item: dict) -> list:
    """Tag names from Jellyfin's Tags or Emby's TagItems, without duplicates."""
    names = [t for t in (item.get("Tags") or []) if isinstance(t, str)]
    names += [t.get("Name") for t in (item.get("TagItems") or []) if isinstance(t, dict) and isinstance(t.get("Name"), str)]
    seen = {}
    for name in names:
        if name.strip():
            seen.setdefault(name.strip().lower(), name.strip())
    return list(seen.values())


def _lookup(db, item_id: str, server_type: Optional[str]) -> Optional[dict]:
    for _kind, base, headers, prefix in _servers(db, server_type):
        try:
            item = _fetch_item(base, headers, prefix, item_id)
            if not item:
                continue
            genres = [g for g in (item.get("Genres") or []) if isinstance(g, str)]
            tags = _tags_of(item)
            # Episodes usually carry no genres or tags of their own; their series does.
            if (not genres or not tags) and item.get("SeriesId"):
                series = _fetch_item(base, headers, prefix, item["SeriesId"]) or {}
                if not genres:
                    genres = [g for g in (series.get("Genres") or []) if isinstance(g, str)]
                if not tags:
                    tags = _tags_of(series)
            ids = item.get("ProviderIds") or {}
            tmdb = next((str(v) for k, v in ids.items() if str(k).lower() == "tmdb" and v), None)
            path = item.get("Path") if isinstance(item.get("Path"), str) else None
            return {"genres": genres, "tmdb": tmdb, "tags": tags, "path": path}
        except Exception:
            continue
    return None


def item_genres(db, item_id: Optional[str], server_type: Optional[str] = None) -> Optional[list]:
    """The item's genres, [] when it has none, or None when they can't be found."""
    details = item_details(db, item_id, server_type)
    return None if details is None else details["genres"]


def item_details(db, item_id: Optional[str], server_type: Optional[str] = None) -> Optional[dict]:
    """{"genres": [...], "tmdb": "123" or None, "tags": [...], "path": str or None}
    for the item, or None when the server can't be asked."""
    item_id = str(item_id or "").strip()
    if not item_id or item_id == "0":
        return None
    key = (str(server_type or "").lower(), item_id)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    details = _lookup(db, item_id, server_type)
    if details is not None:
        with _cache_lock:
            if len(_cache) >= CACHE_MAX:
                _cache.clear()
            _cache[key] = (now, details)
    return details


def library_genres(db) -> list:
    """Every genre name the connected Jellyfin/Emby libraries use, for the
    builder's genre picker. Empty when neither is connected or reachable."""
    now = time.monotonic()
    hit = _genre_list_cache.get("all")
    if hit and now - hit[0] < GENRE_LIST_TTL:
        return hit[1]
    names = {}
    for _kind, base, headers, prefix in _servers(db, None):
        try:
            r = requests.get(f"{base}{prefix}/Genres", params={"Recursive": "true"},
                             headers=headers, timeout=6)
            if r.status_code != 200:
                continue
            for item in (r.json() or {}).get("Items") or []:
                name = str(item.get("Name") or "").strip()
                if name:
                    names.setdefault(name.lower(), name)
        except Exception:
            continue
    result = sorted(names.values(), key=str.lower)
    _genre_list_cache["all"] = (now, result)
    return result


def library_tags(db) -> list:
    """Every tag name the connected Jellyfin/Emby libraries use, for the tag
    rule's picker. Jellyfin lists them in /Items/Filters, Emby at /Tags."""
    now = time.monotonic()
    hit = _genre_list_cache.get("tags")
    if hit and now - hit[0] < GENRE_LIST_TTL:
        return hit[1]
    names = {}
    for kind, base, headers, prefix in _servers(db, None):
        try:
            if kind == "emby":
                r = requests.get(f"{base}{prefix}/Tags", params={"Recursive": "true"}, headers=headers, timeout=6)
                found = [i.get("Name") for i in ((r.json() or {}).get("Items") or [])] if r.status_code == 200 else []
            else:
                r = requests.get(f"{base}{prefix}/Items/Filters", params={"Recursive": "true"}, headers=headers, timeout=6)
                found = ((r.json() or {}).get("Tags") or []) if r.status_code == 200 else []
            for name in found:
                name = str(name or "").strip()
                if name:
                    names.setdefault(name.lower(), name)
        except Exception:
            continue
    result = sorted(names.values(), key=str.lower)
    _genre_list_cache["tags"] = (now, result)
    return result


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
    _genre_list_cache.clear()
