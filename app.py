import json
import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy

# Import configuration
from config.config_loader import load_config
from config.env_validator import EnvironmentValidator
from homeassistant_client import HomeAssistantClient
from thermoworks_client import ThermoWorksClient

# Load configuration
Config = load_config()

# Import requests for external API calls
try:
    import requests
except ImportError:
    requests = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log Flask version for debugging
import flask

logger.info(f"Starting application with Flask version: {flask.__version__}")

# Initialize environment validator to check configuration
env_validator = EnvironmentValidator()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Override database settings for local development without docker
if app.config.get("MOCK_MODE") and os.environ.get('LOCAL_DB', 'true').lower() in ('true', '1', 'yes', 'on'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///grill_stats.db'
    logger.info(f"Using SQLite database: {app.config['SQLALCHEMY_DATABASE_URI']}")
else:
    logger.info(f"Using database: {app.config.get('SQLALCHEMY_DATABASE_URI')}")



# Validate critical configuration on startup
def validate_critical_config():
    """Validate critical configuration on startup"""
    critical_errors = []

    # ThermoWorks API Key (required unless in mock mode)
    if not app.config.get("MOCK_MODE") and not app.config.get("THERMOWORKS_API_KEY"):
        critical_errors.append("THERMOWORKS_API_KEY is required unless MOCK_MODE is enabled")

    # Home Assistant URL (required unless in mock mode)
    if not app.config.get("MOCK_MODE") and not app.config.get("HOMEASSISTANT_URL"):
        critical_errors.append("HOMEASSISTANT_URL is required unless MOCK_MODE is enabled")

    # Home Assistant Token (required unless in mock mode)
    if not app.config.get("MOCK_MODE") and not app.config.get("HOMEASSISTANT_TOKEN"):
        critical_errors.append("HOMEASSISTANT_TOKEN is required unless MOCK_MODE is enabled")

    # Secret Key (should not use default in production)
    if os.getenv("FLASK_ENV") == "production" and app.config.get("SECRET_KEY") == "dev-secret-key-change-in-production":
        critical_errors.append("Using default SECRET_KEY in production is not secure")

    # Check if there are any critical errors
    if critical_errors:
        error_message = "\n".join([f"- {error}" for error in critical_errors])
        logger.error(f"Critical configuration errors:\n{error_message}")

        # In production, raise an exception to prevent startup
        if os.getenv("FLASK_ENV") == "production":
            raise ValueError(f"Critical configuration errors:\n{error_message}")
        else:
            logger.warning("Running with configuration warnings (allowed in development)")


# Run validation
validate_critical_config()

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize User model
from models.user import User

user_manager = User(db)

# Initialize TemperatureAlert model
from models.temperature_alert import AlertType, TemperatureAlert

alert_manager = TemperatureAlert(db)

# Initialize Alert Monitor (will be started after app initialization)
from services.alert_monitor import AlertMonitor

alert_monitor = None

# Initialize Device model (will use existing device service for now)
try:
    from models.device import Device

    device_manager = Device(db)
except ImportError:
    logger.warning("Device model not found, will use device service instead")
    device_manager = None

# Initialize GrillingSession model and SessionTracker
from models.grilling_session import GrillingSession

session_manager = GrillingSession(db)

from services.session_tracker import SessionTracker

session_tracker = SessionTracker(session_manager, mock_mode=app.config.get("MOCK_MODE", False))

# Initialize auth routes
from auth.routes import init_auth_routes

init_auth_routes(app, login_manager, user_manager, bcrypt)

# Initialize API clients
thermoworks_client = ThermoWorksClient(
    api_key=app.config["THERMOWORKS_API_KEY"],
    mock_mode=app.config.get("MOCK_MODE", False),
)

# Initialize HomeAssistant client with mock mode if enabled
homeassistant_client = HomeAssistantClient(
    base_url=app.config.get("HOMEASSISTANT_URL"),
    access_token=app.config.get("HOMEASSISTANT_TOKEN"),
    mock_mode=app.config.get("MOCK_MODE", False),
)

scheduler = BackgroundScheduler()


@app.teardown_appcontext
def close_db(error):
    """Close database connections at the end of each request"""
    try:
        db.session.close()
    except Exception as e:
        logger.warning(f"Error closing database session: {e}")


@app.teardown_request
def teardown_request(exception):
    """Cleanup after each request"""
    try:
        if exception:
            db.session.rollback()
        db.session.close()
    except Exception as e:
        logger.warning(f"Error in teardown_request: {e}")


def sync_temperature_data():
    logger.info("Starting temperature data sync")

    try:
        # Use application context to ensure database connections are properly handled
        with app.app_context():
            try:
                devices = thermoworks_client.get_devices()

                for device in devices:
                    device_id = device.get("id")
                    device_name = device.get("name", f"thermoworks_{device_id}")

                    temperature_data = thermoworks_client.get_temperature_data(device_id)

                    if temperature_data and temperature_data.get("temperature"):
                        sensor_name = f"thermoworks_{device_name.lower().replace(' ', '_')}"

                        attributes = {
                            "device_id": device_id,
                            "last_updated": temperature_data.get("timestamp"),
                            "battery_level": temperature_data.get("battery_level"),
                            "signal_strength": temperature_data.get("signal_strength"),
                        }

                        # Update Home Assistant sensor
                        success = homeassistant_client.create_sensor(
                            sensor_name=sensor_name,
                            state=temperature_data["temperature"],
                            attributes=attributes,
                            unit=temperature_data.get("unit", "F"),
                        )

                        if success:
                            logger.info(
                                f"Updated sensor {sensor_name} with temperature {temperature_data['temperature']}°{temperature_data.get('unit', 'F')}"
                            )
                        else:
                            logger.error(f"Failed to update sensor {sensor_name}")

                        # Process temperature data through session tracker
                        try:
                            # Parse timestamp or use current time
                            timestamp = None
                            if temperature_data.get("timestamp"):
                                timestamp = datetime.fromisoformat(temperature_data["timestamp"].replace("Z", "+00:00"))

                            # For now, we'll use a default user_id of 1 for auto-detected sessions
                            # In a real implementation, this would be determined by device ownership
                            default_user_id = 1

                            session_tracker.process_temperature_reading(
                                device_id=device_id,
                                temperature=float(temperature_data["temperature"]),
                                timestamp=timestamp,
                                user_id=default_user_id,
                            )
                        except Exception as session_error:
                            logger.warning(f"Session tracking error for device {device_id}: {session_error}")

            except Exception as e:
                logger.error(f"Error during temperature sync: {e}")
            finally:
                # Ensure database connections are properly closed
                try:
                    db.session.close()
                except Exception as close_e:
                    logger.warning(f"Error closing database session: {close_e}")

    except Exception as e:
        logger.error(f"Error during temperature sync: {e}")


# ============ TEMPERATURE ALERT CRUD APIs ============


@app.route("/api/alerts", methods=["POST"])
@login_required
def create_alert():
    """Create a new temperature alert"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        # Validate required fields
        required_fields = ["device_id", "probe_id", "alert_type"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f'Missing required fields: {", ".join(missing_fields)}',
                    }
                ),
                400,
            )

        # Validate alert type
        try:
            alert_type = AlertType(data["alert_type"])
        except ValueError:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Invalid alert type. Must be one of: {[t.value for t in AlertType]}",
                    }
                ),
                400,
            )

        # Validate alert-specific data
        errors = alert_manager.validate_alert_data(alert_type, **data)
        if errors:
            return (
                jsonify({"success": False, "message": "Validation errors", "errors": errors}),
                400,
            )

        # Create the alert
        alert_data = {
            "name": data.get("name", f'{data["device_id"]} {data["probe_id"]} Alert'),
            "description": data.get("description"),
            "target_temperature": data.get("target_temperature"),
            "min_temperature": data.get("min_temperature"),
            "max_temperature": data.get("max_temperature"),
            "threshold_value": data.get("threshold_value"),
            "temperature_unit": data.get("temperature_unit", "F"),
        }

        alert = alert_manager.create_alert(
            user_id=current_user.id,
            device_id=data["device_id"],
            probe_id=data["probe_id"],
            alert_type=alert_type,
            **alert_data,
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": alert.to_dict(),
                    "message": "Alert created successfully",
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        return (
            jsonify({"success": False, "message": f"Error creating alert: {str(e)}"}),
            500,
        )


@app.route("/api/alerts", methods=["GET"])
@login_required
def get_alerts():
    """Get all alerts for the current user"""
    try:
        active_only = request.args.get("active_only", "true").lower() == "true"
        device_id = request.args.get("device_id")
        probe_id = request.args.get("probe_id")

        if device_id and probe_id:
            # Get alerts for specific device/probe
            alerts = alert_manager.get_alerts_for_device_probe(device_id, probe_id, active_only)
        else:
            # Get all user alerts
            alerts = alert_manager.get_user_alerts(current_user.id, active_only)

        alerts_data = [alert.to_dict() for alert in alerts]

        return jsonify(
            {
                "success": True,
                "data": {"alerts": alerts_data, "count": len(alerts_data)},
                "message": f"Retrieved {len(alerts_data)} alerts",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return (
            jsonify({"success": False, "message": f"Error fetching alerts: {str(e)}"}),
            500,
        )


@app.route("/api/alerts/<int:alert_id>", methods=["GET"])
@login_required
def get_alert(alert_id):
    """Get a specific alert by ID"""
    try:
        alert = alert_manager.get_alert_by_id(alert_id, current_user.id)

        if not alert:
            return jsonify({"success": False, "message": "Alert not found"}), 404

        return jsonify(
            {
                "success": True,
                "data": alert.to_dict(),
                "message": "Alert retrieved successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching alert {alert_id}: {e}")
        return (
            jsonify({"success": False, "message": f"Error fetching alert: {str(e)}"}),
            500,
        )


@app.route("/api/alerts/<int:alert_id>", methods=["PUT"])
@login_required
def update_alert(alert_id):
    """Update an existing alert"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        # Get existing alert
        existing_alert = alert_manager.get_alert_by_id(alert_id, current_user.id)
        if not existing_alert:
            return jsonify({"success": False, "message": "Alert not found"}), 404

        # Validate alert type if being changed
        if "alert_type" in data:
            try:
                alert_type = AlertType(data["alert_type"])
                # Validate new alert configuration
                errors = alert_manager.validate_alert_data(alert_type, **data)
                if errors:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Validation errors",
                                "errors": errors,
                            }
                        ),
                        400,
                    )
            except ValueError:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Invalid alert type. Must be one of: {[t.value for t in AlertType]}",
                        }
                    ),
                    400,
                )

        # Update the alert
        updated_alert = alert_manager.update_alert(alert_id, current_user.id, **data)

        if not updated_alert:
            return jsonify({"success": False, "message": "Failed to update alert"}), 500

        return jsonify(
            {
                "success": True,
                "data": updated_alert.to_dict(),
                "message": "Alert updated successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error updating alert {alert_id}: {e}")
        return (
            jsonify({"success": False, "message": f"Error updating alert: {str(e)}"}),
            500,
        )


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
@login_required
def delete_alert(alert_id):
    """Delete (deactivate) an alert"""
    try:
        success = alert_manager.delete_alert(alert_id, current_user.id)

        if not success:
            return jsonify({"success": False, "message": "Alert not found"}), 404

        return jsonify({"success": True, "message": "Alert deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting alert {alert_id}: {e}")
        return (
            jsonify({"success": False, "message": f"Error deleting alert: {str(e)}"}),
            500,
        )


@app.route("/api/alerts/types", methods=["GET"])
@login_required
def get_alert_types():
    """Get available alert types and their descriptions"""
    alert_types = [
        {
            "value": "target",
            "label": "Target Temperature",
            "description": "Alert when probe reaches a specific temperature",
            "fields": ["target_temperature"],
        },
        {
            "value": "range",
            "label": "Temperature Range",
            "description": "Alert when probe goes outside a temperature range",
            "fields": ["min_temperature", "max_temperature"],
        },
        {
            "value": "rising",
            "label": "Rising Temperature",
            "description": "Alert when temperature rises by a specific amount",
            "fields": ["threshold_value"],
        },
        {
            "value": "falling",
            "label": "Falling Temperature",
            "description": "Alert when temperature falls by a specific amount",
            "fields": ["threshold_value"],
        },
    ]

    return jsonify(
        {
            "success": True,
            "data": {"alert_types": alert_types},
            "message": "Alert types retrieved successfully",
        }
    )


@app.route("/api/alerts/monitor/status", methods=["GET"])
@login_required
def get_alert_monitor_status():
    """Get status of the alert monitoring service"""
    try:
        if alert_monitor:
            status = alert_monitor.get_status()
            return jsonify(
                {
                    "success": True,
                    "data": status,
                    "message": "Alert monitor status retrieved",
                }
            )
        else:
            return (
                jsonify({"success": False, "message": "Alert monitor not initialized"}),
                503,
            )
    except Exception as e:
        logger.error(f"Error getting alert monitor status: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error getting alert monitor status: {str(e)}",
                }
            ),
            500,
        )


