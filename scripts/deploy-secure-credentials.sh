#!/bin/bash
# Deployment script for secure credential storage system
# This script deploys all components needed for encrypted credential storage

set -euo pipefail

# Configuration
NAMESPACE="grill-stats"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUSTOMIZE_DIR="${SCRIPT_DIR}/../kustomize"
VAULT_NAMESPACE="vault"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    print_status "kubectl is available"
}

# Function to check if kustomize is available
check_kustomize() {
    if ! command -v kustomize &> /dev/null; then
        print_error "kustomize is not installed or not in PATH"
        exit 1
    fi

    print_status "kustomize is available"
}

# Function to check cluster connectivity
check_cluster() {
    print_status "Checking cluster connectivity..."

    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    print_status "Connected to Kubernetes cluster"
}

# Function to create namespace if it doesn't exist
create_namespace() {
    print_status "Creating namespace: $NAMESPACE"

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "Namespace '$NAMESPACE' already exists"
    else
        kubectl create namespace "$NAMESPACE"
        print_status "Created namespace: $NAMESPACE"
    fi
}

# Function to check if 1Password Connect is available
check_1password_connect() {
    print_status "Checking 1Password Connect availability..."

    if ! kubectl get pods -n onepassword-connect &> /dev/null; then
        print_warning "1Password Connect is not deployed"
        print_warning "Please deploy 1Password Connect before proceeding"
        return 1
    fi

    if ! kubectl get pods -n onepassword-connect -l app=onepassword-connect --field-selector=status.phase=Running | grep -q Running; then
        print_warning "1Password Connect is not running"
        return 1
    fi

    print_status "1Password Connect is available"
}

# Function to check if Vault is available
check_vault() {
    print_status "Checking Vault availability..."

    if ! kubectl get namespace "$VAULT_NAMESPACE" &> /dev/null; then
        print_warning "Vault namespace '$VAULT_NAMESPACE' does not exist"
        return 1
    fi

    if ! kubectl get pods -n "$VAULT_NAMESPACE" -l app=vault --field-selector=status.phase=Running | grep -q Running; then
        print_warning "Vault is not running"
        return 1
    fi

    print_status "Vault is available"
}

# Function to deploy 1Password secrets
deploy_1password_secrets() {
    print_status "Deploying 1Password secrets..."

    kubectl apply -f "${KUSTOMIZE_DIR}/base/namespace/1password-secrets.yaml"

    print_status "1Password secrets deployed"
}

# Function to deploy encryption service
deploy_encryption_service() {
    print_status "Deploying encryption service..."

    kubectl apply -f "${KUSTOMIZE_DIR}/base/core-services/encryption-service.yaml"

    print_status "Encryption service deployed"
}

# Function to deploy auth service
deploy_auth_service() {
    print_status "Deploying auth service..."

    kubectl apply -f "${KUSTOMIZE_DIR}/base/core-services/auth-service.yaml"

    print_status "Auth service deployed"
}

# Function to wait for deployment to be ready
wait_for_deployment() {
    local deployment_name="$1"
    local max_wait="${2:-300}"

    print_status "Waiting for deployment '$deployment_name' to be ready..."

    if kubectl wait --for=condition=available --timeout=${max_wait}s deployment/"$deployment_name" -n "$NAMESPACE"; then
        print_status "Deployment '$deployment_name' is ready"
    else
        print_error "Deployment '$deployment_name' failed to become ready"
        return 1
    fi
}

# Function to check deployment health
check_deployment_health() {
    local deployment_name="$1"
    local port="${2:-8082}"

    print_status "Checking health of deployment '$deployment_name'..."

    # Get a pod from the deployment
    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app="$deployment_name" -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$pod_name" ]; then
        print_error "No pods found for deployment '$deployment_name'"
        return 1
    fi

    # Check health endpoint
    if kubectl exec -n "$NAMESPACE" "$pod_name" -- curl -f http://localhost:$port/health &> /dev/null; then
        print_status "Deployment '$deployment_name' is healthy"
    else
        print_warning "Deployment '$deployment_name' health check failed"
        return 1
    fi
}

