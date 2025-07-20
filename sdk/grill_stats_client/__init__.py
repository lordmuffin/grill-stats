"""
Grill Stats SDK client library.

This package provides client libraries for interacting with the Grill Stats API,
including ThermoWorks devices and Home Assistant integration.
"""

from .base_client import APIError, AuthenticationError, BaseClient, ClientError, ConnectionError, ServerError
from .homeassistant_client import HomeAssistantClient
from .thermoworks_client import ThermoWorksClient

__all__ = [
    "APIError",
    "AuthenticationError",
    "BaseClient",
    "ClientError",
    "ConnectionError",
    "HomeAssistantClient",
    "ServerError",
    "ThermoWorksClient",
]

__version__ = "0.1.0"
