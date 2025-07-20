from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from . import Base


class Device(Base):
    """SQLAlchemy model for devices table"""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    device_type = Column(String(100), nullable=False)
    configuration = Column(JSON, nullable=True)
    user_id = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    health_records = relationship("DeviceHealth", back_populates="device", cascade="all, delete-orphan")
    gateway_status = relationship("GatewayStatus", back_populates="device", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="device", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Device(device_id='{self.device_id}', name='{self.name}', type='{self.device_type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert Device object to dictionary"""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "configuration": self.configuration,
            "user_id": self.user_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
