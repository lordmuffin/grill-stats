#!/bin/bash
# =======================================================================
# Home Assistant Integration & Data Storage Test Script
# 
# Purpose: Verify Home Assistant sensor creation, data synchronization
#          and data storage mechanisms
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
HA_URL=$(curl -s "$API_BASE_URL/api/config" | jq -r '.homeassistant_url // "http://homeassistant:8123"')
LOG_FILE="/tmp/grill-stats-ha-test-$(date +%Y%m%d%H%M%S).log"
AUTH_TOKEN=""  # Will be set after login

# Test Credentials - these should be configured before running
TEST_EMAIL="admin@grill-stats.lab.apj.dev"
TEST_PASSWORD="admin1234"  # Replace with appropriate test credentials

# Home Assistant token - needs to be provided
HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJncmlsbC1zdGF0cyIsInN1YiI6ImhvbWVhc3Npc3RhbnQifQ.example"  # Home Assistant long-lived access token

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

log "=== Starting Home Assistant Integration & Data Storage Test ==="
log "Target environment: $API_BASE_URL"
log "Home Assistant URL: $HA_URL"
log "Log file: $LOG_FILE"

# Authentication
if ! login; then
  log "❌ Authentication test failed, cannot proceed with authorized endpoints"
  exit 1
fi

# Test 1: Home Assistant Connection Test
log "\n--- Test 1: Home Assistant Connection Test ---"
HA_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/homeassistant/test")
HA_STATUS=$(echo $HA_RESPONSE | jq -r '.status')

if [[ "$HA_STATUS" == "connected" ]]; then
  log "✅ Home Assistant connection successful"
  log "  Message: $(echo $HA_RESPONSE | jq -r '.message')"
else
  log "❌ Home Assistant connection failed: $HA_RESPONSE"
  log "❌ Subsequent tests may fail due to connection issues"
fi

# Test 2: Get Devices and Identify Associated HA Sensors
log "\n--- Test 2: Identifying ThermoWorks Devices and HA Sensors ---"
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")

if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  DEVICE_COUNT=$(echo $DEVICES_RESPONSE | jq '. | length')
  log "Found $DEVICE_COUNT ThermoWorks devices"
  
  # Store test device info
  if [[ $DEVICE_COUNT -gt 0 ]]; then
    TEST_DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r '.[0].id')
    TEST_DEVICE_NAME=$(echo $DEVICES_RESPONSE | jq -r '.[0].name')
    log "Using device for testing: $TEST_DEVICE_NAME (ID: $TEST_DEVICE_ID)"
    
    # Calculate expected HA entity ID
    SENSOR_NAME="thermoworks_$(echo $TEST_DEVICE_NAME | tr 'A-Z ' 'a-z_')"
    log "Expected Home Assistant sensor name: $SENSOR_NAME"
  else
    log "⚠️ No devices found. Some tests will be skipped."
    TEST_DEVICE_ID=""
    SENSOR_NAME=""
  fi
else
  log "❌ Failed to retrieve device list: $DEVICES_RESPONSE"
  exit 1
fi

# Test 3: Verify Sensor Creation in Home Assistant
log "\n--- Test 3: Verify Sensor Creation in Home Assistant ---"

