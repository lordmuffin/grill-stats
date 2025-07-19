from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class User(UserMixin):
    """User model for authentication"""

    id = None
    email = None
    password = None
    name = None
    is_active = None
    is_locked = None
    failed_login_attempts = None
    last_login = None
    created_at = None

    def __init__(self, db):
        self.db = db

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

            def __repr__(self):
                return f"<User {self.email}>"

            def get_id(self):
                return str(self.id)

        self.model = UserModel

    def create_user(self, email, password_hash, name=None):
        """Create a new user"""
        user = self.model(email=email, password=password_hash, name=name)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def get_user_by_email(self, email):
        """Get a user by email"""
        return self.model.query.filter_by(email=email).first()

    def get_user_by_id(self, user_id):
        """Get a user by ID"""
        return self.model.query.get(int(user_id))

    def increment_failed_login(self, user):
        """Increment failed login attempts"""
        user.failed_login_attempts += 1
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.is_locked = True
        self.db.session.commit()

    def reset_failed_login(self, user):
        """Reset failed login attempts after successful login"""
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        self.db.session.commit()

    def check_if_locked(self, user):
        """Check if user account is locked"""
        return user.is_locked if user else False
