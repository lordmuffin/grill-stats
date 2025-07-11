import os
import logging
from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import structlog
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from temperature_manager import TemperatureManager
from thermoworks_client import ThermoWorksClient
import asyncio
import redis
import json
import time

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize OpenTelemetry
from opentelemetry.sdk.trace import TracerProvider
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize instrumentation
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Initialize clients with graceful degradation
api_key = os.getenv('THERMOWORKS_API_KEY')
if not api_key:
    logger.warning("THERMOWORKS_API_KEY not set, service will run in degraded mode")

thermoworks_client = ThermoWorksClient(
    api_key=api_key,
    base_url=os.getenv('THERMOWORKS_BASE_URL', 'https://api.thermoworks.com')
)

# Initialize database connections with retries
try:
    temperature_manager = TemperatureManager(
        influxdb_host=os.getenv('INFLUXDB_HOST', 'localhost'),
        influxdb_port=int(os.getenv('INFLUXDB_PORT', '8086')),
        influxdb_database=os.getenv('INFLUXDB_DATABASE', 'grill_monitoring'),
        influxdb_username=os.getenv('INFLUXDB_USERNAME'),
        influxdb_password=os.getenv('INFLUXDB_PASSWORD')
    )
    logger.info("InfluxDB connection initialized successfully")
except Exception as e:
    logger.warning(f"InfluxDB connection failed: {e}, service will run in degraded mode")
    temperature_manager = None

# Redis client for real-time data streaming
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', '6379')),
        password=os.getenv('REDIS_PASSWORD'),
        decode_responses=True
    )
    # Test connection
    redis_client.ping()
    logger.info("Redis connection initialized successfully")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}, service will run in degraded mode")
    redis_client = None

# Pydantic models
class TemperatureReading(BaseModel):
    device_id: str
    probe_id: Optional[str] = None
    temperature: float
    unit: str = 'F'
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict] = None

class TemperatureQuery(BaseModel):
    device_id: str
    probe_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    aggregation: Optional[str] = None
    interval: Optional[str] = None

# Health check endpoint
@app.route('/health')
def health_check():
    """Enhanced health check endpoint with smart error handling"""
    health_status = {
        'service': 'temperature-service',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'healthy',
        'dependencies': {},
        'features': {
            'thermoworks_api': bool(api_key),
            'influxdb': bool(temperature_manager),
            'redis': bool(redis_client)
        }
    }
    
    # Check InfluxDB connection
    try:
        temperature_manager.health_check()
        health_status['dependencies']['influxdb'] = 'healthy'
    except Exception as e:
        error_msg = str(e).lower()
        expected_errors = [
            'connection refused', 'name resolution', 'temporary failure',
            'no such host', 'could not translate host name', 'connection reset'
        ]
        
        if any(expected in error_msg for expected in expected_errors):
            health_status['dependencies']['influxdb'] = 'unavailable'
        else:
            health_status['dependencies']['influxdb'] = 'error'
    
    # Check Redis connection
    try:
        redis_client.ping()
        health_status['dependencies']['redis'] = 'healthy'
    except Exception as e:
        error_msg = str(e).lower()
        expected_errors = [
            'connection refused', 'name resolution', 'temporary failure',
            'no such host', 'could not translate host name', 'connection reset'
        ]
        
        if any(expected in error_msg for expected in expected_errors):
            health_status['dependencies']['redis'] = 'unavailable'
        else:
            health_status['dependencies']['redis'] = 'error'
    
    # Determine overall status
    dep_statuses = list(health_status['dependencies'].values())
    
    if all(status == 'healthy' for status in dep_statuses):
        health_status['overall_status'] = 'healthy'
        return jsonify(health_status), 200
    elif all(status in ['healthy', 'unavailable'] for status in dep_statuses):
        health_status['overall_status'] = 'degraded'
        health_status['message'] = 'Service operational, some dependencies unavailable (expected in test environment)'
        logger.warning("Dependencies unavailable (expected in test)")
        return jsonify(health_status), 200
    else:
        health_status['overall_status'] = 'unhealthy'
        health_status['error'] = 'Critical dependency errors detected'
        logger.error("Health check failed with critical errors")
        return jsonify(health_status), 500

