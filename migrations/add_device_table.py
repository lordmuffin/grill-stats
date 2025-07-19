"""
Database migration script to add Device table
This script can be run independently or integrated with Flask-Migrate
"""

import logging
import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import our models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_device_table_sql():
    """SQL commands to create the device table"""
    return """
    -- Create devices table
    CREATE TABLE IF NOT EXISTS devices (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        device_id VARCHAR(50) UNIQUE NOT NULL,
        nickname VARCHAR(100),
        status VARCHAR(20) DEFAULT 'offline',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);
    CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
    CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(is_active);
    CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

    -- Create trigger to update updated_at timestamp
    CREATE OR REPLACE FUNCTION update_device_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trigger_update_device_updated_at ON devices;
    CREATE TRIGGER trigger_update_device_updated_at
        BEFORE UPDATE ON devices
        FOR EACH ROW
        EXECUTE FUNCTION update_device_updated_at();
    """


def rollback_device_table_sql():
    """SQL commands to rollback the device table creation"""
    return """
    -- Drop trigger and function
    DROP TRIGGER IF EXISTS trigger_update_device_updated_at ON devices;
    DROP FUNCTION IF EXISTS update_device_updated_at();

    -- Drop indexes
    DROP INDEX IF EXISTS idx_devices_status;
    DROP INDEX IF EXISTS idx_devices_active;
    DROP INDEX IF EXISTS idx_devices_device_id;
    DROP INDEX IF EXISTS idx_devices_user_id;

    -- Drop table
    DROP TABLE IF EXISTS devices;
    """


def run_migration_with_flask():
    """Run migration using Flask application context"""
    try:
        app = Flask(__name__)
        app.config.from_object(Config)
        db = SQLAlchemy(app)

        with app.app_context():
            # Check if we're using PostgreSQL
            if "postgresql" in app.config["SQLALCHEMY_DATABASE_URI"]:
                # Use raw SQL for PostgreSQL
                db.engine.execute(create_device_table_sql())
                logger.info("Successfully created devices table using PostgreSQL SQL")
            else:
                # Use SQLAlchemy for SQLite or other databases
                from models.device import Device
                from models.user import User

                # Initialize models
                device_manager = Device(db)
                user_manager = User(db)

                # Create all tables
                db.create_all()
                logger.info("Successfully created devices table using SQLAlchemy")

            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def run_migration_direct():
    """Run migration directly using database connection"""
    try:
        from urllib.parse import urlparse

        import psycopg2

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL environment variable not set")
            return False

        # Parse database URL
        parsed = urlparse(db_url)

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading '/'
            user=parsed.username,
            password=parsed.password,
        )

        with conn.cursor() as cursor:
            cursor.execute(create_device_table_sql())
            conn.commit()

        conn.close()
        logger.info("Successfully created devices table using direct connection")
        return True

    except ImportError:
        logger.warning("psycopg2 not available for direct connection")
        return False
    except Exception as e:
        logger.error(f"Direct migration failed: {e}")
        return False


def verify_migration():
    """Verify that the migration was successful"""
    try:
        app = Flask(__name__)
        app.config.from_object(Config)
        db = SQLAlchemy(app)

        with app.app_context():
            # Try to query the devices table
            result = db.engine.execute("SELECT COUNT(*) FROM devices")
            count = result.fetchone()[0]
            logger.info(f"Devices table exists with {count} records")

            # Check if indexes exist (PostgreSQL specific)
            if "postgresql" in app.config["SQLALCHEMY_DATABASE_URI"]:
                result = db.engine.execute(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'devices'
                """
                )
                indexes = [row[0] for row in result.fetchall()]
                logger.info(f"Found indexes: {indexes}")

            return True

    except Exception as e:
        logger.error(f"Migration verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting device table migration...")

    # Try Flask-based migration first
    success = run_migration_with_flask()

    # If that fails, try direct connection
    if not success:
        logger.info("Trying direct database connection...")
        success = run_migration_direct()

    if success:
        logger.info("Migration completed successfully")

        # Verify the migration
        if verify_migration():
            logger.info("Migration verification passed")
        else:
            logger.warning("Migration verification failed")
    else:
        logger.error("Migration failed")
        sys.exit(1)
