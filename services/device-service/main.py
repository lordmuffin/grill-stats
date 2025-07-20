#!/usr/bin/env python3
"""
Device Service API

This module provides a Flask-based API for the Device Service, which is responsible
for managing ThermoWorks devices and retrieving temperature data.
"""

import datetime
import json
import logging
import os
import signal
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlencode

import jwt
import psycopg2
import redis

# Import dependency injection container
from containers import ApplicationContainer, create_container
from dependency_injector.wiring import Provide, inject
from device_manager import DeviceManager
from dotenv import load_dotenv
from flask import Flask, Response, abort, g, jsonify, redirect, render_template_string, request, url_for
from flask_cors import CORS

# OpenTelemetry imports
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.metrics import Counter, Histogram, ObservableGauge
from opentelemetry.sdk.metrics import Meter, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import Tracer, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from psycopg2.extras import RealDictCursor

# Try to import rfx_gateway modules
try:
    from rfx_gateway_client import GatewaySetupStatus, GatewaySetupStep, RFXGatewayClient, RFXGatewayError, WiFiNetwork
    from rfx_gateway_routes import register_gateway_routes

    RFX_GATEWAY_AVAILABLE = True
except ImportError:
    print("WARNING: RFX Gateway modules not available, skipping gateway initialization")
    RFX_GATEWAY_AVAILABLE = False
    GatewaySetupStatus = None
    GatewaySetupStep = None
    RFXGatewayClient = None
    RFXGatewayError = None
    WiFiNetwork = None
    register_gateway_routes = None

from thermoworks_client import (
    DeviceInfo,
    TemperatureReading,
    ThermoworksAPIError,
    ThermoworksAuthenticationError,
    ThermoworksClient,
    ThermoworksConnectionError,
)

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("device_service")

try:
    # Try to import python-thermoworks-cloud if available
    from thermoworks_cloud import ThermoWorksCloud

    THERMOWORKS_CLOUD_AVAILABLE = True
except ImportError:
    THERMOWORKS_CLOUD_AVAILABLE = False
    logger.warning("python-thermoworks-cloud library not available")

# Load environment variables
load_dotenv()


# OpenTelemetry configuration
def configure_opentelemetry() -> Tuple[Tracer, Meter, Counter, ObservableGauge, Histogram]:
    """Configure OpenTelemetry instrumentation

    Returns:
        Tuple containing:
        - tracer: The OpenTelemetry tracer for creating spans
        - meter: The OpenTelemetry meter for creating metrics
        - api_requests_counter: Counter for tracking API requests
        - device_temperature_gauge: Gauge for tracking device temperatures
        - request_duration: Histogram for tracking request durations
    """
    # Create a resource to identify this service
    resource = Resource.create({SERVICE_NAME: "device-service"})

    # Configure tracing
    trace_provider = TracerProvider(resource=resource)
    # Export to console for development (would use Jaeger, Zipkin, or OTLP in production)
    trace_processor = BatchSpanProcessor(ConsoleSpanExporter())
    trace_provider.add_span_processor(trace_processor)
    trace.set_tracer_provider(trace_provider)

    # Configure metrics
    prometheus_reader = PrometheusMetricReader()
    metrics_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
    metrics.set_meter_provider(metrics_provider)

    # Get a tracer and meter for this service
    tracer = trace.get_tracer("device.service")
    meter = metrics.get_meter("device.service")

    # Create some common metrics
    api_requests_counter = meter.create_counter(
        name="api_requests",
        description="Count of API requests",
        unit="1",
    )

    device_temperature_gauge = meter.create_observable_gauge(
        name="device_temperature",
        description="Current temperature of devices",
        unit="celsius",
    )

    request_duration = meter.create_histogram(
        name="request_duration",
        description="Duration of API requests",
        unit="ms",
    )

    return tracer, meter, api_requests_counter, device_temperature_gauge, request_duration


# Configure OpenTelemetry
otel_tracer, otel_meter, api_requests_counter, device_temperature_gauge, request_duration = configure_opentelemetry()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Enable webhooks in configuration
app.config["ENABLE_WEBHOOKS"] = os.environ.get("ENABLE_WEBHOOKS", "true").lower() in ("true", "1", "yes")
app.config["WEBHOOK_SECRET"] = os.environ.get("WEBHOOK_SECRET", str(uuid.uuid4()))
app.config["VERIFY_WEBHOOKS"] = os.environ.get("VERIFY_WEBHOOKS", "true").lower() in ("true", "1", "yes")

# Instrument Flask app with OpenTelemetry
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
Psycopg2Instrumentor().instrument()
RedisInstrumentor().instrument()

# JWT configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"

# Rate limiting configuration
RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "100"))  # Requests per window
RATE_LIMIT_WINDOW = int(os.environ.get("API_RATE_LIMIT_WINDOW", "60"))  # Window in seconds
RATE_LIMIT_BY_IP = os.environ.get("API_RATE_LIMIT_BY_IP", "true").lower() in ("true", "1", "yes")

# Store for rate limiting
rate_limit_store = defaultdict(lambda: deque(maxlen=RATE_LIMIT))
rate_limit_lock = threading.RLock()

# Database configuration
DATABASE_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "grill_stats"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# Initialize database manager
try:
    device_manager = DeviceManager(
        db_host=cast(str, DATABASE_CONFIG["host"]),
        db_port=cast(int, DATABASE_CONFIG["port"]),
        db_name=cast(str, DATABASE_CONFIG["database"]),
        db_username=cast(str, DATABASE_CONFIG["user"]),
        db_password=cast(str, DATABASE_CONFIG["password"]),
    )
    logger.info("Database manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database manager: {e}")
    # Create a placeholder for device_manager to handle the case when it's None
    # This will be None at runtime but satisfies the type checker
    device_manager = cast(DeviceManager, None)

# Redis connection for sharing device data with other services
try:
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD", None),
        decode_responses=True,
    )
    # Test connection
    redis_client.ping()
    logger.info("Connected to Redis")
except redis.RedisError as e:
    logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis.")
    redis_client = None

# Initialize ThermoWorks client
thermoworks_client = ThermoworksClient(
    client_id=os.environ.get("THERMOWORKS_CLIENT_ID"),
    client_secret=os.environ.get("THERMOWORKS_CLIENT_SECRET"),
    redirect_uri=os.environ.get("THERMOWORKS_REDIRECT_URI"),
    base_url=os.environ.get("THERMOWORKS_BASE_URL"),
    auth_url=os.environ.get("THERMOWORKS_AUTH_URL"),
    token_storage_path=os.environ.get("TOKEN_STORAGE_PATH"),
    polling_interval=int(os.environ.get("THERMOWORKS_POLLING_INTERVAL", 60)),
    auto_start_polling=False,  # We'll start it after app initialization
)

# Validate required Home Assistant configuration
ha_url = os.environ.get("HOMEASSISTANT_URL", "http://localhost:8123")
ha_token = os.environ.get("HOMEASSISTANT_TOKEN")

if not ha_token:
    logger.error("HOMEASSISTANT_TOKEN environment variable is required but not set")
    logger.error("Please ensure the Home Assistant long-lived access token is configured in secrets")
    raise ValueError("Missing required Home Assistant token configuration")

logger.info(f"Initializing RFX Gateway client with Home Assistant URL: {ha_url}")

# Initialize RFX Gateway client
rfx_gateway_client = RFXGatewayClient(
    thermoworks_client=thermoworks_client,
    ha_url=ha_url,
    ha_token=ha_token,
    max_scan_duration=int(os.environ.get("RFX_SCAN_DURATION", 30)),
    connection_timeout=int(os.environ.get("RFX_CONNECTION_TIMEOUT", 15)),
    setup_timeout=int(os.environ.get("RFX_SETUP_TIMEOUT", 300)),
)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles dataclasses and datetime objects"""

    def default(self, obj):
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


app.json_encoder = CustomJSONEncoder


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and extract user information

    Args:
        token: JWT token string

    Returns:
        Dictionary with user payload if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def jwt_required(f: Any) -> Any:
    """Decorator for JWT authentication

    Args:
        f: The function to decorate

    Returns:
        Decorated function that requires JWT authentication
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify(error_response("No token provided", 401)), 401

        if token.startswith("Bearer "):
            token = token[7:]

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify(error_response("Invalid or expired token", 401)), 401

        request.current_user = payload
        return f(*args, **kwargs)

    return decorated_function


