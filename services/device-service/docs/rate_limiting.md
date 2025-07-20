# Rate Limiting Implementation

This document describes the rate limiting implementation for the Device Service API.

## Overview

The Device Service implements rate limiting at two levels:

1. **API Endpoint Level**: Limits the number of requests a client can make to the API within a time window
2. **ThermoWorks API Client Level**: Limits the number of requests made to the ThermoWorks Cloud API to prevent hitting their rate limits

## API Endpoint Rate Limiting

### Configuration

The API endpoint rate limiting is configurable through environment variables:

```env
API_RATE_LIMIT=100       # Maximum number of requests allowed per window
API_RATE_LIMIT_WINDOW=60 # Time window in seconds
API_RATE_LIMIT_BY_IP=true # Whether to limit by IP (true) or user ID (false)
```

### Implementation Details

- Uses a sliding window algorithm to track requests
- Limits can be applied per IP address or per user ID
- When the limit is reached, returns a 429 (Too Many Requests) status code
- Includes standard rate limit headers in responses:
  - `X-RateLimit-Limit`: Maximum number of requests allowed
  - `X-RateLimit-Remaining`: Number of requests remaining in the current window
  - `X-RateLimit-Reset`: Time when the rate limit window resets (Unix timestamp)
  - `Retry-After`: Seconds to wait before making another request

### Usage

All API endpoints are automatically protected by the rate limiter. The rate limit decorator is applied to each endpoint function:

```python
@app.route("/api/devices", methods=["GET"])
@jwt_required
@rate_limit
def get_devices():
    # Endpoint implementation
```

## ThermoWorks API Client Rate Limiting

### Configuration

The ThermoWorks API client rate limiting is configurable through environment variables:

```env
THERMOWORKS_RATE_LIMIT=1000   # Maximum number of requests allowed per window
THERMOWORKS_RATE_WINDOW=3600  # Time window in seconds
THERMOWORKS_BURST_LIMIT=10    # Maximum burst of requests allowed
```

### Implementation Details

- Uses a token bucket algorithm to manage rate limits
- Tracks requests per API endpoint
- Can handle burst traffic while maintaining overall rate limits
- Waits if necessary to stay within rate limits
- Raises `RateLimitExceededError` if the maximum wait time is exceeded

### Class: RateLimiter

The `RateLimiter` class provides the core functionality:

```python
limiter = RateLimiter(
    rate_limit=1000,    # Requests per window
    time_window=3600,   # Window in seconds
    burst_limit=10      # Max burst size
)

# Check if a request can be made
if limiter.check_rate_limit("endpoint_name"):
    # Make request

# Wait if needed before making a request
limiter.wait_if_needed("endpoint_name", max_wait=10.0)
```

## Best Practices

1. **Handle Rate Limit Errors**: Applications should properly handle 429 responses with exponential backoff
2. **Monitor Usage**: Keep track of API usage to stay within limits
3. **Cache Results**: Cache API responses when possible to reduce request volume
4. **Batch Operations**: Combine multiple operations into a single request when possible

## Testing Rate Limits

You can test the rate limits by running the following command:

```bash
# Send 150 requests to the API (exceeding the default limit of 100 per minute)
for i in $(seq 1 150); do
  curl -i http://localhost:8080/api/devices
  echo "\n--- Request $i ---\n"
  sleep 0.1
done
```

You should see 429 responses after the rate limit is reached, with appropriate headers indicating when you can try again.
