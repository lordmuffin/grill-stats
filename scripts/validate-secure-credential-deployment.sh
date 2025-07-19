#!/bin/bash
# Validation script for secure credential storage deployment
# This script validates the complete User Story 5 implementation

set -euo pipefail

# Configuration
NAMESPACE="grill-stats"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set kubectl path and add to PATH
KUBECTL_PATH="/mnt/c/Users/lordmuffin/Git/homelab/kubectl"
export PATH="$(dirname "$KUBECTL_PATH"):$PATH"

# Verify kubectl is accessible
if [ ! -f "$KUBECTL_PATH" ]; then
    echo "Error: kubectl not found at $KUBECTL_PATH"
    exit 1
fi

# Make kubectl executable if needed
chmod +x "$KUBECTL_PATH" 2>/dev/null || true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[ℹ]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

# Validation results
VALIDATION_RESULTS=()

# Function to add validation result
add_result() {
    local check_name="$1"
    local status="$2"
    local details="$3"

    VALIDATION_RESULTS+=("$check_name|$status|$details")
}

# Function to check if command exists
check_command() {
    local cmd="$1"
    if command -v "$cmd" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to validate prerequisites
validate_prerequisites() {
    print_section "Validating Prerequisites"

    # Check kubectl
    if check_command kubectl; then
        print_status "kubectl is available"
        add_result "kubectl_available" "PASS" "kubectl command found"
    else
        print_error "kubectl is not available"
        add_result "kubectl_available" "FAIL" "kubectl command not found"
    fi

    # Check vault
    if check_command vault; then
        print_status "vault CLI is available"
        add_result "vault_cli_available" "PASS" "vault command found"
    else
        print_warning "vault CLI is not available (optional for validation)"
        add_result "vault_cli_available" "WARN" "vault command not found"
    fi

    # Check curl
    if check_command curl; then
        print_status "curl is available"
        add_result "curl_available" "PASS" "curl command found"
    else
        print_error "curl is not available"
        add_result "curl_available" "FAIL" "curl command not found"
    fi

    # Check cluster connectivity
    if kubectl cluster-info &> /dev/null; then
        print_status "Kubernetes cluster is accessible"
        add_result "k8s_connectivity" "PASS" "Cluster connectivity verified"
    else
        print_error "Cannot connect to Kubernetes cluster"
        add_result "k8s_connectivity" "FAIL" "Cluster connectivity failed"
    fi
}

# Function to validate namespace
validate_namespace() {
    print_section "Validating Namespace"

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_status "Namespace '$NAMESPACE' exists"
        add_result "namespace_exists" "PASS" "Namespace found"
    else
        print_error "Namespace '$NAMESPACE' does not exist"
        add_result "namespace_exists" "FAIL" "Namespace not found"
    fi
}

# Function to validate secrets
validate_secrets() {
    print_section "Validating Secrets"

    local secrets=(
        "vault-token-secret"
        "vault-admin-token-secret"
        "database-credentials-secret"
        "jwt-secrets-secret"
        "thermoworks-api-secret"
    )

    for secret in "${secrets[@]}"; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
            print_status "Secret '$secret' exists"
            add_result "secret_${secret}" "PASS" "Secret found"

            # Check if secret has data
            local keys=$(kubectl get secret "$secret" -n "$NAMESPACE" -o jsonpath='{.data}' | jq -r 'keys[]' 2>/dev/null || echo "")
            if [ -n "$keys" ]; then
                print_info "  Keys: $keys"
                add_result "secret_${secret}_data" "PASS" "Secret has data"
            else
                print_warning "  Secret '$secret' has no data"
                add_result "secret_${secret}_data" "WARN" "Secret has no data"
            fi
        else
            print_error "Secret '$secret' does not exist"
            add_result "secret_${secret}" "FAIL" "Secret not found"
        fi
    done
}

# Function to validate services
validate_services() {
    print_section "Validating Services"

    local services=(
        "encryption-service"
        "auth-service"
    )

    for service in "${services[@]}"; do
        if kubectl get service "$service" -n "$NAMESPACE" &> /dev/null; then
            print_status "Service '$service' exists"
            add_result "service_${service}" "PASS" "Service found"
        else
            print_error "Service '$service' does not exist"
            add_result "service_${service}" "FAIL" "Service not found"
        fi
    done
}

# Function to validate deployments
validate_deployments() {
    print_section "Validating Deployments"

    local deployments=(
        "encryption-service"
        "auth-service"
    )

    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            print_status "Deployment '$deployment' exists"
            add_result "deployment_${deployment}" "PASS" "Deployment found"

            # Check deployment status
            local ready=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
            local desired=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

            if [ "$ready" -eq "$desired" ] && [ "$ready" -gt 0 ]; then
                print_status "  Deployment '$deployment' is ready ($ready/$desired)"
                add_result "deployment_${deployment}_ready" "PASS" "Deployment is ready"
            else
                print_error "  Deployment '$deployment' is not ready ($ready/$desired)"
                add_result "deployment_${deployment}_ready" "FAIL" "Deployment not ready"
            fi
        else
            print_error "Deployment '$deployment' does not exist"
            add_result "deployment_${deployment}" "FAIL" "Deployment not found"
        fi
    done
}

# Function to validate database
validate_database() {
    print_section "Validating Database"

    # Check if PostgreSQL is running
    if kubectl get pods -n "$NAMESPACE" -l app=postgresql --field-selector=status.phase=Running | grep -q Running; then
        print_status "PostgreSQL is running"
        add_result "postgresql_running" "PASS" "PostgreSQL pod is running"

        # Check database tables
        local tables=(
            "thermoworks_credentials"
            "credential_access_log"
            "encryption_key_management"
        )

        for table in "${tables[@]}"; do
            if kubectl exec -n "$NAMESPACE" -i postgresql-0 -- psql -U grill_stats_app -d grill_stats -c "\dt $table" &> /dev/null; then
                print_status "Table '$table' exists"
                add_result "table_${table}" "PASS" "Table found"
            else
                print_error "Table '$table' does not exist"
                add_result "table_${table}" "FAIL" "Table not found"
            fi
        done
    else
        print_warning "PostgreSQL is not running or not accessible"
        add_result "postgresql_running" "WARN" "PostgreSQL not accessible"
    fi
}

# Function to validate vault integration
validate_vault() {
    print_section "Validating Vault Integration"

    # Check if Vault is accessible
    if kubectl get pods -n vault -l app=vault --field-selector=status.phase=Running | grep -q Running; then
        print_status "Vault is running"
        add_result "vault_running" "PASS" "Vault pod is running"

        # Test Vault connectivity from encryption service
        local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=encryption-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        if [ -n "$pod_name" ]; then
            if kubectl exec -n "$NAMESPACE" "$pod_name" -- curl -s -f http://vault.vault.svc.cluster.local:8200/v1/sys/health &> /dev/null; then
                print_status "Vault is accessible from encryption service"
                add_result "vault_connectivity" "PASS" "Vault connectivity verified"
            else
                print_error "Vault is not accessible from encryption service"
                add_result "vault_connectivity" "FAIL" "Vault connectivity failed"
            fi
        else
            print_warning "Cannot find encryption service pod for connectivity test"
            add_result "vault_connectivity" "WARN" "Cannot test connectivity"
        fi
    else
        print_warning "Vault is not running or not accessible"
        add_result "vault_running" "WARN" "Vault not accessible"
    fi
}

# Function to validate API endpoints
validate_api_endpoints() {
    print_section "Validating API Endpoints"

    # Port forward to services for testing
    local encryption_port=8082
    local auth_port=8081

    # Test encryption service health
    kubectl port-forward -n "$NAMESPACE" svc/encryption-service $encryption_port:8082 &
    local encryption_pf_pid=$!
    sleep 2

    if curl -s -f http://localhost:$encryption_port/health &> /dev/null; then
        print_status "Encryption service health endpoint is accessible"
        add_result "encryption_health" "PASS" "Health endpoint accessible"
    else
        print_error "Encryption service health endpoint is not accessible"
        add_result "encryption_health" "FAIL" "Health endpoint not accessible"
    fi

    # Test auth service health
    kubectl port-forward -n "$NAMESPACE" svc/auth-service $auth_port:8082 &
    local auth_pf_pid=$!
    sleep 2

    if curl -s -f http://localhost:$auth_port/health &> /dev/null; then
        print_status "Auth service health endpoint is accessible"
        add_result "auth_health" "PASS" "Health endpoint accessible"
    else
        print_error "Auth service health endpoint is not accessible"
        add_result "auth_health" "FAIL" "Health endpoint not accessible"
    fi

    # Clean up port forwards
    kill $encryption_pf_pid $auth_pf_pid 2>/dev/null || true
}

# Function to validate key rotation
validate_key_rotation() {
    print_section "Validating Key Rotation"

    # Check if key rotation CronJob exists
    if kubectl get cronjob key-rotation-cronjob -n "$NAMESPACE" &> /dev/null; then
        print_status "Key rotation CronJob exists"
        add_result "key_rotation_cronjob" "PASS" "CronJob found"

        # Check CronJob schedule
        local schedule=$(kubectl get cronjob key-rotation-cronjob -n "$NAMESPACE" -o jsonpath='{.spec.schedule}' 2>/dev/null || echo "")
        if [ -n "$schedule" ]; then
            print_info "  Schedule: $schedule"
            add_result "key_rotation_schedule" "PASS" "Schedule configured"
        else
            print_warning "  No schedule found"
            add_result "key_rotation_schedule" "WARN" "No schedule found"
        fi
    else
        print_warning "Key rotation CronJob does not exist"
        add_result "key_rotation_cronjob" "WARN" "CronJob not found"
    fi

    # Check if key rotation health check exists
    if kubectl get cronjob key-rotation-health-check -n "$NAMESPACE" &> /dev/null; then
        print_status "Key rotation health check CronJob exists"
        add_result "key_rotation_health_check" "PASS" "Health check CronJob found"
    else
        print_warning "Key rotation health check CronJob does not exist"
        add_result "key_rotation_health_check" "WARN" "Health check CronJob not found"
    fi
}

# Function to validate security configuration
validate_security() {
    print_section "Validating Security Configuration"

    # Check pod security contexts
    local deployments=(
        "encryption-service"
        "auth-service"
    )

    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            local security_context=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.securityContext}' 2>/dev/null || echo "{}")

            if echo "$security_context" | jq -e '.runAsNonRoot == true' &> /dev/null; then
                print_status "Deployment '$deployment' runs as non-root"
                add_result "security_${deployment}_nonroot" "PASS" "Non-root user configured"
            else
                print_error "Deployment '$deployment' may run as root"
                add_result "security_${deployment}_nonroot" "FAIL" "Non-root user not configured"
            fi

            if echo "$security_context" | jq -e '.fsGroup' &> /dev/null; then
                print_status "Deployment '$deployment' has filesystem group configured"
                add_result "security_${deployment}_fsgroup" "PASS" "Filesystem group configured"
            else
                print_warning "Deployment '$deployment' has no filesystem group"
                add_result "security_${deployment}_fsgroup" "WARN" "Filesystem group not configured"
            fi
        fi
    done

    # Check network policies
    if kubectl get networkpolicy -n "$NAMESPACE" | grep -q encryption-service; then
        print_status "Network policies are configured"
        add_result "network_policies" "PASS" "Network policies found"
    else
        print_warning "Network policies are not configured"
        add_result "network_policies" "WARN" "Network policies not found"
    fi
}

