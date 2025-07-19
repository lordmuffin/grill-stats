"""
Models package initialization.

This module imports all models and managers to ensure proper initialization
order and provides convenient imports for the rest of the application.
"""

# Import the base database module first
from models.base import Base, db
from models.device_model import DeviceManager, DeviceModel
from models.grilling_session_model import GrillingSessionManager, GrillingSessionModel
from models.temperature_alert_model import AlertType, TemperatureAlertManager, TemperatureAlertModel

# Import all manager classes
# Import all model classes
from models.user_model import UserManager, UserModel

# Create legacy-compatible manager aliases
# These provide backward compatibility with the existing code
User = UserManager
Device = DeviceManager
TemperatureAlert = TemperatureAlertManager
GrillingSession = GrillingSessionManager

# Export all classes for convenient importing
__all__ = [
    "db",
    "Base",
    "UserModel",
    "DeviceModel",
    "TemperatureAlertModel",
    "GrillingSessionModel",
    "AlertType",
    "UserManager",
    "DeviceManager",
    "TemperatureAlertManager",
    "GrillingSessionManager",
    "User",
    "Device",
    "TemperatureAlert",
    "GrillingSession",
]
