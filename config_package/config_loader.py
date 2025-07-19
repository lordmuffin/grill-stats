"""
Configuration Loader for Grill Stats

This module is responsible for loading and validating application configuration,
including environment variables and config classes for different environments.
"""

import logging
import os
import secrets
from typing import Any, Dict, List, Optional, Set, Type, Union

from dotenv import load_dotenv

from .env_validator import (
    EnvironmentValidator,
    EnvVarStatus,
    validate_api_key,
    validate_boolean,
    validate_email,
    validate_host,
    validate_path,
    validate_port,
    validate_secret_key,
    validate_token,
    validate_url,
)

logger = logging.getLogger(__name__)


class BaseConfig:
    """Base configuration class for the application"""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes", "on")
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = "sqlite:///grill_stats.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pooling and timeout settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Verify connections before use
        "pool_timeout": 30,  # Wait up to 30 seconds for connection
        "max_overflow": 20,  # Allow up to 20 overflow connections
    }

    # ThermoWorks API settings
    THERMOWORKS_API_KEY = os.getenv("THERMOWORKS_API_KEY")
    THERMOWORKS_BASE_URL = os.getenv("THERMOWORKS_BASE_URL", "https://api.thermoworks.com/v1")

    # Home Assistant settings
    HOMEASSISTANT_URL = os.getenv("HOMEASSISTANT_URL")
    HOMEASSISTANT_TOKEN = os.getenv("HOMEASSISTANT_TOKEN")

    # Authentication settings
    MAX_LOGIN_ATTEMPTS = 5

    # Mock Mode settings (for development and testing)
    MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes", "on")

    # Redis configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

    @property
    def is_mock_mode_enabled(self) -> bool:
        """Check if mock mode is enabled - only allow in development"""
        return self.MOCK_MODE and not os.getenv("FLASK_ENV", "").lower() == "production"


class DevelopmentConfig(BaseConfig):
    """Development configuration"""

    DEBUG = True
    MOCK_MODE = True

    # Override database URI for development
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'grill_stats')}",
    )

    # Security relaxations for development
    WTF_CSRF_ENABLED = True


class TestingConfig(BaseConfig):
    """Testing configuration"""

    TESTING = True
    DEBUG = True
    MOCK_MODE = True

    # Use in-memory SQLite for tests by default
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Faster encryption for tests
    BCRYPT_LOG_ROUNDS = 4


