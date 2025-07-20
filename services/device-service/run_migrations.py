#!/usr/bin/env python3
"""
Database Migration Script

This script runs Alembic migrations to manage database schema changes.
It can also generate new migration scripts based on model changes.
"""

import argparse
import logging
import os
import sys

from alembic import command
from alembic.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("migrations")


def get_alembic_config():
    """Get Alembic configuration"""
    alembic_cfg = Config("alembic.ini")

    # Override database URL from environment variables if provided
    if os.environ.get("DB_HOST") and os.environ.get("DB_NAME"):
        db_url = f"postgresql://{os.environ.get('DB_USER', 'postgres')}:{os.environ.get('DB_PASSWORD', 'postgres')}@{os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT', '5432')}/{os.environ.get('DB_NAME')}"
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    return alembic_cfg


def create_migration(message):
    """Create a new migration script"""
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, message=message, autogenerate=True)
    logger.info(f"Created new migration with message: {message}")


def upgrade_database(revision="head"):
    """Upgrade the database to the specified revision"""
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)
    logger.info(f"Upgraded database to revision: {revision}")


def downgrade_database(revision="-1"):
    """Downgrade the database to the specified revision"""
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)
    logger.info(f"Downgraded database to revision: {revision}")


def show_history():
    """Show migration history"""
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg, verbose=True)


def show_current_revision():
    """Show current database revision"""
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg, verbose=True)


def init_migrations():
    """Initialize migrations"""
    alembic_cfg = get_alembic_config()
    command.stamp(alembic_cfg, "head")
    logger.info("Initialized migrations")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Database migration script")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Create migration
    create_parser = subparsers.add_parser("create", help="Create a new migration")
    create_parser.add_argument("message", help="Migration message")

    # Upgrade database
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database")
    upgrade_parser.add_argument("--revision", default="head", help="Revision to upgrade to")

    # Downgrade database
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database")
    downgrade_parser.add_argument("--revision", default="-1", help="Revision to downgrade to")

    # History
    subparsers.add_parser("history", help="Show migration history")

    # Current
    subparsers.add_parser("current", help="Show current database revision")

    # Init
    subparsers.add_parser("init", help="Initialize migrations")

    args = parser.parse_args()

    # Execute command
    if args.command == "create":
        create_migration(args.message)
    elif args.command == "upgrade":
        upgrade_database(args.revision)
    elif args.command == "downgrade":
        downgrade_database(args.revision)
    elif args.command == "history":
        show_history()
    elif args.command == "current":
        show_current_revision()
    elif args.command == "init":
        init_migrations()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
