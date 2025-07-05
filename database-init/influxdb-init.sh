#!/bin/bash

# InfluxDB initialization script for Grill Monitoring
# This script sets up the database structure for the Temperature Data Service

set -e

echo "🔧 Starting InfluxDB initialization for Grill Monitoring..."

# Wait for InfluxDB to be ready
until curl -f http://localhost:8086/ping; do
    echo "⏳ Waiting for InfluxDB to be ready..."
    sleep 2
done

echo "✅ InfluxDB is ready, proceeding with initialization..."

# Create database if it doesn't exist
echo "📊 Creating grill_monitoring database..."
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE DATABASE grill_monitoring"

# Create retention policies
echo "🗄️ Creating retention policies..."

# Short-term retention (1 day) for real-time data
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE RETENTION POLICY \"realtime\" ON \"grill_monitoring\" DURATION 1d REPLICATION 1"

# Medium-term retention (7 days) for recent analysis
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE RETENTION POLICY \"recent\" ON \"grill_monitoring\" DURATION 7d REPLICATION 1"

# Long-term retention (30 days) for historical analysis
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE RETENTION POLICY \"historical\" ON \"grill_monitoring\" DURATION 30d REPLICATION 1"

# Archive retention (365 days) for long-term storage
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE RETENTION POLICY \"archive\" ON \"grill_monitoring\" DURATION 365d REPLICATION 1 DEFAULT"

echo "📈 Creating continuous queries for data aggregation..."

# Create continuous query for hourly aggregation
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE CONTINUOUS QUERY \"cq_temperature_hourly\" ON \"grill_monitoring\" BEGIN SELECT mean(\"temperature\") AS \"temperature_avg\", max(\"temperature\") AS \"temperature_max\", min(\"temperature\") AS \"temperature_min\", count(\"temperature\") AS \"temperature_count\" INTO \"grill_monitoring\".\"archive\".\"temperature_hourly\" FROM \"grill_monitoring\".\"autogen\".\"temperature\" GROUP BY time(1h), \"device_id\", \"probe_id\" END"

# Create continuous query for daily aggregation
curl -X POST "http://localhost:8086/query" \
    --data-urlencode "q=CREATE CONTINUOUS QUERY \"cq_temperature_daily\" ON \"grill_monitoring\" BEGIN SELECT mean(\"temperature_avg\") AS \"temperature_avg\", max(\"temperature_max\") AS \"temperature_max\", min(\"temperature_min\") AS \"temperature_min\", sum(\"temperature_count\") AS \"temperature_count\" INTO \"grill_monitoring\".\"archive\".\"temperature_daily\" FROM \"grill_monitoring\".\"archive\".\"temperature_hourly\" GROUP BY time(1d), \"device_id\", \"probe_id\" END"

echo "🧪 Inserting sample temperature data..."

# Insert sample data for testing
CURRENT_TIME=$(date -u +%s)000000000  # nanoseconds

# Sample data for test device 1
curl -X POST "http://localhost:8086/write?db=grill_monitoring" \
    --data-binary "temperature,device_id=test_device_001,probe_id=probe1,unit=F temperature=225.5,battery_level=85,signal_strength=95 ${CURRENT_TIME}"

# Sample data for test device 2  
curl -X POST "http://localhost:8086/write?db=grill_monitoring" \
    --data-binary "temperature,device_id=test_device_002,probe_id=probe1,unit=F temperature=180.2,battery_level=92,signal_strength=88 ${CURRENT_TIME}"

curl -X POST "http://localhost:8086/write?db=grill_monitoring" \
    --data-binary "temperature,device_id=test_device_002,probe_id=probe2,unit=F temperature=165.8,battery_level=92,signal_strength=88 ${CURRENT_TIME}"

# Sample data for RFX device
curl -X POST "http://localhost:8086/write?db=grill_monitoring" \
    --data-binary "temperature,device_id=rfx_device_001,probe_id=external,unit=F temperature=72.4,battery_level=78,signal_strength=76 ${CURRENT_TIME}"

echo "🔍 Creating database users and permissions..."

# Create users (if authentication is enabled)
if [ "${INFLUXDB_ADMIN_USER}" ]; then
    echo "👤 Creating database users..."
    
    # Create read-only user for monitoring
    curl -X POST "http://localhost:8086/query" \
        --data-urlencode "q=CREATE USER \"monitor\" WITH PASSWORD 'monitor_pass'"
    
    curl -X POST "http://localhost:8086/query" \
        --data-urlencode "q=GRANT READ ON \"grill_monitoring\" TO \"monitor\""
    
    # Create application user with write permissions
    curl -X POST "http://localhost:8086/query" \
        --data-urlencode "q=GRANT WRITE ON \"grill_monitoring\" TO \"${INFLUXDB_USER}\""
fi

echo "📊 Verifying database setup..."

# Verify database exists
DB_EXISTS=$(curl -s "http://localhost:8086/query?q=SHOW%20DATABASES" | grep -c "grill_monitoring" || echo "0")
if [ "$DB_EXISTS" -gt "0" ]; then
    echo "✅ Database 'grill_monitoring' created successfully"
else
    echo "❌ Failed to create database 'grill_monitoring'"
    exit 1
fi

# Verify retention policies
RP_COUNT=$(curl -s "http://localhost:8086/query?q=SHOW%20RETENTION%20POLICIES%20ON%20grill_monitoring" | grep -c "archive\|realtime\|recent\|historical" || echo "0")
if [ "$RP_COUNT" -ge "4" ]; then
    echo "✅ Retention policies created successfully"
else
    echo "⚠️ Some retention policies may not have been created"
fi

# Verify sample data
DATA_COUNT=$(curl -s "http://localhost:8086/query?db=grill_monitoring&q=SELECT%20COUNT(temperature)%20FROM%20temperature" | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
if [ "$DATA_COUNT" -gt "0" ]; then
    echo "✅ Sample data inserted successfully ($DATA_COUNT points)"
else
    echo "⚠️ No sample data found"
fi

echo "🎉 InfluxDB initialization completed successfully!"
echo "📊 Database: grill_monitoring"
echo "🗄️ Retention Policies: realtime (1d), recent (7d), historical (30d), archive (365d - default)"
echo "📈 Continuous Queries: hourly and daily aggregation"
echo "🧪 Sample Data: Temperature readings for test devices"