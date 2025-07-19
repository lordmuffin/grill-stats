import datetime
import json
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from flask import Flask
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


class TestDeviceEndpoints:
    """Test device-related endpoints"""

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["service"] == "device-service"

    def test_get_devices_without_auth(self, client):
        """Test getting devices without authentication"""
        response = client.get("/api/devices")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_get_devices_with_invalid_token(self, client):
        """Test getting devices with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/devices", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    def test_get_devices_with_valid_token(self, mock_device_manager, client, auth_token):
        """Test getting devices with valid token"""
        # Mock device manager response
        mock_device_manager.get_devices.return_value = [
            {
                "device_id": "test_device_001",
                "name": "Test Device",
                "device_type": "thermoworks",
                "configuration": {"model": "ThermoWorks Pro"},
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        ]

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/devices", headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert len(data["data"]["devices"]) == 1
        assert data["data"]["devices"][0]["device_id"] == "test_device_001"

        # Verify device manager was called with correct user_id
        mock_device_manager.get_devices.assert_called_once_with(active_only=True, user_id=1)

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_devices_with_force_refresh(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test getting devices with force refresh"""
        # Mock ThermoWorks client
        mock_device = Mock()
        mock_device.device_id = "cloud_device_001"
        mock_device.name = "Cloud Device"
        mock_device.model = "ThermoWorks Cloud"
        mock_device.firmware_version = "1.0.0"
        mock_device.probes = []
        mock_device.battery_level = 85
        mock_device.signal_strength = 95
        mock_device.last_seen = "2023-01-01T12:00:00"
        mock_device.is_online = True

        mock_thermoworks_client.token = Mock()
        mock_thermoworks_client.get_devices.return_value = [mock_device]

        # Mock device manager
        mock_device_manager.get_devices.return_value = []
        mock_device_manager.register_device.return_value = {
            "device_id": "cloud_device_001",
            "name": "Cloud Device",
            "device_type": "thermoworks",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/api/devices?force_refresh=true", headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

        # Verify ThermoWorks client was called
        mock_thermoworks_client.get_devices.assert_called_once_with(force_refresh=True)

        # Verify device was registered
        mock_device_manager.register_device.assert_called_once()

    def test_sync_without_auth(self, client):
        """Test sync endpoint without authentication"""
        response = client.post("/api/sync")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    @patch("main.thermoworks_client")
    def test_sync_without_thermoworks_auth(self, mock_thermoworks_client, client, auth_token):
        """Test sync endpoint without ThermoWorks authentication"""
        mock_thermoworks_client.token = None

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.post("/api/sync", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "thermoworks" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_sync_with_auth(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test sync endpoint with valid authentication"""
        # Mock ThermoWorks client
        mock_thermoworks_client.token = Mock()
        mock_thermoworks_client.get_devices.return_value = []

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.post("/api/sync", headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "sync started" in data["data"]["message"].lower()
        assert "timestamp" in data["data"]


class TestAuthHelpers:
    """Test authentication helper functions"""

    def test_verify_jwt_token_valid(self):
        """Test JWT token verification with valid token"""
        from main import verify_jwt_token

        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            "iat": datetime.datetime.utcnow(),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        result = verify_jwt_token(token)
        assert result is not None
        assert result["user_id"] == 1
        assert result["email"] == "test@example.com"

    def test_verify_jwt_token_expired(self):
        """Test JWT token verification with expired token"""
        from main import verify_jwt_token

        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            "iat": datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        result = verify_jwt_token(token)
        assert result is None

    def test_verify_jwt_token_invalid(self):
        """Test JWT token verification with invalid token"""
        from main import verify_jwt_token

        result = verify_jwt_token("invalid-token")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
