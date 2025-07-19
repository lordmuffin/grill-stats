#!/bin/bash

# Grill-Stats ArgoCD Deployment Script
# This script deploys the grill-stats platform using ArgoCD GitOps

set -euo pipefail

# Configuration
ARGOCD_NAMESPACE="argocd"
REPO_URL="https://github.com/lordmuffin/grill-stats.git"
DEFAULT_ENVIRONMENT="prod-lab"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [ENVIRONMENT]

Deploy grill-stats platform using ArgoCD GitOps

ENVIRONMENTS:
    prod-lab    Production environment (default)
    dev-lab     Development environment
    all         Deploy both environments

OPTIONS:
    -h, --help              Show this help message
    -n, --namespace         ArgoCD namespace (default: argocd)
    -r, --repo-url          Repository URL (default: ${REPO_URL})
    -d, --dry-run           Show what would be deployed without applying
    -v, --validate          Validate configurations before deployment
    -w, --wait              Wait for applications to be healthy
    -f, --force             Force deployment even if applications exist
    --cleanup               Remove all grill-stats applications
    --status                Show status of all applications

EXAMPLES:
    $0                      Deploy production environment
    $0 dev-lab              Deploy development environment
    $0 all                  Deploy both environments
    $0 --dry-run prod-lab   Show what would be deployed
    $0 --status             Show application status
    $0 --cleanup            Remove all applications

EOF
}

# Parse command line arguments
ENVIRONMENT="${DEFAULT_ENVIRONMENT}"
DRY_RUN=false
VALIDATE=false
WAIT=false
FORCE=false
CLEANUP=false
STATUS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -n|--namespace)
            ARGOCD_NAMESPACE="$2"
            shift 2
            ;;
        -r|--repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--validate)
            VALIDATE=true
            shift
            ;;
        -w|--wait)
            WAIT=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --status)
            STATUS=true
            shift
            ;;
        prod-lab|dev-lab|all)
            ENVIRONMENT="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    # Check if connected to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Not connected to a Kubernetes cluster"
        exit 1
    fi

    # Check if ArgoCD namespace exists
    if ! kubectl get namespace "${ARGOCD_NAMESPACE}" &> /dev/null; then
        log_error "ArgoCD namespace '${ARGOCD_NAMESPACE}' does not exist"
        exit 1
    fi

    # Check if ArgoCD is running
    if ! kubectl get deployment argocd-application-controller -n "${ARGOCD_NAMESPACE}" &> /dev/null; then
        log_error "ArgoCD application controller not found in namespace '${ARGOCD_NAMESPACE}'"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Validate configurations
