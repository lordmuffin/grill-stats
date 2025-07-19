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

### Code Quality and Linting
- **Syntax and error checking**: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- **Code complexity and style**: `flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics`
- **Install flake8**: `pip install flake8`

### Testing API Endpoints
- Health check: `curl http://localhost:5000/health`
- List devices: `curl http://localhost:5000/devices`
- Get device temperature: `curl http://localhost:5000/devices/{device_id}/temperature`
- Get device history: `curl http://localhost:5000/devices/{device_id}/history?start=2024-01-01T00:00:00&end=2024-01-02T00:00:00`
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
- **Sensor Naming**: Converts device names to Home Assistant entity IDs (`thermoworks_{device_name}`)

### Key Configuration
- **Sync Interval**: 5-minute background job (configurable in app.py:109)
- **Sensor Attributes**: Temperature, battery level, signal strength, timestamps
- **Docker Deployment**: Uses volume mapping for config directory
- **Port Mapping**: Flask runs on port 5000 (exposed in Docker)

### REST API Endpoints
- `GET /health` - Health check with timestamp
- `GET /devices` - List all ThermoWorks devices
- `GET /devices/{id}/temperature` - Get current temperature for specific device
- `GET /devices/{id}/history` - Get historical data with optional start/end parameters
- `POST /sync` - Trigger manual temperature sync
- `GET /homeassistant/test` - Test Home Assistant connection

## CI/CD Pipeline

The project uses Gitea Actions for continuous integration:

### Workflow Configuration
- **Trigger**: Runs on push to main/develop branches and PRs to main
- **Runner**: Ubuntu-latest with Docker-in-Docker support
- **Workflow File**: `.gitea/workflows/build.yaml`

### Pipeline Steps
**Test Job:**
1. **Repository Checkout**: Uses `actions/checkout@v4`
2. **Python Setup**: Installs Python 3.11 and dependencies
3. **Code Linting**: Runs flake8 for syntax errors and code quality
4. **Application Testing**: Import tests (currently commented out)

**Build Job:**
1. **Docker Image Building**: Creates tagged images (SHA and latest)
2. **Container Testing**: Verifies Docker image starts successfully
3. **Artifact Upload**: Saves Docker image for main branch builds

### Available Quality Checks
- **Syntax Validation**: Flake8 checks for Python syntax errors
- **Code Complexity**: Max complexity 10, line length 127
- **Docker Build Testing**: Ensures container builds and starts

## Technology Stack

### Core Dependencies
- **Flask 2.3.3**: Web framework for REST API
- **APScheduler 3.10.4**: Background job scheduling for temperature sync
- **Requests 2.31.0**: HTTP client for API communication
- **python-dotenv 1.0.0**: Environment variable management
- **Pydantic 2.4.2**: Data validation and serialization
- **homeassistant-api 5.0.0**: Home Assistant REST API integration

### Development Tools
- **flake8**: Code linting and style checking
- **Docker**: Containerization for deployment
- **Gitea Actions**: CI/CD pipeline automation

## Environment Variables
- `THERMOWORKS_API_KEY`: Required for ThermoWorks API access
- `HOMEASSISTANT_URL`: Full URL to Home Assistant instance
- `HOMEASSISTANT_TOKEN`: Long-lived access token for Home Assistant API

## Deployment Notes
- Always be able to perform local tests on my code
- Always start a new feature branch using Git when working Task section
- Remember for CI/CD we are using gitea runners on kubernetes, we can't use Docker commands
- always read PLANNING.MD at the start of a new conversation
- check TASKS.md before starting your work
- mark completed tasks immediately
- add newly discovered tasks
