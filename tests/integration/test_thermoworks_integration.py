#!/usr/bin/env python3
"""
Integration tests for ThermoWorks client with mock data service.

These tests verify that the ThermoWorks client correctly integrates with
the mock data service, ensuring proper data flow and handling of device data.
"""

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from thermoworks_client import ThermoWorksClient


class TestThermoWorksClientIntegration(unittest.TestCase):
    """Integration tests for ThermoWorks client with mock data service"""

    def setUp(self) -> None:
        """Set up the test environment"""
        # Ensure mock mode is enabled for testing
        os.environ["MOCK_MODE"] = "true"

        # Initialize the client with mock mode
        self.client = ThermoWorksClient(api_key="mock-api-key", mock_mode=True)

    def tearDown(self) -> None:
        """Clean up after tests"""
        os.environ.pop("MOCK_MODE", None)

    def test_client_initialization(self) -> None:
        """Test that the client initializes correctly in mock mode"""
        self.assertTrue(self.client.mock_mode)
        self.assertIsNotNone(self.client.mock_service)

    def test_get_devices(self) -> None:
        """Test getting devices from mock service"""
        devices = self.client.get_devices()

        # Verify we got device data
        self.assertIsInstance(devices, list)
        self.assertGreater(len(devices), 0)

        # Check device structure
        device = devices[0]
        self.assertIn("device_id", device)
        self.assertIn("name", device)
        self.assertIn("model", device)
        self.assertIn("probes", device)

    def test_get_temperature_data(self) -> None:
        """Test getting temperature data for a device"""
        # First get devices to find a valid device ID
        devices = self.client.get_devices()
        self.assertGreater(len(devices), 0)

        # Get temperature data for first device
        device_id = devices[0]["device_id"]
        temp_data = self.client.get_temperature_data(device_id)

        # Verify temperature data
        self.assertIsInstance(temp_data, dict)
        self.assertIn("device_id", temp_data)

        # Try with a specific probe
        if "probes" in devices[0] and len(devices[0]["probes"]) > 0:
            probe_id = devices[0]["probes"][0]["probe_id"]
            probe_temp_data = self.client.get_temperature_data(device_id, probe_id)

            # Verify probe-specific data
            self.assertIsInstance(probe_temp_data, dict)
            self.assertEqual(probe_temp_data.get("probe_id"), probe_id)
            self.assertIn("temperature", probe_temp_data)

    def test_get_historical_data(self) -> None:
        """Test getting historical temperature data"""
        # First get devices to find a valid device ID
        devices = self.client.get_devices()
        self.assertGreater(len(devices), 0)

        # Get a device and probe ID
        device_id = devices[0]["device_id"]
        if "probes" in devices[0] and len(devices[0]["probes"]) > 0:
            probe_id = devices[0]["probes"][0]["probe_id"]

            # Set up time range (last 24 hours)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)

            # Get historical data
            history = self.client.get_historical_data(
                device_id=device_id, start_time=start_time.isoformat(), end_time=end_time.isoformat(), probe_id=probe_id
            )

            # Verify historical data
            self.assertIsInstance(history, list)

            # If we have historical data entries, verify their structure
            if history:
                entry = history[0]
                self.assertIn("device_id", entry)
                self.assertIn("probe_id", entry)
                self.assertIn("temperature", entry)
                self.assertIn("timestamp", entry)

    def test_get_device_readings(self) -> None:
        """Test getting device readings"""
        # First get devices to find a valid device ID
        devices = self.client.get_devices()
        self.assertGreater(len(devices), 0)

        # Get device readings
        device_id = devices[0]["device_id"]
        readings = self.client.get_device_readings(device_id)

        # Verify readings data
        self.assertIsInstance(readings, dict)


if __name__ == "__main__":
    unittest.main()
