#!/bin/bash
# Security Audit Script for Grill Stats Platform
# Comprehensive security validation for production deployment

set -e

NAMESPACE="grill-stats"
CLUSTER_CONTEXT="prod-lab"
AUDIT_DIR="/tmp/grill-stats-security-$(date +%Y%m%d_%H%M%S)"
SEVERITY_LEVELS=("CRITICAL" "HIGH" "MEDIUM" "LOW" "INFO")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Security findings tracking
declare -A FINDINGS
declare -A SEVERITY_COUNTS
TOTAL_FINDINGS=0
CRITICAL_FINDINGS=0
HIGH_FINDINGS=0

# Initialize severity counters
for level in "${SEVERITY_LEVELS[@]}"; do
    SEVERITY_COUNTS[$level]=0
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$AUDIT_DIR/security-audit.log"
}

add_finding() {
    local severity=$1
    local category=$2
    local description=$3
    local recommendation=$4

    local finding_id="FINDING_$(printf "%03d" $TOTAL_FINDINGS)"
    FINDINGS[$finding_id]="$severity|$category|$description|$recommendation"

    SEVERITY_COUNTS[$severity]=$((SEVERITY_COUNTS[$severity] + 1))
    TOTAL_FINDINGS=$((TOTAL_FINDINGS + 1))

    case $severity in
        "CRITICAL") CRITICAL_FINDINGS=$((CRITICAL_FINDINGS + 1)); echo -e "${RED}🔴 $severity${NC}: $description" ;;
        "HIGH") HIGH_FINDINGS=$((HIGH_FINDINGS + 1)); echo -e "${YELLOW}🟠 $severity${NC}: $description" ;;
        "MEDIUM") echo -e "${YELLOW}🟡 $severity${NC}: $description" ;;
        "LOW") echo -e "${BLUE}🔵 $severity${NC}: $description" ;;
        "INFO") echo -e "${GREEN}ℹ️  $severity${NC}: $description" ;;
    esac

    log "$severity - $category: $description"
}

setup_audit_environment() {
    echo -e "${BLUE}Setting up security audit environment...${NC}"
    mkdir -p "$AUDIT_DIR"

    # Create audit subdirectories
    mkdir -p "$AUDIT_DIR/rbac"
    mkdir -p "$AUDIT_DIR/network"
    mkdir -p "$AUDIT_DIR/secrets"
    mkdir -p "$AUDIT_DIR/containers"
    mkdir -p "$AUDIT_DIR/policies"

    log "Audit directory created: $AUDIT_DIR"
}

# RBAC Security Audit
audit_rbac() {
    echo -e "\n${BLUE}=== RBAC Security Audit ===${NC}"

    # Service Accounts
    local sa_file="$AUDIT_DIR/rbac/service-accounts.json"
    kubectl get serviceaccount -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$sa_file"

    local sa_count=$(jq '.items | length' "$sa_file")
    if [ "$sa_count" -eq 1 ]; then
        add_finding "MEDIUM" "RBAC" "Only default service account found" "Create dedicated service accounts for each service"
    else
        add_finding "INFO" "RBAC" "$sa_count service accounts configured" "Good: Dedicated service accounts in use"
    fi

    # Role Bindings
    local rb_file="$AUDIT_DIR/rbac/role-bindings.json"
    kubectl get rolebinding -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$rb_file"

    local rb_count=$(jq '.items | length' "$rb_file")
    if [ "$rb_count" -eq 0 ]; then
        add_finding "HIGH" "RBAC" "No role bindings found" "Implement proper RBAC with least privilege principle"
    else
        add_finding "INFO" "RBAC" "$rb_count role bindings configured" "RBAC is configured"
    fi

    # Check for cluster-admin bindings
    local cluster_admin=$(kubectl get clusterrolebinding --context=$CLUSTER_CONTEXT -o json | jq '.items[] | select(.roleRef.name=="cluster-admin") | .subjects[]? | select(.namespace=="'$NAMESPACE'") | .name')
    if [ -n "$cluster_admin" ]; then
        add_finding "CRITICAL" "RBAC" "Cluster-admin privileges found in namespace" "Remove cluster-admin privileges and use least privilege principle"
    fi

    # Analyze service account tokens
    jq -r '.items[] | select(.metadata.name != "default") | .metadata.name' "$sa_file" | while read -r sa; do
        local automount=$(kubectl get serviceaccount $sa -n $NAMESPACE --context=$CLUSTER_CONTEXT -o jsonpath='{.automountServiceAccountToken}')
        if [ "$automount" != "false" ]; then
            add_finding "MEDIUM" "RBAC" "Service account $sa has automount enabled" "Set automountServiceAccountToken: false if not needed"
        fi
    done
}

