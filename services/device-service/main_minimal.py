#!/usr/bin/env python3
"""
Minimal Device Service API for testing dependency injection

A minimal version of main.py that only includes the core functionality needed to test
the dependency injection implementation.
"""

import logging
import os
from typing import Any, Dict

# Import dependency injection container
from containers import create_container
from dependency_injector.wiring import Provide, inject
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from temperature_handler import TemperatureHandler

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("device_service")

# Load environment variables
load_dotenv()

# Initialize container
container = create_container()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# Routes
@app.route("/health", methods=["GET"])
@inject
def health_check(temperature_handler: TemperatureHandler = Provide["services.temperature_handler"]) -> Any:
    """Health check endpoint

    Returns:
        JSON response with health status information
    """
    status = {
        "status": "healthy",
        "timestamp": "2025-07-19T12:00:00",
        "service": "device-service",
        "version": "1.0.0",
        "dependency_injection": "configured",
        "temperature_handler": "injected" if temperature_handler else "not injected",
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
    # Register container
    container.wire(modules=[__name__])

    # Get host and port from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        # Clean up container resources
        container.shutdown_resources()
