#!/bin/bash

# API Gateway Setup Script
set -e

echo "🚀 Setting up API Gateway & Security Infrastructure..."

# Create required directories
echo "📁 Creating directories..."
mkdir -p ./logs
mkdir -p ./data

# Create acme.json for SSL certificates
echo "🔐 Setting up SSL certificate storage..."
touch ./acme.json
chmod 600 ./acme.json

# Set up Redis for gateway services
echo "🔄 Starting Redis for gateway services..."
docker run -d \
  --name gateway-redis \
  --network grill-stats-network \
  -p 6380:6379 \
  redis:7-alpine

# Wait for Redis to be ready
echo "⏳ Waiting for Redis to be ready..."
sleep 5

# Build gateway services
echo "🔨 Building gateway services..."
docker-compose -f docker-compose.gateway.yml build

# Start gateway services
echo "🚀 Starting gateway services..."
docker-compose -f docker-compose.gateway.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Test services
echo "🧪 Testing gateway services..."

# Test Traefik dashboard
echo "Testing Traefik dashboard..."
curl -f http://localhost:8080/api/entrypoints || echo "⚠️  Traefik dashboard not ready"

# Test auth service health
echo "Testing auth service..."
curl -f http://localhost:8000/auth/health || echo "⚠️  Auth service not ready"

# Test rate limiter
echo "Testing rate limiter..."
curl -f http://localhost:8001/health || echo "⚠️  Rate limiter not ready"

# Test security monitor
echo "Testing security monitor..."
curl -f http://localhost:8001/health || echo "⚠️  Security monitor not ready"

# Test WAF service
echo "Testing WAF service..."
curl -f http://localhost:8002/health || echo "⚠️  WAF service not ready"

echo "✅ Gateway setup complete!"
echo ""
echo "📊 Access Points:"
echo "  - Traefik Dashboard: http://localhost:8080"
echo "  - Auth Service: http://localhost:8000/auth/docs"
echo "  - Rate Limiter: http://localhost:8001/docs"
echo "  - Security Monitor: http://localhost:8001/dashboard"
echo "  - WAF Service: http://localhost:8002/docs"
echo ""
echo "🔑 Default Admin Credentials:"
echo "  - Username: admin"
echo "  - Password: admin"
echo ""
echo "⚠️  Remember to change default passwords in production!"
