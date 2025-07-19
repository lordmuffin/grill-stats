#!/bin/bash

# Common backup functions and variables
# Source this file from other backup scripts

set -euo pipefail

# Configuration
BACKUP_BASE_DIR="/backup"
BACKUP_TEMP_DIR="/tmp/backup"
BACKUP_REMOTE_DIR="/backup-remote"
BACKUP_RETENTION_DAYS=30
BACKUP_ENCRYPTION_KEY_FILE="/secrets/backup-encryption/encryption-key"
NOTIFICATION_WEBHOOK_URL_FILE="/secrets/backup-notification/webhook-url"

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1" | tee -a "${BACKUP_LOG_FILE:-/dev/stdout}"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "${BACKUP_LOG_FILE:-/dev/stderr}"
}

log_warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" | tee -a "${BACKUP_LOG_FILE:-/dev/stdout}"
}

# Utility functions
get_timestamp() {
    date +%Y%m%d_%H%M%S
}

get_date_only() {
    date +%Y%m%d
}

create_backup_dir() {
    local service=$1
    local timestamp=$2
    local backup_dir="${BACKUP_BASE_DIR}/${service}/${timestamp}"

    mkdir -p "${backup_dir}"
    echo "${backup_dir}"
}

# Encryption functions
encrypt_file() {
    local input_file=$1
    local output_file=$2
    local encryption_key

    if [[ -f "$BACKUP_ENCRYPTION_KEY_FILE" ]]; then
        encryption_key=$(cat "$BACKUP_ENCRYPTION_KEY_FILE")
    else
        log_error "Encryption key file not found: $BACKUP_ENCRYPTION_KEY_FILE"
        return 1
    fi

    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -pass pass:"$encryption_key" \
        -in "$input_file" \
        -out "$output_file"
}

decrypt_file() {
    local input_file=$1
    local output_file=$2
    local encryption_key

    if [[ -f "$BACKUP_ENCRYPTION_KEY_FILE" ]]; then
        encryption_key=$(cat "$BACKUP_ENCRYPTION_KEY_FILE")
    else
        log_error "Encryption key file not found: $BACKUP_ENCRYPTION_KEY_FILE"
        return 1
    fi

    openssl enc -aes-256-cbc -d -pbkdf2 -iter 100000 \
        -pass pass:"$encryption_key" \
        -in "$input_file" \
        -out "$output_file"
}

# Compression functions
compress_directory() {
    local source_dir=$1
    local output_file=$2

    tar -czf "$output_file" -C "$(dirname "$source_dir")" "$(basename "$source_dir")"
}

decompress_file() {
    local input_file=$1
    local output_dir=$2

    mkdir -p "$output_dir"
    tar -xzf "$input_file" -C "$output_dir"
}

# Backup verification functions
verify_backup_integrity() {
    local backup_file=$1
    local expected_min_size=${2:-1024}  # 1KB minimum

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    local file_size=$(stat -c%s "$backup_file")
    if [[ $file_size -lt $expected_min_size ]]; then
        log_error "Backup file too small: $backup_file (${file_size} bytes)"
        return 1
    fi

    # Test file integrity
    if [[ "$backup_file" == *.gz ]]; then
        if ! gzip -t "$backup_file"; then
            log_error "Backup file corrupted: $backup_file"
            return 1
        fi
    fi

    return 0
}

# Cleanup functions
cleanup_old_backups() {
    local service=$1
    local retention_days=${2:-$BACKUP_RETENTION_DAYS}
    local backup_pattern=${3:-"*"}

    local service_dir="${BACKUP_BASE_DIR}/${service}"

    if [[ -d "$service_dir" ]]; then
        log_info "Cleaning up old backups for $service (retention: $retention_days days)"
        find "$service_dir" -name "$backup_pattern" -type f -mtime +$retention_days -delete

        # Remove empty directories
        find "$service_dir" -type d -empty -delete
    fi
}

# Notification functions
send_notification() {
    local status=$1
    local service=$2
    local message=$3
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    local webhook_url
    if [[ -f "$NOTIFICATION_WEBHOOK_URL_FILE" ]]; then
        webhook_url=$(cat "$NOTIFICATION_WEBHOOK_URL_FILE")
    else
        log_warning "Webhook URL file not found: $NOTIFICATION_WEBHOOK_URL_FILE"
        return 0
    fi

    local payload=$(cat <<EOF
{
    "timestamp": "$timestamp",
    "service": "$service",
    "status": "$status",
    "message": "$message",
    "environment": "${ENVIRONMENT:-unknown}",
    "namespace": "${NAMESPACE:-grill-stats}"
}
EOF
)

    if curl -s -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null; then
        log_info "Notification sent for $service: $status"
    else
        log_warning "Failed to send notification for $service"
    fi
}

# Backup metadata functions
create_backup_manifest() {
    local service=$1
    local backup_dir=$2
    local backup_type=${3:-"full"}
    local additional_info=${4:-"{}"}

    local manifest_file="${backup_dir}/manifest.json"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local backup_size=$(du -sh "$backup_dir" | cut -f1)

    cat > "$manifest_file" <<EOF
{
    "timestamp": "$timestamp",
    "service": "$service",
    "backup_type": "$backup_type",
    "version": "1.0",
    "size": "$backup_size",
    "retention_days": $BACKUP_RETENTION_DAYS,
    "environment": "${ENVIRONMENT:-unknown}",
    "namespace": "${NAMESPACE:-grill-stats}",
    "additional_info": $additional_info
}
EOF

    log_info "Created backup manifest: $manifest_file"
}

# Health check functions
check_service_health() {
    local service=$1
    local host=$2
    local port=$3
    local timeout=${4:-10}

    if timeout "$timeout" bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        log_info "Service $service is healthy ($host:$port)"
        return 0
    else
        log_error "Service $service is not healthy ($host:$port)"
        return 1
    fi
}

