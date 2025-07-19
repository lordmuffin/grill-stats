#!/bin/bash
# =======================================================================
# Final Integration Test Script
#
# Purpose: Coordinate final integration testing after individual tracks
#          have completed their tests
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
LOG_FILE="/tmp/grill-stats-integration-test-$(date +%Y%m%d%H%M%S).log"
AUTH_TOKEN=""  # Will be set after login
TRACK_LOGS_DIR="/tmp/grill-stats-track-logs"

# Test Credentials - these should be configured before running
TEST_EMAIL="admin@grill-stats.lab.apj.dev"
TEST_PASSWORD="admin1234"  # Replace with appropriate test credentials

# Home Assistant token - needs to be provided
HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJncmlsbC1zdGF0cyIsInN1YiI6ImhvbWVhc3Npc3RhbnQifQ.example"  # Home Assistant long-lived access token
HA_URL=$(curl -s "$API_BASE_URL/api/config" | jq -r '.homeassistant_url // "http://homeassistant:8123"')

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

# Process track test results to get summary
process_track_results() {
  local track_log=$1
  local track_name=$2

  if [[ ! -f "$track_log" ]]; then
    log "⚠️ Track log file not found: $track_log"
    return 1
  fi

  SUCCESSES=$(grep -c "✅" $track_log)
  WARNINGS=$(grep -c "⚠️" $track_log)
  FAILURES=$(grep -c "❌" $track_log)

  log "$track_name Results:"
  log "  Successes: $SUCCESSES"
  log "  Warnings: $WARNINGS"
  log "  Failures: $FAILURES"

  if [[ $FAILURES -eq 0 ]]; then
    log "  ✅ $track_name PASSED"
    return 0
  else
    log "  ❌ $track_name FAILED"
    return 1
  fi
}

# -----------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------

log "=== Starting Final Integration Test ==="
log "Target environment: $API_BASE_URL"
log "Log file: $LOG_FILE"

# Create directory for track logs
mkdir -p $TRACK_LOGS_DIR

# Authentication
if ! login; then
  log "❌ Authentication test failed, cannot proceed with authorized endpoints"
  exit 1
fi

# Test 1: Verify Individual Track Results
log "\n--- Test 1: Verify Individual Track Results ---"

# Define track log files (these would be output from previous track runs)
TRACK1_LOG=$(ls -t /tmp/grill-stats-api-test-*.log 2>/dev/null | head -1)
TRACK2_LOG=$(ls -t /tmp/grill-stats-thermoworks-test-*.log 2>/dev/null | head -1)
TRACK3_LOG=$(ls -t /tmp/grill-stats-ha-test-*.log 2>/dev/null | head -1)
TRACK4_LOG=$(ls -t /tmp/grill-stats-performance-test-*.log 2>/dev/null | head -1)
TRACK5_LOG=$(ls -t /tmp/grill-stats-security-ui-test-*.log 2>/dev/null | head -1)

# Process each track's results
TRACKS_FAILED=0

if [[ -n "$TRACK1_LOG" ]]; then
  log "Processing Track 1 (API & Core) results..."
  process_track_results "$TRACK1_LOG" "Track 1 (API & Core)"
  TRACKS_FAILED=$((TRACKS_FAILED + $?))
else
  log "⚠️ Track 1 log not found. Track may not have been run."
fi

if [[ -n "$TRACK2_LOG" ]]; then
  log "Processing Track 2 (ThermoWorks) results..."
  process_track_results "$TRACK2_LOG" "Track 2 (ThermoWorks)"
  TRACKS_FAILED=$((TRACKS_FAILED + $?))
else
  log "⚠️ Track 2 log not found. Track may not have been run."
fi

if [[ -n "$TRACK3_LOG" ]]; then
  log "Processing Track 3 (Home Assistant & Data Storage) results..."
  process_track_results "$TRACK3_LOG" "Track 3 (Home Assistant & Data Storage)"
  TRACKS_FAILED=$((TRACKS_FAILED + $?))
else
  log "⚠️ Track 3 log not found. Track may not have been run."
fi

