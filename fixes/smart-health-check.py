# Enhanced Health Check Logic for Microservices
# This handles expected database connection errors gracefully

import datetime
from flask import jsonify

# Example managers and clients that would be properly imported in production
class DeviceManager:
    def health_check(self):
        # Mock implementation
        return True

class TemperatureManager:
    def health_check(self):
        # Mock implementation
        return True

class RedisClient:
    def ping(self):
        # Mock implementation
        return True

# Initialize mock objects for testing
device_manager = DeviceManager()
temperature_manager = TemperatureManager()
redis_client = RedisClient()

# Flask app stub
class App:
    def route(self, rule):
        def decorator(f):
            return f
        return decorator

app = App()

def enhanced_health_check(service_type="device"):
    """
    Enhanced health check that distinguishes between:
    - Service failures (bad)
    - Expected dependency failures (acceptable for testing)
    """
    
    health_status = {
        'service': 'healthy',
        'dependencies': {},
        'overall_status': 'healthy'
    }
    
    try:
        if service_type == "device":
            # Test database connection
            try:
                device_manager.health_check()
                health_status['dependencies']['database'] = 'healthy'
            except Exception as e:
                if "connection" in str(e).lower() or "resolve" in str(e).lower():
                    health_status['dependencies']['database'] = 'unavailable'
                    health_status['overall_status'] = 'degraded'
                else:
                    health_status['dependencies']['database'] = 'error'
                    health_status['overall_status'] = 'unhealthy'
        
        elif service_type == "temperature":
            # Test InfluxDB connection
            try:
                temperature_manager.health_check()
                health_status['dependencies']['influxdb'] = 'healthy'
            except Exception as e:
                if "connection" in str(e).lower() or "resolve" in str(e).lower():
                    health_status['dependencies']['influxdb'] = 'unavailable'
                    health_status['overall_status'] = 'degraded'
                else:
                    health_status['dependencies']['influxdb'] = 'error'
                    health_status['overall_status'] = 'unhealthy'
            
            # Test Redis connection
            try:
                redis_client.ping()
                health_status['dependencies']['redis'] = 'healthy'
            except Exception as e:
                if "connection" in str(e).lower() or "resolve" in str(e).lower():
                    health_status['dependencies']['redis'] = 'unavailable'
                    health_status['overall_status'] = 'degraded'
                else:
                    health_status['dependencies']['redis'] = 'error'
                    health_status['overall_status'] = 'unhealthy'
        
        # Determine HTTP status code
        if health_status['overall_status'] == 'healthy':
            return health_status, 200
        elif health_status['overall_status'] == 'degraded':
            return health_status, 200  # Still acceptable for testing
        else:
            return health_status, 500
    
    except Exception as e:
        return {
            'service': 'error',
            'error': str(e),
            'overall_status': 'unhealthy'
        }, 500

# Usage in Flask endpoints:
@app.route('/health')
def health_check():
    health_data, status_code = enhanced_health_check("device")
    health_data['timestamp'] = datetime.utcnow().isoformat()
    health_data['service_name'] = 'device-service'
    health_data['version'] = '1.0.0'
    
    return jsonify(health_data), status_code