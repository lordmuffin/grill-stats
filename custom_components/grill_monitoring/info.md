# Grill Monitoring Integration

Monitor your ThermoWorks wireless thermometers and grill temperature sensors directly in Home Assistant.

## What This Integration Does

This integration connects your Home Assistant instance to ThermoWorks temperature monitoring devices through dedicated microservices, providing:

- **Real-time Temperature Monitoring**: Get live temperature readings from your grill and food probes
- **Multi-Probe Support**: Monitor multiple temperature probes simultaneously
- **Battery Monitoring**: Track battery levels of wireless devices
- **Signal Strength Monitoring**: Monitor wireless connectivity and signal quality
- **Device Health Tracking**: Comprehensive health monitoring and error detection

## Requirements

### Microservices Setup

This integration requires two microservices to be running:

1. **Device Service** (Port 8080): Manages device discovery, registration, and health monitoring
2. **Temperature Service** (Port 8081): Handles temperature data collection, storage, and real-time streaming

### ThermoWorks API Access

You'll need:
- A ThermoWorks account with API access
- ThermoWorks API key configured in the microservices
- Compatible ThermoWorks wireless temperature monitoring devices

## Configuration

### Service URLs

During setup, you'll need to provide:
- **Device Service URL**: Usually `http://localhost:8080` for local setup
- **Temperature Service URL**: Usually `http://localhost:8081` for local setup

### Optional Settings

- **Scan Interval**: How often to update temperature data (10-300 seconds, default: 30)
- **Timeout**: Request timeout for API calls (5-60 seconds, default: 10)

## What Gets Created

### Temperature Sensors
- One sensor per device for main temperature reading
- Additional sensors for each probe on multi-probe devices
- Automatic unit detection (Fahrenheit/Celsius)

### Battery Sensors
- Battery level percentage for wireless devices
- Low battery alerts and notifications

### Signal Strength Sensors
- Wireless signal strength in dBm
- Connection quality monitoring

### Device Information
- Device name and model information
- Firmware version tracking
- Manufacturer identification (ThermoWorks)

## Typical Use Cases

### BBQ and Grilling
- Monitor grill chamber temperature
- Track meat internal temperature with food probes
- Set alerts for target temperatures
- Monitor multiple cuts of meat simultaneously

### Smoking
- Long-term temperature monitoring for smoking sessions
- Probe temperature tracking for different meat types
- Alerts for temperature deviations

### General Cooking
- Oven temperature monitoring
- Food safety temperature verification
- Cooking time optimization

## Automation Examples

### Temperature Alerts
Get notified when temperatures reach target levels or go outside safe ranges.

### Battery Warnings
Receive alerts when device batteries are running low.

### Cooking Timers
Create automations based on temperature thresholds to optimize cooking times.

### Multi-Zone Monitoring
Monitor different areas of your grill or smoker simultaneously.

## Integration Benefits

- **Centralized Monitoring**: All temperature data in one place
- **Historical Data**: Track temperature trends over time
- **Smart Alerts**: Automated notifications for various conditions
- **Device Management**: Easy device discovery and configuration
- **Reliable Updates**: Robust error handling and connection management

## Getting Started

1. Ensure your microservices are running and accessible
2. Add the integration through the Home Assistant UI
3. Configure your service URLs
4. Let the integration discover your devices
5. Start monitoring temperatures and creating automations

The integration will automatically discover your ThermoWorks devices and create appropriate sensors in Home Assistant.