# Function to validate monitoring
validate_monitoring() {
    print_section "Validating Monitoring"

    # Check if monitoring is configured
    if kubectl get servicemonitor -n "$NAMESPACE" &> /dev/null; then
        print_status "Service monitors are configured"
        add_result "monitoring_servicemonitor" "PASS" "Service monitors found"
    else
        print_warning "Service monitors are not configured"
        add_result "monitoring_servicemonitor" "WARN" "Service monitors not found"
    fi

    # Check if logging is configured
    local deployments=(
        "encryption-service"
        "auth-service"
    )

    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app="$deployment" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
            if [ -n "$pod_name" ]; then
                if kubectl logs -n "$NAMESPACE" "$pod_name" --tail=1 &> /dev/null; then
                    print_status "Logging is working for '$deployment'"
                    add_result "logging_${deployment}" "PASS" "Logging accessible"
                else
                    print_error "Logging is not working for '$deployment'"
                    add_result "logging_${deployment}" "FAIL" "Logging not accessible"
                fi
            fi
        fi
    done
}

# Function to generate validation report
generate_report() {
    print_section "Validation Report"

    local pass_count=0
    local fail_count=0
    local warn_count=0
    local total_count=0

    echo ""
    printf "%-40s %-8s %-s\n" "Check" "Status" "Details"
    printf "%-40s %-8s %-s\n" "----" "------" "-------"

    for result in "${VALIDATION_RESULTS[@]}"; do
        IFS='|' read -r check_name status details <<< "$result"

        case "$status" in
            "PASS")
                printf "%-40s ${GREEN}%-8s${NC} %-s\n" "$check_name" "$status" "$details"
                ((pass_count++))
                ;;
            "FAIL")
                printf "%-40s ${RED}%-8s${NC} %-s\n" "$check_name" "$status" "$details"
                ((fail_count++))
                ;;
            "WARN")
                printf "%-40s ${YELLOW}%-8s${NC} %-s\n" "$check_name" "$status" "$details"
                ((warn_count++))
                ;;
        esac
        ((total_count++))
    done

    echo ""
    echo "Summary:"
    echo "  Total checks: $total_count"
    echo "  Passed: $pass_count"
    echo "  Failed: $fail_count"
    echo "  Warnings: $warn_count"

    if [ $fail_count -eq 0 ]; then
        print_status "All critical checks passed!"
        if [ $warn_count -gt 0 ]; then
            print_warning "Some non-critical warnings were found"
        fi
        return 0
    else
        print_error "$fail_count critical checks failed"
        return 1
    fi
}

