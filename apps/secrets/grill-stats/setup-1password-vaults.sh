#!/bin/bash

# Grill Stats 1Password Vault Setup Script
# This script helps initialize the 1Password vaults with the required items

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULTS=("grill-stats" "grill-stats-dev" "grill-stats-prod")
REQUIRED_TOOLS=("op" "jq")

# Default values
DRY_RUN=false
FORCE=false
VAULT_NAME=""

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
Usage: $0 [OPTIONS] [VAULT_NAME]

Initialize 1Password vaults with required items for Grill Stats.

VAULT_NAME:
  grill-stats         Base vault for common secrets
  grill-stats-dev     Development environment vault
  grill-stats-prod    Production environment vault
  all                 Setup all vaults (default)

OPTIONS:
  -h, --help          Show this help message
  --dry-run           Show what would be created without executing
  --force             Force creation even if items exist
  -v, --verbose       Enable verbose output

Examples:
  $0                  Setup all vaults
  $0 grill-stats-dev  Setup development vault only
  $0 --dry-run        Show what would be created
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

    # Check if 1Password CLI is authenticated
    if ! op account get &> /dev/null; then
        log_error "1Password CLI is not authenticated. Please run 'op signin'"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Create vault if it doesn't exist
create_vault() {
    local vault_name="$1"
    local description="$2"

    log_info "Creating vault: $vault_name"

    if op vault get "$vault_name" &> /dev/null; then
        log_info "Vault already exists: $vault_name"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create vault: $vault_name"
        return 0
    fi

    if op vault create "$vault_name" --description "$description"; then
        log_success "Created vault: $vault_name"
    else
        log_error "Failed to create vault: $vault_name"
        return 1
    fi
}

# Create secret item in vault
create_secret_item() {
    local vault_name="$1"
    local item_name="$2"
    local category="$3"
    shift 3
    local fields=("$@")

    log_info "Creating secret item: $item_name in vault: $vault_name"

    # Check if item already exists
    if op item get "$item_name" --vault "$vault_name" &> /dev/null; then
        if [[ "$FORCE" == "false" ]]; then
            log_warning "Item already exists: $item_name (use --force to overwrite)"
            return 0
        else
            log_warning "Item exists, will overwrite: $item_name"
        fi
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create item: $item_name with fields: ${fields[*]}"
        return 0
    fi

    # Build op create command
    local cmd="op item create"
    cmd+=" --vault '$vault_name'"
    cmd+=" --category '$category'"
    cmd+=" --title '$item_name'"

    # Add fields
    for field in "${fields[@]}"; do
        cmd+=" '$field'"
    done

    if eval "$cmd" &> /dev/null; then
        log_success "Created item: $item_name"
    else
        log_error "Failed to create item: $item_name"
        return 1
    fi
}

