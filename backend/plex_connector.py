import requests
import json
import os
from typing import Optional
from pathlib import Path

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

class PlexConnector:
    def __init__(self, url: str, token: str = None):
        self.url = url.rstrip('/') if url else None
        self.token = token
        # Look for config file in current directory first, then parent directory
        self.config_file = self._find_config_file()
        self.headers = {}

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
        """Load stable token from plex_config.json"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.token = config.get('plex_token')
                    if self.token:
                        self.headers = {'X-Plex-Token': self.token}
                        print(f"Loaded stable token from {self.config_file}")
                        return True
            else:
                print(f"No plex_config.json found. Using manual token entry.")
        except Exception as e:
            print(f"Error loading stable token: {e}")

        return False

    def save_stable_token(self, token: str):
        """Save token to a writable plex_config.json path."""
        try:
            cfg_dir = os.path.dirname(self.config_file) or "."
            os.makedirs(cfg_dir, exist_ok=True)
            config_data = {
                "plex_token": token,
                "setup_date": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "note": "This token remains valid until you sign out of Plex on this server"
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

            print(f"Stable token saved to {self.config_file}")
            self.token = token
            self.headers = {'X-Plex-Token': self.token}
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

            response = requests.get(f"{self.url}/", headers=self.headers, timeout=10)
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

            response = requests.get(f"{self.url}/", headers=self.headers, timeout=10)
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
            response = requests.get(prefs_url, headers=self.headers, timeout=10)

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
                            set_response = requests.put(
                                f"{prefs_url}?{pref_name}={preroll_path}",
                                headers=self.headers,
                                timeout=10
                            )

                            print(f"Query param response for {pref_name}: {set_response.status_code}")
                            if set_response.status_code in [200, 201, 204]:
                                print(f"SUCCESS: Successfully set Plex preroll using preference: {pref_name}")
                                return True

                            # Method B: PUT request with form data (fallback)
                            set_response = requests.put(
                                prefs_url,
                                headers=self.headers,
                                data={pref_name: preroll_path},
                                timeout=10
                            )

                            print(f"Form data response for {pref_name}: {set_response.status_code}")
                            if set_response.status_code in [200, 201, 204]:
                                print(f"SUCCESS: Successfully set Plex preroll using form data: {pref_name}")
                                return True

                            # Method C: POST request (some Plex versions use POST)
                            set_response = requests.post(
                                f"{prefs_url}?{pref_name}={preroll_path}",
                                headers=self.headers,
                                timeout=10
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
                    alt_response = requests.get(alt_url, headers=self.headers, timeout=5)

                    if alt_response.status_code == 200:
                        print(f"Successfully accessed alternative endpoint: {endpoint}")
                        # Try to set preroll on this endpoint
                        set_response = requests.put(
                            f"{alt_url}?CinemaTrailersPrerollID={preroll_path}",
                            headers=self.headers,
                            timeout=5
                        )

                        if set_response.status_code in [200, 201, 204]:
                            print(f"Successfully set preroll via alternative endpoint: {endpoint}")
                            return True

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
            response = requests.get(prefs_url, headers=self.headers, timeout=10)

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
            response = requests.get(prefs_url, headers=self.headers, timeout=10)

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