# Function to validate secrets are populated
validate_secrets() {
    print_status "Validating secrets are populated..."

    local secrets=(
        "vault-token-secret"
        "database-credentials-secret"
        "jwt-secrets-secret"
        "thermoworks-api-secret"
    )

    for secret in "${secrets[@]}"; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
            print_status "✓ Secret '$secret' exists"
        else
            print_warning "⚠ Secret '$secret' is missing"
        fi
    done
}

# Function to run deployment validation
validate_deployment() {
    print_status "Validating deployment..."

    # Check if services are running
    local services=(
        "encryption-service"
        "auth-service"
    )

    for service in "${services[@]}"; do
        if kubectl get deployment "$service" -n "$NAMESPACE" &> /dev/null; then
            wait_for_deployment "$service" 120
            check_deployment_health "$service"
        else
            print_warning "Service '$service' is not deployed"
        fi
    done

    # Validate secrets
    validate_secrets
}

# Function to display logs
show_logs() {
    local service_name="$1"
    local lines="${2:-50}"

    print_status "Showing logs for service '$service_name'..."

    kubectl logs -n "$NAMESPACE" -l app="$service_name" --tail="$lines"
}

# Function to display next steps
display_next_steps() {
    echo ""
    print_status "Deployment completed successfully!"
    echo ""
    print_status "Next steps:"
    echo "1. Verify that 1Password Connect is syncing secrets correctly"
    echo "2. Check that Vault is properly configured and accessible"
    echo "3. Run the Vault setup script to configure the Transit engine"
    echo "4. Test the encryption service endpoints"
    echo "5. Verify the auth service can connect to ThermoWorks API"
    echo ""
    print_status "Useful commands:"
    echo "# Check pod status"
    echo "kubectl get pods -n $NAMESPACE"
    echo ""
    echo "# Check service logs"
    echo "kubectl logs -n $NAMESPACE -l app=encryption-service"
    echo "kubectl logs -n $NAMESPACE -l app=auth-service"
    echo ""
    echo "# Test encryption service health"
    echo "kubectl port-forward -n $NAMESPACE svc/encryption-service 8082:8082"
    echo "curl http://localhost:8082/health"
    echo ""
    echo "# Test auth service health"
    echo "kubectl port-forward -n $NAMESPACE svc/auth-service 8083:8082"
    echo "curl http://localhost:8083/health"
}

# Function to cleanup deployment
cleanup() {
    print_status "Cleaning up deployment..."

    # Delete services
    kubectl delete -f "${KUSTOMIZE_DIR}/base/core-services/encryption-service.yaml" --ignore-not-found=true
    kubectl delete -f "${KUSTOMIZE_DIR}/base/core-services/auth-service.yaml" --ignore-not-found=true

    # Delete secrets
    kubectl delete -f "${KUSTOMIZE_DIR}/base/namespace/1password-secrets.yaml" --ignore-not-found=true

    print_status "Cleanup completed"
}

# Main deployment function
main() {
    print_status "Starting secure credential storage deployment..."

    # Check prerequisites
    check_kubectl
    check_kustomize
    check_cluster

    # Create namespace
    create_namespace

    # Check dependencies
    if ! check_1password_connect; then
        print_warning "1Password Connect is not available, continuing anyway..."
    fi

    if ! check_vault; then
        print_warning "Vault is not available, continuing anyway..."
    fi

    # Deploy components
    deploy_1password_secrets
    deploy_encryption_service
    deploy_auth_service

    # Validate deployment
    validate_deployment

    # Display next steps
    display_next_steps
}

# Handle command line arguments
case "${1:-}" in
    "cleanup")
        cleanup
        ;;
    "validate")
        validate_deployment
        ;;
    "logs")
        service_name="${2:-encryption-service}"
        show_logs "$service_name"
        ;;
    "health")
        service_name="${2:-encryption-service}"
        check_deployment_health "$service_name"
        ;;
    *)
        main
        ;;
esac
