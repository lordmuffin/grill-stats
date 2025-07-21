from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class EntityType(str, Enum):
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    DEVICE_TRACKER = "device_tracker"
    SWITCH = "switch"


class DeviceClass(str, Enum):
    TEMPERATURE = "temperature"
    BATTERY = "battery"
    SIGNAL_STRENGTH = "signal_strength"
    CONNECTIVITY = "connectivity"
    TIMESTAMP = "timestamp"


class EntityState(BaseModel):
    entity_id: str
    state: Any
    attributes: Dict[str, Any] = Field(default_factory=dict)
    last_changed: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class TemperatureSensor(BaseModel):
    device_id: str
    probe_id: str
    name: str
    temperature: float
    unit: str = "°F"
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class DeviceEntity(BaseModel):
    device_id: str
    name: str
    model: Optional[str] = None
    manufacturer: str = "ThermoWorks"
    sw_version: Optional[str] = None
    hw_version: Optional[str] = None
    identifiers: List[str] = Field(default_factory=list)
    connections: List[tuple] = Field(default_factory=list)
    via_device: Optional[str] = None


class EntityRegistry(BaseModel):
    entities: Dict[str, EntityState] = Field(default_factory=dict)
    devices: Dict[str, DeviceEntity] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_entity(self, entity: EntityState) -> None:
        self.entities[entity.entity_id] = entity
        self.updated_at = datetime.utcnow()

    def remove_entity(self, entity_id: str) -> bool:
        if entity_id in self.entities:
            del self.entities[entity_id]
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_entity(self, entity_id: str) -> Optional[EntityState]:
        return self.entities.get(entity_id)

    def update_entity_state(self, entity_id: str, state: Any, attributes: Optional[Dict] = None) -> bool:
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            entity.state = state
            entity.last_updated = datetime.utcnow()
            if attributes:
                entity.attributes.update(attributes)
            return True
        return False


class AutomationTrigger(BaseModel):
    trigger_type: str
    entity_id: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    above: Optional[float] = None
    below: Optional[float] = None
    for_duration: Optional[str] = None


class AutomationCondition(BaseModel):
    condition_type: str
    entity_id: str
    state: Optional[str] = None
    above: Optional[float] = None
    below: Optional[float] = None


class AutomationAction(BaseModel):
    action_type: str
    service: Optional[str] = None
    service_data: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, str]] = None


class HAAutomation(BaseModel):
    id: str
    alias: str
    description: Optional[str] = None
    trigger: List[AutomationTrigger]
    condition: List[AutomationCondition] = Field(default_factory=list)
    action: List[AutomationAction]
    mode: str = "single"
    enabled: bool = True