if [[ -n "$TRACK4_LOG" ]]; then
  log "Processing Track 4 (Performance & Reliability) results..."
  process_track_results "$TRACK4_LOG" "Track 4 (Performance & Reliability)"
  TRACKS_FAILED=$((TRACKS_FAILED + $?))
else
  log "⚠️ Track 4 log not found. Track may not have been run."
fi

if [[ -n "$TRACK5_LOG" ]]; then
  log "Processing Track 5 (Security, Deployment & UI) results..."
  process_track_results "$TRACK5_LOG" "Track 5 (Security, Deployment & UI)"
  TRACKS_FAILED=$((TRACKS_FAILED + $?))
else
  log "⚠️ Track 5 log not found. Track may not have been run."
fi

# Summarize track results
if [[ $TRACKS_FAILED -eq 0 ]]; then
  log "✅ All tracks passed their tests"
else
  log "⚠️ $TRACKS_FAILED tracks had failures. Review individual track logs for details."
fi

# Test 2: End-to-End Data Flow Test
log "\n--- Test 2: End-to-End Data Flow Test ---"

# Step 1: Get a device from ThermoWorks
log "Step 1: Retrieving device from ThermoWorks..."
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")

if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  DEVICE_COUNT=$(echo $DEVICES_RESPONSE | jq '. | length')
  log "  Found $DEVICE_COUNT devices"

  if [[ $DEVICE_COUNT -gt 0 ]]; then
    TEST_DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r '.[0].id')
    TEST_DEVICE_NAME=$(echo $DEVICES_RESPONSE | jq -r '.[0].name')
    log "  ✅ Successfully retrieved device: $TEST_DEVICE_NAME (ID: $TEST_DEVICE_ID)"
  else
    log "  ❌ No devices found"
    TEST_DEVICE_ID=""
  fi
else
  log "  ❌ Failed to retrieve device list: $DEVICES_RESPONSE"
  TEST_DEVICE_ID=""
fi

if [[ -z "$TEST_DEVICE_ID" ]]; then
  log "❌ Cannot proceed with end-to-end test without a valid device"
