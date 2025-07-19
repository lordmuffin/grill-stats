#!/bin/bash

# setup-ci-cd-secrets.sh
# Setup and manage CI/CD secrets for Gitea workflows
# This script helps to generate and set up required secrets for the CI/CD pipeline

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SECRETS_FILE="${ROOT_DIR}/.secrets.env"
REQUIRED_TOOLS=("curl" "jq" "base64")

# Default values
DRY_RUN=false
GITEA_URL="${GITEA_URL:-http://localhost:3000}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
REPOSITORY="${REPOSITORY:-}"
FORCE=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Setup and manage CI/CD secrets for Gitea workflows.

OPTIONS:
  -h, --help              Show this help message
  --dry-run               Show what would be done without executing
  --force                 Force recreation of existing secrets
  --gitea-url URL         Gitea server URL (default: http://localhost:3000)
  --gitea-token TOKEN     Gitea API token
  --repository REPO       Repository name (format: owner/repo)
  -v, --verbose           Enable verbose output

Examples:
  $0 --gitea-url https://gitea.example.com --gitea-token TOKEN --repository owner/repo
  $0 --dry-run --repository owner/repo
EOF
}

# Check if required tools are installed
check_prerequisites() {
    log_info "Checking prerequisites..."

    for tool in "${REQUIRED_TOOLS[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done

    # Check required parameters
    if [[ -z "$GITEA_TOKEN" ]]; then
        log_error "Gitea API token is required"
        log_info "Use --gitea-token to provide a token"
        exit 1
    fi

    if [[ -z "$REPOSITORY" ]]; then
        log_error "Repository name is required"
        log_info "Use --repository to provide a repository name (format: owner/repo)"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Validate if we can access Gitea API
validate_gitea_access() {
    log_info "Validating Gitea API access..."

    local response
    response=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" "${GITEA_URL}/api/v1/user")

    if echo "$response" | jq -e '.id' > /dev/null; then
        local username
        username=$(echo "$response" | jq -r '.username')
        log_success "Successfully authenticated as ${username}"
    else
        log_error "Failed to authenticate with Gitea API"
        log_error "Response: ${response}"
        exit 1
    fi
}

# List existing secrets
list_secrets() {
    log_info "Listing existing secrets for ${REPOSITORY}..."

    local response
    response=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets")

    if echo "$response" | jq -e 'length' > /dev/null; then
        local count
        count=$(echo "$response" | jq 'length')
        log_info "Found ${count} existing secrets"

        if [[ $count -gt 0 ]]; then
            echo "$response" | jq -r '.[] | .name'
        fi
    else
        log_warning "Failed to list secrets or no secrets found"
        log_error "Response: ${response}"
    fi
}

# Create or update a secret
set_secret() {
    local name="$1"
    local value="$2"
    local description="${3:-}"

    log_info "Setting secret: ${name}..."

    # Check if secret already exists
    local existing_secret
    existing_secret=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets/${name}")

    if echo "$existing_secret" | jq -e '.name' > /dev/null && [[ "$FORCE" == "false" ]]; then
        log_warning "Secret already exists: ${name} (use --force to update)"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would set secret: ${name}"
        return 0
    fi

    # Create or update secret
    local response
    response=$(curl -s -X PUT -H "Authorization: token ${GITEA_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${name}\",\"data\":\"${value}\",\"description\":\"${description}\"}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets/${name}")

    if echo "$response" | jq -e '.name' > /dev/null; then
        log_success "Secret set successfully: ${name}"
    else
        log_error "Failed to set secret: ${name}"
        log_error "Response: ${response}"
        return 1
    fi
}

# Delete a secret
delete_secret() {
    local name="$1"

    log_info "Deleting secret: ${name}..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would delete secret: ${name}"
        return 0
    fi

    local response
    response=$(curl -s -X DELETE -H "Authorization: token ${GITEA_TOKEN}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets/${name}")

    if [[ -z "$response" || "$response" == "{}" ]]; then
        log_success "Secret deleted successfully: ${name}"
    else
        log_error "Failed to delete secret: ${name}"
        log_error "Response: ${response}"
        return 1
    fi
}

# Generate Docker Hub authentication token
generate_docker_auth() {
    log_info "Generating Docker Hub authentication token..."

    # Prompt for Docker Hub credentials
    read -p "Docker Hub username: " docker_username
    read -sp "Docker Hub password/token: " docker_password
    echo ""

    if [[ -z "$docker_username" || -z "$docker_password" ]]; then
        log_error "Docker Hub username and password/token are required"
        return 1
    fi

    # Generate auth token
    local auth_token
    auth_token=$(echo -n "${docker_username}:${docker_password}" | base64)

    log_success "Generated Docker Hub authentication token"

    # Set the secret
    set_secret "DOCKER_AUTH" "$auth_token" "Docker Hub authentication token (base64 encoded)"
}

# Generate ThermoWorks API key
generate_thermoworks_key() {
    log_info "Setting up ThermoWorks API key..."

    # Prompt for ThermoWorks API key
    read -p "ThermoWorks API key: " thermoworks_key

    if [[ -z "$thermoworks_key" ]]; then
        log_error "ThermoWorks API key is required"
        return 1
    fi

    # Set the secret
    set_secret "THERMOWORKS_API_KEY" "$thermoworks_key" "ThermoWorks API key for testing"
}

# Generate Home Assistant token
generate_homeassistant_token() {
    log_info "Setting up Home Assistant token..."

    # Prompt for Home Assistant token
    read -p "Home Assistant URL: " homeassistant_url
    read -sp "Home Assistant token: " homeassistant_token
    echo ""

    if [[ -z "$homeassistant_url" || -z "$homeassistant_token" ]]; then
        log_error "Home Assistant URL and token are required"
        return 1
    fi

    # Set the secrets
    set_secret "HOMEASSISTANT_URL" "$homeassistant_url" "Home Assistant URL for testing"
    set_secret "HOMEASSISTANT_TOKEN" "$homeassistant_token" "Home Assistant token for testing"
}

# Generate PostgreSQL credentials
generate_postgres_credentials() {
    log_info "Setting up PostgreSQL credentials..."

    # Prompt for PostgreSQL credentials
    read -p "PostgreSQL host: " postgres_host
    read -p "PostgreSQL port (default: 5432): " postgres_port
    postgres_port=${postgres_port:-5432}
    read -p "PostgreSQL database (default: grill_stats): " postgres_db
    postgres_db=${postgres_db:-grill_stats}
    read -p "PostgreSQL username: " postgres_user
    read -sp "PostgreSQL password: " postgres_password
    echo ""

    if [[ -z "$postgres_host" || -z "$postgres_user" || -z "$postgres_password" ]]; then
        log_error "PostgreSQL host, username, and password are required"
        return 1
    fi

    # Generate connection string
    local postgres_url="postgresql://${postgres_user}:${postgres_password}@${postgres_host}:${postgres_port}/${postgres_db}"

    # Set the secrets
    set_secret "DB_HOST" "$postgres_host" "PostgreSQL host for testing"
    set_secret "DB_PORT" "$postgres_port" "PostgreSQL port for testing"
    set_secret "DB_NAME" "$postgres_db" "PostgreSQL database name for testing"
    set_secret "DB_USERNAME" "$postgres_user" "PostgreSQL username for testing"
    set_secret "DB_PASSWORD" "$postgres_password" "PostgreSQL password for testing"
    set_secret "DATABASE_URL" "$postgres_url" "PostgreSQL connection URL for testing"
}

# Generate application secrets
generate_app_secrets() {
    log_info "Setting up application secrets..."

    # Generate random secret key
    local secret_key
    secret_key=$(openssl rand -hex 16)

    # Set the secrets
    set_secret "SECRET_KEY" "$secret_key" "Application secret key for testing"
}

# Generate InfluxDB credentials
generate_influxdb_credentials() {
    log_info "Setting up InfluxDB credentials..."

    # Prompt for InfluxDB credentials
    read -p "InfluxDB host: " influxdb_host
    read -p "InfluxDB port (default: 8086): " influxdb_port
    influxdb_port=${influxdb_port:-8086}
    read -p "InfluxDB database (default: grill_stats): " influxdb_db
    influxdb_db=${influxdb_db:-grill_stats}
    read -p "InfluxDB username: " influxdb_user
    read -sp "InfluxDB password: " influxdb_password
    echo ""
    read -sp "InfluxDB token: " influxdb_token
    echo ""

    if [[ -z "$influxdb_host" ]]; then
        log_error "InfluxDB host is required"
        return 1
    fi

    # Set the secrets
    set_secret "INFLUXDB_HOST" "$influxdb_host" "InfluxDB host for testing"
    set_secret "INFLUXDB_PORT" "$influxdb_port" "InfluxDB port for testing"
    set_secret "INFLUXDB_DATABASE" "$influxdb_db" "InfluxDB database name for testing"

    if [[ -n "$influxdb_user" && -n "$influxdb_password" ]]; then
        set_secret "INFLUXDB_USERNAME" "$influxdb_user" "InfluxDB username for testing"
        set_secret "INFLUXDB_PASSWORD" "$influxdb_password" "InfluxDB password for testing"
    fi

    if [[ -n "$influxdb_token" ]]; then
        set_secret "INFLUXDB_TOKEN" "$influxdb_token" "InfluxDB token for testing"
    fi
}

# Generate Redis credentials
generate_redis_credentials() {
    log_info "Setting up Redis credentials..."

    # Prompt for Redis credentials
    read -p "Redis host: " redis_host
    read -p "Redis port (default: 6379): " redis_port
    redis_port=${redis_port:-6379}
    read -sp "Redis password (optional): " redis_password
    echo ""

    if [[ -z "$redis_host" ]]; then
        log_error "Redis host is required"
        return 1
    fi

    # Set the secrets
    set_secret "REDIS_HOST" "$redis_host" "Redis host for testing"
    set_secret "REDIS_PORT" "$redis_port" "Redis port for testing"

    if [[ -n "$redis_password" ]]; then
        set_secret "REDIS_PASSWORD" "$redis_password" "Redis password for testing"
    fi
}

# Save secrets to a local file for reference
save_secrets_to_file() {
    log_info "Saving secrets to file for reference..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would save secrets to file: ${SECRETS_FILE}"
        return 0
    fi

    # Create secrets file with header
    cat > "${SECRETS_FILE}" << EOF
# Grill Stats CI/CD Secrets
# Generated on $(date)
# WARNING: This file contains sensitive information and should not be committed to version control
# Use this file as a reference for setting up Gitea secrets

EOF

    # Get all secrets
    local secrets
    secrets=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets")

    if echo "$secrets" | jq -e 'length' > /dev/null; then
        local count
        count=$(echo "$secrets" | jq 'length')

        if [[ $count -gt 0 ]]; then
            for secret_name in $(echo "$secrets" | jq -r '.[] | .name'); do
                echo "${secret_name}=********" >> "${SECRETS_FILE}"
            done

            log_success "Saved ${count} secrets to ${SECRETS_FILE}"
            chmod 600 "${SECRETS_FILE}"
            log_info "File permissions set to 600 (owner read/write only)"
        fi
    fi
}

# Setup CI/CD secrets
setup_ci_cd_secrets() {
    log_info "Setting up CI/CD secrets..."

    # First list existing secrets
    list_secrets

    # Docker Hub authentication
    generate_docker_auth

    # ThermoWorks API key
    generate_thermoworks_key

    # Home Assistant token
    generate_homeassistant_token

    # PostgreSQL credentials
    generate_postgres_credentials

    # Application secrets
    generate_app_secrets

    # InfluxDB credentials
    generate_influxdb_credentials

    # Redis credentials
    generate_redis_credentials

    # Save secrets to file for reference
    save_secrets_to_file

    log_success "CI/CD secrets setup completed"
}

# Main function
main() {
    log_info "Starting Grill Stats CI/CD secrets setup"

    # Check prerequisites
    check_prerequisites

    # Validate Gitea access
    validate_gitea_access

    # Setup CI/CD secrets
    setup_ci_cd_secrets

    log_success "All tasks completed successfully"
    log_info "Next steps:"
    log_info "1. Update CI/CD pipeline to use the secrets"
    log_info "2. Update documentation"
    log_info "3. Test the pipeline with the new secrets"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --gitea-url)
            GITEA_URL="$2"
            shift 2
            ;;
        --gitea-token)
            GITEA_TOKEN="$2"
            shift 2
            ;;
        --repository)
            REPOSITORY="$2"
            shift 2
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Run main function
main