# Real-time temperature data endpoint
@app.route('/api/temperature/current/<device_id>', methods=['GET'])
def get_current_temperature(device_id):
    """Get current temperature reading for a device"""
    with tracer.start_as_current_span("get_current_temperature"):
        try:
            probe_id = request.args.get('probe_id')
            
            # Try to get from cache first
            cache_key = f"temperature:current:{device_id}"
            if probe_id:
                cache_key += f":{probe_id}"
            
            cached_data = redis_client.get(cache_key)
            if cached_data:
                temperature_data = json.loads(cached_data)
                logger.info("Temperature data retrieved from cache", device_id=device_id)
                return jsonify({
                    'status': 'success',
                    'data': temperature_data,
                    'source': 'cache'
                })
            
            # Get from ThermoWorks API
            temperature_data = thermoworks_client.get_temperature_data(device_id, probe_id)
            
            if temperature_data:
                # Cache the result
                redis_client.setex(cache_key, 30, json.dumps(temperature_data))  # Cache for 30 seconds
                
                # Store in time-series database
                temperature_manager.store_temperature_reading(temperature_data)
                
                # Publish to real-time stream
                redis_client.publish('temperature_stream', json.dumps(temperature_data))
                
                logger.info("Temperature data retrieved", device_id=device_id, temperature=temperature_data.get('temperature'))
                return jsonify({
                    'status': 'success',
                    'data': temperature_data,
                    'source': 'api'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'No temperature data available'
                }), 404
                
        except Exception as e:
            logger.error("Failed to get current temperature", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Historical temperature data endpoint
@app.route('/api/temperature/history/<device_id>', methods=['GET'])
def get_temperature_history(device_id):
    """Get historical temperature data for a device"""
    with tracer.start_as_current_span("get_temperature_history"):
        try:
            probe_id = request.args.get('probe_id')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            aggregation = request.args.get('aggregation', 'none')
            interval = request.args.get('interval', '1m')
            
            # Parse datetime strings
            if start_time:
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
            
            if end_time:
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
            
            # Get historical data
            history_data = temperature_manager.get_temperature_history(
                device_id=device_id,
                probe_id=probe_id,
                start_time=start_time,
                end_time=end_time,
                aggregation=aggregation,
                interval=interval
            )
            
            logger.info("Temperature history retrieved", 
                       device_id=device_id, 
                       count=len(history_data),
                       start_time=start_time.isoformat(),
                       end_time=end_time.isoformat())
            
            return jsonify({
                'status': 'success',
                'data': history_data,
                'count': len(history_data),
                'query': {
                    'device_id': device_id,
                    'probe_id': probe_id,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'aggregation': aggregation,
                    'interval': interval
                }
            })
            
        except Exception as e:
            logger.error("Failed to get temperature history", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Batch temperature data storage
@app.route('/api/temperature/batch', methods=['POST'])
def store_batch_temperature_data():
    """Store multiple temperature readings at once"""
    with tracer.start_as_current_span("store_batch_temperature_data"):
        try:
            readings = request.json.get('readings', [])
            
            if not readings:
                return jsonify({
                    'status': 'error',
                    'message': 'No readings provided'
                }), 400
            
            # Validate readings
            validated_readings = []
            for reading in readings:
                try:
                    temp_reading = TemperatureReading(**reading)
                    validated_readings.append(temp_reading.dict())
                except ValidationError as e:
                    logger.warning("Invalid temperature reading", reading=reading, error=str(e))
                    continue
            
            # Store readings
            stored_count = temperature_manager.store_batch_temperature_readings(validated_readings)
            
            # Publish to real-time stream
            for reading in validated_readings:
                redis_client.publish('temperature_stream', json.dumps(reading))
            
            logger.info("Batch temperature data stored", count=stored_count)
            return jsonify({
                'status': 'success',
                'stored_count': stored_count,
                'total_count': len(readings)
            })
            
        except Exception as e:
            logger.error("Failed to store batch temperature data", error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Temperature statistics endpoint
@app.route('/api/temperature/stats/<device_id>', methods=['GET'])
def get_temperature_stats(device_id):
    """Get temperature statistics for a device"""
    with tracer.start_as_current_span("get_temperature_stats"):
        try:
            probe_id = request.args.get('probe_id')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            
            # Parse datetime strings
            if start_time:
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
            
            if end_time:
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
            
            # Get statistics
            stats = temperature_manager.get_temperature_statistics(
                device_id=device_id,
                probe_id=probe_id,
                start_time=start_time,
                end_time=end_time
            )
            
            logger.info("Temperature statistics retrieved", device_id=device_id)
            return jsonify({
                'status': 'success',
                'data': stats,
                'query': {
                    'device_id': device_id,
                    'probe_id': probe_id,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                }
            })
            
        except Exception as e:
            logger.error("Failed to get temperature statistics", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Real-time temperature stream endpoint
@app.route('/api/temperature/stream/<device_id>')
def temperature_stream(device_id):
    """Server-sent events stream for real-time temperature updates"""
    def generate():
        pubsub = redis_client.pubsub()
        pubsub.subscribe('temperature_stream')
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                if data.get('device_id') == device_id:
                    yield f"data: {json.dumps(data)}\n\n"
    
    return app.response_class(generate(), mimetype='text/plain')

# Live device data endpoint for User Story 3
@app.route('/api/devices/<device_id>/live', methods=['GET'])
def get_device_live_data(device_id):
    """Get current live data for a device including all channels and status"""
    with tracer.start_as_current_span("get_device_live_data"):
        try:
            # Get current temperature data from ThermoWorks API
            device_data = thermoworks_client.get_device_data(device_id)
            device_status = thermoworks_client.get_device_status(device_id)
            
            # Format live data response
            live_data = {
                'device_id': device_id,
                'timestamp': datetime.utcnow().isoformat(),
                'channels': [],
                'status': {
                    'battery_level': device_status.get('battery_level', 0),
                    'signal_strength': device_status.get('signal_strength', 0),
                    'connection_status': device_status.get('connection_status', 'unknown'),
                    'last_seen': device_status.get('last_seen', datetime.utcnow().isoformat())
                }
            }
            
            # Process channels/probes
            for channel in device_data.get('channels', []):
                channel_data = {
                    'channel_id': channel.get('channel_id'),
                    'probe_type': channel.get('probe_type', 'meat'),
                    'temperature': channel.get('temperature'),
                    'unit': channel.get('unit', 'F'),
                    'name': channel.get('name', f"Channel {channel.get('channel_id')}"),
                    'is_connected': channel.get('is_connected', True)
                }
                live_data['channels'].append(channel_data)
            
            # Cache the live data
            cache_key = f"live_data:{device_id}"
            redis_client.setex(cache_key, 30, json.dumps(live_data))
            
            # Store in time-series database
            if temperature_manager:
                for channel in live_data['channels']:
                    temperature_manager.store_temperature_reading({
                        'device_id': device_id,
                        'probe_id': channel['channel_id'],
                        'temperature': channel['temperature'],
                        'unit': channel['unit'],
                        'timestamp': datetime.utcnow().isoformat()
                    })
            
            logger.info("Live device data retrieved", device_id=device_id, channels=len(live_data['channels']))
            return jsonify({
                'status': 'success',
                'data': live_data
            })
            
        except Exception as e:
            logger.error("Failed to get live device data", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Device channels configuration endpoint
@app.route('/api/devices/<device_id>/channels', methods=['GET'])
def get_device_channels(device_id):
    """Get device channel configuration"""
    with tracer.start_as_current_span("get_device_channels"):
        try:
            # Get channel configuration from ThermoWorks API
            device_data = thermoworks_client.get_device_data(device_id)
            
            channels = []
            for channel in device_data.get('channels', []):
                channel_config = {
                    'channel_id': channel.get('channel_id'),
                    'probe_type': channel.get('probe_type', 'meat'),
                    'name': channel.get('name', f"Channel {channel.get('channel_id')}"),
                    'unit': channel.get('unit', 'F'),
                    'is_active': channel.get('is_active', True),
                    'min_temp': channel.get('min_temp', 32),
                    'max_temp': channel.get('max_temp', 500)
                }
                channels.append(channel_config)
            
            logger.info("Device channels retrieved", device_id=device_id, count=len(channels))
            return jsonify({
                'status': 'success',
                'data': {
                    'device_id': device_id,
                    'channels': channels,
                    'count': len(channels)
                }
            })
            
        except Exception as e:
            logger.error("Failed to get device channels", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Device status endpoint
@app.route('/api/devices/<device_id>/status', methods=['GET'])
def get_device_status(device_id):
    """Get device status including battery, signal, and connection info"""
    with tracer.start_as_current_span("get_device_status"):
        try:
            # Get device status from ThermoWorks API
            device_status = thermoworks_client.get_device_status(device_id)
            
            status_data = {
                'device_id': device_id,
                'battery_level': device_status.get('battery_level', 0),
                'signal_strength': device_status.get('signal_strength', 0),
                'connection_status': device_status.get('connection_status', 'unknown'),
                'last_seen': device_status.get('last_seen', datetime.utcnow().isoformat()),
                'firmware_version': device_status.get('firmware_version', 'unknown'),
                'hardware_version': device_status.get('hardware_version', 'unknown'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Cache the status data
            cache_key = f"status:{device_id}"
            redis_client.setex(cache_key, 60, json.dumps(status_data))
            
            logger.info("Device status retrieved", device_id=device_id, battery=status_data['battery_level'])
            return jsonify({
                'status': 'success',
                'data': status_data
            })
            
        except Exception as e:
            logger.error("Failed to get device status", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

# Live data stream endpoint for User Story 3
@app.route('/api/devices/<device_id>/stream', methods=['GET'])
def device_live_stream(device_id):
    """Server-sent events stream for live device data updates"""
    def generate():
        last_update = datetime.utcnow()
        
        while True:
            try:
                # Get current live data
                live_data = get_device_live_data_internal(device_id)
                
                if live_data:
                    yield f"data: {json.dumps(live_data)}\n\n"
                    
                # Wait for next update (5 seconds)
                time.sleep(5)
                
            except Exception as e:
                error_data = {
                    'device_id': device_id,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                time.sleep(10)  # Wait longer on error
    
    return app.response_class(generate(), mimetype='text/plain')

# Internal helper function for live data
def get_device_live_data_internal(device_id):
    """Internal helper to get live device data"""
    try:
        # Check cache first
        cache_key = f"live_data:{device_id}"
        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # Get from ThermoWorks API
        device_data = thermoworks_client.get_device_data(device_id)
        device_status = thermoworks_client.get_device_status(device_id)
        
        live_data = {
            'device_id': device_id,
            'timestamp': datetime.utcnow().isoformat(),
            'channels': [],
            'status': {
                'battery_level': device_status.get('battery_level', 0),
                'signal_strength': device_status.get('signal_strength', 0),
                'connection_status': device_status.get('connection_status', 'unknown')
            }
        }
        
        # Process channels
        for channel in device_data.get('channels', []):
            channel_data = {
                'channel_id': channel.get('channel_id'),
                'probe_type': channel.get('probe_type', 'meat'),
                'temperature': channel.get('temperature'),
                'unit': channel.get('unit', 'F'),
                'name': channel.get('name', f"Channel {channel.get('channel_id')}"),
                'is_connected': channel.get('is_connected', True)
            }
            live_data['channels'].append(channel_data)
        
        # Cache the result
        redis_client.setex(cache_key, 30, json.dumps(live_data))
        
        return live_data
    except Exception as e:
        logger.error("Failed to get live device data internally", device_id=device_id, error=str(e))
        return None

# Temperature alerts endpoint
@app.route('/api/temperature/alerts/<device_id>', methods=['GET'])
def get_temperature_alerts(device_id):
    """Get temperature alerts for a device"""
    with tracer.start_as_current_span("get_temperature_alerts"):
        try:
            probe_id = request.args.get('probe_id')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            
            # Parse datetime strings
            if start_time:
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
            
            if end_time:
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
            
            # Get alerts
            alerts = temperature_manager.get_temperature_alerts(
                device_id=device_id,
                probe_id=probe_id,
                start_time=start_time,
                end_time=end_time
            )
            
            logger.info("Temperature alerts retrieved", device_id=device_id, count=len(alerts))
            return jsonify({
                'status': 'success',
                'data': alerts,
                'count': len(alerts)
            })
            
        except Exception as e:
            logger.error("Failed to get temperature alerts", device_id=device_id, error=str(e))
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

if __name__ == '__main__':
    # Initialize database with retry
    if temperature_manager:
        try:
            temperature_manager.init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    # Start the application
    port = int(os.getenv('PORT', '8080'))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info("Starting Temperature Service", 
               port=port, 
               debug=debug,
               thermoworks_api=bool(api_key),
               influxdb=bool(temperature_manager),
               redis=bool(redis_client))
    
    app.run(host='0.0.0.0', port=port, debug=debug)