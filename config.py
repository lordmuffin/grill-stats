import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration for Flask application"""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///grill_stats.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pooling and timeout settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Verify connections before use
        "pool_timeout": 30,  # Wait up to 30 seconds for connection
        "max_overflow": 20,  # Allow up to 20 overflow connections
        "connect_args": {
            "connect_timeout": 10,  # Connection timeout in seconds
            "application_name": "grill-stats",
        },
    }

    # ThermoWorks API settings
    THERMOWORKS_API_KEY = os.getenv("THERMOWORKS_API_KEY")

    # Home Assistant settings
    HOMEASSISTANT_URL = os.getenv("HOMEASSISTANT_URL")
    HOMEASSISTANT_TOKEN = os.getenv("HOMEASSISTANT_TOKEN")

    # Authentication settings
    MAX_LOGIN_ATTEMPTS = 5

    # Mock Mode settings (for development and testing)
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes", "on")

    @property
    def is_mock_mode_enabled(self):
        """Check if mock mode is enabled - only allow in development"""
        return self.MOCK_MODE and not os.getenv("FLASK_ENV", "").lower() == "production"


class TestConfig(Config):
    """Test configuration"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "postgresql://test:test@localhost:5432/grillstats_test"
    WTF_CSRF_ENABLED = False
    # Always enable mock mode in testing
    MOCK_MODE = True
