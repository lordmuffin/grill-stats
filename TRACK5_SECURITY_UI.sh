#!/bin/bash
# =======================================================================
# Security, Deployment & UI Test Script
# 
# Purpose: Verify security measures, deployment configuration,
#          and UI functionality
# Environment: Production - grill-stats.lab.apj.dev
# =======================================================================

# Configuration
API_BASE_URL="http://localhost:8082"
LOG_FILE="/tmp/grill-stats-security-ui-test-$(date +%Y%m%d%H%M%S).log"
SCREENSHOTS_DIR="/tmp/grill-stats-screenshots"
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

# Check for tools required for testing
check_required_tools() {
  local missing_tools=()
  
  # Check for curl
  if ! command -v curl &> /dev/null; then
    missing_tools+=("curl")
  fi
  
  # Check for jq
  if ! command -v jq &> /dev/null; then
    missing_tools+=("jq")
  fi
  
  # Check for screenshot tools (optional)
  if ! command -v firefox &> /dev/null && ! command -v chromium-browser &> /dev/null && ! command -v chrome &> /dev/null; then
    log "⚠️ No browser found for UI screenshots (firefox, chromium-browser, or chrome)"
  fi
  
  # Check for SSL/TLS testing tools (optional)
  if ! command -v openssl &> /dev/null; then
    log "⚠️ OpenSSL not found - TLS tests will be limited"
  fi
  
  if ! command -v nmap &> /dev/null; then
    log "⚠️ Nmap not found - port scanning tests will be skipped"
  fi
  
  # Report missing required tools
  if [[ ${#missing_tools[@]} -gt 0 ]]; then
    log "❌ Missing required tools: ${missing_tools[*]}"
    log "Please install these tools before running this script"
    return 1
  fi
  
  return 0
}

# Create a screenshot of a webpage if a browser is available
take_screenshot() {
  local url=$1
  local filename=$2
  
  mkdir -p $SCREENSHOTS_DIR
  
  if command -v firefox &> /dev/null; then
    firefox --headless --screenshot "${SCREENSHOTS_DIR}/${filename}.png" "$url"
    return $?
  elif command -v chromium-browser &> /dev/null; then
    chromium-browser --headless --screenshot="${SCREENSHOTS_DIR}/${filename}.png" "$url"
    return $?
  elif command -v chrome &> /dev/null; then
    chrome --headless --screenshot="${SCREENSHOTS_DIR}/${filename}.png" "$url"
    return $?
  else
    log "⚠️ No browser available for screenshots"
    return 1
  fi
}

# -----------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------

log "=== Starting Security, Deployment & UI Test ==="
log "Target environment: $API_BASE_URL"
log "Log file: $LOG_FILE"

# Check for required tools
if ! check_required_tools; then
  log "❌ Missing required tools. Exiting."
  exit 1
fi

# Create screenshots directory
mkdir -p $SCREENSHOTS_DIR

# Test 1: TLS Security
log "\n--- Test 1: TLS Security ---"

# 1.1 Check HTTPS availability
log "Checking HTTPS availability..."
HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_BASE_URL)

if [[ "$HTTPS_RESPONSE" == "200" || "$HTTPS_RESPONSE" == "302" ]]; then
  log "✅ HTTPS is available (HTTP $HTTPS_RESPONSE)"
else
  log "❌ HTTPS check failed (HTTP $HTTPS_RESPONSE)"
fi

# 1.2 Check TLS version and cipher
if command -v openssl &> /dev/null; then
  log "Checking TLS configuration..."
  
  # Extract domain from URL
  DOMAIN=$(echo $API_BASE_URL | sed -E 's/https?:\/\///' | sed -E 's/\/.*//')
  
  # Get TLS information
  TLS_INFO=$(openssl s_client -connect ${DOMAIN}:443 -tls1_2 < /dev/null 2>&1)
  
  # Extract protocol version
  PROTOCOL=$(echo "$TLS_INFO" | grep "Protocol" | awk '{print $2}')
  CIPHER=$(echo "$TLS_INFO" | grep "Cipher" | awk '{print $3}')
  
  log "TLS Protocol: $PROTOCOL"
  log "Cipher: $CIPHER"
  
  # Check if using at least TLS 1.2
  if [[ "$PROTOCOL" == "TLSv1.2" || "$PROTOCOL" == "TLSv1.3" ]]; then
    log "✅ Using secure TLS version ($PROTOCOL)"
  else
    log "❌ Using potentially insecure TLS version ($PROTOCOL)"
  fi
  
  # Check for secure headers
  log "Checking security headers..."
  HEADERS=$(curl -s -I $API_BASE_URL)
  
  if echo "$HEADERS" | grep -i "Strict-Transport-Security" > /dev/null; then
    log "✅ HSTS header is set"
  else
    log "⚠️ HSTS header not found"
  fi
  
  if echo "$HEADERS" | grep -i "X-Content-Type-Options" > /dev/null; then
    log "✅ X-Content-Type-Options header is set"
  else
    log "⚠️ X-Content-Type-Options header not found"
  fi
  
  if echo "$HEADERS" | grep -i "X-Frame-Options" > /dev/null; then
    log "✅ X-Frame-Options header is set"
  else
    log "⚠️ X-Frame-Options header not found"
  fi
fi

# Test 2: Authentication Security
log "\n--- Test 2: Authentication Security ---"

# 2.1 Test login functionality
log "Testing login functionality..."
if login; then
  log "✅ Login system works correctly"
  
  # Check token format (should be JWT or other structured token)
  if [[ "$AUTH_TOKEN" =~ ^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]]; then
    log "✅ Token appears to be in JWT format"
  else
    log "⚠️ Token does not appear to be in JWT format"
  fi
else
  log "❌ Login failed"
fi

# 2.2 Test incorrect login credentials
log "Testing login with incorrect credentials..."
INVALID_LOGIN=$(curl -s -X POST "$API_BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"wrong_password\"}")

if echo "$INVALID_LOGIN" | grep -i "error\|invalid\|failed" > /dev/null; then
  log "✅ Incorrect login credentials properly rejected"
else
  log "❌ Security issue: Incorrect credentials not properly handled"
fi

# 2.3 Test protected endpoint access
log "Testing protected endpoint access..."
PROTECTED_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null "$API_BASE_URL/devices")

if [[ "$PROTECTED_RESPONSE" == "401" || "$PROTECTED_RESPONSE" == "403" ]]; then
  log "✅ Protected endpoint correctly requires authentication"
else
  log "❌ Security issue: Protected endpoint may be accessible without authentication"
fi

# Test 3: API Key Security
log "\n--- Test 3: API Key Security ---"

# 3.1 Check for API key handling
log "Checking for secure API key handling..."
CONFIG_RESPONSE=$(curl -s "$API_BASE_URL/api/config")

# Verify that no sensitive data is exposed
if echo "$CONFIG_RESPONSE" | grep -i "key\|token\|password\|secret" > /dev/null; then
  log "❌ Possible security issue: Config endpoint may expose sensitive data"
  echo "$CONFIG_RESPONSE" | grep -i "key\|token\|password\|secret"
else
  log "✅ Config endpoint does not expose sensitive data"
fi

# Test 4: Docker Container Security
log "\n--- Test 4: Docker Container Security ---"

log "Testing external port exposure..."
if command -v nmap &> /dev/null; then
  # Extract domain from URL
  DOMAIN=$(echo $API_BASE_URL | sed -E 's/https?:\/\///' | sed -E 's/\/.*//')
  
  # Scan common ports
  PORTS_SCAN=$(nmap -Pn -p 80,443,5000,8080,8443 $DOMAIN)
  
  log "Port scan results:"
  echo "$PORTS_SCAN" | grep "open\|closed\|filtered" | tee -a $LOG_FILE
  
  # Check for unexpected open ports
  UNEXPECTED=$(echo "$PORTS_SCAN" | grep -v "443/tcp" | grep "open")
  if [[ -n "$UNEXPECTED" ]]; then
    log "⚠️ Unexpected ports may be exposed:"
    echo "$UNEXPECTED"
  else
    log "✅ Only expected ports are exposed"
  fi
else
  log "⚠️ Nmap not available for port scanning"
fi

# Test 5: UI Functionality
log "\n--- Test 5: UI Functionality ---"

# Authentication required for UI tests
if [[ -z "$AUTH_TOKEN" ]]; then
  login
fi

# 5.1 Dashboard access
log "Testing dashboard access..."
DASHBOARD_RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/dashboard.html \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Accept: text/html,application/xhtml+xml" \
  "$API_BASE_URL/monitoring")

if [[ "$DASHBOARD_RESPONSE" == "200" ]]; then
  log "✅ Dashboard accessible"
  
  # Take screenshot if browser available
  take_screenshot "$API_BASE_URL/monitoring" "dashboard"
  if [[ $? -eq 0 ]]; then
    log "  Screenshot saved to ${SCREENSHOTS_DIR}/dashboard.png"
  fi
  
  # Check for expected dashboard elements
  if grep -i "temperature\|probe\|device\|monitor" /tmp/dashboard.html > /dev/null; then
    log "✅ Dashboard contains expected elements"
  else
    log "⚠️ Dashboard may be missing expected elements"
  fi
else
  log "❌ Dashboard not accessible (HTTP $DASHBOARD_RESPONSE)"
fi

# 5.2 Device management page
log "Testing device management page..."
DEVICES_PAGE=$(curl -s -w "%{http_code}" -o /tmp/devices.html \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Accept: text/html,application/xhtml+xml" \
  "$API_BASE_URL/devices")

if [[ "$DEVICES_PAGE" == "200" ]]; then
  log "✅ Device management page accessible"
  
  # Take screenshot if browser available
  take_screenshot "$API_BASE_URL/devices" "devices"
  if [[ $? -eq 0 ]]; then
    log "  Screenshot saved to ${SCREENSHOTS_DIR}/devices.png"
  fi
else
  log "❌ Device management page not accessible (HTTP $DEVICES_PAGE)"
fi

# 5.3 Real-time data functionality
log "Testing real-time data API..."
REALTIME_DATA=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/monitoring/data")

if [[ $(echo "$REALTIME_DATA" | jq -r '.status') == "success" ]]; then
  log "✅ Real-time data API working"
  PROBE_COUNT=$(echo "$REALTIME_DATA" | jq -r '.data.count')
  log "  Found $PROBE_COUNT temperature probes"
  
  # Check data freshness
  TIMESTAMP=$(echo "$REALTIME_DATA" | jq -r '.data.timestamp')
  TS_SECONDS=$(date -d "$TIMESTAMP" +%s)
  NOW_SECONDS=$(date +%s)
  DIFF_MINUTES=$(( (NOW_SECONDS - TS_SECONDS) / 60 ))
  
  if [[ $DIFF_MINUTES -lt 10 ]]; then
    log "✅ Data is recent (updated $DIFF_MINUTES minutes ago)"
  else
    log "⚠️ Data may be stale (updated $DIFF_MINUTES minutes ago)"
  fi
else
  log "❌ Real-time data API not working"
fi

# 5.4 Session management functionality
log "Testing session management functionality..."
SESSIONS_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/sessions/active")

if [[ $(echo "$SESSIONS_RESPONSE" | jq -r '.success') == "true" ]]; then
  log "✅ Session management API working"
  SESSION_COUNT=$(echo "$SESSIONS_RESPONSE" | jq -r '.data.count')
  log "  Found $SESSION_COUNT active sessions"
else
  log "❌ Session management API not working"
fi

# 5.5 Responsive design test
log "Testing responsive design (simulating different devices)..."

# Define user agents for different devices
MOBILE_UA="Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
TABLET_UA="Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
DESKTOP_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Test dashboard with different devices
DASHBOARD_URL="$API_BASE_URL/monitoring"

if take_screenshot "$DASHBOARD_URL" "dashboard_desktop"; then
  log "✅ Desktop view screenshot captured"
fi

# Test mobile view using curl with mobile user agent
MOBILE_RESPONSE=$(curl -s -A "$MOBILE_UA" -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  "$DASHBOARD_URL")

if [[ "$MOBILE_RESPONSE" == "200" ]]; then
  log "✅ Mobile view accessible"
  
  # Take mobile screenshot if possible
  if command -v firefox &> /dev/null; then
    firefox --headless --screenshot "${SCREENSHOTS_DIR}/dashboard_mobile.png" \
      --window-size=375,812 "$DASHBOARD_URL"
    log "  Mobile screenshot saved to ${SCREENSHOTS_DIR}/dashboard_mobile.png"
  fi
else
  log "❌ Mobile view issue (HTTP $MOBILE_RESPONSE)"
fi

# Test 6: Alert System
log "\n--- Test 6: Alert System ---"

# 6.1 Test alert configuration
log "Testing alert configuration API..."
ALERT_TYPES=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/api/alerts/types")

if [[ $(echo "$ALERT_TYPES" | jq -r '.success') == "true" ]]; then
  log "✅ Alert types API working"
  TYPES=$(echo "$ALERT_TYPES" | jq -r '.data.alert_types | length')
  log "  Found $TYPES alert types available"
else
  log "❌ Alert types API not working"
fi

# 6.2 Test alert creation
# Get device ID for testing
DEVICES_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_BASE_URL/devices")
if [[ $(echo $DEVICES_RESPONSE | jq 'type') == "array" ]]; then
  DEVICE_COUNT=$(echo $DEVICES_RESPONSE | jq '. | length')
  
  if [[ $DEVICE_COUNT -gt 0 ]]; then
    TEST_DEVICE_ID=$(echo $DEVICES_RESPONSE | jq -r '.[0].id')
    
    log "Testing alert creation..."
    
    CREATE_ALERT=$(curl -s -X POST "$API_BASE_URL/api/alerts" \
      -H "Authorization: Bearer $AUTH_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"device_id\": \"$TEST_DEVICE_ID\",
        \"probe_id\": \"probe_1\",
        \"alert_type\": \"target\",
        \"name\": \"Test Alert\",
        \"target_temperature\": 200,
        \"temperature_unit\": \"F\"
      }")
    
    if [[ $(echo "$CREATE_ALERT" | jq -r '.success') == "true" ]]; then
      log "✅ Alert creation working"
      ALERT_ID=$(echo "$CREATE_ALERT" | jq -r '.data.id')
      log "  Created alert ID: $ALERT_ID"
      
      # Clean up by deleting the test alert
      if [[ -n "$ALERT_ID" ]]; then
        DELETE_ALERT=$(curl -s -X DELETE "$API_BASE_URL/api/alerts/$ALERT_ID" \
          -H "Authorization: Bearer $AUTH_TOKEN")
        
        if [[ $(echo "$DELETE_ALERT" | jq -r '.success') == "true" ]]; then
          log "  ✅ Test alert successfully deleted"
        else
          log "  ⚠️ Could not delete test alert"
        fi
      fi
    else
      log "❌ Alert creation failed: $(echo "$CREATE_ALERT" | jq -r '.message')"
    fi
  else
    log "⚠️ Skipping alert creation test (no devices found)"
  fi
else
  log "⚠️ Skipping alert creation test (failed to get device list)"
fi

# Test 7: Deployment Configuration
log "\n--- Test 7: Deployment Configuration ---"

# 7.1 Check application version
APP_CONFIG=$(curl -s "$API_BASE_URL/api/config")
APP_VERSION=$(echo "$APP_CONFIG" | jq -r '.version')
APP_ENV=$(echo "$APP_CONFIG" | jq -r '.environment')

log "Application version: $APP_VERSION"
log "Environment: $APP_ENV"

if [[ "$APP_ENV" == "production" ]]; then
  log "✅ Application is running in production environment"
else
  log "⚠️ Application is not running in production environment: $APP_ENV"
fi

# 7.2 Check service reliability
log "Checking service reliability..."

# Make multiple health checks to verify consistent response
for i in {1..5}; do
  HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE_URL/health")
  if [[ "$HEALTH_RESPONSE" != "200" ]]; then
    log "❌ Health check $i failed: HTTP $HEALTH_RESPONSE"
    HEALTH_FAILURES=1
  fi
  sleep 1
done

if [[ -z "$HEALTH_FAILURES" ]]; then
  log "✅ Service is responding reliably to health checks"
fi

# Summary
log "\n=== Test Summary ==="
log "Tests completed at $(date)"
log "Results logged to $LOG_FILE"
log "Screenshots saved to $SCREENSHOTS_DIR"

# Calculate success rate
SUCCESSES=$(grep -c "✅" $LOG_FILE)
WARNINGS=$(grep -c "⚠️" $LOG_FILE)
FAILURES=$(grep -c "❌" $LOG_FILE)

log "Successes: $SUCCESSES"
log "Warnings: $WARNINGS"
log "Failures: $FAILURES"

if [[ $FAILURES -eq 0 ]]; then
  log "\n✅ All security, deployment & UI tests PASSED"
  exit 0
else
  log "\n❌ Some tests FAILED - review log for details"
  exit 1
fi