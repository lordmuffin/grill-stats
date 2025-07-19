"""
Test configuration module for isolated database testing.

This module provides pytest fixtures for isolated database tests.
"""

import os
import sys

import pytest
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Add services directory to Python path
services_dir = os.path.join(project_root, "services")
sys.path.insert(0, services_dir)

from auth.utils import create_test_user, generate_password_hash
from tests.mocks import MockDevice, MockUser
from tests.utils import TestDatabase


@pytest.fixture
def test_app():
    """Create and configure a Flask app for tests"""
    app = Flask(__name__, template_folder="../templates")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="test-secret-key",
        WTF_CSRF_ENABLED=False,  # Disable CSRF for testing
    )
    return app


@pytest.fixture
def test_db(test_app):
    """Create an isolated test database"""
    test_database = TestDatabase(test_app)
    with test_app.app_context():
        test_database.setup()
    yield test_database.db
    test_database.teardown()


@pytest.fixture
def bcrypt(test_app):
    """Create a bcrypt instance"""
    return Bcrypt(test_app)


@pytest.fixture
def login_manager(test_app):
    """Create a login manager instance"""
    login_manager = LoginManager(test_app)
    login_manager.login_view = "login"
    return login_manager


@pytest.fixture
def mock_user_manager(test_db):
    """Create a mock user manager for isolated testing"""
    return MockUser(test_db)


@pytest.fixture
def mock_device_manager(test_db):
    """Create a mock device manager for isolated testing"""
    return MockDevice(test_db)


@pytest.fixture
def test_user(mock_user_manager, bcrypt):
    """Create a test user"""
    password_hash = generate_password_hash(bcrypt, "password")
    user = mock_user_manager.create_user("test@example.com", password_hash)
    return user


@pytest.fixture
def locked_user(mock_user_manager, bcrypt, test_db):
    """Create a locked test user"""
    password_hash = generate_password_hash(bcrypt, "password")
    user = mock_user_manager.create_user("locked@example.com", password_hash)
    user.is_locked = True
    test_db.session.commit()
    return user


@pytest.fixture
def client(test_app):
    """Create a test client"""
    return test_app.test_client()
