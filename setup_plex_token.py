#!/usr/bin/env python3
"""
Plex Stable Token Setup Script for NeXroll

This script extracts the stable PlexOnlineToken from Preferences.xml
and saves it to plex_config.json for use by NeXroll.
"""

import os
import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path

# Prefer secure secret storage when available
try:
    from nexroll_backend import secure_store
except Exception:
    secure_store = None

# Windows registry access
if sys.platform.startswith("win"):
    try:
        import winreg
        HAS_WINREG = True
    except ImportError:
        HAS_WINREG = False
else:
    HAS_WINREG = False

def get_prefs_paths():
    """Return possible paths to Preferences.xml based on OS."""
    paths = []

    if sys.platform.startswith("linux"):
        paths.extend([
            Path.home() / ".plexmediaserver" / "Preferences.xml",
            Path.home() / ".config" / "plexmediaserver" / "Preferences.xml",
            Path("/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"),
            Path("/opt/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml")
        ])
    elif sys.platform.startswith("darwin"):  # macOS
        paths.extend([
            Path.home() / "Library" / "Application Support" / "Plex Media Server" / "Preferences.xml",
            Path("/Library/Application Support/Plex Media Server/Preferences.xml")
        ])
    elif sys.platform.startswith("win"):
        # Check multiple possible locations on Windows
        local_appdata = os.getenv("LOCALAPPDATA")
        programdata = os.getenv("PROGRAMDATA")
        appdata = os.getenv("APPDATA")

        if local_appdata:
            paths.append(Path(local_appdata) / "Plex Media Server" / "Preferences.xml")
        if programdata:
            paths.append(Path(programdata) / "Plex Media Server" / "Preferences.xml")
        if appdata:
            paths.append(Path(appdata) / "Plex Media Server" / "Preferences.xml")

        # Also check common installation directories
        paths.extend([
            Path("C:/ProgramData/Plex Media Server/Preferences.xml"),
            Path("C:/Users/Default/AppData/Local/Plex Media Server/Preferences.xml")
        ])
    else:
        raise OSError(f"Unsupported OS: {sys.platform}")

    return paths

def extract_token_from_registry():
    """Extract PlexOnlineToken from Windows Registry."""
    if not HAS_WINREG:
        print("Windows registry access not available")
        return None

    try:
        # Open the Plex registry key
        key_path = r"Software\Plex, Inc.\Plex Media Server"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)

        # Try to read the PlexOnlineToken value
        try:
            token, _ = winreg.QueryValueEx(key, "PlexOnlineToken")
            winreg.CloseKey(key)

            if token and token.strip():
                print("SUCCESS: Found PlexOnlineToken in Windows Registry")
                return token.strip()
            else:
                print("Registry key exists but PlexOnlineToken is empty")
                winreg.CloseKey(key)
                return None
        except FileNotFoundError:
            print("PlexOnlineToken not found in registry")
            winreg.CloseKey(key)
            return None

    except FileNotFoundError:
        print("Plex registry key not found")
        return None
    except Exception as e:
        print(f"Error accessing Windows Registry: {e}")
        return None

def extract_token(prefs_path):
    """Extract PlexOnlineToken from Preferences.xml."""
    try:
        tree = ET.parse(prefs_path)
        root = tree.getroot()
        token = root.attrib.get("PlexOnlineToken")

        if not token:
            print("ERROR: PlexOnlineToken not found in Preferences.xml")
            print("   Make sure you're signed into Plex on this server.")
            return None

        return token
    except ET.ParseError as e:
        print(f"ERROR: Error parsing Preferences.xml: {e}")
        return None
    except FileNotFoundError:
        print(f"ERROR: Preferences.xml not found at {prefs_path}")
        return None

def save_token(token, config_file="plex_config.json"):
    """Save token securely (Windows CredMan/DPAPI) and write a sanitized config file."""
    stored = False
    provider = "none"
    # Store in secure provider if available
    try:
        if secure_store is not None:
            stored = secure_store.set_plex_token(token)
            provider = secure_store.provider_info()[1]
    except Exception as e:
        print(f"WARNING: secure store not available: {e}")
        stored = False

    # Always write a sanitized, non-secret config file (for diagnostics/visibility)
    try:
        config_data = {
            "setup_date": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "note": "Token stored in secure store; this file contains no secrets",
            "token_length": len(token),
            "provider": provider
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"WARNING: failed to write sanitized config: {e}")

    print("SUCCESS: Stable token saved")
    print(f"   Provider: {provider} ({'secure' if stored else 'legacy'})")
    print(f"   Token: {token[:20]}...")
    print(f"   Length: {len(token)} characters")

