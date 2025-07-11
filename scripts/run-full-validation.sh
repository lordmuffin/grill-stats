#!/bin/bash
# Full Production Validation Suite for Grill Stats Platform
# Orchestrates all validation scripts and generates comprehensive report

set -e

NAMESPACE="grill-stats"
CLUSTER_CONTEXT="prod-lab"
VALIDATION_DIR="/tmp/grill-stats-full-validation-$(date +%Y%m%d_%H%M%S)"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Validation tracking
declare -A VALIDATION_RESULTS
declare -A VALIDATION_TIMES
declare -A VALIDATION_SCORES
TOTAL_VALIDATIONS=0
PASSED_VALIDATIONS=0
FAILED_VALIDATIONS=0
CONDITIONAL_VALIDATIONS=0

# Configuration
SKIP_PERFORMANCE=${SKIP_PERFORMANCE:-false}
SKIP_SECURITY=${SKIP_SECURITY:-false}
SKIP_INTEGRATION=${SKIP_INTEGRATION:-false}
PARALLEL_EXECUTION=${PARALLEL_EXECUTION:-false}
GENERATE_REPORT=${GENERATE_REPORT:-true}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$VALIDATION_DIR/full-validation.log"
}

validation_result() {
    local name=$1
    local result=$2
    local duration=$3
    local score=$4
    local details=${5:-""}
    
    TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
    VALIDATION_RESULTS[$name]=$result
    VALIDATION_TIMES[$name]=$duration
    VALIDATION_SCORES[$name]=$score
    
    case $result in
        "PASS")
            echo -e "${GREEN}✅ PASS${NC} - $name (${duration}s) [Score: $score/100]"
            PASSED_VALIDATIONS=$((PASSED_VALIDATIONS + 1))
            ;;
        "FAIL")
            echo -e "${RED}❌ FAIL${NC} - $name (${duration}s) [Score: $score/100]"
            FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
            ;;
        "CONDITIONAL")
            echo -e "${YELLOW}⚠️  CONDITIONAL${NC} - $name (${duration}s) [Score: $score/100]"
            CONDITIONAL_VALIDATIONS=$((CONDITIONAL_VALIDATIONS + 1))
            ;;
        "SKIP")
            echo -e "${CYAN}⏭️  SKIP${NC} - $name"
            ;;
    esac
    
    if [ -n "$details" ]; then
        echo -e "  ${PURPLE}Details:${NC} $details"
    fi
    
    log "$result - $name ($duration s) [Score: $score/100]: $details"
}

setup_validation_environment() {
    echo -e "${BLUE}Setting up full validation environment...${NC}"
    mkdir -p "$VALIDATION_DIR"
    
    # Create subdirectories for each validation type
    mkdir -p "$VALIDATION_DIR/production"
    mkdir -p "$VALIDATION_DIR/security"
    mkdir -p "$VALIDATION_DIR/performance"
    mkdir -p "$VALIDATION_DIR/integration"
    mkdir -p "$VALIDATION_DIR/reports"
    
    # Verify cluster connectivity
    if ! kubectl cluster-info --context=$CLUSTER_CONTEXT >/dev/null 2>&1; then
        echo -e "${RED}ERROR: Cannot connect to cluster $CLUSTER_CONTEXT${NC}"
        exit 1
    fi
    
    # Verify namespace exists
    if ! kubectl get namespace $NAMESPACE --context=$CLUSTER_CONTEXT >/dev/null 2>&1; then
        echo -e "${RED}ERROR: Namespace $NAMESPACE not found${NC}"
        exit 1
    fi
    
    log "Validation environment setup complete"
}

