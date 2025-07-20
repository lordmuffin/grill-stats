"""
RFX Gateway API Routes

This module defines the API routes for RFX Gateway setup and management.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from rfx_gateway_client import GatewaySetupStep, RFXGatewayClient, RFXGatewayError

# Configure logging
logger = logging.getLogger("rfx_gateway_routes")

# Create blueprint
rfx_gateway_bp = Blueprint("rfx_gateway", __name__, url_prefix="/api/gateways")


def register_gateway_routes(app, rfx_gateway_client: RFXGatewayClient, thermoworks_client: Any) -> None:
    """
    Register RFX Gateway routes with the Flask app

    Args:
        app: Flask app
        rfx_gateway_client: RFX Gateway client
        thermoworks_client: ThermoWorks client
    """
    # Add blueprint to app
    app.register_blueprint(rfx_gateway_bp)

    # Store clients on blueprint for route handlers
    rfx_gateway_bp.rfx_gateway_client = rfx_gateway_client
    rfx_gateway_bp.thermoworks_client = thermoworks_client


# Success response helper
def success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """Create a success response"""
    response = {
        "status": "success",
        "message": message,
    }

    if data is not None:
        response["data"] = data

    return response


# Error response helper
def error_response(message: str, status_code: int = 400, details: Any = None) -> Dict[str, Any]:
    """Create an error response"""
    response = {
        "status": "error",
        "message": message,
        "status_code": status_code,
    }

    if details is not None:
        response["details"] = details

    return response


@rfx_gateway_bp.route("", methods=["GET"])
def get_gateways() -> Any:
    """
    Get all registered RFX Gateways

    Returns:
        JSON list of gateways
    """
    try:
        # Ensure authenticated
        if not rfx_gateway_bp.thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        gateways = rfx_gateway_bp.thermoworks_client.get_gateways()

        return jsonify(success_response({"gateways": gateways, "count": len(gateways)}))
    except Exception as e:
        logger.error(f"Error getting gateways: {e}")
        return jsonify(error_response(f"Error getting gateways: {str(e)}", 500)), 500


@rfx_gateway_bp.route("/<gateway_id>", methods=["GET"])
def get_gateway(gateway_id: str) -> Any:
    """
    Get information for a specific gateway

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with gateway information
    """
    try:
        # Ensure authenticated
        if not rfx_gateway_bp.thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        gateway = rfx_gateway_bp.thermoworks_client.get_gateway_status(gateway_id)

        return jsonify(success_response({"gateway": gateway}))
    except ValueError as e:
        logger.error(f"Gateway {gateway_id} not found: {e}")
        return jsonify(error_response(f"Gateway not found: {str(e)}", 404)), 404
    except Exception as e:
        logger.error(f"Error getting gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error getting gateway: {str(e)}", 500)), 500


@rfx_gateway_bp.route("/discover", methods=["POST"])
def discover_gateways() -> Any:
    """
    Discover nearby RFX Gateways using Bluetooth

    Returns:
        JSON list of discovered gateways
    """
    try:
        # Get optional timeout parameter
        timeout = request.json.get("timeout") if request.json else None

        # Discover gateways
        gateways = rfx_gateway_bp.rfx_gateway_client.discover_gateways(timeout)

        return jsonify(success_response({"gateways": gateways, "count": len(gateways)}))
    except Exception as e:
        logger.error(f"Error discovering gateways: {e}")
        return (
            jsonify(error_response(f"Error discovering gateways: {str(e)}", 500)),
            500,
        )


@rfx_gateway_bp.route("/<gateway_id>/connect", methods=["POST"])
def connect_to_gateway(gateway_id: str) -> Any:
    """
    Connect to an RFX Gateway via Bluetooth

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with connection status
    """
    try:
        # Connect to gateway
        success = rfx_gateway_bp.rfx_gateway_client.connect_to_gateway(gateway_id)

        if success:
            return jsonify(
                success_response(
                    {"connected": True, "gateway_id": gateway_id},
                    "Successfully connected to gateway",
                )
            )
        else:
            return jsonify(error_response("Failed to connect to gateway", 400)), 400
    except RFXGatewayError as e:
        logger.error(f"Error connecting to gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error connecting to gateway: {str(e)}", 400)),
            400,
        )
    except Exception as e:
        logger.error(f"Error connecting to gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error connecting to gateway: {str(e)}", 500)),
            500,
        )


@rfx_gateway_bp.route("/<gateway_id>/wifi/scan", methods=["POST"])
def scan_wifi_networks(gateway_id: str) -> Any:
    """
    Scan for available Wi-Fi networks

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON list of available Wi-Fi networks
    """
    try:
        # Scan for Wi-Fi networks
        networks = rfx_gateway_bp.rfx_gateway_client.scan_wifi_networks(gateway_id)

        return jsonify(
            success_response(
                {
                    "networks": [n.to_dict() for n in networks],
                    "count": len(networks),
                    "gateway_id": gateway_id,
                }
            )
        )
    except RFXGatewayError as e:
        logger.error(f"Error scanning Wi-Fi networks for gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error scanning Wi-Fi networks: {str(e)}", 400)),
            400,
        )
    except Exception as e:
        logger.error(f"Error scanning Wi-Fi networks for gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error scanning Wi-Fi networks: {str(e)}", 500)),
            500,
        )


@rfx_gateway_bp.route("/<gateway_id>/wifi/configure", methods=["POST"])
def configure_wifi(gateway_id: str) -> Any:
    """
    Configure the gateway to connect to a Wi-Fi network

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with configuration status
    """
    try:
        # Get Wi-Fi configuration from request
        if not request.json:
            return jsonify(error_response("Missing required parameters", 400)), 400

        ssid = request.json.get("ssid")
        password = request.json.get("password")
        security_type = request.json.get("security_type")

        if not ssid or not password:
            return jsonify(error_response("SSID and password are required", 400)), 400

        # Configure Wi-Fi
        success = rfx_gateway_bp.rfx_gateway_client.configure_wifi(gateway_id, ssid, password, security_type)

        if success:
            return jsonify(
                success_response(
                    {"configured": True, "gateway_id": gateway_id, "ssid": ssid},
                    "Successfully configured Wi-Fi connection",
                )
            )
        else:
            return (
                jsonify(error_response("Failed to configure Wi-Fi connection", 400)),
                400,
            )
    except RFXGatewayError as e:
        logger.error(f"Error configuring Wi-Fi for gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error configuring Wi-Fi: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error configuring Wi-Fi for gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error configuring Wi-Fi: {str(e)}", 500)), 500


@rfx_gateway_bp.route("/<gateway_id>/link", methods=["POST"])
def link_to_account(gateway_id: str) -> Any:
    """
    Link the gateway to the user's ThermoWorks Cloud account

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with linking status
    """
    try:
        # Ensure authenticated
        if not rfx_gateway_bp.thermoworks_client.token:
            return jsonify(error_response("Not authenticated", 401)), 401

        # Link gateway to account
        success = rfx_gateway_bp.rfx_gateway_client.link_to_thermoworks_account(gateway_id)

        if success:
            return jsonify(
                success_response(
                    {"linked": True, "gateway_id": gateway_id},
                    "Successfully linked gateway to ThermoWorks Cloud account",
                )
            )
        else:
            return (
                jsonify(error_response("Failed to link gateway to ThermoWorks Cloud account", 400)),
                400,
            )
    except RFXGatewayError as e:
        logger.error(f"Error linking gateway {gateway_id} to account: {e}")
        return (
            jsonify(error_response(f"Error linking gateway to account: {str(e)}", 400)),
            400,
        )
    except Exception as e:
        logger.error(f"Error linking gateway {gateway_id} to account: {e}")
        return (
            jsonify(error_response(f"Error linking gateway to account: {str(e)}", 500)),
            500,
        )


@rfx_gateway_bp.route("/<gateway_id>/setup/complete", methods=["POST"])
def complete_setup(gateway_id: str) -> Any:
    """
    Complete the gateway setup process

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with final setup status
    """
    try:
        # Complete setup
        status = rfx_gateway_bp.rfx_gateway_client.complete_setup(gateway_id)

        return jsonify(
            success_response(
                {"setup_complete": True, "gateway_id": gateway_id, "status": status},
                "Gateway setup completed successfully",
            )
        )
    except RFXGatewayError as e:
        logger.error(f"Error completing setup for gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error completing setup: {str(e)}", 400)), 400
    except Exception as e:
        logger.error(f"Error completing setup for gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error completing setup: {str(e)}", 500)), 500


@rfx_gateway_bp.route("/<gateway_id>/setup/status", methods=["GET"])
def get_setup_status(gateway_id: str) -> Any:
    """
    Get the current setup status for a gateway

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with setup status
    """
    try:
        # Get setup status
        status = rfx_gateway_bp.rfx_gateway_client.get_setup_status(gateway_id)

        return jsonify(success_response({"gateway_id": gateway_id, "setup_status": status}))
    except RFXGatewayError as e:
        logger.error(f"Error getting setup status for gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error getting setup status: {str(e)}", 400)),
            400,
        )
    except Exception as e:
        logger.error(f"Error getting setup status for gateway {gateway_id}: {e}")
        return (
            jsonify(error_response(f"Error getting setup status: {str(e)}", 500)),
            500,
        )


@rfx_gateway_bp.route("/<gateway_id>/setup/cancel", methods=["POST"])
def cancel_setup(gateway_id: str) -> Any:
    """
    Cancel an in-progress gateway setup

    Args:
        gateway_id: Gateway ID

    Returns:
        JSON with cancellation status
    """
    try:
        # Cancel setup
        rfx_gateway_bp.rfx_gateway_client.cancel_setup(gateway_id)

        return jsonify(success_response({"cancelled": True, "gateway_id": gateway_id}, "Gateway setup cancelled"))
    except Exception as e:
        logger.error(f"Error cancelling setup for gateway {gateway_id}: {e}")
        return jsonify(error_response(f"Error cancelling setup: {str(e)}", 500)), 500
