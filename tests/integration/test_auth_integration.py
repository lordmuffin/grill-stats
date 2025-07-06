import unittest
from flask import Flask, url_for, session
from flask_testing import TestCase
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt

from models.user import User
from auth.utils import generate_password_hash
from auth.routes import init_auth_routes


class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


class AuthIntegrationTestCase(TestCase):
    """Integration test case for authentication with protected routes"""
    
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
        
        @app.route('/protected')
        @login_required
        def protected():
            return 'Protected Content'
        
        return app
    
    def setUp(self):
        """Set up the test environment"""
        self.db.create_all()
        
        # Create a test user
        password_hash = generate_password_hash(self.bcrypt, 'password')
        self.test_user = self.user_manager.create_user('test@example.com', password_hash)
    
    def tearDown(self):
        """Tear down the test environment"""
        self.db.session.remove()
        self.db.drop_all()
    
    def test_login_logout_flow(self):
        """Test the full login and logout flow"""
        # Not logged in initially
        response = self.client.get('/protected', follow_redirects=True)
        self.assertIn(b'Please log in', response.data)
        
        # Log in
        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        }, follow_redirects=True)
        
        self.assertIn(b'Welcome back!', response.data)
        
        # Can access protected content
        response = self.client.get('/protected')
        self.assertIn(b'Protected Content', response.data)
        
        # Log out
        response = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'You have been logged out', response.data)
        
        # Can't access protected content again
        response = self.client.get('/protected', follow_redirects=True)
        self.assertIn(b'Please log in', response.data)
    
    def test_redirect_after_login(self):
        """Test that after login, user is redirected to the intended page"""
        # Try to access protected page (gets redirected to login)
        response = self.client.get('/protected', follow_redirects=False)
        self.assertStatus(response, 302)  # Redirect to login
        
        # Log in, should redirect back to protected page
        response = self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        }, follow_redirects=True)
        
        self.assertIn(b'Protected Content', response.data)
    
    def test_session_persistence(self):
        """Test that the login session persists"""
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
        
        # Log in
        self.client.post('/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })
        
        # Check that the user_id is in the session
        with self.client.session_transaction() as sess:
            self.assertIn('_user_id', sess)
            self.assertEqual(sess['_user_id'], '1')  # First user has id=1


if __name__ == '__main__':
    unittest.main()