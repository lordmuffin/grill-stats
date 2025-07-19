#!/bin/bash
#
# Kubernetes Deployment Script
#
# This script deploys the Grill Stats application to a Kubernetes cluster.
# It uses environment variables for configuration and templates from the templates directory.
#
# Usage: ./deploy-kubernetes.sh [--env ENV] [--tag TAG] [--dry-run]
#   --env ENV: Environment to deploy to (dev, staging, prod). Default: dev
#   --tag TAG: Container image tag to deploy. Default: latest
#   --dry-run: Print the generated YAML but don't apply it

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root directory (parent of deployment)
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# Templates directory
TEMPLATES_DIR="${PROJECT_ROOT}/deployment/templates"

# Default values
ENV="dev"
TAG="latest"
DRY_RUN=false

# Process command line arguments
for arg in "$@"; do
  case $arg in
    --env=*)
      ENV="${arg#*=}"
      shift
      ;;
    --tag=*)
      TAG="${arg#*=}"
      shift
      ;;
    --dry-run)
      DRY_RUN=true
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

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
  log "ERROR" "kubectl is not installed. Please install kubectl before running this script."
  exit 1
fi

# Check if envsubst is installed
if ! command -v envsubst &> /dev/null; then
  log "ERROR" "envsubst is not installed. Please install gettext package before running this script."
  exit 1
fi

# Check if base64 is installed
if ! command -v base64 &> /dev/null; then
  log "ERROR" "base64 is not installed. Please install coreutils package before running this script."
  exit 1
fi

# Set environment-specific variables
case $ENV in
  dev)
    NAMESPACE="grill-stats-dev"
    ENVIRONMENT="development"
    DOMAIN="dev.grill-stats.example.com"
    REPLICAS="1"
    CPU_LIMIT="500m"
    MEMORY_LIMIT="512Mi"
    CPU_REQUEST="200m"
    MEMORY_REQUEST="256Mi"
    STORAGE_CLASS="standard"
    DB_NAME="grill_stats"
    INFLUXDB_DATABASE="grill_stats"
    LOG_LEVEL="DEBUG"
    THERMOWORKS_BASE_URL="https://api.thermoworks.com/v1"
    THERMOWORKS_AUTH_URL="https://auth.thermoworks.com"
    THERMOWORKS_REDIRECT_URI="https://dev.grill-stats.example.com/api/auth/thermoworks/callback"
    HOMEASSISTANT_URL="https://dev-ha.example.com"
    ;;
  staging)
    NAMESPACE="grill-stats-staging"
    ENVIRONMENT="staging"
    DOMAIN="staging.grill-stats.example.com"
    REPLICAS="2"
    CPU_LIMIT="1000m"
    MEMORY_LIMIT="1Gi"
    CPU_REQUEST="500m"
    MEMORY_REQUEST="512Mi"
    STORAGE_CLASS="standard"
    DB_NAME="grill_stats"
    INFLUXDB_DATABASE="grill_stats"
    LOG_LEVEL="INFO"
    THERMOWORKS_BASE_URL="https://api.thermoworks.com/v1"
    THERMOWORKS_AUTH_URL="https://auth.thermoworks.com"
    THERMOWORKS_REDIRECT_URI="https://staging.grill-stats.example.com/api/auth/thermoworks/callback"
    HOMEASSISTANT_URL="https://staging-ha.example.com"
    ;;
  prod)
    NAMESPACE="grill-stats-prod"
    ENVIRONMENT="production"
    DOMAIN="grill-stats.example.com"
    REPLICAS="3"
    CPU_LIMIT="2000m"
    MEMORY_LIMIT="2Gi"
    CPU_REQUEST="1000m"
    MEMORY_REQUEST="1Gi"
    STORAGE_CLASS="premium"
    DB_NAME="grill_stats"
    INFLUXDB_DATABASE="grill_stats"
    LOG_LEVEL="INFO"
    THERMOWORKS_BASE_URL="https://api.thermoworks.com/v1"
    THERMOWORKS_AUTH_URL="https://auth.thermoworks.com"
    THERMOWORKS_REDIRECT_URI="https://grill-stats.example.com/api/auth/thermoworks/callback"
    HOMEASSISTANT_URL="https://ha.example.com"
    ;;
  *)
    log "ERROR" "Unknown environment: ${ENV}. Valid values are: dev, staging, prod."
    exit 1
    ;;
