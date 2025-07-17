#!/bin/bash
# =======================================================================
# Performance & Reliability Test Script
# 
# Purpose: Test system performance, stability, and reliability under
#          various load conditions and over extended time periods
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
LOG_FILE="/tmp/grill-stats-performance-test-$(date +%Y%m%d%H%M%S).log"
TEST_DURATION=${TEST_DURATION:-12} # Test duration in hours, can be overridden
REQUEST_INTERVAL=${REQUEST_INTERVAL:-10} # Seconds between requests
LOAD_TEST_DURATION=${LOAD_TEST_DURATION:-10} # Minutes for load test
CONCURRENCY=${CONCURRENCY:-10} # Number of concurrent requests for load test
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

# Function to make API request and measure response time
make_request() {
  local endpoint=$1
  local id=$2
  
  START_TIME=$(date +%s.%N)
  RESPONSE=$(curl -s -w "%{http_code}" -o "/tmp/response_${id}.json" \
    -H "Authorization: Bearer $AUTH_TOKEN" "${API_BASE_URL}${endpoint}")
  END_TIME=$(date +%s.%N)
  
  # Calculate response time in milliseconds
  RESP_TIME=$(echo "($END_TIME - $START_TIME) * 1000" | bc | cut -d'.' -f1)
  
  # Check for success (HTTP 200)
  if [[ "$RESPONSE" == "200" ]]; then
    STATUS="SUCCESS"
  else
    STATUS="FAILED ($RESPONSE)"
  fi
  
  echo "$RESP_TIME $STATUS"
}

# -----------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------

log "=== Starting Performance & Reliability Test ==="
log "Target environment: $API_BASE_URL"
log "Test duration: $TEST_DURATION hours"
log "Log file: $LOG_FILE"

# Authentication
if ! login; then
  log "❌ Authentication test failed, cannot proceed with authorized endpoints"
  exit 1
fi

# Test 1: Normal Load Test
log "\n--- Test 1: Normal Load Baseline ---"

# Define test endpoints
ENDPOINTS=(
  "/health"
  "/devices"
  "/api/config"
  "/api/monitoring/data"
  "/homeassistant/test"
)

# Get a list of device IDs for testing
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")
DEVICE_IDS=()

if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  for i in {0..4}; do  # Get up to 5 device IDs
    DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r ".[$i].id // empty")
    if [[ -n "$DEVICE_ID" ]]; then
      DEVICE_IDS+=($DEVICE_ID)
    fi
  done
fi

log "Found ${#DEVICE_IDS[@]} devices for testing"

