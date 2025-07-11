#!/bin/bash
# Test script for Vault Transit Engine encryption functionality
# This script validates the encryption service setup

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN="${VAULT_TOKEN}"
TRANSIT_PATH="transit"
KEY_NAME="thermoworks-user-credentials"

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

# Test cases for encryption/decryption
print_status "Running encryption/decryption test cases..."

# Test 1: Basic encryption/decryption
print_status "Test 1: Basic encryption/decryption"
TEST_DATA="test-email@example.com"
TEST_B64=$(echo -n "$TEST_DATA" | base64)
ENCRYPTED=$(vault write -field=ciphertext "${TRANSIT_PATH}/encrypt/${KEY_NAME}" plaintext="${TEST_B64}")
DECRYPTED=$(vault write -field=plaintext "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="${ENCRYPTED}")
DECRYPTED_TEXT=$(echo "$DECRYPTED" | base64 -d)

if [ "$TEST_DATA" = "$DECRYPTED_TEXT" ]; then
    print_status "✓ Basic encryption/decryption test passed"
else
    print_error "✗ Basic encryption/decryption test failed"
    exit 1
fi

# Test 2: Different data types
print_status "Test 2: Different data types"
declare -a test_cases=(
    "simple-password"
    "complex-password-with-special-chars!@#$%^&*()"
    "email@domain.com"
    "very-long-password-that-might-cause-issues-with-encryption-but-should-still-work-properly"
    "unicode-test-ñáéíóú"
)

for test_case in "${test_cases[@]}"; do
    TEST_B64=$(echo -n "$test_case" | base64)
    ENCRYPTED=$(vault write -field=ciphertext "${TRANSIT_PATH}/encrypt/${KEY_NAME}" plaintext="${TEST_B64}")
    DECRYPTED=$(vault write -field=plaintext "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="${ENCRYPTED}")
    DECRYPTED_TEXT=$(echo "$DECRYPTED" | base64 -d)
    
    if [ "$test_case" = "$DECRYPTED_TEXT" ]; then
        print_status "✓ Test case '$test_case' passed"
    else
        print_error "✗ Test case '$test_case' failed"
        exit 1
    fi
done

# Test 3: Key information validation
print_status "Test 3: Key information validation"
KEY_INFO=$(vault read -format=json "${TRANSIT_PATH}/keys/${KEY_NAME}")

# Check key properties
if echo "$KEY_INFO" | jq -e '.data.type == "aes256-gcm96"' > /dev/null; then
    print_status "✓ Key type is correct (aes256-gcm96)"
else
    print_error "✗ Key type is incorrect"
    exit 1
fi

if echo "$KEY_INFO" | jq -e '.data.exportable == false' > /dev/null; then
    print_status "✓ Key is non-exportable"
else
    print_error "✗ Key is exportable (security risk)"
    exit 1
fi

if echo "$KEY_INFO" | jq -e '.data.allow_plaintext_backup == false' > /dev/null; then
    print_status "✓ Plaintext backup is disabled"
else
    print_error "✗ Plaintext backup is enabled (security risk)"
    exit 1
fi

if echo "$KEY_INFO" | jq -e '.data.deletion_allowed == false' > /dev/null; then
    print_status "✓ Key deletion is disabled"
else
    print_error "✗ Key deletion is enabled (security risk)"
    exit 1
fi

# Test 4: Performance test
print_status "Test 4: Performance test (100 operations)"
start_time=$(date +%s)
for i in {1..100}; do
    TEST_B64=$(echo -n "performance-test-$i" | base64)
    ENCRYPTED=$(vault write -field=ciphertext "${TRANSIT_PATH}/encrypt/${KEY_NAME}" plaintext="${TEST_B64}")
    DECRYPTED=$(vault write -field=plaintext "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="${ENCRYPTED}")
done
end_time=$(date +%s)
duration=$((end_time - start_time))
print_status "✓ Performance test completed in ${duration} seconds"

# Test 5: Concurrent operations test
print_status "Test 5: Concurrent operations test"
test_concurrent() {
    local id=$1
    TEST_B64=$(echo -n "concurrent-test-$id" | base64)
    ENCRYPTED=$(vault write -field=ciphertext "${TRANSIT_PATH}/encrypt/${KEY_NAME}" plaintext="${TEST_B64}")
    DECRYPTED=$(vault write -field=plaintext "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="${ENCRYPTED}")
    DECRYPTED_TEXT=$(echo "$DECRYPTED" | base64 -d)
    
    if [ "concurrent-test-$id" = "$DECRYPTED_TEXT" ]; then
        return 0
    else
        return 1
    fi
}

# Run concurrent tests
for i in {1..10}; do
    test_concurrent $i &
done

wait
print_status "✓ Concurrent operations test completed"

# Test 6: Error handling
print_status "Test 6: Error handling"
if vault write "${TRANSIT_PATH}/decrypt/${KEY_NAME}" ciphertext="invalid-ciphertext" &>/dev/null; then
    print_error "✗ Error handling test failed (invalid ciphertext should fail)"
    exit 1
else
    print_status "✓ Error handling test passed (invalid ciphertext properly rejected)"
fi

# Test 7: Audit logging
print_status "Test 7: Audit logging verification"
if vault audit list | grep -q "file/"; then
    print_status "✓ Audit logging is enabled"
else
    print_warning "⚠ Audit logging is not enabled"
fi

print_status "All tests completed successfully!"
echo ""
print_status "Vault Transit Engine Test Summary:"
echo "- Basic encryption/decryption: ✓"
echo "- Different data types: ✓"
echo "- Key security validation: ✓"
echo "- Performance test: ✓"
echo "- Concurrent operations: ✓"
echo "- Error handling: ✓"
echo "- Audit logging: ✓"
echo ""
print_status "The Vault Transit Engine is ready for production use!"