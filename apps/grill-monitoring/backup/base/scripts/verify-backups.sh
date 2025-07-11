#!/bin/bash

# Backup verification script
# Verifies integrity and freshness of all backups

source /scripts/backup-common.sh

SERVICE_NAME="backup-verification"
VERIFICATION_TIMESTAMP=$(get_timestamp)
VERIFICATION_DIR="${BACKUP_BASE_DIR}/verification"
VERIFICATION_LOG_FILE="${VERIFICATION_DIR}/verify_${VERIFICATION_TIMESTAMP}.log"

# Ensure verification directory exists
mkdir -p "$VERIFICATION_DIR"

# Redirect all output to log file
exec > >(tee -a "$VERIFICATION_LOG_FILE")
exec 2>&1

log_info "Starting backup verification at $(date)"

# Configuration
MAX_BACKUP_AGE_HOURS=48
MIN_BACKUP_SIZE_KB=1024
STORAGE_WARNING_THRESHOLD=80
STORAGE_CRITICAL_THRESHOLD=95

# Initialize verification results
VERIFICATION_RESULTS='{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","backups":[],"storage":{},"summary":{"total":0,"healthy":0,"warnings":0,"errors":0}}'

# Function to add backup result
add_backup_result() {
    local service=$1
    local status=$2
    local message=$3
    local file_path=${4:-""}
    local size=${5:-""}
    local age_hours=${6:-""}
    
    local result=$(cat <<EOF
{
    "service": "$service",
    "status": "$status",
    "message": "$message",
    "file_path": "$file_path",
    "size": "$size",
    "age_hours": $age_hours,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
    
    VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq ".backups += [$result]")
    
    # Update summary counters
    case "$status" in
        "healthy")
            VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq '.summary.healthy += 1')
            ;;
        "warning")
            VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq '.summary.warnings += 1')
            ;;
        "error")
            VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq '.summary.errors += 1')
            ;;
    esac
    
    VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq '.summary.total += 1')
}

# Function to verify individual backup
verify_backup() {
    local service=$1
    local backup_pattern=$2
    
    log_info "Verifying backups for service: $service"
    
    local service_dir="${BACKUP_BASE_DIR}/${service}"
    
    if [[ ! -d "$service_dir" ]]; then
        log_error "Service backup directory not found: $service_dir"
        add_backup_result "$service" "error" "Backup directory not found" "" "" ""
        return 1
    fi
    
    # Find latest backup
    local latest_backup=$(find "$service_dir" -name "$backup_pattern" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -z "$latest_backup" ]]; then
        log_error "No backup files found for service: $service"
        add_backup_result "$service" "error" "No backup files found" "" "" ""
        return 1
    fi
    
    log_info "Latest backup for $service: $latest_backup"
    
    # Check backup age
    local backup_age_seconds=$(( $(date +%s) - $(stat -c %Y "$latest_backup") ))
    local backup_age_hours=$(( backup_age_seconds / 3600 ))
    
    log_info "Backup age: $backup_age_hours hours"
    
    # Check backup size
    local backup_size_bytes=$(stat -c %s "$latest_backup")
    local backup_size_kb=$(( backup_size_bytes / 1024 ))
    local backup_size_human=$(du -sh "$latest_backup" | cut -f1)
    
    log_info "Backup size: $backup_size_human ($backup_size_kb KB)"
    
    # Verify backup integrity
    local integrity_status="unknown"
    local integrity_message=""
    
    if verify_backup_integrity "$latest_backup" "$MIN_BACKUP_SIZE_KB"; then
        integrity_status="passed"
        integrity_message="Backup integrity verified"
    else
        integrity_status="failed"
        integrity_message="Backup integrity check failed"
    fi
    
    log_info "Integrity check: $integrity_status"
    
    # Advanced verification based on service type
    local advanced_status="unknown"
    local advanced_message=""
    
    case "$service" in
        "postgresql")
            advanced_status="skipped"
            advanced_message="Advanced PostgreSQL verification not implemented"
            ;;
        "influxdb")
            advanced_status="skipped"
            advanced_message="Advanced InfluxDB verification not implemented"
            ;;
        "redis")
            advanced_status="skipped"
            advanced_message="Advanced Redis verification not implemented"
            ;;
        *)
            advanced_status="skipped"
            advanced_message="No advanced verification for this service"
            ;;
    esac
    
    # Determine overall status
    local overall_status="healthy"
    local overall_message="Backup is healthy"
    
    if [[ "$integrity_status" == "failed" ]]; then
        overall_status="error"
        overall_message="Backup integrity check failed"
    elif [[ $backup_age_hours -gt $MAX_BACKUP_AGE_HOURS ]]; then
        overall_status="warning"
        overall_message="Backup is older than $MAX_BACKUP_AGE_HOURS hours"
    elif [[ $backup_size_kb -lt $MIN_BACKUP_SIZE_KB ]]; then
        overall_status="warning"
        overall_message="Backup size is smaller than expected"
    fi
    
    log_info "Overall status for $service: $overall_status - $overall_message"
    
    # Add result
    add_backup_result "$service" "$overall_status" "$overall_message" "$latest_backup" "$backup_size_human" $backup_age_hours
    
    # Send notification if there are issues
    if [[ "$overall_status" != "healthy" ]]; then
        send_notification "$overall_status" "$service" "$overall_message"
    fi
    
    return 0
}