esac

# Check if we have an environment-specific secrets file
ENV_SECRETS_FILE="${PROJECT_ROOT}/.env.${ENV}.secrets"
if [ ! -f "${ENV_SECRETS_FILE}" ]; then
  log "WARN" "Secrets file ${ENV_SECRETS_FILE} not found. Creating template..."
  cat > "${ENV_SECRETS_FILE}" << EOF
# ${ENV} Environment Secrets

# ThermoWorks API
THERMOWORKS_API_KEY=your_api_key_here
THERMOWORKS_CLIENT_ID=your_client_id_here
THERMOWORKS_CLIENT_SECRET=your_client_secret_here

# Home Assistant
HOMEASSISTANT_TOKEN=your_token_here

# Database
DB_USER=postgres
DB_PASSWORD=your_db_password_here

# Redis
REDIS_PASSWORD=your_redis_password_here

# InfluxDB
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=your_influxdb_password_here

# Application
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here
EOF
  log "INFO" "Created secrets template for ${ENV} environment. Please update with your actual values."
  log "WARN" "Deployment will fail without proper secrets. Edit ${ENV_SECRETS_FILE} first."
  exit 1
fi

# Source the secrets file
source "${ENV_SECRETS_FILE}"

# Validate that required secrets are set
MISSING_SECRETS=false
for secret in THERMOWORKS_API_KEY THERMOWORKS_CLIENT_ID THERMOWORKS_CLIENT_SECRET HOMEASSISTANT_TOKEN DB_USER DB_PASSWORD REDIS_PASSWORD INFLUXDB_USERNAME INFLUXDB_PASSWORD SECRET_KEY JWT_SECRET; do
  if [ -z "${!secret}" ]; then
    log "ERROR" "Required secret ${secret} is not set in ${ENV_SECRETS_FILE}."
    MISSING_SECRETS=true
  fi
done

if [ "$MISSING_SECRETS" = true ]; then
  log "ERROR" "Some required secrets are missing. Please update ${ENV_SECRETS_FILE} with all required values."
  exit 1
fi

# Convert secrets to base64
THERMOWORKS_API_KEY_BASE64=$(echo -n "${THERMOWORKS_API_KEY}" | base64 -w 0)
THERMOWORKS_CLIENT_ID_BASE64=$(echo -n "${THERMOWORKS_CLIENT_ID}" | base64 -w 0)
THERMOWORKS_CLIENT_SECRET_BASE64=$(echo -n "${THERMOWORKS_CLIENT_SECRET}" | base64 -w 0)
HOMEASSISTANT_TOKEN_BASE64=$(echo -n "${HOMEASSISTANT_TOKEN}" | base64 -w 0)
DB_USER_BASE64=$(echo -n "${DB_USER}" | base64 -w 0)
DB_PASSWORD_BASE64=$(echo -n "${DB_PASSWORD}" | base64 -w 0)
REDIS_PASSWORD_BASE64=$(echo -n "${REDIS_PASSWORD}" | base64 -w 0)
INFLUXDB_USERNAME_BASE64=$(echo -n "${INFLUXDB_USERNAME}" | base64 -w 0)
INFLUXDB_PASSWORD_BASE64=$(echo -n "${INFLUXDB_PASSWORD}" | base64 -w 0)
SECRET_KEY_BASE64=$(echo -n "${SECRET_KEY}" | base64 -w 0)
JWT_SECRET_BASE64=$(echo -n "${JWT_SECRET}" | base64 -w 0)

# Export all variables for envsubst
export NAMESPACE ENVIRONMENT DOMAIN REPLICAS CPU_LIMIT MEMORY_LIMIT CPU_REQUEST MEMORY_REQUEST
export STORAGE_CLASS DB_NAME INFLUXDB_DATABASE LOG_LEVEL TAG
export THERMOWORKS_BASE_URL THERMOWORKS_AUTH_URL THERMOWORKS_REDIRECT_URI HOMEASSISTANT_URL
export THERMOWORKS_API_KEY_BASE64 THERMOWORKS_CLIENT_ID_BASE64 THERMOWORKS_CLIENT_SECRET_BASE64
export HOMEASSISTANT_TOKEN_BASE64 DB_USER_BASE64 DB_PASSWORD_BASE64 REDIS_PASSWORD_BASE64
export INFLUXDB_USERNAME_BASE64 INFLUXDB_PASSWORD_BASE64 SECRET_KEY_BASE64 JWT_SECRET_BASE64

