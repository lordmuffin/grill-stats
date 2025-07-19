"""
Isolated models package for testing.

This package provides isolated versions of model classes that don't have
circular dependencies, making them suitable for isolated unit tests.
"""

from .user import IsolatedUser

__all__ = ["IsolatedUser"]
