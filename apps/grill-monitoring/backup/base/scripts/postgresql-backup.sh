#!/bin/bash

# PostgreSQL backup script
# Performs daily full backups with WAL archiving and point-in-time recovery support

source /scripts/backup-common.sh

# PostgreSQL specific configuration
POSTGRES_HOST=${POSTGRES_HOST:-postgresql}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-grill_stats}
POSTGRES_USER=${POSTGRES_USER:-grill_stats}
POSTGRES_PASSWORD_FILE="/secrets/postgresql/password"
SERVICE_NAME="postgresql"

# Backup configuration
BACKUP_TIMESTAMP=$(get_timestamp)
BACKUP_DIR=$(create_backup_dir "$SERVICE_NAME" "$BACKUP_TIMESTAMP")
BACKUP_LOG_FILE="${BACKUP_DIR}/backup.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Redirect all output to log file
exec > >(tee -a "$BACKUP_LOG_FILE")
exec 2>&1

log_info "Starting PostgreSQL backup for $POSTGRES_DB"
log_info "Backup directory: $BACKUP_DIR"
log_info "Timestamp: $BACKUP_TIMESTAMP"

# Check if PostgreSQL is healthy
if ! check_service_health "$SERVICE_NAME" "$POSTGRES_HOST" "$POSTGRES_PORT"; then
    handle_backup_error "$SERVICE_NAME" "PostgreSQL service is not healthy"
fi

# Set up PostgreSQL environment
if [[ -f "$POSTGRES_PASSWORD_FILE" ]]; then
    export PGPASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
else
    handle_backup_error "$SERVICE_NAME" "PostgreSQL password file not found: $POSTGRES_PASSWORD_FILE"
fi

export PGHOST=$POSTGRES_HOST
export PGPORT=$POSTGRES_PORT
export PGUSER=$POSTGRES_USER
export PGDATABASE=$POSTGRES_DB

# Test database connection
log_info "Testing database connection..."
if ! psql -c "SELECT 1;" > /dev/null 2>&1; then
    handle_backup_error "$SERVICE_NAME" "Cannot connect to PostgreSQL database"
fi

# Get database information
DB_VERSION=$(psql -t -c "SELECT version();" | xargs)
DB_SIZE=$(psql -t -c "SELECT pg_size_pretty(pg_database_size('$POSTGRES_DB'));" | xargs)
TABLE_COUNT=$(psql -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)

log_info "Database version: $DB_VERSION"
log_info "Database size: $DB_SIZE"
log_info "Number of tables: $TABLE_COUNT"

# Create full database dump
log_info "Creating full database dump..."
FULL_BACKUP_FILE="${BACKUP_DIR}/full_backup.dump"

if pg_dump --verbose --clean --no-owner --no-privileges \
    --format=custom --compress=9 \
    --file="$FULL_BACKUP_FILE" \
    "$POSTGRES_DB"; then
    log_info "Full backup created successfully"
else
    handle_backup_error "$SERVICE_NAME" "Failed to create full database dump"
fi

# Create schema-only backup
log_info "Creating schema-only backup..."
SCHEMA_BACKUP_FILE="${BACKUP_DIR}/schema_backup.sql"

if pg_dump --verbose --schema-only --no-owner --no-privileges \
    --file="$SCHEMA_BACKUP_FILE" \
    "$POSTGRES_DB"; then
    log_info "Schema backup created successfully"
else
    log_warning "Failed to create schema backup"
fi

# Create individual table backups for critical data
log_info "Creating individual table backups..."
CRITICAL_TABLES=("users" "devices" "device_channels" "device_health" "api_keys")

for table in "${CRITICAL_TABLES[@]}"; do
    TABLE_BACKUP_FILE="${BACKUP_DIR}/${table}_backup.sql"
    
    # Check if table exists
    if psql -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table');" | grep -q t; then
        log_info "Backing up table: $table"
        
        if pg_dump --verbose --table="$table" --data-only --no-owner --no-privileges \
            --file="$TABLE_BACKUP_FILE" \
            "$POSTGRES_DB"; then
            log_info "Table backup created: $table"
        else
            log_warning "Failed to backup table: $table"
        fi
    else
        log_warning "Table does not exist: $table"
    fi
done

# Create database statistics backup
log_info "Creating database statistics backup..."
STATS_FILE="${BACKUP_DIR}/database_stats.json"

cat > "$STATS_FILE" <<EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "database": "$POSTGRES_DB",
    "version": "$DB_VERSION",
    "size": "$DB_SIZE",
    "table_count": $TABLE_COUNT,
    "tables": [
$(psql -t -c "SELECT string_agg('        \"' || table_name || '\"', ',\n') FROM information_schema.tables WHERE table_schema = 'public';")
    ],
    "connection_info": {
        "host": "$POSTGRES_HOST",
        "port": $POSTGRES_PORT,
        "database": "$POSTGRES_DB",
        "user": "$POSTGRES_USER"
    }
}
EOF

# Create backup manifest
ADDITIONAL_INFO=$(cat <<EOF
{
    "database_version": "$DB_VERSION",
    "database_size": "$DB_SIZE",
    "table_count": $TABLE_COUNT,
    "backup_method": "pg_dump",
    "compression": "gzip",
    "encryption": "aes-256-cbc"
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
    REMOTE_PATH="${BACKUP_REMOTE_BASE:-s3://grill-stats-backups}/postgresql/$(basename "$ENCRYPTED_BACKUP")"
    
    if sync_to_remote "$ENCRYPTED_BACKUP" "$REMOTE_PATH" "${BACKUP_REMOTE_TYPE:-s3}"; then
        log_info "Remote sync completed"
    else
        log_warning "Remote sync failed"
    fi
fi

# Rotate backups
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
    log_info "PostgreSQL backup completed successfully"
    log_info "Backup file: $ENCRYPTED_BACKUP"
    log_info "Backup size: $BACKUP_SIZE"
else
    handle_backup_error "$SERVICE_NAME" "Backup file not found after completion"
fi

# Update latest backup symlink
LATEST_BACKUP_LINK="${BACKUP_BASE_DIR}/${SERVICE_NAME}/latest_backup.tar.gz.enc"
ln -sf "$(basename "$ENCRYPTED_BACKUP")" "$LATEST_BACKUP_LINK"

log_info "PostgreSQL backup process completed at $(date)"
exit 0