# Create output directory
OUTPUT_DIR="${PROJECT_ROOT}/deployment/output/${ENV}"
mkdir -p "${OUTPUT_DIR}"

# Process templates
log "INFO" "Processing templates for ${ENV} environment..."
for template in "${TEMPLATES_DIR}"/*.yaml; do
  filename=$(basename "${template}")
  output_file="${OUTPUT_DIR}/${filename}"

  log "INFO" "Processing ${filename}..."
  envsubst < "${template}" > "${output_file}"
done

if [ "$DRY_RUN" = true ]; then
  log "INFO" "Dry run requested. Generated YAML files in ${OUTPUT_DIR}:"
  for yaml_file in "${OUTPUT_DIR}"/*.yaml; do
    echo "---"
    echo "# $(basename "${yaml_file}"):"
    cat "${yaml_file}"
    echo
  done
  log "INFO" "Dry run completed. No changes were applied."
  exit 0
fi

# Check if namespace exists
if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
  log "INFO" "Namespace ${NAMESPACE} already exists."
else
  log "INFO" "Creating namespace ${NAMESPACE}..."
  kubectl apply -f "${OUTPUT_DIR}/namespace.yaml"
fi

# Apply all templates in the correct order
log "INFO" "Applying Kubernetes manifests for ${ENV} environment..."

# First apply secrets
log "INFO" "Applying secrets..."
kubectl apply -f "${OUTPUT_DIR}/secrets.yaml"

# Then apply storage resources
log "INFO" "Applying storage resources..."
if [ -f "${OUTPUT_DIR}/redis-pvc.yaml" ]; then
  kubectl apply -f "${OUTPUT_DIR}/redis-pvc.yaml"
fi

# Then apply database deployments
log "INFO" "Deploying databases..."
for resource in postgres influxdb redis; do
  if [ -f "${OUTPUT_DIR}/${resource}-deployment.yaml" ]; then
    kubectl apply -f "${OUTPUT_DIR}/${resource}-deployment.yaml"
  fi
  if [ -f "${OUTPUT_DIR}/${resource}-service.yaml" ]; then
    kubectl apply -f "${OUTPUT_DIR}/${resource}-service.yaml"
  fi
done

# Wait for databases to be ready
log "INFO" "Waiting for databases to be ready..."
for resource in postgres influxdb redis; do
  if kubectl get deployment -n "${NAMESPACE}" "${resource}" &> /dev/null || kubectl get statefulset -n "${NAMESPACE}" "${resource}" &> /dev/null; then
    log "INFO" "Waiting for ${resource} to be ready..."
    if kubectl get deployment -n "${NAMESPACE}" "${resource}" &> /dev/null; then
      kubectl rollout status deployment "${resource}" -n "${NAMESPACE}" --timeout=300s
    elif kubectl get statefulset -n "${NAMESPACE}" "${resource}" &> /dev/null; then
      kubectl rollout status statefulset "${resource}" -n "${NAMESPACE}" --timeout=300s
    fi
  fi
done

# Then apply application deployment
log "INFO" "Deploying application..."
kubectl apply -f "${OUTPUT_DIR}/grill-stats-deployment.yaml"
kubectl apply -f "${OUTPUT_DIR}/grill-stats-service.yaml"

# Finally apply ingress
log "INFO" "Deploying ingress..."
kubectl apply -f "${OUTPUT_DIR}/ingress.yaml"

# Check deployment status
log "INFO" "Checking deployment status..."
kubectl rollout status deployment grill-stats -n "${NAMESPACE}" --timeout=300s

# Final status
log "INFO" "Deployment to ${ENV} environment completed!"
log "INFO" "Application URL: https://${DOMAIN}"

# Instructions for logs and troubleshooting
log "INFO" "To view logs, run: kubectl logs -f -l app=grill-stats -n ${NAMESPACE}"
log "INFO" "To check pod status, run: kubectl get pods -n ${NAMESPACE}"
log "INFO" "To delete the deployment, run: kubectl delete -f ${OUTPUT_DIR}"

exit 0
