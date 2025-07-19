# Grill Monitoring Microservices Platform

A cloud-native, Kubernetes-based microservices platform for monitoring ThermoWorks wireless thermometers with Home Assistant integration. This project transforms a monolithic Flask application into a scalable, distributed system following modern DevOps practices.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Services](#services)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Development](#development)
- [Monitoring](#monitoring)
- [Contributing](#contributing)

## 🏗️ Architecture Overview

The platform follows a microservices architecture with clear service boundaries:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │ Device Service  │    │Temperature Svc  │
│   (Kong/Nginx)  │    │  (PostgreSQL)   │    │   (InfluxDB)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│Home Assistant   │    │  Notification   │    │   Data Proc.    │
│    Service      │    │    Service      │    │    Service      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

- **Device Management Service**: ThermoWorks device discovery and configuration
- **Temperature Data Service**: Real-time data collection with time-series storage
- **Home Assistant Integration**: Sensor creation and state synchronization
- **API Gateway**: Centralized routing, authentication, and rate limiting
- **Data Processing Service**: Analytics, alerts, and data transformation
- **Notification Service**: Multi-channel alerting and escalation
- **Web UI**: Real-time temperature monitoring dashboard

## ✨ Features

See the detailed [FEATURES.md](FEATURES.md) for comprehensive documentation of implemented features.

### 🔄 Real-Time Monitoring

- **OAuth2 authentication** with ThermoWorks Cloud API
- **Robust API client** with automatic token refresh and error handling
- **Configurable polling intervals** from 5 seconds to 5 minutes
- **Real-time temperature charts** with multiple probe support
- **Device health monitoring** with battery and signal indicators
- **Disconnected probe detection** with visual indicators
- **Redis-based caching** for sub-second response times

### 📊 Time-Series Data Storage

- **InfluxDB integration** for high-performance time-series data
- **Configurable retention policies** (1 day, 1 week, 1 month, 1 year)
- **Aggregation queries** (mean, max, min) with custom intervals
- **Batch processing** for high-throughput data ingestion

### 🏠 Home Assistant Integration

- **Automatic sensor creation** with proper device classes
- **State synchronization** with battery and signal strength
- **Entity naming conventions** following HA best practices
- **Service discovery** and health monitoring

### 🛡️ Security & Observability

- **User Authentication** with email/password login
- **Account security** with lockout protection
- **Zero-trust network policies** with Kubernetes NetworkPolicy
- **OpenTelemetry instrumentation** for distributed tracing
- **Structured logging** with JSON formatting
- **Health checks** and readiness probes
- **Resource quotas** and security contexts

## 🛠️ Services

### Device Management Service

**Port**: 8080
**Database**: PostgreSQL
**Purpose**: Device discovery, registration, and configuration management

**Key Endpoints**:
- `POST /api/devices/discover` - Discover and register ThermoWorks devices
- `GET /api/devices` - List all registered devices
- `GET /api/devices/{id}` - Get specific device details
- `PUT /api/devices/{id}` - Update device configuration
- `GET /api/devices/{id}/health` - Device health status
- `GET /api/devices/{id}/temperature` - Current temperature readings
- `GET /api/devices/{id}/history` - Historical temperature data
- `POST /api/sync` - Manually trigger data synchronization
- `GET /api/auth/thermoworks/status` - Check ThermoWorks connection status

### Temperature Data Service

**Port**: 8080
**Database**: InfluxDB + Redis
**Purpose**: Real-time temperature data collection and historical analysis

**Key Endpoints**:
- `GET /api/temperature/current/{device_id}` - Current temperature reading
- `GET /api/temperature/history/{device_id}` - Historical data with aggregation
- `POST /api/temperature/batch` - Batch temperature data storage
- `GET /api/temperature/stats/{device_id}` - Temperature statistics
- `GET /api/temperature/stream/{device_id}` - Real-time SSE stream
- `GET /api/temperature/alerts/{device_id}` - Temperature alerts

### Web UI Service

**Port**: 3000
**Purpose**: React-based web interface for temperature monitoring

**Key Features**:
- Real-time temperature charts
- Multiple probe visualization
- Device selection and configuration
- Historical data viewing
- Responsive design for mobile and desktop

## 📋 Prerequisites

### Infrastructure Requirements
- **Kubernetes 1.24+** with RBAC enabled
- **Helm 3.0+** for package management
- **ArgoCD** for GitOps deployment (optional)
- **Cilium CNI** for advanced networking (recommended)

### Database Requirements
- **PostgreSQL 13+** for device management
- **InfluxDB 1.8+** for time-series data
- **Redis 6.0+** for caching and streaming

### External Services
- **ThermoWorks Cloud API** account and API key
- **Home Assistant** instance with Long-Lived Access Token

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/lordmuffin/grill-stats.git
cd grill-stats
```

### 2. Environment Configuration
```bash
# Copy and edit environment configuration
cp kubernetes/configmap.yaml.example kubernetes/configmap.yaml
# Update secrets with your API keys
kubectl apply -f kubernetes/configmap.yaml
```

### 3. Deploy with Kustomize
```bash
# Create namespace and RBAC
kubectl apply -k kustomize/overlays/dev

# Verify deployment
kubectl get pods -n grill-stats-dev
```

### 4. Deploy Infrastructure
```bash
# Create namespace and RBAC
kubectl apply -f kubernetes/namespace.yaml

# Deploy database services
kubectl apply -f kubernetes/postgresql.yaml
kubectl apply -f kubernetes/influxdb.yaml
kubectl apply -f kubernetes/redis.yaml
```

### 5. Deploy Microservices
```bash
# Deploy core services
kubectl apply -f kubernetes/device-service.yaml
kubectl apply -f kubernetes/temperature-service.yaml

# Verify deployment
kubectl get pods -n grill-stats
```

### 6. Access Services
```bash
# Port forward for local access
kubectl port-forward -n grill-stats svc/device-service 8080:8080
kubectl port-forward -n grill-stats svc/temperature-service 8081:8080
kubectl port-forward -n grill-stats svc/web-ui 3000:3000

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8081/health
```

## ⚙️ Configuration

### Environment Variables

#### Required Secrets
```yaml
THERMOWORKS_CLIENT_ID: "your-thermoworks-client-id"
THERMOWORKS_CLIENT_SECRET: "your-thermoworks-client-secret"
THERMOWORKS_REDIRECT_URI: "http://localhost:8080/api/auth/thermoworks/callback"
HOMEASSISTANT_URL: "http://homeassistant:8123"
HOMEASSISTANT_TOKEN: "your-long-lived-access-token"
DB_USERNAME: "grill_monitor"
DB_PASSWORD: "secure-database-password"
REDIS_PASSWORD: "redis-authentication-password"
SECRET_KEY: "secure-random-secret-key-for-flask-sessions"
```

#### Service Configuration
```yaml
# Sync intervals and thresholds
THERMOWORKS_POLLING_INTERVAL: "60"  # 1 minute
TEMPERATURE_THRESHOLD_HIGH: "250"  # °F
TEMPERATURE_THRESHOLD_LOW: "32"    # °F

# Database connections
DB_HOST: "postgresql-service"
REDIS_HOST: "redis-service"
INFLUXDB_HOST: "influxdb-service"
```

### Kubernetes Resources
- **CPU Requests**: 100m per service
- **Memory Requests**: 128Mi-512Mi per service
- **Storage**: 10Gi for PostgreSQL, 20Gi for InfluxDB
- **Replicas**: 2 per service for high availability

## 📚 API Documentation

### Device Service API

#### Discover Devices
```bash
POST /api/devices/discover
Content-Type: application/json

Response:
{
  "status": "success",
  "data": {
    "devices": [
      {
        "device_id": "tw_12345",
        "name": "Grill Monitor",
        "model": "Signals",
        "firmware_version": "1.2.3",
        "last_seen": "2024-01-01T00:00:00Z",
        "battery_level": 85,
        "signal_strength": 95,
        "is_online": true
      }
    ],
    "count": 1
  }
}
```

#### Get Device Health
```bash
GET /api/devices/{device_id}/health

Response:
{
  "status": "success",
  "data": {
    "device_id": "tw_12345",
    "health": {
      "battery_level": 85,
      "signal_strength": 95,
      "status": "online",
      "last_seen": "2024-01-01T12:00:00Z"
    }
  }
}
```

#### Current Temperature
```bash
GET /api/devices/{device_id}/temperature?probe_id=probe1

Response:
{
  "status": "success",
  "data": {
    "readings": [
      {
        "device_id": "tw_12345",
        "probe_id": "probe1",
        "temperature": 225.5,
        "unit": "F",
        "timestamp": "2024-01-01T12:00:00Z",
        "battery_level": 85,
        "signal_strength": 95
      }
    ],
    "count": 1,
    "source": "api"
  }
}
```

#### Historical Data
```bash
GET /api/devices/{device_id}/history?start_time=2024-01-01T00:00:00Z&end_time=2024-01-02T00:00:00Z&limit=100

Response:
{
  "status": "success",
  "data": {
    "history": [
      {
        "device_id": "tw_12345",
        "probe_id": "probe1",
        "temperature": 225.5,
        "unit": "F",
        "timestamp": "2024-01-01T12:00:00Z"
      }
    ],
    "count": 24,
    "query": {
      "device_id": "tw_12345",
      "start_time": "2024-01-01T00:00:00Z",
      "end_time": "2024-01-02T00:00:00Z",
      "limit": 100
    }
  }
}
```

## 🚢 Deployment

### Local Development

#### Prerequisites
- Python 3.11 or higher
- Docker and Docker Compose
- Git

#### Option 1: Python Virtual Environment (Recommended for Development)

```bash
# Clone repository
git clone https://github.com/lordmuffin/grill-stats.git
cd grill-stats

# Setup Python virtual environment (using provided script)
./setup-venv.sh

# Activate the virtual environment
source venv/bin/activate

# Setup environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the application
python app.py
```

#### Option 2: Docker Compose (Recommended for Full Stack Testing)

```bash
# Clone repository
git clone https://github.com/lordmuffin/grill-stats.git
cd grill-stats

# Setup environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the monolithic application with all dependencies
docker-compose up --build

# To run microservices version instead
docker-compose --profile microservices up --build
```

#### Environment Configuration

You need to configure the following environment variables in your `.env` file:

```
# ThermoWorks API
THERMOWORKS_API_KEY=your_api_key
THERMOWORKS_CLIENT_ID=your-client-id
THERMOWORKS_CLIENT_SECRET=your-client-secret
THERMOWORKS_REDIRECT_URI=http://localhost:8080/api/auth/thermoworks/callback

# Home Assistant
HOMEASSISTANT_URL=http://your-ha-instance:8123
HOMEASSISTANT_TOKEN=your-long-lived-token
```

#### Development Tools

The project is configured with several development tools:

- **flake8**: Code linting and style checking
- **black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking

You can run these tools with the following commands:

```bash
# Lint code
flake8 .

# Format code
black .

# Sort imports
isort .

# Type checking
mypy .
```

#### Working with Individual Services

```bash
# Device Service
cd services/device-service
python main.py

# Temperature Service
cd services/temperature-service
python main.py

# Web UI
cd services/web-ui
npm install
npm start
```

### Kubernetes Deployment
```bash
# Apply all manifests
kubectl apply -f kubernetes/

# Apply with Kustomize for environment-specific configs
kubectl apply -k kustomize/overlays/dev  # Development environment
kubectl apply -k kustomize/overlays/staging  # Staging environment
kubectl apply -k kustomize/overlays/prod  # Production environment

# Monitor deployment
kubectl get pods -n grill-stats -w

# View logs
kubectl logs -f deployment/device-service -n grill-stats
```

### ArgoCD Deployment
```bash
# Create ArgoCD application
kubectl apply -f argocd/application.yaml

# Sync application
argocd app sync grill-stats
```

## 🔧 Development

### Project Structure
```
grill-stats/
├── services/
│   ├── device-service/
│   │   ├── main.py
│   │   ├── thermoworks_client.py
│   │   └── requirements.txt
│   ├── temperature-service/
│   │   ├── main.py
│   │   ├── temperature_manager.py
│   │   └── requirements.txt
│   ├── web-ui/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   │   ├── RealTimeChart.jsx
│   │   │   │   └── TemperatureDashboard.jsx
│   │   │   └── utils/
│   │   │       └── api.js
│   │   └── package.json
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── device-service.yaml
│   └── temperature-service.yaml
├── kustomize/
│   ├── base/
│   │   ├── namespace/
│   │   ├── databases/
│   │   ├── core-services/
│   │   ├── ingress/
│   │   └── operators/
│   └── overlays/
│       ├── dev/
│       ├── staging/
│       └── prod/
├── tests/
├── docs/
└── README.md
```

### Adding New Services
1. Create service directory in `services/`
2. Implement service with health check endpoint
3. Add Kubernetes manifests
4. Update network policies
5. Add to CI/CD pipeline

### Testing
```bash
# Run unit tests
python -m pytest tests/

# Integration tests
kubectl apply -f tests/integration/

# Load testing
artillery run tests/load/temperature-service.yml
```

## 📊 Monitoring

### Health Checks
All services expose `/health` endpoints for:
- **Liveness Probes**: Service is running
- **Readiness Probes**: Service can handle traffic
- **Database Connectivity**: Backend service health

### Observability Stack
- **OpenTelemetry**: Distributed tracing and metrics
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **Structured Logging**: JSON logs with correlation IDs

### Key Metrics
- **Response Time**: p95 < 100ms for current temperature
- **Throughput**: 1000+ requests/second per service
- **Error Rate**: < 0.1% for all endpoints
- **Data Freshness**: Temperature data < 5 minutes old

## 🔄 Migration from Monolithic App

This platform replaces the original monolithic Flask application (`app.py`) with distributed microservices:

### Migration Benefits
- **Scalability**: Independent scaling per service
- **Reliability**: Fault isolation and circuit breakers
- **Maintainability**: Clear service boundaries
- **Performance**: Specialized databases for each use case
- **Observability**: Distributed tracing and monitoring

### Backward Compatibility
- **API Compatibility**: Existing endpoints maintained
- **Data Migration**: Automatic migration scripts
- **Gradual Rollout**: Blue-green deployment support

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-service`
3. Run tests: `make test`
4. Submit pull request with clear description

### Code Standards
- **Python**: PEP 8 with black formatting
- **Docker**: Multi-stage builds with security scanning
- **Kubernetes**: Resource limits and security contexts
- **Documentation**: OpenAPI specs for all APIs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- [Features Overview](FEATURES.md)
- [Multi-Agent Implementation Plan](multi-agent-implementation.md)
- [Claude Code Guidance](CLAUDE.md)
- [API Reference](docs/api-reference.md)

### Issues and Support
- Create issues for bug reports or feature requests
- Check existing issues before creating new ones
- Provide detailed reproduction steps

### Community
- Discussions for questions and ideas
- Contributions welcome for all skill levels
- Code review and mentoring available

---

## 🏷️ Version History

### v1.2.0 (Current)
- ✅ User Authentication with login/logout functionality
- ✅ Account security with failed login tracking and lockout protection
- ✅ Route protection with login requirements
- ✅ User-friendly dashboard interface

### v1.1.0
- ✅ Device Management Service with OAuth2 ThermoWorks integration
- ✅ Real-time temperature monitoring with Chart.js visualization
- ✅ Kubernetes Kustomize configurations for multi-environment deployment
- ✅ Detailed API documentation with OpenAPI/Swagger
- ✅ Robust error handling and connection status tracking

### v1.0.0
- ✅ Device Management Service with PostgreSQL
- ✅ Temperature Data Service with InfluxDB + Redis
- ✅ Kubernetes manifests with security policies
- ✅ OpenTelemetry instrumentation
- ✅ Multi-agent implementation framework

### Roadmap
- 🔄 Home Assistant Integration Service
- 🔄 RFX Gateway support for direct probe connectivity
- ⏳ API Gateway with Kong/Nginx
- ⏳ Notification Service with multi-channel alerts
- ⏳ Data Processing Service with analytics
- ⏳ Mobile application with push notifications

---

**Built with ❤️ for the grilling community**
