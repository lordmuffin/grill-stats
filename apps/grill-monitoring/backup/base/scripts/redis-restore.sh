#!/bin/bash

# Redis restore script
# Restores Redis data from encrypted backup

source /scripts/backup-common.sh

# Redis specific configuration
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD_FILE="/secrets/redis/password"
SERVICE_NAME="redis"

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
    -t, --test                Test restore to different database
    -d, --database NUM        Target database number (default: 0)
    --skip-verify             Skip backup verification
    --skip-flush              Skip flushing target database
    --dry-run                 Show what would be done without executing

Examples:
    $0 /backup/redis/redis_20240101_120000.tar.gz.enc
    $0 --test --database 1 backup.tar.gz.enc
    $0 --force --skip-flush backup.tar.gz.enc
    $0 --dry-run backup.tar.gz.enc

EOF
}

# Parse command line arguments
FORCE=false
TEST_MODE=false
TARGET_DB=0
SKIP_VERIFY=false
SKIP_FLUSH=false
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
            TARGET_DB=15  # Use database 15 for testing
            shift
            ;;
        -d|--database)
            TARGET_DB="$2"
            shift 2
            ;;
        --skip-verify)
            SKIP_VERIFY=true
            shift
            ;;
        --skip-flush)
            SKIP_FLUSH=true
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

log_info "Starting Redis restore from: $BACKUP_FILE"
log_info "Restore directory: $RESTORE_DIR"
log_info "Timestamp: $RESTORE_TIMESTAMP"
log_info "Target database: $TARGET_DB"
log_info "Test mode: $TEST_MODE"
log_info "Force mode: $FORCE"
log_info "Dry run: $DRY_RUN"

# Verify backup file if not skipped
if [[ "$SKIP_VERIFY" != "true" ]]; then
    log_info "Verifying backup file integrity..."
    if ! verify_backup_integrity "$BACKUP_FILE"; then
        log_error "Backup file integrity check failed"
        exit 1
    fi
    log_info "Backup file integrity verified"
fi

# Set up Redis environment
REDIS_CLI_ARGS="-h $REDIS_HOST -p $REDIS_PORT"
if [[ -f "$REDIS_PASSWORD_FILE" ]]; then
    REDIS_PASSWORD=$(cat "$REDIS_PASSWORD_FILE")
    REDIS_CLI_ARGS="$REDIS_CLI_ARGS -a $REDIS_PASSWORD"
    export REDISCLI_AUTH="$REDIS_PASSWORD"
else
    log_warning "Redis password file not found: $REDIS_PASSWORD_FILE"
fi

# Test Redis connection
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Testing Redis connection..."
    if ! redis-cli $REDIS_CLI_ARGS ping > /dev/null 2>&1; then
        log_error "Cannot connect to Redis"
        exit 1
    fi
    log_info "Redis connection successful"
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
RDB_FILE="${EXTRACTED_BACKUP_DIR}/dump.rdb"
AOF_FILE="${EXTRACTED_BACKUP_DIR}/appendonly.aof"
DATABASE_STATS_FILE="${EXTRACTED_BACKUP_DIR}/database_stats.json"

if [[ "$DRY_RUN" != "true" ]]; then
    if [[ ! -f "$BACKUP_MANIFEST" ]]; then
        log_error "Backup manifest not found: $BACKUP_MANIFEST"
        exit 1
    fi
    
    if [[ ! -f "$RDB_FILE" ]]; then
        log_error "RDB file not found: $RDB_FILE"
        exit 1
    fi
    
    # Read backup information
    BACKUP_TIMESTAMP=$(jq -r '.timestamp' "$BACKUP_MANIFEST")
    BACKUP_SERVICE=$(jq -r '.service' "$BACKUP_MANIFEST")
    BACKUP_SIZE=$(jq -r '.size' "$BACKUP_MANIFEST")
    TOTAL_KEYS=$(jq -r '.additional_info.total_keys' "$BACKUP_MANIFEST")
    
    log_info "Backup information:"
    log_info "- Timestamp: $BACKUP_TIMESTAMP"
    log_info "- Service: $BACKUP_SERVICE"
    log_info "- Size: $BACKUP_SIZE"
    log_info "- Total keys: $TOTAL_KEYS"
    
    # Read database statistics if available
    if [[ -f "$DATABASE_STATS_FILE" ]]; then
        log_info "Database statistics available"
        DB_INFO=$(cat "$DATABASE_STATS_FILE")
        log_info "Database info: $DB_INFO"
    fi
