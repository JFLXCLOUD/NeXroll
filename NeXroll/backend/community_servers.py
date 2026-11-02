"""Which Typical Nerds server NeXroll talks to.

Typical Nerds lists its file servers in servers.json, served from
https://prerolls.uk/servers.json with a copy on each server. Since late
October 2026 the list is the main server, https://prerolls.uk ("UK Server
(Fast)"), and a backup, https://home.prerolls.uk ("Home Server (Slow)").
usa.prerolls.uk is gone (it answers 503 "Server migrated") and
uk.prerolls.uk redirects to prerolls.uk.

Without a choice, NeXroll uses the first active server in the list. A server
picked under Change Server is saved as its URL. A saved prerolls.uk server the
list no longer has is set aside, not deleted: NeXroll uses the first active
server and comes back to the saved one if the list does. A URL on any other
host is the user's own mirror and is always used. When the list can't be
fetched, the saved URL is used as it is.

Each server has an "anti-spam" value, the seconds NeXroll leaves between file
downloads from it (added by Typical Nerds on November 1, 2026 so they can
tune each server, the home server being slower; the values are strings, "2"
and "5" at first). Without one the gap is 5 seconds.
"""

from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlsplit

SERVERS_JSON_URLS = (
    "https://prerolls.uk/servers.json",
    "https://home.prerolls.uk/servers.json",
)
FALLBACK_URL = "https://prerolls.uk"
OFFICIAL_DOMAIN = "prerolls.uk"
DOWNLOAD_DELAY_FIELD = "anti-spam"
DEFAULT_DOWNLOAD_DELAY = 5.0   # seconds; what Typical Nerds asked for before the field
MAX_DOWNLOAD_DELAY = 60.0


def normalize(url) -> str:
    """The URL without surrounding spaces or trailing slashes ('' for none)."""
    return str(url or "").strip().rstrip("/")


def _host(url) -> str:
    try:
        return (urlsplit(normalize(url)).hostname or "").lower()
    except ValueError:
        return ""


def same_server(a, b) -> bool:
    """True when two base URLs name the same server (scheme and host case,
    trailing slashes and a default port are ignored)."""
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return False
    try:
        sa, sb = urlsplit(a), urlsplit(b)
        return ((sa.scheme.lower(), _host(a), sa.port, sa.path.rstrip("/"))
                == (sb.scheme.lower(), _host(b), sb.port, sb.path.rstrip("/")))
    except ValueError:
        return a.lower() == b.lower()


def is_official(url) -> bool:
    """True for prerolls.uk and its subdomains, the servers Typical Nerds runs."""
    host = _host(url)
    return host == OFFICIAL_DOMAIN or host.endswith("." + OFFICIAL_DOMAIN)


def active(servers) -> list:
    """Servers marked active, in list order. A list with none marked active
    falls back to every server that has a baseUrl."""
    with_url = [s for s in (servers or []) if isinstance(s, dict) and normalize(s.get("baseUrl"))]
    marked = [s for s in with_url if str(s.get("status", "")).lower() == "active"]
    return marked or with_url


def default_url(servers) -> Optional[str]:
    """The server NeXroll uses when the user hasn't picked one."""
    servers = active(servers)
    return normalize(servers[0]["baseUrl"]) if servers else None


def find(url, servers) -> Optional[dict]:
    """The active list entry for url, if any."""
    return next((s for s in active(servers) if same_server(s.get("baseUrl"), url)), None)


def effective(saved, servers) -> tuple:
    """(URL to use, saved URL being set aside or None).

    servers is the parsed list, or None when it couldn't be fetched."""
    saved = normalize(saved)
    default = default_url(servers) or FALLBACK_URL
    if not saved:
        return default, None
    if not is_official(saved) or not active(servers) or find(saved, servers):
        return saved, None
    return default, saved


def download_delay(url, servers) -> float:
    """Seconds to leave between file downloads from url: the server's
    "anti-spam" value (a number or numeric string, 0 to 60), else 5. Custom
    mirrors and a list that couldn't be fetched get the 5 seconds too."""
    entry = find(url, servers)
    value = entry.get(DOWNLOAD_DELAY_FIELD) if entry else None
    if isinstance(value, bool):
        return DEFAULT_DOWNLOAD_DELAY
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DOWNLOAD_DELAY
    if seconds != seconds:  # NaN
        return DEFAULT_DOWNLOAD_DELAY
    return min(max(seconds, 0.0), MAX_DOWNLOAD_DELAY)


def parse(payload) -> Optional[list]:
    """The server list from a servers.json body, or None if it has none."""
    servers = payload.get("servers") if isinstance(payload, dict) else None
    if not isinstance(servers, list) or not active(servers):
        return None
    return servers


def fetch(get: Callable, headers: dict, urls=SERVERS_JSON_URLS, timeout: float = 10) -> tuple:
    """(servers, source URL) from the first copy of servers.json that answers
    with a usable list, else (None, None). get is requests.get or a stand-in."""
    for url in urls:
        try:
            resp = get(url, timeout=timeout, headers=headers)
            if not getattr(resp, "ok", False):
                continue
            servers = parse(resp.json())
            if servers:
                return servers, url
        except Exception:
            continue
    return None, None