# Production deployment validation
run_production_validation() {
    echo -e "\n${BLUE}=== Production Deployment Validation ===${NC}"
    
    local start_time=$(date +%s)
    local script_path="$SCRIPTS_DIR/validate-production.sh"
    
    if [ ! -f "$script_path" ]; then
        validation_result "PRODUCTION_VALIDATION" "FAIL" "0" "0" "Validation script not found"
        return 1
    fi
    
    # Make script executable
    chmod +x "$script_path"
    
    # Run production validation
    local output_file="$VALIDATION_DIR/production/production-validation.log"
    local json_file="$VALIDATION_DIR/production/production-results.json"
    
    if bash "$script_path" --context=$CLUSTER_CONTEXT -n $NAMESPACE > "$output_file" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Parse results
        local success_rate=$(grep "Success Rate:" "$output_file" | awk '{print $3}' | tr -d '%' || echo "0")
        local total_checks=$(grep "Total Checks:" "$output_file" | awk '{print $3}' || echo "0")
        local failed_checks=$(grep "Failed:" "$output_file" | awk '{print $2}' || echo "0")
        
        # Copy JSON results if available
        if [ -f "/tmp/grill-stats-results-"*".json" ]; then
            cp "/tmp/grill-stats-results-"*".json" "$json_file" 2>/dev/null || true
        fi
        
        if [ "$failed_checks" -eq 0 ]; then
            validation_result "PRODUCTION_VALIDATION" "PASS" "$duration" "$success_rate" "$total_checks checks completed"
        elif [ "$success_rate" -ge 90 ]; then
            validation_result "PRODUCTION_VALIDATION" "CONDITIONAL" "$duration" "$success_rate" "$failed_checks failures out of $total_checks checks"
        else
            validation_result "PRODUCTION_VALIDATION" "FAIL" "$duration" "$success_rate" "$failed_checks failures out of $total_checks checks"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        validation_result "PRODUCTION_VALIDATION" "FAIL" "$duration" "0" "Validation script failed"
    fi
}

# Security audit
run_security_audit() {
    echo -e "\n${BLUE}=== Security Audit ===${NC}"
    
    if [ "$SKIP_SECURITY" = true ]; then
        validation_result "SECURITY_AUDIT" "SKIP" "0" "0" "Security audit skipped"
        return 0
    fi
    
    local start_time=$(date +%s)
    local script_path="$SCRIPTS_DIR/security-audit.sh"
    
    if [ ! -f "$script_path" ]; then
        validation_result "SECURITY_AUDIT" "FAIL" "0" "0" "Security audit script not found"
        return 1
    fi
    
    # Make script executable
    chmod +x "$script_path"
    
    # Run security audit
    local output_file="$VALIDATION_DIR/security/security-audit.log"
    local audit_dir="$VALIDATION_DIR/security/audit-results"
    
    if bash "$script_path" --context=$CLUSTER_CONTEXT -n $NAMESPACE -o "$audit_dir" > "$output_file" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Parse security results
        local total_findings=$(grep "Total Findings:" "$output_file" | awk '{print $3}' || echo "0")
        local critical_findings=$(grep "Critical:" "$output_file" | awk '{print $2}' || echo "0")
        local high_findings=$(grep "High:" "$output_file" | awk '{print $2}' || echo "0")
        local risk_score=$(grep "Risk Score:" "$output_file" | awk '{print $3}' || echo "0")
        
        # Calculate security score (inverse of risk score, normalized)
        local security_score=$((100 - (risk_score > 100 ? 100 : risk_score)))
        
        if [ "$critical_findings" -eq 0 ] && [ "$high_findings" -eq 0 ]; then
            validation_result "SECURITY_AUDIT" "PASS" "$duration" "$security_score" "$total_findings findings, no critical/high"
        elif [ "$critical_findings" -eq 0 ] && [ "$high_findings" -le 2 ]; then
            validation_result "SECURITY_AUDIT" "CONDITIONAL" "$duration" "$security_score" "$high_findings high findings"
        else
            validation_result "SECURITY_AUDIT" "FAIL" "$duration" "$security_score" "$critical_findings critical, $high_findings high findings"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        validation_result "SECURITY_AUDIT" "FAIL" "$duration" "0" "Security audit failed"
    fi
}

