# Redis Deployment for Grill-Stats

## Overview

This document describes the complete Redis deployment setup for the Grill-Stats BBQ monitoring application. The deployment includes high-performance caching, session management, monitoring, backup, and recovery capabilities.

## Architecture

### Components

1. **Redis StatefulSet**: Primary Redis instance with persistent storage
2. **Redis Sentinel**: High availability and automatic failover (production only)
3. **Redis Exporter**: Prometheus metrics collection
4. **Backup System**: Automated backup with verification
5. **Network Policies**: Security controls for Redis access

### Database Usage

The Redis deployment uses multiple databases to organize different types of data:

- **Database 0**: Session management (JWT tokens, user sessions)
- **Database 1**: Live temperature data (real-time readings)
- **Database 2**: Device status (connection and configuration)
- **Database 3**: API response caching
- **Database 4**: ThermoWorks API responses and rate limiting
- **Database 5**: Rate limiting counters
- **Database 6**: SSE connection tracking
- **Database 7**: Aggregated temperature data

## Deployment Configuration

### Base Configuration

Location: `/kustomize/base/databases/`

- `redis.yaml`: StatefulSet and Service definitions
- `redis-config.yaml`: Configuration and cache strategy
- `redis-sentinel.yaml`: High availability setup
- `redis-monitoring.yaml`: Prometheus monitoring
- `redis-backup.yaml`: Backup and recovery
- `redis-network-policy.yaml`: Network security

### Environment-Specific Configurations

#### Development (dev-lab)
- Single Redis instance without Sentinel
- 512MB memory limit
- 5GB storage
- Weekly backups
- Relaxed cache TTL for testing
- Verbose logging for debugging

#### Production (prod-lab)
- Redis with 3-node Sentinel cluster
- 2GB memory limit
- 20GB storage
- Daily backups with verification
- Optimized cache TTL
- Production security hardening

## Configuration Details

### Redis Configuration

Key settings optimized for grill-stats use cases:

```redis
# Memory management
maxmemory 768mb (dev) / 1536mb (prod)
maxmemory-policy allkeys-lru

# Persistence
save 900 1 / 300 10 / 60 10000
appendonly yes (prod) / no (dev)

# Performance
lazyfree-lazy-eviction yes
jemalloc-bg-thread yes
hash-max-ziplist-entries 512
```

### Cache Strategy

Each cache type has specific TTL and key prefix:

```json
{
  "session_management": {
    "ttl": 3600,
    "key_prefix": "session:"
  },
  "live_temperature_data": {
    "ttl": 30,
    "key_prefix": "temp:"
  },
  "device_status": {
    "ttl": 60,
    "key_prefix": "device:"
  }
}
```

## Security Features

### Authentication
- Password-based authentication using Kubernetes secrets
- Command renaming for dangerous operations (production)
- Protected mode enabled

### Network Security
- Network policies restricting access to grill-stats services
- Separate policies for Redis, Sentinel, and Exporter
- DNS resolution allowed for service discovery

### Security Context
- Non-root user (999:999)
- Read-only root filesystem where applicable
- Dropped capabilities

## Monitoring and Alerting

### Metrics Collection
- Redis Exporter provides comprehensive metrics
- ServiceMonitor for Prometheus scraping
- Custom metrics for cache hit ratios and key counts

### Alerting Rules
- Redis instance down
- High memory usage (>90%)
- High connection count (>100)
- Slow query detection
- Low cache hit ratio (<80%)
- Replication lag monitoring

### Dashboards
- Redis performance metrics
- Cache utilization by database
- Connection and command statistics
- Memory and persistence status

## Backup and Recovery

### Automated Backups
- Daily backups at 2 AM (production)
- Weekly backups (development)
- RDB and AOF backup creation
- Compression and metadata generation
- Automatic cleanup (7-day retention)

### Backup Verification
- Daily verification job
- RDB and AOF integrity checks
- Metadata validation
- Automated failure notifications

### Recovery Process
1. Stop Redis service
2. Extract backup files
3. Create restore job
4. Copy data to Redis volume
5. Restart Redis service
6. Verify operation

