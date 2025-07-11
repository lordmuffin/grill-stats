"""
Device Management API endpoints
Provides REST API for device registration, removal, and management
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps

# Import will be done in init_device_api to avoid circular imports
logger = logging.getLogger(__name__)

# Create blueprint for device API
device_api = Blueprint('device_api', __name__, url_prefix='/api/devices')


def create_api_response(success=True, data=None, message="", errors=None, status_code=200):
    """Create standardized API response"""
    response = {
        "success": success,
        "data": data,
        "message": message,
        "errors": errors or [],
        "timestamp": datetime.utcnow().isoformat()
    }
    return jsonify(response), status_code


def validate_json_request(required_fields=None):
    """Decorator to validate JSON request format and required fields"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if request has JSON data
            if not request.is_json:
                return create_api_response(
                    success=False,
                    message="Request must be JSON",
                    errors=["Content-Type must be application/json"],
                    status_code=400
                )
            
            # Check required fields
            if required_fields:
                data = request.get_json()
                missing_fields = []
                for field in required_fields:
                    if field not in data or not data[field]:
                        missing_fields.append(field)
                
                if missing_fields:
                    return create_api_response(
                        success=False,
                        message="Missing required fields",
                        errors=[f"Missing required field: {field}" for field in missing_fields],
                        status_code=400
                    )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def handle_api_exceptions(f):
    """Decorator to handle common API exceptions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return create_api_response(
                success=False,
                message="Validation error",
                errors=[str(e)],
                status_code=400
            )
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}")
            return create_api_response(
                success=False,
                message="Internal server error",
                errors=["An unexpected error occurred"],
                status_code=500
            )
    return decorated_function


@device_api.route('/register', methods=['POST'])
@login_required
@validate_json_request(['device_id'])
@handle_api_exceptions
def register_device():
    """
    Register a new ThermoWorks device
    
    POST /api/devices/register
    {
        "device_id": "TW-ABC-123",
        "nickname": "Grill Probe 1"  // optional
    }
    """
    data = request.get_json()
    device_id = data.get('device_id', '').strip()
    nickname = data.get('nickname', '').strip() or None
    
    # Get device manager from current app
    device_manager = current_app.device_manager
    
    # Validate device ID format
    is_valid, validation_message = device_manager.validate_device_id(device_id)
    if not is_valid:
        return create_api_response(
            success=False,
            message="Invalid device ID",
            errors=[validation_message],
            status_code=400
        )
    
    # Create device
    device = device_manager.create_device(
        user_id=current_user.id,
        device_id=device_id,
        nickname=nickname
    )
    
    logger.info(f"User {current_user.email} registered device {device_id}")
    
    return create_api_response(
        success=True,
        data=device.to_dict(),
        message=f"Device {device_id} successfully registered",
        status_code=201
    )


@device_api.route('/<device_id>', methods=['DELETE'])
@login_required
@handle_api_exceptions
def remove_device(device_id):
    """
    Remove (soft delete) a device
    
    DELETE /api/devices/{device_id}
    """
    # Get device manager from current app
    device_manager = current_app.device_manager
    
    # Check if device exists and belongs to user
    device = device_manager.get_user_device(current_user.id, device_id)
    if not device:
        return create_api_response(
            success=False,
            message="Device not found",
            errors=[f"Device {device_id} not found or does not belong to user"],
            status_code=404
        )
    
    # Check if device is in active grilling session
    if device_manager.check_device_in_session(device_id):
        return create_api_response(
            success=False,
            message="Cannot remove device",
            errors=["Device is currently in an active grilling session"],
            status_code=409
        )
    
    # Soft delete the device
    device_manager.soft_delete_device(current_user.id, device_id)
    
    logger.info(f"User {current_user.email} removed device {device_id}")
    
    return create_api_response(
        success=True,
        message=f"Device {device_id} successfully removed"
    )


@device_api.route('', methods=['GET'])
@login_required
@handle_api_exceptions
def list_devices():
    """
    List user's registered devices
    
    GET /api/devices?status=online&include_inactive=false
    """
    # Get query parameters
    status_filter = request.args.get('status')
    include_inactive = request.args.get('include_inactive', 'false').lower() in ('true', '1', 'yes')
    
    # Get device manager from current app
    device_manager = current_app.device_manager
    
    # Get user's devices
    devices = device_manager.get_user_devices(current_user.id, include_inactive)
    
    # Filter by status if requested
    if status_filter:
        devices = [d for d in devices if d.status == status_filter]
    
    # Convert to dictionaries for JSON serialization
    devices_data = [device.to_dict() for device in devices]
    
    logger.info(f"User {current_user.email} listed {len(devices_data)} devices")
    
    return create_api_response(
        success=True,
        data={
            "devices": devices_data,
            "count": len(devices_data),
            "filters": {
                "status": status_filter,
                "include_inactive": include_inactive
            }
        },
        message="Devices retrieved successfully"
    )


@device_api.route('/<device_id>', methods=['GET'])
@login_required
@handle_api_exceptions
def get_device_details(device_id):
    """
    Get details for a specific device
    
    GET /api/devices/{device_id}
    """
    # Get device manager from current app
    device_manager = current_app.device_manager
    
    # Get device
    device = device_manager.get_user_device(current_user.id, device_id)
    if not device:
        return create_api_response(
            success=False,
            message="Device not found",
            errors=[f"Device {device_id} not found or does not belong to user"],
            status_code=404
        )
    
    return create_api_response(
        success=True,
        data=device.to_dict(),
        message="Device details retrieved successfully"
    )


@device_api.route('/<device_id>/nickname', methods=['PUT'])
@login_required
@validate_json_request(['nickname'])
@handle_api_exceptions
def update_device_nickname(device_id):
    """
    Update device nickname
    
    PUT /api/devices/{device_id}/nickname
    {
        "nickname": "New Nickname"
    }
    """
    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    
    if len(nickname) > 100:
        return create_api_response(
            success=False,
            message="Nickname too long",
            errors=["Nickname must be 100 characters or less"],
            status_code=400
        )
    
    # Get device manager from current app
    device_manager = current_app.device_manager
    
    # Update nickname
    device = device_manager.update_device_nickname(current_user.id, device_id, nickname)
    
    logger.info(f"User {current_user.email} updated nickname for device {device_id}")
    
    return create_api_response(
        success=True,
        data=device.to_dict(),
        message=f"Device nickname updated to '{nickname}'"
    )


@device_api.route('/health', methods=['GET'])
def device_api_health():
    """Health check endpoint for device API"""
    return create_api_response(
        success=True,
        data={"service": "device-api", "status": "healthy"},
        message="Device API is healthy"
    )


def init_device_api(app, device_manager):
    """Initialize device API with Flask app"""
    # Store device manager in app context for access in routes
    app.device_manager = device_manager
    
    # Register blueprint
    app.register_blueprint(device_api)
    
    logger.info("Device API initialized successfully")