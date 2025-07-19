# Grill Stats Production Validation System

A comprehensive validation suite for verifying the production readiness of the Grill Stats platform in Kubernetes environments.

## Overview

This validation system provides end-to-end testing and validation of all components in the Grill Stats microservices platform, ensuring production readiness through automated testing, security auditing, performance validation, and integration testing.

## Components

### 1. Core Validation Scripts

#### `validate-production.sh`
- **Purpose**: Comprehensive production deployment validation
- **Features**:
  - Kubernetes cluster health checks
  - Service deployment validation
  - Database connectivity testing
  - Network policy verification
  - Ingress and TLS certificate validation
  - Monitoring system checks
  - External integration validation
  - Backup system verification
- **Output**: GO/NO-GO decision with detailed JSON report

#### `security-audit.sh`
- **Purpose**: Security compliance and vulnerability assessment
- **Features**:
  - RBAC configuration audit
  - Network security policies
  - Container security contexts
  - Secrets management validation
  - Pod Security Standards compliance
  - Image security scanning
  - Admission controller verification
- **Output**: Security findings with severity levels and recommendations

#### `performance-test.sh`
- **Purpose**: Performance and load testing
- **Features**:
  - Load testing with multiple concurrent users
  - Response time measurement
  - Resource utilization monitoring
  - Database performance testing
  - API endpoint benchmarking
  - Scalability validation
- **Output**: Performance metrics and threshold compliance

#### `integration-test.sh`
- **Purpose**: End-to-end integration testing
- **Features**:
  - Authentication flow testing
  - Device management workflows
  - Temperature data processing
  - Historical data operations
  - Encryption service validation
  - Web UI functionality testing
  - External API integration
- **Output**: Integration test results with pass/fail status

#### `run-full-validation.sh`
- **Purpose**: Orchestrates all validation scripts
- **Features**:
  - Sequential or parallel execution
  - Comprehensive reporting
  - Overall score calculation
  - HTML and JSON report generation
  - Production deployment recommendation
- **Output**: Complete validation suite results

## Quick Start

### Prerequisites

```bash
# Required tools
kubectl
jq
curl
bc (for calculations)
openssl (for certificate checks)

# Optional tools for enhanced functionality
ab (Apache Bench for load testing)
argocd (ArgoCD CLI for GitOps checks)
```

### Basic Usage

```bash
# Run complete validation suite
./scripts/run-full-validation.sh

# Run individual validations
./scripts/validate-production.sh
./scripts/security-audit.sh
./scripts/performance-test.sh
./scripts/integration-test.sh

# Run with specific options
./scripts/run-full-validation.sh --parallel --skip-performance
```

## Detailed Usage

### Production Validation

```bash
# Basic production validation
./scripts/validate-production.sh

# Specific cluster/namespace
./scripts/validate-production.sh --context prod-lab -n grill-stats

# With custom timeout
./scripts/validate-production.sh --timeout 600
```

**Key Validations:**
- ✅ Cluster connectivity and node health
- ✅ All 6 microservices running (auth, device, temperature, historical, encryption, web-ui)
- ✅ Database connectivity (PostgreSQL, InfluxDB, Redis)
- ✅ Network policies and ingress configuration
- ✅ TLS certificates and security
- ✅ Monitoring and alerting setup
- ✅ External integrations (Vault, 1Password, ArgoCD)
- ✅ Backup system status

### Security Audit

```bash
# Complete security audit
./scripts/security-audit.sh

# With custom output directory
./scripts/security-audit.sh -o /path/to/audit/results

# Different environment
./scripts/security-audit.sh --context dev-lab -n grill-dev
```

**Security Categories:**
- 🔐 **RBAC**: Service accounts, roles, and permissions
- 🌐 **Network**: Policies, ingress security, TLS configuration
- 📦 **Container**: Security contexts, capabilities, resource limits
- 🔑 **Secrets**: Encryption, external secret management
- 🛡️ **Pod Security**: Standards compliance, admission control
- 📋 **Compliance**: Policy enforcement, vulnerability scanning

### Performance Testing

```bash
# Standard performance test
./scripts/performance-test.sh

# Extended test with more load
./scripts/performance-test.sh --duration 600 --concurrent 20

# Quick test
./scripts/performance-test.sh --duration 120 --concurrent 5
```

**Performance Metrics:**
- 📊 **Load Testing**: Concurrent user simulation
- ⏱️ **Response Times**: P95/P99 latency measurements
- 💾 **Resource Usage**: CPU and memory utilization
- 🗄️ **Database Performance**: Query response times
- 🔄 **Throughput**: Requests per second capacity
- 🚨 **Error Rates**: Failure percentage under load

### Integration Testing

```bash
# Full integration test suite
./scripts/integration-test.sh

# With custom test duration
./scripts/integration-test.sh --timeout 600

# Specific test directory
./scripts/integration-test.sh --test-dir /path/to/test/results
```

**Integration Test Categories:**
- 🔐 **Authentication**: User registration, login, token validation
- 📱 **Device Management**: Device CRUD operations
- 🌡️ **Temperature Data**: Data ingestion, retrieval, alerts
- 📈 **Historical Data**: Aggregation, export, retention
- 🔒 **Encryption**: Data encryption/decryption, key rotation
- 🖥️ **Web UI**: Frontend functionality, API integration
- 🔌 **External APIs**: ThermoWorks, Vault, Home Assistant

### Full Validation Suite

```bash
# Complete validation with all tests
./scripts/run-full-validation.sh

# Parallel execution for faster completion
./scripts/run-full-validation.sh --parallel

# Skip specific test categories
./scripts/run-full-validation.sh --skip-performance --skip-security

# Different environment
./scripts/run-full-validation.sh --context dev-lab -n grill-dev
```