def get_current_user_id() -> Optional[str]:
    """Get current user ID from request context

    Returns:
        User ID string if available in the request, None otherwise
    """
    if hasattr(request, "current_user") and request.current_user:
        return request.current_user.get("user_id")
    return None


class TemperatureHandler:
    """Handler for temperature readings from the ThermoWorks client"""

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        self.redis_client = redis_client

    def handle_temperature_readings(self, device: DeviceInfo, readings: List[TemperatureReading]) -> None:
        """
        Handle temperature readings from a device

        Args:
            device: Device information
            readings: List of temperature readings
        """
        logger.info(f"Received {len(readings)} temperature readings for device {device.device_id}")

        # Publish to Redis if available
        if self.redis_client:
            try:
                # Publish each reading to a device-specific channel
                for reading in readings:
                    channel = f"temperature:{device.device_id}:{reading.probe_id}"
                    message = json.dumps(reading.to_dict())
                    self.redis_client.publish(channel, message)

                    # Also store the latest reading in a key for easy retrieval
                    key = f"temperature:latest:{device.device_id}:{reading.probe_id}"
                    self.redis_client.set(key, message)
                    self.redis_client.expire(key, 3600)  # Expire after 1 hour

                logger.debug(f"Published temperature readings to Redis for device {device.device_id}")
            except redis.RedisError as e:
                logger.error(f"Failed to publish temperature readings to Redis: {e}")


# Create temperature handler and monkey-patch the client's handler method
temperature_handler = TemperatureHandler(redis_client)
thermoworks_client._handle_temperature_readings = temperature_handler.handle_temperature_readings


# Register a shutdown handler to clean up resources
def shutdown_handler(signum: int, frame: Any) -> None:
    """Handler for shutdown signals

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info("Received shutdown signal, cleaning up resources...")
    thermoworks_client.stop_polling()
    # Give it a moment to clean up
    time.sleep(1)
    logger.info("Cleanup complete, exiting...")
    exit(0)


# Register the shutdown handler for common signals
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


# Make sure to clean up RFX Gateway client resources on shutdown
def exit_handler() -> None:
    """Clean up resources when the application exits"""
    try:
        # Note: This will raise mypy error for 'cleanup' attribute
        # We can ignore this specific error as the method exists at runtime
        rfx_gateway_client.cleanup()  # type: ignore
    except Exception as e:
        logger.error(f"Error cleaning up RFX Gateway client: {e}")


import atexit

atexit.register(exit_handler)


# Try to authenticate with client credentials if available
try:
    if thermoworks_client.client_id and thermoworks_client.client_secret:
        if not thermoworks_client.token:
            logger.info("No token found, attempting client credentials authentication...")
            thermoworks_client.authenticate_with_client_credentials()

        # Start polling if authenticated
        if thermoworks_client.token:
            thermoworks_client.start_polling()
            logger.info("ThermoWorks client authenticated and polling started")
        else:
            logger.warning("Failed to authenticate with client credentials")
    else:
        logger.warning("ThermoWorks client ID or secret not configured, authentication will be required")
except Exception as e:
    logger.error(f"Error during ThermoWorks client initialization: {e}")


# API response helpers
def success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """
    Create a success response

    Args:
        data: Optional data to include in the response
        message: Optional success message

    Returns:
        Dictionary with status, message, and optional data
    """
    response = {
        "status": "success",
        "message": message,
    }

    if data is not None:
        response["data"] = data

    return response


def error_response(message: str, status_code: int = 400, details: Any = None) -> Dict[str, Any]:
    """
    Create an error response

    Args:
        message: Error message
        status_code: HTTP status code
        details: Optional error details

    Returns:
        Dictionary with status, message, status_code, and optional details
    """
    response = {
        "status": "error",
        "message": message,
        "status_code": status_code,
    }

    if details is not None:
        response["details"] = details

    return response


# Rate limiting decorator
def rate_limit(f):
    """Rate limiting decorator for API endpoints"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        with rate_limit_lock:
            now = time.time()
            time_limit = now - RATE_LIMIT_WINDOW

            # Determine client identifier (IP or user ID)
            if RATE_LIMIT_BY_IP:
                client_id = request.remote_addr
            else:
                client_id = get_current_user_id() or request.remote_addr

            # Clean up old requests
            client_requests = rate_limit_store[client_id]
            while client_requests and client_requests[0] < time_limit:
                client_requests.popleft()

            # Check if rate limit is exceeded
            if len(client_requests) >= RATE_LIMIT:
                # Add rate limit headers
                response = jsonify(error_response("Rate limit exceeded", 429))
                response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(client_requests[0] + RATE_LIMIT_WINDOW))
                response.headers["Retry-After"] = str(int(client_requests[0] + RATE_LIMIT_WINDOW - now))
                return response, 429

            # Record request time
            client_requests.append(now)

            # Add rate limit headers to the request context for later use
            g.rate_limit = {
                "limit": RATE_LIMIT,
                "remaining": RATE_LIMIT - len(client_requests),
                "reset": int(now + RATE_LIMIT_WINDOW),
            }

            # Track API request with client ID
            api_requests_counter.add(
                1,
                {
                    "endpoint": request.path,
                    "method": request.method,
                    "client_id": client_id[:16] if len(client_id) > 16 else client_id,  # Truncate long IDs
                },
            )

            return f(*args, **kwargs)

    return decorated_function


# Response interceptor to add rate limit headers
@app.after_request
def add_rate_limit_headers(response):
    """Add rate limit headers to the response"""
    if hasattr(g, "rate_limit"):
        response.headers["X-RateLimit-Limit"] = str(g.rate_limit["limit"])
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit["remaining"])
        response.headers["X-RateLimit-Reset"] = str(g.rate_limit["reset"])
    return response


# Error handlers
@app.errorhandler(400)
def bad_request(error: Any) -> Tuple[Any, int]:
    """Handle 400 Bad Request errors"""
    return jsonify(error_response("Bad Request", 400)), 400


@app.errorhandler(429)
def too_many_requests(error: Any) -> Tuple[Any, int]:
    """Handle 429 Too Many Requests errors"""
    return jsonify(error_response("Rate limit exceeded", 429)), 429


@app.errorhandler(401)
def unauthorized(error: Any) -> Tuple[Any, int]:
    """Handle 401 Unauthorized errors"""
    return jsonify(error_response("Unauthorized", 401)), 401


@app.errorhandler(403)
def forbidden(error: Any) -> Tuple[Any, int]:
    """Handle 403 Forbidden errors"""
    return jsonify(error_response("Forbidden", 403)), 403


@app.errorhandler(404)
def not_found(error: Any) -> Tuple[Any, int]:
    """Handle 404 Not Found errors"""
    return jsonify(error_response("Not Found", 404)), 404


@app.errorhandler(500)
def internal_server_error(error: Any) -> Tuple[Any, int]:
    """Handle 500 Internal Server Error errors"""
    return jsonify(error_response("Internal Server Error", 500)), 500


# Routes
@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint

    Returns:
        JSON response with health status information
    """
    with otel_tracer.start_as_current_span("health_check"):
        # Track API request
        api_requests_counter.add(1, {"endpoint": "/health", "method": "GET"})

        status = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "service": "device-service",
            "version": "1.0.0",
            "telemetry": {"opentelemetry": "enabled", "tracing": True, "metrics": True},
        }

        # Add ThermoWorks client status if available
        if thermoworks_client:
            status["thermoworks_client"] = {
                "connected": thermoworks_client.connection_state["connected"],
                "authenticated": thermoworks_client.token is not None,
                "polling_active": bool(thermoworks_client._polling_thread and thermoworks_client._polling_thread.is_alive()),
            }

        # Add Redis status if available
        if redis_client:
            try:
                redis_client.ping()
                status["redis"] = {"connected": True}
            except redis.RedisError:
                status["redis"] = {"connected": False}

        return jsonify(status)


@app.route("/metrics", methods=["GET"])
def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint"""
    return Response(PrometheusMetricReader.get_metrics_as_text(), mimetype="text/plain")


