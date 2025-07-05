"""Config flow for Grill Monitoring integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_DEVICE_SERVICE_URL,
    CONF_TEMPERATURE_SERVICE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_DEVICE_SERVICE_URL,
    DEFAULT_TEMPERATURE_SERVICE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    ERROR_CANNOT_CONNECT,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_SERVICE_URL, default=DEFAULT_DEVICE_SERVICE_URL): str,
        vol.Required(CONF_TEMPERATURE_SERVICE_URL, default=DEFAULT_TEMPERATURE_SERVICE_URL): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=60)
        ),
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self, device_url: str, temperature_url: str, timeout: int):
        """Initialize."""
        self.device_url = device_url.rstrip("/")
        self.temperature_url = temperature_url.rstrip("/")
        self.timeout = timeout

    async def authenticate(self, hass: core.HomeAssistant) -> tuple[bool, str]:
        """Test if we can authenticate with the services."""
        session = async_get_clientsession(hass)
        
        try:
            async with async_timeout.timeout(self.timeout):
                # Test device service health endpoint
                device_health_url = f"{self.device_url}/health"
                async with session.get(device_health_url) as response:
                    if response.status != 200:
                        return False, f"Device service not reachable (status: {response.status})"
                    
                    device_health = await response.json()
                    _LOGGER.debug("Device service health: %s", device_health)
                
                # Test temperature service health endpoint
                temp_health_url = f"{self.temperature_url}/health"
                async with session.get(temp_health_url) as response:
                    if response.status != 200:
                        return False, f"Temperature service not reachable (status: {response.status})"
                    
                    temp_health = await response.json()
                    _LOGGER.debug("Temperature service health: %s", temp_health)
                
                # Test actual API endpoints
                devices_url = f"{self.device_url}/api/devices"
                async with session.get(devices_url) as response:
                    if response.status != 200:
                        return False, f"Device API not accessible (status: {response.status})"
                    
                    devices_data = await response.json()
                    _LOGGER.debug("Found %d devices", len(devices_data.get("devices", [])))
                
                return True, "Successfully connected to both services"
                
        except asyncio.TimeoutError:
            return False, ERROR_TIMEOUT
        except aiohttp.ClientConnectorError:
            return False, ERROR_CANNOT_CONNECT
        except aiohttp.ClientError as err:
            return False, f"Connection error: {err}"
        except Exception as err:
            _LOGGER.exception("Unexpected error during authentication")
            return False, f"{ERROR_UNKNOWN}: {err}"


async def validate_input(hass: core.HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    hub = PlaceholderHub(
        data[CONF_DEVICE_SERVICE_URL],
        data[CONF_TEMPERATURE_SERVICE_URL],
        data[CONF_TIMEOUT],
    )

    success, message = await hub.authenticate(hass)
    if not success:
        raise CannotConnect(message)

    # Return info that you want to store in the config entry.
    return {
        "title": DEFAULT_NAME,
        "device_service_url": data[CONF_DEVICE_SERVICE_URL],
        "temperature_service_url": data[CONF_TEMPERATURE_SERVICE_URL],
        "message": message,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grill Monitoring."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "device_service_example": DEFAULT_DEVICE_SERVICE_URL,
                    "temperature_service_example": DEFAULT_TEMPERATURE_SERVICE_URL,
                },
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect as err:
            errors["base"] = "cannot_connect"
            _LOGGER.error("Cannot connect to services: %s", err)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(
                f"{user_input[CONF_DEVICE_SERVICE_URL]}_{user_input[CONF_TEMPERATURE_SERVICE_URL]}"
            )
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_service_example": DEFAULT_DEVICE_SERVICE_URL,
                "temperature_service_example": DEFAULT_TEMPERATURE_SERVICE_URL,
            },
        )

    async def async_step_import(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""