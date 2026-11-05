"""Jellyfin/Emby plugins that ask NeXroll for prerolls without an API key.

The key is optional in both plugins, so /plugin/intros answers without one,
even with login on (a security review in November 2026 flagged it: the answer
lists preroll files and signed links to them). Refusing those requests outright
would quietly stop prerolls on every server whose plugin was set up by hand
without a key, so NeXroll first says so: the Connect page and the dashboard's
health tile name each plugin that still connects without a key while login is
on, and a later version can require it.

Only /plugin/intros counts (what a playback asks, and what requiring a key
would refuse). The plugin settings page's Test button calls /plugin/health
before a key is typed in, so it would raise false alarms.

Kept in memory, like PLUGIN_CLIENTS: after a restart a plugin reappears on its
next playback. An entry goes as soon as the same server connects with a key,
or after a week without a keyless request.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

KEEP_SECONDS = 7 * 86400

_LOCK = threading.Lock()
_SEEN: dict[tuple[str, str], dict] = {}


def _server_type(value: Optional[str]) -> str:
    value = (value or "").strip()
    lowered = value.lower()
    if lowered == "jellyfin":
        return "Jellyfin"
    if lowered == "emby":
        return "Emby"
    return value[:40] or "unknown"


def _key(server_type: str, server_name: str, address: str) -> tuple[str, str]:
    # Both plugins send the machine name. Without one, tell servers apart by
    # where the request came from.
    who = (server_name or "").strip().lower() or f"@{(address or '').strip()}"
    return (server_type.lower(), who)


def note(server_type: Optional[str], server_name: Optional[str], plugin_version: Optional[str],
         address: Optional[str], now: Optional[float] = None) -> Optional[dict]:
    """Record a keyless /plugin/intros request.

    Returns the entry (a copy) for a server not on the list yet, else None,
    so the caller can log it once.
    """
    now = time.time() if now is None else now
    kind = _server_type(server_type)
    name = (server_name or "").strip()[:120]
    addr = (address or "").strip()[:64]
    key = _key(kind, name, addr)
    with _LOCK:
        entry = _SEEN.get(key)
        new = entry is None or now - entry["last_seen"] > KEEP_SECONDS
        if new:
            entry = {"server_type": kind, "server_name": name, "first_seen": now, "requests": 0}
            _SEEN[key] = entry
        entry["plugin_version"] = (plugin_version or "").strip()[:40]
        entry["address"] = addr
        entry["last_seen"] = now
        entry["requests"] += 1
        return dict(entry) if new else None


def forget(server_type: Optional[str], server_name: Optional[str], address: Optional[str] = None) -> None:
    """The server now connects with a key: drop it from the list."""
    kind = _server_type(server_type)
    name = (server_name or "").strip()
    with _LOCK:
        _SEEN.pop(_key(kind, name, address or ""), None)
        # A plugin that sent no name before still came from the same address.
        if name and address:
            _SEEN.pop(_key(kind, "", address), None)


def forget_type(server_type: Optional[str]) -> None:
    """NeXroll just saved a key into this server's plugin itself (Connect page).

    Its next request carries the key. Another keyless server of the same type,
    if there is one, is back on the list with its next request.
    """
    want = _server_type(server_type).lower()
    with _LOCK:
        for key in [k for k, v in _SEEN.items() if v["server_type"].lower() == want]:
            del _SEEN[key]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def current(server_type: Optional[str] = None, now: Optional[float] = None) -> list[dict]:
    """Plugins seen without a key in the last week, newest first."""
    now = time.time() if now is None else now
    want = _server_type(server_type).lower() if server_type else None
    with _LOCK:
        for key in [k for k, v in _SEEN.items() if now - v["last_seen"] > KEEP_SECONDS]:
            del _SEEN[key]
        rows = [dict(v) for v in _SEEN.values() if want is None or v["server_type"].lower() == want]
    rows.sort(key=lambda r: r["last_seen"], reverse=True)
    for row in rows:
        row["first_seen"] = _iso(row["first_seen"])
        row["last_seen"] = _iso(row["last_seen"])
    return rows


def seen(server_type: str, now: Optional[float] = None) -> bool:
    """Whether a plugin of this type has reached /plugin/intros without a key."""
    return bool(current(server_type, now=now))


def describe(row: dict) -> str:
    """Names the plugin in messages: 'The Jellyfin plugin on MEDIA-PC'."""
    where = row.get("server_name") or row.get("address") or ""
    return f"The {row.get('server_type') or 'media server'} plugin" + (f" on {where}" if where else "")


def reset() -> None:
    """Tests only."""
    with _LOCK:
        _SEEN.clear()