validate_configs() {
    log_info "Validating ArgoCD configurations..."

    # Validate base configurations
    for file in "${SCRIPT_DIR}/base"/*.yaml; do
        if [[ -f "$file" ]]; then
            log_info "Validating $(basename "$file")"
            if ! kubectl apply --dry-run=client -f "$file" &> /dev/null; then
                log_error "Validation failed for $(basename "$file")"
                return 1
            fi
        fi
    done

    # Validate environment overlays
    for env in prod-lab dev-lab; do
        if [[ -d "${SCRIPT_DIR}/overlays/${env}" ]]; then
            log_info "Validating ${env} overlay"
            if ! kubectl apply --dry-run=client -k "${SCRIPT_DIR}/overlays/${env}" &> /dev/null; then
                log_error "Validation failed for ${env} overlay"
                return 1
            fi
        fi
    done

    log_success "Configuration validation passed"
}

# Deploy applications
deploy_environment() {
    local env="$1"
    log_info "Deploying grill-stats platform for environment: ${env}"

    # Check if applications already exist
    if [[ "${FORCE}" == "false" ]]; then
        if kubectl get application "grill-stats-platform" -n "${ARGOCD_NAMESPACE}" &> /dev/null; then
            log_warning "Application grill-stats-platform already exists. Use --force to redeploy."
            return 0
        fi
    fi

    # Deploy based on environment
    case "${env}" in
        prod-lab)
            deploy_production
            ;;
        dev-lab)
            deploy_development
            ;;
        all)
            deploy_production
            deploy_development
            ;;
        *)
            log_error "Unknown environment: ${env}"
            exit 1
            ;;
    esac
}

# Deploy production environment
deploy_production() {
    log_info "Deploying production environment..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "DRY RUN: Would deploy production environment"
        kubectl apply --dry-run=client -k "${SCRIPT_DIR}/overlays/prod-lab"
    else
        kubectl apply -k "${SCRIPT_DIR}/overlays/prod-lab"
        log_success "Production environment deployed"
    fi
}

# Deploy development environment
deploy_development() {
    log_info "Deploying development environment..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "DRY RUN: Would deploy development environment"
        kubectl apply --dry-run=client -k "${SCRIPT_DIR}/overlays/dev-lab"
    else
        kubectl apply -k "${SCRIPT_DIR}/overlays/dev-lab"
        log_success "Development environment deployed"
    fi
}

# Wait for applications to be healthy
wait_for_applications() {
    log_info "Waiting for applications to be healthy..."

    local apps=(
        "grill-stats-platform"
        "grill-stats-secrets"
        "grill-stats-databases"
        "grill-stats-core-services"
        "grill-stats-monitoring"
    )

    for app in "${apps[@]}"; do
        log_info "Waiting for ${app} to be healthy..."

        # Wait up to 10 minutes for each application
        local timeout=600
        local elapsed=0

        while [[ $elapsed -lt $timeout ]]; do
            if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.status.health.status}' 2>/dev/null | grep -q "Healthy"; then
                log_success "${app} is healthy"
                break
            fi

            sleep 10
            elapsed=$((elapsed + 10))

            if [[ $elapsed -ge $timeout ]]; then
                log_warning "${app} did not become healthy within timeout"
            fi
        done
    done
}

# Show application status
show_status() {
    log_info "Grill-Stats ArgoCD Application Status"
    echo

    # Get all grill-stats applications
    local apps
    apps=$(kubectl get applications -n "${ARGOCD_NAMESPACE}" -o name | grep "grill-stats" | sort)

    if [[ -z "$apps" ]]; then
        log_warning "No grill-stats applications found"
        return 0
    fi

    printf "%-35s %-15s %-15s %-15s\n" "APPLICATION" "HEALTH" "SYNC" "ENVIRONMENT"
    printf "%-35s %-15s %-15s %-15s\n" "$(printf '%*s' 35 | tr ' ' '-')" "$(printf '%*s' 15 | tr ' ' '-')" "$(printf '%*s' 15 | tr ' ' '-')" "$(printf '%*s' 15 | tr ' ' '-')"

    for app in $apps; do
        local app_name
        app_name=$(basename "$app")

        local health
        health=$(kubectl get "$app" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")

        local sync
        sync=$(kubectl get "$app" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")

        local env
        env=$(kubectl get "$app" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/environment}' 2>/dev/null || echo "N/A")

        # Color coding
        local health_color=""
        case "$health" in
            "Healthy") health_color="${GREEN}" ;;
            "Progressing") health_color="${YELLOW}" ;;
            "Degraded") health_color="${RED}" ;;
            *) health_color="${NC}" ;;
        esac

        local sync_color=""
        case "$sync" in
            "Synced") sync_color="${GREEN}" ;;
            "OutOfSync") sync_color="${YELLOW}" ;;
            *) sync_color="${NC}" ;;
        esac

        printf "%-35s ${health_color}%-15s${NC} ${sync_color}%-15s${NC} %-15s\n" "$app_name" "$health" "$sync" "$env"
    done
}

# Cleanup applications
cleanup_applications() {
    log_warning "This will remove all grill-stats applications from ArgoCD"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled"
        return 0
    fi

    log_info "Removing grill-stats applications..."

    # Remove applications in reverse order of dependencies
    local apps=(
        "grill-stats-monitoring"
        "grill-stats-core-services"
        "grill-stats-databases"
        "grill-stats-secrets"
        "grill-stats-platform"
        "grill-stats-project"
    )

    for app in "${apps[@]}"; do
        if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &> /dev/null; then
            log_info "Removing ${app}..."
            kubectl delete application "${app}" -n "${ARGOCD_NAMESPACE}"
        fi
    done

    log_success "Cleanup completed"
}

# Main execution
main() {
    log_info "Grill-Stats ArgoCD Deployment Script"
    log_info "Repository: ${REPO_URL}"
    log_info "ArgoCD Namespace: ${ARGOCD_NAMESPACE}"

    # Handle special operations
    if [[ "${STATUS}" == "true" ]]; then
        show_status
        exit 0
    fi

    if [[ "${CLEANUP}" == "true" ]]; then
        cleanup_applications
        exit 0
    fi

    # Check prerequisites
    check_prerequisites

    # Validate configurations if requested
    if [[ "${VALIDATE}" == "true" ]]; then
        validate_configs
    fi

    # Deploy environment
    deploy_environment "${ENVIRONMENT}"

    # Wait for applications if requested
    if [[ "${WAIT}" == "true" ]]; then
        wait_for_applications
    fi

    # Show final status
    if [[ "${DRY_RUN}" == "false" ]]; then
        echo
        show_status
        echo
        log_success "Deployment completed successfully!"
        log_info "Access ArgoCD UI to monitor application status"
        log_info "Use '$0 --status' to check application health"
    fi
}

# Execute main function
main "$@"
