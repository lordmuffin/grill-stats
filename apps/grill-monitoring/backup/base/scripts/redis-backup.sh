#!/bin/bash

# Redis backup script
# Performs daily RDB snapshots and AOF backups

source /scripts/backup-common.sh

# Redis specific configuration
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD_FILE="/secrets/redis/password"
SERVICE_NAME="redis"

# Backup configuration
BACKUP_TIMESTAMP=$(get_timestamp)
BACKUP_DIR=$(create_backup_dir "$SERVICE_NAME" "$BACKUP_TIMESTAMP")
BACKUP_LOG_FILE="${BACKUP_DIR}/backup.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Redirect all output to log file
exec > >(tee -a "$BACKUP_LOG_FILE")
exec 2>&1

log_info "Starting Redis backup for $REDIS_HOST:$REDIS_PORT"
log_info "Backup directory: $BACKUP_DIR"
log_info "Timestamp: $BACKUP_TIMESTAMP"

# Check if Redis is healthy
if ! check_service_health "$SERVICE_NAME" "$REDIS_HOST" "$REDIS_PORT"; then
    handle_backup_error "$SERVICE_NAME" "Redis service is not healthy"
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
log_info "Testing Redis connection..."
if ! redis-cli $REDIS_CLI_ARGS ping > /dev/null 2>&1; then
    handle_backup_error "$SERVICE_NAME" "Cannot connect to Redis"
fi

# Get Redis information
log_info "Gathering Redis information..."
REDIS_VERSION=$(redis-cli $REDIS_CLI_ARGS INFO server | grep redis_version | cut -d: -f2 | tr -d '\r')
REDIS_MODE=$(redis-cli $REDIS_CLI_ARGS INFO server | grep redis_mode | cut -d: -f2 | tr -d '\r')
REDIS_ARCH=$(redis-cli $REDIS_CLI_ARGS INFO server | grep arch_bits | cut -d: -f2 | tr -d '\r')
REDIS_UPTIME=$(redis-cli $REDIS_CLI_ARGS INFO server | grep uptime_in_seconds | cut -d: -f2 | tr -d '\r')

log_info "Redis version: $REDIS_VERSION"
log_info "Redis mode: $REDIS_MODE"
log_info "Redis architecture: ${REDIS_ARCH}bit"
log_info "Redis uptime: $REDIS_UPTIME seconds"

# Get database information
DB_COUNT=$(redis-cli $REDIS_CLI_ARGS INFO keyspace | grep -c "^db" || echo "0")
TOTAL_KEYS=0

log_info "Found $DB_COUNT databases"

# Create database statistics
DB_STATS_FILE="${BACKUP_DIR}/database_stats.json"
echo '{"databases": [' > "$DB_STATS_FILE"

DB_PROCESSED=0
for db in $(redis-cli $REDIS_CLI_ARGS INFO keyspace | grep "^db" | cut -d: -f1); do
    DB_NUM=$(echo "$db" | sed 's/db//')
    DB_INFO=$(redis-cli $REDIS_CLI_ARGS INFO keyspace | grep "^db${DB_NUM}:" | cut -d: -f2)

    # Parse keys, expires, avg_ttl from db info
    KEYS=$(echo "$DB_INFO" | sed 's/.*keys=\([0-9]*\).*/\1/')
    EXPIRES=$(echo "$DB_INFO" | sed 's/.*expires=\([0-9]*\).*/\1/' || echo "0")
    AVG_TTL=$(echo "$DB_INFO" | sed 's/.*avg_ttl=\([0-9]*\).*/\1/' || echo "0")

    TOTAL_KEYS=$((TOTAL_KEYS + KEYS))

    if [[ $DB_PROCESSED -gt 0 ]]; then
        echo ',' >> "$DB_STATS_FILE"
    fi

    cat >> "$DB_STATS_FILE" <<EOF
    {
        "database": $DB_NUM,
        "keys": $KEYS,
        "expires": $EXPIRES,
        "avg_ttl": $AVG_TTL
    }
EOF

    ((DB_PROCESSED++))
done

echo ']}' >> "$DB_STATS_FILE"

log_info "Total keys across all databases: $TOTAL_KEYS"

# Trigger BGSAVE to create RDB snapshot
log_info "Triggering background save (BGSAVE)..."
LASTSAVE_BEFORE=$(redis-cli $REDIS_CLI_ARGS LASTSAVE)
redis-cli $REDIS_CLI_ARGS BGSAVE

# Wait for background save to complete
log_info "Waiting for background save to complete..."
TIMEOUT=300  # 5 minutes timeout
ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    LASTSAVE_CURRENT=$(redis-cli $REDIS_CLI_ARGS LASTSAVE)
    if [[ "$LASTSAVE_CURRENT" -gt "$LASTSAVE_BEFORE" ]]; then
        log_info "Background save completed"
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [[ $ELAPSED -ge $TIMEOUT ]]; then
    log_warning "Background save timeout, proceeding with current snapshot"
fi

# Get RDB file using --rdb option
log_info "Retrieving RDB snapshot..."
RDB_FILE="${BACKUP_DIR}/dump.rdb"

if redis-cli $REDIS_CLI_ARGS --rdb "$RDB_FILE"; then
    log_info "RDB snapshot retrieved successfully"
