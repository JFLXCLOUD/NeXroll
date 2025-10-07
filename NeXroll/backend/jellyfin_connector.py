import requests
import json
import os
import urllib.parse
import ipaddress
from typing import Optional
from backend import secure_store

def _is_dir_writable(p: str) -> bool:
    try:
        os.makedirs(p, exist_ok=True)
        test = os.path.join(p, f".nexroll_cfg_test_{os.getpid()}.tmp")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        try:
            os.remove(test)
        except Exception:
            pass
        return True
    except Exception:
        return False

def _config_dir_candidates() -> list[str]:
    cands = []
    try:
        if os.name == "nt":
            pd = os.environ.get("ProgramData")
            if pd:
                cands.append(os.path.join(pd, "NeXroll"))
            la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if la:
                cands.append(os.path.join(la, "NeXroll"))
    except Exception:
        pass
    cands.append(os.getcwd())
    return cands

def _resolve_config_dir() -> str:
    for d in _config_dir_candidates():
        if _is_dir_writable(d):
            return d
    return os.getcwd()

def _resolve_config_path() -> str:
    return os.path.join(_resolve_config_dir(), "jellyfin_config.json")

def _bool_env(name: str, default=None):
    try:
        v = os.environ.get(name)
        if v is None:
            return default
        s = str(v).strip().lower()
        if s in ("1","true","yes","on"):
            return True
        if s in ("0","false","no","off"):
            return False
    except Exception:
        pass
    return default

