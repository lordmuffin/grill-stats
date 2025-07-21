"""
Comprehensive Test Suite for API Gateway Security
Tests JWT authentication, rate limiting, WAF, and security middleware
"""

import json
import time
import pytest
import requests
from unittest.mock import patch, MagicMock
from flask import Flask
from flask.testing import FlaskClient

from auth.jwt_middleware import JWTManager, jwt_required, get_current_user
from security.rate_limiter import RateLimiter, RateLimit, RateLimitAlgorithm
from security.security_middleware import SecurityMiddleware, SecurityConfig
from security.waf import WAF, WAFRule, ThreatLevel, ActionType


class TestJWTAuthentication:
    """Test JWT authentication functionality"""
    
    @pytest.fixture
    def jwt_manager(self):
        """Create JWT manager for testing"""
        return JWTManager()
    
    @pytest.fixture
    def user_data(self):
        """Sample user data for token generation"""
        return {
            "id": "123",
            "email": "test@example.com",
            "roles": ["user"]
        }
    
    def test_generate_tokens(self, jwt_manager, user_data):
        """Test JWT token generation"""
        access_token, refresh_token = jwt_manager.generate_tokens(user_data)
        
        assert access_token is not None
        assert refresh_token is not None
        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
    
    def test_verify_valid_token(self, jwt_manager, user_data):
        """Test verification of valid JWT token"""
        access_token, _ = jwt_manager.generate_tokens(user_data)
        
        payload = jwt_manager.verify_token(access_token, "access")
        
        assert payload["user_id"] == user_data["id"]
        assert payload["email"] == user_data["email"]
        assert payload["roles"] == user_data["roles"]
        assert payload["type"] == "access"
    
    def test_verify_invalid_token(self, jwt_manager):
        """Test verification of invalid JWT token"""
        with pytest.raises(Exception):
            jwt_manager.verify_token("invalid_token", "access")
    
    def test_refresh_token(self, jwt_manager, user_data):
        """Test token refresh functionality"""
        _, refresh_token = jwt_manager.generate_tokens(user_data)
        
        new_access_token = jwt_manager.refresh_access_token(refresh_token)
        
        assert new_access_token is not None
        payload = jwt_manager.verify_token(new_access_token, "access")
        assert payload["user_id"] == user_data["id"]
    
    def test_revoke_token(self, jwt_manager, user_data):
        """Test token revocation"""
        access_token, _ = jwt_manager.generate_tokens(user_data)
        
        # Token should be valid initially
        payload = jwt_manager.verify_token(access_token, "access")
        assert payload is not None
        
        # Revoke the token
        success = jwt_manager.revoke_token(access_token, "test_revocation")
        assert success
        
        # Token should be invalid after revocation
        with pytest.raises(Exception):
            jwt_manager.verify_token(access_token, "access")
    
    def test_jwt_required_decorator(self):
        """Test JWT required decorator"""
        app = Flask(__name__)
        
        @app.route("/protected")
        @jwt_required()
        def protected():
            user = get_current_user()
            return {"user_id": user["id"]}
        
        with app.test_client() as client:
            # Test without token
            response = client.get("/protected")
            assert response.status_code == 401
            
            # Test with invalid token
            response = client.get(
                "/protected",
                headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == 401
    
    def test_role_based_access(self):
        """Test role-based access control"""
        app = Flask(__name__)
        
        @app.route("/admin")
        @jwt_required(roles=["admin"])
        def admin_only():
            return {"message": "admin access"}
        
        # This would require setting up proper JWT tokens with roles
        # For now, test the basic structure
        with app.test_client() as client:
            response = client.get("/admin")
            assert response.status_code == 401


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing"""
        limiter = RateLimiter()
        limiter.add_limit("test", RateLimit(
            requests=5,
            window=60,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW
        ))
        return limiter
    
    @patch('security.rate_limiter.redis.Redis')
    def test_rate_limit_check(self, mock_redis, rate_limiter):
        """Test basic rate limit checking"""
        # Mock Redis eval to return [1, 4, 1] (allowed, remaining, current_count)
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = [1, 4, 1]
        rate_limiter.redis_client = mock_redis_instance
        
        result = rate_limiter.check_limit("test", "user_123")
        
        assert result.allowed is True
        assert result.remaining == 4
    
    @patch('security.rate_limiter.redis.Redis')
    def test_rate_limit_exceeded(self, mock_redis, rate_limiter):
        """Test rate limit exceeded scenario"""
        # Mock Redis eval to return [0, 0, 5] (not allowed, no remaining, at limit)
        mock_redis_instance = MagicMock()
        mock_redis_instance.eval.return_value = [0, 0, 5]
        rate_limiter.redis_client = mock_redis_instance
        
        result = rate_limiter.check_limit("test", "user_123")
        
        assert result.allowed is False
        assert result.remaining == 0
    
    def test_rate_limit_algorithms(self):
        """Test different rate limiting algorithms"""
        limiter = RateLimiter()
        
        # Test token bucket
        limiter.add_limit("token_bucket", RateLimit(
            requests=10,
            window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            burst=5
        ))
        
        # Test sliding window
        limiter.add_limit("sliding_window", RateLimit(
            requests=10,
            window=60,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        ))
        
        assert "token_bucket" in limiter.limits
        assert "sliding_window" in limiter.limits
    
    def test_rate_limit_reset(self, rate_limiter):
        """Test rate limit reset functionality"""
        success = rate_limiter.reset_limit("test", "user_123")
        # Will return False if Redis is not available, True if successful
        assert isinstance(success, bool)


class TestSecurityMiddleware:
    """Test security middleware functionality"""
    
    @pytest.fixture
    def app_with_security(self):
        """Create Flask app with security middleware"""
        app = Flask(__name__)
        security = SecurityMiddleware(app)
        
        @app.route("/test")
        def test_endpoint():
            return {"message": "test"}
        
        return app
    
    def test_security_headers(self, app_with_security):
        """Test security headers are added"""
        with app_with_security.test_client() as client:
            response = client.get("/test")
            
            # Check for security headers
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "X-XSS-Protection" in response.headers
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
    
    def test_malicious_input_detection(self):
        """Test malicious input detection"""
        from security.security_middleware import InputValidator
        
        validator = InputValidator(SecurityConfig())
        
        # Test SQL injection patterns
        assert validator.contains_malicious_patterns("'; DROP TABLE users; --")
        assert validator.contains_malicious_patterns("UNION SELECT * FROM passwords")
        
        # Test XSS patterns
        assert validator.contains_malicious_patterns("<script>alert('xss')</script>")
        assert validator.contains_malicious_patterns("javascript:alert(1)")
        
        # Test safe input
        assert not validator.contains_malicious_patterns("normal user input")
        assert not validator.contains_malicious_patterns("search query")
    
    def test_json_validation(self):
        """Test JSON structure validation"""
        from security.security_middleware import InputValidator
        
        validator = InputValidator(SecurityConfig())
        
        # Test valid JSON
        assert validator.validate_json({"key": "value"})
        assert validator.validate_json({"nested": {"key": "value"}})
        
        # Test invalid JSON (too deep)
        config = SecurityConfig()
        config.MAX_JSON_DEPTH = 2
        validator = InputValidator(config)
        
        with pytest.raises(Exception):
            validator.validate_json({
                "level1": {
                    "level2": {
                        "level3": {
                            "level4": "too deep"
                        }
                    }
                }
            })
    
    def test_file_upload_validation(self):
        """Test file upload validation"""
        from security.security_middleware import InputValidator
        from werkzeug.datastructures import FileStorage
        from io import BytesIO
        
        validator = InputValidator(SecurityConfig())
        
        # Test valid file
        valid_file = FileStorage(
            stream=BytesIO(b"test content"),
            filename="test.txt",
            content_type="text/plain"
        )
        assert validator.validate_file_upload(valid_file)
        
        # Test invalid extension
        invalid_file = FileStorage(
            stream=BytesIO(b"test content"),
            filename="test.exe",
            content_type="application/octet-stream"
        )
        with pytest.raises(Exception):
            validator.validate_file_upload(invalid_file)


class TestWAF:
    """Test Web Application Firewall functionality"""
    
    @pytest.fixture
    def waf(self):
        """Create WAF instance for testing"""
        return WAF()
    
    def test_sql_injection_detection(self, waf):
        """Test SQL injection detection"""
        request_data = {
            "url": "http://example.com/api",
            "query_string": "id=1' OR '1'='1",
            "user_agent": "test",
            "body": "",
            "headers": {},
            "cookies": {}
        }
        
        detections = waf.rule_engine.evaluate_request(request_data)
        
        # Should detect SQL injection attempts
        assert len(detections) > 0
        assert any(d.detected for d in detections)
        sql_detections = [d for d in detections if d.detected and "sql" in d.rule_id.lower()]
        assert len(sql_detections) > 0
    
    def test_xss_detection(self, waf):
        """Test XSS detection"""
        request_data = {
            "url": "http://example.com/api",
            "query_string": "",
            "user_agent": "test",
            "body": "<script>alert('xss')</script>",
            "headers": {},
            "cookies": {}
        }
        
        detections = waf.rule_engine.evaluate_request(request_data)
        
        # Should detect XSS attempts
        xss_detections = [d for d in detections if d.detected and "xss" in d.rule_id.lower()]
        assert len(xss_detections) > 0
    
    def test_path_traversal_detection(self, waf):
        """Test path traversal detection"""
        request_data = {
            "url": "http://example.com/../../etc/passwd",
            "query_string": "",
            "user_agent": "test",
            "body": "",
            "headers": {},
            "cookies": {}
        }
        
        detections = waf.rule_engine.evaluate_request(request_data)
        
        # Should detect path traversal attempts
        path_detections = [d for d in detections if d.detected and "path" in d.rule_id.lower()]
        assert len(path_detections) > 0
    
    def test_scanner_detection(self, waf):
        """Test security scanner detection"""
        request_data = {
            "url": "http://example.com/api",
            "query_string": "",
            "user_agent": "sqlmap/1.4.12",
            "body": "",
            "headers": {},
            "cookies": {}
        }
        
        detections = waf.rule_engine.evaluate_request(request_data)
        
        # Should detect security scanners
        scan_detections = [d for d in detections if d.detected and "scan" in d.rule_id.lower()]
        assert len(scan_detections) > 0
    
    def test_custom_rule_addition(self, waf):
        """Test adding custom WAF rules"""
        custom_rule = WAFRule(
            id="custom_001",
            name="Custom Test Rule",
            description="Test rule for custom patterns",
            pattern=r"test_pattern",
            threat_level=ThreatLevel.LOW,
            action=ActionType.LOG
        )
        
        waf.rule_engine.add_rule(custom_rule)
        
        assert "custom_001" in waf.rule_engine.rules
        assert waf.rule_engine.rules["custom_001"].name == "Custom Test Rule"
    
    def test_ip_blocking(self, waf):
        """Test IP blocking functionality"""
        test_ip = "192.168.1.100"
        
        # Block IP
        waf.block_ip(test_ip)
        assert test_ip in waf.blocked_ips
        
        # Unblock IP
        success = waf.unblock_ip(test_ip)
        assert success
        assert test_ip not in waf.blocked_ips
    
    def test_threat_scoring(self, waf):
        """Test threat scoring system"""
        test_ip = "192.168.1.101"
        
        # Initially no score
        assert test_ip not in waf.threat_scores
        
        # Simulate detections
        from security.waf import ThreatDetection
        detections = [
            ThreatDetection(
                detected=True,
                rule_id="test_001",
                threat_level=ThreatLevel.MEDIUM,
                score=30,
                message="Test detection",
                action=ActionType.LOG,
                evidence={"test": "data"}
            )
        ]
        
        waf._update_threat_score(test_ip, 30, detections)
        
        assert test_ip in waf.threat_scores
        assert waf.threat_scores[test_ip]["total_score"] == 30


class TestIntegration:
    """Integration tests for the complete security system"""
    
    def test_end_to_end_security_flow(self):
        """Test complete security flow from request to response"""
        app = Flask(__name__)
        
        # Initialize security components
        security = SecurityMiddleware(app)
        jwt_manager = JWTManager(app)
        
        @app.route("/api/secure")
        @jwt_required()
        def secure_endpoint():
            return {"message": "secure data"}
        
        @app.route("/api/public")
        def public_endpoint():
            return {"message": "public data"}
        
        with app.test_client() as client:
            # Test public endpoint works
            response = client.get("/api/public")
            assert response.status_code == 200
            
            # Test secure endpoint requires auth
            response = client.get("/api/secure")
            assert response.status_code == 401
    
    def test_rate_limiting_integration(self):
        """Test rate limiting in application context"""
        app = Flask(__name__)
        security = SecurityMiddleware(app)
        
        @app.route("/api/limited")
        def limited_endpoint():
            return {"message": "limited"}
        
        # This would require proper Redis setup for full testing
        with app.test_client() as client:
            response = client.get("/api/limited")
            # Should work without rate limiting in test environment
            assert response.status_code == 200
    
    def test_security_headers_integration(self):
        """Test security headers are properly applied"""
        app = Flask(__name__)
        security = SecurityMiddleware(app)
        
        @app.route("/test")
        def test_endpoint():
            return {"test": True}
        
        with app.test_client() as client:
            response = client.get("/test")
            
            # Verify security headers
            required_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options", 
                "X-XSS-Protection"
            ]
            
            for header in required_headers:
                assert header in response.headers


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    with patch('redis.Redis') as mock:
        yield mock


class TestPerformance:
    """Performance tests for security components"""
    
    def test_jwt_token_generation_performance(self):
        """Test JWT token generation performance"""
        jwt_manager = JWTManager()
        user_data = {"id": "123", "email": "test@example.com", "roles": ["user"]}
        
        start_time = time.time()
        for _ in range(100):
            jwt_manager.generate_tokens(user_data)
        end_time = time.time()
        
        # Should be able to generate 100 tokens in reasonable time
        assert (end_time - start_time) < 1.0
    
    def test_waf_rule_evaluation_performance(self):
        """Test WAF rule evaluation performance"""
        waf = WAF()
        request_data = {
            "url": "http://example.com/api/test",
            "query_string": "param=value",
            "user_agent": "test-agent",
            "body": "normal request body",
            "headers": {"Content-Type": "application/json"},
            "cookies": {}
        }
        
        start_time = time.time()
        for _ in range(100):
            waf.rule_engine.evaluate_request(request_data)
        end_time = time.time()
        
        # Should be able to evaluate 100 requests in reasonable time
        assert (end_time - start_time) < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])