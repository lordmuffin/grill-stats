from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from . import Base


class DeviceHealth(Base):
    """SQLAlchemy model for device_health table"""

    __tablename__ = "device_health"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(255), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    battery_level = Column(Integer, nullable=True)
    signal_strength = Column(Integer, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    device = relationship("Device", back_populates="health_records")

    def __repr__(self) -> str:
        return f"<DeviceHealth(device_id='{self.device_id}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert DeviceHealth object to dictionary"""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "battery_level": self.battery_level,
            "signal_strength": self.signal_strength,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
