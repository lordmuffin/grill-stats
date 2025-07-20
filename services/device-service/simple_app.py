#!/usr/bin/env python3
"""
Very simple Flask application with DI to verify the implementation works.
"""

import logging
import os
from typing import Any, Dict

from dependency_injector import containers, providers
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simple service class
class SimpleService:
    def __init__(self, message: str = "Hello, Dependency Injection!"):
        self.message = message

    def get_message(self):
        return self.message


# Define container
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    config.message.from_env("MESSAGE", "Hello, Dependency Injection!")

    service = providers.Singleton(SimpleService, message=config.message)


# Create Flask app
app = Flask(__name__)

# Create and configure container
container = Container()


# Routes
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "dependency_injection": "working"})


@app.route("/message")
def message():
    # Get service from container
    service = container.service()
    return jsonify({"message": service.get_message()})


if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))

    logger.info(f"Starting application on {host}:{port}")
    logger.info(f"Message: {container.service().get_message()}")

    app.run(host=host, port=port)
