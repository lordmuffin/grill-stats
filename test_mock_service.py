#!/usr/bin/env python3
"""
Test script for the enhanced mock data service.

This script simulates fetching temperature data over time and prints the results,
allowing us to see the realistic temperature patterns and cooking profiles in action.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the mock service
from services.mock_data import MockDataService

# Initialize the mock service
mock_service = MockDataService()


def print_device_info(device: dict) -> None:
    """Print detailed device information"""
    print(f"Device: {device['name']} ({device['device_id']})")
    print(f"Model: {device['model']}")
    print(f"Battery: {device['battery_level']}% | Signal: {device['signal_strength']} dBm")
    print(f"Status: {'Online' if device.get('is_online', True) else 'Offline'}")

    probes = device.get("probes", [])
    print(f"Probes: {len(probes)}")

    for probe in probes:
        print(f"  {probe['name']} ({probe['probe_id']}): {probe['current_temp']}°{probe.get('unit', 'F')}")
        print(f"    Type: {probe.get('type', 'food')}")
        if probe.get("alarm_low") is not None:
            print(f"    Alarm Range: {probe.get('alarm_low')} - {probe.get('alarm_high')}°{probe.get('unit', 'F')}")


def test_devices_list() -> None:
    """Test fetching and displaying devices list"""
    print("\n=== DEVICES LIST ===")
    devices = mock_service.get_devices()

    for device in devices:
        print_device_info(device)
        print()


def test_temperature_tracking(device_id: str, iterations: int = 10, interval: int = 5) -> None:
    """Test temperature changes over time for a specific device"""
    print(f"\n=== TEMPERATURE TRACKING: {device_id} ===")
    print(f"Monitoring temperatures for {iterations} iterations at {interval} second intervals")

    # Get initial device info
    devices = mock_service.get_devices()
    device = next((d for d in devices if d["device_id"] == device_id), None)

    if not device:
        print(f"Device {device_id} not found!")
        return

    print_device_info(device)

    # Track temperatures over time
    print("\nTemperature Changes:")
    print(f"{'Time':^20} | {'Probe':^20} | {'Temperature':^12} | {'Battery':^8} | {'Signal':^8}")
    print("-" * 75)

    for i in range(iterations):
        if i > 0:
            time.sleep(interval)

        # Get latest data
        temp_data = mock_service.get_temperature_data(device_id)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if "probes" in temp_data:
            for probe in temp_data["probes"]:
                print(
                    f"{timestamp:^20} | {probe['name']:^20} | {probe['temperature']:^12.1f} | {probe['battery_level']:^8} | {probe['signal_strength']:^8}"
                )
        else:
            # Single probe response
            print(
                f"{timestamp:^20} | {temp_data.get('name', 'Unknown'):^20} | {temp_data.get('temperature', 0):^12.1f} | {temp_data.get('battery_level', 0):^8} | {temp_data.get('signal_strength', 0):^8}"
            )


def test_historical_data(device_id: str, probe_id: str, hours: int = 24) -> None:
    """Test fetching historical data"""
    print(f"\n=== HISTORICAL DATA: {device_id}/{probe_id} ===")
    print(f"Fetching {hours} hours of historical data")

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    history = mock_service.get_historical_data(device_id, probe_id, start_time, end_time)

    print(f"Retrieved {len(history)} historical data points")

    if not history:
        print("No historical data found!")
        return

    # Print first and last few points to see the trend
    first_readings = history[:5]
    last_readings = history[-5:]

    print("\nFirst readings:")
    for reading in first_readings:
        timestamp = reading.get("timestamp", "").replace("Z", "")
        print(f"{timestamp}: {reading.get('temperature')}°{reading.get('unit', 'F')}")

    print("\n... (data points omitted) ...")

    print("\nLast readings:")
    for reading in last_readings:
        timestamp = reading.get("timestamp", "").replace("Z", "")
        print(f"{timestamp}: {reading.get('temperature')}°{reading.get('unit', 'F')}")

    # Calculate some statistics
    temps = [reading.get("temperature", 0) for reading in history]
    if temps:
        min_temp = min(temps)
        max_temp = max(temps)
        avg_temp = sum(temps) / len(temps)

        print(f"\nStatistics: Min={min_temp:.1f}°F, Max={max_temp:.1f}°F, Avg={avg_temp:.1f}°F")


def main() -> None:
    """Run tests of the mock service"""
    import argparse

    parser = argparse.ArgumentParser(description="Test the mock data service")
    parser.add_argument("device_id", nargs="?", help="Specific device ID to test")
    parser.add_argument("probe_name", nargs="?", help="Probe name or type (e.g., brisket, chicken)")
    parser.add_argument("--iterations", "-i", type=int, default=20, help="Number of temperature readings to collect")
    parser.add_argument("--interval", "-t", type=int, default=3, help="Seconds between readings")
    parser.add_argument("--hours", type=int, default=12, help="Hours of historical data to fetch")

    args = parser.parse_args()

    print("=== MOCK SERVICE TEST ===")

    # Test 1: List all devices
    test_devices_list()

    # Get device to test
    devices = mock_service.get_devices()

    # If specific device ID was provided
    if args.device_id:
        device = next((d for d in devices if d["device_id"] == args.device_id), None)
    else:
        # Use first online device
        device = next((d for d in devices if d.get("is_online", True)), None)

    if not device:
        print("No matching device found!")
        return

    # If specific probe name was provided
    probe_id = None
    if args.probe_name and device.get("probes"):
        # Find probe with matching name (case insensitive, partial match)
        probe = next((p for p in device["probes"] if args.probe_name.lower() in p["name"].lower()), None)
        if probe:
            probe_id = probe["probe_id"]

    # Test 2: Track temperatures
    test_temperature_tracking(device["device_id"], iterations=args.iterations, interval=args.interval)

    # Test 3: Historical data
    if device.get("probes"):
        # Use specified probe or first probe
        if probe_id:
            selected_probe_id = probe_id
        else:
            selected_probe_id = device["probes"][0]["probe_id"]

        test_historical_data(device["device_id"], selected_probe_id, hours=args.hours)


if __name__ == "__main__":
    main()
