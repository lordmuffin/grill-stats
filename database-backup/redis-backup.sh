#!/bin/bash
# Redis Backup Script for Grill Stats
# This script creates automated backups of Redis data by triggering BGSAVE
# and copying the resulting RDB file to a backup location

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
BACKUP_DIR="/backups/redis"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=30  # Keep backups for 30 days
REDIS_HOST=${REDIS_HOST:-"redis"}
REDIS_PORT=${REDIS_PORT:-"6379"}
REDIS_PASSWORD=${REDIS_PASSWORD:-""}
ENVIRONMENT=${ENVIRONMENT:-"development"}

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}/daily"
mkdir -p "${BACKUP_DIR}/weekly"
mkdir -p "${BACKUP_DIR}/monthly"

# Log function
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Backup function
perform_backup() {
  log "Starting Redis backup"

  # Create backup filename
  BACKUP_FILE="${BACKUP_DIR}/daily/redis_${TIMESTAMP}.rdb"

  # Trigger BGSAVE on Redis server
  AUTH_PARAM=""
  if [ -n "${REDIS_PASSWORD}" ]; then
    AUTH_PARAM="-a ${REDIS_PASSWORD}"
  fi

  redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ${AUTH_PARAM} BGSAVE

  # Wait for BGSAVE to complete
  log "Waiting for BGSAVE to complete..."
  sleep 5

  # Determine Redis container name
  REDIS_CONTAINER=$(docker ps --format '{{.Names}}' | grep redis | head -n 1)

  if [ -z "${REDIS_CONTAINER}" ]; then
    log "ERROR: Redis container not found!"
    exit 1
  fi

  # Copy the dump.rdb file from the container
  log "Copying RDB file from container ${REDIS_CONTAINER}..."
  docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${BACKUP_FILE}"

  # Check if backup was successful
  if [ -f "${BACKUP_FILE}" ]; then
    log "Backup successfully created: ${BACKUP_FILE}"

    # Compress the backup
    gzip -f "${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE}.gz"

    # Calculate backup size
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "Backup size: ${BACKUP_SIZE}"

    # Create symbolic links for weekly and monthly backups
    DAY_OF_WEEK=$(date +"%u")
    DAY_OF_MONTH=$(date +"%d")

    # Weekly backup (on Sunday, day 7)
    if [ "${DAY_OF_WEEK}" = "7" ]; then
      WEEK_NUMBER=$(date +"%U")
      ln -sf "${BACKUP_FILE}" "${BACKUP_DIR}/weekly/redis_week${WEEK_NUMBER}.rdb.gz"
      log "Created weekly backup link for week ${WEEK_NUMBER}"
    fi

    # Monthly backup (on 1st day of month)
    if [ "${DAY_OF_MONTH}" = "01" ]; then
      MONTH_NAME=$(date +"%b")
      ln -sf "${BACKUP_FILE}" "${BACKUP_DIR}/monthly/redis_${MONTH_NAME}.rdb.gz"
      log "Created monthly backup link for ${MONTH_NAME}"
    fi
  else
    log "ERROR: Backup failed!"
    exit 1
  fi
}

# Clean old backups
cleanup_old_backups() {
  log "Cleaning up old backups (older than ${RETENTION_DAYS} days)"
  find "${BACKUP_DIR}/daily" -name "*.rdb.gz" -type f -mtime +${RETENTION_DAYS} -delete
  log "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
  log "Verifying backup integrity for ${BACKUP_FILE}"

  # Check file size is reasonable (not empty or too small)
  FILE_SIZE=$(stat -c%s "${BACKUP_FILE}")

  if [ "${FILE_SIZE}" -lt 1024 ]; then
    log "ERROR: Backup file is too small (${FILE_SIZE} bytes), might be corrupted!"
    exit 1
  else
    log "Backup verification successful - file size is ${FILE_SIZE} bytes"
  fi
}

# Main execution
log "=== Redis Backup Script ==="
log "Environment: ${ENVIRONMENT}"
log "Redis server: ${REDIS_HOST}:${REDIS_PORT}"

# Perform backup
perform_backup

# Verify the latest backup
verify_backup

# Clean up old backups
cleanup_old_backups

log "Backup process completed successfully"
exit 0
