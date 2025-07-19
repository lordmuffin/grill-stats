#!/bin/bash

# PostgreSQL restore script
# Restores PostgreSQL database from encrypted backup

source /scripts/backup-common.sh

# PostgreSQL specific configuration
POSTGRES_HOST=${POSTGRES_HOST:-postgresql}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-grill_stats}
POSTGRES_USER=${POSTGRES_USER:-grill_stats}
POSTGRES_PASSWORD_FILE="/secrets/postgresql/password"
SERVICE_NAME="postgresql"

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
    -t, --test                Test restore without affecting production
    -p, --point-in-time TIME  Restore to specific point in time (format: YYYY-MM-DD HH:MM:SS)
    -d, --database NAME       Target database name (default: $POSTGRES_DB)
    -u, --user NAME           Database user (default: $POSTGRES_USER)
    --skip-verify             Skip backup verification
    --skip-stop-services      Skip stopping services during restore
    --dry-run                 Show what would be done without executing

Examples:
    $0 /backup/postgresql/postgresql_20240101_120000.tar.gz.enc
    $0 --test --database test_db backup.tar.gz.enc
    $0 --point-in-time "2024-01-01 12:00:00" backup.tar.gz.enc
    $0 --force --skip-verify backup.tar.gz.enc

EOF
}

# Parse command line arguments
FORCE=false
TEST_MODE=false
POINT_IN_TIME=""
SKIP_VERIFY=false
SKIP_STOP_SERVICES=false
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
            shift
            ;;
        -p|--point-in-time)
            POINT_IN_TIME="$2"
            shift 2
            ;;
        -d|--database)
            POSTGRES_DB="$2"
            shift 2
            ;;
        -u|--user)
            POSTGRES_USER="$2"
            shift 2
            ;;
        --skip-verify)
            SKIP_VERIFY=true
            shift
            ;;
        --skip-stop-services)
            SKIP_STOP_SERVICES=true
            shift
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

log_info "Starting PostgreSQL restore from: $BACKUP_FILE"
log_info "Restore directory: $RESTORE_DIR"
log_info "Timestamp: $RESTORE_TIMESTAMP"
log_info "Target database: $POSTGRES_DB"
log_info "Test mode: $TEST_MODE"
log_info "Force mode: $FORCE"
log_info "Dry run: $DRY_RUN"

# Set test database name if in test mode
if [[ "$TEST_MODE" == "true" ]]; then
    POSTGRES_DB="${POSTGRES_DB}_restore_test_${RESTORE_TIMESTAMP}"
    log_info "Using test database: $POSTGRES_DB"
fi

# Verify backup file if not skipped
if [[ "$SKIP_VERIFY" != "true" ]]; then
    log_info "Verifying backup file integrity..."
    if ! verify_backup_integrity "$BACKUP_FILE"; then
        log_error "Backup file integrity check failed"
        exit 1
    fi
    log_info "Backup file integrity verified"
fi

# Set up PostgreSQL environment
if [[ -f "$POSTGRES_PASSWORD_FILE" ]]; then
    export PGPASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
else
    log_error "PostgreSQL password file not found: $POSTGRES_PASSWORD_FILE"
    exit 1
fi

export PGHOST=$POSTGRES_HOST
export PGPORT=$POSTGRES_PORT
export PGUSER=$POSTGRES_USER
export PGDATABASE=$POSTGRES_DB

# Test database connection
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Testing database connection..."
    if ! psql -c "SELECT 1;" > /dev/null 2>&1; then
        log_error "Cannot connect to PostgreSQL database"
        exit 1
    fi
    log_info "Database connection successful"
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
FULL_BACKUP_FILE="${EXTRACTED_BACKUP_DIR}/full_backup.dump"
SCHEMA_BACKUP_FILE="${EXTRACTED_BACKUP_DIR}/schema_backup.sql"

if [[ "$DRY_RUN" != "true" ]]; then
    if [[ ! -f "$BACKUP_MANIFEST" ]]; then
        log_error "Backup manifest not found: $BACKUP_MANIFEST"
        exit 1
    fi

    if [[ ! -f "$FULL_BACKUP_FILE" ]]; then
        log_error "Full backup file not found: $FULL_BACKUP_FILE"
        exit 1
    fi

    # Read backup information
    BACKUP_TIMESTAMP=$(jq -r '.timestamp' "$BACKUP_MANIFEST")
    BACKUP_SERVICE=$(jq -r '.service' "$BACKUP_MANIFEST")
    BACKUP_SIZE=$(jq -r '.size' "$BACKUP_MANIFEST")

    log_info "Backup information:"
    log_info "- Timestamp: $BACKUP_TIMESTAMP"
    log_info "- Service: $BACKUP_SERVICE"
    log_info "- Size: $BACKUP_SIZE"
else
    log_info "DRY RUN: Would verify backup contents"
