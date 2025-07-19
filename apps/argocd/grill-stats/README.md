# Grill-Stats ArgoCD GitOps Configuration

This directory contains the ArgoCD application definitions for GitOps deployment of the grill-stats ThermoWorks BBQ monitoring platform.

## Overview

The grill-stats platform uses ArgoCD for GitOps-based continuous delivery across multiple environments. The configuration follows the app-of-apps pattern for comprehensive platform management.

## Architecture

### App-of-Apps Pattern

The platform uses a hierarchical application structure:

```
grill-stats-platform (root app)
├── grill-stats-project (ArgoCD project)
├── grill-stats-secrets (1Password secrets)
├── grill-stats-databases (PostgreSQL, InfluxDB, Redis)
├── grill-stats-vault (HashiCorp Vault integration)
├── grill-stats-core-services (microservices)
├── grill-stats-ingress (Traefik routes and TLS)
├── grill-stats-supporting-services (supporting services)
└── grill-stats-monitoring (observability)
```

### Sync Waves

Applications are deployed in ordered sync waves:

- **Wave 0**: Project definition, secrets, and namespace setup
- **Wave 1**: Database infrastructure (PostgreSQL, InfluxDB, Redis)
- **Wave 2**: Vault integration and encryption services
- **Wave 3**: Core microservices (auth, device, temperature, historical, encryption)
- **Wave 4**: Web UI, ingress, and supporting services
- **Wave 5**: Monitoring and observability

## Directory Structure

```
apps/argocd/grill-stats/
├── base/                                    # Base ArgoCD applications
│   ├── grill-stats-project.yaml           # ArgoCD project definition
│   ├── grill-stats-platform.yaml          # App-of-apps root application
│   ├── grill-stats-secrets.yaml           # 1Password secrets management
│   ├── grill-stats-databases.yaml         # Database infrastructure
│   ├── grill-stats-core-services.yaml     # Core microservices
│   ├── grill-stats-monitoring.yaml        # Monitoring and vault
│   ├── kustomization.yaml                 # Base kustomization
│   └── kustomizeconfig.yaml              # Kustomize configuration
├── overlays/                               # Environment-specific overlays
│   ├── prod-lab/                          # Production environment
│   │   ├── kustomization.yaml
│   │   └── production-overrides.yaml
│   └── dev-lab/                           # Development environment
│       ├── kustomization.yaml
│       └── development-overrides.yaml
└── README.md                              # This file
```

## Environments

### Production (prod-lab)

- **Target Branch**: `main`
- **Namespace**: `grill-stats`
- **Sync Policy**: Conservative with manual approval for critical changes
- **Pruning**: Disabled for databases and secrets
- **Health Checks**: Extended timeouts for stability
- **Maintenance Windows**: Sunday 2 AM - 4 AM (sync disabled)

### Development (dev-lab)

- **Target Branch**: `develop`
- **Namespace**: `grill-stats-dev`
- **Sync Policy**: Aggressive with automatic sync and pruning
- **Pruning**: Enabled for easier cleanup and testing
- **Health Checks**: Standard timeouts for faster iteration
- **Maintenance Windows**: None (always available)

## Application Configuration

### Core Services

**Services Included:**
- `auth-service`: Authentication and authorization
- `device-service`: ThermoWorks device management
- `temperature-service`: Temperature data collection
- `historical-data-service`: Historical data analysis
- `encryption-service`: Data encryption and key management
- `web-ui-service`: React-based dashboard

**Configuration:**
- Health checks on `/health` endpoints
- Horizontal Pod Autoscaling in production
- Resource limits and requests
- Network policies for security

### Database Infrastructure

**Components:**
- **PostgreSQL**: Device and user data
- **InfluxDB**: Time-series temperature data
- **Redis**: Caching and real-time data

**Configuration:**
- StatefulSets with persistent storage
- Backup jobs and retention policies
- Monitoring and alerting
- High availability in production

### Secrets Management

**1Password Integration:**
- Service-specific secrets via 1Password Connect
- Automatic secret rotation
- Environment-specific vaults
- Secure secret injection

