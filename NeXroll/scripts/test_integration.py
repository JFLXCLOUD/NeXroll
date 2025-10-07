#!/usr/bin/env python3
"""
NeXroll Integration Tests
Tests new v1.0.17 features: secure storage, diagnostics, SSE, time zones, PWA
"""

import requests
import json
import time
import sys
import os
from datetime import datetime, timezone

# Configuration
BASE_URL = "http://localhost:9393"
TIMEOUT = 10

def test_health_endpoint():
    """Test basic health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print("PASS Health endpoint working")
        return True
    except Exception as e:
        print(f"FAIL Health endpoint failed: {e}")
        return False

def test_system_version():
    """Test system version endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/system/version", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        print("PASS System version endpoint working")
        return True
    except Exception as e:
        print(f"FAIL System version endpoint failed: {e}")
        return False

def test_ffmpeg_info():
    """Test FFmpeg info endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/system/ffmpeg-info", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "ffmpeg_present" in data
        assert "ffprobe_present" in data
        print("PASS FFmpeg info endpoint working")
        return True
    except Exception as e:
        print(f"FAIL FFmpeg info endpoint failed: {e}")
        return False

def test_diagnostics_bundle():
    """Test diagnostics bundle creation"""
    try:
        response = requests.get(f"{BASE_URL}/diagnostics/bundle", timeout=TIMEOUT)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"
        assert "filename" in response.headers.get("content-disposition", "")
        print("PASS Diagnostics bundle endpoint working")
        return True
    except Exception as e:
        print(f"FAIL Diagnostics bundle endpoint failed: {e}")
        return False

def test_events_sse():
    """Test Server-Sent Events endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/events", timeout=TIMEOUT, stream=True)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Read a few events
        events_received = 0
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                    assert "type" in data
                    assert "time" in data
                    events_received += 1
                    if events_received >= 2:  # Get a couple events
                        break

        assert events_received >= 2
        print("PASS Server-Sent Events endpoint working")
        return True
    except Exception as e:
        print(f"FAIL Server-Sent Events endpoint failed: {e}")
        return False

def test_secure_token_status():
    """Test secure token status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/plex/stable-token/status", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "has_stable_token" in data
        assert "token_length" in data
        assert "provider" in data
        print("PASS Secure token status endpoint working")
        return True
    except Exception as e:
        print(f"FAIL Secure token status endpoint failed: {e}")
        return False

def test_time_format_validation():
    """Test that API returns proper ISO-8601 UTC timestamps"""
    try:
        # Test schedules endpoint for proper time formatting
        response = requests.get(f"{BASE_URL}/schedules", timeout=TIMEOUT)
        if response.status_code == 200:
            schedules = response.json()
            if schedules:  # Only test if there are schedules
                schedule = schedules[0]
                if schedule.get("start_date"):
                    # Should end with Z for UTC
                    assert schedule["start_date"].endswith("Z"), f"start_date not UTC: {schedule['start_date']}"
                    # Should be parseable as ISO format
                    datetime.fromisoformat(schedule["start_date"].replace("Z", "+00:00"))
                if schedule.get("end_date"):
                    assert schedule["end_date"].endswith("Z"), f"end_date not UTC: {schedule['end_date']}"
                    datetime.fromisoformat(schedule["end_date"].replace("Z", "+00:00"))

        print("PASS Time format validation passed")
        return True
    except Exception as e:
        print(f"FAIL Time format validation failed: {e}")
        return False

def test_scheduler_status():
    """Test scheduler status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/scheduler/status", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "active_schedules" in data
        print("PASS Scheduler status endpoint working")
        return True
    except Exception as e:
        print(f"FAIL Scheduler status endpoint failed: {e}")
        return False

def test_pwa_manifest():
    """Test PWA manifest is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/manifest.json", timeout=TIMEOUT)
        assert response.status_code == 200
        manifest = response.json()
        assert "name" in manifest
        assert "short_name" in manifest
        assert "start_url" in manifest
        assert "display" in manifest
        assert manifest["display"] == "standalone"
        print("PASS PWA manifest accessible")
        return True
    except Exception as e:
        print(f"FAIL PWA manifest test failed: {e}")
        return False

def test_service_worker():
    """Test service worker is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/sw.js", timeout=TIMEOUT)
        assert response.status_code == 200
        assert "serviceWorker" in response.text or "CACHE_NAME" in response.text
        print("PASS Service worker accessible")
        return True
    except Exception as e:
        print(f"FAIL Service worker test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("Running NeXroll v1.0.17 Integration Tests")
    print("=" * 50)

    tests = [
        test_health_endpoint,
        test_system_version,
        test_ffmpeg_info,
        test_diagnostics_bundle,
        test_events_sse,
        test_secure_token_status,
        test_time_format_validation,
        test_scheduler_status,
        test_pwa_manifest,
        test_service_worker,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"FAIL {test.__name__} crashed: {e}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("All integration tests passed!")
        return 0
    else:
        print("ERROR Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())