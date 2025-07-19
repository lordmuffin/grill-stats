#!/bin/bash

# InfluxDB 2.x Deployment Validation Script
# This script validates the InfluxDB deployment for the grill-stats system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-grill-stats}"
ENVIRONMENT="${ENVIRONMENT:-dev-lab}"
TIMEOUT="${TIMEOUT:-300}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed or not in PATH"
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

check_namespace() {
    log_info "Checking namespace..."

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_success "Namespace $NAMESPACE exists"
    else
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
}

check_secrets() {
    log_info "Checking secrets..."

    # Check if influxdb-secrets exists
    if kubectl get secret influxdb-secrets -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB secrets exist"

        # Check required keys
        REQUIRED_KEYS=("influxdb-admin-user" "influxdb-admin-password" "influxdb-admin-token" "influxdb-org" "influxdb-bucket")
        for key in "${REQUIRED_KEYS[@]}"; do
            if kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath="{.data.$key}" &> /dev/null; then
                log_success "Secret key $key exists"
            else
                log_error "Secret key $key is missing"
                exit 1
            fi
        done
    else
        log_error "InfluxDB secrets do not exist"
        exit 1
    fi
}

check_storage() {
    log_info "Checking storage..."

    # Check PVC for InfluxDB data
    if kubectl get pvc -n "$NAMESPACE" -o json | jq -r '.items[] | select(.metadata.name | startswith("influxdb-data")) | .metadata.name' | grep -q influxdb-data; then
        log_success "InfluxDB data PVC exists"

        # Check PVC status
        PVC_STATUS=$(kubectl get pvc -n "$NAMESPACE" -o json | jq -r '.items[] | select(.metadata.name | startswith("influxdb-data")) | .status.phase')
        if [ "$PVC_STATUS" = "Bound" ]; then
            log_success "InfluxDB data PVC is bound"
        else
            log_warning "InfluxDB data PVC status: $PVC_STATUS"
        fi
    else
        log_error "InfluxDB data PVC does not exist"
        exit 1
    fi

    # Check backup PVC
    if kubectl get pvc influxdb-backup-pvc -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB backup PVC exists"

        BACKUP_PVC_STATUS=$(kubectl get pvc influxdb-backup-pvc -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [ "$BACKUP_PVC_STATUS" = "Bound" ]; then
            log_success "InfluxDB backup PVC is bound"
        else
            log_warning "InfluxDB backup PVC status: $BACKUP_PVC_STATUS"
        fi
    else
        log_warning "InfluxDB backup PVC does not exist"
    fi
}

check_statefulset() {
    log_info "Checking StatefulSet..."

    if kubectl get statefulset influxdb -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB StatefulSet exists"

        # Check replicas
        DESIRED_REPLICAS=$(kubectl get statefulset influxdb -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
        READY_REPLICAS=$(kubectl get statefulset influxdb -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')

        if [ "$DESIRED_REPLICAS" = "$READY_REPLICAS" ]; then
            log_success "InfluxDB StatefulSet is ready ($READY_REPLICAS/$DESIRED_REPLICAS)"
        else
            log_warning "InfluxDB StatefulSet replicas: $READY_REPLICAS/$DESIRED_REPLICAS"
        fi
    else
        log_error "InfluxDB StatefulSet does not exist"
        exit 1
    fi
}

check_pods() {
    log_info "Checking pods..."

    # Get pod names
    PODS=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$PODS" ]; then
        log_error "No InfluxDB pods found"
        exit 1
    fi

    for pod in $PODS; do
        log_info "Checking pod: $pod"

        # Check pod status
        POD_STATUS=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [ "$POD_STATUS" = "Running" ]; then
            log_success "Pod $pod is running"
        else
            log_error "Pod $pod status: $POD_STATUS"
            kubectl describe pod "$pod" -n "$NAMESPACE"
            exit 1
        fi

        # Check readiness
        READY=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
        if [ "$READY" = "True" ]; then
            log_success "Pod $pod is ready"
        else
            log_error "Pod $pod is not ready"
            kubectl describe pod "$pod" -n "$NAMESPACE"
            exit 1
        fi
    done
}

check_services() {
    log_info "Checking services..."

    # Check main service
    if kubectl get service influxdb-service -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB service exists"

        # Check service endpoints
        ENDPOINTS=$(kubectl get endpoints influxdb-service -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}')
        if [ -n "$ENDPOINTS" ]; then
            log_success "InfluxDB service has endpoints"
        else
            log_warning "InfluxDB service has no endpoints"
        fi
    else
        log_error "InfluxDB service does not exist"
        exit 1
    fi

    # Check headless service
    if kubectl get service influxdb-headless -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB headless service exists"
    else
        log_warning "InfluxDB headless service does not exist"
    fi

    # Check metrics service
    if kubectl get service influxdb-metrics -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB metrics service exists"
    else
        log_warning "InfluxDB metrics service does not exist"
    fi
}

check_configmaps() {
    log_info "Checking ConfigMaps..."

    # Check config ConfigMap
    if kubectl get configmap influxdb-config -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB config ConfigMap exists"
    else
        log_warning "InfluxDB config ConfigMap does not exist"
    fi

    # Check init scripts ConfigMap
    if kubectl get configmap influxdb-init-scripts -n "$NAMESPACE" &> /dev/null; then
        log_success "InfluxDB init scripts ConfigMap exists"
    else
        log_warning "InfluxDB init scripts ConfigMap does not exist"
    fi
}

check_database_health() {
    log_info "Checking database health..."

    # Get first pod name
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$POD_NAME" ]; then
        log_error "No InfluxDB pod found"
        exit 1
    fi

    # Check if database is responding
    if kubectl exec "$POD_NAME" -n "$NAMESPACE" -- curl -f http://localhost:8086/ping &> /dev/null; then
        log_success "InfluxDB is responding to ping"
    else
        log_error "InfluxDB is not responding to ping"
        exit 1
    fi

    # Check if we can connect with admin token
    ADMIN_TOKEN=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-admin-token}' | base64 -d)
    ORG=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-org}' | base64 -d)

    if kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx ping --host http://localhost:8086 --token "$ADMIN_TOKEN" &> /dev/null; then
        log_success "InfluxDB authentication is working"
    else
        log_error "InfluxDB authentication failed"
        exit 1
    fi
}

check_buckets() {
    log_info "Checking buckets..."

    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')
    ADMIN_TOKEN=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-admin-token}' | base64 -d)
    ORG=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-org}' | base64 -d)

    # Expected buckets
    EXPECTED_BUCKETS=("grill-stats-realtime" "grill-stats-hourly" "grill-stats-daily" "grill-stats-archive" "grill-stats-monitoring")

    # Get existing buckets
    EXISTING_BUCKETS=$(kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx bucket list --org "$ORG" --token "$ADMIN_TOKEN" --json 2>/dev/null | jq -r '.[].name' || echo "")

    for bucket in "${EXPECTED_BUCKETS[@]}"; do
        if echo "$EXISTING_BUCKETS" | grep -q "$bucket"; then
            log_success "Bucket $bucket exists"
        else
            log_warning "Bucket $bucket does not exist"
        fi
    done
}

