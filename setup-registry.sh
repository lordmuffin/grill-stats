#!/bin/bash

# Setup local container registry for ThermoWorks BBQ monitoring application
# This script sets up a local Docker registry for development and testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY_NAME="grill-stats-registry"
REGISTRY_PORT="${REGISTRY_PORT:-5000}"
REGISTRY_VOLUME="registry-data"
REGISTRY_CONFIG_DIR="./registry-config"

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

# Function to check if Docker is running
check_docker() {
    if ! docker info &> /dev/null; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to create registry configuration
create_registry_config() {
    log "Creating registry configuration..."
    
    mkdir -p "${REGISTRY_CONFIG_DIR}"
    
    cat > "${REGISTRY_CONFIG_DIR}/config.yml" << EOF
version: 0.1
log:
  fields:
    service: registry
storage:
  cache:
    blobdescriptor: inmemory
  filesystem:
    rootdirectory: /var/lib/registry
  delete:
    enabled: true
http:
  addr: :5000
  headers:
    X-Content-Type-Options: [nosniff]
    Access-Control-Allow-Origin: ['*']
    Access-Control-Allow-Methods: ['HEAD', 'GET', 'OPTIONS', 'DELETE']
    Access-Control-Allow-Headers: ['Authorization', 'Accept', 'Cache-Control']
    Access-Control-Max-Age: [1728000]
    Access-Control-Allow-Credentials: [true]
    Access-Control-Expose-Headers: ['Docker-Content-Digest']
health:
  storagedriver:
    enabled: true
    interval: 10s
    threshold: 3
EOF
    
    log "Registry configuration created at ${REGISTRY_CONFIG_DIR}/config.yml"
}

# Function to start the registry
start_registry() {
    log "Starting Docker registry..."
    
    # Check if registry is already running
    if docker ps | grep -q "${REGISTRY_NAME}"; then
        warn "Registry ${REGISTRY_NAME} is already running"
        return 0
    fi
    
    # Remove existing stopped container
    if docker ps -a | grep -q "${REGISTRY_NAME}"; then
        log "Removing existing registry container..."
        docker rm -f "${REGISTRY_NAME}"
    fi
    
    # Create volume for registry data
    if ! docker volume ls | grep -q "${REGISTRY_VOLUME}"; then
        log "Creating registry volume..."
        docker volume create "${REGISTRY_VOLUME}"
    fi
    
    # Start the registry
    docker run -d \
        --name "${REGISTRY_NAME}" \
        --restart=always \
        -p "${REGISTRY_PORT}:5000" \
        -v "${REGISTRY_VOLUME}:/var/lib/registry" \
        -v "$(pwd)/${REGISTRY_CONFIG_DIR}/config.yml:/etc/docker/registry/config.yml" \
        registry:2
    
    # Wait for registry to be ready
    log "Waiting for registry to be ready..."
    for i in {1..30}; do
        if curl -sf "http://localhost:${REGISTRY_PORT}/v2/" > /dev/null 2>&1; then
            log "Registry is ready!"
            break
        fi
        sleep 1
    done
    
    if ! curl -sf "http://localhost:${REGISTRY_PORT}/v2/" > /dev/null 2>&1; then
        error "Registry failed to start properly"
        exit 1
    fi
}

# Function to stop the registry
stop_registry() {
    log "Stopping Docker registry..."
    
    if docker ps | grep -q "${REGISTRY_NAME}"; then
        docker stop "${REGISTRY_NAME}"
        docker rm "${REGISTRY_NAME}"
        log "Registry stopped and removed"
    else
        warn "Registry ${REGISTRY_NAME} is not running"
    fi
}

# Function to get registry status
get_registry_status() {
    log "Registry Status:"
    echo "================================================================"
    
    if docker ps | grep -q "${REGISTRY_NAME}"; then
        echo "Status: RUNNING"
        echo "Container: ${REGISTRY_NAME}"
        echo "Port: ${REGISTRY_PORT}"
        echo "URL: http://localhost:${REGISTRY_PORT}"
        echo "API: http://localhost:${REGISTRY_PORT}/v2/"
        
        # Get container info
        CONTAINER_ID=$(docker ps | grep "${REGISTRY_NAME}" | awk '{print $1}')
        UPTIME=$(docker ps --format "table {{.Status}}" | grep "${REGISTRY_NAME}" || echo "Unknown")
        
        echo "Container ID: ${CONTAINER_ID}"
        echo "Uptime: ${UPTIME}"
        
        # Check health
        if curl -sf "http://localhost:${REGISTRY_PORT}/v2/" > /dev/null 2>&1; then
            echo "Health: HEALTHY"
        else
            echo "Health: UNHEALTHY"
        fi
        
        # List stored images
        echo ""
        info "Stored Images:"
        
        # Get catalog
        CATALOG=$(curl -s "http://localhost:${REGISTRY_PORT}/v2/_catalog" | jq -r '.repositories[]?' 2>/dev/null)
        
        if [ -n "${CATALOG}" ]; then
            while read -r repo; do
                if [ -n "${repo}" ]; then
                    echo "  Repository: ${repo}"
                    # Get tags for this repo
                    TAGS=$(curl -s "http://localhost:${REGISTRY_PORT}/v2/${repo}/tags/list" | jq -r '.tags[]?' 2>/dev/null)
                    if [ -n "${TAGS}" ]; then
                        while read -r tag; do
                            if [ -n "${tag}" ]; then
                                echo "    - ${repo}:${tag}"
                            fi
                        done <<< "${TAGS}"
                    fi
                fi
            done <<< "${CATALOG}"
        else
            echo "  No images found"
        fi
    else
        echo "Status: STOPPED"
        echo "Container: ${REGISTRY_NAME} (not running)"
    fi
    
    echo "================================================================"
}

# Function to configure Docker daemon for insecure registry
configure_docker_daemon() {
    log "Configuring Docker daemon for insecure registry..."
    
    DOCKER_DAEMON_CONFIG="/etc/docker/daemon.json"
    REGISTRY_HOST="localhost:${REGISTRY_PORT}"
    
    if [ "$(uname)" = "Darwin" ]; then
        # macOS Docker Desktop
        warn "For macOS Docker Desktop, manually add ${REGISTRY_HOST} to insecure registries:"
        echo "  1. Open Docker Desktop preferences"
        echo "  2. Go to Docker Engine settings"
        echo "  3. Add to the configuration:"
        echo "     \"insecure-registries\": [\"${REGISTRY_HOST}\"]"
        echo "  4. Apply & Restart Docker"
    elif [ "$(uname)" = "Linux" ]; then
        # Linux Docker daemon
        info "Adding ${REGISTRY_HOST} to insecure registries..."
        
        # Create or update daemon.json
        if [ -f "${DOCKER_DAEMON_CONFIG}" ]; then
            # Backup existing config
            sudo cp "${DOCKER_DAEMON_CONFIG}" "${DOCKER_DAEMON_CONFIG}.backup"
            
            # Add insecure registry to existing config
            TEMP_CONFIG=$(mktemp)
            jq ". + {\"insecure-registries\": ([.\"insecure-registries\"[]?, \"${REGISTRY_HOST}\"] | unique)}" "${DOCKER_DAEMON_CONFIG}" > "${TEMP_CONFIG}"
            sudo mv "${TEMP_CONFIG}" "${DOCKER_DAEMON_CONFIG}"
        else
            # Create new config
            sudo mkdir -p /etc/docker
            echo "{\"insecure-registries\": [\"${REGISTRY_HOST}\"]}" | sudo tee "${DOCKER_DAEMON_CONFIG}"
        fi
        
        # Restart Docker daemon
        log "Restarting Docker daemon..."
        sudo systemctl restart docker
        
        # Wait for Docker to be ready
        for i in {1..30}; do
            if docker info &> /dev/null; then
                log "Docker daemon restarted successfully"
                break
            fi
            sleep 1
        done
    else
        warn "Unsupported operating system. Please manually configure Docker for insecure registry:"
        echo "  Add ${REGISTRY_HOST} to your Docker daemon's insecure-registries configuration"
    fi
}

# Function to test registry functionality
test_registry() {
    log "Testing registry functionality..."
    
    REGISTRY_HOST="localhost:${REGISTRY_PORT}"
    TEST_IMAGE="hello-world"
    TEST_TAG="${REGISTRY_HOST}/grill-stats/test:latest"
    
    # Pull a test image
    log "Pulling test image..."
    docker pull "${TEST_IMAGE}"
    
    # Tag and push to registry
    log "Tagging and pushing test image..."
    docker tag "${TEST_IMAGE}" "${TEST_TAG}"
    docker push "${TEST_TAG}"
    
    # Remove local image and pull from registry
    log "Testing pull from registry..."
    docker rmi "${TEST_TAG}"
    docker pull "${TEST_TAG}"
    
    # Clean up
    docker rmi "${TEST_TAG}"
    
    log "Registry test completed successfully!"
}

# Function to clean up registry
cleanup_registry() {
    log "Cleaning up registry..."
    
    # Stop and remove container
    if docker ps -a | grep -q "${REGISTRY_NAME}"; then
        docker stop "${REGISTRY_NAME}" 2>/dev/null || true
        docker rm "${REGISTRY_NAME}" 2>/dev/null || true
    fi
    
    # Remove volume
    if docker volume ls | grep -q "${REGISTRY_VOLUME}"; then
        docker volume rm "${REGISTRY_VOLUME}" 2>/dev/null || true
    fi
    
    # Remove config directory
    if [ -d "${REGISTRY_CONFIG_DIR}" ]; then
        rm -rf "${REGISTRY_CONFIG_DIR}"
    fi
    
    log "Registry cleanup completed"
}

# Help function
show_help() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Setup and manage local Docker registry for ThermoWorks BBQ monitoring application.

Commands:
    start           Start the registry (default)
    stop            Stop the registry
    status          Show registry status
    test            Test registry functionality
    cleanup         Remove registry and all data
    configure       Configure Docker daemon for insecure registry

Options:
    -h, --help      Show this help message
    -p, --port      Set registry port (default: 5000)

Environment Variables:
    REGISTRY_PORT   Registry port number

Examples:
    $0                      # Start registry with default settings
    $0 start -p 5001        # Start registry on port 5001
    $0 status               # Show registry status
    $0 test                 # Test registry functionality
    $0 cleanup              # Remove registry and data
    
Registry Information:
    URL: http://localhost:5000
    API: http://localhost:5000/v2/
    Health: http://localhost:5000/v2/
    Catalog: http://localhost:5000/v2/_catalog
EOF
}

# Parse command line arguments
COMMAND="start"

while [[ $# -gt 0 ]]; do
    case $1 in
        start|stop|status|test|cleanup|configure)
            COMMAND="$1"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--port)
            REGISTRY_PORT="$2"
            shift 2
            ;;
        *)
            error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if Docker is running
check_docker

# Execute command
case $COMMAND in
    start)
        create_registry_config
        start_registry
        info "Registry started successfully!"
        info "Registry URL: http://localhost:${REGISTRY_PORT}"
        info "API endpoint: http://localhost:${REGISTRY_PORT}/v2/"
        info "Use 'docker tag <image> localhost:${REGISTRY_PORT}/<name>:<tag>' to tag images"
        info "Use 'docker push localhost:${REGISTRY_PORT}/<name>:<tag>' to push images"
        ;;
    stop)
        stop_registry
        ;;
    status)
        get_registry_status
        ;;
    test)
        test_registry
        ;;
    cleanup)
        cleanup_registry
        ;;
    configure)
        configure_docker_daemon
        ;;
    *)
        error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac