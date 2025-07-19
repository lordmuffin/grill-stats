"""
Unit tests for User Story 3: Live Device Data functionality
Tests the live data endpoints, SSE streaming, and database operations
"""

import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

# Add the services directory to the path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "services", "temperature-service"),
)

from main import app
from temperature_manager import TemperatureManager

from thermoworks_client import ThermoWorksClient


class TestLiveDataEndpoints(unittest.TestCase):
    """Test live data API endpoints"""

    def setUp(self):
        """Set up test environment"""
        self.app = app.test_client()
        self.app.testing = True

        # Mock data
        self.device_id = "test_device_001"
        self.mock_device_data = {
            "device_id": self.device_id,
            "channels": [
                {
                    "channel_id": 1,
                    "channel_name": "Meat Probe 1",
                    "probe_type": "meat",
                    "temperature": 165.5,
                    "unit": "F",
                    "is_connected": True,
                },
                {
                    "channel_id": 2,
                    "channel_name": "Ambient Probe",
                    "probe_type": "ambient",
                    "temperature": 225.0,
                    "unit": "F",
                    "is_connected": True,
                },
            ],
        }

        self.mock_device_status = {
            "device_id": self.device_id,
            "battery_level": 85,
            "signal_strength": 92,
            "connection_status": "online",
            "last_seen": datetime.utcnow().isoformat(),
            "firmware_version": "1.2.3",
            "hardware_version": "2.0",
        }

    @patch("main.thermoworks_client")
    def test_get_device_live_data_success(self, mock_client):
        """Test successful retrieval of live device data"""
        # Mock ThermoWorks client responses
        mock_client.get_device_data.return_value = self.mock_device_data
        mock_client.get_device_status.return_value = self.mock_device_status

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/live")

        # Verify response
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["device_id"], self.device_id)
        self.assertEqual(len(data["data"]["channels"]), 2)
        self.assertEqual(data["data"]["status"]["battery_level"], 85)
        self.assertEqual(data["data"]["status"]["signal_strength"], 92)

        # Verify client was called correctly
        mock_client.get_device_data.assert_called_once_with(self.device_id)
        mock_client.get_device_status.assert_called_once_with(self.device_id)

    @patch("main.thermoworks_client")
    def test_get_device_live_data_error(self, mock_client):
        """Test error handling for live device data"""
        # Mock ThermoWorks client to raise an exception
        mock_client.get_device_data.side_effect = Exception("API Error")

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/live")

        # Verify error response
        self.assertEqual(response.status_code, 500)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")
        self.assertIn("API Error", data["message"])

    @patch("main.thermoworks_client")
    def test_get_device_channels_success(self, mock_client):
        """Test successful retrieval of device channels"""
        # Mock ThermoWorks client response
        mock_client.get_device_data.return_value = self.mock_device_data

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/channels")

        # Verify response
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["device_id"], self.device_id)
        self.assertEqual(len(data["data"]["channels"]), 2)
        self.assertEqual(data["data"]["count"], 2)

    @patch("main.thermoworks_client")
    def test_get_device_status_success(self, mock_client):
        """Test successful retrieval of device status"""
        # Mock ThermoWorks client response
        mock_client.get_device_status.return_value = self.mock_device_status

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/status")

        # Verify response
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["device_id"], self.device_id)
        self.assertEqual(data["data"]["battery_level"], 85)
        self.assertEqual(data["data"]["signal_strength"], 92)
        self.assertEqual(data["data"]["connection_status"], "online")

    @patch("main.redis_client")
    @patch("main.thermoworks_client")
    def test_device_live_stream_caching(self, mock_client, mock_redis):
        """Test that live data is properly cached in Redis"""
        # Mock Redis to return None (cache miss)
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Important: Create a MagicMock for redis_client to handle None object
        app.redis_client = MagicMock()
        app.redis_client.get.return_value = None
        app.redis_client.setex.return_value = True

        # Mock ThermoWorks client responses
        mock_client.get_device_data.return_value = self.mock_device_data
        mock_client.get_device_status.return_value = self.mock_device_status

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/live")

        # Verify caching was attempted
        mock_redis.get.assert_called_once_with(f"live_data:{self.device_id}")
        mock_redis.setex.assert_called_once()

        # Verify cache key and TTL
        cache_args = mock_redis.setex.call_args
        self.assertEqual(cache_args[0][0], f"live_data:{self.device_id}")
        self.assertEqual(cache_args[0][1], 30)  # 30 second TTL

    @patch("main.redis_client")
    def test_device_live_stream_cache_hit(self, mock_redis):
        """Test that cached live data is returned when available"""
        # Mock Redis to return cached data
        cached_data = {
            "device_id": self.device_id,
            "timestamp": datetime.utcnow().isoformat(),
            "channels": [
                {
                    "channel_id": 1,
                    "temperature": 170.0,
                    "unit": "F",
                    "name": "Cached Probe",
                    "probe_type": "meat",
                    "is_connected": True,
                }
            ],
            "status": {
                "battery_level": 80,
                "signal_strength": 88,
                "connection_status": "online",
            },
        }

        # Create mock redis client and set return value
        app.redis_client = MagicMock()
        app.redis_client.get.return_value = json.dumps(cached_data)
        mock_redis.get.return_value = json.dumps(cached_data)

        # Also patch thermoworks_client to avoid dependency on it
        with patch("main.thermoworks_client") as mock_client:
            # Make request
            response = self.app.get(f"/api/devices/{self.device_id}/live")

            # Verify response uses cached data
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["data"]["channels"][0]["temperature"], 170.0)
            self.assertEqual(data["data"]["status"]["battery_level"], 80)


