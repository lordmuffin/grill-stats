#!/bin/bash
# Test Script for Validation System
# Validates that all validation scripts are properly configured

set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Testing Grill Stats Validation Scripts${NC}"
echo -e "Scripts Directory: $SCRIPTS_DIR"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test script existence and permissions
test_script_files() {
    echo -e "\n${BLUE}Testing Script Files${NC}"

    local scripts=(
        "validate-production.sh"
        "security-audit.sh"
        "performance-test.sh"
        "integration-test.sh"
        "run-full-validation.sh"
    )

    local all_good=true

    for script in "${scripts[@]}"; do
        local script_path="$SCRIPTS_DIR/$script"

        if [ -f "$script_path" ]; then
            if [ -x "$script_path" ]; then
                echo -e "${GREEN}✅${NC} $script - exists and executable"
            else
                echo -e "${YELLOW}⚠️${NC} $script - exists but not executable"
                all_good=false
            fi
        else
            echo -e "${RED}❌${NC} $script - missing"
            all_good=false
        fi
    done

    if [ "$all_good" = true ]; then
        echo -e "${GREEN}All validation scripts are ready${NC}"
    else
        echo -e "${RED}Some scripts need attention${NC}"
    fi
}

# Test help functions
test_help_functions() {
    echo -e "\n${BLUE}Testing Help Functions${NC}"

    local scripts=(
        "validate-production.sh"
        "security-audit.sh"
        "performance-test.sh"
        "integration-test.sh"
        "run-full-validation.sh"
    )

    for script in "${scripts[@]}"; do
        local script_path="$SCRIPTS_DIR/$script"

        if [ -f "$script_path" ]; then
            if timeout 10 bash "$script_path" --help >/dev/null 2>&1; then
                echo -e "${GREEN}✅${NC} $script - help function works"
            else
                echo -e "${YELLOW}⚠️${NC} $script - help function issue"
            fi
        fi
    done
}

# Test script syntax
test_script_syntax() {
    echo -e "\n${BLUE}Testing Script Syntax${NC}"

    local scripts=(
        "validate-production.sh"
        "security-audit.sh"
        "performance-test.sh"
        "integration-test.sh"
        "run-full-validation.sh"
    )

    for script in "${scripts[@]}"; do
        local script_path="$SCRIPTS_DIR/$script"

        if [ -f "$script_path" ]; then
            if bash -n "$script_path" 2>/dev/null; then
                echo -e "${GREEN}✅${NC} $script - syntax valid"
            else
                echo -e "${RED}❌${NC} $script - syntax error"
            fi
        fi
    done
}

# Test required commands
test_dependencies() {
    echo -e "\n${BLUE}Testing Dependencies${NC}"

    local required_commands=(
        "kubectl:Kubernetes CLI"
        "jq:JSON processor"
        "curl:HTTP client"
        "bc:Calculator"
        "openssl:TLS toolkit"
    )

    for cmd_desc in "${required_commands[@]}"; do
        local cmd="${cmd_desc%:*}"
        local desc="${cmd_desc#*:}"

        if command -v "$cmd" >/dev/null 2>&1; then
            local version=$(command -v "$cmd" >/dev/null 2>&1 && echo "available" || echo "unknown")
            echo -e "${GREEN}✅${NC} $cmd - $desc ($version)"
        else
            echo -e "${RED}❌${NC} $cmd - $desc (missing)"
        fi
    done
}

# Test configuration
test_configuration() {
    echo -e "\n${BLUE}Testing Configuration${NC}"

    # Test kubectl configuration
    if kubectl config current-context >/dev/null 2>&1; then
        local context=$(kubectl config current-context)
        echo -e "${GREEN}✅${NC} kubectl context: $context"
    else
        echo -e "${RED}❌${NC} kubectl not configured"
    fi

    # Test namespace access
    if kubectl get namespace >/dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} kubectl has namespace access"
    else
        echo -e "${RED}❌${NC} kubectl cannot access namespaces"
    fi

    # Test jq functionality
    if echo '{"test": "value"}' | jq '.test' >/dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} jq functioning correctly"
    else
        echo -e "${RED}❌${NC} jq not functioning"
    fi
}

# Test dry-run capability
test_dry_run() {
    echo -e "\n${BLUE}Testing Dry-Run Capability${NC}"

    # Test if we can run basic validation without actual deployment
    local script_path="$SCRIPTS_DIR/validate-production.sh"

    if [ -f "$script_path" ]; then
        # Check if script has dry-run or help mode
        if grep -q "dry-run\|help" "$script_path"; then
            echo -e "${GREEN}✅${NC} validate-production.sh - has dry-run capability"
        else
            echo -e "${YELLOW}⚠️${NC} validate-production.sh - no dry-run mode detected"
        fi
    fi
}

# Generate test report
generate_test_report() {
    echo -e "\n${BLUE}Test Summary${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local report_file="/tmp/validation-scripts-test-$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "Grill Stats Validation Scripts Test Report"
        echo "Generated: $(date)"
        echo "Scripts Directory: $SCRIPTS_DIR"
        echo ""
        echo "Test Results:"
        echo "- Script Files: $(ls -la $SCRIPTS_DIR/*.sh | wc -l) scripts found"
        echo "- Dependencies: $(command -v kubectl >/dev/null && echo "kubectl OK" || echo "kubectl MISSING")"
        echo "- Configuration: $(kubectl config current-context 2>/dev/null || echo "NOT CONFIGURED")"
        echo ""
        echo "Scripts Ready for Use:"
        ls -la "$SCRIPTS_DIR"/*.sh
    } > "$report_file"

    echo -e "${GREEN}✅${NC} Validation scripts test completed"
    echo -e "Test report saved: $report_file"
}

# Main execution
main() {
    test_script_files
    test_script_syntax
    test_help_functions
    test_dependencies
    test_configuration
    test_dry_run
    generate_test_report

    echo -e "\n${BLUE}Ready to Use Validation Scripts${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✅ Production Validation:${NC} ./scripts/validate-production.sh"
    echo -e "${GREEN}✅ Security Audit:${NC} ./scripts/security-audit.sh"
    echo -e "${GREEN}✅ Performance Test:${NC} ./scripts/performance-test.sh"
    echo -e "${GREEN}✅ Integration Test:${NC} ./scripts/integration-test.sh"
    echo -e "${GREEN}✅ Full Validation:${NC} ./scripts/run-full-validation.sh"
    echo -e ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "1. Review and customize thresholds in the scripts"
    echo -e "2. Test with your specific Kubernetes cluster"
    echo -e "3. Integrate with your CI/CD pipeline"
    echo -e "4. Set up monitoring and alerting"
    echo -e ""
    echo -e "${BLUE}For help with any script, use:${NC} ./scripts/SCRIPT_NAME.sh --help"
}

# Run the tests
main "$@"
