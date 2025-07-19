# @grill-stats/MOCK.md

# Mock Data System Documentation

This document provides comprehensive guidance for using the mock data system in the grill-stats application, enabling development and testing without requiring live ThermoWorks API connections.

## Overview

The mock data system provides a complete simulation of ThermoWorks device data, including:
- 4 realistic temperature monitoring devices
- Dynamic temperature simulation with cooking patterns
- Historical temperature data with realistic BBQ curves
- Device status simulation (battery, signal strength, online/offline)
- Seamless integration with existing application components

## Quick Start

### Enable Mock Mode

```bash
# Set environment variable
export MOCK_MODE=true

# Start the application
python app.py
```

The application will automatically detect mock mode and use simulated data instead of live API calls.

### Verify Mock Mode

```bash
# Check application status
curl http://localhost:5000/api/config

# Expected response:
{
  "mock_mode": true,
  "environment": "development",
  "version": "1.0.0"
}
```

## Mock Devices

The system provides 4 pre-configured devices with different characteristics:

### 1. Test Signals (mock-signals-001)
- **Model**: SIGNALS
- **Probes**: 1 channel (Air Temperature)
- **Use Case**: Basic ambient monitoring
- **Temperature Pattern**: Stable 225°F ± 5°F fluctuations
- **Battery**: 85%
- **Status**: Online

### 2. Mock BlueDOT (mock-bluedot-002)
- **Model**: BLUEDOT
- **Probes**: 2 channels (Brisket Internal + Pit Temperature)
- **Use Case**: Low & slow BBQ cooking
- **Temperature Patterns**:
  - Probe 1: Food probe (70°F → 203°F with stall behavior)
  - Probe 2: Ambient probe (stable 235°F ± 10°F)
- **Battery**: 92%
- **Status**: Online

### 3. Fake NODE (fake-node-003)
- **Model**: NODE
- **Probes**: 4 channels (Multiple food items + ambient)
- **Use Case**: Multi-probe BBQ setup
- **Temperature Patterns**:
  - Probe 1: Ribs (70°F → 195°F steady rise)
  - Probe 2: Chicken (70°F → 165°F faster cook)
  - Probe 3: Ambient pit (stable 250°F ± 8°F)
  - Probe 4: Water pan (212°F boiling point)
- **Battery**: 76%
- **Status**: Online

### 4. Test DOT (test-dot-004)
- **Model**: DOT
- **Probes**: 2 channels (High-heat grilling)
- **Use Case**: Testing offline device scenarios
- **Temperature Patterns**: Variable high-heat patterns
- **Battery**: 45%
- **Status**: Offline (for testing error scenarios)

## API Endpoints with Mock Data

### Device List
```bash
curl http://localhost:5000/devices

# Returns array of 4 mock devices with current temperature readings
```

### Individual Device Temperature
```bash
curl http://localhost:5000/devices/mock-bluedot-002/temperature

# Returns real-time temperature data with dynamic updates
```

### Historical Data
```bash
curl "http://localhost:5000/devices/mock-bluedot-002/history?start=2025-01-11T06:00:00&end=2025-01-11T10:00:00"

# Returns 4-hour historical cooking curve data
```

### Device Status
```bash
curl http://localhost:5000/devices/mock-signals-001/status

# Returns device metadata, battery level, signal strength
```

## Temperature Simulation

### Simulation Patterns

The mock system generates realistic temperature changes based on probe types:

#### Food Probes
- **Initial**: Start at ambient temperature (70-75°F)
- **Rise Phase**: Gradual increase mimicking real cooking
- **Stall Behavior**: Temperature plateaus (e.g., 160-170°F for brisket)
- **Final Push**: Continued rise to target temperature
- **Variance**: ±2°F random fluctuations for realism

#### Ambient Probes
- **Stable Range**: Maintain target temperature ±5-10°F
- **Periodic Fluctuations**: Small variations mimicking airflow
- **Startup Behavior**: Initial temperature ramp-up
- **Fuel Events**: Occasional temperature spikes

#### Surface Probes
- **Variable Patterns**: High variability for direct heat measurement
- **Peak Temperatures**: Can reach 400-500°F
- **Rapid Changes**: Quick temperature swings

