#!/bin/bash

# Full platform restore script
# Orchestrates complete disaster recovery for grill-stats platform

source /scripts/backup-common.sh

SERVICE_NAME="full-restore"
RESTORE_TIMESTAMP=$(get_timestamp)
RESTORE_DIR=$(create_backup_dir "full-restore" "$RESTORE_TIMESTAMP")
RESTORE_LOG_FILE="${RESTORE_DIR}/full_restore.log"

# Ensure restore directory exists
mkdir -p "$RESTORE_DIR"

# Redirect all output to log file
exec > >(tee -a "$RESTORE_LOG_FILE")
exec 2>&1

# Function to display usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Full platform disaster recovery script for grill-stats.

Options:
    -h, --help                Show this help message
    -f, --force               Force restore without confirmation
    -t, --test                Test restore to temporary environment
    --postgresql-backup FILE  Specific PostgreSQL backup file
    --influxdb-backup FILE    Specific InfluxDB backup file
    --redis-backup FILE       Specific Redis backup file
    --skip-postgresql         Skip PostgreSQL restore
    --skip-influxdb          Skip InfluxDB restore
    --skip-redis             Skip Redis restore
    --skip-services          Skip stopping/starting services
    --timeout SECONDS        Timeout for individual restores (default: 3600)
    --dry-run                Show what would be done without executing

Examples:
    $0 --force                                    # Full restore with latest backups
    $0 --test                                     # Test restore to temporary environment
    $0 --postgresql-backup /path/to/pg_backup.enc # Use specific PostgreSQL backup
    $0 --skip-redis --dry-run                     # Dry run without Redis restore

Recovery Process:
1. Validation and preparation
2. Service shutdown
3. Database restoration (PostgreSQL, InfluxDB, Redis)
4. Service startup and verification
5. Health checks and validation

EOF
}

# Parse command line arguments
FORCE=false
TEST_MODE=false
POSTGRESQL_BACKUP=""
INFLUXDB_BACKUP=""
REDIS_BACKUP=""
SKIP_POSTGRESQL=false
SKIP_INFLUXDB=false
SKIP_REDIS=false
SKIP_SERVICES=false
TIMEOUT=3600
DRY_RUN=false

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
        --postgresql-backup)
            POSTGRESQL_BACKUP="$2"
            shift 2
            ;;
        --influxdb-backup)
            INFLUXDB_BACKUP="$2"
            shift 2
            ;;
        --redis-backup)
            REDIS_BACKUP="$2"
            shift 2
            ;;
        --skip-postgresql)
            SKIP_POSTGRESQL=true
            shift
            ;;
        --skip-influxdb)
            SKIP_INFLUXDB=true
            shift
            ;;
        --skip-redis)
            SKIP_REDIS=true
            shift
            ;;
        --skip-services)
            SKIP_SERVICES=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
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
            log_error "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

log_info "Starting full platform restore"
log_info "Restore directory: $RESTORE_DIR"
log_info "Timestamp: $RESTORE_TIMESTAMP"
log_info "Test mode: $TEST_MODE"
log_info "Force mode: $FORCE"
log_info "Dry run: $DRY_RUN"
log_info "Timeout: $TIMEOUT seconds"

# Function to find latest backup
find_latest_backup() {
    local service=$1
    local service_dir="${BACKUP_BASE_DIR}/${service}"
    
    if [[ -d "$service_dir" ]]; then
        find "$service_dir" -name "*.tar.gz.enc" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-
    else
        echo ""
    fi
}

# Determine backup files to use
if [[ -z "$POSTGRESQL_BACKUP" && "$SKIP_POSTGRESQL" != "true" ]]; then
    POSTGRESQL_BACKUP=$(find_latest_backup "postgresql")
    if [[ -z "$POSTGRESQL_BACKUP" ]]; then
        log_error "No PostgreSQL backup found"
        exit 1
    fi
    log_info "Using PostgreSQL backup: $POSTGRESQL_BACKUP"
fi

if [[ -z "$INFLUXDB_BACKUP" && "$SKIP_INFLUXDB" != "true" ]]; then
    INFLUXDB_BACKUP=$(find_latest_backup "influxdb")
    if [[ -z "$INFLUXDB_BACKUP" ]]; then
        log_error "No InfluxDB backup found"
        exit 1
    fi
    log_info "Using InfluxDB backup: $INFLUXDB_BACKUP"
fi

