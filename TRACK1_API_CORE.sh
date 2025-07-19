#!/bin/bash
# =======================================================================
# API & Core Functionality Test Script
#
# Purpose: Verify connectivity, core functionality, and API endpoints
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
LOG_FILE="/tmp/grill-stats-api-test-$(date +%Y%m%d%H%M%S).log"
TEST_DEVICE_ID="TW-ABC-123"  # Use a known device ID from your environment
AUTH_TOKEN=""  # Will be set after login

# Test Credentials - these should be configured before running
TEST_EMAIL="admin@grill-stats.lab.apj.dev"
TEST_PASSWORD="admin1234"  # Replace with appropriate test credentials

# -----------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------

log() {
  echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1" | tee -a $LOG_FILE
}

check_status() {
  if [ $1 -eq 0 ]; then
    log "✅ $2"
    return 0
  else
    log "❌ $2 failed with status $1"
    return 1
  fi
}

login() {
  log "Attempting login with $TEST_EMAIL..."

  LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

  # Extract token from response
  AUTH_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.data.token')

  if [[ "$AUTH_TOKEN" == "null" || -z "$AUTH_TOKEN" ]]; then
    log "❌ Login failed. Response: $LOGIN_RESPONSE"
    return 1
  else
    log "✅ Login successful, token received"
    return 0
  fi
}

# -----------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------

log "=== Starting API & Core Functionality Test ==="
log "Target environment: $API_BASE_URL"
log "Log file: $LOG_FILE"

# Test 1: Basic connectivity
log "\n--- Test 1: Basic Connectivity ---"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_BASE_URL)
if [[ "$RESPONSE" == "200" || "$RESPONSE" == "302" ]]; then
  log "✅ Basic connectivity test passed (HTTP $RESPONSE)"
else
  log "❌ Basic connectivity test failed (HTTP $RESPONSE)"
  exit 1
fi

# Test 2: Health Endpoint
log "\n--- Test 2: Health Endpoint ---"
HEALTH_RESPONSE=$(curl -s "$API_BASE_URL/health")
HEALTH_STATUS=$(echo $HEALTH_RESPONSE | jq -r '.status')

if [[ "$HEALTH_STATUS" == "healthy" ]]; then
  log "✅ Health endpoint returned status: $HEALTH_STATUS"
  log "  Timestamp: $(echo $HEALTH_RESPONSE | jq -r '.timestamp')"
else
  log "❌ Health endpoint failed: $HEALTH_RESPONSE"
  exit 1
fi

# Test 3: Application Configuration
log "\n--- Test 3: Application Configuration ---"
CONFIG_RESPONSE=$(curl -s "$API_BASE_URL/api/config")
ENVIRONMENT=$(echo $CONFIG_RESPONSE | jq -r '.environment')
VERSION=$(echo $CONFIG_RESPONSE | jq -r '.version')

log "Environment: $ENVIRONMENT"
log "Version: $VERSION"

if [[ "$ENVIRONMENT" == "production" ]]; then
  log "✅ Environment is correctly set to production"
else
  log "⚠️ Environment is not set to production: $ENVIRONMENT"
fi

# Test 4: Authentication
log "\n--- Test 4: Authentication ---"
if ! login; then
  log "❌ Authentication test failed, cannot proceed with authorized endpoints"
  exit 1
fi

# Test 5: Device Listing
log "\n--- Test 5: Device Listing ---"
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")
DEVICE_COUNT=$(echo $DEVICES_RESPONSE | jq '. | length')

log "Found $DEVICE_COUNT devices"
if [[ $DEVICE_COUNT -gt 0 ]]; then
  # Extract first device ID for subsequent tests
  TEST_DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r '.[0].id')
  log "✅ Device listing successful. Using device ID: $TEST_DEVICE_ID for further tests"
else
  log "⚠️ No devices found. Using default test device ID: $TEST_DEVICE_ID"
fi

# Test 6: Device Temperature
log "\n--- Test 6: Device Temperature Data ---"
TEMP_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")
TEMP_VALUE=$(echo $TEMP_RESPONSE | jq -r '.temperature')

if [[ "$TEMP_VALUE" != "null" && -n "$TEMP_VALUE" ]]; then
  log "✅ Temperature data retrieved successfully: $TEMP_VALUE°$(echo $TEMP_RESPONSE | jq -r '.unit')"
  log "  Battery level: $(echo $TEMP_RESPONSE | jq -r '.battery_level')%"
  log "  Signal strength: $(echo $TEMP_RESPONSE | jq -r '.signal_strength')%"
  log "  Last updated: $(echo $TEMP_RESPONSE | jq -r '.timestamp')"
