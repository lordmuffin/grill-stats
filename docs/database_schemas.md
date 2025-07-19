# Database Schemas Documentation

This document provides detailed information about the database schemas used in the Grill Stats application.

## Overview

The Grill Stats application uses SQLAlchemy as an ORM (Object-Relational Mapper) to interact with the database. The application primarily uses PostgreSQL in production and can fall back to SQLite for development and testing.

## Database Connection Pooling

The application implements connection pooling for efficient database connection management. Connection pooling helps improve performance by reusing existing connections rather than creating new ones for each request.

### Configuration

Connection pooling is configured in `config/config_loader.py` and utilized through the `utils/db_utils.py` module. The following settings can be configured:

| Setting | Default | Description |
|---------|---------|-------------|
| `SQLALCHEMY_POOL_SIZE` | 10 | Maximum number of persistent connections to keep in the pool |
| `SQLALCHEMY_MAX_OVERFLOW` | 20 | Maximum number of connections that can be created beyond the pool size |
| `SQLALCHEMY_POOL_RECYCLE` | 3600 | Number of seconds after which a connection is recycled (helps avoid stale connections) |
| `SQLALCHEMY_POOL_PRE_PING` | True | Whether to check if the connection is valid before using it |
| `SQLALCHEMY_POOL_TIMEOUT` | 30 | Number of seconds to wait for a connection to become available |

### PostgreSQL-Specific Optimizations

When using PostgreSQL as the database backend, the following additional optimizations are applied:

| Setting | Value | Description |
|---------|-------|-------------|
| `statement_timeout` | 30000 | Maximum time in milliseconds that a statement can run (prevents long-running queries) |
| `use_native_unicode` | True | Enables native Unicode support for better performance |

These PostgreSQL-specific settings are automatically applied when the application detects a PostgreSQL connection string.

### Usage

The connection pool is automatically initialized when the application starts. The `utils/db_utils.py` module provides functions for:

- Initializing the connection pool
- Monitoring connection pool status
- Safely closing connections
- Transaction management with context managers

## Schema Definitions

### User Model

**Table name:** `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique identifier for the user |
| `email` | String(120) | Unique, Not Null | User's email address |
| `password_hash` | String(128) | Not Null | Bcrypt-hashed password |
| `name` | String(100) | | User's display name |
| `is_active` | Boolean | Default: True | Whether the user is active |
| `failed_login_attempts` | Integer | Default: 0 | Count of failed login attempts |
| `last_failed_login` | DateTime | | Timestamp of the last failed login attempt |
| `is_locked` | Boolean | Default: False | Whether the account is locked due to too many failed attempts |
| `created_at` | DateTime | Default: Now | When the user was created |
| `updated_at` | DateTime | Default: Now, OnUpdate: Now | When the user was last updated |
| `devices` | Relationship | | One-to-many relationship to Device model |

### Device Model

**Table name:** `devices`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique identifier for the device |
| `user_id` | Integer | Foreign Key, Not Null | Reference to the user who owns the device |
| `device_id` | String(50) | Unique, Not Null | ThermoWorks device ID in format TW-XXX-XXX |
| `nickname` | String(100) | | User-assigned nickname for the device |
| `status` | String(20) | Default: "offline" | Device status (online, offline, error) |
| `is_active` | Boolean | Default: True | Whether the device is active |
| `created_at` | DateTime | Default: Now | When the device was created |
| `updated_at` | DateTime | Default: Now, OnUpdate: Now | When the device was last updated |
| `user` | Relationship | | Many-to-one relationship to User model |

### Temperature Alert Model

**Table name:** `temperature_alerts`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique identifier for the alert |
| `user_id` | Integer | Foreign Key, Not Null | Reference to the user who created the alert |
| `device_id` | String(50) | Not Null | ThermoWorks device ID the alert is for |
| `probe_id` | String(50) | Not Null | Probe ID the alert is for |
| `name` | String(100) | | Alert name |
| `description` | Text | | Alert description |
| `alert_type` | String(20) | Not Null | Type of alert (target, range, rising, falling) |
| `target_temperature` | Float | | Target temperature for target-type alerts |
| `min_temperature` | Float | | Minimum temperature for range-type alerts |
| `max_temperature` | Float | | Maximum temperature for range-type alerts |
| `threshold_value` | Float | | Threshold value for rising/falling-type alerts |
| `temperature_unit` | String(5) | Default: "F" | Temperature unit (F or C) |
| `is_active` | Boolean | Default: True | Whether the alert is active |
| `last_triggered` | DateTime | | When the alert was last triggered |
| `created_at` | DateTime | Default: Now | When the alert was created |
| `updated_at` | DateTime | Default: Now, OnUpdate: Now | When the alert was last updated |

### Grilling Session Model

**Table name:** `grilling_sessions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique identifier for the session |
| `user_id` | Integer | Foreign Key, Not Null | Reference to the user who owns the session |
| `device_id` | String(50) | Not Null | ThermoWorks device ID used for the session |
| `name` | String(100) | | Session name |
| `session_type` | String(20) | Default: "auto" | Type of session (auto, manual) |
| `status` | String(20) | Default: "active" | Session status (active, completed, cancelled) |
| `start_time` | DateTime | Not Null, Default: Now | When the session started |
| `end_time` | DateTime | | When the session ended |
| `max_temperature` | Float | | Maximum temperature recorded during the session |
| `min_temperature` | Float | | Minimum temperature recorded during the session |
| `avg_temperature` | Float | | Average temperature during the session |
| `created_at` | DateTime | Default: Now | When the session was created |
| `updated_at` | DateTime | Default: Now, OnUpdate: Now | When the session was last updated |