@app.route("/api/alerts/monitor/check", methods=["POST"])
@login_required
def trigger_alert_check():
    """Trigger an immediate check of all alerts"""
    try:
        if alert_monitor:
            success = alert_monitor.trigger_immediate_check()
            if success:
                return jsonify({"success": True, "message": "Alert check triggered successfully"})
            else:
                return (
                    jsonify({"success": False, "message": "Failed to trigger alert check"}),
                    500,
                )
        else:
            return (
                jsonify({"success": False, "message": "Alert monitor not initialized"}),
                503,
            )
    except Exception as e:
        logger.error(f"Error triggering alert check: {e}")
        return (
            jsonify({"success": False, "message": f"Error triggering alert check: {str(e)}"}),
            500,
        )


@app.route("/api/notifications/latest", methods=["GET"])
@login_required
def get_latest_notifications():
    """Get latest notifications for the current user"""
    try:
        if alert_monitor and alert_monitor.redis_client:
            try:
                import json

                user_notifications_key = f"notifications:user:{current_user.id}:latest"
                notifications_data = alert_monitor.redis_client.lrange(user_notifications_key, 0, -1)

                notifications = []
                for notification_json in notifications_data:
                    try:
                        notifications.append(json.loads(notification_json))
                    except json.JSONDecodeError:
                        continue

                return jsonify(
                    {
                        "success": True,
                        "data": {
                            "notifications": notifications,
                            "count": len(notifications),
                        },
                        "message": f"Retrieved {len(notifications)} notifications",
                    }
                )

            except Exception as e:
                logger.error(f"Error fetching notifications from Redis: {e}")
                return jsonify(
                    {
                        "success": True,
                        "data": {"notifications": [], "count": 0},
                        "message": "No notifications available",
                    }
                )
        else:
            return jsonify(
                {
                    "success": True,
                    "data": {"notifications": [], "count": 0},
                    "message": "Notification system not available",
                }
            )

    except Exception as e:
        logger.error(f"Error getting latest notifications: {e}")
        return (
            jsonify({"success": False, "message": f"Error getting notifications: {str(e)}"}),
            500,
        )


