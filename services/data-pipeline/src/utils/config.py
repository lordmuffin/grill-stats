"""
Configuration management for the data pipeline service.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class KafkaConfig:
    """Kafka configuration settings."""

    bootstrap_servers: str
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None
    consumer_group_id: str = "data-pipeline-group"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    session_timeout_ms: int = 30000
    max_poll_records: int = 500
    fetch_min_bytes: int = 1
    fetch_max_wait_ms: int = 500
    compression_type: str = "lz4"
    batch_size: int = 16384
    linger_ms: int = 5
    buffer_memory: int = 33554432
    retries: int = 3
    retry_backoff_ms: int = 100


@dataclass
class RedisConfig:
    """Redis configuration settings."""

    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    max_connections: int = 10
    retry_on_timeout: bool = True
    health_check_interval: int = 30


@dataclass
class ProcessingConfig:
    """Processing configuration settings."""

    aggregation_window_seconds: int = 300  # 5 minutes
    anomaly_threshold: float = 0.85
    min_training_samples: int = 100
    max_cache_size: int = 10000
    batch_processing_size: int = 100
    processing_timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 1


@dataclass
class MonitoringConfig:
    """Monitoring configuration settings."""

    metrics_port: int = 8000
    health_check_interval: int = 30
    log_level: str = "INFO"
    enable_prometheus: bool = True
    enable_structlog: bool = True
    max_log_file_size: int = 10485760  # 10MB
    log_backup_count: int = 5


class Config:
    """Main configuration class."""

    def __init__(self):
        self.kafka_config = KafkaConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM"),
            sasl_username=os.getenv("KAFKA_SASL_USERNAME"),
            sasl_password=os.getenv("KAFKA_SASL_PASSWORD"),
            consumer_group_id=os.getenv(
                "KAFKA_CONSUMER_GROUP_ID", "data-pipeline-group"
            ),
            auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest"),
            enable_auto_commit=os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "true").lower()
            == "true",
            auto_commit_interval_ms=int(
                os.getenv("KAFKA_AUTO_COMMIT_INTERVAL_MS", "5000")
            ),
            session_timeout_ms=int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "30000")),
            max_poll_records=int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500")),
            compression_type=os.getenv("KAFKA_COMPRESSION_TYPE", "lz4"),
            batch_size=int(os.getenv("KAFKA_BATCH_SIZE", "16384")),
            linger_ms=int(os.getenv("KAFKA_LINGER_MS", "5")),
            retries=int(os.getenv("KAFKA_RETRIES", "3")),
        )

        self.redis_config = RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD"),
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            socket_connect_timeout=int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            retry_on_timeout=os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower()
            == "true",
            health_check_interval=int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")),
        )

        self.processing_config = ProcessingConfig(
            aggregation_window_seconds=int(
                os.getenv("AGGREGATION_WINDOW_SECONDS", "300")
            ),
            anomaly_threshold=float(os.getenv("ANOMALY_THRESHOLD", "0.85")),
            min_training_samples=int(os.getenv("MIN_TRAINING_SAMPLES", "100")),
            max_cache_size=int(os.getenv("MAX_CACHE_SIZE", "10000")),
            batch_processing_size=int(os.getenv("BATCH_PROCESSING_SIZE", "100")),
            processing_timeout_seconds=int(
                os.getenv("PROCESSING_TIMEOUT_SECONDS", "30")
            ),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay_seconds=int(os.getenv("RETRY_DELAY_SECONDS", "1")),
        )

        self.monitoring_config = MonitoringConfig(
            metrics_port=int(os.getenv("METRICS_PORT", "8000")),
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            enable_prometheus=os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true",
            enable_structlog=os.getenv("ENABLE_STRUCTLOG", "true").lower() == "true",
            max_log_file_size=int(os.getenv("MAX_LOG_FILE_SIZE", "10485760")),
            log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        )

        # External service configurations
        self.thermoworks_api_key = os.getenv("THERMOWORKS_API_KEY")
        self.homeassistant_url = os.getenv("HOMEASSISTANT_URL")
        self.homeassistant_token = os.getenv("HOMEASSISTANT_TOKEN")

        # Kafka topics
        self.kafka_topics = {
            "temperature_readings_raw": "temperature.readings.raw",
            "temperature_readings_validated": "temperature.readings.validated",
            "anomalies_detected": "anomalies.detected",
            "alerts_triggered": "alerts.triggered",
            "homeassistant_state_updates": "homeassistant.state.updates",
        }

        # Validate required configurations
        self._validate_config()

    def _validate_config(self):
        """Validate required configuration parameters."""
        required_env_vars = [
            "KAFKA_BOOTSTRAP_SERVERS",
            "REDIS_HOST",
            "THERMOWORKS_API_KEY",
            "HOMEASSISTANT_URL",
            "HOMEASSISTANT_TOKEN",
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

    def get_kafka_producer_config(self) -> Dict:
        """Get Kafka producer configuration."""
        config = {
            "bootstrap.servers": self.kafka_config.bootstrap_servers,
            "security.protocol": self.kafka_config.security_protocol,
            "compression.type": self.kafka_config.compression_type,
            "batch.size": self.kafka_config.batch_size,
            "linger.ms": self.kafka_config.linger_ms,
            "buffer.memory": self.kafka_config.buffer_memory,
            "retries": self.kafka_config.retries,
            "retry.backoff.ms": self.kafka_config.retry_backoff_ms,
            "enable.idempotence": True,
            "acks": "all",
        }

        if self.kafka_config.sasl_mechanism:
            config.update(
                {
                    "sasl.mechanism": self.kafka_config.sasl_mechanism,
                    "sasl.username": self.kafka_config.sasl_username,
                    "sasl.password": self.kafka_config.sasl_password,
                }
            )

        return config

    def get_kafka_consumer_config(self, group_id: str = None) -> Dict:
        """Get Kafka consumer configuration."""
        config = {
            "bootstrap.servers": self.kafka_config.bootstrap_servers,
            "security.protocol": self.kafka_config.security_protocol,
            "group.id": group_id or self.kafka_config.consumer_group_id,
            "auto.offset.reset": self.kafka_config.auto_offset_reset,
            "enable.auto.commit": self.kafka_config.enable_auto_commit,
            "auto.commit.interval.ms": self.kafka_config.auto_commit_interval_ms,
            "session.timeout.ms": self.kafka_config.session_timeout_ms,
            "max.poll.records": self.kafka_config.max_poll_records,
            "fetch.min.bytes": self.kafka_config.fetch_min_bytes,
            "fetch.max.wait.ms": self.kafka_config.fetch_max_wait_ms,
            "enable.partition.eof": False,
        }

        if self.kafka_config.sasl_mechanism:
            config.update(
                {
                    "sasl.mechanism": self.kafka_config.sasl_mechanism,
                    "sasl.username": self.kafka_config.sasl_username,
                    "sasl.password": self.kafka_config.sasl_password,
                }
            )

        return config
