"""
Database utilities for connection pooling and management.

This module provides utilities for optimizing database connections,
implementing connection pooling, and monitoring database performance.
It builds on SQLAlchemy's built-in connection pooling capabilities
to provide a robust, efficient, and monitored database connection system.
"""

import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TypeVar, Union, cast

from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool, QueuePool
from sqlalchemy.pool.base import _ConnectionRecord

# Setup logging
logger = logging.getLogger(__name__)

# Type variable for function decorators
F = TypeVar("F", bound=Callable[..., Any])


def init_connection_pool(app: Flask, db: SQLAlchemy) -> None:
    """
    Initialize SQLAlchemy connection pooling with optimized settings.
    
    This function configures SQLAlchemy connection pooling based on
    the application configuration. It sets up event listeners for
    connection pool events to provide monitoring and logging.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
    """
    logger.info("Initializing database connection pool")
    
    # Get pool configuration from app config or use defaults
    pool_size = app.config.get("SQLALCHEMY_POOL_SIZE", 10)
    max_overflow = app.config.get("SQLALCHEMY_MAX_OVERFLOW", 20)
    pool_recycle = app.config.get("SQLALCHEMY_POOL_RECYCLE", 3600)  # 1 hour
    pool_pre_ping = app.config.get("SQLALCHEMY_POOL_PRE_PING", True)
    pool_timeout = app.config.get("SQLALCHEMY_POOL_TIMEOUT", 30)  # 30 seconds
    
    # Update SQLAlchemy engine options
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": pool_pre_ping,
        "pool_timeout": pool_timeout,
    }
    
    logger.info(
        f"Connection pool settings: size={pool_size}, max_overflow={max_overflow}, "
        f"recycle={pool_recycle}s, timeout={pool_timeout}s, pre_ping={pool_pre_ping}"
    )
    
    # Set up engine event listeners if we can access the engine
    if hasattr(db, "engine"):
        setup_engine_listeners(db.engine)


def setup_engine_listeners(engine: Engine) -> None:
    """
    Set up SQLAlchemy engine event listeners.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    
    # Setup connection pool events
    @event.listens_for(engine, "connect")
    def connect(dbapi_connection: Any, connection_record: _ConnectionRecord) -> None:
        logger.debug("Database connection established")
    
    @event.listens_for(engine, "checkout")
    def checkout(dbapi_connection: Any, connection_record: _ConnectionRecord, connection_proxy: Any) -> None:
        logger.debug("Database connection checked out from pool")
        connection_record.info.setdefault("checkout_time", time.time())
    
    @event.listens_for(engine, "checkin")
    def checkin(dbapi_connection: Any, connection_record: _ConnectionRecord) -> None:
        logger.debug("Database connection returned to pool")
        checkout_time = connection_record.info.get("checkout_time")
        if checkout_time is not None:
            connection_record.info["checkout_time"] = None
            elapsed = time.time() - checkout_time
            logger.debug(f"Connection was checked out for {elapsed:.2f} seconds")


def get_pool_status(db: SQLAlchemy) -> Dict[str, Any]:
    """
    Get current database connection pool status.
    
    Returns information about the current state of the database connection pool,
    including the number of used/unused connections and overflow status.
    
    Args:
        db: SQLAlchemy database instance
    
    Returns:
        Dictionary with pool status information
    """
    if not hasattr(db, "engine"):
        return {"error": "No database engine available"}
    
    engine = db.engine
    if not hasattr(engine, "pool"):
        return {"error": "No connection pool available"}
    
    pool = engine.pool
    
    # Extract pool metrics
    return {
        "pool_size": pool.size(),
        "checked_out_connections": pool.checkedin(),
        "overflow": pool.overflow(),
        "checkedout": pool.checkedout(),
    }


@contextmanager
def db_transaction(db: SQLAlchemy) -> Iterator[None]:
    """
    Context manager for database transactions.
    
    Handles committing or rolling back transactions automatically.
    
    Args:
        db: SQLAlchemy database instance
    
    Yields:
        None
    
    Example:
        with db_transaction(db):
            # Database operations here
            db.session.add(model)
            # No need to commit - it's done automatically
    """
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction rolled back: {e}")
        raise


def measure_query_time(f: F) -> F:
    """
    Decorator to measure and log database query execution time.
    
    Args:
        f: Function to decorate
    
    Returns:
        Decorated function
    """
    
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = f(*args, **kwargs)
        elapsed = time.time() - start_time
        logger.debug(f"Query {f.__name__} took {elapsed:.4f} seconds")
        return result
    
    return cast(F, wrapper)


def close_db_connections(db: SQLAlchemy) -> None:
    """
    Close all database connections in the pool.
    
    This is useful during application shutdown to ensure all
    connections are properly closed.
    
    Args:
        db: SQLAlchemy database instance
    """
    if hasattr(db, "engine") and hasattr(db.engine, "pool"):
        logger.info("Closing all database connections")
        db.engine.pool.dispose()
    
    # Always close the session
    db.session.close()