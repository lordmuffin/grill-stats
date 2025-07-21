import ipaddress
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import redis
import structlog
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, validator

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Alert thresholds
ALERT_THRESHOLD_401 = int(os.getenv("ALERT_THRESHOLD_401", "50"))  # Unauthorized attempts
ALERT_THRESHOLD_403 = int(os.getenv("ALERT_THRESHOLD_403", "25"))  # Forbidden attempts
ALERT_THRESHOLD_429 = int(os.getenv("ALERT_THRESHOLD_429", "100"))  # Rate limit exceeded
ALERT_WINDOW = int(os.getenv("ALERT_WINDOW", "300"))  # 5 minutes

# Logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Redis setup
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Metrics
security_events = Counter("security_events_total", "Total security events", ["type", "severity"])
blocked_requests = Counter("blocked_requests_total", "Total blocked requests", ["reason"])
suspicious_ips = Gauge("suspicious_ips_count", "Number of suspicious IPs being monitored")
active_attacks = Gauge("active_attacks_count", "Number of active attack patterns detected")


# Models
class SecurityEventType(str, Enum):
    AUTHENTICATION_FAILURE = "auth_failure"
    AUTHORIZATION_FAILURE = "authz_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALICIOUS_REQUEST = "malicious_request"
    SQL_INJECTION_ATTEMPT = "sql_injection"
    XSS_ATTEMPT = "xss_attempt"
    BRUTE_FORCE_ATTACK = "brute_force"
    DDoS_ATTEMPT = "ddos_attempt"


class SecuritySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(BaseModel):
    timestamp: datetime
    event_type: SecurityEventType
    severity: SecuritySeverity
    ip_address: str
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    details: Dict[str, Any] = {}


class ThreatIntelligence(BaseModel):
    ip_address: str
    threat_level: str
    country: Optional[str] = None
    organization: Optional[str] = None
    last_seen: datetime
    attack_types: List[str] = []
    confidence_score: float = 0.0


class SecurityAlert(BaseModel):
    id: str
    timestamp: datetime
    alert_type: str
    severity: SecuritySeverity
    message: str
    affected_ips: List[str]
    event_count: int
    time_window: int
    actions_taken: List[str] = []


# FastAPI app
app = FastAPI(
    title="Security Monitoring Service", description="Real-time security monitoring and threat detection", version="1.0.0"
)


