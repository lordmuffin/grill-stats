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

## ✨ Features

### 🔄 Real-Time Monitoring
- **5-minute sync intervals** with ThermoWorks Cloud API
- **Real-time streaming** via Server-Sent Events
- **Redis-based caching** for sub-second response times
- **WebSocket support** for live dashboard updates

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

### 3. Deploy Infrastructure
```bash
# Create namespace and RBAC
kubectl apply -f kubernetes/namespace.yaml

# Deploy database services
kubectl apply -f kubernetes/postgresql.yaml
kubectl apply -f kubernetes/influxdb.yaml
kubectl apply -f kubernetes/redis.yaml
```

### 4. Deploy Microservices
```bash
# Deploy core services
kubectl apply -f kubernetes/device-service.yaml
kubectl apply -f kubernetes/temperature-service.yaml

# Verify deployment
kubectl get pods -n grill-monitoring
```

### 5. Access Services
```bash
# Port forward for local access
kubectl port-forward -n grill-monitoring svc/device-service 8080:8080
kubectl port-forward -n grill-monitoring svc/temperature-service 8081:8080

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8081/health
```

## ⚙️ Configuration

### Environment Variables

#### Required Secrets
```yaml
THERMOWORKS_API_KEY: "your-thermoworks-api-key"
HOMEASSISTANT_URL: "http://homeassistant:8123"
HOMEASSISTANT_TOKEN: "your-long-lived-access-token"
DB_USERNAME: "grill_monitor"
DB_PASSWORD: "secure-database-password"
REDIS_PASSWORD: "redis-authentication-password"
```

#### Service Configuration
```yaml
# Sync intervals and thresholds
SYNC_INTERVAL: "300"  # 5 minutes
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
  "devices": [
    {
      "device_id": "tw_12345",
      "name": "Grill Monitor",
      "device_type": "thermoworks",
      "active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "count": 1
}
```

#### Get Device Health
```bash
GET /api/devices/{device_id}/health

Response:
{
  "status": "success",
  "device_id": "tw_12345",
  "health": {
    "battery_level": 85,
    "signal_strength": 95,
    "status": "online",
    "last_seen": "2024-01-01T12:00:00Z"
  }
}
```

### Temperature Service API

#### Current Temperature
```bash
GET /api/temperature/current/{device_id}?probe_id=probe1

Response:
{
  "status": "success",
  "data": {
    "device_id": "tw_12345",
    "probe_id": "probe1",
    "temperature": 225.5,
    "unit": "F",
    "timestamp": "2024-01-01T12:00:00Z",
    "battery_level": 85,
    "signal_strength": 95
  },
  "source": "api"
}
```

#### Historical Data
```bash
GET /api/temperature/history/{device_id}?start_time=2024-01-01T00:00:00Z&aggregation=mean&interval=1h

Response:
{
  "status": "success",
  "data": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "temperature": 225.5,
      "device_id": "tw_12345"
    }
  ],
  "count": 24,
  "query": {
    "device_id": "tw_12345",
    "start_time": "2024-01-01T00:00:00Z",
    "aggregation": "mean",
    "interval": "1h"
  }
}
```

#### Real-Time Stream
```bash
GET /api/temperature/stream/{device_id}
Accept: text/event-stream

Response:
data: {"device_id":"tw_12345","temperature":225.5,"timestamp":"2024-01-01T12:00:00Z"}

data: {"device_id":"tw_12345","temperature":226.0,"timestamp":"2024-01-01T12:01:00Z"}
```

## 🚢 Deployment

### Local Development
```bash
# Run services locally with Docker Compose
docker-compose up --build

# Individual service development
cd services/device-service
python main.py
```

### Kubernetes Deployment
```bash
# Apply all manifests
kubectl apply -f kubernetes/

# Monitor deployment
kubectl get pods -n grill-monitoring -w

# View logs
kubectl logs -f deployment/device-service -n grill-monitoring
```

### ArgoCD Deployment
```bash
# Create ArgoCD application
kubectl apply -f argocd/application.yaml

# Sync application
argocd app sync grill-monitoring
```

## 🔧 Development

### Project Structure
```
grill-stats/
├── services/
│   ├── device-service/
│   │   ├── main.py
│   │   ├── device_manager.py
│   │   ├── thermoworks_client.py
│   │   └── requirements.txt
│   └── temperature-service/
│       ├── main.py
│       ├── temperature_manager.py
│       └── thermoworks_client.py
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── device-service.yaml
│   └── temperature-service.yaml
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

### v1.0.0 (Current)
- ✅ Device Management Service with PostgreSQL
- ✅ Temperature Data Service with InfluxDB + Redis
- ✅ Kubernetes manifests with security policies
- ✅ OpenTelemetry instrumentation
- ✅ Multi-agent implementation framework

### Roadmap
- 🔄 Home Assistant Integration Service
- ⏳ API Gateway with Kong/Nginx
- ⏳ Notification Service with multi-channel alerts
- ⏳ Data Processing Service with analytics
- ⏳ Web Dashboard with real-time updates

---

**Built with ❤️ for the grilling community**