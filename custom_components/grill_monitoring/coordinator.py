"""Data update coordinator for Grill Monitoring integration."""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any

import aiohttp
import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    ENDPOINT_DEVICES,
    ENDPOINT_CURRENT_TEMPERATURE,
    ENDPOINT_DEVICE_HEALTH,
    ERROR_CANNOT_CONNECT,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class GrillMonitoringCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Grill Monitoring services."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_service_url: str,
        temperature_service_url: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize the coordinator."""
        self.device_service_url = device_service_url.rstrip("/")
        self.temperature_service_url = temperature_service_url.rstrip("/")
        self.timeout = timeout
        self.session = async_get_clientsession(hass)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from both services."""
        try:
            async with async_timeout.timeout(self.timeout):
                # Fetch devices and their temperature data
                devices = await self._fetch_devices()
                device_data = {}
                
                for device in devices:
                    device_id = device.get("id")
                    if not device_id:
                        continue
                    
                    # Get current temperature data
                    temperature_data = await self._fetch_current_temperature(device_id)
                    device_health = await self._fetch_device_health(device_id)
                    
                    device_data[device_id] = {
                        "device_info": device,
                        "temperature_data": temperature_data,
                        "health_data": device_health,
                    }
                
                return device_data
                
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout communicating with services: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with services: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _fetch_devices(self) -> List[Dict[str, Any]]:
        """Fetch all devices from the device service."""
        url = f"{self.device_service_url}{ENDPOINT_DEVICES}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("devices", [])
                else:
                    _LOGGER.error(f"Failed to fetch devices: {response.status}")
                    return []
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error fetching devices: {err}")
            return []

    async def _fetch_current_temperature(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Fetch current temperature data for a device."""
        url = f"{self.temperature_service_url}{ENDPOINT_CURRENT_TEMPERATURE.format(device_id=device_id)}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data")
                else:
                    _LOGGER.debug(f"No temperature data for device {device_id}: {response.status}")
                    return None
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error fetching temperature for device {device_id}: {err}")
            return None

    async def _fetch_device_health(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Fetch device health data."""
        url = f"{self.device_service_url}{ENDPOINT_DEVICE_HEALTH.format(device_id=device_id)}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("health")
                else:
                    _LOGGER.debug(f"No health data for device {device_id}: {response.status}")
                    return None
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error fetching health for device {device_id}: {err}")
            return None

    async def async_test_connection(self) -> tuple[bool, str]:
        """Test connection to both services."""
        try:
            async with async_timeout.timeout(self.timeout):
                # Test device service
                device_url = f"{self.device_service_url}/health"
                async with self.session.get(device_url) as response:
                    if response.status != 200:
                        return False, f"Device service not reachable: {response.status}"
                
                # Test temperature service  
                temp_url = f"{self.temperature_service_url}/health"
                async with self.session.get(temp_url) as response:
                    if response.status != 200:
                        return False, f"Temperature service not reachable: {response.status}"
                
                return True, "Connected successfully"
                
        except asyncio.TimeoutError:
            return False, ERROR_TIMEOUT
        except aiohttp.ClientError as err:
            return False, f"{ERROR_CANNOT_CONNECT}: {err}"
        except Exception as err:
            return False, f"{ERROR_UNKNOWN}: {err}"

    def get_device_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific device."""
        return self.data.get(device_id) if self.data else None

    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get temperature data for a specific device and probe."""
        device_data = self.get_device_data(device_id)
        if not device_data:
            return None
        
        temp_data = device_data.get("temperature_data")
        if not temp_data:
            return None
        
        # If probe_id is specified, filter for that probe
        if probe_id and isinstance(temp_data, dict):
            probe_data = temp_data.get("probes", {}).get(probe_id)
            if probe_data:
                return {
                    "device_id": device_id,
                    "probe_id": probe_id,
                    "temperature": probe_data.get("temperature"),
                    "unit": probe_data.get("unit", "°F"),
                    "timestamp": probe_data.get("timestamp"),
                }
        
        # Return main temperature data
        return temp_data

    def get_device_health(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get health data for a specific device."""
        device_data = self.get_device_data(device_id)
        if not device_data:
            return None
        
        return device_data.get("health_data")

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all device information."""
        if not self.data:
            return []
        
        devices = []
        for device_id, device_data in self.data.items():
            device_info = device_data.get("device_info", {})
            device_info["id"] = device_id
            devices.append(device_info)
        
        return devices

    def get_device_probes(self, device_id: str) -> List[Dict[str, Any]]:
        """Get all probes for a specific device."""
        temp_data = self.get_temperature_data(device_id)
        if not temp_data:
            return []
        
        probes = []
        if isinstance(temp_data, dict) and "probes" in temp_data:
            for probe_id, probe_data in temp_data["probes"].items():
                probe_info = {
                    "id": probe_id,
                    "name": probe_data.get("name", f"Probe {probe_id}"),
                    "temperature": probe_data.get("temperature"),
                    "unit": probe_data.get("unit", "°F"),
                    "timestamp": probe_data.get("timestamp"),
                }
                probes.append(probe_info)
        
        return probes