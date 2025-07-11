# Network Security Guide for Grill-Stats Platform

## Overview

This document provides a comprehensive guide to the network security implementation for the Grill-Stats platform. The platform implements a zero-trust network security model using Kubernetes NetworkPolicies to control service-to-service communication.

## Architecture Overview

The Grill-Stats platform consists of multiple microservices that require secure communication:

### Core Services
- **Web UI Service** - React-based frontend (Port 3000/80)
- **Auth Service** - Authentication and authorization (Port 8082)
- **Device Service** - ThermoWorks device management (Port 8080)
- **Temperature Service** - Real-time temperature data (Port 8081)
- **Historical Service** - Long-term data analysis (Port 8083)
- **Encryption Service** - Data encryption/decryption (Port 8082)

### Data Layer
- **PostgreSQL** - Relational data storage (Port 5432)
- **InfluxDB** - Time-series data storage (Port 8086)
- **Redis** - Caching and session storage (Port 6379)
- **TimescaleDB** - Historical data analysis (Port 5432)

### External Integrations
- **ThermoWorks API** - Device data synchronization (HTTPS)
- **HashiCorp Vault** - Secret management (Port 8200)
- **1Password Connect** - Secret injection (Port 8080)
- **Home Assistant** - Home automation integration (Port 8123)

## Security Model

### Zero-Trust Principles

1. **Default Deny**: All traffic is denied by default
2. **Explicit Allow**: Only specifically authorized traffic is permitted
3. **Least Privilege**: Services can only access what they need
4. **Microsegmentation**: Network boundaries at the service level

### Network Policy Structure

The network policies are organized into several categories:

#### 1. Core Service Policies
- **Location**: `/kustomize/base/core-services/network-policies.yaml`
- **Purpose**: Control inter-service communication for core application services
- **Scope**: Web UI, Auth, Device, Temperature, Historical, and Encryption services

#### 2. Database Access Policies
- **Location**: `/kustomize/base/databases/database-network-policies.yaml`
- **Purpose**: Restrict database access to authorized services only
- **Scope**: PostgreSQL, InfluxDB, Redis, TimescaleDB, and monitoring exporters

#### 3. External Service Policies
- **Location**: `/kustomize/base/external-services/network-policies.yaml`
- **Purpose**: Control access to external services and APIs
- **Scope**: ThermoWorks API, Vault, 1Password, Home Assistant, backup storage

#### 4. Monitoring Policies
- **Location**: `/kustomize/base/monitoring/network-policies.yaml`
- **Purpose**: Enable comprehensive observability while maintaining security
- **Scope**: Prometheus, Grafana, Jaeger, OpenTelemetry, logging, alerting

#### 5. Environment-Specific Policies
- **Development**: `/kustomize/overlays/dev/network-policies-dev.yaml`
- **Staging**: `/kustomize/overlays/staging/network-policies-staging.yaml`
- **Production**: `/kustomize/overlays/prod/network-policies-prod.yaml`

## Service Communication Matrix

### Ingress Traffic (Who can access services)

| Service | Allowed Sources | Ports | Purpose |
|---------|----------------|-------|---------|
| Web UI | Traefik Ingress | 80, 3000 | External user access |
| Auth Service | Web UI, Other Services, Traefik | 8082 | Authentication |
| Device Service | Web UI, Temperature, Historical, Traefik | 8080 | Device management |
| Temperature Service | Web UI, Device, Historical, Traefik | 8081 | Temperature data |
| Historical Service | Web UI, Device, Traefik | 8083 | Historical analysis |
| Encryption Service | Auth Service, Device Service | 8082 | Data encryption |

### Egress Traffic (What services can access)

| Service | Allowed Destinations | Ports | Purpose |
|---------|---------------------|-------|---------|
| Web UI | Backend Services | 8080-8083 | API calls |
| Auth Service | PostgreSQL, Redis, Encryption | 5432, 6379, 8082 | Data access |
| Device Service | PostgreSQL, Redis, ThermoWorks API, Home Assistant | 5432, 6379, 443, 8123 | External integrations |
| Temperature Service | InfluxDB, Redis, Device, Auth | 8086, 6379, 8080, 8082 | Data storage |
| Historical Service | InfluxDB, PostgreSQL, Auth, Temperature | 8086, 5432, 8082, 8081 | Data analysis |
| Encryption Service | Vault, Auth, PostgreSQL | 8200, 8082, 5432 | Secret management |

