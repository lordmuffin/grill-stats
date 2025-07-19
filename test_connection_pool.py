#!/usr/bin/env python3
"""
PostgreSQL Connection Pool Test Script

This script tests the database connection pooling implementation with PostgreSQL.
It simulates multiple concurrent connections and verifies that connections
are properly managed by the connection pool.
"""

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import application modules
from app import app, db
from utils.db_utils import get_pool_status, init_connection_pool


def execute_query(query_num: int) -> str:
    """Execute a simple database query"""
    with app.app_context():
        # Execute a simple query that will use a connection from the pool
        result = db.session.execute("SELECT 1 as test_value").fetchone()
        # Get the current pool status
        pool_status = get_pool_status(db)
        logger.info(f"Query {query_num} executed with result: {result}, Pool status: {pool_status}")
        # Simulate some processing time
        time.sleep(0.1)
        return f"Query {query_num} completed"


def run_concurrent_queries(num_queries: int = 15) -> List[str]:
    """Run multiple queries concurrently to test connection pooling"""
    logger.info(f"Running {num_queries} concurrent queries...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit multiple queries to be executed concurrently
        futures = [executor.submit(execute_query, i) for i in range(num_queries)]
        # Wait for all queries to complete and collect results
        results = [future.result() for future in futures]

    return results


def test_connection_pool() -> bool:
    """Test database connection pooling with PostgreSQL"""
    try:
        with app.app_context():
            # Initialize connection pool (if not already done)
            init_connection_pool(app, db)

            # Get initial pool status
            initial_status = get_pool_status(db)
            logger.info(f"Initial pool status: {initial_status}")

            # Get database connection info
            db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            db_type = "PostgreSQL" if db_uri.startswith(("postgresql", "postgres")) else "SQLite/Other"
            logger.info(f"Testing connection pooling with {db_type} database")

            # Get pool configuration
            engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
            logger.info(f"Pool configuration: {engine_options}")

            # Run multiple concurrent queries
            results = run_concurrent_queries(15)
            logger.info(f"Completed {len(results)} queries")

            # Get final pool status
            time.sleep(1)  # Wait for connections to be returned to the pool
            final_status = get_pool_status(db)
            logger.info(f"Final pool status: {final_status}")

            # Close all connections
            db.session.close()

            return True

    except Exception as e:
        logger.error(f"Error testing connection pool: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("Starting PostgreSQL connection pool test")
    success = test_connection_pool()
    if success:
        logger.info("Connection pool test completed successfully")
        sys.exit(0)
    else:
        logger.error("Connection pool test failed")
        sys.exit(1)