# Performance testing
run_performance_test() {
    echo -e "\n${BLUE}=== Performance Testing ===${NC}"
    
    if [ "$SKIP_PERFORMANCE" = true ]; then
        validation_result "PERFORMANCE_TEST" "SKIP" "0" "0" "Performance testing skipped"
        return 0
    fi
    
    local start_time=$(date +%s)
    local script_path="$SCRIPTS_DIR/performance-test.sh"
    
    if [ ! -f "$script_path" ]; then
        validation_result "PERFORMANCE_TEST" "FAIL" "0" "0" "Performance test script not found"
        return 1
    fi
    
    # Make script executable
    chmod +x "$script_path"
    
    # Run performance test
    local output_file="$VALIDATION_DIR/performance/performance-test.log"
    
    if bash "$script_path" --context=$CLUSTER_CONTEXT -n $NAMESPACE -d 180 -c 5 > "$output_file" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Parse performance results
        local cpu_threshold=$(grep "CPU usage within limits" "$output_file" && echo "PASS" || echo "FAIL")
        local response_threshold=$(grep "Response time within limits" "$output_file" && echo "PASS" || echo "FAIL")
        local error_threshold=$(grep "Error rate within limits" "$output_file" && echo "PASS" || echo "FAIL")
        
        # Calculate performance score
        local performance_score=0
        [ "$cpu_threshold" = "PASS" ] && performance_score=$((performance_score + 33))
        [ "$response_threshold" = "PASS" ] && performance_score=$((performance_score + 33))
        [ "$error_threshold" = "PASS" ] && performance_score=$((performance_score + 34))
        
        if [ "$cpu_threshold" = "PASS" ] && [ "$response_threshold" = "PASS" ] && [ "$error_threshold" = "PASS" ]; then
            validation_result "PERFORMANCE_TEST" "PASS" "$duration" "$performance_score" "All performance thresholds met"
        elif [ "$performance_score" -ge 67 ]; then
            validation_result "PERFORMANCE_TEST" "CONDITIONAL" "$duration" "$performance_score" "Some performance thresholds exceeded"
        else
            validation_result "PERFORMANCE_TEST" "FAIL" "$duration" "$performance_score" "Multiple performance thresholds exceeded"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        validation_result "PERFORMANCE_TEST" "FAIL" "$duration" "0" "Performance test failed"
    fi
}

# Integration testing
run_integration_test() {
    echo -e "\n${BLUE}=== Integration Testing ===${NC}"
    
    if [ "$SKIP_INTEGRATION" = true ]; then
        validation_result "INTEGRATION_TEST" "SKIP" "0" "0" "Integration testing skipped"
        return 0
    fi
    
    local start_time=$(date +%s)
    local script_path="$SCRIPTS_DIR/integration-test.sh"
    
    if [ ! -f "$script_path" ]; then
        validation_result "INTEGRATION_TEST" "FAIL" "0" "0" "Integration test script not found"
        return 1
    fi
    
    # Make script executable
    chmod +x "$script_path"
    
    # Run integration test
    local output_file="$VALIDATION_DIR/integration/integration-test.log"
    
    if bash "$script_path" --context=$CLUSTER_CONTEXT -n $NAMESPACE -t 300 > "$output_file" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Parse integration results
        local pass_rate=$(grep "Pass Rate:" "$output_file" | awk '{print $3}' | tr -d '%' || echo "0")
        local total_tests=$(grep "Total Tests:" "$output_file" | awk '{print $3}' || echo "0")
        local failed_tests=$(grep "Failed:" "$output_file" | awk '{print $2}' || echo "0")
        
        if [ "$failed_tests" -eq 0 ]; then
            validation_result "INTEGRATION_TEST" "PASS" "$duration" "$pass_rate" "$total_tests tests passed"
        elif [ "$pass_rate" -ge 90 ]; then
            validation_result "INTEGRATION_TEST" "CONDITIONAL" "$duration" "$pass_rate" "$failed_tests failures out of $total_tests tests"
        else
            validation_result "INTEGRATION_TEST" "FAIL" "$duration" "$pass_rate" "$failed_tests failures out of $total_tests tests"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        validation_result "INTEGRATION_TEST" "FAIL" "$duration" "0" "Integration test failed"
    fi
}

# Additional validation checks
run_additional_checks() {
    echo -e "\n${BLUE}=== Additional Validation Checks ===${NC}"
    
    # ArgoCD Application Health
    check_argocd_health
    
    # Backup System Status
    check_backup_status
    
    # Monitoring System Health
    check_monitoring_health
    
    # External Dependencies
    check_external_dependencies
}

