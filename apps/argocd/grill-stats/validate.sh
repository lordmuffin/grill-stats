#!/bin/bash

# Grill-Stats ArgoCD Configuration Validation Script
# This script validates all ArgoCD configurations for the grill-stats platform

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMP_DIR="/tmp/grill-stats-validation"
EXIT_CODE=0

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
    EXIT_CODE=1
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Validate grill-stats ArgoCD configurations

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -f, --fix               Attempt to fix common issues
    --yaml-only             Only validate YAML syntax
    --k8s-only              Only validate Kubernetes resources
    --argocd-only           Only validate ArgoCD applications

EXAMPLES:
    $0                      Run all validations
    $0 --verbose            Run with detailed output
    $0 --yaml-only          Only check YAML syntax
    $0 --fix                Fix common issues

EOF
}

# Parse command line arguments
VERBOSE=false
FIX=false
YAML_ONLY=false
K8S_ONLY=false
ARGOCD_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--fix)
            FIX=true
            shift
            ;;
        --yaml-only)
            YAML_ONLY=true
            shift
            ;;
        --k8s-only)
            K8S_ONLY=true
            shift
            ;;
        --argocd-only)
            ARGOCD_ONLY=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Create temporary directory
mkdir -p "${TEMP_DIR}"

# Cleanup function
cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# Check if tools are available
check_tools() {
    log_info "Checking required tools..."

    local tools=("kubectl" "yq")
    local missing_tools=()

    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install missing tools and try again"
        exit 1
    fi

    log_success "Required tools are available"
}

