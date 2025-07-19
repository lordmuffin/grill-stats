#!/bin/bash

# InfluxDB restore script
# Restores InfluxDB buckets from encrypted backup

source /scripts/backup-common.sh

# InfluxDB specific configuration
INFLUX_HOST=${INFLUX_HOST:-http://influxdb:8086}
INFLUX_ORG=${INFLUX_ORG:-grill-stats}
INFLUX_TOKEN_FILE="/secrets/influxdb/admin-token"
SERVICE_NAME="influxdb"

# Restore configuration
RESTORE_TIMESTAMP=$(get_timestamp)
RESTORE_DIR=$(create_backup_dir "restore" "$RESTORE_TIMESTAMP")
RESTORE_LOG_FILE="${RESTORE_DIR}/restore.log"

# Ensure restore directory exists
mkdir -p "$RESTORE_DIR"

# Redirect all output to log file
exec > >(tee -a "$RESTORE_LOG_FILE")
exec 2>&1

# Function to display usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] <backup_file>

Options:
    -h, --help                Show this help message
    -f, --force               Force restore without confirmation
    -t, --test                Test restore to temporary buckets
    -b, --bucket NAME         Restore only specific bucket
    -o, --org NAME            Target organization (default: $INFLUX_ORG)
    --skip-verify             Skip backup verification
    --new-bucket-suffix TEXT  Suffix for new bucket names (default: _restored)
    --dry-run                 Show what would be done without executing

Examples:
    $0 /backup/influxdb/influxdb_20240101_120000.tar.gz.enc
    $0 --test --bucket grill-stats-realtime backup.tar.gz.enc
    $0 --force --new-bucket-suffix _recovery backup.tar.gz.enc
    $0 --dry-run backup.tar.gz.enc

EOF
}

# Parse command line arguments
FORCE=false
TEST_MODE=false
SPECIFIC_BUCKET=""
SKIP_VERIFY=false
NEW_BUCKET_SUFFIX="_restored"
DRY_RUN=false
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -t|--test)
            TEST_MODE=true
            NEW_BUCKET_SUFFIX="_test_${RESTORE_TIMESTAMP}"
            shift
            ;;
        -b|--bucket)
            SPECIFIC_BUCKET="$2"
            shift 2
            ;;
        -o|--org)
            INFLUX_ORG="$2"
            shift 2
            ;;
        --skip-verify)
            SKIP_VERIFY=true
            shift
            ;;
        --new-bucket-suffix)
            NEW_BUCKET_SUFFIX="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# Validate backup file
if [[ -z "$BACKUP_FILE" ]]; then
    log_error "Backup file not specified"
    usage
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

log_info "Starting InfluxDB restore from: $BACKUP_FILE"
log_info "Restore directory: $RESTORE_DIR"
log_info "Timestamp: $RESTORE_TIMESTAMP"
log_info "Target organization: $INFLUX_ORG"
log_info "Test mode: $TEST_MODE"
log_info "Force mode: $FORCE"
log_info "Dry run: $DRY_RUN"
log_info "Bucket suffix: $NEW_BUCKET_SUFFIX"

# Verify backup file if not skipped
if [[ "$SKIP_VERIFY" != "true" ]]; then
    log_info "Verifying backup file integrity..."
    if ! verify_backup_integrity "$BACKUP_FILE"; then
        log_error "Backup file integrity check failed"
        exit 1
    fi
    log_info "Backup file integrity verified"
fi

# Set up InfluxDB environment
if [[ -f "$INFLUX_TOKEN_FILE" ]]; then
    export INFLUX_TOKEN=$(cat "$INFLUX_TOKEN_FILE")
else
    log_error "InfluxDB token file not found: $INFLUX_TOKEN_FILE"
    exit 1
fi

export INFLUX_HOST_ENV=$INFLUX_HOST
export INFLUX_ORG_ENV=$INFLUX_ORG

