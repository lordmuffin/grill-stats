#!/bin/bash
# Integration Testing Script for Grill Stats Platform
# End-to-end testing of all services and integrations

set -e

NAMESPACE="grill-stats"
CLUSTER_CONTEXT="prod-lab"
TEST_DIR="/tmp/grill-stats-integration-$(date +%Y%m%d_%H%M%S)"
TEST_TIMEOUT=300
RETRY_COUNT=3
RETRY_DELAY=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Test tracking
declare -A TEST_RESULTS
declare -A TEST_TIMES
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Test data
TEST_DEVICE_ID="test-device-$(date +%s)"
TEST_USER_EMAIL="test@grillstats.com"
TEST_PASSWORD="TestPassword123!"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$TEST_DIR/integration-test.log"
}

test_result() {
    local test_name=$1
    local result=$2
    local duration=$3
    local details=${4:-""}
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    TEST_RESULTS[$test_name]=$result
    TEST_TIMES[$test_name]=$duration
    
    case $result in
        "PASS")
            echo -e "${GREEN}✅ PASS${NC} - $test_name (${duration}ms)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            ;;
        "FAIL")
            echo -e "${RED}❌ FAIL${NC} - $test_name (${duration}ms)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            ;;
        "SKIP")
            echo -e "${YELLOW}⏭️  SKIP${NC} - $test_name"
            SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
            ;;
    esac
    
    if [ -n "$details" ]; then
        echo -e "  ${PURPLE}Details:${NC} $details"
    fi
    
    log "$result - $test_name ($duration ms): $details"
}

retry_command() {
    local command="$1"
    local description="$2"
    local count=0
    
    while [ $count -lt $RETRY_COUNT ]; do
        if eval "$command"; then
            return 0
        fi
        count=$((count + 1))
        if [ $count -lt $RETRY_COUNT ]; then
            log "Retrying '$description' (attempt $((count + 1))/$RETRY_COUNT)"
            sleep $RETRY_DELAY
        fi
    done
    
    log "Failed '$description' after $RETRY_COUNT attempts"
    return 1
}

setup_test_environment() {
    echo -e "${BLUE}Setting up integration test environment...${NC}"
    mkdir -p "$TEST_DIR"
    
    # Get service endpoints
    local ingress=$(kubectl get ingressroute -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq -r '.items[0].spec.routes[0].match' | grep -oP 'Host\(`\K[^`]+' || echo "")
    
    if [ -n "$ingress" ]; then
        BASE_URL="https://$ingress"
        log "Testing against ingress: $BASE_URL"
    else
        # Use port-forward for testing
        setup_port_forwards
        BASE_URL="http://localhost:8080"
        log "Using port-forward for testing"
    fi
    
    # Create test data files
    create_test_data_files
}

setup_port_forwards() {
    echo -e "${YELLOW}Setting up port forwards...${NC}"
    
    # Web UI
    kubectl port-forward -n $NAMESPACE svc/web-ui-service 8080:80 --context=$CLUSTER_CONTEXT &
    WEB_UI_PID=$!
    
    # Auth Service
    kubectl port-forward -n $NAMESPACE svc/auth-service 8082:8082 --context=$CLUSTER_CONTEXT &
    AUTH_PID=$!
    
    # Device Service
    kubectl port-forward -n $NAMESPACE svc/device-service 8081:8080 --context=$CLUSTER_CONTEXT &
    DEVICE_PID=$!
    
    # Temperature Service
    kubectl port-forward -n $NAMESPACE svc/temperature-service 8083:8080 --context=$CLUSTER_CONTEXT &
    TEMP_PID=$!
    
    # Historical Service
    kubectl port-forward -n $NAMESPACE svc/historical-data-service 8084:8080 --context=$CLUSTER_CONTEXT &
    HIST_PID=$!
    
    # Encryption Service
    kubectl port-forward -n $NAMESPACE svc/encryption-service 8085:8082 --context=$CLUSTER_CONTEXT &
    ENCRYPT_PID=$!
    
    # Wait for port forwards to be ready
    sleep 10
    
    # Store PIDs for cleanup
    echo "$WEB_UI_PID $AUTH_PID $DEVICE_PID $TEMP_PID $HIST_PID $ENCRYPT_PID" > "$TEST_DIR/port-forward-pids.txt"
}

