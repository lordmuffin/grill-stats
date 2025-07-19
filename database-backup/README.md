# Database Backup and Restore Procedures

This document outlines the backup and restore procedures for the Grill Monitoring Platform's database infrastructure, including PostgreSQL, InfluxDB, and Redis.

## Table of Contents

- [Overview](#overview)
- [Backup Strategies](#backup-strategies)
- [Backup Frequency and Retention](#backup-frequency-and-retention)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [Restore Procedures](#restore-procedures)
- [Verification Procedures](#verification-procedures)
- [Disaster Recovery](#disaster-recovery)

## Overview

The Grill Monitoring Platform uses three types of databases:

1. **PostgreSQL**: Relational database for device management and user data
2. **InfluxDB**: Time-series database for temperature data
3. **Redis**: In-memory database for caching and pub/sub

Each database requires different backup strategies to ensure data integrity and recoverability.

## Backup Strategies

### PostgreSQL

- **Method**: Full database dumps using `pg_dump`
- **Format**: Custom format (compressed binary)
- **Verification**: Integrity check using `pg_restore -l`
- **Retention**: 30 days for daily backups, 52 weeks for weekly backups, 12 months for monthly backups

### InfluxDB

- **Method**: Native InfluxDB backup using `influxd backup`
- **Format**: InfluxDB backup format (tar.gz)
- **Verification**: Manifest file existence check
- **Retention**: 30 days for daily backups, 52 weeks for weekly backups, 12 months for monthly backups

### Redis

- **Method**: RDB snapshots using `BGSAVE` command
- **Format**: RDB files (compressed with gzip)
- **Verification**: File size check
- **Additional**: AOF persistence for real-time durability

## Backup Frequency and Retention

| Type | Frequency | Retention |
|------|-----------|-----------|
| Daily Backups | Every day | 30 days |
| Weekly Backups | Sundays | 52 weeks |
| Monthly Backups | 1st of month | 12 months |

## Development Environment

In the development environment, backups are managed through a dedicated database backup service in the Docker Compose stack.

### Running Manual Backups

```bash
# PostgreSQL backup
docker-compose exec db-backup /scripts/postgres-backup.sh

# InfluxDB backup
docker-compose exec db-backup /scripts/influxdb-backup.sh

# Redis backup
docker-compose exec db-backup /scripts/redis-backup.sh
```

### Backup Storage

Backups are stored in a Docker volume named `backups_volume`, which can be accessed from the `db-backup` service. The backup directory structure is:

```
/backups/
├── postgres/
│   ├── daily/
│   ├── weekly/
│   └── monthly/
├── influxdb/
│   ├── daily/
│   ├── weekly/
│   └── monthly/
└── redis/
    ├── daily/
    ├── weekly/
    └── monthly/
```

## Production Environment

In the production environment, backups are managed through Kubernetes CronJobs.

### Backup Schedule

- PostgreSQL: Daily at 1:00 AM
- InfluxDB: Daily at 2:00 AM
- Redis: Daily at 3:00 AM

### Backup Storage

Backups are stored on a persistent volume with the following specifications:

- PVC Name: `db-backups-pvc`
- Storage Size: 50Gi
- Access Mode: ReadWriteMany

### Monitoring Backup Jobs

```bash
# Check backup CronJob status
kubectl get cronjobs -n grill-stats

# Check last backup job execution
kubectl get jobs -n grill-stats

# View backup job logs
kubectl logs job/postgres-backup-<timestamp> -n grill-stats
kubectl logs job/influxdb-backup-<timestamp> -n grill-stats
kubectl logs job/redis-backup-<timestamp> -n grill-stats
```

## Restore Procedures

### PostgreSQL Restore

```bash
# Local development environment
docker-compose exec db-backup bash -c "PGPASSWORD=postgres pg_restore -h postgres -U postgres -d grill_stats -c /backups/postgres/daily/grill_stats_YYYYMMDD_HHMMSS.sql.gz"

# Production Kubernetes environment
kubectl exec -it postgres-0 -n grill-stats -- bash -c "PGPASSWORD=\$POSTGRES_PASSWORD pg_restore -h localhost -U postgres -d grill_stats -c /path/to/backup/grill_stats_YYYYMMDD_HHMMSS.sql.gz"
```

### InfluxDB Restore

```bash
# Local development environment
docker-compose exec db-backup bash -c "mkdir -p /tmp/influxdb-restore && tar -xzf /backups/influxdb/daily/grill_stats_YYYYMMDD_HHMMSS.tar.gz -C /tmp/influxdb-restore && influxd restore -database grill_stats -datadir /var/lib/influxdb/data -metadir /var/lib/influxdb/meta /tmp/influxdb-restore"

# Production Kubernetes environment
kubectl exec -it influxdb-0 -n grill-stats -- bash -c "mkdir -p /tmp/influxdb-restore && tar -xzf /path/to/backup/grill_stats_YYYYMMDD_HHMMSS.tar.gz -C /tmp/influxdb-restore && influxd restore -database grill_stats -datadir /var/lib/influxdb/data -metadir /var/lib/influxdb/meta /tmp/influxdb-restore"
```

### Redis Restore

```bash
# Local development environment
docker-compose stop redis
docker-compose exec db-backup bash -c "gunzip -c /backups/redis/daily/redis_YYYYMMDD_HHMMSS.rdb.gz > /tmp/dump.rdb"
docker cp /tmp/dump.rdb grill-stats_redis_1:/data/dump.rdb
docker-compose start redis

# Production Kubernetes environment
kubectl scale deployment redis -n grill-stats --replicas=0
kubectl exec -it db-backup-pod -n grill-stats -- bash -c "gunzip -c /backups/redis/daily/redis_YYYYMMDD_HHMMSS.rdb.gz > /tmp/dump.rdb"
kubectl cp /tmp/dump.rdb redis-0:/data/dump.rdb -n grill-stats
kubectl scale deployment redis -n grill-stats --replicas=1
```

## Verification Procedures

Each backup script includes a verification step to ensure backup integrity:

- **PostgreSQL**: Uses `pg_restore -l` to check backup file validity
- **InfluxDB**: Checks for the existence of manifest files
- **Redis**: Verifies file size is above minimum threshold

## Disaster Recovery

### RTO and RPO Targets

- **Recovery Time Objective (RTO)**: < 1 hour
- **Recovery Point Objective (RPO)**: < 15 minutes

### Cross-Region Replication

For production environments, consider implementing:

1. **PostgreSQL**: Streaming replication with standby server in a different region
2. **InfluxDB**: Continuous queries to replicate data to a secondary cluster
3. **Redis**: Redis Sentinel or Redis Cluster with cross-region replicas

### Automated Recovery Steps

1. **Detect Failure**: Monitor database health with Prometheus alerts
2. **Failover**: Automated failover for replicated databases
3. **Restore**: If no replica is available, restore from the most recent backup
4. **Verify**: Run application health checks to verify successful recovery
5. **Sync**: Re-synchronize any missed data from application logs or message queues

### Disaster Recovery Testing

Regularly test the disaster recovery procedures:

1. Simulate database failures
2. Practice restore procedures in a test environment
3. Measure actual RTO and RPO achieved
4. Document findings and improve procedures

## Backup Automation

Backup automation is implemented through:

1. **Development**: Docker Compose service with manual execution
2. **Production**: Kubernetes CronJobs scheduled daily

Backup jobs send alerts on failure through the monitoring system.
