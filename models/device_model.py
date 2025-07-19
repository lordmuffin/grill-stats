"""
Device model for ThermoWorks device management.

This module defines the DeviceModel class for storing device information
and related tables. It uses SQLAlchemy for ORM functionality.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base, db


class DeviceModel(Base):
    """Device model for ThermoWorks device management."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String(50), unique=True, nullable=False)
    nickname = Column(String(100), nullable=True)
    status = Column(String(20), default="offline")  # online, offline, error
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Use string references to avoid circular imports
    user = relationship("UserModel", back_populates="devices")

    def __repr__(self) -> str:
        """String representation of the device."""
        return f'<Device {self.device_id} ({self.nickname or "No nickname"})>'

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "nickname": self.nickname,
            "status": self.status,
            "is_active": self.is_active,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
            "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
        }


class DeviceManager:
    """Manager class for device operations."""

    def __init__(self, db_instance=None) -> None:
        """Initialize device manager with database instance."""
        self.db = db_instance or db

    @staticmethod
    def validate_device_id(device_id: Optional[str]) -> Tuple[bool, str]:
        """Validate ThermoWorks device ID format (TW-XXX-XXX)."""
        if not device_id:
            return False, "Device ID is required"

        # First check if device_id is exactly in uppercase format
        # If it contains lowercase letters, it should fail validation
        if device_id != device_id.upper():
            return False, "Device ID must be uppercase. Expected format: TW-XXX-XXX"

        # ThermoWorks format: TW-XXX-XXX (where X can be alphanumeric)
        pattern = r"^TW-[A-Z0-9]{3}-[A-Z0-9]{3}$"
        if not re.match(pattern, device_id):
            return False, "Invalid device ID format. Expected format: TW-XXX-XXX"

        return True, "Valid device ID format"

    def create_device(self, user_id: int, device_id: str, nickname: Optional[str] = None) -> DeviceModel:
        """Create a new device for a user."""
        # Validate device ID format
        is_valid, message = self.validate_device_id(device_id)
        if not is_valid:
            raise ValueError(message)

        # Check if device already exists
        existing_device = DeviceModel.query.filter_by(device_id=device_id.upper()).first()
        if existing_device:
            raise ValueError(f"Device {device_id} is already registered")

        device = DeviceModel(user_id=user_id, device_id=device_id.upper(), nickname=nickname)
        self.db.session.add(device)
        self.db.session.commit()
        return device

    def get_device_by_id(self, device_id: str) -> Optional[DeviceModel]:
        """Get device by device_id."""
        device = DeviceModel.query.filter_by(device_id=device_id.upper()).first()
        return device

    def get_user_devices(self, user_id: int, include_inactive: bool = False) -> List[DeviceModel]:
        """Get all devices for a user."""
        query = DeviceModel.query.filter_by(user_id=user_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        devices = query.all()
        return devices

    def get_user_device(self, user_id: int, device_id: str) -> Optional[DeviceModel]:
        """Get a specific device for a user."""
        device = DeviceModel.query.filter_by(user_id=user_id, device_id=device_id.upper(), is_active=True).first()
        return device

    def soft_delete_device(self, user_id: int, device_id: str) -> DeviceModel:
        """Soft delete a device (set is_active=False)."""
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found or already deleted")

        device.is_active = False
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def update_device_status(self, device_id: str, status: str) -> Optional[DeviceModel]:
        """Update device status (online/offline/error)."""
        device = self.get_device_by_id(device_id)
        if device:
            device.status = status
            device.updated_at = datetime.utcnow()
            self.db.session.commit()
        return device

    def update_device_nickname(self, user_id: int, device_id: str, nickname: str) -> DeviceModel:
        """Update device nickname."""
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        device.nickname = nickname
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def check_device_in_session(self, device_id: str) -> bool:
        """Check if device is currently in an active grilling session."""
        # TODO: This will be implemented when session tracking is added
        # For now, return False to allow deletion
        return False
