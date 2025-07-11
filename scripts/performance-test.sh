#!/bin/bash
# Performance Testing Script for Grill Stats Platform
# Tests load, latency, and resource utilization

set -e

NAMESPACE="grill-stats"
CLUSTER_CONTEXT="prod-lab"
RESULTS_DIR="/tmp/grill-stats-perf-$(date +%Y%m%d_%H%M%S)"
DURATION=300  # 5 minutes
CONCURRENT_USERS=10

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Performance metrics
declare -A METRICS
declare -A THRESHOLDS

# Initialize thresholds
THRESHOLDS[CPU_LIMIT]=80
THRESHOLDS[MEMORY_LIMIT]=80
THRESHOLDS[RESPONSE_TIME]=2000
THRESHOLDS[ERROR_RATE]=5

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$RESULTS_DIR/performance.log"
}

setup_test_environment() {
    echo -e "${BLUE}Setting up performance test environment...${NC}"
    mkdir -p "$RESULTS_DIR"
    
    # Get service endpoints
    local ingress=$(kubectl get ingressroute -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq -r '.items[0].spec.routes[0].match' | grep -oP 'Host\(`\K[^`]+' || echo "")
    
    if [ -n "$ingress" ]; then
        METRICS[BASE_URL]="https://$ingress"
        log "Testing against: ${METRICS[BASE_URL]}"
    else
        # Use port-forward for internal testing
        kubectl port-forward -n $NAMESPACE svc/web-ui-service 8080:80 --context=$CLUSTER_CONTEXT &
        METRICS[BASE_URL]="http://localhost:8080"
        METRICS[PORT_FORWARD_PID]=$!
        log "Using port-forward for testing"
        sleep 5
    fi
}

cleanup_test_environment() {
    if [ -n "${METRICS[PORT_FORWARD_PID]}" ]; then
        kill "${METRICS[PORT_FORWARD_PID]}" 2>/dev/null || true
    fi
}

# Baseline resource usage
collect_baseline_metrics() {
    echo -e "${BLUE}Collecting baseline metrics...${NC}"
    
    # CPU and Memory usage
    kubectl top pods -n $NAMESPACE --context=$CLUSTER_CONTEXT --no-headers > "$RESULTS_DIR/baseline-resources.txt"
    
    # Network metrics
    kubectl get pods -n $NAMESPACE --context=$CLUSTER_CONTEXT -o json | jq -r '.items[] | select(.status.phase=="Running") | "\(.metadata.name) \(.status.podIP)"' > "$RESULTS_DIR/pod-ips.txt"
    
    log "Baseline metrics collected"
}

# Load testing with different patterns
run_load_tests() {
    echo -e "${BLUE}Running load tests...${NC}"
    
    # Test 1: Steady load
    echo -e "${YELLOW}Test 1: Steady load ($CONCURRENT_USERS concurrent users)${NC}"
    run_steady_load
    
    # Test 2: Spike load
    echo -e "${YELLOW}Test 2: Spike load (burst to 50 users)${NC}"
    run_spike_load
    
    # Test 3: Device polling simulation
    echo -e "${YELLOW}Test 3: Device polling simulation${NC}"
    run_device_polling_test
    
    # Test 4: Real-time data streaming
    echo -e "${YELLOW}Test 4: Real-time data streaming${NC}"
    run_streaming_test
}

run_steady_load() {
    local test_duration=$((DURATION / 4))
    local output_file="$RESULTS_DIR/steady-load.txt"
    
    # Apache Bench test
    if command -v ab >/dev/null 2>&1; then
        ab -t $test_duration -c $CONCURRENT_USERS -g "$RESULTS_DIR/steady-load.gnuplot" \
           "${METRICS[BASE_URL]}/api/devices" > "$output_file" 2>&1
        
        # Parse results
        local rps=$(grep "Requests per second" "$output_file" | awk '{print $4}')
        local mean_time=$(grep "Time per request" "$output_file" | head -1 | awk '{print $4}')
        local failed=$(grep "Failed requests" "$output_file" | awk '{print $3}')
        
        METRICS[STEADY_RPS]=$rps
        METRICS[STEADY_MEAN_TIME]=$mean_time
        METRICS[STEADY_FAILED]=$failed
        
        log "Steady load - RPS: $rps, Mean time: ${mean_time}ms, Failed: $failed"
    else
        log "Apache Bench not available, using curl-based test"
        run_curl_load_test $test_duration $CONCURRENT_USERS "steady"
    fi
}