if [[ -n "$SENSOR_NAME" && -n "$HA_TOKEN" ]]; then
  # Check if sensor exists in Home Assistant
  HA_ENTITY_RESPONSE=$(curl -s -H "Authorization: Bearer $HA_TOKEN" \
    "$HA_URL/api/states/sensor.$SENSOR_NAME")
  
  ENTITY_STATE=$(echo $HA_ENTITY_RESPONSE | jq -r '.state')
  
  if [[ "$ENTITY_STATE" != "null" && -n "$ENTITY_STATE" ]]; then
    log "✅ Sensor exists in Home Assistant: sensor.$SENSOR_NAME"
    log "  Current state: $ENTITY_STATE"
    log "  Last updated: $(echo $HA_ENTITY_RESPONSE | jq -r '.last_updated')"
    
    # Verify attributes
    ATTRIBUTES=$(echo $HA_ENTITY_RESPONSE | jq -r '.attributes')
    log "  Sensor attributes:"
    log "    Device ID: $(echo $ATTRIBUTES | jq -r '.device_id // "Not set"')"
    log "    Friendly name: $(echo $ATTRIBUTES | jq -r '.friendly_name // "Not set"')"
    log "    Unit of measurement: $(echo $ATTRIBUTES | jq -r '.unit_of_measurement // "Not set"')"
    log "    Device class: $(echo $ATTRIBUTES | jq -r '.device_class // "Not set"')"
    log "    Battery level: $(echo $ATTRIBUTES | jq -r '.battery_level // "Not set"')"
    log "    Signal strength: $(echo $ATTRIBUTES | jq -r '.signal_strength // "Not set"')"
    
    # Verify expected attributes
    MISSING_ATTRS=0
    for attr in "device_id" "friendly_name" "unit_of_measurement"; do
      if [[ $(echo $ATTRIBUTES | jq "has(\"$attr\")") != "true" ]]; then
        log "  ⚠️ Missing expected attribute: $attr"
        MISSING_ATTRS=$((MISSING_ATTRS + 1))
      fi
    done
    
    if [[ $MISSING_ATTRS -eq 0 ]]; then
      log "  ✅ All required attributes present"
    fi
  else
    log "❌ Sensor does not exist in Home Assistant: sensor.$SENSOR_NAME"
    log "  Response: $HA_ENTITY_RESPONSE"
  fi
else
  log "⚠️ Skipping Home Assistant sensor verification (missing device or HA token)"
fi

# Test 4: Trigger Data Sync and Verify Update
log "\n--- Test 4: Trigger Data Sync and Verify Update ---"

if [[ -n "$SENSOR_NAME" && -n "$HA_TOKEN" ]]; then
  # Get current state for comparison
  BEFORE_SYNC=$(curl -s -H "Authorization: Bearer $HA_TOKEN" \
    "$HA_URL/api/states/sensor.$SENSOR_NAME")
  BEFORE_STATE=$(echo $BEFORE_SYNC | jq -r '.state')
  BEFORE_LAST_UPDATED=$(echo $BEFORE_SYNC | jq -r '.last_updated')
  
  log "State before sync: $BEFORE_STATE (updated: $BEFORE_LAST_UPDATED)"
  
  # Trigger manual sync
  log "Triggering manual sync..."
  SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")
  
  if [[ $(echo $SYNC_RESPONSE | jq -r '.status') == "success" ]]; then
    log "✅ Manual sync triggered successfully"
    
    # Wait for sync to complete
    log "Waiting 10 seconds for sync to complete..."
    sleep 10
    
    # Check updated state
    AFTER_SYNC=$(curl -s -H "Authorization: Bearer $HA_TOKEN" \
      "$HA_URL/api/states/sensor.$SENSOR_NAME")
    AFTER_STATE=$(echo $AFTER_SYNC | jq -r '.state')
    AFTER_LAST_UPDATED=$(echo $AFTER_SYNC | jq -r '.last_updated')
    
    log "State after sync: $AFTER_STATE (updated: $AFTER_LAST_UPDATED)"
    
    if [[ "$BEFORE_LAST_UPDATED" != "$AFTER_LAST_UPDATED" ]]; then
      log "✅ Sensor was updated during sync"
    else
      log "⚠️ Sensor does not appear to have been updated during sync"
    fi
  else
    log "❌ Manual sync failed: $SYNC_RESPONSE"
  fi
else
  log "⚠️ Skipping sync verification (missing device or HA token)"
fi

# Test 5: Verify Entity Naming Compliance
log "\n--- Test 5: Verify Entity Naming Compliance ---"