# Test InfluxDB connection
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Testing InfluxDB connection..."
    if ! influx ping --host="$INFLUX_HOST"; then
        log_error "Cannot connect to InfluxDB"
        exit 1
    fi
    log_info "InfluxDB connection successful"
fi

# Decrypt and extract backup
log_info "Decrypting and extracting backup..."
DECRYPTED_BACKUP="${RESTORE_DIR}/backup.tar.gz"
EXTRACTED_BACKUP_DIR="${RESTORE_DIR}/backup_extracted"

if [[ "$DRY_RUN" != "true" ]]; then
    if ! decrypt_file "$BACKUP_FILE" "$DECRYPTED_BACKUP"; then
        log_error "Failed to decrypt backup file"
        exit 1
    fi

    if ! decompress_file "$DECRYPTED_BACKUP" "$EXTRACTED_BACKUP_DIR"; then
        log_error "Failed to extract backup file"
        exit 1
    fi

    log_info "Backup decrypted and extracted successfully"
else
    log_info "DRY RUN: Would decrypt and extract backup"
fi

# Verify extracted backup contents
BACKUP_MANIFEST="${EXTRACTED_BACKUP_DIR}/manifest.json"
BUCKET_STATS_FILE="${EXTRACTED_BACKUP_DIR}/bucket_stats.json"
METADATA_DIR="${EXTRACTED_BACKUP_DIR}/metadata"

if [[ "$DRY_RUN" != "true" ]]; then
    if [[ ! -f "$BACKUP_MANIFEST" ]]; then
        log_error "Backup manifest not found: $BACKUP_MANIFEST"
        exit 1
    fi

    # Read backup information
    BACKUP_TIMESTAMP=$(jq -r '.timestamp' "$BACKUP_MANIFEST")
    BACKUP_SERVICE=$(jq -r '.service' "$BACKUP_MANIFEST")
    BACKUP_SIZE=$(jq -r '.size' "$BACKUP_MANIFEST")
    BUCKET_COUNT=$(jq -r '.additional_info.bucket_count' "$BACKUP_MANIFEST")

    log_info "Backup information:"
    log_info "- Timestamp: $BACKUP_TIMESTAMP"
    log_info "- Service: $BACKUP_SERVICE"
    log_info "- Size: $BACKUP_SIZE"
    log_info "- Bucket count: $BUCKET_COUNT"

    # List available buckets in backup
    AVAILABLE_BUCKETS=$(find "$EXTRACTED_BACKUP_DIR" -maxdepth 1 -type d -name "grill-stats-*" -o -name "_*" | xargs -I {} basename {} | sort)
    log_info "Available buckets in backup: $(echo "$AVAILABLE_BUCKETS" | tr '\n' ' ')"
else
    log_info "DRY RUN: Would verify backup contents"
    AVAILABLE_BUCKETS="grill-stats-realtime grill-stats-hourly grill-stats-daily"
fi

# Confirmation prompt unless forced
if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
    echo ""
    echo "WARNING: This will restore InfluxDB buckets from backup."
    echo "This operation will overwrite existing bucket contents."
    echo ""
    echo "Backup file: $BACKUP_FILE"
    echo "Backup timestamp: $BACKUP_TIMESTAMP"
    echo "Target organization: $INFLUX_ORG"
    echo "Test mode: $TEST_MODE"
    echo "Available buckets: $(echo "$AVAILABLE_BUCKETS" | tr '\n' ' ')"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# Function to restore individual bucket
