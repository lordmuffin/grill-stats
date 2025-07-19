"""
Mock models package for testing.

This package provides mock versions of model classes that don't have
circular dependencies between them, making them suitable for isolated unit tests.
"""

from .device import MockDevice
from .user import MockUser

__all__ = ["MockDevice", "MockUser"]