# Network Security Audit
audit_network_security() {
    echo -e "\n${BLUE}=== Network Security Audit ===${NC}"

    # Network Policies
    local np_file="$AUDIT_DIR/network/network-policies.json"
    kubectl get networkpolicy -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$np_file"

    local np_count=$(jq '.items | length' "$np_file")
    if [ "$np_count" -eq 0 ]; then
        add_finding "HIGH" "NETWORK" "No network policies found" "Implement network policies to restrict pod-to-pod communication"
    else
        add_finding "INFO" "NETWORK" "$np_count network policies configured" "Network segmentation is implemented"

        # Check for default deny policy
        local default_deny=$(jq -r '.items[] | select(.metadata.name | contains("default-deny")) | .metadata.name' "$np_file")
        if [ -z "$default_deny" ]; then
            add_finding "MEDIUM" "NETWORK" "No default deny policy found" "Implement a default deny network policy"
        fi
    fi

    # Ingress Security
    local ingress_file="$AUDIT_DIR/network/ingress.json"
    kubectl get ingress,ingressroute -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$ingress_file" 2>/dev/null || echo '{"items":[]}' > "$ingress_file"

    # Check for TLS configuration
    local tls_enabled=$(jq '[.items[] | select(.spec.tls or .spec.routes[]?.middlewares[]? | contains("tls"))] | length' "$ingress_file")
    local total_ingress=$(jq '.items | length' "$ingress_file")

    if [ "$total_ingress" -gt 0 ]; then
        if [ "$tls_enabled" -eq "$total_ingress" ]; then
            add_finding "INFO" "NETWORK" "All ingress routes use TLS" "Good: TLS is properly configured"
        else
            add_finding "HIGH" "NETWORK" "Some ingress routes missing TLS" "Configure TLS for all public endpoints"
        fi
    fi

    # Check for LoadBalancer services
    local lb_services=$(kubectl get service -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '[.items[] | select(.spec.type=="LoadBalancer")] | length')
    if [ "$lb_services" -gt 0 ]; then
        add_finding "MEDIUM" "NETWORK" "$lb_services LoadBalancer services found" "Review if LoadBalancer services are necessary; consider using ClusterIP with ingress"
    fi

    # Check for services without selectors
    local external_services=$(kubectl get service -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '[.items[] | select(.spec.selector == null)] | length')
    if [ "$external_services" -gt 0 ]; then
        add_finding "INFO" "NETWORK" "$external_services external services found" "Review external service configurations for security"
    fi
}

