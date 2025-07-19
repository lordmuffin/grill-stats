#!/bin/bash
# InfluxDB Backup Script for Grill Stats
# This script creates automated backups of InfluxDB time-series data with retention policies
# It supports both Docker Compose and Kubernetes environments

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
BACKUP_DIR="/backups/influxdb"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=30  # Keep backups for 30 days
INFLUXDB_HOST=${INFLUXDB_HOST:-"influxdb"}
INFLUXDB_PORT=${INFLUXDB_PORT:-"8086"}
INFLUXDB_DATABASE=${INFLUXDB_DATABASE:-"grill_stats"}
INFLUXDB_USERNAME=${INFLUXDB_USERNAME:-"admin"}
INFLUXDB_PASSWORD=${INFLUXDB_PASSWORD:-"influx-password"}
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
  log "Starting InfluxDB backup for ${INFLUXDB_DATABASE}"

  # Create backup directory
  BACKUP_PATH="${BACKUP_DIR}/daily/${INFLUXDB_DATABASE}_${TIMESTAMP}"
  mkdir -p "${BACKUP_PATH}"

  # Execute influxd backup
  # Note: For InfluxDB 1.8, we use the influxd backup command
  influxd backup \
    -database "${INFLUXDB_DATABASE}" \
    -host "${INFLUXDB_HOST}:${INFLUXDB_PORT}" \
    -retention autogen \
    "${BACKUP_PATH}"

  # Check if backup was successful
  if [ $? -eq 0 ]; then
    log "Backup successfully created: ${BACKUP_PATH}"

    # Compress the backup
    tar -czf "${BACKUP_PATH}.tar.gz" -C "${BACKUP_DIR}/daily" "$(basename "${BACKUP_PATH}")"
    rm -rf "${BACKUP_PATH}"  # Remove uncompressed backup

    # Calculate backup size
    BACKUP_SIZE=$(du -h "${BACKUP_PATH}.tar.gz" | cut -f1)
    log "Backup size: ${BACKUP_SIZE}"

    # Create symbolic links for weekly and monthly backups
    DAY_OF_WEEK=$(date +"%u")
    DAY_OF_MONTH=$(date +"%d")

    # Weekly backup (on Sunday, day 7)
    if [ "${DAY_OF_WEEK}" = "7" ]; then
      WEEK_NUMBER=$(date +"%U")
      ln -sf "${BACKUP_PATH}.tar.gz" "${BACKUP_DIR}/weekly/${INFLUXDB_DATABASE}_week${WEEK_NUMBER}.tar.gz"
      log "Created weekly backup link for week ${WEEK_NUMBER}"
    fi

    # Monthly backup (on 1st day of month)
    if [ "${DAY_OF_MONTH}" = "01" ]; then
      MONTH_NAME=$(date +"%b")
      ln -sf "${BACKUP_PATH}.tar.gz" "${BACKUP_DIR}/monthly/${INFLUXDB_DATABASE}_${MONTH_NAME}.tar.gz"
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
  find "${BACKUP_DIR}/daily" -name "*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete
  log "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
  log "Verifying backup integrity"

  # Extract backup to a temporary location without overwriting the original database
  TMP_EXTRACT="/tmp/influxdb_verify_${TIMESTAMP}"
  mkdir -p "${TMP_EXTRACT}"

  tar -xzf "${BACKUP_PATH}.tar.gz" -C "${TMP_EXTRACT}"

  # Check if files exist and are not empty
  MANIFEST_FILE=$(find "${TMP_EXTRACT}" -name "*.manifest" | head -n 1)

  if [ -s "${MANIFEST_FILE}" ]; then
    log "Backup verification successful - manifest file exists and is not empty"
    rm -rf "${TMP_EXTRACT}"  # Clean up
  else
    log "ERROR: Backup verification failed - manifest file is missing or empty!"
    rm -rf "${TMP_EXTRACT}"  # Clean up
    exit 1
  fi
}

# Main execution
log "=== InfluxDB Backup Script ==="
log "Environment: ${ENVIRONMENT}"
log "Database: ${INFLUXDB_DATABASE} on ${INFLUXDB_HOST}:${INFLUXDB_PORT}"

# Perform backup
perform_backup

# Verify the latest backup
verify_backup

# Clean up old backups
cleanup_old_backups

log "Backup process completed successfully"
exit 0
