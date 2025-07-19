from datetime import datetime

import pytest
from pydantic import ValidationError
from src.models.temperature_models import TemperatureQuery, TemperatureReading


def test_temperature_reading_creation():
    """Test creating a valid temperature reading model."""
    reading = TemperatureReading(
        device_id="device_001",
        probe_id="probe_001",
        grill_id="grill_001",
        temperature=225.5,
        unit="F",
        timestamp=datetime.utcnow(),
        battery_level=85.0,
        signal_strength=90.0,
        metadata={"position": "center"},
    )

    assert reading.device_id == "device_001"
    assert reading.probe_id == "probe_001"
    assert reading.grill_id == "grill_001"
    assert reading.temperature == 225.5
    assert reading.unit == "F"
    assert isinstance(reading.timestamp, datetime)
    assert reading.battery_level == 85.0
    assert reading.signal_strength == 90.0
    assert reading.metadata == {"position": "center"}


def test_temperature_reading_minimal():
    """Test creating a temperature reading with only required fields."""
    reading = TemperatureReading(device_id="device_001", temperature=225.5)

    assert reading.device_id == "device_001"
    assert reading.temperature == 225.5
    assert reading.unit == "F"  # Default value
    assert isinstance(reading.timestamp, datetime)  # Auto-generated
    assert reading.probe_id is None
    assert reading.grill_id is None
    assert reading.battery_level is None
    assert reading.signal_strength is None
    assert reading.metadata is None


def test_temperature_reading_missing_required():
    """Test that creating a reading without required fields raises an error."""
    with pytest.raises(ValidationError):
        TemperatureReading(probe_id="probe_001", temperature=225.5)

    with pytest.raises(ValidationError):
        TemperatureReading(device_id="device_001")


def test_temperature_query_creation():
    """Test creating a valid temperature query model."""
    start_time = datetime.utcnow()
    end_time = datetime.utcnow()

    query = TemperatureQuery(
        device_id="device_001",
        probe_id="probe_001",
        grill_id="grill_001",
        start_time=start_time,
        end_time=end_time,
        aggregation="avg",
        interval="1h",
        limit=100,
    )

    assert query.device_id == "device_001"
    assert query.probe_id == "probe_001"
    assert query.grill_id == "grill_001"
    assert query.start_time == start_time
    assert query.end_time == end_time
    assert query.aggregation == "avg"
    assert query.interval == "1h"
    assert query.limit == 100


def test_temperature_query_empty():
    """Test creating an empty temperature query."""
    query = TemperatureQuery()

    assert query.device_id is None
    assert query.probe_id is None
    assert query.grill_id is None
    assert query.start_time is None
    assert query.end_time is None
    assert query.aggregation is None
    assert query.interval is None
    assert query.limit is None
