"""
Mock Data Infrastructure for Grill Stats Application

This module provides mock data services for development and testing without requiring
live ThermoWorks API connections. It includes realistic device data, temperature
readings, and historical data suitable for UI development and testing.

Components:
- MockDataService: Main service class that replaces ThermoWorks API calls
- devices.json: Static device configuration data
- historical.json: Pre-generated historical temperature data
- Temperature data generator: Creates realistic real-time temperature variations

Usage:
    from services.mock_data import MockDataService
    
    mock_service = MockDataService()
    devices = mock_service.get_devices()
    temperature_data = mock_service.get_temperature_data(device_id, probe_id)
"""

from .mock_service import MockDataService

__all__ = ['MockDataService']