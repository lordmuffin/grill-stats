"""
Security Middleware for Flask Application
Provides comprehensive security measures including input validation, security headers, and threat protection
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest, Forbidden

from .rate_limiter import get_rate_limit_key, rate_limiter

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration with reasonable defaults"""

    # Content Security Policy
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: ws:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "media-src 'self'; "
        "frame-src 'none';"
    )

    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()",
        "Content-Security-Policy": CSP_POLICY,
    }

    # Input validation
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    MAX_JSON_DEPTH = 10
    MAX_FORM_FIELDS = 100

    # Rate limiting
    ENABLE_RATE_LIMITING = True
    RATE_LIMIT_STORAGE_URL = "redis://localhost:6379/2"

    # IP blocking
    BLOCKED_IPS: Set[str] = set()
    BLOCKED_USER_AGENTS: Set[str] = {"sqlmap", "nikto", "nmap", "masscan", "nuclei", "gobuster", "dirb", "dirbuster", "wfuzz"}

    # Suspicious patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(\b(script|javascript|vbscript|onload|onerror|onclick)\b)",
        r"(<script[^>]*>.*?</script>)",
        r"(\b(eval|expression|javascript:)\b)",
        r"((\%27)|(\')|(\")|(\%22)).*(\b(or|and)\b).*(\=)",
        r"(\b(concat|char|ascii|substring|length|mid|user|database|version)\b\s*\()",
    ]

    # File upload security
    ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "csv", "json"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class InputValidator:
    """Input validation and sanitization"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.SQL_INJECTION_PATTERNS]

    def validate_json(self, data: Any, depth: int = 0) -> bool:
        """Validate JSON data structure and depth"""
        if depth > self.config.MAX_JSON_DEPTH:
            raise BadRequest("JSON structure too deep")

        if isinstance(data, dict):
            if len(data) > self.config.MAX_FORM_FIELDS:
                raise BadRequest("Too many form fields")

            for key, value in data.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise BadRequest("Invalid key format")

                if not self.validate_json(value, depth + 1):
                    return False

        elif isinstance(data, list):
            if len(data) > 1000:  # Prevent large array attacks
                raise BadRequest("Array too large")

            for item in data:
                if not self.validate_json(item, depth + 1):
                    return False

        elif isinstance(data, str):
            if len(data) > 10000:  # 10KB string limit
                raise BadRequest("String value too large")

            if self.contains_malicious_patterns(data):
                raise BadRequest("Potentially malicious input detected")

        return True

    def contains_malicious_patterns(self, text: str) -> bool:
        """Check for malicious patterns in text"""
        if not isinstance(text, str):
            return False

        # Check for SQL injection patterns
        for pattern in self.sql_patterns:
            if pattern.search(text):
                logger.warning(f"Potential SQL injection attempt: {text[:100]}")
                return True

        # Check for XSS patterns
        xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"eval\s*\(",
            r"expression\s*\(",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential XSS attempt: {text[:100]}")
                return True

        return False

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize uploaded filename"""
        if not filename:
            return "unnamed_file"

        # Remove path traversal attempts
        filename = filename.replace("..", "").replace("/", "").replace("\\", "")

        # Remove special characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:250] + ("." + ext if ext else "")

        return filename

    def validate_file_upload(self, file) -> bool:
        """Validate file upload"""
        if not file.filename:
            return False

        # Check extension
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        if ext not in self.config.ALLOWED_EXTENSIONS:
            raise BadRequest(f"File type '{ext}' not allowed")

        # Check file size (basic check, more thorough check in upload handler)
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset position

        if size > self.config.MAX_FILE_SIZE:
            raise BadRequest("File too large")

        return True


class ThreatDetector:
    """Detect and handle security threats"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.suspicious_ips: Dict[str, Dict[str, Any]] = {}

    def is_blocked_ip(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.config.BLOCKED_IPS

    def is_blocked_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is blocked"""
        if not user_agent:
            return False

        user_agent_lower = user_agent.lower()
        return any(blocked in user_agent_lower for blocked in self.config.BLOCKED_USER_AGENTS)

    def track_suspicious_activity(self, ip: str, activity_type: str) -> bool:
        """Track suspicious activity and determine if IP should be blocked"""
        now = time.time()

        if ip not in self.suspicious_ips:
            self.suspicious_ips[ip] = {"activities": [], "first_seen": now, "score": 0}

        ip_data = self.suspicious_ips[ip]

        # Clean old activities (older than 1 hour)
        ip_data["activities"] = [activity for activity in ip_data["activities"] if now - activity["timestamp"] < 3600]

        # Add new activity
        ip_data["activities"].append({"type": activity_type, "timestamp": now})

        # Calculate threat score
        score = self._calculate_threat_score(ip_data["activities"])
        ip_data["score"] = score

        # Block if score is too high
        if score >= 100:
            self.config.BLOCKED_IPS.add(ip)
            logger.warning(f"IP {ip} blocked due to high threat score: {score}")
            return True

        return False

    def _calculate_threat_score(self, activities: List[Dict[str, Any]]) -> int:
        """Calculate threat score based on activities"""
        score = 0

        # Count activities by type
        activity_counts = {}
        for activity in activities:
            activity_type = activity["type"]
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1

        # Score based on activity types and frequency
        scoring_rules = {
            "sql_injection": 50,
            "xss_attempt": 30,
            "path_traversal": 40,
            "rate_limit_exceeded": 10,
            "invalid_auth": 20,
            "suspicious_request": 15,
            "blocked_user_agent": 25,
        }

        for activity_type, count in activity_counts.items():
            base_score = scoring_rules.get(activity_type, 5)
            # Exponential scoring for repeated attempts
            score += base_score * min(count, 10)
            if count > 5:
                score += base_score * (count - 5) * 2

        return score