run_spike_load() {
    local output_file="$RESULTS_DIR/spike-load.txt"
    
    # Spike test using curl
    echo "Starting spike load test..." > "$output_file"
    
    # Ramp up quickly
    for i in $(seq 1 50); do
        curl -s -w "%{http_code},%{time_total}\n" -o /dev/null "${METRICS[BASE_URL]}/api/devices" &
    done
    
    # Wait for all requests to complete
    wait
    
    # Collect metrics during spike
    kubectl top pods -n $NAMESPACE --context=$CLUSTER_CONTEXT --no-headers > "$RESULTS_DIR/spike-resources.txt"
    
    log "Spike load test completed"
}

run_device_polling_test() {
    local output_file="$RESULTS_DIR/device-polling.txt"
    
    # Simulate device polling pattern
    echo "Device polling test results:" > "$output_file"
    
    # Get device list first
    local devices=$(curl -s "${METRICS[BASE_URL]}/api/devices" | jq -r '.[].id' 2>/dev/null || echo "")
    
    if [ -n "$devices" ]; then
        echo "$devices" | while read -r device_id; do
            # Poll each device every 30 seconds
            for i in $(seq 1 10); do
                local start_time=$(date +%s%3N)
                local response=$(curl -s -w "%{http_code}" "${METRICS[BASE_URL]}/api/devices/$device_id/temperature")
                local end_time=$(date +%s%3N)
                local duration=$((end_time - start_time))
                
                echo "$device_id,$response,$duration" >> "$output_file"
                sleep 30
            done &
        done
        wait
    else
        log "No devices found for polling test"
    fi
}

run_streaming_test() {
    local output_file="$RESULTS_DIR/streaming-test.txt"
    
    # Test Server-Sent Events or WebSocket connections
    echo "Real-time streaming test:" > "$output_file"
    
    # Multiple concurrent connections
    for i in $(seq 1 5); do
        (
            timeout 60 curl -s -N "${METRICS[BASE_URL]}/api/stream/temperature" | \
            while read -r line; do
                echo "$(date +%s%3N): $line" >> "$output_file"
            done
        ) &
    done
    
    wait
    log "Streaming test completed"
}

run_curl_load_test() {
    local duration=$1
    local concurrent=$2
    local test_name=$3
    local output_file="$RESULTS_DIR/curl-${test_name}.txt"
    
    echo "Curl load test - Duration: ${duration}s, Concurrent: $concurrent" > "$output_file"
    
    local end_time=$(($(date +%s) + duration))
    
    while [ $(date +%s) -lt $end_time ]; do
        for i in $(seq 1 $concurrent); do
            curl -s -w "%{http_code},%{time_total},%{size_download}\n" \
                 -o /dev/null "${METRICS[BASE_URL]}/api/devices" >> "$output_file" &
        done
        wait
        sleep 1
    done
    
    # Calculate statistics
    local total_requests=$(grep -c "," "$output_file")
    local successful=$(grep -c "200," "$output_file")
    local avg_time=$(awk -F',' '{sum+=$2; count++} END {print sum/count}' "$output_file")
    
    METRICS[${test_name^^}_TOTAL]=$total_requests
    METRICS[${test_name^^}_SUCCESS]=$successful
    METRICS[${test_name^^}_AVG_TIME]=$avg_time
    
    log "Curl $test_name test - Total: $total_requests, Success: $successful, Avg time: ${avg_time}s"
}

# Resource monitoring during tests
monitor_resources() {
    echo -e "${BLUE}Monitoring resource usage...${NC}"
    
    local monitor_file="$RESULTS_DIR/resource-monitor.txt"
    echo "timestamp,pod,cpu,memory" > "$monitor_file"
    
    # Monitor for test duration
    local end_time=$(($(date +%s) + DURATION))
    
    while [ $(date +%s) -lt $end_time ]; do
        kubectl top pods -n $NAMESPACE --context=$CLUSTER_CONTEXT --no-headers | while read -r line; do
            local pod=$(echo "$line" | awk '{print $1}')
            local cpu=$(echo "$line" | awk '{print $2}')
            local memory=$(echo "$line" | awk '{print $3}')
            echo "$(date +%s),$pod,$cpu,$memory" >> "$monitor_file"
        done
        sleep 30
    done &
    
    METRICS[MONITOR_PID]=$!
}

