"""
Environment Variable Validator for Grill Stats

This module provides utilities to validate environment variables and configuration
settings for the Grill Stats application. It ensures that required variables are
present and have the correct types/formats before the application starts.
"""

import logging
import os
import re
import socket
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class EnvVarStatus(Enum):
    """Status of environment variable validation"""

    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"
    INSECURE = "insecure"
    WARNING = "warning"


class EnvVarValidationResult:
    """Result of validating an environment variable"""

    def __init__(self, name: str, status: EnvVarStatus, value: Optional[str] = None, message: Optional[str] = None):
        self.name = name
        self.status = status
        # Store value only for logging/reporting, avoid storing sensitive values
        self.value = self._sanitize_sensitive_value(name, value)
        self.message = message

    def _sanitize_sensitive_value(self, name: str, value: Optional[str]) -> Optional[str]:
        """Sanitize sensitive values for logging/reporting"""
        if value is None:
            return None

        sensitive_vars = {"API_KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIAL", "JWT"}

        # Check if any sensitive words appear in the variable name
        if any(word in name.upper() for word in sensitive_vars):
            if value:
                return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}" if len(value) > 2 else "***"
            return None
        return value

    def __str__(self) -> str:
        """String representation of validation result"""
        if self.status == EnvVarStatus.VALID:
            return f"{self.name}: ✓ VALID"
        elif self.status == EnvVarStatus.MISSING:
            return f"{self.name}: ✗ MISSING - {self.message or 'Required variable is not set'}"
        elif self.status == EnvVarStatus.INVALID:
            return f"{self.name}: ✗ INVALID - {self.message or 'Value fails validation'}"
        elif self.status == EnvVarStatus.WARNING:
            return f"{self.name}: ⚠ WARNING - {self.message or 'Potential issue detected'}"
        elif self.status == EnvVarStatus.INSECURE:
            return f"{self.name}: ⚠ INSECURE - {self.message or 'Using insecure value'}"
        return f"{self.name}: {self.status}"


class EnvironmentValidator:
    """Validates environment variables for the application"""

    def __init__(self) -> None:
        self.results: List[EnvVarValidationResult] = []
        self.required_vars: Set[str] = set()
        self.failed_validations: List[EnvVarValidationResult] = []

    def validate(
        self,
        var_name: str,
        required: bool = True,
        validator: Optional[Callable[[str], Tuple[bool, Optional[str]]]] = None,
        default: Optional[str] = None,
        warn_default: bool = False,
    ) -> EnvVarValidationResult:
        """
        Validate an environment variable

        Args:
            var_name: Name of the environment variable
            required: Whether the variable is required
            validator: Optional function to validate the value
            default: Default value to use if variable is not set
            warn_default: Whether to warn if using default value

        Returns:
            EnvVarValidationResult: Result of validation
        """
        value = os.getenv(var_name)

        # Track required variables
        if required:
            self.required_vars.add(var_name)

        # Check if variable is missing
        if value is None:
            if required and default is None:
                result = EnvVarValidationResult(
                    var_name, EnvVarStatus.MISSING, None, f"Required variable {var_name} is not set"
                )
                self.results.append(result)
                self.failed_validations.append(result)
                return result
            elif default is not None:
                value = default
                if warn_default:
                    result = EnvVarValidationResult(
                        var_name, EnvVarStatus.WARNING, value, f"Using default value for {var_name}"
                    )
                    self.results.append(result)
                    return result

        # Validate the value if a validator is provided
        if validator and value is not None:
            is_valid, message = validator(value)
            if not is_valid:
                result = EnvVarValidationResult(
                    var_name, EnvVarStatus.INVALID, value, message or f"Invalid value for {var_name}"
                )
                self.results.append(result)
                self.failed_validations.append(result)
                return result

        # If we got here, the value is valid
        result = EnvVarValidationResult(var_name, EnvVarStatus.VALID, value)
        self.results.append(result)
        return result

    def get_env_or_default(self, var_name: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable value or default"""
        return os.getenv(var_name, default)

    def has_failures(self) -> bool:
        """Check if any validations failed"""
        return len(self.failed_validations) > 0

    def get_failures(self) -> List[EnvVarValidationResult]:
        """Get all failed validations"""
        return self.failed_validations

    def get_results(self) -> List[EnvVarValidationResult]:
        """Get all validation results"""
        return self.results

    def format_failures(self) -> str:
        """Format failed validations as a string"""
        if not self.failed_validations:
            return "All environment variables passed validation."

        lines = ["Environment validation failed:"]
        for result in self.failed_validations:
            lines.append(f"  - {result}")
        return "\n".join(lines)

    def format_results(self) -> str:
        """Format all validation results as a string"""
        if not self.results:
            return "No environment variables were validated."

        lines = ["Environment validation results:"]
        for result in self.results:
            lines.append(f"  - {result}")
        return "\n".join(lines)


# Common validation functions


def validate_url(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a URL"""
    try:
        result = urlparse(value)
        if not all([result.scheme, result.netloc]):
            return False, f"Invalid URL format: {value}"
        return True, None
    except Exception:
        return False, f"Could not parse URL: {value}"


def validate_port(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a port number"""
    try:
        port = int(value)
        if not (0 < port < 65536):
            return False, f"Port must be between 1 and 65535, got: {port}"
        return True, None
    except ValueError:
        return False, f"Port must be a number, got: {value}"


def validate_api_key(value: str) -> Tuple[bool, Optional[str]]:
    """Validate an API key (basic checks)"""
    if not value or len(value) < 10:
        return False, "API key is too short (should be at least 10 characters)"
    return True, None


def validate_token(value: str) -> Tuple[bool, Optional[str]]:
    """Validate an authentication token (basic checks)"""
    if not value or len(value) < 10:
        return False, "Token is too short (should be at least 10 characters)"
    return True, None


def validate_boolean(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a boolean value"""
    valid_true = {"true", "1", "yes", "y", "on", "t"}
    valid_false = {"false", "0", "no", "n", "off", "f"}

    if value.lower() not in valid_true and value.lower() not in valid_false:
        return False, f"Invalid boolean value: {value}. Use true/false, yes/no, 1/0, on/off."
    return True, None


def validate_email(value: str) -> Tuple[bool, Optional[str]]:
    """Validate an email address"""
    # Basic email validation pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, value):
        return False, f"Invalid email format: {value}"
    return True, None


def validate_secret_key(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a secret key"""
    if not value:
        return False, "Secret key cannot be empty"

    if len(value) < 24:
        return False, "Secret key is too short (should be at least 24 characters)"

    # Check for default or common testing keys
    common_keys = {
        "dev-secret-key",
        "development",
        "test",
        "secret",
        "your-secret-key",
        "dev-secret-key-change-in-production",
        "your-flask-secret-key-change-this-in-production",
    }

    if any(common in value.lower() for common in common_keys):
        return False, "Using a default or common secret key is not secure"

    return True, None


def validate_host(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a hostname"""
    try:
        # Check if it's a valid hostname or IP address
        socket.gethostbyname(value)
        return True, None
    except socket.error:
        # Special cases for docker networks and local development
        if value in {"localhost", "127.0.0.1", "host.docker.internal", "postgres", "redis", "homeassistant"}:
            return True, None
        return False, f"Invalid hostname: {value}"


def validate_path(value: str) -> Tuple[bool, Optional[str]]:
    """Validate a file path"""
    if not value:
        return False, "Path cannot be empty"

    # Avoid absolute path validation as it depends on runtime environment
    return True, None