restore_bucket() {
    local bucket_name=$1
    local bucket_backup_dir="${EXTRACTED_BACKUP_DIR}/${bucket_name}"
    local target_bucket_name="${bucket_name}${NEW_BUCKET_SUFFIX}"

    if [[ "$TEST_MODE" != "true" && "$NEW_BUCKET_SUFFIX" == "_restored" ]]; then
        target_bucket_name="$bucket_name"
    fi

    log_info "Restoring bucket: $bucket_name -> $target_bucket_name"

    if [[ ! -d "$bucket_backup_dir" ]]; then
        log_warning "Bucket backup directory not found: $bucket_backup_dir"
        return 1
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would restore bucket $bucket_name to $target_bucket_name"
        return 0
    fi

    # Create target bucket if it doesn't exist (for test mode)
    if [[ "$TEST_MODE" == "true" || "$NEW_BUCKET_SUFFIX" != "_restored" ]]; then
        log_info "Creating target bucket: $target_bucket_name"

        # Check if bucket already exists
        if influx bucket list --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --name="$target_bucket_name" > /dev/null 2>&1; then
            log_info "Bucket $target_bucket_name already exists"
        else
            if influx bucket create --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --name="$target_bucket_name" --retention="720h"; then
                log_info "Created bucket: $target_bucket_name"
            else
                log_error "Failed to create bucket: $target_bucket_name"
                return 1
            fi
        fi
    fi

    # Restore bucket data
    if influx restore "$bucket_backup_dir" \
        --host="$INFLUX_HOST" \
        --org="$INFLUX_ORG" \
        --token="$INFLUX_TOKEN" \
        --bucket="$target_bucket_name" \
        --full; then
        log_info "Successfully restored bucket: $bucket_name"
        return 0
    else
        log_error "Failed to restore bucket: $bucket_name"
        return 1
    fi
}

# Restore buckets
RESTORED_BUCKETS=()
FAILED_BUCKETS=()

if [[ -n "$SPECIFIC_BUCKET" ]]; then
    # Restore only specific bucket
    log_info "Restoring specific bucket: $SPECIFIC_BUCKET"

    if echo "$AVAILABLE_BUCKETS" | grep -q "^$SPECIFIC_BUCKET$"; then
        if restore_bucket "$SPECIFIC_BUCKET"; then
            RESTORED_BUCKETS+=("$SPECIFIC_BUCKET")
        else
            FAILED_BUCKETS+=("$SPECIFIC_BUCKET")
        fi
    else
        log_error "Bucket $SPECIFIC_BUCKET not found in backup"
        exit 1
    fi
else
    # Restore all buckets
    log_info "Restoring all buckets..."

    for bucket in $AVAILABLE_BUCKETS; do
        if restore_bucket "$bucket"; then
            RESTORED_BUCKETS+=("$bucket")
        else
            FAILED_BUCKETS+=("$bucket")
        fi
    done
fi

# Restore metadata if available
if [[ -d "$METADATA_DIR" && "$DRY_RUN" != "true" ]]; then
    log_info "Restoring metadata..."

    # Restore dashboards
    if [[ -f "$METADATA_DIR/dashboards.json" ]]; then
        log_info "Restoring dashboards..."
        # Note: This would require influx CLI with dashboard import capability
        # For now, we'll just log the availability
        log_info "Dashboard metadata available but automatic restore not implemented"
    fi

    # Restore tasks
    if [[ -f "$METADATA_DIR/tasks.json" ]]; then
        log_info "Restoring tasks..."
        # Note: This would require task import capability
        log_info "Task metadata available but automatic restore not implemented"
    fi
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would restore metadata if available"
fi

# Verify restored buckets
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Verifying restored buckets..."

    for bucket in "${RESTORED_BUCKETS[@]}"; do
        target_bucket_name="${bucket}${NEW_BUCKET_SUFFIX}"

        if [[ "$TEST_MODE" != "true" && "$NEW_BUCKET_SUFFIX" == "_restored" ]]; then
            target_bucket_name="$bucket"
        fi

        # Check if bucket exists
        if influx bucket list --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --name="$target_bucket_name" > /dev/null 2>&1; then
            log_info "Bucket $target_bucket_name verified"

            # Get measurement count
            MEASUREMENT_COUNT=$(influx query --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" \
                "import \"influxdata/influxdb/schema\" schema.measurements(bucket: \"$target_bucket_name\") |> count()" \
                --raw 2>/dev/null | tail -n +2 | wc -l || echo "0")

            log_info "Bucket $target_bucket_name contains $MEASUREMENT_COUNT measurements"
        else
            log_error "Bucket $target_bucket_name not found after restore"
            FAILED_BUCKETS+=("$target_bucket_name")
        fi
    done
