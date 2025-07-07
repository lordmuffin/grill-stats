import unittest
from flask import Flask, url_for
from flask_testing import TestCase
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

from models.user import User
from auth.utils import generate_password_hash, check_password, create_test_user
from auth.routes import init_auth_routes
from forms.auth_forms import LoginForm


class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


class AuthTestCase(TestCase):
    """Test case for authentication functionality"""
    
    def create_app(self):
        """Create and configure the Flask app for testing"""
        app = Flask(__name__, template_folder='../../templates')
        app.config.from_object(TestConfig)
        
        self.db = SQLAlchemy(app)
        self.bcrypt = Bcrypt(app)
        self.login_manager = LoginManager(app)
        
        # Initialize User model
        self.user_manager = User(self.db)
        
        # Initialize auth routes
        init_auth_routes(app, self.login_manager, self.user_manager, self.bcrypt)
        
        @app.route('/dashboard')
        def dashboard():
            return 'Dashboard Page'
        
        return app
    
    def setUp(self):
        """Set up the test environment"""
        self.db.create_all()
        
        # Create a test user
        password_hash = generate_password_hash(self.bcrypt, 'password')
        self.test_user = self.user_manager.create_user('test@example.com', password_hash)
        
        # Create a locked user
        locked_user = self.user_manager.create_user('locked@example.com', password_hash)
        locked_user.is_locked = True
        self.db.session.commit()
    
    def tearDown(self):
        """Tear down the test environment"""
        self.db.session.remove()
        self.db.drop_all()
    
    def test_login_page(self):
        """Test that the login page loads"""
        response = self.client.get('/login')
        self.assert200(response)
        self.assert_template_used('login.html')
    
    def test_successful_login(self):
        """Test successful login with valid credentials"""
        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        }, follow_redirects=True)
        
        self.assert200(response)
        self.assertIn(b'Welcome back!', response.data)
        self.assertIn(b'Dashboard', response.data)
    
    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrong-password'
        })
        
        self.assert200(response)
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_nonexistent_user(self):
        """Test login with a non-existent user"""
        response = self.client.post('/login', data={
            'email': 'nonexistent@example.com',
            'password': 'password'
        })
        
        self.assert200(response)
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_empty_fields(self):
        """Test login with empty fields"""
        response = self.client.post('/login', data={
            'email': '',
            'password': ''
        })
        
        self.assert200(response)
        self.assertIn(b'Email and password cannot be empty', response.data)
    
    def test_locked_account(self):
        """Test login with a locked account"""
        response = self.client.post('/login', data={
            'email': 'locked@example.com',
            'password': 'password'
        })
        
        self.assert200(response)
        self.assertIn(b'Your account has been locked', response.data)
    
    def test_failed_login_counter(self):
        """Test that failed login attempts are counted"""
        # Initial login attempt with wrong password
        self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrong-password'
        })
        
        # Verify that failed_login_attempts has been incremented
        user = self.user_manager.get_user_by_email('test@example.com')
        self.assertEqual(user.failed_login_attempts, 1)
        
        # Another failed attempt
        self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrong-password'
        })
        
        # Verify counter is now 2
        user = self.user_manager.get_user_by_email('test@example.com')
        self.assertEqual(user.failed_login_attempts, 2)
        
        # Successful login should reset counter
        self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        
        # Verify counter is reset
        user = self.user_manager.get_user_by_email('test@example.com')
        self.assertEqual(user.failed_login_attempts, 0)
    
    def test_account_lockout(self):
        """Test that an account gets locked after multiple failed attempts"""
        # Simulate 5 failed login attempts
        for _ in range(5):
            self.client.post('/login', data={
                'email': 'test@example.com',
                'password': 'wrong-password'
            })
        
        # Verify account is now locked
        user = self.user_manager.get_user_by_email('test@example.com')
        self.assertTrue(user.is_locked)
        
        # Try to login with correct password
        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        
        # Should fail due to account being locked
        self.assertIn(b'Your account has been locked', response.data)


if __name__ == '__main__':
    unittest.main()