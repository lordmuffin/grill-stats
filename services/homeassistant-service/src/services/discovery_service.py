import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.entity_models import DeviceClass, EntityType
from ..models.ha_models import HAConfig, HADiscoveryConfig
from .ha_client import HomeAssistantClient

logger = logging.getLogger(__name__)


class DiscoveryService:
    def __init__(self, ha_client: HomeAssistantClient, config: HAConfig):
        self.ha_client = ha_client
        self.config = config
        self.discovered_entities: Dict[str, HADiscoveryConfig] = {}

    async def auto_discover_devices(self) -> Dict[str, Any]:
        try:
            logger.info("Starting auto-discovery of grill monitoring devices")

            # Get all current entities in Home Assistant
            current_states = self.ha_client.get_states()

            # Filter for our entities
            grill_entities = [
                state
                for state in current_states
                if state.get("entity_id", "").startswith(f"sensor.{self.config.entity_prefix}")
                or state.get("entity_id", "").startswith(f"binary_sensor.{self.config.entity_prefix}")
            ]

            discovery_results = {
                "discovered_entities": len(grill_entities),
                "devices_found": set(),
                "entity_types": {},
                "discovery_time": datetime.utcnow().isoformat(),
            }

            for entity_state in grill_entities:
                entity_id = entity_state.get("entity_id")
                attributes = entity_state.get("attributes", {})
                device_id = attributes.get("device_id")

                if device_id:
                    discovery_results["devices_found"].add(device_id)

                entity_type = entity_id.split(".")[0]
                discovery_results["entity_types"][entity_type] = discovery_results["entity_types"].get(entity_type, 0) + 1

                # Create discovery config
                await self._create_entity_discovery_config(entity_state)

            discovery_results["devices_found"] = list(discovery_results["devices_found"])

            logger.info(
                f"Auto-discovery completed: {len(grill_entities)} entities found across {len(discovery_results['devices_found'])} devices"
            )
            return discovery_results

        except Exception as e:
            logger.error(f"Failed to auto-discover devices: {e}")
            return {"error": str(e)}

    async def register_device_discovery(self, device_id: str, device_info: Dict[str, Any]) -> bool:
        try:
            # Create MQTT discovery topics for the device
            device_config = {
                "identifiers": [device_id],
                "name": device_info.get("name", f"Grill Device {device_id}"),
                "manufacturer": device_info.get("manufacturer", "ThermoWorks"),
                "model": device_info.get("model", "Wireless Thermometer"),
                "sw_version": device_info.get("sw_version"),
                "hw_version": device_info.get("hw_version"),
            }

            # Temperature sensor discovery
            if device_info.get("has_temperature", True):
                for probe_id in device_info.get("probes", ["1"]):
                    await self._register_temperature_sensor_discovery(device_id, probe_id, device_config)

            # Battery sensor discovery
            if device_info.get("has_battery", True):
                await self._register_battery_sensor_discovery(device_id, device_config)

            # Signal strength sensor discovery
            if device_info.get("has_signal_strength", True):
                await self._register_signal_strength_discovery(device_id, device_config)

            # Connection binary sensor discovery
            if device_info.get("has_connectivity", True):
                await self._register_connection_sensor_discovery(device_id, device_config)

            logger.info(f"Device discovery registered for {device_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register device discovery for {device_id}: {e}")
            return False

    async def _register_temperature_sensor_discovery(self, device_id: str, probe_id: str, device_config: Dict):
        try:
            entity_id = f"sensor.{self.config.entity_prefix}_{device_id}_{probe_id}_temperature"
            unique_id = f"{self.config.entity_prefix}_{device_id}_{probe_id}_temperature"

            discovery_config = HADiscoveryConfig(
                name=f"Probe {probe_id} Temperature",
                unique_id=unique_id,
                state_topic=f"homeassistant/sensor/{device_id}/{unique_id}/state",
                device_class=DeviceClass.TEMPERATURE.value,
                unit_of_measurement="°F",
                value_template="{{ value_json.temperature }}",
                availability_topic=f"homeassistant/sensor/{device_id}/{unique_id}/availability",
                device=device_config,
                icon="mdi:thermometer",
            )

            self.discovered_entities[entity_id] = discovery_config
            logger.debug(f"Registered temperature sensor discovery: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to register temperature sensor discovery: {e}")

    async def _register_battery_sensor_discovery(self, device_id: str, device_config: Dict):
        try:
            entity_id = f"sensor.{self.config.entity_prefix}_{device_id}_battery"
            unique_id = f"{self.config.entity_prefix}_{device_id}_battery"

            discovery_config = HADiscoveryConfig(
                name=f"Device {device_id} Battery",
                unique_id=unique_id,
                state_topic=f"homeassistant/sensor/{device_id}/{unique_id}/state",
                device_class=DeviceClass.BATTERY.value,
                unit_of_measurement="%",
                value_template="{{ value_json.battery_level }}",
                availability_topic=f"homeassistant/sensor/{device_id}/{unique_id}/availability",
                device=device_config,
                icon="mdi:battery",
                entity_category="diagnostic",
            )

            self.discovered_entities[entity_id] = discovery_config
            logger.debug(f"Registered battery sensor discovery: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to register battery sensor discovery: {e}")

    async def _register_signal_strength_discovery(self, device_id: str, device_config: Dict):
        try:
            entity_id = f"sensor.{self.config.entity_prefix}_{device_id}_signal_strength"
            unique_id = f"{self.config.entity_prefix}_{device_id}_signal_strength"

            discovery_config = HADiscoveryConfig(
                name=f"Device {device_id} Signal Strength",
                unique_id=unique_id,
                state_topic=f"homeassistant/sensor/{device_id}/{unique_id}/state",
                device_class=DeviceClass.SIGNAL_STRENGTH.value,
                unit_of_measurement="dBm",
                value_template="{{ value_json.signal_strength }}",
                availability_topic=f"homeassistant/sensor/{device_id}/{unique_id}/availability",
                device=device_config,
                icon="mdi:wifi",
                entity_category="diagnostic",
            )

            self.discovered_entities[entity_id] = discovery_config
            logger.debug(f"Registered signal strength discovery: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to register signal strength discovery: {e}")

    async def _register_connection_sensor_discovery(self, device_id: str, device_config: Dict):
        try:
            entity_id = f"binary_sensor.{self.config.entity_prefix}_{device_id}_connection"
            unique_id = f"{self.config.entity_prefix}_{device_id}_connection"

            discovery_config = HADiscoveryConfig(
                name=f"Device {device_id} Connection",
                unique_id=unique_id,
                state_topic=f"homeassistant/binary_sensor/{device_id}/{unique_id}/state",
                device_class=DeviceClass.CONNECTIVITY.value,
                value_template="{{ value_json.is_connected | lower }}",
                availability_topic=f"homeassistant/binary_sensor/{device_id}/{unique_id}/availability",
                device=device_config,
                icon="mdi:wifi",
                entity_category="diagnostic",
            )

            self.discovered_entities[entity_id] = discovery_config
            logger.debug(f"Registered connection sensor discovery: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to register connection sensor discovery: {e}")

    async def _create_entity_discovery_config(self, entity_state: Dict):
        try:
            entity_id = entity_state.get("entity_id")
            attributes = entity_state.get("attributes", {})

            if not entity_id:
                return

            entity_type = entity_id.split(".")[0]
            device_id = attributes.get("device_id", "unknown")

            # Create device config
            device_config = {
                "identifiers": [device_id],
                "name": f"Grill Device {device_id}",
                "manufacturer": "ThermoWorks",
                "model": "Wireless Thermometer",
            }

            # Create discovery config based on entity type
            if entity_type == "sensor":
                discovery_config = HADiscoveryConfig(
                    name=attributes.get("friendly_name", entity_id),
                    unique_id=entity_id,
                    state_topic=f"homeassistant/sensor/{device_id}/{entity_id}/state",
                    device_class=attributes.get("device_class"),
                    unit_of_measurement=attributes.get("unit_of_measurement"),
                    device=device_config,
                    icon=attributes.get("icon"),
                    entity_category=attributes.get("entity_category"),
                )
            elif entity_type == "binary_sensor":
                discovery_config = HADiscoveryConfig(
                    name=attributes.get("friendly_name", entity_id),
                    unique_id=entity_id,
                    state_topic=f"homeassistant/binary_sensor/{device_id}/{entity_id}/state",
                    device_class=attributes.get("device_class"),
                    device=device_config,
                    icon=attributes.get("icon"),
                    entity_category=attributes.get("entity_category"),
                )
            else:
                return

            self.discovered_entities[entity_id] = discovery_config
            logger.debug(f"Created discovery config for existing entity: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to create discovery config for {entity_state.get('entity_id')}: {e}")

    def get_discovery_payload(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get MQTT discovery payload for an entity"""
        try:
            if entity_id not in self.discovered_entities:
                return None

            config = self.discovered_entities[entity_id]

            # Convert to MQTT discovery format
            payload = {
                "name": config.name,
                "unique_id": config.unique_id,
                "state_topic": config.state_topic,
                "device": config.device,
            }

            if config.device_class:
                payload["device_class"] = config.device_class

            if config.unit_of_measurement:
                payload["unit_of_measurement"] = config.unit_of_measurement

            if config.value_template:
                payload["value_template"] = config.value_template

            if config.availability_topic:
                payload["availability_topic"] = config.availability_topic

            if config.icon:
                payload["icon"] = config.icon

            if config.entity_category:
                payload["entity_category"] = config.entity_category

            return payload

        except Exception as e:
            logger.error(f"Failed to get discovery payload for {entity_id}: {e}")
            return None

    def get_all_discovery_configs(self) -> Dict[str, HADiscoveryConfig]:
        return self.discovered_entities.copy()

    def remove_discovery_config(self, entity_id: str) -> bool:
        try:
            if entity_id in self.discovered_entities:
                del self.discovered_entities[entity_id]
                logger.debug(f"Removed discovery config for {entity_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove discovery config for {entity_id}: {e}")
            return False

    def get_discovery_stats(self) -> Dict[str, Any]:
        entity_types = {}
        device_count = set()

        for entity_id, config in self.discovered_entities.items():
            entity_type = entity_id.split(".")[0]
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

            if config.device and "identifiers" in config.device:
                device_count.update(config.device["identifiers"])

        return {
            "total_entities": len(self.discovered_entities),
            "entity_types": entity_types,
            "unique_devices": len(device_count),
            "last_discovery": datetime.utcnow().isoformat(),
        }
