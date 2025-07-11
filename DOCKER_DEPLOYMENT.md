# Docker Deployment Guide for ThermoWorks BBQ Monitoring Application

This guide provides comprehensive instructions for building, deploying, and managing Docker containers for the ThermoWorks BBQ monitoring application microservices.

## Overview

The ThermoWorks BBQ monitoring application consists of six core microservices, each containerized for production deployment:

1. **Authentication Service** (`auth-service`) - JWT-based authentication with ThermoWorks integration
2. **Device Service** (`device-service`) - Device management and ThermoWorks Cloud integration
3. **Temperature Service** (`temperature-service`) - Real-time temperature data with SSE streaming
4. **Historical Data Service** (`historical-data-service`) - Historical temperature data analysis
5. **Encryption Service** (`encryption-service`) - Secure credential storage with Vault integration
6. **Web UI Service** (`web-ui`) - React frontend application

## Architecture

### Container Design Principles

All services follow production-ready containerization patterns:

- **Multi-stage builds** for optimized image size
- **Alpine Linux** base images for minimal attack surface
- **Non-root user execution** for enhanced security
- **Health checks** for Kubernetes readiness/liveness probes
- **Consistent labeling** and metadata
- **Resource-efficient** layer caching

### Service Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| auth-service | 8082 | HTTP | Authentication API |
| device-service | 8080 | HTTP | Device Management API |
| temperature-service | 8080 | HTTP | Temperature Data API |
| historical-data-service | 8080 | HTTP | Historical Data API |
| encryption-service | 8082 | HTTP | Encryption API |
| web-ui | 80 | HTTP | Web Interface |

### Image Tagging Strategy

All images follow a consistent tagging strategy:

```
{registry}/{project}/{service}:{tag}
```

Where:
- `registry`: Container registry URL (e.g., `localhost:5000`)
- `project`: `grill-stats`
- `service`: Service name (e.g., `auth-service`)
- `tag`: Version tag (`latest`, `v1.0.3`, `git-commit-hash`)

## Quick Start

### 1. Setup Local Registry

```bash
# Start local Docker registry
./setup-registry.sh start

# Configure Docker for insecure registry (Linux only)
./setup-registry.sh configure

# Check registry status
./setup-registry.sh status
```

### 2. Build All Images

```bash
# Build all microservice images
./build-images.sh

# Build with custom registry
./build-images.sh -r harbor.example.com

# Build with vulnerability scanning
./build-images.sh -s

# Build with custom version
./build-images.sh -v 1.0.4
```

### 3. Push Images to Registry

```bash
# Push all images to registry
./push-images.sh

# Push to custom registry
./push-images.sh -r harbor.example.com

# List available images
./push-images.sh -l
```

## Detailed Build Process

### Manual Build Commands

If you prefer to build images manually:

```bash
# Build auth-service
cd services/auth-service
docker build -t localhost:5000/grill-stats/auth-service:latest .

# Build device-service
cd ../device-service
docker build -t localhost:5000/grill-stats/device-service:latest .

# Build temperature-service
cd ../temperature-service
docker build -t localhost:5000/grill-stats/temperature-service:latest .

# Build historical-data-service
cd ../historical-data-service
docker build -t localhost:5000/grill-stats/historical-data-service:latest .

# Build encryption-service
cd ../encryption-service
docker build -t localhost:5000/grill-stats/encryption-service:latest .

# Build web-ui
cd ../web-ui
docker build -t localhost:5000/grill-stats/web-ui:latest .
```

### Build Arguments

All Python services support these build arguments:

- `BUILD_DATE`: Build timestamp
- `GIT_COMMIT`: Git commit hash
- `VERSION`: Application version

Example:
```bash
docker build \
  --build-arg BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --build-arg GIT_COMMIT="$(git rev-parse --short HEAD)" \
  --build-arg VERSION="1.0.3" \
  -t localhost:5000/grill-stats/auth-service:latest \
  services/auth-service
```

## Container Registry Setup

### Local Registry

The provided `setup-registry.sh` script manages a local Docker registry:

```bash
# Start registry
./setup-registry.sh start

# Check status
./setup-registry.sh status

# Test functionality
./setup-registry.sh test

# Stop registry
./setup-registry.sh stop

# Clean up everything
./setup-registry.sh cleanup
```

### Registry Configuration

The registry uses the following configuration:

```yaml
version: 0.1
log:
  fields:
    service: registry
storage:
  cache:
    blobdescriptor: inmemory
  filesystem:
    rootdirectory: /var/lib/registry
  delete:
    enabled: true
http:
  addr: :5000
  headers:
    X-Content-Type-Options: [nosniff]
    Access-Control-Allow-Origin: ['*']
    Access-Control-Allow-Methods: ['HEAD', 'GET', 'OPTIONS', 'DELETE']
    Access-Control-Allow-Headers: ['Authorization', 'Accept', 'Cache-Control']
    Access-Control-Max-Age: [1728000]
    Access-Control-Allow-Credentials: [true]
    Access-Control-Expose-Headers: ['Docker-Content-Digest']
```

### External Registry Setup

For production deployments, use external registries:

#### Harbor Registry
```bash
# Login to Harbor
docker login harbor.example.com

# Build and push
./build-images.sh -r harbor.example.com
./push-images.sh -r harbor.example.com
```

#### Docker Hub
```bash
# Login to Docker Hub
docker login

# Build and push
./build-images.sh -r docker.io/username
./push-images.sh -r docker.io/username
```

#### Azure Container Registry
```bash
# Login to ACR
az acr login --name myregistry

# Build and push
./build-images.sh -r myregistry.azurecr.io
./push-images.sh -r myregistry.azurecr.io
```

## Security Considerations

### Image Security

All images implement security best practices:

1. **Non-root execution**: All services run as non-root user (UID 1001)
2. **Minimal base images**: Alpine Linux for reduced attack surface
3. **No secrets in images**: All secrets provided via environment variables
4. **Vulnerability scanning**: Optional Trivy scanning in build process
5. **Read-only filesystem**: Containers run with read-only root filesystem

### Vulnerability Scanning

Enable vulnerability scanning during build:

```bash
# Install Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Build with scanning
./build-images.sh -s
```

### Runtime Security

Configure runtime security in Kubernetes:

```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1001
    fsGroup: 1001
  containers:
  - name: auth-service
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
```

## Kubernetes Integration

### Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: grill-stats
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: localhost:5000/grill-stats/auth-service:latest
        ports:
        - containerPort: 8082
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-credentials
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8082
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8082
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### Service Discovery

```yaml
apiVersion: v1
kind: Service
metadata:
  name: auth-service
  namespace: grill-stats
spec:
  selector:
    app: auth-service
  ports:
  - port: 8082
    targetPort: 8082
    protocol: TCP
  type: ClusterIP
```

## Environment Variables

### Common Variables

All services support these environment variables:

```bash
# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=your-secure-secret-key
```

### Service-Specific Variables

#### Auth Service
```bash
JWT_SECRET_KEY=your-jwt-secret
JWT_EXPIRATION_HOURS=24
BCRYPT_ROUNDS=12
```

#### Device Service
```bash
THERMOWORKS_CLIENT_ID=your-client-id
THERMOWORKS_CLIENT_SECRET=your-client-secret
THERMOWORKS_API_URL=https://api.thermoworks.com
```

#### Temperature Service
```bash
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=grill-stats
INFLUXDB_BUCKET=temperature-data
```

#### Historical Data Service
```bash
TIMESCALE_URL=postgresql://user:pass@timescale:5432/historical
RETENTION_DAYS=365
```

#### Encryption Service
```bash
VAULT_URL=http://vault:8200
VAULT_TOKEN=your-vault-token
VAULT_MOUNT_PATH=transit
```

## Monitoring and Logging

### Health Checks

All services expose health endpoints:

```bash
# Check service health
curl http://localhost:8082/health  # auth-service
curl http://localhost:8080/health  # device-service
curl http://localhost:8080/health  # temperature-service
curl http://localhost:8080/health  # historical-data-service
curl http://localhost:8082/health  # encryption-service
curl http://localhost:80/         # web-ui
```

### Metrics Collection

