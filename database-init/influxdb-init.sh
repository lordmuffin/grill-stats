#!/bin/bash

# InfluxDB 2.x initialization script for Grill Monitoring
# This script sets up the database structure for the Temperature Data Service

set -e

echo "🔧 Starting InfluxDB 2.x initialization for Grill Monitoring..."

# Wait for InfluxDB to be ready
until curl -f http://localhost:8086/ping; do
    echo "⏳ Waiting for InfluxDB 2.x to be ready..."
    sleep 3
done

echo "✅ InfluxDB 2.x is ready, proceeding with initialization..."

# Get configuration from environment variables
ADMIN_TOKEN="${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}"
ORG="${DOCKER_INFLUXDB_INIT_ORG:-grill-stats}"
BUCKET="${DOCKER_INFLUXDB_INIT_BUCKET:-grill-stats-realtime}"
RETENTION="${DOCKER_INFLUXDB_INIT_RETENTION:-168h}"

# Verify we have required environment variables
if [ -z "$ADMIN_TOKEN" ]; then
    echo "❌ DOCKER_INFLUXDB_INIT_ADMIN_TOKEN is required"
    exit 1
fi

# List existing buckets to see what's already set up
echo "📊 Checking existing buckets..."
EXISTING_BUCKETS=$(influx bucket list --org "$ORG" --token "$ADMIN_TOKEN" --host http://localhost:8086 --json 2>/dev/null || echo "[]")

# Create buckets with appropriate retention policies
echo "🗄️ Creating buckets with retention policies..."

# Real-time bucket (7 days retention)
if echo "$EXISTING_BUCKETS" | grep -q "grill-stats-realtime"; then
    echo "📊 Real-time bucket already exists"
else
    influx bucket create \
        --name grill-stats-realtime \
        --org "$ORG" \
        --retention 168h \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 || echo "⚠️ Failed to create real-time bucket"
fi

# Hourly aggregated bucket (90 days retention)
if echo "$EXISTING_BUCKETS" | grep -q "grill-stats-hourly"; then
    echo "📊 Hourly bucket already exists"
else
    influx bucket create \
        --name grill-stats-hourly \
        --org "$ORG" \
        --retention 2160h \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 || echo "⚠️ Failed to create hourly bucket"
fi

# Daily aggregated bucket (1 year retention)
if echo "$EXISTING_BUCKETS" | grep -q "grill-stats-daily"; then
    echo "📊 Daily bucket already exists"
else
    influx bucket create \
        --name grill-stats-daily \
        --org "$ORG" \
        --retention 8760h \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 || echo "⚠️ Failed to create daily bucket"
fi

# Archive bucket (infinite retention)
if echo "$EXISTING_BUCKETS" | grep -q "grill-stats-archive"; then
    echo "📊 Archive bucket already exists"
else
    influx bucket create \
        --name grill-stats-archive \
        --org "$ORG" \
        --retention 0 \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 || echo "⚠️ Failed to create archive bucket"
fi

# Monitoring bucket (30 days retention)
if echo "$EXISTING_BUCKETS" | grep -q "grill-stats-monitoring"; then
    echo "📊 Monitoring bucket already exists"
else
    influx bucket create \
        --name grill-stats-monitoring \
        --org "$ORG" \
        --retention 720h \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 || echo "⚠️ Failed to create monitoring bucket"
fi

echo "📈 Creating tasks for data aggregation..."

# Create hourly downsampling task
cat > /tmp/hourly-downsample.flux << 'EOF'
import "influxdata/influxdb/tasks"

option task = {
  name: "downsample-hourly-temperature",
  every: 1h,
  offset: 5m,
}

from(bucket: "grill-stats-realtime")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature_readings")
  |> group(columns: ["device_id", "channel_id", "probe_type", "user_id"])
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> to(bucket: "grill-stats-hourly")
EOF

# Create daily downsampling task
cat > /tmp/daily-downsample.flux << 'EOF'
import "influxdata/influxdb/tasks"

option task = {
  name: "downsample-daily-temperature", 
  every: 1d,
  offset: 10m,
}

from(bucket: "grill-stats-hourly")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "temperature_readings")
  |> group(columns: ["device_id", "channel_id", "probe_type", "user_id"])
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> to(bucket: "grill-stats-daily")
EOF