# Function to check storage usage
check_storage_usage() {
    log_info "Checking storage usage..."
    
    local backup_storage_usage=$(df "$BACKUP_BASE_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    local backup_storage_available=$(df -h "$BACKUP_BASE_DIR" | tail -1 | awk '{print $4}')
    local backup_storage_total=$(df -h "$BACKUP_BASE_DIR" | tail -1 | awk '{print $2}')
    
    log_info "Backup storage usage: ${backup_storage_usage}% (${backup_storage_available} available of ${backup_storage_total} total)"
    
    # Check remote storage if configured
    local remote_storage_usage=0
    local remote_storage_available="N/A"
    local remote_storage_total="N/A"
    
    if [[ -d "$BACKUP_REMOTE_DIR" ]]; then
        remote_storage_usage=$(df "$BACKUP_REMOTE_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
        remote_storage_available=$(df -h "$BACKUP_REMOTE_DIR" | tail -1 | awk '{print $4}')
        remote_storage_total=$(df -h "$BACKUP_REMOTE_DIR" | tail -1 | awk '{print $2}')
        
        log_info "Remote storage usage: ${remote_storage_usage}% (${remote_storage_available} available of ${remote_storage_total} total)"
    fi
    
    # Update verification results with storage info
    VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq ".storage = {
        \"backup_storage\": {
            \"usage_percent\": $backup_storage_usage,
            \"available\": \"$backup_storage_available\",
            \"total\": \"$backup_storage_total\"
        },
        \"remote_storage\": {
            \"usage_percent\": $remote_storage_usage,
            \"available\": \"$remote_storage_available\",
            \"total\": \"$remote_storage_total\"
        }
    }")
    
    # Check storage thresholds
    local storage_status="healthy"
    local storage_message="Storage usage is within acceptable limits"
    
    if [[ $backup_storage_usage -ge $STORAGE_CRITICAL_THRESHOLD ]]; then
        storage_status="critical"
        storage_message="Backup storage usage is critical (${backup_storage_usage}%)"
        log_error "$storage_message"
        send_notification "error" "storage" "$storage_message"
    elif [[ $backup_storage_usage -ge $STORAGE_WARNING_THRESHOLD ]]; then
        storage_status="warning"
        storage_message="Backup storage usage is high (${backup_storage_usage}%)"
        log_warning "$storage_message"
        send_notification "warning" "storage" "$storage_message"
    fi
    
    VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq ".storage.status = \"$storage_status\"")
    VERIFICATION_RESULTS=$(echo "$VERIFICATION_RESULTS" | jq ".storage.message = \"$storage_message\"")
}

