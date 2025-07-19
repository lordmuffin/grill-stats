#!/bin/bash
# =======================================================================
# ThermoWorks Integration Test Script
#
# Purpose: Verify ThermoWorks API integration, authentication, and data
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
LOG_FILE="/tmp/grill-stats-thermoworks-test-$(date +%Y%m%d%H%M%S).log"
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

log "=== Starting ThermoWorks Integration Test ==="
log "Target environment: $API_BASE_URL"
log "Log file: $LOG_FILE"

# Authentication
if ! login; then
  log "❌ Authentication test failed, cannot proceed with authorized endpoints"
  exit 1
fi

# Test 1: ThermoWorks API Key Verification
log "\n--- Test 1: ThermoWorks API Key Verification ---"
# Get list of devices to verify API key is working
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")

if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  log "✅ ThermoWorks API key is valid (able to fetch devices)"
  DEVICE_COUNT=$(echo $DEVICES_RESPONSE | jq '. | length')
  log "  Found $DEVICE_COUNT devices"

  # Store first device ID for subsequent tests
  if [[ $DEVICE_COUNT -gt 0 ]]; then
    TEST_DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r '.[0].id')
    log "  Using device ID: $TEST_DEVICE_ID for further tests"
  else
    log "⚠️ No devices found. Some tests may be skipped."
    TEST_DEVICE_ID=""
  fi
else
  log "❌ ThermoWorks API key appears invalid: $DEVICES_RESPONSE"
  exit 1
fi

# Test 2: Device Authentication Flow
log "\n--- Test 2: Device Authentication Flow ---"
# Make a request that will trigger the token refresh flow
AUTH_TEST_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/config")

if [[ $(echo $AUTH_TEST_RESPONSE | jq 'has("environment")') == "true" ]]; then
  log "✅ Authentication flow works correctly"
  log "  Environment: $(echo $AUTH_TEST_RESPONSE | jq -r '.environment')"
  log "  Version: $(echo $AUTH_TEST_RESPONSE | jq -r '.version')"
else
  log "❌ Authentication flow test failed: $AUTH_TEST_RESPONSE"
fi

# Test 3: Device Discovery
log "\n--- Test 3: Device Discovery ---"
# Get details about each device to verify correct detection
log "Examining discovered devices..."

if [[ $DEVICE_COUNT -gt 0 ]]; then
  echo $DEVICES_RESPONSE | jq -c '.[]' | while read -r device; do
    DEVICE_ID=$(echo $device | jq -r '.id')
    DEVICE_NAME=$(echo $device | jq -r '.name')
    DEVICE_MODEL=$(echo $device | jq -r '.model // "Unknown"')
    FIRMWARE=$(echo $device | jq -r '.firmware_version // "Unknown"')

    log "Device: $DEVICE_NAME (ID: $DEVICE_ID)"
    log "  Model: $DEVICE_MODEL"
    log "  Firmware: $FIRMWARE"

    # Get temperature data to verify probe details
    if [[ -n "$DEVICE_ID" ]]; then
      TEMP_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$DEVICE_ID/temperature")

      # Check if we got valid temperature data
      if [[ $(echo $TEMP_RESPONSE | jq 'has("temperature")') == "true" ]]; then
        log "  ✅ Successfully retrieved temperature data"
        log "    Current Temperature: $(echo $TEMP_RESPONSE | jq -r '.temperature')°$(echo $TEMP_RESPONSE | jq -r '.unit // "F"')"
        log "    Battery Level: $(echo $TEMP_RESPONSE | jq -r '.battery_level // "Unknown"')%"
        log "    Signal Strength: $(echo $TEMP_RESPONSE | jq -r '.signal_strength // "Unknown"')%"
      else
        log "  ❌ Failed to retrieve temperature data"
      fi
    fi
  done
  log "✅ Device discovery test completed"
else
  log "⚠️ No devices available to test discovery functionality"
fi

