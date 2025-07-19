from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Query, relationship


class User(UserMixin):
    """User model for authentication"""

    id: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None
    failed_login_attempts: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model: Any  # Will be set to UserModel in __init__
    UserModel: Any  # Will be set in __init__
    db: SQLAlchemy

    def __init__(self, db: SQLAlchemy) -> None:
        self.db = db

        # Define UserModel class with type annotation
        # This addresses the "db.Model is not defined" error
        UserModel = self.db.Model

        class UserModel(UserModel, UserMixin):  # type: ignore
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

            # Define relationships explicitly here with strings to avoid circular imports
            # These will be properly resolved by SQLAlchemy at runtime
            devices = relationship("DeviceModel", back_populates="user")
            temperature_alerts = relationship("TemperatureAlertModel", back_populates="user")
            grilling_sessions = relationship("GrillingSessionModel", back_populates="user")

            def __repr__(self) -> str:
                return f"<User {self.email}>"

            def get_id(self) -> str:
                return str(self.id)

        # Store the model class for later use
        self.model = UserModel  # type: ignore
        # Make UserModel accessible from outside
        self.UserModel = UserModel  # type: ignore

    def create_user(self, email: str, password_hash: str, name: Optional[str] = None) -> Any:
        """Create a new user"""
        user = self.model(email=email, password=password_hash, name=name)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def get_user_by_email(self, email: str) -> Optional[Any]:
        """Get a user by email"""
        return self.model.query.filter_by(email=email).first()

    def get_user_by_id(self, user_id: Union[str, int]) -> Optional[Any]:
        """Get a user by ID"""
        return self.model.query.get(int(user_id))

    def increment_failed_login(self, user: Any) -> None:
        """Increment failed login attempts"""
        user.failed_login_attempts += 1
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.is_locked = True
        self.db.session.commit()

    def reset_failed_login(self, user: Any) -> None:
        """Reset failed login attempts after successful login"""
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.session.commit()

    def check_if_locked(self, user: Optional[Any]) -> bool:
        """Check if user account is locked"""
        result = user.is_locked if user else False
        return result
