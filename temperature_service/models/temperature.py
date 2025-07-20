"""
Temperature data models using Pydantic for validation.

These models represent the core data structures for temperature readings,
alerts, and device status information.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class TemperatureUnit(str, Enum):
    """Temperature units."""

    FAHRENHEIT = "F"
    CELSIUS = "C"
    KELVIN = "K"


class DeviceStatus(str, Enum):
    """Device connection status."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ProbeType(str, Enum):
    """Types of temperature probes."""

    MEAT = "meat"
    AMBIENT = "ambient"
    GRILL = "grill"
    FOOD = "food"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of temperature alerts."""

    HIGH_TEMPERATURE = "high_temperature"
    LOW_TEMPERATURE = "low_temperature"
    RAPID_CHANGE = "rapid_change"
    CONNECTION_LOST = "connection_lost"
    BATTERY_LOW = "battery_low"
    SIGNAL_WEAK = "signal_weak"
    TARGET_REACHED = "target_reached"
    ANOMALY = "anomaly"


class TemperatureReading(BaseModel):
    """Temperature reading data model."""

    # Core fields
    device_id: str
    temperature: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional fields
    probe_id: Optional[str] = None
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("temperature")
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature range is reasonable."""
        if v < -100 or v > 1000:
            raise ValueError(f"Temperature {v} is outside reasonable range (-100 to 1000)")
        return v

    @validator("battery_level")
    def validate_battery_level(cls, v: Optional[int]) -> Optional[int]:
        """Validate battery level range."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Battery level {v} must be between 0 and 100")
        return v

    @validator("signal_strength")
    def validate_signal_strength(cls, v: Optional[int]) -> Optional[int]:
        """Validate signal strength range."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Signal strength {v} must be between 0 and 100")
        return v

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}


class BatchTemperatureReadings(BaseModel):
    """Batch of temperature readings."""

    readings: List[TemperatureReading]


class TemperatureAlert(BaseModel):
    """Temperature alert data model."""

    # Core fields
    device_id: str
    alert_id: str = Field(default_factory=lambda: f"alert_{datetime.utcnow().timestamp()}")
    alert_type: AlertType
    severity: AlertSeverity
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Alert details
    temperature: Optional[float] = None
    probe_id: Optional[str] = None
    threshold: Optional[float] = None
    message: str

    # State tracking
    acknowledged: bool = False
    resolved: bool = False
    resolved_timestamp: Optional[datetime] = None

    # Related readings
    related_readings: List[Dict[str, Any]] = Field(default_factory=list)


class TemperatureStatistics(BaseModel):
    """Temperature statistics data model."""

    # Identifiers
    device_id: str
    probe_id: Optional[str] = None

    # Time range
    start_time: datetime
    end_time: datetime

    # Statistics
    count: int = 0
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    avg_temperature: Optional[float] = None
    median_temperature: Optional[float] = None
    stddev_temperature: Optional[float] = None

    # Unit
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT


class DeviceChannelStatus(BaseModel):
    """Status information for a specific device channel/probe."""

    channel_id: str
    name: str
    probe_type: ProbeType = ProbeType.MEAT
    temperature: Optional[float] = None
    unit: TemperatureUnit = TemperatureUnit.FAHRENHEIT
    is_connected: bool = True
    last_reading: Optional[datetime] = None
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    target_temp: Optional[float] = None


class DeviceLiveData(BaseModel):
    """Live data for a device including all channels and status."""

    # Device identification
    device_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Channels (probes)
    channels: List[DeviceChannelStatus] = Field(default_factory=list)

    # Device status
    status: Dict[str, Any] = Field(
        default_factory=lambda: {
            "battery_level": None,
            "signal_strength": None,
            "connection_status": DeviceStatus.UNKNOWN,
            "last_seen": None,
        }
    )

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.isoformat()}


class TemperatureQuery(BaseModel):
    """Query parameters for temperature data retrieval."""

    # Identifiers
    device_id: str
    probe_id: Optional[str] = None

    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Aggregation
    aggregation: Optional[str] = None
    interval: Optional[str] = None

    # Filtering
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None

    # Pagination
    limit: Optional[int] = 1000
    offset: Optional[int] = 0

    # Sorting
    sort_order: str = "desc"  # asc or desc

    @validator("sort_order")
    def validate_sort_order(cls, v: str) -> str:
        """Validate sort order."""
        if v.lower() not in ["asc", "desc"]:
            raise ValueError('Sort order must be either "asc" or "desc"')
        return v.lower()


class AnomalyDetectionResult(BaseModel):
    """Results from anomaly detection processing."""

    device_id: str
    probe_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reading: float
    is_anomaly: bool
    confidence: float
    expected_range: Dict[str, float]
    deviation: float
    context_window: List[Dict[str, Any]] = Field(default_factory=list)
