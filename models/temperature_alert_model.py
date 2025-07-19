"""
Temperature Alert model for monitoring probe temperatures.

This module defines the TemperatureAlertModel class and related functionality
for monitoring temperature readings and generating alerts.
"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base, db


class AlertType(enum.Enum):
    """Alert types supported by the system."""

    TARGET = "target"
    RANGE = "range"
    RISING = "rising"
    FALLING = "falling"


class TemperatureAlertModel(Base):
    """Temperature Alert model for monitoring probe temperatures."""

    __tablename__ = "temperature_alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String(100), nullable=False)
    probe_id = Column(String(100), nullable=False)

    # Alert configuration
    target_temperature = Column(Float, nullable=True)  # For target alerts
    min_temperature = Column(Float, nullable=True)  # For range alerts
    max_temperature = Column(Float, nullable=True)  # For range alerts
    threshold_value = Column(Float, nullable=True)  # For rising/falling alerts

    alert_type = Column(Enum(AlertType), nullable=False, default=AlertType.TARGET)
    temperature_unit = Column(String(1), default="F")  # F or C

    # Alert state
    is_active = Column(Boolean, default=True)
    triggered_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_temperature = Column(Float, nullable=True)  # Track last known temperature
    notification_sent = Column(Boolean, default=False)

    # Metadata
    name = Column(String(100), nullable=True)  # User-friendly alert name
    description = Column(String(255), nullable=True)  # Optional description
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Use string references to avoid circular imports
    user = relationship("UserModel", back_populates="temperature_alerts")

    def __repr__(self) -> str:
        """String representation of the temperature alert."""
        return f"<TemperatureAlert {self.id}: {self.name} ({self.alert_type.value})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "probe_id": self.probe_id,
            "name": self.name,
            "description": self.description,
            "alert_type": self.alert_type.value,
            "target_temperature": self.target_temperature,
            "min_temperature": self.min_temperature,
            "max_temperature": self.max_temperature,
            "threshold_value": self.threshold_value,
            "temperature_unit": self.temperature_unit,
            "is_active": self.is_active,
            "triggered_at": (self.triggered_at.isoformat() if self.triggered_at else None),
            "last_checked_at": (self.last_checked_at.isoformat() if self.last_checked_at else None),
            "last_temperature": self.last_temperature,
            "notification_sent": self.notification_sent,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
            "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
        }

    def should_trigger(self, current_temperature: Optional[float]) -> bool:
        """Check if this alert should trigger based on current temperature."""
        if not self.is_active or current_temperature is None:
            return False

        # Convert temperature if needed (assuming input is always in Fahrenheit for now)
        temp = current_temperature

        if self.alert_type == AlertType.TARGET:
            # Trigger when temperature reaches or exceeds target
            return bool(temp >= self.target_temperature)

        elif self.alert_type == AlertType.RANGE:
            # Trigger when temperature is outside the range
            return bool(temp < self.min_temperature or temp > self.max_temperature)

        elif self.alert_type == AlertType.RISING:
            # Trigger when temperature rises by threshold amount
            if self.last_temperature is not None:
                return bool((temp - self.last_temperature) >= self.threshold_value)
            return False

        elif self.alert_type == AlertType.FALLING:
            # Trigger when temperature falls by threshold amount
            if self.last_temperature is not None:
                return bool((self.last_temperature - temp) >= self.threshold_value)
            return False

        return False

    def update_temperature(self, current_temperature: float) -> None:
        """Update the last known temperature and check time."""
        self.last_temperature = current_temperature
        self.last_checked_at = datetime.utcnow()

    def trigger_alert(self) -> None:
        """Mark alert as triggered."""
        self.triggered_at = datetime.utcnow()
        self.notification_sent = False  # Reset to allow new notification

    def mark_notification_sent(self) -> None:
        """Mark that notification has been sent for this trigger."""
        self.notification_sent = True


class TemperatureAlertManager:
    """Manager class for temperature alert operations."""

    def __init__(self, db_instance=None) -> None:
        """Initialize temperature alert manager with database instance."""
        self.db = db_instance or db

    def create_alert(
        self, user_id: int, device_id: str, probe_id: str, alert_type: AlertType, **kwargs: Any
    ) -> TemperatureAlertModel:
        """Create a new temperature alert."""
        alert = TemperatureAlertModel(
            user_id=user_id,
            device_id=device_id,
            probe_id=probe_id,
            alert_type=alert_type,
            **kwargs,
        )
        self.db.session.add(alert)
        self.db.session.commit()
        return alert

    def get_user_alerts(self, user_id: int, active_only: bool = True) -> List[TemperatureAlertModel]:
        """Get all alerts for a user."""
        query = TemperatureAlertModel.query.filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        alerts = query.all()
        return alerts

    def get_alert_by_id(self, alert_id: int, user_id: Optional[int] = None) -> Optional[TemperatureAlertModel]:
        """Get a specific alert by ID."""
        query = TemperatureAlertModel.query.filter_by(id=alert_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        alert = query.first()
        return alert

    def get_alerts_for_device_probe(
        self, device_id: str, probe_id: str, active_only: bool = True
    ) -> List[TemperatureAlertModel]:
        """Get all alerts for a specific device/probe combination."""
        query = TemperatureAlertModel.query.filter_by(device_id=device_id, probe_id=probe_id)
        if active_only:
            query = query.filter_by(is_active=True)
        alerts = query.all()
        return alerts

    def get_active_alerts(self) -> List[TemperatureAlertModel]:
        """Get all active alerts for monitoring."""
        alerts = TemperatureAlertModel.query.filter_by(is_active=True).all()
        return alerts

    def update_alert(self, alert_id: int, user_id: int, **kwargs: Any) -> Optional[TemperatureAlertModel]:
        """Update an existing alert."""
        alert = self.get_alert_by_id(alert_id, user_id)
        if alert:
            for key, value in kwargs.items():
                if hasattr(alert, key):
                    setattr(alert, key, value)
            alert.updated_at = datetime.utcnow()
            self.db.session.commit()
            return alert
        return None

    def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """Delete an alert (soft delete by setting is_active=False)."""
        alert = self.get_alert_by_id(alert_id, user_id)
        if alert:
            alert.is_active = False
            alert.updated_at = datetime.utcnow()
            self.db.session.commit()
            return True
        return False

    def validate_alert_data(self, alert_type: AlertType, **kwargs: Any) -> List[str]:
        """Validate alert configuration data."""
        errors = []

        if alert_type == AlertType.TARGET:
            if "target_temperature" not in kwargs or kwargs["target_temperature"] is None:
                errors.append("Target temperature is required for target alerts")
            elif not isinstance(kwargs["target_temperature"], (int, float)):
                errors.append("Target temperature must be a number")

        elif alert_type == AlertType.RANGE:
            if "min_temperature" not in kwargs or kwargs["min_temperature"] is None:
                errors.append("Minimum temperature is required for range alerts")
            if "max_temperature" not in kwargs or kwargs["max_temperature"] is None:
                errors.append("Maximum temperature is required for range alerts")
            if (
                kwargs.get("min_temperature") is not None
                and kwargs.get("max_temperature") is not None
                and kwargs["min_temperature"] >= kwargs["max_temperature"]
            ):
                errors.append("Minimum temperature must be less than maximum temperature")

        elif alert_type in [AlertType.RISING, AlertType.FALLING]:
            if "threshold_value" not in kwargs or kwargs["threshold_value"] is None:
                errors.append("Threshold value is required for rising/falling alerts")
            elif not isinstance(kwargs["threshold_value"], (int, float)) or kwargs["threshold_value"] <= 0:
                errors.append("Threshold value must be a positive number")

        return errors