# Create archive task
cat > /tmp/archive-task.flux << 'EOF'
import "influxdata/influxdb/tasks"

option task = {
  name: "archive-temperature-data",
  every: 1d,
  offset: 30m,
}

from(bucket: "grill-stats-daily")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "temperature_readings")
  |> to(bucket: "grill-stats-archive")
EOF

# Create tasks
echo "📈 Creating hourly downsampling task..."
influx task create \
    --file /tmp/hourly-downsample.flux \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 || echo "⚠️ Hourly task may already exist"

echo "📈 Creating daily downsampling task..."
influx task create \
    --file /tmp/daily-downsample.flux \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 || echo "⚠️ Daily task may already exist"

echo "📈 Creating archive task..."
influx task create \
    --file /tmp/archive-task.flux \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 || echo "⚠️ Archive task may already exist"

echo "🔑 Creating service tokens..."

# Create tokens for different services
echo "🔑 Creating temperature service token..."
TEMP_TOKEN=$(influx auth create \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 \
    --description "Temperature Service Token" \
    --write-buckets "grill-stats-realtime" \
    --read-buckets "grill-stats-realtime,grill-stats-hourly,grill-stats-daily" \
    --json 2>/dev/null | jq -r '.token' || echo "")

echo "🔑 Creating historical service token..."
HIST_TOKEN=$(influx auth create \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 \
    --description "Historical Service Token" \
    --read-buckets "grill-stats-realtime,grill-stats-hourly,grill-stats-daily,grill-stats-archive" \
    --json 2>/dev/null | jq -r '.token' || echo "")

echo "🔑 Creating web UI token..."
WEB_TOKEN=$(influx auth create \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 \
    --description "Web UI Token" \
    --read-buckets "grill-stats-realtime,grill-stats-hourly,grill-stats-daily,grill-stats-archive" \
    --json 2>/dev/null | jq -r '.token' || echo "")

echo "🔑 Creating monitoring token..."
MON_TOKEN=$(influx auth create \
    --org "$ORG" \
    --token "$ADMIN_TOKEN" \
    --host http://localhost:8086 \
    --description "Monitoring Token" \
    --read-buckets "grill-stats-realtime,grill-stats-hourly,grill-stats-daily,grill-stats-archive,grill-stats-monitoring" \
    --json 2>/dev/null | jq -r '.token' || echo "")

echo "🧪 Inserting sample temperature data..."

# Insert sample data for testing (only if not in production)
if [ "${ENVIRONMENT}" != "production" ] && [ "${ENVIRONMENT}" != "prod" ]; then
    # Current timestamp in nanoseconds
    CURRENT_TIME=$(date +%s)000000000
    
    # Sample data for ThermoWorks Signals device
    cat > /tmp/sample-data.txt << EOF
temperature_readings,device_id=test_signals_001,channel_id=1,probe_type=meat,user_id=test_user,device_type=signals,location=test_lab temperature=165.5,unit="F",battery_level=85,signal_strength=-45,accuracy=0.1,calibration_offset=0.0 $CURRENT_TIME
temperature_readings,device_id=test_signals_001,channel_id=2,probe_type=ambient,user_id=test_user,device_type=signals,location=test_lab temperature=225.0,unit="F",battery_level=85,signal_strength=-45,accuracy=0.1,calibration_offset=0.0 $CURRENT_TIME
temperature_readings,device_id=test_signals_001,channel_id=3,probe_type=meat,user_id=test_user,device_type=signals,location=test_lab temperature=155.2,unit="F",battery_level=85,signal_strength=-45,accuracy=0.1,calibration_offset=0.0 $CURRENT_TIME
temperature_readings,device_id=test_signals_001,channel_id=4,probe_type=meat,user_id=test_user,device_type=signals,location=test_lab temperature=140.8,unit="F",battery_level=85,signal_strength=-45,accuracy=0.1,calibration_offset=0.0 $CURRENT_TIME
device_status,device_id=test_signals_001,user_id=test_user,device_type=signals,location=test_lab online=true,battery_level=85,signal_strength=-45,connection_status="connected",last_seen=1642267800,firmware_version="2.1.0",hardware_version="1.0",uptime=3600,memory_usage=45,cpu_usage=12 $CURRENT_TIME
EOF
    
    # Insert sample data
    influx write \
        --org "$ORG" \
        --bucket grill-stats-realtime \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 \
        --file /tmp/sample-data.txt || echo "⚠️ Sample data insertion failed"
    
    echo "✅ Sample data inserted successfully!"
