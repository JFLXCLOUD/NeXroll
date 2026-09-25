"""Read-only, authenticated media-server probes for dashboard health."""

from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

import requests

from backend import secure_store
from backend.jellyfin_auth import jellyfin_auth_headers
from backend.jellyfin_connector import _infer_tls_verify as jellyfin_tls_verify
from backend.plex_connector import _infer_tls_verify as plex_tls_verify


def probe_server(name, url, credential):
    """Never expose URLs, credentials or request exceptions in health output."""
    def result(status, detail=""):
        return {"name": name, "status": status, "detail": detail}

    if not url:
        # Plugins report on playback/test connection, not a regular heartbeat.
        # An old registration cannot prove either an outage or current health.
        return result("warn", f"Cannot verify the {name} connection: configure its server URL and credentials in Connections")
    if not credential:
        return result("error", f"{name} credentials are missing; reconnect in Connections")

    try:
        base = url.rstrip("/")
        if name == "Plex":
            endpoint, headers, verify = base + "/", {"X-Plex-Token": credential}, plex_tls_verify(url)
        elif name == "Jellyfin":
            endpoint, headers, verify = base + "/System/Info", jellyfin_auth_headers(credential), jellyfin_tls_verify(url)
        else:
            endpoint = base + ("" if base.lower().endswith("/emby") else "/emby") + "/System/Info"
            headers, verify = {"X-Emby-Token": credential}, True
        with requests.get(endpoint, headers=headers, timeout=(3, 3),
                          verify=verify, allow_redirects=False) as response:
            if response.status_code in (401, 403):
                return result("error", f"{name} rejected its credentials; reconnect in Connections")
            if response.status_code != 200:
                return result("error", f"{name} connection failed (HTTP {response.status_code})")
            # A reverse proxy/login page returning 200 is not a media server.
            if name == "Plex":
                root = ET.fromstring(response.content)
                valid = root.tag == "MediaContainer" and bool(root.get("machineIdentifier"))
            else:
                info = response.json()
                valid = isinstance(info, dict) and bool(info.get("Id")) and bool(info.get("Version"))
            if not valid:
                return result("error", f"{name} returned an unexpected response; check its server URL")
        return result("ok")
    except requests.exceptions.SSLError:
        return result("error", f"Cannot verify the {name} server certificate")
    except requests.exceptions.RequestException:
        return result("error", f"No connection to media server ({name})")
    except (ValueError, ET.ParseError):
        return result("error", f"{name} returned an unexpected response; check its server URL or credentials")


def check_media_servers(setting, plugin_clients):
    """Resolve legacy/current credentials before probing independent servers."""
    configured = []
    for name, key_attr in (("Plex", "plex_token"), ("Jellyfin", "jellyfin_api_key"), ("Emby", "emby_api_key")):
        url = getattr(setting, name.lower() + "_url", None)
        has_plugin = any((c.get("server_type") or "").lower() == name.lower() for c in plugin_clients)
        if not url and not has_plugin:
            continue
        credential = getattr(setting, key_attr, None)
        if not credential:
            try:
                credential = getattr(secure_store, "get_" + key_attr)()
            except Exception:
                credential = None
        configured.append((name, url, credential))
    if not configured:
        return []
    # One slow/offline server must not delay checking the others in sequence.
    with ThreadPoolExecutor(max_workers=len(configured)) as pool:
        return list(pool.map(lambda args: probe_server(*args), configured))