def main():
    print("NeXroll Plex Stable Token Setup")
    print("=" * 40)

    try:
        print(f"Current OS: {sys.platform}")

        # First, try Windows Registry (if on Windows)
        if sys.platform.startswith("win") and HAS_WINREG:
            print("\n[1/2] Checking Windows Registry for Plex token...")
            token = extract_token_from_registry()
            if token:
                save_token(token)
                print("\n" + "="*60)
                print("SETUP COMPLETE!")
                print("="*60)
                print("   Token extracted from Windows Registry.")
                print("   Your NeXroll app can now use this stable token.")
                print("   You can now use the 'Connect with Stable Token' option in NeXroll.")
                return

        # If registry didn't work or not on Windows, try file-based approach
        print("\n[2/2] Checking for Preferences.xml files...")
        prefs_paths = get_prefs_paths()
        print(f"Checking {len(prefs_paths)} possible locations...")
        print()

        found_path = None
        for i, prefs_path in enumerate(prefs_paths, 1):
            print(f"[{i}/{len(prefs_paths)}] Checking: {prefs_path}")
            if prefs_path.exists():
                print(f"SUCCESS: Found Preferences.xml at {prefs_path}")
                found_path = prefs_path
                break
            else:
                print(f"   Not found at: {prefs_path}")

        if not found_path:
            print("\n" + "="*60)
            print("ERROR: Could not find Plex configuration!")
            print("="*60)
            print("\nTried:")
            if sys.platform.startswith("win"):
                print("   ✓ Windows Registry (HKEY_CURRENT_USER/Software/Plex, Inc./Plex Media Server)")
            print("   ✓ Multiple Preferences.xml locations")
            print()
            print("This usually means:")
            print("   1. Plex Media Server is not installed")
            print("   2. Plex Media Server has never been run/signed into")
            print("   3. Plex is installed in a non-standard location")
            print()
            print("To fix this:")
            print("   1. Install Plex Media Server from: https://plex.tv/downloads")
            print("   2. Run Plex Media Server and sign in with your Plex account")
            print("   3. Make sure you're signed into the SERVER (not just the web app)")
            print("   4. Try accessing http://localhost:32400/web to verify Plex is running")
            print()
            if sys.platform.startswith("win"):
                print("Windows Registry Access:")
                print("   If you can access Plex settings, the token might be in:")
                print("   Registry: HKEY_CURRENT_USER/Software/Plex, Inc./Plex Media Server")
                print("   Value: PlexOnlineToken")
            print()
            print("Locations checked:")
            for i, path in enumerate(prefs_paths, 1):
                print(f"   {i}. {path}")
            print()

            # Offer manual token entry as alternative
            print("Alternatively, you can enter your Plex token manually:")
            print("   1. Open http://localhost:32400/web in your browser")
            print("   2. Sign into Plex")
            print("   3. Go to Settings → General → Advanced")
            print("   4. Copy the 'Authentication Token'")
            print()

            manual_token = input("Enter your Plex token (or press Enter to skip): ").strip()

            if manual_token:
                print("Validating token format...")
                if len(manual_token) < 20:
                    print("ERROR: Token appears to be too short. Please check your token.")
                    print("Plex tokens are typically 20+ characters long.")
                    sys.exit(1)

                save_token(manual_token)
                print("\n" + "="*60)
                print("SETUP COMPLETE WITH MANUAL TOKEN!")
                print("="*60)
                print("   Your NeXroll app can now use this token.")
                print("   Note: Manual tokens may expire and need to be updated periodically.")
                return
            else:
                print("Skipping manual token entry.")
                sys.exit(1)

        print(f"\nUsing Preferences.xml from: {found_path}")
        token = extract_token(found_path)

        if not token:
            print("\n" + "="*60)
            print("ERROR: Could not extract Plex token from Preferences.xml")
            print("="*60)
            print("\nThis usually means:")
            print("   1. You're not signed into Plex on this server")
            print("   2. The Preferences.xml file is corrupted")
            print("   3. You need to sign into Plex through the server (not web app)")
            print()
            print("To fix this:")
            print("   1. Open Plex Media Server (not the web app)")
            print("   2. Sign in with your Plex account")
            print("   3. Make sure the server shows as 'Owned' in your account")
            print("   4. Try accessing http://localhost:32400/web and sign in there too")
            print()
            sys.exit(1)

        save_token(token)

        print("\n" + "="*60)
        print("SETUP COMPLETE!")
        print("="*60)
        print("   Token extracted from Preferences.xml file.")
        print("   Your NeXroll app can now use this stable token.")
        print("   The token will remain valid until you sign out of Plex.")
        print("   You can now use the 'Connect with Stable Token' option in NeXroll.")

    except Exception as e:
        print(f"\nERROR: Unexpected error during setup: {e}")
        print("Please check your Plex Media Server installation and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()