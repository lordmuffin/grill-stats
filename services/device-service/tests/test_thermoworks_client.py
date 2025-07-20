#!/usr/bin/env python3
"""
Tests for ThermoWorks Client

This module contains tests for the ThermoWorks client, including authentication,
device discovery, temperature data retrieval, and rate limiting.
"""

import datetime
import json
import os
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
import requests

from thermoworks_client import (
    AuthToken,
    DeviceInfo,
    RateLimiter,
    RateLimitExceededError,
    TemperatureReading,
    ThermoworksAPIError,
    ThermoworksAuthenticationError,
    ThermoworksClient,
    ThermoworksConnectionError,
)


class TestRateLimiter:
    """Tests for the RateLimiter class"""

    def test_initialization(self):
        """Test rate limiter initialization with default values"""
        rate_limiter = RateLimiter()
        assert rate_limiter.rate_limit == 1000
        assert rate_limiter.time_window == 3600
        assert rate_limiter.burst_limit == 10
        assert rate_limiter.rate == 1000 / 3600

    def test_initialization_with_custom_values(self):
        """Test rate limiter initialization with custom values"""
        rate_limiter = RateLimiter(rate_limit=100, time_window=60, burst_limit=5)
        assert rate_limiter.rate_limit == 100
        assert rate_limiter.time_window == 60
        assert rate_limiter.burst_limit == 5
        assert rate_limiter.rate == 100 / 60

    def test_check_rate_limit_under_limit(self):
        """Test check_rate_limit when under the limit"""
        rate_limiter = RateLimiter(rate_limit=10, time_window=60, burst_limit=5)
        # Should start with full burst tokens
        assert rate_limiter.check_rate_limit("test_endpoint") is True
        # Should consume one token
        assert rate_limiter.buckets["test_endpoint"]["tokens"] < 5

    def test_check_rate_limit_over_limit(self):
        """Test check_rate_limit when over the limit"""
        rate_limiter = RateLimiter(rate_limit=5, time_window=60, burst_limit=5)

        # Use up all tokens
        for _ in range(5):
            assert rate_limiter.check_rate_limit("test_endpoint") is True

        # Should be over the limit now
        assert rate_limiter.check_rate_limit("test_endpoint") is False

    def test_token_refill(self):
        """Test tokens are refilled over time"""
        rate_limiter = RateLimiter(rate_limit=60, time_window=60, burst_limit=5)

        # Use up some tokens
        for _ in range(3):
            rate_limiter.check_rate_limit("test_endpoint")

        # Manually set last_refill to be 10 seconds ago
        rate_limiter.buckets["test_endpoint"]["last_refill"] = time.time() - 10

        # Should have refilled some tokens (10 seconds = 10 tokens at 1/sec)
        rate_limiter.check_rate_limit("test_endpoint")
        # 5 (burst) - 3 (used) + 10 (refilled) - 1 (just used) = 11, capped at 5
        assert rate_limiter.buckets["test_endpoint"]["tokens"] == 5

    def test_wait_if_needed_success(self):
        """Test wait_if_needed when rate limit is not exceeded"""
        rate_limiter = RateLimiter(rate_limit=10, time_window=60, burst_limit=5)
        # Should not raise an exception
        rate_limiter.wait_if_needed("test_endpoint")

    def test_wait_if_needed_timeout(self):
        """Test wait_if_needed when rate limit is exceeded and timeout occurs"""
        rate_limiter = RateLimiter(rate_limit=5, time_window=60, burst_limit=5)

        # Use up all tokens
        for _ in range(5):
            rate_limiter.check_rate_limit("test_endpoint")

        # Should raise an exception with a short timeout
        with pytest.raises(RateLimitExceededError):
            rate_limiter.wait_if_needed("test_endpoint", max_wait=0.1)

    def test_multiple_endpoints(self):
        """Test rate limiting for multiple endpoints"""
        rate_limiter = RateLimiter(rate_limit=5, time_window=60, burst_limit=5)

        # Use up tokens for endpoint1
        for _ in range(5):
            rate_limiter.check_rate_limit("endpoint1")

        # endpoint1 should be over limit
        assert rate_limiter.check_rate_limit("endpoint1") is False

        # endpoint2 should still have tokens
        assert rate_limiter.check_rate_limit("endpoint2") is True

    def test_thread_safety(self):
        """Test rate limiter is thread-safe"""
        rate_limiter = RateLimiter(rate_limit=100, time_window=60, burst_limit=10)
        results = []

        def worker():
            """Worker function to check rate limits in parallel"""
            for _ in range(20):
                results.append(rate_limiter.check_rate_limit("shared_endpoint"))

        # Create and start 5 threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # We should have had exactly 10 successful checks (burst limit)
        # The rest should have failed
        assert results.count(True) == 10
        assert results.count(False) == 90