### Customizing Simulation

Modify simulation parameters in `/services/mock_data/mock_service.py`:

```python
# Temperature change limits per update cycle
FOOD_TEMP_MAX_CHANGE = 2.0      # Max change for food probes
AMBIENT_TEMP_MAX_CHANGE = 5.0   # Max change for ambient probes
SURFACE_TEMP_MAX_CHANGE = 15.0  # Max change for surface probes

# Update frequency
SIMULATION_UPDATE_INTERVAL = 10  # Seconds between updates
```

## Historical Data

### Pre-generated Data

The system includes 4,320 pre-generated temperature readings (4 hours at 30-second intervals) featuring realistic BBQ cooking scenarios:

- **Brisket Cook**: 12-hour low & slow with temperature stall
- **Ribs Cook**: 6-hour steady rise to 195°F
- **Chicken Cook**: 2-hour faster cook to 165°F
- **Ambient Monitoring**: Stable pit temperatures with controlled fluctuations

### Accessing Historical Data

```javascript
// Frontend example
const startTime = '2025-01-11T06:00:00Z';
const endTime = '2025-01-11T10:00:00Z';

fetch(`/devices/mock-bluedot-002/history?start=${startTime}&end=${endTime}`)
  .then(response => response.json())
  .then(data => {
    // data contains array of temperature readings
    console.log(`Received ${data.length} temperature readings`);
  });
```

### Historical Data Structure

```json
{
  "device_id": "mock-bluedot-002",
  "probe_id": "probe_1",
  "readings": [
    {
      "timestamp": "2025-01-11T06:00:00Z",
      "temperature": 72.5,
      "probe_name": "Brisket Internal",
      "unit": "F"
    }
  ],
  "metadata": {
    "total_readings": 480,
    "duration_hours": 4,
    "avg_temperature": 145.2,
    "max_temperature": 203.0,
    "min_temperature": 72.5
  }
}
```

## Development Workflows

### UI Development

1. **Enable Mock Mode**:
   ```bash
   export MOCK_MODE=true
   ```

2. **Start Backend**:
   ```bash
   python app.py
   ```

3. **Start Frontend** (in separate terminal):
   ```bash
   cd services/web-ui
   npm start
   ```

4. **Access Application**:
   - Backend: http://localhost:5000
   - Frontend: http://localhost:3000

### Testing Scenarios

#### Normal Operation
- All devices online and reporting
- Realistic temperature progression
- Battery levels slowly decreasing

#### Error Scenarios
- test-dot-004 device offline
- Network connectivity issues
- Battery low warnings

#### Edge Cases
- Rapid temperature changes
- Temperature alarms triggering
- Device disconnection/reconnection

### Feature Testing

#### Device Management
```javascript
// Test device registration with mock data
const mockDeviceId = 'TW-TEST-999';
const nickname = 'Test Device';

// The system will simulate successful registration
// without requiring actual ThermoWorks API calls
```

#### Session Tracking
```javascript
// Mock data includes realistic session patterns
// Sessions automatically detected when temperature rises >20°F in 30 minutes
// Useful for testing session start/end detection algorithms
```

#### Alert System
```javascript
// Set temperature alerts on mock devices
// Alerts will trigger based on simulated temperature data
// Test notification system without waiting for real cooking
```

## Configuration

### Environment Variables

```bash
# Enable/disable mock mode
MOCK_MODE=true|false|1|0|yes|no|on|off

# Mock data directory (optional)
MOCK_DATA_DIR=services/mock_data

# Simulation update interval (seconds)
MOCK_UPDATE_INTERVAL=10
```

### Production Safety

Mock mode is automatically disabled in production:

```python
# In config.py
MOCK_MODE = (
    os.getenv('MOCK_MODE', 'false').lower() in ['true', '1', 'yes', 'on']
    and os.getenv('FLASK_ENV', 'production') != 'production'
)
```

### Mock Mode Indicator

When in development, the UI displays a mock mode indicator:

```html
<!-- Appears in development builds only -->
<div class="mock-mode-badge">
  🧪 Mock Mode Active
</div>
```

## File Structure