class SecurityMonitor:
    def __init__(self):
        self.redis = redis_client
        self.suspicious_patterns = {
            # SQL Injection patterns
            "sql_injection": [
                r"union\s+select",
                r"drop\s+table",
                r"insert\s+into",
                r"delete\s+from",
                r"update\s+.*set",
                r"exec\s*\(",
                r"xp_cmdshell",
                r"sp_executesql",
            ],
            # XSS patterns
            "xss": [r"<script[^>]*>", r"javascript:", r"onerror\s*=", r"onload\s*=", r"onclick\s*=", r"alert\s*\("],
            # Path traversal
            "path_traversal": [r"\.\./", r"\.\.\\", r"%2e%2e%2f", r"%2e%2e\\", r"/etc/passwd", r"/proc/self", r"boot.ini"],
            # Command injection
            "command_injection": [r";\s*cat\s+", r";\s*ls\s+", r";\s*rm\s+", r"&&\s*cat\s+", r"\|\s*cat\s+", r"`cat\s+"],
        }

        self.blocked_ips: Set[str] = set()
        self.load_blocked_ips()

    def load_blocked_ips(self):
        """Load blocked IPs from Redis"""
        try:
            blocked = self.redis.smembers("blocked_ips")
            self.blocked_ips = set(blocked) if blocked else set()
            logger.info("Loaded blocked IPs", count=len(self.blocked_ips))
        except Exception as e:
            logger.error("Failed to load blocked IPs", error=str(e))

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is blocked"""
        return ip_address in self.blocked_ips

    def block_ip(self, ip_address: str, duration: int = 3600, reason: str = "Security violation"):
        """Block an IP address"""
        try:
            # Add to in-memory set
            self.blocked_ips.add(ip_address)

            # Store in Redis with expiration
            self.redis.sadd("blocked_ips", ip_address)
            self.redis.setex(
                f"blocked_ip:{ip_address}",
                duration,
                json.dumps(
                    {
                        "reason": reason,
                        "blocked_at": datetime.utcnow().isoformat(),
                        "expires_at": (datetime.utcnow() + timedelta(seconds=duration)).isoformat(),
                    }
                ),
            )

            blocked_requests.labels(reason=reason).inc()
            logger.warning("IP blocked", ip=ip_address, reason=reason, duration=duration)

        except Exception as e:
            logger.error("Failed to block IP", ip=ip_address, error=str(e))

    def unblock_ip(self, ip_address: str):
        """Unblock an IP address"""
        try:
            self.blocked_ips.discard(ip_address)
            self.redis.srem("blocked_ips", ip_address)
            self.redis.delete(f"blocked_ip:{ip_address}")

            logger.info("IP unblocked", ip=ip_address)

        except Exception as e:
            logger.error("Failed to unblock IP", ip=ip_address, error=str(e))

    def analyze_request(
        self, ip_address: str, method: str, path: str, user_agent: str, headers: Dict[str, str], body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze request for security threats"""
        threats = []
        risk_score = 0.0

        # Check for malicious patterns in path
        path_lower = path.lower()
        for pattern_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                import re

                if re.search(pattern, path_lower, re.IGNORECASE):
                    threats.append({"type": pattern_type, "pattern": pattern, "location": "path"})
                    risk_score += 0.8

        # Check user agent
        if user_agent:
            ua_lower = user_agent.lower()
            suspicious_ua_patterns = ["sqlmap", "nikto", "nmap", "masscan", "zap", "burp", "w3af", "acunetix", "netsparker"]
            for pattern in suspicious_ua_patterns:
                if pattern in ua_lower:
                    threats.append({"type": "malicious_tool", "pattern": pattern, "location": "user_agent"})
                    risk_score += 1.0

        # Check for suspicious headers
        suspicious_headers = ["x-forwarded-for", "x-real-ip", "x-originating-ip"]
        for header in suspicious_headers:
            if header in headers and self._is_suspicious_header_value(headers[header]):
                threats.append({"type": "header_manipulation", "header": header, "location": "headers"})
                risk_score += 0.5

        # Check body for threats (if provided)
        if body:
            body_lower = body.lower()
            for pattern_type, patterns in self.suspicious_patterns.items():
                for pattern in patterns:
                    import re

                    if re.search(pattern, body_lower, re.IGNORECASE):
                        threats.append({"type": pattern_type, "pattern": pattern, "location": "body"})
                        risk_score += 0.9

        return {
            "ip_address": ip_address,
            "risk_score": min(risk_score, 10.0),  # Cap at 10
            "threats": threats,
            "blocked": risk_score >= 5.0,  # Block if risk score is high
        }

    def _is_suspicious_header_value(self, value: str) -> bool:
        """Check if header value is suspicious"""
        try:
            # Check for multiple IPs (potential proxy abuse)
            if "," in value:
                ips = [ip.strip() for ip in value.split(",")]
                if len(ips) > 3:  # More than 3 IPs is suspicious
                    return True

            # Check for private IP ranges in forwarded headers
            try:
                ip = ipaddress.ip_address(value.split(",")[0].strip())
                if ip.is_private:
                    return False  # Private IPs are generally OK
            except ValueError:
                return True  # Invalid IP format is suspicious

            return False
        except Exception:
            return True

    def record_security_event(self, event: SecurityEvent):
        """Record a security event"""
        try:
            # Store event in Redis
            event_key = f"security_event:{int(time.time() * 1000)}"
            event_data = event.dict()
            event_data["timestamp"] = event.timestamp.isoformat()

            self.redis.setex(event_key, 86400, json.dumps(event_data))  # Keep for 24 hours

            # Update metrics
            security_events.labels(type=event.event_type.value, severity=event.severity.value).inc()

            # Track IP-specific events
            ip_events_key = f"ip_events:{event.ip_address}"
            self.redis.lpush(ip_events_key, json.dumps(event_data))
            self.redis.ltrim(ip_events_key, 0, 99)  # Keep last 100 events
            self.redis.expire(ip_events_key, 86400)

            # Check for attack patterns
            self._check_attack_patterns(event)

            logger.info("Security event recorded", event=event.dict())

        except Exception as e:
            logger.error("Failed to record security event", error=str(e))

    def _check_attack_patterns(self, event: SecurityEvent):
        """Check for attack patterns and trigger alerts"""
        try:
            # Check for brute force attacks
            if event.event_type == SecurityEventType.AUTHENTICATION_FAILURE:
                self._check_brute_force(event.ip_address)

            # Check for rate limit abuse
            if event.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED:
                self._check_rate_limit_abuse(event.ip_address)

            # Check for multiple attack types from same IP
            self._check_multi_vector_attack(event.ip_address)

        except Exception as e:
            logger.error("Failed to check attack patterns", error=str(e))

    def _check_brute_force(self, ip_address: str):
        """Check for brute force attack patterns"""
        try:
            # Count auth failures in last 5 minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=5)
            failures = 0

            ip_events_key = f"ip_events:{ip_address}"
            events = self.redis.lrange(ip_events_key, 0, -1)

            for event_data in events:
                event = json.loads(event_data)
                event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if event_time > cutoff_time and event["event_type"] == "auth_failure":
                    failures += 1

            # Block IP if too many failures
            if failures >= 20:  # 20 failures in 5 minutes
                self.block_ip(ip_address, duration=3600, reason="Brute force attack detected")

                # Create alert
                alert = SecurityAlert(
                    id=f"brute_force_{ip_address}_{int(time.time())}",
                    timestamp=datetime.utcnow(),
                    alert_type="brute_force_attack",
                    severity=SecuritySeverity.HIGH,
                    message=f"Brute force attack detected from {ip_address}",
                    affected_ips=[ip_address],
                    event_count=failures,
                    time_window=300,
                    actions_taken=["ip_blocked"],
                )
                self._create_alert(alert)

        except Exception as e:
            logger.error("Failed to check brute force pattern", error=str(e))

    def _check_rate_limit_abuse(self, ip_address: str):
        """Check for rate limit abuse patterns"""
        try:
            # Count rate limit violations in last 10 minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=10)
            violations = 0

            ip_events_key = f"ip_events:{ip_address}"
            events = self.redis.lrange(ip_events_key, 0, -1)

            for event_data in events:
                event = json.loads(event_data)
                event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if event_time > cutoff_time and event["event_type"] == "rate_limit_exceeded":
                    violations += 1

            # Block IP if excessive violations
            if violations >= 50:  # 50 violations in 10 minutes
                self.block_ip(ip_address, duration=7200, reason="Rate limit abuse detected")

                alert = SecurityAlert(
                    id=f"rate_abuse_{ip_address}_{int(time.time())}",
                    timestamp=datetime.utcnow(),
                    alert_type="rate_limit_abuse",
                    severity=SecuritySeverity.MEDIUM,
                    message=f"Rate limit abuse detected from {ip_address}",
                    affected_ips=[ip_address],
                    event_count=violations,
                    time_window=600,
                    actions_taken=["ip_blocked"],
                )
                self._create_alert(alert)

        except Exception as e:
            logger.error("Failed to check rate limit abuse", error=str(e))

    def _check_multi_vector_attack(self, ip_address: str):
        """Check for multi-vector attack patterns"""
        try:
            # Check for different attack types from same IP in last hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            attack_types = set()

            ip_events_key = f"ip_events:{ip_address}"
            events = self.redis.lrange(ip_events_key, 0, -1)

            for event_data in events:
                event = json.loads(event_data)
                event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if event_time > cutoff_time:
                    if event["event_type"] in ["sql_injection", "xss_attempt", "malicious_request"]:
                        attack_types.add(event["event_type"])

            # Alert if multiple attack vectors detected
            if len(attack_types) >= 3:
                self.block_ip(ip_address, duration=14400, reason="Multi-vector attack detected")

                alert = SecurityAlert(
                    id=f"multi_vector_{ip_address}_{int(time.time())}",
                    timestamp=datetime.utcnow(),
                    alert_type="multi_vector_attack",
                    severity=SecuritySeverity.CRITICAL,
                    message=f"Multi-vector attack detected from {ip_address}",
                    affected_ips=[ip_address],
                    event_count=len(attack_types),
                    time_window=3600,
                    actions_taken=["ip_blocked"],
                )
                self._create_alert(alert)

        except Exception as e:
            logger.error("Failed to check multi-vector attack", error=str(e))

    def _create_alert(self, alert: SecurityAlert):
        """Create and store security alert"""
        try:
            alert_key = f"security_alert:{alert.id}"
            alert_data = alert.dict()
            alert_data["timestamp"] = alert.timestamp.isoformat()

            self.redis.setex(alert_key, 86400 * 7, json.dumps(alert_data))  # Keep for 7 days

            # Add to alerts list
            self.redis.lpush("security_alerts", alert.id)
            self.redis.ltrim("security_alerts", 0, 999)  # Keep last 1000 alerts

            active_attacks.inc()

            logger.warning("Security alert created", alert=alert.dict())

        except Exception as e:
            logger.error("Failed to create alert", error=str(e))

    def get_security_dashboard(self) -> Dict[str, Any]:
        """Get security dashboard data"""
        try:
            dashboard = {
                "timestamp": datetime.utcnow().isoformat(),
                "blocked_ips_count": len(self.blocked_ips),
                "recent_alerts": [],
                "threat_summary": {},
                "top_attacking_ips": [],
                "attack_trends": {},
            }

            # Get recent alerts
            alert_ids = self.redis.lrange("security_alerts", 0, 9)  # Last 10 alerts
            for alert_id in alert_ids:
                alert_key = f"security_alert:{alert_id}"
                alert_data = self.redis.get(alert_key)
                if alert_data:
                    dashboard["recent_alerts"].append(json.loads(alert_data))

            # Get threat summary (last 24 hours)
            threat_counts = defaultdict(int)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            # This would typically query a time-series database in production
            # For now, we'll provide a basic summary
            dashboard["threat_summary"] = {"total_events": 0, "blocked_requests": 0, "unique_attackers": 0, "attack_types": {}}

            return dashboard

        except Exception as e:
            logger.error("Failed to get security dashboard", error=str(e))
            return {"error": "Failed to retrieve dashboard data"}


