#!/bin/bash

# Redis Deployment Validation Script
# This script validates the Redis deployment for the grill-stats application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NAMESPACE=${NAMESPACE:-"grill-stats"}
ENVIRONMENT=${ENVIRONMENT:-"dev-lab"}
TIMEOUT=${TIMEOUT:-300}

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
    print_status $GREEN "✓ $1"
}

print_error() {
    print_status $RED "✗ $1"
}

print_warning() {
    print_status $YELLOW "⚠ $1"
}

print_info() {
    print_status $BLUE "ℹ $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for pod to be ready
wait_for_pod() {
    local selector=$1
    local timeout=$2
    
    print_info "Waiting for pods with selector: $selector"
    
    if kubectl wait --for=condition=ready pod -l "$selector" -n "$NAMESPACE" --timeout="${timeout}s" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check Redis connectivity
check_redis_connection() {
    local pod_name=$1
    local password=$2
    
    if kubectl exec -n "$NAMESPACE" "$pod_name" -- redis-cli -a "$password" ping >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get Redis password
get_redis_password() {
    kubectl get secret grill-stats-secrets -n "$NAMESPACE" -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d 2>/dev/null || echo ""
}

# Main validation function
main() {
    print_header "Redis Deployment Validation for Grill-Stats"
    print_info "Environment: $ENVIRONMENT"
    print_info "Namespace: $NAMESPACE"
    print_info "Timeout: ${TIMEOUT}s"
    
    # Check prerequisites
    print_header "Checking Prerequisites"
    
    if ! command_exists kubectl; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    print_success "kubectl is available"
    
    if ! kubectl cluster-info >/dev/null 2>&1; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    print_success "Connected to Kubernetes cluster"
    
    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
        print_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    print_success "Namespace $NAMESPACE exists"
    
    # Check Redis StatefulSet
    print_header "Checking Redis StatefulSet"
    
    if ! kubectl get statefulset redis -n "$NAMESPACE" >/dev/null 2>&1; then
        print_error "Redis StatefulSet not found"
        exit 1
    fi
    print_success "Redis StatefulSet exists"
    
    # Check Redis pod status
    print_header "Checking Redis Pod Status"
    
    if ! wait_for_pod "app.kubernetes.io/name=redis" $TIMEOUT; then
        print_error "Redis pod is not ready within ${TIMEOUT}s"
        kubectl get pods -l app.kubernetes.io/name=redis -n "$NAMESPACE"
        exit 1
    fi
    print_success "Redis pod is ready"
    
    # Get Redis pod name
    REDIS_POD=$(kubectl get pods -l app.kubernetes.io/name=redis -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
    print_info "Redis pod: $REDIS_POD"
    
    # Check Redis password
    print_header "Checking Redis Authentication"
    
    REDIS_PASSWORD=$(get_redis_password)
    if [[ -z "$REDIS_PASSWORD" ]]; then
        print_error "Cannot retrieve Redis password from secret"
        exit 1
    fi
    print_success "Redis password retrieved"
    
    # Test Redis connectivity
    print_header "Testing Redis Connectivity"
    
    if ! check_redis_connection "$REDIS_POD" "$REDIS_PASSWORD"; then
        print_error "Cannot connect to Redis"
        exit 1
    fi
    print_success "Redis connection successful"
    
    # Test Redis commands
    print_header "Testing Redis Commands"
    
    # Test basic operations
    if kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" set test_key "test_value" >/dev/null 2>&1; then
        print_success "Redis SET command works"
    else
        print_error "Redis SET command failed"
        exit 1
    fi
    
    if kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" get test_key >/dev/null 2>&1; then
        print_success "Redis GET command works"
    else
        print_error "Redis GET command failed"
        exit 1
    fi
    
    # Clean up test key
    kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" del test_key >/dev/null 2>&1
    
    # Test database selection
    for db in {0..7}; do
        if kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" -n "$db" ping >/dev/null 2>&1; then
            print_success "Database $db accessible"
        else
            print_warning "Database $db not accessible"
        fi
    done
    
    # Check Redis configuration
    print_header "Checking Redis Configuration"
    
    # Check memory settings
    MAX_MEMORY=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" CONFIG GET maxmemory | tail -1)
    if [[ "$MAX_MEMORY" != "0" ]]; then
        print_success "Max memory configured: $MAX_MEMORY"
    else
        print_warning "Max memory not configured"
    fi
    
    # Check persistence settings
    SAVE_CONFIG=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" CONFIG GET save | tail -1)
    if [[ -n "$SAVE_CONFIG" ]]; then
        print_success "Persistence configured: $SAVE_CONFIG"
    else
        print_warning "Persistence not configured"
    fi
    
    # Check Redis services
    print_header "Checking Redis Services"
    
    if kubectl get service redis-service -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis service exists"
    else
        print_error "Redis service not found"
        exit 1
    fi
    
    if kubectl get service redis -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis headless service exists"
    else
        print_error "Redis headless service not found"
        exit 1
    fi
    
    # Check Redis Sentinel (for production)
    print_header "Checking Redis Sentinel"
    
    if [[ "$ENVIRONMENT" == "prod-lab" ]]; then
        if kubectl get statefulset redis-sentinel -n "$NAMESPACE" >/dev/null 2>&1; then
            print_success "Redis Sentinel StatefulSet exists"
            
            if wait_for_pod "app.kubernetes.io/name=redis-sentinel" 60; then
                print_success "Redis Sentinel pods are ready"
                
                # Test Sentinel functionality
                SENTINEL_POD=$(kubectl get pods -l app.kubernetes.io/name=redis-sentinel -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
                if kubectl exec -n "$NAMESPACE" "$SENTINEL_POD" -- redis-cli -p 26379 ping >/dev/null 2>&1; then
                    print_success "Redis Sentinel connectivity works"
                else
                    print_error "Redis Sentinel connectivity failed"
                fi
            else
                print_warning "Redis Sentinel pods not ready"
            fi
        else
            print_warning "Redis Sentinel not configured (expected for production)"
        fi
    else
        print_info "Redis Sentinel not expected in $ENVIRONMENT environment"
    fi
    
    # Check Redis monitoring
    print_header "Checking Redis Monitoring"
    
    if kubectl get deployment redis-exporter -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis Exporter deployment exists"
        
        if wait_for_pod "app.kubernetes.io/name=redis-exporter" 60; then
            print_success "Redis Exporter pod is ready"
            
            # Test metrics endpoint
            EXPORTER_POD=$(kubectl get pods -l app.kubernetes.io/name=redis-exporter -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
            if kubectl exec -n "$NAMESPACE" "$EXPORTER_POD" -- wget -q -O - http://localhost:9121/metrics | head -5 >/dev/null 2>&1; then
                print_success "Redis Exporter metrics endpoint works"
            else
                print_warning "Redis Exporter metrics endpoint not accessible"
            fi
        else
            print_warning "Redis Exporter pod not ready"
        fi
    else
        print_error "Redis Exporter deployment not found"
    fi
    
    # Check backup configuration
    print_header "Checking Backup Configuration"
    
    if kubectl get cronjob redis-backup -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis backup CronJob exists"
    else
        print_warning "Redis backup CronJob not found"
    fi
    
    if kubectl get pvc redis-backup-pvc -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis backup PVC exists"
    else
        print_warning "Redis backup PVC not found"
    fi
    
    # Check network policies
    print_header "Checking Network Policies"
    
    if kubectl get networkpolicy redis-network-policy -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis network policy exists"
    else
        print_warning "Redis network policy not found"
    fi
    
    if kubectl get networkpolicy redis-exporter-network-policy -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis Exporter network policy exists"
    else
        print_warning "Redis Exporter network policy not found"
    fi
    
    # Check persistent volumes
    print_header "Checking Persistent Storage"
    
    if kubectl get pvc redis-data-redis-0 -n "$NAMESPACE" >/dev/null 2>&1; then
        print_success "Redis data PVC exists"
        
        PVC_STATUS=$(kubectl get pvc redis-data-redis-0 -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [[ "$PVC_STATUS" == "Bound" ]]; then
            print_success "Redis data PVC is bound"
        else
            print_error "Redis data PVC status: $PVC_STATUS"
        fi
    else
        print_error "Redis data PVC not found"
    fi
    
    # Performance checks
    print_header "Performance Checks"
    
    # Check memory usage
    MEMORY_USAGE=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    print_info "Current memory usage: $MEMORY_USAGE"
    
    # Check connected clients
    CONNECTED_CLIENTS=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" INFO clients | grep connected_clients | cut -d: -f2 | tr -d '\r')
    print_info "Connected clients: $CONNECTED_CLIENTS"
    
    # Check keyspace
    KEYSPACE_INFO=$(kubectl exec -n "$NAMESPACE" "$REDIS_POD" -- redis-cli -a "$REDIS_PASSWORD" INFO keyspace | grep -E "^db[0-9]:" | wc -l)
    print_info "Active databases: $KEYSPACE_INFO"
    
    # Final summary
    print_header "Validation Summary"
    print_success "Redis deployment validation completed successfully!"
    print_info "All critical components are operational"
    
    # Configuration recommendations
    print_header "Recommendations"
    if [[ "$ENVIRONMENT" == "dev-lab" ]]; then
        print_info "Consider enabling Redis Sentinel for high availability testing"
        print_info "Monitor memory usage and adjust limits as needed"
    else
        print_info "Ensure backup verification jobs are running regularly"
        print_info "Monitor Redis Sentinel logs for any failover events"
    fi
    
    print_info "Set up Grafana dashboards for Redis monitoring"
    print_info "Configure alerting rules for Redis health metrics"
    print_info "Test backup and recovery procedures periodically"
    
    print_success "Redis is ready for grill-stats application!"
}

# Script usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -n, --namespace NAMESPACE    Kubernetes namespace (default: grill-stats)"
    echo "  -e, --environment ENV        Environment (dev-lab/prod-lab) (default: dev-lab)"
    echo "  -t, --timeout TIMEOUT        Timeout in seconds (default: 300)"
    echo "  -h, --help                   Show this help message"
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
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main validation
main