# Function to generate verification report
generate_verification_report() {
    local report_file="${VERIFICATION_DIR}/verification_report_$(get_date_only).json"
    
    echo "$VERIFICATION_RESULTS" | jq . > "$report_file"
    
    log_info "Verification report generated: $report_file"
    
    # Create human-readable report
    local human_report="${VERIFICATION_DIR}/verification_report_$(get_date_only).txt"
    
    cat > "$human_report" <<EOF
Backup Verification Report
=========================
Generated: $(date)

Summary:
- Total backups checked: $(echo "$VERIFICATION_RESULTS" | jq -r '.summary.total')
- Healthy backups: $(echo "$VERIFICATION_RESULTS" | jq -r '.summary.healthy')
- Warnings: $(echo "$VERIFICATION_RESULTS" | jq -r '.summary.warnings')
- Errors: $(echo "$VERIFICATION_RESULTS" | jq -r '.summary.errors')

Storage Status:
- Backup storage usage: $(echo "$VERIFICATION_RESULTS" | jq -r '.storage.backup_storage.usage_percent')%
- Available space: $(echo "$VERIFICATION_RESULTS" | jq -r '.storage.backup_storage.available')
- Total space: $(echo "$VERIFICATION_RESULTS" | jq -r '.storage.backup_storage.total')

Individual Backup Status:
EOF
    
    echo "$VERIFICATION_RESULTS" | jq -r '.backups[] | "- \(.service): \(.status) - \(.message) (Age: \(.age_hours)h, Size: \(.size))"' >> "$human_report"
    
    log_info "Human-readable report generated: $human_report"
    
    # Create latest symlinks
    ln -sf "$(basename "$report_file")" "${VERIFICATION_DIR}/latest_verification.json"
    ln -sf "$(basename "$human_report")" "${VERIFICATION_DIR}/latest_verification.txt"
}

# Function to cleanup old verification reports
cleanup_old_reports() {
    log_info "Cleaning up old verification reports..."
    
    # Keep verification reports for 30 days
    find "$VERIFICATION_DIR" -name "verification_report_*.json" -mtime +30 -delete
    find "$VERIFICATION_DIR" -name "verification_report_*.txt" -mtime +30 -delete
    find "$VERIFICATION_DIR" -name "verify_*.log" -mtime +30 -delete
    
    log_info "Old verification reports cleaned up"
}

# Main verification process
main() {
    log_info "Starting backup verification process"
    
    # Install required packages
    if command -v apk > /dev/null; then
        apk add --no-cache jq curl
    elif command -v apt-get > /dev/null; then
        apt-get update && apt-get install -y jq curl
    elif command -v yum > /dev/null; then
        yum install -y jq curl
    fi
    
    # Verify each service's backups
    verify_backup "postgresql" "*.tar.gz.enc"
    verify_backup "influxdb" "*.tar.gz.enc"
    verify_backup "redis" "*.tar.gz.enc"
    
    # Check storage usage
    check_storage_usage
    
    # Generate verification report
    generate_verification_report
    
    # Cleanup old reports
    cleanup_old_reports
    
    # Calculate final status
    local total_errors=$(echo "$VERIFICATION_RESULTS" | jq -r '.summary.errors')
    local total_warnings=$(echo "$VERIFICATION_RESULTS" | jq -r '.summary.warnings')
    local total_healthy=$(echo "$VERIFICATION_RESULTS" | jq -r '.summary.healthy')
    
    log_info "Verification completed:"
    log_info "- Healthy: $total_healthy"
    log_info "- Warnings: $total_warnings"
    log_info "- Errors: $total_errors"
    
    # Send summary notification
    if [[ $total_errors -gt 0 ]]; then
        send_notification "error" "backup-verification" "Backup verification completed with $total_errors errors and $total_warnings warnings"
        exit 1
    elif [[ $total_warnings -gt 0 ]]; then
        send_notification "warning" "backup-verification" "Backup verification completed with $total_warnings warnings"
        exit 0
    else
        send_notification "success" "backup-verification" "All backups verified successfully"
        exit 0
    fi
}

# Execute main function
main "$@"