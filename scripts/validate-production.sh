#!/bin/bash
# Production Deployment Validation Script for Grill Stats Platform
# Validates all components, services, and integrations in the prod-lab cluster

set -e

# Set kubectl path and kubeconfig
KUBECTL_PATH="/mnt/c/Users/lordmuffin/Git/homelab/kubectl"
KUBECONFIG_PATH="/mnt/c/Users/lordmuffin/.kube/config"
export PATH="$(dirname "$KUBECTL_PATH"):$PATH"
export KUBECONFIG="$KUBECONFIG_PATH"

# Verify kubectl and kubeconfig are accessible
if [ ! -f "$KUBECTL_PATH" ]; then
    echo "Error: kubectl not found at $KUBECTL_PATH"
    exit 1
fi

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "Error: kubeconfig not found at $KUBECONFIG_PATH"
    echo "Please specify the correct path to your kubeconfig file"
    exit 1
fi

# Make kubectl executable if needed
chmod +x "$KUBECTL_PATH" 2>/dev/null || true

# Configuration
NAMESPACE="grill-stats"
CLUSTER_CONTEXT="healing-organics-cloud-homelab"
LOG_FILE="/tmp/grill-stats-validation-$(date +%Y%m%d_%H%M%S).log"
RESULTS_FILE="/tmp/grill-stats-results-$(date +%Y%m%d_%H%M%S).json"
TIMEOUT=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Status tracking
declare -A SERVICE_STATUS
declare -A RESPONSE_TIMES
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Status function
check_status() {
    local service=$1
    local status=$2
    local message=$3
    local details=${4:-""}
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    SERVICE_STATUS[$service]=$status
    
    if [ "$status" == "GO" ]; then
        echo -e "${GREEN}✓ GO${NC} - $service: $message"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    elif [ "$status" == "NO-GO" ]; then
        echo -e "${RED}✗ NO-GO${NC} - $service: $message"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    else
        echo -e "${YELLOW}⚠ WARNING${NC} - $service: $message"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    
    if [ -n "$details" ]; then
        echo -e "  ${PURPLE}Details:${NC} $details"
    fi
    
    log "$status - $service: $message $details"
}

# Performance measurement
measure_response_time() {
    local service=$1
    local endpoint=$2
    local start=$(date +%s%N)
    
    if curl -sf --max-time $TIMEOUT "$endpoint" >/dev/null 2>&1; then
        local end=$(date +%s%N)
        local duration=$((($end - $start) / 1000000))
        RESPONSE_TIMES[$service]=$duration
        echo "$duration"
    else
        echo "-1"
    fi
}

