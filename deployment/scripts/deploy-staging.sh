#!/bin/bash
#
# Staging Environment Deployment Script
#
# This script deploys the Grill Stats application to the staging environment.
# It uses docker-compose with production settings but in a staging context.
#
# Usage: ./deploy-staging.sh [--build] [--clean] [--tag TAG]
#   --build: Force rebuild of all containers
#   --clean: Remove all containers and volumes before deploying
#   --tag TAG: Specify a specific image tag to deploy (default: staging)

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root directory (parent of deployment)
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Process command line arguments
BUILD=false
CLEAN=false
TAG="staging"

for arg in "$@"; do
  case $arg in
    --build)
      BUILD=true
      shift
      ;;
    --clean)
      CLEAN=true
      shift
      ;;
    --tag=*)
      TAG="${arg#*=}"
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

# Check if .env.staging file exists, create template if not
ENV_FILE="${PROJECT_ROOT}/.env.staging"
if [ ! -f "${ENV_FILE}" ]; then
  log "WARN" ".env.staging file not found. Creating template..."
  cat > "${ENV_FILE}" << EOF
# Staging Environment Configuration

# ThermoWorks API
THERMOWORKS_API_KEY=your_api_key_here
THERMOWORKS_CLIENT_ID=your_client_id_here
THERMOWORKS_CLIENT_SECRET=your_client_secret_here
THERMOWORKS_REDIRECT_URI=https://staging.grill-stats.example.com/api/auth/thermoworks/callback
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
DB_PASSWORD=staging_secure_password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=staging_redis_password

# InfluxDB
INFLUXDB_HOST=influxdb
INFLUXDB_PORT=8086
INFLUXDB_DATABASE=grill_stats
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=staging_influx_password

# Application
SECRET_KEY=staging_secret_key_replace_this
JWT_SECRET=staging_jwt_secret_replace_this
LOG_LEVEL=INFO
FLASK_ENV=production
DEBUG=false
EOF
  log "INFO" "Created .env.staging template. Please update with your actual values."
  log "WARN" "Deployment will fail without proper configuration. Edit .env.staging first."
  exit 1
fi

# Navigate to project root
cd "${PROJECT_ROOT}"

# Create staging compose file if it doesn't exist
STAGING_COMPOSE="${PROJECT_ROOT}/docker-compose.staging.yml"
if [ ! -f "${STAGING_COMPOSE}" ]; then
  log "INFO" "Creating staging docker-compose configuration..."
  cp "${PROJECT_ROOT}/docker-compose.yml" "${STAGING_COMPOSE}"

  # Update the compose file for staging environment
  # This is a simple sed replacement; for more complex changes, consider using a template
  sed -i 's/latest/'"${TAG}"'/g' "${STAGING_COMPOSE}"
  sed -i 's/development/staging/g' "${STAGING_COMPOSE}"

  log "INFO" "Created staging docker-compose configuration."
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
  log "INFO" "Cleaning up existing containers and volumes..."
  docker-compose -f "${STAGING_COMPOSE}" down -v
fi

# Set environment to staging
export FLASK_ENV=production  # Use production mode but in staging environment
export DEBUG=false

# Pull latest images
log "INFO" "Pulling latest images for tag: ${TAG}..."
docker-compose -f "${STAGING_COMPOSE}" pull

# Deploy with docker-compose
if [ "$BUILD" = true ]; then
  log "INFO" "Building and deploying to staging environment..."
  docker-compose -f "${STAGING_COMPOSE}" up -d --build
else
  log "INFO" "Deploying to staging environment..."
  docker-compose -f "${STAGING_COMPOSE}" up -d
fi

# Check if deployment was successful
if [ $? -eq 0 ]; then
  log "INFO" "Deployment to staging environment completed successfully!"
else
  log "ERROR" "Deployment to staging environment failed."
  exit 1
fi

# Check if containers are healthy
log "INFO" "Checking container health..."
sleep 10  # Give containers time to start

CONTAINERS=$(docker-compose -f "${STAGING_COMPOSE}" ps -q)
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
  log "INFO" "Run 'docker-compose -f ${STAGING_COMPOSE} logs' to see container logs."
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
log "INFO" "To view logs, run: docker-compose -f ${STAGING_COMPOSE} logs -f"
log "INFO" "To stop the environment, run: docker-compose -f ${STAGING_COMPOSE} down"
log "INFO" "Staging environment is available at: http://localhost:5000"

exit 0
