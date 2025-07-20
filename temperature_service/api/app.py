"""
FastAPI application for temperature data service.

This module provides the main FastAPI application for the temperature data service,
with middleware, exception handlers, and startup/shutdown hooks.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from temperature_service.clients import close_influxdb_client, close_redis_client, close_thermoworks_client
from temperature_service.config import get_settings
from temperature_service.services import close_temperature_service, get_temperature_service
from temperature_service.utils import instrument_fastapi, setup_tracing

from .routes import router as temperature_router

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def startup_event() -> None:
    """Application startup event handler."""
    # Set up tracing
    if settings.service.enable_tracing:
        setup_tracing(
            service_name=settings.service.service_name,
            service_version=settings.service.service_version,
            otlp_endpoint=settings.service.tracer_endpoint,
            console_export=settings.service.is_development,
        )
        logger.info("Distributed tracing initialized")

    # Initialize temperature service
    temperature_service = await get_temperature_service()

    # Start temperature collection if enabled
    if settings.service.collection_interval > 0:
        await temperature_service.start_collection()

    logger.info(
        "%s v%s started in %s environment",
        settings.service.service_name,
        settings.service.service_version,
        settings.service.environment,
    )


async def shutdown_event() -> None:
    """Application shutdown event handler."""
    # Stop temperature service
    await close_temperature_service()

    # Close client connections
    await close_influxdb_client()
    await close_redis_client()
    await close_thermoworks_client()

    logger.info("%s shutdown complete", settings.service.service_name)


def create_app() -> FastAPI:
    """Create FastAPI application.

    Returns:
        FastAPI application
    """
    # Create FastAPI application
    app = FastAPI(
        title="Temperature Data Service",
        description="API for temperature data collection and retrieval",
        version=settings.service.service_version,
        docs_url=settings.service.docs_url,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.service.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request timing middleware
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next: Callable) -> Response:
        """Add response timing header."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Add exception handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "message": str(exc.detail),
                "code": exc.status_code,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "message": "Validation error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions."""
        logger.exception("Unhandled exception: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
            },
        )

    # Add startup and shutdown events
    app.add_event_handler("startup", startup_event)
    app.add_event_handler("shutdown", shutdown_event)

    # Add routes
    app.include_router(temperature_router)

    # Add OpenTelemetry instrumentation
    if settings.service.enable_tracing:
        instrument_fastapi(app)

    return app