Services expose metrics for Prometheus:

```bash
# Metrics endpoints (if enabled)
curl http://localhost:8082/metrics  # auth-service
curl http://localhost:8080/metrics  # device-service
```

### Log Aggregation

Configure log aggregation with structured logging:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: logging-config
data:
  logging.yml: |
    version: 1
    formatters:
      json:
        format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "%(name)s", "message": "%(message)s"}'
    handlers:
      console:
        class: logging.StreamHandler
        formatter: json
    root:
      level: INFO
      handlers: [console]
```

## Troubleshooting

### Common Issues

#### Build Failures

1. **Docker daemon not running**
   ```bash
   # Check Docker status
   docker info
   
   # Start Docker (Linux)
   sudo systemctl start docker
   ```

2. **Permission denied**
   ```bash
   # Add user to docker group
   sudo usermod -aG docker $USER
   newgrp docker
   ```

3. **Out of disk space**
   ```bash
   # Clean up Docker
   docker system prune -a
   docker volume prune
   ```

#### Registry Issues

1. **Registry not accessible**
   ```bash
   # Check registry status
   curl -f http://localhost:5000/v2/
   
   # Restart registry
   ./setup-registry.sh stop
   ./setup-registry.sh start
   ```

2. **Push failures**
   ```bash
   # Check insecure registry configuration
   docker info | grep -i insecure
   
   # Reconfigure Docker daemon
   ./setup-registry.sh configure
   ```

#### Runtime Issues

1. **Container startup failures**
   ```bash
   # Check container logs
   docker logs <container-id>
   
   # Run container interactively
   docker run -it --rm <image> /bin/sh
   ```

2. **Health check failures**
   ```bash
   # Test health endpoint
   curl -f http://localhost:8082/health
   
   # Check container health
   docker inspect <container-id> | grep -i health
   ```

### Debugging Tools

#### Container Inspection

```bash
# Get container details
docker inspect <container-id>

# Execute commands in container
docker exec -it <container-id> /bin/sh

# View container processes
docker top <container-id>
```

#### Network Debugging

```bash
# List networks
docker network ls

# Inspect network
docker network inspect <network-name>

# Test connectivity
docker run --rm --network <network> alpine ping <service-name>
```

## Performance Optimization

### Build Optimization

1. **Multi-stage builds**: Separate build and runtime stages
2. **Layer caching**: Order instructions by change frequency
3. **Minimal dependencies**: Only install required packages
4. **Build context**: Use .dockerignore to exclude unnecessary files

### Runtime Optimization

1. **Resource limits**: Set appropriate CPU and memory limits
2. **Health check intervals**: Balance responsiveness with resource usage
3. **Replica scaling**: Configure horizontal pod autoscaling
4. **Connection pooling**: Optimize database connections

## Automation and CI/CD

### GitHub Actions Example

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v1
    
    - name: Build images
      run: |
        ./build-images.sh -r ${{ secrets.REGISTRY_URL }}
    
    - name: Login to registry
      uses: docker/login-action@v1
      with:
        registry: ${{ secrets.REGISTRY_URL }}
        username: ${{ secrets.REGISTRY_USERNAME }}
        password: ${{ secrets.REGISTRY_PASSWORD }}
    
    - name: Push images
      run: |
        ./push-images.sh -r ${{ secrets.REGISTRY_URL }}
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                script {
                    sh './build-images.sh -r ${REGISTRY_URL}'
                }
            }
        }
        
        stage('Test') {
            steps {
                script {
                    sh './setup-registry.sh test'
                }
            }
        }
        
        stage('Push') {
            steps {
                script {
                    sh './push-images.sh -r ${REGISTRY_URL}'
                }
            }
        }
        
        stage('Deploy') {
            steps {
                script {
                    sh 'kubectl apply -k kustomize/overlays/prod'
                }
            }
        }
    }
}
```

## Conclusion

This Docker deployment setup provides a robust, secure, and scalable foundation for the ThermoWorks BBQ monitoring application. The multi-stage builds, security practices, and automation scripts ensure consistent deployments across different environments.

For additional support or questions, refer to the main project documentation or open an issue in the project repository.