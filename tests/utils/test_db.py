"""
Test database utilities.

This module provides utilities for setting up and tearing down test databases.
"""

from typing import Any, Dict, List, Optional, Tuple, Type, Union

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import scoped_session, sessionmaker

from .test_models import (
    create_mock_device_model,
    create_mock_grilling_session_model,
    create_mock_temperature_alert_model,
    create_mock_user_model,
)


class TestDatabase:
    """
    Test database helper for isolated database tests.

    This class helps set up isolated database sessions for unit tests,
    preventing cross-test contamination and circular dependencies.
    """

    def __init__(self, app: Flask) -> None:
        """
        Initialize the test database.

        Args:
            app: Flask application instance
        """
        self.app = app
        self.db = SQLAlchemy(app)

        # Create mock models with no relationships to avoid circular dependencies
        self.UserModel = create_mock_user_model(self.db)
        self.DeviceModel = create_mock_device_model(self.db)
        self.TemperatureAlertModel = create_mock_temperature_alert_model(self.db)
        self.GrillingSessionModel = create_mock_grilling_session_model(self.db)

        # Set up model registry for relationship resolution
        registry = {
            "UserModel": self.UserModel,
            "DeviceModel": self.DeviceModel,
            "TemperatureAlertModel": self.TemperatureAlertModel,
            "GrillingSessionModel": self.GrillingSessionModel,
        }

        # Attach registry to models for test-only name resolution
        # This mimics SQLAlchemy's _decl_class_registry but just for tests
        for model in registry.values():
            model._test_registry = registry

    def setup(self) -> None:
        """
        Set up the test database.

        Creates all tables and prepares the database for testing.
        """
        with self.app.app_context():
            self.db.create_all()

    def teardown(self) -> None:
        """
        Tear down the test database.

        Removes all session data and drops all tables.
        """
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    def create_session(self) -> scoped_session:
        """
        Create a new database session for isolated testing.

        Returns:
            A scoped database session
        """
        return self.db.session

    def get_models(self) -> Dict[str, Any]:
        """
        Get all mock models.

        Returns:
            Dictionary of model classes keyed by name
        """
        return {
            "UserModel": self.UserModel,
            "DeviceModel": self.DeviceModel,
            "TemperatureAlertModel": self.TemperatureAlertModel,
            "GrillingSessionModel": self.GrillingSessionModel,
        }
