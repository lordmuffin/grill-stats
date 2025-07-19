# HashiCorp Vault Transit Secrets Engine Integration

This directory contains the complete configuration for integrating HashiCorp Vault Transit secrets engine with the grill-stats ThermoWorks BBQ monitoring application. The integration provides enterprise-grade AES-256-GCM encryption for secure credential storage and management.

## Overview

The Vault Transit integration implements User Story 5 (Secure Credential Storage) requirements:

- **AES-256-GCM encryption** for ThermoWorks user credentials
- **Encryption-as-a-service** via Vault Transit engine
- **Automated key rotation** with environment-specific policies
- **Comprehensive audit logging** for all encryption operations
- **Kubernetes service account authentication** with least privilege access
- **Environment-specific encryption keys** (dev/staging/prod)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Vault Transit Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   Grill-Stats   │    │   Vault Agent   │    │   Vault     │ │
│  │    Services     │◄───┤   (Sidecar)     │◄───┤  Transit    │ │
│  │                 │    │                 │    │  Engine     │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│           │                       │                     │       │
│           ▼                       ▼                     ▼       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   Encryption    │    │   Token Mgmt    │    │   Key Mgmt  │ │
│  │   Operations    │    │   & Renewal     │    │  & Rotation │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Vault Transit Setup (`vault-transit-setup.yaml`)
- Enables Transit secrets engine
- Creates environment-specific encryption keys
- Configures key rotation policies
- Sets up audit logging

### 2. Kubernetes Authentication (`vault-kubernetes-auth.yaml`)
- Configures Vault Kubernetes auth method
- Creates service-specific authentication roles
- Implements least privilege access policies

### 3. Service Accounts (`vault-service-accounts.yaml`)
- Dedicated service accounts for each grill-stats service
- Proper RBAC configurations
- Vault Agent annotations for automatic token injection

### 4. Vault Agent Configuration (`vault-agent-config.yaml`)
- Secure token management and automatic renewal
- Template-based configuration generation
- In-memory secret storage for security

### 5. Monitoring & Alerting (`vault-monitoring.yaml`)
- Comprehensive metrics collection
- Prometheus alerting rules
- Grafana dashboard for visualization
- Audit log collection and analysis

## Environment Configuration

### Production Environment
- **Key Rotation**: 90 days
- **Replica Count**: 2 (High Availability)
- **Resources**: 256Mi memory, 200m CPU
- **TLS Verification**: Enabled
- **Backup**: Enabled
- **Notifications**: Enabled

### Development Environment
- **Key Rotation**: 30 days
- **Replica Count**: 1
- **Resources**: 128Mi memory, 100m CPU
- **TLS Verification**: Disabled
- **Backup**: Disabled
- **Notifications**: Disabled

### Staging Environment
- **Key Rotation**: 60 days
- **Replica Count**: 1
- **Resources**: 192Mi memory, 150m CPU
- **TLS Verification**: Enabled
- **Backup**: Enabled
- **Notifications**: Disabled

## Encryption Keys

### Key Types
1. **User Credentials**: `thermoworks-user-credentials-{env}`
2. **API Tokens**: `thermoworks-api-tokens-{env}`
3. **Device Credentials**: `thermoworks-device-credentials-{env}`

### Key Properties
- **Type**: AES-256-GCM
- **Exportable**: False
- **Plaintext Backup**: Disabled
- **Deletion**: Disabled
- **Derivation**: Disabled

## Security Features

### Authentication & Authorization
- **Kubernetes Service Account Integration**: Secure, pod-based authentication
- **Least Privilege Access**: Role-based access with minimal required permissions
- **Token Rotation**: Automatic token renewal with configurable TTL
- **Audit Logging**: Comprehensive logging of all encryption operations

### Network Security
- **Network Policies**: Restrict traffic between services
- **TLS Encryption**: All vault communications encrypted in transit
- **Security Contexts**: Non-root containers with read-only filesystems
- **Pod Security Standards**: Enforced security policies

### Key Management
- **Automatic Rotation**: Environment-specific rotation schedules
- **Version Management**: Multiple key versions with minimum decryption versions
- **Backup & Recovery**: Secure key backup strategies
- **Monitoring**: Real-time key health and rotation status

## Deployment

### Prerequisites
1. HashiCorp Vault cluster deployed and accessible
2. Kubernetes cluster with proper RBAC
3. 1Password Connect operator for secret management
4. Prometheus and Grafana for monitoring

### Installation Steps

