# Historical Data Service

A microservice for storing and retrieving historical temperature data from grilling sessions using TimescaleDB.

## Overview

The Historical Data Service is responsible for:

1. Storing temperature readings in a TimescaleDB hypertable
2. Managing data retention (90-day policy)
3. Providing API endpoints for querying historical temperature data
4. Supporting aggregation and time-based filtering of data

## API Endpoints

### Health Check
```
GET /health
```
Returns the health status of the service and its dependencies.

### Store Temperature Reading
```
POST /api/temperature
```
Stores a single temperature reading in the database.

**Request Body:**
```json
{
  "device_id": "device_001",
  "probe_id": "probe_001",
  "grill_id": "grill_001",
  "temperature": 225.5,
  "unit": "F",
  "timestamp": "2025-07-05T12:34:56Z",
  "battery_level": 85.0,
  "signal_strength": 90.0,
  "metadata": {
    "position": "center"
  }
}
```

### Store Batch Temperature Readings
```
POST /api/temperature/batch
```
Stores multiple temperature readings at once.

**Request Body:**
```json
{
  "readings": [
    {
      "device_id": "device_001",
      "probe_id": "probe_001",
      "grill_id": "grill_001",
      "temperature": 225.5,
      "unit": "F"
    },
    {
      "device_id": "device_001",
      "probe_id": "probe_002",
      "grill_id": "grill_001",
      "temperature": 220.0,
      "unit": "F"
    }
  ]
}
```

### Get Temperature History
```
GET /api/temperature/history
```

**Query Parameters:**
- `device_id`: Filter by device ID
- `probe_id`: Filter by probe ID
- `grill_id`: Filter by grill ID
- `start_time`: Start time in ISO 8601 format (default: 24 hours ago)
- `end_time`: End time in ISO 8601 format (default: now)
- `aggregation`: Aggregation function to apply (`none`, `avg`, `min`, `max`)
- `interval`: Time interval for aggregation (e.g., `5m`, `1h`, `1d`)
- `limit`: Maximum number of results to return

### Get Temperature Statistics
```
GET /api/temperature/statistics
```

**Query Parameters:**
- `device_id`: Filter by device ID
- `probe_id`: Filter by probe ID
- `grill_id`: Filter by grill ID
- `start_time`: Start time in ISO 8601 format (default: 24 hours ago)
- `end_time`: End time in ISO 8601 format (default: now)

## Database Schema

### temperature_readings
- `id`: Serial ID
- `time`: Timestamp with timezone (hypertable partition field)
- `device_id`: Device identifier
- `probe_id`: Probe identifier
- `grill_id`: Grill identifier
- `temperature`: Temperature reading
- `unit`: Temperature unit (default: 'F')
- `battery_level`: Battery level percentage
- `signal_strength`: Signal strength percentage
- `metadata`: Additional metadata as JSONB

### cooking_sessions
- `id`: Serial ID
- `name`: Session name
- `grill_id`: Grill identifier
- `start_time`: Session start time
- `end_time`: Session end time
- `user_id`: User identifier
- `metadata`: Additional metadata as JSONB
- `created_at`: Record creation timestamp

### session_probes
- `id`: Serial ID
- `session_id`: Foreign key to cooking_sessions
- `probe_id`: Probe identifier
- `probe_name`: User-friendly probe name
- `target_temp`: Target temperature
- `metadata`: Additional metadata as JSONB
- `created_at`: Record creation timestamp

## TimescaleDB Features

- **Hypertable**: Automatically partitions data by time for efficient storage and queries
- **Data Retention**: 90-day automatic data retention policy
- **Continuous Aggregates**: Precomputed aggregates for faster historical queries
- **Compression**: Older data is automatically compressed to save storage space

## Environment Variables

- `TIMESCALEDB_HOST`: TimescaleDB host (default: localhost)
- `TIMESCALEDB_PORT`: TimescaleDB port (default: 5432)
- `TIMESCALEDB_DATABASE`: Database name (default: grill_monitoring)
- `TIMESCALEDB_USERNAME`: Database username (default: grill_monitor)
- `TIMESCALEDB_PASSWORD`: Database password
- `DEBUG`: Enable debug mode (default: false)
- `PORT`: Port to run the service on (default: 8080)

## Testing

Run tests using pytest:

```bash
python -m pytest
```

For coverage report:

```bash
python -m pytest --cov=src tests/
```