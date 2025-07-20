#!/usr/bin/env python3
"""
Tests for Webhook Handler Module

This module tests the webhook handler functionality, including signature verification,
IP filtering, and handling of webhook events.
"""

import hashlib
import hmac
import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import Flask, request
from webhook_handler import WebhookConfig, WebhookManager, register_webhook_handlers

from thermoworks_client import DeviceInfo, TemperatureReading


@pytest.fixture
def app():
    """Create a Flask test application"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def webhook_manager():
    """Create a WebhookManager instance"""
    return WebhookManager()


@pytest.fixture
def client(app, webhook_manager):
    """Create a Flask test client with webhook routes"""
    app.register_blueprint(webhook_manager.blueprint)
    return app.test_client()


class TestWebhookConfig:
    """Tests for the WebhookConfig class"""

    def test_webhook_config_initialization(self):
        """Test webhook configuration initialization"""
        handler = MagicMock()
        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
        )

        assert config.event_type == "test_event"
        assert config.secret == "test_secret"
        assert config.handler is handler
        assert config.verify_signature is True
        assert config.signature_header == "X-Webhook-Signature"
        assert config.allowed_ips is None

    def test_webhook_config_with_custom_values(self):
        """Test webhook configuration with custom values"""
        handler = MagicMock()
        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
            verify_signature=False,
            signature_header="X-Custom-Signature",
            allowed_ips=["192.168.1.1", "10.0.0.1"],
        )

        assert config.event_type == "test_event"
        assert config.secret == "test_secret"
        assert config.handler is handler
        assert config.verify_signature is False
        assert config.signature_header == "X-Custom-Signature"
        assert config.allowed_ips == ["192.168.1.1", "10.0.0.1"]


class TestWebhookManager:
    """Tests for the WebhookManager class"""

    def test_register_webhook(self, webhook_manager):
        """Test registering a webhook"""
        handler = MagicMock()
        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        assert "test_webhook" in webhook_manager.webhooks
        assert webhook_manager.webhooks["test_webhook"] is config

    def test_verify_signature_valid(self, webhook_manager):
        """Test webhook signature verification with valid signature"""
        handler = MagicMock()
        secret = "test_secret"

        config = WebhookConfig(
            event_type="test_event",
            secret=secret,
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        payload = b'{"data": "test"}'
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        assert webhook_manager._verify_signature("test_webhook", payload, signature) is True

    def test_verify_signature_invalid(self, webhook_manager):
        """Test webhook signature verification with invalid signature"""
        handler = MagicMock()
        secret = "test_secret"

        config = WebhookConfig(
            event_type="test_event",
            secret=secret,
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        payload = b'{"data": "test"}'
        signature = "invalid_signature"

        assert webhook_manager._verify_signature("test_webhook", payload, signature) is False

    def test_verify_signature_disabled(self, webhook_manager):
        """Test webhook signature verification when disabled"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
            verify_signature=False,
        )

        webhook_manager.register_webhook("test_webhook", config)

        payload = b'{"data": "test"}'
        signature = "any_signature"

        assert webhook_manager._verify_signature("test_webhook", payload, signature) is True

    def test_verify_ip_allowed(self, webhook_manager):
        """Test IP verification with allowed IP"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
            allowed_ips=["192.168.1.1", "10.0.0.1"],
        )

        webhook_manager.register_webhook("test_webhook", config)

        assert webhook_manager._verify_ip("test_webhook", "192.168.1.1") is True
        assert webhook_manager._verify_ip("test_webhook", "10.0.0.1") is True
        assert webhook_manager._verify_ip("test_webhook", "172.16.0.1") is False

    def test_verify_ip_no_restrictions(self, webhook_manager):
        """Test IP verification with no IP restrictions"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
            allowed_ips=None,
        )

        webhook_manager.register_webhook("test_webhook", config)

        assert webhook_manager._verify_ip("test_webhook", "192.168.1.1") is True
        assert webhook_manager._verify_ip("test_webhook", "any_ip") is True


