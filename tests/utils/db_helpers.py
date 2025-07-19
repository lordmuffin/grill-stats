"""
Database helper utilities for testing.

This module provides utility functions for working with databases in tests.
"""

from typing import Any, Optional

from flask import Flask, current_app


def get_flask_app_from_db(db: Any) -> Flask:
    """
    Get the Flask app associated with a SQLAlchemy database instance.

    This handles various ways the app might be associated with the db instance.

    Args:
        db: SQLAlchemy database instance

    Returns:
        Flask application instance

    Raises:
        RuntimeError: If no Flask app can be found
    """
    # Try various ways to get the app
    app = None

    # First, try common attributes/methods
    if hasattr(db, "app"):
        app = db.app
    elif hasattr(db, "get_app") and callable(db.get_app):
        app = db.get_app()
    elif hasattr(db, "_app"):
        app = db._app
    elif hasattr(db, "_flask_app"):
        app = db._flask_app

    # If that didn't work, try current_app if in application context
    if app is None:
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            pass

    # As a last resort, try to get app from engine/metadata/session
    if app is None and hasattr(db, "engine"):
        # Try to extract app from engine info
        if hasattr(db.engine, "app"):
            app = db.engine.app

    if app is None and hasattr(db, "metadata"):
        # Try to extract from metadata
        if hasattr(db.metadata, "bind") and hasattr(db.metadata.bind, "app"):
            app = db.metadata.bind.app

    # If we still don't have an app, raise error
    if app is None:
        raise RuntimeError("Could not find Flask app associated with database instance")

    return app