### ThermoWorks Credentials Model

**Table name:** `thermoworks_credentials`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key | Unique identifier for the credentials |
| `user_id` | Integer | Foreign Key, Not Null | Reference to the user who owns the credentials |
| `access_token` | Text | | ThermoWorks API access token |
| `refresh_token` | Text | | ThermoWorks API refresh token |
| `expires_at` | DateTime | | When the access token expires |
| `created_at` | DateTime | Default: Now | When the credentials were created |
| `updated_at` | DateTime | Default: Now, OnUpdate: Now | When the credentials were last updated |

## Relationships

The following relationships exist between the models:

- **User to Device**: One-to-many (one user can have many devices)
- **User to TemperatureAlert**: One-to-many (one user can have many alerts)
- **User to GrillingSession**: One-to-many (one user can have many sessions)
- **User to ThermoWorksCredentials**: One-to-one (one user has one set of credentials)

## Model Implementation

The models are implemented using a combination of class-based models and manager classes:

1. The base model definitions are in `models/base.py`
2. Each model has its own module (e.g., `models/user.py`, `models/device.py`)
3. Model managers provide methods for CRUD operations

## Migration Management

Database migrations are managed using Flask-Migrate (a wrapper around Alembic). This allows for version-controlled schema changes.

Migration commands:

```bash
# Initialize migrations
flask db init

# Create a new migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback a migration
flask db downgrade
```

## Connection Pooling Monitoring

You can monitor the connection pool status through:

1. The `/health` endpoint, which returns connection pool metrics
2. Application logs, which include pool checkout/checkin information at DEBUG level
3. PostgreSQL metrics for active connections

## Best Practices

1. Always use the `db_transaction` context manager for transactional operations
2. Use `db.session.close()` at the end of request handling
3. Keep transaction scopes as small as possible
4. Use `pool_pre_ping=True` to avoid stale connections
5. Set appropriate pool size based on your application's concurrency needs
6. Monitor connection usage to detect connection leaks
7. For PostgreSQL, use the statement timeout to prevent long-running queries
8. Take advantage of native Unicode support for better text handling performance

## Testing Connection Pooling

You can test the connection pooling implementation using the provided test script:

```bash
python test_connection_pool.py
```

This script will:
1. Initialize the connection pool with the configured settings
2. Execute multiple concurrent queries to test connection reuse
3. Verify that connections are properly returned to the pool
4. Display pool statistics throughout the test

For performance testing under load, you can use tools like `ab` (Apache Benchmark) or JMeter to simulate concurrent connections and measure response times.
