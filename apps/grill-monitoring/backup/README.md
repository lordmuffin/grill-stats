# Grill Stats Backup System

## Overview

This comprehensive backup system provides enterprise-grade data protection for the Grill Stats ThermoWorks BBQ monitoring platform. The system handles automated backups, verification, and recovery for all critical data stores.

## Architecture

### Databases Protected

- **PostgreSQL**: User data, device configurations, encrypted credentials
- **InfluxDB**: Time-series temperature data with multiple retention policies
- **Redis**: Session data and caching (less critical)

### Key Features

- **Automated Backups**: Daily scheduled backups with configurable retention
- **Encryption**: AES-256-CBC encryption for all backup files
- **Compression**: Gzip compression to optimize storage usage
- **Verification**: Daily integrity checks and backup validation
- **Remote Storage**: S3-compatible remote backup storage
- **Monitoring**: Prometheus metrics and Grafana dashboards
- **Alerting**: Comprehensive alert rules for backup failures
- **Recovery**: Automated restore scripts with dry-run and test modes

## Backup Schedule & Retention

| Service    | Schedule  | Retention | RTO    | RPO    |
|------------|-----------|-----------|--------|--------|
| PostgreSQL | 2:00 AM   | 30 days   | 1 hour | 24 hrs |
| InfluxDB   | 3:00 AM   | 7 days    | 2 hours| 24 hrs |
| Redis      | 4:00 AM   | 7 days    | 30 min | 24 hrs |
| Verification | 6:00 AM | 30 days   | N/A    | N/A    |

## Quick Start

### Deploy Backup System

```bash
# Production deployment
kubectl apply -k apps/grill-stats/backup/overlays/prod

# Development deployment
kubectl apply -k apps/grill-stats/backup/overlays/dev
```

### Check Backup Status

```bash
# View backup jobs
kubectl get cronjobs -n grill-stats

# Check recent backup executions
kubectl get jobs -n grill-stats -l app.kubernetes.io/component=backup

# View backup logs
kubectl logs -n grill-stats -l app.kubernetes.io/name=postgresql-backup
```

### Manual Backup

```bash
# PostgreSQL backup
kubectl create job --from=cronjob/postgresql-backup manual-pg-backup-$(date +%Y%m%d) -n grill-stats

# InfluxDB backup
kubectl create job --from=cronjob/influxdb-backup manual-influx-backup-$(date +%Y%m%d) -n grill-stats

# Redis backup
kubectl create job --from=cronjob/redis-backup manual-redis-backup-$(date +%Y%m%d) -n grill-stats
```

## Disaster Recovery

### Test Restore (Recommended)

```bash
# Deploy restore job
kubectl apply -f apps/grill-stats/backup/base/backup-restore-job.yaml

# Wait for job to be ready
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=backup-restore-job -n grill-stats

# Test full restore (dry run)
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/full-restore.sh --test --dry-run

# Test individual service restore
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/postgresql-restore.sh --test --dry-run /backup/postgresql/latest_backup.tar.gz.enc
```

### Emergency Recovery

```bash
# Full platform restore (DANGEROUS - TEST FIRST)
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/full-restore.sh --force

# Individual service restore
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/postgresql-restore.sh --force /backup/postgresql/latest_backup.tar.gz.enc
```

## Monitoring & Alerting

### Grafana Dashboard

Access the backup monitoring dashboard at:
- URL: `http://grafana.example.com/d/backup-monitoring`
- Metrics: Job success rates, backup sizes, storage usage, duration

### Prometheus Metrics

Key metrics available:
- `kube_job_status_succeeded`: Backup job success/failure
- `kube_job_status_completion_time`: Backup completion time
- `node_filesystem_avail_bytes`: Backup storage availability

### Alert Rules

The system includes alerts for:
- Backup job failures
- Storage capacity warnings
- Backup age warnings
- Verification failures

## Configuration

### Environment Variables

Key configuration options in `backup-config` ConfigMap:

```yaml
BACKUP_RETENTION_DAYS: "30"
BACKUP_REMOTE_SYNC: "true"
BACKUP_REMOTE_BASE: "s3://grill-stats-backups"
BACKUP_ENCRYPTION_ENABLED: "true"
NOTIFICATION_ENABLED: "true"
```

### Secrets Management

Secrets are managed via 1Password Connect:

- `backup-encryption-secret`: Encryption keys, S3 credentials
- `backup-notification-secret`: Webhook URLs, notification tokens
- Database connection secrets referenced from existing services

### Schedule Modification

To modify backup schedules:

```bash
# Edit CronJob directly
kubectl edit cronjob postgresql-backup -n grill-stats

# Or update via Kustomize overlay
vim apps/grill-stats/backup/overlays/prod/backup-config.yaml
```

## Storage Structure

```
/backup/
├── postgresql/
│   ├── postgresql_20240101_020000.tar.gz.enc
│   ├── weekly/
│   │   └── postgresql_weekly_20240107_020000.tar.gz.enc
│   ├── monthly/
│   │   └── postgresql_monthly_20240101_020000.tar.gz.enc
│   └── latest_backup.tar.gz.enc -> postgresql_20240101_020000.tar.gz.enc
├── influxdb/
│   ├── influxdb_20240101_030000.tar.gz.enc
│   ├── weekly/
│   └── monthly/
├── redis/
│   ├── redis_20240101_040000.tar.gz.enc
│   └── weekly/
└── verification/
    ├── verification_report_20240101.json
    ├── verification_report_20240101.txt
    └── latest_verification.json -> verification_report_20240101.json
```

