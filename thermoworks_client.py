import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class ThermoWorksClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.thermoworks.com",
        mock_mode: bool = None,
    ):
        self.api_key = api_key
        self.base_url = base_url

        # Determine if mock mode should be used
        if mock_mode is None:
            mock_mode = os.getenv("MOCK_MODE", "false").lower() in (
                "true",
                "1",
                "yes",
                "on",
            )

        self.mock_mode = mock_mode and not os.getenv("FLASK_ENV", "").lower() == "production"

        if self.mock_mode:
            logger.info("ThermoWorks client initialized in MOCK MODE")
            # Import and initialize mock service
            try:
                from services.mock_data import MockDataService

                self.mock_service = MockDataService()
            except ImportError as e:
                logger.error("Failed to import MockDataService: %s", e)
                self.mock_mode = False
                self.mock_service = None
        else:
            logger.info("ThermoWorks client initialized in LIVE MODE")
            self.mock_service = None

        # Initialize real session for non-mock mode
        if not self.mock_mode:
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            )

    def get_devices(self) -> List[Dict]:
        if self.mock_mode and self.mock_service:
            return self.mock_service.get_devices()

        try:
            response = self.session.get(f"{self.base_url}/devices")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get devices: {e}")
            return []

    def get_device_readings(self, device_id: str) -> Dict:
        if self.mock_mode and self.mock_service:
            return self.mock_service.get_device_status(device_id)

        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}/readings")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get readings for device {device_id}: {e}")
            return {}

    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Dict:
        if self.mock_mode and self.mock_service:
            return self.mock_service.get_temperature_data(device_id, probe_id)

        try:
            endpoint = f"{self.base_url}/devices/{device_id}/temperature"
            if probe_id:
                endpoint += f"/{probe_id}"

            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()

            return {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": data.get("temperature"),
                "unit": data.get("unit", "F"),
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
                "battery_level": data.get("battery_level"),
                "signal_strength": data.get("signal_strength"),
            }
        except requests.RequestException as e:
            logger.error(f"Failed to get temperature data: {e}")
            return {}

    def get_historical_data(
        self,
        device_id: str,
        start_time: str,
        end_time: str,
        probe_id: Optional[str] = None,
    ) -> List[Dict]:
        if self.mock_mode and self.mock_service:
            from datetime import datetime

            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                return self.mock_service.get_historical_data(device_id, probe_id or "probe_1", start_dt, end_dt)
            except Exception as e:
                logger.error(f"Failed to parse datetime in mock mode: {e}")
                return []

        try:
            params = {"start": start_time, "end": end_time}
            if probe_id:
                params["probe_id"] = probe_id

            response = self.session.get(f"{self.base_url}/devices/{device_id}/history", params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
