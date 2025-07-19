#!/bin/bash
# PostgreSQL Backup Script for Grill Stats
# This script creates automated backups of PostgreSQL database with retention policies
# It supports both Docker Compose and Kubernetes environments

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=30  # Keep backups for 30 days
DB_NAME=${DB_NAME:-"grill_stats"}
DB_USER=${DB_USER:-"postgres"}
DB_PASSWORD=${DB_PASSWORD:-"postgres"}
DB_HOST=${DB_HOST:-"postgres"}
DB_PORT=${DB_PORT:-"5432"}
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
  log "Starting PostgreSQL backup for ${DB_NAME}"

  # Create backup filename
  BACKUP_FILE="${BACKUP_DIR}/daily/${DB_NAME}_${TIMESTAMP}.sql.gz"

  # Execute pg_dump
  PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -F c \
    -b \
    -v \
    -f "${BACKUP_FILE%.gz}"

  # Compress the backup
  gzip -f "${BACKUP_FILE%.gz}"

  # Check if backup was successful
  if [ $? -eq 0 ]; then
    log "Backup successfully created: ${BACKUP_FILE}"

    # Calculate backup size
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "Backup size: ${BACKUP_SIZE}"

    # Create symbolic links for weekly and monthly backups
    DAY_OF_WEEK=$(date +"%u")
    DAY_OF_MONTH=$(date +"%d")

    # Weekly backup (on Sunday, day 7)
    if [ "${DAY_OF_WEEK}" = "7" ]; then
      WEEK_NUMBER=$(date +"%U")
      ln -sf "${BACKUP_FILE}" "${BACKUP_DIR}/weekly/${DB_NAME}_week${WEEK_NUMBER}.sql.gz"
      log "Created weekly backup link for week ${WEEK_NUMBER}"
    fi

    # Monthly backup (on 1st day of month)
    if [ "${DAY_OF_MONTH}" = "01" ]; then
      MONTH_NAME=$(date +"%b")
      ln -sf "${BACKUP_FILE}" "${BACKUP_DIR}/monthly/${DB_NAME}_${MONTH_NAME}.sql.gz"
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
  find "${BACKUP_DIR}/daily" -name "*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
  log "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
  log "Verifying backup integrity for ${BACKUP_FILE}"

  # Test the backup file with pg_restore (without actually restoring)
  PGPASSWORD="${DB_PASSWORD}" pg_restore -l "${BACKUP_FILE}" > /dev/null

  if [ $? -eq 0 ]; then
    log "Backup verification successful"

    # For production environment, consider additional verification like test restore to temporary database
    if [ "${ENVIRONMENT}" = "production" ]; then
      log "Production environment detected. Consider setting up test restore verification."
    fi
  else
    log "ERROR: Backup verification failed!"
    exit 1
  fi
}

# Main execution
log "=== PostgreSQL Backup Script ==="
log "Environment: ${ENVIRONMENT}"
log "Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"

# Perform backup
perform_backup

# Verify the latest backup
verify_backup

# Clean up old backups
cleanup_old_backups

log "Backup process completed successfully"
exit 0
