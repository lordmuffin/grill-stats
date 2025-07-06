import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration for Flask application"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///grill_stats.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ThermoWorks API settings
    THERMOWORKS_API_KEY = os.getenv('THERMOWORKS_API_KEY')
    
    # Home Assistant settings
    HOMEASSISTANT_URL = os.getenv('HOMEASSISTANT_URL')
    HOMEASSISTANT_TOKEN = os.getenv('HOMEASSISTANT_TOKEN')
    
    # Authentication settings
    MAX_LOGIN_ATTEMPTS = 5