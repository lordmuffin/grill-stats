import requests
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class ThermoWorksClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.thermoworks.com", mock_mode: Optional[bool] = None):
        self.api_key = api_key
        self.base_url = base_url
        
        # Determine if mock mode should be used
        if mock_mode is None:
            mock_mode = os.getenv('MOCK_MODE', 'false').lower() in ('true', '1', 'yes', 'on')
        
        self.mock_mode = mock_mode and not os.getenv('FLASK_ENV', '').lower() == 'production'
        
        if self.mock_mode:
            logger.info("ThermoWorks temperature service client initialized in MOCK MODE")
            # Import and initialize mock service
            try:
                import sys
                sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
                from mock_data import MockDataService
                self.mock_service = MockDataService()
            except ImportError as e:
                logger.error("Failed to import MockDataService", error=str(e))
                self.mock_mode = False
                self.mock_service = None
        else:
            logger.info("ThermoWorks temperature service client initialized in LIVE MODE")
            self.mock_service = None
        
        # Initialize real session for non-mock mode
        if not self.mock_mode:
            self.session = requests.Session()
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'grill-stats-temperature-service/1.0'
            }
            
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            else:
                logger.warning("ThermoWorks client initialized without API key, will return mock data")
                
            self.session.headers.update(headers)
    
    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Dict:
        """Get current temperature data from ThermoWorks API"""
        if self.mock_mode and self.mock_service:
            return self.mock_service.get_temperature_data(device_id, probe_id)
            
        if not self.api_key:
            # Return mock data for testing
            mock_data = {
                'device_id': device_id,
                'probe_id': probe_id,
                'temperature': 72.0,
                'unit': 'F',
                'timestamp': datetime.utcnow().isoformat(),
                'battery_level': 100,
                'signal_strength': 100,
                'metadata': {
                    'source': 'mock_data',
                    'api_version': '1.0',
                    'device_type': 'mock',
                    'probe_type': 'mock'
                }
            }
            logger.debug("Returning mock temperature data", device_id=device_id)
            return mock_data
            
        try:
            endpoint = f"{self.base_url}/devices/{device_id}/temperature"
            if probe_id:
                endpoint += f"/{probe_id}"
            
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()
            
            # Normalize temperature data
            normalized_data = {
                'device_id': device_id,
                'probe_id': probe_id,
                'temperature': data.get('temperature'),
                'unit': data.get('unit', 'F'),
                'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
                'battery_level': data.get('battery_level'),
                'signal_strength': data.get('signal_strength'),
                'metadata': {
                    'source': 'thermoworks_api',
                    'api_version': data.get('api_version', '1.0'),
                    'device_type': data.get('device_type'),
                    'probe_type': data.get('probe_type')
                }
            }
            
            logger.info("Temperature data retrieved from ThermoWorks", 
                       device_id=device_id, 
                       temperature=normalized_data['temperature'])
            
            return normalized_data
            
        except requests.RequestException as e:
            logger.error("Failed to get temperature data from ThermoWorks", 
                        device_id=device_id, 
                        error=str(e))
            return {}
    
    def get_multiple_temperature_readings(self, device_ids: List[str]) -> List[Dict]:
        """Get temperature readings for multiple devices"""
        try:
            # Batch request to ThermoWorks API
            batch_data = {
                'device_ids': device_ids,
                'include_metadata': True
            }
            
            response = self.session.post(f"{self.base_url}/devices/temperature/batch", json=batch_data)
            response.raise_for_status()
            
            batch_results = response.json()
            
            # Normalize batch results
            normalized_readings = []
            for result in batch_results.get('readings', []):
                normalized_reading = {
                    'device_id': result.get('device_id'),
                    'probe_id': result.get('probe_id'),
                    'temperature': result.get('temperature'),
                    'unit': result.get('unit', 'F'),
                    'timestamp': result.get('timestamp', datetime.utcnow().isoformat()),
                    'battery_level': result.get('battery_level'),
                    'signal_strength': result.get('signal_strength'),
                    'metadata': {
                        'source': 'thermoworks_api_batch',
                        'batch_id': batch_results.get('batch_id'),
                        'device_type': result.get('device_type'),
                        'probe_type': result.get('probe_type')
                    }
                }
                normalized_readings.append(normalized_reading)
            
            logger.info("Batch temperature data retrieved from ThermoWorks", 
                       count=len(normalized_readings))
            
            return normalized_readings
            
        except requests.RequestException as e:
            logger.error("Failed to get batch temperature data from ThermoWorks", 
                        device_ids=device_ids, 
                        error=str(e))
            return []
    
    def get_historical_temperature_data(self, device_id: str, start_time: str, end_time: str,
                                      probe_id: Optional[str] = None) -> List[Dict]:
        """Get historical temperature data from ThermoWorks API"""
        try:
            params = {
                'start': start_time,
                'end': end_time
            }
            
            if probe_id:
                params['probe_id'] = probe_id
            
            response = self.session.get(
                f"{self.base_url}/devices/{device_id}/temperature/history", 
                params=params
            )
            response.raise_for_status()
            
            historical_data = response.json()
            
            # Normalize historical data
            normalized_data = []
            for reading in historical_data.get('readings', []):
                normalized_reading = {
                    'device_id': device_id,
                    'probe_id': reading.get('probe_id'),
                    'temperature': reading.get('temperature'),
                    'unit': reading.get('unit', 'F'),
                    'timestamp': reading.get('timestamp'),
                    'battery_level': reading.get('battery_level'),
                    'signal_strength': reading.get('signal_strength'),
                    'metadata': {
                        'source': 'thermoworks_api_historical',
                        'device_type': reading.get('device_type'),
                        'probe_type': reading.get('probe_type')
                    }
                }
                normalized_data.append(normalized_reading)
            
            logger.info("Historical temperature data retrieved from ThermoWorks", 
                       device_id=device_id, 
                       count=len(normalized_data))
            
            return normalized_data
            
        except requests.RequestException as e:
            logger.error("Failed to get historical temperature data from ThermoWorks", 
                        device_id=device_id, 
                        error=str(e))
            return []
    
    def get_device_probes(self, device_id: str) -> List[Dict]:
        """Get probe information for a device"""
        try:
            response = self.session.get(f"{self.base_url}/devices/{device_id}/probes")
            response.raise_for_status()
            
            probes_data = response.json()
            
            logger.info("Device probes retrieved from ThermoWorks", 
                       device_id=device_id, 
                       count=len(probes_data.get('probes', [])))
            
            return probes_data.get('probes', [])
            
        except requests.RequestException as e:
            logger.error("Failed to get device probes from ThermoWorks", 
                        device_id=device_id, 
                        error=str(e))
            return []
    
    def test_api_connection(self) -> bool:
        """Test ThermoWorks API connection"""
        try:
            response = self.session.get(f"{self.base_url}/ping")
            return response.status_code == 200
            
        except requests.RequestException as e:
            logger.error("ThermoWorks API connection test failed", error=str(e))
            return False