else
  log "❌ Failed to retrieve temperature data: $TEMP_RESPONSE"
fi

# Test 7: Historical Data
log "\n--- Test 7: Historical Data ---"
# Get data from last 24 hours
START_TIME=$(date -u -d "24 hours ago" +"%Y-%m-%dT%H:%M:%S")
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S")

HISTORY_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
  "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$START_TIME&end=$END_TIME")
HISTORY_COUNT=$(echo $HISTORY_RESPONSE | jq '. | length')

log "Retrieved $HISTORY_COUNT historical data points"
if [[ $HISTORY_COUNT -gt 0 ]]; then
  log "✅ Historical data retrieval successful"
  log "  First reading: $(echo $HISTORY_RESPONSE | jq -r '.[0].temperature')°$(echo $HISTORY_RESPONSE | jq -r '.[0].unit')"
  log "  First timestamp: $(echo $HISTORY_RESPONSE | jq -r '.[0].timestamp')"
else
  log "⚠️ No historical data found for the last 24 hours"
fi

# Test 8: Manual Sync
log "\n--- Test 8: Manual Sync ---"
SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")
SYNC_STATUS=$(echo $SYNC_RESPONSE | jq -r '.status')

if [[ "$SYNC_STATUS" == "success" ]]; then
  log "✅ Manual sync successful"
  log "  Message: $(echo $SYNC_RESPONSE | jq -r '.message')"
else
  log "❌ Manual sync failed: $SYNC_RESPONSE"
fi

# Test 9: Home Assistant Connection
log "\n--- Test 9: Home Assistant Connection ---"
HA_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/homeassistant/test")
HA_STATUS=$(echo $HA_RESPONSE | jq -r '.status')

if [[ "$HA_STATUS" == "connected" ]]; then
  log "✅ Home Assistant connection successful"
  log "  Message: $(echo $HA_RESPONSE | jq -r '.message')"
else
  log "❌ Home Assistant connection failed: $HA_RESPONSE"
fi

# Test 10: API Response Time Measurement
log "\n--- Test 10: API Response Time Measurement ---"

# Array of endpoints to test
endpoints=(
  "/health"
  "/devices"
  "/api/config"
  "/devices/$TEST_DEVICE_ID/temperature"
  "/homeassistant/test"
)

log "Measuring response times for key endpoints..."
log "| Endpoint | Response Time (ms) | Status Code |"
log "|----------|-------------------|-------------|"

for endpoint in "${endpoints[@]}"; do
  # Use curl's timing option to measure response time
  TIMING=$(curl -s -w "\n%{time_total},%{http_code}" -o /dev/null \
    -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL$endpoint")

  # Parse timing result
  TIME=$(echo "$TIMING" | tail -n1 | cut -d',' -f1)
  STATUS=$(echo "$TIMING" | tail -n1 | cut -d',' -f2)

  # Convert to milliseconds
  TIME_MS=$(echo "$TIME * 1000" | bc | cut -d'.' -f1)

  log "| $endpoint | ${TIME_MS}ms | $STATUS |"
done

# Test 11: Real-time Dashboard Access
log "\n--- Test 11: Real-time Dashboard Access ---"
DASHBOARD_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/monitoring")

if [[ "$DASHBOARD_RESPONSE" == "200" ]]; then
  log "✅ Real-time dashboard accessible"
else
  log "❌ Real-time dashboard inaccessible (HTTP $DASHBOARD_RESPONSE)"
fi

# Test 12: API Sessions
log "\n--- Test 12: Active Sessions API ---"
SESSIONS_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/sessions/active")
SESSION_COUNT=$(echo $SESSIONS_RESPONSE | jq -r '.data.count')

log "Found $SESSION_COUNT active sessions"
if [[ "$SESSION_COUNT" -ge 0 ]]; then
  log "✅ Sessions API working correctly"
else
  log "❌ Sessions API failed: $SESSIONS_RESPONSE"
fi

# Summary
log "\n=== Test Summary ==="
log "Tests completed at $(date)"
log "Results logged to $LOG_FILE"
log "Total tests: 12"

# Calculate success rate
SUCCESSES=$(grep -c "✅" $LOG_FILE)
WARNINGS=$(grep -c "⚠️" $LOG_FILE)
FAILURES=$(grep -c "❌" $LOG_FILE)

log "Successes: $SUCCESSES"
log "Warnings: $WARNINGS"
log "Failures: $FAILURES"

if [[ $FAILURES -eq 0 ]]; then
  log "\n✅ All critical tests PASSED"
  exit 0
else
  log "\n❌ Some tests FAILED - review log for details"
  exit 1
fi
