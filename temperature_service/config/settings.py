"""
Temperature Service Configuration Settings.

This module provides a centralized configuration system for the temperature service,
utilizing Pydantic for schema validation and environment variable loading.
"""

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyUrl, BaseSettings, Field, validator


class InfluxDBSettings(BaseSettings):
    """InfluxDB connection and configuration settings."""

    host: str = Field(default="localhost", env="INFLUXDB_HOST")
    port: int = Field(default=8086, env="INFLUXDB_PORT")
    database: str = Field(default="grill_monitoring", env="INFLUXDB_DATABASE")
    username: Optional[str] = Field(default=None, env="INFLUXDB_USERNAME")
    password: Optional[str] = Field(default=None, env="INFLUXDB_PASSWORD")
    ssl: bool = Field(default=False, env="INFLUXDB_SSL")
    verify_ssl: bool = Field(default=True, env="INFLUXDB_VERIFY_SSL")
    timeout: int = Field(default=10, env="INFLUXDB_TIMEOUT")
    connection_pool_size: int = Field(default=10, env="INFLUXDB_POOL_SIZE")
    retries: int = Field(default=3, env="INFLUXDB_RETRIES")

    # Retention policies configuration
    retention_policies: Dict[str, Dict[str, Any]] = Field(
        default={
            "raw": {"duration": "7d", "replication": 1, "default": False},
            "hourly": {"duration": "30d", "replication": 1, "default": False},
            "daily": {"duration": "365d", "replication": 1, "default": True},
            "monthly": {"duration": "INF", "replication": 1, "default": False},
        }
    )

    # Data downsampling configuration
    continuous_queries: Dict[str, Dict[str, Any]] = Field(
        default={
            "hourly_rollup": {
                "source_retention": "raw",
                "target_retention": "hourly",
                "interval": "1h",
                "fields": ["mean", "min", "max"],
            },
            "daily_rollup": {
                "source_retention": "hourly",
                "target_retention": "daily",
                "interval": "1d",
                "fields": ["mean", "min", "max"],
            },
        }
    )

    class Config:
        env_prefix = ""
        case_sensitive = False


class RedisSettings(BaseSettings):
    """Redis connection and configuration settings."""

    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    ssl: bool = Field(default=False, env="REDIS_SSL")
    connection_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    connection_timeout: int = Field(default=5, env="REDIS_TIMEOUT")

    # Stream settings
    stream_key: str = Field(default="temperature_stream", env="REDIS_STREAM_KEY")
    max_stream_length: int = Field(default=10000, env="REDIS_STREAM_MAX_LENGTH")

    # Pub/Sub channels
    pub_sub_channels: Dict[str, str] = Field(
        default={"temperature": "temperature_data", "device_status": "device_status", "alerts": "temperature_alerts"}
    )

    # Cache settings
    default_cache_ttl: int = Field(default=60, env="REDIS_CACHE_TTL")  # seconds

    class Config:
        env_prefix = ""
        case_sensitive = False


class ThermoworksSettings(BaseSettings):
    """ThermoWorks API client settings."""

    api_key: Optional[str] = Field(default=None, env="THERMOWORKS_API_KEY")
    base_url: str = Field(default="https://api.thermoworks.com", env="THERMOWORKS_BASE_URL")
    timeout: int = Field(default=10, env="THERMOWORKS_TIMEOUT")
    retry_count: int = Field(default=3, env="THERMOWORKS_RETRY_COUNT")
    retry_backoff_factor: float = Field(default=0.5, env="THERMOWORKS_RETRY_BACKOFF")
    polling_interval: int = Field(default=60, env="THERMOWORKS_POLLING_INTERVAL")  # seconds

    class Config:
        env_prefix = ""
        case_sensitive = False


class ServiceSettings(BaseSettings):
    """Main service settings."""

    # Service identity
    service_name: str = Field(default="temperature-service", env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")

    # Environment settings
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Web server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")
    workers: int = Field(default=4, env="WORKERS")

    # API settings
    api_prefix: str = Field(default="/api", env="API_PREFIX")
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")

    # Data collection settings
    collection_interval: int = Field(default=60, env="COLLECTION_INTERVAL")  # seconds
    batch_size: int = Field(default=100, env="BATCH_SIZE")

    # Circuit breaker settings
    circuit_breaker_failure_threshold: int = Field(default=5, env="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_recovery_timeout: int = Field(default=30, env="CIRCUIT_BREAKER_RECOVERY_TIMEOUT")

    # Feature flags
    enable_websockets: bool = Field(default=True, env="ENABLE_WEBSOCKETS")
    enable_sse: bool = Field(default=True, env="ENABLE_SSE")
    enable_redis_pubsub: bool = Field(default=True, env="ENABLE_REDIS_PUBSUB")
    enable_batch_processing: bool = Field(default=True, env="ENABLE_BATCH_PROCESSING")
    enable_anomaly_detection: bool = Field(default=False, env="ENABLE_ANOMALY_DETECTION")

    # Mock mode settings
    mock_mode: bool = Field(default=False, env="MOCK_MODE")

    # Tracing settings
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    tracer_endpoint: Optional[str] = Field(default=None, env="TRACER_ENDPOINT")

    # API documentation
    docs_url: str = Field(default="/docs", env="DOCS_URL")

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {', '.join(allowed_levels)}")
        return v.upper()

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        allowed_environments = ["development", "testing", "staging", "production"]
        if v.lower() not in allowed_environments:
            raise ValueError(f"Environment must be one of: {', '.join(allowed_environments)}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        """Check if environment is production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if environment is development."""
        return self.environment == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class Settings(BaseSettings):
    """Combined application settings."""

    service: ServiceSettings = ServiceSettings()
    influxdb: InfluxDBSettings = InfluxDBSettings()
    redis: RedisSettings = RedisSettings()
    thermoworks: ThermoworksSettings = ThermoworksSettings()


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
