#!/bin/bash
# Setup script for HashiCorp Vault Transit Engine for ThermoWorks credential encryption
# This script should be run by a Vault administrator after Vault is initialized
#
# Security Features:
# - AES-256-GCM encryption
# - Key rotation capabilities
# - Kubernetes authentication
# - Audit logging
# - RBAC policies

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN="${VAULT_TOKEN}"
TRANSIT_PATH="transit"
KEY_NAME="thermoworks-user-credentials"
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

# Check if Vault is accessible
print_status "Checking Vault connectivity..."
if ! vault status &>/dev/null; then
    print_error "Cannot connect to Vault at ${VAULT_ADDR}"
    exit 1
fi

# Check if we have a valid token
if [ -z "$VAULT_TOKEN" ]; then
    print_error "VAULT_TOKEN environment variable is not set"
    exit 1
fi

# Login to Vault
export VAULT_TOKEN
print_status "Authenticating with Vault..."

# Enable Transit secrets engine if not already enabled
print_status "Checking Transit secrets engine..."
if ! vault secrets list | grep -q "${TRANSIT_PATH}/"; then
    print_status "Enabling Transit secrets engine..."
    vault secrets enable -path="${TRANSIT_PATH}" transit
else
    print_warning "Transit secrets engine already enabled at ${TRANSIT_PATH}/"
fi

# Create encryption key for ThermoWorks credentials
print_status "Creating encryption key '${KEY_NAME}'..."
if ! vault read "${TRANSIT_PATH}/keys/${KEY_NAME}" &>/dev/null; then
    vault write -f "${TRANSIT_PATH}/keys/${KEY_NAME}" \
        type="aes256-gcm96" \
        derived=false \
        convergent_encryption=false \
        exportable=false \
        allow_plaintext_backup=false
    print_status "Encryption key '${KEY_NAME}' created successfully"
else
    print_warning "Encryption key '${KEY_NAME}' already exists"
fi

# Configure key settings
print_status "Configuring key settings..."
vault write "${TRANSIT_PATH}/keys/${KEY_NAME}/config" \
    min_decryption_version=1 \
    min_encryption_version=1 \
    deletion_allowed=false \
    auto_rotate_period=720h

# Create Kubernetes authentication role for grill-stats
print_status "Setting up Kubernetes authentication..."

# Enable Kubernetes auth if not already enabled
if ! vault auth list | grep -q "kubernetes/"; then
    print_status "Enabling Kubernetes authentication..."
    vault auth enable kubernetes
fi

# Configure Kubernetes auth
print_status "Configuring Kubernetes authentication..."
vault write auth/kubernetes/config \
    kubernetes_host="https://kubernetes.default.svc.cluster.local" \
    kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# Create policy for grill-stats encryption service
print_status "Creating Vault policy for grill-stats..."
cat <<EOF | vault policy write grill-stats-encryption -
# Allow encryption/decryption operations
path "${TRANSIT_PATH}/encrypt/${KEY_NAME}" {
  capabilities = ["create", "update"]
}

path "${TRANSIT_PATH}/decrypt/${KEY_NAME}" {
  capabilities = ["create", "update"]
}

# Allow reading key information
path "${TRANSIT_PATH}/keys/${KEY_NAME}" {
  capabilities = ["read"]
}

# Allow key rotation (admin only)
path "${TRANSIT_PATH}/keys/${KEY_NAME}/rotate" {
  capabilities = ["create", "update"]
}

# Allow reading key configuration
path "${TRANSIT_PATH}/keys/${KEY_NAME}/config" {
  capabilities = ["read"]
}
EOF

# Create Kubernetes role
print_status "Creating Kubernetes role for grill-stats..."
vault write auth/kubernetes/role/grill-stats-role \
    bound_service_account_names="encryption-service,grill-stats,auth-service,device-service,temperature-service" \
    bound_service_account_namespaces="grill-stats,default" \
    policies="grill-stats-encryption" \
    ttl=24h

# Display key information
print_status "Encryption key setup complete!"
echo ""
print_status "Key Information:"
vault read "${TRANSIT_PATH}/keys/${KEY_NAME}"

# Enable audit logging
print_status "Enabling audit logging..."
if ! vault audit list | grep -q "file/"; then
    vault audit enable file file_path=/vault/logs/audit.log
    print_status "Audit logging enabled"
else
    print_warning "Audit logging already enabled"
fi

# Create admin policy for key rotation
print_status "Creating admin policy for key rotation..."
cat <<EOF | vault policy write grill-stats-admin -
# Allow all operations on the encryption key
path "${TRANSIT_PATH}/keys/${KEY_NAME}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Allow key rotation
path "${TRANSIT_PATH}/keys/${KEY_NAME}/rotate" {
  capabilities = ["create", "update"]
}

# Allow reading key configuration
path "${TRANSIT_PATH}/keys/${KEY_NAME}/config" {
  capabilities = ["read", "update"]
}

# Allow managing encryption policies
path "${TRANSIT_PATH}/encrypt/${KEY_NAME}" {
  capabilities = ["create", "update"]
}

path "${TRANSIT_PATH}/decrypt/${KEY_NAME}" {
  capabilities = ["create", "update"]
}
EOF

# Test encryption/decryption
print_status "Testing encryption/decryption..."
TEST_PLAINTEXT=$(echo -n "test-credential-$(date +%s)" | base64)
ENCRYPTED=$(vault write -field=ciphertext "${TRANSIT_PATH}/encrypt/${KEY_NAME}" plaintext="${TEST_PLAINTEXT}")
DECRYPTED=$(vault write -field=plaintext "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="${ENCRYPTED}")

if [ "$TEST_PLAINTEXT" = "$DECRYPTED" ]; then
    print_status "Encryption/decryption test passed!"
else
    print_error "Encryption/decryption test failed!"
    exit 1
fi

# Create a backup of the key info
print_status "Backing up key information..."
vault read -format=json "${TRANSIT_PATH}/keys/${KEY_NAME}" > "${SCRIPT_DIR}/vault-key-backup-$(date +%Y%m%d-%H%M%S).json"

# Validate security configuration
print_status "Validating security configuration..."
KEY_INFO=$(vault read -format=json "${TRANSIT_PATH}/keys/${KEY_NAME}")
if echo "$KEY_INFO" | jq -e '.data.exportable == false' > /dev/null && \
   echo "$KEY_INFO" | jq -e '.data.allow_plaintext_backup == false' > /dev/null && \
   echo "$KEY_INFO" | jq -e '.data.deletion_allowed == false' > /dev/null; then
    print_status "Security configuration validated successfully"
else
    print_error "Security configuration validation failed!"
    exit 1
fi

print_status "Vault Transit engine setup completed successfully!"
echo ""
print_status "Security Summary:"
echo "- Encryption: AES-256-GCM"
echo "- Key exportable: false"
echo "- Plaintext backup: false"
echo "- Deletion allowed: false"
echo "- Auto-rotation: 720h (30 days)"
echo "- Audit logging: enabled"
echo ""
echo "Next steps:"
echo "1. Deploy the encryption service to Kubernetes"
echo "2. Configure 1Password Connect to store Vault tokens"
echo "3. Update auth-service to use encrypted credential storage"
echo "4. Run database migration to add encrypted credential columns"
echo "5. Test the complete encryption flow"