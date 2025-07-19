#!/bin/bash
#
# Production Environment Deployment Script
#
# This script deploys the Grill Stats application to the production environment.
# It uses docker-compose with production settings and additional safeguards.
#
# Usage: ./deploy-production.sh [--clean] [--tag TAG] [--force]
#   --clean: Remove all containers and volumes before deploying
#   --tag TAG: Specify a specific image tag to deploy (default: latest)
#   --force: Skip confirmation prompt

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root directory (parent of deployment)
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Process command line arguments
CLEAN=false
TAG="latest"
FORCE=false

for arg in "$@"; do
  case $arg in
    --clean)
      CLEAN=true
      shift
      ;;
    --tag=*)
      TAG="${arg#*=}"
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    *)
      # Unknown option
      ;;
  esac
done

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print with timestamp
log() {
  local level=$1
  local message=$2
  local color=$NC

  case $level in
    INFO)
      color=$GREEN
      ;;
    WARN)
      color=$YELLOW
      ;;
    ERROR)
      color=$RED
      ;;
    *)
      color=$BLUE
      ;;
  esac

  echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${color}${level}${NC}: ${message}"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
  log "ERROR" "Docker is not installed. Please install Docker before running this script."
  exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
  log "ERROR" "docker-compose is not installed. Please install docker-compose before running this script."
  exit 1
fi

# Check if .env.production file exists, create template if not
ENV_FILE="${PROJECT_ROOT}/.env.production"
if [ ! -f "${ENV_FILE}" ]; then
  log "WARN" ".env.production file not found. Creating template..."
  cat > "${ENV_FILE}" << EOF
# Production Environment Configuration

# ThermoWorks API
THERMOWORKS_API_KEY=your_api_key_here
THERMOWORKS_CLIENT_ID=your_client_id_here
THERMOWORKS_CLIENT_SECRET=your_client_secret_here
THERMOWORKS_REDIRECT_URI=https://grill-stats.example.com/api/auth/thermoworks/callback
THERMOWORKS_BASE_URL=https://api.thermoworks.com/v1
THERMOWORKS_AUTH_URL=https://auth.thermoworks.com

# Home Assistant
HOMEASSISTANT_URL=https://your-ha-instance.example.com
HOMEASSISTANT_TOKEN=your_token_here

# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=grill_stats
DB_USER=postgres
DB_PASSWORD=production_secure_password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=production_redis_password

# InfluxDB
INFLUXDB_HOST=influxdb
INFLUXDB_PORT=8086
INFLUXDB_DATABASE=grill_stats
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=production_influx_password

# Application
SECRET_KEY=production_secret_key_replace_this
JWT_SECRET=production_jwt_secret_replace_this
LOG_LEVEL=INFO
FLASK_ENV=production
DEBUG=false
EOF
  log "INFO" "Created .env.production template. Please update with your actual values."
  log "WARN" "Deployment will fail without proper configuration. Edit .env.production first."
  exit 1
fi

# Navigate to project root
cd "${PROJECT_ROOT}"

# Create production compose file if it doesn't exist
PRODUCTION_COMPOSE="${PROJECT_ROOT}/docker-compose.production.yml"
if [ ! -f "${PRODUCTION_COMPOSE}" ]; then
  log "INFO" "Creating production docker-compose configuration..."
  cat > "${PRODUCTION_COMPOSE}" << EOF
version: '3.8'

