# Device Management API Documentation

## Overview

The Device Management API provides complete backend functionality for managing ThermoWorks devices in the grill-stats application. This RESTful API handles device registration, removal, listing, and management with comprehensive authentication and validation.

## Base URL

All endpoints are prefixed with `/api/devices`

## Authentication

All endpoints require user authentication. Users can only access and manage their own devices.

**Authentication Method:** Flask-Login session-based authentication
**Required:** User must be logged in via the authentication system

## API Response Format

All API responses follow a standardized JSON format:

```json
{
  "success": true|false,
  "data": {...},
  "message": "Human-readable message",
  "errors": ["Array of error messages"],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

## Endpoints

### 1. Register Device

Register a new ThermoWorks device for the authenticated user.

**Endpoint:** `POST /api/devices/register`

**Request Body:**
```json
{
  "device_id": "TW-ABC-123",
  "nickname": "Grill Probe 1"  // optional
}
```

**Request Validation:**
- `device_id`: Required, must match ThermoWorks format `TW-XXX-XXX`
- `nickname`: Optional, max 100 characters

**Success Response (201):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "device_id": "TW-ABC-123",
    "nickname": "Grill Probe 1",
    "status": "offline",
    "is_active": true,
    "created_at": "2023-12-07T10:30:00.000Z",
    "updated_at": "2023-12-07T10:30:00.000Z"
  },
  "message": "Device TW-ABC-123 successfully registered",
  "errors": [],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

**Error Responses:**
- `400`: Invalid device ID format or duplicate device
- `401`: Authentication required

### 2. List User Devices

Retrieve all devices registered to the authenticated user.

**Endpoint:** `GET /api/devices`

**Query Parameters:**
- `status`: Filter by device status (`online`, `offline`, `error`)
- `include_inactive`: Include soft-deleted devices (`true`/`false`, default: `false`)

**Success Response (200):**
```json
{
  "success": true,
  "data": {
    "devices": [
      {
        "id": 1,
        "device_id": "TW-ABC-123",
        "nickname": "Grill Probe 1",
        "status": "online",
        "is_active": true,
        "created_at": "2023-12-07T10:30:00.000Z",
        "updated_at": "2023-12-07T10:30:00.000Z"
      }
    ],
    "count": 1,
    "filters": {
      "status": null,
      "include_inactive": false
    }
  },
  "message": "Devices retrieved successfully",
  "errors": [],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

### 3. Get Device Details

Retrieve details for a specific device.

**Endpoint:** `GET /api/devices/{device_id}`

**Path Parameters:**
- `device_id`: ThermoWorks device ID (e.g., `TW-ABC-123`)

**Success Response (200):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "device_id": "TW-ABC-123",
    "nickname": "Grill Probe 1",
    "status": "online",
    "is_active": true,
    "created_at": "2023-12-07T10:30:00.000Z",
    "updated_at": "2023-12-07T10:30:00.000Z"
  },
  "message": "Device details retrieved successfully",
  "errors": [],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

**Error Responses:**
- `404`: Device not found or doesn't belong to user
- `401`: Authentication required

### 4. Remove Device

Soft delete a device (sets `is_active` to `false`).

**Endpoint:** `DELETE /api/devices/{device_id}`

**Path Parameters:**
- `device_id`: ThermoWorks device ID (e.g., `TW-ABC-123`)

**Success Response (200):**
```json
{
  "success": true,
  "data": null,
  "message": "Device TW-ABC-123 successfully removed",
  "errors": [],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

**Error Responses:**
- `404`: Device not found or doesn't belong to user
- `409`: Device is in active grilling session (cannot be removed)
- `401`: Authentication required

### 5. Update Device Nickname

Update the nickname for a device.

**Endpoint:** `PUT /api/devices/{device_id}/nickname`

**Path Parameters:**
- `device_id`: ThermoWorks device ID (e.g., `TW-ABC-123`)

**Request Body:**
```json
{
  "nickname": "New Nickname"
}
```

**Request Validation:**
- `nickname`: Required, max 100 characters

**Success Response (200):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "device_id": "TW-ABC-123",
    "nickname": "New Nickname",
    "status": "online",
    "is_active": true,
    "created_at": "2023-12-07T10:30:00.000Z",
    "updated_at": "2023-12-07T10:30:15.000Z"
  },
  "message": "Device nickname updated to 'New Nickname'",
  "errors": [],
  "timestamp": "2023-12-07T10:30:15.000Z"
}
```

