# Webhook Integration

This document describes the webhook integration for real-time updates in the Device Service.

## Overview

The Device Service supports webhooks to receive real-time updates from ThermoWorks and other external services. This allows for push-based updates rather than pull-based polling, resulting in more timely data and reduced API calls.

## Webhook Endpoints

The following webhook endpoints are available:

### Temperature Updates

**Endpoint:** `/api/webhooks/temperature`
**Method:** `POST`
**Event Type:** `temperature_update`

Receives real-time temperature updates from devices.

Example payload:
```json
{
  "device_id": "device_12345",
  "device_name": "Signals",
  "model": "Signals",
  "battery_level": 85,
  "signal_strength": 92,
  "is_online": true,
  "probes": [
    {
      "probe_id": "1",
      "temperature": 225.5,
      "unit": "F",
      "timestamp": "2025-07-20T14:30:00Z"
    },
    {
      "probe_id": "2",
      "temperature": 135.2,
      "unit": "F",
      "timestamp": "2025-07-20T14:30:00Z"
    }
  ]
}
```

### Device Status Updates

**Endpoint:** `/api/webhooks/device-status`
**Method:** `POST`
**Event Type:** `device_status_update`

Receives updates about device status changes (online/offline, battery level, etc.).

Example payload:
```json
{
  "device_id": "device_12345",
  "device_name": "Signals",
  "model": "Signals",
  "status": "online",
  "battery_level": 85,
  "signal_strength": 92,
  "last_seen": "2025-07-20T14:30:00Z"
}
```

## Webhook Verification

To ensure webhook security, we implement the following measures:

1. **Signature Verification:** Each webhook request should include a signature in the `X-Webhook-Signature` header.
2. **IP Allowlisting:** Optionally restrict webhook access to specific IP addresses.

### Signature Verification

The signature is computed as follows:

```
signature = hmac.new(
    secret_key,
    request_body,
    hashlib.sha256
).hexdigest()
```

Where:
- `secret_key` is the shared secret between the service and the webhook sender
- `request_body` is the raw HTTP request body

### Webhook Verification Endpoint

Each webhook has a verification endpoint that can be used to check if the webhook is properly configured:

**Endpoint:** `/api/webhooks/{webhook_id}/verify`
**Method:** `GET`

Response:
```json
{
  "status": "success",
  "webhook_id": "temperature",
  "event_type": "temperature_update",
  "verification_required": true,
  "signature_header": "X-Webhook-Signature",
  "url": "https://your-service.com/api/webhooks/temperature"
}
```

## Configuration

Webhooks can be configured using the following environment variables:

```env
# Enable or disable webhooks
ENABLE_WEBHOOKS=true

# Secret key for webhook signature verification
WEBHOOK_SECRET=your-webhook-secret

# Enable or disable signature verification
VERIFY_WEBHOOKS=true
```

## Registering with ThermoWorks Cloud

To register a webhook with ThermoWorks Cloud, follow these steps:

1. Get the webhook URL from the verification endpoint: `/api/webhooks/temperature/verify`
2. Register the webhook with ThermoWorks Cloud using their API or developer portal
3. Provide the webhook secret to ThermoWorks Cloud
4. Test the webhook integration by monitoring the logs

## Testing Webhooks Locally

You can test webhooks locally using the following curl command:

```bash
# Generate a test signature
SECRET="your-webhook-secret"
PAYLOAD='{"device_id":"test_device","device_name":"Test Device","model":"Test","battery_level":100,"signal_strength":100,"is_online":true,"probes":[{"probe_id":"1","temperature":225.5,"unit":"F","timestamp":"2025-07-20T14:30:00Z"}]}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

# Send the webhook request
curl -X POST http://localhost:8080/api/webhooks/temperature \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

## Error Handling

Webhook errors are logged and can be monitored in the application logs. Common error scenarios include:

- Invalid signature
- Invalid payload format
- Error processing webhook data
- Rate limiting issues

The service will return appropriate HTTP status codes in these scenarios, which the webhook sender should handle with retry logic if needed.

## Best Practices

1. **Keep secrets secure:** Store the webhook secret securely and never expose it in logs or client-side code.
2. **Monitor webhook errors:** Set up alerts for webhook processing errors.
3. **Implement idempotency:** Ensure webhooks can be processed multiple times without side effects.
4. **Handle retries:** Implement proper retry logic on both sides of the webhook integration.
5. **Limit payload size:** Keep webhook payloads small to minimize processing overhead.