# Function to save report to file
save_report() {
    local report_file="$SCRIPT_DIR/../validation-report-$(date +%Y%m%d-%H%M%S).json"

    cat > "$report_file" << EOF
{
  "validation_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "validator_version": "1.0.0",
  "namespace": "$NAMESPACE",
  "results": [
EOF

    local first=true
    for result in "${VALIDATION_RESULTS[@]}"; do
        IFS='|' read -r check_name status details <<< "$result"

        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$report_file"
        fi

        cat >> "$report_file" << EOF
    {
      "check_name": "$check_name",
      "status": "$status",
      "details": "$details"
    }
EOF
    done

    cat >> "$report_file" << EOF
  ]
}
EOF

    print_info "Validation report saved to: $report_file"
}

# Main function
main() {
    print_section "User Story 5: Secure Credential Storage - Deployment Validation"
    print_info "Validating the complete implementation of secure credential storage"

    # Run all validation checks
    validate_prerequisites
    validate_namespace
    validate_secrets
    validate_services
    validate_deployments
    validate_database
    validate_vault
    validate_api_endpoints
    validate_key_rotation
    validate_security
    validate_monitoring

    # Generate and save report
    if generate_report; then
        save_report
        print_section "Validation Completed Successfully"
        print_status "User Story 5 implementation is ready for production use!"
        exit 0
    else
        save_report
        print_section "Validation Completed with Issues"
        print_error "Please address the failed checks before proceeding to production"
        exit 1
    fi
}

# Run main function
main "$@"
