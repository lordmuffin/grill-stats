# Database Connection Pooling Testing Guide

This document provides guidance on how to test the database connection pooling implementation in the Grill Stats application.

## Prerequisites

- Python 3.11 or higher
- Installed dependencies from `requirements.txt`
- A running PostgreSQL database (or SQLite for development)

## Testing Connection Pooling

### 1. Using the Health Endpoint

The `/health` endpoint now provides information about the database connection pool:

```bash
# Get application health, including connection pool status
curl http://localhost:5001/health
```

Example response:

```json
{
  "status": "healthy",
  "timestamp": "2025-07-19T15:30:45.123456",
  "database": {
    "connection_pool": {
      "pool_size": 10,
      "checked_out_connections": 1,
      "overflow": 0,
      "checkedout": 1
    }
  }
}
```

### 2. Using the Database Pool API Endpoint

For more detailed connection pool information, use the dedicated API endpoint (requires authentication):

```bash
# Get detailed connection pool information (requires login)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:5001/api/database/pool
```

Example response:

```json
{
  "status": "success",
  "data": {
    "pool_status": {
      "pool_size": 10,
      "checked_out_connections": 1,
      "overflow": 0,
      "checkedout": 1
    },
    "config": {
      "pool_size": 10,
      "max_overflow": 20,
      "pool_recycle": 3600,
      "pool_timeout": 30,
      "pool_pre_ping": true
    }
  },
  "timestamp": "2025-07-19T15:31:45.123456"
}
```

### 3. Testing with Python Script

For direct testing of connection pooling, you can use the included test script:

```python
# test_pool.py
from app import app, db
from utils.db_utils import get_pool_status

with app.app_context():
    # Get initial pool status
    print("Initial pool status:", get_pool_status(db))

    # Run some queries to get connections from the pool
    for i in range(3):
        db.session.execute("SELECT 1").fetchone()
        print(f"After query {i+1}, pool status:", get_pool_status(db))

    # Close the session to return connections to the pool
    db.session.close()
    print("Final pool status:", get_pool_status(db))
```

Run the script:

```bash
python test_pool.py
```

### 4. Monitoring Active Connections in PostgreSQL

To verify connection pooling from the database side, you can query PostgreSQL for active connections:

```sql
-- Show all active connections
SELECT * FROM pg_stat_activity;

-- Count connections by application
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY application_name;

-- Show oldest connections
SELECT pid, backend_start, application_name
FROM pg_stat_activity
ORDER BY backend_start;
```

### 5. Testing Connection Reuse

To test that connections are being reused properly:

1. Enable debug logging in the application:
   ```bash
   export FLASK_DEBUG=true
   export LOGLEVEL=DEBUG
   ```

2. Start the application and make multiple requests
3. Check the logs for messages about connection checkout/checkin
4. Verify that the number of connections in the pool remains stable

## Validating Connection Pool Configuration

The connection pool is configured with the following settings:

```python
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 3600,  # 1 hour
    "pool_pre_ping": True,
    "pool_timeout": 30,  # 30 seconds
}
```

To validate these settings:

1. Check the application logs for the message "Connection pool settings: size=..."
2. Use the `/api/database/pool` endpoint to view current configuration
3. Verify that the settings match what's defined in the configuration

## Testing Connection Pool Performance

To test the performance benefits of connection pooling:

1. Run a simple load test against the application
2. Monitor database connection count
3. Track response times for API requests

Example using Apache Bench:

```bash
# Send 1000 requests with 10 concurrent users
ab -n 1000 -c 10 http://localhost:5001/health
```

## Troubleshooting

If connection pooling is not working as expected:

1. Check that `SQLALCHEMY_ENGINE_OPTIONS` is properly set in the configuration
2. Verify that `init_connection_pool(app, db)` is being called during application startup
3. Examine the logs for any errors related to connection pooling
4. Ensure the database server allows enough concurrent connections

## Expected Pool Behavior

- **New Connections**: When the application starts, it may create up to `pool_size` connections (10) as needed
- **Connection Reuse**: After a request completes, connections are returned to the pool
- **Overflow**: Under heavy load, up to `max_overflow` (20) additional connections may be created
- **Timeout**: If all connections are in use, new requests will wait up to `pool_timeout` (30s) for an available connection
- **Recycling**: Connections older than `pool_recycle` (3600s) will be closed and new ones created
- **Pre-Ping**: The `pool_pre_ping` setting ensures connections are valid before use by sending a test query
