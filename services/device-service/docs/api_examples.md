# API Examples

This document provides examples of how to use the Device Service API endpoints.

## Authentication

Most endpoints require authentication using a JWT token.

```bash
# Include the token in the Authorization header
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices
```

## Health Check

Check the health of the service:

```bash
curl http://localhost:8080/health
```

Example response:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-20T12:00:00",
  "service": "device-service",
  "version": "1.0.0",
  "telemetry": {
    "opentelemetry": "enabled",
    "tracing": true,
    "metrics": true
  }
}
```

## Device Management

### List All Devices

Get a list of all devices:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices
```

Example response:
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "devices": [
      {
        "device_id": "device_12345",
        "name": "Patio Smoker",
        "device_type": "thermoworks",
        "model": "Signals",
        "status": "online",
        "battery_level": 85,
        "signal_strength": 92,
        "is_online": true,
        "probes": [
          {
            "id": "1",
            "name": "Meat"
          },
          {
            "id": "2",
            "name": "Ambient"
          }
        ],
        "created_at": "2025-06-01T10:00:00Z",
        "updated_at": "2025-07-20T12:00:00Z"
      }
    ],
    "count": 1,
    "source": "database"
  }
}
```

### Get a Specific Device

Get details for a specific device:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices/device_12345
```

### Update a Device

Update a device's name or configuration:

```bash
curl -X PUT \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Device Name", "configuration": {"custom_field": "value"}}' \
  http://localhost:8080/api/devices/device_12345
```

### Delete a Device

Delete a device (soft delete):

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8080/api/devices/device_12345
```

## Temperature Data

### Get Current Temperature

Get current temperature readings for a device:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices/device_12345/temperature
```

Example response:
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "readings": [
      {
        "device_id": "device_12345",
        "probe_id": "1",
        "temperature": 225.5,
        "unit": "F",
        "timestamp": "2025-07-20T12:00:00Z",
        "battery_level": 85,
        "signal_strength": 92
      },
      {
        "device_id": "device_12345",
        "probe_id": "2",
        "temperature": 135.2,
        "unit": "F",
        "timestamp": "2025-07-20T12:00:00Z",
        "battery_level": 85,
        "signal_strength": 92
      }
    ],
    "count": 2,
    "source": "api"
  }
}
```

### Get Temperature for a Specific Probe

Get temperature readings for a specific probe:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices/device_12345/temperature?probe_id=1
```

### Get Temperature History

Get historical temperature data:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:8080/api/devices/device_12345/history?start=2025-07-19T00:00:00&end=2025-07-20T00:00:00"
```

## Probe Management

### List All Probes for a Device

Get all probes for a device:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices/device_12345/probes
```

Example response:
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "device_id": "device_12345",
    "probes": [
      {
        "id": "1",
        "name": "Meat",
        "type": "food",
        "color": "red"
      },
      {
        "id": "2",
        "name": "Ambient",
        "type": "ambient",
        "color": "blue"
      }
    ],
    "count": 2,
    "source": "api"
  }
}
```

### Get a Specific Probe

Get details for a specific probe:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8080/api/devices/device_12345/probes/1
```

### Update a Probe

Update a probe's configuration:

```bash
curl -X PUT \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Brisket", "color": "green", "target_temp": 205, "high_alarm": 210, "low_alarm": 200}' \
  http://localhost:8080/api/devices/device_12345/probes/1
```

## Webhooks

### Receive Temperature Updates

Example payload for the `/api/webhooks/temperature` endpoint:

```json
{
  "device_id": "device_12345",
  "device_name": "Patio Smoker",
  "model": "Signals",
  "battery_level": 85,
  "signal_strength": 92,
  "is_online": true,
  "probes": [
    {
      "probe_id": "1",
      "temperature": 225.5,
      "unit": "F",
      "timestamp": "2025-07-20T12:00:00Z"
    },
    {
      "probe_id": "2",
      "temperature": 135.2,
      "unit": "F",
      "timestamp": "2025-07-20T12:00:00Z"
    }
  ]
}
```

### Verify Webhook Configuration

Check webhook configuration:

```bash
curl http://localhost:8080/api/webhooks/temperature/verify
```

## Sync Operations

### Manual Sync

Trigger a manual data sync:

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8080/api/sync
```

## Error Handling

All API endpoints return standard error responses:

```json
{
  "status": "error",
  "message": "Error message",
  "status_code": 400,
  "details": {
    "additional": "error details"
  }
}
```

Common error status codes:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Too Many Requests
- 500: Internal Server Error
