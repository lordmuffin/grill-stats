#!/usr/bin/env python3
"""
Device Service API

This module provides a Flask-based API for the Device Service, which is responsible
for managing ThermoWorks devices and retrieving temperature data.
"""

import json
import logging
import os
import signal
import threading
import time
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlencode

import jwt
import requests
from containers import ApplicationContainer, ServicesContainer
from dependency_injector.wiring import Provide, inject
from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, url_for
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("device_service")

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Create container
container = ApplicationContainer()

from rfx_gateway_client import GatewaySetupStatus, GatewaySetupStep, RFXGatewayError, WiFiNetwork
from rfx_gateway_routes import register_gateway_routes

# Import handlers after container setup to allow wiring
from temperature_handler import TemperatureHandler

from thermoworks_client import DeviceInfo, TemperatureReading, ThermoworksAPIError, ThermoworksAuthenticationError

try:
    # Try to import python-thermoworks-cloud if available
    from thermoworks_cloud import ThermoWorksCloud

    THERMOWORKS_CLOUD_AVAILABLE = True
except ImportError:
    THERMOWORKS_CLOUD_AVAILABLE = False
    logger.warning("python-thermoworks-cloud library not available")

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# JWT configuration from container
JWT_SECRET = container.config.jwt.secret()
JWT_ALGORITHM = container.config.jwt.algorithm()


# Custom JSON encoder that handles dataclasses and datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles dataclasses and datetime objects"""

    def default(self, obj):
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


app.json_encoder = CustomJSONEncoder

# Wire dependencies to the application
from dependency_injector.wiring import wire

wire(
    modules=[__name__, "temperature_handler", "rfx_gateway_routes"],
    packages=[
        "thermoworks_client",
        "rfx_gateway_client",
        "device_manager",
    ],
    container=container,
)

# Get service instances from container
device_manager = container.services.device_manager()
redis_client = container.services.redis_client()
thermoworks_client = container.services.thermoworks_client()
rfx_gateway_client = container.services.rfx_gateway_client()

# Get telemetry instances from container
otel_tracer = container.telemetry.tracer()
api_requests_counter = container.telemetry.api_requests_counter(container.telemetry.meter())
device_temperature_gauge = container.telemetry.device_temperature_gauge(container.telemetry.meter())
request_duration = container.telemetry.request_duration(container.telemetry.meter())

from opentelemetry.exporter.prometheus import PrometheusMetricReader

# Instrument Flask app with OpenTelemetry
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
Psycopg2Instrumentor().instrument()
RedisInstrumentor().instrument()

# Create temperature handler
temperature_handler = TemperatureHandler(redis_client)
thermoworks_client._handle_temperature_readings = temperature_handler.handle_temperature_readings


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


# Error handlers
@app.errorhandler(400)
def bad_request(error: Any) -> Tuple[Any, int]:
    """Handle 400 Bad Request errors"""
    return jsonify(error_response("Bad Request", 400)), 400


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
@inject
def health_check(
    thermoworks_client=Provide[ServicesContainer.thermoworks_client],
    redis_client=Provide[ServicesContainer.redis_client],
) -> Any:
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
@inject
def auth_thermoworks(thermoworks_client=Provide[ServicesContainer.thermoworks_client]) -> Any:
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
@inject
def auth_thermoworks_callback(thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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
@inject
def auth_thermoworks_status(thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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
@inject
def auth_thermoworks_refresh(thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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
@inject
def get_devices(
    thermoworks_client=Provide[ServicesContainer.thermoworks_client],
    device_manager=Provide[ServicesContainer.device_manager],
) -> Any:
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
@inject
def get_device(device_id, thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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


@app.route("/api/devices/<device_id>/temperature", methods=["GET"])
@inject
def get_device_temperature(
    device_id,
    thermoworks_client=Provide[ServicesContainer.thermoworks_client],
    redis_client=Provide[ServicesContainer.redis_client],
):
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
@inject
def get_device_history(device_id, thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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
@inject
def discover_devices(thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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
@inject
def get_device_health(device_id, thermoworks_client=Provide[ServicesContainer.thermoworks_client]):
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


@app.route("/api/sync", methods=["POST"])
@jwt_required
@inject
def sync(
    thermoworks_client=Provide[ServicesContainer.thermoworks_client],
    device_manager=Provide[ServicesContainer.device_manager],
    temperature_handler=Provide[TemperatureHandler],
):
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
        },
        "servers": [
            {
                "url": "/",
                "description": "Current server",
            },
        ],
        "paths": {
            # Swagger paths omitted for brevity
        },
    }
    # Add all your swagger paths here
    return jsonify(swagger)


# Register the RFX Gateway routes
register_gateway_routes(app)


# Create the temperature handler module
@app.before_request
def create_temperature_handler():
    """Create the temperature handler if it doesn't exist"""
    if not hasattr(app, "temperature_handler"):
        app.temperature_handler = TemperatureHandler(redis_client)
        thermoworks_client._handle_temperature_readings = app.temperature_handler.handle_temperature_readings


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
