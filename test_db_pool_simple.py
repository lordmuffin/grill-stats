#!/usr/bin/env python3
"""
Simple Database Connection Pool Test

This script tests the database connection pooling implementation
without requiring the full application context.

Note: This test uses SQLite which uses a SingletonThreadPool, which behaves
differently from the QueuePool used with PostgreSQL in production. In a
SingletonThreadPool, connection statistics won't change as we open and close
connections because SQLite connections are maintained per-thread rather than
in a true connection pool.

For a complete test of PostgreSQL connection pooling, use the app.py's
production configuration with a PostgreSQL database.
"""

import logging
import os
import time
from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy pool parameters
POOL_SIZE = 5
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600


def create_test_engine() -> Engine:
    """Create a test SQLAlchemy engine with connection pooling."""
    # Use PostgreSQL-style parameters for testing
    # For SQLite, we need to use different parameters as it uses SingletonThreadPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},  # Allow cross-thread usage
        pool_pre_ping=True,
    )
    return engine


def get_pool_status(engine: Engine) -> Dict[str, Any]:
    """Get the current status of the connection pool."""
    pool = engine.pool

    # Different pool types have different attributes/methods
    # Handle both QueuePool (PostgreSQL) and SingletonThreadPool (SQLite)
    try:
        # For QueuePool
        if hasattr(pool, "size") and callable(pool.size):
            return {
                "size": pool.size(),
                "checkedin": pool.checkedin(),
                "overflow": pool.overflow(),
                "checkedout": pool.checkedout(),
            }
        # For SingletonThreadPool or other pool types
        return {
            "size": getattr(pool, "size", 0),
            "checkedout": getattr(pool, "_connections", 0),
            "pool_type": pool.__class__.__name__,
        }
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return {"error": str(e)}


def run_test():
    """Test the connection pool functionality."""
    logger.info("Testing SQLAlchemy connection pooling")
    engine = create_test_engine()

    # Create a test table
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"))
        conn.execute(text("INSERT INTO test (id, value) VALUES (1, 'test')"))

    logger.info(f"Initial pool status: {get_pool_status(engine)}")

    # Test multiple connections
    connections = []
    for i in range(POOL_SIZE + 2):  # Test with more connections than pool_size
        logger.info(f"Creating connection {i + 1}")
        conn = engine.connect()
        result = conn.execute(text("SELECT * FROM test")).fetchone()
        logger.info(f"Query result: {result}")
        connections.append(conn)
        logger.info(f"Pool status after connection {i + 1}: {get_pool_status(engine)}")
        time.sleep(0.5)

    # Return connections to the pool
    logger.info("Returning connections to the pool")
    for i, conn in enumerate(connections):
        conn.close()
        logger.info(f"Pool status after closing connection {i + 1}: {get_pool_status(engine)}")
        time.sleep(0.5)

    logger.info(f"Final pool status: {get_pool_status(engine)}")
    logger.info("Test completed successfully!")


def print_postgresql_test_instructions():
    """Print instructions for testing with PostgreSQL"""
    logger.info("\n")
    logger.info("===== PostgreSQL Connection Pool Testing =====")
    logger.info("For a complete test with PostgreSQL connection pooling:")
    logger.info("1. Set up a PostgreSQL database and configure connection string in .env")
    logger.info("2. Run the application with FLASK_DEBUG=true to see connection pool logs")
    logger.info("3. Use the /api/database/pool endpoint to monitor pool statistics")
    logger.info("4. For load testing, run multiple concurrent requests to test pool behavior")
    logger.info("   Example: ab -c 20 -n 100 http://localhost:5001/health")
    logger.info("\n")


if __name__ == "__main__":
    run_test()
    print_postgresql_test_instructions()
