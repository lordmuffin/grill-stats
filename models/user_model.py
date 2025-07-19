"""
User model for authentication.

This module defines the UserModel class for storing user information
and related tables. It uses SQLAlchemy for ORM functionality.
"""

from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base, db


class UserModel(Base, UserMixin):
    """User model for authentication and user management."""

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

    # Define relationships with string references to avoid circular imports
    # These will be properly resolved by SQLAlchemy at runtime
    devices = relationship("DeviceModel", back_populates="user")
    temperature_alerts = relationship("TemperatureAlertModel", back_populates="user")
    grilling_sessions = relationship("GrillingSessionModel", back_populates="user")

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User {self.email}>"

    def get_id(self) -> str:
        """Get user ID as string for Flask-Login."""
        return str(self.id)


class UserManager:
    """Manager class for user operations."""

    def __init__(self, db_instance=None) -> None:
        """Initialize user manager with database instance."""
        self.db = db_instance or db

    def create_user(self, email: str, password_hash: str, name: Optional[str] = None) -> UserModel:
        """Create a new user."""
        user = UserModel(email=email, password=password_hash, name=name)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """Get a user by email."""
        user = UserModel.query.filter_by(email=email).first()
        return user

    def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """Get a user by ID."""
        user = UserModel.query.get(int(user_id))
        return user

    def increment_failed_login(self, user: UserModel) -> None:
        """Increment failed login attempts."""
        user.failed_login_attempts += 1
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.is_locked = True
        self.db.session.commit()

    def reset_failed_login(self, user: UserModel) -> None:
        """Reset failed login attempts after successful login."""
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.session.commit()

    def check_if_locked(self, user: Optional[UserModel]) -> bool:
        """Check if user account is locked."""
        result = user.is_locked if user else False
        return result
