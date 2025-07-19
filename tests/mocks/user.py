"""
Mock User model for testing.

This module provides a modified User model class that doesn't have circular dependencies
between models, making it suitable for isolated unit tests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from flask_login import UserMixin


class MockUser(UserMixin):
    """
    Mock User model for testing without circular dependencies.

    This class implements the same API as the real User class but uses
    the mock models from test_models.py to avoid circular dependencies.
    """

    id: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None
    failed_login_attempts: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model: Any  # Will be set to MockUserModel in __init__
    db: Any  # SQLAlchemy database instance

    def __init__(self, db: Any) -> None:
        """
        Initialize the mock User model.

        Args:
            db: SQLAlchemy database instance
        """
        self.db = db

        # Use the pre-defined mock model from the test database
        # instead of creating a new one to avoid circular dependencies
        from tests.utils.test_db import TestDatabase

        # Get all models from a temporary TestDatabase instance
        app = db.metadata.bind.engine.url.database
        from flask import current_app

        test_db = TestDatabase(current_app)
        models = test_db.get_models()

        # Use the mock UserModel
        self.model = models["UserModel"]

    def create_user(self, email: str, password_hash: str, name: Optional[str] = None) -> Any:
        """
        Create a new user for testing.

        Args:
            email: User email
            password_hash: Hashed password
            name: Optional user name

        Returns:
            The created user model instance
        """
        user = self.model(email=email, password=password_hash, name=name)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def get_user_by_email(self, email: str) -> Optional[Any]:
        """
        Get a user by email.

        Args:
            email: User email

        Returns:
            User model instance or None if not found
        """
        return self.model.query.filter_by(email=email).first()

    def get_user_by_id(self, user_id: Union[str, int]) -> Optional[Any]:
        """
        Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            User model instance or None if not found
        """
        return self.model.query.get(int(user_id))

    def increment_failed_login(self, user: Any) -> None:
        """
        Increment failed login attempts.

        Args:
            user: User model instance
        """
        user.failed_login_attempts += 1
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.is_locked = True
        self.db.session.commit()

    def reset_failed_login(self, user: Any) -> None:
        """
        Reset failed login attempts after successful login.

        Args:
            user: User model instance
        """
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.session.commit()

    def check_if_locked(self, user: Optional[Any]) -> bool:
        """
        Check if user account is locked.

        Args:
            user: User model instance

        Returns:
            True if locked, False otherwise
        """
        return user.is_locked if user else False
