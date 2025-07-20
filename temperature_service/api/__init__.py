"""API endpoints for temperature data service."""

from .app import create_app
from .routes import router as temperature_router

__all__ = [
    "create_app",
    "temperature_router",
]