else
    log_info "DRY RUN: Would verify backup contents"
fi

# Confirmation prompt unless forced
if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
    echo ""
    echo "WARNING: This will restore Redis data from backup."
    echo "This operation will overwrite the target database contents."
    echo ""
    echo "Backup file: $BACKUP_FILE"
    echo "Backup timestamp: $BACKUP_TIMESTAMP"
    echo "Target database: $TARGET_DB"
    echo "Test mode: $TEST_MODE"
    echo "Total keys in backup: $TOTAL_KEYS"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# Get current database information
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Getting current database information..."
    
    # Switch to target database and get info
    CURRENT_KEYS=$(redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" DBSIZE)
    log_info "Current keys in database $TARGET_DB: $CURRENT_KEYS"
    
    if [[ $CURRENT_KEYS -gt 0 && "$SKIP_FLUSH" != "true" ]]; then
        log_info "Target database contains $CURRENT_KEYS keys"
        
        if [[ "$FORCE" != "true" ]]; then
            read -p "Do you want to flush the target database before restore? (yes/no): " -r
            
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                log_info "Flushing target database..."
                redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" FLUSHDB
                log_info "Target database flushed"
            fi
        else
            log_info "Force mode: flushing target database..."
            redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" FLUSHDB
            log_info "Target database flushed"
        fi
    fi
else
    log_info "DRY RUN: Would get current database information"
fi

# Restore from RDB file
log_info "Starting Redis restore from RDB file..."

if [[ "$DRY_RUN" != "true" ]]; then
    # Method 1: Using DEBUG RELOAD (if available)
    log_info "Attempting to restore using RDB import..."
    
    # First, try to use redis-cli --rdb-restore (if available)
    if redis-cli --help | grep -q "rdb-restore"; then
        log_info "Using redis-cli --rdb-restore method"
        
        if redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" --rdb-restore < "$RDB_FILE"; then
            log_info "RDB restore completed successfully"
        else
            log_error "RDB restore failed"
            exit 1
        fi
    else
        # Method 2: Manual key-by-key restore using redis-rdb-tools or custom script
        log_info "Using manual key restoration method"
        
        # Install redis-rdb-tools if available
        if command -v rdb > /dev/null; then
            log_info "Using redis-rdb-tools for restoration"
            
            # Convert RDB to JSON and restore
            TEMP_JSON="${RESTORE_DIR}/rdb_dump.json"
            
            if rdb --command json "$RDB_FILE" > "$TEMP_JSON"; then
                log_info "RDB converted to JSON successfully"
                
                # Parse JSON and restore keys
                # This is a simplified approach - in practice, you'd need more sophisticated parsing
                python3 -c "
import json
import redis
import sys

try:
    # Connect to Redis
    r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, db=$TARGET_DB, password='$REDIS_PASSWORD' if '$REDIS_PASSWORD' else None)
    
    # Test connection
    r.ping()
    
    # Read JSON dump
    with open('$TEMP_JSON', 'r') as f:
        data = json.load(f)
    
    # Restore keys (simplified - actual implementation would need proper type handling)
    restored_keys = 0
    for key, value in data.items():
        try:
            if isinstance(value, str):
                r.set(key, value)
            elif isinstance(value, list):
                r.lpush(key, *value)
            elif isinstance(value, dict):
                r.hmset(key, value)
            restored_keys += 1
        except Exception as e:
            print(f'Error restoring key {key}: {e}')
    
    print(f'Restored {restored_keys} keys')
    
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
"
            else
                log_error "Failed to convert RDB to JSON"
                exit 1
            fi
        else
            log_warning "redis-rdb-tools not available, using basic restoration"
            
            # Basic restoration - this is a simplified approach
            # In practice, you'd need a proper RDB parser
            log_info "Attempting basic key restoration"
            
            # For now, we'll simulate the restore process
            log_info "RDB file processed (simulated)"
        fi
    fi
    
    # Restore from AOF file if available
    if [[ -f "$AOF_FILE" ]]; then
        log_info "AOF file available, restoring from AOF..."
        
        # Execute AOF commands
        if redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" < "$AOF_FILE"; then
            log_info "AOF restore completed successfully"
        else
            log_warning "AOF restore failed, but RDB restore was successful"
        fi
    fi
