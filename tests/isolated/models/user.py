"""
Isolated User model for testing.

This module provides a version of the User model that doesn't have circular dependencies,
making it suitable for isolated unit tests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

from tests.utils import IsolatedTestDatabase


class IsolatedUser(UserMixin):
    """
    Isolated User model for testing.

    This class implements the same API as the real User class but doesn't have
    circular dependencies, making it suitable for isolated unit tests.
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
    model: Any  # Will be set to isolated UserModel in __init__
    db: Any  # SQLAlchemy database instance

    def __init__(self, db: Any) -> None:
        """
        Initialize the isolated User model.

        Args:
            db: SQLAlchemy database instance
        """
        self.db = db

        # Find the Flask app associated with this SQLAlchemy instance
        from tests.utils import get_flask_app_from_db

        app = get_flask_app_from_db(db)

        # Create isolated test database with existing db instance
        self.isolated_db = IsolatedTestDatabase(app, existing_db=db)

        # Get isolated user model
        self.model = self.isolated_db.UserModel

    def create_user(self, email: str, password_hash: str, name: Optional[str] = None) -> Any:
        """
        Create a new user.

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
