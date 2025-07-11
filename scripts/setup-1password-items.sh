#!/bin/bash
# Setup script for 1Password items required for secure credential storage
# This script creates the necessary 1Password items for the grill-stats application

set -euo pipefail

# Configuration
VAULT_NAME="HomeLab"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if 1Password CLI is installed
check_op_cli() {
    if ! command -v op &> /dev/null; then
        print_error "1Password CLI (op) is not installed"
        print_error "Please install it from: https://developer.1password.com/docs/cli/get-started/"
        exit 1
    fi
    
    print_status "1Password CLI is installed"
}

# Function to check if user is signed in
check_op_signin() {
    if ! op account list &> /dev/null; then
        print_error "You are not signed in to 1Password CLI"
        print_error "Please run: op signin"
        exit 1
    fi
    
    print_status "Signed in to 1Password CLI"
}

# Function to create 1Password item
create_op_item() {
    local item_name="$1"
    local item_title="$2"
    local item_category="$3"
    shift 3
    local fields=("$@")
    
    print_status "Creating 1Password item: $item_title"
    
    # Check if item already exists
    if op item get "$item_name" --vault="$VAULT_NAME" &> /dev/null; then
        print_warning "Item '$item_name' already exists, skipping creation"
        return 0
    fi
    
    # Build the op item create command
    local cmd="op item create --category=\"$item_category\" --title=\"$item_title\" --vault=\"$VAULT_NAME\""
    
    # Add fields
    for field in "${fields[@]}"; do
        cmd="$cmd --field=\"$field\""
    done
    
    # Execute the command
    eval "$cmd"
    
    if [ $? -eq 0 ]; then
        print_status "✓ Created item: $item_title"
    else
        print_error "✗ Failed to create item: $item_title"
        return 1
    fi
}

# Function to update 1Password item
update_op_item() {
    local item_name="$1"
    local field_name="$2"
    local field_value="$3"
    
    print_status "Updating 1Password item: $item_name"
    
    op item edit "$item_name" --vault="$VAULT_NAME" --field "$field_name=$field_value"
    
    if [ $? -eq 0 ]; then
        print_status "✓ Updated item: $item_name"
    else
        print_error "✗ Failed to update item: $item_name"
        return 1
    fi
}

