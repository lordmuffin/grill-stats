"""
Enhanced InfluxDB client with connection pooling and advanced features.

This module provides a high-performance InfluxDB client with connection pooling,
retry logic, and circuit breaker integration for improved resilience.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
from influxdb import InfluxDBClient
from opentelemetry import trace

from temperature_service.config import InfluxDBSettings, get_settings
from temperature_service.utils import (
    CircuitBreaker,
    CircuitBreakerError,
    create_circuit_breaker,
    trace_async_function,
    trace_function,
)

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class InfluxDBConnectionPool:
    """Connection pool for InfluxDB clients."""

    def __init__(
        self,
        host: str = settings.influxdb.host,
        port: int = settings.influxdb.port,
        username: Optional[str] = settings.influxdb.username,
        password: Optional[str] = settings.influxdb.password,
        database: str = settings.influxdb.database,
        ssl: bool = settings.influxdb.ssl,
        verify_ssl: bool = settings.influxdb.verify_ssl,
        timeout: int = settings.influxdb.timeout,
        pool_size: int = settings.influxdb.connection_pool_size,
        retries: int = settings.influxdb.retries,
    ):
        """Initialize connection pool.

        Args:
            host: InfluxDB host
            port: InfluxDB port
            username: InfluxDB username
            password: InfluxDB password
            database: InfluxDB database
            ssl: Use SSL for connection
            verify_ssl: Verify SSL certificate
            timeout: Connection timeout in seconds
            pool_size: Number of connections in pool
            retries: Number of retries on connection failure
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.ssl = ssl
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.pool_size = pool_size
        self.retries = retries

        # Initialize connection pool
        self._pool: List[InfluxDBClient] = []
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=pool_size)

        # Create circuit breaker
        self._circuit_breaker = create_circuit_breaker(
            name="influxdb",
            failure_threshold=3,
            recovery_timeout=30,
        )

        logger.info("Initialized InfluxDB connection pool (host: %s, port: %d, pool_size: %d)", host, port, pool_size)

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            # Only initialize if pool is empty
            if not self._pool:
                for _ in range(self.pool_size):
                    client = self._create_client()
                    self._pool.append(client)

                logger.info("InfluxDB connection pool initialized with %d connections", self.pool_size)

    def _create_client(self) -> InfluxDBClient:
        """Create a new InfluxDB client."""
        client = InfluxDBClient(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            database=self.database,
            ssl=self.ssl,
            verify_ssl=self.verify_ssl,
            timeout=self.timeout,
        )

        # Test connection by pinging server
        try:
            client.ping()
            client.create_database(self.database)
            client.switch_database(self.database)
            logger.debug("Created new InfluxDB client connection")
            return client
        except Exception as e:
            logger.error("Failed to create InfluxDB client connection: %s", str(e))
            raise

    async def get_client(self) -> InfluxDBClient:
        """Get a client from the pool."""
        # Initialize pool if needed
        if not self._pool:
            await self.initialize()

        # Try to get client from pool
        async with self._lock:
            if self._pool:
                client = self._pool.pop()
                return client
            else:
                # If pool is empty, create a new client
                logger.warning("InfluxDB connection pool is empty, creating new client")
                return self._create_client()

    async def release_client(self, client: InfluxDBClient) -> None:
        """Return a client to the pool."""
        async with self._lock:
            try:
                # Test connection before returning to pool
                client.ping()
                self._pool.append(client)
            except Exception as e:
                logger.warning("Discarding bad InfluxDB connection: %s", str(e))
                # Create a new connection to replace the bad one
                try:
                    new_client = self._create_client()
                    self._pool.append(new_client)
                except Exception:
                    logger.error("Failed to create replacement InfluxDB connection")

    async def close(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for client in self._pool:
                try:
                    client.close()
                except Exception as e:
                    logger.warning("Error closing InfluxDB connection: %s", str(e))

            self._pool.clear()
            self._executor.shutdown(wait=False)
            logger.info("InfluxDB connection pool closed")

    async def execute(self, func_name: str, *args, **kwargs) -> Any:
        """Execute a function on an InfluxDB client from the pool.

        Args:
            func_name: Name of the InfluxDBClient method to call
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        Returns:
            Result of the function call
        """
        # Try operation with circuit breaker
        try:
            return await self._circuit_breaker_execute(func_name, *args, **kwargs)
        except CircuitBreakerError as e:
            logger.error("InfluxDB circuit breaker open: %s", str(e))
            raise

    @trace_async_function(name="influxdb_execute")
    async def _circuit_breaker_execute(self, func_name: str, *args, **kwargs) -> Any:
        """Execute with circuit breaker protection."""
        if self._circuit_breaker.is_open:
            raise CircuitBreakerError("influxdb", self._circuit_breaker.last_failure)

        # Get client from pool
        client = await self.get_client()

        try:
            # Get the function to call
            func = getattr(client, func_name)

            # Execute in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with tracer.start_as_current_span(f"influxdb.{func_name}"):
                result = await loop.run_in_executor(self._executor, partial(self._execute_with_retry, func, *args, **kwargs))

            # Record success in circuit breaker
            if self._circuit_breaker.state.value != "closed":
                self._circuit_breaker.reset()

            return result
        except Exception as e:
            # Record failure in circuit breaker
            self._circuit_breaker._on_failure(e)
            logger.error("InfluxDB operation failed: %s", str(e))
            raise
        finally:
            # Return client to pool
            await self.release_client(client)

    def _execute_with_retry(self, func: Any, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_error = None

        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    # Exponential backoff with jitter
                    backoff = min(2**attempt, 60) * (0.9 + 0.2 * (time.time() % 1))
                    logger.warning(
                        "InfluxDB operation failed (attempt %d/%d), retrying in %.2f seconds: %s",
                        attempt,
                        self.retries,
                        backoff,
                        str(e),
                    )
                    time.sleep(backoff)
                else:
                    logger.error("InfluxDB operation failed after %d attempts: %s", self.retries, str(e))

        # If we get here, all retries failed
        if last_error:
            raise last_error

        # This should never happen, but just in case
        raise RuntimeError("InfluxDB operation failed for unknown reason")


class EnhancedInfluxDBClient:
    """Enhanced InfluxDB client with advanced features."""

    def __init__(
        self,
        connection_pool: Optional[InfluxDBConnectionPool] = None,
        settings: Optional[InfluxDBSettings] = None,
    ):
        """Initialize enhanced InfluxDB client.

        Args:
            connection_pool: Optional existing connection pool
            settings: Optional InfluxDB settings (defaults to app settings)
        """
        self.settings = settings or get_settings().influxdb
        self.connection_pool = connection_pool or InfluxDBConnectionPool(
            host=self.settings.host,
            port=self.settings.port,
            username=self.settings.username,
            password=self.settings.password,
            database=self.settings.database,
            ssl=self.settings.ssl,
            verify_ssl=self.settings.verify_ssl,
            timeout=self.settings.timeout,
            pool_size=self.settings.connection_pool_size,
            retries=self.settings.retries,
        )

    async def initialize(self) -> None:
        """Initialize client and set up database."""
        await self.connection_pool.initialize()
        await self.setup_database()

    async def setup_database(self) -> None:
        """Set up database with retention policies and continuous queries."""
        # Make sure database exists
        await self.connection_pool.execute("create_database", self.settings.database)

        # Create retention policies
        for name, policy in self.settings.retention_policies.items():
            await self.create_retention_policy(
                name=name,
                duration=policy["duration"],
                replication=policy["replication"],
                default=policy["default"],
            )

        # Create continuous queries for downsampling
        for name, query_config in self.settings.continuous_queries.items():
            await self.create_continuous_query(
                name=name,
                source_retention=query_config["source_retention"],
                target_retention=query_config["target_retention"],
                interval=query_config["interval"],
                fields=query_config["fields"],
            )

    async def create_retention_policy(
        self,
        name: str,
        duration: str,
        replication: int = 1,
        default: bool = False,
    ) -> None:
        """Create a retention policy if it doesn't exist."""
        try:
            # Check if policy already exists
            policies = await self.connection_pool.execute("get_list_retention_policies")

            if any(p["name"] == name for p in policies):
                logger.debug("Retention policy '%s' already exists", name)
                return

            # Create policy
            await self.connection_pool.execute(
                "create_retention_policy",
                name=name,
                duration=duration,
                replication=replication,
                database=self.settings.database,
                default=default,
            )

            logger.info("Created retention policy '%s' with duration %s", name, duration)
        except Exception as e:
            logger.error("Failed to create retention policy '%s': %s", name, str(e))
            raise

    async def create_continuous_query(
        self,
        name: str,
        source_retention: str,
        target_retention: str,
        interval: str,
        fields: List[str],
    ) -> None:
        """Create a continuous query for downsampling if it doesn't exist."""
        try:
            # Check if query already exists
            queries = await self.connection_pool.execute("query", "SHOW CONTINUOUS QUERIES")

            for db_queries in queries.values():
                if any(q["name"] == name for q in db_queries):
                    logger.debug("Continuous query '%s' already exists", name)
                    return

            # Build query string
            field_list = []
            for field in fields:
                field_list.append(f"{field}(temperature) AS {field}_temperature")
                field_list.append(f"{field}(battery_level) AS {field}_battery")
                field_list.append(f"{field}(signal_strength) AS {field}_signal")

            field_str = ", ".join(field_list)

            query_str = f"""
                CREATE CONTINUOUS QUERY {name} ON {self.settings.database}
                BEGIN
                    SELECT {field_str}
                    INTO {self.settings.database}.{target_retention}.downsampled
                    FROM {self.settings.database}.{source_retention}.temperature
                    GROUP BY time({interval}), device_id, probe_id
                END
            """

            # Execute query
            await self.connection_pool.execute("query", query_str)

            logger.info("Created continuous query '%s' with interval %s", name, interval)
        except Exception as e:
            logger.error("Failed to create continuous query '%s': %s", name, str(e))
            raise

    @trace_async_function(name="influxdb_write_points")
    async def write_points(
        self,
        points: List[Dict[str, Any]],
        retention_policy: Optional[str] = None,
        batch_size: int = 1000,
    ) -> bool:
        """Write data points to InfluxDB.

        Args:
            points: List of data points to write
            retention_policy: Optional retention policy to use
            batch_size: Number of points to write in each batch

        Returns:
            True if all points were written successfully
        """
        if not points:
            return True

        # Process data points in batches
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            try:
                success = await self.connection_pool.execute(
                    "write_points",
                    batch,
                    retention_policy=retention_policy,
                    batch_size=batch_size,
                )

                if not success:
                    logger.error("Failed to write batch of %d points", len(batch))
                    return False

                logger.debug("Successfully wrote batch of %d points", len(batch))
            except Exception as e:
                logger.error("Error writing batch of %d points: %s", len(batch), str(e))
                return False

        return True

    @trace_async_function(name="influxdb_query")
    async def query(
        self,
        query: str,
        bind_params: Optional[Dict[str, Any]] = None,
        epoch: Optional[str] = None,
        chunked: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Execute a query against InfluxDB.

        Args:
            query: InfluxQL query string
            bind_params: Optional parameters to bind to query
            epoch: Optional time precision for results
            chunked: Whether to return results in chunks

        Returns:
            Query results
        """
        try:
            result = await self.connection_pool.execute(
                "query",
                query,
                params=bind_params,
                epoch=epoch,
                chunked=chunked,
            )
            return result
        except Exception as e:
            logger.error("Query failed: %s - %s", query, str(e))
            raise

    @trace_async_function(name="influxdb_health_check")
    async def health_check(self) -> bool:
        """Check if InfluxDB is healthy.

        Returns:
            True if InfluxDB is healthy, False otherwise
        """
        try:
            # Try to ping the server
            result = await self.connection_pool.execute("ping")

            # Check if we got a valid response
            if not isinstance(result, dict) or "version" not in result:
                logger.warning("InfluxDB ping returned unexpected response: %s", result)
                return False

            logger.debug("InfluxDB health check passed (version: %s)", result.get("version"))
            return True
        except Exception as e:
            logger.error("InfluxDB health check failed: %s", str(e))
            return False

    async def close(self) -> None:
        """Close the client."""
        await self.connection_pool.close()

    @trace_async_function(name="influxdb_get_temperature_history")
    async def get_temperature_history(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: str = "none",
        interval: str = "1m",
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get historical temperature data.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID
            start_time: Start time for query
            end_time: End time for query
            aggregation: Aggregation function (none, mean, max, min, sum)
            interval: Time interval for aggregation (e.g., 1m, 5m, 1h)
            limit: Maximum number of points to return
            offset: Number of points to skip

        Returns:
            List of temperature readings
        """
        # Determine fields to select based on aggregation
        if aggregation == "none":
            select_fields = "temperature, battery_level, signal_strength"
        else:
            select_fields = f"{aggregation}(temperature) as temperature"
            if aggregation in ["mean", "max", "min"]:
                select_fields += f", {aggregation}(battery_level) as battery_level"
                select_fields += f", {aggregation}(signal_strength) as signal_strength"

        # Build query
        query = f"SELECT {select_fields} FROM temperature WHERE device_id = $device_id"
        params = {"device_id": device_id}

        # Add probe filter if specified
        if probe_id:
            query += " AND probe_id = $probe_id"
            params["probe_id"] = probe_id

        # Add time range filters
        if start_time:
            query += " AND time >= $start_time"
            params["start_time"] = start_time.isoformat()

        if end_time:
            query += " AND time <= $end_time"
            params["end_time"] = end_time.isoformat()

        # Add group by clause for aggregation
        if aggregation != "none":
            query += f" GROUP BY time({interval})"

        # Add order, limit, and offset
        query += " ORDER BY time DESC"
        query += f" LIMIT {limit} OFFSET {offset}"

        # Execute query
        result = await self.query(query, bind_params=params)

        # Process results
        data = []
        if "temperature" in result:
            for point in result["temperature"]:
                item = {
                    "device_id": device_id,
                    "timestamp": point.get("time"),
                    "temperature": point.get("temperature"),
                }

                if probe_id:
                    item["probe_id"] = probe_id

                # Add optional fields
                for field in ["battery_level", "signal_strength"]:
                    if field in point and point[field] is not None:
                        item[field] = point[field]

                data.append(item)

        return data

    @trace_async_function(name="influxdb_get_temperature_statistics")
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
            start_time: Start time for query
            end_time: End time for query

        Returns:
            Dictionary of temperature statistics
        """
        # Build query
        query = """
            SELECT
                MEAN(temperature) as avg_temperature,
                MAX(temperature) as max_temperature,
                MIN(temperature) as min_temperature,
                COUNT(temperature) as count,
                STDDEV(temperature) as stddev_temperature,
                PERCENTILE(temperature, 50) as median_temperature
            FROM temperature
            WHERE device_id = $device_id
        """
        params = {"device_id": device_id}

        # Add probe filter if specified
        if probe_id:
            query += " AND probe_id = $probe_id"
            params["probe_id"] = probe_id

        # Add time range filters
        if start_time:
            query += " AND time >= $start_time"
            params["start_time"] = start_time.isoformat()

        if end_time:
            query += " AND time <= $end_time"
            params["end_time"] = end_time.isoformat()

        # Execute query
        result = await self.query(query, bind_params=params)

        # Process results
        stats = {
            "device_id": device_id,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "count": 0,
            "min_temperature": None,
            "max_temperature": None,
            "avg_temperature": None,
            "median_temperature": None,
            "stddev_temperature": None,
        }

        if probe_id:
            stats["probe_id"] = probe_id

        if "temperature" in result and result["temperature"]:
            point = result["temperature"][0]

            for key in [
                "count",
                "min_temperature",
                "max_temperature",
                "avg_temperature",
                "median_temperature",
                "stddev_temperature",
            ]:
                if key in point and point[key] is not None:
                    stats[key] = point[key]

        return stats

    @trace_async_function(name="influxdb_get_temperature_alerts")
    async def get_temperature_alerts(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        threshold_high: float = 250.0,
        threshold_low: float = 32.0,
    ) -> List[Dict[str, Any]]:
        """Get temperature alerts.

        Args:
            device_id: Device ID
            probe_id: Optional probe ID
            start_time: Start time for query
            end_time: End time for query
            threshold_high: High temperature threshold
            threshold_low: Low temperature threshold

        Returns:
            List of temperature alerts
        """
        alerts = []

        # Query for high temperature alerts
        high_query = f"""
            SELECT temperature, time
            FROM temperature
            WHERE device_id = $device_id
            AND temperature > {threshold_high}
        """

        # Query for low temperature alerts
        low_query = f"""
            SELECT temperature, time
            FROM temperature
            WHERE device_id = $device_id
            AND temperature < {threshold_low}
        """

        params = {"device_id": device_id}

        # Add probe filter if specified
        if probe_id:
            high_query += " AND probe_id = $probe_id"
            low_query += " AND probe_id = $probe_id"
            params["probe_id"] = probe_id

        # Add time range filters
        if start_time:
            high_query += " AND time >= $start_time"
            low_query += " AND time >= $start_time"
            params["start_time"] = start_time.isoformat()

        if end_time:
            high_query += " AND time <= $end_time"
            low_query += " AND time <= $end_time"
            params["end_time"] = end_time.isoformat()

        # Add ordering
        high_query += " ORDER BY time DESC"
        low_query += " ORDER BY time DESC"

        # Execute queries
        high_result = await self.query(high_query, bind_params=params)
        low_result = await self.query(low_query, bind_params=params)

        # Process high temperature alerts
        if "temperature" in high_result:
            for point in high_result["temperature"]:
                severity = "warning"
                if point.get("temperature", 0) > threshold_high + 50:
                    severity = "critical"

                alerts.append(
                    {
                        "timestamp": point.get("time"),
                        "temperature": point.get("temperature"),
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "alert_type": "high_temperature",
                        "threshold": threshold_high,
                        "severity": severity,
                    }
                )

        # Process low temperature alerts
        if "temperature" in low_result:
            for point in low_result["temperature"]:
                alerts.append(
                    {
                        "timestamp": point.get("time"),
                        "temperature": point.get("temperature"),
                        "device_id": device_id,
                        "probe_id": probe_id,
                        "alert_type": "low_temperature",
                        "threshold": threshold_low,
                        "severity": "warning",
                    }
                )

        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x["timestamp"], reverse=True)

        return alerts


# Singleton instance for application-wide use
_influxdb_client: Optional[EnhancedInfluxDBClient] = None


async def get_influxdb_client() -> EnhancedInfluxDBClient:
    """Get or create the InfluxDB client singleton."""
    global _influxdb_client

    if _influxdb_client is None:
        _influxdb_client = EnhancedInfluxDBClient()
        await _influxdb_client.initialize()

    return _influxdb_client


async def close_influxdb_client() -> None:
    """Close the InfluxDB client singleton."""
    global _influxdb_client

    if _influxdb_client is not None:
        await _influxdb_client.close()
        _influxdb_client = None
