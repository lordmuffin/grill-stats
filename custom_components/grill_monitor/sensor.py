"""Support for Grill Monitor sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, GrillMonitorDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Grill Monitor sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([GrillTemperatureSensor(coordinator)])


class GrillTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Grill Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(self, coordinator: GrillMonitorDataCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_temperature"
        self._attr_name = "Grill Temperature"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get("temperature")
