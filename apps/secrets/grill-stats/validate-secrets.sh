#!/bin/bash

# Grill Stats 1Password Connect Secrets Validation Script
# This script validates the secret configurations and deployment status

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${SCRIPT_DIR}"
ENVIRONMENTS=("dev-lab" "prod-lab")
REQUIRED_TOOLS=("kubectl" "kustomize" "yq" "jq")

# Logging functions
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

# Check if required tools are installed
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    for tool in "${REQUIRED_TOOLS[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    log_success "All required tools are available"
}

# Validate YAML syntax
validate_yaml_syntax() {
    local file="$1"
    log_info "Validating YAML syntax for $file"
    
    if ! yq eval '.' "$file" > /dev/null 2>&1; then
        log_error "Invalid YAML syntax in $file"
        return 1
    fi
    
    log_success "YAML syntax valid for $file"
    return 0
}

# Validate Kubernetes resources
validate_kubernetes_resources() {
    local file="$1"
    log_info "Validating Kubernetes resources in $file"
    
    # Check if file contains valid Kubernetes resources
    if ! kubectl --dry-run=client -f "$file" create &> /dev/null; then
        log_error "Invalid Kubernetes resources in $file"
        return 1
    fi
    
    log_success "Kubernetes resources valid in $file"
    return 0
}

# Validate OnePassword Connect resources
validate_onepassword_resources() {
    local file="$1"
    log_info "Validating OnePassword Connect resources in $file"
    
    # Check for required fields in OnePasswordItem resources
    local onepassword_items
    onepassword_items=$(yq eval '.[] | select(.kind == "OnePasswordItem")' "$file" 2>/dev/null || echo "")
    
    if [[ -n "$onepassword_items" ]]; then
        # Validate itemPath is present
        if ! yq eval '.[] | select(.kind == "OnePasswordItem") | .spec.itemPath' "$file" | grep -q "vaults/"; then
            log_error "OnePasswordItem resources missing proper itemPath in $file"
            return 1
        fi
        
        log_success "OnePassword Connect resources valid in $file"
    fi
    
    return 0
}

# Validate secret structure
validate_secret_structure() {
    local file="$1"
    log_info "Validating secret structure in $file"
    
    # Check for required labels
    local secrets
    secrets=$(yq eval '.[] | select(.kind == "Secret")' "$file" 2>/dev/null || echo "")
    
    if [[ -n "$secrets" ]]; then
        # Check for required labels
        local required_labels=("app.kubernetes.io/name" "app.kubernetes.io/component" "managed-by")
        
        for label in "${required_labels[@]}"; do
            if ! yq eval ".[] | select(.kind == \"Secret\") | .metadata.labels.\"$label\"" "$file" | grep -q "."; then
                log_warning "Secret missing required label '$label' in $file"
            fi
        done
        
        # Check for OnePassword annotation
        if ! yq eval '.[] | select(.kind == "Secret") | .metadata.annotations."onepassword.com/item-path"' "$file" | grep -q "vaults/"; then
            log_warning "Secret missing OnePassword annotation in $file"
        fi
        
        log_success "Secret structure valid in $file"
    fi
    
    return 0
}

# Validate environment-specific configurations
validate_environment_config() {
    local env="$1"
    local env_dir="${BASE_DIR}/${env}"
    
    log_info "Validating environment configuration for $env"
    
    if [[ ! -d "$env_dir" ]]; then
        log_error "Environment directory $env_dir does not exist"
        return 1
    fi
    
    # Check for required files
    local required_files=("kustomization.yaml" "environment-secrets-1password.yaml")
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$env_dir/$file" ]]; then
            log_error "Required file $file missing in $env_dir"
            return 1
        fi
    done
    
    # Validate kustomization can build
    if ! kustomize build "$env_dir" > /dev/null 2>&1; then
        log_error "Kustomization build failed for $env"
        return 1
    fi
    
    log_success "Environment configuration valid for $env"
    return 0
}