**Error Responses:**
- `400`: Invalid nickname (too long or missing)
- `404`: Device not found or doesn't belong to user
- `401`: Authentication required

### 6. Health Check

Check the health of the Device API service.

**Endpoint:** `GET /api/devices/health`

**Authentication:** Not required

**Success Response (200):**
```json
{
  "success": true,
  "data": {
    "service": "device-api",
    "status": "healthy"
  },
  "message": "Device API is healthy",
  "errors": [],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data or validation error
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., device in use)
- `500 Internal Server Error`: Unexpected server error

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "errors": [
    "Specific error message 1",
    "Specific error message 2"
  ],
  "timestamp": "2023-12-07T10:30:00.000Z"
}
```

## Device ID Validation

Device IDs must follow the ThermoWorks format:

**Format:** `TW-XXX-XXX`
- Must start with `TW-`
- Followed by exactly 3 alphanumeric characters
- Followed by `-`
- Followed by exactly 3 alphanumeric characters
- Case insensitive (will be converted to uppercase)

**Valid Examples:**
- `TW-ABC-123`
- `TW-123-ABC`
- `TW-A1B-2C3`
- `tw-abc-123` (converted to uppercase)

**Invalid Examples:**
- `TW-ABCD-123` (too many characters)
- `TW-AB-123` (too few characters)
- `ABC-123-DEF` (doesn't start with TW-)
- `TW-ABC` (missing second part)

## Database Schema

### Device Table

```sql
CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(50) UNIQUE NOT NULL,
    nickname VARCHAR(100),
    status VARCHAR(20) DEFAULT 'offline',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_devices_user_id ON devices(user_id);
CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_devices_active ON devices(is_active);
CREATE INDEX idx_devices_status ON devices(status);
```

### Device Status Values

- `offline`: Device is not currently connected
- `online`: Device is connected and reporting data
- `error`: Device has encountered an error

## Security Features

### Authentication
- All endpoints (except health check) require user authentication
- Users can only access their own devices
- Session-based authentication using Flask-Login

### Input Validation
- All request data is validated before processing
- Device ID format validation
- Nickname length validation
- JSON request format validation

### Authorization
- Users can only manage devices they have registered
- Device ownership is verified on all operations
- Soft delete prevents accidental data loss

### Error Handling
- Comprehensive exception handling
- No sensitive information leaked in error messages
- Structured error responses for client handling

## Integration Points

### With User Authentication System
- Requires existing user authentication (Flask-Login)
- Uses `current_user.id` for device ownership
- Integrates with existing user session management

### With Session Tracking (Future)
- `check_device_in_session()` method prepared for session integration
- Prevents device removal when in active grilling session
- Will be enhanced when session tracking is implemented

### With Frontend (Chunk 3)
- Standardized JSON API responses for easy frontend integration
- RESTful endpoint design
- Comprehensive error handling for UI feedback

## Testing

### Manual Testing with cURL

1. **Register a device:**
```bash
curl -X POST http://localhost:5000/api/devices/register \
  -H "Content-Type: application/json" \
  -d '{"device_id": "TW-ABC-123", "nickname": "Test Probe"}' \
  --cookie-jar cookies.txt \
  --cookie cookies.txt
```

2. **List devices:**
```bash
curl -X GET http://localhost:5000/api/devices \
  --cookie cookies.txt
```

3. **Remove device:**
```bash
curl -X DELETE http://localhost:5000/api/devices/TW-ABC-123 \
  --cookie cookies.txt
```

### Automated Testing

Run the validation script:
```bash
python validate_device_implementation.py
```

## Deployment Notes

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Flask secret key for sessions
- Standard Flask configuration variables

### Database Migration
```bash
python migrations/add_device_table.py
```

### Dependencies
All required dependencies are listed in `requirements.txt`:
- Flask >= 2.3.3
- Flask-SQLAlchemy == 3.1.1
- Flask-Login == 0.6.3
- psycopg2-binary == 2.9.9

## Support and Maintenance

### Logging
- All device operations are logged with user context
- Error logging for debugging and monitoring
- Device registration and removal events tracked

### Monitoring
- Health check endpoint for service monitoring
- Database connection health checks in migration script
- Performance considerations with proper indexing

### Future Enhancements
- Integration with actual ThermoWorks API for device validation
- Real-time device status updates
- Device configuration management
- Advanced device analytics and reporting
