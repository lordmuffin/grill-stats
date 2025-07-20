"""
ThermoWorks API client for the Grill Stats SDK.

This module provides a client for interacting with the ThermoWorks API to
retrieve device information, temperature data, and historical readings.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast

from .base_client import APIError, BaseClient

logger = logging.getLogger(__name__)


class ThermoWorksClient(BaseClient):
    """
    Client for interacting with the ThermoWorks API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.thermoworks.com",
        mock_mode: bool = False,
        timeout: int = 10,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the ThermoWorks client.

        Args:
            api_key: ThermoWorks API key.
            base_url: Base URL for the ThermoWorks API.
            mock_mode: Whether to run in mock mode.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            **kwargs: Additional arguments.
        """
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            mock_mode=mock_mode,
            **kwargs,
        )

        # Initialize the mock service if in mock mode
        self.mock_service = None
        if self.mock_mode:
            try:
                # Import locally to avoid dependency if not needed
                from services.mock_data import MockDataService

                self.mock_service = MockDataService()
                logger.info("ThermoWorks client initialized in MOCK MODE")
            except ImportError as e:
                logger.warning(f"Failed to import MockDataService: {e}")
                logger.warning("Mock mode enabled but MockDataService not available")

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Get a list of all ThermoWorks devices.

        Returns:
            List of device objects.
        """
        if self.mock_mode and self.mock_service:
            devices = self.mock_service.get_devices()
            return devices

        try:
            response = self.get("devices")
            return cast(List[Dict[str, Any]], response)
        except APIError as e:
            logger.error(f"Failed to get devices: {e}")
            return []

    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a device by ID.

        Args:
            device_id: The device ID.

        Returns:
            Device object if found, None otherwise.
        """
        if self.mock_mode and self.mock_service:
            # Try to find the device in the mock devices
            devices = self.mock_service.get_devices()
            for device in devices:
                if device.get("id") == device_id:
                    return device
            return None

        try:
            response = self.get(f"devices/{device_id}")
            return cast(Dict[str, Any], response)
        except APIError as e:
            logger.error(f"Failed to get device {device_id}: {e}")
            return None

    def get_device_readings(self, device_id: str) -> Dict[str, Any]:
        """
        Get readings for a device.

        Args:
            device_id: The device ID.

        Returns:
            Device readings.
        """
        if self.mock_mode and self.mock_service:
            readings = self.mock_service.get_device_status(device_id)
            return readings

        try:
            response = self.get(f"devices/{device_id}/readings")
            return cast(Dict[str, Any], response)
        except APIError as e:
            logger.error(f"Failed to get readings for device {device_id}: {e}")
            return {}

    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get temperature data for a device.

        Args:
            device_id: The device ID.
            probe_id: The probe ID (optional).

        Returns:
            Temperature data.
        """
        if self.mock_mode and self.mock_service:
            temp_data = self.mock_service.get_temperature_data(device_id, probe_id)
            return temp_data

        try:
            endpoint = f"devices/{device_id}/temperature"
            if probe_id:
                endpoint += f"/{probe_id}"

            response = self.get(endpoint)

            # Normalize the response format
            return {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": response.get("temperature"),
                "unit": response.get("unit", "F"),
                "timestamp": response.get("timestamp", datetime.now().isoformat()),
                "battery_level": response.get("battery_level"),
                "signal_strength": response.get("signal_strength"),
            }
        except APIError as e:
            logger.error(f"Failed to get temperature data for device {device_id}: {e}")
            return {}

    def get_historical_data(
        self,
        device_id: str,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        probe_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get historical temperature data for a device.

        Args:
            device_id: The device ID.
            start_time: Start time (ISO format string or datetime).
            end_time: End time (ISO format string or datetime).
            probe_id: The probe ID (optional).

        Returns:
            List of historical temperature readings.
        """
        # Convert datetime objects to ISO format strings
        if isinstance(start_time, datetime):
            start_time = start_time.isoformat()
        if isinstance(end_time, datetime):
            end_time = end_time.isoformat()

        if self.mock_mode and self.mock_service:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                history_data = self.mock_service.get_historical_data(device_id, probe_id or "probe_1", start_dt, end_dt)
                return history_data
            except Exception as e:
                logger.error(f"Failed to parse datetime in mock mode: {e}")
                return []

        try:
            params = {"start": start_time, "end": end_time}
            if probe_id:
                params["probe_id"] = probe_id

            response = self.get(f"devices/{device_id}/history", params=params)
            return cast(List[Dict[str, Any]], response)
        except APIError as e:
            logger.error(f"Failed to get historical data for device {device_id}: {e}")
            return []