class TestWebhookEndpoints:
    """Tests for webhook endpoints"""

    def test_handle_webhook_success(self, client, webhook_manager):
        """Test successful webhook handling"""
        handler = MagicMock()
        secret = "test_secret"

        config = WebhookConfig(
            event_type="test_event",
            secret=secret,
            handler=handler,
            verify_signature=True,
        )

        webhook_manager.register_webhook("test_webhook", config)

        payload = {"data": "test"}
        payload_bytes = json.dumps(payload).encode()

        signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

        response = client.post(
            "/api/webhooks/test_webhook",
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

        # Verify handler was called with correct data
        handler.assert_called_once_with(payload)

    def test_handle_webhook_unknown_id(self, client):
        """Test webhook handling with unknown webhook ID"""
        response = client.post(
            "/api/webhooks/unknown_webhook",
            json={"data": "test"},
        )

        assert response.status_code == 404

    def test_handle_webhook_missing_signature(self, client, webhook_manager):
        """Test webhook handling with missing signature"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        response = client.post(
            "/api/webhooks/test_webhook",
            json={"data": "test"},
        )

        assert response.status_code == 400
        assert b"Missing signature header" in response.data

    def test_handle_webhook_invalid_signature(self, client, webhook_manager):
        """Test webhook handling with invalid signature"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        response = client.post(
            "/api/webhooks/test_webhook",
            json={"data": "test"},
            headers={"X-Webhook-Signature": "invalid_signature"},
        )

        assert response.status_code == 403
        assert b"Invalid signature" in response.data

    def test_handle_webhook_ip_not_allowed(self, client, webhook_manager):
        """Test webhook handling with IP not allowed"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
            allowed_ips=["192.168.1.1"],
        )

        webhook_manager.register_webhook("test_webhook", config)

        with patch("webhook_handler.request") as mock_request:
            mock_request.remote_addr = "10.0.0.1"

            response = client.post(
                "/api/webhooks/test_webhook",
                json={"data": "test"},
                headers={"X-Webhook-Signature": "any_signature"},
                environ_base={"REMOTE_ADDR": "10.0.0.1"},
            )

            assert response.status_code == 403
            assert b"IP address not allowed" in response.data

    def test_verify_webhook_endpoint(self, client, webhook_manager):
        """Test webhook verification endpoint"""
        handler = MagicMock()

        config = WebhookConfig(
            event_type="test_event",
            secret="test_secret",
            handler=handler,
        )

        webhook_manager.register_webhook("test_webhook", config)

        response = client.get("/api/webhooks/test_webhook/verify")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["webhook_id"] == "test_webhook"
        assert data["event_type"] == "test_event"
        assert data["verification_required"] is True
        assert data["signature_header"] == "X-Webhook-Signature"
        assert "/api/webhooks/test_webhook" in data["url"]

    def test_verify_webhook_unknown_id(self, client):
        """Test webhook verification with unknown webhook ID"""
        response = client.get("/api/webhooks/unknown_webhook/verify")

        assert response.status_code == 404


class TestRegisterWebhookHandlers:
    """Tests for register_webhook_handlers function"""

    def test_register_webhook_handlers(self, app):
        """Test registering webhook handlers with the Flask application"""
        temperature_handler = MagicMock()

        with patch.dict(
            os.environ,
            {
                "WEBHOOK_SECRET": "test_webhook_secret",
                "VERIFY_WEBHOOKS": "true",
            },
        ):
            register_webhook_handlers(app, temperature_handler)

            # Verify blueprint was registered
            assert any(bp.name == "webhooks" for bp in app.blueprints.values())

            # Get the webhook manager from the module
            from webhook_handler import webhook_manager

            # Verify webhooks were registered
            assert "temperature" in webhook_manager.webhooks
            assert "device-status" in webhook_manager.webhooks

            # Verify configuration
            assert webhook_manager.webhooks["temperature"].event_type == "temperature_update"
            assert webhook_manager.webhooks["temperature"].secret == "test_webhook_secret"
            assert webhook_manager.webhooks["temperature"].verify_signature is True

            assert webhook_manager.webhooks["device-status"].event_type == "device_status_update"
            assert webhook_manager.webhooks["device-status"].secret == "test_webhook_secret"
            assert webhook_manager.webhooks["device-status"].verify_signature is True

    def test_temperature_handler(self, app):
        """Test the default temperature handler"""
        temperature_handler = MagicMock()

        with patch.dict(
            os.environ,
            {
                "WEBHOOK_SECRET": "test_webhook_secret",
            },
        ):
            register_webhook_handlers(app, temperature_handler)

            # Get the webhook manager and temperature handler
            from webhook_handler import webhook_manager

            # Create test data
            data = {
                "device_id": "test_device_id",
                "device_name": "Test Device",
                "model": "Test Model",
                "battery_level": 80,
                "signal_strength": 90,
                "is_online": True,
                "probes": [
                    {
                        "probe_id": "1",
                        "temperature": 225.5,
                        "unit": "F",
                        "timestamp": "2025-07-20T12:00:00Z",
                    },
                    {
                        "probe_id": "2",
                        "temperature": 135.2,
                        "unit": "F",
                        "timestamp": "2025-07-20T12:00:00Z",
                    },
                ],
            }

            # Call the handler directly
            webhook_manager.webhooks["temperature"].handler(data)

            # Verify temperature handler was called
            temperature_handler.assert_called_once()

            # Check that the correct DeviceInfo and TemperatureReading objects were created
            call_args = temperature_handler.call_args[0]
            device, readings = call_args

            assert isinstance(device, DeviceInfo)
            assert device.device_id == "test_device_id"
            assert device.name == "Test Device"
            assert device.model == "Test Model"
            assert device.battery_level == 80
            assert device.signal_strength == 90
            assert device.is_online is True

            assert len(readings) == 2
            assert all(isinstance(r, TemperatureReading) for r in readings)
            assert readings[0].device_id == "test_device_id"
            assert readings[0].probe_id == "1"
            assert readings[0].temperature == 225.5
            assert readings[0].unit == "F"
            assert readings[0].timestamp == "2025-07-20T12:00:00Z"
            assert readings[1].probe_id == "2"
            assert readings[1].temperature == 135.2


if __name__ == "__main__":
    pytest.main([__file__])
