import os
import logging
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from thermoworks_client import ThermoWorksClient
from homeassistant_client import HomeAssistantClient
from config import Config

# Import requests for external API calls
try:
    import requests
except ImportError:
    requests = None

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log Flask version for debugging
import flask
logger.info(f"Starting application with Flask version: {flask.__version__}")

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

# Initialize User model
from models.user import User
user_manager = User(db)

# Initialize auth routes
from auth.routes import init_auth_routes
init_auth_routes(app, login_manager, user_manager, bcrypt)

# Initialize API clients
thermoworks_client = ThermoWorksClient(
    api_key=app.config['THERMOWORKS_API_KEY']
)

homeassistant_client = HomeAssistantClient(
    base_url=app.config['HOMEASSISTANT_URL'],
    access_token=app.config['HOMEASSISTANT_TOKEN']
)

scheduler = BackgroundScheduler()

@app.teardown_appcontext
def close_db(error):
    """Close database connections at the end of each request"""
    try:
        db.session.close()
    except Exception as e:
        logger.warning(f"Error closing database session: {e}")

@app.teardown_request
def teardown_request(exception):
    """Cleanup after each request"""
    try:
        if exception:
            db.session.rollback()
        db.session.close()
    except Exception as e:
        logger.warning(f"Error in teardown_request: {e}")