else
  # Step 2: Get temperature data from ThermoWorks
  log "Step 2: Retrieving temperature data from ThermoWorks..."
  TEMP_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")

  if [[ $(echo $TEMP_RESPONSE | jq 'has("temperature")') == "true" ]]; then
    TEMP_VALUE=$(echo $TEMP_RESPONSE | jq -r '.temperature')
    TEMP_UNIT=$(echo $TEMP_RESPONSE | jq -r '.unit')
    TIMESTAMP=$(echo $TEMP_RESPONSE | jq -r '.timestamp')

    log "  ✅ Successfully retrieved temperature: $TEMP_VALUE°$TEMP_UNIT (at $TIMESTAMP)"
  else
    log "  ❌ Failed to retrieve temperature data: $TEMP_RESPONSE"
  fi

  # Step 3: Trigger a sync to Home Assistant
  log "Step 3: Triggering data sync to Home Assistant..."
  SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")

  if [[ $(echo $SYNC_RESPONSE | jq -r '.status') == "success" ]]; then
    log "  ✅ Successfully triggered sync operation"

    # Wait for sync to complete
    log "  Waiting 10 seconds for sync to complete..."
    sleep 10
  else
    log "  ❌ Failed to trigger sync operation: $SYNC_RESPONSE"
  fi

  # Step 4: Verify data in Home Assistant (if HA token is available)
  if [[ -n "$HA_TOKEN" ]]; then
    log "Step 4: Verifying data in Home Assistant..."

    # Calculate expected Home Assistant entity ID
    SENSOR_NAME="thermoworks_$(echo $TEST_DEVICE_NAME | tr 'A-Z ' 'a-z_')"
    log "  Expected sensor name: $SENSOR_NAME"

    HA_ENTITY_RESPONSE=$(curl -s -H "Authorization: Bearer $HA_TOKEN" \
      "$HA_URL/api/states/sensor.$SENSOR_NAME")

    ENTITY_STATE=$(echo $HA_ENTITY_RESPONSE | jq -r '.state')

    if [[ "$ENTITY_STATE" != "null" && -n "$ENTITY_STATE" ]]; then
      log "  ✅ Successfully verified data in Home Assistant: $ENTITY_STATE°"
      log "    Last updated: $(echo $HA_ENTITY_RESPONSE | jq -r '.last_updated')"

      # Compare values (allowing for slight differences due to rounding)
      if [[ $(echo "scale=1; ($ENTITY_STATE - $TEMP_VALUE)^2 < 1" | bc) -eq 1 ]]; then
        log "  ✅ Temperature values match between ThermoWorks and Home Assistant"
      else
        log "  ⚠️ Temperature values differ: ThermoWorks=$TEMP_VALUE, HA=$ENTITY_STATE"
      fi
    else
      log "  ❌ Failed to retrieve entity from Home Assistant: $HA_ENTITY_RESPONSE"
    fi
  else
    log "  ⚠️ Skipping Home Assistant verification (no HA token provided)"
  fi

  # Step 5: Verify data is stored and retrievable
  log "Step 5: Verifying data storage..."

  # Get recent history to verify the data point was stored
  START_TIME=$(date -u -d "1 hour ago" +"%Y-%m-%dT%H:%M:%S")
  END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S")

  HISTORY_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$START_TIME&end=$END_TIME")

  if [[ $(echo $HISTORY_RESPONSE | jq 'type') == "array" ]]; then
    POINTS_COUNT=$(echo $HISTORY_RESPONSE | jq '. | length')
    log "  ✅ Successfully retrieved $POINTS_COUNT historical data points"

    if [[ $POINTS_COUNT -gt 0 ]]; then
      LATEST_TEMP=$(echo $HISTORY_RESPONSE | jq -r '.[0].temperature')
      LATEST_TS=$(echo $HISTORY_RESPONSE | jq -r '.[0].timestamp')

      log "  Latest stored temperature: $LATEST_TEMP° at $LATEST_TS"

      # Compare with current temperature
      if [[ $(echo "scale=1; ($LATEST_TEMP - $TEMP_VALUE)^2 < 1" | bc) -eq 1 ]]; then
        log "  ✅ Current and stored temperature values match"
      else
        log "  ⚠️ Current and stored temperature values differ: Current=$TEMP_VALUE, Stored=$LATEST_TEMP"
      fi
    fi
  else
    log "  ❌ Failed to retrieve historical data: $HISTORY_RESPONSE"
  fi

  # Step 6: Verify UI displays data properly
  log "Step 6: Verifying UI data display..."

  # Access monitoring dashboard to check data display
  DASHBOARD_RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/dashboard.html \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Accept: text/html,application/xhtml+xml" \
    "$API_BASE_URL/monitoring")

  if [[ "$DASHBOARD_RESPONSE" == "200" ]]; then
    log "  ✅ Successfully accessed monitoring dashboard"

    # Check if temperature value appears in the dashboard HTML
    if grep -q "$TEMP_VALUE" /tmp/dashboard.html; then
      log "  ✅ Temperature value appears in dashboard"
    else
      log "  ⚠️ Temperature value may not be displayed in dashboard"
    fi

    # Check if device name appears in the dashboard HTML
    if grep -q "$TEST_DEVICE_NAME" /tmp/dashboard.html; then
      log "  ✅ Device name appears in dashboard"
    else
      log "  ⚠️ Device name may not be displayed in dashboard"
    fi
  else
    log "  ❌ Failed to access monitoring dashboard (HTTP $DASHBOARD_RESPONSE)"
  fi
fi

# Test 3: Recovery Simulation Test
log "\n--- Test 3: Recovery Simulation Test ---"

# Step 1: Simulate a brief service disruption
log "Step 1: Simulating service disruption..."

# Force a configuration reload (which should cause minimal disruption)
RELOAD_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/config/reload")

# Wait briefly for the service to recover
log "Waiting 5 seconds for service to stabilize..."
sleep 5

# Step 2: Verify all components are functioning after disruption
log "Step 2: Verifying system functionality after disruption..."

# Check health endpoint
HEALTH_RESPONSE=$(curl -s "$API_BASE_URL/health")
HEALTH_STATUS=$(echo $HEALTH_RESPONSE | jq -r '.status')

if [[ "$HEALTH_STATUS" == "healthy" ]]; then
  log "  ✅ Health endpoint responding normally"
else
  log "  ❌ Health endpoint not responding normally: $HEALTH_RESPONSE"
fi

# Check device listing
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")

if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  log "  ✅ Device listing functioning normally"
else
  log "  ❌ Device listing not functioning normally: $DEVICES_RESPONSE"
fi

# Check temperature data
if [[ -n "$TEST_DEVICE_ID" ]]; then
  TEMP_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")

  if [[ $(echo $TEMP_RESPONSE | jq 'has("temperature")') == "true" ]]; then
    log "  ✅ Temperature data retrieval functioning normally"
  else
    log "  ❌ Temperature data retrieval not functioning normally: $TEMP_RESPONSE"
  fi
fi

# Step 3: Force a data sync to ensure all components are communicating
log "Step 3: Forcing data sync to verify component communication..."
SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")

if [[ $(echo $SYNC_RESPONSE | jq -r '.status') == "success" ]]; then
  log "  ✅ Data sync functioning normally"
else
  log "  ❌ Data sync not functioning normally: $SYNC_RESPONSE"
fi

# Test 4: Final Approval Checklist
log "\n--- Test 4: Final Approval Checklist ---"

# 1. API Functionality
log "1. API Functionality"
if [[ "$HEALTH_STATUS" == "healthy" ]]; then
  log "  ✅ API is functioning"
else
  log "  ❌ API is not functioning properly"
fi

# 2. ThermoWorks Integration
log "2. ThermoWorks Integration"
if [[ -n "$TEST_DEVICE_ID" && $(echo $TEMP_RESPONSE | jq 'has("temperature")') == "true" ]]; then
  log "  ✅ ThermoWorks integration is functioning"
else
  log "  ❌ ThermoWorks integration is not functioning properly"
fi

# 3. Home Assistant Integration
log "3. Home Assistant Integration"
if [[ -n "$HA_TOKEN" && "$ENTITY_STATE" != "null" && -n "$ENTITY_STATE" ]]; then
  log "  ✅ Home Assistant integration is functioning"
else
  log "  ❌ Home Assistant integration could not be verified"
fi

# 4. Data Storage
log "4. Data Storage"
if [[ $(echo $HISTORY_RESPONSE | jq 'type') == "array" && $POINTS_COUNT -gt 0 ]]; then
  log "  ✅ Data storage is functioning"
else
  log "  ❌ Data storage is not functioning properly"
fi

# 5. UI Functionality
log "5. UI Functionality"
if [[ "$DASHBOARD_RESPONSE" == "200" ]]; then
  log "  ✅ UI is functioning"
else
  log "  ❌ UI is not functioning properly"
fi

# 6. Recovery & Resilience
log "6. Recovery & Resilience"
RECOVERY_SUCCESS=true
if [[ "$HEALTH_STATUS" != "healthy" || $(echo $DEVICES_RESPONSE | jq 'type') != "array" ]]; then
  RECOVERY_SUCCESS=false
fi

if [[ "$RECOVERY_SUCCESS" == "true" ]]; then
  log "  ✅ System demonstrates recovery & resilience"
else
  log "  ❌ System does not demonstrate adequate recovery & resilience"
fi

# Summary
log "\n=== Final Integration Test Summary ==="
log "Tests completed at $(date)"
log "Results logged to $LOG_FILE"

# Calculate success rate
SUCCESSES=$(grep -c "✅" $LOG_FILE)
WARNINGS=$(grep -c "⚠️" $LOG_FILE)
FAILURES=$(grep -c "❌" $LOG_FILE)

log "Successes: $SUCCESSES"
log "Warnings: $WARNINGS"
log "Failures: $FAILURES"

# Final Go/No-Go Decision
if [[ $FAILURES -eq 0 && $TRACKS_FAILED -eq 0 ]]; then
  log "\n✅ ALL INTEGRATION TESTS PASSED - System is READY FOR PRODUCTION"
  exit 0
elif [[ $FAILURES -le 2 && $TRACKS_FAILED -le 1 ]]; then
  log "\n⚠️ PARTIAL SUCCESS - System has minor issues to address before production"
  exit 1
else
  log "\n❌ INTEGRATION TESTS FAILED - System NOT READY for production"
  exit 2
fi
