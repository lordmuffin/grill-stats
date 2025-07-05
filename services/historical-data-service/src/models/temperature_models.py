from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime

class TemperatureReading(BaseModel):
    """Model for temperature reading data."""
    device_id: str
    probe_id: Optional[str] = None
    grill_id: Optional[str] = None
    temperature: float
    unit: str = 'F'
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    battery_level: Optional[float] = None
    signal_strength: Optional[float] = None
    metadata: Optional[Dict] = None

class TemperatureQuery(BaseModel):
    """Model for temperature query parameters."""
    device_id: Optional[str] = None
    probe_id: Optional[str] = None
    grill_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    aggregation: Optional[str] = None
    interval: Optional[str] = None
    limit: Optional[int] = None

class TemperatureHistory(BaseModel):
    """Model for temperature history response."""
    device_id: str
    probe_id: Optional[str] = None
    grill_id: Optional[str] = None
    readings: List[dict]
    count: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None