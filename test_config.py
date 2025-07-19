#!/usr/bin/env python3
"""
Test script for the environment configuration and validation system.

This script tests the config module's ability to validate environment variables
and configure the application correctly for different environments.
"""

import logging
import os
import sys
from unittest import mock

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config.config_loader import BaseConfig, ConfigLoader, DevelopmentConfig, DockerConfig, ProductionConfig, TestingConfig
from config.env_validator import EnvironmentValidator, EnvVarStatus


def test_environment_validator() -> None:
    """Test the EnvironmentValidator class"""
    logger.info("Testing EnvironmentValidator...")

    # Create a validator
    validator = EnvironmentValidator()

    # Test validation of a required variable that's missing
    with mock.patch.dict(os.environ, {}, clear=True):
        result = validator.validate("TEST_VAR", required=True)
        assert result.status == EnvVarStatus.MISSING
        logger.info("✓ Correctly identified missing required variable")

    # Test validation of a required variable that's present
    with mock.patch.dict(os.environ, {"TEST_VAR": "test_value"}, clear=True):
        result = validator.validate("TEST_VAR", required=True)
        assert result.status == EnvVarStatus.VALID
        logger.info("✓ Correctly validated present required variable")

    # Test validation with a custom validator function
    with mock.patch.dict(os.environ, {"TEST_VAR": "invalid"}, clear=True):
        result = validator.validate("TEST_VAR", required=True, validator=lambda v: (v == "valid", "Value must be 'valid'"))
        assert result.status == EnvVarStatus.INVALID
        logger.info("✓ Correctly identified invalid value with custom validator")

    # Test validation with a default value
    with mock.patch.dict(os.environ, {}, clear=True):
        result = validator.validate("TEST_VAR", required=True, default="default_value")
        assert result.status == EnvVarStatus.VALID
        assert result.value == "default_value"
        logger.info("✓ Correctly used default value for missing variable")

    # Test warning on default value
    with mock.patch.dict(os.environ, {}, clear=True):
        result = validator.validate("TEST_VAR", required=True, default="default_value", warn_default=True)
        assert result.status == EnvVarStatus.WARNING
        logger.info("✓ Correctly warned about using default value")

    logger.info("All EnvironmentValidator tests passed!")


def test_config_loader() -> None:
    """Test the ConfigLoader class"""
    logger.info("Testing ConfigLoader...")

    # Test getting the correct config class based on environment
    with mock.patch.dict(os.environ, {"FLASK_ENV": "development"}, clear=True):
        loader = ConfigLoader()
        config_class = loader.get_config_class()
        assert config_class == DevelopmentConfig
        logger.info("✓ Correctly loaded DevelopmentConfig for development environment")

    with mock.patch.dict(os.environ, {"FLASK_ENV": "testing"}, clear=True):
        loader = ConfigLoader()
        config_class = loader.get_config_class()
        assert config_class == TestingConfig
        logger.info("✓ Correctly loaded TestingConfig for testing environment")

    with mock.patch.dict(os.environ, {"FLASK_ENV": "production"}, clear=True):
        loader = ConfigLoader()
        config_class = loader.get_config_class()
        assert config_class == ProductionConfig
        logger.info("✓ Correctly loaded ProductionConfig for production environment")

    with mock.patch.dict(os.environ, {"FLASK_ENV": "docker"}, clear=True):
        loader = ConfigLoader()
        config_class = loader.get_config_class()
        assert config_class == DockerConfig
        logger.info("✓ Correctly loaded DockerConfig for docker environment")

    # Test validation of common configuration in testing mode (more relaxed requirements)
    test_env = {
        "SECRET_KEY": "aVeryLongAndSecureRandomKeyForTesting12345",  # Avoid common patterns in key
        "MOCK_MODE": "true",  # With mock mode true, API keys can be placeholders
        "THERMOWORKS_API_KEY": "test-api-key-long-enough",
        "HOMEASSISTANT_URL": "http://homeassistant:8123",
        "HOMEASSISTANT_TOKEN": "test-token-long-enough-for-validation",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "FLASK_ENV": "testing",  # Use testing environment for tests
    }

    with mock.patch.dict(os.environ, test_env, clear=True):
        loader = ConfigLoader()
        result = loader.validate_common_config()
        if not result:
            logger.error(f"Common config validation failed: {loader.get_error_summary()}")
            logger.info(f"All validation results: {loader.get_validation_results()}")
        assert result is True
        logger.info("✓ Successfully validated common configuration")

    # Test validation of production configuration
    with mock.patch.dict(os.environ, {**test_env, "FLASK_ENV": "production"}, clear=True):
        loader = ConfigLoader()
        # This should fail because we're using a default-looking secret key
        assert loader.validate_production_config() is False
        logger.info("✓ Correctly rejected weak secret key in production")

    # Test validation with proper production settings
    production_env = {
        **test_env,
        "FLASK_ENV": "production",
        "SECRET_KEY": "super-secure-production-key-123456789",
        "DEBUG": "false",
        "MOCK_MODE": "false",
    }

    with mock.patch.dict(os.environ, production_env, clear=True):
        loader = ConfigLoader()
        assert loader.validate_production_config() is True
        logger.info("✓ Successfully validated proper production configuration")

    logger.info("All ConfigLoader tests passed!")


def test_config_classes() -> None:
    """Test the configuration classes"""
    logger.info("Testing configuration classes...")

    # Test BaseConfig
    assert hasattr(BaseConfig, "SECRET_KEY")
    assert hasattr(BaseConfig, "SQLALCHEMY_DATABASE_URI")
    assert hasattr(BaseConfig, "MOCK_MODE")

    # Test DevelopmentConfig
    assert DevelopmentConfig.DEBUG is True
    assert DevelopmentConfig.MOCK_MODE is True

    # Test TestingConfig
    assert TestingConfig.TESTING is True
    assert TestingConfig.MOCK_MODE is True

    # Test ProductionConfig
    assert ProductionConfig.DEBUG is False
    assert ProductionConfig.TESTING is False
    assert ProductionConfig.MOCK_MODE is False

    logger.info("All configuration class tests passed!")


def main() -> bool:
    """Run all tests"""
    logger.info("Starting Environment Configuration System tests...")

    try:
        test_environment_validator()
        test_config_loader()
        test_config_classes()

        logger.info("🎉 All environment configuration tests passed successfully!")
        return True

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
