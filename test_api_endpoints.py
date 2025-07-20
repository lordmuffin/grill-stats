#!/usr/bin/env python3
"""
Test script for API endpoints.

This script tests the various API endpoints of the Grill Stats application.
It uses the requests library to make HTTP requests to the endpoints.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pprint import pprint

import requests


def test_health_endpoint(base_url: str) -> bool:
    """Test the health check endpoint"""
    print("\n=== TESTING HEALTH ENDPOINT ===")
    response = requests.get(f"{base_url}/health")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Timestamp: {data.get('timestamp')}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_devices_endpoint(base_url: str) -> bool:
    """Test the devices endpoint"""
    print("\n=== TESTING DEVICES ENDPOINT ===")
    response = requests.get(f"{base_url}/devices")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        devices = response.json()
        print(f"Found {len(devices)} devices")

        # Print basic info about first device if available
        if devices:
            first_device = devices[0]
            print(f"Sample device: {first_device.get('name')} (ID: {first_device.get('device_id')})")
            probe_count = len(first_device.get("probes", []))
            print(f"Probe count: {probe_count}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_device_temperature_endpoint(base_url: str, device_id: str) -> bool:
    """Test the device temperature endpoint"""
    print(f"\n=== TESTING DEVICE TEMPERATURE ENDPOINT: {device_id} ===")
    response = requests.get(f"{base_url}/devices/{device_id}/temperature")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()

        # Print temperature data
        if "probes" in data:
            # Multiple probes
            print(f"Device: {data.get('device_id')}")
            print(f"Timestamp: {data.get('timestamp')}")
            print("Probe readings:")
            for probe in data.get("probes", []):
                print(f"  {probe.get('name')}: {probe.get('temperature')}°{probe.get('unit', 'F')}")
        else:
            # Single probe
            print(f"Device: {data.get('device_id')}")
            print(f"Probe: {data.get('probe_id')}")
            print(f"Temperature: {data.get('temperature')}°{data.get('unit', 'F')}")
            print(f"Timestamp: {data.get('timestamp')}")
            print(f"Battery level: {data.get('battery_level')}%")
            print(f"Signal strength: {data.get('signal_strength')} dBm")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_device_history_endpoint(base_url: str, device_id: str) -> bool:
    """Test the device history endpoint"""
    print(f"\n=== TESTING DEVICE HISTORY ENDPOINT: {device_id} ===")

    # Set time range for last 24 hours
    end_time = datetime.now().isoformat()
    start_time = (datetime.now() - timedelta(hours=24)).isoformat()

    # Make request with time range parameters
    params = {"start": start_time, "end": end_time}

    response = requests.get(f"{base_url}/devices/{device_id}/history", params=params)

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()

        # Print history data count
        data_points = data if isinstance(data, list) else []
        print(f"Retrieved {len(data_points)} historical data points")

        # Print first data point if available
        if data_points:
            first_point = data_points[0]
            print("Sample data point:")
            print(f"  Timestamp: {first_point.get('timestamp')}")
            print(f"  Temperature: {first_point.get('temperature')}°{first_point.get('unit', 'F')}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_sync_endpoint(base_url: str) -> bool:
    """Test the manual sync endpoint"""
    print("\n=== TESTING MANUAL SYNC ENDPOINT ===")
    response = requests.post(f"{base_url}/sync")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_homeassistant_endpoint(base_url: str) -> bool:
    """Test the Home Assistant connection test endpoint"""
    print("\n=== TESTING HOME ASSISTANT CONNECTION ===")
    response = requests.get(f"{base_url}/homeassistant/test")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def test_monitoring_data_endpoint(base_url: str) -> bool:
    """Test the monitoring data endpoint"""
    print("\n=== TESTING MONITORING DATA ENDPOINT ===")
    response = requests.get(f"{base_url}/api/monitoring/data")

    if response.status_code == 200:
        print(f"Status Code: {response.status_code} ✓")
        data = response.json()

        status = data.get("status")
        probe_data = data.get("data", {}).get("probes", [])

        print(f"Status: {status}")
        print(f"Retrieved {len(probe_data)} probe readings")

        # Print first probe if available
        if probe_data:
            first_probe = probe_data[0]
            print("Sample probe reading:")
            print(f"  ID: {first_probe.get('id')}")
            print(f"  Name: {first_probe.get('name')}")
            print(f"  Temperature: {first_probe.get('temperature')}°{first_probe.get('unit', 'F')}")
            print(f"  Source: {first_probe.get('source')}")
        return True
    else:
        print(f"Status Code: {response.status_code} ✗")
        print(f"Response: {response.text}")
        return False


def main() -> None:
    """Main function to run API tests"""
    import argparse

    parser = argparse.ArgumentParser(description="Test the Grill Stats API endpoints")
    parser.add_argument("--host", default="localhost", help="Server hostname or IP")
    parser.add_argument("--port", type=int, default=5001, help="Server port")
    parser.add_argument("--device", help="Specific device ID to test")

    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print(f"Testing API endpoints at {base_url}")

    # Test health endpoint
    test_health_endpoint(base_url)

    # Test devices endpoint to get device IDs
    test_devices_endpoint(base_url)

    # If specific device ID was provided, use that for testing
    device_id = args.device

    # If no device ID provided, fetch one from the devices endpoint
    if not device_id:
        try:
            response = requests.get(f"{base_url}/devices")
            if response.status_code == 200:
                devices = response.json()
                if devices:
                    # Use the first device
                    device_id = devices[0].get("device_id")
                    print(f"Using device ID: {device_id}")
        except Exception as e:
            print(f"Error fetching devices: {e}")

    # Test device-specific endpoints if we have a device ID
    if device_id:
        test_device_temperature_endpoint(base_url, device_id)
        test_device_history_endpoint(base_url, device_id)

    # Test other endpoints
    test_sync_endpoint(base_url)
    test_homeassistant_endpoint(base_url)

    # Test monitoring data endpoint
    test_monitoring_data_endpoint(base_url)

    print("\n=== API TESTS COMPLETED ===")


if __name__ == "__main__":
    main()
