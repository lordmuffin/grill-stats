"""
Test utility models for isolated database testing.

This module provides mock model classes for unit tests that don't require
the full set of relationships, preventing circular dependencies in tests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String


def create_mock_device_model(db: Any) -> Type:
    """
    Create a simplified Device model for testing without circular dependencies.

    Args:
        db: SQLAlchemy database instance

    Returns:
        A Device model class for testing
    """

    class MockDeviceModel(db.Model):
        __tablename__ = "devices"

        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        device_id = Column(String(50), unique=True, nullable=False)
        nickname = Column(String(100), nullable=True)
        status = Column(String(20), default="offline")
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        def __repr__(self) -> str:
            return f'<Device {self.device_id} ({self.nickname or "No nickname"})>'

    return MockDeviceModel


def create_mock_user_model(db: Any) -> Type:
    """
    Create a simplified User model for testing without circular dependencies.

    Args:
        db: SQLAlchemy database instance

    Returns:
        A User model class for testing
    """

    class MockUserModel(db.Model, UserMixin):
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

        def __repr__(self) -> str:
            return f"<User {self.email}>"

        def get_id(self) -> str:
            return str(self.id)

    return MockUserModel


def create_mock_temperature_alert_model(db: Any) -> Type:
    """
    Create a simplified TemperatureAlert model for testing without circular dependencies.

    Args:
        db: SQLAlchemy database instance

    Returns:
        A TemperatureAlert model class for testing
    """

    class MockTemperatureAlertModel(db.Model):
        __tablename__ = "temperature_alerts"

        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        device_id = Column(String(100), nullable=False)
        probe_id = Column(String(100), nullable=False)
        target_temperature = Column(Integer, nullable=True)
        min_temperature = Column(Integer, nullable=True)
        max_temperature = Column(Integer, nullable=True)
        threshold_value = Column(Integer, nullable=True)
        alert_type = Column(String(20), nullable=False, default="target")
        temperature_unit = Column(String(1), default="F")
        is_active = Column(Boolean, default=True)
        triggered_at = Column(DateTime, nullable=True)
        last_checked_at = Column(DateTime, nullable=True)
        last_temperature = Column(Integer, nullable=True)
        notification_sent = Column(Boolean, default=False)
        name = Column(String(100), nullable=True)
        description = Column(String(255), nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        def __repr__(self) -> str:
            return f"<TemperatureAlert {self.id}: {self.name} ({self.alert_type})>"

    return MockTemperatureAlertModel


def create_mock_grilling_session_model(db: Any) -> Type:
    """
    Create a simplified GrillingSession model for testing without circular dependencies.

    Args:
        db: SQLAlchemy database instance

    Returns:
        A GrillingSession model class for testing
    """

    class MockGrillingSessionModel(db.Model):
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

        def __repr__(self) -> str:
            return f"<GrillingSession {self.id}: {self.name or 'Unnamed session'}>"

    return MockGrillingSessionModel