class SecurityMiddleware:
    """Comprehensive security middleware"""

    def __init__(self, app: Optional[Flask] = None, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.validator = InputValidator(self.config)
        self.threat_detector = ThreatDetector(self.config)

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize security middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.config["MAX_CONTENT_LENGTH"] = self.config.MAX_CONTENT_LENGTH

        # Register error handlers
        app.errorhandler(413)(self.handle_large_payload)
        app.errorhandler(429)(self.handle_rate_limit)

        logger.info("Security middleware initialized")

    def before_request(self):
        """Process request before handling"""
        try:
            # Get client IP
            client_ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
            if "," in client_ip:
                client_ip = client_ip.split(",")[0].strip()

            g.client_ip = client_ip

            # Check blocked IPs
            if self.threat_detector.is_blocked_ip(client_ip):
                logger.warning(f"Blocked IP attempted access: {client_ip}")
                return jsonify({"error": "Access denied"}), 403

            # Check blocked user agents
            user_agent = request.headers.get("User-Agent", "")
            if self.threat_detector.is_blocked_user_agent(user_agent):
                self.threat_detector.track_suspicious_activity(client_ip, "blocked_user_agent")
                logger.warning(f"Blocked user agent from {client_ip}: {user_agent}")
                return jsonify({"error": "Access denied"}), 403

            # Rate limiting
            if self.config.ENABLE_RATE_LIMITING:
                result = self._check_rate_limits(client_ip)
                if not result.allowed:
                    self.threat_detector.track_suspicious_activity(client_ip, "rate_limit_exceeded")
                    return self._rate_limit_response(result)

            # Validate request content
            if request.content_length and request.content_length > self.config.MAX_CONTENT_LENGTH:
                return jsonify({"error": "Request too large"}), 413

            # Validate JSON content
            if request.is_json:
                try:
                    json_data = request.get_json()
                    if json_data is not None:
                        self.validator.validate_json(json_data)
                except BadRequest as e:
                    self.threat_detector.track_suspicious_activity(client_ip, "invalid_input")
                    return jsonify({"error": str(e)}), 400
                except Exception as e:
                    logger.error(f"JSON validation error: {e}")
                    return jsonify({"error": "Invalid JSON data"}), 400

            # Validate form data
            if request.form and len(request.form) > self.config.MAX_FORM_FIELDS:
                return jsonify({"error": "Too many form fields"}), 400

            # Check for suspicious patterns in query parameters
            for key, value in request.args.items():
                if self.validator.contains_malicious_patterns(value):
                    self.threat_detector.track_suspicious_activity(client_ip, "suspicious_request")
                    return jsonify({"error": "Invalid request parameters"}), 400

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # Fail securely - deny access on unexpected errors
            return jsonify({"error": "Security check failed"}), 500

    def after_request(self, response):
        """Add security headers to response"""
        # Add security headers
        for header, value in self.config.SECURITY_HEADERS.items():
            response.headers[header] = value

        # Remove server information
        response.headers.pop("Server", None)

        # Add custom headers
        response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")
        response.headers["X-Security-Policy"] = "enforced"

        return response

    def _check_rate_limits(self, client_ip: str) -> Any:
        """Check various rate limits"""
        # Global rate limit
        key = get_rate_limit_key("ip")
        result = rate_limiter.check_limit("global", key)

        if not result.allowed:
            return result

        # API-specific rate limits
        if request.path.startswith("/api/"):
            result = rate_limiter.check_limit("api", key)
            if not result.allowed:
                return result

        # Auth endpoint rate limiting
        if request.path.startswith("/api/auth/"):
            result = rate_limiter.check_limit("auth", key)
            if not result.allowed:
                return result

        return result

    def _rate_limit_response(self, result) -> tuple:
        """Generate rate limit exceeded response"""
        response = jsonify(
            {
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Try again in {result.retry_after} seconds.",
                "retry_after": result.retry_after,
            }
        )

        response.headers["X-Rate-Limit-Remaining"] = str(result.remaining)
        response.headers["X-Rate-Limit-Reset"] = str(result.reset_time)
        response.headers["Retry-After"] = str(result.retry_after or 60)

        return response, 429

    def handle_large_payload(self, error):
        """Handle request too large errors"""
        return (
            jsonify(
                {"error": "Request too large", "message": f"Maximum content length is {self.config.MAX_CONTENT_LENGTH} bytes"}
            ),
            413,
        )

    def handle_rate_limit(self, error):
        """Handle rate limit errors"""
        return jsonify({"error": "Rate limit exceeded", "message": "Too many requests"}), 429


def security_required(f):
    """Decorator for endpoints requiring additional security checks"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Additional security checks can be added here
        return f(*args, **kwargs)

    return decorated_function


def validate_api_key(f):
    """Decorator for API key validation"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return jsonify({"error": "API key required"}), 401

        # Validate API key (implement your validation logic)
        # This is a simple example - use proper key validation in production
        if api_key not in current_app.config.get("VALID_API_KEYS", []):
            return jsonify({"error": "Invalid API key"}), 401

        return f(*args, **kwargs)

    return decorated_function
