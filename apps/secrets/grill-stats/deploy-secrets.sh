#!/bin/bash

# Grill Stats 1Password Connect Secrets Deployment Script
# This script deploys the secret configurations to Kubernetes

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
REQUIRED_TOOLS=("kubectl" "kustomize")

# Default values
DRY_RUN=false
ENVIRONMENT=""
FORCE=false
SKIP_VALIDATION=false

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

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] [ENVIRONMENT]

Deploy Grill Stats 1Password Connect secrets to Kubernetes.

ENVIRONMENT:
  dev-lab     Deploy to development lab environment
  prod-lab    Deploy to production lab environment
  base        Deploy base secrets only
  all         Deploy to all environments (default)

OPTIONS:
  -h, --help           Show this help message
  --dry-run            Show what would be deployed without applying
  --force              Force deployment even if validation fails
  --skip-validation    Skip validation checks before deployment
  -v, --verbose        Enable verbose output

Examples:
  $0 dev-lab           Deploy to dev-lab environment
  $0 --dry-run         Show deployment plan for all environments
  $0 prod-lab --force  Force deploy to prod-lab
EOF
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
    
    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Validate secrets before deployment
validate_secrets() {
    local env="$1"
    
    if [[ "$SKIP_VALIDATION" == "true" ]]; then
        log_warning "Skipping validation as requested"
        return 0
    fi
    
    log_info "Validating secrets for environment: $env"
    
    local validation_script="${BASE_DIR}/validate-secrets.sh"
    
    if [[ ! -f "$validation_script" ]]; then
        log_warning "Validation script not found, skipping validation"
        return 0
    fi
    
    if ! "$validation_script" --dry-run; then
        log_error "Validation failed for environment: $env"
        if [[ "$FORCE" == "false" ]]; then
            log_error "Use --force to deploy anyway"
            return 1
        else
            log_warning "Validation failed but forcing deployment"
        fi
    fi
    
    log_success "Validation passed for environment: $env"
    return 0
}

# Create namespace if it doesn't exist
ensure_namespace() {
    local namespace="$1"
    
    log_info "Ensuring namespace exists: $namespace"
    
    if ! kubectl get namespace "$namespace" &> /dev/null; then
        log_info "Creating namespace: $namespace"
        if [[ "$DRY_RUN" == "false" ]]; then
            kubectl create namespace "$namespace"
        else
            log_info "[DRY RUN] Would create namespace: $namespace"
        fi
    else
        log_info "Namespace already exists: $namespace"
    fi
}

# Deploy secrets for a specific environment
deploy_environment() {
    local env="$1"
    local namespace
    local kustomize_dir
    
    case "$env" in
        "base")
            namespace="grill-stats"
            kustomize_dir="$BASE_DIR"
            ;;
        "dev-lab")
            namespace="grill-stats-dev"
            kustomize_dir="$BASE_DIR/dev-lab"
            ;;
        "prod-lab")
            namespace="grill-stats-prod"
            kustomize_dir="$BASE_DIR/prod-lab"
            ;;
        *)
            log_error "Unknown environment: $env"
            return 1
            ;;
    esac
    
    log_info "Deploying secrets for environment: $env"
    log_info "Namespace: $namespace"
    log_info "Kustomize directory: $kustomize_dir"
    
    # Validate secrets
    validate_secrets "$env" || return 1
    
    # Ensure namespace exists
    ensure_namespace "$namespace"
    
    # Build kustomization
    log_info "Building kustomization for environment: $env"
    
    if ! kustomize build "$kustomize_dir" > /dev/null; then
        log_error "Failed to build kustomization for environment: $env"
        return 1
    fi
    
    # Deploy secrets
    log_info "Deploying secrets for environment: $env"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would deploy the following resources:"
        kustomize build "$kustomize_dir" | kubectl apply --dry-run=client -f -
    else
        if kustomize build "$kustomize_dir" | kubectl apply -f -; then
            log_success "Successfully deployed secrets for environment: $env"
        else
            log_error "Failed to deploy secrets for environment: $env"
            return 1
        fi
    fi
    
    return 0
}