else
    echo "🔒 Skipping sample data insertion for production environment"
fi

echo "📊 Verifying database setup..."

# Verify buckets
BUCKET_COUNT=$(influx bucket list --org "$ORG" --token "$ADMIN_TOKEN" --host http://localhost:8086 --json 2>/dev/null | jq length || echo "0")
if [ "$BUCKET_COUNT" -ge "4" ]; then
    echo "✅ Buckets created successfully ($BUCKET_COUNT buckets)"
else
    echo "⚠️ Some buckets may not have been created"
fi

# Verify tasks
TASK_COUNT=$(influx task list --org "$ORG" --token "$ADMIN_TOKEN" --host http://localhost:8086 --json 2>/dev/null | jq length || echo "0")
if [ "$TASK_COUNT" -ge "2" ]; then
    echo "✅ Tasks created successfully ($TASK_COUNT tasks)"
else
    echo "⚠️ Some tasks may not have been created"
fi

# Verify tokens
TOKEN_COUNT=$(influx auth list --org "$ORG" --token "$ADMIN_TOKEN" --host http://localhost:8086 --json 2>/dev/null | jq length || echo "0")
if [ "$TOKEN_COUNT" -ge "4" ]; then
    echo "✅ Service tokens created successfully ($TOKEN_COUNT tokens)"
else
    echo "⚠️ Some service tokens may not have been created"
fi

# Verify sample data (if not production)
if [ "${ENVIRONMENT}" != "production" ] && [ "${ENVIRONMENT}" != "prod" ]; then
    DATA_COUNT=$(influx query \
        --org "$ORG" \
        --token "$ADMIN_TOKEN" \
        --host http://localhost:8086 \
        'from(bucket: "grill-stats-realtime") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "temperature_readings") |> count()' \
        --raw 2>/dev/null | grep -o '"_value":[0-9]*' | cut -d':' -f2 | head -1 || echo "0")
    
    if [ "$DATA_COUNT" -gt "0" ]; then
        echo "✅ Sample data verified successfully ($DATA_COUNT points)"
    else
        echo "⚠️ No sample data found"
    fi
fi

echo "🎉 InfluxDB 2.x initialization completed successfully!"
echo "📊 Organization: $ORG"
echo "🗄️ Buckets: realtime (7d), hourly (90d), daily (1y), archive (∞), monitoring (30d)"
echo "📈 Tasks: hourly aggregation, daily aggregation, archival"
echo "🔑 Service Tokens: temperature-service, historical-service, web-ui, monitoring"
echo "🧪 Sample Data: Available in non-production environments"

# Save token information for services (if tokens were created successfully)
if [ -n "$TEMP_TOKEN" ] && [ -n "$HIST_TOKEN" ] && [ -n "$WEB_TOKEN" ] && [ -n "$MON_TOKEN" ]; then
    echo "💾 Saving service token information..."
    cat > /tmp/service-tokens.env << EOF
# Service Tokens for InfluxDB 2.x
TEMPERATURE_SERVICE_TOKEN=$TEMP_TOKEN
HISTORICAL_SERVICE_TOKEN=$HIST_TOKEN
WEB_UI_TOKEN=$WEB_TOKEN
MONITORING_TOKEN=$MON_TOKEN
EOF
    echo "✅ Service tokens saved to /tmp/service-tokens.env"
    echo "⚠️ These tokens should be stored securely in Kubernetes secrets"
fi