# Global security monitor instance
security_monitor = SecurityMonitor()


# Routes
@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/events")
async def record_event(event: SecurityEvent, background_tasks: BackgroundTasks):
    """Record a security event"""
    try:
        background_tasks.add_task(security_monitor.record_security_event, event)
        return {"message": "Event recorded successfully"}
    except Exception as e:
        logger.error("Failed to record event", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/analyze")
async def analyze_request(
    ip_address: str, method: str, path: str, user_agent: str = "", headers: Dict[str, str] = {}, body: Optional[str] = None
):
    """Analyze a request for security threats"""
    try:
        # Check if IP is blocked
        if security_monitor.is_ip_blocked(ip_address):
            return {"blocked": True, "reason": "IP address is blocked", "risk_score": 10.0}

        # Analyze the request
        analysis = security_monitor.analyze_request(ip_address, method, path, user_agent, headers, body)

        # If high risk, record security event
        if analysis["risk_score"] >= 5.0:
            event = SecurityEvent(
                timestamp=datetime.utcnow(),
                event_type=SecurityEventType.MALICIOUS_REQUEST,
                severity=SecuritySeverity.HIGH,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=path,
                details={"threats": analysis["threats"], "risk_score": analysis["risk_score"]},
            )
            security_monitor.record_security_event(event)

        return analysis

    except Exception as e:
        logger.error("Failed to analyze request", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/blocked-ips")
async def get_blocked_ips():
    """Get list of blocked IP addresses"""
    try:
        blocked_ips_info = []
        for ip in security_monitor.blocked_ips:
            ip_info_key = f"blocked_ip:{ip}"
            ip_data = redis_client.get(ip_info_key)
            if ip_data:
                ip_info = json.loads(ip_data)
                ip_info["ip_address"] = ip
                blocked_ips_info.append(ip_info)

        return {"blocked_ips": blocked_ips_info}
    except Exception as e:
        logger.error("Failed to get blocked IPs", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/block-ip")
async def block_ip(ip_address: str, duration: int = 3600, reason: str = "Manual block"):
    """Manually block an IP address"""
    try:
        security_monitor.block_ip(ip_address, duration, reason)
        return {"message": f"IP {ip_address} blocked successfully"}
    except Exception as e:
        logger.error("Failed to block IP", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/block-ip/{ip_address}")
async def unblock_ip(ip_address: str):
    """Unblock an IP address"""
    try:
        security_monitor.unblock_ip(ip_address)
        return {"message": f"IP {ip_address} unblocked successfully"}
    except Exception as e:
        logger.error("Failed to unblock IP", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/dashboard")
async def get_dashboard():
    """Get security monitoring dashboard"""
    try:
        dashboard = security_monitor.get_security_dashboard()
        return dashboard
    except Exception as e:
        logger.error("Failed to get dashboard", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/alerts")
async def get_alerts(limit: int = 50):
    """Get recent security alerts"""
    try:
        alert_ids = redis_client.lrange("security_alerts", 0, limit - 1)
        alerts = []

        for alert_id in alert_ids:
            alert_key = f"security_alert:{alert_id}"
            alert_data = redis_client.get(alert_key)
            if alert_data:
                alerts.append(json.loads(alert_data))

        return {"alerts": alerts}
    except Exception as e:
        logger.error("Failed to get alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
