# Grill Stats 1Password Connect Secrets

This directory contains the complete 1Password Connect secret configuration for the Grill Stats microservices platform. The secrets are organized by service and environment, providing secure credential management for all components.

## Overview

The Grill Stats platform uses 1Password Connect to manage secrets across multiple environments:

- **Base Secrets**: Common secrets used across all environments
- **Dev Lab**: Development environment with relaxed security for testing
- **Prod Lab**: Production environment with strict security controls

## Directory Structure

```
apps/secrets/grill-stats/
├── README.md                                    # This file
├── kustomization.yaml                           # Base kustomization
├── validate-secrets.sh                         # Validation script
├── deploy-secrets.sh                           # Deployment script
├── auth-service-1password.yaml                 # Auth service secrets
├── device-service-1password.yaml               # Device service secrets
├── temperature-service-1password.yaml          # Temperature service secrets
├── historical-data-service-1password.yaml      # Historical data service secrets
├── encryption-service-1password.yaml           # Encryption service secrets
├── web-ui-1password.yaml                       # Web UI service secrets
├── databases-1password.yaml                    # Database secrets
├── rbac-1password.yaml                         # RBAC configurations
├── dev-lab/                                    # Development environment
│   ├── kustomization.yaml                      # Dev kustomization
│   ├── environment-secrets-1password.yaml      # Dev environment secrets
│   └── rbac-dev-1password.yaml                 # Dev RBAC
└── prod-lab/                                   # Production environment
    ├── kustomization.yaml                      # Prod kustomization
    ├── environment-secrets-1password.yaml      # Prod environment secrets
    └── rbac-prod-1password.yaml                # Prod RBAC
```

## Services and Secrets

### Authentication Service (`auth-service-1password.yaml`)
- JWT secrets and session management
- Database credentials (PostgreSQL)
- Redis configuration for session storage
- ThermoWorks API credentials
- Rate limiting and security configuration

### Device Service (`device-service-1password.yaml`)
- Device discovery and management
- ThermoWorks API integration
- PostgreSQL database access
- Redis caching configuration
- Home Assistant integration
- RFX Gateway configuration

### Temperature Service (`temperature-service-1password.yaml`)
- InfluxDB credentials for time-series data
- Redis caching configuration
- ThermoWorks API access
- Temperature data processing settings
- Streaming configuration

### Historical Data Service (`historical-data-service-1password.yaml`)
- TimescaleDB credentials
- InfluxDB access for data migration
- Redis caching configuration
- Data retention and compression settings
- Analytics configuration

### Encryption Service (`encryption-service-1password.yaml`)
- HashiCorp Vault integration
- Encryption keys and certificates
- Audit logging configuration
- Rate limiting for encryption operations
- Database access for audit logs

### Web UI Service (`web-ui-1password.yaml`)
- API endpoint configurations
- Authentication settings
- Feature flags and performance settings
- Security headers and CSP configuration
- Development tools configuration

### Database Secrets (`databases-1password.yaml`)
- PostgreSQL admin and service user credentials
- InfluxDB tokens and organization setup
- Redis authentication and clustering
- TimescaleDB configuration and users
- Connection pooling and SSL settings

## Environment-Specific Configuration

### Development Lab (`dev-lab/`)
- Relaxed security settings for development
- Debug mode enabled
- Shorter JWT expiration times
- Sandbox ThermoWorks API endpoints
- Local service discovery
- Development tools enabled

### Production Lab (`prod-lab/`)
- Strict security controls
- Production ThermoWorks API endpoints
- Longer data retention periods
- Backup and monitoring enabled
- Security hardening settings
- Audit logging enabled

## RBAC Configuration

### Service Accounts
- `grill-stats-secrets-manager`: Central secret management
- `auth-service-secrets`: Auth service access
- `device-service-secrets`: Device service access
- `temperature-service-secrets`: Temperature service access
- `historical-data-service-secrets`: Historical data service access
- `encryption-service-secrets`: Encryption service access
- `web-ui-secrets`: Web UI service access

### Permissions
- **Secret Management**: Full CRUD access for secret managers
- **Service Access**: Read-only access to service-specific secrets
- **Environment Isolation**: Strict separation between dev and prod
- **Audit Logging**: All secret access is logged

## 1Password Vault Structure

### Base Vault (`grill-stats`)
```
grill-stats/
├── auth-service-secrets
├── device-service-secrets
├── temperature-service-secrets
├── historical-data-service-secrets
├── encryption-service-secrets
├── web-ui-secrets
├── postgresql-secrets
├── influxdb-secrets
├── redis-secrets
└── timescaledb-secrets
```