**Secret Types:**
- API keys (ThermoWorks, Home Assistant)
- Database credentials
- Encryption keys
- TLS certificates

## Deployment

### Prerequisites

1. ArgoCD installed and configured
2. 1Password Connect operator deployed
3. Required namespaces created
4. RBAC permissions configured

### Initial Deployment

```bash
# Deploy the app-of-apps for production
kubectl apply -f apps/argocd/grill-stats/base/grill-stats-platform.yaml

# Deploy development environment
kubectl apply -f apps/argocd/grill-stats/base/grill-stats-platform-dev.yaml
```

### Environment-Specific Deployment

```bash
# Production deployment
kubectl apply -k apps/argocd/grill-stats/overlays/prod-lab

# Development deployment
kubectl apply -k apps/argocd/grill-stats/overlays/dev-lab
```

## Monitoring and Observability

### ArgoCD Dashboard

Access the ArgoCD UI to monitor application health and sync status:

```
https://argocd.your-domain.com/applications/grill-stats-platform
```

### Application Health

Each application includes custom health checks:

- **Database**: StatefulSet replica readiness
- **Core Services**: Deployment readiness with health endpoints
- **Secrets**: 1Password Connect sync status
- **Ingress**: Certificate and route availability

### Sync Status

Monitor sync status for each application:

```bash
# Check all grill-stats applications
kubectl get applications -n argocd | grep grill-stats

# Get detailed status
kubectl describe application grill-stats-platform -n argocd
```

## Troubleshooting

### Common Issues

1. **Sync Failures**
   - Check ArgoCD logs: `kubectl logs -n argocd deployment/argocd-application-controller`
   - Verify repository access and credentials
   - Check resource quotas and limits

2. **Secret Sync Issues**
   - Verify 1Password Connect connectivity
   - Check secret definitions and vault references
   - Ensure proper RBAC permissions

3. **Database Issues**
   - Check persistent volume claims
   - Verify storage class availability
   - Monitor resource usage and limits

### Debugging Commands

```bash
# Check application sync status
kubectl get app grill-stats-platform -n argocd -o yaml

# View application events
kubectl describe app grill-stats-core-services -n argocd

# Check sync history
kubectl get app grill-stats-platform -n argocd -o jsonpath='{.status.history}'

# Force sync
kubectl patch app grill-stats-platform -n argocd --type merge -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

## Security Considerations

### RBAC

The ArgoCD project includes comprehensive RBAC:

- **Developers**: Read access and sync permissions
- **Operators**: Full application management
- **Admins**: Project and repository management

### Network Security

- NetworkPolicies for inter-service communication
- TLS termination at ingress
- Service mesh integration (future)

### Secret Management

- Never store secrets in Git
- Use 1Password Connect for secret injection
- Implement secret rotation policies
- Audit secret access

## CI/CD Integration

### Automated Deployment

The platform supports automated deployment via:

1. **Git Webhooks**: Automatic sync on code changes
2. **Image Updates**: Automated image tag updates
3. **Promotion Workflows**: Environment promotion pipelines

### Image Management

```bash
# Update image tags via Kustomize
kubectl patch app grill-stats-core-services -n argocd --type merge -p '{"spec":{"source":{"kustomize":{"images":["ghcr.io/lordmuffin/grill-stats:v1.2.3"]}}}}'
```

## Maintenance

### Backup Strategy

- Database backups via automated jobs
- Configuration backups in Git
- Secret backups in 1Password
- Disaster recovery procedures

### Updates and Upgrades

1. Test changes in development environment
2. Validate with staging deployment
3. Schedule production updates during maintenance windows
4. Monitor health and rollback if needed

### Monitoring

- Application performance metrics
- Sync status and frequency
- Resource utilization
- Security audit logs

## Support

For issues and questions:

1. Check ArgoCD application status
2. Review application logs
3. Consult troubleshooting guide
4. Create GitHub issue with details

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Documentation](https://kustomize.io/)
- [1Password Connect Operator](https://github.com/1Password/onepassword-operator)
- [Grill-Stats Architecture](../../kustomize/README.md)