else
    log_info "DRY RUN: Would verify restored buckets"
fi

# Cleanup temporary files
log_info "Cleaning up temporary files..."
rm -f "$DECRYPTED_BACKUP"
rm -rf "$EXTRACTED_BACKUP_DIR"

# Generate restore report
RESTORE_REPORT_FILE="${RESTORE_DIR}/restore_report.json"
if [[ "$DRY_RUN" != "true" ]]; then
    cat > "$RESTORE_REPORT_FILE" <<EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "service": "$SERVICE_NAME",
    "backup_file": "$BACKUP_FILE",
    "restore_directory": "$RESTORE_DIR",
    "target_organization": "$INFLUX_ORG",
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "backup_timestamp": "$BACKUP_TIMESTAMP",
    "bucket_suffix": "$NEW_BUCKET_SUFFIX",
    "restored_buckets": [$(printf '"%s",' "${RESTORED_BUCKETS[@]}" | sed 's/,$//')],
    "failed_buckets": [$(printf '"%s",' "${FAILED_BUCKETS[@]}" | sed 's/,$//')],
    "status": "$(if [[ ${#FAILED_BUCKETS[@]} -eq 0 ]]; then echo "completed"; else echo "partial"; fi)",
    "duration_seconds": $(( $(date +%s) - $(date -d "$RESTORE_TIMESTAMP" +%s) ))
}
EOF
else
    cat > "$RESTORE_REPORT_FILE" <<EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "service": "$SERVICE_NAME",
    "backup_file": "$BACKUP_FILE",
    "restore_directory": "$RESTORE_DIR",
    "target_organization": "$INFLUX_ORG",
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "dry_run": true,
    "bucket_suffix": "$NEW_BUCKET_SUFFIX",
    "status": "dry_run_completed"
}
EOF
fi

# Report results
log_info "Restore Results:"
log_info "- Restored buckets: ${#RESTORED_BUCKETS[@]}"
log_info "- Failed buckets: ${#FAILED_BUCKETS[@]}"

if [[ ${#RESTORED_BUCKETS[@]} -gt 0 ]]; then
    log_info "Successfully restored buckets: $(printf '%s ' "${RESTORED_BUCKETS[@]}")"
fi

if [[ ${#FAILED_BUCKETS[@]} -gt 0 ]]; then
    log_error "Failed to restore buckets: $(printf '%s ' "${FAILED_BUCKETS[@]}")"
fi

# Send notification
if [[ "$DRY_RUN" != "true" ]]; then
    if [[ ${#FAILED_BUCKETS[@]} -eq 0 ]]; then
        if [[ "$TEST_MODE" == "true" ]]; then
            send_notification "success" "$SERVICE_NAME" "Test restore completed successfully for ${#RESTORED_BUCKETS[@]} buckets"
        else
            send_notification "success" "$SERVICE_NAME" "InfluxDB restore completed successfully for ${#RESTORED_BUCKETS[@]} buckets"
        fi
    else
        send_notification "warning" "$SERVICE_NAME" "InfluxDB restore completed with ${#FAILED_BUCKETS[@]} failures out of $(( ${#RESTORED_BUCKETS[@]} + ${#FAILED_BUCKETS[@]} )) buckets"
    fi
else
    send_notification "info" "$SERVICE_NAME" "Dry run InfluxDB restore completed"
fi

log_info "InfluxDB restore process completed at $(date)"
log_info "Restore report: $RESTORE_REPORT_FILE"

# Exit with appropriate code
if [[ ${#FAILED_BUCKETS[@]} -gt 0 ]]; then
    exit 1
else
    exit 0
fi
