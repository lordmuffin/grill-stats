#!/usr/bin/env python3
"""
Device Service API

This module provides a Flask-based API for the Device Service, which is responsible
for managing ThermoWorks devices and retrieving temperature data.
"""

import os
import json
import logging
import time
import signal
import datetime
import threading
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode

import redis
from flask import Flask, request, jsonify, redirect, url_for, Response, abort, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

from thermoworks_client import (
    ThermoworksClient,
    ThermoworksAPIError,
    ThermoworksAuthenticationError,
    ThermoworksConnectionError,
    DeviceInfo,
    TemperatureReading,
)
from rfx_gateway_client import (
    RFXGatewayClient,
    RFXGatewayError,
    GatewaySetupStep,
    WiFiNetwork,
    GatewaySetupStatus,
)
from rfx_gateway_routes import register_gateway_routes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("device_service")

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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

# Initialize RFX Gateway client
rfx_gateway_client = RFXGatewayClient(
    thermoworks_client=thermoworks_client,
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


class TemperatureHandler:
    """Handler for temperature readings from the ThermoWorks client"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
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
def shutdown_handler(signum, frame):
    """Handler for shutdown signals"""
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
def exit_handler():
    try:
        rfx_gateway_client.cleanup()
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
def bad_request(error):
    return jsonify(error_response("Bad Request", 400)), 400


@app.errorhandler(401)
def unauthorized(error):
    return jsonify(error_response("Unauthorized", 401)), 401


@app.errorhandler(403)
def forbidden(error):
    return jsonify(error_response("Forbidden", 403)), 403


@app.errorhandler(404)
def not_found(error):
    return jsonify(error_response("Not Found", 404)), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify(error_response("Internal Server Error", 500)), 500


# Routes
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "device-service",
        "version": "1.0.0",
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


@app.route("/api/auth/thermoworks", methods=["GET"])
def auth_thermoworks():
    """
    Start the OAuth2 authentication flow for ThermoWorks
    
    Returns:
        JSON with authorization URL
    """
    try:
        # Generate a state parameter for CSRF protection
        state = request.args.get("state")
        
        # Generate the authorization URL
        auth_url, state = thermoworks_client.generate_authorization_url(state=state)
        
        # Check if the client wants a redirect or JSON response
        if request.args.get("redirect", "false").lower() == "true":
            return redirect(auth_url)
            
        return jsonify(success_response({
            "authorization_url": auth_url,
            "state": state,
        }))
    except Exception as e:
        logger.error(f"Error generating authorization URL: {e}")
        return jsonify(error_response(f"Error generating authorization URL: {str(e)}", 500)), 500


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
            
        return jsonify(success_response({
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "scope": token.scope,
        }, "Successfully authenticated with ThermoWorks"))
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
            
        return jsonify(error_response(f"Error during authentication: {str(e)}", 500)), 500


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
        return jsonify(error_response(f"Error getting authentication status: {str(e)}", 500)), 500


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
            
        return jsonify(success_response({
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "scope": token.scope,
        }, "Successfully refreshed authentication token"))
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error during token refresh: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        return jsonify(error_response(f"Error during token refresh: {str(e)}", 500)), 500


@app.route("/api/devices", methods=["GET"])
def get_devices():
    """
    Get all discovered devices
    
    Returns:
        JSON with list of devices
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401
            
        # Get force_refresh parameter
        force_refresh = request.args.get("force_refresh", "false").lower() == "true"
        
        # Get devices
        devices = thermoworks_client.get_devices(force_refresh=force_refresh)
        
        return jsonify(success_response({
            "devices": devices,
            "count": len(devices),
        }))
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting devices: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting devices: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify(error_response(f"Error getting devices: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>", methods=["GET"])
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
        
        return jsonify(success_response({
            "device": device,
        }))
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
def get_device_temperature(device_id):
    """
    Get current temperature readings for a device
    
    Args:
        device_id: Device ID
        
    Returns:
        JSON with temperature readings
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401
            
        # Get probe_id parameter
        probe_id = request.args.get("probe_id")
        
        # Check Redis for cached data if available
        if redis_client and not request.args.get("force_refresh", "false").lower() == "true":
            try:
                # Try to get the latest reading from Redis
                if probe_id:
                    key = f"temperature:latest:{device_id}:{probe_id}"
                    cached_data = redis_client.get(key)
                    if cached_data:
                        reading = json.loads(cached_data)
                        return jsonify(success_response({
                            "readings": [reading],
                            "count": 1,
                            "source": "cache",
                        }))
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
                            return jsonify(success_response({
                                "readings": readings,
                                "count": len(readings),
                                "source": "cache",
                            }))
            except redis.RedisError as e:
                logger.warning(f"Failed to get temperature from Redis: {e}")
        
        # Get temperature from API
        readings = thermoworks_client.get_device_temperature(device_id, probe_id=probe_id)
        
        return jsonify(success_response({
            "readings": readings,
            "count": len(readings),
            "source": "api",
        }))
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error getting temperature for device {device_id}: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
    except ThermoworksAPIError as e:
        logger.error(f"API error getting temperature for device {device_id}: {e}")
        return jsonify(error_response(f"API error: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error getting temperature for device {device_id}: {e}")
        return jsonify(error_response(f"Error getting temperature: {str(e)}", 500)), 500


@app.route("/api/devices/<device_id>/history", methods=["GET"])
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
        
        return jsonify(success_response({
            "history": readings,
            "count": len(readings),
            "query": {
                "device_id": device_id,
                "probe_id": probe_id,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
        }))
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
        
        return jsonify(success_response({
            "devices": devices,
            "count": len(devices),
        }))
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
        
        return jsonify(success_response({
            "device_id": device_id,
            "health": health,
        }))
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
        return jsonify(error_response(f"Error getting device health: {str(e)}", 500)), 500


@app.route("/api/sync", methods=["POST"])
def sync():
    """
    Manually trigger a data sync
    
    Returns:
        JSON with sync status
    """
    try:
        # Ensure authenticated
        if not thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401
            
        # Create a background thread to sync data
        def sync_data():
            try:
                # Get devices
                devices = thermoworks_client.get_devices(force_refresh=True)
                logger.info(f"Synced {len(devices)} devices")
                
                # Get temperature for each device
                for device in devices:
                    try:
                        readings = thermoworks_client.get_device_temperature(device.device_id)
                        logger.info(f"Synced {len(readings)} temperature readings for device {device.device_id}")
                        
                        # Handle readings
                        temperature_handler.handle_temperature_readings(device, readings)
                    except Exception as e:
                        logger.error(f"Error syncing temperature for device {device.device_id}: {e}")
            except Exception as e:
                logger.error(f"Error during sync: {e}")
                
        # Start sync thread
        sync_thread = threading.Thread(target=sync_data)
        sync_thread.daemon = True
        sync_thread.start()
        
        return jsonify(success_response({
            "message": "Sync started in background",
            "timestamp": datetime.datetime.now().isoformat(),
        }))
    except ThermoworksAuthenticationError as e:
        logger.error(f"Authentication error during sync: {e}")
        return jsonify(error_response(f"Authentication failed: {str(e)}", 401)), 401
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
            "/health": {
                "get": {
                    "summary": "Health check",
                    "description": "Check the health of the service",
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "timestamp": {"type": "string", "format": "date-time"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
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
                            "required": true,
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
                            "required": true,
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
                                                                "timestamp": {"type": "string", "format": "date-time"},
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
                            "required": true,
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
                                                                "timestamp": {"type": "string", "format": "date-time"},
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
                            "required": true,
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
                                                            "last_seen": {"type": "string", "format": "date-time"},
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
                                                    "timestamp": {"type": "string", "format": "date-time"},
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


# Register the RFX Gateway routes
register_gateway_routes(app, rfx_gateway_client, thermoworks_client)

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