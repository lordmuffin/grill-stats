"""
Distributed tracing utilities using OpenTelemetry.

This module provides convenience functions for setting up distributed tracing
with OpenTelemetry, which helps track requests across service boundaries.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.status import Status, StatusCode

from temperature_service.config import get_settings

# Type variable for function return values
T = TypeVar("T")

logger = logging.getLogger(__name__)
settings = get_settings()

# Global tracer instance
_tracer = None


def setup_tracing(
    service_name: Optional[str] = None,
    service_version: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> None:
    """Set up OpenTelemetry tracing.

    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        otlp_endpoint: Endpoint for OTLP exporter (e.g., http://jaeger:4317)
        console_export: Whether to also export spans to console
    """
    global _tracer

    # Use settings if not explicitly provided
    service_name = service_name or settings.service.service_name
    service_version = service_version or settings.service.service_version
    otlp_endpoint = otlp_endpoint or settings.service.tracer_endpoint

    # Create resource with service info
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": settings.service.environment,
        }
    )

    # Create and set tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Add exporters
    if otlp_endpoint:
        # Configure OTLP exporter to send traces to Jaeger/collector
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"Configured OTLP tracing exporter to {otlp_endpoint}")

    if console_export or settings.service.is_development:
        # Also export to console in development mode
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Configured console tracing exporter")

    # Initialize instrumentation for common libraries
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()

    # Create the tracer
    _tracer = trace.get_tracer(service_name, service_version)

    logger.info(f"Tracing initialized for {service_name} v{service_version} " f"in {settings.service.environment} environment")


def get_tracer():
    """Get the configured tracer instance."""
    global _tracer

    if _tracer is None:
        setup_tracing()

    return _tracer


def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace a function.

    Args:
        name: Custom name for the span (defaults to function name)
        attributes: Additional attributes to add to the span
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get span name from provided name or function name
            span_name = name or func.__qualname__

            # Get attributes with defaults
            span_attributes = {
                "function": func.__qualname__,
                "module": func.__module__,
            }
            if attributes:
                span_attributes.update(attributes)

            # Create and activate span
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name, attributes=span_attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    # Record exception details in span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


def trace_async_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace an async function.

    Args:
        name: Custom name for the span (defaults to function name)
        attributes: Additional attributes to add to the span
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get span name from provided name or function name
            span_name = name or func.__qualname__

            # Get attributes with defaults
            span_attributes = {
                "function": func.__qualname__,
                "module": func.__module__,
            }
            if attributes:
                span_attributes.update(attributes)

            # Create and activate span
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name, attributes=span_attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    # Record exception details in span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


def instrument_fastapi(app):
    """Instrument a FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
