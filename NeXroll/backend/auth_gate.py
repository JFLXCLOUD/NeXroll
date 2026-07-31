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


def is_auth_gate_exempt(method: str, path: str) -> bool:
    return (
        method.upper() == "OPTIONS"
        or path in AUTH_GATE_EXEMPT_EXACT
        or path.startswith(AUTH_GATE_EXEMPT_PREFIXES)
    )
