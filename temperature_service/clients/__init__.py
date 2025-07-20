"""Client implementations for external services."""

from .influxdb_client import EnhancedInfluxDBClient, InfluxDBConnectionPool, close_influxdb_client, get_influxdb_client
from .redis_client import RedisClient, close_redis_client, get_redis_client
from .thermoworks_client import (
    AsyncThermoworksClient,
    ThermoworksAPIError,
    ThermoworksAuthenticationError,
    ThermoworksConnectionError,
    close_thermoworks_client,
    get_thermoworks_client,
)

__all__ = [
    # InfluxDB Client
    "EnhancedInfluxDBClient",
    "InfluxDBConnectionPool",
    "get_influxdb_client",
    "close_influxdb_client",
    # Redis Client
    "RedisClient",
    "get_redis_client",
    "close_redis_client",
    # ThermoWorks Client
    "AsyncThermoworksClient",
    "ThermoworksAPIError",
    "ThermoworksAuthenticationError",
    "ThermoworksConnectionError",
    "get_thermoworks_client",
    "close_thermoworks_client",
]