# ============ WEBSOCKET EVENT HANDLERS ============


@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection"""
    if current_user.is_authenticated:
        user_room = f"user_{current_user.id}"
        join_room(user_room)
        emit("status", {"message": "Connected to notification system"})
        logger.info(f"User {current_user.id} connected to WebSocket")


@socketio.on("disconnect")
def handle_disconnect():
    """Handle WebSocket disconnection"""
    if current_user.is_authenticated:
        user_room = f"user_{current_user.id}"
        leave_room(user_room)
        logger.info(f"User {current_user.id} disconnected from WebSocket")


@socketio.on("join_notifications")
def handle_join_notifications():
    """Join the user-specific notification room"""
    if current_user.is_authenticated:
        user_room = f"user_{current_user.id}"
        join_room(user_room)
        emit("status", {"message": "Joined notification room"})


@socketio.on("test_notification")
def handle_test_notification():
    """Send a test notification (for debugging)"""
    if current_user.is_authenticated:
        user_room = f"user_{current_user.id}"
        test_notification = {
            "alert_id": "test",
            "alert_name": "Test Alert",
            "message": "This is a test notification",
            "alert_type": "target",
            "device_id": "test_device",
            "probe_id": "test_probe",
            "current_temperature": 200.0,
            "temperature_unit": "F",
            "timestamp": datetime.now().isoformat(),
        }
        socketio.emit("notification", test_notification, room=user_room)


# ============ END WEBSOCKET EVENT HANDLERS ============

# ============ END TEMPERATURE ALERT APIS ============

# ============ SESSION TRACKING APIS ============


@app.route("/api/sessions/history", methods=["GET"])
@login_required
def get_session_history():
    """Get session history for the current user"""
    try:
        # Get query parameters
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        status = request.args.get("status")  # 'active', 'completed', 'cancelled'

        # Validate limit
        if limit > 100:
            limit = 100

        # Get user sessions
        sessions = session_manager.get_user_sessions(user_id=current_user.id, status=status, limit=limit, offset=offset)

        # Convert to dictionaries
        sessions_data = [session.to_dict() for session in sessions]

        # Add additional computed fields
        for session_data in sessions_data:
            session_obj = next((s for s in sessions if s.id == session_data["id"]), None)
            if session_obj:
                session_data["current_duration"] = session_obj.calculate_duration()
                session_data["is_active"] = session_obj.is_active()

        return jsonify(
            {
                "success": True,
                "data": {
                    "sessions": sessions_data,
                    "count": len(sessions_data),
                    "limit": limit,
                    "offset": offset,
                },
                "message": f"Retrieved {len(sessions_data)} sessions",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching session history: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error fetching session history: {str(e)}",
                }
            ),
            500,
        )


@app.route("/api/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    """Get a specific session by ID"""
    try:
        session = session_manager.get_session_by_id(session_id)

        if not session or session.user_id != current_user.id:
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_data = session.to_dict()
        session_data["current_duration"] = session.calculate_duration()
        session_data["is_active"] = session.is_active()

        return jsonify(
            {
                "success": True,
                "data": session_data,
                "message": "Session retrieved successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {e}")
        return (
            jsonify({"success": False, "message": f"Error fetching session: {str(e)}"}),
            500,
        )


@app.route("/api/sessions/<int:session_id>/name", methods=["POST"])
@login_required
def update_session_name(session_id):
    """Update session name"""
    try:
        data = request.get_json()
        if not data or "name" not in data:
            return jsonify({"success": False, "message": "Name is required"}), 400

        # Verify session ownership
        session = session_manager.get_session_by_id(session_id)
        if not session or session.user_id != current_user.id:
            return jsonify({"success": False, "message": "Session not found"}), 404

        # Update session name
        updated_session = session_manager.update_session(session_id, name=data["name"])

        if not updated_session:
            return (
                jsonify({"success": False, "message": "Failed to update session"}),
                500,
            )

        return jsonify(
            {
                "success": True,
                "data": updated_session.to_dict(),
                "message": "Session name updated successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error updating session {session_id} name: {e}")
        return (
            jsonify({"success": False, "message": f"Error updating session name: {str(e)}"}),
            500,
        )


@app.route("/api/sessions/active", methods=["GET"])
@login_required
def get_active_sessions():
    """Get currently active sessions for the user"""
    try:
        active_sessions = session_manager.get_active_sessions(user_id=current_user.id)

        sessions_data = []
        for session in active_sessions:
            session_data = session.to_dict()
            session_data["current_duration"] = session.calculate_duration()
            session_data["is_active"] = True
            sessions_data.append(session_data)

        return jsonify(
            {
                "success": True,
                "data": {"sessions": sessions_data, "count": len(sessions_data)},
                "message": f"Retrieved {len(sessions_data)} active sessions",
            }
        )

    except Exception as e:
        logger.error(f"Error fetching active sessions: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error fetching active sessions: {str(e)}",
                }
            ),
            500,
        )


@app.route("/api/sessions/start", methods=["POST"])
@login_required
def start_session_manually():
    """Manually start a grilling session"""
    try:
        data = request.get_json()
        device_id = data.get("device_id") if data else None
        session_type = data.get("session_type", "manual") if data else "manual"

        if not device_id:
            return jsonify({"success": False, "message": "Device ID is required"}), 400

        # Start session
        session = session_tracker.force_start_session(device_id=device_id, user_id=current_user.id, session_type=session_type)

        if not session:
            return (
                jsonify({"success": False, "message": "Failed to start session"}),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "data": session.to_dict(),
                    "message": "Session started successfully",
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Error starting manual session: {e}")
        return (
            jsonify({"success": False, "message": f"Error starting session: {str(e)}"}),
            500,
        )


@app.route("/api/sessions/<int:session_id>/end", methods=["POST"])
@login_required
def end_session_manually(session_id):
    """Manually end a grilling session"""
    try:
        # Verify session ownership
        session = session_manager.get_session_by_id(session_id)
        if not session or session.user_id != current_user.id:
            return jsonify({"success": False, "message": "Session not found"}), 404

        # End session
        ended_session = session_manager.end_session(session_id)

        if not ended_session:
            return jsonify({"success": False, "message": "Failed to end session"}), 500

        # Generate name if not set
        if not ended_session.name:
            name = session_manager.generate_session_name(ended_session)
            session_manager.update_session(session_id, name=name)
            ended_session = session_manager.get_session_by_id(session_id)

        return jsonify(
            {
                "success": True,
                "data": ended_session.to_dict(),
                "message": "Session ended successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error ending session {session_id}: {e}")
        return (
            jsonify({"success": False, "message": f"Error ending session: {str(e)}"}),
            500,
        )


@app.route("/api/sessions/tracker/status", methods=["GET"])
@login_required
def get_session_tracker_status():
    """Get session tracker status and device statuses"""
    try:
        # Get tracker health
        health = session_tracker.health_check()

        # Get all session statuses
        device_statuses = session_tracker.get_all_session_statuses()

        return jsonify(
            {
                "success": True,
                "data": {"tracker_health": health, "device_statuses": device_statuses},
                "message": "Session tracker status retrieved successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error getting session tracker status: {e}")
        return (
            jsonify({"success": False, "message": f"Error getting tracker status: {str(e)}"}),
            500,
        )


@app.route("/api/sessions/simulate", methods=["POST"])
@login_required
def simulate_session():
    """Simulate a grilling session for testing (mock mode only)"""
    try:
        if not app.config.get("MOCK_MODE", False):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Simulation only available in mock mode",
                    }
                ),
                403,
            )

        data = request.get_json()
        device_id = data.get("device_id", "mock_device_001")
        profile = data.get("profile", "grilling")  # grilling, smoking, roasting

        # Start simulation
        session_tracker.simulate_temperature_data(device_id=device_id, user_id=current_user.id, session_profile=profile)

        return jsonify(
            {
                "success": True,
                "message": f"Session simulation started for device {device_id} with profile {profile}",
            }
        )

    except Exception as e:
        logger.error(f"Error starting session simulation: {e}")
        return (
            jsonify({"success": False, "message": f"Error starting simulation: {str(e)}"}),
            500,
        )


# ============ END SESSION TRACKING APIS ============


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/monitoring")
@login_required
def monitoring():
    """Real-time temperature monitoring dashboard"""
    return render_template("monitoring.html")


@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/api/config")
def get_app_config():
    """Get application configuration info for UI"""
    return jsonify(
        {
            "mock_mode": app.config.get("MOCK_MODE", False),
            "environment": os.getenv("FLASK_ENV", "development"),
            "version": (open("VERSION").read().strip() if os.path.exists("VERSION") else "unknown"),
        }
    )


@app.route("/devices")
@login_required
def get_devices():
    # For HTML request, render template
    if request.headers.get("Accept", "").find("html") != -1:
        devices = thermoworks_client.get_devices()
        return render_template("devices.html", devices=devices)
    # For API request, return JSON
    else:
        devices = thermoworks_client.get_devices()
        return jsonify(devices)


@app.route("/devices/<device_id>/temperature")
@login_required
def get_device_temperature(device_id):
    temperature_data = thermoworks_client.get_temperature_data(device_id)
    return jsonify(temperature_data)


@app.route("/devices/<device_id>/history")
@login_required
def get_device_history(device_id):
    start_time = request.args.get("start", (datetime.now() - timedelta(hours=24)).isoformat())
    end_time = request.args.get("end", datetime.now().isoformat())

    history = thermoworks_client.get_historical_data(device_id, start_time, end_time)
    return jsonify(history)


@app.route("/sync", methods=["POST"])
@login_required
def manual_sync():
    try:
        sync_temperature_data()

        # For HTML request, redirect back
        if request.headers.get("Accept", "").find("html") != -1:
            return redirect(url_for("dashboard"))
        # For API request, return JSON
        else:
            return jsonify({"status": "success", "message": "Temperature data synced successfully"})
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")

        # For HTML request, flash message and redirect back
        if request.headers.get("Accept", "").find("html") != -1:
            from flask import flash

            flash(f"Sync failed: {str(e)}", "danger")
            return redirect(url_for("dashboard"))
        # For API request, return JSON error
        else:
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/homeassistant/test")
@login_required
def test_homeassistant():
    if homeassistant_client.test_connection():
        return jsonify({"status": "connected", "message": "Home Assistant connection successful"})
    else:
        return (
            jsonify({"status": "error", "message": "Failed to connect to Home Assistant"}),
            500,
        )


@app.route("/api/monitoring/data")
@login_required
def get_monitoring_data():
    """
    Get real-time temperature data from all connected probes
    Returns unified data from all probe sources (ThermoWorks Cloud, RFX Gateway, etc.)
    """
    try:
        # Fetch data from all probe sources
        all_probes = []

        # --- ThermoWorks Cloud Probes ---
        try:
            # Get ThermoWorks devices
            devices = thermoworks_client.get_devices()

            # For each device, get temperature data
            for device in devices:
                device_id = device.get("id")
                device_name = device.get("name", f"ThermoWorks {device_id}")

                try:
                    # Get temperature data for this device
                    temperature_data = thermoworks_client.get_temperature_data(device_id)

                    if temperature_data and temperature_data.get("temperature"):
                        # Create a probe entry
                        probe = {
                            "id": f"thermoworks_{device_id}",
                            "name": f"Probe {device_name}",
                            "device_id": device_id,
                            "device_name": device_name,
                            "source": "thermoworks",
                            "temperature": temperature_data.get("temperature"),
                            "unit": temperature_data.get("unit", "F"),
                            "timestamp": temperature_data.get("timestamp", datetime.now().isoformat()),
                            "battery_level": temperature_data.get("battery_level"),
                            "signal_strength": temperature_data.get("signal_strength"),
                            "status": "online",
                        }

                        all_probes.append(probe)
                except Exception as e:
                    logger.error(f"Error getting temperature for ThermoWorks device {device_id}: {e}")
        except Exception as e:
            logger.error(f"Error fetching ThermoWorks devices: {e}")

        # --- RFX Gateway Probes ---
        try:
            # Import RFXGatewayClient only if it's not already imported
            try:
                # Check if device-service is available
                import requests

                from services.device_service.device_manager import DeviceManager
                from services.device_service.rfx_gateway_client import RFXGatewayClient

                # Try to access the device-service API (assuming it's running on standard port)
                device_service_url = os.environ.get("DEVICE_SERVICE_URL", "http://localhost:8080")

                # Get gateways from device service
                response = requests.get(f"{device_service_url}/api/gateways", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    gateways = data.get("data", {}).get("gateways", [])

                    # For each gateway, get temperature readings
                    for gateway in gateways:
                        gateway_id = gateway.get("gateway_id")
                        gateway_name = gateway.get("name", f"RFX Gateway {gateway_id[-6:]}")

                        # Only process online gateways
                        if gateway.get("online", False):
                            try:
                                # Get temperature readings for this gateway
                                temp_response = requests.get(
                                    f"{device_service_url}/api/gateways/{gateway_id}/temperature",
                                    timeout=2,
                                )

                                if temp_response.status_code == 200:
                                    temp_data = temp_response.json()
                                    readings = temp_data.get("data", {}).get("readings", [])

                                    # Process each reading
                                    for reading in readings:
                                        probe_id = reading.get("probe_id")
                                        probe_name = reading.get("name", f"Probe {probe_id}")

                                        # Create normalized probe entry
                                        probe = {
                                            "id": f"rfx_{gateway_id}_{probe_id}",
                                            "name": probe_name,
                                            "device_id": gateway_id,
                                            "device_name": f"RFX: {gateway_name}",
                                            "source": "rfx_gateway",
                                            "temperature": reading.get("temperature"),
                                            "unit": reading.get("unit", "F"),
                                            "timestamp": reading.get("timestamp", datetime.now().isoformat()),
                                            "battery_level": reading.get("battery_level"),
                                            "signal_strength": reading.get("signal_strength"),
                                            "status": "online",
                                        }

                                        all_probes.append(probe)
                            except Exception as e:
                                logger.error(f"Error getting temperature for RFX Gateway {gateway_id}: {e}")
            except (ImportError, requests.RequestException) as e:
                logger.warning(f"RFX Gateway service not available: {e}")
        except Exception as e:
            logger.error(f"Error accessing RFX Gateway service: {e}")

        # Initialize Redis client if not already defined
        try:
            import redis

            redis_client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", 6379)),
                password=os.environ.get("REDIS_PASSWORD", None),
                decode_responses=True,
            )
            # Test connection
            redis_client.ping()
        except (ImportError, redis.RedisError) as e:
            logger.warning(f"Redis not available for temperature cache: {e}")
            redis_client = None

        # If no probes were found but Redis is available, check for cached readings
        if not all_probes and redis_client:
            try:
                # Get all temperature keys
                temp_keys = redis_client.keys("temperature:latest:*")

                for key in temp_keys:
                    cached_data = redis_client.get(key)
                    if cached_data:
                        try:
                            reading = json.loads(cached_data)
                            parts = key.split(":")

                            if len(parts) >= 4:
                                device_id = parts[2]
                                probe_id = parts[3]

                                # Create probe from cached data
                                probe = {
                                    "id": f"cached_{device_id}_{probe_id}",
                                    "name": f"Probe {probe_id}",
                                    "device_id": device_id,
                                    "device_name": f"Device {device_id}",
                                    "source": "cache",
                                    "temperature": reading.get("temperature"),
                                    "unit": reading.get("unit", "F"),
                                    "timestamp": reading.get("timestamp", datetime.now().isoformat()),
                                    "battery_level": reading.get("battery_level"),
                                    "signal_strength": reading.get("signal_strength"),
                                    "status": "offline",  # Mark as offline since we're using cached data
                                }

                                all_probes.append(probe)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.error(f"Error reading cached temperature data: {e}")

        return jsonify(
            {
                "status": "success",
                "data": {
                    "probes": all_probes,
                    "count": len(all_probes),
                    "timestamp": datetime.now().isoformat(),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error fetching monitoring data: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Error fetching monitoring data: {str(e)}",
                }
            ),
            500,
        )


def create_tables():
    """Create database tables and add test user in development"""
    db.create_all()

    # Create a test user in development mode
    if app.config.get("ENV", "production") != "production":
        from auth.utils import create_test_user

        create_test_user(user_manager, bcrypt, "test@example.com", "password")
        logger.info("Created test user: test@example.com / password")

    # Create admin user in production if specified via environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", "Administrator")

    logger.info(f"Admin credentials check - Email: {admin_email}, Password: {'***' if admin_password else 'None'}")

    if admin_email and admin_password:
        try:
            from auth.utils import create_test_user

            existing_admin = user_manager.get_user_by_email(admin_email)
            if not existing_admin:
                create_test_user(user_manager, bcrypt, admin_email, admin_password)
                logger.info(f"Successfully created admin user: {admin_email}")
            else:
                logger.info(f"Admin user already exists: {admin_email}")
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            import traceback

            logger.error(traceback.format_exc())
    else:
        logger.warning("Admin credentials not provided - no admin user created")


# Initialize database - Flask 3.0+ compatible
def initialize_app():
    """Initialize application with database setup and scheduler"""
    global alert_monitor

    with app.app_context():
        create_tables()
        logger.info("Database initialization completed")

    # Initialize and start alert monitor
    try:
        alert_monitor = AlertMonitor(app, alert_manager, socketio)
        alert_monitor.start()
        logger.info("Alert monitoring service started")
    except Exception as e:
        logger.error(f"Failed to start alert monitor: {e}")

    # Set up the scheduler for temperature sync
    scheduler.add_job(func=sync_temperature_data, trigger="interval", minutes=5, id="temperature_sync")

    # Add session tracker maintenance jobs
    def cleanup_session_tracker():
        """Clean up inactive device tracking data"""
        try:
            with app.app_context():
                cleaned_count = session_tracker.cleanup_inactive_devices(hours_inactive=24)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} inactive devices from session tracker")
        except Exception as e:
            logger.error(f"Error cleaning up session tracker: {e}")

    def cleanup_old_sessions():
        """Clean up old incomplete sessions"""
        try:
            with app.app_context():
                cleaned_count = session_manager.cleanup_old_sessions(days_old=7)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old incomplete sessions")
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")

    # Schedule session tracker cleanup every hour
    scheduler.add_job(
        func=cleanup_session_tracker,
        trigger="interval",
        hours=1,
        id="session_tracker_cleanup",
    )

    # Schedule old session cleanup daily at 2 AM
    scheduler.add_job(
        func=cleanup_old_sessions,
        trigger="cron",
        hour=2,
        minute=0,
        id="old_sessions_cleanup",
    )

    scheduler.start()
    logger.info("Temperature sync and session tracking schedulers started")


# Call initialization immediately when module is loaded (works in all deployment scenarios)
logger.info("Attempting to initialize application...")
try:
    initialize_app()
    logger.info("Application initialization successful")
    # Don't test Home Assistant connection during startup as it can hang/crash the app
    # This will be tested on first request or via health check endpoint
except Exception as e:
    logger.error(f"Failed to initialize app during startup: {e}")
    import traceback

    logger.error(f"Initialization traceback: {traceback.format_exc()}")

    # We'll retry on first request if this fails
    @app.before_request
    def retry_initialization():
        """Retry initialization on first request if startup failed"""
        if not hasattr(app, "_database_initialized"):
            try:
                initialize_app()
                app._database_initialized = True
                logger.info("Application initialization completed on first request")
            except Exception as retry_e:
                logger.error(f"Failed to initialize application on first request: {retry_e}")


# This makes the app work with gunicorn in production
application = app

logger.info(f"Module __name__ is: {__name__}")
logger.info("About to check if __name__ == '__main__'")

if __name__ == "__main__":
    logger.info("*** FLASK SERVER STARTING ***")
    logger.info("Starting Grill Stats application")

    # Run Flask development server
    try:
        # Use debug=False in production deployment
        is_production = os.environ.get("FLASK_ENV") == "production"
        debug_mode = not is_production
        port = int(os.environ.get('PORT', 5001))
        logger.info(f"Starting Flask server - Production: {is_production}, Debug: {debug_mode}, Port: {port}")
        logger.info("About to call app.run...")
        socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if alert_monitor:
            alert_monitor.stop()
        scheduler.shutdown()
    except Exception as run_e:
        logger.error(f"Error starting Flask server: {run_e}")
        import traceback

        logger.error(f"Flask server traceback: {traceback.format_exc()}")
else:
    logger.info("Module imported but not executed directly - Flask server not started")
