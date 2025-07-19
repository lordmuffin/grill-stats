#!/usr/bin/env python3
"""
Test script for historical data service endpoints.
This script tests the new device history endpoint and other API endpoints.
"""

import json
import os
from datetime import datetime, timedelta

import jwt
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("HISTORICAL_SERVICE_URL", "http://localhost:8083")
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "your-secret-key")


def generate_test_jwt(user_id="test_user"):
    """Generate a test JWT token for authentication."""
    payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=1)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def test_health_check():
    """Test the health check endpoint."""
    print("🏥 Testing health check endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)

        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health check passed: {health_data['status']}")
            print(f"   Service: {health_data['service']}")
            print(f"   Version: {health_data['version']}")
            print(f"   Features: {health_data.get('features', {})}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_device_history():
    """Test the device history endpoint."""
    print("\n📈 Testing device history endpoint...")

    # Generate test JWT
    token = generate_test_jwt("test_user")

    # Test parameters
    device_id = "test_device_001"
    start_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    end_time = datetime.utcnow().isoformat()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    params = {"start_time": start_time, "end_time": end_time, "limit": 100}

    try:
        response = requests.get(
            f"{BASE_URL}/api/devices/{device_id}/history",
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()

            if data["status"] == "success":
                history_data = data["data"]
                print(f"✅ Device history retrieved successfully")
                print(f"   Device ID: {history_data['device_id']}")
                print(f"   Total readings: {history_data['total_readings']}")
                print(f"   Probes: {len(history_data['probes'])}")

                # Print probe details
                for probe in history_data["probes"]:
                    print(
                        f"   - Probe {probe['probe_id']}: {len(probe['readings'])} readings"
                    )

                    # Show sample reading
                    if probe["readings"]:
                        sample = probe["readings"][0]
                        print(
                            f"     Sample: {sample['temperature']}°{sample['unit']} at {sample['timestamp']}"
                        )

                return True
            else:
                print(f"❌ Device history failed: {data['message']}")
                return False

        elif response.status_code == 401:
            print("❌ Authentication failed - check JWT token")
            return False
        else:
            print(f"❌ Device history failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Device history failed: {e}")
        return False


def test_device_history_no_auth():
    """Test the device history endpoint without authentication."""
    print("\n🔒 Testing device history endpoint without authentication...")

    device_id = "test_device_001"
    start_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    end_time = datetime.utcnow().isoformat()

    params = {"start_time": start_time, "end_time": end_time, "limit": 100}

    try:
        response = requests.get(
            f"{BASE_URL}/api/devices/{device_id}/history", params=params, timeout=10
        )

        if response.status_code == 401:
            print("✅ Authentication properly required (401 Unauthorized)")
            return True
        else:
            print(f"❌ Expected 401 but got {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Test failed: {e}")
        return False


def test_device_history_with_aggregation():
    """Test the device history endpoint with data aggregation."""
    print("\n📊 Testing device history with aggregation...")

    token = generate_test_jwt("test_user")
    device_id = "test_device_001"
    start_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    end_time = datetime.utcnow().isoformat()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    params = {
        "start_time": start_time,
        "end_time": end_time,
        "aggregation": "avg",
        "interval": "1h",
        "limit": 50,
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/devices/{device_id}/history",
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()

            if data["status"] == "success":
                history_data = data["data"]
                print(f"✅ Aggregated device history retrieved successfully")
                print(f"   Total readings: {history_data['total_readings']}")
                print(f"   Aggregation: hourly averages")
                return True
            else:
                print(f"❌ Aggregated history failed: {data['message']}")
                return False
        else:
            print(f"❌ Aggregated history failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Aggregated history failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Historical Data Service Endpoint Tests")
    print("=" * 50)

    # Track test results
    tests_passed = 0
    total_tests = 0

    # Test health check
    total_tests += 1
    if test_health_check():
        tests_passed += 1

    # Test device history with authentication
    total_tests += 1
    if test_device_history():
        tests_passed += 1

    # Test device history without authentication
    total_tests += 1
    if test_device_history_no_auth():
        tests_passed += 1

    # Test device history with aggregation
    total_tests += 1
    if test_device_history_with_aggregation():
        tests_passed += 1

    # Print summary
    print("\n" + "=" * 50)
    print(f"📋 Test Summary: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("✅ All tests passed! Historical data service is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the service configuration and try again.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