# Setup base vault (grill-stats)
setup_base_vault() {
    local vault_name="grill-stats"

    log_info "Setting up base vault: $vault_name"

    # Create vault
    create_vault "$vault_name" "Grill Stats base secrets for common services"

    # Auth service secrets
    create_secret_item "$vault_name" "auth-service-secrets" "Secure Note" \
        "jwt-secret=password:" \
        "jwt-algorithm=text:HS256" \
        "session-secret=password:" \
        "database-url=text:" \
        "database-host=text:" \
        "database-port=text:5432" \
        "database-name=text:grill_stats" \
        "database-user=text:" \
        "database-password=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-password=password:" \
        "redis-url=text:" \
        "thermoworks-client-id=text:" \
        "thermoworks-client-secret=password:" \
        "thermoworks-base-url=text:https://api.thermoworks.com" \
        "thermoworks-auth-url=text:https://auth.thermoworks.com"

    # Device service secrets
    create_secret_item "$vault_name" "device-service-secrets" "Secure Note" \
        "jwt-secret=password:" \
        "database-url=text:" \
        "database-host=text:" \
        "database-port=text:5432" \
        "database-name=text:grill_stats" \
        "database-user=text:" \
        "database-password=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-password=password:" \
        "thermoworks-client-id=text:" \
        "thermoworks-client-secret=password:" \
        "oauth2-client-id=text:" \
        "oauth2-client-secret=password:" \
        "homeassistant-url=text:" \
        "homeassistant-token=password:"

    # Temperature service secrets
    create_secret_item "$vault_name" "temperature-service-secrets" "Secure Note" \
        "jwt-secret=password:" \
        "influxdb-url=text:" \
        "influxdb-token=password:" \
        "influxdb-org=text:" \
        "influxdb-bucket=text:" \
        "influxdb-username=text:" \
        "influxdb-password=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-password=password:" \
        "thermoworks-client-id=text:" \
        "thermoworks-client-secret=password:"

    # Historical data service secrets
    create_secret_item "$vault_name" "historical-data-service-secrets" "Secure Note" \
        "jwt-secret=password:" \
        "timescale-url=text:" \
        "timescale-host=text:" \
        "timescale-port=text:5432" \
        "timescale-database=text:grill_stats_historical" \
        "timescale-username=text:" \
        "timescale-password=password:" \
        "influxdb-url=text:" \
        "influxdb-token=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-password=password:"

    # Encryption service secrets
    create_secret_item "$vault_name" "encryption-service-secrets" "Secure Note" \
        "jwt-secret=password:" \
        "vault-url=text:" \
        "vault-token=password:" \
        "vault-role-id=text:" \
        "vault-secret-id=password:" \
        "vault-namespace=text:" \
        "vault-mount-path=text:transit" \
        "vault-key-name=text:grill-stats-encryption-key" \
        "database-url=text:" \
        "database-host=text:" \
        "database-port=text:5432" \
        "database-name=text:grill_stats_audit" \
        "database-user=text:" \
        "database-password=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-password=password:"

    # Web UI secrets
    create_secret_item "$vault_name" "web-ui-secrets" "Secure Note" \
        "api-base-url=text:" \
        "auth-service-url=text:" \
        "device-service-url=text:" \
        "temperature-service-url=text:" \
        "historical-service-url=text:" \
        "jwt-secret=password:" \
        "websocket-url=text:" \
        "cors-origins=text:"

    # Database secrets
    create_secret_item "$vault_name" "postgresql-secrets" "Database" \
        "postgres-password=password:" \
        "postgres-user=text:postgres" \
        "postgres-database=text:postgres" \
        "database-name=text:grill_stats" \
        "database-user=text:" \
        "database-password=password:" \
        "auth-service-user=text:" \
        "auth-service-password=password:" \
        "device-service-user=text:" \
        "device-service-password=password:" \
        "readonly-user=text:" \
        "readonly-password=password:"

    create_secret_item "$vault_name" "influxdb-secrets" "Database" \
        "influxdb-admin-user=text:" \
        "influxdb-admin-password=password:" \
        "influxdb-admin-token=password:" \
        "influxdb-org=text:grill-stats" \
        "influxdb-bucket=text:temperature-data" \
        "influxdb-user=text:" \
        "influxdb-password=password:" \
        "influxdb-token=password:" \
        "temperature-service-token=password:" \
        "historical-service-token=password:" \
        "web-ui-token=password:"

    create_secret_item "$vault_name" "redis-secrets" "Database" \
        "redis-password=password:" \
        "redis-host=text:" \
        "redis-port=text:6379" \
        "redis-url=text:" \
        "redis-sentinel-password=password:" \
        "redis-sentinel-service-name=text:grill-stats-redis"

    create_secret_item "$vault_name" "timescaledb-secrets" "Database" \
        "timescale-admin-user=text:" \
        "timescale-admin-password=password:" \
        "timescale-database=text:grill_stats_historical" \
        "timescale-user=text:" \
        "timescale-password=password:" \
        "timescale-readonly-user=text:" \
        "timescale-readonly-password=password:" \
        "timescale-backup-user=text:" \
        "timescale-backup-password=password:" \
        "timescale-host=text:" \
        "timescale-port=text:5432"

    log_success "Base vault setup completed: $vault_name"
}

