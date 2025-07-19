#!/bin/bash

# InfluxDB backup script
# Performs daily exports of time-series data with bucket-specific retention

source /scripts/backup-common.sh

# InfluxDB specific configuration
INFLUX_HOST=${INFLUX_HOST:-http://influxdb:8086}
INFLUX_ORG=${INFLUX_ORG:-grill-stats}
INFLUX_TOKEN_FILE="/secrets/influxdb/admin-token"
SERVICE_NAME="influxdb"

# Backup configuration
BACKUP_TIMESTAMP=$(get_timestamp)
BACKUP_DIR=$(create_backup_dir "$SERVICE_NAME" "$BACKUP_TIMESTAMP")
BACKUP_LOG_FILE="${BACKUP_DIR}/backup.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Redirect all output to log file
exec > >(tee -a "$BACKUP_LOG_FILE")
exec 2>&1

log_info "Starting InfluxDB backup for organization $INFLUX_ORG"
log_info "Backup directory: $BACKUP_DIR"
log_info "Timestamp: $BACKUP_TIMESTAMP"

# Check if InfluxDB is healthy
INFLUX_HOST_CLEAN=$(echo "$INFLUX_HOST" | sed 's|^http://||' | sed 's|^https://||')
INFLUX_PORT=$(echo "$INFLUX_HOST_CLEAN" | cut -d: -f2)
INFLUX_HOST_CLEAN=$(echo "$INFLUX_HOST_CLEAN" | cut -d: -f1)

if ! check_service_health "$SERVICE_NAME" "$INFLUX_HOST_CLEAN" "${INFLUX_PORT:-8086}"; then
    handle_backup_error "$SERVICE_NAME" "InfluxDB service is not healthy"
fi

# Set up InfluxDB environment
if [[ -f "$INFLUX_TOKEN_FILE" ]]; then
    export INFLUX_TOKEN=$(cat "$INFLUX_TOKEN_FILE")
else
    handle_backup_error "$SERVICE_NAME" "InfluxDB token file not found: $INFLUX_TOKEN_FILE"
fi

export INFLUX_HOST_ENV=$INFLUX_HOST
export INFLUX_ORG_ENV=$INFLUX_ORG

# Test InfluxDB connection
log_info "Testing InfluxDB connection..."
if ! influx ping --host="$INFLUX_HOST"; then
    handle_backup_error "$SERVICE_NAME" "Cannot connect to InfluxDB"
fi

# Get InfluxDB information
log_info "Gathering InfluxDB information..."
INFLUX_VERSION=$(influx version | grep InfluxDB | awk '{print $2}')
INFLUX_BUILD=$(influx version | grep InfluxDB | awk '{print $3}')

log_info "InfluxDB version: $INFLUX_VERSION"
log_info "InfluxDB build: $INFLUX_BUILD"

# Get list of buckets
log_info "Retrieving bucket list..."
BUCKETS=$(influx bucket list --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --json | jq -r '.[].name')

if [[ -z "$BUCKETS" ]]; then
    handle_backup_error "$SERVICE_NAME" "No buckets found or failed to retrieve bucket list"
fi

log_info "Found buckets: $(echo "$BUCKETS" | tr '\n' ' ')"

# Define backup buckets and their retention policies
declare -A BUCKET_RETENTION=(
    ["grill-stats-realtime"]="7"      # Keep 7 days of realtime data
    ["grill-stats-hourly"]="30"       # Keep 30 days of hourly data
    ["grill-stats-daily"]="365"       # Keep 365 days of daily data
    ["grill-stats-archive"]="3650"    # Keep 10 years of archive data
    ["_monitoring"]="30"              # Keep 30 days of monitoring data
    ["_tasks"]="30"                   # Keep 30 days of task data
)

# Create bucket statistics
BUCKET_STATS_FILE="${BACKUP_DIR}/bucket_stats.json"
echo '{"buckets": [' > "$BUCKET_STATS_FILE"

BUCKET_COUNT=0
for bucket in $BUCKETS; do
    log_info "Gathering statistics for bucket: $bucket"

    # Get bucket size and measurement count
    BUCKET_SIZE=$(influx query --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" \
        "from(bucket: \"$bucket\") |> range(start: -30d) |> count() |> yield(name: \"count\")" \
        --raw 2>/dev/null | tail -n +2 | wc -l || echo "0")

    LAST_WRITE=$(influx query --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" \
        "from(bucket: \"$bucket\") |> range(start: -1d) |> last() |> yield(name: \"last\")" \
        --raw 2>/dev/null | tail -1 | cut -d, -f6 || echo "unknown")

    if [[ $BUCKET_COUNT -gt 0 ]]; then
        echo ',' >> "$BUCKET_STATS_FILE"
    fi

    cat >> "$BUCKET_STATS_FILE" <<EOF
    {
        "name": "$bucket",
        "size_estimate": $BUCKET_SIZE,
        "last_write": "$LAST_WRITE",
        "retention_days": ${BUCKET_RETENTION[$bucket]:-30}
    }
EOF

    ((BUCKET_COUNT++))
done

echo ']}' >> "$BUCKET_STATS_FILE"

# Backup each bucket
for bucket in $BUCKETS; do
    log_info "Backing up bucket: $bucket"

    BUCKET_BACKUP_DIR="${BACKUP_DIR}/${bucket}"
    mkdir -p "$BUCKET_BACKUP_DIR"

    # Perform backup with compression
    if influx backup "$BUCKET_BACKUP_DIR" \
        --host="$INFLUX_HOST" \
        --org="$INFLUX_ORG" \
        --token="$INFLUX_TOKEN" \
        --bucket="$bucket" \
        --compression=gzip; then
        log_info "Backup completed for bucket: $bucket"
    else
        log_error "Failed to backup bucket: $bucket"
        # Continue with other buckets instead of failing completely
        continue
    fi

    # Create bucket-specific manifest
    BUCKET_MANIFEST="${BUCKET_BACKUP_DIR}/bucket_manifest.json"
    cat > "$BUCKET_MANIFEST" <<EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "bucket": "$bucket",
    "org": "$INFLUX_ORG",
    "backup_method": "influx backup",
    "compression": "gzip",
    "retention_days": ${BUCKET_RETENTION[$bucket]:-30}
}
EOF
done

# Export metadata (organizations, buckets, users, etc.)
log_info "Exporting metadata..."
METADATA_DIR="${BACKUP_DIR}/metadata"
mkdir -p "$METADATA_DIR"

# Export organizations
influx org list --host="$INFLUX_HOST" --token="$INFLUX_TOKEN" --json > "$METADATA_DIR/organizations.json" 2>/dev/null || log_warning "Failed to export organizations"

# Export users
influx user list --host="$INFLUX_HOST" --token="$INFLUX_TOKEN" --json > "$METADATA_DIR/users.json" 2>/dev/null || log_warning "Failed to export users"

# Export buckets
influx bucket list --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --json > "$METADATA_DIR/buckets.json" 2>/dev/null || log_warning "Failed to export buckets"

# Export dashboards
influx dashboards --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --json > "$METADATA_DIR/dashboards.json" 2>/dev/null || log_warning "Failed to export dashboards"

# Export tasks
influx task list --host="$INFLUX_HOST" --org="$INFLUX_ORG" --token="$INFLUX_TOKEN" --json > "$METADATA_DIR/tasks.json" 2>/dev/null || log_warning "Failed to export tasks"

# Create backup manifest
ADDITIONAL_INFO=$(cat <<EOF
{
    "influxdb_version": "$INFLUX_VERSION",
    "influxdb_build": "$INFLUX_BUILD",
    "organization": "$INFLUX_ORG",
    "bucket_count": $BUCKET_COUNT,
    "backup_method": "influx backup",
    "compression": "gzip",
    "includes_metadata": true
}
EOF
)

create_backup_manifest "$SERVICE_NAME" "$BACKUP_DIR" "full" "$ADDITIONAL_INFO"

# Compress backup directory
log_info "Compressing backup directory..."
COMPRESSED_BACKUP="${BACKUP_BASE_DIR}/${SERVICE_NAME}/${SERVICE_NAME}_${BACKUP_TIMESTAMP}.tar.gz"

if compress_directory "$BACKUP_DIR" "$COMPRESSED_BACKUP"; then
    log_info "Backup compressed successfully"
else
    handle_backup_error "$SERVICE_NAME" "Failed to compress backup"
fi

# Encrypt backup
log_info "Encrypting backup..."
ENCRYPTED_BACKUP="${COMPRESSED_BACKUP}.enc"

if encrypt_file "$COMPRESSED_BACKUP" "$ENCRYPTED_BACKUP"; then
    log_info "Backup encrypted successfully"
    # Remove unencrypted backup
    rm -f "$COMPRESSED_BACKUP"
else
    handle_backup_error "$SERVICE_NAME" "Failed to encrypt backup"
fi

# Verify backup integrity
log_info "Verifying backup integrity..."
BACKUP_SIZE=$(du -sh "$ENCRYPTED_BACKUP" | cut -f1)

if validate_backup_consistency "$ENCRYPTED_BACKUP" "$SERVICE_NAME"; then
    log_info "Backup integrity verified"
else
    handle_backup_error "$SERVICE_NAME" "Backup integrity verification failed"
fi

# Sync to remote storage if configured
if [[ "${BACKUP_REMOTE_SYNC:-false}" == "true" ]]; then
    log_info "Syncing to remote storage..."
    REMOTE_PATH="${BACKUP_REMOTE_BASE:-s3://grill-stats-backups}/influxdb/$(basename "$ENCRYPTED_BACKUP")"

    if sync_to_remote "$ENCRYPTED_BACKUP" "$REMOTE_PATH" "${BACKUP_REMOTE_TYPE:-s3}"; then
        log_info "Remote sync completed"
    else
        log_warning "Remote sync failed"
    fi
fi

# Rotate backups with different retention for different data types
log_info "Rotating old backups..."
rotate_backups "$SERVICE_NAME" 7 4 12

# Weekly backup handling (Sunday)
if [[ $(date +%u) -eq 7 ]]; then
    WEEKLY_DIR="${BACKUP_BASE_DIR}/${SERVICE_NAME}/weekly"
    mkdir -p "$WEEKLY_DIR"
    cp "$ENCRYPTED_BACKUP" "$WEEKLY_DIR/$(basename "$ENCRYPTED_BACKUP")"
    log_info "Weekly backup created"
fi

# Monthly backup handling (first day of month)
if [[ $(date +%d) -eq 01 ]]; then
    MONTHLY_DIR="${BACKUP_BASE_DIR}/${SERVICE_NAME}/monthly"
    mkdir -p "$MONTHLY_DIR"
    cp "$ENCRYPTED_BACKUP" "$MONTHLY_DIR/$(basename "$ENCRYPTED_BACKUP")"
    log_info "Monthly backup created"
fi

# Cleanup temporary files
rm -rf "$BACKUP_DIR"

# Final verification
if [[ -f "$ENCRYPTED_BACKUP" ]]; then
    handle_backup_success "$SERVICE_NAME" "$ENCRYPTED_BACKUP" "$BACKUP_SIZE"
    log_info "InfluxDB backup completed successfully"
    log_info "Backup file: $ENCRYPTED_BACKUP"
    log_info "Backup size: $BACKUP_SIZE"
else
    handle_backup_error "$SERVICE_NAME" "Backup file not found after completion"
fi

# Update latest backup symlink
LATEST_BACKUP_LINK="${BACKUP_BASE_DIR}/${SERVICE_NAME}/latest_backup.tar.gz.enc"
ln -sf "$(basename "$ENCRYPTED_BACKUP")" "$LATEST_BACKUP_LINK"

log_info "InfluxDB backup process completed at $(date)"
exit 0