# Test 4: Multi-Probe Support
log "\n--- Test 4: Multi-Probe Support ---"

if [[ -n "$TEST_DEVICE_ID" ]]; then
  # Try to get probe-specific data if available
  DEVICE_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")

  # Check if there are multiple probes (look for probe_id field or array of probes)
  PROBE_IDS=$(echo $DEVICE_RESPONSE | jq -r '.probes[].id' 2>/dev/null)

  if [[ -n "$PROBE_IDS" ]]; then
    log "✅ Device has multiple probes"
    log "Probe IDs: $PROBE_IDS"

    # Test each probe
    echo $DEVICE_RESPONSE | jq -c '.probes[]' | while read -r probe; do
      PROBE_ID=$(echo $probe | jq -r '.id')
      PROBE_TYPE=$(echo $probe | jq -r '.type // "Unknown"')
      PROBE_TEMP=$(echo $probe | jq -r '.temperature')

      log "  Probe $PROBE_ID ($PROBE_TYPE): $PROBE_TEMP°$(echo $DEVICE_RESPONSE | jq -r '.unit // "F"')"
    done
  else
    # Single probe device
    log "⚠️ Device appears to have only a single probe"
    log "  Temperature: $(echo $DEVICE_RESPONSE | jq -r '.temperature')°$(echo $DEVICE_RESPONSE | jq -r '.unit // "F"')"
  fi
else
  log "⚠️ No test device available to verify multi-probe support"
fi

# Test 5: Polling Configuration
log "\n--- Test 5: Polling Configuration ---"

# Make multiple requests to test polling behavior
log "Testing polling behavior with multiple requests..."

for i in {1..3}; do
  START_TIME=$(date +%s.%N)
  curl -s -o /dev/null -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices"
  END_TIME=$(date +%s.%N)

  # Calculate execution time
  EXEC_TIME=$(echo "$END_TIME - $START_TIME" | bc)

  log "  Request $i completed in ${EXEC_TIME}s"

  # Wait briefly between requests
  sleep 2
done

# Test manual sync to verify polling mechanism
SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")

if [[ $(echo $SYNC_RESPONSE | jq -r '.status') == "success" ]]; then
  log "✅ Manual sync successful - polling mechanism functional"
else
  log "❌ Manual sync failed: $SYNC_RESPONSE"
fi

# Test 6: Error Recovery Mechanism
log "\n--- Test 6: Error Recovery Mechanism ---"

# Intentionally make a request to a non-existent device to test error handling
BAD_DEVICE_ID="TW-XXX-999"
ERROR_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$BAD_DEVICE_ID/temperature")

# Check how the application handles the error
if [[ $(echo $ERROR_RESPONSE | jq 'has("error")') == "true" || $(echo $ERROR_RESPONSE | jq 'has("message")') == "true" ]]; then
  log "✅ Application properly handles device errors"
  log "  Error response: $(echo $ERROR_RESPONSE | jq -r '.message // .error')"
else
  log "⚠️ Unexpected error response format: $ERROR_RESPONSE"
fi

# Test immediately after to verify system recovers
if [[ -n "$TEST_DEVICE_ID" ]]; then
  RECOVERY_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")

  if [[ $(echo $RECOVERY_RESPONSE | jq 'has("temperature")') == "true" ]]; then
    log "✅ System successfully recovered after error"
    log "  Temperature: $(echo $RECOVERY_RESPONSE | jq -r '.temperature')°$(echo $RECOVERY_RESPONSE | jq -r '.unit // "F"')"
  else
    log "❌ System failed to recover after error: $RECOVERY_RESPONSE"
  fi
fi

# Test 7: Data Validation
log "\n--- Test 7: Data Validation ---"

