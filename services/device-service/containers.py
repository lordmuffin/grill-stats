"""
Dependency Injection Container for Device Service

This module provides a dependency injection container for the Device Service.
It manages the instantiation and wiring of all service components.
"""

import logging
import os
from typing import Any, Dict, Optional, cast

import redis
from dependency_injector import containers, providers
from dependency_injector.providers import Configuration, Factory, Resource, Singleton
from device_manager import DeviceManager
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import Resource as OTelResource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from rfx_gateway_client import RFXGatewayClient

from thermoworks_client import ThermoworksClient


class OpenTelemetryContainer(containers.DeclarativeContainer):
    """Container for OpenTelemetry components"""

    config = providers.Configuration()

    # Create a resource to identify this service
    resource = providers.Factory(OTelResource.create, {SERVICE_NAME: "device-service"})

    # Configure tracing
    trace_provider = providers.Singleton(TracerProvider, resource=resource)

    trace_processor = providers.Singleton(BatchSpanProcessor, ConsoleSpanExporter())

    # Function to configure and initialize tracing
    init_tracing = providers.Callable(
        lambda trace_provider, trace_processor: (
            trace_provider.add_span_processor(trace_processor),
            trace.set_tracer_provider(trace_provider),
        )[
            1
        ]  # Return the result of set_tracer_provider
    )

    # Configure metrics
    prometheus_reader = providers.Singleton(PrometheusMetricReader)

    metrics_provider = providers.Singleton(
        MeterProvider, resource=resource, metric_readers=providers.List([prometheus_reader])
    )

    # Function to initialize metrics
    init_metrics = providers.Callable(lambda metrics_provider: metrics.set_meter_provider(metrics_provider))

    # Get a tracer for this service
    tracer = providers.Callable(lambda: trace.get_tracer("device.service"))

    # Get a meter for this service
    meter = providers.Callable(lambda: metrics.get_meter("device.service"))

    # Create common metrics
    api_requests_counter = providers.Callable(
        lambda meter: meter.create_counter(
            name="api_requests",
            description="Count of API requests",
            unit="1",
        )
    )

    device_temperature_gauge = providers.Callable(
        lambda meter: meter.create_observable_gauge(
            name="device_temperature",
            description="Current temperature of devices",
            unit="celsius",
        )
    )

    request_duration = providers.Callable(
        lambda meter: meter.create_histogram(
            name="request_duration",
            description="Duration of API requests",
            unit="ms",
        )
    )


class ServicesContainer(containers.DeclarativeContainer):
    """Container for main service components"""

    config = providers.Configuration()
    telemetry = providers.DependenciesContainer()

    # Database configuration
    db_config = providers.Dict(
        host=config.db.host.as_str(default="localhost"),
        port=config.db.port.as_int(default=5432),
        database=config.db.name.as_str(default="grill_stats"),
        username=config.db.username.as_str(default="postgres"),
        password=config.db.password.as_str(default=""),
    )

    # Device Manager
    device_manager = providers.Singleton(
        DeviceManager,
        db_host=db_config.provided["host"],
        db_port=db_config.provided["port"],
        db_name=db_config.provided["database"],
        db_username=db_config.provided["username"],
        db_password=db_config.provided["password"],
    )

    # Redis client
    redis_client = providers.Resource(
        lambda config: (
            redis.Redis(
                host=config.redis.host.as_str(default="localhost"),
                port=config.redis.port.as_int(default=6379),
                password=config.redis.password.as_str(default=None),
                decode_responses=True,
            )
            if not config.redis.mock.as_bool(default=False)
            else None
        ),
        config=config,
    )

    # ThermoWorks client
    thermoworks_client = providers.Singleton(
        ThermoworksClient,
        client_id=config.thermoworks.client_id.as_str(default=None),
        client_secret=config.thermoworks.client_secret.as_str(default=None),
        redirect_uri=config.thermoworks.redirect_uri.as_str(default=None),
        base_url=config.thermoworks.base_url.as_str(default=None),
        auth_url=config.thermoworks.auth_url.as_str(default=None),
        token_storage_path=config.thermoworks.token_storage_path.as_str(default=None),
        polling_interval=config.thermoworks.polling_interval.as_int(default=60),
        auto_start_polling=config.thermoworks.auto_start_polling.as_bool(default=False),
    )

    # RFX Gateway client
    rfx_gateway_client = providers.Singleton(
        RFXGatewayClient,
        thermoworks_client=thermoworks_client,
        ha_url=config.homeassistant.url.as_str(default="http://localhost:8123"),
        ha_token=config.homeassistant.token.as_str(default=None),
        max_scan_duration=config.rfx.scan_duration.as_int(default=30),
        connection_timeout=config.rfx.connection_timeout.as_int(default=15),
        setup_timeout=config.rfx.setup_timeout.as_int(default=300),
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Main application container"""

    config = providers.Configuration()

    # Load configuration from environment variables
    config.db.host.from_env("DB_HOST", "localhost")
    config.db.port.from_env("DB_PORT", "5432")
    config.db.name.from_env("DB_NAME", "grill_stats")
    config.db.username.from_env("DB_USER", "postgres")
    config.db.password.from_env("DB_PASSWORD", "")

    config.redis.host.from_env("REDIS_HOST", "localhost")
    config.redis.port.from_env("REDIS_PORT", "6379")
    config.redis.password.from_env("REDIS_PASSWORD")
    config.redis.mock.from_env("MOCK_REDIS", "false")

    config.thermoworks.client_id.from_env("THERMOWORKS_CLIENT_ID")
    config.thermoworks.client_secret.from_env("THERMOWORKS_CLIENT_SECRET")
    config.thermoworks.redirect_uri.from_env("THERMOWORKS_REDIRECT_URI")
    config.thermoworks.base_url.from_env("THERMOWORKS_BASE_URL")
    config.thermoworks.auth_url.from_env("THERMOWORKS_AUTH_URL")
    config.thermoworks.token_storage_path.from_env("TOKEN_STORAGE_PATH")
    config.thermoworks.polling_interval.from_env("THERMOWORKS_POLLING_INTERVAL", "60")
    config.thermoworks.auto_start_polling.from_env("THERMOWORKS_AUTO_START_POLLING", "false")

    config.homeassistant.url.from_env("HOMEASSISTANT_URL", "http://localhost:8123")
    config.homeassistant.token.from_env("HOMEASSISTANT_TOKEN")

    config.rfx.scan_duration.from_env("RFX_SCAN_DURATION", "30")
    config.rfx.connection_timeout.from_env("RFX_CONNECTION_TIMEOUT", "15")
    config.rfx.setup_timeout.from_env("RFX_SETUP_TIMEOUT", "300")

    config.jwt.secret.from_env("JWT_SECRET", "your-secret-key")
    config.jwt.algorithm.from_env("JWT_ALGORITHM", "HS256")

    # Setup sub-containers
    telemetry = providers.Container(OpenTelemetryContainer, config=config)

    services = providers.Container(ServicesContainer, config=config, telemetry=telemetry)

    # Initialize OpenTelemetry
    init_telemetry = providers.Callable(
        lambda telemetry: (
            telemetry.init_tracing(
                telemetry.trace_provider(),
                telemetry.trace_processor(),
            ),
            telemetry.init_metrics(
                telemetry.metrics_provider(),
            ),
        )
    )


# Helper function to initialize the container
def create_container() -> ApplicationContainer:
    """Create and initialize the application container"""
    container = ApplicationContainer()

    # Initialize telemetry
    container.init_telemetry(container.telemetry)

    return container