# Database performance testing
test_database_performance() {
    echo -e "${BLUE}Testing database performance...${NC}"
    
    # PostgreSQL performance
    test_postgresql_performance
    
    # InfluxDB performance
    test_influxdb_performance
    
    # Redis performance
    test_redis_performance
}

test_postgresql_performance() {
    local pg_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
    local output_file="$RESULTS_DIR/postgresql-performance.txt"
    
    if [ -n "$pg_pod" ]; then
        echo "PostgreSQL Performance Test:" > "$output_file"
        
        # Connection test
        local start_time=$(date +%s%3N)
        kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- psql -U grill_stats -d grill_stats -c "SELECT 1;" >> "$output_file"
        local end_time=$(date +%s%3N)
        local connect_time=$((end_time - start_time))
        
        # Query performance
        kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $pg_pod -- psql -U grill_stats -d grill_stats -c "EXPLAIN ANALYZE SELECT * FROM devices LIMIT 100;" >> "$output_file"
        
        METRICS[PG_CONNECT_TIME]=$connect_time
        log "PostgreSQL connect time: ${connect_time}ms"
    fi
}

test_influxdb_performance() {
    local influx_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=influxdb -o jsonpath='{.items[0].metadata.name}')
    local output_file="$RESULTS_DIR/influxdb-performance.txt"
    
    if [ -n "$influx_pod" ]; then
        echo "InfluxDB Performance Test:" > "$output_file"
        
        # Write performance test
        local start_time=$(date +%s%3N)
        kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx write --bucket grill-stats --precision s "temperature,device=test-device value=25.5 $(date +%s)" >> "$output_file"
        local end_time=$(date +%s%3N)
        local write_time=$((end_time - start_time))
        
        # Read performance test
        start_time=$(date +%s%3N)
        kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $influx_pod -- influx query 'from(bucket:"grill-stats") |> range(start: -1h) |> limit(n: 100)' >> "$output_file"
        end_time=$(date +%s%3N)
        local read_time=$((end_time - start_time))
        
        METRICS[INFLUX_WRITE_TIME]=$write_time
        METRICS[INFLUX_READ_TIME]=$read_time
        log "InfluxDB write: ${write_time}ms, read: ${read_time}ms"
    fi
}

test_redis_performance() {
    local redis_pod=$(kubectl get pod -n $NAMESPACE --context=$CLUSTER_CONTEXT -l app=redis -o jsonpath='{.items[0].metadata.name}')
    local output_file="$RESULTS_DIR/redis-performance.txt"
    
    if [ -n "$redis_pod" ]; then
        echo "Redis Performance Test:" > "$output_file"
        
        # Benchmark test
        kubectl exec -n $NAMESPACE --context=$CLUSTER_CONTEXT $redis_pod -- redis-benchmark -n 1000 -c 10 -t set,get >> "$output_file"
        
        log "Redis benchmark completed"
    fi
}

# API endpoint testing
test_api_endpoints() {
    echo -e "${BLUE}Testing API endpoints...${NC}"
    
    local endpoints=(
        "/api/auth/health"
        "/api/devices"
        "/api/devices/health"
        "/api/temperature/health"
        "/api/historical/health"
        "/api/encryption/health"
        "/health"
    )
    
    local endpoint_file="$RESULTS_DIR/api-endpoints.txt"
    echo "endpoint,status,time,size" > "$endpoint_file"
    
    for endpoint in "${endpoints[@]}"; do
        local start_time=$(date +%s%3N)
        local response=$(curl -s -w "%{http_code},%{time_total},%{size_download}" -o /dev/null "${METRICS[BASE_URL]}$endpoint")
        local end_time=$(date +%s%3N)
        local total_time=$((end_time - start_time))
        
        echo "$endpoint,$response,$total_time" >> "$endpoint_file"
        log "API test $endpoint: $response"
    done
}