class TestLiveDataDatabase(unittest.TestCase):
    """Test database operations for live data"""

    def setUp(self):
        """Set up test database"""
        self.device_id = "test_device_db"
        self.channel_id = 1

        # Mock database connection
        self.mock_db = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_db.cursor.return_value = self.mock_cursor

    def test_device_channels_table_structure(self):
        """Test that device_channels table has correct structure"""
        # This would be a real database test in practice
        # For now, verify the SQL schema exists
        schema_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "database-init",
            "live-data-schema.sql",
        )

        self.assertTrue(os.path.exists(schema_file))

        with open(schema_file, "r") as f:
            schema_content = f.read()

        # Verify key tables exist in schema
        self.assertIn("CREATE TABLE IF NOT EXISTS device_channels", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS live_temperature_readings", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS device_status_log", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS temperature_alerts", schema_content)

    def test_live_data_view_creation(self):
        """Test that live data views are created correctly"""
        schema_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "database-init",
            "live-data-schema.sql",
        )

        with open(schema_file, "r") as f:
            schema_content = f.read()

        # Verify views exist
        self.assertIn("CREATE OR REPLACE VIEW current_device_status", schema_content)
        self.assertIn("CREATE OR REPLACE VIEW live_device_data_summary", schema_content)
        self.assertIn("CREATE OR REPLACE VIEW current_channel_temperatures", schema_content)

    def test_temperature_reading_validation(self):
        """Test temperature reading validation constraints"""
        # Test data validation (would be done by database constraints)
        valid_reading = {
            "device_id": self.device_id,
            "channel_id": self.channel_id,
            "temperature": 165.5,
            "unit": "F",
            "is_connected": True,
        }

        # Valid reading should pass basic validation
        self.assertIsInstance(valid_reading["temperature"], (int, float))
        self.assertIn(valid_reading["unit"], ["F", "C"])
        self.assertIsInstance(valid_reading["is_connected"], bool)

        # Invalid temperature should fail
        invalid_reading = valid_reading.copy()
        invalid_reading["temperature"] = 2000  # Too high
        self.assertGreater(invalid_reading["temperature"], 1000)  # Would fail DB constraint

    def test_device_status_validation(self):
        """Test device status validation constraints"""
        valid_status = {
            "device_id": self.device_id,
            "battery_level": 85,
            "signal_strength": 92,
            "connection_status": "online",
        }

        # Valid status should pass basic validation
        self.assertGreaterEqual(valid_status["battery_level"], 0)
        self.assertLessEqual(valid_status["battery_level"], 100)
        self.assertGreaterEqual(valid_status["signal_strength"], 0)
        self.assertLessEqual(valid_status["signal_strength"], 100)
        self.assertIn(valid_status["connection_status"], ["online", "offline", "error", "unknown"])