## Operations

### Deployment Commands

```bash
# Apply base configuration
kubectl apply -k kustomize/base/databases/

# Deploy to development
kubectl apply -k kustomize/overlays/dev-lab/

# Deploy to production
kubectl apply -k kustomize/overlays/prod-lab/
```

### Monitoring Commands

```bash
# Check Redis status
kubectl get pods -l app.kubernetes.io/name=redis -n grill-stats

# View Redis logs
kubectl logs -f redis-0 -n grill-stats

# Check metrics
kubectl port-forward svc/redis-exporter 9121:9121 -n grill-stats
curl http://localhost:9121/metrics

# Monitor Sentinel (production)
kubectl logs -f redis-sentinel-0 -n grill-stats
```

### Backup Commands

```bash
# Trigger manual backup
kubectl create job --from=cronjob/redis-backup manual-backup-$(date +%s) -n grill-stats

# List backups
kubectl exec -it redis-0 -n grill-stats -- ls -la /backup/

# Verify backup
kubectl create job --from=cronjob/redis-backup-verification verify-$(date +%s) -n grill-stats
```

### Scaling Operations

```bash
# Scale Redis Sentinel (production only)
kubectl scale statefulset redis-sentinel --replicas=3 -n grill-stats

# Check Sentinel status
kubectl exec -it redis-sentinel-0 -n grill-stats -- redis-cli -p 26379 SENTINEL MASTERS
```

## Troubleshooting

### Common Issues

1. **Redis Pod Not Starting**
   - Check persistent volume claims
   - Verify configuration syntax
   - Review security contexts

2. **High Memory Usage**
   - Monitor cache hit ratios
   - Adjust maxmemory settings
   - Review TTL configurations

3. **Connection Issues**
   - Verify network policies
   - Check service discovery
   - Validate authentication

4. **Backup Failures**
   - Check storage permissions
   - Verify backup volume claims
   - Review backup job logs

### Debugging Commands

```bash
# Connect to Redis CLI
kubectl exec -it redis-0 -n grill-stats -- redis-cli -a $REDIS_PASSWORD

# Check Redis configuration
kubectl exec -it redis-0 -n grill-stats -- redis-cli -a $REDIS_PASSWORD CONFIG GET "*"

# Monitor Redis operations
kubectl exec -it redis-0 -n grill-stats -- redis-cli -a $REDIS_PASSWORD MONITOR

# Check memory usage
kubectl exec -it redis-0 -n grill-stats -- redis-cli -a $REDIS_PASSWORD INFO memory

# View slow queries
kubectl exec -it redis-0 -n grill-stats -- redis-cli -a $REDIS_PASSWORD SLOWLOG GET 10
```

## Performance Optimization

### Memory Management
- Configured LRU eviction policy
- Optimized data structure settings
- Memory-efficient persistence options

### Connection Pooling
- Recommended connection pool settings
- Health check intervals
- Timeout configurations

### Cache Optimization
- TTL tuning for different data types
- Key prefix organization
- Database separation strategy

## Integration with Grill-Stats Services

### Session Management
- JWT token storage in database 0
- Session expiry notifications
- User authentication state

### Live Data Caching
- Real-time temperature readings
- Device status updates
- SSE connection management

### API Response Caching
- ThermoWorks API responses
- Rate limiting enforcement
- Performance optimization

## Maintenance

### Regular Tasks
- Monitor memory usage and adjust limits
- Review cache hit ratios and TTL settings
- Verify backup integrity
- Update Redis version as needed

### Capacity Planning
- Monitor data growth trends
- Plan storage expansion
- Adjust resource limits

### Security Updates
- Regular password rotation
- Network policy reviews
- Configuration audits

## Future Enhancements

### Planned Improvements
- Redis Cluster for horizontal scaling
- Cross-region replication
- Advanced monitoring dashboards
- Automated failover testing

### Performance Enhancements
- Memory optimization studies
- Cache warming strategies
- Connection pooling optimization
