from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from . import Base


class AuditLog(Base):
    """SQLAlchemy model for audit_log table"""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    action = Column(String(100), nullable=False)
    device_id = Column(String(255), ForeignKey("devices.device_id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String(255), nullable=True)
    changes = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    device = relationship("Device", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', device_id='{self.device_id}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert AuditLog object to dictionary"""
        return {
            "id": self.id,
            "action": self.action,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "changes": self.changes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