# Check secret deployment status
check_secret_deployment() {
    local namespace="$1"
    local secret_name="$2"
    
    log_info "Checking deployment status of secret $secret_name in namespace $namespace"
    
    # Check if namespace exists
    if ! kubectl get namespace "$namespace" &> /dev/null; then
        log_warning "Namespace $namespace does not exist"
        return 1
    fi
    
    # Check if secret exists
    if ! kubectl get secret "$secret_name" -n "$namespace" &> /dev/null; then
        log_warning "Secret $secret_name does not exist in namespace $namespace"
        return 1
    fi
    
    # Check if secret has data
    local secret_data
    secret_data=$(kubectl get secret "$secret_name" -n "$namespace" -o jsonpath='{.data}' 2>/dev/null || echo "{}")
    
    if [[ "$secret_data" == "{}" ]]; then
        log_warning "Secret $secret_name in namespace $namespace has no data"
        return 1
    fi
    
    log_success "Secret $secret_name deployed and populated in namespace $namespace"
    return 0
}

# Check OnePassword Connect operator status
check_onepassword_operator() {
    log_info "Checking OnePassword Connect operator status"
    
    # Check if OnePassword Connect operator is deployed
    if ! kubectl get deployment onepassword-connect-operator -n onepassword-connect &> /dev/null; then
        log_warning "OnePassword Connect operator not found"
        return 1
    fi
    
    # Check if operator is running
    local ready_replicas
    ready_replicas=$(kubectl get deployment onepassword-connect-operator -n onepassword-connect -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    
    if [[ "$ready_replicas" -eq 0 ]]; then
        log_warning "OnePassword Connect operator not ready"
        return 1
    fi
    
    log_success "OnePassword Connect operator is running"
    return 0
}

# Generate validation report
generate_validation_report() {
    local report_file="${BASE_DIR}/validation-report.json"
    log_info "Generating validation report: $report_file"
    
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    cat > "$report_file" << EOF
{
  "validation_timestamp": "$timestamp",
  "script_version": "1.0.0",
  "base_directory": "$BASE_DIR",
  "environments": $(printf '%s\n' "${ENVIRONMENTS[@]}" | jq -R . | jq -s .),
  "validation_results": {
    "yaml_syntax": {},
    "kubernetes_resources": {},
    "onepassword_resources": {},
    "secret_structure": {},
    "environment_configs": {},
    "secret_deployments": {},
    "operator_status": {}
  }
}
EOF
    
    log_success "Validation report template created: $report_file"
}

# Main validation function
main() {
    local exit_code=0
    
    log_info "Starting Grill Stats 1Password Connect secrets validation"
    
    # Check prerequisites
    check_prerequisites
    
    # Generate validation report
    generate_validation_report
    
    # Validate base configuration files
    log_info "Validating base configuration files..."
    
    for file in "$BASE_DIR"/*.yaml; do
        if [[ -f "$file" ]]; then
            validate_yaml_syntax "$file" || exit_code=1
            validate_kubernetes_resources "$file" || exit_code=1
            validate_onepassword_resources "$file" || exit_code=1
            validate_secret_structure "$file" || exit_code=1
        fi
    done
    
    # Validate environment-specific configurations
    log_info "Validating environment-specific configurations..."
    
    for env in "${ENVIRONMENTS[@]}"; do
        validate_environment_config "$env" || exit_code=1
        
        # Validate environment-specific files
        for file in "$BASE_DIR/$env"/*.yaml; do
            if [[ -f "$file" ]]; then
                validate_yaml_syntax "$file" || exit_code=1
                validate_kubernetes_resources "$file" || exit_code=1
                validate_onepassword_resources "$file" || exit_code=1
                validate_secret_structure "$file" || exit_code=1
            fi
        done
    done
    
    # Check OnePassword Connect operator (if cluster is accessible)
    if kubectl cluster-info &> /dev/null; then
        log_info "Cluster accessible, checking deployed resources..."
        
        check_onepassword_operator || log_warning "OnePassword Connect operator check failed"
        
        # Check secret deployment status
        local namespaces=("grill-stats" "grill-stats-dev" "grill-stats-prod")
        local secrets=("auth-service-secrets" "device-service-secrets" "temperature-service-secrets")
        
        for namespace in "${namespaces[@]}"; do
            for secret in "${secrets[@]}"; do
                check_secret_deployment "$namespace" "$secret" || log_warning "Secret deployment check failed"
            done
        done
    else
        log_warning "Cluster not accessible, skipping deployment checks"
    fi
    
    # Final validation summary
    if [[ $exit_code -eq 0 ]]; then
        log_success "All validations passed successfully"
    else
        log_error "Some validations failed - check output above"
    fi
    
    return $exit_code
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -h, --help    Show this help message"
            echo "  --dry-run     Run validation without checking deployments"
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"