check_argocd_health() {
    local start_time=$(date +%s)
    
    # Check if ArgoCD applications are healthy
    local argocd_apps=$(kubectl get application -n argocd --context=$CLUSTER_CONTEXT -o json 2>/dev/null | jq '[.items[] | select(.metadata.name | contains("grill-stats"))]' || echo "[]")
    local app_count=$(echo "$argocd_apps" | jq 'length')
    
    if [ "$app_count" -gt 0 ]; then
        local healthy_apps=$(echo "$argocd_apps" | jq '[.[] | select(.status.health.status=="Healthy")] | length')
        local synced_apps=$(echo "$argocd_apps" | jq '[.[] | select(.status.sync.status=="Synced")] | length')
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        if [ "$healthy_apps" -eq "$app_count" ] && [ "$synced_apps" -eq "$app_count" ]; then
            validation_result "ARGOCD_HEALTH" "PASS" "$duration" "100" "$app_count apps healthy and synced"
        else
            validation_result "ARGOCD_HEALTH" "FAIL" "$duration" "50" "$healthy_apps/$app_count healthy, $synced_apps/$app_count synced"
        fi
    else
        validation_result "ARGOCD_HEALTH" "SKIP" "0" "0" "No ArgoCD applications found"
    fi
}

check_backup_status() {
    local start_time=$(date +%s)
    
    # Check backup CronJobs
    local backup_jobs=$(kubectl get cronjob -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '[.items[] | select(.metadata.name | contains("backup"))]')
    local job_count=$(echo "$backup_jobs" | jq 'length')
    
    if [ "$job_count" -gt 0 ]; then
        local active_jobs=$(echo "$backup_jobs" | jq '[.[] | select(.spec.suspend != true)] | length')
        local recent_jobs=$(kubectl get job -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '[.items[] | select(.metadata.name | contains("backup")) | select(.status.succeeded==1)] | length')
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        if [ "$active_jobs" -eq "$job_count" ] && [ "$recent_jobs" -gt 0 ]; then
            validation_result "BACKUP_STATUS" "PASS" "$duration" "100" "$job_count active jobs, $recent_jobs recent successes"
        else
            validation_result "BACKUP_STATUS" "CONDITIONAL" "$duration" "70" "$active_jobs/$job_count active, $recent_jobs recent successes"
        fi
    else
        validation_result "BACKUP_STATUS" "SKIP" "0" "0" "No backup jobs found"
    fi
}

check_monitoring_health() {
    local start_time=$(date +%s)
    
    # Check ServiceMonitors
    local service_monitors=$(kubectl get servicemonitor -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '.items | length')
    local prometheus_rules=$(kubectl get prometheusrule -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '.items | length')
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ "$service_monitors" -gt 0 ] && [ "$prometheus_rules" -gt 0 ]; then
        validation_result "MONITORING_HEALTH" "PASS" "$duration" "100" "$service_monitors monitors, $prometheus_rules rules"
    elif [ "$service_monitors" -gt 0 ] || [ "$prometheus_rules" -gt 0 ]; then
        validation_result "MONITORING_HEALTH" "CONDITIONAL" "$duration" "70" "Partial monitoring setup"
    else
        validation_result "MONITORING_HEALTH" "FAIL" "$duration" "0" "No monitoring configuration found"
    fi
}

check_external_dependencies() {
    local start_time=$(date +%s)
    
    # Check 1Password Connect
    local op_secrets=$(kubectl get onepassworditem -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null | jq '.items | length' || echo "0")
    
    # Check Vault connectivity
    local vault_pods=$(kubectl get pod -n vault --context=$CLUSTER_CONTEXT -l app=vault -o json 2>/dev/null | jq '.items | length' || echo "0")
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    local score=0
    local details=""
    
    if [ "$op_secrets" -gt 0 ]; then
        score=$((score + 50))
        details="$details 1Password: $op_secrets secrets"
    fi
    
    if [ "$vault_pods" -gt 0 ]; then
        score=$((score + 50))
        details="$details Vault: $vault_pods pods"
    fi
    
    if [ "$score" -eq 100 ]; then
        validation_result "EXTERNAL_DEPS" "PASS" "$duration" "$score" "$details"
    elif [ "$score" -gt 0 ]; then
        validation_result "EXTERNAL_DEPS" "CONDITIONAL" "$duration" "$score" "$details"
    else
        validation_result "EXTERNAL_DEPS" "FAIL" "$duration" "0" "No external dependencies found"
    fi
}

