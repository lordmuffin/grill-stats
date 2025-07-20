"""
Async ThermoWorks client for temperature data collection.

This module provides an asynchronous client for the ThermoWorks API,
with circuit breaker protection and comprehensive error handling.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import aiohttp
from opentelemetry import trace

from temperature_service.config import ThermoworksSettings, get_settings
from temperature_service.models import TemperatureReading
from temperature_service.utils import CircuitBreakerError, create_circuit_breaker, trace_async_function

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class ThermoworksAPIError(Exception):
    """Exception raised for ThermoWorks API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class ThermoworksAuthenticationError(ThermoworksAPIError):
    """Exception raised for authentication errors."""

    pass


class ThermoworksConnectionError(ThermoworksAPIError):
    """Exception raised for connection errors."""

    pass


class AsyncThermoworksClient:
    """Asynchronous ThermoWorks API client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        retry_count: Optional[int] = None,
        retry_backoff_factor: Optional[float] = None,
        settings: Optional[ThermoworksSettings] = None,
    ):
        """Initialize ThermoWorks client.

        Args:
            api_key: ThermoWorks API key
            base_url: ThermoWorks API base URL
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_backoff_factor: Backoff factor for retries
            settings: Optional settings object
        """
        self.settings = settings or get_settings().thermoworks

        # Use provided values or fall back to settings
        self.api_key = api_key or self.settings.api_key
        self.base_url = base_url or self.settings.base_url
        self.timeout = timeout or self.settings.timeout
        self.retry_count = retry_count or self.settings.retry_count
        self.retry_backoff_factor = retry_backoff_factor or self.settings.retry_backoff_factor

        # Session and state
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

        # Check if mock mode should be used
        self.mock_mode = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes", "on")

        if self.mock_mode:
            logger.info("ThermoWorks client initialized in MOCK MODE")
        else:
            logger.info("ThermoWorks client initialized in LIVE MODE")

        # Create circuit breaker
        self._circuit_breaker = create_circuit_breaker(
            name="thermoworks_api",
            failure_threshold=3,
            recovery_timeout=30,
        )

    @trace_async_function(name="thermoworks_initialize")
    async def initialize(self) -> None:
        """Initialize client session."""
        if self._initialized:
            return

        # Create HTTP session with timeout
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        self._initialized = True
        logger.debug("ThermoWorks client session initialized")

    @trace_async_function(name="thermoworks_close")
    async def close(self) -> None:
        """Close client session."""
        if self.session:
            await self.session.close()
            self.session = None
            self._initialized = False
            logger.debug("ThermoWorks client session closed")

    @trace_async_function(name="thermoworks_request")
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Make a request to the ThermoWorks API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base URL)
            params: Optional query parameters
            data: Optional request body
            headers: Optional additional headers

        Returns:
            Response data (JSON decoded)

        Raises:
            ThermoworksAPIError: On API error
            ThermoworksAuthenticationError: On authentication error
            ThermoworksConnectionError: On connection error
        """
        # Check if circuit breaker is open
        if self._circuit_breaker.is_open:
            raise CircuitBreakerError("thermoworks_api", self._circuit_breaker.last_failure)

        # Handle mock mode
        if self.mock_mode:
            return await self._mock_request(method, endpoint, params, data)

        # Initialize session if needed
        if not self._initialized:
            await self.initialize()

        if not self.session:
            raise ThermoworksConnectionError("Client session not initialized")

        # Build URL
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # Merge headers
        request_headers = {}
        if headers:
            request_headers.update(headers)

        # Execute request with retry logic
        for attempt in range(1, self.retry_count + 1):
            try:
                async with self.session.request(method, url, params=params, json=data, headers=request_headers) as response:
                    # Handle different status codes
                    if response.status == 200:
                        # Success
                        result = await response.json()

                        # Reset circuit breaker on success
                        if self._circuit_breaker.state.value != "closed":
                            self._circuit_breaker.reset()

                        return result
                    elif response.status == 401 or response.status == 403:
                        # Authentication error
                        error_text = await response.text()
                        error = ThermoworksAuthenticationError(
                            f"Authentication failed: {error_text}",
                            status_code=response.status,
                        )
                        self._circuit_breaker._on_failure(error)
                        raise error
                    else:
                        # Other API error
                        error_text = await response.text()
                        error = ThermoworksAPIError(
                            f"API error ({response.status}): {error_text}",
                            status_code=response.status,
                        )
                        self._circuit_breaker._on_failure(error)
                        raise error
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Connection error
                error = ThermoworksConnectionError(f"Connection error: {str(e)}")

                if attempt < self.retry_count:
                    # Calculate backoff time with exponential backoff and jitter
                    backoff = min(2**attempt, 60) * self.retry_backoff_factor
                    backoff *= 0.9 + 0.2 * (time.time() % 1)  # Add jitter

                    logger.warning(
                        "ThermoWorks API request failed (attempt %d/%d), retrying in %.2f seconds: %s",
                        attempt,
                        self.retry_count,
                        backoff,
                        str(e),
                    )

                    await asyncio.sleep(backoff)
                else:
                    # All retries failed
                    logger.error("ThermoWorks API request failed after %d attempts: %s", self.retry_count, str(e))
                    self._circuit_breaker._on_failure(error)
                    raise error
            except Exception as e:
                # Unexpected error
                error = ThermoworksAPIError(f"Unexpected error: {str(e)}")
                self._circuit_breaker._on_failure(error)
                raise error

    async def _mock_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Handle mock requests.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body

        Returns:
            Mock response data
        """
        # Extract device_id from endpoint
        device_id = None
        if "/devices/" in endpoint:
            parts = endpoint.split("/")
            idx = parts.index("devices")
            if idx + 1 < len(parts):
                device_id = parts[idx + 1]

        # Handle different endpoints
        if endpoint == "devices" or endpoint == "/devices":
            # List devices
            return self._mock_get_devices()
        elif device_id and endpoint.endswith("/readings"):
            # Get device readings
            return self._mock_get_device_readings(device_id)
        elif device_id and endpoint.endswith("/temperature"):
            # Get temperature data
            probe_id = params.get("probe_id") if params else None
            return self._mock_get_temperature_data(device_id, probe_id)
        elif device_id and endpoint.endswith("/history"):
            # Get historical data
            start_time = params.get("start") if params else None
            end_time = params.get("end") if params else None
            probe_id = params.get("probe_id") if params else None
            return self._mock_get_historical_data(device_id, probe_id, start_time, end_time)
        else:
            # Unknown endpoint
            logger.warning("Unknown mock endpoint: %s", endpoint)
            return {}

    def _mock_get_devices(self) -> List[Dict[str, Any]]:
        """Get mock devices list."""
        return [
            {
                "device_id": "device_1",
                "name": "Smoker Thermometer",
                "model": "Signals",
                "firmware_version": "2.1.0",
                "last_seen": datetime.utcnow().isoformat(),
                "battery_level": 75,
                "signal_strength": 90,
                "is_online": True,
                "probes": [
                    {"probe_id": "probe_1", "type": "meat", "name": "Brisket Probe"},
                    {"probe_id": "probe_2", "type": "ambient", "name": "Grill Probe"},
                ],
            },
            {
                "device_id": "device_2",
                "name": "Kitchen Thermometer",
                "model": "ChefAlarm",
                "firmware_version": "1.5.2",
                "last_seen": datetime.utcnow().isoformat(),
                "battery_level": 60,
                "signal_strength": 80,
                "is_online": True,
                "probes": [
                    {"probe_id": "probe_1", "type": "meat", "name": "Food Probe"},
                ],
            },
        ]

    def _mock_get_device_readings(self, device_id: str) -> Dict[str, Any]:
        """Get mock device readings."""
        if device_id == "device_1":
            return {
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "readings": [
                    {
                        "probe_id": "probe_1",
                        "temperature": 165.5,
                        "unit": "F",
                        "type": "meat",
                        "name": "Brisket Probe",
                    },
                    {
                        "probe_id": "probe_2",
                        "temperature": 225.0,
                        "unit": "F",
                        "type": "ambient",
                        "name": "Grill Probe",
                    },
                ],
                "status": {
                    "battery_level": 75,
                    "signal_strength": 90,
                    "connection_status": "connected",
                },
            }
        elif device_id == "device_2":
            return {
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "readings": [
                    {
                        "probe_id": "probe_1",
                        "temperature": 145.2,
                        "unit": "F",
                        "type": "meat",
                        "name": "Food Probe",
                    }
                ],
                "status": {
                    "battery_level": 60,
                    "signal_strength": 80,
                    "connection_status": "connected",
                },
            }
        else:
            return {
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "readings": [],
                "status": {
                    "battery_level": 0,
                    "signal_strength": 0,
                    "connection_status": "disconnected",
                },
            }

    def _mock_get_temperature_data(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get mock temperature data."""
        readings = self._mock_get_device_readings(device_id)

        # Find specific probe if requested
        if probe_id:
            for reading in readings.get("readings", []):
                if reading.get("probe_id") == probe_id:
                    return {
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "temperature": reading.get("temperature"),
                        "unit": reading.get("unit", "F"),
                        "timestamp": readings.get("timestamp", datetime.utcnow().isoformat()),
                        "battery_level": readings.get("status", {}).get("battery_level"),
                        "signal_strength": readings.get("status", {}).get("signal_strength"),
                    }

            # Probe not found
            return {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": None,
                "unit": "F",
                "timestamp": datetime.utcnow().isoformat(),
                "battery_level": None,
                "signal_strength": None,
            }

        # Return first probe if no specific probe requested
        if readings.get("readings"):
            reading = readings["readings"][0]
            return {
                "device_id": device_id,
                "probe_id": reading.get("probe_id"),
                "temperature": reading.get("temperature"),
                "unit": reading.get("unit", "F"),
                "timestamp": readings.get("timestamp", datetime.utcnow().isoformat()),
                "battery_level": readings.get("status", {}).get("battery_level"),
                "signal_strength": readings.get("status", {}).get("signal_strength"),
            }

        # No readings
        return {
            "device_id": device_id,
            "probe_id": None,
            "temperature": None,
            "unit": "F",
            "timestamp": datetime.utcnow().isoformat(),
            "battery_level": None,
            "signal_strength": None,
        }

    def _mock_get_historical_data(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get mock historical data."""
        # Generate some historical data points
        now = datetime.utcnow()

        # Default to last hour if no time range specified
        if not start_time:
            start_time = (now - datetime.timedelta(hours=1)).isoformat()
        if not end_time:
            end_time = now.isoformat()

        # Parse time range
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            start_dt = now - datetime.timedelta(hours=1)
            end_dt = now

        # Generate mock data
        data = []

        # Determine base temperature based on device and probe
        base_temp = 225.0
        if device_id == "device_1":
            if probe_id == "probe_1":
                base_temp = 160.0  # Brisket
            elif probe_id == "probe_2":
                base_temp = 225.0  # Grill
        elif device_id == "device_2":
            base_temp = 145.0  # Food

        # Generate data points
        duration = (end_dt - start_dt).total_seconds()
        num_points = min(100, int(duration / 60))  # One point per minute, max 100

        if num_points <= 0:
            num_points = 1

        interval = duration / num_points

        for i in range(num_points):
            # Calculate timestamp
            point_time = start_dt + datetime.timedelta(seconds=i * interval)

            # Calculate temperature with some variation
            variation = (i / num_points) * 10.0  # Gradually increase by up to 10 degrees
            noise = ((i * 7919) % 10) / 5.0 - 1.0  # Pseudo-random noise between -1 and 1
            temperature = base_temp + variation + noise

            # Create data point
            data_point = {
                "device_id": device_id,
                "timestamp": point_time.isoformat(),
                "temperature": round(temperature, 1),
                "unit": "F",
                "battery_level": max(50, 100 - i // 10),  # Gradually decrease battery
                "signal_strength": max(60, 95 - i // 20),  # Gradually decrease signal
            }

            if probe_id:
                data_point["probe_id"] = probe_id

            data.append(data_point)

        return data

    @trace_async_function(name="thermoworks_get_devices")
    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get all ThermoWorks devices.

        Returns:
            List of devices
        """
        try:
            result = await self._request("GET", "/devices")
            logger.debug("Retrieved %d ThermoWorks devices", len(result))
            return result
        except Exception as e:
            logger.error("Failed to get ThermoWorks devices: %s", str(e))
            return []

    @trace_async_function(name="thermoworks_get_device_readings")
    async def get_device_readings(self, device_id: str) -> Dict[str, Any]:
        """Get readings for a specific device.

        Args:
            device_id: Device ID

        Returns:
            Device readings data
        """
        try:
            result = await self._request("GET", f"/devices/{device_id}/readings")
            logger.debug("Retrieved readings for device %s", device_id)
            return result
        except Exception as e:
            logger.error("Failed to get readings for device %s: %s", device_id, str(e))
            return {}

    @trace_async_function(name="thermoworks_get_temperature_data")
    async def get_temperature_data(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get current temperature data for a device.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID

        Returns:
            Temperature data
        """
        try:
            endpoint = f"/devices/{device_id}/temperature"
            params = {}

            if probe_id:
                params["probe_id"] = probe_id

            data = await self._request("GET", endpoint, params=params)

            # Format response
            result = {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": data.get("temperature"),
                "unit": data.get("unit", "F"),
                "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                "battery_level": data.get("battery_level"),
                "signal_strength": data.get("signal_strength"),
            }

            logger.debug(
                "Retrieved temperature data for device %s: %.1f%s",
                device_id,
                result.get("temperature", 0),
                result.get("unit", "F"),
            )

            return result
        except Exception as e:
            logger.error("Failed to get temperature data for device %s: %s", device_id, str(e))
            return {}

    @trace_async_function(name="thermoworks_get_historical_data")
    async def get_historical_data(
        self,
        device_id: str,
        start_time: str,
        end_time: str,
        probe_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical temperature data.

        Args:
            device_id: Device ID
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            probe_id: Optional probe ID

        Returns:
            List of historical temperature readings
        """
        try:
            params = {"start": start_time, "end": end_time}

            if probe_id:
                params["probe_id"] = probe_id

            result = await self._request("GET", f"/devices/{device_id}/history", params=params)

            logger.debug("Retrieved %d historical data points for device %s", len(result), device_id)

            return result
        except Exception as e:
            logger.error("Failed to get historical data for device %s: %s", device_id, str(e))
            return []

    @trace_async_function(name="thermoworks_get_device_data")
    async def get_device_data(self, device_id: str) -> Dict[str, Any]:
        """Get comprehensive device data including all channels/probes.

        Args:
            device_id: Device ID

        Returns:
            Complete device data
        """
        try:
            # Get device readings (includes all probes)
            readings = await self.get_device_readings(device_id)

            # Format channels
            channels = []
            for reading in readings.get("readings", []):
                channel = {
                    "channel_id": reading.get("probe_id"),
                    "probe_type": reading.get("type", "meat"),
                    "temperature": reading.get("temperature"),
                    "unit": reading.get("unit", "F"),
                    "name": reading.get("name", f"Channel {reading.get('probe_id')}"),
                    "is_connected": True,
                }
                channels.append(channel)

            # Create result
            result = {
                "device_id": device_id,
                "timestamp": readings.get("timestamp", datetime.utcnow().isoformat()),
                "channels": channels,
                "status": readings.get(
                    "status",
                    {
                        "battery_level": None,
                        "signal_strength": None,
                        "connection_status": "unknown",
                    },
                ),
            }

            return result
        except Exception as e:
            logger.error("Failed to get device data for %s: %s", device_id, str(e))
            return {
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "channels": [],
                "status": {
                    "battery_level": None,
                    "signal_strength": None,
                    "connection_status": "error",
                    "error": str(e),
                },
            }

    @trace_async_function(name="thermoworks_get_device_status")
    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get device status information.

        Args:
            device_id: Device ID

        Returns:
            Device status data
        """
        try:
            # Get device readings
            readings = await self.get_device_readings(device_id)

            # Extract status information
            status = readings.get("status", {})

            # Add additional fields
            status.update(
                {
                    "device_id": device_id,
                    "last_seen": readings.get("timestamp", datetime.utcnow().isoformat()),
                    "connection_status": status.get("connection_status", "unknown"),
                }
            )

            return status
        except Exception as e:
            logger.error("Failed to get device status for %s: %s", device_id, str(e))
            return {
                "device_id": device_id,
                "connection_status": "error",
                "last_seen": datetime.utcnow().isoformat(),
                "error": str(e),
            }


# Singleton instance for application-wide use
_thermoworks_client: Optional[AsyncThermoworksClient] = None


async def get_thermoworks_client() -> AsyncThermoworksClient:
    """Get or create the ThermoWorks client singleton."""
    global _thermoworks_client

    if _thermoworks_client is None:
        _thermoworks_client = AsyncThermoworksClient()
        await _thermoworks_client.initialize()

    return _thermoworks_client


async def close_thermoworks_client() -> None:
    """Close the ThermoWorks client singleton."""
    global _thermoworks_client

    if _thermoworks_client is not None:
        await _thermoworks_client.close()
        _thermoworks_client = None