# Analyze results and generate report
analyze_results() {
    echo -e "${BLUE}Analyzing performance results...${NC}"
    
    # Stop resource monitoring
    if [ -n "${METRICS[MONITOR_PID]}" ]; then
        kill "${METRICS[MONITOR_PID]}" 2>/dev/null || true
    fi
    
    # Resource utilization analysis
    analyze_resource_usage
    
    # Response time analysis
    analyze_response_times
    
    # Error rate analysis
    analyze_error_rates
    
    # Generate performance report
    generate_performance_report
}

analyze_resource_usage() {
    local resource_file="$RESULTS_DIR/resource-monitor.txt"
    
    if [ -f "$resource_file" ]; then
        echo -e "${YELLOW}Resource Usage Analysis:${NC}"
        
        # CPU usage
        local max_cpu=$(awk -F',' 'NR>1 {gsub(/[^0-9]/, "", $3); if($3>max) max=$3} END {print max}' "$resource_file")
        local avg_cpu=$(awk -F',' 'NR>1 {gsub(/[^0-9]/, "", $3); sum+=$3; count++} END {print sum/count}' "$resource_file")
        
        # Memory usage
        local max_memory=$(awk -F',' 'NR>1 {gsub(/[^0-9]/, "", $4); if($4>max) max=$4} END {print max}' "$resource_file")
        local avg_memory=$(awk -F',' 'NR>1 {gsub(/[^0-9]/, "", $4); sum+=$4; count++} END {print sum/count}' "$resource_file")
        
        METRICS[MAX_CPU]=$max_cpu
        METRICS[AVG_CPU]=$avg_cpu
        METRICS[MAX_MEMORY]=$max_memory
        METRICS[AVG_MEMORY]=$avg_memory
        
        log "CPU - Max: ${max_cpu}%, Avg: ${avg_cpu}%"
        log "Memory - Max: ${max_memory}Mi, Avg: ${avg_memory}Mi"
    fi
}

analyze_response_times() {
    local endpoint_file="$RESULTS_DIR/api-endpoints.txt"
    
    if [ -f "$endpoint_file" ]; then
        echo -e "${YELLOW}Response Time Analysis:${NC}"
        
        # Calculate percentiles
        local p95=$(awk -F',' 'NR>1 {print $3}' "$endpoint_file" | sort -n | awk '{all[NR] = $0} END{print all[int(NR*0.95)]}')
        local p99=$(awk -F',' 'NR>1 {print $3}' "$endpoint_file" | sort -n | awk '{all[NR] = $0} END{print all[int(NR*0.99)]}')
        
        METRICS[P95_RESPONSE_TIME]=$p95
        METRICS[P99_RESPONSE_TIME]=$p99
        
        log "Response times - P95: ${p95}ms, P99: ${p99}ms"
    fi
}

analyze_error_rates() {
    local endpoint_file="$RESULTS_DIR/api-endpoints.txt"
    
    if [ -f "$endpoint_file" ]; then
        echo -e "${YELLOW}Error Rate Analysis:${NC}"
        
        local total_requests=$(wc -l < "$endpoint_file")
        local error_requests=$(awk -F',' '$2 !~ /^2/ {print $2}' "$endpoint_file" | wc -l)
        local error_rate=$((error_requests * 100 / total_requests))
        
        METRICS[ERROR_RATE]=$error_rate
        
        log "Error rate: ${error_rate}% ($error_requests/$total_requests)"
    fi
}

