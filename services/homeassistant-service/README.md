# Home Assistant Integration Service

Comprehensive Home Assistant integration service for the Grill Stats platform, providing seamless connectivity, entity management, state synchronization, and automation capabilities.

## Features

### Core Integration
- **REST API Client**: Robust Home Assistant REST API client with authentication and error handling
- **WebSocket Support**: Real-time bidirectional communication with Home Assistant
- **Entity Management**: Complete sensor and device entity lifecycle management
- **State Synchronization**: Intelligent bidirectional state sync with throttling and error recovery
- **Auto Discovery**: MQTT discovery protocol support for automatic entity registration

### Entity Types
- **Temperature Sensors**: Real-time temperature data from grill probes
- **Battery Sensors**: Device battery level monitoring with low battery alerts
- **Signal Strength Sensors**: Wireless signal quality monitoring
- **Connection Binary Sensors**: Device connectivity status tracking
- **Device Groups**: Logical device grouping with metadata

### Automation Support
- **Temperature Alerts**: Configurable high/low temperature threshold alerts
- **Device Offline Alerts**: Automatic notification when devices go offline
- **Battery Low Alerts**: Proactive battery replacement notifications
- **Cooking Session Automation**: Session-based automation with scene support
- **Custom Triggers**: Flexible trigger and action configuration

### Advanced Features
- **Health Monitoring**: Comprehensive service health checks and metrics
- **Error Recovery**: Automatic retry mechanisms with exponential backoff
- **Performance Metrics**: Detailed performance and reliability monitoring
- **Caching Support**: Redis-based caching for improved performance
- **Mock Mode**: Development and testing support without live Home Assistant

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant Service                       │
├─────────────────┬───────────────────┬───────────────────────────┤
│   API Routes    │   Core Services   │      Utilities            │
│                 │                   │                           │
│ • Health        │ • HA Client       │ • Metrics Collector       │
│ • Temperature   │ • Entity Manager  │ • Health Monitor          │
│ • Device Mgmt   │ • State Sync      │ • Automation Helpers      │
│ • Automation    │ • Discovery       │ • Notification System     │
│ • Metrics       │                   │ • Scene Management        │
└─────────────────┴───────────────────┴───────────────────────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │   Home Assistant    │
                 │                     │
                 │ • REST API          │
                 │ • WebSocket         │
                 │ • MQTT Discovery    │
                 │ • Automation        │
                 └─────────────────────┘
```

## Installation

### Docker Deployment

```bash
# Build the image
docker build -t grill-stats/homeassistant-service .

# Run with environment variables
docker run -d \
  --name homeassistant-service \
  -p 5000:5000 \
  -e HOME_ASSISTANT_URL=http://homeassistant:8123 \
  -e HOME_ASSISTANT_TOKEN=your_token_here \
  -e REDIS_URL=redis://redis:6379/0 \
  grill-stats/homeassistant-service
```

### Environment Variables

```bash
# Home Assistant Configuration
HOME_ASSISTANT_URL=http://homeassistant:8123
HOME_ASSISTANT_TOKEN=your_long_lived_access_token
HOME_ASSISTANT_VERIFY_SSL=true
HOME_ASSISTANT_TIMEOUT=30
HOME_ASSISTANT_WEBSOCKET_ENABLED=true

# Service Configuration
ENTITY_PREFIX=grill_stats
SYNC_INTERVAL=30
THROTTLE_INTERVAL=5
BATCH_SIZE=10
PORT=5000
DEBUG=false

# Redis Configuration (optional)
REDIS_URL=redis://redis:6379/0

# Development
MOCK_MODE=false
```

## API Reference

### Health Endpoint
```http
GET /health
```

Response:
```json
{
  "overall_health": "healthy",
  "last_updated": "2023-12-07T10:30:00Z",
  "checks": {
    "ha_connection": {
      "status": "healthy",
      "message": "Connection successful, response time: 45.2ms"
    }
  }
}
```

### Temperature Sync
```http
POST /api/v1/temperature
Content-Type: application/json

{
  "device_id": "device_001",
  "probe_id": "1",
  "temperature": 225.5,
  "unit": "°F",
  "battery_level": 85,
  "signal_strength": -45
}
```

### Device Registration
```http
POST /api/v1/device
Content-Type: application/json

{
  "device_id": "device_001",
  "name": "Grill Device 1",
  "manufacturer": "ThermoWorks",
  "model": "Wireless Thermometer"
}
```

### Automation Creation
```http
POST /api/v1/automation
Content-Type: application/json

{
  "type": "temperature_alert",
  "device_id": "device_001",
  "probe_id": "1",
  "alert_name": "High Temperature Alert",
  "temperature_threshold": 250.0,
  "threshold_type": "above",
  "deploy": true
}
```

## Usage Examples

### Basic Temperature Monitoring

```python
import requests

# Register device
device_data = {
    "device_id": "grill_001",
    "name": "Main Grill",
    "manufacturer": "ThermoWorks"
}
requests.post("http://service:5000/api/v1/device", json=device_data)

