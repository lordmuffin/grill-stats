"""
Simple script to test database connection pooling.

This script can be run directly without installing all dependencies.
It tests the basic functionality of SQLAlchemy connection pooling.
"""

import logging
import time
from typing import Any, Dict

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_engine() -> Engine:
    """Create a test SQLAlchemy engine with connection pooling."""
    # Using SQLite memory database for simplicity
    engine = create_engine(
        "sqlite:///:memory:",
        echo=True,  # Show SQL queries
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    return engine


def get_pool_status(engine: Engine) -> Dict[str, Any]:
    """Get the current status of the connection pool."""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checkedin": pool.checkedin(),
        "overflow": pool.overflow(),
        "checkedout": pool.checkedout(),
    }


def test_connection_pool() -> None:
    """Test the connection pool functionality."""
    engine = create_test_engine()

    # Create a test table
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"))
        conn.execute(text("INSERT INTO test (id, value) VALUES (1, 'test')"))
        conn.commit()

    logger.info("Initial pool status: %s", get_pool_status(engine))

    # Test multiple connections
    connections = []
    for i in range(3):
        logger.info("Creating connection %d", i + 1)
        conn = engine.connect()
        result = conn.execute(text("SELECT * FROM test")).fetchone()
        logger.info("Query result: %s", result)
        connections.append(conn)
        logger.info("Pool status after connection %d: %s", i + 1, get_pool_status(engine))
        time.sleep(1)

    # Return connections to the pool
    logger.info("Returning connections to the pool")
    for i, conn in enumerate(connections):
        conn.close()
        logger.info("Pool status after closing connection %d: %s", i + 1, get_pool_status(engine))
        time.sleep(1)

    logger.info("Final pool status: %s", get_pool_status(engine))


if __name__ == "__main__":
    logger.info("Testing SQLAlchemy connection pooling")
    test_connection_pool()
    logger.info("Test completed successfully!")
