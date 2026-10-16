AUTH_GATE_EXEMPT_EXACT = frozenset({
    "/",
    "/health",
    "/favicon.ico",
    "/manifest.json",
    "/asset-manifest.json",
    "/sw.js",
    "/robots.txt",
    "/logo192.png",
    "/logo512.png",
    "/NeXroll_Logo_BLK.png",
    "/NeXroll_Logo_WHT.png",
    "/auth/status",
    "/auth/login",
    "/auth/logout",
    "/auth/register",
    "/auth/reset-password",
})

# /plugin/ is what the Jellyfin/Emby plugins call (intros, stream, register,
# health) with their own optional API key. /jellyfin/plugin/ and /emby/plugin/
# used to be exempt too, but only NeXroll's own pages call them, and
# .../configure pushes a NeXroll URL and a fresh API key into the plugin: left
# open, anyone who could reach NeXroll could repoint the plugin at their own
# server.
AUTH_GATE_EXEMPT_PREFIXES = (
    "/static/",
    "/icons/",
    "/plugin/",
)

# Cross-origin access. NeXroll's pages are served from the same origin as the
# API, so browsers need CORS only for the routes other origins call: the
# plugin routes and the API-key /external/ routes (dashboards). Everything else
# answers its own origin, plus the development UI on port 3000.
OPEN_CORS_PREFIXES = ("/plugin/", "/external/")
DEV_UI_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")

# Headers a reverse proxy or tunnel adds. A request that carries one was
# relayed, even when the relay runs on the same machine.
FORWARDING_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
    "x-original-forwarded-for",
    "cf-connecting-ip",
    "true-client-ip",
)

_LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SAFE_CROSS_SITE_MODES = frozenset({"navigate", "no-cors"})

_NON_PERSON_USERNAMES = frozenset({
    "administrator",
    "defaultapppool",
    "localsystem",
    "networkservice",
    "nobody",
    "root",
    "system",
    "www-data",
})


def friendly_local_username(environment=None, fallback: str = "") -> str:
    """Return a human local account name, excluding common service users."""
    environment = environment or {}
    raw = environment.get("USERNAME") or environment.get("USER") or fallback or ""
    name = str(raw).strip().replace("/", "\\").split("\\")[-1]
    if not name or name.casefold() in _NON_PERSON_USERNAMES:
        return ""
    return name[:80]


def is_auth_gate_exempt(method: str, path: str) -> bool:
    return (
        method.upper() == "OPTIONS"
        or path in AUTH_GATE_EXEMPT_EXACT
        or path.startswith(AUTH_GATE_EXEMPT_PREFIXES)
    )


def is_open_cors_path(path: str) -> bool:
    return path.startswith(OPEN_CORS_PREFIXES)


def is_cross_site_blocked(method: str, path: str, headers) -> bool:
    """True for a request the browser marks as coming from another site that
    could change something or read data.

    Browsers send Sec-Fetch-Site on every request; scripts, the plugins and
    other servers don't, so they are never affected. From another site,
    following a link to NeXroll (navigate) and embedding an image or video
    (no-cors) stay allowed; a form post, or a script calling the API, is
    refused. NeXroll's own pages are same-origin, and the dev UI on port 3000
    is same-site. Without this, any page a NeXroll user opened could change
    their install while login is off. The plugin and /external/ routes are
    exempt (they take an API key), and preflights are left to CORS.
    """
    if (headers.get("sec-fetch-site") or "").lower() != "cross-site":
        return False
    if path == "/health" or is_open_cors_path(path):
        return False
    verb = method.upper()
    if verb == "OPTIONS":
        return False
    if verb in ("GET", "HEAD") and (headers.get("sec-fetch-mode") or "").lower() in _SAFE_CROSS_SITE_MODES:
        return False
    return True


def _host_name(host: str) -> str:
    value = host.strip().lower()
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def is_direct_local(client_host: str, headers) -> bool:
    """True when a request was made on this machine straight to NeXroll.

    The connecting address alone is not enough: a reverse proxy or tunnel on
    the same machine connects from 127.0.0.1 too, so every request it relays
    would look local. Relayed requests carry forwarding headers or the public
    host name; a local curl or browser sends neither.
    """
    if (client_host or "") not in _LOOPBACK_CLIENTS:
        return False
    if any(headers.get(name) is not None for name in FORWARDING_HEADERS):
        return False
    host = headers.get("host")
    if host is None or not host.strip():
        return True
    return _host_name(host) in _LOOPBACK_HOSTS
