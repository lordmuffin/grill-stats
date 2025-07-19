import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog
from influxdb import InfluxDBClient

logger = structlog.get_logger()


class TemperatureManager:
    def __init__(
        self,
        influxdb_host: str,
        influxdb_port: int,
        influxdb_database: str,
        influxdb_username: str = None,
        influxdb_password: str = None,
    ):
        self.client = InfluxDBClient(
            host=influxdb_host,
            port=influxdb_port,
            username=influxdb_username,
            password=influxdb_password,
            database=influxdb_database,
        )
        self.database = influxdb_database

    def health_check(self):
        """Check InfluxDB connection health"""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error("InfluxDB health check failed", error=str(e))
            raise

    def init_db(self):
        """Initialize InfluxDB database and retention policies"""
        try:
            # Create database if it doesn't exist
            databases = self.client.get_list_database()
            if not any(db["name"] == self.database for db in databases):
                self.client.create_database(self.database)
                logger.info("Created InfluxDB database", database=self.database)

            # Switch to the database
            self.client.switch_database(self.database)

            # Create retention policies
            retention_policies = [
                {
                    "name": "one_day",
                    "duration": "1d",
                    "replication": 1,
                    "default": False,
                },
                {
                    "name": "one_week",
                    "duration": "7d",
                    "replication": 1,
                    "default": False,
                },
                {
                    "name": "one_month",
                    "duration": "30d",
                    "replication": 1,
                    "default": False,
                },
                {
                    "name": "one_year",
                    "duration": "365d",
                    "replication": 1,
                    "default": True,
                },
            ]

            for policy in retention_policies:
                try:
                    self.client.create_retention_policy(
                        name=policy["name"],
                        duration=policy["duration"],
                        replication=policy["replication"],
                        database=self.database,
                        default=policy["default"],
                    )
                    logger.info(
                        "Created retention policy",
                        name=policy["name"],
                        duration=policy["duration"],
                    )
                except Exception as e:
                    # Policy might already exist
                    logger.debug(
                        "Retention policy creation skipped",
                        name=policy["name"],
                        error=str(e),
                    )

            logger.info("InfluxDB initialized successfully")

        except Exception as e:
            logger.error("InfluxDB initialization failed", error=str(e))
            raise

    def store_temperature_reading(self, reading_data: Dict) -> bool:
        """Store a single temperature reading"""
        try:
            # Prepare data point
            data_point = {
                "measurement": "temperature",
                "tags": {
                    "device_id": reading_data["device_id"],
                    "unit": reading_data.get("unit", "F"),
                },
                "fields": {
                    "temperature": float(reading_data["temperature"]),
                    "battery_level": reading_data.get("battery_level"),
                    "signal_strength": reading_data.get("signal_strength"),
                },
                "time": reading_data.get("timestamp", datetime.utcnow().isoformat()),
            }

            # Add probe_id if present
            if reading_data.get("probe_id"):
                data_point["tags"]["probe_id"] = reading_data["probe_id"]

            # Add metadata fields
            if reading_data.get("metadata"):
                for key, value in reading_data["metadata"].items():
                    if isinstance(value, (int, float)):
                        data_point["fields"][f"meta_{key}"] = value
                    else:
                        data_point["tags"][f"meta_{key}"] = str(value)

            # Write to InfluxDB
            success = self.client.write_points([data_point])

            if success:
                logger.debug("Temperature reading stored", device_id=reading_data["device_id"])
            else:
                logger.warning(
                    "Failed to store temperature reading",
                    device_id=reading_data["device_id"],
                )

            return success

        except Exception as e:
            logger.error(
                "Error storing temperature reading",
                device_id=reading_data.get("device_id"),
                error=str(e),
            )
            return False

    def store_batch_temperature_readings(self, readings: List[Dict]) -> int:
        """Store multiple temperature readings at once"""
        try:
            data_points = []

            for reading_data in readings:
                data_point = {
                    "measurement": "temperature",
                    "tags": {
                        "device_id": reading_data["device_id"],
                        "unit": reading_data.get("unit", "F"),
                    },
                    "fields": {"temperature": float(reading_data["temperature"])},
                    "time": reading_data.get("timestamp", datetime.utcnow().isoformat()),
                }

                # Add probe_id if present
                if reading_data.get("probe_id"):
                    data_point["tags"]["probe_id"] = reading_data["probe_id"]

                # Add optional fields
                for field in ["battery_level", "signal_strength"]:
                    if reading_data.get(field) is not None:
                        data_point["fields"][field] = reading_data[field]

                # Add metadata
                if reading_data.get("metadata"):
                    for key, value in reading_data["metadata"].items():
                        if isinstance(value, (int, float)):
                            data_point["fields"][f"meta_{key}"] = value
                        else:
                            data_point["tags"][f"meta_{key}"] = str(value)

                data_points.append(data_point)

            # Write batch to InfluxDB
            success = self.client.write_points(data_points, batch_size=1000)

            if success:
                logger.info("Batch temperature readings stored", count=len(data_points))
                return len(data_points)
            else:
                logger.warning("Failed to store batch temperature readings")
                return 0

        except Exception as e:
            logger.error("Error storing batch temperature readings", error=str(e))
            return 0

    def get_temperature_history(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: str = "none",
        interval: str = "1m",
    ) -> List[Dict]:
        """Get historical temperature data"""
        try:
            # Build query
            query = f"SELECT "

            if aggregation == "none":
                query += "temperature, battery_level, signal_strength"
            elif aggregation == "mean":
                query += f"MEAN(temperature) as temperature"
            elif aggregation == "max":
                query += f"MAX(temperature) as temperature"
            elif aggregation == "min":
                query += f"MIN(temperature) as temperature"
            else:
                query += "temperature"

            query += f" FROM temperature WHERE device_id = '{device_id}'"

            if probe_id:
                query += f" AND probe_id = '{probe_id}'"

            if start_time:
                query += f" AND time >= '{start_time.isoformat()}'"

            if end_time:
                query += f" AND time <= '{end_time.isoformat()}'"

            if aggregation != "none":
                query += f" GROUP BY time({interval}) fill(null)"

            query += " ORDER BY time DESC"

            # Execute query
            result = self.client.query(query)

            # Format results
            data_points = []
            for point in result.get_points():
                data_point = {
                    "timestamp": point["time"],
                    "temperature": point.get("temperature"),
                    "device_id": device_id,
                }

                if probe_id:
                    data_point["probe_id"] = probe_id

                # Add optional fields
                for field in ["battery_level", "signal_strength"]:
                    if point.get(field) is not None:
                        data_point[field] = point[field]

                data_points.append(data_point)

            logger.debug(
                "Temperature history retrieved",
                device_id=device_id,
                count=len(data_points),
            )

            return data_points

        except Exception as e:
            logger.error(
                "Error retrieving temperature history",
                device_id=device_id,
                error=str(e),
            )
            return []

    def get_temperature_statistics(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict:
        """Get temperature statistics for a device"""
        try:
            # Build query
            query = f"""
                SELECT
                    MEAN(temperature) as avg_temperature,
                    MAX(temperature) as max_temperature,
                    MIN(temperature) as min_temperature,
                    COUNT(temperature) as count,
                    STDDEV(temperature) as stddev_temperature
                FROM temperature
                WHERE device_id = '{device_id}'
            """

            if probe_id:
                query += f" AND probe_id = '{probe_id}'"

            if start_time:
                query += f" AND time >= '{start_time.isoformat()}'"

            if end_time:
                query += f" AND time <= '{end_time.isoformat()}'"

            # Execute query
            result = self.client.query(query)

            stats = {}
            for point in result.get_points():
                stats = {
                    "avg_temperature": point.get("avg_temperature"),
                    "max_temperature": point.get("max_temperature"),
                    "min_temperature": point.get("min_temperature"),
                    "count": point.get("count", 0),
                    "stddev_temperature": point.get("stddev_temperature"),
                    "device_id": device_id,
                }

                if probe_id:
                    stats["probe_id"] = probe_id

                break  # Only one result expected

            logger.debug("Temperature statistics retrieved", device_id=device_id)
            return stats

        except Exception as e:
            logger.error(
                "Error retrieving temperature statistics",
                device_id=device_id,
                error=str(e),
            )
            return {}

    def get_temperature_alerts(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        threshold_high: float = 250.0,
        threshold_low: float = 32.0,
    ) -> List[Dict]:
        """Get temperature alerts (readings outside normal range)"""
        try:
            # Build query for high temperatures
            query_high = f"""
                SELECT temperature, time
                FROM temperature
                WHERE device_id = '{device_id}'
                AND temperature > {threshold_high}
            """

            # Build query for low temperatures
            query_low = f"""
                SELECT temperature, time
                FROM temperature
                WHERE device_id = '{device_id}'
                AND temperature < {threshold_low}
            """

            if probe_id:
                query_high += f" AND probe_id = '{probe_id}'"
                query_low += f" AND probe_id = '{probe_id}'"

            if start_time:
                query_high += f" AND time >= '{start_time.isoformat()}'"
                query_low += f" AND time >= '{start_time.isoformat()}'"

            if end_time:
                query_high += f" AND time <= '{end_time.isoformat()}'"
                query_low += f" AND time <= '{end_time.isoformat()}'"

            query_high += " ORDER BY time DESC"
            query_low += " ORDER BY time DESC"

            alerts = []

            # Get high temperature alerts
            result_high = self.client.query(query_high)
            for point in result_high.get_points():
                alerts.append(
                    {
                        "timestamp": point["time"],
                        "temperature": point["temperature"],
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "alert_type": "high_temperature",
                        "threshold": threshold_high,
                        "severity": ("warning" if point["temperature"] < threshold_high + 50 else "critical"),
                    }
                )

            # Get low temperature alerts
            result_low = self.client.query(query_low)
            for point in result_low.get_points():
                alerts.append(
                    {
                        "timestamp": point["time"],
                        "temperature": point["temperature"],
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "alert_type": "low_temperature",
                        "threshold": threshold_low,
                        "severity": "warning",
                    }
                )

            # Sort by timestamp
            alerts.sort(key=lambda x: x["timestamp"], reverse=True)

            logger.debug("Temperature alerts retrieved", device_id=device_id, count=len(alerts))

            return alerts

        except Exception as e:
            logger.error("Error retrieving temperature alerts", device_id=device_id, error=str(e))
            return []
