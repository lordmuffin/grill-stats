# Mock Data Infrastructure for Grill Stats

This directory contains the complete mock data infrastructure for the Grill Stats application, enabling UI development and testing without requiring live ThermoWorks API connections.

## Overview

The mock data system provides:
- Realistic device configurations for multiple ThermoWorks devices
- Dynamic temperature data with realistic cooking patterns
- Historical data covering 4-hour BBQ cooking scenarios
- Seamless integration that replaces live API calls during development

## Components

### Core Files

- **`mock_service.py`** - Main MockDataService class that replaces ThermoWorks API calls
- **`devices.json`** - Static device configuration data for 4 mock devices
- **`historical.json`** - Pre-generated 4-hour historical temperature data
- **`generate_historical_data.py`** - Script to regenerate historical data
- **`__init__.py`** - Module initialization and exports

### Mock Devices

The system includes 4 realistic devices:

1. **Test Signals** (`mock-signals-001`)
   - 1 channel ambient temperature probe
   - Simulates basic temperature monitoring

2. **Mock BlueDOT** (`mock-bluedot-002`)
   - 2 channels: brisket internal + pit temperature
   - Simulates dual-probe BBQ setup

3. **Fake NODE** (`mock-node-003`)
   - 4 channels: ribs, chicken, smoker air, water pan
   - Simulates full multi-probe setup

4. **Test DOT** (`mock-dot-004`)
   - 2 channels: steak internal + grill surface
   - Simulates high-heat grilling (offline for testing)

## Usage

### Environment Configuration

Enable mock mode by setting the `MOCK_MODE` environment variable:

```bash
# Enable mock mode
export MOCK_MODE=true

# Or in .env file
MOCK_MODE=true
```

### Supported Values

The following values enable mock mode:
- `true`, `1`, `yes`, `on` (case insensitive)

Mock mode is automatically disabled in production environments (`FLASK_ENV=production`).

### Integration

The mock service integrates seamlessly with existing code:

```python
from services.mock_data import MockDataService

# Initialize (automatically detects mock mode)
mock_service = MockDataService()

# Get devices (returns list of mock devices)
devices = mock_service.get_devices()

# Get temperature data (returns realistic, changing temperatures)
temp_data = mock_service.get_temperature_data('mock-bluedot-002', 'probe_1')

# Get historical data (returns 4-hour cooking curves)
history = mock_service.get_historical_data(
    'mock-node-003',
    'probe_1',
    start_time,
    end_time
)
```

### API Compatibility

The MockDataService provides the same methods as the real ThermoWorks client:

- `get_devices()` - Returns list of available devices
- `get_device_status(device_id)` - Returns device status and metadata
- `get_temperature_data(device_id, probe_id)` - Returns current temperature readings
- `get_historical_data(device_id, probe_id, start_time, end_time)` - Returns historical data
- `is_device_online(device_id)` - Checks device online status
- `get_device_battery_level(device_id)` - Returns battery level

## Temperature Simulation

### Real-Time Data

The mock service generates realistic temperature changes:

- **Food Probes**: Gradual temperature rise with cooking patterns
- **Ambient Probes**: Stable temperatures with controlled fluctuations
- **Surface Probes**: Variable temperatures mimicking grill surfaces

### Cooking Patterns

Historical data includes realistic BBQ cooking scenarios:

- **Brisket**: Low and slow with temperature stall around 160-170°F
- **Ribs**: Steady rise to 195°F over 4 hours
- **Chicken**: Faster cook to 165°F internal temperature
- **Ambient**: Consistent pit temperature with minor fluctuations
- **Water Pan**: Stable around 212°F (boiling)
- **High Heat**: Variable grill surface temperatures

### Data Generation

Temperature changes follow realistic patterns:

```python
# Food probes: gradual rise toward target
# - Rate: 0.5-2.0°F per minute
# - Stall behavior around 160°F for brisket
# - Slowdown near target temperature

# Ambient probes: stable with minor variations
# - Rate: ±0.2°F per minute
# - Oscillation around target temperature
# - Realistic pit temperature behavior

# Surface probes: higher variability
# - Rate: ±1.0°F per minute
# - Greater temperature swings
# - Simulates direct heat variations
```

## Development Workflow

### Starting Development

1. **Enable Mock Mode**:
   ```bash
   export MOCK_MODE=true
   ```

2. **Start Application**:
   ```bash
   python app.py
   ```

3. **Verify Mock Mode**:
   - Check application logs for "MOCK MODE" messages
   - Visit `/api/config` endpoint to confirm mock_mode: true
   - UI should show mock mode indicator (development only)

### UI Development

Mock mode enables full UI development without API dependencies:

- **Device List**: Shows 4 mock devices with varying states
- **Live Data**: Temperature values update every 5-10 seconds
- **Historical Charts**: 4-hour cooking curves for different scenarios
- **Alerts**: Battery levels and signal strength variations
- **Offline Testing**: One device (Test DOT) is offline for testing

### Testing Scenarios

The mock data supports comprehensive testing:

1. **Multi-Device Setup**: 4 devices with different probe counts
2. **Mixed States**: Online/offline devices, varying battery levels
3. **Different Cooking Types**: Various temperature patterns and targets
4. **Time-Series Data**: Historical data spanning 4 hours with 30-second intervals
5. **Error Conditions**: Offline devices, connection failures