# Container Security Audit
audit_container_security() {
    echo -e "\n${BLUE}=== Container Security Audit ===${NC}"

    # Get all deployments
    local deployments_file="$AUDIT_DIR/containers/deployments.json"
    kubectl get deployment -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$deployments_file"

    # Security Context Analysis
    jq -r '.items[] | .metadata.name' "$deployments_file" | while read -r deployment; do
        local deployment_json=$(jq ".items[] | select(.metadata.name==\"$deployment\")" "$deployments_file")

        # Check runAsNonRoot
        local run_as_non_root=$(echo "$deployment_json" | jq -r '.spec.template.spec.securityContext.runAsNonRoot // false')
        if [ "$run_as_non_root" != "true" ]; then
            add_finding "HIGH" "CONTAINER" "Deployment $deployment may run as root" "Set runAsNonRoot: true in security context"
        fi

        # Check readOnlyRootFilesystem
        local containers=$(echo "$deployment_json" | jq -r '.spec.template.spec.containers[].name')
        echo "$containers" | while read -r container; do
            local read_only=$(echo "$deployment_json" | jq -r ".spec.template.spec.containers[] | select(.name==\"$container\") | .securityContext.readOnlyRootFilesystem // false")
            if [ "$read_only" != "true" ]; then
                add_finding "MEDIUM" "CONTAINER" "Container $container in $deployment has writable root filesystem" "Set readOnlyRootFilesystem: true"
            fi

            # Check for privileged containers
            local privileged=$(echo "$deployment_json" | jq -r ".spec.template.spec.containers[] | select(.name==\"$container\") | .securityContext.privileged // false")
            if [ "$privileged" == "true" ]; then
                add_finding "CRITICAL" "CONTAINER" "Container $container in $deployment is privileged" "Remove privileged: true unless absolutely necessary"
            fi

            # Check capabilities
            local capabilities=$(echo "$deployment_json" | jq -r ".spec.template.spec.containers[] | select(.name==\"$container\") | .securityContext.capabilities.add[]? // empty")
            if [ -n "$capabilities" ]; then
                add_finding "MEDIUM" "CONTAINER" "Container $container has additional capabilities: $capabilities" "Review and minimize capabilities"
            fi
        done

        # Check resource limits
        local has_limits=$(echo "$deployment_json" | jq -r '.spec.template.spec.containers[] | select(.resources.limits == null) | .name')
        if [ -n "$has_limits" ]; then
            add_finding "MEDIUM" "CONTAINER" "Deployment $deployment missing resource limits" "Set CPU and memory limits for all containers"
        fi

        # Check resource requests
        local has_requests=$(echo "$deployment_json" | jq -r '.spec.template.spec.containers[] | select(.resources.requests == null) | .name')
        if [ -n "$has_requests" ]; then
            add_finding "LOW" "CONTAINER" "Deployment $deployment missing resource requests" "Set CPU and memory requests for better scheduling"
        fi
    done

    # Image Security
    audit_container_images
}

audit_container_images() {
    echo -e "\n${YELLOW}Container Image Security:${NC}"

    local deployments_file="$AUDIT_DIR/containers/deployments.json"
    local images_file="$AUDIT_DIR/containers/images.txt"

    # Extract all container images
    jq -r '.items[].spec.template.spec.containers[].image' "$deployments_file" | sort -u > "$images_file"

    while read -r image; do
        # Check for latest tag
        if echo "$image" | grep -q ":latest$"; then
            add_finding "MEDIUM" "CONTAINER" "Image using latest tag: $image" "Use specific version tags for reproducible deployments"
        fi

        # Check for official images
        if echo "$image" | grep -q "^[^/]*/[^/]*$"; then
            add_finding "INFO" "CONTAINER" "Using Docker Hub image: $image" "Consider using images from trusted registries"
        fi

        # Check for private registry
        if echo "$image" | grep -q "^[^/]*\.[^/]*"; then
            add_finding "INFO" "CONTAINER" "Using private registry: $image" "Good: Using private registry"
        fi

        # Check for digest pinning
        if ! echo "$image" | grep -q "@sha256:"; then
            add_finding "LOW" "CONTAINER" "Image not pinned by digest: $image" "Consider pinning images by digest for immutability"
        fi
    done < "$images_file"

    # Check for image pull secrets
    local pull_secrets=$(jq -r '.items[].spec.template.spec.imagePullSecrets[]?.name // empty' "$deployments_file" | sort -u)
    if [ -z "$pull_secrets" ]; then
        add_finding "INFO" "CONTAINER" "No image pull secrets configured" "Configure image pull secrets for private registries"
    else
        add_finding "INFO" "CONTAINER" "Image pull secrets configured: $pull_secrets" "Good: Image pull secrets are configured"
    fi
}

