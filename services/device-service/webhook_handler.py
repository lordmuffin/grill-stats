#!/usr/bin/env python3
"""
Webhook Handler Module

This module provides functionality for handling webhooks from ThermoWorks
and other external services to receive real-time updates.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from flask import Blueprint, Response, abort, current_app, jsonify, request

from thermoworks_client import DeviceInfo, TemperatureReading

# Configure logging
logger = logging.getLogger("webhook_handler")


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint"""

    # Event type (e.g., 'temperature_update', 'device_status')
    event_type: str

    # Webhook secret for verification
    secret: str

    # Handler function to process the webhook
    handler: Callable[[Dict[str, Any]], None]

    # Whether to verify the signature
    verify_signature: bool = True

    # Signature header name
    signature_header: str = "X-Webhook-Signature"

    # Allowed IP addresses (empty list means all IPs allowed)
    allowed_ips: List[str] = None


class WebhookManager:
    """Manager for webhook endpoints and handlers"""

    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.blueprint = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

        # Register the webhook routes
        self.blueprint.add_url_rule("/<webhook_id>", view_func=self._handle_webhook, methods=["POST"])

        # Register the verification endpoint
        self.blueprint.add_url_rule("/<webhook_id>/verify", view_func=self._verify_webhook, methods=["GET"])

    def register_webhook(self, webhook_id: str, config: WebhookConfig) -> None:
        """Register a new webhook endpoint

        Args:
            webhook_id: Unique identifier for the webhook
            config: Webhook configuration
        """
        self.webhooks[webhook_id] = config
        logger.info(f"Registered webhook handler for {webhook_id} ({config.event_type})")

    def _verify_signature(self, webhook_id: str, payload: bytes, signature: str) -> bool:
        """Verify the webhook signature

        Args:
            webhook_id: Webhook identifier
            payload: Raw request payload
            signature: Signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        if webhook_id not in self.webhooks:
            return False

        config = self.webhooks[webhook_id]

        if not config.verify_signature:
            return True

        # Calculate expected signature
        expected_signature = hmac.new(config.secret.encode(), payload, hashlib.sha256).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)

    def _verify_ip(self, webhook_id: str, ip_address: str) -> bool:
        """Verify if the IP address is allowed

        Args:
            webhook_id: Webhook identifier
            ip_address: IP address to verify

        Returns:
            True if IP is allowed, False otherwise
        """
        if webhook_id not in self.webhooks:
            return False

        config = self.webhooks[webhook_id]

        # If no allowed IPs are specified, all IPs are allowed
        if not config.allowed_ips:
            return True

        return ip_address in config.allowed_ips

    def _handle_webhook(self, webhook_id: str) -> Response:
        """Handle an incoming webhook request

        Args:
            webhook_id: Webhook identifier

        Returns:
            Flask response
        """
        start_time = time.time()

        # Check if webhook exists
        if webhook_id not in self.webhooks:
            logger.warning(f"Received webhook for unknown ID: {webhook_id}")
            abort(404, f"Webhook {webhook_id} not found")

        config = self.webhooks[webhook_id]

        # Verify IP address if needed
        if config.allowed_ips and not self._verify_ip(webhook_id, request.remote_addr):
            logger.warning(f"IP address not allowed for webhook {webhook_id}: {request.remote_addr}")
            abort(403, "IP address not allowed")

        # Get the raw payload for signature verification
        payload = request.get_data()

        # Verify signature if needed
        if config.verify_signature:
            signature = request.headers.get(config.signature_header)
            if not signature:
                logger.warning(f"Missing signature header for webhook {webhook_id}")
                abort(400, "Missing signature header")

            if not self._verify_signature(webhook_id, payload, signature):
                logger.warning(f"Invalid signature for webhook {webhook_id}")
                abort(403, "Invalid signature")

        # Parse the payload
        try:
            if request.is_json:
                data = request.json
            else:
                data = json.loads(payload.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            abort(400, "Invalid payload format")

        # Process the webhook
        try:
            # Call the handler function
            config.handler(data)

            # Log the processing time
            processing_time = time.time() - start_time
            logger.info(f"Processed webhook {webhook_id} in {processing_time:.2f}s")

            return jsonify(
                {
                    "status": "success",
                    "message": f"Webhook {webhook_id} processed successfully",
                    "processing_time": processing_time,
                }
            )
        except Exception as e:
            logger.error(f"Error processing webhook {webhook_id}: {e}")
            abort(500, f"Error processing webhook: {str(e)}")

    def _verify_webhook(self, webhook_id: str) -> Response:
        """Verify a webhook configuration

        Args:
            webhook_id: Webhook identifier

        Returns:
            Flask response
        """
        # Check if webhook exists
        if webhook_id not in self.webhooks:
            logger.warning(f"Verification request for unknown webhook ID: {webhook_id}")
            abort(404, f"Webhook {webhook_id} not found")

        config = self.webhooks[webhook_id]

        # Return webhook verification details
        return jsonify(
            {
                "status": "success",
                "webhook_id": webhook_id,
                "event_type": config.event_type,
                "verification_required": config.verify_signature,
                "signature_header": config.signature_header if config.verify_signature else None,
                "url": f"{request.url_root.rstrip('/')}/api/webhooks/{webhook_id}",
            }
        )


# Global webhook manager
webhook_manager = WebhookManager()


def register_webhook_handlers(app, temperature_handler=None):
    """Register webhook handlers with the Flask application

    Args:
        app: Flask application
        temperature_handler: Function to handle temperature updates
    """
    # Register the blueprint
    app.register_blueprint(webhook_manager.blueprint)

    # Default temperature handler function
    def default_temperature_handler(data: Dict[str, Any]) -> None:
        """Default handler for temperature updates"""
        logger.info(f"Received temperature update: {data}")

        if not temperature_handler:
            logger.warning("No temperature handler registered")
            return

        # Extract device information
        try:
            device_id = data.get("device_id")
            if not device_id:
                logger.warning("Missing device_id in temperature update")
                return

            # Create device info
            device = DeviceInfo(
                device_id=device_id,
                name=data.get("device_name", "Unknown Device"),
                model=data.get("model", "Unknown Model"),
                battery_level=data.get("battery_level"),
                signal_strength=data.get("signal_strength"),
                is_online=data.get("is_online", True),
            )

            # Extract temperature readings
            readings = []
            for probe_data in data.get("probes", []):
                reading = TemperatureReading(
                    device_id=device_id,
                    probe_id=probe_data.get("probe_id", "0"),
                    temperature=probe_data.get("temperature", 0.0),
                    unit=probe_data.get("unit", "F"),
                    timestamp=probe_data.get("timestamp"),
                    battery_level=data.get("battery_level"),
                    signal_strength=data.get("signal_strength"),
                )
                readings.append(reading)

            # Call temperature handler
            temperature_handler(device, readings)
            logger.debug(f"Processed {len(readings)} temperature readings for device {device_id}")

        except Exception as e:
            logger.error(f"Error processing temperature update: {e}")
            raise

    # Register temperature webhook
    webhook_manager.register_webhook(
        "temperature",
        WebhookConfig(
            event_type="temperature_update",
            secret=os.environ.get("WEBHOOK_SECRET", "your-webhook-secret"),
            handler=default_temperature_handler,
            verify_signature=os.environ.get("VERIFY_WEBHOOKS", "true").lower() in ("true", "1", "yes"),
        ),
    )

    # Register device status webhook
    def device_status_handler(data: Dict[str, Any]) -> None:
        """Handler for device status updates"""
        logger.info(f"Received device status update: {data}")

        # Process device status updates
        # This could update device status in database or notify other systems
        pass

    webhook_manager.register_webhook(
        "device-status",
        WebhookConfig(
            event_type="device_status_update",
            secret=os.environ.get("WEBHOOK_SECRET", "your-webhook-secret"),
            handler=device_status_handler,
            verify_signature=os.environ.get("VERIFY_WEBHOOKS", "true").lower() in ("true", "1", "yes"),
        ),
    )

    logger.info("Registered webhook handlers")
