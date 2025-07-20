from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from . import Base


class GatewayStatus(Base):
    """SQLAlchemy model for gateway_status table"""

    __tablename__ = "gateway_status"

    id = Column(Integer, primary_key=True)
    gateway_id = Column(String(255), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    online = Column(Boolean, default=False)
    wifi_connected = Column(Boolean, default=False)
    wifi_ssid = Column(String(255), nullable=True)
    wifi_signal_strength = Column(Integer, nullable=True)
    cloud_linked = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    status = Column(String(50), default="unknown")
    firmware_version = Column(String(50), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    device = relationship("Device", back_populates="gateway_status")

    def __repr__(self) -> str:
        return f"<GatewayStatus(gateway_id='{self.gateway_id}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert GatewayStatus object to dictionary"""
        return {
            "id": self.id,
            "gateway_id": self.gateway_id,
            "online": self.online,
            "wifi_connected": self.wifi_connected,
            "wifi_ssid": self.wifi_ssid,
            "wifi_signal_strength": self.wifi_signal_strength,
            "cloud_linked": self.cloud_linked,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status,
            "firmware_version": self.firmware_version,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
