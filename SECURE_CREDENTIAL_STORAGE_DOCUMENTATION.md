# Secure Credential Storage Documentation

## Overview

This document provides comprehensive documentation for User Story 5: Secure Credential Storage implementation in the ThermoWorks BBQ monitoring application. The implementation provides enterprise-grade security for storing and managing ThermoWorks user credentials with AES-256 encryption, automated key rotation, and comprehensive audit logging.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Security Features](#security-features)
3. [Components](#components)
4. [Deployment Guide](#deployment-guide)
5. [Configuration](#configuration)
6. [API Documentation](#api-documentation)
7. [Security Considerations](#security-considerations)
8. [Monitoring and Alerting](#monitoring-and-alerting)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

## Architecture Overview

The secure credential storage system implements a multi-layered security architecture:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                Client Applications                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                              Authentication Service                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                            Rate Limiting                                   ││
│  │  ┌─────────────────────────────────────────────────────────────────────────┐││
│  │  │                       Encryption Service                               │││
│  │  │  ┌─────────────────────────────────────────────────────────────────────┐│││
│  │  │  │                    HashiCorp Vault                                 ││││
│  │  │  │                 (Transit Engine)                                  ││││
│  │  │  └─────────────────────────────────────────────────────────────────────┘│││
│  │  └─────────────────────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────────────┤
│                            Database Layer                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                   Encrypted Credential Storage                           │ │
│  │                     (PostgreSQL)                                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────┤
│                        Secret Management                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                      1Password Connect                                   │ │
│  │                    (Vault Token Storage)                                 │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────┤
│                        Audit & Monitoring                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                     Comprehensive Logging                                │ │
│  │                    Key Rotation Automation                               │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Security Features

### 1. AES-256 Encryption
- **Algorithm**: AES-256-GCM96 (Galois/Counter Mode)
- **Key Management**: HashiCorp Vault Transit Engine
- **Key Rotation**: Automated rotation every 30 days
- **Key Versioning**: Multiple key versions supported for backward compatibility

### 2. No Plain Text Storage
- **Database**: Only encrypted ciphertext stored in PostgreSQL
- **Memory**: Credentials decrypted only in memory during API calls
- **Logs**: No sensitive data logged in plain text
- **Backups**: All backups contain only encrypted data

### 3. Secure Key Management
- **Vault Transit Engine**: Encryption-as-a-Service approach
- **Key Isolation**: Keys never leave Vault boundary
- **Access Control**: Role-based access with Kubernetes service accounts
- **Audit Trail**: All key operations logged and monitored

### 4. Rate Limiting
- **Encryption Operations**: 100 requests per user per hour
- **Decryption Operations**: 100 requests per user per hour
- **Sliding Window**: 60-minute sliding window
- **User Isolation**: Rate limits applied per user

### 5. Comprehensive Audit Logging
- **Structured Logging**: JSON format with standardized fields
- **Event Types**: All credential operations categorized
- **Retention**: 90-day retention with automated cleanup
- **Monitoring**: Real-time alerts for security events

## Components

### 1. Encryption Service

**Location**: `services/encryption-service/`

**Responsibilities**:
- Encrypt/decrypt ThermoWorks credentials
- Manage rate limiting
- Validate input data
- Audit logging
- Health monitoring

**Key Files**:
- `src/credential_encryption_service.py` - Core encryption service
- `src/audit_logger.py` - Enhanced audit logging
- `main.py` - Flask API application
- `requirements.txt` - Python dependencies

### 2. Authentication Service

**Location**: `services/auth-service/`

**Responsibilities**:
- User authentication and session management
- ThermoWorks credential storage integration
- JWT token generation
- Rate limit enforcement

**Key Files**:
- `main.py` - Flask API with credential endpoints
- `credential_integration.py` - Integration with encryption service

### 3. Database Schema

**Location**: `database-init/`

**Key Files**:
- `setup-encrypted-credentials.sql` - Complete database setup
- `add_thermoworks_credentials_table.sql` - Credential table creation
- `migrate-to-encrypted-credentials.sql` - Migration utilities

**Tables**:
- `thermoworks_credentials` - Encrypted credential storage
- `credential_access_log` - Audit log table
- `encryption_key_management` - Key management metadata

### 4. Key Rotation Automation

**Location**: `scripts/key-rotation-automation.py`

**Responsibilities**:
- Automated key rotation based on age and usage
- Health monitoring of encryption keys
- Backup management
- Notification system

### 5. Kubernetes Deployment

**Location**: `kustomize/base/core-services/`

**Key Files**:
- `encryption-service.yaml` - Encryption service deployment
- `auth-service.yaml` - Authentication service deployment
- `key-rotation-cronjob.yaml` - Automated key rotation

### 6. 1Password Integration

**Location**: `kustomize/base/namespace/1password-secrets.yaml`

**Responsibilities**:
- Secure storage of Vault tokens
- Automated secret synchronization
- Database credentials management
- API key management

## Deployment Guide

### Prerequisites

1. **Kubernetes Cluster**: v1.25+ with proper RBAC
2. **HashiCorp Vault**: v1.12+ with Transit Engine
3. **PostgreSQL**: v14+ with proper permissions
4. **1Password Connect**: Deployed and configured
5. **Docker**: For building container images

### Step 1: Setup HashiCorp Vault

```bash
# Run the Vault setup script
./scripts/setup-vault-transit.sh

# Verify Vault configuration
./scripts/test-vault-encryption.sh
```

### Step 2: Configure 1Password Connect

```bash
# Setup 1Password items
./scripts/setup-1password-items.sh

# Validate 1Password integration
./scripts/setup-1password-items.sh validate
```

### Step 3: Database Migration

```bash
# Run database setup
./scripts/setup-database.sh

# Verify database schema
./scripts/setup-database.sh validate
```

### Step 4: Deploy Services

```bash
# Deploy all secure credential components
./scripts/deploy-secure-credentials.sh

# Check deployment status
./scripts/deploy-secure-credentials.sh validate
```

### Step 5: Testing

```bash
# Run comprehensive tests
./scripts/run-encryption-tests.sh

# Run security tests only
./scripts/run-encryption-tests.sh security
```

## Configuration

### Environment Variables

#### Encryption Service
```bash
# Vault Configuration
VAULT_URL=http://vault.vault.svc.cluster.local:8200
VAULT_TOKEN=<from-1password>

# Rate Limiting
ENCRYPTION_RATE_LIMIT=100
ENCRYPTION_RATE_WINDOW=60

# Audit Logging
AUDIT_LOG_FILE=/var/log/grill-stats/audit.log
AUDIT_LOG_LEVEL=INFO
AUDIT_ENABLE_SYSLOG=false
AUDIT_ENABLE_REMOTE=false
```

#### Authentication Service
```bash
# Database Configuration
DB_HOST=postgresql.grill-stats.svc.cluster.local
DB_PORT=5432
DB_NAME=grill_stats
DB_USER=<from-1password>
DB_PASSWORD=<from-1password>

# Encryption Service
ENCRYPTION_SERVICE_URL=http://encryption-service:8082

# JWT Configuration
JWT_SECRET=<from-1password>
SECRET_KEY=<from-1password>
```

#### Key Rotation
```bash
# Rotation Schedule
ROTATION_INTERVAL_HOURS=720
MAX_KEY_AGE_DAYS=90
MAX_USAGE_COUNT=1000000

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_PATH=/var/backups/vault-keys

# Monitoring
HEALTH_CHECK_INTERVAL_MINUTES=60
MONITORING_ENABLED=true
```

### Configuration Files

#### Vault Policy
```hcl
# Encryption service policy
path "transit/encrypt/thermoworks-user-credentials" {
  capabilities = ["create", "update"]
}

path "transit/decrypt/thermoworks-user-credentials" {
  capabilities = ["create", "update"]
}

path "transit/keys/thermoworks-user-credentials" {
  capabilities = ["read"]
}
```

#### Database Configuration
```sql
-- Required database setup
CREATE DATABASE grill_stats;
CREATE USER grill_stats_app WITH ENCRYPTED PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE grill_stats TO grill_stats_app;
```

## API Documentation

### Encryption Service Endpoints

#### POST /encrypt
Encrypts ThermoWorks credentials.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "user_id": "123"
}
```

**Response**:
```json
{
  "status": "success",
  "encrypted_credential": {
    "encrypted_email": "vault:v1:...",
    "encrypted_password": "vault:v1:...",
    "metadata": {
      "key_version": 1,
      "algorithm": "aes256-gcm96",
      "encrypted_at": "2024-01-01T00:00:00Z",
      "access_count": 0
    }
  }
}
```

#### POST /decrypt
Decrypts ThermoWorks credentials.

**Request**:
```json
{
  "encrypted_credential": {
    "encrypted_email": "vault:v1:...",
    "encrypted_password": "vault:v1:...",
    "metadata": {...}
  },
  "user_id": "123"
}
```

**Response**:
```json
{
  "status": "success",
  "credentials": {
    "email": "user@example.com",
    "password": "secure_password"
  }
}
```

#### GET /rate-limit/{user_id}
Check rate limit status for a user.

**Response**:
```json
{
  "status": "success",
  "rate_limit": {
    "user_id": "123",
    "remaining_requests": 95,
    "is_allowed": true,
    "max_requests": 100,
    "window_seconds": 3600
  }
}
```

### Authentication Service Endpoints

#### POST /api/auth/thermoworks/connect
Connect ThermoWorks account with encrypted credential storage.

**Request**:
```json
{
  "thermoworks_email": "user@example.com",
  "thermoworks_password": "secure_password"
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "connected": true,
    "encrypted": true,
    "thermoworks_email": "user@example.com"
  }
}
```

#### GET /api/auth/thermoworks/status
Get ThermoWorks connection status.

**Response**:
```json
{
  "status": "success",
  "data": {
    "connected": true,
    "encrypted": true,
    "is_active": true,
    "last_validated": "2024-01-01T00:00:00Z",
    "validation_attempts": 0,
    "encryption_info": {
      "algorithm": "aes256-gcm96",
      "key_version": 1,
      "encrypted_at": "2024-01-01T00:00:00Z",
      "access_count": 5
    }
  }
}
```

## Security Considerations

### 1. Threat Model

**Protected Assets**:
- ThermoWorks user credentials (email/password)
- Vault encryption keys
- Database connection strings
- API tokens

**Threat Actors**:
- External attackers
- Malicious insiders
- Compromised applications
- Database breaches

**Attack Vectors**:
- SQL injection
- API abuse
- Memory dumps
- Log file exposure
- Network interception

### 2. Security Controls

**Encryption**:
- AES-256-GCM encryption for credentials
- TLS 1.3 for all network communications
- Encrypted storage for all sensitive data

**Access Control**:
- Role-based access control (RBAC)
- Principle of least privilege
- Service account isolation
- Network segmentation

**Monitoring**:
- Real-time security event monitoring
- Automated threat detection
- Audit log analysis
- Performance monitoring

### 3. Compliance

**Standards**:
- SOC 2 Type II
- ISO 27001
- NIST Cybersecurity Framework
- OWASP Top 10

**Data Protection**:
- GDPR compliance for EU users
- CCPA compliance for California users
- Data minimization principles
- Right to erasure support

## Monitoring and Alerting

### 1. Key Metrics

**Performance Metrics**:
- Encryption/decryption latency
- API response times
- Rate limit utilization
- Database query performance

**Security Metrics**:
- Failed authentication attempts
- Rate limit violations
- Encryption key age
- Audit log events

**Availability Metrics**:
- Service uptime
- Vault connectivity
- Database availability
- Key rotation success rate

### 2. Alerting Rules

**Critical Alerts**:
- Vault connectivity loss
- Encryption key rotation failure
- Multiple authentication failures
- Database connection errors

**Warning Alerts**:
- High rate limit utilization
- Encryption key age approaching limit
- Slow API response times
- Audit log errors

### 3. Dashboards

**Security Dashboard**:
- Real-time threat indicators
- Authentication success/failure rates
- Encryption operation trends
- Key rotation status

**Performance Dashboard**:
- API latency metrics
- Database performance
- Rate limiting statistics
- Service availability

## Troubleshooting

### Common Issues

#### 1. Vault Authentication Failures

**Symptoms**:
- `Failed to authenticate with Vault` errors
- Encryption service returning 503 errors

**Solutions**:
```bash
# Check Vault token validity
vault token lookup

# Verify Kubernetes service account
kubectl get serviceaccount encryption-service -n grill-stats

# Test Vault connectivity
curl -H "X-Vault-Token: $VAULT_TOKEN" $VAULT_URL/v1/sys/health
```

#### 2. Rate Limiting Issues

**Symptoms**:
- `Rate limit exceeded` errors
- 429 HTTP status codes

**Solutions**:
```bash
# Check rate limit status
curl -H "Authorization: Bearer $JWT_TOKEN" \
     "$AUTH_SERVICE_URL/api/auth/thermoworks/rate-limit"

# Adjust rate limits (if needed)
kubectl patch configmap encryption-service-config \
  -p '{"data":{"ENCRYPTION_RATE_LIMIT":"200"}}'
```

#### 3. Database Connection Issues

**Symptoms**:
- Database connection errors
- Credential storage failures

**Solutions**:
```bash
# Test database connectivity
kubectl exec -it postgresql-0 -- psql -U grill_stats_app -d grill_stats

# Check database credentials
kubectl get secret database-credentials-secret -o yaml

# Verify database schema
./scripts/setup-database.sh validate
```

#### 4. Key Rotation Problems

**Symptoms**:
- Key rotation failures
- Old key version errors

**Solutions**:
```bash
# Check key rotation status
./scripts/key-rotation-automation.py --status

# Manual key rotation
./scripts/key-rotation-automation.py --rotate

# Verify key information
vault read transit/keys/thermoworks-user-credentials
```

### Debug Commands

```bash
# Check service logs
kubectl logs -n grill-stats -l app=encryption-service

# Monitor audit logs
kubectl exec -n grill-stats encryption-service-xxx -- \
  tail -f /var/log/grill-stats/audit.log

# Test encryption/decryption
curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","user_id":"1"}' \
  http://encryption-service:8082/encrypt

# Check database state
kubectl exec -it postgresql-0 -- psql -U grill_stats_app -d grill_stats \
  -c "SELECT * FROM thermoworks_credentials WHERE user_id = 1;"
```

## Maintenance

### Regular Tasks

#### Daily
- Monitor audit logs for security events
- Check service health status
- Verify key rotation scheduler

#### Weekly
- Review rate limiting metrics
- Analyze performance trends
- Check backup integrity

#### Monthly
- Update dependencies
- Review security policies
- Rotate non-automated secrets

#### Quarterly
- Security assessment
- Compliance audit
- Disaster recovery testing

### Backup and Recovery

#### Backup Strategy
```bash
# Database backups
pg_dump grill_stats > backup-$(date +%Y%m%d).sql

# Vault key metadata backup
vault read -format=json transit/keys/thermoworks-user-credentials > \
  key-backup-$(date +%Y%m%d).json

# Configuration backups
kubectl get configmap,secret -n grill-stats -o yaml > \
  config-backup-$(date +%Y%m%d).yaml
```

#### Recovery Procedures
1. **Service Recovery**: Redeploy from known good configuration
2. **Database Recovery**: Restore from encrypted backup
3. **Key Recovery**: Vault cluster recovery procedures
4. **Configuration Recovery**: Apply backed-up configurations

### Updates and Patching

#### Security Updates
- Monitor CVE databases for relevant vulnerabilities
- Apply security patches within 48 hours
- Test patches in staging environment first

#### Dependency Updates
- Update Python packages monthly
- Update base container images monthly
- Update Kubernetes manifests as needed

#### Version Control
- Tag all releases with semantic versioning
- Maintain changelog for all changes
- Document breaking changes

## Conclusion

This secure credential storage implementation provides enterprise-grade security for ThermoWorks user credentials while maintaining usability and performance. The multi-layered approach ensures comprehensive protection against various threat vectors while providing visibility through comprehensive audit logging.

For questions or issues, please refer to the troubleshooting section or contact the development team.

---

**Document Version**: 1.0
**Last Updated**: 2024-01-01
**Next Review**: 2024-04-01
