import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests
import websockets
from retrying import retry

from ..models.ha_models import HAConfig, HAConnectionStatus, HAEvent, HAHealthStatus, HAServiceCall
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    def __init__(self, config: HAConfig, mock_mode: bool = False):
        self.config = config
        self.mock_mode = mock_mode
        self.session = None
        self.websocket = None
        self.health_status = HAHealthStatus(status=HAConnectionStatus.DISCONNECTED)
        self.metrics = MetricsCollector()
        self.event_handlers: Dict[str, List[Callable]] = {}

        if not mock_mode:
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {config.access_token}",
                    "Content-Type": "application/json",
                }
            )
            self.session.verify = config.verify_ssl

    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def test_connection(self) -> bool:
        if self.mock_mode:
            logger.info("Mock Home Assistant connection test: Success")
            self.health_status.status = HAConnectionStatus.CONNECTED
            self.health_status.last_successful_connection = datetime.utcnow()
            return True

        try:
            start_time = time.time()
            response = self.session.get(f"{self.config.base_url}/api/", timeout=self.config.timeout)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                self.health_status.status = HAConnectionStatus.CONNECTED
                self.health_status.response_time_ms = response_time
                self.health_status.consecutive_failures = 0
                self.health_status.last_successful_connection = datetime.utcnow()
                self.health_status.error_message = None
                self.metrics.record_connection_success(response_time)
                logger.info(f"Home Assistant connection successful ({response_time:.2f}ms)")
                return True
            else:
                raise requests.RequestException(f"HTTP {response.status_code}")

        except requests.RequestException as e:
            self.health_status.status = HAConnectionStatus.ERROR
            self.health_status.consecutive_failures += 1
            self.health_status.error_message = str(e)
            self.metrics.record_connection_failure()
            logger.error(f"Failed to connect to Home Assistant: {e}")
            return False

    def get_states(self) -> List[Dict]:
        if self.mock_mode:
            logger.info("Mock Home Assistant get_states called")
            return []

        try:
            response = self.session.get(f"{self.config.base_url}/api/states", timeout=self.config.timeout)
            response.raise_for_status()
            self.metrics.record_api_call("get_states", True)
            return response.json()
        except requests.RequestException as e:
            self.metrics.record_api_call("get_states", False)
            logger.error(f"Failed to get states: {e}")
            return []

    def get_entity_state(self, entity_id: str) -> Optional[Dict]:
        if self.mock_mode:
            logger.info(f"Mock Home Assistant get_entity_state called for {entity_id}")
            return {"entity_id": entity_id, "state": "unknown", "attributes": {}}

        try:
            response = self.session.get(f"{self.config.base_url}/api/states/{entity_id}", timeout=self.config.timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            self.metrics.record_api_call("get_entity_state", True)
            return response.json()
        except requests.RequestException as e:
            self.metrics.record_api_call("get_entity_state", False)
            logger.error(f"Failed to get state for {entity_id}: {e}")
            return None

    def set_entity_state(self, entity_id: str, state: str, attributes: Optional[Dict] = None) -> bool:
        if self.mock_mode:
            logger.info(f"Mock Home Assistant set_entity_state called for {entity_id} = {state}")
            return True

        try:
            data = {"state": state, "attributes": attributes or {}}
            response = self.session.post(
                f"{self.config.base_url}/api/states/{entity_id}", json=data, timeout=self.config.timeout
            )
            response.raise_for_status()
            self.metrics.record_api_call("set_entity_state", True)
            logger.debug(f"Successfully set state for {entity_id}")
            return True
        except requests.RequestException as e:
            self.metrics.record_api_call("set_entity_state", False)
            logger.error(f"Failed to set state for {entity_id}: {e}")
            return False

    def call_service(self, service_call: HAServiceCall) -> bool:
        if self.mock_mode:
            logger.info(f"Mock Home Assistant call_service called for {service_call.domain}.{service_call.service}")
            return True

        try:
            data = {}
            if service_call.service_data:
                data.update(service_call.service_data)
            if service_call.target:
                data["target"] = service_call.target

            response = self.session.post(
                f"{self.config.base_url}/api/services/{service_call.domain}/{service_call.service}",
                json=data,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            self.metrics.record_service_call(f"{service_call.domain}.{service_call.service}", True)
            logger.debug(f"Successfully called service {service_call.domain}.{service_call.service}")
            return True
        except requests.RequestException as e:
            self.metrics.record_service_call(f"{service_call.domain}.{service_call.service}", False)
            logger.error(f"Failed to call service {service_call.domain}.{service_call.service}: {e}")
            return False

    def send_event(self, event: HAEvent) -> bool:
        if self.mock_mode:
            logger.info(f"Mock Home Assistant send_event called for {event.event_type}")
            return True

        try:
            response = self.session.post(
                f"{self.config.base_url}/api/events/{event.event_type}", json=event.data, timeout=self.config.timeout
            )
            response.raise_for_status()
            self.metrics.record_event_sent(event.event_type, True)
            logger.debug(f"Successfully sent event {event.event_type}")
            return True
        except requests.RequestException as e:
            self.metrics.record_event_sent(event.event_type, False)
            logger.error(f"Failed to send event {event.event_type}: {e}")
            return False

    async def connect_websocket(self):
        if self.mock_mode:
            logger.info("Mock WebSocket connection established")
            return

        if not self.config.websocket_enabled:
            return

        try:
            ws_url = f"{self.config.base_url.replace('http', 'ws')}/api/websocket"
            self.websocket = await websockets.connect(ws_url)

            # Authenticate WebSocket connection
            auth_msg = {"type": "auth", "access_token": self.config.access_token}
            await self.websocket.send(json.dumps(auth_msg))

            # Subscribe to state changes
            subscribe_msg = {"id": 1, "type": "subscribe_events", "event_type": "state_changed"}
            await self.websocket.send(json.dumps(subscribe_msg))

            logger.info("WebSocket connection established and subscribed to events")

            # Start listening for events
            asyncio.create_task(self._websocket_listener())

        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            self.websocket = None

    async def _websocket_listener(self):
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_websocket_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.websocket = None
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")

    async def _handle_websocket_message(self, data: Dict):
        if data.get("type") == "event" and data.get("event", {}).get("event_type") == "state_changed":
            event_data = data["event"]["data"]
            entity_id = event_data.get("entity_id")

            # Trigger registered event handlers
            for handler in self.event_handlers.get("state_changed", []):
                try:
                    await handler(entity_id, event_data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    def register_event_handler(self, event_type: str, handler: Callable):
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def get_health_status(self) -> HAHealthStatus:
        self.health_status.last_check = datetime.utcnow()
        return self.health_status

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.get_metrics()

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        if self.session:
            self.session.close()
            self.session = None
