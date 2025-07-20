#!/usr/bin/env python3
"""
Tests for Probe Management Endpoints

This module tests the probe management functionality, including listing, getting,
updating, and configuring probes.
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


class TestProbeListEndpoint:
    """Tests for the probe list endpoint"""

    def test_get_probes_without_auth(self, client):
        """Test getting probes without authentication"""
        response = client.get("/api/devices/test_device_001/probes")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_get_probes_with_invalid_token(self, client):
        """Test getting probes with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/devices/test_device_001/probes", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probes_device_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test getting probes for a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes", headers=headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probes_success(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test successful probe listing"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return a device with probes
        mock_device = Mock()
        mock_device.device_id = "test_device_001"
        mock_device.probes = [
            {"id": "1", "name": "Meat", "type": "food", "color": "red"},
            {"id": "2", "name": "Ambient", "type": "ambient", "color": "blue"},
        ]

        mock_thermoworks_client.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert len(data["data"]["probes"]) == 2
        assert data["data"]["probes"][0]["id"] == "1"
        assert data["data"]["probes"][0]["name"] == "Meat"
        assert data["data"]["probes"][1]["id"] == "2"
        assert data["data"]["probes"][1]["name"] == "Ambient"

        # Verify device_manager was called with correct parameters
        mock_device_manager.get_device.assert_called_once_with("test_device_001", user_id=1)

        # Verify thermoworks_client was called with correct parameters
        mock_thermoworks_client.get_device.assert_called_once_with("test_device_001")


class TestProbeDetailEndpoint:
    """Tests for the probe detail endpoint"""

    def test_get_probe_without_auth(self, client):
        """Test getting a probe without authentication"""
        response = client.get("/api/devices/test_device_001/probes/1")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_get_probe_with_invalid_token(self, client):
        """Test getting a probe with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/devices/test_device_001/probes/1", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probe_device_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test getting a probe for a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes/1", headers=headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probe_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test getting a probe that doesn't exist"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return a device with probes
        mock_device = Mock()
        mock_device.device_id = "test_device_001"
        mock_device.probes = [
            {"id": "1", "name": "Meat", "type": "food", "color": "red"},
            {"id": "2", "name": "Ambient", "type": "ambient", "color": "blue"},
        ]

        mock_thermoworks_client.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes/3", headers=headers)  # Probe ID 3 doesn't exist

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "probe not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probe_success(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test successful probe retrieval"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return a device with probes
        mock_device = Mock()
        mock_device.device_id = "test_device_001"
        mock_device.probes = [
            {"id": "1", "name": "Meat", "type": "food", "color": "red"},
            {"id": "2", "name": "Ambient", "type": "ambient", "color": "blue"},
        ]

        mock_thermoworks_client.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes/1", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["probe"]["id"] == "1"
        assert data["data"]["probe"]["name"] == "Meat"
        assert data["data"]["probe"]["type"] == "food"
        assert data["data"]["probe"]["color"] == "red"


class TestProbeUpdateEndpoint:
    """Tests for the probe update endpoint"""

    def test_update_probe_without_auth(self, client):
        """Test updating a probe without authentication"""
        response = client.put("/api/devices/test_device_001/probes/1")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_update_probe_with_invalid_token(self, client):
        """Test updating a probe with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.put("/api/devices/test_device_001/probes/1", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_update_probe_device_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test updating a probe for a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"name": "Updated Probe Name"}

        response = client.put("/api/devices/test_device_001/probes/1", headers=headers, json=payload)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_update_probe_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test updating a probe that doesn't exist"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return a device with probes
        mock_device = Mock()
        mock_device.device_id = "test_device_001"
        mock_device.probes = [
            {"id": "1", "name": "Meat", "type": "food", "color": "red"},
            {"id": "2", "name": "Ambient", "type": "ambient", "color": "blue"},
        ]

        mock_thermoworks_client.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"name": "Updated Probe Name"}

        response = client.put(
            "/api/devices/test_device_001/probes/3", headers=headers, json=payload  # Probe ID 3 doesn't exist
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "probe not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_update_probe_success(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test successful probe update"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {
                "probes": {
                    "1": {"name": "Meat", "color": "red", "target_temp": 200},
                    "2": {"name": "Ambient", "color": "blue"},
                }
            },
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return a device with probes
        mock_device = Mock()
        mock_device.device_id = "test_device_001"
        mock_device.probes = [
            {"id": "1", "name": "Meat", "type": "food", "color": "red"},
            {"id": "2", "name": "Ambient", "type": "ambient", "color": "blue"},
        ]

        mock_thermoworks_client.get_device.return_value = mock_device

        # Mock update_device to return updated device
        mock_device_manager.update_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {
                "probes": {
                    "1": {"name": "Brisket", "color": "green", "target_temp": 205, "high_alarm": 210, "low_alarm": 200},
                    "2": {"name": "Ambient", "color": "blue"},
                }
            },
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T12:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {"name": "Brisket", "color": "green", "target_temp": 205, "high_alarm": 210, "low_alarm": 200}

        response = client.put("/api/devices/test_device_001/probes/1", headers=headers, json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["probe"]["name"] == "Brisket"
        assert data["data"]["probe"]["color"] == "green"
        assert data["data"]["probe"]["target_temp"] == 205
        assert data["data"]["probe"]["high_alarm"] == 210
        assert data["data"]["probe"]["low_alarm"] == 200

        # Verify device_manager was called with correct parameters
        mock_device_manager.update_device.assert_called_once()
        call_args = mock_device_manager.update_device.call_args[0]
        call_kwargs = mock_device_manager.update_device.call_args[1]

        assert call_args[0] == "test_device_001"
        assert "configuration" in call_args[1]
        assert "probes" in call_args[1]["configuration"]
        assert call_args[1]["configuration"]["probes"]["1"] == payload
        assert call_kwargs["user_id"] == 1


class TestProbeTemperatureEndpoint:
    """Tests for the probe temperature endpoint"""

    def test_get_probe_temperature_without_auth(self, client):
        """Test getting probe temperature without authentication"""
        response = client.get("/api/devices/test_device_001/probes/1/temperature")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "token" in data["message"].lower()

    def test_get_probe_temperature_with_invalid_token(self, client):
        """Test getting probe temperature with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/devices/test_device_001/probes/1/temperature", headers=headers)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["status"] == "error"

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probe_temperature_device_not_found(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test getting temperature for a probe on a device that doesn't exist"""
        # Mock device manager to return None for get_device
        mock_device_manager.get_device.return_value = None

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes/1/temperature", headers=headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @patch("main.device_manager")
    @patch("main.thermoworks_client")
    def test_get_probe_temperature_success(self, mock_thermoworks_client, mock_device_manager, client, auth_token):
        """Test successful probe temperature retrieval"""
        # Mock device manager to return a device
        mock_device_manager.get_device.return_value = {
            "device_id": "test_device_001",
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        # Mock ThermoWorks client to return temperature readings
        mock_reading = Mock()
        mock_reading.device_id = "test_device_001"
        mock_reading.probe_id = "1"
        mock_reading.temperature = 225.5
        mock_reading.unit = "F"
        mock_reading.timestamp = "2025-07-20T12:00:00Z"
        mock_reading.battery_level = 85
        mock_reading.signal_strength = 92

        mock_thermoworks_client.get_device_temperature.return_value = [mock_reading]

        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/api/devices/test_device_001/probes/1/temperature", headers=headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["reading"]["device_id"] == "test_device_001"
        assert data["data"]["reading"]["probe_id"] == "1"
        assert data["data"]["reading"]["temperature"] == 225.5
        assert data["data"]["reading"]["unit"] == "F"

        # Verify device_manager was called with correct parameters
        mock_device_manager.get_device.assert_called_once_with("test_device_001", user_id=1)

        # Verify thermoworks_client was called with correct parameters
        mock_thermoworks_client.get_device_temperature.assert_called_once_with("test_device_001", probe_id="1")


if __name__ == "__main__":
    pytest.main([__file__])