# Wait for secrets to be populated by OnePassword Connect
wait_for_secrets() {
    local namespace="$1"
    local timeout=300  # 5 minutes
    local interval=10  # 10 seconds
    
    log_info "Waiting for OnePassword Connect to populate secrets in namespace: $namespace"
    
    local secrets=("auth-service-secrets" "device-service-secrets" "temperature-service-secrets")
    
    for secret in "${secrets[@]}"; do
        log_info "Waiting for secret: $secret"
        
        local elapsed=0
        while [[ $elapsed -lt $timeout ]]; do
            if kubectl get secret "$secret" -n "$namespace" -o jsonpath='{.data}' 2>/dev/null | grep -q "."; then
                log_success "Secret populated: $secret"
                break
            fi
            
            sleep $interval
            elapsed=$((elapsed + interval))
            log_info "Waiting for secret $secret... (${elapsed}s/${timeout}s)"
        done
        
        if [[ $elapsed -ge $timeout ]]; then
            log_warning "Timeout waiting for secret to be populated: $secret"
        fi
    done
}

# Verify deployment
verify_deployment() {
    local env="$1"
    local namespace
    
    case "$env" in
        "base")
            namespace="grill-stats"
            ;;
        "dev-lab")
            namespace="grill-stats-dev"
            ;;
        "prod-lab")
            namespace="grill-stats-prod"
            ;;
        *)
            log_error "Unknown environment: $env"
            return 1
            ;;
    esac
    
    log_info "Verifying deployment for environment: $env"
    
    # Check if OnePasswordItem resources exist
    local onepassword_items
    onepassword_items=$(kubectl get onepassworditems -n "$namespace" --no-headers 2>/dev/null | wc -l)
    
    if [[ $onepassword_items -eq 0 ]]; then
        log_warning "No OnePasswordItem resources found in namespace: $namespace"
    else
        log_success "Found $onepassword_items OnePasswordItem resources in namespace: $namespace"
    fi
    
    # Check if secrets exist
    local secrets
    secrets=$(kubectl get secrets -n "$namespace" --no-headers 2>/dev/null | grep -c "grill-stats" || echo "0")
    
    if [[ $secrets -eq 0 ]]; then
        log_warning "No grill-stats secrets found in namespace: $namespace"
    else
        log_success "Found $secrets grill-stats secrets in namespace: $namespace"
    fi
    
    # Wait for secrets to be populated (if not dry run)
    if [[ "$DRY_RUN" == "false" ]]; then
        wait_for_secrets "$namespace"
    fi
    
    return 0
}

# Main deployment function
main() {
    local exit_code=0
    
    log_info "Starting Grill Stats 1Password Connect secrets deployment"
    
    # Check prerequisites
    check_prerequisites
    
    # Determine what to deploy
    if [[ -n "$ENVIRONMENT" ]]; then
        if [[ "$ENVIRONMENT" == "all" ]]; then
            # Deploy to all environments
            for env in "base" "${ENVIRONMENTS[@]}"; do
                deploy_environment "$env" || exit_code=1
                verify_deployment "$env" || exit_code=1
            done
        else
            # Deploy to specific environment
            deploy_environment "$ENVIRONMENT" || exit_code=1
            verify_deployment "$ENVIRONMENT" || exit_code=1
        fi
    else
        # Default: deploy to all environments
        for env in "base" "${ENVIRONMENTS[@]}"; do
            deploy_environment "$env" || exit_code=1
            verify_deployment "$env" || exit_code=1
        done
    fi
    
    # Final deployment summary
    if [[ $exit_code -eq 0 ]]; then
        log_success "All deployments completed successfully"
        log_info "Next steps:"
        log_info "1. Verify OnePassword Connect operator is running"
        log_info "2. Check that secrets are populated with data"
        log_info "3. Update service deployments to use the new secrets"
    else
        log_error "Some deployments failed - check output above"
    fi
    
    return $exit_code
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        -v|--verbose)
            set -x
            shift
            ;;
        dev-lab|prod-lab|base|all)
            ENVIRONMENT="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set default environment if not specified
if [[ -z "$ENVIRONMENT" ]]; then
    ENVIRONMENT="all"
fi

# Run main function
main "$@"