# Kubernetes cluster validation
validate_cluster() {
    echo -e "\n${BLUE}=== Kubernetes Cluster Validation ===${NC}"
    
    # Check cluster connectivity
    if kubectl cluster-info --context=$CLUSTER_CONTEXT >/dev/null 2>&1; then
        check_status "CLUSTER_CONNECTIVITY" "GO" "Cluster accessible"
    else
        check_status "CLUSTER_CONNECTIVITY" "NO-GO" "Cannot connect to cluster"
        return 1
    fi
    
    # Check nodes
    local node_info=$(kubectl get nodes --context=$CLUSTER_CONTEXT -o json 2>/dev/null)
    local node_count=$(echo "$node_info" | jq '.items | length')
    local ready_nodes=$(echo "$node_info" | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length')
    
    if [ "$node_count" -eq "$ready_nodes" ] && [ "$node_count" -gt 0 ]; then
        check_status "CLUSTER_NODES" "GO" "$ready_nodes/$node_count nodes ready"
        
        # Check node resources
        local cpu_pressure=$(echo "$node_info" | jq '[.items[].status.conditions[] | select(.type=="MemoryPressure" and .status=="True")] | length')
        local mem_pressure=$(echo "$node_info" | jq '[.items[].status.conditions[] | select(.type=="DiskPressure" and .status=="True")] | length')
        
        if [ "$cpu_pressure" -eq 0 ] && [ "$mem_pressure" -eq 0 ]; then
            check_status "NODE_RESOURCES" "GO" "No resource pressure on nodes"
        else
            check_status "NODE_RESOURCES" "WARNING" "Resource pressure detected on some nodes"
        fi
    else
        check_status "CLUSTER_NODES" "NO-GO" "Only $ready_nodes/$node_count nodes ready"
    fi
    
    # Check namespace
    if kubectl get namespace $NAMESPACE --context=$CLUSTER_CONTEXT >/dev/null 2>&1; then
        check_status "NAMESPACE" "GO" "Namespace $NAMESPACE exists"
        
        # Check resource quotas
        local quotas=$(kubectl get resourcequota -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null)
        if [ "$(echo "$quotas" | jq '.items | length')" -gt 0 ]; then
            local quota_status="GO"
            if command -v jq >/dev/null 2>&1; then
                echo "$quotas" | jq -r '.items[].status.used | to_entries[] | select(.value != "0") | .key + ": " + .value' | while read -r usage; do
                    log "Resource usage: $usage"
                done
            fi
            check_status "RESOURCE_QUOTAS" "$quota_status" "Resource quotas configured and monitored"
        fi
    else
        check_status "NAMESPACE" "NO-GO" "Namespace $NAMESPACE not found"
        return 1
    fi
}

# Service validation
validate_services() {
    echo -e "\n${BLUE}=== Core Services Validation ===${NC}"
    
    local services=(
        "auth-service:8082"
        "device-service:8080"
        "temperature-service:8080"
        "historical-data-service:8080"
        "encryption-service:8082"
        "web-ui-service:80"
    )
    
    for service_port in "${services[@]}"; do
        local service="${service_port%:*}"
        local port="${service_port#*:}"
        
        # Check deployment
        local deployment=$(kubectl get deployment $service -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null)
        if [ -n "$deployment" ]; then
            local replicas=$(echo "$deployment" | jq '.status.readyReplicas // 0')
            local desired=$(echo "$deployment" | jq '.spec.replicas')
            local available=$(echo "$deployment" | jq '.status.availableReplicas // 0')
            
            if [ "$replicas" -eq "$desired" ] && [ "$replicas" -gt 0 ]; then
                check_status "${service^^}_DEPLOYMENT" "GO" "$replicas/$desired replicas ready" "Available: $available"
            else
                check_status "${service^^}_DEPLOYMENT" "NO-GO" "Only $replicas/$desired replicas ready"
            fi
            
            # Check rollout status
            local conditions=$(echo "$deployment" | jq -r '.status.conditions[] | select(.type=="Progressing") | .status')
            if [ "$conditions" == "True" ]; then
                check_status "${service^^}_ROLLOUT" "GO" "Deployment stable"
            else
                check_status "${service^^}_ROLLOUT" "WARNING" "Deployment may be unstable"
            fi
        else
            check_status "${service^^}_DEPLOYMENT" "NO-GO" "Deployment not found"
        fi
        
        # Check service endpoints
        local endpoints=$(kubectl get endpoints $service -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null)
        if [ -n "$endpoints" ]; then
            local endpoint_count=$(echo "$endpoints" | jq '.subsets[0].addresses | length // 0')
            
            if [ "$endpoint_count" -gt 0 ]; then
                check_status "${service^^}_ENDPOINTS" "GO" "$endpoint_count endpoints available"
            else
                check_status "${service^^}_ENDPOINTS" "NO-GO" "No endpoints available"
            fi
        fi
        
        # Health check
        local pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=$service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$pod" ]; then
            if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pod -- wget -q --spider "http://localhost:$port/health" 2>/dev/null; then
                check_status "${service^^}_HEALTH" "GO" "Health check passed"
                
                # Get detailed health info if available
                local health_data=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pod -- wget -qO- "http://localhost:$port/health" 2>/dev/null || echo "{}")
                if [ -n "$health_data" ] && [ "$health_data" != "{}" ]; then
                    local status=$(echo "$health_data" | jq -r '.status // "unknown"')
                    log "Health status for $service: $status"
                fi
            else
                check_status "${service^^}_HEALTH" "NO-GO" "Health check failed"
            fi
        fi
        
        # Check resource usage
        if [ -n "$pod" ]; then
            local metrics=$(kubectl top pod $pod -n $NAMESPACE --context=$CLUSTER_CONTEXT --no-headers 2>/dev/null || echo "")
            if [ -n "$metrics" ]; then
                local cpu=$(echo "$metrics" | awk '{print $2}')
                local memory=$(echo "$metrics" | awk '{print $3}')
                log "Resource usage for $service: CPU=$cpu, Memory=$memory"
            fi
        fi
    done
}

