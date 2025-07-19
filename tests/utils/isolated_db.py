"""
Isolated database utilities for testing.

This module provides utilities for creating isolated SQLAlchemy models for testing
without circular dependencies between models.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Type

from flask import Flask
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class IsolatedTestDatabase:
    """
    Helper for creating isolated test models without circular dependencies.
    """

    def __init__(self, app: Flask, existing_db: Optional[SQLAlchemy] = None) -> None:
        """
        Initialize the isolated test database.

        Args:
            app: Flask application
            existing_db: Optional existing SQLAlchemy instance to use
        """
        self.app = app

        # Use existing db if provided, otherwise create a new one
        if existing_db is not None:
            self.db = existing_db
        else:
            self.db = SQLAlchemy(app)

        # Define isolated model classes
        self.UserModel = self._create_user_model()
        self.DeviceModel = self._create_device_model()
        self.TemperatureAlertModel = self._create_temperature_alert_model()
        self.GrillingSessionModel = self._create_grilling_session_model()

        # Set up table creation in app context
        with self.app.app_context():
            self.db.create_all()

    def _create_user_model(self) -> Type:
        """Create an isolated user model without circular dependencies."""
        db = self.db

        class UserModel(db.Model, UserMixin):
            __tablename__ = "users"

            id = Column(Integer, primary_key=True)
            email = Column(String(120), unique=True, nullable=False)
            password = Column(String(128), nullable=False)
            name = Column(String(100), nullable=True)
            is_active = Column(Boolean, default=True)
            is_locked = Column(Boolean, default=False)
            failed_login_attempts = Column(Integer, default=0)
            last_login = Column(DateTime, nullable=True)
            created_at = Column(DateTime, default=datetime.utcnow)

            def get_id(self) -> str:
                return str(self.id)

            def __repr__(self) -> str:
                return f"<User {self.email}>"

        return UserModel

    def _create_device_model(self) -> Type:
        """Create an isolated device model without circular dependencies."""
        db = self.db

        class DeviceModel(db.Model):
            __tablename__ = "devices"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
            device_id = Column(String(50), unique=True, nullable=False)
            nickname = Column(String(100), nullable=True)
            status = Column(String(20), default="offline")
            is_active = Column(Boolean, default=True)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            # Define relationship to user but with no back-reference
            user = relationship("UserModel")

            def __repr__(self) -> str:
                return f'<Device {self.device_id} ({self.nickname or "No nickname"})>'

        return DeviceModel

    def _create_temperature_alert_model(self) -> Type:
        """Create an isolated temperature alert model without circular dependencies."""
        db = self.db

        class TemperatureAlertModel(db.Model):
            __tablename__ = "temperature_alerts"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
            device_id = Column(String(100), nullable=False)
            probe_id = Column(String(100), nullable=False)
            target_temperature = Column(Float, nullable=True)
            min_temperature = Column(Float, nullable=True)
            max_temperature = Column(Float, nullable=True)
            threshold_value = Column(Float, nullable=True)
            alert_type = Column(String(20), nullable=False, default="target")
            temperature_unit = Column(String(1), default="F")
            is_active = Column(Boolean, default=True)
            triggered_at = Column(DateTime, nullable=True)
            last_checked_at = Column(DateTime, nullable=True)
            last_temperature = Column(Float, nullable=True)
            notification_sent = Column(Boolean, default=False)
            name = Column(String(100), nullable=True)
            description = Column(String(255), nullable=True)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            # Define relationship to user but with no back-reference
            user = relationship("UserModel")

            def __repr__(self) -> str:
                return f"<TemperatureAlert {self.id}: {self.name} ({self.alert_type})>"

        return TemperatureAlertModel

    def _create_grilling_session_model(self) -> Type:
        """Create an isolated grilling session model without circular dependencies."""
        db = self.db

        class GrillingSessionModel(db.Model):
            __tablename__ = "grilling_sessions"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
            device_id = Column(String(100), nullable=False)
            name = Column(String(100), nullable=True)
            description = Column(String(255), nullable=True)
            start_time = Column(DateTime, default=datetime.utcnow)
            end_time = Column(DateTime, nullable=True)
            is_active = Column(Boolean, default=True)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            # Define relationship to user but with no back-reference
            user = relationship("UserModel")

            def __repr__(self) -> str:
                return f"<GrillingSession {self.id}: {self.name or 'Unnamed session'}>"

        return GrillingSessionModel

    def get_db(self) -> SQLAlchemy:
        """Get the SQLAlchemy database instance."""
        return self.db

    def get_models(self) -> Dict[str, Any]:
        """Get all isolated model classes."""
        return {
            "UserModel": self.UserModel,
            "DeviceModel": self.DeviceModel,
            "TemperatureAlertModel": self.TemperatureAlertModel,
            "GrillingSessionModel": self.GrillingSessionModel,
        }

    def teardown(self) -> None:
        """Tear down the database, removing all data."""
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()
