from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class HAConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class HAConfig(BaseModel):
    base_url: str
    access_token: str
    verify_ssl: bool = True
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    websocket_enabled: bool = True
    entity_prefix: str = "grill_stats"


class HAServiceCall(BaseModel):
    domain: str
    service: str
    service_data: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None
    blocking: bool = False
    limit: Optional[float] = None


class HAEvent(BaseModel):
    event_type: str
    data: Dict[str, Any]
    origin: str = "LOCAL"
    time_fired: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[Dict[str, Any]] = None


class HAStateChange(BaseModel):
    entity_id: str
    old_state: Optional[Dict[str, Any]] = None
    new_state: Dict[str, Any]
    changed_at: datetime = Field(default_factory=datetime.utcnow)


class HADiscoveryConfig(BaseModel):
    name: str
    unique_id: str
    state_topic: str
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    value_template: Optional[str] = None
    availability_topic: Optional[str] = None
    device: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    entity_category: Optional[str] = None


class HAHealthStatus(BaseModel):
    status: HAConnectionStatus
    last_check: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0
    last_successful_connection: Optional[datetime] = None


class HAStatistics(BaseModel):
    entities_created: int = 0
    entities_updated: int = 0
    entities_removed: int = 0
    service_calls_made: int = 0
    service_calls_failed: int = 0
    events_sent: int = 0
    events_failed: int = 0
    last_sync: Optional[datetime] = None
    sync_duration_ms: Optional[float] = None
    errors_last_hour: int = 0