import json
import os
from datetime import datetime, timedelta

import jwt
import structlog
from flask import Blueprint, jsonify, request
from opentelemetry import trace
from pydantic import ValidationError
from src.database.timescale_manager import TimescaleManager
from src.models.temperature_models import TemperatureQuery, TemperatureReading

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)


def get_user_id_from_jwt(token):
    """Extract user ID from JWT token."""
    try:
        if not token:
            return None

        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # Decode JWT token
        secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key")
        decoded_token = jwt.decode(token, secret_key, algorithms=["HS256"])
        return decoded_token.get("user_id")
    except Exception as e:
        logger.warning("Failed to decode JWT token", error=str(e))
        return None


def get_user_devices(user_id):
    """Get list of device IDs that belong to the user."""
    try:
        # This would typically query the user-device mapping table
        # For now, we'll return a simple check or assume all devices belong to the user
        # In a real implementation, this would query the PostgreSQL database
        # to get the user's devices from the user_devices table
        return None  # Return None to indicate we should use the device_id from request
    except Exception as e:
        logger.error("Error getting user devices", error=str(e))
        return []


def register_routes(app, timescale_manager: TimescaleManager):
    """Register all API routes with the Flask app."""

    # Health check endpoint
    @app.route("/health")
    def health_check():
        """Health check endpoint for the historical data service."""
        health_status = {
            "service": "historical-data-service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "features": {
                "device_history": True,
                "user_authentication": True,
                "data_aggregation": True,
                "time_series_storage": True,
            },
            "dependencies": {},
        }

        # Check TimescaleDB connection
        try:
            if timescale_manager and timescale_manager.health_check():
                health_status["dependencies"]["timescaledb"] = "healthy"
            else:
                health_status["dependencies"]["timescaledb"] = "unhealthy"
        except Exception as e:
            error_msg = str(e).lower()
            expected_errors = [
                "connection refused",
                "name resolution",
                "temporary failure",
                "no such host",
                "could not translate host name",
                "connection reset",
            ]

            if any(expected in error_msg for expected in expected_errors):
                health_status["dependencies"]["timescaledb"] = "unavailable"
            else:
                health_status["dependencies"]["timescaledb"] = "error"

        # Determine overall status
        dep_statuses = list(health_status["dependencies"].values())

        if all(status == "healthy" for status in dep_statuses):
            health_status["overall_status"] = "healthy"
            return jsonify(health_status), 200
        elif all(status in ["healthy", "unavailable"] for status in dep_statuses):
            health_status["overall_status"] = "degraded"
            health_status["message"] = "Service operational, some dependencies unavailable (expected in test environment)"
            logger.warning("Dependencies unavailable (expected in test)")
            return jsonify(health_status), 200
        else:
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = "Critical dependency errors detected"
            logger.error("Health check failed with critical errors")
            return jsonify(health_status), 500

    # Temperature data ingestion endpoint
    @app.route("/api/temperature", methods=["POST"])
    def store_temperature_reading():
        """Store a single temperature reading."""
        with tracer.start_as_current_span("store_temperature_reading"):
            try:
                # Validate the incoming data
                try:
                    data = request.json
                    reading = TemperatureReading(**data)
                except ValidationError as e:
                    logger.warning("Invalid temperature reading data", error=str(e))
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Invalid temperature reading data",
                                "details": str(e),
                            }
                        ),
                        400,
                    )

                # Store the reading
                success = timescale_manager.store_temperature_reading(reading.dict())

                if success:
                    logger.info(
                        "Temperature reading stored successfully",
                        device_id=reading.device_id,
                        probe_id=reading.probe_id,
                    )
                    return jsonify(
                        {
                            "status": "success",
                            "message": "Temperature reading stored successfully",
                        }
                    )
                else:
                    logger.error("Failed to store temperature reading")
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Failed to store temperature reading",
                            }
                        ),
                        500,
                    )

            except Exception as e:
                logger.error("Error processing temperature reading", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    # Batch temperature data ingestion endpoint
    @app.route("/api/temperature/batch", methods=["POST"])
    def store_batch_temperature_readings():
        """Store multiple temperature readings at once."""
        with tracer.start_as_current_span("store_batch_temperature_readings"):
            try:
                readings = request.json.get("readings", [])

                if not readings:
                    return (
                        jsonify({"status": "error", "message": "No readings provided"}),
                        400,
                    )

                # Validate readings
                validated_readings = []
                for reading_data in readings:
                    try:
                        reading = TemperatureReading(**reading_data)
                        validated_readings.append(reading.dict())
                    except ValidationError as e:
                        logger.warning(
                            "Invalid temperature reading",
                            reading=reading_data,
                            error=str(e),
                        )
                        continue

                if not validated_readings:
                    return (
                        jsonify({"status": "error", "message": "No valid readings provided"}),
                        400,
                    )

                # Store readings
                stored_count = timescale_manager.store_batch_temperature_readings(validated_readings)

                logger.info("Batch temperature data stored", count=stored_count)
                return jsonify(
                    {
                        "status": "success",
                        "stored_count": stored_count,
                        "total_count": len(readings),
                    }
                )

            except Exception as e:
                logger.error("Failed to store batch temperature data", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    # Temperature history retrieval endpoint
    @app.route("/api/temperature/history", methods=["GET"])
    def get_temperature_history():
        """Get historical temperature data based on query parameters."""
        with tracer.start_as_current_span("get_temperature_history"):
            try:
                # Parse query parameters
                device_id = request.args.get("device_id")
                probe_id = request.args.get("probe_id")
                grill_id = request.args.get("grill_id")
                start_time_str = request.args.get("start_time")
                end_time_str = request.args.get("end_time")
                aggregation = request.args.get("aggregation", "none")
                interval = request.args.get("interval", "1h")
                limit = request.args.get("limit")

                # Convert limit to integer if provided
                if limit:
                    try:
                        limit = int(limit)
                    except ValueError:
                        limit = None

                # Parse datetime strings
                start_time = None
                end_time = None

                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid start_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to 24 hours ago
                    start_time = datetime.utcnow() - timedelta(hours=24)

                if end_time_str:
                    try:
                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid end_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to now
                    end_time = datetime.utcnow()

                # Validate that at least one identifier is provided
                if not device_id and not probe_id and not grill_id:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "At least one of device_id, probe_id, or grill_id must be provided",
                            }
                        ),
                        400,
                    )

                # Get historical data
                history_data = timescale_manager.get_temperature_history(
                    device_id=device_id,
                    probe_id=probe_id,
                    grill_id=grill_id,
                    start_time=start_time,
                    end_time=end_time,
                    aggregation=aggregation,
                    interval=interval,
                    limit=limit,
                )

                logger.info(
                    "Temperature history retrieved",
                    count=len(history_data),
                    device_id=device_id,
                    probe_id=probe_id,
                    grill_id=grill_id,
                )

                return jsonify(
                    {
                        "status": "success",
                        "data": history_data,
                        "count": len(history_data),
                        "query": {
                            "device_id": device_id,
                            "probe_id": probe_id,
                            "grill_id": grill_id,
                            "start_time": start_time.isoformat(),
                            "end_time": end_time.isoformat(),
                            "aggregation": aggregation,
                            "interval": interval,
                            "limit": limit,
                        },
                    }
                )

            except Exception as e:
                logger.error("Failed to get temperature history", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    # User-specific device history endpoint
    @app.route("/api/devices/<device_id>/history", methods=["GET"])
    def get_device_history(device_id):
        """Get historical temperature data for a specific device (with user authentication)."""
        with tracer.start_as_current_span("get_device_history"):
            try:
                # Get user ID from JWT token
                auth_header = request.headers.get("Authorization")
                user_id = get_user_id_from_jwt(auth_header)

                if not user_id:
                    return (
                        jsonify({"status": "error", "message": "Authentication required"}),
                        401,
                    )

                # Parse query parameters
                start_time_str = request.args.get("start_time")
                end_time_str = request.args.get("end_time")
                probe_id = request.args.get("probe_id")
                aggregation = request.args.get("aggregation", "none")
                interval = request.args.get("interval", "1m")
                limit = request.args.get("limit")

                # Convert limit to integer if provided
                if limit:
                    try:
                        limit = int(limit)
                    except ValueError:
                        limit = 1000  # Default limit
                else:
                    limit = 1000

                # Parse datetime strings
                start_time = None
                end_time = None

                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid start_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to 24 hours ago
                    start_time = datetime.utcnow() - timedelta(hours=24)

                if end_time_str:
                    try:
                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid end_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to now
                    end_time = datetime.utcnow()

                # Validate time range
                if start_time >= end_time:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Start time must be before end time",
                            }
                        ),
                        400,
                    )

                # Get historical data
                history_data = timescale_manager.get_temperature_history(
                    device_id=device_id,
                    probe_id=probe_id,
                    start_time=start_time,
                    end_time=end_time,
                    aggregation=aggregation,
                    interval=interval,
                    limit=limit,
                )

                # Group data by probe for easier frontend consumption
                probes = {}
                for reading in history_data:
                    probe_key = reading.get("probe_id", "unknown")
                    if probe_key not in probes:
                        probes[probe_key] = {"probe_id": probe_key, "readings": []}
                    probes[probe_key]["readings"].append(
                        {
                            "timestamp": reading["time"],
                            "temperature": reading["temperature"],
                            "unit": reading.get("unit", "F"),
                            "battery_level": reading.get("battery_level"),
                            "signal_strength": reading.get("signal_strength"),
                        }
                    )

                # Convert to list and sort by timestamp
                probe_list = []
                for probe_data in probes.values():
                    probe_data["readings"].sort(key=lambda x: x["timestamp"])
                    probe_list.append(probe_data)

                probe_list.sort(key=lambda x: x["probe_id"])

                logger.info(
                    "Device history retrieved",
                    device_id=device_id,
                    user_id=user_id,
                    probe_count=len(probe_list),
                    total_readings=len(history_data),
                )

                return jsonify(
                    {
                        "status": "success",
                        "data": {
                            "device_id": device_id,
                            "probes": probe_list,
                            "total_readings": len(history_data),
                            "time_range": {
                                "start": start_time.isoformat(),
                                "end": end_time.isoformat(),
                            },
                        },
                    }
                )

            except Exception as e:
                logger.error("Failed to get device history", device_id=device_id, error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    # Temperature statistics endpoint
    @app.route("/api/temperature/statistics", methods=["GET"])
    def get_temperature_statistics():
        """Get temperature statistics based on query parameters."""
        with tracer.start_as_current_span("get_temperature_statistics"):
            try:
                # Parse query parameters
                device_id = request.args.get("device_id")
                probe_id = request.args.get("probe_id")
                grill_id = request.args.get("grill_id")
                start_time_str = request.args.get("start_time")
                end_time_str = request.args.get("end_time")

                # Parse datetime strings
                start_time = None
                end_time = None

                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid start_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to 24 hours ago
                    start_time = datetime.utcnow() - timedelta(hours=24)

                if end_time_str:
                    try:
                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid end_time format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)",
                                }
                            ),
                            400,
                        )
                else:
                    # Default to now
                    end_time = datetime.utcnow()

                # Validate that at least one identifier is provided
                if not device_id and not probe_id and not grill_id:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "At least one of device_id, probe_id, or grill_id must be provided",
                            }
                        ),
                        400,
                    )

                # Get statistics
                stats = timescale_manager.get_temperature_statistics(
                    device_id=device_id,
                    probe_id=probe_id,
                    grill_id=grill_id,
                    start_time=start_time,
                    end_time=end_time,
                )

                logger.info(
                    "Temperature statistics retrieved",
                    device_id=device_id,
                    probe_id=probe_id,
                    grill_id=grill_id,
                )

                return jsonify({"status": "success", "data": stats})

            except Exception as e:
                logger.error("Failed to get temperature statistics", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    # Session management endpoints
    @app.route("/api/sessions", methods=["POST"])
    def create_cooking_session():
        """Create a new cooking session."""
        with tracer.start_as_current_span("create_cooking_session"):
            try:
                # TODO: Implement cooking session creation
                return (
                    jsonify({"status": "error", "message": "Not implemented yet"}),
                    501,
                )
            except Exception as e:
                logger.error("Failed to create cooking session", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/sessions/<session_id>", methods=["GET"])
    def get_cooking_session(session_id):
        """Get details of a specific cooking session."""
        with tracer.start_as_current_span("get_cooking_session"):
            try:
                # TODO: Implement cooking session retrieval
                return (
                    jsonify({"status": "error", "message": "Not implemented yet"}),
                    501,
                )
            except Exception as e:
                logger.error("Failed to get cooking session", session_id=session_id, error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/sessions", methods=["GET"])
    def list_cooking_sessions():
        """List all cooking sessions."""
        with tracer.start_as_current_span("list_cooking_sessions"):
            try:
                # TODO: Implement cooking session listing
                return (
                    jsonify({"status": "error", "message": "Not implemented yet"}),
                    501,
                )
            except Exception as e:
                logger.error("Failed to list cooking sessions", error=str(e))
                return jsonify({"status": "error", "message": str(e)}), 500
