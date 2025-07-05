#!/bin/bash

# Podman Pod Testing - Simulates Kubernetes-style networking
# Creates a pod with shared network where services can communicate

set -e

POD_NAME="grill-monitoring-test-pod"
POSTGRES_CONTAINER="postgres-pod"
REDIS_CONTAINER="redis-pod"
INFLUXDB_CONTAINER="influxdb-pod"
DEVICE_SERVICE_CONTAINER="device-service-pod"
TEMP_SERVICE_CONTAINER="temperature-service-pod"

echo "🚀 Starting Podman Pod Test (Kubernetes-style)"
echo "=============================================="

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    
    echo "⏳ Waiting for $service_name to be ready..."
    for i in $(seq 1 $max_attempts); do
        if curl -f http://localhost:$port/ping 2>/dev/null || \
           curl -f http://localhost:$port/health 2>/dev/null || \
           nc -z localhost $port 2>/dev/null; then
            echo "✅ $service_name is ready!"
            return 0
        fi
        echo "   Attempt $i/$max_attempts - waiting..."
        sleep 2
    done
    echo "❌ $service_name failed to start within timeout"
    return 1
}

# Cleanup function
cleanup_pod() {
    echo "🧹 Cleaning up existing pod and containers..."
    podman pod stop $POD_NAME 2>/dev/null || true
    podman pod rm $POD_NAME 2>/dev/null || true
    
    # Clean up individual containers if they exist
    for container in $POSTGRES_CONTAINER $REDIS_CONTAINER $INFLUXDB_CONTAINER $DEVICE_SERVICE_CONTAINER $TEMP_SERVICE_CONTAINER; do
        podman stop $container 2>/dev/null || true
        podman rm $container 2>/dev/null || true
    done
}

# Cleanup on exit
trap cleanup_pod EXIT

# Initial cleanup
cleanup_pod

echo "📦 Creating pod with shared network..."
podman pod create --name $POD_NAME \
  -p 5432:5432 \
  -p 6379:6379 \
  -p 8086:8086 \
  -p 8080:8080 \
  -p 8081:8081 \
  -p 5000:5000

echo "🗄️ Starting database services in pod..."

# Start PostgreSQL
echo "   Starting PostgreSQL..."
podman run -d --pod $POD_NAME --name $POSTGRES_CONTAINER \
  -e POSTGRES_DB=grill_monitoring \
  -e POSTGRES_USER=grill_monitor \
  -e POSTGRES_PASSWORD=testpass \
  -v $(pwd)/database-init/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql \
  docker.io/library/postgres:13

# Start Redis
echo "   Starting Redis..."
podman run -d --pod $POD_NAME --name $REDIS_CONTAINER \
  docker.io/library/redis:6-alpine redis-server --requirepass testpass

# Start InfluxDB
echo "   Starting InfluxDB..."
podman run -d --pod $POD_NAME --name $INFLUXDB_CONTAINER \
  -e INFLUXDB_DB=grill_monitoring \
  -e INFLUXDB_USER=grill_monitor \
  -e INFLUXDB_USER_PASSWORD=testpass \
  -e INFLUXDB_ADMIN_USER=admin \
  -e INFLUXDB_ADMIN_PASSWORD=adminpass \
  -v $(pwd)/database-init/influxdb-init.sh:/docker-entrypoint-initdb.d/init.sh \
  docker.io/library/influxdb:1.8

echo "⏳ Waiting for databases to initialize..."
sleep 45

echo "🔍 Testing database connectivity..."

# Test PostgreSQL
echo "   Testing PostgreSQL..."
if podman exec $POSTGRES_CONTAINER pg_isready -U grill_monitor -d grill_monitoring; then
    echo "   ✅ PostgreSQL is ready"
else
    echo "   ❌ PostgreSQL connection failed"
fi

# Test Redis
echo "   Testing Redis..."
if podman exec $REDIS_CONTAINER redis-cli -a testpass ping | grep -q PONG; then
    echo "   ✅ Redis is ready"
else
    echo "   ❌ Redis connection failed"
fi

# Test InfluxDB
echo "   Testing InfluxDB..."
if podman exec $INFLUXDB_CONTAINER curl -f http://localhost:8086/ping; then
    echo "   ✅ InfluxDB is ready"
