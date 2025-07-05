from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertMetrics(Base):
    __tablename__ = "alert_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(255), nullable=False)
    metric_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    labels = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertTrend(Base):
    __tablename__ = "alert_trends"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(255), nullable=False)
    time_bucket = Column(DateTime, nullable=False)
    bucket_size = Column(String(50), nullable=False)  # hour, day, week, month
    value = Column(Float, nullable=False)
    count = Column(Integer, nullable=False)
    min_value = Column(Float)
    max_value = Column(Float)
    avg_value = Column(Float)
    labels = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertAnalytics(Base):
    __tablename__ = "alert_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_type = Column(String(100), nullable=False)
    analysis_data = Column(JSON, nullable=False)
    time_range_start = Column(DateTime, nullable=False)
    time_range_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertNoiseScore(Base):
    __tablename__ = "alert_noise_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, nullable=False)
    noise_score = Column(Float, nullable=False)
    signal_score = Column(Float, nullable=False)
    correlation_score = Column(Float, nullable=False)
    false_positive_rate = Column(Float, nullable=False)
    calculation_date = Column(DateTime, nullable=False)
    factors = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertPatternAnalysis(Base):
    __tablename__ = "alert_pattern_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    pattern_type = Column(String(100), nullable=False)
    pattern_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False)
    affected_rules = Column(JSON)
    recommendations = Column(JSON)
    analysis_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic models for API
class AlertMetricsCreate(BaseModel):
    metric_name: str
    metric_type: MetricType
    value: float
    labels: Optional[Dict[str, str]] = None
    timestamp: Optional[datetime] = None


class AlertMetricsResponse(BaseModel):
    id: int
    metric_name: str
    metric_type: MetricType
    value: float
    labels: Optional[Dict[str, str]]
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AlertTrendResponse(BaseModel):
    id: int
    metric_name: str
    time_bucket: datetime
    bucket_size: str
    value: float
    count: int
    min_value: Optional[float]
    max_value: Optional[float]
    avg_value: Optional[float]
    labels: Optional[Dict[str, str]]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertAnalyticsResponse(BaseModel):
    id: int
    analysis_type: str
    analysis_data: Dict[str, Any]
    time_range_start: datetime
    time_range_end: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AlertNoiseScoreResponse(BaseModel):
    id: int
    alert_rule_id: int
    noise_score: float
    signal_score: float
    correlation_score: float
    false_positive_rate: float
    calculation_date: datetime
    factors: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertPatternAnalysisResponse(BaseModel):
    id: int
    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence_score: float
    affected_rules: Optional[List[int]]
    recommendations: Optional[List[Dict[str, Any]]]
    analysis_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AlertDashboardData(BaseModel):
    total_alerts: int
    active_alerts: int
    critical_alerts: int
    alert_rate_24h: float
    alert_resolution_time: float
    top_alert_rules: List[Dict[str, Any]]
    alert_trends: List[AlertTrendResponse]
    noise_to_signal_ratio: float
    notification_stats: Dict[str, Any]
    escalation_stats: Dict[str, Any]


class AlertOptimizationSuggestions(BaseModel):
    noisy_rules: List[Dict[str, Any]]
    underutilized_rules: List[Dict[str, Any]]
    correlation_opportunities: List[Dict[str, Any]]
    threshold_adjustments: List[Dict[str, Any]]
    consolidation_suggestions: List[Dict[str, Any]]


class AlertPerformanceMetrics(BaseModel):
    detection_latency: float
    notification_latency: float
    resolution_time: float
    false_positive_rate: float
    notification_delivery_rate: float
    escalation_rate: float
    correlation_accuracy: float


class AlertVolumeAnalysis(BaseModel):
    hourly_volume: List[Dict[str, Any]]
    daily_volume: List[Dict[str, Any]]
    weekly_volume: List[Dict[str, Any]]
    volume_predictions: List[Dict[str, Any]]
    peak_times: List[Dict[str, Any]]
    volume_trends: Dict[str, Any]