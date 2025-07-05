from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    channel_type = Column(String(50), nullable=False)
    subject_template = Column(Text)
    body_template = Column(Text, nullable=False)
    variables = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationHistory(Base):
    __tablename__ = "notification_history"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, nullable=False)
    channel_id = Column(Integer, nullable=False)
    channel_type = Column(String(50), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(Text)
    body = Column(Text)
    status = Column(String(50), default=NotificationStatus.PENDING)
    priority = Column(String(50), default=NotificationPriority.NORMAL)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    error_message = Column(Text)
    response_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationQuota(Base):
    __tablename__ = "notification_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_type = Column(String(50), nullable=False)
    recipient = Column(String(255), nullable=False)
    quota_type = Column(String(50), nullable=False)  # hourly, daily, weekly
    quota_limit = Column(Integer, nullable=False)
    current_count = Column(Integer, default=0)
    reset_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False)
    channel_type = Column(String(50), nullable=False)
    severity_filter = Column(JSON)  # List of severities to receive
    time_restrictions = Column(JSON)  # Quiet hours configuration
    frequency_limit = Column(JSON)  # Rate limiting preferences
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic models for API
class NotificationTemplateCreate(BaseModel):
    name: str
    channel_type: str
    subject_template: Optional[str] = None
    body_template: str
    variables: Optional[Dict[str, Any]] = None


class NotificationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None


class NotificationTemplateResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    subject_template: Optional[str]
    body_template: str
    variables: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationHistoryResponse(BaseModel):
    id: int
    alert_id: int
    channel_id: int
    channel_type: str
    recipient: str
    subject: Optional[str]
    body: str
    status: NotificationStatus
    priority: NotificationPriority
    attempts: int
    max_attempts: int
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]
    error_message: Optional[str]
    response_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationQuotaCreate(BaseModel):
    channel_type: str
    recipient: str
    quota_type: str
    quota_limit: int
    reset_at: datetime


class NotificationQuotaResponse(BaseModel):
    id: int
    channel_type: str
    recipient: str
    quota_type: str
    quota_limit: int
    current_count: int
    reset_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferenceCreate(BaseModel):
    user_id: str
    channel_type: str
    severity_filter: Optional[List[str]] = None
    time_restrictions: Optional[Dict[str, Any]] = None
    frequency_limit: Optional[Dict[str, Any]] = None
    enabled: bool = True


class NotificationPreferenceUpdate(BaseModel):
    severity_filter: Optional[List[str]] = None
    time_restrictions: Optional[Dict[str, Any]] = None
    frequency_limit: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class NotificationPreferenceResponse(BaseModel):
    id: int
    user_id: str
    channel_type: str
    severity_filter: Optional[List[str]]
    time_restrictions: Optional[Dict[str, Any]]
    frequency_limit: Optional[Dict[str, Any]]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationRequest(BaseModel):
    alert_id: int
    channel_ids: List[int]
    priority: NotificationPriority = NotificationPriority.NORMAL
    template_id: Optional[int] = None
    template_variables: Optional[Dict[str, Any]] = None
    schedule_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    notification_id: int
    status: NotificationStatus
    message: str
    estimated_delivery: Optional[datetime] = None
    
    
class BulkNotificationRequest(BaseModel):
    alert_ids: List[int]
    channel_ids: List[int]
    priority: NotificationPriority = NotificationPriority.NORMAL
    template_id: Optional[int] = None
    template_variables: Optional[Dict[str, Any]] = None


class NotificationStatsResponse(BaseModel):
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    average_delivery_time: float
    channel_stats: Dict[str, Dict[str, int]]
    recent_failures: List[Dict[str, Any]]