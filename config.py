"""Configuration module for Grill Stats application

This module re-exports configuration classes and loaders from the config package.
"""

import logging

from config.config_loader import load_config
from config.env_validator import EnvironmentValidator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the appropriate configuration class
try:
    Config = load_config()
    logger.info(f"Loaded configuration for environment: {Config.__name__}")
except Exception as e:
    logger.error(f"Error loading configuration: {e}")
    raise

# For backwards compatibility, export TestConfig
from config.config_loader import TestingConfig as TestConfig
