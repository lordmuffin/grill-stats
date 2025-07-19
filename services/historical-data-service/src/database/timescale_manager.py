import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import structlog
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import DictCursor
from retry import retry

logger = structlog.get_logger()


class TimescaleManager:
    """Manages interactions with TimescaleDB for temperature data."""

    def __init__(
        self, host: str, port: int, database: str, username: str, password: str
    ):
        """Initialize the TimescaleDB manager with connection parameters."""
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self._connect()

    def _connect(self):
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
            )
            # Set isolation level for creating extensions
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Connected to TimescaleDB successfully")
        except Exception as e:
            logger.error("Failed to connect to TimescaleDB", error=str(e))
            raise

    def health_check(self) -> bool:
        """Check TimescaleDB connection health."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error("TimescaleDB health check failed", error=str(e))
            raise

    @retry(tries=3, delay=2, backoff=2)
    def init_db(self):
        """Initialize TimescaleDB schema and hypertables."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor() as cursor:
                # Create extension if it doesn't exist
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

                # Create temperature_readings table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS temperature_readings (
                        id SERIAL,
                        time TIMESTAMPTZ NOT NULL,
                        device_id VARCHAR(255) NOT NULL,
                        probe_id VARCHAR(255),
                        grill_id VARCHAR(255),
                        temperature FLOAT NOT NULL,
                        unit VARCHAR(10) DEFAULT 'F',
                        battery_level FLOAT,
                        signal_strength FLOAT,
                        metadata JSONB
                    )
                """
                )

                # Create indexes for better query performance
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_temperature_device_id ON temperature_readings(device_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_temperature_probe_id ON temperature_readings(probe_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_temperature_grill_id ON temperature_readings(grill_id)"
                )

                # Convert to hypertable if not already
                try:
                    cursor.execute(
                        """
                        SELECT create_hypertable('temperature_readings', 'time',
                                                if_not_exists => TRUE)
                    """
                    )
                except Exception as e:
                    logger.warning(
                        "Hypertable creation issue (might already be a hypertable)",
                        error=str(e),
                    )

                # Create retention policy (90 days)
                cursor.execute(
                    """
                    SELECT add_retention_policy('temperature_readings',
                                              INTERVAL '90 days',
                                              if_not_exists => TRUE)
                """
                )

                # Create sessions table for tracking cooking sessions
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cooking_sessions (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255),
                        grill_id VARCHAR(255),
                        start_time TIMESTAMPTZ NOT NULL,
                        end_time TIMESTAMPTZ,
                        user_id VARCHAR(255),
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """
                )

                # Create indexes for sessions
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_grill_id ON cooking_sessions(grill_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON cooking_sessions(user_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_time ON cooking_sessions(start_time, end_time)"
                )

                logger.info("TimescaleDB schema initialized successfully")

        except Exception as e:
            logger.error("TimescaleDB initialization failed", error=str(e))
            raise

    def store_temperature_reading(self, reading: Dict[str, Any]) -> bool:
        """Store a single temperature reading in TimescaleDB."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor() as cursor:
                # Convert metadata to JSON if needed
                metadata = None
                if reading.get("metadata"):
                    if isinstance(reading["metadata"], dict):
                        metadata = json.dumps(reading["metadata"])
                    else:
                        metadata = reading["metadata"]

                # Use timestamp from reading or current time
                timestamp = reading.get("timestamp")
                if not timestamp:
                    timestamp = datetime.utcnow()
                elif isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

                # Insert the temperature reading
                cursor.execute(
                    """
                    INSERT INTO temperature_readings (
                        time, device_id, probe_id, grill_id, temperature,
                        unit, battery_level, signal_strength, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        timestamp,
                        reading["device_id"],
                        reading.get("probe_id"),
                        reading.get("grill_id"),
                        reading["temperature"],
                        reading.get("unit", "F"),
                        reading.get("battery_level"),
                        reading.get("signal_strength"),
                        metadata,
                    ),
                )

                self.connection.commit()
                logger.debug(
                    "Temperature reading stored", device_id=reading["device_id"]
                )
                return True

        except Exception as e:
            logger.error("Error storing temperature reading", error=str(e))
            if self.connection:
                self.connection.rollback()
            return False

    def store_batch_temperature_readings(self, readings: List[Dict[str, Any]]) -> int:
        """Store multiple temperature readings at once."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor() as cursor:
                count = 0
                for reading in readings:
                    # Convert metadata to JSON if needed
                    metadata = None
                    if reading.get("metadata"):
                        if isinstance(reading["metadata"], dict):
                            metadata = json.dumps(reading["metadata"])
                        else:
                            metadata = reading["metadata"]

                    # Use timestamp from reading or current time
                    timestamp = reading.get("timestamp")
                    if not timestamp:
                        timestamp = datetime.utcnow()
                    elif isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )

                    # Insert the temperature reading
                    cursor.execute(
                        """
                        INSERT INTO temperature_readings (
                            time, device_id, probe_id, grill_id, temperature,
                            unit, battery_level, signal_strength, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            timestamp,
                            reading["device_id"],
                            reading.get("probe_id"),
                            reading.get("grill_id"),
                            reading["temperature"],
                            reading.get("unit", "F"),
                            reading.get("battery_level"),
                            reading.get("signal_strength"),
                            metadata,
                        ),
                    )
                    count += 1

                self.connection.commit()
                logger.info("Batch temperature readings stored", count=count)
                return count

        except Exception as e:
            logger.error("Error storing batch temperature readings", error=str(e))
            if self.connection:
                self.connection.rollback()
            return 0

    def get_temperature_history(
        self,
        device_id: Optional[str] = None,
        probe_id: Optional[str] = None,
        grill_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: Optional[str] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical temperature data based on query parameters."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor(cursor_factory=DictCursor) as cursor:
                # Build the base query
                query = "SELECT "

                # Add fields based on aggregation
                if not aggregation or aggregation.lower() == "none":
                    query += "time, device_id, probe_id, grill_id, temperature, unit, battery_level, signal_strength, metadata"
                elif aggregation.lower() == "avg":
                    query += f"time_bucket('{interval or '1 hour'}', time) as time, "
                    query += "device_id, probe_id, grill_id, AVG(temperature) as temperature, "
                    query += "unit, AVG(battery_level) as battery_level, AVG(signal_strength) as signal_strength"
                elif aggregation.lower() == "min":
                    query += f"time_bucket('{interval or '1 hour'}', time) as time, "
                    query += "device_id, probe_id, grill_id, MIN(temperature) as temperature, "
                    query += "unit, MIN(battery_level) as battery_level, MIN(signal_strength) as signal_strength"
                elif aggregation.lower() == "max":
                    query += f"time_bucket('{interval or '1 hour'}', time) as time, "
                    query += "device_id, probe_id, grill_id, MAX(temperature) as temperature, "
                    query += "unit, MAX(battery_level) as battery_level, MAX(signal_strength) as signal_strength"
                else:
                    # Default to no aggregation
                    query += "time, device_id, probe_id, grill_id, temperature, unit, battery_level, signal_strength, metadata"

                query += " FROM temperature_readings WHERE 1=1"

                # Add filters
                params = []
                if device_id:
                    query += " AND device_id = %s"
                    params.append(device_id)

                if probe_id:
                    query += " AND probe_id = %s"
                    params.append(probe_id)

                if grill_id:
                    query += " AND grill_id = %s"
                    params.append(grill_id)

                if start_time:
                    query += " AND time >= %s"
                    params.append(start_time)

                if end_time:
                    query += " AND time <= %s"
                    params.append(end_time)

                # Add group by for aggregations
                if aggregation and aggregation.lower() != "none":
                    query += f" GROUP BY time_bucket('{interval or '1 hour'}', time), device_id, probe_id, grill_id, unit"

                # Add order by
                query += " ORDER BY time DESC"

                # Add limit
                if limit:
                    query += f" LIMIT {limit}"

                # Execute the query
                cursor.execute(query, params)

                # Process results
                result = []
                for row in cursor:
                    data_point = dict(row)

                    # Convert timestamp to ISO format
                    if "time" in data_point and data_point["time"]:
                        data_point["time"] = data_point["time"].isoformat()

                    # Convert metadata from JSON if needed
                    if "metadata" in data_point and data_point["metadata"]:
                        if isinstance(data_point["metadata"], str):
                            try:
                                data_point["metadata"] = json.loads(
                                    data_point["metadata"]
                                )
                            except:
                                pass

                    result.append(data_point)

                logger.debug(
                    "Temperature history retrieved",
                    count=len(result),
                    device_id=device_id,
                    probe_id=probe_id,
                    grill_id=grill_id,
                )

                return result

        except Exception as e:
            logger.error("Error retrieving temperature history", error=str(e))
            return []

    def get_temperature_statistics(
        self,
        device_id: Optional[str] = None,
        probe_id: Optional[str] = None,
        grill_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get temperature statistics for selected data."""
        try:
            if not self.connection or self.connection.closed:
                self._connect()

            with self.connection.cursor(cursor_factory=DictCursor) as cursor:
                # Build the statistics query
                query = """
                    SELECT
                        COUNT(*) as reading_count,
                        AVG(temperature) as avg_temperature,
                        MIN(temperature) as min_temperature,
                        MAX(temperature) as max_temperature,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY temperature) as median_temperature,
                        STDDEV(temperature) as stddev_temperature,
                        MIN(time) as first_reading_time,
                        MAX(time) as last_reading_time
                    FROM temperature_readings
                    WHERE 1=1
                """

                # Add filters
                params = []
                if device_id:
                    query += " AND device_id = %s"
                    params.append(device_id)

                if probe_id:
                    query += " AND probe_id = %s"
                    params.append(probe_id)

                if grill_id:
                    query += " AND grill_id = %s"
                    params.append(grill_id)

                if start_time:
                    query += " AND time >= %s"
                    params.append(start_time)

                if end_time:
                    query += " AND time <= %s"
                    params.append(end_time)

                # Execute the query
                cursor.execute(query, params)

                # Get the result
                row = cursor.fetchone()
                if row:
                    stats = dict(row)

                    # Convert timestamps to ISO format
                    for key in ["first_reading_time", "last_reading_time"]:
                        if key in stats and stats[key]:
                            stats[key] = stats[key].isoformat()

                    # Add query parameters
                    stats["query"] = {
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "grill_id": grill_id,
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                    }

                    return stats

                return {}

        except Exception as e:
            logger.error("Error retrieving temperature statistics", error=str(e))
            return {}
