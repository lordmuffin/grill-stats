import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class ThermoWorksClient:
    def __init__(self, api_key: str, base_url: str = "https://api.thermoworks.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'grill-monitoring/1.0'
        })
    
    def get_devices(self) -> List[Dict]:
        """Get all devices from ThermoWorks API"""
        try:
            response = self.session.get(f"{self.base_url}/devices")
            response.raise_for_status()
            
            devices = response.json()
            logger.info("Retrieved devices from ThermoWorks", count=len(devices))
            return devices
            
        except requests.RequestException as e:
            logger.error("Failed to get devices from ThermoWorks", error=str(e))
            return []
    
    def get_device_info(self, device_id: str) -> Dict:
        """Get specific device information"""
        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}")
            response.raise_for_status()
            
            device_info = response.json()
            logger.info("Retrieved device info", device_id=device_id)
            return device_info
            
        except requests.RequestException as e:
            logger.error("Failed to get device info", device_id=device_id, error=str(e))
            return {}
    
    def get_device_health(self, device_id: str) -> Dict:
        """Get device health status"""
        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}/health")
            response.raise_for_status()
            
            health_data = response.json()
            
            # Normalize health data
            normalized_health = {
                'device_id': device_id,
                'battery_level': health_data.get('battery_level'),
                'signal_strength': health_data.get('signal_strength'),
                'last_seen': health_data.get('last_seen'),
                'status': health_data.get('status', 'unknown'),
                'connectivity': health_data.get('connectivity', 'unknown'),
                'firmware_version': health_data.get('firmware_version'),
                'checked_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Retrieved device health", device_id=device_id, status=normalized_health['status'])
            return normalized_health
            
        except requests.RequestException as e:
            logger.error("Failed to get device health", device_id=device_id, error=str(e))
            return {
                'device_id': device_id,
                'status': 'error',
                'error': str(e),
                'checked_at': datetime.utcnow().isoformat()
            }
    
    def get_device_configuration(self, device_id: str) -> Dict:
        """Get device configuration"""
        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}/config")
            response.raise_for_status()
            
            config_data = response.json()
            logger.info("Retrieved device configuration", device_id=device_id)
            return config_data
            
        except requests.RequestException as e:
            logger.error("Failed to get device configuration", device_id=device_id, error=str(e))
            return {}
    
    def update_device_configuration(self, device_id: str, config_data: Dict) -> bool:
        """Update device configuration"""
        try:
            response = self.session.put(
                f"{self.base_url}/devices/{device_id}/config",
                json=config_data
            )
            response.raise_for_status()
            
            logger.info("Updated device configuration", device_id=device_id)
            return True
            
        except requests.RequestException as e:
            logger.error("Failed to update device configuration", device_id=device_id, error=str(e))
            return False
    
    def test_api_connection(self) -> bool:
        """Test API connection"""
        try:
            response = self.session.get(f"{self.base_url}/ping")
            return response.status_code == 200
            
        except requests.RequestException as e:
            logger.error("API connection test failed", error=str(e))
            return False