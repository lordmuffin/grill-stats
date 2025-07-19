#!/bin/bash
# Database setup script for encrypted credential storage
# This script sets up all necessary database tables and functions

set -euo pipefail

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-grill_stats}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATABASE_INIT_DIR="${SCRIPT_DIR}/../database-init"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to run SQL file
run_sql_file() {
    local file_path="$1"
    local description="$2"

    print_status "Running $description..."

    if [ ! -f "$file_path" ]; then
        print_error "SQL file not found: $file_path"
        return 1
    fi

    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$file_path"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$file_path"
    fi

    if [ $? -eq 0 ]; then
        print_status "✓ $description completed successfully"
    else
        print_error "✗ $description failed"
        return 1
    fi
}

# Function to test database connection
test_connection() {
    print_status "Testing database connection..."

    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1
    fi

    if [ $? -eq 0 ]; then
        print_status "✓ Database connection successful"
    else
        print_error "✗ Failed to connect to database"
        print_error "Please check your database connection settings:"
        print_error "  Host: $DB_HOST"
        print_error "  Port: $DB_PORT"
        print_error "  Database: $DB_NAME"
        print_error "  User: $DB_USER"
        exit 1
    fi
}

# Function to check if table exists
table_exists() {
    local table_name="$1"

    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 FROM information_schema.tables WHERE table_name = '$table_name';" -t | grep -q 1
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 FROM information_schema.tables WHERE table_name = '$table_name';" -t | grep -q 1
    fi
}

# Function to backup existing data
backup_existing_data() {
    print_status "Creating backup of existing data..."

    local backup_dir="${SCRIPT_DIR}/../backups"
    mkdir -p "$backup_dir"

    local backup_file="${backup_dir}/grill_stats_backup_$(date +%Y%m%d_%H%M%S).sql"

    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$backup_file"
    else
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$backup_file"
    fi

    if [ $? -eq 0 ]; then
        print_status "✓ Backup created: $backup_file"
    else
        print_warning "⚠ Backup failed, continuing with setup"
    fi
}

# Function to validate setup
validate_setup() {
    print_status "Validating database setup..."

    # Check if required tables exist
    declare -a required_tables=(
        "users"
        "thermoworks_credentials"
        "credential_access_log"
        "encryption_key_management"
    )

    for table in "${required_tables[@]}"; do
        if table_exists "$table"; then
            print_status "✓ Table '$table' exists"
        else
            print_error "✗ Table '$table' is missing"
            return 1
        fi
    done

    # Check if required functions exist
    print_status "Checking required functions..."

    if [ -n "$DB_PASSWORD" ]; then
        function_count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM information_schema.routines WHERE routine_name IN ('validate_thermoworks_credentials', 'log_credential_access', 'get_credential_security_metrics');" -t | xargs)
    else
        function_count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM information_schema.routines WHERE routine_name IN ('validate_thermoworks_credentials', 'log_credential_access', 'get_credential_security_metrics');" -t | xargs)
    fi

    if [ "$function_count" -eq 3 ]; then
        print_status "✓ All required functions exist"
    else
        print_error "✗ Some required functions are missing"
        return 1
    fi

    print_status "✓ Database setup validation successful"
}

# Function to display security metrics
display_security_metrics() {
    print_status "Displaying security metrics..."

    if [ -n "$DB_PASSWORD" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT * FROM get_credential_security_metrics();"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT * FROM get_credential_security_metrics();"
    fi
}

# Main execution
main() {
    print_status "Starting database setup for encrypted credential storage..."
    print_status "Database: $DB_NAME at $DB_HOST:$DB_PORT"

    # Test database connection
    test_connection

    # Create backup if tables exist
    if table_exists "users"; then
        backup_existing_data
    fi

    # Run database setup scripts in order
    print_status "Setting up database schema..."

    # 1. Run basic postgres initialization if needed
    if [ -f "${DATABASE_INIT_DIR}/postgres-init.sql" ]; then
        run_sql_file "${DATABASE_INIT_DIR}/postgres-init.sql" "Basic PostgreSQL initialization"
    fi

    # 2. Set up encrypted credentials
    run_sql_file "${DATABASE_INIT_DIR}/setup-encrypted-credentials.sql" "Encrypted credential storage setup"

    # 3. Run any additional migrations
    if [ -f "${DATABASE_INIT_DIR}/migrate-to-encrypted-credentials.sql" ]; then
        run_sql_file "${DATABASE_INIT_DIR}/migrate-to-encrypted-credentials.sql" "Encrypted credential migration"
    fi

    # Validate the setup
    validate_setup

    # Display security metrics
    display_security_metrics

    print_status "Database setup completed successfully!"
    echo ""
    print_status "Next steps:"
    echo "1. Set up HashiCorp Vault Transit Engine"
    echo "2. Deploy the encryption service"
    echo "3. Configure authentication service to use encrypted credentials"
    echo "4. Test the complete encryption flow"
}

# Handle command line arguments
case "${1:-}" in
    "test")
        test_connection
        ;;
    "validate")
        validate_setup
        ;;
    "backup")
        backup_existing_data
        ;;
    "metrics")
        display_security_metrics
        ;;
    *)
        main
        ;;
esac