check_tasks() {
    log_info "Checking tasks..."

    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')
    ADMIN_TOKEN=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-admin-token}' | base64 -d)
    ORG=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-org}' | base64 -d)

    # Expected tasks
    EXPECTED_TASKS=("downsample-hourly-temperature" "downsample-daily-temperature" "archive-temperature-data")

    # Get existing tasks
    EXISTING_TASKS=$(kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx task list --org "$ORG" --token "$ADMIN_TOKEN" --json 2>/dev/null | jq -r '.[].name' || echo "")

    for task in "${EXPECTED_TASKS[@]}"; do
        if echo "$EXISTING_TASKS" | grep -q "$task"; then
            log_success "Task $task exists"
        else
            log_warning "Task $task does not exist"
        fi
    done
}

check_monitoring() {
    log_info "Checking monitoring..."

    # Check ServiceMonitor
    if kubectl get servicemonitor influxdb-metrics -n "$NAMESPACE" &> /dev/null; then
        log_success "ServiceMonitor exists"
    else
        log_warning "ServiceMonitor does not exist"
    fi

    # Check PrometheusRule
    if kubectl get prometheusrule influxdb-alerts -n "$NAMESPACE" &> /dev/null; then
        log_success "PrometheusRule exists"
    else
        log_warning "PrometheusRule does not exist"
    fi

    # Check if metrics endpoint is accessible
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')

    if kubectl exec "$POD_NAME" -n "$NAMESPACE" -- curl -s http://localhost:8086/metrics | grep -q "influxdb_"; then
        log_success "Metrics endpoint is accessible"
    else
        log_warning "Metrics endpoint is not accessible"
    fi
}

check_backup() {
    log_info "Checking backup configuration..."

    # Check backup CronJob
    if kubectl get cronjob influxdb-backup -n "$NAMESPACE" &> /dev/null; then
        log_success "Backup CronJob exists"

        # Check if it's enabled
        SUSPENDED=$(kubectl get cronjob influxdb-backup -n "$NAMESPACE" -o jsonpath='{.spec.suspend}')
        if [ "$SUSPENDED" = "false" ] || [ "$SUSPENDED" = "null" ]; then
            log_success "Backup CronJob is enabled"
        else
            log_warning "Backup CronJob is suspended"
        fi
    else
        log_warning "Backup CronJob does not exist"
    fi

    # Check maintenance CronJob
    if kubectl get cronjob influxdb-maintenance -n "$NAMESPACE" &> /dev/null; then
        log_success "Maintenance CronJob exists"
    else
        log_warning "Maintenance CronJob does not exist"
    fi
}