# Generate comprehensive report
generate_comprehensive_report() {
    if [ "$GENERATE_REPORT" != true ]; then
        return 0
    fi
    
    echo -e "\n${BLUE}=== Generating Comprehensive Report ===${NC}"
    
    local report_file="$VALIDATION_DIR/reports/comprehensive-report.json"
    local html_report="$VALIDATION_DIR/reports/comprehensive-report.html"
    local summary_file="$VALIDATION_DIR/reports/validation-summary.txt"
    
    # Calculate overall score
    local total_score=0
    local score_count=0
    
    for validation in "${!VALIDATION_SCORES[@]}"; do
        if [ "${VALIDATION_RESULTS[$validation]}" != "SKIP" ]; then
            total_score=$((total_score + VALIDATION_SCORES[$validation]))
            score_count=$((score_count + 1))
        fi
    done
    
    local overall_score=$((score_count > 0 ? total_score / score_count : 0))
    
    # Generate JSON report
    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cluster": "$CLUSTER_CONTEXT",
  "namespace": "$NAMESPACE",
  "validation_suite_version": "1.0.0",
  "overall_score": $overall_score,
  "summary": {
    "total_validations": $TOTAL_VALIDATIONS,
    "passed": $PASSED_VALIDATIONS,
    "failed": $FAILED_VALIDATIONS,
    "conditional": $CONDITIONAL_VALIDATIONS,
    "skipped": $((TOTAL_VALIDATIONS - PASSED_VALIDATIONS - FAILED_VALIDATIONS - CONDITIONAL_VALIDATIONS))
  },
  "validations": {
EOF
    
    # Add validation results
    local first=true
    for validation in "${!VALIDATION_RESULTS[@]}"; do
        if [ "$first" = false ]; then
            echo "," >> "$report_file"
        fi
        
        cat >> "$report_file" << EOF
    "$validation": {
      "result": "${VALIDATION_RESULTS[$validation]}",
      "duration_seconds": ${VALIDATION_TIMES[$validation]},
      "score": ${VALIDATION_SCORES[$validation]}
    }
EOF
        first=false
    done
    
    # Add configuration and metadata
    cat >> "$report_file" << EOF
  },
  "configuration": {
    "skip_performance": $SKIP_PERFORMANCE,
    "skip_security": $SKIP_SECURITY,
    "skip_integration": $SKIP_INTEGRATION,
    "parallel_execution": $PARALLEL_EXECUTION
  },
  "environment": {
    "cluster_context": "$CLUSTER_CONTEXT",
    "namespace": "$NAMESPACE",
    "validation_directory": "$VALIDATION_DIR"
  }
}
EOF
    
    # Generate HTML report
    generate_html_report "$html_report"
    
    # Generate summary
    cat > "$summary_file" << EOF
Grill Stats Production Validation Summary
========================================

Date: $(date)
Cluster: $CLUSTER_CONTEXT
Namespace: $NAMESPACE
Overall Score: $overall_score/100

Results:
- Total Validations: $TOTAL_VALIDATIONS
- Passed: $PASSED_VALIDATIONS
- Failed: $FAILED_VALIDATIONS
- Conditional: $CONDITIONAL_VALIDATIONS
- Skipped: $((TOTAL_VALIDATIONS - PASSED_VALIDATIONS - FAILED_VALIDATIONS - CONDITIONAL_VALIDATIONS))