## Configuration

### Environment Variables

```bash
# Cluster configuration
export CLUSTER_CONTEXT="prod-lab"
export NAMESPACE="grill-stats"

# Skip specific validations
export SKIP_PERFORMANCE=true
export SKIP_SECURITY=false
export SKIP_INTEGRATION=false

# Execution mode
export PARALLEL_EXECUTION=true
export GENERATE_REPORT=true
```

### Test Thresholds

The validation system uses configurable thresholds:

```bash
# Performance thresholds
CPU_LIMIT=80%
MEMORY_LIMIT=80%
RESPONSE_TIME=2000ms
ERROR_RATE=5%

# Security thresholds
CRITICAL_FINDINGS=0
HIGH_FINDINGS=2
RISK_SCORE=50
```

## Output Reports

### JSON Reports
- **Location**: `/tmp/grill-stats-*-TIMESTAMP/`
- **Format**: Structured JSON with detailed results
- **Usage**: Automation and CI/CD integration

### HTML Reports
- **Location**: `/tmp/grill-stats-*-TIMESTAMP/reports/`
- **Format**: Human-readable HTML dashboard
- **Usage**: Stakeholder review and documentation

### Summary Reports
- **Location**: `/tmp/grill-stats-*-TIMESTAMP/reports/`
- **Format**: Plain text summary
- **Usage**: Quick status review

## GO/NO-GO Criteria

### Production Deployment Approval

#### ✅ **GO** (Approved for Production)
- All critical validations pass
- No security critical/high findings
- Performance meets all thresholds
- Integration tests pass rate > 95%
- Overall score > 90/100

#### ⚠️ **CONDITIONAL GO** (Conditional Approval)
- Minor issues detected
- Security findings are medium/low only
- Performance mostly within limits
- Integration tests pass rate > 85%
- Overall score > 80/100

#### ❌ **NO-GO** (Not Approved)
- Critical validation failures
- Security critical/high findings present
- Performance significantly below thresholds
- Integration tests pass rate < 85%
- Overall score < 80/100

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Production Validation
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate-production:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup kubectl
        uses: azure/setup-kubectl@v1

      - name: Run Production Validation
        run: |
          chmod +x scripts/run-full-validation.sh
          ./scripts/run-full-validation.sh --parallel

      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: validation-results
          path: /tmp/grill-stats-full-validation-*/
```

### ArgoCD Integration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: grill-stats-validation
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/grill-stats
    targetRevision: HEAD
    path: scripts
  destination:
    server: https://kubernetes.default.svc
    namespace: grill-stats
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## Troubleshooting

### Common Issues

#### 1. **Permission Errors**
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Check kubectl permissions
kubectl auth can-i '*' '*' --all-namespaces
```

#### 2. **Missing Dependencies**
```bash
# Install required tools
apt-get update
apt-get install -y kubectl jq curl bc openssl

# Verify installations
kubectl version --client
jq --version
```

#### 3. **Network Connectivity**
```bash
# Test cluster connectivity
kubectl cluster-info

# Check service endpoints
kubectl get endpoints -n grill-stats
```

#### 4. **Resource Constraints**
```bash
# Check node resources
kubectl top nodes

# Check pod resource usage
kubectl top pods -n grill-stats
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG=true
./scripts/run-full-validation.sh

# Verbose output
./scripts/validate-production.sh --verbose

# Save debug information
./scripts/run-full-validation.sh --debug-output /path/to/debug/
```

## Customization

### Adding Custom Validations

1. **Create custom validation function**:
```bash
validate_custom_component() {
    local start_time=$(date +%s%3N)

    # Your validation logic here
    if custom_validation_passes; then
        check_status "CUSTOM_COMPONENT" "GO" "Custom validation passed"
    else
        check_status "CUSTOM_COMPONENT" "NO-GO" "Custom validation failed"
    fi
}
```

2. **Add to main validation sequence**:
```bash
# In main() function
validate_cluster
validate_services
validate_custom_component  # Add your custom validation
```

### Custom Thresholds

```bash
# Create custom threshold file
cat > custom-thresholds.conf << EOF
CPU_LIMIT=85
MEMORY_LIMIT=75
RESPONSE_TIME=1500
ERROR_RATE=3
EOF

# Source in validation script
source custom-thresholds.conf
```

## Best Practices

### 1. **Pre-Production Validation**
- Run full validation suite before any production deployment
- Validate in staging environment first
- Address all NO-GO items before proceeding

### 2. **Regular Monitoring**
- Schedule periodic validation runs
- Monitor performance trends over time
- Set up alerts for validation failures

### 3. **Security Compliance**
- Run security audits regularly
- Address security findings promptly
- Maintain security baseline documentation

### 4. **Performance Baselines**
- Establish performance baselines
- Monitor for performance degradation
- Scale resources based on validation results

## Support

### Documentation
- **Architecture**: `/docs/architecture.md`
- **API Documentation**: `/docs/api/`
- **Deployment Guide**: `/docs/deployment.md`

### Monitoring
- **Grafana Dashboards**: `https://grafana.your-domain.com/d/grill-stats`
- **Prometheus Metrics**: `https://prometheus.your-domain.com`
- **Alert Manager**: `https://alertmanager.your-domain.com`

### Contact
- **Platform Team**: platform-team@your-company.com
- **Security Team**: security-team@your-company.com
- **SRE Team**: sre-team@your-company.com

---

## License

This validation system is part of the Grill Stats platform and follows the same licensing terms as the main project.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your validation enhancements
4. Test thoroughly
5. Submit a pull request

For major changes, please open an issue first to discuss the proposed changes.

---

*Generated by the Grill Stats Production Validation System*
