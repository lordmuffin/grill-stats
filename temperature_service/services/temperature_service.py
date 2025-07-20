"""
Core Temperature Data Service.

This module provides the main service for temperature data collection,
processing, and storage. It coordinates between different components
like data sources, storage, and real-time streaming.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from opentelemetry import trace

from temperature_service.clients import (
    AsyncThermoworksClient,
    EnhancedInfluxDBClient,
    RedisClient,
    get_influxdb_client,
    get_redis_client,
    get_thermoworks_client,
)
from temperature_service.config import get_settings
from temperature_service.models import (
    AlertSeverity,
    AlertType,
    AnomalyDetectionResult,
    BatchTemperatureReadings,
    TemperatureAlert,
    TemperatureQuery,
    TemperatureReading,
    TemperatureStatistics,
)
from temperature_service.utils import trace_async_function

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class TemperatureService:
    """Core temperature data service."""

    def __init__(
        self,
        influxdb_client: Optional[EnhancedInfluxDBClient] = None,
        redis_client: Optional[RedisClient] = None,
        thermoworks_client: Optional[AsyncThermoworksClient] = None,
    ):
        """Initialize temperature service.

        Args:
            influxdb_client: Optional InfluxDB client
            redis_client: Optional Redis client
            thermoworks_client: Optional ThermoWorks client
        """
        # Will be initialized lazily if not provided
        self._influxdb_client = influxdb_client
        self._redis_client = redis_client
        self._thermoworks_client = thermoworks_client

        # Service state
        self._collection_running = False
        self._polling_task: Optional[asyncio.Task] = None
        self._known_devices: Set[str] = set()
        self._last_collection_time: Dict[str, datetime] = {}
        self._collection_stats: Dict[str, Dict[str, Any]] = {}

        # Anomaly detection state
        self._device_stats: Dict[str, Dict[str, Any]] = {}

        logger.info("Temperature service initialized")

    async def initialize(self) -> None:
        """Initialize service and connections."""
        # Initialize clients if not provided
        if self._influxdb_client is None:
            self._influxdb_client = await get_influxdb_client()

        if self._redis_client is None:
            self._redis_client = await get_redis_client()

        if self._thermoworks_client is None:
            self._thermoworks_client = await get_thermoworks_client()

        logger.info("Temperature service connections initialized")

    async def close(self) -> None:
        """Close service and connections."""
        # Stop collection
        await self.stop_collection()

        # No need to close individual clients as they will be
        # closed by their respective singletons
        logger.info("Temperature service closed")

    @trace_async_function(name="temperature_service_health_check")
    async def health_check(self) -> Dict[str, Any]:
        """Check service health.

        Returns:
            Health check result
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "collection": {
                "running": self._collection_running,
                "known_devices": len(self._known_devices),
                "stats": self._collection_stats,
            },
        }

        # Check InfluxDB
        try:
            if self._influxdb_client:
                influxdb_healthy = await self._influxdb_client.health_check()
                health["components"]["influxdb"] = "healthy" if influxdb_healthy else "unhealthy"
            else:
                health["components"]["influxdb"] = "not_initialized"
        except Exception as e:
            health["components"]["influxdb"] = f"error: {str(e)}"

        # Check Redis
        try:
            if self._redis_client:
                redis_healthy = await self._redis_client.health_check()
                health["components"]["redis"] = "healthy" if redis_healthy else "unhealthy"
            else:
                health["components"]["redis"] = "not_initialized"
        except Exception as e:
            health["components"]["redis"] = f"error: {str(e)}"

        # Check ThermoWorks API
        try:
            # Just try to list devices
            if self._thermoworks_client:
                devices = await self._thermoworks_client.get_devices()
                health["components"]["thermoworks_api"] = "healthy" if devices else "degraded"
            else:
                health["components"]["thermoworks_api"] = "not_initialized"
        except Exception as e:
            health["components"]["thermoworks_api"] = f"error: {str(e)}"

        # Determine overall status
        component_statuses = [
            status for status in health["components"].values() if isinstance(status, str) and not status.startswith("error")
        ]

        if "unhealthy" in component_statuses:
            health["status"] = "unhealthy"
        elif "degraded" in component_statuses or "not_initialized" in component_statuses:
            health["status"] = "degraded"

        return health

    @trace_async_function(name="temperature_service_start_collection")
    async def start_collection(
        self,
        interval: Optional[int] = None,
        devices: Optional[List[str]] = None,
    ) -> None:
        """Start temperature data collection.

        Args:
            interval: Collection interval in seconds (defaults to config)
            devices: Optional list of specific device IDs to collect
        """
        if self._collection_running:
            logger.warning("Temperature collection already running")
            return

        # Initialize connections if needed
        await self.initialize()

        # Get collection interval
        collection_interval = interval or settings.service.collection_interval

        # Set initial state
        self._collection_running = True
        self._known_devices = set(devices) if devices else set()
        self._collection_stats = {
            "start_time": datetime.utcnow().isoformat(),
            "collections": 0,
            "readings": 0,
            "errors": 0,
            "last_collection": None,
            "devices": {},
        }

        # Start collection task
        self._polling_task = asyncio.create_task(self._collection_loop(collection_interval))

        logger.info("Started temperature collection (interval: %d seconds)", collection_interval)

    @trace_async_function(name="temperature_service_stop_collection")
    async def stop_collection(self) -> None:
        """Stop temperature data collection."""
        if not self._collection_running:
            return

        self._collection_running = False

        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

        logger.info("Stopped temperature collection")

    async def _collection_loop(self, interval: int) -> None:
        """Main collection loop.

        Args:
            interval: Collection interval in seconds
        """
        try:
            while self._collection_running:
                try:
                    # Collect temperature data
                    start_time = time.time()
                    await self._collect_temperature_data()

                    # Update stats
                    self._collection_stats["collections"] += 1
                    self._collection_stats["last_collection"] = datetime.utcnow().isoformat()

                    # Calculate sleep time
                    elapsed = time.time() - start_time
                    sleep_time = max(0.1, interval - elapsed)

                    logger.debug(
                        "Temperature collection completed in %.2f seconds, " "sleeping for %.2f seconds", elapsed, sleep_time
                    )

                    await asyncio.sleep(sleep_time)
                except asyncio.CancelledError:
                    logger.info("Temperature collection task cancelled")
                    break
                except Exception as e:
                    logger.error("Error in temperature collection: %s", str(e))
                    self._collection_stats["errors"] += 1
                    await asyncio.sleep(max(1, interval // 2))
        finally:
            self._collection_running = False
            logger.info("Temperature collection loop stopped")

    @trace_async_function(name="temperature_service_collect_temperature_data")
    async def _collect_temperature_data(self) -> None:
        """Collect temperature data from all devices."""
        if not self._thermoworks_client:
            logger.error("ThermoWorks client not initialized")
            return

        # Discover devices if needed
        if not self._known_devices:
            devices = await self._thermoworks_client.get_devices()
            self._known_devices = {device["device_id"] for device in devices}

            for device_id in self._known_devices:
                if device_id not in self._collection_stats["devices"]:
                    self._collection_stats["devices"][device_id] = {
                        "collections": 0,
                        "readings": 0,
                        "errors": 0,
                        "last_collection": None,
                    }

        # Collect data for each device
        collection_tasks = []
        for device_id in self._known_devices:
            task = self._collect_device_data(device_id)
            collection_tasks.append(task)

        # Wait for all collection tasks to complete
        if collection_tasks:
            await asyncio.gather(*collection_tasks, return_exceptions=True)

    @trace_async_function(name="temperature_service_collect_device_data")
    async def _collect_device_data(self, device_id: str) -> None:
        """Collect temperature data for a specific device.

        Args:
            device_id: Device ID
        """
        try:
            # Get device data
            device_data = await self._thermoworks_client.get_device_data(device_id)

            # Process each channel/probe
            readings = []
            for channel in device_data.get("channels", []):
                temperature = channel.get("temperature")
                if temperature is None:
                    continue

                # Create reading
                reading = TemperatureReading(
                    device_id=device_id,
                    probe_id=channel.get("channel_id"),
                    temperature=temperature,
                    unit=channel.get("unit", "F"),
                    timestamp=datetime.utcnow(),
                    battery_level=device_data.get("status", {}).get("battery_level"),
                    signal_strength=device_data.get("status", {}).get("signal_strength"),
                )

                readings.append(reading)

            # Store readings
            if readings:
                await self._store_temperature_readings(readings)

                # Update device stats
                device_stats = self._collection_stats["devices"].get(
                    device_id,
                    {
                        "collections": 0,
                        "readings": 0,
                        "errors": 0,
                        "last_collection": None,
                    },
                )

                device_stats["collections"] += 1
                device_stats["readings"] += len(readings)
                device_stats["last_collection"] = datetime.utcnow().isoformat()

                self._collection_stats["devices"][device_id] = device_stats
                self._collection_stats["readings"] += len(readings)

                # Record last collection time
                self._last_collection_time[device_id] = datetime.utcnow()

                logger.debug("Collected %d temperature readings for device %s", len(readings), device_id)
            else:
                logger.warning("No temperature readings collected for device %s", device_id)
        except Exception as e:
            logger.error("Error collecting temperature data for device %s: %s", device_id, str(e))

            # Update error stats
            device_stats = self._collection_stats["devices"].get(
                device_id,
                {
                    "collections": 0,
                    "readings": 0,
                    "errors": 0,
                    "last_collection": None,
                },
            )

            device_stats["errors"] += 1
            self._collection_stats["devices"][device_id] = device_stats

    @trace_async_function(name="temperature_service_store_temperature_readings")
    async def _store_temperature_readings(
        self,
        readings: List[TemperatureReading],
    ) -> None:
        """Store temperature readings.

        Args:
            readings: Temperature readings to store
        """
        if not readings:
            return

        # Store in InfluxDB
        await self._store_in_influxdb(readings)

        # Publish to Redis
        await self._publish_to_redis(readings)

        # Check for anomalies
        if settings.service.enable_anomaly_detection:
            await self._check_for_anomalies(readings)

    @trace_async_function(name="temperature_service_store_in_influxdb")
    async def _store_in_influxdb(self, readings: List[TemperatureReading]) -> None:
        """Store temperature readings in InfluxDB.

        Args:
            readings: Temperature readings to store
        """
        if not self._influxdb_client:
            logger.warning("InfluxDB client not initialized, skipping storage")
            return

        try:
            # Convert readings to InfluxDB points
            points = []
            for reading in readings:
                point = {
                    "measurement": "temperature",
                    "tags": {
                        "device_id": reading.device_id,
                        "unit": reading.unit,
                    },
                    "fields": {
                        "temperature": float(reading.temperature),
                    },
                    "time": reading.timestamp.isoformat(),
                }

                # Add probe_id if present
                if reading.probe_id:
                    point["tags"]["probe_id"] = reading.probe_id

                # Add optional fields
                if reading.battery_level is not None:
                    point["fields"]["battery_level"] = float(reading.battery_level)

                if reading.signal_strength is not None:
                    point["fields"]["signal_strength"] = float(reading.signal_strength)

                # Add metadata
                for key, value in reading.metadata.items():
                    if isinstance(value, (int, float)):
                        point["fields"][f"meta_{key}"] = float(value)
                    else:
                        point["tags"][f"meta_{key}"] = str(value)

                points.append(point)

            # Write to InfluxDB
            success = await self._influxdb_client.write_points(points)

            if not success:
                logger.error("Failed to write %d temperature readings to InfluxDB", len(readings))
        except Exception as e:
            logger.error("Error storing temperature readings in InfluxDB: %s", str(e))

    @trace_async_function(name="temperature_service_publish_to_redis")
    async def _publish_to_redis(self, readings: List[TemperatureReading]) -> None:
        """Publish temperature readings to Redis.

        Args:
            readings: Temperature readings to publish
        """
        if not self._redis_client or not settings.service.enable_redis_pubsub:
            return

        try:
            # Add readings to stream
            for reading in readings:
                # Convert to dict for JSON serialization
                reading_dict = reading.dict()

                # Add to stream
                stream_key = settings.redis.stream_key
                await self._redis_client.add_to_stream(
                    stream_key,
                    reading_dict,
                    max_len=settings.redis.max_stream_length,
                )

                # Publish to channel
                channel = settings.redis.pub_sub_channels["temperature"]
                await self._redis_client.publish(channel, reading_dict)

                logger.debug("Published temperature reading for device %s to Redis", reading.device_id)
        except Exception as e:
            logger.error("Error publishing temperature readings to Redis: %s", str(e))

    @trace_async_function(name="temperature_service_check_for_anomalies")
    async def _check_for_anomalies(self, readings: List[TemperatureReading]) -> None:
        """Check for anomalies in temperature readings.

        Args:
            readings: Temperature readings to check
        """
        for reading in readings:
            device_key = f"{reading.device_id}:{reading.probe_id or 'default'}"

            # Get device stats
            if device_key not in self._device_stats:
                self._device_stats[device_key] = {
                    "min_temp": reading.temperature,
                    "max_temp": reading.temperature,
                    "sum_temp": reading.temperature,
                    "count": 1,
                    "readings": [reading.temperature],
                    "last_reading": reading.temperature,
                    "last_reading_time": reading.timestamp,
                }
                continue

            stats = self._device_stats[device_key]

            # Calculate expected range based on history
            min_temp = stats["min_temp"]
            max_temp = stats["max_temp"]
            avg_temp = stats["sum_temp"] / stats["count"]

            # Keep a window of readings for variance calculation
            readings_window = stats["readings"][-10:] + [reading.temperature]

            # Calculate standard deviation
            if len(readings_window) > 1:
                mean = sum(readings_window) / len(readings_window)
                variance = sum((x - mean) ** 2 for x in readings_window) / len(readings_window)
                stddev = variance**0.5
            else:
                stddev = 0

            # Define expected range as avg +/- 3*stddev
            expected_min = avg_temp - 3 * stddev
            expected_max = avg_temp + 3 * stddev

            # Calculate rate of change
            time_delta = (reading.timestamp - stats["last_reading_time"]).total_seconds()
            if time_delta > 0:
                rate_of_change = abs(reading.temperature - stats["last_reading"]) / time_delta
            else:
                rate_of_change = 0

            # Check for anomalies
            is_anomaly = False
            anomaly_confidence = 0.0

            # Temperature outside expected range
            if reading.temperature < expected_min or reading.temperature > expected_max:
                is_anomaly = True
                # Calculate confidence based on deviation from expected range
                deviation = min(abs(reading.temperature - expected_min), abs(reading.temperature - expected_max))
                anomaly_confidence = min(1.0, deviation / (max(1, stddev)))

            # Rapid temperature change
            if rate_of_change > 5 and time_delta < 300:  # >5 degrees per second, within 5 minutes
                is_anomaly = True
                anomaly_confidence = max(anomaly_confidence, min(1.0, rate_of_change / 10))

            # Create anomaly detection result
            if is_anomaly and anomaly_confidence > 0.7:  # Only report high confidence anomalies
                anomaly = AnomalyDetectionResult(
                    device_id=reading.device_id,
                    probe_id=reading.probe_id,
                    timestamp=reading.timestamp,
                    reading=reading.temperature,
                    is_anomaly=True,
                    confidence=anomaly_confidence,
                    expected_range={
                        "min": expected_min,
                        "max": expected_max,
                        "avg": avg_temp,
                    },
                    deviation=abs(reading.temperature - avg_temp),
                    context_window=[
                        {
                            "timestamp": (stats["last_reading_time"] - timedelta(seconds=i * 30)).isoformat(),
                            "temperature": temp,
                        }
                        for i, temp in enumerate(reversed(stats["readings"][-5:]))
                    ],
                )

                # Create alert
                alert = TemperatureAlert(
                    device_id=reading.device_id,
                    alert_type=AlertType.ANOMALY,
                    severity=AlertSeverity.WARNING if anomaly_confidence < 0.9 else AlertSeverity.CRITICAL,
                    timestamp=reading.timestamp,
                    temperature=reading.temperature,
                    probe_id=reading.probe_id,
                    message=f"Anomalous temperature reading detected: {reading.temperature}°F (expected range: {expected_min:.1f}-{expected_max:.1f}°F)",
                    related_readings=anomaly.context_window,
                )

                # Publish alert
                if self._redis_client and settings.service.enable_redis_pubsub:
                    alert_channel = settings.redis.pub_sub_channels["alerts"]
                    await self._redis_client.publish(alert_channel, alert.dict())

                logger.warning(
                    "Anomaly detected for device %s: %.1f°F (expected range: %.1f-%.1f°F)",
                    reading.device_id,
                    reading.temperature,
                    expected_min,
                    expected_max,
                )

            # Update stats
            stats["min_temp"] = min(stats["min_temp"], reading.temperature)
            stats["max_temp"] = max(stats["max_temp"], reading.temperature)
            stats["sum_temp"] += reading.temperature
            stats["count"] += 1
            stats["last_reading"] = reading.temperature
            stats["last_reading_time"] = reading.timestamp
            stats["readings"] = readings_window

    @trace_async_function(name="temperature_service_get_current_temperature")
    async def get_current_temperature(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get current temperature for a device.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID

        Returns:
            Current temperature data
        """
        # Check if we have cached data from recent collection
        if device_id in self._last_collection_time:
            last_time = self._last_collection_time[device_id]
            if (datetime.utcnow() - last_time).total_seconds() < 30:
                # Data is fresh, get from cache
                if self._redis_client:
                    cache_key = f"temperature:current:{device_id}"
                    if probe_id:
                        cache_key += f":{probe_id}"

                    cached_data = await self._redis_client.get(cache_key)
                    if cached_data:
                        logger.debug("Retrieved temperature data from cache for device %s", device_id)
                        return {
                            "status": "success",
                            "data": cached_data,
                            "source": "cache",
                        }

        # No fresh data, get from ThermoWorks API
        if self._thermoworks_client:
            try:
                temperature_data = await self._thermoworks_client.get_temperature_data(device_id, probe_id)

                if temperature_data and temperature_data.get("temperature") is not None:
                    # Cache the result
                    if self._redis_client:
                        cache_key = f"temperature:current:{device_id}"
                        if probe_id:
                            cache_key += f":{probe_id}"

                        await self._redis_client.set(cache_key, temperature_data, expire=30)

                    # Store in InfluxDB
                    reading = TemperatureReading(
                        device_id=device_id,
                        probe_id=probe_id,
                        temperature=temperature_data["temperature"],
                        unit=temperature_data.get("unit", "F"),
                        timestamp=datetime.utcnow(),
                        battery_level=temperature_data.get("battery_level"),
                        signal_strength=temperature_data.get("signal_strength"),
                    )

                    await self._store_temperature_readings([reading])

                    return {
                        "status": "success",
                        "data": temperature_data,
                        "source": "api",
                    }
                else:
                    return {
                        "status": "error",
                        "message": "No temperature data available",
                    }
            except Exception as e:
                logger.error("Failed to get current temperature for device %s: %s", device_id, str(e))
                return {
                    "status": "error",
                    "message": str(e),
                }

        return {
            "status": "error",
            "message": "ThermoWorks client not initialized",
        }

    @trace_async_function(name="temperature_service_get_temperature_history")
    async def get_temperature_history(
        self,
        query: TemperatureQuery,
    ) -> Dict[str, Any]:
        """Get historical temperature data.

        Args:
            query: Query parameters

        Returns:
            Historical temperature data
        """
        if not self._influxdb_client:
            return {
                "status": "error",
                "message": "InfluxDB client not initialized",
            }

        try:
            # Set default time range if not provided
            if query.start_time is None:
                query.start_time = datetime.utcnow() - timedelta(hours=24)

            if query.end_time is None:
                query.end_time = datetime.utcnow()

            # Get historical data
            history_data = await self._influxdb_client.get_temperature_history(
                device_id=query.device_id,
                probe_id=query.probe_id,
                start_time=query.start_time,
                end_time=query.end_time,
                aggregation=query.aggregation or "none",
                interval=query.interval or "1m",
                limit=query.limit or 1000,
                offset=query.offset or 0,
            )

            return {
                "status": "success",
                "data": history_data,
                "count": len(history_data),
                "query": {
                    "device_id": query.device_id,
                    "probe_id": query.probe_id,
                    "start_time": query.start_time.isoformat() if query.start_time else None,
                    "end_time": query.end_time.isoformat() if query.end_time else None,
                    "aggregation": query.aggregation,
                    "interval": query.interval,
                },
            }
        except Exception as e:
            logger.error("Failed to get temperature history for device %s: %s", query.device_id, str(e))
            return {
                "status": "error",
                "message": str(e),
            }

    @trace_async_function(name="temperature_service_get_temperature_statistics")
    async def get_temperature_statistics(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get temperature statistics.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Temperature statistics
        """
        if not self._influxdb_client:
            return {
                "status": "error",
                "message": "InfluxDB client not initialized",
            }

        try:
            # Set default time range if not provided
            if start_time is None:
                start_time = datetime.utcnow() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.utcnow()

            # Get statistics
            stats = await self._influxdb_client.get_temperature_statistics(
                device_id=device_id,
                probe_id=probe_id,
                start_time=start_time,
                end_time=end_time,
            )

            return {
                "status": "success",
                "data": stats,
                "query": {
                    "device_id": device_id,
                    "probe_id": probe_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                },
            }
        except Exception as e:
            logger.error("Failed to get temperature statistics for device %s: %s", device_id, str(e))
            return {
                "status": "error",
                "message": str(e),
            }

    @trace_async_function(name="temperature_service_get_temperature_alerts")
    async def get_temperature_alerts(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        threshold_high: float = 250.0,
        threshold_low: float = 32.0,
    ) -> Dict[str, Any]:
        """Get temperature alerts.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID
            start_time: Optional start time
            end_time: Optional end time
            threshold_high: High temperature threshold
            threshold_low: Low temperature threshold

        Returns:
            Temperature alerts
        """
        if not self._influxdb_client:
            return {
                "status": "error",
                "message": "InfluxDB client not initialized",
            }

        try:
            # Set default time range if not provided
            if start_time is None:
                start_time = datetime.utcnow() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.utcnow()

            # Get alerts
            alerts = await self._influxdb_client.get_temperature_alerts(
                device_id=device_id,
                probe_id=probe_id,
                start_time=start_time,
                end_time=end_time,
                threshold_high=threshold_high,
                threshold_low=threshold_low,
            )

            return {
                "status": "success",
                "data": alerts,
                "count": len(alerts),
                "query": {
                    "device_id": device_id,
                    "probe_id": probe_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "threshold_high": threshold_high,
                    "threshold_low": threshold_low,
                },
            }
        except Exception as e:
            logger.error("Failed to get temperature alerts for device %s: %s", device_id, str(e))
            return {
                "status": "error",
                "message": str(e),
            }

    @trace_async_function(name="temperature_service_store_batch_readings")
    async def store_batch_readings(
        self,
        batch: BatchTemperatureReadings,
    ) -> Dict[str, Any]:
        """Store a batch of temperature readings.

        Args:
            batch: Batch of temperature readings

        Returns:
            Result of batch storage
        """
        if not batch.readings:
            return {
                "status": "error",
                "message": "No readings provided",
            }

        try:
            # Store readings
            await self._store_temperature_readings(batch.readings)

            return {
                "status": "success",
                "stored_count": len(batch.readings),
                "total_count": len(batch.readings),
            }
        except Exception as e:
            logger.error("Failed to store batch temperature data: %s", str(e))
            return {
                "status": "error",
                "message": str(e),
            }

    @trace_async_function(name="temperature_service_get_device_live_data")
    async def get_device_live_data(self, device_id: str) -> Dict[str, Any]:
        """Get live data for a device.

        Args:
            device_id: Device ID

        Returns:
            Live device data
        """
        if not self._thermoworks_client:
            return {
                "status": "error",
                "message": "ThermoWorks client not initialized",
            }

        try:
            # Check cache first
            if self._redis_client:
                cache_key = f"live_data:{device_id}"
                cached_data = await self._redis_client.get(cache_key)
                if cached_data:
                    return {
                        "status": "success",
                        "data": cached_data,
                        "source": "cache",
                    }

            # Get device data from ThermoWorks API
            device_data = await self._thermoworks_client.get_device_data(device_id)

            # Store in time-series database
            readings = []
            for channel in device_data.get("channels", []):
                if channel.get("temperature") is not None:
                    reading = TemperatureReading(
                        device_id=device_id,
                        probe_id=channel.get("channel_id"),
                        temperature=channel.get("temperature"),
                        unit=channel.get("unit", "F"),
                        timestamp=datetime.utcnow(),
                        battery_level=device_data.get("status", {}).get("battery_level"),
                        signal_strength=device_data.get("status", {}).get("signal_strength"),
                    )
                    readings.append(reading)

            if readings:
                await self._store_temperature_readings(readings)

            # Cache the result
            if self._redis_client:
                cache_key = f"live_data:{device_id}"
                await self._redis_client.set(cache_key, device_data, expire=30)

            return {
                "status": "success",
                "data": device_data,
                "source": "api",
            }
        except Exception as e:
            logger.error("Failed to get live device data for %s: %s", device_id, str(e))
            return {
                "status": "error",
                "message": str(e),
            }


# Singleton instance for application-wide use
_temperature_service: Optional[TemperatureService] = None


async def get_temperature_service() -> TemperatureService:
    """Get or create the temperature service singleton."""
    global _temperature_service

    if _temperature_service is None:
        _temperature_service = TemperatureService()
        await _temperature_service.initialize()

    return _temperature_service


async def close_temperature_service() -> None:
    """Close the temperature service singleton."""
    global _temperature_service

    if _temperature_service is not None:
        await _temperature_service.close()
        _temperature_service = None