Individual Validation Results:
EOF
    
    for validation in "${!VALIDATION_RESULTS[@]}"; do
        printf "%-25s: %s (Score: %s/100, Duration: %ss)\n" \
            "$validation" \
            "${VALIDATION_RESULTS[$validation]}" \
            "${VALIDATION_SCORES[$validation]}" \
            "${VALIDATION_TIMES[$validation]}" >> "$summary_file"
    done
    
    echo -e "\n${PURPLE}Reports Generated:${NC}"
    echo -e "  JSON Report: $report_file"
    echo -e "  HTML Report: $html_report"
    echo -e "  Summary: $summary_file"
}

generate_html_report() {
    local html_file=$1
    
    cat > "$html_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Grill Stats Production Validation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .summary { display: flex; justify-content: space-around; margin: 20px 0; }
        .summary-item { text-align: center; padding: 10px; }
        .score { font-size: 2em; font-weight: bold; }
        .pass { color: green; }
        .fail { color: red; }
        .conditional { color: orange; }
        .skip { color: gray; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .footer { margin-top: 40px; font-size: 0.8em; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Grill Stats Production Validation Report</h1>
        <p><strong>Generated:</strong> $(date)</p>
        <p><strong>Cluster:</strong> $CLUSTER_CONTEXT</p>
        <p><strong>Namespace:</strong> $NAMESPACE</p>
    </div>
    
    <div class="summary">
        <div class="summary-item">
            <div class="score">$overall_score/100</div>
            <div>Overall Score</div>
        </div>
        <div class="summary-item">
            <div class="score pass">$PASSED_VALIDATIONS</div>
            <div>Passed</div>
        </div>
        <div class="summary-item">
            <div class="score fail">$FAILED_VALIDATIONS</div>
            <div>Failed</div>
        </div>
        <div class="summary-item">
            <div class="score conditional">$CONDITIONAL_VALIDATIONS</div>
            <div>Conditional</div>
        </div>
    </div>
    
    <table>
        <tr>
            <th>Validation</th>
            <th>Result</th>
            <th>Score</th>
            <th>Duration</th>
        </tr>
EOF
    
    for validation in "${!VALIDATION_RESULTS[@]}"; do
        local result="${VALIDATION_RESULTS[$validation]}"
        local class=""
        
        case $result in
            "PASS") class="pass" ;;
            "FAIL") class="fail" ;;
            "CONDITIONAL") class="conditional" ;;
            "SKIP") class="skip" ;;
        esac
        
        cat >> "$html_file" << EOF
        <tr>
            <td>$validation</td>
            <td class="$class">$result</td>
            <td>${VALIDATION_SCORES[$validation]}/100</td>
            <td>${VALIDATION_TIMES[$validation]}s</td>
        </tr>
EOF
    done
    
    cat >> "$html_file" << EOF
    </table>
    
    <div class="footer">
        <p>Generated by Grill Stats Production Validation Suite</p>
        <p>Report Directory: $VALIDATION_DIR</p>
    </div>
</body>
</html>
EOF
}

