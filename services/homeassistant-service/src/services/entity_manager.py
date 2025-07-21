import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.entity_models import DeviceClass, DeviceEntity, EntityRegistry, EntityState, EntityType, TemperatureSensor
from ..models.ha_models import HADiscoveryConfig
from .ha_client import HomeAssistantClient

logger = logging.getLogger(__name__)


class EntityManager:
    def __init__(self, ha_client: HomeAssistantClient, entity_prefix: str = "grill_stats"):
        self.ha_client = ha_client
        self.entity_prefix = entity_prefix
        self.registry = EntityRegistry()
        self.device_configs: Dict[str, HADiscoveryConfig] = {}

    def create_temperature_sensor(self, sensor_data: TemperatureSensor) -> bool:
        try:
            entity_id = f"sensor.{self.entity_prefix}_{sensor_data.device_id}_{sensor_data.probe_id}_temperature"

            attributes = {
                "device_id": sensor_data.device_id,
                "probe_id": sensor_data.probe_id,
                "unit_of_measurement": sensor_data.unit,
                "device_class": DeviceClass.TEMPERATURE.value,
                "friendly_name": f"{sensor_data.name} Temperature",
                "last_seen": sensor_data.last_seen.isoformat(),
            }

            if sensor_data.battery_level is not None:
                attributes["battery_level"] = sensor_data.battery_level

            if sensor_data.signal_strength is not None:
                attributes["signal_strength"] = sensor_data.signal_strength

            # Create entity state
            entity_state = EntityState(entity_id=entity_id, state=sensor_data.temperature, attributes=attributes)

            # Add to registry and sync to Home Assistant
            self.registry.add_entity(entity_state)
            success = self.ha_client.set_entity_state(entity_id, str(sensor_data.temperature), attributes)

            if success:
                logger.info(f"Created temperature sensor: {entity_id}")

                # Create discovery config for MQTT auto-discovery (if supported)
                self._create_discovery_config(entity_state)

            return success

        except Exception as e:
            logger.error(f"Failed to create temperature sensor for {sensor_data.device_id}: {e}")
            return False

    def create_battery_sensor(self, device_id: str, battery_level: int) -> bool:
        try:
            entity_id = f"sensor.{self.entity_prefix}_{device_id}_battery"

            attributes = {
                "device_id": device_id,
                "device_class": DeviceClass.BATTERY.value,
                "unit_of_measurement": "%",
                "friendly_name": f"Device {device_id} Battery",
                "icon": "mdi:battery" if battery_level > 20 else "mdi:battery-alert",
            }

            entity_state = EntityState(entity_id=entity_id, state=battery_level, attributes=attributes)

            self.registry.add_entity(entity_state)
            success = self.ha_client.set_entity_state(entity_id, str(battery_level), attributes)

            if success:
                logger.info(f"Created battery sensor: {entity_id}")
                self._create_discovery_config(entity_state)

            return success

        except Exception as e:
            logger.error(f"Failed to create battery sensor for {device_id}: {e}")
            return False

    def create_signal_strength_sensor(self, device_id: str, signal_strength: int) -> bool:
        try:
            entity_id = f"sensor.{self.entity_prefix}_{device_id}_signal_strength"

            attributes = {
                "device_id": device_id,
                "device_class": DeviceClass.SIGNAL_STRENGTH.value,
                "unit_of_measurement": "dBm",
                "friendly_name": f"Device {device_id} Signal Strength",
                "icon": "mdi:wifi" if signal_strength > -70 else "mdi:wifi-strength-1",
            }

            entity_state = EntityState(entity_id=entity_id, state=signal_strength, attributes=attributes)

            self.registry.add_entity(entity_state)
            success = self.ha_client.set_entity_state(entity_id, str(signal_strength), attributes)

            if success:
                logger.info(f"Created signal strength sensor: {entity_id}")
                self._create_discovery_config(entity_state)

            return success

        except Exception as e:
            logger.error(f"Failed to create signal strength sensor for {device_id}: {e}")
            return False

    def create_connection_binary_sensor(self, device_id: str, is_connected: bool) -> bool:
        try:
            entity_id = f"binary_sensor.{self.entity_prefix}_{device_id}_connection"

            attributes = {
                "device_id": device_id,
                "device_class": DeviceClass.CONNECTIVITY.value,
                "friendly_name": f"Device {device_id} Connection",
                "icon": "mdi:wifi" if is_connected else "mdi:wifi-off",
            }

            entity_state = EntityState(entity_id=entity_id, state="on" if is_connected else "off", attributes=attributes)

            self.registry.add_entity(entity_state)
            success = self.ha_client.set_entity_state(entity_id, "on" if is_connected else "off", attributes)

            if success:
                logger.info(f"Created connection sensor: {entity_id}")
                self._create_discovery_config(entity_state)

            return success

        except Exception as e:
            logger.error(f"Failed to create connection sensor for {device_id}: {e}")
            return False

    def create_device_group(self, device_entity: DeviceEntity) -> bool:
        try:
            # Register device in registry
            self.registry.devices[device_entity.device_id] = device_entity

            # Create device registry entry in Home Assistant
            device_data = {
                "identifiers": device_entity.identifiers or [device_entity.device_id],
                "name": device_entity.name,
                "manufacturer": device_entity.manufacturer,
                "model": device_entity.model,
                "sw_version": device_entity.sw_version,
                "hw_version": device_entity.hw_version,
            }

            if device_entity.via_device:
                device_data["via_device"] = device_entity.via_device

            if device_entity.connections:
                device_data["connections"] = device_entity.connections

            logger.info(f"Created device group for: {device_entity.device_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create device group for {device_entity.device_id}: {e}")
            return False

    def update_entity_state(self, entity_id: str, state: Any, attributes: Optional[Dict] = None) -> bool:
        try:
            # Update in registry
            success = self.registry.update_entity_state(entity_id, state, attributes)

            if success:
                # Sync to Home Assistant
                ha_success = self.ha_client.set_entity_state(entity_id, str(state), attributes)

                if ha_success:
                    logger.debug(f"Updated entity state: {entity_id} = {state}")
                return ha_success

            return False

        except Exception as e:
            logger.error(f"Failed to update entity state for {entity_id}: {e}")
            return False

    def remove_entity(self, entity_id: str) -> bool:
        try:
            # Remove from registry
            success = self.registry.remove_entity(entity_id)

            if success:
                # Remove discovery config if exists
                if entity_id in self.device_configs:
                    del self.device_configs[entity_id]

                logger.info(f"Removed entity: {entity_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to remove entity {entity_id}: {e}")
            return False

    def get_entity(self, entity_id: str) -> Optional[EntityState]:
        return self.registry.get_entity(entity_id)

    def get_all_entities(self) -> Dict[str, EntityState]:
        return self.registry.entities.copy()

    def get_entities_by_device(self, device_id: str) -> List[EntityState]:
        return [entity for entity in self.registry.entities.values() if entity.attributes.get("device_id") == device_id]

    def cleanup_stale_entities(self, max_age_hours: int = 24) -> int:
        try:
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
            stale_entities = []

            for entity_id, entity in self.registry.entities.items():
                last_updated = entity.last_updated.timestamp()
                if last_updated < cutoff_time:
                    stale_entities.append(entity_id)

            removed_count = 0
            for entity_id in stale_entities:
                if self.remove_entity(entity_id):
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} stale entities")

            return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup stale entities: {e}")
            return 0

    def _create_discovery_config(self, entity_state: EntityState) -> None:
        try:
            entity_type = entity_state.entity_id.split(".")[0]
            device_id = entity_state.attributes.get("device_id", "unknown")

            config = HADiscoveryConfig(
                name=entity_state.attributes.get("friendly_name", entity_state.entity_id),
                unique_id=entity_state.entity_id,
                state_topic=f"homeassistant/{entity_type}/{device_id}/{entity_state.entity_id}/state",
                device_class=entity_state.attributes.get("device_class"),
                unit_of_measurement=entity_state.attributes.get("unit_of_measurement"),
                icon=entity_state.attributes.get("icon"),
                device={
                    "identifiers": [device_id],
                    "name": f"Grill Stats Device {device_id}",
                    "manufacturer": "ThermoWorks",
                    "model": "Wireless Thermometer",
                },
            )

            self.device_configs[entity_state.entity_id] = config
            logger.debug(f"Created discovery config for {entity_state.entity_id}")

        except Exception as e:
            logger.error(f"Failed to create discovery config for {entity_state.entity_id}: {e}")

    def get_discovery_configs(self) -> Dict[str, HADiscoveryConfig]:
        return self.device_configs.copy()

    def get_registry_stats(self) -> Dict[str, Any]:
        return {
            "total_entities": len(self.registry.entities),
            "total_devices": len(self.registry.devices),
            "entities_by_type": self._get_entities_by_type(),
            "last_updated": self.registry.updated_at.isoformat(),
        }

    def _get_entities_by_type(self) -> Dict[str, int]:
        entity_types = {}
        for entity_id in self.registry.entities.keys():
            entity_type = entity_id.split(".")[0]
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        return entity_types