generate_performance_report() {
    local report_file="$RESULTS_DIR/performance-report.json"
    
    echo -e "${BLUE}Generating performance report...${NC}"
    
    cat > "$report_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "test_duration": $DURATION,
  "concurrent_users": $CONCURRENT_USERS,
  "cluster": "$CLUSTER_CONTEXT",
  "namespace": "$NAMESPACE",
  "base_url": "${METRICS[BASE_URL]}",
  "load_tests": {
    "steady_load": {
      "rps": "${METRICS[STEADY_RPS]:-0}",
      "mean_time": "${METRICS[STEADY_MEAN_TIME]:-0}",
      "failed_requests": "${METRICS[STEADY_FAILED]:-0}"
    }
  },
  "resource_usage": {
    "cpu": {
      "max_percent": "${METRICS[MAX_CPU]:-0}",
      "avg_percent": "${METRICS[AVG_CPU]:-0}",
      "threshold": ${THRESHOLDS[CPU_LIMIT]}
    },
    "memory": {
      "max_mb": "${METRICS[MAX_MEMORY]:-0}",
      "avg_mb": "${METRICS[AVG_MEMORY]:-0}",
      "threshold": ${THRESHOLDS[MEMORY_LIMIT]}
    }
  },
  "response_times": {
    "p95_ms": "${METRICS[P95_RESPONSE_TIME]:-0}",
    "p99_ms": "${METRICS[P99_RESPONSE_TIME]:-0}",
    "threshold": ${THRESHOLDS[RESPONSE_TIME]}
  },
  "error_rate": {
    "percent": "${METRICS[ERROR_RATE]:-0}",
    "threshold": ${THRESHOLDS[ERROR_RATE]}
  },
  "database_performance": {
    "postgresql_connect_ms": "${METRICS[PG_CONNECT_TIME]:-0}",
    "influxdb_write_ms": "${METRICS[INFLUX_WRITE_TIME]:-0}",
    "influxdb_read_ms": "${METRICS[INFLUX_READ_TIME]:-0}"
  }
}
EOF
    
    # Performance summary
    echo -e "\n${BLUE}Performance Test Summary:${NC}"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check thresholds
    local status="PASS"
    
    if [ "${METRICS[MAX_CPU]:-0}" -gt "${THRESHOLDS[CPU_LIMIT]}" ]; then
        echo -e "${RED}❌ CPU usage exceeded threshold: ${METRICS[MAX_CPU]}% > ${THRESHOLDS[CPU_LIMIT]}%${NC}"
        status="FAIL"
    else
        echo -e "${GREEN}✅ CPU usage within limits: ${METRICS[MAX_CPU]}% <= ${THRESHOLDS[CPU_LIMIT]}%${NC}"
    fi
    
    if [ "${METRICS[P95_RESPONSE_TIME]:-0}" -gt "${THRESHOLDS[RESPONSE_TIME]}" ]; then
        echo -e "${RED}❌ Response time exceeded threshold: ${METRICS[P95_RESPONSE_TIME]}ms > ${THRESHOLDS[RESPONSE_TIME]}ms${NC}"
        status="FAIL"
    else
        echo -e "${GREEN}✅ Response time within limits: ${METRICS[P95_RESPONSE_TIME]}ms <= ${THRESHOLDS[RESPONSE_TIME]}ms${NC}"
    fi
    
    if [ "${METRICS[ERROR_RATE]:-0}" -gt "${THRESHOLDS[ERROR_RATE]}" ]; then
        echo -e "${RED}❌ Error rate exceeded threshold: ${METRICS[ERROR_RATE]}% > ${THRESHOLDS[ERROR_RATE]}%${NC}"
        status="FAIL"
    else
        echo -e "${GREEN}✅ Error rate within limits: ${METRICS[ERROR_RATE]}% <= ${THRESHOLDS[ERROR_RATE]}%${NC}"
    fi
    
    echo -e "\n${PURPLE}Results Directory:${NC} $RESULTS_DIR"
    echo -e "${PURPLE}Performance Report:${NC} $report_file"
    
    if [ "$status" == "PASS" ]; then
        echo -e "\n${GREEN}🎉 PERFORMANCE TEST: PASSED${NC}"
        return 0
    else
        echo -e "\n${RED}❌ PERFORMANCE TEST: FAILED${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           Grill Stats Performance Testing Suite              ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "Duration: ${DURATION}s"
    echo -e "Concurrent Users: $CONCURRENT_USERS"
    echo -e "Results Directory: $RESULTS_DIR"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Setup and run tests
    setup_test_environment
    collect_baseline_metrics
    
    # Start resource monitoring
    monitor_resources
    
    # Run all tests
    run_load_tests
    test_database_performance
    test_api_endpoints
    
    # Analyze and report
    analyze_results
    
    # Cleanup
    cleanup_test_environment
}

# Handle cleanup on exit
trap cleanup_test_environment EXIT

# Check prerequisites
if ! command -v kubectl >/dev/null 2>&1; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq is not installed${NC}"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -c|--concurrent)
            CONCURRENT_USERS="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --context)
            CLUSTER_CONTEXT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -d, --duration SECONDS    Test duration (default: 300)"
            echo "  -c, --concurrent USERS    Concurrent users (default: 10)"
            echo "  -n, --namespace NAME      Kubernetes namespace (default: grill-stats)"
            echo "  --context NAME            Kubernetes context (default: prod-lab)"
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