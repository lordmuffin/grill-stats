from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannelType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    condition = Column(JSON, nullable=False)
    severity = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alerts = relationship("Alert", back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    fingerprint = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(String(50), nullable=False)
    status = Column(String(50), default=AlertStatus.ACTIVE)
    source = Column(String(255))
    labels = Column(JSON)
    annotations = Column(JSON)
    starts_at = Column(DateTime, default=datetime.utcnow)
    ends_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(255))
    resolved_at = Column(DateTime)
    resolved_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rule = relationship("AlertRule", back_populates="alerts")
    events = relationship("AlertEvent", back_populates="alert")
    correlations = relationship("AlertCorrelation", back_populates="alert")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    event_type = Column(
        String(50), nullable=False
    )  # created, updated, acknowledged, resolved
    event_data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(255))

    # Relationships
    alert = relationship("Alert", back_populates="events")


class AlertCorrelation(Base):
    __tablename__ = "alert_correlations"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    correlation_id = Column(String(255), nullable=False)
    correlation_type = Column(String(50), nullable=False)  # temporal, spatial, causal
    confidence_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    alert = relationship("Alert", back_populates="correlations")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    configuration = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    rules = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic models for API
class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    condition: Dict[str, Any]
    severity: AlertSeverity
    enabled: bool = True

    @validator("condition")
    def validate_condition(cls, v):
        required_fields = ["metric", "operator", "threshold"]
        if not all(field in v for field in required_fields):
            raise ValueError("Condition must contain metric, operator, and threshold")
        return v


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    severity: Optional[AlertSeverity] = None
    enabled: Optional[bool] = None


class AlertCreate(BaseModel):
    rule_id: int
    title: str
    description: Optional[str] = None
    severity: AlertSeverity
    source: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None


class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None


class AlertResponse(BaseModel):
    id: int
    rule_id: int
    fingerprint: str
    title: str
    description: Optional[str]
    severity: AlertSeverity
    status: AlertStatus
    source: Optional[str]
    labels: Optional[Dict[str, str]]
    annotations: Optional[Dict[str, str]]
    starts_at: datetime
    ends_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationChannelCreate(BaseModel):
    name: str
    type: NotificationChannelType
    configuration: Dict[str, Any]
    enabled: bool = True

    @validator("configuration")
    def validate_configuration(cls, v, values):
        channel_type = values.get("type")
        if channel_type == NotificationChannelType.EMAIL:
            required_fields = [
                "smtp_server",
                "smtp_port",
                "username",
                "password",
                "recipients",
            ]
        elif channel_type == NotificationChannelType.SMS:
            required_fields = ["provider", "api_key", "from_number", "to_numbers"]
        elif channel_type == NotificationChannelType.PUSH:
            required_fields = ["provider", "api_key", "app_id"]
        elif channel_type == NotificationChannelType.WEBHOOK:
            required_fields = ["url", "method"]
        else:
            required_fields = []

        if not all(field in v for field in required_fields):
            raise ValueError(
                f"Configuration for {channel_type} must contain: {required_fields}"
            )
        return v


class EscalationPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rules: List[Dict[str, Any]]
    enabled: bool = True

    @validator("rules")
    def validate_rules(cls, v):
        for rule in v:
            if not all(field in rule for field in ["delay_minutes", "channels"]):
                raise ValueError(
                    "Each escalation rule must contain delay_minutes and channels"
                )
        return v


class AlertCorrelationCreate(BaseModel):
    alert_id: int
    correlation_id: str
    correlation_type: str
    confidence_score: float

    @validator("confidence_score")
    def validate_confidence_score(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Confidence score must be between 0 and 1")
        return v