class ProductionConfig(BaseConfig):
    """Production configuration"""

    DEBUG = False
    TESTING = False
    MOCK_MODE = False

    # Override database URI for production
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'grill_stats')}",
    )

    # Security hardening for production
    @classmethod
    def init_app(cls, app: Any) -> None:
        """Initialize production settings"""
        # Ensure proper secret key in production
        if app.config["SECRET_KEY"] == "dev-secret-key-change-in-production":
            raise ValueError("Security error: You must set a proper SECRET_KEY environment variable " "in production!")

        # Set secure cookies
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["REMEMBER_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


class DockerConfig(ProductionConfig):
    """Docker configuration - for running in containers"""

    # Adjust database settings for container networking
    @classmethod
    def init_app(cls, app: Any) -> None:
        """Initialize docker settings"""
        ProductionConfig.init_app(app)

        # Set proper host headers for proxy setup
        app.config["PREFERRED_URL_SCHEME"] = "https"
        app.config["PROPAGATE_EXCEPTIONS"] = True


class ConfigLoader:
    """Configuration loader and validator for the application"""

    ENV_CONFIGS = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
        "docker": DockerConfig,
        # Default to development if not specified
        "default": DevelopmentConfig,
    }

    def __init__(self) -> None:
        """Initialize configuration loader"""
        self.validator = EnvironmentValidator()
        self._load_environment()

    def _load_environment(self) -> None:
        """Load environment variables from .env file"""
        load_dotenv()

    def get_config_class(self) -> Type[BaseConfig]:
        """Get the appropriate configuration class based on environment"""
        env = os.getenv("FLASK_ENV", "development").lower()
        return self.ENV_CONFIGS.get(env, self.ENV_CONFIGS["default"])

    def validate_common_config(self) -> bool:
        """Validate common configuration settings"""
        # Flask core settings
        # Get environment to check if we're in a test
        env = os.getenv("FLASK_ENV", "development").lower()
        is_testing = env == "testing"

        # Secret key - use a more relaxed validator for testing
        if is_testing:
            # In tests, we just need a minimal length check
            self.validator.validate(
                "SECRET_KEY",
                required=True,
                validator=lambda v: (len(v) >= 16, "Secret key must be at least 16 characters"),
                default="test-secret-key-12345",
                warn_default=True,
            )
        else:
            self.validator.validate(
                "SECRET_KEY",
                required=True,
                validator=validate_secret_key,
                default="dev-secret-key-change-in-production",
                warn_default=True,
            )

        self.validator.validate("DEBUG", required=False, validator=validate_boolean, default="false")

        # Database settings
        self.validator.validate("DB_HOST", required=False, validator=validate_host, default="localhost")

        self.validator.validate("DB_PORT", required=False, validator=validate_port, default="5432")

        self.validator.validate("DB_NAME", required=False, default="grill_stats")

        self.validator.validate("DB_USER", required=False, default="postgres")

        self.validator.validate("DB_PASSWORD", required=False, default="postgres")

        # Check if mock mode is enabled
        mock_mode = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes", "on")
        env = os.getenv("FLASK_ENV", "development").lower()
        is_testing = env == "testing"

        # ThermoWorks API settings (required unless in mock mode or testing)
        self.validator.validate("THERMOWORKS_API_KEY", required=not (mock_mode or is_testing), validator=validate_api_key)

        self.validator.validate(
            "THERMOWORKS_BASE_URL", required=False, validator=validate_url, default="https://api.thermoworks.com/v1"
        )

        # Home Assistant settings (required unless in mock mode or testing)
        self.validator.validate("HOMEASSISTANT_URL", required=not (mock_mode or is_testing), validator=validate_url)

        self.validator.validate("HOMEASSISTANT_TOKEN", required=not (mock_mode or is_testing), validator=validate_token)

        # Mock mode
        self.validator.validate("MOCK_MODE", required=False, validator=validate_boolean, default="false")

        # Redis settings
        self.validator.validate("REDIS_HOST", required=False, validator=validate_host, default="localhost")

        self.validator.validate("REDIS_PORT", required=False, validator=validate_port, default="6379")

        return not self.validator.has_failures()

    def validate_production_config(self) -> bool:
        """Validate production-specific configuration"""
        # Only run these checks if we're in production mode
        if os.getenv("FLASK_ENV", "").lower() != "production":
            return True

        # In production, SECRET_KEY should never use the default
        secret_key = os.getenv("SECRET_KEY")
        if secret_key == "dev-secret-key-change-in-production" or not secret_key:
            self.validator.validate(
                "SECRET_KEY", required=True, validator=lambda v: (False, "Default secret key used in production"), default=None
            )
            return False

        # Additional production checks
        self.validator.validate(
            "DEBUG",
            required=False,
            validator=lambda v: (v.lower() not in ("true", "1", "yes", "on"), "Debug mode should be disabled in production"),
            default="false",
        )

        self.validator.validate(
            "MOCK_MODE",
            required=False,
            validator=lambda v: (v.lower() not in ("true", "1", "yes", "on"), "Mock mode should be disabled in production"),
            default="false",
        )

        return not self.validator.has_failures()

    def validate_all(self) -> bool:
        """Validate all configuration settings"""
        common_valid = self.validate_common_config()

        # If we're in production, also validate production-specific settings
        if os.getenv("FLASK_ENV", "").lower() == "production":
            production_valid = self.validate_production_config()
            return common_valid and production_valid

        return common_valid

    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors"""
        return [str(result) for result in self.validator.get_failures()]

    def get_validation_results(self) -> str:
        """Get formatted validation results"""
        return self.validator.format_results()

    def get_error_summary(self) -> str:
        """Get formatted error summary"""
        return self.validator.format_failures()


def load_config() -> Type[BaseConfig]:
    """Load and validate configuration"""
    loader = ConfigLoader()

    # Validate configuration
    if not loader.validate_all():
        error_summary = loader.get_error_summary()
        logger.error(f"Configuration validation failed:\n{error_summary}")

        # Only raise exception in production, warn in development
        if os.getenv("FLASK_ENV", "").lower() == "production":
            raise ValueError(f"Invalid configuration:\n{error_summary}")

    # Get the appropriate config class
    return loader.get_config_class()
