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

def get_prefs_path():
    """Return the likely path to Preferences.xml based on OS."""
    if sys.platform.startswith("linux"):
        return Path.home() / ".plexmediaserver" / "Preferences.xml"
    elif sys.platform.startswith("darwin"):  # macOS
        return Path.home() / "Library" / "Application Support" / "Plex Media Server" / "Preferences.xml"
    elif sys.platform.startswith("win"):
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise OSError("LOCALAPPDATA environment variable not found")
        return Path(local_appdata) / "Plex Media Server" / "Preferences.xml"
    else:
        raise OSError(f"Unsupported OS: {sys.platform}")

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
    """Save token to a JSON config file."""
    config_data = {
        "plex_token": token,
        "setup_date": str(Path(__file__).parent),
        "note": "This token remains valid until you sign out of Plex on this server"
    }

    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    print(f"SUCCESS: Stable token saved to {config_file}")
    print(f"   Token: {token[:20]}...")
    print(f"   Length: {len(token)} characters")

def main():
    print("NeXroll Plex Stable Token Setup")
    print("=" * 40)

    try:
        prefs_path = get_prefs_path()
        print(f"Looking for Preferences.xml at: {prefs_path}")

        if not prefs_path.exists():
            print(f"ERROR: Preferences.xml not found at {prefs_path}")
            print("\nTroubleshooting:")
            print("   1. Make sure Plex Media Server is installed and running")
            print("   2. Sign into Plex on this server (not just the web app)")
            print("   3. Check if the path is correct for your OS")
            print(f"   4. Current OS: {sys.platform}")
            sys.exit(1)

        print("SUCCESS: Found Preferences.xml")
        token = extract_token(prefs_path)

        if not token:
            sys.exit(1)

        save_token(token)

        print("\nSetup complete!")
        print("   Your NeXroll app can now use this stable token.")
        print("   The token will remain valid until you sign out of Plex.")

    except Exception as e:
        print(f"WARNING: Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()