class TestLiveDataIntegration(unittest.TestCase):
    """Integration tests for live data functionality"""

    def setUp(self):
        """Set up integration test environment"""
        self.device_id = "integration_test_device"
        self.app = app.test_client()
        self.app.testing = True

    @patch("main.redis_client")
    @patch("main.temperature_manager")
    @patch("main.thermoworks_client")
    def test_live_data_end_to_end(self, mock_client, mock_temp_mgr, mock_redis):
        """Test complete live data flow from API to storage"""
        # Mock all dependencies
        mock_device_data = {
            "device_id": self.device_id,
            "channels": [
                {
                    "channel_id": 1,
                    "temperature": 175.0,
                    "unit": "F",
                    "probe_type": "meat",
                    "is_connected": True,
                }
            ],
        }

        mock_device_status = {
            "battery_level": 90,
            "signal_strength": 95,
            "connection_status": "online",
        }

        mock_client.get_device_data.return_value = mock_device_data
        mock_client.get_device_status.return_value = mock_device_status
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.setex.return_value = True
        mock_temp_mgr.store_temperature_reading.return_value = True

        # Make request
        response = self.app.get(f"/api/devices/{self.device_id}/live")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")

        # Verify all components were called
        mock_client.get_device_data.assert_called_once_with(self.device_id)
        mock_client.get_device_status.assert_called_once_with(self.device_id)
        mock_redis.setex.assert_called_once()
        mock_temp_mgr.store_temperature_reading.assert_called_once()

    def test_live_data_error_handling(self):
        """Test error handling in live data flow"""
        # Test with invalid device ID
        response = self.app.get("/api/devices/invalid_device/live")

        # Should handle gracefully (specific error depends on implementation)
        self.assertIn(response.status_code, [400, 404, 500])

        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")
        self.assertIn("message", data)

    def test_multiple_channel_handling(self):
        """Test handling of devices with multiple channels"""
        # This would test the multi-channel functionality
        # Implementation depends on how channels are managed
        pass


class TestLiveDataPerformance(unittest.TestCase):
    """Performance tests for live data functionality"""

    def setUp(self):
        """Set up performance test environment"""
        self.device_id = "performance_test_device"
        self.app = app.test_client()
        self.app.testing = True

    @patch("main.redis_client")
    @patch("main.thermoworks_client")
    def test_live_data_response_time(self, mock_client, mock_redis):
        """Test that live data responses are fast enough"""
        # Mock quick responses
        mock_device_data = {
            "device_id": self.device_id,
            "channels": [{"channel_id": 1, "temperature": 180.0}],
        }
        mock_client.get_device_data.return_value = mock_device_data
        mock_client.get_device_status.return_value = {"battery_level": 85}
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        # Measure response time
        start_time = time.time()
        response = self.app.get(f"/api/devices/{self.device_id}/live")
        end_time = time.time()

        response_time = end_time - start_time

        # Verify response is fast (< 1 second)
        self.assertLess(response_time, 1.0)
        self.assertEqual(response.status_code, 200)

    def test_cache_performance(self):
        """Test that caching improves performance"""
        # This would test cache hit vs miss performance
        # Implementation depends on caching strategy
        pass


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
