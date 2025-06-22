import requests
import json
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        })
    
    def test_connection(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/api/")
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"Failed to connect to Home Assistant: {e}")
            return False
    
    def get_states(self) -> List[Dict]:
        try:
            response = self.session.get(f"{self.base_url}/api/states")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get states: {e}")
            return []
    
    def get_entity_state(self, entity_id: str) -> Optional[Dict]:
        try:
            response = self.session.get(f"{self.base_url}/api/states/{entity_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get state for {entity_id}: {e}")
            return None
    
    def set_entity_state(self, entity_id: str, state: str, attributes: Optional[Dict] = None) -> bool:
        try:
            data = {
                'state': state,
                'attributes': attributes or {}
            }
            response = self.session.post(f"{self.base_url}/api/states/{entity_id}", json=data)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to set state for {entity_id}: {e}")
            return False
    
    def call_service(self, domain: str, service: str, service_data: Optional[Dict] = None, target: Optional[Dict] = None) -> bool:
        try:
            data = {}
            if service_data:
                data.update(service_data)
            if target:
                data['target'] = target
            
            response = self.session.post(f"{self.base_url}/api/services/{domain}/{service}", json=data)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to call service {domain}.{service}: {e}")
            return False
    
    def create_sensor(self, sensor_name: str, state: Any, attributes: Optional[Dict] = None, unit: Optional[str] = None) -> bool:
        entity_id = f"sensor.{sensor_name}"
        sensor_attributes = attributes or {}
        
        if unit:
            sensor_attributes['unit_of_measurement'] = unit
        
        sensor_attributes.update({
            'friendly_name': sensor_name.replace('_', ' ').title(),
            'device_class': 'temperature' if unit in ['°F', '°C', 'F', 'C'] else None
        })
        
        return self.set_entity_state(entity_id, str(state), sensor_attributes)
    
    def send_notification(self, message: str, title: Optional[str] = None) -> bool:
        service_data = {'message': message}
        if title:
            service_data['title'] = title
        
        return self.call_service('notify', 'persistent_notification', service_data)