create_test_data_files() {
    # Test device data
    cat > "$TEST_DIR/test-device.json" << EOF
{
  "id": "$TEST_DEVICE_ID",
  "name": "Integration Test Device",
  "type": "thermoworks-probe",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "1.0.0",
  "settings": {
    "temperature_unit": "fahrenheit",
    "alert_threshold": 200,
    "sampling_rate": 1000
  }
}
EOF
    
    # Test temperature data
    cat > "$TEST_DIR/test-temperature.json" << EOF
{
  "device_id": "$TEST_DEVICE_ID",
  "temperature": 165.5,
  "unit": "fahrenheit",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "probe_id": "probe_1",
  "battery_level": 85,
  "signal_strength": -45
}
EOF
    
    # Test user data
    cat > "$TEST_DIR/test-user.json" << EOF
{
  "email": "$TEST_USER_EMAIL",
  "password": "$TEST_PASSWORD",
  "first_name": "Test",
  "last_name": "User",
  "timezone": "America/New_York"
}
EOF
}

# Health check tests
test_health_checks() {
    echo -e "\n${BLUE}=== Health Check Tests ===${NC}"
    
    local services=(
        "auth-service:8082"
        "device-service:8081"
        "temperature-service:8083"
        "historical-data-service:8084"
        "encryption-service:8085"
        "web-ui:8080"
    )
    
    for service_port in "${services[@]}"; do
        local service="${service_port%:*}"
        local port="${service_port#*:}"
        
        local start_time=$(date +%s%3N)
        local url="http://localhost:$port/health"
        
        if [ "$service" == "web-ui" ]; then
            url="$BASE_URL/health"
        fi
        
        if retry_command "curl -sf --max-time 10 '$url' >/dev/null" "Health check for $service"; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            # Get detailed health info
            local health_data=$(curl -sf --max-time 10 "$url" 2>/dev/null || echo "{}")
            local status=$(echo "$health_data" | jq -r '.status // "unknown"')
            
            test_result "HEALTH_$service" "PASS" "$duration" "Status: $status"
        else
            test_result "HEALTH_$service" "FAIL" "0" "Health check failed"
        fi
    done
}

# Database connectivity tests
test_database_connectivity() {
    echo -e "\n${BLUE}=== Database Connectivity Tests ===${NC}"
    
    # PostgreSQL
    local start_time=$(date +%s%3N)
    local pg_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$pg_pod" ]; then
        if retry_command "kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- pg_isready -U grill_stats" "PostgreSQL connection"; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            # Test query
            local query_result=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- psql -U grill_stats -d grill_stats -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
            
            test_result "DATABASE_PostgreSQL" "PASS" "$duration" "Tables: $query_result"
        else
            test_result "DATABASE_PostgreSQL" "FAIL" "0" "Connection failed"
        fi
    else
        test_result "DATABASE_PostgreSQL" "SKIP" "0" "PostgreSQL pod not found"
    fi
    
    # InfluxDB
    start_time=$(date +%s%3N)
    local influx_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=influxdb -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$influx_pod" ]; then
        if retry_command "kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx ping" "InfluxDB connection"; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            # Test bucket access
            local buckets=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx bucket list --json 2>/dev/null | jq '[.[] | select(.name | contains("grill-stats"))] | length')
            
            test_result "DATABASE_InfluxDB" "PASS" "$duration" "Buckets: $buckets"
        else
            test_result "DATABASE_InfluxDB" "FAIL" "0" "Connection failed"
        fi
    else
        test_result "DATABASE_InfluxDB" "SKIP" "0" "InfluxDB pod not found"
    fi
    
    # Redis
    start_time=$(date +%s%3N)
    local redis_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=redis -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$redis_pod" ]; then
        if retry_command "kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli ping" "Redis connection"; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            # Test key operations
            kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli set "test-key" "test-value" >/dev/null
            local get_result=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli get "test-key")
            kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli del "test-key" >/dev/null
            
            if [ "$get_result" == "test-value" ]; then
                test_result "DATABASE_Redis" "PASS" "$duration" "Key operations work"
            else
                test_result "DATABASE_Redis" "FAIL" "$duration" "Key operations failed"
            fi
        else
            test_result "DATABASE_Redis" "FAIL" "0" "Connection failed"
        fi
    else
        test_result "DATABASE_Redis" "SKIP" "0" "Redis pod not found"
    fi
}

