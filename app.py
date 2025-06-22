import os
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from thermoworks_client import ThermoWorksClient
from homeassistant_client import HomeAssistantClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

thermoworks_client = ThermoWorksClient(
    api_key=os.getenv('THERMOWORKS_API_KEY')
)

homeassistant_client = HomeAssistantClient(
    base_url=os.getenv('HOMEASSISTANT_URL'),
    access_token=os.getenv('HOMEASSISTANT_TOKEN')
)

scheduler = BackgroundScheduler()

def sync_temperature_data():
    logger.info("Starting temperature data sync")
    
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

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/devices')
def get_devices():
    devices = thermoworks_client.get_devices()
    return jsonify(devices)

@app.route('/devices/<device_id>/temperature')
def get_device_temperature(device_id):
    temperature_data = thermoworks_client.get_temperature_data(device_id)
    return jsonify(temperature_data)

@app.route('/devices/<device_id>/history')
def get_device_history(device_id):
    start_time = request.args.get('start', (datetime.now() - timedelta(hours=24)).isoformat())
    end_time = request.args.get('end', datetime.now().isoformat())
    
    history = thermoworks_client.get_historical_data(device_id, start_time, end_time)
    return jsonify(history)

@app.route('/sync', methods=['POST'])
def manual_sync():
    try:
        sync_temperature_data()
        return jsonify({'status': 'success', 'message': 'Temperature data synced successfully'})
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/homeassistant/test')
def test_homeassistant():
    if homeassistant_client.test_connection():
        return jsonify({'status': 'connected', 'message': 'Home Assistant connection successful'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to connect to Home Assistant'}), 500

if __name__ == '__main__':
    if not homeassistant_client.test_connection():
        logger.warning("Could not connect to Home Assistant - check your configuration")
    
    scheduler.add_job(
        func=sync_temperature_data,
        trigger="interval",
        minutes=5,
        id='temperature_sync'
    )
    scheduler.start()
    
    logger.info("Starting Grill Stats application")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()