# Device Service

The Device Service is responsible for managing ThermoWorks devices and retrieving temperature data.

## Features

- OAuth2 authentication with ThermoWorks API
- Device discovery and management
- Real-time temperature monitoring
- Historical temperature data retrieval
- Home Assistant integration for RFX Gateways
- Redis integration for real-time data sharing

## Architecture

The Device Service is built with a clean architecture using dependency injection. It consists of the following components:

- **Flask API**: Provides REST endpoints for device management and temperature data
- **ThermoWorks Client**: Communicates with the ThermoWorks Cloud API
- **Device Manager**: Manages device data in the database
- **RFX Gateway Client**: Communicates with RFX Gateways through Home Assistant
- **Temperature Handler**: Processes temperature readings
- **Redis Integration**: Shares data with other services

## Dependency Injection

The service uses the `dependency-injector` library to implement a clean dependency injection pattern. This makes the codebase more modular, testable, and maintainable.

### Container Structure

- **ApplicationContainer**: Main container that configures the application
  - **OpenTelemetryContainer**: Container for OpenTelemetry components
  - **ServicesContainer**: Container for main service components

### Key Benefits

- **Testability**: Services can be easily mocked for unit testing
- **Flexibility**: Dependencies can be replaced without changing the client code
- **Configurability**: Configuration is centralized and can be easily changed
- **Decoupling**: Components are decoupled and can be developed independently

### Usage Example

```python
# Define dependencies in containers.py
class ServicesContainer(containers.DeclarativeContainer):
    device_manager = providers.Singleton(
        DeviceManager,
        db_host=config.db.host,
        db_port=config.db.port,
        # ...
    )

# Use dependencies in your code
@app.route("/api/devices")
@inject
def get_devices(
    device_manager=Provide[ServicesContainer.device_manager]
):
    # Use device_manager
    devices = device_manager.get_devices()
    return jsonify({"devices": devices})
```

## OpenTelemetry Integration

The service is instrumented with OpenTelemetry for observability:

- **Tracing**: Captures request spans and dependencies
- **Metrics**: Tracks API requests, response times, and temperature data
- **Prometheus Integration**: Exposes metrics for scraping

## Development

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis (optional)
- ThermoWorks API credentials
- Home Assistant instance (for RFX Gateway support)

### Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables (see below)
4. Run the service: `python main.py`

### Environment Variables

Create a `.env` file with the following variables:

```
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=grill_stats
DB_USER=postgres
DB_PASSWORD=

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# ThermoWorks
THERMOWORKS_CLIENT_ID=your-client-id
THERMOWORKS_CLIENT_SECRET=your-client-secret
THERMOWORKS_REDIRECT_URI=http://localhost:8080/api/auth/thermoworks/callback
THERMOWORKS_BASE_URL=https://api.thermoworks.com
THERMOWORKS_AUTH_URL=https://auth.thermoworks.com
TOKEN_STORAGE_PATH=./tokens

# Home Assistant
HOMEASSISTANT_URL=http://your-ha-instance:8123
HOMEASSISTANT_TOKEN=your-long-lived-token

# RFX Gateway
RFX_SCAN_DURATION=30
RFX_CONNECTION_TIMEOUT=15
RFX_SETUP_TIMEOUT=300

# JWT
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
```

### Testing

Run tests with pytest:

```
pytest tests/
```

## API Documentation

API documentation is available at `/api/docs` when the service is running.

## License

MIT