## Security

### Encryption

- **Algorithm**: AES-256-CBC with PBKDF2 key derivation
- **Key Management**: 1Password Connect integration
- **Iterations**: 100,000 iterations for key derivation
- **Salt**: Random salt for each backup file

### Access Control

- **RBAC**: Kubernetes Role-Based Access Control
- **Service Accounts**: Dedicated service accounts for backup operations
- **Network Policies**: Restricted network access for backup jobs
- **Secret Management**: No secrets in configuration files

### Compliance

- **Encryption at Rest**: All backups encrypted
- **Encryption in Transit**: TLS for all remote transfers
- **Access Logging**: All backup operations logged
- **Audit Trail**: Complete audit trail for all operations

## Troubleshooting

### Common Issues

1. **Backup Job Fails**
   ```bash
   # Check job logs
   kubectl logs -n grill-stats job/postgresql-backup
   
   # Check service connectivity
   kubectl exec -n grill-stats -it backup-restore-job -- nc -zv postgresql 5432
   
   # Check storage availability
   kubectl exec -n grill-stats -it backup-restore-job -- df -h /backup
   ```

2. **Storage Full**
   ```bash
   # Check storage usage
   kubectl exec -n grill-stats -it backup-restore-job -- df -h /backup
   
   # Clean up old backups
   kubectl exec -n grill-stats -it backup-restore-job -- find /backup -name "*.tar.gz.enc" -mtime +30 -delete
   
   # Check retention policies
   kubectl get configmap backup-config -n grill-stats -o yaml
   ```

3. **Verification Fails**
   ```bash
   # Check verification logs
   kubectl logs -n grill-stats -l app.kubernetes.io/name=backup-verification
   
   # Test backup integrity
   kubectl exec -n grill-stats -it backup-restore-job -- /scripts/verify-backups.sh
   
   # Check encryption keys
   kubectl get secret backup-encryption-secret -n grill-stats
   ```

### Debug Commands

```bash
# List all backup files
kubectl exec -n grill-stats -it backup-restore-job -- find /backup -name "*.tar.gz.enc" -ls

# Check backup file sizes
kubectl exec -n grill-stats -it backup-restore-job -- du -sh /backup/*

# Verify backup integrity
kubectl exec -n grill-stats -it backup-restore-job -- /scripts/verify-backups.sh

# Check database connectivity
kubectl exec -n grill-stats -it backup-restore-job -- pg_isready -h postgresql -p 5432
kubectl exec -n grill-stats -it backup-restore-job -- redis-cli -h redis ping
kubectl exec -n grill-stats -it backup-restore-job -- curl -f http://influxdb:8086/health
```

## Development

### Testing

```bash
# Run backup tests
kubectl create job --from=cronjob/postgresql-backup test-pg-backup -n grill-stats

# Test restore process
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/postgresql-restore.sh --test --dry-run /backup/postgresql/latest_backup.tar.gz.enc

# Verify backup integrity
kubectl exec -it backup-restore-job -n grill-stats -- /scripts/verify-backups.sh
```

### Adding New Services

1. Create backup script in `scripts/` directory
2. Create CronJob configuration
3. Add to base `kustomization.yaml`
4. Create environment-specific overlays
5. Add monitoring and alerting rules

### Modifying Backup Scripts

Scripts are stored in the `backup-scripts` ConfigMap:

```bash
# Edit scripts
kubectl edit configmap backup-scripts -n grill-stats

# Or update files and apply
kubectl apply -k apps/grill-stats/backup/overlays/prod
```

## Performance Tuning

### Resource Limits

Adjust resource limits in environment overlays:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
    ephemeral-storage: "2Gi"
  limits:
    memory: "2Gi"
    cpu: "1000m"
    ephemeral-storage: "10Gi"
```

### Backup Optimization

- **Compression Level**: Configurable gzip compression
- **Parallel Jobs**: Multiple backup streams for large databases
- **Incremental Backups**: Future enhancement for PostgreSQL
- **Deduplication**: Storage-level deduplication for efficiency

## Future Enhancements

- **Incremental Backups**: Reduce backup time and storage
- **Point-in-Time Recovery**: PostgreSQL WAL-based recovery
- **Cross-Region Replication**: Multi-region disaster recovery
- **Automated Testing**: Regular restore validation
- **API Integration**: RESTful backup management interface
- **Machine Learning**: Predictive failure detection

## Support

For issues, questions, or contributions:

1. **Documentation**: Check this README and runbook
2. **Logs**: Review backup job logs and verification reports
3. **Monitoring**: Check Grafana dashboards and Prometheus metrics
4. **Issues**: Create GitHub issues for bugs or feature requests
5. **Discussions**: Use GitHub discussions for questions

## License

This backup system is part of the Grill Stats project and follows the same license terms.