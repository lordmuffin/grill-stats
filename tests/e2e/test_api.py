import os
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()

@pytest.fixture
def app():
    from config import TestConfig
    from models.user import User
    from auth.routes import init_auth_routes
    
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app.config.from_object(TestConfig)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://test:test@postgres:5432/grillstats_test')
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # Initialize auth
        user_manager = User(db)
        init_auth_routes(app, login_manager, user_manager, bcrypt)
        
        # Add test routes
        @app.route('/health')
        def health_check():
            from datetime import datetime
            return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}
            
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data