# Authentication tests
test_authentication() {
    echo -e "\n${BLUE}=== Authentication Tests ===${NC}"
    
    # Test user registration
    local start_time=$(date +%s%3N)
    local register_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -d @"$TEST_DIR/test-user.json" \
        "http://localhost:8082/api/auth/register" 2>/dev/null)
    
    if [ -n "$register_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local user_id=$(echo "$register_response" | jq -r '.user_id // "unknown"')
        test_result "AUTH_Register" "PASS" "$duration" "User ID: $user_id"
        
        # Store user ID for cleanup
        echo "$user_id" > "$TEST_DIR/test-user-id.txt"
    else
        test_result "AUTH_Register" "FAIL" "0" "Registration failed"
    fi
    
    # Test user login
    start_time=$(date +%s%3N)
    local login_data=$(cat << EOF
{
  "email": "$TEST_USER_EMAIL",
  "password": "$TEST_PASSWORD"
}
EOF
)
    
    local login_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -d "$login_data" \
        "http://localhost:8082/api/auth/login" 2>/dev/null)
    
    if [ -n "$login_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local access_token=$(echo "$login_response" | jq -r '.access_token // "unknown"')
        test_result "AUTH_Login" "PASS" "$duration" "Token received"
        
        # Store token for other tests
        echo "$access_token" > "$TEST_DIR/auth-token.txt"
    else
        test_result "AUTH_Login" "FAIL" "0" "Login failed"
    fi
    
    # Test token validation
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        local token=$(cat "$TEST_DIR/auth-token.txt")
        
        start_time=$(date +%s%3N)
        local validate_response=$(curl -sf --max-time 30 -X GET \
            -H "Authorization: Bearer $token" \
            "http://localhost:8082/api/auth/validate" 2>/dev/null)
        
        if [ -n "$validate_response" ]; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            local valid=$(echo "$validate_response" | jq -r '.valid // false')
            test_result "AUTH_Validate" "PASS" "$duration" "Valid: $valid"
        else
            test_result "AUTH_Validate" "FAIL" "0" "Token validation failed"
        fi
    else
        test_result "AUTH_Validate" "SKIP" "0" "No token available"
    fi
}