# Setup development vault (grill-stats-dev)
setup_dev_vault() {
    local vault_name="grill-stats-dev"

    log_info "Setting up development vault: $vault_name"

    # Create vault
    create_vault "$vault_name" "Grill Stats development environment secrets"

    # Development environment secrets
    create_secret_item "$vault_name" "dev-lab-environment-secrets" "Secure Note" \
        "environment=text:dev-lab" \
        "debug-enabled=text:true" \
        "log-level=text:DEBUG" \
        "database-url=text:" \
        "database-host=text:postgresql-dev.grill-stats-dev.svc.cluster.local" \
        "database-port=text:5432" \
        "database-name=text:grill_stats_dev" \
        "database-user=text:" \
        "database-password=password:" \
        "influxdb-url=text:http://influxdb-dev.grill-stats-dev.svc.cluster.local:8086" \
        "influxdb-token=password:" \
        "influxdb-org=text:grill-stats-dev" \
        "influxdb-bucket=text:temperature-data-dev" \
        "redis-host=text:redis-dev.grill-stats-dev.svc.cluster.local" \
        "redis-port=text:6379" \
        "redis-password=password:" \
        "thermoworks-client-id=text:" \
        "thermoworks-client-secret=password:" \
        "thermoworks-base-url=text:https://sandbox-api.thermoworks.com" \
        "thermoworks-auth-url=text:https://sandbox-auth.thermoworks.com" \
        "jwt-secret=password:" \
        "jwt-expiration=text:7200" \
        "homeassistant-url=text:" \
        "homeassistant-token=password:" \
        "vault-url=text:http://vault-dev.grill-stats-dev.svc.cluster.local:8200" \
        "vault-token=password:" \
        "vault-namespace=text:grill-stats-dev"

    # Development database users
    create_secret_item "$vault_name" "dev-lab-database-users" "Database" \
        "postgres-admin-user=text:postgres" \
        "postgres-admin-password=password:" \
        "auth-service-user=text:auth_service_dev" \
        "auth-service-password=password:" \
        "device-service-user=text:device_service_dev" \
        "device-service-password=password:" \
        "encryption-service-user=text:encryption_service_dev" \
        "encryption-service-password=password:" \
        "historical-service-user=text:historical_service_dev" \
        "historical-service-password=password:" \
        "readonly-user=text:readonly_dev" \
        "readonly-password=password:" \
        "influxdb-admin-user=text:admin" \
        "influxdb-admin-password=password:" \
        "influxdb-admin-token=password:" \
        "temperature-service-token=password:" \
        "historical-service-token=password:" \
        "web-ui-token=password:" \
        "redis-password=password:" \
        "timescale-admin-user=text:timescale_admin" \
        "timescale-admin-password=password:" \
        "timescale-user=text:timescale_dev" \
        "timescale-password=password:"

    # Copy base service secrets for dev (with dev-specific modifications)
    # This would include all the service secrets but with dev-specific values

    log_success "Development vault setup completed: $vault_name"
}

