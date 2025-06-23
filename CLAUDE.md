# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
- **Local development**: `python app.py` (requires environment variables)
- **Docker development**: `docker-compose up --build`
- **Production Docker**: `docker build -t grill-stats . && docker run -p 5000:5000 grill-stats`

### Environment Setup
- Create `.env` file with required variables:
  ```
  THERMOWORKS_API_KEY=your_api_key
  HOMEASSISTANT_URL=http://your-ha-instance:8123
  HOMEASSISTANT_TOKEN=your_long_lived_token
  ```
- Install dependencies: `pip install -r requirements.txt`

### Testing API Endpoints
- Health check: `curl http://localhost:5000/health`
- Manual sync: `curl -X POST http://localhost:5000/sync`
- Test Home Assistant connection: `curl http://localhost:5000/homeassistant/test`

## Architecture Overview

This is a Flask-based temperature monitoring service that bridges ThermoWorks wireless thermometers with Home Assistant. The application follows a three-layer architecture:

### Core Components
1. **app.py**: Main Flask application with REST endpoints and scheduled sync job
2. **thermoworks_client.py**: ThermoWorks API client for fetching temperature data
3. **homeassistant_client.py**: Home Assistant REST API client for creating sensors

### Data Flow
1. **Scheduled Sync**: APScheduler runs `sync_temperature_data()` every 5 minutes
2. **Device Discovery**: Fetches all ThermoWorks devices via API
3. **Temperature Collection**: Retrieves current temperature readings for each device
4. **Sensor Creation**: Creates/updates Home Assistant sensors with temperature data
5. **Attribute Mapping**: Includes device metadata (battery, signal strength, timestamps)

### API Integration Patterns
- **ThermoWorks Client**: Uses Bearer token authentication with session management
- **Home Assistant Client**: Uses Long-Lived Access Token with REST API
- **Error Handling**: Comprehensive logging with graceful failure recovery
- **Sensor Naming**: Converts device names to Home Assistant entity IDs (`thermoworks_device_name`)

### Key Configuration
- **Sync Interval**: 5-minute background job (configurable in app.py:109)
- **Sensor Attributes**: Temperature, battery level, signal strength, timestamps
- **Docker Deployment**: Uses volume mapping for config directory
- **Port Mapping**: Flask runs on port 5000 (exposed in Docker)

## CI/CD Pipeline

The project uses Gitea Actions for continuous integration:

### Workflow Configuration
- **Trigger**: Runs on every push to any branch
- **Runner**: Ubuntu-latest
- **Workflow File**: `.gitea/workflows/demo.yaml`

### Pipeline Steps
1. **Repository Checkout**: Uses `actions/checkout@v4`
2. **Environment Info**: Displays runner OS, branch, and repository details
3. **File Listing**: Lists all files in the workspace
4. **Status Reporting**: Shows job completion status

### Current Limitations
- No automated testing or linting steps
- No Docker image building or deployment
- Basic demo workflow without production features

## Environment Variables
- `THERMOWORKS_API_KEY`: Required for ThermoWorks API access
- `HOMEASSISTANT_URL`: Full URL to Home Assistant instance
- `HOMEASSISTANT_TOKEN`: Long-lived access token for Home Assistant API