# Remote backup functions
sync_to_remote() {
    local local_file=$1
    local remote_path=$2
    local remote_type=${3:-"s3"}

    case "$remote_type" in
        "s3")
            sync_to_s3 "$local_file" "$remote_path"
            ;;
        "rsync")
            sync_to_rsync "$local_file" "$remote_path"
            ;;
        *)
            log_error "Unsupported remote type: $remote_type"
            return 1
            ;;
    esac
}

sync_to_s3() {
    local local_file=$1
    local s3_path=$2

    if [[ -f "/secrets/backup-encryption/s3-access-key" ]] && [[ -f "/secrets/backup-encryption/s3-secret-key" ]]; then
        export AWS_ACCESS_KEY_ID=$(cat /secrets/backup-encryption/s3-access-key)
        export AWS_SECRET_ACCESS_KEY=$(cat /secrets/backup-encryption/s3-secret-key)

        if aws s3 cp "$local_file" "$s3_path"; then
            log_info "Successfully synced to S3: $s3_path"
        else
            log_error "Failed to sync to S3: $s3_path"
            return 1
        fi
    else
        log_warning "S3 credentials not found, skipping remote sync"
    fi
}

sync_to_rsync() {
    local local_file=$1
    local rsync_path=$2

    if rsync -av "$local_file" "$rsync_path"; then
        log_info "Successfully synced via rsync: $rsync_path"
    else
        log_error "Failed to sync via rsync: $rsync_path"
        return 1
    fi
}

# Backup validation functions
validate_backup_consistency() {
    local backup_file=$1
    local service=$2
    local validation_type=${3:-"basic"}

    case "$service" in
        "postgresql")
            validate_postgresql_backup "$backup_file" "$validation_type"
            ;;
        "influxdb")
            validate_influxdb_backup "$backup_file" "$validation_type"
            ;;
        "redis")
            validate_redis_backup "$backup_file" "$validation_type"
            ;;
        *)
            log_warning "No specific validation for service: $service"
            verify_backup_integrity "$backup_file"
            ;;
    esac
}

validate_postgresql_backup() {
    local backup_file=$1
    local validation_type=$2

    # Basic integrity check
    if ! verify_backup_integrity "$backup_file" 10240; then
        return 1
    fi

    if [[ "$validation_type" == "advanced" ]]; then
        # TODO: Implement advanced PostgreSQL validation
        # This would involve restoring to a test database and running queries
        log_info "Advanced PostgreSQL validation not implemented yet"
    fi

    return 0
}

validate_influxdb_backup() {
    local backup_file=$1
    local validation_type=$2

    # Basic integrity check
    if ! verify_backup_integrity "$backup_file" 1024; then
        return 1
    fi

    if [[ "$validation_type" == "advanced" ]]; then
        # TODO: Implement advanced InfluxDB validation
        log_info "Advanced InfluxDB validation not implemented yet"
    fi

    return 0
}

validate_redis_backup() {
    local backup_file=$1
    local validation_type=$2

    # Basic integrity check
    if ! verify_backup_integrity "$backup_file" 1024; then
        return 1
    fi

    if [[ "$validation_type" == "advanced" ]]; then
        # TODO: Implement advanced Redis validation
        log_info "Advanced Redis validation not implemented yet"
    fi

    return 0
}

# Backup rotation functions
rotate_backups() {
    local service=$1
    local keep_daily=${2:-7}
    local keep_weekly=${3:-4}
    local keep_monthly=${4:-12}

    local service_dir="${BACKUP_BASE_DIR}/${service}"

    if [[ ! -d "$service_dir" ]]; then
        log_warning "Service directory not found: $service_dir"
        return 0
    fi

    # Keep daily backups
    find "$service_dir" -name "*.tar.gz.enc" -mtime +$keep_daily -not -path "*/weekly/*" -not -path "*/monthly/*" -delete

    # Weekly backup rotation (keep Sunday backups)
    local weekly_dir="${service_dir}/weekly"
    mkdir -p "$weekly_dir"
    find "$weekly_dir" -name "*.tar.gz.enc" -mtime +$((keep_weekly * 7)) -delete

    # Monthly backup rotation (keep first of month backups)
    local monthly_dir="${service_dir}/monthly"
    mkdir -p "$monthly_dir"
    find "$monthly_dir" -name "*.tar.gz.enc" -mtime +$((keep_monthly * 30)) -delete

    log_info "Backup rotation completed for $service"
}

# Error handling
handle_backup_error() {
    local service=$1
    local error_message=$2
    local backup_file=${3:-""}

    log_error "Backup failed for $service: $error_message"

    # Clean up partial backup
    if [[ -n "$backup_file" && -f "$backup_file" ]]; then
        rm -f "$backup_file"
        log_info "Cleaned up partial backup: $backup_file"
    fi

    # Send error notification
    send_notification "error" "$service" "$error_message"

    # Exit with error code
    exit 1
}

# Success handling
handle_backup_success() {
    local service=$1
    local backup_file=$2
    local backup_size=$3

    log_info "Backup completed successfully for $service"
    log_info "Backup file: $backup_file"
    log_info "Backup size: $backup_size"

    # Send success notification
    send_notification "success" "$service" "Backup completed successfully (size: $backup_size)"
}

# Export functions for use in other scripts
export -f log_info log_error log_warning
export -f get_timestamp get_date_only create_backup_dir
export -f encrypt_file decrypt_file compress_directory decompress_file
export -f verify_backup_integrity cleanup_old_backups
export -f send_notification create_backup_manifest
export -f check_service_health sync_to_remote
export -f validate_backup_consistency rotate_backups
export -f handle_backup_error handle_backup_success