else
    echo "   ❌ InfluxDB connection failed"
fi

echo "🔨 Building application images..."

# Build device service
echo "   Building device service..."
podman build -t device-service:pod-test ./services/device-service/

# Build temperature service
echo "   Building temperature service..."
podman build -t temperature-service:pod-test ./services/temperature-service/

echo "🚀 Starting application services in pod..."

# Start Device Service
echo "   Starting Device Service..."
podman run -d --pod $POD_NAME --name $DEVICE_SERVICE_CONTAINER \
  -e DB_HOST=localhost \
  -e DB_PORT=5432 \
  -e DB_NAME=grill_monitoring \
  -e DB_USERNAME=grill_monitor \
  -e DB_PASSWORD=testpass \
  -e THERMOWORKS_API_KEY=test-key \
  -e DEBUG=true \
  -e PYTHONUNBUFFERED=1 \
  device-service:pod-test

# Start Temperature Service  
echo "   Starting Temperature Service..."
podman run -d --pod $POD_NAME --name $TEMP_SERVICE_CONTAINER \
  -e INFLUXDB_HOST=localhost \
  -e INFLUXDB_PORT=8086 \
  -e INFLUXDB_DATABASE=grill_monitoring \
  -e INFLUXDB_USERNAME=grill_monitor \
  -e INFLUXDB_PASSWORD=testpass \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=testpass \
  -e THERMOWORKS_API_KEY=test-key \
  -e DEBUG=true \
  -e PYTHONUNBUFFERED=1 \
  temperature-service:pod-test

echo "⏳ Waiting for application services to start..."
sleep 30

echo "🔍 Testing application service health endpoints..."

# Test Device Service
echo "   Testing Device Service..."
if curl -f http://localhost:8080/health; then
    echo "   ✅ Device Service: Healthy"
    curl -s http://localhost:8080/health | python3 -m json.tool | head -10
else
    echo "   ❌ Device Service: Failed"
fi

echo ""

# Test Temperature Service
echo "   Testing Temperature Service..."
if curl -f http://localhost:8081/health; then
    echo "   ✅ Temperature Service: Healthy"  
    curl -s http://localhost:8081/health | python3 -m json.tool | head -10
else
    echo "   ❌ Temperature Service: Failed"
fi

echo ""
echo "🧪 Running comprehensive API tests..."

# Test Device Service APIs
echo "📱 Testing Device Service APIs..."
echo "   GET /api/devices"
curl -s http://localhost:8080/api/devices | python3 -m json.tool | head -5

echo ""
echo "   POST /api/devices/discover"
curl -s -X POST http://localhost:8080/api/devices/discover | python3 -m json.tool | head -5

# Test Temperature Service APIs
echo ""
echo "🌡️ Testing Temperature Service APIs..."
echo "   GET /api/temperature/stats/test_device_001"
curl -s http://localhost:8081/api/temperature/stats/test_device_001 | python3 -m json.tool | head -5

echo ""
echo "   GET /api/temperature/history/test_device_001"
curl -s "http://localhost:8081/api/temperature/history/test_device_001?start_time=2024-01-01T00:00:00Z" | python3 -m json.tool | head -10

echo ""
echo "📊 Pod Status Summary:"
echo "====================="
podman pod ps
echo ""

echo "🐳 Container Status:"
echo "==================="
podman ps --pod-id-file /tmp/nonexistent 2>/dev/null || podman ps -a

echo ""
echo "🎉 Podman Pod Test Complete!"
echo ""
echo "📄 Services accessible at:"
echo "   🗄️ PostgreSQL: localhost:5432"
echo "   🔗 Redis: localhost:6379" 
echo "   📊 InfluxDB: localhost:8086"
echo "   📱 Device Service: http://localhost:8080"
echo "   🌡️ Temperature Service: http://localhost:8081"
echo ""
echo "🔍 Test some endpoints:"
echo "   curl http://localhost:8080/health"
echo "   curl http://localhost:8081/health"
echo "   curl http://localhost:8080/api/devices"
echo ""
echo "🛑 To stop the pod: podman pod stop $POD_NAME"
echo "🧹 To cleanup: podman pod rm $POD_NAME"
echo ""
echo "ℹ️  Pod will be automatically cleaned up when this script exits"