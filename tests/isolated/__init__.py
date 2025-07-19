"""
Isolated test utilities package.

This package provides isolated test utilities to avoid circular dependencies.
"""

from .models import IsolatedUser

__all__ = ["IsolatedUser"]