# Secrets Security Audit
audit_secrets_security() {
    echo -e "\n${BLUE}=== Secrets Security Audit ===${NC}"

    # Regular Secrets
    local secrets_file="$AUDIT_DIR/secrets/secrets.json"
    kubectl get secret -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$secrets_file"

    local secret_count=$(jq '.items | length' "$secrets_file")
    add_finding "INFO" "SECRETS" "$secret_count secrets found in namespace" "Inventory of secrets"

    # Check for default token secrets
    local default_tokens=$(jq -r '.items[] | select(.metadata.name | contains("default-token")) | .metadata.name' "$secrets_file")
    if [ -n "$default_tokens" ]; then
        add_finding "INFO" "SECRETS" "Default service account tokens present" "Consider using bound service account tokens"
    fi

    # Check for TLS secrets
    local tls_secrets=$(jq -r '.items[] | select(.type=="kubernetes.io/tls") | .metadata.name' "$secrets_file")
    if [ -n "$tls_secrets" ]; then
        add_finding "INFO" "SECRETS" "TLS secrets found: $tls_secrets" "TLS secrets are configured"

        # Check TLS secret expiration (if cert-manager annotations exist)
        echo "$tls_secrets" | while read -r secret; do
            local cert_data=$(kubectl get secret $secret -n $NAMESPACE --context=$CLUSTER_CONTEXT -o jsonpath='{.data.tls\.crt}' | base64 -d)
            if [ -n "$cert_data" ]; then
                local expiry=$(echo "$cert_data" | openssl x509 -noout -dates 2>/dev/null | grep "notAfter" | cut -d= -f2)
                if [ -n "$expiry" ]; then
                    log "TLS certificate $secret expires: $expiry"
                fi
            fi
        done
    fi

    # 1Password Connect Secrets
    local op_secrets_file="$AUDIT_DIR/secrets/onepassword-secrets.json"
    kubectl get onepassworditem -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json > "$op_secrets_file" 2>/dev/null || echo '{"items":[]}' > "$op_secrets_file"

    local op_count=$(jq '.items | length' "$op_secrets_file")
    if [ "$op_count" -gt 0 ]; then
        add_finding "INFO" "SECRETS" "$op_count 1Password secrets configured" "Good: Using external secret management"

        # Check sync status
        local synced=$(jq '[.items[] | select(.status.conditions[] | select(.type=="Synced" and .status=="True"))] | length' "$op_secrets_file")
        if [ "$synced" -ne "$op_count" ]; then
            add_finding "MEDIUM" "SECRETS" "Only $synced/$op_count 1Password secrets synced" "Check 1Password Connect configuration"
        fi
    else
        add_finding "MEDIUM" "SECRETS" "No external secret management detected" "Consider using external secret management (1Password, Vault, etc.)"
    fi

    # Check for secrets in environment variables
    local deployments_file="$AUDIT_DIR/containers/deployments.json"
    if [ -f "$deployments_file" ]; then
        local plain_secrets=$(jq -r '.items[].spec.template.spec.containers[].env[]? | select(.value and (.name | ascii_downcase | contains("password") or contains("secret") or contains("token") or contains("key"))) | .name' "$deployments_file")
        if [ -n "$plain_secrets" ]; then
            add_finding "HIGH" "SECRETS" "Potential secrets in environment variables: $plain_secrets" "Use secret references instead of plain text values"
        fi
    fi
}

# Pod Security Standards Audit
audit_pod_security() {
    echo -e "\n${BLUE}=== Pod Security Standards Audit ===${NC}"

    # Check for Pod Security Standards labels
    local pss_enforce=$(kubectl get namespace $NAMESPACE --context=$CLUSTER_CONTEXT -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}' 2>/dev/null)
    local pss_audit=$(kubectl get namespace $NAMESPACE --context=$CLUSTER_CONTEXT -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/audit}' 2>/dev/null)
    local pss_warn=$(kubectl get namespace $NAMESPACE --context=$CLUSTER_CONTEXT -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/warn}' 2>/dev/null)

    if [ -z "$pss_enforce" ]; then
        add_finding "HIGH" "POD_SECURITY" "No Pod Security Standards enforcement configured" "Configure Pod Security Standards for the namespace"
    else
        add_finding "INFO" "POD_SECURITY" "Pod Security Standards enforcement: $pss_enforce" "Good: Pod Security Standards are configured"
    fi

    # Check for Pod Security Policies (deprecated)
    local psp_count=$(kubectl get podsecuritypolicy --context=$CLUSTER_CONTEXT 2>/dev/null | wc -l)
    if [ "$psp_count" -gt 1 ]; then  # Greater than 1 because of header
        add_finding "MEDIUM" "POD_SECURITY" "Pod Security Policies detected (deprecated)" "Migrate to Pod Security Standards"
    fi

    # Check for Security Context Constraints (OpenShift)
    local scc_count=$(kubectl get securitycontextconstraints --context=$CLUSTER_CONTEXT 2>/dev/null | wc -l)
    if [ "$scc_count" -gt 1 ]; then
        add_finding "INFO" "POD_SECURITY" "Security Context Constraints detected" "OpenShift security controls are in place"
    fi
}

