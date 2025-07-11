#!/bin/bash

# Podman Pod Testing - Simulates Kubernetes-style networking
# Creates a pod with shared network where services can communicate

set -e

POD_NAME="grill-stats-test-pod"

echo "🚀 Starting Podman Pod Test (Kubernetes-style)"
echo "=============================================="

# Cleanup any existing pod
echo "🧹 Cleaning up existing pod..."
podman pod stop $POD_NAME 2>/dev/null || true
podman pod rm $POD_NAME 2>/dev/null || true

# Create pod with shared network
echo "📦 Creating pod with shared network..."
podman pod create --name $POD_NAME \
  -p 5432:5432 \
  -p 6379:6379 \
  -p 8086:8086 \
  -p 8080:8080 \
  -p 8081:8081

# Start database services in the pod
echo "🗄️  Starting database services..."

# PostgreSQL
podman run -d --pod $POD_NAME --name postgres-test \
  -e POSTGRES_DB=grill_monitoring \
  -e POSTGRES_USER=grill_monitor \
  -e POSTGRES_PASSWORD=testpass \
  postgres:13

# Redis
podman run -d --pod $POD_NAME --name redis-test \
  redis:6-alpine redis-server --requirepass testpass

# InfluxDB
podman run -d --pod $POD_NAME --name influxdb-test \
  -e INFLUXDB_DB=grill_monitoring \
  -e INFLUXDB_USER=grill_monitor \
  -e INFLUXDB_USER_PASSWORD=testpass \
  influxdb:1.8

# Wait for databases to start
echo "⏳ Waiting for databases to start..."
sleep 30

# Test database connectivity
echo "🔍 Testing database connectivity..."
podman exec postgres-test pg_isready -U grill_monitor -d grill_monitoring
podman exec redis-test redis-cli --raw incr ping
podman exec influxdb-test curl -f http://localhost:8086/ping

# Start application services
echo "🚀 Starting application services..."

# Device Service
podman run -d --pod $POD_NAME --name device-service-pod \
  -e DB_HOST=localhost \
  -e DB_PORT=5432 \
  -e DB_NAME=grill_monitoring \
  -e DB_USERNAME=grill_monitor \
  -e DB_PASSWORD=testpass \
  -e THERMOWORKS_API_KEY=test-key \
  -e DEBUG=true \
  localhost/device-service-test:test

# Temperature Service  
podman run -d --pod $POD_NAME --name temperature-service-pod \
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
  localhost/temperature-service-test:test

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 20

# Test services
echo "🔍 Testing service health endpoints..."
curl -f http://localhost:8080/health && echo "✅ Device Service: Healthy"
curl -f http://localhost:8081/health && echo "✅ Temperature Service: Healthy"

echo ""
echo "🎉 Pod test complete! Services running in shared network."
echo "📊 Access services at:"
echo "   Device Service: http://localhost:8080"
echo "   Temperature Service: http://localhost:8081"
echo ""
echo "🛑 To stop the pod: podman pod stop $POD_NAME"
echo "🧹 To cleanup: podman pod rm $POD_NAME"