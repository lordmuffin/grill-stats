"""
Temperature Data Service - Main Entry Point.

This module provides the entry point for running the temperature data service
with uvicorn, configured with ASGI middleware and workers.
"""

import logging
import os
import sys
from typing import Any, Dict

import structlog
import uvicorn

from temperature_service.api import create_app
from temperature_service.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Get application settings
settings = get_settings()


def get_uvicorn_config() -> Dict[str, Any]:
    """Get uvicorn configuration from environment or settings.

    Returns:
        Uvicorn configuration dictionary
    """
    return {
        "host": os.getenv("HOST", settings.service.host),
        "port": int(os.getenv("PORT", settings.service.port)),
        "log_level": os.getenv("LOG_LEVEL", settings.service.log_level).lower(),
        "workers": int(os.getenv("WORKERS", settings.service.workers)),
        "reload": os.getenv("RELOAD", str(settings.service.is_development)).lower() in ("true", "1", "yes"),
    }


def main() -> None:
    """Run the application with uvicorn."""
    # Create FastAPI application
    app = create_app()

    # Get uvicorn configuration
    config = get_uvicorn_config()

    # Log startup information
    logger.info(
        "Starting Temperature Data Service",
        host=config["host"],
        port=config["port"],
        workers=config["workers"],
        log_level=config["log_level"],
        reload=config["reload"],
        environment=settings.service.environment,
    )

    # Run with uvicorn
    uvicorn.run(
        "main:create_app",
        host=config["host"],
        port=config["port"],
        log_level=config["log_level"],
        workers=config["workers"],
        reload=config["reload"],
        factory=True,
    )


# Create application factory for uvicorn
def create_app():  # type: ignore
    """Create FastAPI application for uvicorn."""
    from temperature_service.api import create_app

    return create_app()


if __name__ == "__main__":
    main()