# Function to generate secure password
generate_password() {
    local length="${1:-32}"
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Function to generate JWT secret
generate_jwt_secret() {
    openssl rand -hex 32
}

# Main setup function
setup_1password_items() {
    print_status "Setting up 1Password items for grill-stats application..."
    
    # 1. Vault Token
    create_op_item "grill-stats-vault-token" "Grill Stats Vault Token" "api credential" \
        "label=token,type=concealed,value=" \
        "label=vault_url,type=text,value=http://vault.vault.svc.cluster.local:8200" \
        "label=description,type=text,value=HashiCorp Vault token for grill-stats encryption service"
    
    # 2. Vault Admin Token
    create_op_item "grill-stats-vault-admin-token" "Grill Stats Vault Admin Token" "api credential" \
        "label=token,type=concealed,value=" \
        "label=vault_url,type=text,value=http://vault.vault.svc.cluster.local:8200" \
        "label=description,type=text,value=HashiCorp Vault admin token for key rotation"
    
    # 3. Database Credentials
    local db_password=$(generate_password 24)
    create_op_item "grill-stats-database-credentials" "Grill Stats Database Credentials" "database" \
        "label=hostname,type=text,value=postgresql.grill-stats.svc.cluster.local" \
        "label=port,type=text,value=5432" \
        "label=database,type=text,value=grill_stats" \
        "label=username,type=text,value=grill_stats_app" \
        "label=password,type=concealed,value=$db_password" \
        "label=description,type=text,value=PostgreSQL database credentials for grill-stats"
    
    # 4. JWT Secrets
    local jwt_secret=$(generate_jwt_secret)
    local app_secret=$(generate_password 32)
    create_op_item "grill-stats-jwt-secrets" "Grill Stats JWT Secrets" "secure note" \
        "label=jwt_secret,type=concealed,value=$jwt_secret" \
        "label=app_secret_key,type=concealed,value=$app_secret" \
        "label=description,type=text,value=JWT and Flask application secrets for grill-stats"
    
    # 5. ThermoWorks API Credentials
    create_op_item "grill-stats-thermoworks-api" "Grill Stats ThermoWorks API" "api credential" \
        "label=client_id,type=text,value=" \
        "label=client_secret,type=concealed,value=" \
        "label=base_url,type=text,value=https://api.thermoworks.com" \
        "label=auth_url,type=text,value=https://auth.thermoworks.com" \
        "label=description,type=text,value=ThermoWorks API credentials for grill-stats"
    
    print_status "✓ All 1Password items created successfully"
}

# Function to display next steps
display_next_steps() {
    echo ""
    print_status "1Password items setup completed!"
    echo ""
    print_status "Next steps:"
    echo "1. Update the Vault tokens in 1Password after Vault is initialized"
    echo "2. Add your ThermoWorks API credentials to the ThermoWorks API item"
    echo "3. Deploy the 1Password Connect operator to your Kubernetes cluster"
    echo "4. Apply the 1Password secret manifests to your cluster"
    echo "5. Verify that secrets are being synced correctly"
    echo ""
    print_status "To update a field in 1Password, use:"
    echo "op item edit <item-name> --vault=$VAULT_NAME --field <field-name>=<value>"
    echo ""
    print_status "To view an item, use:"
    echo "op item get <item-name> --vault=$VAULT_NAME"
}

# Function to validate setup
validate_setup() {
    print_status "Validating 1Password setup..."
    
    declare -a required_items=(
        "grill-stats-vault-token"
        "grill-stats-vault-admin-token"
        "grill-stats-database-credentials"
        "grill-stats-jwt-secrets"
        "grill-stats-thermoworks-api"
    )
    
    for item in "${required_items[@]}"; do
        if op item get "$item" --vault="$VAULT_NAME" &> /dev/null; then
            print_status "✓ Item '$item' exists"
        else
            print_error "✗ Item '$item' is missing"
            return 1
        fi
    done
    
    print_status "✓ All required 1Password items exist"
}

# Function to export example environment variables
export_env_vars() {
    print_status "Exporting example environment variables..."
    
    cat > "${SCRIPT_DIR}/grill-stats-env.example" << EOF
# Example environment variables for grill-stats application
# These values should be populated from 1Password Connect secrets

# Vault Configuration
VAULT_URL=http://vault.vault.svc.cluster.local:8200
VAULT_TOKEN=<from-1password>

# Database Configuration
DB_HOST=postgresql.grill-stats.svc.cluster.local
DB_PORT=5432
DB_NAME=grill_stats
DB_USER=grill_stats_app
DB_PASSWORD=<from-1password>

# JWT Configuration
JWT_SECRET=<from-1password>
SECRET_KEY=<from-1password>

# ThermoWorks API Configuration
THERMOWORKS_CLIENT_ID=<from-1password>
THERMOWORKS_CLIENT_SECRET=<from-1password>
THERMOWORKS_BASE_URL=https://api.thermoworks.com
THERMOWORKS_AUTH_URL=https://auth.thermoworks.com

# Encryption Service Configuration
ENCRYPTION_SERVICE_URL=http://encryption-service:8082
ENCRYPTION_RATE_LIMIT=100
ENCRYPTION_RATE_WINDOW=60

# Application Configuration
LOG_LEVEL=INFO
DEBUG=false
EOF
    
    print_status "✓ Example environment variables exported to: ${SCRIPT_DIR}/grill-stats-env.example"
}

# Main execution
main() {
    print_status "Starting 1Password setup for grill-stats application..."
    
    # Check prerequisites
    check_op_cli
    check_op_signin
    
    # Setup 1Password items
    setup_1password_items
    
    # Validate setup
    validate_setup
    
    # Export environment variables
    export_env_vars
    
    # Display next steps
    display_next_steps
}

# Handle command line arguments
case "${1:-}" in
    "validate")
        check_op_cli
        check_op_signin
        validate_setup
        ;;
    "env")
        export_env_vars
        ;;
    *)
        main
        ;;
esac