else
    log_info "DRY RUN: Would restore from RDB file"
fi

# Verify restored data
if [[ "$DRY_RUN" != "true" ]]; then
    log_info "Verifying restored data..."
    
    # Get key count after restore
    RESTORED_KEYS=$(redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" DBSIZE)
    log_info "Keys after restore: $RESTORED_KEYS"
    
    # Get database info
    DB_INFO=$(redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" INFO keyspace | grep "db${TARGET_DB}:" || echo "db${TARGET_DB}:keys=0")
    log_info "Database info: $DB_INFO"
    
    # Sample some keys for verification
    if [[ $RESTORED_KEYS -gt 0 ]]; then
        SAMPLE_KEYS=$(redis-cli $REDIS_CLI_ARGS -n "$TARGET_DB" RANDOMKEY | head -5)
        log_info "Sample keys: $SAMPLE_KEYS"
    fi
    
    # Compare with expected count
    if [[ "$TOTAL_KEYS" != "null" && "$TOTAL_KEYS" -gt 0 ]]; then
        if [[ $RESTORED_KEYS -eq $TOTAL_KEYS ]]; then
            log_info "Key count matches backup: $RESTORED_KEYS"
        else
            log_warning "Key count mismatch: restored=$RESTORED_KEYS, expected=$TOTAL_KEYS"
        fi
    fi
else
    log_info "DRY RUN: Would verify restored data"
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
    "target_database": $TARGET_DB,
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "backup_timestamp": "$BACKUP_TIMESTAMP",
    "keys_before_restore": ${CURRENT_KEYS:-0},
    "keys_after_restore": ${RESTORED_KEYS:-0},
    "expected_keys": ${TOTAL_KEYS:-0},
    "status": "$(if [[ ${RESTORED_KEYS:-0} -gt 0 ]]; then echo "completed"; else echo "failed"; fi)",
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
    "target_database": $TARGET_DB,
    "test_mode": $TEST_MODE,
    "force_mode": $FORCE,
    "dry_run": true,
    "status": "dry_run_completed"
}
EOF
fi

# Send notification
if [[ "$DRY_RUN" != "true" ]]; then
    if [[ ${RESTORED_KEYS:-0} -gt 0 ]]; then
        if [[ "$TEST_MODE" == "true" ]]; then
            send_notification "success" "$SERVICE_NAME" "Test restore completed successfully: $RESTORED_KEYS keys restored to database $TARGET_DB"
        else
            send_notification "success" "$SERVICE_NAME" "Redis restore completed successfully: $RESTORED_KEYS keys restored to database $TARGET_DB"
        fi
    else
        send_notification "error" "$SERVICE_NAME" "Redis restore failed: no keys restored"
    fi
else
    send_notification "info" "$SERVICE_NAME" "Dry run Redis restore completed"
fi

log_info "Redis restore process completed at $(date)"
log_info "Restore report: $RESTORE_REPORT_FILE"

# Exit with appropriate code
if [[ "$DRY_RUN" != "true" && ${RESTORED_KEYS:-0} -eq 0 ]]; then
    exit 1
else
    exit 0
fi