```
services/mock_data/
├── __init__.py                    # Module initialization
├── mock_service.py               # MockDataService class (428 lines)
├── devices.json                  # Device configurations and metadata
├── historical.json               # Pre-generated historical temperature data
├── generate_historical_data.py   # Script to regenerate historical data
└── README.md                     # Technical documentation
```

## Troubleshooting

### Common Issues

#### Mock Mode Not Working
```bash
# Check environment variable
echo $MOCK_MODE

# Verify configuration
python -c "from config import Config; print(f'Mock mode: {Config.MOCK_MODE}')"

# Check application logs
tail -f app.log | grep -i mock
```

#### No Temperature Updates
```bash
# Verify MockDataService is running
python -c "
from services.mock_data.mock_service import MockDataService
service = MockDataService()
devices = service.get_devices()
print(f'Found {len(devices)} mock devices')
"
```

#### Missing Historical Data
```bash
# Regenerate historical data
cd services/mock_data
python generate_historical_data.py
```

### Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `MockDataService not initialized` | Mock mode enabled but service failed to start | Check mock_data directory exists and contains valid JSON files |
| `No mock devices found` | devices.json missing or invalid | Verify devices.json exists and contains valid device array |
| `Historical data not available` | historical.json missing | Run `generate_historical_data.py` to create historical data |
| `Mock mode disabled in production` | FLASK_ENV=production | Set FLASK_ENV=development to enable mock mode |

## Advanced Usage

### Custom Device Configuration

Create custom devices by modifying `devices.json`:

```json
{
  "devices": [
    {
      "device_id": "custom-device-001",
      "name": "Custom Test Device",
      "model": "CUSTOM",
      "firmware_version": "1.0.0",
      "battery_level": 90,
      "signal_strength": -40,
      "is_online": true,
      "probes": [
        {
          "probe_id": "probe_1",
          "name": "Custom Probe",
          "type": "food",
          "min_temp": -40,
          "max_temp": 572,
          "current_temp": 75.0,
          "unit": "F",
          "alarm_low": 160,
          "alarm_high": 170
        }
      ]
    }
  ]
}
```

### Temperature Pattern Customization

Modify temperature simulation in `mock_service.py`:

```python
def _simulate_temperature_change(self, probe_data: Dict[str, Any]) -> float:
    """Customize temperature simulation patterns"""
    probe_type = probe_data.get('type', 'ambient')
    current_temp = probe_data.get('current_temp', 70.0)

    if probe_type == 'food':
        # Custom food probe simulation logic
        target_temp = 203.0  # Brisket target
        if current_temp < target_temp:
            # Implement custom cooking curve
            change = calculate_custom_food_change(current_temp, target_temp)
        else:
            change = random.uniform(-1.0, 1.0)

    return current_temp + change
```

### Integration Testing

Test mock data integration with your components:

```python
# Example test case
def test_device_list_with_mock_data():
    """Test that device list endpoint works with mock data"""
    app.config['TESTING'] = True
    os.environ['MOCK_MODE'] = 'true'

    with app.test_client() as client:
        response = client.get('/devices')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data) == 4  # Expected number of mock devices
        assert all(device['device_id'].startswith(('mock-', 'test-', 'fake-')) for device in data)
```

## Best Practices

### Development
- Always use mock mode for UI development
- Test with different device scenarios (online/offline)
- Validate temperature patterns match expectations
- Use mock data for automated testing

### Testing
- Test both normal and error scenarios
- Verify alert system with mock temperature changes
- Test session detection with simulated cooking patterns
- Validate historical data visualization

### Production
- Ensure mock mode is disabled in production
- Document any mock data dependencies
- Plan migration path from mock to live data
- Monitor for accidental mock mode activation

## Support

For issues with the mock data system:

1. **Check Configuration**: Verify environment variables and file structure
2. **Review Logs**: Check application logs for mock service messages
3. **Validate Data**: Ensure JSON files contain valid data
4. **Test Components**: Verify individual components work in isolation
5. **Reset Data**: Regenerate mock data files if corrupted

The mock data system is designed to be robust and self-contained, providing a reliable foundation for development and testing of the grill-stats application.
