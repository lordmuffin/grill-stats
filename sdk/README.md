# Grill Stats API Client SDK

This SDK provides Python client libraries for interacting with the Grill Stats API, including ThermoWorks devices and Home Assistant integration.

## Installation

```bash
# From the project root directory
pip install -e ./sdk
```

## Usage

### ThermoWorks Client

The ThermoWorks client provides access to ThermoWorks devices, temperature data, and historical readings.

```python
from grill_stats_client import ThermoWorksClient

# Initialize client
client = ThermoWorksClient(api_key="your_api_key")

# Get all devices
devices = client.get_devices()
for device in devices:
    print(f"Device: {device['name']} (ID: {device['id']})")

# Get temperature data for a specific device
temperature_data = client.get_temperature_data(device_id="device123")
print(f"Temperature: {temperature_data['temperature']}°{temperature_data['unit']}")
print(f"Battery Level: {temperature_data['battery_level']}%")
print(f"Signal Strength: {temperature_data['signal_strength']}%")

# Get historical data
from datetime import datetime, timedelta

end_time = datetime.now()
start_time = end_time - timedelta(hours=24)  # Last 24 hours

history = client.get_historical_data(
    device_id="device123",
    start_time=start_time,
    end_time=end_time
)

for reading in history:
    print(f"Time: {reading['timestamp']}, Temp: {reading['temperature']}°{reading['unit']}")
```

### Home Assistant Client

The Home Assistant client provides integration with Home Assistant, allowing you to create sensors, send notifications, and call services.

```python
from grill_stats_client import HomeAssistantClient

# Initialize client
client = HomeAssistantClient(
    base_url="http://homeassistant.local:8123",
    access_token="your_long_lived_token"
)

# Test connection
if client.test_connection():
    print("Connected to Home Assistant!")
else:
    print("Failed to connect to Home Assistant")

# Create or update a temperature sensor
client.create_sensor(
    sensor_name="grill_temperature",
    state=225.5,
    attributes={
        "device_id": "device123",
        "last_updated": "2025-07-20T15:30:00Z",
        "battery_level": 85,
        "signal_strength": 92
    },
    unit="F"
)

# Send a notification
client.send_notification(
    message="Your brisket has reached the target temperature!",
    title="Grill Alert"
)

# Call a service
client.call_service(
    domain="light",
    service="turn_on",
    service_data={"brightness": 255},
    target={"entity_id": "light.kitchen"}
)
```

### Mock Mode

Both clients support a mock mode for testing and development without requiring actual API access.

```python
# Initialize clients in mock mode
thermoworks_client = ThermoWorksClient(mock_mode=True)
homeassistant_client = HomeAssistantClient(mock_mode=True)

# Use clients as normal - they will return mock data
devices = thermoworks_client.get_devices()
```

## Error Handling

The SDK provides custom exception classes for different types of errors:

```python
from grill_stats_client import ThermoWorksClient, APIError, AuthenticationError, ConnectionError

client = ThermoWorksClient(api_key="invalid_key")

try:
    devices = client.get_devices()
except AuthenticationError:
    print("Authentication failed - check your API key")
except ConnectionError as e:
    print(f"Connection error: {e}")
except APIError as e:
    print(f"API error: {e}")
```

## Configuration Options

Both clients support additional configuration options:

```python
client = ThermoWorksClient(
    api_key="your_api_key",
    base_url="https://api.thermoworks.com",  # Custom API URL
    timeout=30,  # Custom timeout in seconds
    max_retries=5,  # Maximum number of retries
    retry_backoff_factor=1.0,  # Backoff factor for retries
    retry_status_forcelist=[429, 500, 502, 503, 504]  # Status codes to retry
)
```