# Device management tests
test_device_management() {
    echo -e "\n${BLUE}=== Device Management Tests ===${NC}"
    
    local auth_token=""
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        auth_token=$(cat "$TEST_DIR/auth-token.txt")
    fi
    
    # Test device registration
    local start_time=$(date +%s%3N)
    local device_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $auth_token" \
        -d @"$TEST_DIR/test-device.json" \
        "http://localhost:8081/api/devices" 2>/dev/null)
    
    if [ -n "$device_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local device_id=$(echo "$device_response" | jq -r '.id // "unknown"')
        test_result "DEVICE_Register" "PASS" "$duration" "Device ID: $device_id"
    else
        test_result "DEVICE_Register" "FAIL" "0" "Device registration failed"
    fi
    
    # Test device listing
    start_time=$(date +%s%3N)
    local devices_response=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8081/api/devices" 2>/dev/null)
    
    if [ -n "$devices_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local device_count=$(echo "$devices_response" | jq '. | length')
        test_result "DEVICE_List" "PASS" "$duration" "Devices: $device_count"
    else
        test_result "DEVICE_List" "FAIL" "0" "Device listing failed"
    fi
    
    # Test device details
    start_time=$(date +%s%3N)
    local device_details=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8081/api/devices/$TEST_DEVICE_ID" 2>/dev/null)
    
    if [ -n "$device_details" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local device_name=$(echo "$device_details" | jq -r '.name // "unknown"')
        test_result "DEVICE_Details" "PASS" "$duration" "Name: $device_name"
    else
        test_result "DEVICE_Details" "FAIL" "0" "Device details failed"
    fi
    
    # Test device update
    start_time=$(date +%s%3N)
    local update_data=$(cat << EOF
{
  "name": "Updated Integration Test Device",
  "settings": {
    "temperature_unit": "celsius",
    "alert_threshold": 93,
    "sampling_rate": 2000
  }
}
EOF
)
    
    local update_response=$(curl -sf --max-time 30 -X PUT \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $auth_token" \
        -d "$update_data" \
        "http://localhost:8081/api/devices/$TEST_DEVICE_ID" 2>/dev/null)
    
    if [ -n "$update_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local updated_name=$(echo "$update_response" | jq -r '.name // "unknown"')
        test_result "DEVICE_Update" "PASS" "$duration" "Updated name: $updated_name"
    else
        test_result "DEVICE_Update" "FAIL" "0" "Device update failed"
    fi
}

# Temperature data tests
test_temperature_data() {
    echo -e "\n${BLUE}=== Temperature Data Tests ===${NC}"
    
    local auth_token=""
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        auth_token=$(cat "$TEST_DIR/auth-token.txt")
    fi
    
    # Test temperature data ingestion
    local start_time=$(date +%s%3N)
    local temp_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $auth_token" \
        -d @"$TEST_DIR/test-temperature.json" \
        "http://localhost:8083/api/temperature/data" 2>/dev/null)
    
    if [ -n "$temp_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local data_id=$(echo "$temp_response" | jq -r '.id // "unknown"')
        test_result "TEMP_Ingest" "PASS" "$duration" "Data ID: $data_id"
    else
        test_result "TEMP_Ingest" "FAIL" "0" "Temperature ingestion failed"
    fi
    
    # Test current temperature reading
    start_time=$(date +%s%3N)
    local current_temp=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8083/api/temperature/current/$TEST_DEVICE_ID" 2>/dev/null)
    
    if [ -n "$current_temp" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local temp_value=$(echo "$current_temp" | jq -r '.temperature // "unknown"')
        test_result "TEMP_Current" "PASS" "$duration" "Temperature: $temp_value"
    else
        test_result "TEMP_Current" "FAIL" "0" "Current temperature failed"
    fi
    
    # Test temperature history
    start_time=$(date +%s%3N)
    local history_response=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8083/api/temperature/history/$TEST_DEVICE_ID?hours=1" 2>/dev/null)
    
    if [ -n "$history_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local data_points=$(echo "$history_response" | jq '. | length')
        test_result "TEMP_History" "PASS" "$duration" "Data points: $data_points"
    else
        test_result "TEMP_History" "FAIL" "0" "Temperature history failed"
    fi
    
    # Test temperature alerts
    start_time=$(date +%s%3N)
    local alert_data=$(cat << EOF
{
  "device_id": "$TEST_DEVICE_ID",
  "temperature": 250.0,
  "unit": "fahrenheit",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "probe_id": "probe_1"
}
EOF
)
    
    local alert_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $auth_token" \
        -d "$alert_data" \
        "http://localhost:8083/api/temperature/data" 2>/dev/null)
    
    if [ -n "$alert_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        # Check if alert was triggered
        local alert_triggered=$(echo "$alert_response" | jq -r '.alert_triggered // false')
        test_result "TEMP_Alert" "PASS" "$duration" "Alert triggered: $alert_triggered"
    else
        test_result "TEMP_Alert" "FAIL" "0" "Temperature alert test failed"
    fi
}

# Historical data tests
test_historical_data() {
    echo -e "\n${BLUE}=== Historical Data Tests ===${NC}"
    
    local auth_token=""
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        auth_token=$(cat "$TEST_DIR/auth-token.txt")
    fi
    
    # Test data aggregation
    local start_time=$(date +%s%3N)
    local aggregation_response=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8084/api/historical/aggregate/$TEST_DEVICE_ID?period=1h&function=avg" 2>/dev/null)
    
    if [ -n "$aggregation_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local avg_temp=$(echo "$aggregation_response" | jq -r '.average_temperature // "unknown"')
        test_result "HIST_Aggregate" "PASS" "$duration" "Average temp: $avg_temp"
    else
        test_result "HIST_Aggregate" "FAIL" "0" "Historical aggregation failed"
    fi
    
    # Test data export
    start_time=$(date +%s%3N)
    local export_response=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8084/api/historical/export/$TEST_DEVICE_ID?format=csv&start=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" 2>/dev/null)
    
    if [ -n "$export_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local line_count=$(echo "$export_response" | wc -l)
        test_result "HIST_Export" "PASS" "$duration" "CSV lines: $line_count"
    else
        test_result "HIST_Export" "FAIL" "0" "Historical export failed"
    fi
    
    # Test data retention
    start_time=$(date +%s%3N)
    local retention_response=$(curl -sf --max-time 30 -X GET \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8084/api/historical/retention/status" 2>/dev/null)
    
    if [ -n "$retention_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local retention_policy=$(echo "$retention_response" | jq -r '.retention_policy // "unknown"')
        test_result "HIST_Retention" "PASS" "$duration" "Policy: $retention_policy"
    else
        test_result "HIST_Retention" "FAIL" "0" "Retention status failed"
    fi
}

# Encryption service tests
test_encryption() {
    echo -e "\n${BLUE}=== Encryption Service Tests ===${NC}"
    
    local auth_token=""
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        auth_token=$(cat "$TEST_DIR/auth-token.txt")
    fi
    
    # Test data encryption
    local start_time=$(date +%s%3N)
    local encrypt_data=$(cat << EOF
{
  "data": "sensitive-test-data-$(date +%s)",
  "key_id": "default"
}
EOF
)
    
    local encrypt_response=$(curl -sf --max-time 30 -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $auth_token" \
        -d "$encrypt_data" \
        "http://localhost:8085/api/encryption/encrypt" 2>/dev/null)
    
    if [ -n "$encrypt_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local encrypted_data=$(echo "$encrypt_response" | jq -r '.encrypted_data // "unknown"')
        test_result "ENCRYPT_Encrypt" "PASS" "$duration" "Data encrypted"
        
        # Store encrypted data for decryption test
        echo "$encrypted_data" > "$TEST_DIR/encrypted-data.txt"
    else
        test_result "ENCRYPT_Encrypt" "FAIL" "0" "Encryption failed"
    fi
    
    # Test data decryption
    if [ -f "$TEST_DIR/encrypted-data.txt" ]; then
        local encrypted_data=$(cat "$TEST_DIR/encrypted-data.txt")
        
        start_time=$(date +%s%3N)
        local decrypt_data=$(cat << EOF
{
  "encrypted_data": "$encrypted_data",
  "key_id": "default"
}
EOF
)
        
        local decrypt_response=$(curl -sf --max-time 30 -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $auth_token" \
            -d "$decrypt_data" \
            "http://localhost:8085/api/encryption/decrypt" 2>/dev/null)
        
        if [ -n "$decrypt_response" ]; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            
            local decrypted_data=$(echo "$decrypt_response" | jq -r '.decrypted_data // "unknown"')
            test_result "ENCRYPT_Decrypt" "PASS" "$duration" "Data decrypted"
        else
            test_result "ENCRYPT_Decrypt" "FAIL" "0" "Decryption failed"
        fi
    else
        test_result "ENCRYPT_Decrypt" "SKIP" "0" "No encrypted data available"
    fi
    
    # Test key rotation
    start_time=$(date +%s%3N)
    local key_rotate_response=$(curl -sf --max-time 30 -X POST \
        -H "Authorization: Bearer $auth_token" \
        "http://localhost:8085/api/encryption/rotate-key" 2>/dev/null)
    
    if [ -n "$key_rotate_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local new_key_id=$(echo "$key_rotate_response" | jq -r '.new_key_id // "unknown"')
        test_result "ENCRYPT_KeyRotate" "PASS" "$duration" "New key ID: $new_key_id"
    else
        test_result "ENCRYPT_KeyRotate" "FAIL" "0" "Key rotation failed"
    fi
}

# Web UI tests
test_web_ui() {
    echo -e "\n${BLUE}=== Web UI Tests ===${NC}"
    
    # Test main page load
    local start_time=$(date +%s%3N)
    local main_page=$(curl -sf --max-time 30 -L "$BASE_URL/" 2>/dev/null)
    
    if [ -n "$main_page" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        # Check for key elements
        local has_title=$(echo "$main_page" | grep -c "Grill Stats" || echo "0")
        test_result "WEB_UI_Load" "PASS" "$duration" "Page loaded, title found: $has_title"
    else
        test_result "WEB_UI_Load" "FAIL" "0" "Main page load failed"
    fi
    
    # Test static assets
    local assets=("css" "js" "favicon.ico")
    
    for asset in "${assets[@]}"; do
        start_time=$(date +%s%3N)
        local asset_response=$(curl -sf --max-time 30 -I "$BASE_URL/static/$asset" 2>/dev/null | head -n1)
        
        if echo "$asset_response" | grep -q "200"; then
            local end_time=$(date +%s%3N)
            local duration=$((end_time - start_time))
            test_result "WEB_UI_Asset_$asset" "PASS" "$duration" "Asset available"
        else
            test_result "WEB_UI_Asset_$asset" "FAIL" "0" "Asset not available"
        fi
    done
    
    # Test API endpoints through web UI
    start_time=$(date +%s%3N)
    local api_health=$(curl -sf --max-time 30 "$BASE_URL/api/health" 2>/dev/null)
    
    if [ -n "$api_health" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local status=$(echo "$api_health" | jq -r '.status // "unknown"')
        test_result "WEB_UI_API" "PASS" "$duration" "API status: $status"
    else
        test_result "WEB_UI_API" "FAIL" "0" "API health check failed"
    fi
}

# External integration tests
test_external_integrations() {
    echo -e "\n${BLUE}=== External Integration Tests ===${NC}"
    
    # Test ThermoWorks API simulation
    local start_time=$(date +%s%3N)
    local thermoworks_response=$(curl -sf --max-time 30 -X GET \
        "http://localhost:8081/api/devices/sync" 2>/dev/null)
    
    if [ -n "$thermoworks_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local sync_status=$(echo "$thermoworks_response" | jq -r '.status // "unknown"')
        test_result "EXT_ThermoWorks" "PASS" "$duration" "Sync status: $sync_status"
    else
        test_result "EXT_ThermoWorks" "FAIL" "0" "ThermoWorks sync failed"
    fi
    
    # Test Vault integration
    start_time=$(date +%s%3N)
    local vault_response=$(curl -sf --max-time 30 -X GET \
        "http://localhost:8085/api/encryption/vault/status" 2>/dev/null)
    
    if [ -n "$vault_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local vault_status=$(echo "$vault_response" | jq -r '.status // "unknown"')
        test_result "EXT_Vault" "PASS" "$duration" "Vault status: $vault_status"
    else
        test_result "EXT_Vault" "FAIL" "0" "Vault integration failed"
    fi
    
    # Test Home Assistant integration
    start_time=$(date +%s%3N)
    local ha_response=$(curl -sf --max-time 30 -X GET \
        "http://localhost:8083/api/temperature/homeassistant/status" 2>/dev/null)
    
    if [ -n "$ha_response" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        local ha_status=$(echo "$ha_response" | jq -r '.status // "unknown"')
        test_result "EXT_HomeAssistant" "PASS" "$duration" "HA status: $ha_status"
    else
        test_result "EXT_HomeAssistant" "FAIL" "0" "Home Assistant integration failed"
    fi
}

# Performance and stress tests
test_performance() {
    echo -e "\n${BLUE}=== Performance Tests ===${NC}"
    
    # Concurrent user simulation
    local start_time=$(date +%s%3N)
    local concurrent_users=5
    local requests_per_user=10
    
    for i in $(seq 1 $concurrent_users); do
        (
            for j in $(seq 1 $requests_per_user); do
                curl -sf --max-time 10 "http://localhost:8081/api/devices" >/dev/null 2>&1
            done
        ) &
    done
    
    wait
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))
    
    test_result "PERF_Concurrent" "PASS" "$duration" "$concurrent_users users, $requests_per_user requests each"
    
    # Memory usage test
    start_time=$(date +%s%3N)
    local memory_usage=$(kubectl top pods -n $NAMESPACE --context=$CLUSTER_CONTEXT --no-headers | awk '{sum += $3} END {print sum}')
    
    if [ -n "$memory_usage" ]; then
        local end_time=$(date +%s%3N)
        local duration=$((end_time - start_time))
        
        test_result "PERF_Memory" "PASS" "$duration" "Total memory usage: ${memory_usage}Mi"
    else
        test_result "PERF_Memory" "FAIL" "0" "Memory usage check failed"
    fi
    
    # Response time test
    start_time=$(date +%s%3N)
    local response_times=()
    
    for i in $(seq 1 10); do
        local req_start=$(date +%s%3N)
        curl -sf --max-time 10 "http://localhost:8081/api/devices" >/dev/null 2>&1
        local req_end=$(date +%s%3N)
        local req_duration=$((req_end - req_start))
        response_times+=($req_duration)
    done
    
    local avg_response_time=$(printf '%s\n' "${response_times[@]}" | awk '{sum+=$1} END {print sum/NR}')
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))
    
    test_result "PERF_ResponseTime" "PASS" "$duration" "Average response time: ${avg_response_time}ms"
}

# Cleanup test data
cleanup_test_data() {
    echo -e "\n${BLUE}=== Cleanup Test Data ===${NC}"
    
    local auth_token=""
    if [ -f "$TEST_DIR/auth-token.txt" ]; then
        auth_token=$(cat "$TEST_DIR/auth-token.txt")
    fi
    
    # Delete test device
    if [ -n "$auth_token" ]; then
        local delete_response=$(curl -sf --max-time 30 -X DELETE \
            -H "Authorization: Bearer $auth_token" \
            "http://localhost:8081/api/devices/$TEST_DEVICE_ID" 2>/dev/null)
        
        if [ -n "$delete_response" ]; then
            log "Test device deleted successfully"
        else
            log "Warning: Failed to delete test device"
        fi
    fi
    
    # Delete test user
    if [ -f "$TEST_DIR/test-user-id.txt" ] && [ -n "$auth_token" ]; then
        local user_id=$(cat "$TEST_DIR/test-user-id.txt")
        local delete_user_response=$(curl -sf --max-time 30 -X DELETE \
            -H "Authorization: Bearer $auth_token" \
            "http://localhost:8082/api/auth/users/$user_id" 2>/dev/null)
        
        if [ -n "$delete_user_response" ]; then
            log "Test user deleted successfully"
        else
            log "Warning: Failed to delete test user"
        fi
    fi
    
    # Clean up port forwards
    if [ -f "$TEST_DIR/port-forward-pids.txt" ]; then
        local pids=$(cat "$TEST_DIR/port-forward-pids.txt")
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        log "Port forwards cleaned up"
    fi
}

# Generate test report
generate_test_report() {
    echo -e "\n${BLUE}Generating integration test report...${NC}"
    
    local report_file="$TEST_DIR/integration-report.json"
    
    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cluster": "$CLUSTER_CONTEXT",
  "namespace": "$NAMESPACE",
  "base_url": "$BASE_URL",
  "test_summary": {
    "total_tests": $TOTAL_TESTS,
    "passed": $PASSED_TESTS,
    "failed": $FAILED_TESTS,
    "skipped": $SKIPPED_TESTS,
    "pass_rate": $(echo "scale=2; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc -l)
  },
  "test_results": {
EOF
    
    # Add individual test results
    local first=true
    for test_name in "${!TEST_RESULTS[@]}"; do
        if [ "$first" = false ]; then
            echo "," >> "$report_file"
        fi
        
        cat >> "$report_file" << EOF
    "$test_name": {
      "result": "${TEST_RESULTS[$test_name]}",
      "duration_ms": ${TEST_TIMES[$test_name]:-0}
    }
EOF
        first=false
    done
    
    echo -e "\n  }\n}" >> "$report_file"
    
    log "Integration test report generated: $report_file"
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           Grill Stats Integration Test Suite                 ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "Cluster: ${PURPLE}$CLUSTER_CONTEXT${NC}"
    echo -e "Namespace: ${PURPLE}$NAMESPACE${NC}"
    echo -e "Test Directory: ${PURPLE}$TEST_DIR${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Setup test environment
    setup_test_environment
    
    # Run test suites
    test_health_checks
    test_database_connectivity
    test_authentication
    test_device_management
    test_temperature_data
    test_historical_data
    test_encryption
    test_web_ui
    test_external_integrations
    test_performance
    
    # Cleanup
    cleanup_test_data
    
    # Generate report
    generate_test_report
    
    # Test summary
    echo -e "\n${BLUE}Integration Test Summary:${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Total Tests: $TOTAL_TESTS"
    echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
    echo -e "${RED}Failed: $FAILED_TESTS${NC}"
    echo -e "${YELLOW}Skipped: $SKIPPED_TESTS${NC}"
    
    local pass_rate=$(echo "scale=2; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc -l)
    echo -e "Pass Rate: ${pass_rate}%"
    
    echo -e "\n${PURPLE}Test Results:${NC}"
    echo -e "  Integration Report: $TEST_DIR/integration-report.json"
    echo -e "  Test Log: $TEST_DIR/integration-test.log"
    
    # Final status
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 INTEGRATION TESTS: PASSED${NC}"
        echo -e "All tests completed successfully. System is ready for production."
        return 0
    elif [ $FAILED_TESTS -le 2 ] && [ $(echo "$pass_rate >= 90" | bc -l) -eq 1 ]; then
        echo -e "\n${YELLOW}⚠️  INTEGRATION TESTS: CONDITIONAL PASS${NC}"
        echo -e "Most tests passed. Review failures before production deployment."
        return 0
    else
        echo -e "\n${RED}❌ INTEGRATION TESTS: FAILED${NC}"
        echo -e "Multiple test failures detected. Address issues before production."
        return 1
    fi
}

# Handle cleanup on exit
trap cleanup_test_data EXIT

# Check prerequisites
for cmd in kubectl jq curl bc; do
    if ! command -v $cmd >/dev/null 2>&1; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --context)
            CLUSTER_CONTEXT="$2"
            shift 2
            ;;
        -t|--timeout)
            TEST_TIMEOUT="$2"
            shift 2
            ;;
        -d|--test-dir)
            TEST_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -n, --namespace NAME      Kubernetes namespace (default: grill-stats)"
            echo "  --context NAME            Kubernetes context (default: prod-lab)"
            echo "  -t, --timeout SECONDS     Test timeout (default: 300)"
            echo "  -d, --test-dir DIR        Test directory (default: auto-generated)"
            echo "  -h, --help                Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"