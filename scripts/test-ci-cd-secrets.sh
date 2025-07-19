#!/bin/bash

# test-ci-cd-secrets.sh
# Test the CI/CD secret management implementation
# This script validates that the required secrets are properly configured

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQUIRED_TOOLS=("curl" "jq")

# Default values
GITEA_URL="${GITEA_URL:-http://localhost:3000}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
REPOSITORY="${REPOSITORY:-}"
VERBOSE=false

# Required secrets list
REQUIRED_SECRETS=(
  "DOCKER_AUTH"
  "SECRET_KEY"
  "THERMOWORKS_API_KEY"
  "HOMEASSISTANT_URL"
  "HOMEASSISTANT_TOKEN"
  "DB_HOST"
  "DB_PORT"
  "DB_NAME"
  "DB_USERNAME"
  "DB_PASSWORD"
  "DATABASE_URL"
)

# Optional secrets list
OPTIONAL_SECRETS=(
  "INFLUXDB_HOST"
  "INFLUXDB_PORT"
  "INFLUXDB_DATABASE"
  "INFLUXDB_USERNAME"
  "INFLUXDB_PASSWORD"
  "INFLUXDB_TOKEN"
  "REDIS_HOST"
  "REDIS_PORT"
  "REDIS_PASSWORD"
)

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
Usage: $0 [OPTIONS]

Test the CI/CD secret management implementation.

