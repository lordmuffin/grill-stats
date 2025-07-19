#!/usr/bin/env python3
"""
Admin user creation script for grill-stats production environment.
Usage: python create_admin.py <email> <password> [name]
"""

import os
import sys

from flask import Flask
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth.utils import generate_password_hash
from config import Config
from models.user import User


def create_admin_user(email, password, name=None):
    """Create an admin user for production"""

    # Initialize Flask app with minimal config
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db = SQLAlchemy(app)
    bcrypt = Bcrypt(app)

    with app.app_context():
        # Initialize user manager
        user_manager = User(db)

        # Create tables if they don't exist
        db.create_all()

        # Check if user already exists
        existing_user = user_manager.get_user_by_email(email)
        if existing_user:
            print(f"User with email '{email}' already exists!")
            return False

        # Create password hash
        password_hash = generate_password_hash(bcrypt, password)

        # Create user
        try:
            user = user_manager.create_user(email, password_hash, name)
            print(f"Admin user created successfully!")
            print(f"Email: {email}")
            print(f"Name: {name or 'Not specified'}")
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password> [name]")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else None

    success = create_admin_user(email, password, name)
    sys.exit(0 if success else 1)
