"""
Test script for database connection pooling.

This script tests the database connection pooling utilities to ensure they
are working correctly.
"""

import os
import sys
import time

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the required modules
from app import app, db
from utils.db_utils import get_pool_status, init_connection_pool


def test_db_pool():
    """Test database connection pool initialization and status."""
    print("Testing database connection pooling...")

    # Initialize the connection pool
    with app.app_context():
        # Initialize the connection pool if not already initialized
        init_connection_pool(app, db)

        # Get the pool status
        try:
            pool_status = get_pool_status(db)
            print(f"Pool status: {pool_status}")

            # Test pool configuration
            engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
            print(f"Pool configuration: {engine_options}")

            # Basic validation
            assert "pool_size" in engine_options, "pool_size should be configured"
            assert "max_overflow" in engine_options, "max_overflow should be configured"
            assert "pool_recycle" in engine_options, "pool_recycle should be configured"

            print("Connection pooling configuration test passed!")

            # Test multiple connections
            print("Testing multiple connections...")
            for i in range(3):
                # Run a simple query to get a connection from the pool
                db.session.execute("SELECT 1").fetchone()
                print(f"Connection {i+1} executed, pool status: {get_pool_status(db)}")
                time.sleep(0.5)

            # Close all connections
            print("Closing all connections...")
            db.session.close()

            # Get final pool status
            print(f"Final pool status: {get_pool_status(db)}")

            print("Database connection pooling test completed successfully!")
            return True
        except Exception as e:
            print(f"Error testing database connection pool: {e}")
            return False


if __name__ == "__main__":
    success = test_db_pool()
    if not success:
        sys.exit(1)