class TestThermoworksClient:
    """Tests for the ThermoworksClient class"""

    @pytest.fixture
    def mock_token_file(self, tmp_path):
        """Create a mock token file"""
        token_file = tmp_path / "token.json"
        token_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "devices:read temperature:read",
            "created_at": time.time(),
        }
        token_file.write_text(json.dumps(token_data))
        return token_file

    @pytest.fixture
    def client(self):
        """Create a mock ThermoWorks client"""
        with patch("thermoworks_client.requests.Session"):
            client = ThermoworksClient(
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="https://example.com/callback",
                base_url="https://api.example.com",
                auth_url="https://auth.example.com",
                token_storage_path=None,  # Don't load/save tokens
                auto_start_polling=False,
                mock_mode=False,
            )
            client.token = AuthToken(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                token_type="Bearer",
                expires_in=3600,
                scope="devices:read temperature:read",
                created_at=time.time(),
            )
            return client

    def test_rate_limiter_integration(self, client):
        """Test rate limiter integration with ThermoWorks client"""
        # Mock the session
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"devices": []}
        client.session.request.return_value = mock_response

        # Replace rate limiter with a mock
        client.rate_limiter = Mock()

        # Call API method
        client.get_devices()

        # Verify rate limiter was called
        client.rate_limiter.wait_if_needed.assert_called_once()

    @patch("thermoworks_client.requests.post")
    def test_authentication_rate_limiting(self, mock_post, client):
        """Test rate limiting during authentication"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        # Replace rate limiter with a spy
        client.rate_limiter = MagicMock()
        client.rate_limiter.wait_if_needed.side_effect = RateLimitExceededError("Rate limit exceeded")

        # Try to authenticate
        with pytest.raises(RateLimitExceededError):
            client.authenticate_with_client_credentials()

    @patch("thermoworks_client.requests.Session.request")
    def test_api_request_rate_limiting(self, mock_request, client):
        """Test rate limiting during API requests"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_request.return_value = mock_response

        # Replace rate limiter with a spy
        client.rate_limiter = MagicMock()
        client.rate_limiter.wait_if_needed.side_effect = RateLimitExceededError("Rate limit exceeded")

        # Try to make API request
        with pytest.raises(RateLimitExceededError):
            client._make_api_request("GET", "/test")

    @patch("thermoworks_client.requests.Session.request")
    def test_successful_request_with_rate_limiting(self, mock_request, client):
        """Test successful API request with rate limiting"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_request.return_value = mock_response

        # Make API request
        result = client._make_api_request("GET", "/test")

        # Verify result
        assert result == {"data": "test"}

        # Verify rate limiter was called
        assert client.rate_limiter.wait_if_needed.called

    def test_rate_limiter_configuration(self):
        """Test rate limiter configuration from environment variables"""
        with patch.dict(
            os.environ,
            {
                "THERMOWORKS_RATE_LIMIT": "500",
                "THERMOWORKS_RATE_WINDOW": "1800",
                "THERMOWORKS_BURST_LIMIT": "20",
            },
        ):
            with patch("thermoworks_client.requests.Session"):
                client = ThermoworksClient(
                    auto_start_polling=False,
                    mock_mode=False,
                )
                assert client.rate_limiter.rate_limit == 500
                assert client.rate_limiter.time_window == 1800
                assert client.rate_limiter.burst_limit == 20


if __name__ == "__main__":
    pytest.main([__file__])
