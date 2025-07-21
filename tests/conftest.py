import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth.utils import create_test_user, generate_password_hash

# Import your app modules
from models.user import User

# Set test environment
os.environ["TESTING"] = "true"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["SECRET_KEY"] = "test-secret-key"


@pytest.fixture
def app():
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
def db(app):
    """Create a database instance"""
    db = SQLAlchemy(app)
    with app.app_context():
        db.create_all()
    yield db
    db.session.remove()
    db.drop_all()


@pytest.fixture
def bcrypt(app):
    """Create a bcrypt instance"""
    return Bcrypt(app)


@pytest.fixture
def login_manager(app):
    """Create a login manager instance"""
    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    return login_manager


@pytest.fixture
def user_manager(db):
    """Create a user manager instance"""
    return User(db)


@pytest.fixture
def test_user(user_manager, bcrypt):
    """Create a test user"""
    password_hash = generate_password_hash(bcrypt, "password")
    user = user_manager.create_user("test@example.com", password_hash)
    return user


@pytest.fixture
def locked_user(user_manager, bcrypt, db):
    """Create a locked test user"""
    password_hash = generate_password_hash(bcrypt, "password")
    user = user_manager.create_user("locked@example.com", password_hash)
    user.is_locked = True
    db.session.commit()
    return user


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


# API Gateway Security Test Fixtures


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    with patch("redis.Redis") as mock_redis_class:
        mock_redis_instance = MagicMock()
        mock_redis_class.return_value = mock_redis_instance

        # Configure common Redis operations
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.setex.return_value = True
        mock_redis_instance.delete.return_value = 1
        mock_redis_instance.exists.return_value = False
        mock_redis_instance.keys.return_value = []
        mock_redis_instance.eval.return_value = [1, 5, 1]  # allowed, remaining, current

        yield mock_redis_instance


@pytest.fixture
def sample_request_data():
    """Sample request data for WAF testing"""
    return {
        "url": "https://api.example.com/test",
        "path": "/test",
        "method": "GET",
        "query_string": "param=value",
        "user_agent": "test-agent/1.0",
        "referer": "https://example.com",
        "content_type": "application/json",
        "headers": {"Content-Type": "application/json", "User-Agent": "test-agent/1.0", "Authorization": "Bearer test-token"},
        "cookies": {"session": "test-session"},
        "body": '{"test": "data"}',
        "remote_addr": "192.168.1.100",
    }


@pytest.fixture
def malicious_request_data():
    """Malicious request data for WAF testing"""
    return {
        "url": "https://api.example.com/test?id=1' OR '1'='1",
        "path": "/test",
        "method": "POST",
        "query_string": "id=1' OR '1'='1",
        "user_agent": "sqlmap/1.4.12",
        "referer": "",
        "content_type": "application/json",
        "headers": {"Content-Type": "application/json", "User-Agent": "sqlmap/1.4.12"},
        "cookies": {},
        "body": '<script>alert("xss")</script>',
        "remote_addr": "10.0.0.1",
    }


@pytest.fixture
def valid_user_data():
    """Valid user data for JWT testing"""
    return {"id": "12345", "email": "test@example.com", "roles": ["user"], "name": "Test User"}


@pytest.fixture
def admin_user_data():
    """Admin user data for JWT testing"""
    return {"id": "67890", "email": "admin@example.com", "roles": ["admin", "user"], "name": "Admin User"}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        # Mark all tests in security modules
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)

        # Mark integration tests
        if "integration" in item.name or "test_end_to_end" in item.name:
            item.add_marker(pytest.mark.integration)

        # Mark performance tests as slow
        if "performance" in item.name or "test_.*_performance" in item.name:
            item.add_marker(pytest.mark.slow)