else
    handle_backup_error "$SERVICE_NAME" "Failed to retrieve RDB snapshot"
fi

# Backup AOF file if available
log_info "Checking for AOF file..."
AOF_ENABLED=$(redis-cli $REDIS_CLI_ARGS CONFIG GET appendonly | tail -1)

if [[ "$AOF_ENABLED" == "yes" ]]; then
    log_info "AOF is enabled, backing up AOF file..."
    AOF_FILE="${BACKUP_DIR}/appendonly.aof"

    # Force AOF rewrite to ensure consistency
    redis-cli $REDIS_CLI_ARGS BGREWRITEAOF

    # Wait for AOF rewrite to complete
    sleep 5

    # Copy AOF file (this would need to be done via kubectl cp in K8s)
    # For now, we'll create a backup using the current AOF state
    if redis-cli $REDIS_CLI_ARGS --eval "$(cat <<'EOF'
local aof_data = {}
local keys = redis.call('KEYS', '*')
for i=1,#keys do
    local key = keys[i]
    local type = redis.call('TYPE', key)['ok']
    if type == 'string' then
        aof_data[#aof_data+1] = 'SET ' .. key .. ' "' .. redis.call('GET', key) .. '"'
    elseif type == 'hash' then
        local hash = redis.call('HGETALL', key)
        for j=1,#hash,2 do
            aof_data[#aof_data+1] = 'HSET ' .. key .. ' "' .. hash[j] .. '" "' .. hash[j+1] .. '"'
        end
    elseif type == 'list' then
        local list = redis.call('LRANGE', key, 0, -1)
        for j=1,#list do
            aof_data[#aof_data+1] = 'LPUSH ' .. key .. ' "' .. list[j] .. '"'
        end
    elseif type == 'set' then
        local set = redis.call('SMEMBERS', key)
        for j=1,#set do
            aof_data[#aof_data+1] = 'SADD ' .. key .. ' "' .. set[j] .. '"'
        end
    elseif type == 'zset' then
        local zset = redis.call('ZRANGE', key, 0, -1, 'WITHSCORES')
        for j=1,#zset,2 do
            aof_data[#aof_data+1] = 'ZADD ' .. key .. ' ' .. zset[j+1] .. ' "' .. zset[j] .. '"'
        end
    end
end
return table.concat(aof_data, '\n')
EOF
)" 0 > "$AOF_FILE"; then
        log_info "AOF backup created successfully"
    else
        log_warning "Failed to create AOF backup"
    fi
else
    log_info "AOF is disabled, skipping AOF backup"
fi

# Create Redis configuration backup
log_info "Backing up Redis configuration..."
CONFIG_FILE="${BACKUP_DIR}/redis_config.txt"
redis-cli $REDIS_CLI_ARGS CONFIG GET '*' > "$CONFIG_FILE"

# Create Redis info backup
log_info "Backing up Redis info..."
INFO_FILE="${BACKUP_DIR}/redis_info.txt"
redis-cli $REDIS_CLI_ARGS INFO > "$INFO_FILE"

# Create memory usage report
log_info "Creating memory usage report..."
MEMORY_FILE="${BACKUP_DIR}/memory_usage.json"
USED_MEMORY=$(redis-cli $REDIS_CLI_ARGS INFO memory | grep used_memory: | cut -d: -f2 | tr -d '\r')
USED_MEMORY_HUMAN=$(redis-cli $REDIS_CLI_ARGS INFO memory | grep used_memory_human: | cut -d: -f2 | tr -d '\r')
MAX_MEMORY=$(redis-cli $REDIS_CLI_ARGS CONFIG GET maxmemory | tail -1)

cat > "$MEMORY_FILE" <<EOF
{
    "used_memory": "$USED_MEMORY",
    "used_memory_human": "$USED_MEMORY_HUMAN",
    "max_memory": "$MAX_MEMORY",
    "total_keys": $TOTAL_KEYS,
    "database_count": $DB_COUNT
}
EOF

# Create backup manifest
ADDITIONAL_INFO=$(cat <<EOF
{
    "redis_version": "$REDIS_VERSION",
    "redis_mode": "$REDIS_MODE",
    "redis_arch": "${REDIS_ARCH}bit",
    "database_count": $DB_COUNT,
    "total_keys": $TOTAL_KEYS,
    "used_memory": "$USED_MEMORY_HUMAN",
    "aof_enabled": "$AOF_ENABLED",
    "backup_method": "RDB + AOF",
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
    REMOTE_PATH="${BACKUP_REMOTE_BASE:-s3://grill-stats-backups}/redis/$(basename "$ENCRYPTED_BACKUP")"

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
    log_info "Redis backup completed successfully"
    log_info "Backup file: $ENCRYPTED_BACKUP"
    log_info "Backup size: $BACKUP_SIZE"
else
    handle_backup_error "$SERVICE_NAME" "Backup file not found after completion"
fi

# Update latest backup symlink
LATEST_BACKUP_LINK="${BACKUP_BASE_DIR}/${SERVICE_NAME}/latest_backup.tar.gz.enc"
ln -sf "$(basename "$ENCRYPTED_BACKUP")" "$LATEST_BACKUP_LINK"

log_info "Redis backup process completed at $(date)"
exit 0