# Setup production vault (grill-stats-prod)
setup_prod_vault() {
    local vault_name="grill-stats-prod"

    log_info "Setting up production vault: $vault_name"

    # Create vault
    create_vault "$vault_name" "Grill Stats production environment secrets"

    # Production environment secrets
    create_secret_item "$vault_name" "prod-lab-environment-secrets" "Secure Note" \
        "environment=text:prod-lab" \
        "debug-enabled=text:false" \
        "log-level=text:INFO" \
        "database-url=text:" \
        "database-host=text:postgresql-prod.grill-stats-prod.svc.cluster.local" \
        "database-port=text:5432" \
        "database-name=text:grill_stats_prod" \
        "database-user=text:" \
        "database-password=password:" \
        "influxdb-url=text:http://influxdb-prod.grill-stats-prod.svc.cluster.local:8086" \
        "influxdb-token=password:" \
        "influxdb-org=text:grill-stats-prod" \
        "influxdb-bucket=text:temperature-data-prod" \
        "redis-host=text:redis-prod.grill-stats-prod.svc.cluster.local" \
        "redis-port=text:6379" \
        "redis-password=password:" \
        "thermoworks-client-id=text:" \
        "thermoworks-client-secret=password:" \
        "thermoworks-base-url=text:https://api.thermoworks.com" \
        "thermoworks-auth-url=text:https://auth.thermoworks.com" \
        "jwt-secret=password:" \
        "jwt-expiration=text:3600" \
        "homeassistant-url=text:" \
        "homeassistant-token=password:" \
        "vault-url=text:http://vault-prod.grill-stats-prod.svc.cluster.local:8200" \
        "vault-token=password:" \
        "vault-namespace=text:grill-stats-prod" \
        "security-hardening-enabled=text:true" \
        "ssl-enabled=text:true" \
        "backup-enabled=text:true" \
        "monitoring-enabled=text:true" \
        "alerting-enabled=text:true"

    # Production database users
    create_secret_item "$vault_name" "prod-lab-database-users" "Database" \
        "postgres-admin-user=text:postgres" \
        "postgres-admin-password=password:" \
        "auth-service-user=text:auth_service_prod" \
        "auth-service-password=password:" \
        "device-service-user=text:device_service_prod" \
        "device-service-password=password:" \
        "encryption-service-user=text:encryption_service_prod" \
        "encryption-service-password=password:" \
        "historical-service-user=text:historical_service_prod" \
        "historical-service-password=password:" \
        "readonly-user=text:readonly_prod" \
        "readonly-password=password:" \
        "backup-user=text:backup_prod" \
        "backup-password=password:" \
        "influxdb-admin-user=text:admin" \
        "influxdb-admin-password=password:" \
        "influxdb-admin-token=password:" \
        "temperature-service-token=password:" \
        "historical-service-token=password:" \
        "web-ui-token=password:" \
        "redis-password=password:" \
        "timescale-admin-user=text:timescale_admin" \
        "timescale-admin-password=password:" \
        "timescale-user=text:timescale_prod" \
        "timescale-password=password:" \
        "timescale-backup-user=text:timescale_backup" \
        "timescale-backup-password=password:"

    # Production security secrets
    create_secret_item "$vault_name" "prod-lab-security-secrets" "Secure Note" \
        "tls-cert=text:" \
        "tls-key=password:" \
        "tls-ca=text:" \
        "external-api-key=password:" \
        "webhook-secret=password:" \
        "encryption-key=password:" \
        "signing-key=password:" \
        "security-token=password:" \
        "csrf-token=password:" \
        "monitoring-api-key=password:" \
        "alerting-webhook-key=password:"

    log_success "Production vault setup completed: $vault_name"
}

# Main setup function
main() {
    local exit_code=0

    log_info "Starting Grill Stats 1Password vault setup"

    # Check prerequisites
    check_prerequisites

    # Setup vaults based on selection
    if [[ -n "$VAULT_NAME" ]]; then
        case "$VAULT_NAME" in
            "grill-stats")
                setup_base_vault || exit_code=1
                ;;
            "grill-stats-dev")
                setup_dev_vault || exit_code=1
                ;;
            "grill-stats-prod")
                setup_prod_vault || exit_code=1
                ;;
            "all")
                setup_base_vault || exit_code=1
                setup_dev_vault || exit_code=1
                setup_prod_vault || exit_code=1
                ;;
            *)
                log_error "Unknown vault: $VAULT_NAME"
                exit_code=1
                ;;
        esac
    else
        # Default: setup all vaults
        setup_base_vault || exit_code=1
        setup_dev_vault || exit_code=1
        setup_prod_vault || exit_code=1
    fi

    # Final setup summary
    if [[ $exit_code -eq 0 ]]; then
        log_success "All vaults setup completed successfully"
        log_info "Next steps:"
        log_info "1. Fill in the actual secret values in 1Password"
        log_info "2. Configure 1Password Connect with vault access"
        log_info "3. Deploy the Kubernetes secret configurations"
        log_info "4. Verify OnePassword Connect can access the secrets"
    else
        log_error "Some vault setups failed - check output above"
    fi

    return $exit_code
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
        -v|--verbose)
            set -x
            shift
            ;;
        grill-stats|grill-stats-dev|grill-stats-prod|all)
            VAULT_NAME="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set default vault if not specified
if [[ -z "$VAULT_NAME" ]]; then
    VAULT_NAME="all"
fi

# Run main function
main "$@"
