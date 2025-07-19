"""
Mock Device model for testing.

This module provides a modified Device model class that doesn't have circular dependencies
between models, making it suitable for isolated unit tests.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


class MockDevice:
    """
    Mock Device model for testing without circular dependencies.

    This class implements the same API as the real Device class but uses
    the mock models from test_models.py to avoid circular dependencies.
    """

    model: Any  # Will be set to MockDeviceModel in __init__
    db: Any  # SQLAlchemy database instance

    def __init__(self, db: Any) -> None:
        """
        Initialize the mock Device model.

        Args:
            db: SQLAlchemy database instance
        """
        self.db = db

        # Use the pre-defined mock model from the test database
        # instead of creating a new one to avoid circular dependencies
        # Get all models from a temporary TestDatabase instance
        from flask import current_app

        from tests.utils.test_db import TestDatabase

        test_db = TestDatabase(current_app)
        models = test_db.get_models()

        # Use the mock DeviceModel
        self.model = models["DeviceModel"]

    @staticmethod
    def validate_device_id(device_id: Optional[str]) -> Tuple[bool, str]:
        """
        Validate ThermoWorks device ID format (TW-XXX-XXX).

        Args:
            device_id: Device ID to validate

        Returns:
            Tuple of (is_valid, message)
        """
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

    def create_device(self, user_id: int, device_id: str, nickname: Optional[str] = None) -> Any:
        """
        Create a new device for a user.

        Args:
            user_id: User ID
            device_id: Device ID
            nickname: Optional device nickname

        Returns:
            The created device model instance

        Raises:
            ValueError: If device ID is invalid or already exists
        """
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

    def get_device_by_id(self, device_id: str) -> Optional[Any]:
        """
        Get device by device_id.

        Args:
            device_id: Device ID

        Returns:
            Device model instance or None if not found
        """
        return self.model.query.filter_by(device_id=device_id.upper()).first()

    def get_user_devices(self, user_id: int, include_inactive: bool = False) -> List[Any]:
        """
        Get all devices for a user.

        Args:
            user_id: User ID
            include_inactive: Whether to include inactive devices

        Returns:
            List of device model instances
        """
        query = self.model.query.filter_by(user_id=user_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        # Explicitly cast the result to List[Any] to satisfy mypy
        result: List[Any] = query.all()
        return result

    def get_user_device(self, user_id: int, device_id: str) -> Optional[Any]:
        """
        Get a specific device for a user.

        Args:
            user_id: User ID
            device_id: Device ID

        Returns:
            Device model instance or None if not found
        """
        return self.model.query.filter_by(user_id=user_id, device_id=device_id.upper(), is_active=True).first()

    def soft_delete_device(self, user_id: int, device_id: str) -> Any:
        """
        Soft delete a device (set is_active=False).

        Args:
            user_id: User ID
            device_id: Device ID

        Returns:
            Updated device model instance

        Raises:
            ValueError: If device not found
        """
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found or already deleted")

        device.is_active = False
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def update_device_status(self, device_id: str, status: str) -> Optional[Any]:
        """
        Update device status (online/offline/error).

        Args:
            device_id: Device ID
            status: New status

        Returns:
            Updated device model instance or None if not found
        """
        device = self.get_device_by_id(device_id)
        if device:
            device.status = status
            device.updated_at = datetime.utcnow()
            self.db.session.commit()
        return device

    def update_device_nickname(self, user_id: int, device_id: str, nickname: str) -> Any:
        """
        Update device nickname.

        Args:
            user_id: User ID
            device_id: Device ID
            nickname: New nickname

        Returns:
            Updated device model instance

        Raises:
            ValueError: If device not found
        """
        device = self.get_user_device(user_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        device.nickname = nickname
        device.updated_at = datetime.utcnow()
        self.db.session.commit()
        return device

    def check_device_in_session(self, device_id: str) -> bool:
        """
        Check if device is currently in an active grilling session.

        Args:
            device_id: Device ID

        Returns:
            True if in active session, False otherwise
        """
        # For test mock, always return False
        return False
