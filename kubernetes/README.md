# Kubernetes Configuration for Grill Stats Platform

This directory contains the Kubernetes manifests for deploying and managing the Grill Stats Platform infrastructure.

## Directory Structure

The Kubernetes configuration follows a Kustomize-based organization:

```
kubernetes/
├── base/                   # Base configurations
│   ├── namespace/          # Base namespace definitions
│   │   ├── namespace.yaml
│   │   ├── resourcequota.yaml
│   │   ├── networkpolicy.yaml
│   │   ├── serviceaccounts.yaml
│   │   ├── rbac.yaml
│   │   └── kustomization.yaml
│   └── ... (other base components)
└── overlays/               # Environment-specific overlays
    ├── dev/                # Development environment
    │   └── namespace/
    │       ├── namespace.yaml
    │       ├── resourcequota.yaml
    │       └── kustomization.yaml
    ├── staging/            # Staging environment
    │   └── namespace/
    │       ├── namespace.yaml
    │       ├── resourcequota.yaml
    │       └── kustomization.yaml
    └── prod/               # Production environment
        └── namespace/
            ├── namespace.yaml
            ├── resourcequota.yaml
            └── kustomization.yaml
```

## Namespace Configuration

The platform uses isolated namespaces for different environments to ensure proper separation and resource allocation.

### Base Namespace

The base namespace configuration includes:

- **Namespace Definition**: `grill-stats` namespace with standard labels
- **Pod Security Policies**: Set to "restricted" for enhanced security
- **Resource Quotas**: Limits on CPU, memory, pods, services, etc.
- **Network Policies**: Zero-trust network model with explicit allow rules
- **Service Accounts**: Pre-configured service accounts for each microservice
- **RBAC Rules**: Role-based access control for least-privilege permission model

### Environment Overlays

Each environment (dev, staging, prod) extends the base configuration with specific adjustments:

- **Development**: Lower resource quotas, suitable for development and testing
- **Staging**: Medium resource allocation, mirrors production at a smaller scale
- **Production**: Full resource allocation for high availability and performance

## Usage Guidelines

### Applying Configurations

To apply a specific environment configuration:

```bash
# Development environment
kubectl apply -k kubernetes/overlays/dev/namespace

# Staging environment
kubectl apply -k kubernetes/overlays/staging/namespace

# Production environment
kubectl apply -k kubernetes/overlays/prod/namespace
```

### Adding New Microservices

When adding a new microservice:

1. Add a service account to the base `serviceaccounts.yaml`
2. Define appropriate RBAC rules in `rbac.yaml`
3. Update network policies if the service requires special access

### Network Policy Guidelines

The platform follows a zero-trust networking model:

1. All ingress/egress traffic is denied by default
2. Specific allow rules are defined for required communications
3. Service-to-service communication is allowed within the namespace
4. External API access is restricted to specific services

### Resource Management

Resource quotas and limits are pre-configured:

- **CPU/Memory Requests**: Always set appropriate resource requests
- **CPU/Memory Limits**: Use reasonable limits to prevent resource hogging
- **Storage**: Persistent volume claims follow the default storage class

## Security Considerations

1. **Pod Security**: All namespaces enforce restricted pod security standards
2. **Network Security**: Zero-trust model with explicit allow rules
3. **RBAC**: Least-privilege principle for all service accounts
4. **Secrets**: Managed via external secret providers (1Password integration)

## Monitoring & Observability

All namespaces include configurations for:

1. **Prometheus Access**: Allow rules for metrics scraping
2. **Logging**: Standard labels for log collection
3. **Tracing**: OpenTelemetry integration via service mesh

## Reference

For more information about Kubernetes best practices, refer to:

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Zero-trust Network Model](https://cloud.google.com/blog/products/networking/network-security-aspects-of-a-zero-trust-security-model)
- [Kustomize Documentation](https://kubectl.docs.kubernetes.io/guides/)
