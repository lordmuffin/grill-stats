"""
Home Assistant API client for the Grill Stats SDK.

This module provides a client for interacting with the Home Assistant API to
create/update sensors, send notifications, and call services.
"""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from .base_client import APIError, BaseClient

logger = logging.getLogger(__name__)


class HomeAssistantClient(BaseClient):
    """
    Client for interacting with the Home Assistant API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        mock_mode: bool = False,
        timeout: int = 10,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Home Assistant client.

        Args:
            base_url: Base URL for the Home Assistant API.
            access_token: Long-lived access token for authentication.
            mock_mode: Whether to run in mock mode.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            **kwargs: Additional arguments.
        """
        if mock_mode:
            logger.info("HomeAssistantClient initialized in MOCK MODE")
            base_url = "http://mock-homeassistant"
            access_token = "mock-token"
        else:
            if not base_url or not access_token:
                raise ValueError("base_url and access_token are required when not in mock mode")

        super().__init__(
            base_url=base_url,
            api_key=access_token,
            timeout=timeout,
            max_retries=max_retries,
            mock_mode=mock_mode,
            **kwargs,
        )

    def test_connection(self) -> bool:
        """
        Test the connection to the Home Assistant API.

        Returns:
            True if the connection is successful, False otherwise.
        """
        if self.mock_mode:
            logger.info("Mock Home Assistant connection test: Success")
            return True

        try:
            response = self.get("api/")
            return True
        except APIError as e:
            logger.error(f"Failed to connect to Home Assistant: {e}")
            return False

    def get_states(self) -> List[Dict[str, Any]]:
        """
        Get all entity states.

        Returns:
            List of entity states.
        """
        if self.mock_mode:
            logger.info("Mock Home Assistant get_states called")
            return []

        try:
            response = self.get("api/states")
            return cast(List[Dict[str, Any]], response)
        except APIError as e:
            logger.error(f"Failed to get states: {e}")
            return []

    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the state of a specific entity.

        Args:
            entity_id: The entity ID.

        Returns:
            Entity state if found, None otherwise.
        """
        if self.mock_mode:
            logger.info(f"Mock Home Assistant get_entity_state called for {entity_id}")
            return None

        try:
            response = self.get(f"api/states/{entity_id}")
            return cast(Dict[str, Any], response)
        except APIError as e:
            if getattr(e, "status_code", None) == 404:
                return None
            logger.error(f"Failed to get state for {entity_id}: {e}")
            return None

    def set_entity_state(self, entity_id: str, state: str, attributes: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set the state of a specific entity.

        Args:
            entity_id: The entity ID.
            state: The state value.
            attributes: Entity attributes.

        Returns:
            True if successful, False otherwise.
        """
        if self.mock_mode:
            logger.info(f"Mock Home Assistant set_entity_state called for {entity_id} = {state}")
            return True

        try:
            data = {"state": state, "attributes": attributes or {}}
            self.post(f"api/states/{entity_id}", data=data)
            return True
        except APIError as e:
            logger.error(f"Failed to set state for {entity_id}: {e}")
            return False

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None,
        target: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Call a Home Assistant service.

        Args:
            domain: The service domain.
            service: The service name.
            service_data: Service data.
            target: Service target.

        Returns:
            True if successful, False otherwise.
        """
        if self.mock_mode:
            logger.info(f"Mock Home Assistant call_service called for {domain}.{service}")
            return True

        try:
            data: Dict[str, Any] = {}
            if service_data:
                data.update(service_data)
            if target:
                data["target"] = target

            self.post(f"api/services/{domain}/{service}", data=data)
            return True
        except APIError as e:
            logger.error(f"Failed to call service {domain}.{service}: {e}")
            return False

    def create_sensor(
        self,
        sensor_name: str,
        state: Any,
        attributes: Optional[Dict[str, Any]] = None,
        unit: Optional[str] = None,
    ) -> bool:
        """
        Create or update a sensor entity.

        Args:
            sensor_name: The sensor name.
            state: The sensor state.
            attributes: Sensor attributes.
            unit: Unit of measurement.

        Returns:
            True if successful, False otherwise.
        """
        if self.mock_mode:
            logger.info(f"Mock sensor created: {sensor_name} = {state}{unit if unit else ''}")
            return True

        entity_id = f"sensor.{sensor_name}"
        sensor_attributes = attributes or {}

        if unit:
            sensor_attributes["unit_of_measurement"] = unit

        sensor_attributes.update(
            {
                "friendly_name": sensor_name.replace("_", " ").title(),
                "device_class": ("temperature" if unit in ["°F", "°C", "F", "C"] else None),
            }
        )

        return self.set_entity_state(entity_id, str(state), sensor_attributes)

    def send_notification(self, message: str, title: Optional[str] = None) -> bool:
        """
        Send a notification via Home Assistant.

        Args:
            message: The notification message.
            title: The notification title.

        Returns:
            True if successful, False otherwise.
        """
        if self.mock_mode:
            logger.info(f"Mock Home Assistant notification: {title if title else 'Notification'} - {message}")
            return True

        service_data = {"message": message}
        if title:
            service_data["title"] = title

        return self.call_service("notify", "persistent_notification", service_data)