## File Structure

```
services/mock-data/
├── __init__.py                 # Module exports
├── mock_service.py            # Main MockDataService class
├── devices.json               # Static device configurations
├── historical.json            # Pre-generated historical data
├── generate_historical_data.py # Historical data generator script
└── README.md                  # This documentation
```

## Regenerating Historical Data

To regenerate historical data with new patterns:

```bash
cd services/mock-data
python generate_historical_data.py
```

This creates a new `historical.json` file with:
- 4320 temperature readings (4 hours × 60 minutes × 2 readings/minute)
- Realistic cooking curves for all probe types
- Different scenarios for each device

## Configuration

### Mock Service Settings

The MockDataService can be configured via environment variables:

```bash
# Temperature update frequency (seconds)
MOCK_UPDATE_INTERVAL=5

# Temperature volatility (standard deviation)
MOCK_TEMPERATURE_NOISE=1.0

# Battery drain rate (% per hour)
MOCK_BATTERY_DRAIN=0.5
```

### Device Customization

Edit `devices.json` to modify mock devices:

```json
{
  "device_id": "custom-device-001",
  "name": "Custom Device",
  "model": "CUSTOM",
  "battery_level": 95,
  "signal_strength": -45,
  "is_online": true,
  "probes": [
    {
      "probe_id": "probe_1",
      "name": "Custom Probe",
      "type": "food",
      "current_temp": 150.0,
      "alarm_low": 140,
      "alarm_high": 160
    }
  ]
}
```

## Integration Points

### Flask Application

```python
# config.py
MOCK_MODE = os.getenv('MOCK_MODE', 'false').lower() in ('true', '1', 'yes', 'on')

# app.py
thermoworks_client = ThermoWorksClient(
    api_key=app.config['THERMOWORKS_API_KEY'],
    mock_mode=app.config.get('MOCK_MODE', False)
)
```

### Microservices

```python
# Device Service
client = ThermoworksClient(mock_mode=True)
devices = client.get_devices()  # Returns mock devices

# Temperature Service
client = ThermoWorksClient(mock_mode=True)
temp_data = client.get_temperature_data(device_id, probe_id)
```

### React Frontend

```javascript
// Check mock mode status
fetch('/api/config')
  .then(response => response.json())
  .then(config => {
    if (config.mock_mode) {
      console.log('Running in mock mode');
      // Show mock mode indicator
    }
  });

// Data fetching works the same
fetch('/api/devices')
  .then(response => response.json())
  .then(devices => {
    // Process mock or real devices identically
  });
```

## Production Safety

Mock mode is automatically disabled in production:

- `FLASK_ENV=production` prevents mock mode activation
- Configuration validation ensures no mock data in production
- Logging clearly indicates when mock mode is active
- UI indicators are only shown in development environments

## Troubleshooting

### Mock Mode Not Working

1. **Check Environment Variable**:
   ```bash
   echo $MOCK_MODE
   ```

2. **Verify Application Logs**:
   Look for "MOCK MODE" initialization messages

3. **Check Configuration Endpoint**:
   ```bash
   curl http://localhost:5000/api/config
   ```

### Import Errors

If MockDataService import fails:

1. **Check Python Path**:
   ```python
   import sys
   print(sys.path)
   ```

2. **Verify File Structure**:
   ```bash
   ls -la services/mock-data/
   ```

3. **Check Module Init**:
   ```bash
   python -c "from services.mock_data import MockDataService"
   ```

### Temperature Data Issues

1. **Verify JSON Files**:
   ```bash
   python -c "import json; print(json.load(open('devices.json')))"
   ```

2. **Check Update Frequency**:
   Temperature values should change every 5-10 seconds

3. **Monitor Simulation**:
   Enable debug logging to see temperature calculations

## API Reference

### MockDataService Methods

#### `get_devices(force_refresh=False)`
Returns list of mock devices with current temperature data.

**Returns**: `List[Dict]` - Device information with current temperatures

#### `get_device_status(device_id)`
Returns status information for a specific device.

**Parameters**:
- `device_id` (str): Device identifier

**Returns**: `Dict` - Device status including online state, battery, signal

#### `get_temperature_data(device_id, probe_id=None)`
Returns current temperature data for device/probe.

**Parameters**:
- `device_id` (str): Device identifier
- `probe_id` (str, optional): Probe identifier

**Returns**: `Dict` - Temperature reading with metadata

#### `get_historical_data(device_id, probe_id, start_time, end_time)`
Returns historical temperature data for specified time range.

**Parameters**:
- `device_id` (str): Device identifier
- `probe_id` (str): Probe identifier
- `start_time` (datetime): Start of time range
- `end_time` (datetime): End of time range

**Returns**: `List[Dict]` - Historical temperature readings

## Contributing

When adding new features to the mock data system:

1. **Maintain API Compatibility**: Ensure mock methods match real API signatures
2. **Realistic Data**: Generate data that reflects real-world usage patterns
3. **Performance**: Keep data generation efficient for real-time updates
4. **Documentation**: Update this README with new features or changes
5. **Testing**: Verify mock mode works across all application components

## License

This mock data infrastructure is part of the Grill Stats application and follows the same licensing terms.
