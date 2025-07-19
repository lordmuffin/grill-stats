#!/bin/bash

# Push Docker images to container registry
# This script pushes all built ThermoWorks BBQ monitoring microservice images

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY_URL="${REGISTRY_URL:-localhost:5000}"
PROJECT_NAME="grill-stats"
VERSION=$(cat VERSION 2>/dev/null || echo "1.0.3")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Function to print colored output
log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')] INFO:${NC} $1"
}

# Function to push a Docker image
push_service() {
    local service_name=$1
    local image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service_name}"

    log "Pushing ${service_name} service images..."

    # Check if image exists locally
    if ! docker images "${image_name}:latest" --format "{{.Repository}}" | grep -q "${image_name}"; then
        error "Image ${image_name}:latest not found locally. Please build images first."
        return 1
    fi

    # Push all tags
    for tag in "latest" "${VERSION}" "${GIT_COMMIT}"; do
        info "Pushing ${image_name}:${tag}..."

        if docker push "${image_name}:${tag}"; then
            log "Successfully pushed ${image_name}:${tag}"
        else
            error "Failed to push ${image_name}:${tag}"
            return 1
        fi
    done

    return 0
}

# Function to verify registry connectivity
verify_registry() {
    local registry_url=$1

    log "Verifying registry connectivity to ${registry_url}..."

    # Try to connect to registry
    if curl -sf "${registry_url}/v2/" > /dev/null 2>&1; then
        log "Registry ${registry_url} is accessible"
        return 0
    else
        # If direct HTTP fails, try with docker login check
        if docker login "${registry_url}" --username=test --password=test > /dev/null 2>&1; then
            log "Registry ${registry_url} is accessible (authentication required)"
            return 0
        else
            warn "Unable to verify registry connectivity. Proceeding with push..."
            return 0
        fi
    fi
}

# Function to get image digest
get_image_digest() {
    local image_name=$1
    local tag=$2

    docker inspect "${image_name}:${tag}" --format='{{index .RepoDigests 0}}' 2>/dev/null || echo "N/A"
}

# Main push process
main() {
    log "Starting Docker image push process for ThermoWorks BBQ monitoring application"
    info "Registry: ${REGISTRY_URL}"
    info "Project: ${PROJECT_NAME}"
    info "Version: ${VERSION}"
    info "Git Commit: ${GIT_COMMIT}"

    # Verify registry connectivity
    verify_registry "${REGISTRY_URL}"

    # Array of services to push
    declare -A services=(
        ["auth-service"]="Authentication Service"
        ["device-service"]="Device Management Service"
        ["temperature-service"]="Temperature Data Service"
        ["historical-data-service"]="Historical Data Service"
        ["encryption-service"]="Encryption Service"
        ["web-ui"]="Web UI Service"
    )

    # Push summary
    declare -A push_results=()
    declare -A image_digests=()

    # Push each service
    for service in "${!services[@]}"; do
        service_description="${services[$service]}"
        image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service}"

        if push_service "${service}"; then
            push_results["${service}"]="SUCCESS"
            image_digests["${service}"]=$(get_image_digest "${image_name}" "latest")
        else
            push_results["${service}"]="FAILED"
            error "Push failed for ${service}"
        fi

        echo ""
    done

    # Print push summary
    log "Push Summary:"
    echo "================================================================"
    printf "%-25s %-10s %-20s\n" "Service" "Status" "Latest Digest"
    echo "================================================================"

    for service in "${!services[@]}"; do
        status="${push_results[$service]}"
        digest="${image_digests[$service]:-N/A}"
        # Truncate digest for display
        display_digest=$(echo "${digest}" | cut -c1-20)

        if [ "${status}" = "SUCCESS" ]; then
            printf "%-25s ${GREEN}%-10s${NC} %-20s\n" "${service}" "${status}" "${display_digest}"
        else
            printf "%-25s ${RED}%-10s${NC} %-20s\n" "${service}" "${status}" "${display_digest}"
        fi
    done

    echo "================================================================"

    # Count successful pushes
    success_count=0
    total_count=${#services[@]}

    for service in "${!services[@]}"; do
        if [ "${push_results[$service]}" = "SUCCESS" ]; then
            ((success_count++))
        fi
    done

    if [ $success_count -eq $total_count ]; then
        log "All ${total_count} services pushed successfully!"
        info "Container images are now available at:"

        for service in "${!services[@]}"; do
            image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service}"
            echo "  - ${image_name}:latest"
            echo "  - ${image_name}:${VERSION}"
            echo "  - ${image_name}:${GIT_COMMIT}"
        done

        echo ""
        info "Next steps:"
        echo "  1. Update Kubernetes manifests with new image tags"
        echo "  2. Deploy to Kubernetes: kubectl apply -k kustomize/overlays/dev"
        echo "  3. Monitor deployment: kubectl get pods -n grill-stats -w"
        echo "  4. Verify services: kubectl get svc -n grill-stats"
    else
        error "Push completed with failures: ${success_count}/${total_count} services pushed successfully"
        exit 1
    fi
}

# Function to list available images
list_images() {
    log "Available images in registry ${REGISTRY_URL}:"

    for service in "auth-service" "device-service" "temperature-service" "historical-data-service" "encryption-service" "web-ui"; do
        image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service}"
        echo ""
        info "Service: ${service}"
        docker images "${image_name}" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | head -n 4
    done
}

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Push Docker images for ThermoWorks BBQ monitoring microservices to container registry.

Options:
    -h, --help          Show this help message
    -r, --registry      Set registry URL (default: localhost:5000)
    -v, --version       Set version tag (default: from VERSION file)
    -l, --list          List available images without pushing
    -f, --force         Force push (overwrite existing images)

Environment Variables:
    REGISTRY_URL        Docker registry URL
    DOCKER_USERNAME     Registry username (if authentication required)
    DOCKER_PASSWORD     Registry password (if authentication required)

Examples:
    $0                              # Push with default settings
    $0 -r harbor.example.com        # Push to custom registry
    $0 -v 1.0.4                     # Push with custom version
    $0 -l                           # List available images
    $0 -f                           # Force push (overwrite existing)

Authentication:
    # If registry requires authentication, login first:
    docker login ${REGISTRY_URL}

    # Or use environment variables:
    export DOCKER_USERNAME=myuser
    export DOCKER_PASSWORD=mypass
    $0
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--registry)
            REGISTRY_URL="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -l|--list)
            list_images
            exit 0
            ;;
        -f|--force)
            FORCE_PUSH="true"
            shift
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info &> /dev/null; then
    error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if we're in the correct directory
if [ ! -f "VERSION" ] || [ ! -d "services" ]; then
    error "Please run this script from the root of the grill-stats repository."
    exit 1
fi

# Authenticate with registry if credentials are provided
if [ -n "${DOCKER_USERNAME}" ] && [ -n "${DOCKER_PASSWORD}" ]; then
    log "Authenticating with registry ${REGISTRY_URL}..."
    echo "${DOCKER_PASSWORD}" | docker login "${REGISTRY_URL}" -u "${DOCKER_USERNAME}" --password-stdin
fi

# Run main push process
main
