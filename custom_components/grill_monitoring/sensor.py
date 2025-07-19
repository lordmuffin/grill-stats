"""Sensor platform for Grill Monitoring integration."""

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrillMonitoringDevice
from .const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_TYPE,
    ATTR_FIRMWARE_VERSION,
    ATTR_LAST_SEEN,
    ATTR_PROBE_ID,
    ATTR_SIGNAL_STRENGTH,
    ATTR_TEMPERATURE_UNIT,
    DOMAIN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from .coordinator import GrillMonitoringCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Grill Monitoring sensor platform."""
    coordinator: GrillMonitoringCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create sensors for each device
    for device_id, device_data in coordinator.data.items():
        device_info = device_data.get("device_info", {})
        temperature_data = device_data.get("temperature_data", {})

        # Create main device temperature sensor
        entities.append(
            GrillTemperatureSensor(
                coordinator=coordinator,
                device_id=device_id,
                probe_id=None,
                name=device_info.get("name", f"Device {device_id}"),
            )
        )

        # Create probe-specific sensors if device has multiple probes
        if isinstance(temperature_data, dict) and "probes" in temperature_data:
            for probe_id, probe_data in temperature_data["probes"].items():
                probe_name = probe_data.get("name", f"Probe {probe_id}")
                entities.append(
                    GrillTemperatureSensor(
                        coordinator=coordinator,
                        device_id=device_id,
                        probe_id=probe_id,
                        name=f"{device_info.get('name', f'Device {device_id}')} {probe_name}",
                    )
                )

        # Create battery level sensor if available
        health_data = device_data.get("health_data", {})
        if health_data and "battery_level" in health_data:
            entities.append(
                GrillBatterySensor(
                    coordinator=coordinator,
                    device_id=device_id,
                    name=f"{device_info.get('name', f'Device {device_id}')} Battery",
                )
            )

        # Create signal strength sensor if available
        if health_data and "signal_strength" in health_data:
            entities.append(
                GrillSignalStrengthSensor(
                    coordinator=coordinator,
                    device_id=device_id,
                    name=f"{device_info.get('name', f'Device {device_id}')} Signal",
                )
            )

    async_add_entities(entities)


class GrillTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Grill Temperature Sensor."""

    def __init__(
        self,
        coordinator: GrillMonitoringCoordinator,
        device_id: str,
        probe_id: Optional[str],
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._probe_id = probe_id
        self._name = name
        self._device = GrillMonitoringDevice(coordinator, device_id)

        # Generate unique ID
        unique_id = f"{device_id}_temperature"
        if probe_id:
            unique_id += f"_{probe_id}"
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit of measurement."""
        temp_data = self.coordinator.get_temperature_data(
            self._device_id, self._probe_id
        )
        if temp_data:
            unit = temp_data.get("unit", "°F")
            return (
                UnitOfTemperature.FAHRENHEIT
                if unit == "°F"
                else UnitOfTemperature.CELSIUS
            )
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self) -> Optional[float]:
        """Return the native value of the sensor."""
        temp_data = self.coordinator.get_temperature_data(
            self._device_id, self._probe_id
        )
        if temp_data:
            return temp_data.get("temperature")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            ATTR_DEVICE_ID: self._device_id,
        }

        if self._probe_id:
            attributes[ATTR_PROBE_ID] = self._probe_id

        temp_data = self.coordinator.get_temperature_data(
            self._device_id, self._probe_id
        )
        if temp_data:
            attributes[ATTR_TEMPERATURE_UNIT] = temp_data.get("unit", "°F")
            if "timestamp" in temp_data:
                attributes[ATTR_LAST_SEEN] = temp_data["timestamp"]

        device_data = self.coordinator.get_device_data(self._device_id)
        if device_data:
            device_info = device_data.get("device_info", {})
            if "device_type" in device_info:
                attributes[ATTR_DEVICE_TYPE] = device_info["device_type"]
            if "firmware_version" in device_info:
                attributes[ATTR_FIRMWARE_VERSION] = device_info["firmware_version"]

        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.get_temperature_data(self._device_id, self._probe_id)
            is not None
        )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return self._device.device_info


class GrillBatterySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Grill Battery Sensor."""

    def __init__(
        self,
        coordinator: GrillMonitoringCoordinator,
        device_id: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._device = GrillMonitoringDevice(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.BATTERY

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit of measurement."""
        return PERCENTAGE

    @property
    def native_value(self) -> Optional[float]:
        """Return the native value of the sensor."""
        health_data = self.coordinator.get_device_health(self._device_id)
        if health_data:
            return health_data.get("battery_level")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            ATTR_DEVICE_ID: self._device_id,
        }

        health_data = self.coordinator.get_device_health(self._device_id)
        if health_data:
            if "last_seen" in health_data:
                attributes[ATTR_LAST_SEEN] = health_data["last_seen"]

        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.get_device_health(self._device_id) is not None
        )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return self._device.device_info


class GrillSignalStrengthSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Grill Signal Strength Sensor."""

    def __init__(
        self,
        coordinator: GrillMonitoringCoordinator,
        device_id: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._device = GrillMonitoringDevice(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_signal_strength"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.SIGNAL_STRENGTH

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit of measurement."""
        return "dBm"

    @property
    def native_value(self) -> Optional[float]:
        """Return the native value of the sensor."""
        health_data = self.coordinator.get_device_health(self._device_id)
        if health_data:
            return health_data.get("signal_strength")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            ATTR_DEVICE_ID: self._device_id,
        }

        health_data = self.coordinator.get_device_health(self._device_id)
        if health_data:
            if "last_seen" in health_data:
                attributes[ATTR_LAST_SEEN] = health_data["last_seen"]

        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.get_device_health(self._device_id) is not None
        )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return self._device.device_info
