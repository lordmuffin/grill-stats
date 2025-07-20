#!/usr/bin/env python3
"""
Tests for Device Management Endpoints

This module tests the device update, deletion, and configuration management endpoints.
"""

import datetime
import json
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from flask import Flask

# Import from main module
# Note: These imports may need adjustment based on the actual implementation
from main import JWT_ALGORITHM, JWT_SECRET, app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_token():
    """Create a valid JWT token for testing"""
    payload = {
        "user_id": 1,
        "email": "test@example.com",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TestDeviceUpdateEndpoint:
    """Tests for the device update endpoint"""

    def test_update_device_without_auth(self, client):
        """Test updating a device without authentication"""
        response = client.put("/api/devices/test_device_001")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_update_device_with_invalid_token(self, client):
        """Test updating a device with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.put("/api/devices/test_device_001", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    def test_update_device_not_found(self, mock_device_manager, client, auth_token):
        """Test updating a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"name": "Updated Device Name"}

        response = client.put("/api/devices/test_device_001", headers=headers, json=payload)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    def test_update_device_success(self, mock_device_manager, client, auth_token):
        """Test successful device update"""
        # Mock device manager to return a device and update successfully
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        mock_device_manager.update_device.return_value = {
            "device_id": "test_device_001",
            "name": "Updated Device Name",
            "device_type": "thermoworks",
            "configuration": {"setting": "value"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T12:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"name": "Updated Device Name", "configuration": {"setting": "value"}}

        response = client.put("/api/devices/test_device_001", headers=headers, json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["device"]["name"] == "Updated Device Name"
        assert data["data"]["device"]["configuration"] == {"setting": "value"}

        # Verify device_manager was called with correct parameters
        mock_device_manager.update_device.assert_called_once_with(
            "test_device_001", {"name": "Updated Device Name", "configuration": {"setting": "value"}}, user_id=1
        )

    @patch("main.device_manager")
    def test_update_device_invalid_data(self, mock_device_manager, client, auth_token):
        """Test updating a device with invalid data"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock update_device to raise a ValueError
        mock_device_manager.update_device.side_effect = ValueError("Invalid device data")

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"invalid_field": "value"}

        response = client.put("/api/devices/test_device_001", headers=headers, json=payload)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "invalid" in data["message"].lower()


class TestDeviceDeleteEndpoint:
    """Tests for the device delete endpoint"""

    def test_delete_device_without_auth(self, client):
        """Test deleting a device without authentication"""
        response = client.delete("/api/devices/test_device_001")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_delete_device_with_invalid_token(self, client):
        """Test deleting a device with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.delete("/api/devices/test_device_001", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    def test_delete_device_not_found(self, mock_device_manager, client, auth_token):
        """Test deleting a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.delete("/api/devices/test_device_001", headers=headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    def test_delete_device_success(self, mock_device_manager, client, auth_token):
        """Test successful device deletion"""
        # Mock device manager to return a device and delete successfully
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        mock_device_manager.delete_device.return_value = True

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.delete("/api/devices/test_device_001", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "deleted" in data["message"].lower()

        # Verify device_manager was called with correct parameters
        mock_device_manager.delete_device.assert_called_once_with("test_device_001", user_id=1)

    @patch("main.device_manager")
    def test_delete_device_error(self, mock_device_manager, client, auth_token):
        """Test device deletion with error"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock delete_device to raise an exception
        mock_device_manager.delete_device.side_effect = Exception("Database error")

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.delete("/api/devices/test_device_001", headers=headers)

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "delete" in data["message"].lower()


class TestDeviceConfigurationManagement:
    """Tests for device configuration management"""

    @patch("main.device_manager")
    def test_get_device_configuration(self, mock_device_manager, client, auth_token):
        """Test getting device configuration"""
        # Mock device manager to return a device with configuration
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"alert_threshold": 200, "notification_enabled": True, "display_unit": "F"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/configuration", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["configuration"] == {"alert_threshold": 200, "notification_enabled": True, "display_unit": "F"}

        # Verify device_manager was called with correct parameters
        mock_device_manager.get_device.assert_called_once_with("test_device_001", user_id=1)

    @patch("main.device_manager")
    def test_update_device_configuration(self, mock_device_manager, client, auth_token):
        """Test updating device configuration"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"alert_threshold": 200, "notification_enabled": True, "display_unit": "F"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock update_device_configuration
        mock_device_manager.update_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"alert_threshold": 220, "notification_enabled": False, "display_unit": "F"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T12:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"configuration": {"alert_threshold": 220, "notification_enabled": False}}

        response = client.put("/api/devices/test_device_001/configuration", headers=headers, json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["configuration"]["alert_threshold"] == 220
        assert data["data"]["configuration"]["notification_enabled"] is False
        assert data["data"]["configuration"]["display_unit"] == "F"

        # Verify device_manager was called with correct parameters
        mock_device_manager.update_device.assert_called_once_with(
            "test_device_001",
            {"configuration": {"alert_threshold": 220, "notification_enabled": False, "display_unit": "F"}},
            user_id=1,
        )


if __name__ == "__main__":
    pytest.main([__file__])
