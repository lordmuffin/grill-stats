"""
Tests for the refactored SQLAlchemy models.

This module contains tests for the database models and their relationships
to ensure that the refactored model architecture works correctly.
"""

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

from models.base import db
from models.device_model import DeviceManager, DeviceModel
from models.grilling_session_model import GrillingSessionManager, GrillingSessionModel
from models.temperature_alert_model import AlertType, TemperatureAlertManager, TemperatureAlertModel
from models.user_model import UserManager, UserModel


@pytest.fixture
def app():
    """Create Flask application for testing."""
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    return app


@pytest.fixture
def database(app):
    """Set up database for testing."""
    # Initialize the database with the app
    db.init_app(app)

    with app.app_context():
        # Create all tables
        db.create_all()

        yield db

        # Clean up
        db.session.remove()
        db.drop_all()


def test_user_model_creation(app, database):
    """Test creating a user model."""
    with app.app_context():
        user_manager = UserManager(database)
        user = user_manager.create_user("test@example.com", "hashed_password", "Test User")

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_active is True
        assert user.is_locked is False


def test_device_model_creation(app, database):
    """Test creating a device model with user relationship."""
    with app.app_context():
        # Create a user first
        user_manager = UserManager(database)
        user = user_manager.create_user("device_test@example.com", "hashed_password")

        # Create a device for this user
        device_manager = DeviceManager(database)
        device = device_manager.create_device(user.id, "TW-ABC-123", "My Grill")

        assert device.id is not None
        assert device.device_id == "TW-ABC-123"
        assert device.nickname == "My Grill"
        assert device.user_id == user.id

        # Test relationship
        assert device.user.email == "device_test@example.com"


def test_device_user_relationship(app, database):
    """Test the relationship between user and device models."""
    with app.app_context():
        # Create a user
        user_manager = UserManager(database)
        user = user_manager.create_user("relationship_test@example.com", "hashed_password")

        # Create multiple devices for this user
        device_manager = DeviceManager(database)
        device1 = device_manager.create_device(user.id, "TW-DEF-456", "Smoker")
        device2 = device_manager.create_device(user.id, "TW-GHI-789", "Grill")

        # Query the user again to refresh relationships
        refreshed_user = UserModel.query.get(user.id)

        # Test that the user has the correct devices
        assert len(refreshed_user.devices) == 2
        device_ids = [d.device_id for d in refreshed_user.devices]
        assert "TW-DEF-456" in device_ids
        assert "TW-GHI-789" in device_ids


def test_temperature_alert_creation(app, database):
    """Test creating a temperature alert with user relationship."""
    with app.app_context():
        # Create a user
        user_manager = UserManager(database)
        user = user_manager.create_user("alert_test@example.com", "hashed_password")

        # Create an alert
        alert_manager = TemperatureAlertManager(database)
        alert = alert_manager.create_alert(
            user_id=user.id,
            device_id="TW-JKL-123",
            probe_id="PROBE1",
            alert_type=AlertType.TARGET,
            target_temperature=225.0,
            name="Cooking Alert",
        )

        assert alert.id is not None
        assert alert.device_id == "TW-JKL-123"
        assert alert.probe_id == "PROBE1"
        assert alert.alert_type == AlertType.TARGET
        assert alert.target_temperature == 225.0
        assert alert.user_id == user.id

        # Test relationship
        assert alert.user.email == "alert_test@example.com"


def test_grilling_session_creation(app, database):
    """Test creating a grilling session with user relationship."""
    with app.app_context():
        # Create a user
        user_manager = UserManager(database)
        user = user_manager.create_user("session_test@example.com", "hashed_password")

        # Create a session
        session_manager = GrillingSessionManager(database)
        session = session_manager.create_session(user_id=user.id, devices=["TW-MNO-123", "TW-PQR-456"], session_type="smoking")

        assert session.id is not None
        assert session.status == "active"
        assert session.session_type == "smoking"
        assert session.user_id == user.id

        # Test relationship
        assert session.user.email == "session_test@example.com"

        # Test device list
        device_list = session.get_device_list()
        assert len(device_list) == 2
        assert "TW-MNO-123" in device_list
        assert "TW-PQR-456" in device_list


def test_missing_user_foreign_key(app, database):
    """Test that device is linked to correct user."""
    with app.app_context():
        # Create a user
        user_manager = UserManager(database)
        user = user_manager.create_user("foreign_key@example.com", "hashed_password")

        # Create a device for this user
        device_manager = DeviceManager(database)
        device = device_manager.create_device(user.id, "TW-STU-789", "Foreign Key Test")

        # Verify the foreign key relationship
        assert device.user_id == user.id
        assert device.user.email == "foreign_key@example.com"


def test_model_serialization(app, database):
    """Test model to_dict serialization."""
    with app.app_context():
        # Create test data
        user_manager = UserManager(database)
        user = user_manager.create_user("serialize_test@example.com", "hashed_password")

        device_manager = DeviceManager(database)
        device = device_manager.create_device(user.id, "TW-VWX-789", "Serialized Device")

        alert_manager = TemperatureAlertManager(database)
        alert = alert_manager.create_alert(
            user_id=user.id,
            device_id=device.device_id,
            probe_id="PROBE1",
            alert_type=AlertType.RANGE,
            min_temperature=200.0,
            max_temperature=250.0,
            name="Range Alert",
        )

        session_manager = GrillingSessionManager(database)
        session = session_manager.create_session(user_id=user.id, devices=[device.device_id], session_type="grilling")

        # Test serialization of each model
        device_dict = device.to_dict()
        assert device_dict["device_id"] == "TW-VWX-789"
        assert device_dict["nickname"] == "Serialized Device"

        alert_dict = alert.to_dict()
        assert alert_dict["device_id"] == "TW-VWX-789"
        assert alert_dict["alert_type"] == "range"
        assert alert_dict["min_temperature"] == 200.0
        assert alert_dict["max_temperature"] == 250.0

        session_dict = session.to_dict()
        assert session_dict["status"] == "active"
        assert session_dict["session_type"] == "grilling"
        assert device.device_id in session_dict["devices_used"]
