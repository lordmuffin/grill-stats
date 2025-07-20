# \!/usr/bin/env python3
"""
Super simple Flask application for testing Docker deployment.
"""

import logging
import os
from typing import Any, Dict

from flask import Flask, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# Routes
@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint

    Returns:
        JSON response with health status information
    """
    status = {
        "status": "healthy",
        "timestamp": "2025-07-19T12:00:00",
        "service": "device-service",
        "version": "1.0.0",
        "message": "Simple demo server is running",
    }

    return jsonify(status)


@app.route("/api/devices", methods=["GET"])
def get_devices() -> Any:
    """Get all devices

    Returns:
        JSON with list of devices
    """
    # Mock response for testing
    devices = [
        {"device_id": "mock-device-1", "name": "Mock Thermometer 1", "model": "Signals", "status": "online"},
        {"device_id": "mock-device-2", "name": "Mock Thermometer 2", "model": "Smoke", "status": "offline"},
    ]

    return jsonify(
        {"status": "success", "message": "Success", "data": {"devices": devices, "count": len(devices), "source": "mock"}}
    )


if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

    logger.info(f"Starting simple demo server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
