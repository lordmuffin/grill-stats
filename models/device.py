import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Query, relationship


class Device:
    """Device model for ThermoWorks device management"""

    model: Type[Any]  # Will be set to DeviceModel in __init__
    db: SQLAlchemy

    def __init__(self, db: SQLAlchemy) -> None:
        self.db = db

        # Define DeviceModel class with type annotation
        # This addresses the "db.Model is not defined" error
        DeviceModel: Type[Any] = self.db.Model

        class DeviceModel(DeviceModel):  # type: ignore
            __tablename__ = "devices"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
            device_id = Column(String(50), unique=True, nullable=False)
            nickname = Column(String(100), nullable=True)
            status = Column(String(20), default="offline")  # online, offline, error
            is_active = Column(Boolean, default=True)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            # Use back_populates instead of backref for explicit relationship management
            user = relationship("UserModel", back_populates="devices")

            def __repr__(self) -> str:
                return f'<Device {self.device_id} ({self.nickname or "No nickname"})>'

            def to_dict(self) -> Dict[str, Any]:
                """Convert device to dictionary for JSON serialization"""
                return {
                    "id": self.id,
                    "device_id": self.device_id,
                    "nickname": self.nickname,
                    "status": self.status,
                    "is_active": self.is_active,
                    "created_at": (self.created_at.isoformat() if self.created_at else None),
                    "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
                }

        # Store the model class for later use
        self.model = DeviceModel  # type: ignore

    @staticmethod
    def validate_device_id(device_id: Optional[str]) -> Tuple[bool, str]:
        """Validate ThermoWorks device ID format (TW-XXX-XXX)"""
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

    def create_device(self, user_id: int, device_id: str, nickname: Optional[str] = None) -> Any:  # Returns DeviceModel
        """Create a new device for a user"""
        # Validate device ID format
        is_valid, message = self.validate_device_id(device_id)
        if not is_valid:
            raise ValueError(message)

        # Check if device already exists
        existing_device = self.model.query.filter_by(device_id=device_id.upper()).first()
        if existing_device:
            raise ValueError(f"Device {device_id} is already registered")

        device = self.model(user_id=user_id, device_id=device_id.upper(), nickname=nickname)
        self.db.session.add(device)
        self.db.session.commit()
        return device

    def get_device_by_id(self, device_id: str) -> Optional[Any]:  # Returns Optional[DeviceModel]
        """Get device by device_id"""
        return self.model.query.filter_by(device_id=device_id.upper()).first()

    def get_user_devices(self, user_id: int, include_inactive: bool = False) -> List[Any]:  # Returns List[DeviceModel]
        """Get all devices for a user"""
        query = self.model.query.filter_by(user_id=user_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        # Explicitly cast the result to List[Any] to satisfy mypy
        result: List[Any] = query.all()
        return result

    def get_user_device(self, user_id: int, device_id: str) -> Optional[Any]:  # Returns Optional[DeviceModel]
        """Get a specific device for a user"""
        return self.model.query.filter_by(user_id=user_id, device_id=device_id.upper(), is_active=True).first()

    def soft_delete_device(self, user_id: int, device_id: str) -> Any:  # Returns DeviceModel
        """Soft delete a device (set is_active=False)"""
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found or already deleted")

        device.is_active = False
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def update_device_status(self, device_id: str, status: str) -> Optional[Any]:  # Returns Optional[DeviceModel]
        """Update device status (online/offline/error)"""
        device = self.get_device_by_id(device_id)
        if device:
            device.status = status
            device.updated_at = datetime.utcnow()
            self.db.session.commit()
        return device

    def update_device_nickname(self, user_id: int, device_id: str, nickname: str) -> Any:  # Returns DeviceModel
        """Update device nickname"""
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        device.nickname = nickname
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def check_device_in_session(self, device_id: str) -> bool:
        """Check if device is currently in an active grilling session"""
        # TODO: This will be implemented when session tracking is added
        # For now, return False to allow deletion
        return False