### Development Vault (`grill-stats-dev`)
```
grill-stats-dev/
├── dev-lab-environment-secrets
├── dev-lab-database-users
├── auth-service-secrets
├── device-service-secrets
├── temperature-service-secrets
├── historical-data-service-secrets
├── encryption-service-secrets
├── web-ui-secrets
└── [database-secrets]
```

### Production Vault (`grill-stats-prod`)
```
grill-stats-prod/
├── prod-lab-environment-secrets
├── prod-lab-database-users
├── prod-lab-security-secrets
├── auth-service-secrets
├── device-service-secrets
├── temperature-service-secrets
├── historical-data-service-secrets
├── encryption-service-secrets
├── web-ui-secrets
└── [database-secrets]
```

## Deployment

### Prerequisites
- 1Password Connect operator installed in cluster
- Kubernetes cluster with appropriate namespaces
- Required tools: `kubectl`, `kustomize`, `yq`, `jq`

### Validation
```bash
# Validate all secret configurations
./validate-secrets.sh

# Validate specific environment
./validate-secrets.sh --environment dev-lab
```

### Deployment Commands
```bash
# Deploy to all environments
./deploy-secrets.sh

# Deploy to specific environment
./deploy-secrets.sh dev-lab

# Dry run deployment
./deploy-secrets.sh --dry-run

# Force deployment (skip validation)
./deploy-secrets.sh prod-lab --force
```

### Using Kustomize Directly
```bash
# Build and review configuration
kustomize build .
kustomize build dev-lab/
kustomize build prod-lab/

# Apply to cluster
kustomize build . | kubectl apply -f -
kustomize build dev-lab/ | kubectl apply -f -
kustomize build prod-lab/ | kubectl apply -f -
```

## Security Considerations

### Secret Rotation
- Automatic rotation every 90 days for production
- Manual rotation for development (30 days)
- Vault integration for encryption key rotation
- Database credential rotation via scripts

### Access Control
- Principle of least privilege
- Service-specific secret access
- Environment isolation
- Audit logging for all access

### Encryption
- All secrets encrypted at rest in 1Password
- Transit encryption via TLS
- Additional encryption for sensitive data
- Vault integration for application-level encryption

## Monitoring and Alerting

### Secret Health Checks
- OnePassword Connect operator status
- Secret population monitoring
- Credential validation checks
- Rotation status tracking

### Alerting
- Failed secret retrievals
- Rotation failures
- Unauthorized access attempts
- Operator health issues

## Troubleshooting

### Common Issues

1. **Secrets Not Populated**
   - Check OnePassword Connect operator status
   - Verify vault paths and item names
   - Check RBAC permissions

2. **Authentication Failures**
   - Validate 1Password Connect credentials
   - Check service account permissions
   - Verify namespace configurations

3. **Secret Access Denied**
   - Review RBAC configurations
   - Check service account assignments
   - Verify namespace isolation

### Debug Commands
```bash
# Check OnePassword Connect operator
kubectl get pods -n onepassword-connect

# Check OnePasswordItem resources
kubectl get onepassworditems -n grill-stats

# Check secret status
kubectl get secrets -n grill-stats
kubectl describe secret auth-service-secrets -n grill-stats

# View operator logs
kubectl logs -n onepassword-connect deployment/onepassword-connect-operator
```

## Integration with Services

### Service Configuration
Services should reference secrets using environment variables:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  template:
    spec:
      serviceAccountName: auth-service-secrets
      containers:
      - name: auth-service
        env:
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: auth-service-secrets
              key: jwt-secret
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: auth-service-secrets
              key: database-url
```

### Volume Mounts
For certificate files or complex configurations:

```yaml
volumes:
- name: vault-certs
  secret:
    secretName: encryption-service-secrets
    items:
    - key: vault-ca-cert
      path: ca.crt
    - key: vault-client-cert
      path: client.crt
    - key: vault-client-key
      path: client.key
```

## Maintenance

### Regular Tasks
- Monthly secret rotation review
- Quarterly security audit
- Annual vault organization cleanup
- Continuous monitoring of secret health

### Backup and Recovery
- 1Password vaults backed up automatically
- Kubernetes secret manifests in Git
- Recovery procedures documented
- Disaster recovery testing

## Support

For issues related to secret management:
1. Check the troubleshooting section
2. Review operator logs
3. Validate configurations with provided scripts
4. Consult 1Password Connect documentation
5. Contact platform team for assistance

## Contributing

When adding new secrets:
1. Follow the established naming conventions
2. Include appropriate labels and annotations
3. Update RBAC configurations
4. Add validation rules
5. Update documentation
6. Test in development environment first

## References

- [1Password Connect Documentation](https://developer.1password.com/docs/connect)
- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kustomize Documentation](https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/)
- [HashiCorp Vault](https://www.vaultproject.io/docs)
- [Grill Stats Platform Documentation](../../../README.md)