# Add device-specific endpoints if available
if [[ ${#DEVICE_IDS[@]} -gt 0 ]]; then
  DEVICE_ID=${DEVICE_IDS[0]}
  ENDPOINTS+=("/devices/$DEVICE_ID/temperature")
  ENDPOINTS+=("/devices/$DEVICE_ID/history?start=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S)&end=$(date -u +%Y-%m-%dT%H:%M:%S)")
fi

# Baseline performance test
log "Running baseline performance test with ${#ENDPOINTS[@]} endpoints..."
log "| Endpoint | Response Time (ms) | Status |"
log "|----------|-------------------|--------|"

for endpoint in "${ENDPOINTS[@]}"; do
  RESULT=$(make_request "$endpoint" "baseline")
  RESP_TIME=$(echo $RESULT | cut -d' ' -f1)
  STATUS=$(echo $RESULT | cut -d' ' -f2-)
  
  log "| $endpoint | $RESP_TIME ms | $STATUS |"
done

# Test 2: Sustained Load Test
log "\n--- Test 2: Sustained Load Test (${LOAD_TEST_DURATION} minutes) ---"

log "Running sustained load test with $CONCURRENCY concurrent users for $LOAD_TEST_DURATION minutes..."
log "Starting at $(date)"

# Create results directory
RESULTS_DIR="/tmp/loadtest_results"
mkdir -p $RESULTS_DIR

# Function for single user load test
run_user_load() {
  local user_id=$1
  local iterations=$2
  local result_file="${RESULTS_DIR}/user_${user_id}.txt"
  
  # Clear result file
  echo "" > $result_file
  
  for ((i=1; i<=iterations; i++)); do
    # Pick random endpoint
    ENDPOINT=${ENDPOINTS[$RANDOM % ${#ENDPOINTS[@]}]}
    
    # Make request and record result
    RESULT=$(make_request "$ENDPOINT" "load_${user_id}_${i}")
    RESP_TIME=$(echo $RESULT | cut -d' ' -f1)
    STATUS=$(echo $RESULT | cut -d' ' -f2-)
    
    echo "$i,$ENDPOINT,$RESP_TIME,$STATUS" >> $result_file
    
    # Random delay between 1-5 seconds
    sleep $(( ( RANDOM % 5 ) + 1 ))
  done
}

# Calculate iterations based on duration
ITERATIONS=$(( LOAD_TEST_DURATION * 60 / 5 )) # Assume ~5 seconds per iteration

# Start concurrent user processes
for ((u=1; u<=CONCURRENCY; u++)); do
  log "Starting user $u with $ITERATIONS iterations"
  run_user_load $u $ITERATIONS &
done

# Wait for all processes to complete
wait
log "Load test completed at $(date)"

# Analyze results
log "\n--- Load Test Results ---"
TOTAL_REQUESTS=0
TOTAL_SUCCESS=0
TOTAL_FAILURE=0
SUM_RESPONSE_TIME=0
MAX_RESPONSE_TIME=0
MIN_RESPONSE_TIME=999999

for result_file in ${RESULTS_DIR}/user_*.txt; do
  while IFS=, read -r iter endpoint resp_time status; do
    if [[ -n "$resp_time" ]]; then
      TOTAL_REQUESTS=$((TOTAL_REQUESTS + 1))
      
      if [[ "$status" == "SUCCESS" ]]; then
        TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
      else
        TOTAL_FAILURE=$((TOTAL_FAILURE + 1))
      fi
      
      SUM_RESPONSE_TIME=$((SUM_RESPONSE_TIME + resp_time))
      
      if [[ $resp_time -gt $MAX_RESPONSE_TIME ]]; then
        MAX_RESPONSE_TIME=$resp_time
      fi
      
      if [[ $resp_time -lt $MIN_RESPONSE_TIME ]]; then
        MIN_RESPONSE_TIME=$resp_time
      fi
    fi
  done < $result_file
done

# Calculate averages
if [[ $TOTAL_REQUESTS -gt 0 ]]; then
  AVG_RESPONSE_TIME=$(( SUM_RESPONSE_TIME / TOTAL_REQUESTS ))
  SUCCESS_RATE=$(( TOTAL_SUCCESS * 100 / TOTAL_REQUESTS ))
else
  AVG_RESPONSE_TIME=0
  SUCCESS_RATE=0
fi

log "Total Requests: $TOTAL_REQUESTS"
log "Successful Requests: $TOTAL_SUCCESS ($SUCCESS_RATE%)"
log "Failed Requests: $TOTAL_FAILURE"
log "Average Response Time: $AVG_RESPONSE_TIME ms"
log "Minimum Response Time: $MIN_RESPONSE_TIME ms"
log "Maximum Response Time: $MAX_RESPONSE_TIME ms"

if [[ $SUCCESS_RATE -ge 95 ]]; then
  log "✅ Load test passed with $SUCCESS_RATE% success rate"
else
  log "❌ Load test failed with only $SUCCESS_RATE% success rate"
fi

# Test 3: Long-Running Stability Test
log "\n--- Test 3: Long-Running Stability Test ($TEST_DURATION hours) ---"
log "Starting stability test at $(date)"

# Create stability test directory
STABILITY_DIR="/tmp/stability_results"
mkdir -p $STABILITY_DIR

# Calculate test parameters
END_TIME=$(( $(date +%s) + $TEST_DURATION * 3600 ))
CHECK_INTERVAL=$REQUEST_INTERVAL  # Seconds between checks
TOTAL_CHECKS=$(( TEST_DURATION * 3600 / CHECK_INTERVAL ))
COMPLETED_CHECKS=0
FAILED_CHECKS=0

log "Will run $TOTAL_CHECKS checks over $TEST_DURATION hours"
log "Check interval: $CHECK_INTERVAL seconds"

# Start stability monitoring
while [[ $(date +%s) -lt $END_TIME ]]; do
  CHECK_START=$(date +%s)
  COMPLETED_CHECKS=$((COMPLETED_CHECKS + 1))
  CHECK_TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
  RESULT_FILE="${STABILITY_DIR}/check_${COMPLETED_CHECKS}.txt"
  
  log "Running stability check $COMPLETED_CHECKS of $TOTAL_CHECKS at $CHECK_TIMESTAMP"
  
  # Run basic health check
  HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/health")
  HEALTH_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
  
  if [[ "$HEALTH_CODE" == "200" ]]; then
    log "  ✅ Health endpoint OK"
    echo "HEALTH,200,$(date +%s)" >> $RESULT_FILE
  else
    log "  ❌ Health endpoint failed: $HEALTH_CODE"
    echo "HEALTH,$HEALTH_CODE,$(date +%s)" >> $RESULT_FILE
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
  fi
  
  # Check devices endpoint (requires auth)
  DEVICES_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")
  DEVICES_CODE=$(echo "$DEVICES_RESPONSE" | tail -n1)
  
  if [[ "$DEVICES_CODE" == "200" ]]; then
    log "  ✅ Devices endpoint OK"
    echo "DEVICES,200,$(date +%s)" >> $RESULT_FILE
    
    # Check if token expired and we need to re-login
    DEVICES_BODY=$(echo "$DEVICES_RESPONSE" | head -n -1)
    if [[ "$DEVICES_BODY" == *"unauthorized"* || "$DEVICES_BODY" == *"Unauthorized"* ]]; then
      log "  ⚠️ Token expired, re-authenticating"
      login
    fi
  else
    log "  ❌ Devices endpoint failed: $DEVICES_CODE"
    echo "DEVICES,$DEVICES_CODE,$(date +%s)" >> $RESULT_FILE
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    
    # Try to re-authenticate on failure
    login
  fi
  
  # Check monitoring data
  MONITORING_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data")
  MONITORING_CODE=$(echo "$MONITORING_RESPONSE" | tail -n1)
  
  if [[ "$MONITORING_CODE" == "200" ]]; then
    log "  ✅ Monitoring data endpoint OK"
    echo "MONITORING,200,$(date +%s)" >> $RESULT_FILE
    
    # Extract number of probes for reporting
    MONITORING_BODY=$(echo "$MONITORING_RESPONSE" | head -n -1)
    PROBE_COUNT=$(echo $MONITORING_BODY | jq -r '.data.count // 0')
    log "    Found $PROBE_COUNT active probes"
  else
    log "  ❌ Monitoring data endpoint failed: $MONITORING_CODE"
    echo "MONITORING,$MONITORING_CODE,$(date +%s)" >> $RESULT_FILE
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
  fi
  
  # Every hour, check memory usage pattern
  if [[ $((COMPLETED_CHECKS % (3600 / CHECK_INTERVAL))) -eq 0 ]]; then
    log "  Running hourly memory check"
    
    # We can't directly check memory on remote host, but we can measure API response times
    # as a proxy for potential memory issues
    
    START_TIME=$(date +%s.%N)
    curl -s -o /dev/null -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data"
    END_TIME=$(date +%s.%N)
    
    # Calculate response time in milliseconds
    RESP_TIME=$(echo "($END_TIME - $START_TIME) * 1000" | bc | cut -d'.' -f1)
    
    log "    Monitoring data response time: $RESP_TIME ms"
    echo "MEMORY_CHECK,$RESP_TIME,$(date +%s)" >> $RESULT_FILE
  fi
  
  # Calculate completion percentage
  PCT_COMPLETE=$(( COMPLETED_CHECKS * 100 / TOTAL_CHECKS ))
  log "  Stability test $PCT_COMPLETE% complete ($COMPLETED_CHECKS/$TOTAL_CHECKS checks)"
  
  # Wait until next check interval
  CHECK_END=$(date +%s)
  CHECK_DURATION=$((CHECK_END - CHECK_START))
  WAIT_TIME=$((CHECK_INTERVAL - CHECK_DURATION))
  
  if [[ $WAIT_TIME -gt 0 ]]; then
    sleep $WAIT_TIME
  fi
done

# Analyze stability results
log "\n--- Stability Test Results ---"
log "Test completed at $(date)"
log "Total checks: $COMPLETED_CHECKS"
log "Failed checks: $FAILED_CHECKS"

if [[ $COMPLETED_CHECKS -gt 0 ]]; then
  STABILITY_RATE=$(( (COMPLETED_CHECKS - FAILED_CHECKS) * 100 / COMPLETED_CHECKS ))
  log "Stability rate: $STABILITY_RATE%"
  
  if [[ $STABILITY_RATE -ge 98 ]]; then
    log "✅ Stability test passed with $STABILITY_RATE% success rate"
  elif [[ $STABILITY_RATE -ge 90 ]]; then
    log "⚠️ Stability test borderline with $STABILITY_RATE% success rate"
  else
    log "❌ Stability test failed with only $STABILITY_RATE% success rate"
  fi
else
  log "❌ No stability checks completed"
fi

# Test 4: Recovery Test
log "\n--- Test 4: Recovery Test ---"
log "Testing system recovery after simulated failures"

# Test 4.1: Simulate network interruption with bad requests
log "Simulating network interruption with intentionally bad requests..."

for i in {1..10}; do
  # Make intentionally malformed request
  BAD_RESPONSE=$(curl -s -m 1 -w "%{http_code}" -o /dev/null "$API_BASE_URL/api/nonexistent_endpoint_${RANDOM}")
  log "  Bad request $i: HTTP $BAD_RESPONSE"
  
  # Minimal delay between bad requests
  sleep 0.5
done

# Test if system recovers
log "Checking if system recovers after bad requests..."
sleep 5  # Wait for system to recover

HEALTH_RESPONSE=$(curl -s "$API_BASE_URL/health")
HEALTH_STATUS=$(echo $HEALTH_RESPONSE | jq -r '.status')

if [[ "$HEALTH_STATUS" == "healthy" ]]; then
  log "✅ System recovered successfully after bad requests"
else
  log "❌ System failed to recover after bad requests"
fi

# Test 4.2: Test recovery after authentication failure
log "Testing recovery after authentication failure..."

# Intentionally use invalid token
INVALID_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
  -H "Authorization: Bearer INVALID_TOKEN" "$API_BASE_URL/devices")

log "  Invalid auth request: HTTP $INVALID_RESPONSE"

# Test proper re-authentication
log "  Re-authenticating..."
if login; then
  log "✅ Successfully re-authenticated after invalid token"
  
  # Verify can access protected endpoint
  VERIFY_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
    -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")
  
  if [[ "$VERIFY_RESPONSE" == "200" ]]; then
    log "✅ Successfully accessed protected endpoint after re-authentication"
  else
    log "❌ Failed to access protected endpoint after re-authentication"
  fi
else
  log "❌ Failed to re-authenticate after invalid token"
fi

# Test 4.3: Test forced sync recovery
log "Testing forced sync recovery..."

# Force a sync operation
SYNC_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/sync")
SYNC_STATUS=$(echo $SYNC_RESPONSE | jq -r '.status')

if [[ "$SYNC_STATUS" == "success" ]]; then
  log "✅ Forced sync operation successful"
  
  # Verify data was updated
  sleep 5  # Wait for sync to complete
  
  MONITORING_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data")
  MONITORING_STATUS=$(echo $MONITORING_RESPONSE | jq -r '.status')
  
  if [[ "$MONITORING_STATUS" == "success" ]]; then
    log "✅ Data successfully updated after forced sync"
    TIMESTAMP=$(echo $MONITORING_RESPONSE | jq -r '.data.timestamp')
    log "  Data timestamp: $TIMESTAMP"
  else
    log "❌ Failed to verify data update after forced sync"
  fi
else
  log "❌ Forced sync operation failed"
fi

# Summary
log "\n=== Test Summary ==="
log "Tests completed at $(date)"
log "Results logged to $LOG_FILE"

# Calculate success rate from log file
SUCCESSES=$(grep -c "✅" $LOG_FILE)
WARNINGS=$(grep -c "⚠️" $LOG_FILE)
FAILURES=$(grep -c "❌" $LOG_FILE)

log "Successes: $SUCCESSES"
log "Warnings: $WARNINGS"
log "Failures: $FAILURES"

log "\nLoad Test Success Rate: $SUCCESS_RATE%"
log "Stability Test Success Rate: $STABILITY_RATE%"

if [[ $FAILURES -eq 0 && $SUCCESS_RATE -ge 95 && $STABILITY_RATE -ge 95 ]]; then
  log "\n✅ All performance and reliability tests PASSED"
  exit 0
else
  log "\n⚠️ Some performance or reliability issues detected - review log for details"
  exit 1
fi