#!/usr/bin/env python3
"""
Test script to verify Plex connection independently
Usage: python test_plex_connection.py
"""

import requests
import json
import os

def load_stable_token():
    """Load stable token from plex_config.json"""
    config_file = "plex_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('plex_token')
        except Exception as e:
            print(f"Error loading stable token: {e}")
    return None

def test_plex_connection(url: str, token: str = None) -> dict:
    """Test Plex connection and return detailed results"""
    print(f"Testing Plex connection to: {url}")
    print(f"Using token: {token[:10]}...")

    headers = {'X-Plex-Token': token}

    try:
        # Test basic connection
        print("\n1. Testing basic connection...")
        response = requests.get(f"{url}/", headers=headers, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            print("[SUCCESS] Basic connection successful!")
            return {
                "success": True,
                "status_code": response.status_code,
                "message": "Connection successful",
                "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
            }
        else:
            print(f"[FAILED] Connection failed with status {response.status_code}")
            return {
                "success": False,
                "status_code": response.status_code,
                "message": f"HTTP {response.status_code}",
                "response_content": response.text[:500]
            }

    except requests.exceptions.ConnectionError:
        print("[FAILED] Connection Error: Cannot reach the Plex server")
        return {
            "success": False,
            "error": "ConnectionError",
            "message": "Cannot reach the Plex server. Check if Plex is running and the URL is correct."
        }

    except requests.exceptions.Timeout:
        print("[FAILED] Timeout Error: Request timed out")
        return {
            "success": False,
            "error": "Timeout",
            "message": "Request timed out. The Plex server may be slow to respond."
        }

    except Exception as e:
        print(f"[FAILED] Unexpected Error: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

def main():
    # Test with stable token from config file
    PLEX_URL = "http://localhost:32400/"
    PLEX_TOKEN = load_stable_token()

    if not PLEX_TOKEN:
        print("ERROR: No stable token found in plex_config.json")
        print("Please run setup_plex_token.py first to configure the stable token.")
        return

    print("=" * 60)
    print("PLEX CONNECTION TEST (Using Stable Token)")
    print("=" * 60)
    print(f"Loaded stable token from plex_config.json")
    print(f"Token length: {len(PLEX_TOKEN)} characters")

    result = test_plex_connection(PLEX_URL, PLEX_TOKEN)

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    if result["success"]:
        print("SUCCESS: Plex connection is working!")
        print(f"Status: {result['status_code']}")
        print(f"Response: {result.get('response_preview', 'N/A')}")
    else:
        print("FAILED: Plex connection issue detected")
        print(f"Error: {result.get('error', 'Unknown')}")
        print(f"Message: {result['message']}")

        if "response_content" in result:
            print(f"Server Response: {result['response_content']}")

    print("\n" + "=" * 60)
    print("TROUBLESHOOTING TIPS")
    print("=" * 60)

    if not result["success"]:
        print("1. Verify Plex Media Server is running:")
        print("   - Open Plex Web App at http://localhost:32400/web")
        print("   - Check if you can access the server")

        print("\n2. Verify your stable token configuration:")
        print("   - Check that plex_config.json exists and contains a valid token")
        print("   - Run setup_plex_token.py to refresh the stable token")

        print("\n3. Check network connectivity:")
        print("   - Try accessing http://localhost:32400 in your browser")
        print("   - If using a different machine, ensure proper network access")

        print("\n4. Verify token permissions:")
        print("   - Make sure the stable token has server access permissions")
        print("   - The stable token should remain valid until you sign out of Plex")

    print("\nTest completed.")

if __name__ == "__main__":
    main()