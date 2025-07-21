import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class ConnectionMetrics:
    total_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    average_response_time: float = 0.0
    last_connection_time: datetime = field(default_factory=datetime.utcnow)
    uptime_percentage: float = 100.0


@dataclass
class APIMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    calls_by_endpoint: Dict[str, int] = field(default_factory=dict)
    average_response_time: float = 0.0
    last_call_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ServiceMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    calls_by_service: Dict[str, int] = field(default_factory=dict)
    last_call_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EventMetrics:
    total_events_sent: int = 0
    successful_events: int = 0
    failed_events: int = 0
    events_by_type: Dict[str, int] = field(default_factory=dict)
    last_event_time: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        
        # Core metrics
        self.connection_metrics = ConnectionMetrics()
        self.api_metrics = APIMetrics()
        self.service_metrics = ServiceMetrics()
        self.event_metrics = EventMetrics()
        
        # Response time tracking
        self.response_times = deque(maxlen=window_size)
        self.connection_times = deque(maxlen=window_size)
        
        # Error tracking
        self.error_counts = defaultdict(int)
        self.error_history = deque(maxlen=window_size)
        
        # Performance tracking
        self.start_time = datetime.utcnow()
        self.request_rates = deque(maxlen=window_size)
        
    def record_connection_success(self, response_time_ms: float):
        try:
            self.connection_metrics.total_attempts += 1
            self.connection_metrics.successful_connections += 1
            self.connection_metrics.last_connection_time = datetime.utcnow()
            
            # Track response times
            self.connection_times.append(response_time_ms)
            self.connection_metrics.average_response_time = sum(self.connection_times) / len(self.connection_times)
            
            # Update uptime percentage
            self._update_uptime_percentage()
            
            logger.debug(f"Connection success recorded: {response_time_ms:.2f}ms")
            
        except Exception as e:
            logger.error(f"Failed to record connection success: {e}")

    def record_connection_failure(self):
        try:
            self.connection_metrics.total_attempts += 1
            self.connection_metrics.failed_connections += 1
            
            # Update uptime percentage
            self._update_uptime_percentage()
            
            # Track error
            self.error_counts["connection_failure"] += 1
            self.error_history.append({
                "type": "connection_failure",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.debug("Connection failure recorded")
            
        except Exception as e:
            logger.error(f"Failed to record connection failure: {e}")

    def record_api_call(self, endpoint: str, success: bool, response_time_ms: float = 0):
        try:
            self.api_metrics.total_calls += 1
            self.api_metrics.last_call_time = datetime.utcnow()
            
            if success:
                self.api_metrics.successful_calls += 1
            else:
                self.api_metrics.failed_calls += 1
                self.error_counts[f"api_failure_{endpoint}"] += 1
                self.error_history.append({
                    "type": "api_failure",
                    "endpoint": endpoint,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Track by endpoint
            if endpoint not in self.api_metrics.calls_by_endpoint:
                self.api_metrics.calls_by_endpoint[endpoint] = 0
            self.api_metrics.calls_by_endpoint[endpoint] += 1
            
            # Track response times
            if response_time_ms > 0:
                self.response_times.append(response_time_ms)
                self.api_metrics.average_response_time = sum(self.response_times) / len(self.response_times)
            
            logger.debug(f"API call recorded: {endpoint} (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to record API call: {e}")

    def record_service_call(self, service: str, success: bool):
        try:
            self.service_metrics.total_calls += 1
            self.service_metrics.last_call_time = datetime.utcnow()
            
            if success:
                self.service_metrics.successful_calls += 1
            else:
                self.service_metrics.failed_calls += 1
                self.error_counts[f"service_failure_{service}"] += 1
                self.error_history.append({
                    "type": "service_failure",
                    "service": service,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Track by service
            if service not in self.service_metrics.calls_by_service:
                self.service_metrics.calls_by_service[service] = 0
            self.service_metrics.calls_by_service[service] += 1
            
            logger.debug(f"Service call recorded: {service} (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to record service call: {e}")

    def record_event_sent(self, event_type: str, success: bool):
        try:
            self.event_metrics.total_events_sent += 1
            self.event_metrics.last_event_time = datetime.utcnow()
            
            if success:
                self.event_metrics.successful_events += 1
            else:
                self.event_metrics.failed_events += 1
                self.error_counts[f"event_failure_{event_type}"] += 1
                self.error_history.append({
                    "type": "event_failure",
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Track by event type
            if event_type not in self.event_metrics.events_by_type:
                self.event_metrics.events_by_type[event_type] = 0
            self.event_metrics.events_by_type[event_type] += 1
            
            logger.debug(f"Event recorded: {event_type} (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to record event: {e}")

    def _update_uptime_percentage(self):
        try:
            if self.connection_metrics.total_attempts > 0:
                self.connection_metrics.uptime_percentage = (
                    self.connection_metrics.successful_connections / 
                    self.connection_metrics.total_attempts * 100
                )
        except Exception as e:
            logger.error(f"Failed to update uptime percentage: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        try:
            now = datetime.utcnow()
            uptime_duration = now - self.start_time
            
            # Calculate request rate (requests per minute)
            total_requests = (
                self.api_metrics.total_calls +
                self.service_metrics.total_calls +
                self.event_metrics.total_events_sent
            )
            
            request_rate = 0
            if uptime_duration.total_seconds() > 0:
                request_rate = total_requests / (uptime_duration.total_seconds() / 60)
            
            return {
                "uptime": {
                    "start_time": self.start_time.isoformat(),
                    "current_time": now.isoformat(),
                    "uptime_seconds": uptime_duration.total_seconds(),
                    "uptime_formatted": str(uptime_duration)
                },
                "connection": {
                    "total_attempts": self.connection_metrics.total_attempts,
                    "successful_connections": self.connection_metrics.successful_connections,
                    "failed_connections": self.connection_metrics.failed_connections,
                    "success_rate": (
                        self.connection_metrics.successful_connections / 
                        max(self.connection_metrics.total_attempts, 1) * 100
                    ),
                    "average_response_time_ms": self.connection_metrics.average_response_time,
                    "uptime_percentage": self.connection_metrics.uptime_percentage,
                    "last_connection": self.connection_metrics.last_connection_time.isoformat()
                },
                "api": {
                    "total_calls": self.api_metrics.total_calls,
                    "successful_calls": self.api_metrics.successful_calls,
                    "failed_calls": self.api_metrics.failed_calls,
                    "success_rate": (
                        self.api_metrics.successful_calls / 
                        max(self.api_metrics.total_calls, 1) * 100
                    ),
                    "average_response_time_ms": self.api_metrics.average_response_time,
                    "calls_by_endpoint": dict(self.api_metrics.calls_by_endpoint),
                    "last_call": self.api_metrics.last_call_time.isoformat()
                },
                "services": {
                    "total_calls": self.service_metrics.total_calls,
                    "successful_calls": self.service_metrics.successful_calls,
                    "failed_calls": self.service_metrics.failed_calls,
                    "success_rate": (
                        self.service_metrics.successful_calls / 
                        max(self.service_metrics.total_calls, 1) * 100
                    ),
                    "calls_by_service": dict(self.service_metrics.calls_by_service),
                    "last_call": self.service_metrics.last_call_time.isoformat()
                },
                "events": {
                    "total_events_sent": self.event_metrics.total_events_sent,
                    "successful_events": self.event_metrics.successful_events,
                    "failed_events": self.event_metrics.failed_events,
                    "success_rate": (
                        self.event_metrics.successful_events / 
                        max(self.event_metrics.total_events_sent, 1) * 100
                    ),
                    "events_by_type": dict(self.event_metrics.events_by_type),
                    "last_event": self.event_metrics.last_event_time.isoformat()
                },
                "performance": {
                    "request_rate_per_minute": request_rate,
                    "total_requests": total_requests,
                    "error_rate": self._calculate_error_rate(),
                    "recent_errors": list(self.error_history)[-10:],  # Last 10 errors
                },
                "errors": dict(self.error_counts)
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {"error": str(e)}

    def _calculate_error_rate(self) -> float:
        try:
            total_operations = (
                self.connection_metrics.total_attempts +
                self.api_metrics.total_calls +
                self.service_metrics.total_calls +
                self.event_metrics.total_events_sent
            )
            
            total_errors = (
                self.connection_metrics.failed_connections +
                self.api_metrics.failed_calls +
                self.service_metrics.failed_calls +
                self.event_metrics.failed_events
            )
            
            if total_operations > 0:
                return (total_errors / total_operations) * 100
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate error rate: {e}")
            return 0.0

    def reset_metrics(self):
        try:
            self.connection_metrics = ConnectionMetrics()
            self.api_metrics = APIMetrics()
            self.service_metrics = ServiceMetrics()
            self.event_metrics = EventMetrics()
            
            self.response_times.clear()
            self.connection_times.clear()
            self.error_counts.clear()
            self.error_history.clear()
            
            self.start_time = datetime.utcnow()
            
            logger.info("Metrics reset successfully")
            
        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        try:
            metrics = self.get_metrics()
            
            # Determine health status based on key metrics
            connection_health = "healthy" if metrics["connection"]["success_rate"] > 95 else "degraded"
            api_health = "healthy" if metrics["api"]["success_rate"] > 95 else "degraded"
            error_health = "healthy" if metrics["performance"]["error_rate"] < 5 else "degraded"
            
            overall_health = "healthy"
            if any(health == "degraded" for health in [connection_health, api_health, error_health]):
                overall_health = "degraded"
            
            return {
                "overall_health": overall_health,
                "connection_health": connection_health,
                "api_health": api_health,
                "error_health": error_health,
                "uptime_seconds": metrics["uptime"]["uptime_seconds"],
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {e}")
            return {"overall_health": "unknown", "error": str(e)}