services:
  # PostgreSQL for device management
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: \${DB_NAME}
      POSTGRES_USER: \${DB_USER}
      POSTGRES_PASSWORD: \${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database-init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${DB_USER} -d \${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    networks:
      - grill-stats-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  # InfluxDB for time-series data
  influxdb:
    image: influxdb:1.8
    environment:
      INFLUXDB_DB: \${INFLUXDB_DATABASE}
      INFLUXDB_USER: \${INFLUXDB_USERNAME}
      INFLUXDB_USER_PASSWORD: \${INFLUXDB_PASSWORD}
      INFLUXDB_ADMIN_USER: \${INFLUXDB_USERNAME}
      INFLUXDB_ADMIN_PASSWORD: \${INFLUXDB_PASSWORD}
    volumes:
      - influxdb_data:/var/lib/influxdb
      - ./database-init/influxdb-init.sh:/docker-entrypoint-initdb.d/init.sh
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8086/ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    networks:
      - grill-stats-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  # Redis for caching and pub/sub
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass \${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "\${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - grill-stats-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  # Main Grill Stats Service
  grill-stats:
    image: lordmuffin/grill-stats:${TAG}
    ports:
      - "5000:5000"
    environment:
      # ThermoWorks API
      - THERMOWORKS_API_KEY=\${THERMOWORKS_API_KEY}
      - THERMOWORKS_CLIENT_ID=\${THERMOWORKS_CLIENT_ID}
      - THERMOWORKS_CLIENT_SECRET=\${THERMOWORKS_CLIENT_SECRET}
      - THERMOWORKS_REDIRECT_URI=\${THERMOWORKS_REDIRECT_URI}
      - THERMOWORKS_BASE_URL=\${THERMOWORKS_BASE_URL}
      - THERMOWORKS_AUTH_URL=\${THERMOWORKS_AUTH_URL}

      # Home Assistant
      - HOMEASSISTANT_URL=\${HOMEASSISTANT_URL}
      - HOMEASSISTANT_TOKEN=\${HOMEASSISTANT_TOKEN}

      # Database
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=\${DB_NAME}
      - DB_USER=\${DB_USER}
      - DB_PASSWORD=\${DB_PASSWORD}

      # Redis
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=\${REDIS_PASSWORD}

      # InfluxDB
      - INFLUXDB_HOST=influxdb
      - INFLUXDB_PORT=8086
      - INFLUXDB_DATABASE=\${INFLUXDB_DATABASE}
      - INFLUXDB_USERNAME=\${INFLUXDB_USERNAME}
      - INFLUXDB_PASSWORD=\${INFLUXDB_PASSWORD}

      # Application
      - SECRET_KEY=\${SECRET_KEY}
      - JWT_SECRET=\${JWT_SECRET}
      - LOG_LEVEL=\${LOG_LEVEL:-INFO}
      - FLASK_ENV=production
      - DEBUG=false
      - PYTHONUNBUFFERED=1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      influxdb:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 45s
    networks:
      - grill-stats-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

volumes:
  postgres_data:
  influxdb_data:
  redis_data:

networks:
  grill-stats-network:
    driver: bridge
EOF
  log "INFO" "Created production docker-compose configuration."
fi

# Ask for confirmation before deploying to production (unless --force is used)
if [ "$FORCE" = false ]; then
  log "WARN" "You are about to deploy to PRODUCTION environment with tag: ${TAG}"
  log "WARN" "This will affect live services. Are you sure you want to continue? (y/n)"
  read -r response
  if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    log "INFO" "Deployment cancelled."
    exit 0
  fi
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
  log "INFO" "Cleaning up existing containers and volumes..."
  docker-compose -f "${PRODUCTION_COMPOSE}" down -v
fi

# Pull latest images
log "INFO" "Pulling latest images for tag: ${TAG}..."
docker-compose -f "${PRODUCTION_COMPOSE}" pull

# Deploy with docker-compose
log "INFO" "Deploying to production environment..."
docker-compose -f "${PRODUCTION_COMPOSE}" --env-file "${ENV_FILE}" up -d

# Check if deployment was successful
if [ $? -eq 0 ]; then
  log "INFO" "Deployment to production environment completed successfully!"
else
  log "ERROR" "Deployment to production environment failed."
  exit 1
fi

# Check if containers are healthy
log "INFO" "Checking container health..."
sleep 10  # Give containers time to start

CONTAINERS=$(docker-compose -f "${PRODUCTION_COMPOSE}" ps -q)
UNHEALTHY=false

for container in $CONTAINERS; do
  status=$(docker inspect --format='{{.State.Status}}' $container 2>/dev/null)

  if [ "$status" != "running" ]; then
    log "ERROR" "Container $(docker inspect --format='{{.Name}}' $container) is not running (status: $status)"
    UNHEALTHY=true
  fi
done

if [ "$UNHEALTHY" = true ]; then
  log "ERROR" "Some containers are not healthy. Check docker-compose logs for more details."
  log "INFO" "Run 'docker-compose -f ${PRODUCTION_COMPOSE} logs' to see container logs."
  exit 1
else
  log "INFO" "All containers are running."
fi

# Test basic health endpoint
log "INFO" "Testing health endpoint..."
if command -v curl &> /dev/null; then
  response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
  if [ "$response" = "200" ]; then
    log "INFO" "Health check passed."
  else
    log "WARN" "Health check returned status: ${response}"
  fi
else
  log "WARN" "curl not found, skipping health check."
fi

# Instructions for logs and shutdown
log "INFO" "To view logs, run: docker-compose -f ${PRODUCTION_COMPOSE} logs -f"
log "INFO" "To stop the environment, run: docker-compose -f ${PRODUCTION_COMPOSE} down"
log "INFO" "Production environment is available at: http://localhost:5000"

exit 0