# Send temperature data
temp_data = {
    "device_id": "grill_001",
    "probe_id": "1",
    "temperature": 225.5,
    "unit": "°F",
    "battery_level": 85
}
requests.post("http://service:5000/api/v1/temperature", json=temp_data)
```

### Creating Temperature Alerts

```python
# Create high temperature alert
alert_config = {
    "type": "temperature_alert",
    "device_id": "grill_001",
    "probe_id": "1",
    "alert_name": "Overcook Protection",
    "temperature_threshold": 275.0,
    "threshold_type": "above",
    "notification_title": "Temperature Alert",
    "notification_message": "Grill temperature is too high!",
    "deploy": True
}
requests.post("http://service:5000/api/v1/automation", json=alert_config)
```

### Device Health Monitoring

```python
# Create device offline alert
offline_config = {
    "type": "device_offline",
    "device_id": "grill_001",
    "alert_name": "Device Disconnected",
    "offline_duration": "00:05:00"
}
requests.post("http://service:5000/api/v1/automation", json=offline_config)

# Create battery low alert
battery_config = {
    "type": "battery_low",
    "device_id": "grill_001",
    "battery_threshold": 20,
    "alert_name": "Replace Battery"
}
requests.post("http://service:5000/api/v1/automation", json=battery_config)
```

## Home Assistant Integration

### Entity Naming Convention
- Temperature sensors: `sensor.grill_stats_{device_id}_{probe_id}_temperature`
- Battery sensors: `sensor.grill_stats_{device_id}_battery`
- Signal strength: `sensor.grill_stats_{device_id}_signal_strength`
- Connection status: `binary_sensor.grill_stats_{device_id}_connection`

### Auto-Discovery
The service automatically registers entities in Home Assistant using MQTT discovery protocol:

```yaml
# Example discovery payload
sensor:
  - name: "Grill Device 1 Probe 1 Temperature"
    unique_id: "grill_stats_device_001_1_temperature"
    state_topic: "homeassistant/sensor/device_001/temperature/state"
    device_class: "temperature"
    unit_of_measurement: "°F"
    device:
      identifiers: ["device_001"]
      name: "Grill Device 1"
      manufacturer: "ThermoWorks"
```

### Automation Examples

Home Assistant automations automatically created by the service:

```yaml
# Temperature alert automation
automation:
  - id: "temperature_alert_device_001_1_high_temp"
    alias: "Temperature Alert: High Temperature"
    trigger:
      platform: numeric_state
      entity_id: sensor.grill_stats_device_001_1_temperature
      above: 250
      for: "00:00:30"
    action:
      service: notify.persistent_notification
      data:
        title: "Temperature Alert"
        message: "Grill temperature is above 250°F"
```

## Performance & Monitoring

### Key Metrics
- **Connection Success Rate**: >99% target
- **API Response Time**: <200ms average
- **State Sync Latency**: <5 seconds
- **Error Rate**: <1% of operations
- **Memory Usage**: <100MB typical

### Health Checks
- Home Assistant connectivity
- Entity registry health
- State synchronization status
- Discovery service health
- Memory and performance metrics

### Logging
Structured logging with multiple levels:
```
2023-12-07 10:30:15 - homeassistant.client - INFO - Connection successful (45.2ms)
2023-12-07 10:30:16 - entity.manager - INFO - Created temperature sensor: sensor.grill_stats_device_001_1_temperature
2023-12-07 10:30:17 - state.sync - DEBUG - Queued temperature sync for device_001: 225.5°F
```

## Testing

### Run Integration Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/test_integration.py -v

# Run with coverage
pytest tests/test_integration.py --cov=src --cov-report=html
```

### Test Coverage
- Home Assistant client functionality
- Entity creation and management
- State synchronization workflows
- Automation creation and management
- Discovery service integration
- Error handling and recovery
- Complete integration workflows

## Development

### Mock Mode
Enable mock mode for development without Home Assistant:
```bash
export MOCK_MODE=true
python main.py
```

### Adding New Entity Types
1. Define entity model in `src/models/entity_models.py`
2. Add creation method to `EntityManager`
3. Add sync support to `StateSynchronizer`
4. Update discovery service for auto-registration
5. Add API endpoint in `src/api/routes.py`

### Custom Automation Types
1. Define automation structure in `src/models/entity_models.py`
2. Add creation method to `AutomationHelper`
3. Implement Home Assistant deployment logic
4. Add API endpoint for automation creation

## Troubleshooting

### Common Issues

**Connection Failed**
```bash
# Check Home Assistant URL and token
curl -H "Authorization: Bearer YOUR_TOKEN" http://homeassistant:8123/api/

# Verify SSL settings
export HOME_ASSISTANT_VERIFY_SSL=false
```

**Entity Not Appearing**
- Check entity naming conventions
- Verify Home Assistant discovery is enabled
- Check service logs for errors
- Force sync all entities via API

**State Sync Issues**
- Check Redis connectivity
- Verify WebSocket connection
- Review throttling settings
- Monitor sync metrics

**Automation Deployment Failed**
- Verify Home Assistant automation service
- Check automation syntax
- Review Home Assistant logs
- Test with mock mode first

### Debug Mode
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
python main.py
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add comprehensive tests
4. Update documentation
5. Submit pull request

## License

MIT License - see LICENSE file for details.