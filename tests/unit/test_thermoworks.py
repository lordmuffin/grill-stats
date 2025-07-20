#!/usr/bin/env python3
"""
Unit tests for ThermoWorks client.

These tests verify the functionality of the ThermoWorks client
including API interaction, error handling, and data processing.
"""

import unittest
from unittest.mock import MagicMock, patch

from thermoworks_client import DeviceInfo, TemperatureReading, ThermoWorksClient


class TestThermoWorksClient(unittest.TestCase):
    """Unit tests for ThermoWorks client"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.mock_session = MagicMock()

        # Create a patcher for requests.Session
        self.session_patcher = patch("thermoworks_client.requests.Session", return_value=self.mock_session)
        # Start the patcher
        self.mock_session_class = self.session_patcher.start()

        # Initialize client with a mock API key
        self.client = ThermoWorksClient(api_key="test-api-key", base_url="https://test.api.thermoworks.com", mock_mode=False)

    def tearDown(self) -> None:
        """Clean up after tests"""
        # Stop the patcher
        self.session_patcher.stop()

    def test_initialization(self) -> None:
        """Test client initialization without mock mode"""
        self.assertEqual(self.client.api_key, "test-api-key")
        self.assertEqual(self.client.base_url, "https://test.api.thermoworks.com")
        self.assertEqual(self.client.mock_mode, False)
        self.assertIsNone(self.client.mock_service)

        # Verify session headers
        self.mock_session.headers.update.assert_called_once()
        headers_arg = self.mock_session.headers.update.call_args[0][0]
        self.assertEqual(headers_arg["Authorization"], "Bearer test-api-key")
        self.assertEqual(headers_arg["Content-Type"], "application/json")

    def test_initialization_with_explicit_mock_mode(self) -> None:
        """Test client initialization with explicitly enabled mock mode"""
        # Mock the MockDataService import that would happen inside the ThermoWorksClient
        with patch.object(ThermoWorksClient, "mock_service", create=True) as mock_service:
            # Create client with explicit mock mode
            client = ThermoWorksClient(api_key="test-api-key", mock_mode=True)

            # Verify mock mode was enabled
            self.assertTrue(client.mock_mode)

    def test_get_devices(self) -> None:
        """Test getting devices"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"device_id": "device-1", "name": "Test Device 1"},
            {"device_id": "device-2", "name": "Test Device 2"},
        ]
        mock_response.raise_for_status = MagicMock()
        self.mock_session.get.return_value = mock_response

        # Call the method
        devices = self.client.get_devices()

        # Verify the request
        self.mock_session.get.assert_called_once_with("https://test.api.thermoworks.com/devices")

        # Verify the result
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["device_id"], "device-1")
        self.assertEqual(devices[1]["name"], "Test Device 2")

    def test_get_temperature_data(self) -> None:
        """Test getting temperature data"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "temperature": 165.5,
            "unit": "F",
            "timestamp": "2025-01-11T12:34:56Z",
            "battery_level": 85,
            "signal_strength": -45,
        }
        mock_response.raise_for_status = MagicMock()
        self.mock_session.get.return_value = mock_response

        # Call the method
        temp_data = self.client.get_temperature_data("device-1", "probe-1")

        # Verify the request
        self.mock_session.get.assert_called_once_with("https://test.api.thermoworks.com/devices/device-1/temperature/probe-1")

        # Verify the result
        self.assertEqual(temp_data["device_id"], "device-1")
        self.assertEqual(temp_data["probe_id"], "probe-1")
        self.assertEqual(temp_data["temperature"], 165.5)
        self.assertEqual(temp_data["unit"], "F")
        self.assertEqual(temp_data["battery_level"], 85)
        self.assertEqual(temp_data["signal_strength"], -45)

    def test_get_historical_data(self) -> None:
        """Test getting historical data"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"timestamp": "2025-01-11T10:00:00Z", "temperature": 150.0, "unit": "F"},
            {"timestamp": "2025-01-11T10:30:00Z", "temperature": 160.0, "unit": "F"},
        ]
        mock_response.raise_for_status = MagicMock()
        self.mock_session.get.return_value = mock_response

        # Call the method
        start_time = "2025-01-11T10:00:00Z"
        end_time = "2025-01-11T11:00:00Z"
        history = self.client.get_historical_data("device-1", start_time, end_time, "probe-1")

        # Verify the request
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args
        self.assertEqual(call_args[0][0], "https://test.api.thermoworks.com/devices/device-1/history")
        self.assertEqual(call_args[1]["params"], {"start": start_time, "end": end_time, "probe_id": "probe-1"})

        # Verify the result
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["timestamp"], "2025-01-11T10:00:00Z")
        self.assertEqual(history[0]["temperature"], 150.0)
        self.assertEqual(history[1]["temperature"], 160.0)

    def test_get_device_readings(self) -> None:
        """Test getting device readings"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "probes": [{"probe_id": "probe-1", "temperature": 165.5}, {"probe_id": "probe-2", "temperature": 225.0}]
        }
        mock_response.raise_for_status = MagicMock()
        self.mock_session.get.return_value = mock_response

        # Call the method
        readings = self.client.get_device_readings("device-1")

        # Verify the request
        self.mock_session.get.assert_called_once_with("https://test.api.thermoworks.com/devices/device-1/readings")

        # Verify the result
        self.assertEqual(readings["probes"][0]["probe_id"], "probe-1")
        self.assertEqual(readings["probes"][1]["temperature"], 225.0)


if __name__ == "__main__":
    unittest.main()