if [[ -n "$HA_TOKEN" ]]; then
  # Get all entities that match our naming pattern
  HA_STATES=$(curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/states")
  THERMOWORKS_ENTITIES=$(echo $HA_STATES | jq '[.[] | select(.entity_id | startswith("sensor.thermoworks_"))]')
  ENTITY_COUNT=$(echo $THERMOWORKS_ENTITIES | jq '. | length')
  
  log "Found $ENTITY_COUNT ThermoWorks sensor entities in Home Assistant"
  
  if [[ $ENTITY_COUNT -gt 0 ]]; then
    # Check naming convention for each entity
    NAMING_ISSUES=0
    
    echo $THERMOWORKS_ENTITIES | jq -c '.[]' | while read -r entity; do
      ENTITY_ID=$(echo $entity | jq -r '.entity_id')
      FRIENDLY_NAME=$(echo $entity | jq -r '.attributes.friendly_name // "Unknown"')
      
      log "  Entity: $ENTITY_ID (\"$FRIENDLY_NAME\")"
      
      # Check if name follows conventions (lowercase, underscores)
      if [[ ! $ENTITY_ID =~ ^sensor\.thermoworks_[a-z0-9_]+$ ]]; then
        log "  ⚠️ Entity ID does not follow naming convention: $ENTITY_ID"
        NAMING_ISSUES=$((NAMING_ISSUES + 1))
      fi
    done
    
    if [[ $NAMING_ISSUES -eq 0 ]]; then
      log "✅ All entities follow proper naming conventions"
    else
      log "⚠️ Found $NAMING_ISSUES entities with naming issues"
    fi
  fi
else
  log "⚠️ Skipping entity naming verification (missing HA token)"
fi

# Test 6: Test Redis Caching (if available)
log "\n--- Test 6: Redis Caching Test ---"

# Get monitoring data which should use cache if available
MONITORING_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data")

if [[ $(echo $MONITORING_RESPONSE | jq -r '.status') == "success" ]]; then
  log "✅ Monitoring data retrieved successfully"
  PROBE_COUNT=$(echo $MONITORING_RESPONSE | jq -r '.data.count')
  log "  Found $PROBE_COUNT temperature probes"
  
  # Look for cache indicators in the response
  CACHE_SOURCES=$(echo $MONITORING_RESPONSE | jq -r '.data.probes[].source' | grep -c "cache" || true)
  
  if [[ $CACHE_SOURCES -gt 0 ]]; then
    log "✅ Redis cache is being used ($CACHE_SOURCES cached readings)"
  else
    log "⚠️ No cached readings detected - Redis may not be configured or needed"
  fi
  
  # Make subsequent request to test cache performance
  START_TIME=$(date +%s.%N)
  curl -s -o /dev/null -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data"
  END_TIME=$(date +%s.%N)
  
  # Calculate execution time
  EXEC_TIME=$(echo "$END_TIME - $START_TIME" | bc)
  
  log "  Second request completed in ${EXEC_TIME}s (should be faster if caching works)"
else
  log "❌ Failed to retrieve monitoring data: $(echo $MONITORING_RESPONSE | jq -r '.message')"
fi

# Test 7: Check for InfluxDB Integration
log "\n--- Test 7: InfluxDB Integration Check ---"

# We can't directly test InfluxDB, but we can look for related endpoints and configs
INFLUX_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/config")

# Look for InfluxDB configuration indicators
if [[ $(echo $INFLUX_RESPONSE | jq -r '.influxdb_enabled // "false"') == "true" ]]; then
  log "✅ InfluxDB integration is enabled"
  log "  Host: $(echo $INFLUX_RESPONSE | jq -r '.influxdb_host // "Unknown"')"
  log "  Database: $(echo $INFLUX_RESPONSE | jq -r '.influxdb_db // "Unknown"')"
else
  log "⚠️ No evidence of InfluxDB integration in the configuration"
fi

# Try to access historical data (which might come from InfluxDB if configured)
if [[ -n "$TEST_DEVICE_ID" ]]; then
  START_TIME=$(date -u -d "24 hours ago" +"%Y-%m-%dT%H:%M:%S")
  END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S")
  
  HISTORY_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$START_TIME&end=$END_TIME")
  
  if [[ $(echo $HISTORY_RESPONSE | jq 'type') == "array" ]]; then
    DATA_POINTS=$(echo $HISTORY_RESPONSE | jq '. | length')
    log "  Retrieved $DATA_POINTS historical data points for the last 24 hours"
    
    if [[ $DATA_POINTS -gt 0 ]]; then
      log "✅ Historical data storage is working"
      
      # Check data resolution to infer if data compression/downsampling is in place
      if [[ $DATA_POINTS -gt 1 ]]; then
        # Get first and second timestamp
        FIRST_TS=$(echo $HISTORY_RESPONSE | jq -r '.[0].timestamp')
        SECOND_TS=$(echo $HISTORY_RESPONSE | jq -r '.[1].timestamp')
        
        # Convert to seconds
        FIRST_SEC=$(date -d "$FIRST_TS" +%s)
        SECOND_SEC=$(date -d "$SECOND_TS" +%s)
        
        # Calculate difference in minutes
        DIFF_MIN=$(( (SECOND_SEC - FIRST_SEC) / 60 ))
        
        log "  Data resolution: ~$DIFF_MIN minutes between points"
        
        if [[ $DIFF_MIN -le 5 ]]; then
          log "  ✅ High-resolution data storage detected (intervals ≤ 5 minutes)"
        else
          log "  ⚠️ Lower-resolution data detected (intervals of $DIFF_MIN minutes)"
        fi
      fi
    else
      log "⚠️ No historical data points found"
    fi
  else
    log "❌ Failed to retrieve historical data"
  fi
else
  log "⚠️ No test device available for historical data check"
fi

# Test 8: Check Data Retention
log "\n--- Test 8: Data Retention Check ---"

# Try to get data from different time periods to check retention
if [[ -n "$TEST_DEVICE_ID" ]]; then
  # Check last week
  WEEK_START=$(date -u -d "7 days ago" +"%Y-%m-%dT%H:%M:%S")
  WEEK_END=$(date -u -d "6 days ago" +"%Y-%m-%dT%H:%M:%S")
  
  WEEK_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$WEEK_START&end=$WEEK_END")
  
  if [[ $(echo $WEEK_RESPONSE | jq 'type') == "array" ]]; then
    WEEK_POINTS=$(echo $WEEK_RESPONSE | jq '. | length')
    log "  Data from 7 days ago: $WEEK_POINTS points"
    
    if [[ $WEEK_POINTS -gt 0 ]]; then
      log "  ✅ Weekly data retention confirmed"
    else
      log "  ⚠️ No data found from 7 days ago"
    fi
  fi
  
  # Try to get month-old data if available
  MONTH_START=$(date -u -d "30 days ago" +"%Y-%m-%dT%H:%M:%S")
  MONTH_END=$(date -u -d "29 days ago" +"%Y-%m-%dT%H:%M:%S")
  
  MONTH_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    "$API_BASE_URL/devices/$TEST_DEVICE_ID/history?start=$MONTH_START&end=$MONTH_END")
  
  if [[ $(echo $MONTH_RESPONSE | jq 'type') == "array" ]]; then
    MONTH_POINTS=$(echo $MONTH_RESPONSE | jq '. | length')
    log "  Data from 30 days ago: $MONTH_POINTS points"
    
    if [[ $MONTH_POINTS -gt 0 ]]; then
      log "  ✅ Monthly data retention confirmed"
    else
      log "  ⚠️ No data found from 30 days ago"
    fi
  fi
else
  log "⚠️ No test device available for retention check"
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