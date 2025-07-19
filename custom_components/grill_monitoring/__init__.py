"""The Grill Monitoring integration."""

import asyncio
import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_SERVICE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SERVICE_URL,
    CONF_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import GrillMonitoringCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Grill Monitoring from a config entry."""
    device_service_url = entry.data[CONF_DEVICE_SERVICE_URL]
    temperature_service_url = entry.data[CONF_TEMPERATURE_SERVICE_URL]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    timeout = entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    coordinator = GrillMonitoringCoordinator(
        hass=hass,
        device_service_url=device_service_url,
        temperature_service_url=temperature_service_url,
        scan_interval=scan_interval,
        timeout=timeout,
    )

    # Test the connection
    connected, error_msg = await coordinator.async_test_connection()
    if not connected:
        _LOGGER.error("Failed to connect to Grill Monitoring services: %s", error_msg)
        raise ConfigEntryNotReady(error_msg)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class GrillMonitoringDevice:
    """Representation of a Grill Monitoring device."""

    def __init__(self, coordinator: GrillMonitoringCoordinator, device_id: str):
        """Initialize the device."""
        self.coordinator = coordinator
        self.device_id = device_id
        self._device_info = None

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        if self._device_info is None:
            device_data = self.coordinator.get_device_data(self.device_id)
            device_info = device_data.get("device_info", {}) if device_data else {}

            self._device_info = {
                "identifiers": {(DOMAIN, self.device_id)},
                "name": device_info.get("name", f"Grill Device {self.device_id}"),
                "manufacturer": "ThermoWorks",
                "model": device_info.get("device_type", "Unknown"),
                "sw_version": device_info.get("firmware_version"),
                "via_device": (DOMAIN, "grill_monitoring_hub"),
            }

        return self._device_info

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """Return True if entity should be polled."""
        return False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update the entity."""
        await self.coordinator.async_request_refresh()


class GrillMonitoringHub:
    """Representation of the Grill Monitoring hub."""

    def __init__(self, coordinator: GrillMonitoringCoordinator):
        """Initialize the hub."""
        self.coordinator = coordinator

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return hub device information."""
        return {
            "identifiers": {(DOMAIN, "grill_monitoring_hub")},
            "name": "Grill Monitoring Hub",
            "manufacturer": "Grill Monitoring",
            "model": "Integration Hub",
            "sw_version": "1.0.0",
        }