# Validate YAML syntax
validate_yaml_syntax() {
    log_info "Validating YAML syntax..."

    local yaml_files
    yaml_files=$(find "${SCRIPT_DIR}" -name "*.yaml" -o -name "*.yml")

    local failed_files=()

    for file in $yaml_files; do
        if [[ "${VERBOSE}" == "true" ]]; then
            log_info "Checking $(basename "$file")"
        fi

        if ! yq eval '.' "$file" > /dev/null 2>&1; then
            log_error "Invalid YAML syntax in $(basename "$file")"
            failed_files+=("$(basename "$file")")
        fi
    done

    if [[ ${#failed_files[@]} -eq 0 ]]; then
        log_success "All YAML files have valid syntax"
    else
        log_error "YAML syntax validation failed for: ${failed_files[*]}"
    fi
}

# Validate Kubernetes resources
validate_k8s_resources() {
    log_info "Validating Kubernetes resources..."

    # Check if kubectl is connected
    if ! kubectl cluster-info &> /dev/null; then
        log_warning "Not connected to Kubernetes cluster, skipping K8s resource validation"
        return 0
    fi

    # Validate base resources
    log_info "Validating base resources..."
    if ! kubectl apply --dry-run=client -f "${SCRIPT_DIR}/base/" &> "${TEMP_DIR}/base-validation.log"; then
        log_error "Base resources validation failed"
        if [[ "${VERBOSE}" == "true" ]]; then
            cat "${TEMP_DIR}/base-validation.log"
        fi
    else
        log_success "Base resources are valid"
    fi

    # Validate environment overlays
    for env in prod-lab dev-lab; do
        if [[ -d "${SCRIPT_DIR}/overlays/${env}" ]]; then
            log_info "Validating ${env} overlay..."
            if ! kubectl apply --dry-run=client -k "${SCRIPT_DIR}/overlays/${env}" &> "${TEMP_DIR}/${env}-validation.log"; then
                log_error "${env} overlay validation failed"
                if [[ "${VERBOSE}" == "true" ]]; then
                    cat "${TEMP_DIR}/${env}-validation.log"
                fi
            else
                log_success "${env} overlay is valid"
            fi
        fi
    done
}

# Validate ArgoCD applications
validate_argocd_applications() {
    log_info "Validating ArgoCD application configurations..."

    # Check for required fields in ArgoCD applications
    local app_files
    app_files=$(find "${SCRIPT_DIR}/base" -name "*.yaml" -exec grep -l "kind: Application" {} \;)

    for file in $app_files; do
        local app_name
        app_name=$(basename "$file" .yaml)

        if [[ "${VERBOSE}" == "true" ]]; then
            log_info "Validating ArgoCD application: $app_name"
        fi

        # Check required fields
        local required_fields=(
            ".metadata.name"
            ".metadata.namespace"
            ".spec.project"
            ".spec.source.repoURL"
            ".spec.source.path"
            ".spec.destination.server"
            ".spec.destination.namespace"
        )

        for field in "${required_fields[@]}"; do
            if ! yq eval "$field" "$file" > /dev/null 2>&1; then
                log_error "Missing required field '$field' in $app_name"
            fi
        done

        # Check for common issues
        validate_application_specific "$file"
    done
}

# Validate application-specific configurations
validate_application_specific() {
    local file="$1"
    local app_name
    app_name=$(yq eval '.metadata.name' "$file")

    # Check sync policy
    if yq eval '.spec.syncPolicy.automated.prune' "$file" | grep -q "true"; then
        if [[ "$app_name" == *"database"* ]] || [[ "$app_name" == *"secret"* ]]; then
            log_warning "Pruning enabled for $app_name - consider disabling for safety"
        fi
    fi

    # Check for finalizers
    if ! yq eval '.metadata.finalizers' "$file" | grep -q "resources-finalizer.argocd.argoproj.io"; then
        log_warning "Missing finalizer in $app_name - resources may not be cleaned up properly"
    fi

    # Check sync waves
    if ! yq eval '.metadata.annotations."argocd.argoproj.io/sync-wave"' "$file" > /dev/null 2>&1; then
        log_warning "Missing sync wave annotation in $app_name - may cause deployment ordering issues"
    fi

    # Check health checks
    if [[ "$app_name" == *"database"* ]]; then
        if ! yq eval '.spec.health' "$file" > /dev/null 2>&1; then
            log_warning "Missing health check configuration in $app_name"
        fi
    fi
}

# Validate kustomization files
validate_kustomization() {
    log_info "Validating kustomization files..."

    local kustomization_files
    kustomization_files=$(find "${SCRIPT_DIR}" -name "kustomization.yaml")

    for file in $kustomization_files; do
        if [[ "${VERBOSE}" == "true" ]]; then
            log_info "Validating $(realpath --relative-to="${SCRIPT_DIR}" "$file")"
        fi

        # Check if all referenced resources exist
        local resources
        resources=$(yq eval '.resources[]' "$file" 2>/dev/null || echo "")

        if [[ -n "$resources" ]]; then
            while IFS= read -r resource; do
                if [[ "$resource" == ../* ]]; then
                    # Relative path
                    local resource_path
                    resource_path=$(dirname "$file")/"$resource"
                    if [[ ! -e "$resource_path" ]]; then
                        log_error "Referenced resource not found: $resource (from $(basename "$file"))"
                    fi
                elif [[ "$resource" == *".yaml" ]]; then
                    # File in same directory
                    local resource_file
                    resource_file=$(dirname "$file")/"$resource"
                    if [[ ! -f "$resource_file" ]]; then
                        log_error "Referenced resource file not found: $resource (from $(basename "$file"))"
                    fi
                fi
            done <<< "$resources"
        fi

        # Check for common kustomization issues
        validate_kustomization_specific "$file"
    done
}

# Validate kustomization-specific configurations
validate_kustomization_specific() {
    local file="$1"

    # Check for proper namespace handling
    if yq eval '.namespace' "$file" > /dev/null 2>&1; then
        local namespace
        namespace=$(yq eval '.namespace' "$file")
        if [[ "$namespace" != "argocd" ]] && [[ "$namespace" != "grill-stats"* ]]; then
            log_warning "Unexpected namespace '$namespace' in $(basename "$file")"
        fi
    fi

    # Check for common labels
    if ! yq eval '.commonLabels."app.kubernetes.io/name"' "$file" > /dev/null 2>&1; then
        log_warning "Missing common label app.kubernetes.io/name in $(basename "$file")"
    fi

    # Check for patches
    local patches
    patches=$(yq eval '.patchesStrategicMerge[]' "$file" 2>/dev/null || echo "")
    if [[ -n "$patches" ]]; then
        while IFS= read -r patch; do
            local patch_file
            patch_file=$(dirname "$file")/"$patch"
            if [[ ! -f "$patch_file" ]]; then
                log_error "Patch file not found: $patch (from $(basename "$file"))"
            fi
        done <<< "$patches"
    fi
}

# Check for security best practices
validate_security() {
    log_info "Validating security configurations..."

    # Check for hardcoded secrets
    local yaml_files
    yaml_files=$(find "${SCRIPT_DIR}" -name "*.yaml" -o -name "*.yml")

    for file in $yaml_files; do
        if grep -i "password\|secret\|token\|key" "$file" | grep -v "1Password\|OnePassword\|secretRef\|secretKeyRef"; then
            log_warning "Potential hardcoded secret in $(basename "$file")"
        fi
    done

    # Check for proper RBAC
    if ! grep -r "rbac.authorization.k8s.io" "${SCRIPT_DIR}" > /dev/null; then
        log_warning "No RBAC configurations found - consider implementing proper access controls"
    fi

    # Check for network policies
    if ! grep -r "kind: NetworkPolicy" "${SCRIPT_DIR}" > /dev/null; then
        log_warning "No NetworkPolicy configurations found - consider implementing network segmentation"
    fi
}

# Fix common issues
fix_common_issues() {
    log_info "Attempting to fix common issues..."

    # Fix missing finalizers
    local app_files
    app_files=$(find "${SCRIPT_DIR}/base" -name "*.yaml" -exec grep -l "kind: Application" {} \;)

    for file in $app_files; do
        if ! yq eval '.metadata.finalizers' "$file" | grep -q "resources-finalizer.argocd.argoproj.io"; then
            log_info "Adding finalizer to $(basename "$file")"
            yq eval '.metadata.finalizers += ["resources-finalizer.argocd.argoproj.io"]' -i "$file"
        fi
    done

    # Fix missing sync waves
    local sync_wave_map=(
        "grill-stats-project.yaml:0"
        "grill-stats-secrets.yaml:0"
        "grill-stats-databases.yaml:1"
        "grill-stats-vault.yaml:2"
        "grill-stats-core-services.yaml:3"
        "grill-stats-ingress.yaml:4"
        "grill-stats-monitoring.yaml:5"
    )

    for mapping in "${sync_wave_map[@]}"; do
        local file_name="${mapping%:*}"
        local wave="${mapping#*:}"
        local file_path="${SCRIPT_DIR}/base/${file_name}"

        if [[ -f "$file_path" ]]; then
            if ! yq eval '.metadata.annotations."argocd.argoproj.io/sync-wave"' "$file_path" > /dev/null 2>&1; then
                log_info "Adding sync wave $wave to $file_name"
                yq eval '.metadata.annotations."argocd.argoproj.io/sync-wave" = "'$wave'"' -i "$file_path"
            fi
        fi
    done

    log_success "Common issues have been fixed"
}

# Generate validation report
generate_report() {
    log_info "Generating validation report..."

    local report_file="${TEMP_DIR}/validation-report.md"

    cat > "$report_file" << EOF
# Grill-Stats ArgoCD Validation Report

Generated: $(date)

## Summary

- **Total Files**: $(find "${SCRIPT_DIR}" -name "*.yaml" -o -name "*.yml" | wc -l)
- **Applications**: $(find "${SCRIPT_DIR}/base" -name "*.yaml" -exec grep -l "kind: Application" {} \; | wc -l)
- **Kustomizations**: $(find "${SCRIPT_DIR}" -name "kustomization.yaml" | wc -l)
- **Overlays**: $(find "${SCRIPT_DIR}/overlays" -maxdepth 1 -type d | tail -n +2 | wc -l)

## Validation Results

EOF

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo "✅ All validations passed successfully" >> "$report_file"
    else
        echo "❌ Some validations failed - check logs for details" >> "$report_file"
    fi

    echo "" >> "$report_file"
    echo "## Files Validated" >> "$report_file"
    echo "" >> "$report_file"

    find "${SCRIPT_DIR}" -name "*.yaml" -o -name "*.yml" | sort | while read -r file; do
        echo "- $(realpath --relative-to="${SCRIPT_DIR}" "$file")" >> "$report_file"
    done

    log_success "Validation report generated: $report_file"

    if [[ "${VERBOSE}" == "true" ]]; then
        cat "$report_file"
    fi
}

# Main validation function
main() {
    log_info "Grill-Stats ArgoCD Configuration Validation"
    log_info "Script directory: ${SCRIPT_DIR}"

    # Check tools
    check_tools

    # Run validations based on options
    if [[ "${YAML_ONLY}" == "true" ]]; then
        validate_yaml_syntax
    elif [[ "${K8S_ONLY}" == "true" ]]; then
        validate_k8s_resources
    elif [[ "${ARGOCD_ONLY}" == "true" ]]; then
        validate_argocd_applications
    else
        # Run all validations
        validate_yaml_syntax
        validate_k8s_resources
        validate_argocd_applications
        validate_kustomization
        validate_security
    fi

    # Fix issues if requested
    if [[ "${FIX}" == "true" ]]; then
        fix_common_issues
    fi

    # Generate report
    generate_report

    # Final status
    if [[ $EXIT_CODE -eq 0 ]]; then
        log_success "All validations completed successfully!"
    else
        log_error "Some validations failed. Check the logs above for details."
    fi

    exit $EXIT_CODE
}

# Execute main function
main "$@"
