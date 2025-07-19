"""
Enhanced audit logging for the encryption service.

This module provides comprehensive audit logging capabilities including:
- Structured logging with JSON format
- Multiple output destinations (file, syslog, remote)
- Log rotation and retention
- Security event categorization
- Compliance reporting
"""

import json
import logging
import logging.handlers
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(Enum):
    """Audit event types for categorization"""

    CREDENTIAL_ENCRYPT = "credential_encrypt"
    CREDENTIAL_DECRYPT = "credential_decrypt"
    CREDENTIAL_ACCESS = "credential_access"
    KEY_ROTATION = "key_rotation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AuditSeverity(Enum):
    """Audit severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event"""

    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    outcome: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource": self.resource,
            "outcome": self.outcome,
            "details": self.details,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Enhanced audit logger with multiple output destinations"""

    def __init__(
        self,
        log_file: str = None,
        log_level: str = "INFO",
        enable_syslog: bool = False,
        enable_remote: bool = False,
        remote_endpoint: str = None,
        max_file_size: int = 10485760,  # 10MB
        backup_count: int = 5,
    ):
        """Initialize the audit logger

        Args:
            log_file: Path to log file (defaults to /var/log/grill-stats/audit.log)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_syslog: Enable syslog output
            enable_remote: Enable remote logging
            remote_endpoint: Remote logging endpoint URL
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files to keep
        """
        self.log_file = log_file or os.getenv(
            "AUDIT_LOG_FILE", "/var/log/grill-stats/audit.log"
        )
        self.log_level = getattr(logging, log_level.upper())
        self.enable_syslog = enable_syslog
        self.enable_remote = enable_remote
        self.remote_endpoint = remote_endpoint
        self.max_file_size = max_file_size
        self.backup_count = backup_count

        # Thread-safe event buffer for remote logging
        self._event_buffer = []
        self._buffer_lock = threading.Lock()
        self._buffer_max_size = 100
        self._flush_interval = 60  # seconds

        # Initialize loggers
        self._setup_loggers()

        # Start background tasks
        self._start_background_tasks()

    def _setup_loggers(self):
        """Setup logging handlers"""
        # Create main audit logger
        self.logger = logging.getLogger("grill_stats_audit")
        self.logger.setLevel(self.log_level)

        # Clear existing handlers
        self.logger.handlers = []

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # File handler with rotation
        try:
            # Create log directory if it doesn't exist
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                self.log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to setup file logging: {e}")

        # Syslog handler
        if self.enable_syslog:
            try:
                syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
                syslog_handler.setFormatter(formatter)
                self.logger.addHandler(syslog_handler)
            except Exception as e:
                print(f"Failed to setup syslog: {e}")

        # Console handler for development
        if os.getenv("AUDIT_LOG_CONSOLE", "false").lower() == "true":
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def _start_background_tasks(self):
        """Start background tasks for remote logging"""
        if self.enable_remote and self.remote_endpoint:
            # Start buffer flush thread
            flush_thread = threading.Thread(
                target=self._flush_buffer_periodically, daemon=True
            )
            flush_thread.start()

    def _flush_buffer_periodically(self):
        """Periodically flush the event buffer to remote endpoint"""
        while True:
            time.sleep(self._flush_interval)
            self._flush_buffer()

    def _flush_buffer(self):
        """Flush event buffer to remote endpoint"""
        if not self.enable_remote or not self.remote_endpoint:
            return

        with self._buffer_lock:
            if not self._event_buffer:
                return

            events_to_send = self._event_buffer.copy()
            self._event_buffer.clear()

        try:
            import requests

            response = requests.post(
                self.remote_endpoint,
                json={"events": events_to_send},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()

        except Exception as e:
            self.logger.error(f"Failed to send audit events to remote endpoint: {e}")
            # Put events back in buffer
            with self._buffer_lock:
                self._event_buffer.extend(events_to_send)

    def log_event(self, event: AuditEvent):
        """Log an audit event

        Args:
            event: AuditEvent to log
        """
        # Log to file/syslog
        log_message = event.to_json()

        if event.severity == AuditSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif event.severity == AuditSeverity.HIGH:
            self.logger.error(log_message)
        elif event.severity == AuditSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

        # Add to remote buffer if enabled
        if self.enable_remote:
            with self._buffer_lock:
                self._event_buffer.append(event.to_dict())

                # Flush if buffer is full
                if len(self._event_buffer) >= self._buffer_max_size:
                    self._flush_buffer()

    def log_credential_encrypt(
        self,
        user_id: str,
        success: bool,
        duration_ms: int = None,
        ip_address: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log credential encryption event"""
        event = AuditEvent(
            event_type=AuditEventType.CREDENTIAL_ENCRYPT,
            severity=AuditSeverity.MEDIUM,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            action="encrypt_credentials",
            resource="thermoworks_credentials",
            outcome="success" if success else "failure",
            details=details,
            duration_ms=duration_ms,
        )
        self.log_event(event)

    def log_credential_decrypt(
        self,
        user_id: str,
        success: bool,
        duration_ms: int = None,
        ip_address: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log credential decryption event"""
        event = AuditEvent(
            event_type=AuditEventType.CREDENTIAL_DECRYPT,
            severity=AuditSeverity.HIGH,  # Decryption is more sensitive
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            action="decrypt_credentials",
            resource="thermoworks_credentials",
            outcome="success" if success else "failure",
            details=details,
            duration_ms=duration_ms,
        )
        self.log_event(event)

    def log_authentication(
        self,
        user_id: str,
        success: bool,
        ip_address: str = None,
        user_agent: str = None,
        error_message: str = None,
    ):
        """Log authentication event"""
        event = AuditEvent(
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.MEDIUM,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action="authenticate",
            outcome="success" if success else "failure",
            error_message=error_message,
        )
        self.log_event(event)

    def log_rate_limit_exceeded(
        self, user_id: str, ip_address: str = None, details: Dict[str, Any] = None
    ):
        """Log rate limit exceeded event"""
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=AuditSeverity.HIGH,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            action="rate_limit_exceeded",
            outcome="blocked",
            details=details,
        )
        self.log_event(event)

    def log_security_violation(
        self,
        user_id: str,
        violation_type: str,
        ip_address: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log security violation event"""
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            action=violation_type,
            outcome="blocked",
            details=details,
        )
        self.log_event(event)

    def log_key_rotation(
        self,
        success: bool,
        key_name: str,
        new_version: int = None,
        details: Dict[str, Any] = None,
    ):
        """Log key rotation event"""
        event = AuditEvent(
            event_type=AuditEventType.KEY_ROTATION,
            severity=AuditSeverity.HIGH,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="rotate_key",
            resource=key_name,
            outcome="success" if success else "failure",
            details=details,
        )
        self.log_event(event)

    def log_service_start(
        self, service_name: str, version: str = None, details: Dict[str, Any] = None
    ):
        """Log service start event"""
        event = AuditEvent(
            event_type=AuditEventType.SERVICE_START,
            severity=AuditSeverity.LOW,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="service_start",
            resource=service_name,
            outcome="success",
            details=details,
        )
        self.log_event(event)

    def log_service_stop(self, service_name: str, details: Dict[str, Any] = None):
        """Log service stop event"""
        event = AuditEvent(
            event_type=AuditEventType.SERVICE_STOP,
            severity=AuditSeverity.LOW,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="service_stop",
            resource=service_name,
            outcome="success",
            details=details,
        )
        self.log_event(event)

    def log_error(
        self,
        error_message: str,
        user_id: str = None,
        ip_address: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log error event"""
        event = AuditEvent(
            event_type=AuditEventType.ERROR,
            severity=AuditSeverity.HIGH,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            ip_address=ip_address,
            action="error",
            outcome="failure",
            error_message=error_message,
            details=details,
        )
        self.log_event(event)

    def get_audit_statistics(
        self, start_time: datetime = None, end_time: datetime = None
    ) -> Dict[str, Any]:
        """Get audit statistics for a time period

        Args:
            start_time: Start time for statistics
            end_time: End time for statistics

        Returns:
            Dictionary with audit statistics
        """
        # This would typically query a database or parse log files
        # For now, return basic statistics
        return {
            "total_events": 0,
            "events_by_type": {},
            "events_by_severity": {},
            "events_by_outcome": {},
            "top_users": [],
            "top_ip_addresses": [],
            "time_range": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None,
            },
        }

    def export_audit_log(
        self,
        output_format: str = "json",
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> str:
        """Export audit log in specified format

        Args:
            output_format: Export format (json, csv, xml)
            start_time: Start time for export
            end_time: End time for export

        Returns:
            Exported audit log as string
        """
        # This would typically read from log files or database
        # For now, return placeholder
        return json.dumps(
            {
                "export_format": output_format,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "events": [],
            }
        )


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(
            enable_syslog=os.getenv("AUDIT_ENABLE_SYSLOG", "false").lower() == "true",
            enable_remote=os.getenv("AUDIT_ENABLE_REMOTE", "false").lower() == "true",
            remote_endpoint=os.getenv("AUDIT_REMOTE_ENDPOINT"),
            log_level=os.getenv("AUDIT_LOG_LEVEL", "INFO"),
        )
    return _audit_logger


def log_credential_encrypt(
    user_id: str,
    success: bool,
    duration_ms: int = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
):
    """Convenience function for logging credential encryption"""
    get_audit_logger().log_credential_encrypt(
        user_id, success, duration_ms, ip_address, details
    )


def log_credential_decrypt(
    user_id: str,
    success: bool,
    duration_ms: int = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
):
    """Convenience function for logging credential decryption"""
    get_audit_logger().log_credential_decrypt(
        user_id, success, duration_ms, ip_address, details
    )


def log_authentication(
    user_id: str,
    success: bool,
    ip_address: str = None,
    user_agent: str = None,
    error_message: str = None,
):
    """Convenience function for logging authentication"""
    get_audit_logger().log_authentication(
        user_id, success, ip_address, user_agent, error_message
    )


def log_rate_limit_exceeded(
    user_id: str, ip_address: str = None, details: Dict[str, Any] = None
):
    """Convenience function for logging rate limit exceeded"""
    get_audit_logger().log_rate_limit_exceeded(user_id, ip_address, details)


def log_security_violation(
    user_id: str,
    violation_type: str,
    ip_address: str = None,
    details: Dict[str, Any] = None,
):
    """Convenience function for logging security violations"""
    get_audit_logger().log_security_violation(
        user_id, violation_type, ip_address, details
    )


def log_key_rotation(
    success: bool,
    key_name: str,
    new_version: int = None,
    details: Dict[str, Any] = None,
):
    """Convenience function for logging key rotation"""
    get_audit_logger().log_key_rotation(success, key_name, new_version, details)


def log_service_start(
    service_name: str, version: str = None, details: Dict[str, Any] = None
):
    """Convenience function for logging service start"""
    get_audit_logger().log_service_start(service_name, version, details)


def log_service_stop(service_name: str, details: Dict[str, Any] = None):
    """Convenience function for logging service stop"""
    get_audit_logger().log_service_stop(service_name, details)


def log_error(
    error_message: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
):
    """Convenience function for logging errors"""
    get_audit_logger().log_error(error_message, user_id, ip_address, details)