# Run all validations
run_all_validations() {
    if [ "$PARALLEL_EXECUTION" = true ]; then
        echo -e "${CYAN}Running validations in parallel...${NC}"
        
        # Run validations in parallel
        run_production_validation &
        local prod_pid=$!
        
        if [ "$SKIP_SECURITY" != true ]; then
            run_security_audit &
            local sec_pid=$!
        fi
        
        if [ "$SKIP_PERFORMANCE" != true ]; then
            run_performance_test &
            local perf_pid=$!
        fi
        
        # Wait for parallel jobs to complete
        wait $prod_pid
        [ -n "$sec_pid" ] && wait $sec_pid
        [ -n "$perf_pid" ] && wait $perf_pid
        
        # Run integration test sequentially (requires clean state)
        if [ "$SKIP_INTEGRATION" != true ]; then
            run_integration_test
        fi
    else
        echo -e "${CYAN}Running validations sequentially...${NC}"
        
        run_production_validation
        run_security_audit
        run_performance_test
        run_integration_test
    fi
    
    # Additional checks always run sequentially
    run_additional_checks
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      Grill Stats Full Production Validation Suite           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "Cluster: ${PURPLE}$CLUSTER_CONTEXT${NC}"
    echo -e "Namespace: ${PURPLE}$NAMESPACE${NC}"
    echo -e "Validation Directory: ${PURPLE}$VALIDATION_DIR${NC}"
    echo -e "Parallel Execution: ${PURPLE}$PARALLEL_EXECUTION${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Setup environment
    setup_validation_environment
    
    # Run all validations
    run_all_validations
    
    # Generate comprehensive report
    generate_comprehensive_report
    
    # Final summary
    echo -e "\n${BLUE}Full Validation Summary:${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Total Validations: $TOTAL_VALIDATIONS"
    echo -e "${GREEN}Passed: $PASSED_VALIDATIONS${NC}"
    echo -e "${RED}Failed: $FAILED_VALIDATIONS${NC}"
    echo -e "${YELLOW}Conditional: $CONDITIONAL_VALIDATIONS${NC}"
    echo -e "${CYAN}Skipped: $((TOTAL_VALIDATIONS - PASSED_VALIDATIONS - FAILED_VALIDATIONS - CONDITIONAL_VALIDATIONS))${NC}"
    
    # Calculate overall score
    local total_score=0
    local score_count=0
    
    for validation in "${!VALIDATION_SCORES[@]}"; do
        if [ "${VALIDATION_RESULTS[$validation]}" != "SKIP" ]; then
            total_score=$((total_score + VALIDATION_SCORES[$validation]))
            score_count=$((score_count + 1))
        fi
    done
    
    local overall_score=$((score_count > 0 ? total_score / score_count : 0))
    echo -e "\nOverall Score: ${PURPLE}$overall_score/100${NC}"
    
    echo -e "\n${PURPLE}Validation Results:${NC}"
    echo -e "  Validation Directory: $VALIDATION_DIR"
    echo -e "  Comprehensive Report: $VALIDATION_DIR/reports/comprehensive-report.json"
    echo -e "  HTML Report: $VALIDATION_DIR/reports/comprehensive-report.html"
    echo -e "  Summary: $VALIDATION_DIR/reports/validation-summary.txt"
    
    # Final deployment recommendation
    if [ $FAILED_VALIDATIONS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 PRODUCTION DEPLOYMENT: APPROVED${NC}"
        echo -e "All validations passed. System is ready for production deployment."
        return 0
    elif [ $FAILED_VALIDATIONS -le 1 ] && [ $overall_score -ge 85 ]; then
        echo -e "\n${YELLOW}⚠️  PRODUCTION DEPLOYMENT: CONDITIONAL APPROVAL${NC}"
        echo -e "Minor issues detected. Review and address before full production deployment."
        return 0
    else
        echo -e "\n${RED}❌ PRODUCTION DEPLOYMENT: NOT APPROVED${NC}"
        echo -e "Multiple critical issues detected. Address failures before production deployment."
        return 1
    fi
}

# Check prerequisites
for cmd in kubectl jq curl; do
    if ! command -v $cmd >/dev/null 2>&1; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --context)
            CLUSTER_CONTEXT="$2"
            shift 2
            ;;
        --skip-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --skip-security)
            SKIP_SECURITY=true
            shift
            ;;
        --skip-integration)
            SKIP_INTEGRATION=true
            shift
            ;;
        --parallel)
            PARALLEL_EXECUTION=true
            shift
            ;;
        --no-report)
            GENERATE_REPORT=false
            shift
            ;;
        -o|--output)
            VALIDATION_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -n, --namespace NAME      Kubernetes namespace (default: grill-stats)"
            echo "  --context NAME            Kubernetes context (default: prod-lab)"
            echo "  --skip-performance        Skip performance testing"
            echo "  --skip-security           Skip security audit"
            echo "  --skip-integration        Skip integration testing"
            echo "  --parallel                Run validations in parallel"
            echo "  --no-report               Skip report generation"
            echo "  -o, --output DIR          Output directory (default: auto-generated)"
            echo "  -h, --help                Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all validations"
            echo "  $0 --parallel                        # Run validations in parallel"
            echo "  $0 --skip-performance --skip-security # Run only production and integration tests"
            echo "  $0 --context dev-lab -n grill-dev    # Test different environment"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"