def _infer_tls_verify(url: Optional[str]) -> bool:
    """
    Determine whether to verify TLS certificates when talking to Jellyfin.

    Priority:
      1) NEXROLL_JELLYFIN_TLS_VERIFY env (1/true/on or 0/false/off)
      2) Heuristic: for https URLs pointing to private/local hosts, default False,
         otherwise True.
    """
    env = _bool_env("NEXROLL_JELLYFIN_TLS_VERIFY", None)
    if env is not None:
        return bool(env)
    try:
        if not url:
            return True
        u = urllib.parse.urlparse(str(url))
        if u.scheme.lower() != "https":
            return True
        host = u.hostname or ""
        if host in ("localhost", "127.0.0.1"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            if host.endswith(".local"):
                return False
    except Exception:
        return True
    return True

class JellyfinConnector:
    def __init__(self, url: Optional[str], api_key: Optional[str] = None):
        self.url = url.rstrip("/") if url else None
        self.api_key = api_key
        self.config_file = self._find_config_file()
        self.headers = {}
        self._verify = _infer_tls_verify(self.url)

        if not api_key:
            self.load_stable_key()

        if self.api_key:
            self.headers = {
                "X-Emby-Token": self.api_key,
                "X-MediaBrowser-Token": self.api_key,
            }

    def _find_config_file(self) -> str:
        """
        Resolve a writable jellyfin_config.json path.
        Migrate legacy config from cwd/parent if present and new path missing.
        """
        new_path = _resolve_config_path()
        try:
            legacy_cands = []
            try:
                cwd = os.getcwd()
                legacy_cands.append(os.path.join(cwd, "jellyfin_config.json"))
                legacy_cands.append(os.path.join(os.path.dirname(cwd), "jellyfin_config.json"))
            except Exception:
                pass
            if not os.path.exists(new_path):
                for lp in legacy_cands:
                    try:
                        if lp and os.path.exists(lp):
                            os.makedirs(os.path.dirname(new_path), exist_ok=True)
                            with open(lp, "rb") as src, open(new_path, "wb") as dst:
                                dst.write(src.read())
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        return new_path

    def load_stable_key(self) -> bool:
        """Load Jellyfin API key from secure store; migrate from legacy jellyfin_config.json if present."""
        try:
            key = None
            try:
                key = secure_store.get_jellyfin_api_key()
            except Exception:
                key = None

            if key:
                self.api_key = key
                self.headers = {
                    "X-Emby-Token": self.api_key,
                    "X-MediaBrowser-Token": self.api_key,
                }
                print("Loaded Jellyfin API key from secure store")
                return True

            # Legacy fallback: json file with "api_key"
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f) or {}
                except Exception:
                    cfg = {}
                legacy = cfg.get("api_key")
                if legacy:
                    if secure_store.set_jellyfin_api_key(legacy):
                        # rewrite file sanitized
                        try:
                            cfg.pop("api_key", None)
                            cfg["token_migrated"] = True
                            cfg["token_length"] = len(legacy)
                            cfg.setdefault("note", "API key migrated to secure store; file contains no secrets")
                            with open(self.config_file, "w", encoding="utf-8") as wf:
                                json.dump(cfg, wf, indent=2)
                        except Exception:
                            pass
                        self.api_key = legacy
                        self.headers = {
                            "X-Emby-Token": self.api_key,
                            "X-MediaBrowser-Token": self.api_key,
                        }
                        print(f"Migrated Jellyfin API key from {self.config_file} to secure store")
                        return True
                else:
                    print("No API key present in legacy jellyfin_config.json")
            else:
                print("No jellyfin_config.json; expecting secure key or manual entry")
        except Exception as e:
            print(f"Error loading Jellyfin API key: {e}")
        return False

    def save_stable_key(self, api_key: str) -> bool:
        """Persist API key to secure store. Writes a sanitized jellyfin_config.json without secrets for diagnostics."""
        try:
            ok = False
            try:
                ok = secure_store.set_jellyfin_api_key(api_key)
            except Exception:
                ok = False

            if not ok:
                print("Secure store not available; refusing to write plaintext API key")
                return False

            try:
                cfg_dir = os.path.dirname(self.config_file) or "."
                os.makedirs(cfg_dir, exist_ok=True)
                cfg = {
                    "setup_date": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    "note": "API key saved to secure store; this file contains no secrets",
                    "token_length": len(api_key),
                }
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception:
                pass

            self.api_key = api_key
            self.headers = {
                "X-Emby-Token": self.api_key,
                "X-MediaBrowser-Token": self.api_key,
            }
            print("Stable Jellyfin API key saved to secure store")
            return True
        except Exception as e:
            print(f"Error saving Jellyfin API key: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Return True if the Jellyfin server is reachable (public info endpoint OK).
        """
        try:
            if not self.url or not isinstance(self.url, str):
                return False
            info_url = f"{self.url}/System/Info/Public"
            r = requests.get(info_url, timeout=10, verify=self._verify)
            if r.status_code == 200:
                return True
            # fallback: ping
            try:
                r2 = requests.get(f"{self.url}/System/Ping", timeout=5, verify=self._verify)
                return r2.status_code == 200
            except Exception:
                return False
        except Exception:
            return False

    def get_server_info(self) -> Optional[dict]:
        """
        Return a normalized dict with Jellyfin server info if reachable.
        Never raises; returns None on failure/missing URL.
        """
        try:
            if not self.url or not isinstance(self.url, str):
                return None
            info_url = f"{self.url}/System/Info/Public"
            r = requests.get(info_url, timeout=10, verify=self._verify)
            if r.status_code == 200:
                try:
                    data = r.json() if r.content else {}
                except Exception:
                    data = {}
                return {
                    "connected": True,
                    "status": "OK",
                    "name": data.get("ServerName") or "Unknown Server",
                    "version": data.get("Version") or "Unknown",
                    "product": data.get("ProductName") or "Jellyfin",
                    "operating_system": data.get("OperatingSystem") or "Unknown",
                    "id": data.get("Id") or None,
                }
            return None
        except Exception:
            return None
    def _request(self, method: str, path: str, **kwargs):
        """
        Internal helper to call Jellyfin REST with token, timeout and TLS heuristics.
        """
        if not self.url:
            raise RuntimeError("Jellyfin URL not configured")
        base = self.url.rstrip("/")
        rel = path if str(path or "").startswith("/") else f"/{path}"
        url = f"{base}{rel}"
        hdrs = dict(self.headers or {})
        user_hdrs = kwargs.pop("headers", None) or {}
        try:
            if isinstance(user_hdrs, dict):
                hdrs.update(user_hdrs)
        except Exception:
            pass
        timeout = kwargs.pop("timeout", 10)
        verify = kwargs.pop("verify", self._verify)
        return requests.request(method.upper(), url, headers=hdrs, timeout=timeout, verify=verify, **kwargs)

    def list_plugins(self) -> Optional[list]:
        """
        GET /Plugins
        Returns a list of installed plugins (or None on failure).
        """
        try:
            r = self._request("GET", "/Plugins", timeout=10)
            if getattr(r, "status_code", 0) == 200:
                try:
                    return r.json() if r.content else []
                except Exception:
                    return []
        except Exception:
            return None
        return None

    def find_plugin_by_name(self, name_substr: str) -> Optional[dict]:
        """
        Find a plugin by case-insensitive display name substring match (e.g., 'Local Intros').
        Returns the plugin dict or None if not found.
        """
        try:
            if not name_substr:
                return None
            plugins = self.list_plugins() or []
            needle = str(name_substr).strip().lower()
            for p in plugins:
                n = str((p.get("Name") or p.get("name") or "")).lower()
                if needle in n:
                    return p
            return None
        except Exception:
            return None

    def get_plugin_configuration(self, plugin_id: str) -> Optional[dict]:
        """
        GET /Plugins/{pluginId}/Configuration
        """
        try:
            if not plugin_id:
                return None
            r = self._request("GET", f"/Plugins/{plugin_id}/Configuration", timeout=10)
            if getattr(r, "status_code", 0) == 200 and getattr(r, "content", None) is not None:
                try:
                    j = r.json()
                    return j if isinstance(j, dict) else {}
                except Exception:
                    return {}
            return None
        except Exception:
            return None

    def set_plugin_configuration(self, plugin_id: str, config: dict) -> bool:
        """
        POST /Plugins/{pluginId}/Configuration
        Returns True on HTTP 200/202/204.
        """
        try:
            r = self._request("POST", f"/Plugins/{plugin_id}/Configuration", json=config, timeout=12)
            return getattr(r, "status_code", 0) in (200, 202, 204)
        except Exception:
            return False