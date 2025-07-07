import os
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

@pytest.fixture
def app():
    from config import TestConfig
    app = Flask(__name__)
    app.config.from_object(TestConfig)
    # Set database URL
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://test:test@postgres:5432/grillstats_test')
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert 'timestamp' in response.json