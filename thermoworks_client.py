import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ThermoWorksClient:
    def __init__(self, api_key: str, base_url: str = "https://api.thermoworks.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def get_devices(self) -> List[Dict]:
        try:
            response = self.session.get(f"{self.base_url}/devices")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get devices: {e}")
            return []
    
    def get_device_readings(self, device_id: str) -> Dict:
        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}/readings")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get readings for device {device_id}: {e}")
            return {}
    
    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Dict:
        try:
            endpoint = f"{self.base_url}/devices/{device_id}/temperature"
            if probe_id:
                endpoint += f"/{probe_id}"
            
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()
            
            return {
                'device_id': device_id,
                'probe_id': probe_id,
                'temperature': data.get('temperature'),
                'unit': data.get('unit', 'F'),
                'timestamp': data.get('timestamp', datetime.now().isoformat()),
                'battery_level': data.get('battery_level'),
                'signal_strength': data.get('signal_strength')
            }
        except requests.RequestException as e:
            logger.error(f"Failed to get temperature data: {e}")
            return {}
    
    def get_historical_data(self, device_id: str, start_time: str, end_time: str) -> List[Dict]:
        try:
            params = {
                'start': start_time,
                'end': end_time
            }
            response = self.session.get(f"{self.base_url}/devices/{device_id}/history", params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get historical data: {e}")
            return []