def sync_temperature_data():
    logger.info("Starting temperature data sync")
    
    try:
        # Use application context to ensure database connections are properly handled
        with app.app_context():
            try:
                devices = thermoworks_client.get_devices()
                
                for device in devices:
                    device_id = device.get('id')
                    device_name = device.get('name', f'thermoworks_{device_id}')
                    
                    temperature_data = thermoworks_client.get_temperature_data(device_id)
                    
                    if temperature_data and temperature_data.get('temperature'):
                        sensor_name = f"thermoworks_{device_name.lower().replace(' ', '_')}"
                        
                        attributes = {
                            'device_id': device_id,
                            'last_updated': temperature_data.get('timestamp'),
                            'battery_level': temperature_data.get('battery_level'),
                            'signal_strength': temperature_data.get('signal_strength')
                        }
                        
                        success = homeassistant_client.create_sensor(
                            sensor_name=sensor_name,
                            state=temperature_data['temperature'],
                            attributes=attributes,
                            unit=temperature_data.get('unit', 'F')
                        )
                        
                        if success:
                            logger.info(f"Updated sensor {sensor_name} with temperature {temperature_data['temperature']}°{temperature_data.get('unit', 'F')}")
                        else:
                            logger.error(f"Failed to update sensor {sensor_name}")
                            
            except Exception as e:
                logger.error(f"Error during temperature sync: {e}")
            finally:
                # Ensure database connections are properly closed
                try:
                    db.session.close()
                except Exception as close_e:
                    logger.warning(f"Error closing database session: {close_e}")
                    
    except Exception as e:
        logger.error(f"Error during temperature sync: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/monitoring')
@login_required
def monitoring():
    """Real-time temperature monitoring dashboard"""
    return render_template('monitoring.html')

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/devices')
@login_required
def get_devices():
    # For HTML request, render template
    if request.headers.get('Accept', '').find('html') != -1:
        devices = thermoworks_client.get_devices()
        return render_template('devices.html', devices=devices)
    # For API request, return JSON
    else:
        devices = thermoworks_client.get_devices()
        return jsonify(devices)

@app.route('/devices/<device_id>/temperature')
@login_required
def get_device_temperature(device_id):
    temperature_data = thermoworks_client.get_temperature_data(device_id)
    return jsonify(temperature_data)

@app.route('/devices/<device_id>/history')
@login_required
def get_device_history(device_id):
    start_time = request.args.get('start', (datetime.now() - timedelta(hours=24)).isoformat())
    end_time = request.args.get('end', datetime.now().isoformat())
    
    history = thermoworks_client.get_historical_data(device_id, start_time, end_time)
    return jsonify(history)

@app.route('/sync', methods=['POST'])
@login_required
def manual_sync():
    try:
        sync_temperature_data()
        
        # For HTML request, redirect back
        if request.headers.get('Accept', '').find('html') != -1:
            return redirect(url_for('dashboard'))
        # For API request, return JSON
        else:
            return jsonify({'status': 'success', 'message': 'Temperature data synced successfully'})
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        
        # For HTML request, flash message and redirect back
        if request.headers.get('Accept', '').find('html') != -1:
            from flask import flash
            flash(f'Sync failed: {str(e)}', 'danger')
            return redirect(url_for('dashboard'))
        # For API request, return JSON error
        else:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/homeassistant/test')
@login_required
def test_homeassistant():
    if homeassistant_client.test_connection():
        return jsonify({'status': 'connected', 'message': 'Home Assistant connection successful'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to connect to Home Assistant'}), 500
        
@app.route('/api/monitoring/data')
@login_required
def get_monitoring_data():
    """
    Get real-time temperature data from all connected probes
    Returns unified data from all probe sources (ThermoWorks Cloud, RFX Gateway, etc.)
    """
    try:
        # Fetch data from all probe sources
        all_probes = []
        
        # --- ThermoWorks Cloud Probes ---
        try:
            # Get ThermoWorks devices
            devices = thermoworks_client.get_devices()
            
            # For each device, get temperature data
            for device in devices:
                device_id = device.get('id')
                device_name = device.get('name', f'ThermoWorks {device_id}')
                
                try:
                    # Get temperature data for this device
                    temperature_data = thermoworks_client.get_temperature_data(device_id)
                    
                    if temperature_data and temperature_data.get('temperature'):
                        # Create a probe entry
                        probe = {
                            'id': f"thermoworks_{device_id}",
                            'name': f"Probe {device_name}",
                            'device_id': device_id,
                            'device_name': device_name,
                            'source': 'thermoworks',
                            'temperature': temperature_data.get('temperature'),
                            'unit': temperature_data.get('unit', 'F'),
                            'timestamp': temperature_data.get('timestamp', datetime.now().isoformat()),
                            'battery_level': temperature_data.get('battery_level'),
                            'signal_strength': temperature_data.get('signal_strength'),
                            'status': 'online'
                        }
                        
                        all_probes.append(probe)
                except Exception as e:
                    logger.error(f"Error getting temperature for ThermoWorks device {device_id}: {e}")
        except Exception as e:
            logger.error(f"Error fetching ThermoWorks devices: {e}")
        
        # --- RFX Gateway Probes ---
        try:
            # Import RFXGatewayClient only if it's not already imported
            try:
                from services.device_service.rfx_gateway_client import RFXGatewayClient
                from services.device_service.device_manager import DeviceManager
                
                # Check if device-service is available
                import requests
                
                # Try to access the device-service API (assuming it's running on standard port)
                device_service_url = os.environ.get('DEVICE_SERVICE_URL', 'http://localhost:8080')
                
                # Get gateways from device service
                response = requests.get(f"{device_service_url}/api/gateways", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    gateways = data.get('data', {}).get('gateways', [])
                    
                    # For each gateway, get temperature readings
                    for gateway in gateways:
                        gateway_id = gateway.get('gateway_id')
                        gateway_name = gateway.get('name', f'RFX Gateway {gateway_id[-6:]}')
                        
                        # Only process online gateways
                        if gateway.get('online', False):
                            try:
                                # Get temperature readings for this gateway
                                temp_response = requests.get(
                                    f"{device_service_url}/api/gateways/{gateway_id}/temperature",
                                    timeout=2
                                )
                                
                                if temp_response.status_code == 200:
                                    temp_data = temp_response.json()
                                    readings = temp_data.get('data', {}).get('readings', [])
                                    
                                    # Process each reading
                                    for reading in readings:
                                        probe_id = reading.get('probe_id')
                                        probe_name = reading.get('name', f'Probe {probe_id}')
                                        
                                        # Create normalized probe entry
                                        probe = {
                                            'id': f"rfx_{gateway_id}_{probe_id}",
                                            'name': probe_name,
                                            'device_id': gateway_id,
                                            'device_name': f"RFX: {gateway_name}",
                                            'source': 'rfx_gateway',
                                            'temperature': reading.get('temperature'),
                                            'unit': reading.get('unit', 'F'),
                                            'timestamp': reading.get('timestamp', datetime.now().isoformat()),
                                            'battery_level': reading.get('battery_level'),
                                            'signal_strength': reading.get('signal_strength'),
                                            'status': 'online'
                                        }
                                        
                                        all_probes.append(probe)
                            except Exception as e:
                                logger.error(f"Error getting temperature for RFX Gateway {gateway_id}: {e}")
            except (ImportError, requests.RequestException) as e:
                logger.warning(f"RFX Gateway service not available: {e}")
        except Exception as e:
            logger.error(f"Error accessing RFX Gateway service: {e}")
        
        # Initialize Redis client if not already defined
        try:
            import redis
            redis_client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", 6379)),
                password=os.environ.get("REDIS_PASSWORD", None),
                decode_responses=True
            )
            # Test connection
            redis_client.ping()
        except (ImportError, redis.RedisError) as e:
            logger.warning(f"Redis not available for temperature cache: {e}")
            redis_client = None
        
        # If no probes were found but Redis is available, check for cached readings
        if not all_probes and redis_client:
            try:
                # Get all temperature keys
                temp_keys = redis_client.keys("temperature:latest:*")
                
                for key in temp_keys:
                    cached_data = redis_client.get(key)
                    if cached_data:
                        try:
                            reading = json.loads(cached_data)
                            parts = key.split(":")
                            
                            if len(parts) >= 4:
                                device_id = parts[2]
                                probe_id = parts[3]
                                
                                # Create probe from cached data
                                probe = {
                                    'id': f"cached_{device_id}_{probe_id}",
                                    'name': f"Probe {probe_id}",
                                    'device_id': device_id,
                                    'device_name': f"Device {device_id}",
                                    'source': 'cache',
                                    'temperature': reading.get('temperature'),
                                    'unit': reading.get('unit', 'F'),
                                    'timestamp': reading.get('timestamp', datetime.now().isoformat()),
                                    'battery_level': reading.get('battery_level'),
                                    'signal_strength': reading.get('signal_strength'),
                                    'status': 'offline'  # Mark as offline since we're using cached data
                                }
                                
                                all_probes.append(probe)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.error(f"Error reading cached temperature data: {e}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'probes': all_probes,
                'count': len(all_probes),
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching monitoring data: {e}")
        return jsonify({
            'status': 'error',
            'message': f"Error fetching monitoring data: {str(e)}"
        }), 500

def create_tables():
    """Create database tables and add test user in development"""
    db.create_all()
    
    # Create a test user in development mode
    if app.config.get('ENV', 'production') != 'production':
        from auth.utils import create_test_user
        create_test_user(user_manager, bcrypt, 'test@example.com', 'password')
        logger.info("Created test user: test@example.com / password")

# Initialize database - Flask 3.0+ compatible
def initialize_app():
    """Initialize application with database setup and scheduler"""
    with app.app_context():
        create_tables()
        logger.info("Database initialization completed")
    
    # Set up the scheduler for temperature sync
    scheduler.add_job(
        func=sync_temperature_data,
        trigger="interval",
        minutes=5,
        id='temperature_sync'
    )
    scheduler.start()
    logger.info("Temperature sync scheduler started")

# Call initialization immediately when module is loaded (works in all deployment scenarios)
try:
    initialize_app()
    if not homeassistant_client.test_connection():
        logger.warning("Could not connect to Home Assistant - check your configuration")
except Exception as e:
    logger.error(f"Failed to initialize app during startup: {e}")
    # We'll retry on first request if this fails
    @app.before_request
    def retry_initialization():
        """Retry initialization on first request if startup failed"""
        if not hasattr(app, '_database_initialized'):
            try:
                initialize_app()
                app._database_initialized = True
                logger.info("Application initialization completed on first request")
            except Exception as retry_e:
                logger.error(f"Failed to initialize application on first request: {retry_e}")

# This makes the app work with gunicorn in production
application = app

if __name__ == '__main__':
    logger.info("Starting Grill Stats application")
    
    # Run Flask development server
    try:
        # Use debug=False in production deployment
        is_production = os.environ.get('FLASK_ENV') == 'production'
        debug_mode = not is_production
        logger.info(f"Starting Flask server - Production: {is_production}, Debug: {debug_mode}")
        app.run(host='0.0.0.0', port=5000, debug=debug_mode)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()