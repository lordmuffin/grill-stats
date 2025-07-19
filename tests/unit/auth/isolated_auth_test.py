"""
Isolated unit tests for authentication functionality.

This module provides unit tests for authentication that don't have circular dependencies.
"""

import os
import sys
import unittest

import pytest
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from auth.utils import generate_password_hash
from tests.isolated import IsolatedUser


class TestConfig:
    """Test configuration"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


class TestIsolatedAuth(unittest.TestCase):
    """Test authentication functionality with isolated models"""

    def setUp(self):
        """Set up test environment"""
        # Create Flask app
        self.app = Flask(__name__)
        self.app.config.from_object(TestConfig)

        # Configure app context
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Set up database
        self.db = SQLAlchemy(self.app)
        self.db.create_all()

        # Set up authentication
        self.bcrypt = Bcrypt(self.app)
        self.login_manager = LoginManager(self.app)

        # Create isolated user manager
        self.user_manager = IsolatedUser(self.db)

        # Create test user
        password_hash = generate_password_hash(self.bcrypt, "password")
        self.test_user = self.user_manager.create_user("test@example.com", password_hash)

        # Create locked user
        locked_user = self.user_manager.create_user("locked@example.com", password_hash)
        locked_user.is_locked = True
        self.db.session.commit()

    def tearDown(self):
        """Tear down test environment"""
        self.db.session.remove()
        self.db.drop_all()
        self.app_context.pop()

    def test_get_user_by_email(self):
        """Test getting user by email"""
        # Get existing user
        user = self.user_manager.get_user_by_email("test@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "test@example.com")

        # Get non-existent user
        user = self.user_manager.get_user_by_email("nonexistent@example.com")
        self.assertIsNone(user)

    def test_get_user_by_id(self):
        """Test getting user by ID"""
        # Get existing user
        user = self.user_manager.get_user_by_id(self.test_user.id)
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "test@example.com")

        # Get non-existent user
        user = self.user_manager.get_user_by_id(999)
        self.assertIsNone(user)

    def test_failed_login_counter(self):
        """Test failed login counter"""
        # Initially no failed attempts
        self.assertEqual(self.test_user.failed_login_attempts, 0)

        # Increment failed login counter
        self.user_manager.increment_failed_login(self.test_user)
        self.assertEqual(self.test_user.failed_login_attempts, 1)

        # Increment again
        self.user_manager.increment_failed_login(self.test_user)
        self.assertEqual(self.test_user.failed_login_attempts, 2)

        # Reset counter
        self.user_manager.reset_failed_login(self.test_user)
        self.assertEqual(self.test_user.failed_login_attempts, 0)

    def test_account_lockout(self):
        """Test account lockout after multiple failed attempts"""
        # Initially not locked
        self.assertFalse(self.test_user.is_locked)

        # Increment failed login counter to trigger lockout
        for _ in range(5):
            self.user_manager.increment_failed_login(self.test_user)

        # Verify account is locked
        self.assertTrue(self.test_user.is_locked)
        self.assertTrue(self.user_manager.check_if_locked(self.test_user))

    def test_check_if_locked(self):
        """Test checking if account is locked"""
        # Check locked account
        locked_user = self.user_manager.get_user_by_email("locked@example.com")
        self.assertTrue(self.user_manager.check_if_locked(locked_user))

        # Check unlocked account
        self.assertFalse(self.user_manager.check_if_locked(self.test_user))

        # Check non-existent user
        self.assertFalse(self.user_manager.check_if_locked(None))


if __name__ == "__main__":
    unittest.main()