```bash
# 1. Deploy base Vault configuration
kubectl apply -k kustomize/base/vault/

# 2. Deploy environment-specific configuration
kubectl apply -k kustomize/overlays/prod/  # For production
kubectl apply -k kustomize/overlays/dev/   # For development

# 3. Verify deployment
kubectl get pods -n grill-stats -l component=vault-transit
kubectl logs -f deployment/vault-agent -n grill-stats

# 4. Test encryption operations
kubectl exec -it deployment/encryption-service -n grill-stats -- \
  curl -X POST http://localhost:8082/encrypt \
  -H "Content-Type: application/json" \
  -d '{"plaintext": "test-credential", "key_name": "thermoworks-user-credentials-prod"}'
```

### Configuration Validation

```bash
# Check Vault Transit engine status
vault secrets list | grep transit

# Verify encryption keys
vault list transit/keys

# Test encryption/decryption
vault write transit/encrypt/thermoworks-user-credentials-prod plaintext=$(base64 <<< "test-data")
vault write transit/decrypt/thermoworks-user-credentials-prod ciphertext="vault:v1:..."

# Check audit logs
vault audit list
```

## Monitoring & Alerting

### Key Metrics
- **Encryption/Decryption Operations**: Rate and success metrics
- **Key Rotation Status**: Age and version tracking
- **Token Health**: TTL and renewal status
- **Error Rates**: Failure counts and error types
- **Latency**: Operation response times

### Alert Conditions
- **Encryption Failures**: Immediate alert on any encryption failure
- **Key Rotation Due**: Warning when keys approach rotation threshold
- **Token Expiration**: Alert when tokens expire soon
- **Service Unavailability**: Critical alert when Vault Agent is down
- **High Latency**: Warning when encryption operations are slow

### Grafana Dashboard
- Real-time operation metrics
- Key rotation timeline
- Error rate trends
- Performance charts
- System health overview

## Maintenance

### Key Rotation
- **Automated**: Configured via Vault policies
- **Manual**: Emergency rotation procedures
- **Notification**: Slack/email alerts on rotation events
- **Monitoring**: Rotation status tracking

### Backup & Recovery
- **Key Backup**: Encrypted backups to persistent storage
- **Disaster Recovery**: Key restoration procedures
- **Testing**: Regular backup validation
- **Retention**: Configurable retention policies

### Troubleshooting
- **Log Analysis**: Centralized logging with ELK stack
- **Health Checks**: Automated service health monitoring
- **Debugging**: Debug mode configuration for development
- **Performance**: Profiling and optimization tools

## Security Considerations

### Threat Model
- **Data at Rest**: Encryption keys protect stored credentials
- **Data in Transit**: TLS encryption for all communications
- **Key Compromise**: Rapid key rotation and version management
- **Access Control**: Strict RBAC and network policies

### Compliance
- **SOC 2**: Audit logging and access controls
- **GDPR**: Data encryption and right to erasure
- **HIPAA**: Encryption and access logging
- **PCI DSS**: Cryptographic key management

### Best Practices
- **Principle of Least Privilege**: Minimal required permissions
- **Defense in Depth**: Multiple layers of security
- **Regular Audits**: Automated security scanning
- **Incident Response**: Documented procedures and playbooks

## Integration Examples

### Encryption Service Usage
```python
import hvac
import base64

# Initialize Vault client
client = hvac.Client(url='https://vault.vault.svc.cluster.local:8200')
client.token = open('/vault/secrets/token').read().strip()

# Encrypt user credentials
def encrypt_user_credentials(plaintext_creds):
    response = client.secrets.transit.encrypt_data(
        name='thermoworks-user-credentials-prod',
        plaintext=base64.b64encode(plaintext_creds.encode()).decode()
    )
    return response['data']['ciphertext']

# Decrypt user credentials
def decrypt_user_credentials(ciphertext):
    response = client.secrets.transit.decrypt_data(
        name='thermoworks-user-credentials-prod',
        ciphertext=ciphertext
    )
    return base64.b64decode(response['data']['plaintext']).decode()
```

### Kubernetes Pod Configuration
```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "grill-stats-encryption"
spec:
  serviceAccountName: grill-stats-encryption
  containers:
  - name: app
    image: grill-stats/service:latest
    env:
    - name: VAULT_TOKEN_PATH
      value: /vault/secrets/token
    - name: VAULT_ADDR
      value: https://vault.vault.svc.cluster.local:8200
    volumeMounts:
    - name: vault-secrets
      mountPath: /vault/secrets
      readOnly: true
```

## Support

For issues or questions regarding the Vault Transit integration:

1. **Documentation**: Check this README and related configuration files
2. **Logs**: Review Vault Agent and service logs
3. **Monitoring**: Check Grafana dashboards and Prometheus alerts
4. **Testing**: Use the included test scripts and validation procedures

## Contributing

When modifying the Vault Transit configuration:

1. **Test thoroughly** in development environment
2. **Update documentation** for any configuration changes
3. **Review security implications** of all modifications
4. **Validate monitoring** and alerting configurations
5. **Follow deployment procedures** for production changes