# Database validation
validate_databases() {
    echo -e "\n${BLUE}=== Database Validation ===${NC}"
    
    # PostgreSQL
    local pg_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$pg_pod" ]; then
        if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- pg_isready -U grill_stats >/dev/null 2>&1; then
            check_status "POSTGRESQL_CONNECTIVITY" "GO" "PostgreSQL responsive"
            
            # Check database and tables
            local table_count=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- psql -U grill_stats -d grill_stats -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ' || echo "0")
            if [ "$table_count" -gt 0 ]; then
                check_status "POSTGRESQL_SCHEMA" "GO" "$table_count tables found in database"
            else
                check_status "POSTGRESQL_SCHEMA" "WARNING" "No tables found in database"
            fi
            
            # Check connection pool
            local connections=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- psql -U grill_stats -d grill_stats -t -c "SELECT COUNT(*) FROM pg_stat_activity;" 2>/dev/null | tr -d ' ' || echo "0")
            check_status "POSTGRESQL_CONNECTIONS" "GO" "$connections active connections"
        else
            check_status "POSTGRESQL_CONNECTIVITY" "NO-GO" "PostgreSQL not responsive"
        fi
    else
        check_status "POSTGRESQL_CONNECTIVITY" "NO-GO" "PostgreSQL pod not found"
    fi
    
    # InfluxDB
    local influx_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=influxdb -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$influx_pod" ]; then
        if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx ping >/dev/null 2>&1; then
            check_status "INFLUXDB_CONNECTIVITY" "GO" "InfluxDB responsive"
            
            # Check buckets
            local buckets=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx bucket list --json 2>/dev/null || echo "[]")
            local bucket_count=$(echo "$buckets" | jq '[.[] | select(.name | contains("grill-stats"))] | length')
            if [ "$bucket_count" -gt 0 ]; then
                check_status "INFLUXDB_BUCKETS" "GO" "$bucket_count grill-stats buckets found"
            else
                check_status "INFLUXDB_BUCKETS" "WARNING" "No grill-stats buckets found"
            fi
        else
            check_status "INFLUXDB_CONNECTIVITY" "NO-GO" "InfluxDB not responsive"
        fi
    else
        check_status "INFLUXDB_CONNECTIVITY" "NO-GO" "InfluxDB pod not found"
    fi
    
    # Redis
    local redis_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$redis_pod" ]; then
        if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli ping >/dev/null 2>&1; then
            check_status "REDIS_CONNECTIVITY" "GO" "Redis responsive"
            
            # Check memory and keys
            local info=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli info memory 2>/dev/null || echo "")
            local memory=$(echo "$info" | grep used_memory_human | cut -d: -f2 | tr -d '\r' || echo "unknown")
            local keys=$(kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-cli dbsize 2>/dev/null | awk '{print $2}' || echo "0")
            
            check_status "REDIS_STATUS" "GO" "Memory: $memory, Keys: $keys"
        else
            check_status "REDIS_CONNECTIVITY" "NO-GO" "Redis not responsive"
        fi
    else
        check_status "REDIS_CONNECTIVITY" "NO-GO" "Redis pod not found"
    fi
}