### Database Access Control

| Database | Allowed Services | Monitoring | Backup |
|----------|------------------|------------|--------|
| PostgreSQL | Auth, Device, Historical, Encryption | postgres-exporter | postgresql-backup |
| InfluxDB | Temperature, Historical | Native metrics | influxdb-backup |
| Redis | Auth, Device, Temperature | redis-exporter | redis-backup |
| TimescaleDB | Historical | postgres-exporter | timescaledb-backup |

## Environment-Specific Security

### Development Environment
- **Security Level**: Relaxed
- **Access**: Allows broader access for debugging
- **External Access**: Permits development tools and direct database access
- **Monitoring**: Full observability with external access

### Staging Environment
- **Security Level**: Moderate
- **Access**: Controlled access with testing considerations
- **External Access**: Limited to staging-specific services
- **Monitoring**: Production-like monitoring with test access

### Production Environment
- **Security Level**: Strict
- **Access**: Minimal required access only
- **External Access**: Highly restricted, approved services only
- **Monitoring**: Security-focused monitoring with strict access controls

## Troubleshooting Network Issues

### Common Issues and Solutions

#### 1. Service Cannot Connect to Database

**Symptoms**: Database connection timeouts, authentication failures

**Diagnosis**:
```bash
# Check network policies
kubectl get networkpolicies -n grill-stats

# Check service connectivity
kubectl exec -it <service-pod> -- curl -v <database-service>:5432
```

**Resolution**:
- Verify service labels match network policy selectors
- Check database network policy allows the service
- Ensure service is in correct namespace

#### 2. External API Access Blocked

**Symptoms**: Timeouts when calling external APIs

**Diagnosis**:
```bash
# Check egress rules
kubectl describe networkpolicy <service>-network-policy

# Test external connectivity
kubectl exec -it <service-pod> -- curl -v https://external-api.com
```

**Resolution**:
- Verify external service network policy exists
- Check IP blocks and port restrictions
- Confirm DNS resolution is allowed

#### 3. Monitoring Not Working

**Symptoms**: Missing metrics, no health check data

**Diagnosis**:
```bash
# Check monitoring policies
kubectl get networkpolicies -l app.kubernetes.io/component=monitoring

# Test metrics endpoint
kubectl exec -it <service-pod> -- curl localhost:8080/metrics
```

**Resolution**:
- Verify monitoring network policies are applied
- Check Prometheus can reach service metrics ports
- Ensure health check endpoints are accessible

## Security Best Practices

### 1. Label Consistency
- Use consistent labeling across all services
- Follow Kubernetes recommended labels
- Include app.kubernetes.io/part-of for service grouping

### 2. Port Specification
- Always specify exact ports in network policies
- Use named ports when possible
- Avoid wildcard port specifications

### 3. Regular Auditing
- Regularly review network policies
- Audit service communication patterns
- Monitor for unauthorized access attempts

### 4. Environment Isolation
- Use separate namespaces for different environments
- Implement strict production network policies
- Allow relaxed policies only in development

### 5. Monitoring and Alerting
- Monitor network policy violations
- Set up alerts for blocked connections
- Track service communication patterns

## Deployment and Maintenance

### Applying Network Policies

```bash
# Apply to development environment
kubectl apply -k kustomize/overlays/dev

# Apply to staging environment
kubectl apply -k kustomize/overlays/staging

# Apply to production environment
kubectl apply -k kustomize/overlays/prod
```

### Validation

```bash
# Validate network policies
kubectl get networkpolicies -n grill-stats

# Check policy details
kubectl describe networkpolicy <policy-name> -n grill-stats
```

### Updates and Changes

1. **Development**: Test changes in development environment first
2. **Staging**: Validate in staging with integration tests
3. **Production**: Apply during maintenance windows with rollback plan

## Conclusion

The Grill-Stats platform implements a comprehensive network security model that provides:

- **Zero-trust architecture** with default deny policies
- **Microsegmentation** at the service level
- **Environment-specific security** controls
- **Comprehensive monitoring** and observability
- **Secure external integrations**

This security model ensures that the platform maintains strong security posture while enabling necessary service communication and operational visibility.