@app.route("/api/auth/thermoworks", methods=["GET"])
def auth_thermoworks() -> Any:
    """
    Start the OAuth2 authentication flow for ThermoWorks

    Returns:
        JSON with authorization URL or a redirect response
    """
    try:
        # Generate a state parameter for CSRF protection
        state = request.args.get("state")

        # Generate the authorization URL
        auth_url, state = thermoworks_client.generate_authorization_url(state=state)

        # Check if the client wants a redirect or JSON response
        if request.args.get("redirect", "false").lower() == "true":
            return redirect(auth_url)

        return jsonify(
            success_response(
                {
                    "authorization_url": auth_url,
                    "state": state,
                }
            )
        )
    except Exception as e:
        logger.error(f"Error generating authorization URL: {e}")
        return (
            jsonify(error_response(f"Error generating authorization URL: {str(e)}", 500)),
            500,
        )


@app.route("/api/auth/thermoworks/callback", methods=["GET"])
def auth_thermoworks_callback():
    """
    Handle the OAuth2 callback from ThermoWorks

    Returns:
        Redirect to the frontend or JSON response
    """
    try:
        # Get the authorization code and state from the request
        code = request.args.get("code")
        state = request.args.get("state")

        if not code:
            return jsonify(error_response("No authorization code provided", 400)), 400

        # Exchange the code for an access token
        token = thermoworks_client.exchange_code_for_token(code, state=state)

        # Start polling if not already started
        thermoworks_client.start_polling()

        # Check if the client wants a redirect or JSON response
        redirect_uri = request.args.get("redirect_uri")
        if redirect_uri:
            # Build the redirect URL with success parameters
            params = {
                "status": "success",
                "message": "Successfully authenticated with ThermoWorks",
            }
            redirect_url = f"{redirect_uri}?{urlencode(params)}"
            return redirect(redirect_url)

        return jsonify(
            success_response(
                {
                    "token_type": token.token_type,
                    "expires_in": token.expires_in,
                    "scope": token.scope,
                },
                "Successfully authenticated with ThermoWorks",
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error: {e}")

        # Check if the client wants a redirect or JSON response
        redirect_uri = request.args.get("redirect_uri")
        if redirect_uri:
            # Build the redirect URL with error parameters
            params = {
                "status": "error",
                "message": f"Authentication failed: {str(e)}",
            }
            redirect_url = f"{redirect_uri}?{urlencode(params)}"
            return redirect(redirect_url)

        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except Exception as e:
        logger.error(f"Error during authentication callback: {e}")

        # Check if the client wants a redirect or JSON response
        redirect_uri = request.args.get("redirect_uri")
        if redirect_uri:
            # Build the redirect URL with error parameters
            params = {
                "status": "error",
                "message": f"Error during authentication: {str(e)}",
            }
            redirect_url = f"{redirect_uri}?{urlencode(params)}"
            return redirect(redirect_url)

        return (
            jsonify(error_response(f"Error during authentication: {str(e)}", 500)),
            500,
        )


@app.route("/api/auth/thermoworks/status", methods=["GET"])
def auth_thermoworks_status():
    """
    Get the current ThermoWorks authentication status

    Returns:
        JSON with authentication status
    """
    try:
        status = thermoworks_client.get_connection_status()
        return jsonify(success_response(status))
    except Exception as e:
        logger.error(f"Error getting authentication status: {e}")
        return (
            jsonify(error_response(f"Error getting authentication status: {str(e)}", 500)),
            500,
        )


@app.route("/api/auth/thermoworks/refresh", methods=["POST"])
def auth_thermoworks_refresh():
    """
    Force a refresh of the ThermoWorks authentication token

    Returns:
        JSON with refresh status
    """
    try:
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        if not thermoworks_client.token.refresh_token:
            # Try client credentials instead
            token = thermoworks_client.authenticate_with_client_credentials()
        else:
            # Refresh the token
            token = thermoworks_client.refresh_token()

        return jsonify(
            success_response(
                {
                    "token_type": token.token_type,
                    "expires_in": token.expires_in,
                    "scope": token.scope,
                },
                "Successfully refreshed authentication token",
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error during token refresh: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        return (
            jsonify(error_response(f"Error during token refresh: {str(e)}", 500)),
            500,
        )


@app.route("/api/devices", methods=["GET"])
@jwt_required
@rate_limit
def get_devices() -> Any:
    """
    Get all devices for the authenticated user

    Returns:
        JSON with list of devices
    """
    with otel_tracer.start_as_current_span("get_devices") as span:
        start_time = time.time()
        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": "/api/devices", "method": "GET"})

            user_id = get_current_user_id()
            if not user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("User ID not found", 401)), 401

            span.set_attribute("user_id", user_id)

            # Get force_refresh parameter
            force_refresh = request.args.get("force_refresh", "false").lower() == "true"
            span.set_attribute("force_refresh", force_refresh)

            # Get devices from database (user-specific)
            db_devices = []
            with otel_tracer.start_as_current_span("get_devices_from_database") as db_span:
                if device_manager:
                    db_devices = device_manager.get_devices(active_only=True, user_id=user_id)
                    db_span.set_attribute("device_count", len(db_devices))
                    span.set_attribute("db_device_count", len(db_devices))
                else:
                    db_span.set_attribute("error", True)
                    db_span.set_attribute("error.message", "Device manager not available")

            # Get devices from ThermoWorks Cloud API if available and authenticated
            cloud_devices = []
            if thermoworks_client.token and (force_refresh or not db_devices):
                with otel_tracer.start_as_current_span("get_devices_from_cloud") as cloud_span:
                    try:
                        cloud_devices = thermoworks_client.get_devices(force_refresh=force_refresh)
                        cloud_span.set_attribute("device_count", len(cloud_devices))
                        span.set_attribute("cloud_device_count", len(cloud_devices))

                        # Sync cloud devices to database with user association
                        if device_manager:
                            with otel_tracer.start_as_current_span("sync_cloud_devices_to_db") as sync_span:
                                sync_span.set_attribute("device_count", len(cloud_devices))

                                for device in cloud_devices:
                                    device_data = {
                                        "device_id": device.device_id,
                                        "name": device.name,
                                        "device_type": "thermoworks",
                                        "user_id": user_id,
                                        "configuration": {
                                            "model": device.model,
                                            "firmware_version": device.firmware_version,
                                            "probes": device.probes,
                                        },
                                    }
                                    device_manager.register_device(device_data)

                                    # Update device health
                                    health_data = {
                                        "battery_level": device.battery_level,
                                        "signal_strength": device.signal_strength,
                                        "last_seen": device.last_seen,
                                        "status": "online" if device.is_online else "offline",
                                    }
                                    device_manager.update_device_health(device.device_id, health_data)

                                # Refresh database devices after sync
                                db_devices = device_manager.get_devices(active_only=True, user_id=user_id)
                                sync_span.set_attribute("updated_db_count", len(db_devices))

                    except Exception as e:
                        logger.warning(f"Failed to sync devices from ThermoWorks Cloud: {e}")
                        cloud_span.set_attribute("error", True)
                        cloud_span.set_attribute("error.message", str(e))

            # Combine and format devices
            all_devices = []

            with otel_tracer.start_as_current_span("format_device_data") as format_span:
                # Add database devices with enhanced info
                for device in db_devices:
                    device_info = {
                        "device_id": device["device_id"],
                        "name": device["name"],
                        "device_type": device["device_type"],
                        "model": device.get("configuration", {}).get("model", "Unknown"),
                        "firmware_version": device.get("configuration", {}).get("firmware_version"),
                        "status": "offline",  # Default, will be updated if we have health data
                        "last_seen": None,
                        "battery_level": None,
                        "signal_strength": None,
                        "is_online": False,
                        "probes": device.get("configuration", {}).get("probes", []),
                        "created_at": device["created_at"],
                        "updated_at": device["updated_at"],
                    }

                    # Try to get latest health data
                    if device_manager:
                        try:
                            conn = device_manager.get_connection()
                            with conn.cursor() as cur:
                                cur.execute(
                                    """
                                    SELECT battery_level, signal_strength, last_seen, status
                                    FROM device_health
                                    WHERE device_id = %s
                                    ORDER BY created_at DESC
                                    LIMIT 1
                                """,
                                    (device["device_id"],),
                                )
                                health = cur.fetchone()
                                if health:
                                    device_info["battery_level"] = health[0]
                                    device_info["signal_strength"] = health[1]
                                    device_info["last_seen"] = health[2].isoformat() if health[2] else None
                                    device_info["status"] = health[3] or "offline"
                                    device_info["is_online"] = health[3] == "online"
                            conn.close()
                        except Exception as e:
                            logger.warning(f"Failed to get health data for device {device['device_id']}: {e}")

                    all_devices.append(device_info)

                # Add cloud devices that might not be in database yet
                for device in cloud_devices:
                    if not any(d["device_id"] == device.device_id for d in all_devices):
                        device_info = {
                            "device_id": device.device_id,
                            "name": device.name,
                            "device_type": "thermoworks",
                            "model": device.model,
                            "firmware_version": device.firmware_version,
                            "status": "online" if device.is_online else "offline",
                            "last_seen": device.last_seen,
                            "battery_level": device.battery_level,
                            "signal_strength": device.signal_strength,
                            "is_online": device.is_online,
                            "probes": device.probes,
                            "created_at": None,
                            "updated_at": None,
                        }
                        all_devices.append(device_info)

                format_span.set_attribute("total_device_count", len(all_devices))

            # Calculate response time
            duration_ms = (time.time() - start_time) * 1000
            request_duration.record(duration_ms, {"endpoint": "/api/devices", "device_count": len(all_devices)})

            # Set final span attributes
            span.set_attribute("total_device_count", len(all_devices))
            span.set_attribute("data_source", "database" if db_devices else "cloud" if cloud_devices else "none")

            return jsonify(
                success_response(
                    {
                        "devices": all_devices,
                        "count": len(all_devices),
                        "source": ("database" if db_devices else "cloud" if cloud_devices else "none"),
                    }
                )
            )
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            return jsonify(error_response(f"Error getting devices: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>", methods=["GET"])
@rate_limit
def get_device(device_id):
    """
    Get a specific device

    Args:
        device_id: Device ID

    Returns:
        JSON with device details
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Get device
        device = thermoworks_client.get_device(device_id)

        # Enrich with database information if available
        if device_manager:
            try:
                db_device = device_manager.get_device(device_id)
                if db_device:
                    # Add database-specific fields
                    device_data = device.to_dict() if hasattr(device, "to_dict") else device
                    device_data["user_id"] = db_device.get("user_id")
                    device_data["configuration"] = db_device.get("configuration", {})
                    device_data["created_at"] = db_device.get("created_at")
                    device_data["updated_at"] = db_device.get("updated_at")
                    device = device_data
            except Exception as e:
                logger.warning(f"Failed to get device from database: {e}")

        return jsonify(
            success_response(
                {
                    "device": device,
                }
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting device {device_id}: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting device {device_id}: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except ValueError as e:
        logger.error(f"Device {device_id} not found: {e}")
        return jsonify(error_response(f"Device not found: {str(e)}", 404)), 404
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {e}")
        return jsonify(error_response(f"Error getting device: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>", methods=["PUT"])
@jwt_required
@rate_limit
def update_device(device_id):
    """
    Update a specific device

    Args:
        device_id: Device ID

    Returns:
        JSON with updated device details
    """
    with otel_tracer.start_as_current_span("update_device") as span:
        span.set_attribute("device_id", device_id)

        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": f"/api/devices/{device_id}", "method": "PUT"})

            # Ensure authenticated
            if not thermoworks_client.token:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("Not authenticated", 401)), 401

            # Get user ID from JWT
            user_id = get_current_user_id()
            if not user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("User ID not found", 401)), 401

            span.set_attribute("user_id", user_id)

            # Get request data
            data = request.json
            if not data:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "invalid_request")
                return jsonify(error_response("No data provided", 400)), 400

            # Validate request data
            if "name" not in data and "configuration" not in data:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "invalid_request")
                return jsonify(error_response("At least one of 'name' or 'configuration' must be provided", 400)), 400

            # Check if device exists in database
            if not device_manager:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "database_error")
                return jsonify(error_response("Database not available", 500)), 500

            # Fetch device from database
            db_device = device_manager.get_device(device_id)
            if not db_device:
                # Try to get from ThermoWorks API
                try:
                    cloud_device = thermoworks_client.get_device(device_id)
                    # Register device in database with user association
                    device_data = {
                        "device_id": cloud_device.device_id,
                        "name": cloud_device.name,
                        "device_type": "thermoworks",
                        "user_id": user_id,
                        "configuration": {
                            "model": cloud_device.model,
                            "firmware_version": cloud_device.firmware_version,
                            "probes": cloud_device.probes,
                        },
                    }
                    device_manager.register_device(device_data)
                    db_device = device_manager.get_device(device_id)
                except Exception as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    logger.error(f"Device {device_id} not found in database or ThermoWorks API: {e}")
                    return jsonify(error_response(f"Device not found: {str(e)}", 404)), 404

            # Check user authorization for device
            if db_device.get("user_id") != user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authorization_error")
                return jsonify(error_response("Not authorized to update this device", 403)), 403

            # Update device in database
            update_data = {}

            # Only update fields that were provided
            if "name" in data:
                update_data["name"] = data["name"]
                span.set_attribute("update.name", True)

            # Update configuration if provided
            if "configuration" in data:
                # Merge existing configuration with new configuration
                existing_config = db_device.get("configuration", {})
                updated_config = {**existing_config, **data["configuration"]}
                update_data["configuration"] = updated_config
                span.set_attribute("update.configuration", True)

            # Add metadata
            update_data["updated_at"] = datetime.datetime.now().isoformat()

            # Perform the update
            updated_device = device_manager.update_device(device_id, update_data)
            span.set_attribute("update.success", True)

            # Get the updated device from database
            db_device = device_manager.get_device(device_id)

            # Add audit log for the update
            try:
                audit_data = {
                    "action": "update_device",
                    "device_id": device_id,
                    "user_id": user_id,
                    "changes": update_data,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                device_manager.add_audit_log(audit_data)
            except Exception as e:
                logger.warning(f"Failed to add audit log: {e}")

            return jsonify(
                success_response(
                    {
                        "device": db_device,
                        "updated_at": update_data["updated_at"],
                    },
                    "Device updated successfully",
                )
            )

        except ValueError as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "value_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Value error updating device {device_id}: {e}")
            return jsonify(error_response(f"Value error: {str(e)}", 400)), 400
        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Error updating device {device_id}: {e}")
            return jsonify(error_response(f"Error updating device: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/temperature", methods=["GET"])
@rate_limit
def get_device_temperature(device_id):
    """
    Get current temperature readings for a device

    Args:
        device_id: Device ID

    Returns:
        JSON with temperature readings
    """
    # Create a span for this request
    with otel_tracer.start_as_current_span(f"get_device_temperature_{device_id}") as span:
        start_time = time.time()
        try:
            # Add span attributes for context
            span.set_attribute("device_id", device_id)

            # Track API request
            api_requests_counter.add(
                1, {"endpoint": "/api/devices/{device_id}/temperature", "method": "GET", "device_id": device_id}
            )

            # Ensure authenticated
            if not thermoworks_client.token:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("Not authenticated", 401)), 401

            # Get probe_id parameter
            probe_id = request.args.get("probe_id")
            span.set_attribute("probe_id", probe_id if probe_id else "all")

            # Add a nested span for cache checking
            with otel_tracer.start_as_current_span("check_redis_cache") as cache_span:
                cache_span.set_attribute("cache_type", "redis")

                # Check Redis for cached data if available
                if redis_client and not request.args.get("force_refresh", "false").lower() == "true":
                    try:
                        # Try to get the latest reading from Redis
                        if probe_id:
                            key = f"temperature:latest:{device_id}:{probe_id}"
                            cached_data = redis_client.get(key)
                            if cached_data:
                                reading = json.loads(cached_data)

                                # Record cache hit
                                cache_span.set_attribute("cache_hit", True)
                                span.set_attribute("data_source", "cache")

                                # Record request duration
                                duration_ms = (time.time() - start_time) * 1000
                                request_duration.record(
                                    duration_ms,
                                    {
                                        "endpoint": "/api/devices/{device_id}/temperature",
                                        "source": "cache",
                                        "device_id": device_id,
                                    },
                                )

                                return jsonify(
                                    success_response(
                                        {
                                            "readings": [reading],
                                            "count": 1,
                                            "source": "cache",
                                        }
                                    )
                                )
                        else:
                            # Pattern match to get all probes for this device
                            keys = redis_client.keys(f"temperature:latest:{device_id}:*")
                            if keys:
                                readings = []
                                for key in keys:
                                    cached_data = redis_client.get(key)
                                    if cached_data:
                                        readings.append(json.loads(cached_data))
                                if readings:
                                    # Record cache hit
                                    cache_span.set_attribute("cache_hit", True)
                                    span.set_attribute("data_source", "cache")
                                    cache_span.set_attribute("reading_count", len(readings))

                                    # Record request duration
                                    duration_ms = (time.time() - start_time) * 1000
                                    request_duration.record(
                                        duration_ms,
                                        {
                                            "endpoint": "/api/devices/{device_id}/temperature",
                                            "source": "cache",
                                            "device_id": device_id,
                                        },
                                    )

                                    return jsonify(
                                        success_response(
                                            {
                                                "readings": readings,
                                                "count": len(readings),
                                                "source": "cache",
                                            }
                                        )
                                    )

                        # If we get here, it's a cache miss
                        cache_span.set_attribute("cache_hit", False)

                    except redis.RedisError as e:
                        logger.warning(f"Failed to get temperature from Redis: {e}")
                        cache_span.set_attribute("error", True)
                        cache_span.set_attribute("error.message", str(e))

            # Add a nested span for API call
            with otel_tracer.start_as_current_span("thermoworks_api_call") as api_span:
                api_span.set_attribute("api_endpoint", "get_device_temperature")
                api_span.set_attribute("device_id", device_id)

                # Get temperature from API
                readings = thermoworks_client.get_device_temperature(device_id, probe_id=probe_id)
                api_span.set_attribute("reading_count", len(readings))
                span.set_attribute("data_source", "api")

                # Record metrics for temperatures if readings exist
                if readings:
                    for reading in readings:
                        # Record current temperature as a gauge metric
                        attributes = {"device_id": device_id, "probe_id": reading.probe_id, "unit": reading.unit}
                        # Note: In a real implementation, we would register a callback for the observable gauge
                        # Here we're simulating it with a direct value for demonstration
                        span.set_attribute(f"temperature.{reading.probe_id}", reading.temperature)

            # Record request duration
            duration_ms = (time.time() - start_time) * 1000
            request_duration.record(
                duration_ms, {"endpoint": "/api/devices/{device_id}/temperature", "source": "api", "device_id": device_id}
            )

            return jsonify(
                success_response(
                    {
                        "readings": readings,
                        "count": len(readings),
                        "source": "api",
                    }
                )
            )
        except ThermoworksAuthenticationError as e:
            logger.error(f"Authentication error getting temperature for device {device_id}: {e}")
            span.set_attribute("error", True)
            span.set_attribute("error.type", "authentication_error")
            span.set_attribute("error.message", str(e))
            return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
        except ThermoworksAPIError as e:
            logger.error(f"API error getting temperature for device {device_id}: {e}")
            span.set_attribute("error", True)
            span.set_attribute("error.type", "api_error")
            span.set_attribute("error.message", str(e))
            return jsonify(error_response(f"API error: {str(e)}", 400)), 400
        except Exception as e:
            logger.error(f"Error getting temperature for device {device_id}: {e}")
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            return jsonify(error_response(f"Error getting temperature: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/history", methods=["GET"])
@rate_limit
def get_device_history(device_id):
    """
    Get historical temperature readings for a device

    Args:
        device_id: Device ID

    Returns:
        JSON with historical temperature readings
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Get query parameters
        probe_id = request.args.get("probe_id")
        start_time = request.args.get("start_time") or request.args.get("start")
        end_time = request.args.get("end_time") or request.args.get("end")
        limit = request.args.get("limit", 100, type=int)

        # Get history from API
        readings = thermoworks_client.get_device_history(
            device_id,
            probe_id=probe_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        return jsonify(
            success_response(
                {
                    "history": readings,
                    "count": len(readings),
                    "query": {
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "limit": limit,
                    },
                }
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting history for device {device_id}: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting history for device {device_id}: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error getting history for device {device_id}: {e}")
        return jsonify(error_response(f"Error getting history: {str(e)}", 500)), 500


@app.route("/api/devices/discover", methods=["POST"])
@rate_limit
def discover_devices():
    """
    Discover ThermoWorks devices

    Returns:
        JSON with discovered devices
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Discover devices (force refresh)
        devices = thermoworks_client.get_devices(force_refresh=True)

        return jsonify(
            success_response(
                {
                    "devices": devices,
                    "count": len(devices),
                }
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error discovering devices: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error discovering devices: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error discovering devices: {e}")
        return jsonify(error_response(f"Error discovering devices: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/health", methods=["GET"])
@rate_limit
def get_device_health(device_id):
    """
    Get the health status of a device

    Args:
        device_id: Device ID

    Returns:
        JSON with device health status
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Get device
        device = thermoworks_client.get_device(device_id)

        # Extract health information
        health = {
            "battery_level": device.battery_level,
            "signal_strength": device.signal_strength,
            "status": "online" if device.is_online else "offline",
            "last_seen": device.last_seen,
        }

        return jsonify(
            success_response(
                {
                    "device_id": device_id,
                    "health": health,
                }
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting device health {device_id}: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting device health {device_id}: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except ValueError as e:
        logger.error(f"Device {device_id} not found: {e}")
        return jsonify(error_response(f"Device not found: {str(e)}", 404)), 404
    except Exception as e:
        logger.error(f"Error getting device health {device_id}: {e}")
        return (
            jsonify(error_response(f"Error getting device health: {str(e)}", 500)),
            500,
        )


@app.route("/api/devices/<device_id>", methods=["DELETE"])
@jwt_required
@rate_limit
def delete_device(device_id):
    """Delete a specific device (soft delete)

    Args:
        device_id: Device ID

    Returns:
        JSON response indicating success or failure
    """
    with otel_tracer.start_as_current_span("delete_device") as span:
        span.set_attribute("device_id", device_id)

        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": f"/api/devices/{device_id}", "method": "DELETE"})

            # Get user ID from JWT
            user_id = get_current_user_id()
            if not user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("User ID not found", 401)), 401

            span.set_attribute("user_id", user_id)

            # Check if device exists in database
            if not device_manager:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "database_error")
                return jsonify(error_response("Database not available", 500)), 500

            # Get device from database
            db_device = device_manager.get_device(device_id)
            if not db_device:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "not_found")
                return jsonify(error_response(f"Device {device_id} not found", 404)), 404

            # Check if user is authorized to delete the device
            if db_device.get("user_id") != user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authorization_error")
                return jsonify(error_response("Not authorized to delete this device", 403)), 403

            # Soft delete the device
            result = device_manager.delete_device(device_id)
            if not result:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "delete_failed")
                return jsonify(error_response(f"Failed to delete device {device_id}", 500)), 500

            # Add audit log
            try:
                audit_data = {
                    "action": "delete_device",
                    "device_id": device_id,
                    "user_id": user_id,
                    "changes": {"active": False},
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                device_manager.add_audit_log(audit_data)
            except Exception as e:
                logger.warning(f"Failed to add audit log: {e}")

            span.set_attribute("delete.success", True)

            return jsonify(
                success_response(
                    {
                        "device_id": device_id,
                        "deleted": True,
                        "timestamp": datetime.datetime.now().isoformat(),
                    },
                    "Device deleted successfully",
                )
            )

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Error deleting device {device_id}: {e}")
            return jsonify(error_response(f"Error deleting device: {str(e)}", 500)), 500
    """
    Get the health status of a device

    Args:
        device_id: Device ID

    Returns:
        JSON with device health status
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Get device
        device = thermoworks_client.get_device(device_id)

        # Extract health information
        health = {
            "battery_level": device.battery_level,
            "signal_strength": device.signal_strength,
            "status": "online" if device.is_online else "offline",
            "last_seen": device.last_seen,
        }

        return jsonify(
            success_response(
                {
                    "device_id": device_id,
                    "health": health,
                }
            )
        )
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting device health {device_id}: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting device health {device_id}: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except ValueError as e:
        logger.error(f"Device {device_id} not found: {e}")
        return jsonify(error_response(f"Device not found: {str(e)}", 404)), 404
    except Exception as e:
        logger.error(f"Error getting device health {device_id}: {e}")
        return (
            jsonify(error_response(f"Error getting device health: {str(e)}", 500)),
            500,
        )


@app.route("/api/devices/<device_id>/probes", methods=["GET"])
@jwt_required
@rate_limit
def get_device_probes(device_id):
    """Get all probes for a specific device

    Args:
        device_id: Device ID

    Returns:
        JSON with device probes information
    """
    with otel_tracer.start_as_current_span("get_device_probes") as span:
        span.set_attribute("device_id", device_id)

        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": f"/api/devices/{device_id}/probes", "method": "GET"})

            # Ensure authenticated
            if not thermoworks_client.token:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("Not authenticated", 401)), 401

            # Get user ID from JWT
            user_id = get_current_user_id()
            if not user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("User ID not found", 401)), 401

            span.set_attribute("user_id", user_id)

            # Get device from API
            try:
                device = thermoworks_client.get_device(device_id)
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                logger.error(f"Error getting device from ThermoWorks API: {e}")

                # Try database fallback if API call fails
                if device_manager:
                    db_device = device_manager.get_device(device_id)
                    if not db_device:
                        return jsonify(error_response(f"Device {device_id} not found", 404)), 404

                    # Check user authorization
                    if db_device.get("user_id") != user_id:
                        return jsonify(error_response("Not authorized to access this device", 403)), 403

                    # Get probes from device configuration
                    configuration = db_device.get("configuration", {})
                    probes = configuration.get("probes", [])

                    return jsonify(
                        success_response(
                            {
                                "device_id": device_id,
                                "probes": probes,
                                "count": len(probes),
                                "source": "database",
                            }
                        )
                    )
                else:
                    return jsonify(error_response(f"Device {device_id} not found", 404)), 404

            # Extract probes information
            probes = device.probes if hasattr(device, "probes") else []

            # If we got the device from API, but no probes information, check database
            if not probes and device_manager:
                db_device = device_manager.get_device(device_id)
                if db_device:
                    configuration = db_device.get("configuration", {})
                    db_probes = configuration.get("probes", [])
                    if db_probes:
                        probes = db_probes

            # For cleaner response, convert any DeviceProbe objects to dicts
            formatted_probes = []
            for probe in probes:
                if hasattr(probe, "to_dict"):
                    formatted_probes.append(probe.to_dict())
                elif isinstance(probe, dict):
                    formatted_probes.append(probe)
                else:
                    # Basic conversion of unknown object type
                    formatted_probes.append({"id": str(probe), "name": f"Probe {probe}"})

            return jsonify(
                success_response(
                    {
                        "device_id": device_id,
                        "probes": formatted_probes,
                        "count": len(formatted_probes),
                        "source": "api",
                    }
                )
            )

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Error getting probes for device {device_id}: {e}")
            return jsonify(error_response(f"Error getting probes: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/probes/<probe_id>", methods=["GET"])
@rate_limit
def get_device_probe(device_id, probe_id):
    """Get specific probe information for a device

    Args:
        device_id: Device ID
        probe_id: Probe ID

    Returns:
        JSON with probe information
    """
    with otel_tracer.start_as_current_span("get_device_probe") as span:
        span.set_attribute("device_id", device_id)
        span.set_attribute("probe_id", probe_id)

        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": f"/api/devices/{device_id}/probes/{probe_id}", "method": "GET"})

            # Ensure authenticated
            if not thermoworks_client.token:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("Not authenticated", 401)), 401

            # Get device from API
            try:
                device = thermoworks_client.get_device(device_id)
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                logger.error(f"Error getting device from ThermoWorks API: {e}")
                return jsonify(error_response(f"Device {device_id} not found", 404)), 404

            # Find the specific probe
            probes = device.probes if hasattr(device, "probes") else []
            target_probe = None

            for probe in probes:
                probe_id_value = probe.get("id") if isinstance(probe, dict) else getattr(probe, "id", None)
                if str(probe_id_value) == probe_id:
                    target_probe = probe
                    break

            if not target_probe:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "not_found")
                return jsonify(error_response(f"Probe {probe_id} not found for device {device_id}", 404)), 404

            # Format probe data
            if hasattr(target_probe, "to_dict"):
                probe_data = target_probe.to_dict()
            elif isinstance(target_probe, dict):
                probe_data = target_probe
            else:
                # Basic conversion of unknown object type
                probe_data = {"id": probe_id, "name": f"Probe {probe_id}"}

            # Get current temperature for this probe if available
            temperature = None
            try:
                readings = thermoworks_client.get_device_temperature(device_id, probe_id=probe_id)
                if readings and len(readings) > 0:
                    temperature = readings[0].to_dict() if hasattr(readings[0], "to_dict") else readings[0]
            except Exception as e:
                logger.warning(f"Failed to get temperature for probe {probe_id}: {e}")

            # Include temperature in response if available
            if temperature:
                probe_data["current_temperature"] = temperature

            return jsonify(
                success_response(
                    {
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "probe": probe_data,
                    }
                )
            )

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Error getting probe {probe_id} for device {device_id}: {e}")
            return jsonify(error_response(f"Error getting probe: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/probes/<probe_id>", methods=["PUT"])
@jwt_required
@rate_limit
def update_device_probe(device_id, probe_id):
    """Update probe configuration

    Args:
        device_id: Device ID
        probe_id: Probe ID

    Returns:
        JSON with updated probe information
    """
    with otel_tracer.start_as_current_span("update_device_probe") as span:
        span.set_attribute("device_id", device_id)
        span.set_attribute("probe_id", probe_id)

        try:
            # Track API request
            api_requests_counter.add(1, {"endpoint": f"/api/devices/{device_id}/probes/{probe_id}", "method": "PUT"})

            # Get user ID from JWT
            user_id = get_current_user_id()
            if not user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authentication_error")
                return jsonify(error_response("User ID not found", 401)), 401

            span.set_attribute("user_id", user_id)

            # Get request data
            data = request.json
            if not data:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "invalid_request")
                return jsonify(error_response("No data provided", 400)), 400

            # Check if device exists in database
            if not device_manager:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "database_error")
                return jsonify(error_response("Database not available", 500)), 500

            # Get device from database
            db_device = device_manager.get_device(device_id)
            if not db_device:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "not_found")
                return jsonify(error_response(f"Device {device_id} not found", 404)), 404

            # Check user authorization
            if db_device.get("user_id") != user_id:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "authorization_error")
                return jsonify(error_response("Not authorized to update this device", 403)), 403

            # Get current configuration
            configuration = db_device.get("configuration", {})
            probes = configuration.get("probes", [])

            # Find the probe to update
            probe_index = None
            for i, probe in enumerate(probes):
                if str(probe.get("id")) == probe_id:
                    probe_index = i
                    break

            # If probe not found, add it
            if probe_index is None:
                # Create new probe entry
                new_probe = {
                    "id": probe_id,
                    "name": data.get("name", f"Probe {probe_id}"),
                }

                # Add additional fields if provided
                for field in ["type", "color", "target_temp", "high_alarm", "low_alarm"]:
                    if field in data:
                        new_probe[field] = data[field]

                # Add to probes list
                probes.append(new_probe)
            else:
                # Update existing probe
                for field in ["name", "type", "color", "target_temp", "high_alarm", "low_alarm"]:
                    if field in data:
                        probes[probe_index][field] = data[field]

            # Update configuration
            configuration["probes"] = probes

            # Update device in database
            update_data = {"configuration": configuration, "updated_at": datetime.datetime.now().isoformat()}

            device_manager.update_device(device_id, update_data)

            # Add audit log
            try:
                audit_data = {
                    "action": "update_probe",
                    "device_id": device_id,
                    "user_id": user_id,
                    "changes": {"probe_id": probe_id, "update": data},
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                device_manager.add_audit_log(audit_data)
            except Exception as e:
                logger.warning(f"Failed to add audit log: {e}")

            # Get updated probe
            updated_probe = None
            for probe in probes:
                if str(probe.get("id")) == probe_id:
                    updated_probe = probe
                    break

            return jsonify(
                success_response(
                    {
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "probe": updated_probe,
                        "updated_at": update_data["updated_at"],
                    },
                    "Probe updated successfully",
                )
            )

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.type", "unexpected_error")
            span.set_attribute("error.message", str(e))
            logger.error(f"Error updating probe {probe_id} for device {device_id}: {e}")
            return jsonify(error_response(f"Error updating probe: {str(e)}", 500)), 500


@app.route("/api/sync", methods=["POST"])
@jwt_required
@rate_limit
def sync():
    """
    Manually trigger a data sync for the authenticated user

    Returns:
        JSON with sync status
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify(error_response("User ID not found", 401)), 401

        # Ensure authenticated with ThermoWorks
        if not thermoworks_client.token:
            return (
                jsonify(error_response("Not authenticated with ThermoWorks", 401)),
                401,
            )

        # Create a background thread to sync data
        def sync_data():
            try:
                # Get devices from ThermoWorks Cloud
                devices = thermoworks_client.get_devices(force_refresh=True)
                logger.info(f"Synced {len(devices)} devices from ThermoWorks Cloud")

                # Sync devices to database
                if device_manager:
                    for device in devices:
                        device_data = {
                            "device_id": device.device_id,
                            "name": device.name,
                            "device_type": "thermoworks",
                            "user_id": user_id,
                            "configuration": {
                                "model": device.model,
                                "firmware_version": device.firmware_version,
                                "probes": device.probes,
                            },
                        }
                        device_manager.register_device(device_data)

                        # Update device health
                        health_data = {
                            "battery_level": device.battery_level,
                            "signal_strength": device.signal_strength,
                            "last_seen": device.last_seen,
                            "status": "online" if device.is_online else "offline",
                        }
                        device_manager.update_device_health(device.device_id, health_data)

                        # Get temperature for each device
                        try:
                            readings = thermoworks_client.get_device_temperature(device.device_id)
                            logger.info(f"Synced {len(readings)} temperature readings for device {device.device_id}")

                            # Handle readings
                            temperature_handler.handle_temperature_readings(device, readings)
                        except Exception as e:
                            logger.error(f"Error syncing temperature for device {device.device_id}: {e}")

                logger.info(f"Sync completed for user {user_id}")

            except Exception as e:
                logger.error(f"Error during sync: {e}")

        # Start sync thread
        sync_thread = threading.Thread(target=sync_data)
        sync_thread.daemon = True
        sync_thread.start()

        return jsonify(
            success_response(
                {
                    "message": "Sync started in background",
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            )
        )
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        return jsonify(error_response(f"Error during sync: {str(e)}", 500)), 500


# OpenAPI documentation
SWAGGER_UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Device Service API Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="//unpkg.com/swagger-ui-dist@3/swagger-ui.css" />
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="//unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
    <script>
        const ui = SwaggerUIBundle({
            url: "{{ url_for('swagger_json') }}",
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            defaultModelsExpandDepth: -1,
            docExpansion: "list",
        })
    </script>
</body>
</html>
"""


@app.route("/api/docs", methods=["GET"])
def swagger_ui():
    """OpenAPI documentation UI"""
    return render_template_string(SWAGGER_UI_TEMPLATE)


@app.route("/api/docs/swagger.json", methods=["GET"])
def swagger_json():
    """OpenAPI documentation in JSON format"""
    swagger = {
        "openapi": "3.0.0",
        "info": {
            "title": "Device Service API",
            "description": "API for managing ThermoWorks devices and retrieving temperature data",
            "version": "1.0.0",
            "contact": {
                "name": "Device Service Team",
                "email": "support@grillstats.com",
                "url": "https://grillstats.com/docs",
            },
        },
        "servers": [
            {
                "url": "/",
                "description": "Current server",
            },
        ],
        "tags": [
            {"name": "health", "description": "Health check endpoints"},
            {"name": "auth", "description": "Authentication endpoints"},
            {"name": "devices", "description": "Device management endpoints"},
            {"name": "temperature", "description": "Temperature data endpoints"},
            {"name": "probes", "description": "Probe management endpoints"},
            {"name": "webhooks", "description": "Webhook endpoints for real-time updates"},
        ],
        "security": [{"bearerAuth": []}],
        "paths": {
            "/health": {
                "get": {
                    "tags": ["health"],
                    "summary": "Health check",
                    "description": "Check the health of the service",
                    "operationId": "healthCheck",
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "timestamp": {
                                                "type": "string",
                                                "format": "date-time",
                                            },
                                            "service": {"type": "string"},
                                            "version": {"type": "string"},
                                            "telemetry": {
                                                "type": "object",
                                                "properties": {
                                                    "opentelemetry": {"type": "string"},
                                                    "tracing": {"type": "boolean"},
                                                    "metrics": {"type": "boolean"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "/metrics": {
                "get": {
                    "tags": ["health"],
                    "summary": "Prometheus metrics",
                    "description": "Get Prometheus metrics for monitoring",
                    "operationId": "getPrometheusMetrics",
                    "responses": {
                        "200": {
                            "description": "Prometheus metrics in text format",
                            "content": {"text/plain": {"schema": {"type": "string"}}},
                        }
                    },
                }
            },
            "/api/auth/thermoworks": {
                "get": {
                    "summary": "Start OAuth2 flow",
                    "description": "Get an authorization URL for ThermoWorks OAuth2 flow",
                    "parameters": [
                        {
                            "name": "state",
                            "in": "query",
                            "description": "Optional state parameter for CSRF protection",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "redirect",
                            "in": "query",
                            "description": "Whether to redirect to the authorization URL",
                            "schema": {"type": "boolean"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Authorization URL generated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "authorization_url": {"type": "string"},
                                                    "state": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "302": {
                            "description": "Redirect to authorization URL",
                        },
                        "500": {
                            "description": "Error generating authorization URL",
                        },
                    },
                },
            },
            "/api/auth/thermoworks/callback": {
                "get": {
                    "summary": "OAuth2 callback",
                    "description": "Handle the OAuth2 callback from ThermoWorks",
                    "parameters": [
                        {
                            "name": "code",
                            "in": "query",
                            "description": "Authorization code",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "state",
                            "in": "query",
                            "description": "State parameter for CSRF protection",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "redirect_uri",
                            "in": "query",
                            "description": "URI to redirect to after authentication",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Authentication successful",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "token_type": {"type": "string"},
                                                    "expires_in": {"type": "integer"},
                                                    "scope": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "302": {
                            "description": "Redirect to the provided redirect URI",
                        },
                        "400": {
                            "description": "No authorization code provided",
                        },
                        "401": {
                            "description": "Authentication failed",
                        },
                        "500": {
                            "description": "Error during authentication",
                        },
                    },
                },
            },
            "/api/auth/thermoworks/status": {
                "get": {
                    "summary": "Authentication status",
                    "description": "Get the current ThermoWorks authentication status",
                    "responses": {
                        "200": {
                            "description": "Authentication status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "connected": {"type": "boolean"},
                                                    "authenticated": {"type": "boolean"},
                                                    "polling_active": {"type": "boolean"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "500": {
                            "description": "Error getting authentication status",
                        },
                    },
                },
            },
            "/api/auth/thermoworks/refresh": {
                "post": {
                    "summary": "Refresh authentication token",
                    "description": "Force a refresh of the ThermoWorks authentication token",
                    "responses": {
                        "200": {
                            "description": "Token refreshed successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "token_type": {"type": "string"},
                                                    "expires_in": {"type": "integer"},
                                                    "scope": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated or authentication failed",
                        },
                        "500": {
                            "description": "Error during token refresh",
                        },
                    },
                },
            },
            "/api/devices": {
                "get": {
                    "summary": "Get all devices",
                    "description": "Get a list of all discovered devices",
                    "parameters": [
                        {
                            "name": "force_refresh",
                            "in": "query",
                            "description": "Whether to force a refresh from the API",
                            "schema": {"type": "boolean"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "List of devices",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "devices": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "device_id": {"type": "string"},
                                                                "name": {"type": "string"},
                                                                "model": {"type": "string"},
                                                            },
                                                        },
                                                    },
                                                    "count": {"type": "integer"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "500": {
                            "description": "Error getting devices",
                        },
                    },
                },
            },
            "/api/devices/{device_id}": {
                "get": {
                    "summary": "Get device details",
                    "description": "Get details for a specific device",
                    "parameters": [
                        {
                            "name": "device_id",
                            "in": "path",
                            "description": "Device ID",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Device details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "device": {
                                                        "type": "object",
                                                        "properties": {
                                                            "device_id": {"type": "string"},
                                                            "name": {"type": "string"},
                                                            "model": {"type": "string"},
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "404": {
                            "description": "Device not found",
                        },
                        "500": {
                            "description": "Error getting device",
                        },
                    },
                },
            },
            "/api/devices/{device_id}/temperature": {
                "get": {
                    "summary": "Get device temperature",
                    "description": "Get current temperature readings for a device",
                    "parameters": [
                        {
                            "name": "device_id",
                            "in": "path",
                            "description": "Device ID",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "probe_id",
                            "in": "query",
                            "description": "Probe ID",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "force_refresh",
                            "in": "query",
                            "description": "Whether to force a refresh from the API",
                            "schema": {"type": "boolean"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Temperature readings",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "readings": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "device_id": {"type": "string"},
                                                                "probe_id": {"type": "string"},
                                                                "temperature": {"type": "number"},
                                                                "unit": {"type": "string"},
                                                                "timestamp": {
                                                                    "type": "string",
                                                                    "format": "date-time",
                                                                },
                                                            },
                                                        },
                                                    },
                                                    "count": {"type": "integer"},
                                                    "source": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "500": {
                            "description": "Error getting temperature",
                        },
                    },
                },
            },
            "/api/devices/{device_id}/history": {
                "get": {
                    "summary": "Get temperature history",
                    "description": "Get historical temperature readings for a device",
                    "parameters": [
                        {
                            "name": "device_id",
                            "in": "path",
                            "description": "Device ID",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "probe_id",
                            "in": "query",
                            "description": "Probe ID",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "start_time",
                            "in": "query",
                            "description": "Start time in ISO format",
                            "schema": {"type": "string", "format": "date-time"},
                        },
                        {
                            "name": "end_time",
                            "in": "query",
                            "description": "End time in ISO format",
                            "schema": {"type": "string", "format": "date-time"},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "Maximum number of readings to return",
                            "schema": {"type": "integer", "default": 100},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Historical temperature readings",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "history": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "device_id": {"type": "string"},
                                                                "probe_id": {"type": "string"},
                                                                "temperature": {"type": "number"},
                                                                "unit": {"type": "string"},
                                                                "timestamp": {
                                                                    "type": "string",
                                                                    "format": "date-time",
                                                                },
                                                            },
                                                        },
                                                    },
                                                    "count": {"type": "integer"},
                                                    "query": {
                                                        "type": "object",
                                                        "properties": {
                                                            "device_id": {"type": "string"},
                                                            "probe_id": {"type": "string"},
                                                            "start_time": {"type": "string"},
                                                            "end_time": {"type": "string"},
                                                            "limit": {"type": "integer"},
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "500": {
                            "description": "Error getting history",
                        },
                    },
                },
            },
            "/api/devices/discover": {
                "post": {
                    "summary": "Discover devices",
                    "description": "Discover ThermoWorks devices",
                    "responses": {
                        "200": {
                            "description": "Discovered devices",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "devices": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "device_id": {"type": "string"},
                                                                "name": {"type": "string"},
                                                                "model": {"type": "string"},
                                                            },
                                                        },
                                                    },
                                                    "count": {"type": "integer"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "500": {
                            "description": "Error discovering devices",
                        },
                    },
                },
            },
            "/api/devices/{device_id}/health": {
                "get": {
                    "summary": "Get device health",
                    "description": "Get the health status of a device",
                    "parameters": [
                        {
                            "name": "device_id",
                            "in": "path",
                            "description": "Device ID",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Device health status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "device_id": {"type": "string"},
                                                    "health": {
                                                        "type": "object",
                                                        "properties": {
                                                            "battery_level": {"type": "integer"},
                                                            "signal_strength": {"type": "integer"},
                                                            "status": {"type": "string"},
                                                            "last_seen": {
                                                                "type": "string",
                                                                "format": "date-time",
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "404": {
                            "description": "Device not found",
                        },
                        "500": {
                            "description": "Error getting device health",
                        },
                    },
                },
            },
            "/api/sync": {
                "post": {
                    "summary": "Sync data",
                    "description": "Manually trigger a data sync",
                    "responses": {
                        "200": {
                            "description": "Sync started",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "message": {"type": "string"},
                                                    "timestamp": {
                                                        "type": "string",
                                                        "format": "date-time",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "401": {
                            "description": "Not authenticated",
                        },
                        "500": {
                            "description": "Error during sync",
                        },
                    },
                },
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT Authorization header using the Bearer scheme",
                }
            },
            "schemas": {
                "DeviceInfo": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "name": {"type": "string"},
                        "model": {"type": "string"},
                        "firmware_version": {"type": "string"},
                        "last_seen": {"type": "string", "format": "date-time"},
                        "battery_level": {"type": "integer"},
                        "signal_strength": {"type": "integer"},
                        "is_online": {"type": "boolean"},
                        "probes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                "TemperatureReading": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "probe_id": {"type": "string"},
                        "temperature": {"type": "number"},
                        "unit": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "battery_level": {"type": "integer"},
                        "signal_strength": {"type": "integer"},
                    },
                },
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success"]},
                        "message": {"type": "string"},
                        "data": {"type": "object"},
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["error"]},
                        "message": {"type": "string"},
                        "status_code": {"type": "integer"},
                        "details": {"type": "object"},
                    },
                },
            },
        },
    }

    return jsonify(swagger)


# Register the RFX Gateway routes if available
if RFX_GATEWAY_AVAILABLE and register_gateway_routes is not None:
    try:
        register_gateway_routes(app, rfx_gateway_client, thermoworks_client)
    except Exception as e:
        logger.warning(f"Failed to register RFX Gateway routes: {e}")

if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        # Ensure we clean up resources when the app exits
        thermoworks_client.stop_polling()
        rfx_gateway_client.cleanup()