if [[ -z "$REDIS_BACKUP" && "$SKIP_REDIS" != "true" ]]; then
    REDIS_BACKUP=$(find_latest_backup "redis")
    if [[ -z "$REDIS_BACKUP" ]]; then
        log_warning "No Redis backup found, skipping Redis restore"
        SKIP_REDIS=true
    else
        log_info "Using Redis backup: $REDIS_BACKUP"
    fi
fi

# Validate backup files
log_info "Validating backup files..."

if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
    if [[ ! -f "$POSTGRESQL_BACKUP" ]]; then
        log_error "PostgreSQL backup file not found: $POSTGRESQL_BACKUP"
        exit 1
    fi
fi

if [[ "$SKIP_INFLUXDB" != "true" ]]; then
    if [[ ! -f "$INFLUXDB_BACKUP" ]]; then
        log_error "InfluxDB backup file not found: $INFLUXDB_BACKUP"
        exit 1
    fi
fi

if [[ "$SKIP_REDIS" != "true" ]]; then
    if [[ ! -f "$REDIS_BACKUP" ]]; then
        log_error "Redis backup file not found: $REDIS_BACKUP"
        exit 1
    fi
fi

# Confirmation prompt unless forced
if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
    echo ""
    echo "=========================================="
    echo "        DISASTER RECOVERY WARNING"
    echo "=========================================="
    echo ""
    echo "This will perform a FULL PLATFORM RESTORE"
    echo "This operation will:"
    echo "  - Stop all application services"
    echo "  - Overwrite all database contents"
    echo "  - Restore from the following backups:"
    echo ""
    
    if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
        echo "  PostgreSQL: $(basename "$POSTGRESQL_BACKUP")"
    fi
    
    if [[ "$SKIP_INFLUXDB" != "true" ]]; then
        echo "  InfluxDB:   $(basename "$INFLUXDB_BACKUP")"
    fi
    
    if [[ "$SKIP_REDIS" != "true" ]]; then
        echo "  Redis:      $(basename "$REDIS_BACKUP")"
    fi
    
    echo ""
    echo "Test mode: $TEST_MODE"
    echo "Expected downtime: 30-60 minutes"
    echo ""
    echo "=========================================="
    echo ""
    read -p "Are you ABSOLUTELY SURE you want to proceed? (type 'YES' to confirm): " -r
    
    if [[ "$REPLY" != "YES" ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# Initialize restore status tracking
RESTORE_STATUS="{"
RESTORE_STATUS+="\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
RESTORE_STATUS+="\"test_mode\":$TEST_MODE,"
RESTORE_STATUS+="\"force_mode\":$FORCE,"
RESTORE_STATUS+="\"dry_run\":$DRY_RUN,"
RESTORE_STATUS+="\"services\":{"
RESTORE_STATUS+="\"postgresql\":{\"status\":\"pending\",\"message\":\"\"},"
RESTORE_STATUS+="\"influxdb\":{\"status\":\"pending\",\"message\":\"\"},"
RESTORE_STATUS+="\"redis\":{\"status\":\"pending\",\"message\":\"\"}"
RESTORE_STATUS+="},"
RESTORE_STATUS+="\"overall_status\":\"in_progress\""
RESTORE_STATUS+="}"

# Function to update restore status
update_restore_status() {
    local service=$1
    local status=$2
    local message=$3
    
    RESTORE_STATUS=$(echo "$RESTORE_STATUS" | jq ".services.${service}.status = \"$status\"")
    RESTORE_STATUS=$(echo "$RESTORE_STATUS" | jq ".services.${service}.message = \"$message\"")
    
    # Write status to file
    echo "$RESTORE_STATUS" | jq . > "${RESTORE_DIR}/restore_status.json"
}

# Function to run restore with timeout
run_restore_with_timeout() {
    local service=$1
    local script_path=$2
    local backup_file=$3
    local additional_args=${4:-""}
    
    log_info "Starting $service restore..."
    update_restore_status "$service" "in_progress" "Restore in progress"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        additional_args="$additional_args --dry-run"
    fi
    
    if [[ "$TEST_MODE" == "true" ]]; then
        additional_args="$additional_args --test"
    fi
    
    if [[ "$FORCE" == "true" ]]; then
        additional_args="$additional_args --force"
    fi
    
    local restore_command="$script_path $additional_args $backup_file"
    log_info "Running command: $restore_command"
    
    if timeout "$TIMEOUT" bash -c "$restore_command" > "${RESTORE_DIR}/${service}_restore.log" 2>&1; then
        log_info "$service restore completed successfully"
        update_restore_status "$service" "completed" "Restore completed successfully"
        return 0
    else
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            log_error "$service restore timed out after $TIMEOUT seconds"
            update_restore_status "$service" "timeout" "Restore timed out"
        else
            log_error "$service restore failed with exit code $exit_code"
            update_restore_status "$service" "failed" "Restore failed"
        fi
        return $exit_code
    fi
}

# Step 1: Pre-restore validation
log_info "Step 1: Pre-restore validation"

if [[ "$DRY_RUN" != "true" ]]; then
    # Check if services are running
    log_info "Checking service status..."
    
    # Check PostgreSQL
    if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
        if ! check_service_health "postgresql" "postgresql" "5432"; then
            log_warning "PostgreSQL service not responding"
        fi
    fi
    
    # Check InfluxDB
    if [[ "$SKIP_INFLUXDB" != "true" ]]; then
        if ! check_service_health "influxdb" "influxdb" "8086"; then
            log_warning "InfluxDB service not responding"
        fi
    fi
    
    # Check Redis
    if [[ "$SKIP_REDIS" != "true" ]]; then
        if ! check_service_health "redis" "redis" "6379"; then
            log_warning "Redis service not responding"
        fi
    fi
else
    log_info "DRY RUN: Would check service status"
fi

# Step 2: Stop services
log_info "Step 2: Stopping services"

if [[ "$SKIP_SERVICES" != "true" && "$DRY_RUN" != "true" ]]; then
    log_info "Stopping application services..."
    
    # Scale down all deployments
    if kubectl scale deployment --all --replicas=0 -n grill-stats; then
        log_info "Deployments scaled down successfully"
    else
        log_warning "Failed to scale down some deployments"
    fi
    
    # Wait for pods to terminate
    log_info "Waiting for pods to terminate..."
    sleep 30
    
    # Check if any pods are still running
    RUNNING_PODS=$(kubectl get pods -n grill-stats --field-selector=status.phase=Running --no-headers | wc -l)
    if [[ $RUNNING_PODS -gt 0 ]]; then
        log_warning "$RUNNING_PODS pods still running, waiting longer..."
        sleep 30
    fi
    
    log_info "Services stopped"
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would stop application services"
fi

# Step 3: Database restoration
log_info "Step 3: Database restoration"

RESTORE_FAILED=false

# PostgreSQL restore
if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
    if ! run_restore_with_timeout "postgresql" "/scripts/postgresql-restore.sh" "$POSTGRESQL_BACKUP" "--skip-stop-services"; then
        RESTORE_FAILED=true
    fi
fi

# InfluxDB restore
if [[ "$SKIP_INFLUXDB" != "true" ]]; then
    if ! run_restore_with_timeout "influxdb" "/scripts/influxdb-restore.sh" "$INFLUXDB_BACKUP"; then
        RESTORE_FAILED=true
    fi
fi

# Redis restore
if [[ "$SKIP_REDIS" != "true" ]]; then
    if ! run_restore_with_timeout "redis" "/scripts/redis-restore.sh" "$REDIS_BACKUP"; then
        RESTORE_FAILED=true
    fi
fi

# Step 4: Start services
log_info "Step 4: Starting services"

if [[ "$SKIP_SERVICES" != "true" && "$TEST_MODE" != "true" && "$DRY_RUN" != "true" ]]; then
    log_info "Starting application services..."
    
    # Scale up deployments
    if kubectl scale deployment --all --replicas=1 -n grill-stats; then
        log_info "Deployments scaled up successfully"
    else
        log_warning "Failed to scale up some deployments"
    fi
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 60
    
    # Check pod readiness
    READY_PODS=$(kubectl get pods -n grill-stats --field-selector=status.phase=Running --no-headers | wc -l)
    log_info "$READY_PODS pods are running"
    
    log_info "Services started"
elif [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN: Would start application services"
fi

# Step 5: Post-restore validation
log_info "Step 5: Post-restore validation"

if [[ "$DRY_RUN" != "true" ]]; then
    # Health checks
    log_info "Performing health checks..."
    
    # PostgreSQL health check
    if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
        if check_service_health "postgresql" "postgresql" "5432"; then
            log_info "PostgreSQL health check passed"
        else
            log_error "PostgreSQL health check failed"
            RESTORE_FAILED=true
        fi
    fi
    
    # InfluxDB health check
    if [[ "$SKIP_INFLUXDB" != "true" ]]; then
        if check_service_health "influxdb" "influxdb" "8086"; then
            log_info "InfluxDB health check passed"
        else
            log_error "InfluxDB health check failed"
            RESTORE_FAILED=true
        fi
    fi
    
    # Redis health check
    if [[ "$SKIP_REDIS" != "true" ]]; then
        if check_service_health "redis" "redis" "6379"; then
            log_info "Redis health check passed"
        else
            log_error "Redis health check failed"
            RESTORE_FAILED=true
        fi
    fi
else
    log_info "DRY RUN: Would perform health checks"
fi

# Generate final report
log_info "Generating final restore report..."

FINAL_STATUS="completed"
if [[ "$RESTORE_FAILED" == "true" ]]; then
    FINAL_STATUS="failed"
elif [[ "$DRY_RUN" == "true" ]]; then
    FINAL_STATUS="dry_run_completed"
fi

RESTORE_STATUS=$(echo "$RESTORE_STATUS" | jq ".overall_status = \"$FINAL_STATUS\"")
RESTORE_STATUS=$(echo "$RESTORE_STATUS" | jq ".completed_at = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"")
RESTORE_STATUS=$(echo "$RESTORE_STATUS" | jq ".duration_seconds = $(( $(date +%s) - $(date -d "$RESTORE_TIMESTAMP" +%s) ))")

# Write final status
echo "$RESTORE_STATUS" | jq . > "${RESTORE_DIR}/restore_status.json"

# Create human-readable report
RESTORE_REPORT_FILE="${RESTORE_DIR}/full_restore_report.txt"
cat > "$RESTORE_REPORT_FILE" <<EOF
Full Platform Restore Report
============================
Generated: $(date)
Status: $FINAL_STATUS

Configuration:
- Test Mode: $TEST_MODE
- Force Mode: $FORCE
- Dry Run: $DRY_RUN
- Timeout: $TIMEOUT seconds

Services Restored:
EOF

if [[ "$SKIP_POSTGRESQL" != "true" ]]; then
    PG_STATUS=$(echo "$RESTORE_STATUS" | jq -r '.services.postgresql.status')
    PG_MESSAGE=$(echo "$RESTORE_STATUS" | jq -r '.services.postgresql.message')
    echo "- PostgreSQL: $PG_STATUS - $PG_MESSAGE" >> "$RESTORE_REPORT_FILE"
fi

if [[ "$SKIP_INFLUXDB" != "true" ]]; then
    INFLUX_STATUS=$(echo "$RESTORE_STATUS" | jq -r '.services.influxdb.status')
    INFLUX_MESSAGE=$(echo "$RESTORE_STATUS" | jq -r '.services.influxdb.message')
    echo "- InfluxDB: $INFLUX_STATUS - $INFLUX_MESSAGE" >> "$RESTORE_REPORT_FILE"
fi

if [[ "$SKIP_REDIS" != "true" ]]; then
    REDIS_STATUS=$(echo "$RESTORE_STATUS" | jq -r '.services.redis.status')
    REDIS_MESSAGE=$(echo "$RESTORE_STATUS" | jq -r '.services.redis.message')
    echo "- Redis: $REDIS_STATUS - $REDIS_MESSAGE" >> "$RESTORE_REPORT_FILE"
fi

DURATION=$(echo "$RESTORE_STATUS" | jq -r '.duration_seconds')
echo "" >> "$RESTORE_REPORT_FILE"
echo "Duration: $DURATION seconds" >> "$RESTORE_REPORT_FILE"

# Send notification
if [[ "$FINAL_STATUS" == "completed" ]]; then
    if [[ "$TEST_MODE" == "true" ]]; then
        send_notification "success" "$SERVICE_NAME" "Test restore completed successfully"
    else
        send_notification "success" "$SERVICE_NAME" "Full platform restore completed successfully"
    fi
elif [[ "$FINAL_STATUS" == "failed" ]]; then
    send_notification "error" "$SERVICE_NAME" "Full platform restore failed"
elif [[ "$FINAL_STATUS" == "dry_run_completed" ]]; then
    send_notification "info" "$SERVICE_NAME" "Dry run full platform restore completed"
fi

log_info "Full platform restore process completed at $(date)"
log_info "Final status: $FINAL_STATUS"
log_info "Restore report: $RESTORE_REPORT_FILE"
log_info "Restore status: ${RESTORE_DIR}/restore_status.json"

# Exit with appropriate code
if [[ "$FINAL_STATUS" == "failed" ]]; then
    exit 1
else
    exit 0
fi