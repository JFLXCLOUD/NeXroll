import requests
import json
import os
import urllib.parse
import ipaddress
from typing import Optional
from pathlib import Path
from datetime import datetime
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
    # Fallbacks
    cands.append(os.getcwd())
    return cands


def _resolve_config_dir() -> str:
    for d in _config_dir_candidates():
        if _is_dir_writable(d):
            return d
    # Last resort
    return os.getcwd()


def _resolve_config_path() -> str:
    return os.path.join(_resolve_config_dir(), "plex_config.json")

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
    Determine whether to verify TLS certificates when talking to Plex.

    Priority:
      1) NEXROLL_PLEX_TLS_VERIFY env (1/true/on or 0/false/off)
      2) Heuristic: for https URLs pointing to private/local hosts, default False
         otherwise True.
    """
    # Explicit env override
    env = _bool_env("NEXROLL_PLEX_TLS_VERIFY", None)
    if env is not None:
        return bool(env)

    # No URL or not HTTPS -> nothing to verify
    try:
        if not url:
            return True
        u = urllib.parse.urlparse(str(url))
        if u.scheme.lower() != "https":
            return True
        host = u.hostname or ""
        # Localhost indicators
        if host in ("localhost", "127.0.0.1"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP; treat .local as mDNS/local
            if host.endswith(".local"):
                return False
    except Exception:
        return True
    return True

class PlexConnector:
    def __init__(self, url: Optional[str], token: Optional[str] = None):
        self.url = url.rstrip('/') if url else None
        self.token = token
        # Look for config file in current directory first, then parent directory
        self.config_file = self._find_config_file()
        self.headers = {}
        self._verify = _infer_tls_verify(self.url)

        # Try to load stable token from config file if no token provided
        if not token:
            self.load_stable_token()

        if self.token:
            self.headers = {'X-Plex-Token': self.token}

    def _find_config_file(self):
        """
        Resolve a writable plex_config.json path.
        Migrate legacy config from cwd/parent if present and new path missing.
        """
        new_path = _resolve_config_path()
        # Migrate legacy locations once
        try:
            legacy_cands = []
            try:
                cwd = os.getcwd()
                legacy_cands.append(os.path.join(cwd, "plex_config.json"))
                legacy_cands.append(os.path.join(os.path.dirname(cwd), "plex_config.json"))
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

    def load_stable_token(self):
        """Load stable token from secure store (preferred). Migrate from legacy plex_config.json if present."""
        try:
            # 1) Preferred: secure store
            try:
                tok = secure_store.get_plex_token()
            except Exception:
                tok = None

            if tok:
                self.token = tok
                self.headers = {'X-Plex-Token': self.token}
                print("✓ Loaded Plex token from secure store (Windows Credential Manager)")
                return True

            # 2) Legacy fallback and one-time migration from plex_config.json
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                legacy = cfg.get('plex_token')
                if legacy:
                    print(f">>> UPGRADE DETECTED: Found legacy Plex token in {self.config_file}")
                    print(f">>> MIGRATING: Moving token to secure store (Windows Credential Manager)...")
                    if secure_store.set_plex_token(legacy):
                        # Rewrite legacy file without the plaintext token
                        try:
                            cfg.pop('plex_token', None)
                            cfg['token_migrated'] = True
                            cfg['migration_date'] = datetime.utcnow().isoformat() + "Z"
                            cfg['token_length'] = len(legacy)
                            cfg.setdefault('note', 'Token migrated to secure store; file contains no secrets')
                            with open(self.config_file, 'w', encoding='utf-8') as wf:
                                json.dump(cfg, wf, indent=2)
                            print(f">>> MIGRATION SUCCESS: Token securely stored in Windows Credential Manager")
                            print(f">>> CONFIG UPDATED: Sanitized {self.config_file} (no plaintext secrets)")
                        except Exception as e:
                            print(f">>> MIGRATION WARNING: Token migrated but config rewrite failed: {e}")
                            pass
                        self.token = legacy
                        self.headers = {'X-Plex-Token': self.token}
                        return True
                    else:
                        print(f">>> MIGRATION FAILED: Could not access secure store. Token remains in {self.config_file}")
                        # Fall back to using the legacy token
                        self.token = legacy
                        self.headers = {'X-Plex-Token': self.token}
                        return True
                else:
                    print(f"ℹ No token found in {self.config_file} (already migrated or not configured)")
            else:
                print("ℹ No plex_config.json found; token should be in secure store or needs manual entry")
        except Exception as e:
            print(f"⚠ Error loading Plex token: {e}")

        return False

    def save_stable_token(self, token: str):
        """Persist token to secure store. Writes a sanitized plex_config.json without secrets for diagnostics."""
        try:
            ok = False
            try:
                ok = secure_store.set_plex_token(token)
            except Exception:
                ok = False

            if not ok:
                print("Secure store not available; refusing to write plaintext token")
                return False

            # Optionally write a sanitized config file (no secrets) for tooling/diagnostics
            try:
                cfg_dir = os.path.dirname(self.config_file) or "."
                os.makedirs(cfg_dir, exist_ok=True)
                cfg = {
                    "setup_date": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    "note": "Token saved to secure store; this file contains no secrets",
                    "token_length": len(token)
                }
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception:
                pass

            self.token = token
            self.headers = {'X-Plex-Token': self.token}
            print("Stable token saved to secure store")
            return True
        except Exception as e:
            print(f"Error saving token: {e}")
            return False

    def test_connection(self) -> bool:
        try:
            # Guard against missing/invalid URL
            if not self.url or not isinstance(self.url, str):
                return False

            # Log minimal token preview without assuming length
            token_preview = "<none>"
            try:
                if self.token:
                    token_preview = (self.token[:10] + "...") if len(self.token) > 10 else str(self.token)
            except Exception:
                token_preview = "<error>"

            print(f"Testing Plex connection to: {self.url}")
            print(f"Using token: {token_preview}")

            response = requests.get(f"{self.url}/", headers=self.headers, timeout=10, verify=self._verify)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
        except Exception:
            return False

    def get_server_info(self) -> Optional[dict]:
        """
        Return a normalized dict with Plex server info if reachable.
        Never raises; returns None on failure/missing URL.
        """
        try:
            if not self.url or not isinstance(self.url, str):
                return None

            response = requests.get(f"{self.url}/", headers=self.headers, timeout=10, verify=self._verify)
            if response.status_code == 200:
                # Parse XML response to get server info
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(response.content)
                    server_info = {
                        "connected": True,
                        "status": "OK",
                        "name": root.get('friendlyName') or 'Unknown Server',
                        "version": root.get('version') or 'Unknown',
                        "platform": root.get('platform') or 'Unknown',
                        "machine_identifier": root.get('machineIdentifier') or 'Unknown'
                    }
                    return server_info
                except Exception:
                    # If XML parse fails, still treat server as reachable
                    return {"connected": True}
            return None
        except Exception:
            return None

    def set_preroll(self, preroll_path: str) -> bool:
        """Set the preroll video in Plex server settings"""
        try:
            print(f"Attempting to set Plex preroll to: {preroll_path}")

            # Method 1: Try to set via preferences API with different approaches
            prefs_url = f"{self.url}/:/prefs"

            # First, let's try to get current preferences to understand the structure
            response = requests.get(prefs_url, headers=self.headers, timeout=10, verify=self._verify)

            if response.status_code == 200:
                print("Successfully accessed Plex preferences endpoint")

                # Parse the XML response to find preroll settings
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(response.content)

                    # Look for preroll-related preferences
                    preroll_prefs = []
                    for setting in root.findall('.//Setting'):
                        setting_id = setting.get('id', '')
                        if ('preroll' in setting_id.lower() or
                            'cinema' in setting_id.lower() or
                            'trailer' in setting_id.lower()):
                            preroll_prefs.append(setting_id)

                    print(f"Found preroll-related preferences: {preroll_prefs}")

                    # Prioritize the exact preference name from Plex settings
                    preference_names = [
                        "CinemaTrailersPrerollID",  # Exact match from user's HTML
                        "cinemaTrailersPrerollID",
                        "CinemaTrailersPreroll",
                        "cinemaTrailersPreroll",
                        "PrerollID",
                        "prerollID"
                    ]

                    # Add any discovered preferences that aren't already in our list
                    for pref in preroll_prefs:
                        if pref not in preference_names:
                            preference_names.append(pref)

                    # Remove duplicates while preserving order
                    seen = set()
                    preference_names = [x for x in preference_names if not (x in seen or seen.add(x))]

                    # Try each preference name
                    for pref_name in preference_names:
                        try:
                            print(f"Trying to set preference: {pref_name} = {preroll_path}")

                            # Method A: PUT request with query parameters (correct method per Plex API guide)
                            qval = urllib.parse.quote(preroll_path, safe=":/\\;, ")
                            set_response = requests.put(
                                f"{prefs_url}?{pref_name}={qval}",
                                headers=self.headers,
                                timeout=10,
                                verify=self._verify
                            )

                            print(f"Query param response for {pref_name}: {set_response.status_code}")
                            if set_response.status_code in [200, 201, 204]:
                                print(f"SUCCESS: Attempted to set Plex preroll using preference: {pref_name}; verifying...")
                                if self._verify_preroll_setting(pref_name, preroll_path):
                                    print(f"SUCCESS: Verified preference {pref_name} updated.")
                                    return True
                                else:
                                    print(f"WARNING: Preference {pref_name} returned {set_response.status_code} but value did not change; trying next method...")

                            # Method B: PUT request with form data (fallback)
                            set_response = requests.put(
                                prefs_url,
                                headers=self.headers,
                                data={pref_name: preroll_path},
                                timeout=10,
                                verify=self._verify
                            )

                            print(f"Form data response for {pref_name}: {set_response.status_code}")
                            if set_response.status_code in [200, 201, 204]:
                                print(f"SUCCESS: Attempted form-data set for {pref_name}; verifying...")
                                if self._verify_preroll_setting(pref_name, preroll_path):
                                    print(f"SUCCESS: Verified preference {pref_name} updated via form data.")
                                    return True
                                else:
                                    print(f"WARNING: Form-data set returned {set_response.status_code} but value did not change; trying POST...")

                            # Method C: POST request (some Plex versions use POST)
                            set_response = requests.post(
                                f"{prefs_url}?{pref_name}={preroll_path}",
                                headers=self.headers,
                                timeout=10,
                                verify=self._verify
                            )

                            print(f"POST response for {pref_name}: {set_response.status_code}")
                            if set_response.status_code in [200, 201, 204]:
                                print(f"SUCCESS: Successfully set Plex preroll using POST: {pref_name}")
                                # Verify the setting was applied
                                if self._verify_preroll_setting(pref_name, preroll_path):
                                    return True
                                else:
                                    print(f"WARNING: Setting appeared successful but verification failed for {pref_name}")
                                    continue

                        except Exception as e:
                            print(f"ERROR: Failed to set preference {pref_name}: {str(e)}")
                            continue

                    # If CinemaTrailersPrerollID is available but all methods failed, try one more time with explicit focus
                    if "CinemaTrailersPrerollID" in preroll_prefs:
                        print("INFO: Retrying with CinemaTrailersPrerollID specifically...")
                        try:
                            # Try multiple value formats for CinemaTrailersPrerollID
                            value_formats = [
                                preroll_path,  # Full path/URL
                                preroll_path.split('/')[-1] if '/' in preroll_path else preroll_path.split('\\')[-1],  # Just filename
                                "",  # Empty string to clear
                                "0"  # Some systems use 0 to disable
                            ]

                            for value in value_formats:
                                print(f"Trying CinemaTrailersPrerollID = '{value}'")

                                set_response = requests.put(
                                    f"{prefs_url}?CinemaTrailersPrerollID={value}",
                                    headers=self.headers,
                                    timeout=10
                                )

                                if set_response.status_code in [200, 201, 204]:
                                    print(f"SUCCESS: Successfully set CinemaTrailersPrerollID to: '{value}'")
                                    # Verify the setting
                                    if self._verify_preroll_setting("CinemaTrailersPrerollID", value):
                                        return True
                                    else:
                                        print("WARNING: Setting succeeded but verification failed")
                                        continue
                                else:
                                    print(f"ERROR: CinemaTrailersPrerollID='{value}' failed: {set_response.status_code}")

                        except Exception as e:
                            print(f"ERROR: CinemaTrailersPrerollID retry failed: {str(e)}")

                    print("All preference setting attempts failed")

                except ET.ParseError as e:
                    print(f"Failed to parse Plex preferences XML: {e}")

            else:
                print(f"Failed to access Plex preferences: {response.status_code}")
                print(f"Response: {response.text[:200]}")

            # Method 2: Try alternative endpoints that might handle preroll settings
            alt_endpoints = [
                "/library/preferences",
                "/system/preferences",
                "/preferences",
                "/settings/preferences"
            ]

            for endpoint in alt_endpoints:
                try:
                    alt_url = f"{self.url}{endpoint}"
                    alt_response = requests.get(alt_url, headers=self.headers, timeout=5, verify=self._verify)

                    if alt_response.status_code == 200:
                        print(f"Successfully accessed alternative endpoint: {endpoint}")
                        # Try to set preroll on this endpoint
                        set_response = requests.put(
                            f"{alt_url}?CinemaTrailersPrerollID={preroll_path}",
                            headers=self.headers,
                            timeout=5,
                            verify=self._verify
                        )

                        if set_response.status_code in [200, 201, 204]:
                            print(f"Attempted to set preroll via alternative endpoint: {endpoint}; verifying...")
                            if self._verify_preroll_setting("CinemaTrailersPrerollID", preroll_path):
                                print(f"SUCCESS: Verified update via alternative endpoint {endpoint}")
                                return True
                            else:
                                print(f"WARNING: Alternative endpoint {endpoint} returned {set_response.status_code} but value did not change")

                except Exception as e:
                    print(f"Alternative endpoint {endpoint} failed: {str(e)}")
                    continue

            # Method 3: Try to upload the preroll file to Plex and reference it
            # This is a more complex approach that would require file upload
            print("All direct preference methods failed. Preroll may need to be uploaded to Plex first.")

            # Return False to indicate failure - the preroll was not successfully set
            print("All attempts to set preroll failed")
            return False

        except requests.exceptions.Timeout:
            print("Timeout while setting Plex preroll")
            return False
        except requests.exceptions.ConnectionError:
            print("Connection error while setting Plex preroll")
            return False
        except Exception as e:
            print(f"Unexpected error setting Plex preroll: {str(e)}")
            return False

    def get_current_preroll(self) -> Optional[str]:
        """Get the current preroll setting from Plex"""
        try:
            # Query Plex's current preroll setting
            prefs_url = f"{self.url}/:/prefs"
            response = requests.get(prefs_url, headers=self.headers, timeout=10, verify=self._verify)

            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(response.content)

                    # Look for preroll-related preferences
                    preroll_prefs = [
                        "CinemaTrailersPrerollID",
                        "cinemaTrailersPrerollID",
                        "CinemaTrailersPreroll",
                        "cinemaTrailersPreroll",
                        "PrerollID",
                        "prerollID"
                    ]

                    for pref_name in preroll_prefs:
                        for setting in root.findall('.//Setting'):
                            setting_id = setting.get('id', '')
                            if setting_id == pref_name:
                                current_value = setting.get('value', '')
                                if current_value:
                                    print(f"Current Plex preroll setting ({pref_name}): {current_value}")
                                    return current_value
                                else:
                                    print(f"Plex preroll setting ({pref_name}) is empty")
                                    return ""

                    print("No preroll setting found in Plex preferences")
                    return None

                except ET.ParseError as e:
                    print(f"Failed to parse Plex preferences XML: {e}")
                    return None
            else:
                print(f"Failed to access Plex preferences: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error getting current preroll: {str(e)}")
            return None

    def _verify_preroll_setting(self, pref_name: str, expected_value: str) -> bool:
        """Verify that a preroll setting was applied correctly"""
        try:
            # Try to read back the preference to verify it was set
            prefs_url = f"{self.url}/:/prefs"
            response = requests.get(prefs_url, headers=self.headers, timeout=10, verify=self._verify)

            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(response.content)

                    # Find the specific preference
                    for setting in root.findall('.//Setting'):
                        setting_id = setting.get('id', '')
                        if setting_id == pref_name:
                            current_value = setting.get('value', '')
                            if current_value == expected_value:
                                print(f"SUCCESS: Verified {pref_name} is set to: {current_value}")
                                return True
                            else:
                                print(f"WARNING: {pref_name} is set to: {current_value}, expected: {expected_value}")
                                return False

                    print(f"WARNING: Could not find preference {pref_name} in response")
                    return False

                except ET.ParseError as e:
                    print(f"Failed to parse verification XML: {e}")
                    return False
            else:
                print(f"Failed to verify setting: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error verifying preroll setting: {str(e)}")
            return False