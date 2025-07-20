# Device Service Troubleshooting Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Common Authentication Issues](#common-authentication-issues)
3. [Rate Limiting Issues](#rate-limiting-issues)
4. [Connection and API Issues](#connection-and-api-issues)
5. [Database Related Issues](#database-related-issues)
6. [Device and Probe Management Issues](#device-and-probe-management-issues)
7. [Performance Troubleshooting](#performance-troubleshooting)
8. [Error Codes Reference](#error-codes-reference)
9. [Troubleshooting Workflows](#troubleshooting-workflows)
10. [Log Analysis](#log-analysis)
11. [Maintenance Operations](#maintenance-operations)

## Introduction

This troubleshooting guide provides information on diagnosing and resolving common issues with the Device Service. The Device Service is responsible for managing ThermoWorks devices, retrieving temperature data, and handling device communication with Home Assistant.

### Architecture Overview

The Device Service consists of the following key components:

- **Flask API Server**: Provides REST endpoints for device management
- **ThermoWorks Client**: Handles communication with the ThermoWorks Cloud API
- **Device Manager**: Manages device data in the PostgreSQL database
- **RFX Gateway Client**: Communicates with RFX Gateways through Home Assistant
- **Temperature Handler**: Processes temperature readings

### Prerequisites

Before troubleshooting, ensure you have:

- Access to service logs
- Environment variables properly configured
- Database connection details
- API credentials for ThermoWorks API (if applicable)
- Home Assistant connection details (if applicable)

### How to Use This Guide

1. Identify symptoms of the issue you're experiencing
2. Check for error messages in logs
3. Look up the issue in the appropriate section of this guide
4. Follow the recommended troubleshooting steps
5. If the issue persists, refer to the [Troubleshooting Workflows](#troubleshooting-workflows) section

## Common Authentication Issues

### ThermoWorks API Authentication

#### Issue: OAuth2 Token Acquisition Failure

**Symptoms:**
- Errors with message "Failed to obtain access token"
- 401 Unauthorized responses from ThermoWorks API
- Service unable to connect to ThermoWorks API

**Possible Causes:**
- Invalid client ID or client secret
- Incorrect redirect URI
- Expired refresh token
- Rate limiting by the authentication server

**Solutions:**
1. Verify client ID and client secret in environment variables:
   ```
   THERMOWORKS_CLIENT_ID=your-client-id
   THERMOWORKS_CLIENT_SECRET=your-client-secret
   THERMOWORKS_REDIRECT_URI=http://your-redirect-uri
   ```

2. Check token storage file permissions:
   ```bash
   ls -l ~/.thermoworks_token.json
   # Should show: -rw------- 1 user user ...
   ```

3. Delete existing token to force re-authentication:
   ```bash
   rm ~/.thermoworks_token.json
   ```

4. Manually trigger authentication flow:
   ```bash
   curl -X POST http://localhost:8080/api/auth/thermoworks/start
   ```

#### Issue: Token Refresh Failures

**Symptoms:**
- Authenticated connections work initially but fail after token expiry
- Log messages containing "Token refresh failed"
- Intermittent 401 errors

**Possible Causes:**
- Refresh token expired or revoked
- Network connectivity issues
- Authentication server downtime

**Solutions:**
1. Check connectivity to auth server:
   ```bash
   curl -I https://auth.thermoworks.com
   ```

2. Verify refresh token presence:
   ```bash
   grep "refresh_token" ~/.thermoworks_token.json
   ```

3. Force token refresh via API:
   ```bash
   curl -X POST http://localhost:8080/api/auth/thermoworks/refresh
   ```

4. Enable token debug logging by setting environment variable:
   ```
   LOG_LEVEL=DEBUG
   THERMOWORKS_AUTH_DEBUG=true
   ```

### Home Assistant Authentication

#### Issue: Invalid Access Token

**Symptoms:**
- Errors connecting to Home Assistant
- 401 Unauthorized responses
- Log messages containing "Home Assistant authentication failed"

**Solutions:**
1. Verify token in environment variables:
   ```
   HOMEASSISTANT_URL=http://your-ha-instance:8123
   HOMEASSISTANT_TOKEN=your-long-lived-token
   ```

2. Create a new long-lived access token in Home Assistant:
   - Go to your Home Assistant profile
   - Scroll to the bottom to Long-Lived Access Tokens section
   - Create a new token and update the environment variable

3. Test Home Assistant connection:
   ```bash
   curl -X GET http://localhost:8080/api/homeassistant/test
   ```

## Rate Limiting Issues

### ThermoWorks API Rate Limits

#### Issue: Rate Limit Exceeded

**Symptoms:**
- 429 Too Many Requests responses
- Log messages containing "Rate limit exceeded"
- `RateLimitExceededError` exceptions

**Possible Causes:**
- Too many requests within time window (default: 1000 requests per hour)
- Burst limit exceeded (default: 10 requests)
- Multiple service instances sharing same credentials

**Solutions:**
1. Adjust rate limiting settings:
   ```
   THERMOWORKS_RATE_LIMIT=1000   # Maximum requests per window
   THERMOWORKS_RATE_WINDOW=3600  # Window in seconds
   THERMOWORKS_BURST_LIMIT=10    # Maximum burst
   ```

2. Implement exponential backoff for retries:
   ```python
   retry_after = min(2 ** attempt, 60)  # Max 60 seconds
   time.sleep(retry_after)
   ```

3. Check if multiple instances are running:
   ```bash
   ps aux | grep device-service
   ```

4. Increase polling interval to reduce API calls:
   ```
   THERMOWORKS_POLLING_INTERVAL=300  # 5 minutes
   ```

5. Enable caching to reduce API calls:
   ```
   ENABLE_REDIS_CACHE=true
   REDIS_CACHE_TTL=600
   ```

### API Endpoint Rate Limits

#### Issue: Local API Rate Limiting

**Symptoms:**
- 429 Too Many Requests responses from the Device Service API
- Log messages containing "API rate limit exceeded"
- Client applications unable to access API

**Solutions:**
1. Adjust API rate limit settings:
   ```
   API_RATE_LIMIT=100       # Maximum requests per window
   API_RATE_LIMIT_WINDOW=60 # Window in seconds
   API_RATE_LIMIT_BY_IP=true
   ```

2. Check headers for rate limit information:
   ```bash
   curl -I http://localhost:8080/api/devices
   # Look for X-RateLimit-* headers
   ```

3. Implement client-side throttling:
   ```python
   # Wait if Retry-After header is present
   if 'Retry-After' in response.headers:
       time.sleep(int(response.headers['Retry-After']))
   ```

## Connection and API Issues

### ThermoWorks API Connection

#### Issue: Unable to Connect to ThermoWorks API

**Symptoms:**
- Timeout errors when connecting to API
- Log messages containing "Connection refused" or "Connection timeout"
- Service unable to retrieve device data

**Possible Causes:**
- Network connectivity issues
- Firewall blocking outbound connections
- DNS resolution failures
- ThermoWorks API service outage

**Solutions:**
1. Check network connectivity:
   ```bash
   ping api.thermoworks.com
   curl -I https://api.thermoworks.com
   ```

2. Verify DNS resolution:
   ```bash
   nslookup api.thermoworks.com
   ```

3. Check for firewall issues:
   ```bash
   telnet api.thermoworks.com 443
   ```

4. Enable connection debug logging:
   ```
   LOG_LEVEL=DEBUG
   REQUESTS_DEBUG=true
   ```

5. Configure connection timeouts:
   ```
   API_CONNECT_TIMEOUT=10
   API_READ_TIMEOUT=30
   ```

#### Issue: TLS/SSL Certificate Validation Errors

**Symptoms:**
- SSL certificate validation errors
- Log messages containing "SSL verification failed"
- Connection failures with HTTPS endpoints

**Solutions:**
1. Update CA certificates:
   ```bash
   apt-get update && apt-get install ca-certificates
   ```

2. Verify certificate manually:
   ```bash
   openssl s_client -connect api.thermoworks.com:443
   ```

3. Configure certificate verification:
   ```
   SSL_VERIFY=true
   SSL_CERT_FILE=/path/to/custom/cacert.pem  # Optional
   ```

### Home Assistant Connection

#### Issue: Unable to Connect to Home Assistant

**Symptoms:**
- Errors connecting to Home Assistant
- Log messages containing "Failed to connect to Home Assistant"
- RFX Gateway integration not working

**Solutions:**
1. Verify Home Assistant URL and accessibility:
   ```bash
   curl -I http://your-ha-instance:8123
   ```

2. Check for Home Assistant version compatibility:
   ```bash
   curl -X GET http://localhost:8080/api/homeassistant/version
   ```

3. Test sensor creation:
   ```bash
   curl -X POST http://localhost:8080/api/homeassistant/test-sensor
   ```

4. Increase Home Assistant connection timeout:
   ```
   HOMEASSISTANT_TIMEOUT=30
   ```

## Database Related Issues

### Connection Issues

#### Issue: Unable to Connect to Database

**Symptoms:**
- Log messages containing "Database connection failed"
- Service failing to start with database errors
- API endpoints returning 500 errors related to database

**Possible Causes:**
- Incorrect database credentials
- Database server not running
- Network connectivity issues
- Connection pool exhaustion

**Solutions:**
1. Verify database environment variables:
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=grill_stats
   DB_USER=postgres
   DB_PASSWORD=your-password
   ```

2. Check database server status:
   ```bash
   pg_isready -h $DB_HOST -p $DB_PORT
   ```

3. Test connection with psql:
   ```bash
   psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME
   ```

4. Configure connection pooling:
   ```
   DB_POOL_SIZE=10
   DB_MAX_OVERFLOW=20
   DB_POOL_TIMEOUT=30
   DB_POOL_RECYCLE=1800
   ```

5. Monitor connection pool status:
   ```bash
   curl -X GET http://localhost:8080/api/database/pool
   ```

### Migration and Schema Issues

#### Issue: Table or Column Does Not Exist

**Symptoms:**
- Log messages containing "relation does not exist" or "column does not exist"
- 500 errors with database-related messages

**Solutions:**
1. Run database initialization:
   ```bash
   curl -X POST http://localhost:8080/api/database/init
   ```

2. Check database schema:
   ```bash
   psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\dt"
   psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\d devices"
   ```

3. Run migrations manually:
   ```bash
   cd services/device-service
   python run_migrations.py
   ```

## Device and Probe Management Issues

### Device Discovery

#### Issue: Devices Not Appearing

**Symptoms:**
- Empty device list returned by API
- Devices visible in ThermoWorks app but not in Device Service
- Log messages indicating no devices found

**Possible Causes:**
- Authentication issues with ThermoWorks API
- Incorrect permissions for the OAuth2 token
- Devices not registered with ThermoWorks account

**Solutions:**
1. Verify authentication (see [Authentication Issues](#common-authentication-issues))

2. Check for devices directly with ThermoWorks API:
   ```bash
   curl -X GET http://localhost:8080/api/thermoworks/devices
   ```

3. Force device discovery:
   ```bash
   curl -X POST http://localhost:8080/api/devices/discover
   ```

4. Enable device discovery logging:
   ```
   LOG_LEVEL=DEBUG
   DEVICE_DISCOVERY_DEBUG=true
   ```

### Temperature Data Issues

#### Issue: No Temperature Data

**Symptoms:**
- Devices are discovered but temperature readings are missing
- Zero or null temperature values
- Last updated timestamp not changing

**Possible Causes:**
- Device is offline or batteries are low
- Probes not properly connected
- Temperature polling failures

**Solutions:**
1. Check device status in ThermoWorks app

2. Verify device health:
   ```bash
   curl -X GET http://localhost:8080/api/devices/[device_id]/health
   ```

3. Force temperature update:
   ```bash
   curl -X POST http://localhost:8080/api/devices/[device_id]/temperature/refresh
   ```

4. Enable temperature polling logging:
   ```
   LOG_LEVEL=DEBUG
   TEMPERATURE_POLLING_DEBUG=true
   ```

### Probe Management

#### Issue: Probe Configuration Errors

**Symptoms:**
- Errors when updating probe configuration
- Probe names or settings not saving correctly
- Probe alert settings not working

**Solutions:**
1. Reset probe configuration:
   ```bash
   curl -X DELETE http://localhost:8080/api/devices/[device_id]/probes/[probe_id]/config
   ```

2. Update probe with minimal configuration:
   ```bash
   curl -X PUT http://localhost:8080/api/devices/[device_id]/probes/[probe_id] \
     -H "Content-Type: application/json" \
     -d '{"name": "Probe 1"}'
   ```

3. Check probe configuration format:
   ```bash
   curl -X GET http://localhost:8080/api/devices/[device_id]/probes
   ```

## Performance Troubleshooting

### API Response Time Issues

#### Issue: Slow API Responses

**Symptoms:**
- API requests take longer than expected to complete
- Timeouts from client applications
- Performance metrics showing high p95 response times

**Possible Causes:**
- Database query performance issues
- External API call latency
- Resource constraints (CPU, memory)
- Connection pool exhaustion

**Solutions:**
1. Check performance metrics:
   ```bash
   curl -X GET http://localhost:8080/metrics
   ```

2. Enable query logging to identify slow queries:
   ```
   DB_QUERY_LOG=true
   DB_SLOW_QUERY_THRESHOLD_MS=500
   ```

3. Check for resource constraints:
   ```bash
   top -c -p $(pgrep -f device-service)
   ```

4. Optimize database connections:
   ```
   DB_POOL_SIZE=20
   DB_POOL_TIMEOUT=30
   ```

5. Enable caching:
   ```
   ENABLE_REDIS_CACHE=true
   CACHE_TTL_DEVICES=300
   CACHE_TTL_TEMPERATURE=60
   ```

### Memory Leaks

#### Issue: Increasing Memory Usage

**Symptoms:**
- Memory usage grows over time
- Service eventually crashes with out-of-memory errors
- Performance degrades as service runs longer

**Solutions:**
1. Monitor memory usage:
   ```bash
   ps -o pid,rss,command -p $(pgrep -f device-service)
   ```

2. Check for open database connections:
   ```bash
   curl -X GET http://localhost:8080/api/database/connections
   ```

3. Implement garbage collection monitoring:
   ```
   ENABLE_GC_STATS=true
   ```

4. Restart service periodically if needed:
   ```bash
   systemctl restart device-service
   ```

## Error Codes Reference

### HTTP Status Codes

| Status Code | Description                | Common Causes                                       | Solutions                                                 |
|-------------|----------------------------|-----------------------------------------------------|----------------------------------------------------------|
| 400         | Bad Request                | Invalid parameters, malformed request               | Check request format and parameters                       |
| 401         | Unauthorized               | Missing or invalid authentication                   | Verify token and authentication                           |
| 403         | Forbidden                  | Insufficient permissions                            | Check user roles and permissions                          |
| 404         | Not Found                  | Resource does not exist                             | Verify resource IDs and paths                             |
| 429         | Too Many Requests          | Rate limit exceeded                                 | Implement backoff and retry logic                         |
| 500         | Internal Server Error      | Unhandled exceptions, database errors               | Check logs for detailed error messages                    |
| 502         | Bad Gateway                | Upstream service error (ThermoWorks API)            | Check connectivity to external services                   |
| 503         | Service Unavailable        | Service is overloaded or maintenance                | Retry with exponential backoff                            |
| 504         | Gateway Timeout            | Upstream service timeout                            | Increase timeout settings                                 |

### Application Error Codes

| Error Code      | Description                        | Common Causes                                       | Solutions                                                 |
|-----------------|------------------------------------|-----------------------------------------------------|----------------------------------------------------------|
| AUTH_001        | Authentication Failed              | Invalid credentials                                 | Verify client ID and secret                               |
| AUTH_002        | Token Refresh Failed               | Expired refresh token                               | Force re-authentication                                   |
| RATE_001        | API Rate Limit Exceeded            | Too many requests                                   | Implement backoff and retry                               |
| RATE_002        | ThermoWorks Rate Limit Exceeded    | Too many requests to ThermoWorks API                | Reduce polling frequency                                  |
| CONN_001        | Connection Failed                  | Network connectivity issues                         | Check network and DNS                                     |
| CONN_002        | SSL Verification Failed            | Certificate issues                                  | Update CA certificates                                    |
| DB_001          | Database Connection Failed         | Connection issues                                   | Verify credentials and connectivity                       |
| DB_002          | Query Failed                       | SQL syntax or constraint errors                     | Check logs for specific error                             |
| DEV_001         | Device Not Found                   | Invalid device ID                                   | Verify device ID                                          |
| DEV_002         | Device Offline                     | Device is not connected                             | Check device status                                       |
| PROBE_001       | Probe Not Found                    | Invalid probe ID                                    | Verify probe ID                                           |
| PROBE_002       | Probe Configuration Error          | Invalid configuration                               | Check configuration format                                |

## Troubleshooting Workflows

### General Troubleshooting Flow

1. **Identify the Issue Category**
   - Authentication issue?
   - Connection issue?
   - Database issue?
   - Device/probe issue?
   - Performance issue?

2. **Check Logs**
   - Look for error messages
   - Note timestamps of errors
   - Identify patterns

3. **Verify Configuration**
   - Environment variables
   - Service settings
   - External service credentials

4. **Check Connectivity**
   - Network connectivity
   - External API availability
   - Database connectivity

5. **Test Specific Components**
   - Authentication flow
   - Device discovery
   - Temperature polling
   - Database operations

6. **Implement Solution**
   - Apply specific solutions from this guide
   - Restart services if needed
   - Verify issue is resolved

### Authentication Issues Workflow

```
Start
  |
  v
Is ThermoWorks API authentication failing?
  |
  +---> Yes ---> Check environment variables
  |               |
  |               v
  |             Are credentials correct?
  |               |
  |               +---> No ---> Update credentials
  |               |
  |               +---> Yes ---> Delete token file and force re-auth
  |                               |
  |                               v
  |                             Did re-auth succeed?
  |                               |
  |                               +---> No ---> Check ThermoWorks API status
  |                               |
  |                               +---> Yes ---> Issue resolved
  |
  +---> No ---> Is Home Assistant authentication failing?
                |
                +---> Yes ---> Check HA token and URL
                |               |
                |               v
                |             Are HA settings correct?
                |               |
                |               +---> No ---> Update HA settings
                |               |
                |               +---> Yes ---> Create new HA token
                |
                +---> No ---> Check other authentication issues
```

### Device Discovery Issues Workflow

```
Start
  |
  v
Are devices missing from the device list?
  |
  +---> Yes ---> Is authentication working?
  |               |
  |               +---> No ---> Fix authentication issues first
  |               |
  |               +---> Yes ---> Force device discovery
  |                               |
  |                               v
  |                             Are devices visible now?
  |                               |
  |                               +---> No ---> Check ThermoWorks account directly
  |                               |
  |                               +---> Yes ---> Issue resolved
  |
  +---> No ---> Are temperature readings missing?
                |
                +---> Yes ---> Check device health
                |               |
                |               v
                |             Is device online?
                |               |
                |               +---> No ---> Check device batteries/connectivity
                |               |
                |               +---> Yes ---> Force temperature update
                |
                +---> No ---> Check other device issues
```

## Log Analysis

### Important Log Patterns

When analyzing logs, look for these patterns to identify specific issues:

#### Authentication Issues
```
"Failed to obtain access token"
"Token refresh failed"
"Home Assistant authentication failed"
```

#### Rate Limiting Issues
```
"Rate limit exceeded"
"429 Too Many Requests"
"RateLimitExceededError"
```

#### Connection Issues
```
"Connection refused"
"Connection timeout"
"SSL verification failed"
```

#### Database Issues
```
"Database connection failed"
"relation does not exist"
"column does not exist"
```

#### Device Issues
```
"No devices found"
"Device not found"
"Device is offline"
```

### Enabling Debug Logging

To get more detailed logs for troubleshooting:

1. Set the log level to DEBUG:
   ```
   LOG_LEVEL=DEBUG
   ```

2. Enable component-specific debugging:
   ```
   THERMOWORKS_AUTH_DEBUG=true
   DEVICE_DISCOVERY_DEBUG=true
   TEMPERATURE_POLLING_DEBUG=true
   HOMEASSISTANT_DEBUG=true
   DB_QUERY_LOG=true
   ```

3. View logs:
   ```bash
   journalctl -u device-service -f
   # or
   docker logs -f device-service
   # or
   cat /var/log/device-service.log
   ```

## Maintenance Operations

### Database Maintenance

#### Index Optimization

Over time, database indexes can become fragmented and less efficient. To optimize:

```bash
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "REINDEX TABLE devices;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "REINDEX TABLE device_health;"
```

#### Table Vacuuming

To reclaim storage and update statistics:

```bash
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE devices;"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE device_health;"
```

### Service Maintenance

#### Periodic Restart

For long-running services, a periodic restart can help prevent memory leaks and other issues:

```bash
systemctl restart device-service
```

#### Token Rotation

Periodically rotating OAuth tokens can improve security:

```bash
curl -X POST http://localhost:8080/api/auth/thermoworks/rotate
```

#### Cache Clearing

If caching is enabled, clearing caches can help resolve stale data issues:

```bash
curl -X POST http://localhost:8080/api/cache/clear
```

### Monitoring and Alerting

#### Prometheus Metrics

The service exposes Prometheus metrics at `/metrics` which can be used to set up alerting:

```bash
curl -X GET http://localhost:8080/metrics
```

Key metrics to monitor:
- `device_service_api_requests_total` - Total API requests
- `device_service_api_request_duration_seconds` - API request duration
- `device_service_device_count` - Number of devices
- `device_service_thermoworks_api_errors` - ThermoWorks API errors
- `device_service_database_errors` - Database errors

#### Health Check

Use the health check endpoint to monitor service health:

```bash
curl -X GET http://localhost:8080/health
```

A healthy response includes:
```json
{
  "status": "healthy",
  "database": {
    "status": "connected",
    "pool_size": 10,
    "active_connections": 2
  },
  "thermoworks_api": {
    "status": "connected",
    "last_connection": "2025-07-20T12:00:00Z"
  },
  "homeassistant": {
    "status": "connected",
    "last_connection": "2025-07-20T12:00:00Z"
  },
  "uptime_seconds": 3600
}
```