# Compliance and Policy Audit
audit_compliance() {
    echo -e "\n${BLUE}=== Compliance and Policy Audit ===${NC}"

    # Check for admission controllers
    local admission_plugins=$(kubectl get configmap -n kube-system --context=$CLUSTER_CONTEXT extension-apiserver-authentication -o jsonpath='{.data}' 2>/dev/null)
    if [ -n "$admission_plugins" ]; then
        add_finding "INFO" "COMPLIANCE" "Admission controllers are configured" "Good: Admission control is enabled"
    fi

    # Check for OPA Gatekeeper
    local gatekeeper_count=$(kubectl get crd --context=$CLUSTER_CONTEXT | grep -c "gatekeeper" || echo "0")
    if [ "$gatekeeper_count" -gt 0 ]; then
        add_finding "INFO" "COMPLIANCE" "OPA Gatekeeper detected" "Good: Policy enforcement is available"

        # Check for constraints
        local constraints=$(kubectl get constraint --context=$CLUSTER_CONTEXT 2>/dev/null | wc -l)
        if [ "$constraints" -gt 1 ]; then
            add_finding "INFO" "COMPLIANCE" "$((constraints - 1)) Gatekeeper constraints configured" "Policy constraints are active"
        fi
    else
        add_finding "MEDIUM" "COMPLIANCE" "No policy enforcement detected" "Consider implementing OPA Gatekeeper or similar"
    fi

    # Check for Falco (runtime security)
    local falco_count=$(kubectl get pod -A --context=$CLUSTER_CONTEXT | grep -c "falco" || echo "0")
    if [ "$falco_count" -gt 0 ]; then
        add_finding "INFO" "COMPLIANCE" "Falco runtime security detected" "Good: Runtime security monitoring is active"
    else
        add_finding "MEDIUM" "COMPLIANCE" "No runtime security monitoring detected" "Consider implementing Falco or similar"
    fi

    # Check for security scanning
    local vuln_scan_count=$(kubectl get crd --context=$CLUSTER_CONTEXT | grep -c "vulnerabilityreport\|clustercompliancereport" || echo "0")
    if [ "$vuln_scan_count" -gt 0 ]; then
        add_finding "INFO" "COMPLIANCE" "Vulnerability scanning tools detected" "Good: Security scanning is configured"
    else
        add_finding "MEDIUM" "COMPLIANCE" "No vulnerability scanning detected" "Consider implementing vulnerability scanning"
    fi
}

