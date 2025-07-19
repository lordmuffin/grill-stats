#!/bin/bash

# Build and tag Docker images for all ThermoWorks BBQ monitoring microservices
# This script builds production-ready Docker images for Kubernetes deployment

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
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
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

# Function to build and tag a Docker image
build_service() {
    local service_name=$1
    local service_path=$2
    local image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service_name}"

    log "Building ${service_name} service..."

    # Check if Dockerfile exists
    if [ ! -f "${service_path}/Dockerfile" ]; then
        error "Dockerfile not found for ${service_name} at ${service_path}/Dockerfile"
        return 1
    fi

    # Build the image
    docker build \
        --build-arg BUILD_DATE="${BUILD_DATE}" \
        --build-arg GIT_COMMIT="${GIT_COMMIT}" \
        --build-arg VERSION="${VERSION}" \
        -t "${image_name}:latest" \
        -t "${image_name}:${VERSION}" \
        -t "${image_name}:${GIT_COMMIT}" \
        "${service_path}"

    if [ $? -eq 0 ]; then
        log "Successfully built ${service_name} image"
        info "Tagged as: ${image_name}:latest, ${image_name}:${VERSION}, ${image_name}:${GIT_COMMIT}"
    else
        error "Failed to build ${service_name} image"
        return 1
    fi
}

# Function to scan image for vulnerabilities (if trivy is available)
scan_image() {
    local image_name=$1

    if command -v trivy &> /dev/null; then
        log "Scanning ${image_name} for vulnerabilities..."
        trivy image --severity HIGH,CRITICAL "${image_name}:latest" || warn "Vulnerability scan failed for ${image_name}"
    else
        warn "Trivy not found. Skipping vulnerability scan for ${image_name}"
    fi
}

# Function to get image size
get_image_size() {
    local image_name=$1
    docker images "${image_name}:latest" --format "table {{.Size}}" | tail -n 1
}

# Main build process
main() {
    log "Starting Docker image build process for ThermoWorks BBQ monitoring application"
    info "Registry: ${REGISTRY_URL}"
    info "Project: ${PROJECT_NAME}"
    info "Version: ${VERSION}"
    info "Build Date: ${BUILD_DATE}"
    info "Git Commit: ${GIT_COMMIT}"

    # Array of services to build
    declare -A services=(
        ["auth-service"]="services/auth-service"
        ["device-service"]="services/device-service"
        ["temperature-service"]="services/temperature-service"
        ["historical-data-service"]="services/historical-data-service"
        ["encryption-service"]="services/encryption-service"
        ["web-ui"]="services/web-ui"
    )

    # Build summary
    declare -A build_results=()
    declare -A image_sizes=()

    # Build each service
    for service in "${!services[@]}"; do
        service_path="${services[$service]}"
        image_name="${REGISTRY_URL}/${PROJECT_NAME}/${service}"

        if build_service "${service}" "${service_path}"; then
            build_results["${service}"]="SUCCESS"
            image_sizes["${service}"]=$(get_image_size "${image_name}")

            # Optional: Scan for vulnerabilities
            if [ "${SCAN_IMAGES}" = "true" ]; then
                scan_image "${image_name}"
            fi
        else
            build_results["${service}"]="FAILED"
            error "Build failed for ${service}"
        fi

        echo ""
    done

    # Print build summary
    log "Build Summary:"
    echo "================================================================"
    printf "%-25s %-10s %-15s\n" "Service" "Status" "Size"
    echo "================================================================"

    for service in "${!services[@]}"; do
        status="${build_results[$service]}"
        size="${image_sizes[$service]:-N/A}"

        if [ "${status}" = "SUCCESS" ]; then
            printf "%-25s ${GREEN}%-10s${NC} %-15s\n" "${service}" "${status}" "${size}"
        else
            printf "%-25s ${RED}%-10s${NC} %-15s\n" "${service}" "${status}" "${size}"
        fi
    done

    echo "================================================================"

    # Count successful builds
    success_count=0
    total_count=${#services[@]}

    for service in "${!services[@]}"; do
        if [ "${build_results[$service]}" = "SUCCESS" ]; then
            ((success_count++))
        fi
    done

    if [ $success_count -eq $total_count ]; then
        log "All ${total_count} services built successfully!"
        info "Next steps:"
        echo "  1. Push images to registry: ./push-images.sh"
        echo "  2. Deploy to Kubernetes: kubectl apply -k kustomize/overlays/dev"
        echo "  3. Monitor deployment: kubectl get pods -n grill-stats -w"
    else
        error "Build completed with failures: ${success_count}/${total_count} services built successfully"
        exit 1
    fi
}

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Build Docker images for ThermoWorks BBQ monitoring microservices.

Options:
    -h, --help          Show this help message
    -r, --registry      Set registry URL (default: localhost:5000)
    -v, --version       Set version tag (default: from VERSION file)
    -s, --scan          Enable vulnerability scanning with Trivy
    --no-cache          Build without using cache

Environment Variables:
    REGISTRY_URL        Docker registry URL
    SCAN_IMAGES         Enable vulnerability scanning (true/false)

Examples:
    $0                              # Build with default settings
    $0 -r harbor.example.com        # Build with custom registry
    $0 -v 1.0.4 -s                 # Build with custom version and scanning
    SCAN_IMAGES=true $0             # Build with vulnerability scanning
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
        -s|--scan)
            SCAN_IMAGES="true"
            shift
            ;;
        --no-cache)
            DOCKER_BUILD_ARGS="${DOCKER_BUILD_ARGS} --no-cache"
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

# Run main build process
main