fi

# Confirmation prompt unless forced
if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
    echo ""
    echo "WARNING: This will restore the database '$POSTGRES_DB' from backup."
    echo "This operation will overwrite the current database contents."
    echo ""
    echo "Backup file: $BACKUP_FILE"
    echo "Backup timestamp: $BACKUP_TIMESTAMP"
    echo "Target database: $POSTGRES_DB"
    echo "Test mode: $TEST_MODE"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# Stop application services if not skipped and not in test mode
if [[ "$SKIP_STOP_SERVICES" != "true" && "$TEST_MODE" != "true" && "$DRY_RUN" != "true" ]]; then
    log_info "Stopping application services..."

    # Scale down deployments
    kubectl scale deployment --all --replicas=0 -n grill-stats || log_warning "Failed to scale down deployments"

    # Wait for pods to terminate
    sleep 30

    log_info "Application services stopped"
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would stop application services"
fi

# Create target database if in test mode
if [[ "$TEST_MODE" == "true" && "$DRY_RUN" != "true" ]]; then
    log_info "Creating test database: $POSTGRES_DB"

    # Connect to postgres database to create new database
    PGDATABASE=postgres psql -c "CREATE DATABASE \"$POSTGRES_DB\";" || log_warning "Database may already exist"

    log_info "Test database created"
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would create test database if in test mode"
fi

# Perform database restore
log_info "Starting database restore..."

if [[ "$DRY_RUN" != "true" ]]; then
    # Restore from full backup
    if pg_restore --verbose --clean --if-exists --no-owner --no-privileges \
        --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
        --dbname="$POSTGRES_DB" \
        "$FULL_BACKUP_FILE"; then
        log_info "Database restore completed successfully"
    else
        log_error "Database restore failed"
        exit 1
    fi

    # Restore individual critical tables if available
    for table_backup in "${EXTRACTED_BACKUP_DIR}"/*_backup.sql; do
        if [[ -f "$table_backup" ]]; then
            table_name=$(basename "$table_backup" _backup.sql)
            log_info "Restoring table: $table_name"

            if psql -f "$table_backup" "$POSTGRES_DB"; then
                log_info "Table $table_name restored successfully"
            else
                log_warning "Failed to restore table: $table_name"
            fi
        fi
    done
else
    log_info "DRY RUN: Would restore database from $FULL_BACKUP_FILE"
fi

# Verify restored database
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Verifying restored database..."

    # Check if database exists and is accessible
    if psql -c "SELECT 1;" "$POSTGRES_DB" > /dev/null 2>&1; then
        log_info "Database is accessible"
    else
        log_error "Database is not accessible after restore"
        exit 1
    fi

    # Get table count
    TABLE_COUNT=$(psql -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" "$POSTGRES_DB" | xargs)
    log_info "Number of tables in restored database: $TABLE_COUNT"

    # Check for specific tables
    CRITICAL_TABLES=("users" "devices" "device_channels" "device_health")
    for table in "${CRITICAL_TABLES[@]}"; do
        if psql -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table');" "$POSTGRES_DB" | grep -q t; then
            ROW_COUNT=$(psql -t -c "SELECT count(*) FROM $table;" "$POSTGRES_DB" | xargs)
            log_info "Table $table exists with $ROW_COUNT rows"
        else
            log_warning "Table $table does not exist in restored database"
        fi
    done
else
    log_info "DRY RUN: Would verify restored database"
fi

# Restart application services if not skipped and not in test mode
if [[ "$SKIP_STOP_SERVICES" != "true" && "$TEST_MODE" != "true" && "$DRY_RUN" != "true" ]]; then
    log_info "Restarting application services..."

    # Scale up deployments
    kubectl scale deployment --all --replicas=1 -n grill-stats || log_warning "Failed to scale up deployments"

    # Wait for services to be ready
    sleep 30

    log_info "Application services restarted"
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would restart application services"
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
    "target_database": "$POSTGRES_DB",
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "backup_timestamp": "$BACKUP_TIMESTAMP",
    "table_count": $TABLE_COUNT,
    "status": "completed",
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
    "target_database": "$POSTGRES_DB",
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "dry_run": true,
    "status": "dry_run_completed"
}
EOF
fi

# Send notification
if [[ "$DRY_RUN" != "true" ]]; then
    if [[ "$TEST_MODE" == "true" ]]; then
        send_notification "success" "$SERVICE_NAME" "Test restore completed successfully for database: $POSTGRES_DB"
    else
        send_notification "success" "$SERVICE_NAME" "Database restore completed successfully for database: $POSTGRES_DB"
    fi
else
    send_notification "info" "$SERVICE_NAME" "Dry run restore completed for database: $POSTGRES_DB"
fi

log_info "PostgreSQL restore process completed at $(date)"
log_info "Restore report: $RESTORE_REPORT_FILE"

exit 0
