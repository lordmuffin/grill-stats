#!/bin/bash
#
# Development Environment Deployment Script
#
# This script deploys the Grill Stats application to the development environment.
# It uses docker-compose to set up a local development environment with all required services.
#
# Usage: ./deploy-dev.sh [--build] [--clean]
#   --build: Force rebuild of all containers
#   --clean: Remove all containers and volumes before deploying

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root directory (parent of deployment)
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Process command line arguments
BUILD=false
CLEAN=false

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

# Check if .env file exists, create from example if not
ENV_FILE="${PROJECT_ROOT}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  if [ -f "${PROJECT_ROOT}/.env.example" ]; then
    log "WARN" ".env file not found. Creating from .env.example..."
    cp "${PROJECT_ROOT}/.env.example" "${ENV_FILE}"
    log "INFO" "Created .env file from example. Please update with your actual values."
  else
    log "ERROR" "Neither .env nor .env.example files found. Please create a .env file with required environment variables."
    exit 1
  fi
fi

# Navigate to project root
cd "${PROJECT_ROOT}"

# Clean if requested
if [ "$CLEAN" = true ]; then
  log "INFO" "Cleaning up existing containers and volumes..."
  docker-compose down -v
  docker-compose -f docker-compose.dev.yml down -v
fi

# Set environment to development
export FLASK_ENV=development
export DEBUG=true

# Deploy with docker-compose
if [ "$BUILD" = true ]; then
  log "INFO" "Building and deploying to development environment with fresh builds..."
  docker-compose -f docker-compose.dev.yml up -d --build
else
  log "INFO" "Deploying to development environment..."
  docker-compose -f docker-compose.dev.yml up -d
fi

# Check if deployment was successful
if [ $? -eq 0 ]; then
  log "INFO" "Deployment to development environment completed successfully!"
  log "INFO" "The following services are now available:"
  log "INFO" "- Main API: http://localhost:5000"
  log "INFO" "- Auth Service: http://localhost:8082"
  log "INFO" "- Device Service: http://localhost:8080"
  log "INFO" "- Web UI: http://localhost:3000"
  log "INFO" "- PostgreSQL: localhost:5432"
  log "INFO" "- Redis: localhost:6379"
else
  log "ERROR" "Deployment to development environment failed."
  exit 1
fi

# Check if containers are healthy
log "INFO" "Checking container health..."
sleep 5  # Give containers time to start

CONTAINERS=$(docker-compose -f docker-compose.dev.yml ps -q)
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
  log "INFO" "Run 'docker-compose -f docker-compose.dev.yml logs' to see container logs."
  exit 1
else
  log "INFO" "All containers are running."
fi

# Instructions for logs and shutdown
log "INFO" "To view logs, run: docker-compose -f docker-compose.dev.yml logs -f"
log "INFO" "To stop the environment, run: docker-compose -f docker-compose.dev.yml down"

exit 0