# Generate security recommendations
generate_recommendations() {
    echo -e "\n${BLUE}=== Security Recommendations ===${NC}"

    local recommendations_file="$AUDIT_DIR/recommendations.md"

    cat > "$recommendations_file" << EOF
# Security Audit Recommendations

## Executive Summary
- **Total Findings:** $TOTAL_FINDINGS
- **Critical:** ${SEVERITY_COUNTS[CRITICAL]}
- **High:** ${SEVERITY_COUNTS[HIGH]}
- **Medium:** ${SEVERITY_COUNTS[MEDIUM]}
- **Low:** ${SEVERITY_COUNTS[LOW]}
- **Info:** ${SEVERITY_COUNTS[INFO]}

## Detailed Findings

EOF

    # Add findings to recommendations
    for finding_id in "${!FINDINGS[@]}"; do
        local finding_data="${FINDINGS[$finding_id]}"
        local severity=$(echo "$finding_data" | cut -d'|' -f1)
        local category=$(echo "$finding_data" | cut -d'|' -f2)
        local description=$(echo "$finding_data" | cut -d'|' -f3)
        local recommendation=$(echo "$finding_data" | cut -d'|' -f4)

        cat >> "$recommendations_file" << EOF
### $finding_id - $severity

**Category:** $category
**Description:** $description
**Recommendation:** $recommendation

EOF
    done

    # Add general recommendations
    cat >> "$recommendations_file" << EOF
## General Security Recommendations

### Immediate Actions (Critical/High)
1. **Implement Pod Security Standards** - Configure appropriate PSS levels for all namespaces
2. **Enable Network Policies** - Implement default deny and specific allow rules
3. **Configure Security Contexts** - Set runAsNonRoot, readOnlyRootFilesystem, and drop capabilities
4. **Secure Container Images** - Use specific tags, scan for vulnerabilities, and use private registries

### Short-term Improvements (Medium)
1. **External Secret Management** - Implement Vault, 1Password Connect, or similar
2. **RBAC Hardening** - Create service-specific roles with minimal permissions
3. **Admission Control** - Deploy OPA Gatekeeper or similar policy enforcement
4. **Monitoring and Alerting** - Implement security monitoring and alerting

### Long-term Enhancements (Low/Info)
1. **Runtime Security** - Deploy Falco or similar runtime monitoring
2. **Vulnerability Scanning** - Implement continuous image and cluster scanning
3. **Compliance Frameworks** - Implement CIS, NIST, or other compliance standards
4. **Security Automation** - Automate security policy enforcement and remediation

## Compliance Considerations

### Industry Standards
- **CIS Kubernetes Benchmark** - Follow CIS recommendations for hardening
- **NIST Cybersecurity Framework** - Implement NIST controls where applicable
- **OWASP Top 10** - Address web application security concerns

### Regulatory Requirements
- Consider GDPR, HIPAA, SOC 2, or other relevant regulations
- Implement appropriate data protection and privacy controls
- Maintain audit trails and access logs

EOF

    log "Security recommendations generated: $recommendations_file"
}

