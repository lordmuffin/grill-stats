"""
Base module for SQLAlchemy database setup.

This module provides the SQLAlchemy instance and declarative base model
to be used by all models in the application. By centralizing the database
setup, we avoid circular imports and ensure proper initialization order.
"""

from typing import Any, Type

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import DeclarativeMeta

# Initialize SQLAlchemy without binding to an app
db = SQLAlchemy()

# Type hint for the base model class
Base: Any = db.Model

# Export db for use by other modules
__all__ = ["db", "Base"]
