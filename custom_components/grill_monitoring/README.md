# Grill Monitoring Custom Component

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/lordmuffin/grill-stats)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A comprehensive Home Assistant integration for monitoring ThermoWorks wireless thermometers and grill temperature sensors.

## Features

- **Multi-Device Support**: Automatically discovers and monitors multiple ThermoWorks devices
- **Multi-Probe Sensors**: Supports devices with multiple temperature probes
- **Real-time Monitoring**: Configurable update intervals (10-300 seconds)
- **Battery Monitoring**: Tracks battery levels for wireless devices
- **Signal Strength**: Monitors wireless signal strength and connectivity
- **Device Health**: Comprehensive health monitoring and error handling
- **HACS Compatible**: Easy installation and updates through HACS

## Installation

### HACS Installation (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/lordmuffin/grill-stats`
6. Select "Integration" as the category
7. Click "Add"
8. Find "Grill Monitoring" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the `grill_monitoring` folder from this repository
2. Copy it to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

Before configuring the integration, ensure you have:

1. **Device Service**: Running at `http://localhost:8080` (or your custom URL)
2. **Temperature Service**: Running at `http://localhost:8081` (or your custom URL)
3. **ThermoWorks API Key**: Configured in your microservices

### Setup via UI

1. Go to **Settings > Devices & Services**
2. Click **Add Integration**
3. Search for "Grill Monitoring"
4. Enter your service URLs:
   - Device Service URL (default: `http://localhost:8080`)
   - Temperature Service URL (default: `http://localhost:8081`)
5. Configure optional settings:
   - **Scan Interval**: How often to update data (10-300 seconds, default: 30)
   - **Timeout**: Request timeout in seconds (5-60 seconds, default: 10)
6. Click **Submit**

The integration will automatically test the connection and discover your devices.

## Entities

The integration creates the following entity types:

### Temperature Sensors
- **Device Temperature**: Main temperature reading for each device
- **Probe Temperature**: Individual temperature readings for multi-probe devices
- **Unit**: Automatically detects Fahrenheit or Celsius
- **Attributes**: Device ID, probe ID, temperature unit, last seen timestamp

### Battery Sensors
- **Battery Level**: Battery percentage for wireless devices
- **Attributes**: Device ID, last seen timestamp

### Signal Strength Sensors
- **Signal Strength**: Wireless signal strength in dBm
- **Attributes**: Device ID, last seen timestamp

## Device Information

Each device appears in Home Assistant with:
- **Name**: Device name from ThermoWorks
- **Manufacturer**: ThermoWorks
- **Model**: Device type
- **Software Version**: Firmware version (if available)
- **Identifiers**: Unique device ID

## Services

The integration provides access to the underlying microservice APIs:

### Available Data
- Real-time temperature readings
- Historical temperature data
- Device health status
- Battery levels and signal strength
- Device configuration and metadata

### API Endpoints
- Device discovery and management
- Current temperature readings
- Historical data queries
- Temperature statistics
- Device health monitoring

## Troubleshooting

### Common Issues

**Integration not loading:**
- Verify both microservices are running and accessible
- Check the service URLs in the integration configuration
- Review Home Assistant logs for connection errors

**No devices discovered:**
- Ensure ThermoWorks API key is configured in the microservices
- Check device service logs for API connection issues
- Verify devices are registered and active in ThermoWorks

**Temperature data not updating:**
- Check temperature service logs for API errors
- Verify scan interval is appropriate for your setup
- Ensure devices are powered on and connected

**Battery/Signal data missing:**
- Some devices may not report battery or signal data
- Check device health endpoint for available data
- Verify device supports these features

### Debug Logging

Enable debug logging by adding to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.grill_monitoring: debug
```

### Service Health

Monitor service health using the built-in health check endpoints:
- Device Service: `http://localhost:8080/health`
- Temperature Service: `http://localhost:8081/health`

## Configuration Examples

### Basic Configuration
```yaml
# Automatically configured via UI
# No manual YAML configuration required
```

### Advanced Microservice Setup
```yaml
# Example microservice configuration
# See main project documentation for details
services:
  device-service:
    environment:
      - THERMOWORKS_API_KEY=your_api_key
      - DB_HOST=postgres
      - DB_NAME=grill_monitoring

  temperature-service:
    environment:
      - THERMOWORKS_API_KEY=your_api_key
      - INFLUXDB_HOST=influxdb
      - REDIS_HOST=redis
```

## Automation Examples

### Temperature Alerts
```yaml
automation:
  - alias: "Grill Temperature Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.grill_device_temperature
        above: 400
    action:
      - service: notify.mobile_app
        data:
          message: "Grill temperature is too high: {{ states('sensor.grill_device_temperature') }}°F"
```

### Battery Low Warning
```yaml
automation:
  - alias: "Grill Battery Low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.grill_device_battery
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Grill device battery is low: {{ states('sensor.grill_device_battery') }}%"
```

### Multi-Probe Monitoring
```yaml
automation:
  - alias: "Meat Ready Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.grill_device_probe_1
        above: 165
    condition:
      - condition: numeric_state
        entity_id: sensor.grill_device_probe_2
        above: 160
    action:
      - service: notify.mobile_app
        data:
          message: "Both probes indicate meat is ready!"
```

## Support

For issues and support:
- **GitHub Issues**: [Report bugs and feature requests](https://github.com/lordmuffin/grill-stats/issues)
- **Documentation**: [Full project documentation](https://github.com/lordmuffin/grill-stats)
- **Community**: [Home Assistant Community Forum](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Please see the main project repository for contribution guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