# Generate security report
generate_security_report() {
    echo -e "\n${BLUE}Generating security audit report...${NC}"

    local report_file="$AUDIT_DIR/security-report.json"

    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cluster": "$CLUSTER_CONTEXT",
  "namespace": "$NAMESPACE",
  "audit_version": "1.0",
  "summary": {
    "total_findings": $TOTAL_FINDINGS,
    "critical_findings": ${SEVERITY_COUNTS[CRITICAL]},
    "high_findings": ${SEVERITY_COUNTS[HIGH]},
    "medium_findings": ${SEVERITY_COUNTS[MEDIUM]},
    "low_findings": ${SEVERITY_COUNTS[LOW]},
    "info_findings": ${SEVERITY_COUNTS[INFO]}
  },
  "risk_score": $(( (SEVERITY_COUNTS[CRITICAL] * 10) + (SEVERITY_COUNTS[HIGH] * 7) + (SEVERITY_COUNTS[MEDIUM] * 5) + (SEVERITY_COUNTS[LOW] * 2) + (SEVERITY_COUNTS[INFO] * 1) )),
  "categories": {
    "rbac": {
      "findings": $(echo "${!FINDINGS[@]}" | tr ' ' '\n' | while read -r id; do echo "${FINDINGS[$id]}" | grep -c "RBAC"; done | awk '{sum+=$1} END {print sum+0}'),
      "status": "$([ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && echo "PASS" || echo "FAIL")"
    },
    "network": {
      "findings": $(echo "${!FINDINGS[@]}" | tr ' ' '\n' | while read -r id; do echo "${FINDINGS[$id]}" | grep -c "NETWORK"; done | awk '{sum+=$1} END {print sum+0}'),
      "status": "$([ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && echo "PASS" || echo "FAIL")"
    },
    "container": {
      "findings": $(echo "${!FINDINGS[@]}" | tr ' ' '\n' | while read -r id; do echo "${FINDINGS[$id]}" | grep -c "CONTAINER"; done | awk '{sum+=$1} END {print sum+0}'),
      "status": "$([ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && echo "PASS" || echo "FAIL")"
    },
    "secrets": {
      "findings": $(echo "${!FINDINGS[@]}" | tr ' ' '\n' | while read -r id; do echo "${FINDINGS[$id]}" | grep -c "SECRETS"; done | awk '{sum+=$1} END {print sum+0}'),
      "status": "$([ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && echo "PASS" || echo "FAIL")"
    }
  },
  "findings": [
EOF

    # Add individual findings
    local first=true
    for finding_id in "${!FINDINGS[@]}"; do
        local finding_data="${FINDINGS[$finding_id]}"
        local severity=$(echo "$finding_data" | cut -d'|' -f1)
        local category=$(echo "$finding_data" | cut -d'|' -f2)
        local description=$(echo "$finding_data" | cut -d'|' -f3)
        local recommendation=$(echo "$finding_data" | cut -d'|' -f4)

        if [ "$first" = false ]; then
            echo "," >> "$report_file"
        fi

        cat >> "$report_file" << EOF
    {
      "id": "$finding_id",
      "severity": "$severity",
      "category": "$category",
      "description": "$description",
      "recommendation": "$recommendation",
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    }
EOF
        first=false
    done

    echo -e "\n  ]\n}" >> "$report_file"

    log "Security report generated: $report_file"
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║             Grill Stats Security Audit Suite                 ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "Cluster: ${PURPLE}$CLUSTER_CONTEXT${NC}"
    echo -e "Namespace: ${PURPLE}$NAMESPACE${NC}"
    echo -e "Audit Directory: ${PURPLE}$AUDIT_DIR${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Setup audit environment
    setup_audit_environment

    # Run security audits
    audit_rbac
    audit_network_security
    audit_container_security
    audit_secrets_security
    audit_pod_security
    audit_compliance

    # Generate reports
    generate_recommendations
    generate_security_report

    # Security summary
    echo -e "\n${BLUE}Security Audit Summary:${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Total Findings: $TOTAL_FINDINGS"
    echo -e "${RED}Critical: ${SEVERITY_COUNTS[CRITICAL]}${NC}"
    echo -e "${YELLOW}High: ${SEVERITY_COUNTS[HIGH]}${NC}"
    echo -e "${YELLOW}Medium: ${SEVERITY_COUNTS[MEDIUM]}${NC}"
    echo -e "${BLUE}Low: ${SEVERITY_COUNTS[LOW]}${NC}"
    echo -e "${GREEN}Info: ${SEVERITY_COUNTS[INFO]}${NC}"

    local risk_score=$(( (SEVERITY_COUNTS[CRITICAL] * 10) + (SEVERITY_COUNTS[HIGH] * 7) + (SEVERITY_COUNTS[MEDIUM] * 5) + (SEVERITY_COUNTS[LOW] * 2) + (SEVERITY_COUNTS[INFO] * 1) ))
    echo -e "\nRisk Score: $risk_score"

    echo -e "\n${PURPLE}Audit Results:${NC}"
    echo -e "  Security Report: $AUDIT_DIR/security-report.json"
    echo -e "  Recommendations: $AUDIT_DIR/recommendations.md"
    echo -e "  Full Log: $AUDIT_DIR/security-audit.log"

    # Final security status
    if [ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && [ ${SEVERITY_COUNTS[HIGH]} -eq 0 ]; then
        echo -e "\n${GREEN}✅ SECURITY AUDIT: PASSED${NC}"
        echo -e "No critical or high severity issues found."
        return 0
    elif [ ${SEVERITY_COUNTS[CRITICAL]} -eq 0 ] && [ ${SEVERITY_COUNTS[HIGH]} -le 2 ]; then
        echo -e "\n${YELLOW}⚠️  SECURITY AUDIT: CONDITIONAL PASS${NC}"
        echo -e "Minor high severity issues found. Review recommendations."
        return 0
    else
        echo -e "\n${RED}❌ SECURITY AUDIT: FAILED${NC}"
        echo -e "Critical or multiple high severity issues found."
        echo -e "Address security findings before production deployment."
        return 1
    fi
}

# Check prerequisites
if ! command -v kubectl >/dev/null 2>&1; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq is not installed${NC}"
    exit 1
fi

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
        -o|--output)
            AUDIT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -n, --namespace NAME      Kubernetes namespace (default: grill-stats)"
            echo "  --context NAME            Kubernetes context (default: prod-lab)"
            echo "  -o, --output DIR          Output directory (default: auto-generated)"
            echo "  -h, --help                Show this help"
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
