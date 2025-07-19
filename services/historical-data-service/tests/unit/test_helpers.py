from datetime import datetime, timezone

import pytest
from src.utils.helpers import (
    format_datetime_iso,
    format_temperature_data,
    parse_iso_datetime,
    safe_json_loads,
)


def test_parse_iso_datetime():
    """Test parsing ISO datetime strings."""
    # Test with UTC 'Z' suffix
    dt_str = "2025-07-04T12:30:45Z"
    result = parse_iso_datetime(dt_str)
    assert isinstance(result, datetime)
    assert result.year == 2025
    assert result.month == 7
    assert result.day == 4
    assert result.hour == 12
    assert result.minute == 30
    assert result.second == 45
    assert result.tzinfo is not None  # Should have timezone info

    # Test with timezone offset
    dt_str = "2025-07-04T12:30:45+02:00"
    result = parse_iso_datetime(dt_str)
    assert isinstance(result, datetime)
    assert result.year == 2025
    assert result.month == 7
    assert result.day == 4
    assert result.hour == 12
    assert result.minute == 30
    assert result.second == 45
    assert result.tzinfo is not None

    # Test with None input
    assert parse_iso_datetime(None) is None

    # Test with invalid input
    assert parse_iso_datetime("not-a-date") is None


def test_format_datetime_iso():
    """Test formatting datetimes to ISO strings."""
    # Create a timezone-aware datetime
    dt = datetime(2025, 7, 4, 12, 30, 45, tzinfo=timezone.utc)
    result = format_datetime_iso(dt)
    assert result == "2025-07-04T12:30:45+00:00"

    # Test with None input
    assert format_datetime_iso(None) is None


def test_safe_json_loads():
    """Test safely loading JSON strings."""
    # Valid JSON
    json_str = '{"key": "value", "number": 42}'
    result = safe_json_loads(json_str)
    assert result == {"key": "value", "number": 42}

    # Invalid JSON
    assert safe_json_loads("not-json") == {}

    # None input
    assert safe_json_loads(None) == {}

    # Empty string
    assert safe_json_loads("") == {}


def test_format_temperature_data():
    """Test formatting temperature reading data."""
    now = datetime.now(timezone.utc)

    # Test with datetime objects and string metadata
    readings = [
        {
            "time": now,
            "device_id": "device_001",
            "probe_id": "probe_001",
            "temperature": 225.5,
            "metadata": '{"position": "center"}',
        },
        {
            "time": now,
            "device_id": "device_002",
            "probe_id": None,  # Should be removed in the result
            "temperature": 300.0,
            "metadata": '{"position": "left"}',
        },
    ]

    result = format_temperature_data(readings)

    # First reading
    assert result[0]["time"] == now.isoformat()
    assert result[0]["device_id"] == "device_001"
    assert result[0]["probe_id"] == "probe_001"
    assert result[0]["temperature"] == 225.5
    assert result[0]["metadata"] == {"position": "center"}

    # Second reading
    assert result[1]["time"] == now.isoformat()
    assert result[1]["device_id"] == "device_002"
    assert "probe_id" not in result[1]  # None values should be removed
    assert result[1]["temperature"] == 300.0
    assert result[1]["metadata"] == {"position": "left"}

    # Test with dict metadata and no datetime
    readings = [
        {
            "device_id": "device_003",
            "temperature": 180.0,
            "metadata": {"position": "right"},
        }
    ]

    result = format_temperature_data(readings)
    assert result[0]["device_id"] == "device_003"
    assert result[0]["temperature"] == 180.0
    assert result[0]["metadata"] == {"position": "right"}