# Network and ingress validation
validate_network() {
    echo -e "\n${BLUE}=== Network and Ingress Validation ===${NC}"
    
    # Check ingress routes
    local routes=$(kubectl get ingressroute -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local route_count=$(echo "$routes" | jq '.items | length')
    
    if [ "$route_count" -gt 0 ]; then
        check_status "INGRESS_ROUTES" "GO" "$route_count ingress routes configured"
        
        # Check each route
        echo "$routes" | jq -r '.items[] | .metadata.name' | while read -r route; do
            log "Ingress route configured: $route"
        done
    else
        check_status "INGRESS_ROUTES" "NO-GO" "No ingress routes found"
    fi
    
    # Check certificates
    local certs=$(kubectl get certificate -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local valid_certs=$(echo "$certs" | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length')
    
    if [ "$valid_certs" -gt 0 ]; then
        check_status "TLS_CERTIFICATES" "GO" "$valid_certs valid certificates"
    else
        check_status "TLS_CERTIFICATES" "WARNING" "No valid certificates found"
    fi
    
    # Network policies
    local policies=$(kubectl get networkpolicy -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local policy_count=$(echo "$policies" | jq '.items | length')
    
    if [ "$policy_count" -gt 0 ]; then
        check_status "NETWORK_POLICIES" "GO" "$policy_count network policies active"
        
        # Verify key policies
        local required_policies=("default-deny" "allow-ingress" "allow-prometheus")
        for policy in "${required_policies[@]}"; do
            if echo "$policies" | jq -r '.items[].metadata.name' | grep -q "$policy"; then
                log "Required network policy found: $policy"
            else
                log "WARNING: Required network policy missing: $policy"
            fi
        done
    else
        check_status "NETWORK_POLICIES" "WARNING" "No network policies found"
    fi
    
    # Service mesh check (if applicable)
    if kubectl get namespace istio-system --context=$CLUSTER_CONTEXT >/dev/null 2>&1; then
        local sidecars=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq '[.items[].spec.containers[] | select(.name=="istio-proxy")] | length')
        if [ "$sidecars" -gt 0 ]; then
            check_status "SERVICE_MESH" "GO" "$sidecars Istio sidecars running"
        fi
    fi
}

# Monitoring validation
validate_monitoring() {
    echo -e "\n${BLUE}=== Monitoring and Observability Validation ===${NC}"
    
    # ServiceMonitors
    local monitors=$(kubectl get servicemonitor -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local monitor_count=$(echo "$monitors" | jq '.items | length')
    
    if [ "$monitor_count" -gt 0 ]; then
        check_status "SERVICE_MONITORS" "GO" "$monitor_count service monitors configured"
        
        # Check each monitor's targets
        echo "$monitors" | jq -r '.items[] | .metadata.name' | while read -r monitor; do
            log "ServiceMonitor configured: $monitor"
        done
    else
        check_status "SERVICE_MONITORS" "WARNING" "No service monitors found"
    fi
    
    # PrometheusRules
    local rules=$(kubectl get prometheusrule -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local rule_count=$(echo "$rules" | jq '.items | length')
    
    if [ "$rule_count" -gt 0 ]; then
        check_status "PROMETHEUS_RULES" "GO" "$rule_count prometheus rules configured"
        
        # Count alert rules
        local alert_count=$(echo "$rules" | jq '[.items[].spec.groups[].rules[] | select(.alert)] | length')
        log "Total alert rules defined: $alert_count"
    else
        check_status "PROMETHEUS_RULES" "WARNING" "No prometheus rules found"
    fi
    
    # Check metrics endpoint accessibility
    local services=("auth-service" "device-service" "temperature-service")
    for service in "${services[@]}"; do
        local pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=$service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$pod" ]; then
            if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pod -- wget -q --spider "http://localhost:8080/metrics" 2>/dev/null; then
                log "Metrics endpoint accessible for $service"
            fi
        fi
    done
    
    # Grafana dashboards
    local dashboards=$(kubectl get configmap -n $NAMESPACE --context=$CLUSTER_CONTEXT -l grafana_dashboard=1 -o json 2>/dev/null || echo '{"items":[]}')
    local dashboard_count=$(echo "$dashboards" | jq '.items | length')
    
    if [ "$dashboard_count" -gt 0 ]; then
        check_status "GRAFANA_DASHBOARDS" "GO" "$dashboard_count Grafana dashboards configured"
    else
        check_status "GRAFANA_DASHBOARDS" "WARNING" "No Grafana dashboards found"
    fi
}

# External integrations validation
validate_external() {
    echo -e "\n${BLUE}=== External Integrations Validation ===${NC}"
    
    # Vault connectivity
    local vault_endpoint="https://vault.vault.svc.cluster.local:8200"
    local encryption_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=encryption-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -n "$encryption_pod" ]; then
        if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $encryption_pod -- wget -q --spider --no-check-certificate "$vault_endpoint/v1/sys/health" 2>/dev/null; then
            check_status "VAULT_CONNECTIVITY" "GO" "Vault accessible from encryption service"
        else
            check_status "VAULT_CONNECTIVITY" "WARNING" "Vault connectivity issues"
        fi
    fi
    
    # 1Password Connect
    local op_secrets=$(kubectl get onepassworditem -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local secret_count=$(echo "$op_secrets" | jq '.items | length')
    
    if [ "$secret_count" -gt 0 ]; then
        check_status "ONEPASSWORD_SECRETS" "GO" "$secret_count 1Password secrets configured"
        
        # Check sync status
        local synced=$(echo "$op_secrets" | jq '[.items[] | select(.status.conditions[] | select(.type=="Synced" and .status=="True"))] | length')
        if [ "$synced" -eq "$secret_count" ]; then
            check_status "ONEPASSWORD_SYNC" "GO" "All secrets synced successfully"
        else
            check_status "ONEPASSWORD_SYNC" "WARNING" "Only $synced/$secret_count secrets synced"
        fi
    else
        check_status "ONEPASSWORD_SECRETS" "WARNING" "No 1Password secrets found"
    fi
    
    # ArgoCD applications
    local argo_apps=$(kubectl get application -n argocd --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local grill_apps=$(echo "$argo_apps" | jq '[.items[] | select(.metadata.name | contains("grill-stats"))]')
    local app_count=$(echo "$grill_apps" | jq 'length')
    
    if [ "$app_count" -gt 0 ]; then
        local healthy=$(echo "$grill_apps" | jq '[.[] | select(.status.health.status=="Healthy")] | length')
        local synced=$(echo "$grill_apps" | jq '[.[] | select(.status.sync.status=="Synced")] | length')
        
        if [ "$healthy" -eq "$app_count" ] && [ "$synced" -eq "$app_count" ]; then
            check_status "ARGOCD_APPS" "GO" "$app_count ArgoCD apps healthy and synced"
        else
            check_status "ARGOCD_APPS" "WARNING" "$healthy/$app_count healthy, $synced/$app_count synced"
        fi
    else
        check_status "ARGOCD_APPS" "WARNING" "No grill-stats ArgoCD applications found"
    fi
    
    # ThermoWorks API connectivity test
    local device_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=device-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$device_pod" ]; then
        # Check if the service can reach external API
        if kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $device_pod -- wget -q --spider https://api.thermoworks.com 2>/dev/null; then
            check_status "THERMOWORKS_API" "GO" "ThermoWorks API reachable"
        else
            check_status "THERMOWORKS_API" "WARNING" "Cannot reach ThermoWorks API"
        fi
    fi
}

# Backup validation
validate_backups() {
    echo -e "\n${BLUE}=== Backup System Validation ===${NC}"
    
    # Check backup CronJobs
    local backup_jobs=$(kubectl get cronjob -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local job_names=$(echo "$backup_jobs" | jq -r '.items[] | select(.metadata.name | contains("backup")) | .metadata.name')
    local job_count=$(echo "$job_names" | grep -c . || echo "0")
    
    if [ "$job_count" -gt 0 ]; then
        check_status "BACKUP_CRONJOBS" "GO" "$job_count backup jobs configured"
        
        # Check each backup job
        echo "$job_names" | while read -r job; do
            local schedule=$(echo "$backup_jobs" | jq -r ".items[] | select(.metadata.name==\"$job\") | .spec.schedule")
            local suspend=$(echo "$backup_jobs" | jq -r ".items[] | select(.metadata.name==\"$job\") | .spec.suspend // false")
            
            if [ "$suspend" == "false" ]; then
                log "Backup job $job scheduled: $schedule"
            else
                log "WARNING: Backup job $job is suspended"
            fi
        done
    else
        check_status "BACKUP_CRONJOBS" "WARNING" "No backup jobs found"
    fi
    
    # Check recent backup executions
    local recent_jobs=$(kubectl get job -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local successful_backups=$(echo "$recent_jobs" | jq '[.items[] | select(.metadata.name | contains("backup")) | select(.status.succeeded==1)] | length')
    local failed_backups=$(echo "$recent_jobs" | jq '[.items[] | select(.metadata.name | contains("backup")) | select(.status.failed and .status.failed>0)] | length')
    
    if [ "$successful_backups" -gt 0 ]; then
        check_status "RECENT_BACKUPS" "GO" "$successful_backups successful recent backups"
    else
        check_status "RECENT_BACKUPS" "WARNING" "No recent successful backups"
    fi
    
    if [ "$failed_backups" -gt 0 ]; then
        check_status "BACKUP_FAILURES" "WARNING" "$failed_backups failed backup jobs detected"
    fi
    
    # Check backup storage
    local backup_pvcs=$(kubectl get pvc -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local backup_storage=$(echo "$backup_pvcs" | jq '[.items[] | select(.metadata.name | contains("backup"))] | length')
    
    if [ "$backup_storage" -gt 0 ]; then
        check_status "BACKUP_STORAGE" "GO" "$backup_storage backup storage volumes configured"
    fi
}

# End-to-end functionality tests
validate_e2e() {
    echo -e "\n${BLUE}=== End-to-End Functionality Tests ===${NC}"
    
    # Get service URLs
    local base_url=""
    local ingress=$(kubectl get ingressroute -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null | jq -r '.items[0].spec.routes[0].match' | grep -oP 'Host\(`\K[^`]+' || echo "")
    
    if [ -n "$ingress" ]; then
        base_url="https://$ingress"
        log "Testing against ingress URL: $base_url"
    else
        log "No ingress found, skipping E2E tests"
        check_status "E2E_TESTS" "WARNING" "Cannot perform E2E tests without ingress"
        return
    fi
    
    # Test authentication endpoint
    local auth_response=$(curl -sf --max-time $TIMEOUT "$base_url/api/auth/health" 2>/dev/null || echo "")
    if [ -n "$auth_response" ]; then
        check_status "E2E_AUTH" "GO" "Authentication service accessible"
    else
        check_status "E2E_AUTH" "WARNING" "Authentication service not accessible externally"
    fi
    
    # Test device listing
    local device_response=$(curl -sf --max-time $TIMEOUT "$base_url/api/devices" 2>/dev/null || echo "")
    if [ -n "$device_response" ]; then
        check_status "E2E_DEVICES" "GO" "Device API accessible"
    else
        check_status "E2E_DEVICES" "WARNING" "Device API not accessible externally"
    fi
    
    # Test web UI
    local ui_response=$(curl -sf --max-time $TIMEOUT -I "$base_url" 2>/dev/null | head -n1 || echo "")
    if echo "$ui_response" | grep -q "200\|301\|302"; then
        check_status "E2E_WEB_UI" "GO" "Web UI accessible"
    else
        check_status "E2E_WEB_UI" "WARNING" "Web UI not accessible externally"
    fi
}

# Performance validation
validate_performance() {
    echo -e "\n${BLUE}=== Performance Validation ===${NC}"
    
    # Check HPA status
    local hpas=$(kubectl get hpa -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local hpa_count=$(echo "$hpas" | jq '.items | length')
    
    if [ "$hpa_count" -gt 0 ]; then
        check_status "HPA_CONFIGURED" "GO" "$hpa_count Horizontal Pod Autoscalers configured"
        
        # Check HPA metrics
        echo "$hpas" | jq -r '.items[] | .metadata.name + ": Current/Target = " + (.status.currentReplicas|tostring) + "/" + (.spec.minReplicas|tostring) + "-" + (.spec.maxReplicas|tostring)' | while read -r hpa_status; do
            log "HPA Status: $hpa_status"
        done
    else
        check_status "HPA_CONFIGURED" "WARNING" "No Horizontal Pod Autoscalers found"
    fi
    
    # Check PDB status
    local pdbs=$(kubectl get pdb -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local pdb_count=$(echo "$pdbs" | jq '.items | length')
    
    if [ "$pdb_count" -gt 0 ]; then
        check_status "PDB_CONFIGURED" "GO" "$pdb_count Pod Disruption Budgets configured"
    else
        check_status "PDB_CONFIGURED" "WARNING" "No Pod Disruption Budgets found"
    fi
    
    # Response time checks
    if [ ${#RESPONSE_TIMES[@]} -gt 0 ]; then
        echo -e "\n${PURPLE}Response Times:${NC}"
        for service in "${!RESPONSE_TIMES[@]}"; do
            local time="${RESPONSE_TIMES[$service]}"
            if [ "$time" -lt 1000 ]; then
                echo -e "  ${GREEN}✓${NC} $service: ${time}ms"
            elif [ "$time" -lt 3000 ]; then
                echo -e "  ${YELLOW}⚠${NC} $service: ${time}ms"
            else
                echo -e "  ${RED}✗${NC} $service: ${time}ms"
            fi
        done
    fi
}

# Security validation
validate_security() {
    echo -e "\n${BLUE}=== Security Validation ===${NC}"
    
    # Check security contexts
    local deployments=$(kubectl get deployment -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local secured_deployments=$(echo "$deployments" | jq '[.items[] | select(.spec.template.spec.securityContext or .spec.template.spec.containers[].securityContext)] | length')
    local total_deployments=$(echo "$deployments" | jq '.items | length')
    
    if [ "$secured_deployments" -eq "$total_deployments" ] && [ "$total_deployments" -gt 0 ]; then
        check_status "SECURITY_CONTEXTS" "GO" "All deployments have security contexts"
    else
        check_status "SECURITY_CONTEXTS" "WARNING" "Only $secured_deployments/$total_deployments deployments have security contexts"
    fi
    
    # Check RBAC
    local service_accounts=$(kubectl get serviceaccount -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local sa_count=$(echo "$service_accounts" | jq '.items | length')
    
    if [ "$sa_count" -gt 1 ]; then  # More than just the default SA
        check_status "SERVICE_ACCOUNTS" "GO" "$sa_count service accounts configured"
    else
        check_status "SERVICE_ACCOUNTS" "WARNING" "Using default service account"
    fi
    
    # Check secrets encryption
    local sealed_secrets=$(kubectl get sealedsecret -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json 2>/dev/null || echo '{"items":[]}')
    local sealed_count=$(echo "$sealed_secrets" | jq '.items | length')
    
    if [ "$sealed_count" -gt 0 ]; then
        check_status "SEALED_SECRETS" "GO" "$sealed_count sealed secrets in use"
    fi
}

# Generate summary report
generate_summary() {
    echo -e "\n${BLUE}=== DEPLOYMENT VALIDATION SUMMARY ===${NC}"
    echo -e "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo -e "Cluster: $CLUSTER_CONTEXT"
    echo -e "Namespace: $NAMESPACE"
    echo -e "\nTotal Checks: $TOTAL_CHECKS"
    echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
    echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
    echo -e "${YELLOW}Warnings: $WARNING_CHECKS${NC}"
    
    local success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    echo -e "\nSuccess Rate: $success_rate%"
    
    # Generate JSON report
    cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cluster": "$CLUSTER_CONTEXT",
  "namespace": "$NAMESPACE",
  "summary": {
    "total_checks": $TOTAL_CHECKS,
    "passed": $PASSED_CHECKS,
    "failed": $FAILED_CHECKS,
    "warnings": $WARNING_CHECKS,
    "success_rate": $success_rate
  },
  "categories": {
    "cluster": {
      "status": "${SERVICE_STATUS[CLUSTER_CONNECTIVITY]:-UNKNOWN}",
      "nodes": "${SERVICE_STATUS[CLUSTER_NODES]:-UNKNOWN}",
      "namespace": "${SERVICE_STATUS[NAMESPACE]:-UNKNOWN}"
    },
    "services": {
      "auth": "${SERVICE_STATUS[AUTH-SERVICE_DEPLOYMENT]:-UNKNOWN}",
      "device": "${SERVICE_STATUS[DEVICE-SERVICE_DEPLOYMENT]:-UNKNOWN}",
      "temperature": "${SERVICE_STATUS[TEMPERATURE-SERVICE_DEPLOYMENT]:-UNKNOWN}",
      "historical": "${SERVICE_STATUS[HISTORICAL-DATA-SERVICE_DEPLOYMENT]:-UNKNOWN}",
      "encryption": "${SERVICE_STATUS[ENCRYPTION-SERVICE_DEPLOYMENT]:-UNKNOWN}",
      "web_ui": "${SERVICE_STATUS[WEB-UI-SERVICE_DEPLOYMENT]:-UNKNOWN}"
    },
    "databases": {
      "postgresql": "${SERVICE_STATUS[POSTGRESQL_CONNECTIVITY]:-UNKNOWN}",
      "influxdb": "${SERVICE_STATUS[INFLUXDB_CONNECTIVITY]:-UNKNOWN}",
      "redis": "${SERVICE_STATUS[REDIS_CONNECTIVITY]:-UNKNOWN}"
    },
    "infrastructure": {
      "ingress": "${SERVICE_STATUS[INGRESS_ROUTES]:-UNKNOWN}",
      "certificates": "${SERVICE_STATUS[TLS_CERTIFICATES]:-UNKNOWN}",
      "monitoring": "${SERVICE_STATUS[SERVICE_MONITORS]:-UNKNOWN}",
      "backups": "${SERVICE_STATUS[BACKUP_CRONJOBS]:-UNKNOWN}"
    },
    "integrations": {
      "vault": "${SERVICE_STATUS[VAULT_CONNECTIVITY]:-UNKNOWN}",
      "onepassword": "${SERVICE_STATUS[ONEPASSWORD_SECRETS]:-UNKNOWN}",
      "argocd": "${SERVICE_STATUS[ARGOCD_APPS]:-UNKNOWN}",
      "thermoworks": "${SERVICE_STATUS[THERMOWORKS_API]:-UNKNOWN}"
    }
  },
  "response_times": {
EOF
    
    if [ ${#RESPONSE_TIMES[@]} -gt 0 ]; then
        local first=true
        for service in "${!RESPONSE_TIMES[@]}"; do
            if [ "$first" = false ]; then
                echo "," >> "$RESULTS_FILE"
            fi
            echo -n "    \"$service\": ${RESPONSE_TIMES[$service]}" >> "$RESULTS_FILE"
            first=false
        done
        echo "" >> "$RESULTS_FILE"
    fi
    
    cat >> "$RESULTS_FILE" << EOF
  },
  "services": {
EOF
    
    local first=true
    for service in "${!SERVICE_STATUS[@]}"; do
        if [ "$first" = false ]; then
            echo "," >> "$RESULTS_FILE"
        fi
        echo -n "    \"$service\": \"${SERVICE_STATUS[$service]}\"" >> "$RESULTS_FILE"
        first=false
    done
    
    echo -e "\n  }\n}" >> "$RESULTS_FILE"
    
    echo -e "\n${PURPLE}Reports:${NC}"
    echo -e "  Detailed results: $RESULTS_FILE"
    echo -e "  Full log: $LOG_FILE"
    
    # Deployment status
    if [ "$FAILED_CHECKS" -eq 0 ]; then
        echo -e "\n${GREEN}🎉 PRODUCTION DEPLOYMENT: GO${NC}"
        echo -e "All critical checks passed. System is ready for production use."
        return 0
    elif [ "$FAILED_CHECKS" -le 2 ] && [ "$success_rate" -ge 90 ]; then
        echo -e "\n${YELLOW}⚠️  PRODUCTION DEPLOYMENT: CONDITIONAL GO${NC}"
        echo -e "Minor issues detected. Review warnings before proceeding."
        return 0
    else
        echo -e "\n${RED}❌ PRODUCTION DEPLOYMENT: NO-GO${NC}"
        echo -e "Critical issues detected. Address failures before production use."
        echo -e "\nFailed checks:"
        for service in "${!SERVICE_STATUS[@]}"; do
            if [ "${SERVICE_STATUS[$service]}" == "NO-GO" ]; then
                echo -e "  - $service"
            fi
        done
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        Grill Stats Production Deployment Validation          ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "Cluster: ${PURPLE}$CLUSTER_CONTEXT${NC}"
    echo -e "Namespace: ${PURPLE}$NAMESPACE${NC}"
    echo -e "Started: $(date)"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Core validations
    validate_cluster || exit 1
    validate_services
    validate_databases
    validate_network
    validate_monitoring
    validate_external
    validate_backups
    
    # Additional validations
    validate_security
    validate_performance
    validate_e2e
    
    # Generate final report
    generate_summary
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

# Run main function
main "$@"