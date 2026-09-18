"""Decide whether a media-server plugin is pointed somewhere it cannot reach.

The NeXroll Intros plugin runs *inside* Jellyfin or Emby and dials back to
NeXroll over HTTP. Its address is typed by a person, and `localhost:9393` is the
obvious thing to type - it is what NeXroll's own documentation and browser bar
show. It is also wrong for almost everyone: the plugin resolves `localhost`
inside the media server's own container or host, where NeXroll is not listening.

The failure is silent. The plugin stays "Active" in the server's plugin list, the
server plays no intro, and NeXroll shows a healthy connection, because nothing in
that chain is broken - the two halves simply never meet. A production install hit
exactly this: plugin Active, `NexrollUrl` set to `http://localhost:9393`, and zero
plugin check-ins, while Plex on the same NeXroll played prerolls perfectly.

NeXroll already computes the address the plugin *should* use - the one the
browser just reached it on, which is demonstrably routable. This module decides
when to apply it.
"""
from __future__ import annotations

from urllib.parse import urlparse

# Hosts that mean "this machine", which is the media server itself when the
# plugin resolves them, not NeXroll.
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]"}


def _host_of(url: str) -> str:
    try:
        return (urlparse(str(url or "").strip()).hostname or "").lower()
    except Exception:
        return ""


def is_unreachable_from_server(configured_url: str, suggested_url: str) -> bool:
    """True when the plugin's address cannot reach this NeXroll.

    Unset, or loopback while NeXroll is actually somewhere else. A loopback
    address is left alone when NeXroll genuinely is on that host, since a plugin
    running natively beside it can use it.
    """
    configured = str(configured_url or "").strip()
    if not configured:
        return True
    configured_host = _host_of(configured)
    if configured_host not in LOOPBACK_HOSTS:
        return False
    suggested_host = _host_of(suggested_url)
    if not suggested_host:
        return False
    return suggested_host not in LOOPBACK_HOSTS


def should_repair(configured_url: str, suggested_url: str, plugin_has_checked_in: bool) -> bool:
    """Whether to rewrite the plugin's address to the suggested one.

    Never touches a plugin that has checked in. A working setup is working
    whatever its address looks like from here - it may be reaching NeXroll by a
    route this process cannot see - and silently repointing it would be the more
    dangerous mistake.
    """
    if plugin_has_checked_in:
        return False
    if not str(suggested_url or "").strip():
        return False
    return is_unreachable_from_server(configured_url, suggested_url)


def describe_repair(configured_url: str, suggested_url: str) -> str:
    """One line for the log, naming both addresses."""
    shown = str(configured_url or "").strip() or "(not set)"
    return (f"Plugin was pointed at {shown}, which resolves inside the media server "
            f"rather than to NeXroll; repointed to {suggested_url}")
