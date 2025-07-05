"""
Event schemas for Kafka messages.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class EventType(str, Enum):
    """Event type enumeration."""
    TEMPERATURE_READING = "temperature_reading"
    TEMPERATURE_VALIDATED = "temperature_validated"
    ANOMALY_DETECTED = "anomaly_detected"
    ALERT_TRIGGERED = "alert_triggered"
    HOMEASSISTANT_STATE_UPDATE = "homeassistant_state_update"


class SeverityLevel(str, Enum):
    """Severity level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeviceStatus(str, Enum):
    """Device status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class BaseEvent(BaseModel):
    """Base event schema."""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    source: str = Field(..., description="Source of the event")
    version: str = Field(default="1.0", description="Schema version")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TemperatureReading(BaseModel):
    """Temperature reading data."""
    device_id: str = Field(..., description="Device identifier")
    device_name: str = Field(..., description="Human-readable device name")
    temperature: float = Field(..., description="Temperature value")
    temperature_unit: str = Field(default="F", description="Temperature unit")
    battery_level: Optional[float] = Field(None, description="Battery level percentage")
    signal_strength: Optional[float] = Field(None, description="Signal strength")
    location: Optional[str] = Field(None, description="Device location")
    status: DeviceStatus = Field(default=DeviceStatus.ONLINE, description="Device status")
    
    @validator('temperature')
    def validate_temperature(cls, v):
        if v < -100 or v > 1000:
            raise ValueError('Temperature must be between -100 and 1000')
        return v
    
    @validator('battery_level')
    def validate_battery_level(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Battery level must be between 0 and 100')
        return v
    
    @validator('signal_strength')
    def validate_signal_strength(cls, v):
        if v is not None and (v < -100 or v > 0):
            raise ValueError('Signal strength must be between -100 and 0 dBm')
        return v


class TemperatureReadingEvent(BaseEvent):
    """Raw temperature reading event."""
    event_type: EventType = Field(default=EventType.TEMPERATURE_READING, const=True)
    data: TemperatureReading = Field(..., description="Temperature reading data")


class ValidationError(BaseModel):
    """Validation error details."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    value: Any = Field(..., description="Invalid value")


class TemperatureValidatedEvent(BaseEvent):
    """Validated temperature reading event."""
    event_type: EventType = Field(default=EventType.TEMPERATURE_VALIDATED, const=True)
    data: TemperatureReading = Field(..., description="Validated temperature reading")
    validation_status: str = Field(..., description="Validation status")
    validation_errors: List[ValidationError] = Field(default=[], description="Validation errors")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class AnomalyDetails(BaseModel):
    """Anomaly detection details."""
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    confidence_score: float = Field(..., description="Confidence score (0-1)")
    severity: SeverityLevel = Field(..., description="Severity level")
    expected_range: Dict[str, float] = Field(..., description="Expected value range")
    actual_value: float = Field(..., description="Actual value that triggered anomaly")
    historical_stats: Dict[str, Any] = Field(default={}, description="Historical statistics")
    
    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        if v < 0 or v > 1:
            raise ValueError('Confidence score must be between 0 and 1')
        return v


class AnomalyDetectedEvent(BaseEvent):
    """Anomaly detected event."""
    event_type: EventType = Field(default=EventType.ANOMALY_DETECTED, const=True)
    device_id: str = Field(..., description="Device identifier")
    temperature_reading: TemperatureReading = Field(..., description="Temperature reading that triggered anomaly")
    anomaly_details: AnomalyDetails = Field(..., description="Anomaly detection details")
    detection_time_ms: float = Field(..., description="Detection processing time in milliseconds")


class AlertAction(BaseModel):
    """Alert action details."""
    action_type: str = Field(..., description="Type of action to take")
    target: str = Field(..., description="Target for the action")
    parameters: Dict[str, Any] = Field(default={}, description="Action parameters")


class AlertTriggeredEvent(BaseEvent):
    """Alert triggered event."""
    event_type: EventType = Field(default=EventType.ALERT_TRIGGERED, const=True)
    device_id: str = Field(..., description="Device identifier")
    alert_type: str = Field(..., description="Type of alert")
    severity: SeverityLevel = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    anomaly_event: AnomalyDetectedEvent = Field(..., description="Anomaly that triggered the alert")
    actions: List[AlertAction] = Field(default=[], description="Actions to take")
    expires_at: Optional[datetime] = Field(None, description="Alert expiration time")


class HomeAssistantState(BaseModel):
    """Home Assistant state data."""
    entity_id: str = Field(..., description="Entity ID")
    state: str = Field(..., description="Entity state")
    attributes: Dict[str, Any] = Field(default={}, description="Entity attributes")
    last_changed: datetime = Field(..., description="Last changed timestamp")
    last_updated: datetime = Field(..., description="Last updated timestamp")


class HomeAssistantStateUpdateEvent(BaseEvent):
    """Home Assistant state update event."""
    event_type: EventType = Field(default=EventType.HOMEASSISTANT_STATE_UPDATE, const=True)
    device_id: str = Field(..., description="Device identifier")
    ha_state: HomeAssistantState = Field(..., description="Home Assistant state")
    update_status: str = Field(..., description="Update status")
    update_time_ms: float = Field(..., description="Update processing time in milliseconds")


class BatchEvent(BaseModel):
    """Batch event containing multiple events."""
    batch_id: str = Field(..., description="Batch identifier")
    events: List[Union[
        TemperatureReadingEvent,
        TemperatureValidatedEvent,
        AnomalyDetectedEvent,
        AlertTriggeredEvent,
        HomeAssistantStateUpdateEvent
    ]] = Field(..., description="List of events in the batch")
    total_events: int = Field(..., description="Total number of events in batch")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Batch creation time")
    
    @validator('total_events')
    def validate_total_events(cls, v, values):
        if 'events' in values and len(values['events']) != v:
            raise ValueError('Total events must match the number of events in the list')
        return v


# Schema registry for event types
EVENT_SCHEMAS = {
    EventType.TEMPERATURE_READING: TemperatureReadingEvent,
    EventType.TEMPERATURE_VALIDATED: TemperatureValidatedEvent,
    EventType.ANOMALY_DETECTED: AnomalyDetectedEvent,
    EventType.ALERT_TRIGGERED: AlertTriggeredEvent,
    EventType.HOMEASSISTANT_STATE_UPDATE: HomeAssistantStateUpdateEvent
}


def validate_event(event_type: EventType, data: Dict[str, Any]) -> BaseEvent:
    """Validate an event against its schema."""
    schema_class = EVENT_SCHEMAS.get(event_type)
    if not schema_class:
        raise ValueError(f"Unknown event type: {event_type}")
    
    try:
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Event validation failed: {str(e)}")


def serialize_event(event: BaseEvent) -> Dict[str, Any]:
    """Serialize an event to a dictionary."""
    return event.dict()


def deserialize_event(data: Dict[str, Any]) -> BaseEvent:
    """Deserialize an event from a dictionary."""
    event_type = data.get('event_type')
    if not event_type:
        raise ValueError("Event type is required")
    
    return validate_event(EventType(event_type), data)