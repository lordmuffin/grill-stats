import pytest
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your app modules
from models.user import User
from auth.utils import generate_password_hash, create_test_user


@pytest.fixture
def app():
    """Create and configure a Flask app for tests"""
    app = Flask(__name__, template_folder='../templates')
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
    login_manager.login_view = 'login'
    return login_manager


@pytest.fixture
def user_manager(db):
    """Create a user manager instance"""
    return User(db)


@pytest.fixture
def test_user(user_manager, bcrypt):
    """Create a test user"""
    password_hash = generate_password_hash(bcrypt, 'password')
    user = user_manager.create_user('test@example.com', password_hash)
    return user


@pytest.fixture
def locked_user(user_manager, bcrypt, db):
    """Create a locked test user"""
    password_hash = generate_password_hash(bcrypt, 'password')
    user = user_manager.create_user('locked@example.com', password_hash)
    user.is_locked = True
    db.session.commit()
    return user


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()