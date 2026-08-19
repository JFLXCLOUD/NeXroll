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

AUTH_GATE_EXEMPT_PREFIXES = (
    "/static/",
    "/plugin/",
    "/jellyfin/plugin/",
    "/emby/plugin/",
)

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
