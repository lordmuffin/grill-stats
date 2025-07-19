import json
from datetime import datetime, timedelta

import pytest
from main import app
from src.database.timescale_manager import TimescaleManager


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["service"] == "historical-data-service"
    assert "dependencies" in data
    assert "overall_status" in data


def test_store_temperature_reading(client, monkeypatch):
    """Test storing a temperature reading."""

    # Mock the TimescaleManager.store_temperature_reading method
    def mock_store_temperature_reading(self, reading):
        return True

    monkeypatch.setattr(
        TimescaleManager, "store_temperature_reading", mock_store_temperature_reading
    )

    # Test data
    data = {
        "device_id": "test_device_001",
        "probe_id": "test_probe_001",
        "grill_id": "test_grill_001",
        "temperature": 225.5,
        "unit": "F",
        "timestamp": datetime.utcnow().isoformat(),
        "battery_level": 85.0,
        "signal_strength": 90.0,
        "metadata": {"position": "center"},
    }

    response = client.post(
        "/api/temperature", data=json.dumps(data), content_type="application/json"
    )

    assert response.status_code == 200

    result = json.loads(response.data)
    assert result["status"] == "success"
    assert "message" in result


def test_store_temperature_reading_invalid_data(client):
    """Test storing an invalid temperature reading."""
    # Missing required field (temperature)
    data = {"device_id": "test_device_001"}

    response = client.post(
        "/api/temperature", data=json.dumps(data), content_type="application/json"
    )

    assert response.status_code == 400

    result = json.loads(response.data)
    assert result["status"] == "error"
    assert "message" in result


def test_store_batch_temperature_readings(client, monkeypatch):
    """Test storing batch temperature readings."""

    # Mock the TimescaleManager.store_batch_temperature_readings method
    def mock_store_batch_temperature_readings(self, readings):
        return len(readings)

    monkeypatch.setattr(
        TimescaleManager,
        "store_batch_temperature_readings",
        mock_store_batch_temperature_readings,
    )

    # Test data
    data = {
        "readings": [
            {
                "device_id": "test_device_001",
                "probe_id": "test_probe_001",
                "temperature": 225.5,
            },
            {
                "device_id": "test_device_002",
                "probe_id": "test_probe_002",
                "temperature": 300.0,
            },
        ]
    }

    response = client.post(
        "/api/temperature/batch", data=json.dumps(data), content_type="application/json"
    )

    assert response.status_code == 200

    result = json.loads(response.data)
    assert result["status"] == "success"
    assert result["stored_count"] == 2
    assert result["total_count"] == 2


def test_get_temperature_history(client, monkeypatch):
    """Test getting temperature history."""
    # Sample history data
    sample_history = [
        {
            "time": datetime.utcnow().isoformat(),
            "device_id": "test_device_001",
            "probe_id": "test_probe_001",
            "temperature": 225.5,
        },
        {
            "time": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            "device_id": "test_device_001",
            "probe_id": "test_probe_001",
            "temperature": 220.0,
        },
    ]

    # Mock the TimescaleManager.get_temperature_history method
    def mock_get_temperature_history(self, **kwargs):
        return sample_history

    monkeypatch.setattr(
        TimescaleManager, "get_temperature_history", mock_get_temperature_history
    )

    # Test the endpoint
    response = client.get(
        "/api/temperature/history?device_id=test_device_001&probe_id=test_probe_001"
    )

    assert response.status_code == 200

    result = json.loads(response.data)
    assert result["status"] == "success"
    assert "data" in result
    assert len(result["data"]) == 2
    assert result["count"] == 2
    assert "query" in result


def test_get_temperature_statistics(client, monkeypatch):
    """Test getting temperature statistics."""
    # Sample statistics data
    sample_stats = {
        "reading_count": 120,
        "avg_temperature": 225.5,
        "min_temperature": 180.0,
        "max_temperature": 275.0,
        "first_reading_time": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "last_reading_time": datetime.utcnow().isoformat(),
    }

    # Mock the TimescaleManager.get_temperature_statistics method
    def mock_get_temperature_statistics(self, **kwargs):
        return sample_stats

    monkeypatch.setattr(
        TimescaleManager, "get_temperature_statistics", mock_get_temperature_statistics
    )

    # Test the endpoint
    response = client.get(
        "/api/temperature/statistics?device_id=test_device_001&probe_id=test_probe_001"
    )

    assert response.status_code == 200

    result = json.loads(response.data)
    assert result["status"] == "success"
    assert "data" in result
    assert result["data"]["reading_count"] == 120
    assert result["data"]["avg_temperature"] == 225.5