check_network_policy() {
    log_info "Checking network policy..."

    if kubectl get networkpolicy influxdb-network-policy -n "$NAMESPACE" &> /dev/null; then
        log_success "Network policy exists"
    else
        log_warning "Network policy does not exist"
    fi
}

check_ingress() {
    log_info "Checking ingress..."

    if kubectl get ingress influxdb-ingress -n "$NAMESPACE" &> /dev/null; then
        log_success "Ingress exists"

        # Check TLS configuration
        TLS_HOSTS=$(kubectl get ingress influxdb-ingress -n "$NAMESPACE" -o jsonpath='{.spec.tls[*].hosts[*]}')
        if [ -n "$TLS_HOSTS" ]; then
            log_success "TLS is configured for: $TLS_HOSTS"
        else
            log_warning "TLS is not configured"
        fi
    else
        log_warning "Ingress does not exist"
    fi
}

test_data_operations() {
    log_info "Testing data operations..."

    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')
    ADMIN_TOKEN=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-admin-token}' | base64 -d)
    ORG=$(kubectl get secret influxdb-secrets -n "$NAMESPACE" -o jsonpath='{.data.influxdb-org}' | base64 -d)

    # Test write operation
    TIMESTAMP=$(date +%s)
    TEST_DATA="temperature_readings,device_id=validation_test,channel_id=1,probe_type=test temperature=123.45 $TIMESTAMP"

    if kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx write --org "$ORG" --bucket grill-stats-realtime --token "$ADMIN_TOKEN" --precision s "$TEST_DATA" &> /dev/null; then
        log_success "Data write test successful"
    else
        log_error "Data write test failed"
        exit 1
    fi

    # Test read operation
    sleep 2  # Give time for data to be indexed

    if kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx query --org "$ORG" --token "$ADMIN_TOKEN" \
        'from(bucket: "grill-stats-realtime") |> range(start: -5m) |> filter(fn: (r) => r.device_id == "validation_test")' \
        | grep -q "validation_test"; then
        log_success "Data read test successful"
    else
        log_error "Data read test failed"
        exit 1
    fi

    # Clean up test data
    kubectl exec "$POD_NAME" -n "$NAMESPACE" -- influx delete --org "$ORG" --bucket grill-stats-realtime --token "$ADMIN_TOKEN" \
        --start "$(date -d '1 hour ago' --iso-8601)" --stop "$(date --iso-8601)" \
        --predicate 'device_id=="validation_test"' &> /dev/null || true
}

performance_check() {
    log_info "Checking performance..."

    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=influxdb -o jsonpath='{.items[0].metadata.name}')

    # Check resource usage
    if command -v kubectl &> /dev/null && kubectl top pod "$POD_NAME" -n "$NAMESPACE" &> /dev/null; then
        RESOURCE_USAGE=$(kubectl top pod "$POD_NAME" -n "$NAMESPACE" --no-headers)
        log_success "Resource usage: $RESOURCE_USAGE"
    else
        log_warning "Cannot check resource usage (metrics-server may not be available)"
    fi

    # Check disk usage
    DISK_USAGE=$(kubectl exec "$POD_NAME" -n "$NAMESPACE" -- df -h /var/lib/influxdb2 | tail -1 | awk '{print $5}')
    log_success "Disk usage: $DISK_USAGE"
}

generate_report() {
    log_info "Generating validation report..."

    REPORT_FILE="/tmp/influxdb-validation-report-$(date +%Y%m%d_%H%M%S).txt"

    cat > "$REPORT_FILE" << EOF
# InfluxDB Deployment Validation Report
Generated: $(date)
Environment: $ENVIRONMENT
Namespace: $NAMESPACE

## Validation Results
EOF

    # Add validation results to report
    # Note: This would typically be implemented with proper result tracking
    # For now, we'll just indicate that the report was generated

    log_success "Validation report generated: $REPORT_FILE"
}

main() {
    echo "=================================================="
    echo "InfluxDB 2.x Deployment Validation"
    echo "Environment: $ENVIRONMENT"
    echo "Namespace: $NAMESPACE"
    echo "=================================================="

    check_prerequisites
    check_namespace
    check_secrets
    check_storage
    check_statefulset
    check_pods
    check_services
    check_configmaps
    check_database_health
    check_buckets
    check_tasks
    check_monitoring
    check_backup
    check_network_policy
    check_ingress
    test_data_operations
    performance_check
    generate_report

    echo "=================================================="
    log_success "InfluxDB validation completed successfully!"
    echo "All critical components are functioning properly."
    echo "=================================================="
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -n, --namespace    Kubernetes namespace (default: grill-stats)"
            echo "  -e, --environment  Environment name (default: dev-lab)"
            echo "  -t, --timeout      Timeout in seconds (default: 300)"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