OPTIONS:
  -h, --help              Show this help message
  --gitea-url URL         Gitea server URL (default: http://localhost:3000)
  --gitea-token TOKEN     Gitea API token
  --repository REPO       Repository name (format: owner/repo)
  -v, --verbose           Enable verbose output

Examples:
  $0 --gitea-url https://gitea.example.com --gitea-token TOKEN --repository owner/repo
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

    # Check required parameters
    if [[ -z "$GITEA_TOKEN" ]]; then
        log_error "Gitea API token is required"
        log_info "Use --gitea-token to provide a token"
        exit 1
    fi

    if [[ -z "$REPOSITORY" ]]; then
        log_error "Repository name is required"
        log_info "Use --repository to provide a repository name (format: owner/repo)"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Validate if we can access Gitea API
validate_gitea_access() {
    log_info "Validating Gitea API access..."

    local response
    response=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" "${GITEA_URL}/api/v1/user")

    if echo "$response" | jq -e '.id' > /dev/null; then
        local username
        username=$(echo "$response" | jq -r '.username')
        log_success "Successfully authenticated as ${username}"
    else
        log_error "Failed to authenticate with Gitea API"
        log_error "Response: ${response}"
        exit 1
    fi
}

# Get list of secrets in repository
get_secrets() {
    log_info "Getting secrets for ${REPOSITORY}..."

    local response
    response=$(curl -s -X GET -H "Authorization: token ${GITEA_TOKEN}" \
        "${GITEA_URL}/api/v1/repos/${REPOSITORY}/secrets")

    if echo "$response" | jq -e 'length' > /dev/null; then
        echo "$response" | jq -r '.[] | .name'
    else
        log_error "Failed to get secrets"
        log_error "Response: ${response}"
        exit 1
    fi
}

# Validate required secrets
validate_required_secrets() {
    log_info "Validating required secrets..."

    local secrets
    local missing_secrets=()

    # Get existing secrets
    secrets=$(get_secrets)

    # Check required secrets
    for secret in "${REQUIRED_SECRETS[@]}"; do
        if ! echo "$secrets" | grep -q "^${secret}$"; then
            missing_secrets+=("$secret")
        else
            if [[ "$VERBOSE" == "true" ]]; then
                log_success "Found required secret: ${secret}"
            fi
        fi
    done

    # Report missing secrets
    if [[ ${#missing_secrets[@]} -gt 0 ]]; then
        log_error "Missing required secrets:"
        for secret in "${missing_secrets[@]}"; do
            log_error "- ${secret}"
        done
        return 1
    else
        log_success "All required secrets are configured"
        return 0
    fi
}

# Validate optional secrets
validate_optional_secrets() {
    log_info "Validating optional secrets..."

    local secrets
    local missing_secrets=()

    # Get existing secrets
    secrets=$(get_secrets)

    # Check optional secrets
    for secret in "${OPTIONAL_SECRETS[@]}"; do
        if ! echo "$secrets" | grep -q "^${secret}$"; then
            missing_secrets+=("$secret")
        else
            if [[ "$VERBOSE" == "true" ]]; then
                log_success "Found optional secret: ${secret}"
            fi
        fi
    done

    # Report missing secrets
    if [[ ${#missing_secrets[@]} -gt 0 ]]; then
        log_warning "Missing optional secrets:"
        for secret in "${missing_secrets[@]}"; do
            log_warning "- ${secret}"
        done
    else
        log_success "All optional secrets are configured"
    fi

    return 0
}

# Validate workflow files
validate_workflow_files() {
    log_info "Validating workflow files..."

    local error=0
    local workflow_dir="${ROOT_DIR}/.gitea/workflows"

    # Check if workflow directory exists
    if [[ ! -d "$workflow_dir" ]]; then
        log_error "Workflow directory not found: ${workflow_dir}"
        return 1
    fi

    # Check secure-build.yaml
    local secure_build="${workflow_dir}/secure-build.yaml"
    if [[ ! -f "$secure_build" ]]; then
        log_error "Secure build workflow not found: ${secure_build}"
        error=1
    else
        log_success "Found secure build workflow"

        # Check for secret usage
        local secret_count
        secret_count=$(grep -c 'secrets\.' "$secure_build" || true)

        if [[ $secret_count -eq 0 ]]; then
            log_error "No secrets used in secure build workflow"
            error=1
        else
            log_success "Found ${secret_count} secret references in secure build workflow"
        fi
    fi

    return $error
}

# Test Docker authentication
test_docker_auth() {
    log_info "Testing Docker Hub authentication..."

    local secrets
    secrets=$(get_secrets)

    # Check if Docker auth is configured
    if ! echo "$secrets" | grep -q "^DOCKER_AUTH$"; then
        log_error "DOCKER_AUTH secret not found"
        return 1
    fi

    log_success "Docker Hub authentication is configured"
    log_warning "Note: Cannot actually test Docker Hub authentication without the secret value"

    return 0
}

# Validate secret management documentation
validate_documentation() {
    log_info "Validating secret management documentation..."

    local error=0
    local docs_dir="${ROOT_DIR}/docs"

    # Check if docs directory exists
    if [[ ! -d "$docs_dir" ]]; then
        log_error "Documentation directory not found: ${docs_dir}"
        return 1
    fi

    # Check for secret management documentation
    local secret_docs="${docs_dir}/ci-cd-secret-management.md"
    if [[ ! -f "$secret_docs" ]]; then
        log_error "Secret management documentation not found: ${secret_docs}"
        error=1
    else
        log_success "Found secret management documentation"

        # Check if all required secrets are documented
        for secret in "${REQUIRED_SECRETS[@]}"; do
            if ! grep -q "$secret" "$secret_docs"; then
                log_error "Required secret not documented: ${secret}"
                error=1
            elif [[ "$VERBOSE" == "true" ]]; then
                log_success "Found documentation for required secret: ${secret}"
            fi
        done

        # Check if all optional secrets are documented
        for secret in "${OPTIONAL_SECRETS[@]}"; do
            if ! grep -q "$secret" "$secret_docs"; then
                log_warning "Optional secret not documented: ${secret}"
            elif [[ "$VERBOSE" == "true" ]]; then
                log_success "Found documentation for optional secret: ${secret}"
            fi
        done
    }

    return $error
}

# Validate the secret setup script
validate_setup_script() {
    log_info "Validating CI/CD secret setup script..."

    local setup_script="${ROOT_DIR}/scripts/setup-ci-cd-secrets.sh"

    # Check if setup script exists
    if [[ ! -f "$setup_script" ]]; then
        log_error "Secret setup script not found: ${setup_script}"
        return 1
    fi

    log_success "Found secret setup script"

    # Check if script is executable
    if [[ ! -x "$setup_script" ]]; then
        log_error "Secret setup script is not executable"
        log_info "Run: chmod +x ${setup_script}"
        return 1
    fi

    log_success "Secret setup script is executable"

    # Check if all required secrets are included in the script
    for secret in "${REQUIRED_SECRETS[@]}"; do
        if ! grep -q "$secret" "$setup_script"; then
            log_error "Required secret not included in setup script: ${secret}"
            return 1
        elif [[ "$VERBOSE" == "true" ]]; then
            log_success "Found required secret in setup script: ${secret}"
        fi
    done

    log_success "All required secrets are included in the setup script"

    return 0
}

# Run a comprehensive test
run_comprehensive_test() {
    log_info "Running comprehensive CI/CD secret management test..."

    local error=0

    # Validate Gitea access
    validate_gitea_access || error=1

    # Validate required secrets
    validate_required_secrets || error=1

    # Validate optional secrets
    validate_optional_secrets

    # Validate workflow files
    validate_workflow_files || error=1

    # Test Docker authentication
    test_docker_auth || error=1

    # Validate documentation
    validate_documentation || error=1

    # Validate setup script
    validate_setup_script || error=1

    # Print final result
    if [[ $error -eq 0 ]]; then
        log_success "CI/CD secret management test passed!"
        log_info "The secret management implementation is configured correctly."
    else
        log_error "CI/CD secret management test failed!"
        log_info "Please fix the issues reported above."
    fi

    return $error
}

# Main function
main() {
    log_info "Starting CI/CD secret management test"

    # Check prerequisites
    check_prerequisites

    # Run comprehensive test
    run_comprehensive_test

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "All tests completed successfully"
    else
        log_error "Some tests failed"
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
        --gitea-url)
            GITEA_URL="$2"
            shift 2
            ;;
        --gitea-token)
            GITEA_TOKEN="$2"
            shift 2
            ;;
        --repository)
            REPOSITORY="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Run main function
main