if [[ -n "$TEST_DEVICE_ID" ]]; then
  # Get historical data to check for validation
  START_TIME=$(date -u -d "24 hours ago" +"%Y-%m-%dT%H:%M:%S")
  END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S")

  HISTORY_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$START_TIME&end=$END_TIME")

  if [[ $(echo $HISTORY_RESPONSE | jq 'type') == "array" ]]; then
    POINTS_COUNT=$(echo $HISTORY_RESPONSE | jq '. | length')
    log "Retrieved $POINTS_COUNT historical data points"

    # Check for obviously invalid readings (negative temps, extremely high temps)
    INVALID_COUNT=$(echo $HISTORY_RESPONSE | jq '[.[] | select(.temperature < -20 or .temperature > 1000)] | length')

    if [[ $INVALID_COUNT -eq 0 ]]; then
      log "✅ No obviously invalid temperature readings detected"
    else
      log "⚠️ Found $INVALID_COUNT potentially invalid temperature readings"
    fi

    # Check for data gaps
    if [[ $POINTS_COUNT -gt 1 ]]; then
      # Extract timestamps
      TIMESTAMPS_FILE="/tmp/timestamps.txt"
      echo $HISTORY_RESPONSE | jq -r '.[].timestamp' > $TIMESTAMPS_FILE

      # Calculate average gap between readings in minutes
      PREV_TS=""
      SUM_GAPS=0
      COUNT_GAPS=0

      while read TS; do
        if [[ -n "$PREV_TS" ]]; then
          TS_SEC=$(date -d "$TS" +%s)
          PREV_TS_SEC=$(date -d "$PREV_TS" +%s)
          GAP_MIN=$(( (TS_SEC - PREV_TS_SEC) / 60 ))

          SUM_GAPS=$((SUM_GAPS + GAP_MIN))
          COUNT_GAPS=$((COUNT_GAPS + 1))
        fi
        PREV_TS=$TS
      done < $TIMESTAMPS_FILE

      if [[ $COUNT_GAPS -gt 0 ]]; then
        AVG_GAP=$((SUM_GAPS / COUNT_GAPS))
        log "Average gap between readings: ${AVG_GAP} minutes"

        if [[ $AVG_GAP -le 10 ]]; then
          log "✅ Polling frequency appears adequate (avg. ${AVG_GAP} min)"
        else
          log "⚠️ Polling frequency may be too low (avg. ${AVG_GAP} min)"
        fi
      fi

      rm $TIMESTAMPS_FILE
    fi
  else
    log "⚠️ Unable to retrieve historical data for validation testing"
  fi
else
  log "⚠️ No test device available for data validation"
fi

# Test 8: Disconnected Probe Detection
log "\n--- Test 8: Disconnected Probe Detection ---"
# This is difficult to test without physically disconnecting a probe
# We'll look for any error status indicators in the device data

if [[ -n "$TEST_DEVICE_ID" ]]; then
  DEVICE_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices/$TEST_DEVICE_ID/temperature")

  # Check for status field or other error indicators
  CONNECTION_STATUS=$(echo $DEVICE_RESPONSE | jq -r '.status // .connection_status // "unknown"')

  if [[ "$CONNECTION_STATUS" == "connected" || "$CONNECTION_STATUS" == "online" ]]; then
    log "✅ Device connection status tracking is functional"
    log "  Current status: $CONNECTION_STATUS"
  elif [[ "$CONNECTION_STATUS" != "unknown" ]]; then
    log "⚠️ Device shows non-connected status: $CONNECTION_STATUS"
  else
    log "⚠️ Cannot determine if disconnection detection is supported"
  fi

  # Check if temperature is null or an error value
  TEMP_VALUE=$(echo $DEVICE_RESPONSE | jq -r '.temperature')

  if [[ "$TEMP_VALUE" == "null" || "$TEMP_VALUE" == "" ]]; then
    log "⚠️ Temperature reading is null - possible disconnected probe"
  fi
else
  log "⚠️ No test device available for disconnection testing"
fi

# Summary
log "\n=== Test Summary ==="
log "Tests completed at $(date)"
log "Results logged to $LOG_FILE"

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
