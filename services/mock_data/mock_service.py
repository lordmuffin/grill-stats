#!/usr/bin/env python3
"""
Mock Data Service for Grill Stats Application

This service provides mock data that replaces live ThermoWorks API calls during development
and testing. It generates realistic temperature data variations and supports all the same
methods as the real ThermoWorks client.

Features:
- Realistic temperature data with gradual changes based on meat types
- Multiple probe types with different cooking patterns
- Cooking events simulation (lid opening, temp adjustments, etc.)
- Battery level and signal strength simulation
- Historical data support
- Device status management
"""

import json
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .temp_simulator import simulator as temp_simulator

logger = logging.getLogger(__name__)


class MockDataService:
    """Mock data service that replaces ThermoWorks API calls"""

    def __init__(self, data_directory: Optional[str] = None):
        """
        Initialize the mock data service

        Args:
            data_directory: Directory containing mock data files
        """
        if data_directory is None:
            data_directory = os.path.dirname(os.path.abspath(__file__))

        self.data_directory = Path(data_directory)
        self.devices_file = self.data_directory / "devices.json"
        self.historical_file = self.data_directory / "historical.json"

        # Internal state for temperature simulation
        self._last_update: Dict[str, float] = {}  # device_id -> last update timestamp
        self._simulation_lock = threading.Lock()

        # Load initial data
        self._load_device_data()

        logger.info("MockDataService initialized with data directory: %s", data_directory)

    def _load_device_data(self) -> None:
        """Load device data from JSON file"""
        try:
            with open(self.devices_file, "r") as f:
                self._device_data = json.load(f)
            logger.debug(
                "Loaded device data for %d devices",
                len(self._device_data.get("devices", [])),
            )
        except Exception as e:
            logger.error("Failed to load device data: %s", e)
            self._device_data = {"devices": [], "metadata": {}}

    def get_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get a list of all mock devices

        Args:
            force_refresh: Whether to force a refresh (ignored in mock)

        Returns:
            List of device dictionaries matching ThermoWorks API format
        """
        try:
            devices = []

            with self._simulation_lock:
                for device in self._device_data.get("devices", []):
                    # Create a copy to avoid modifying original data
                    device_copy = device.copy()

                    # Update temperatures for online devices
                    if device_copy.get("is_online", True):
                        updated_probes = []
                        for probe in device_copy.get("probes", []):
                            probe_copy = probe.copy()

                            # Use the enhanced temperature simulator
                            new_temp = temp_simulator.update_temperature(
                                device_id=device_copy["device_id"],
                                probe_id=probe_copy["probe_id"],
                                current_temp=probe_copy["current_temp"],
                                probe_name=probe_copy["name"],
                                probe_type=probe_copy.get("type", "food"),
                            )
                            probe_copy["current_temp"] = new_temp
                            updated_probes.append(probe_copy)

                        device_copy["probes"] = updated_probes

                        # Get device status from simulator (battery, signal)
                        device_status = temp_simulator.get_device_status(device_copy["device_id"])
                        device_copy["battery_level"] = device_status["battery_level"]
                        device_copy["signal_strength"] = device_status["signal_strength"]
                        device_copy["is_charging"] = device_status.get("is_charging", False)

                    devices.append(device_copy)

            logger.debug("Returned %d mock devices", len(devices))
            return devices

        except Exception as e:
            logger.error("Error getting mock devices: %s", e)
            return []

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        Get status for a specific device

        Args:
            device_id: Device identifier

        Returns:
            Device status dictionary
        """
        try:
            devices = self.get_devices()
            for device in devices:
                if device["device_id"] == device_id:
                    # Use the enhanced device status
                    device_status = temp_simulator.get_device_status(device_id)

                    return {
                        "device_id": device_id,
                        "name": device["name"],
                        "model": device["model"],
                        "is_online": device.get("is_online", True),
                        "battery_level": device_status["battery_level"],
                        "signal_strength": device_status["signal_strength"],
                        "is_charging": device_status.get("is_charging", False),
                        "last_seen": device.get("last_seen", datetime.utcnow().isoformat()),
                        "firmware_version": device.get("firmware_version", "1.0.0"),
                        "probe_count": len(device.get("probes", [])),
                    }

            logger.warning("Device not found: %s", device_id)
            return {}

        except Exception as e:
            logger.error("Error getting device status for %s: %s", device_id, e)
            return {}

    def get_temperature_data(self, device_id: str, probe_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get temperature data for a device and probe

        Args:
            device_id: Device identifier
            probe_id: Probe identifier (if None, return all probes)

        Returns:
            Temperature data dictionary
        """
        try:
            devices = self.get_devices()

            for device in devices:
                if device["device_id"] == device_id:
                    if not device.get("is_online", True):
                        return {
                            "error": "Device is offline",
                            "device_id": device_id,
                            "is_online": False,
                        }

                    probes_data = []

                    for probe in device.get("probes", []):
                        if probe_id is None or probe["probe_id"] == probe_id:
                            # Get device status for this reading
                            device_status = temp_simulator.get_device_status(device_id)

                            probe_data = {
                                "device_id": device_id,
                                "probe_id": probe["probe_id"],
                                "name": probe["name"],
                                "type": probe.get("type", "food"),
                                "temperature": probe["current_temp"],
                                "unit": probe.get("unit", "F"),
                                "timestamp": datetime.utcnow().isoformat(),
                                "battery_level": device_status["battery_level"],
                                "signal_strength": device_status["signal_strength"],
                                "is_charging": device_status.get("is_charging", False),
                                "alarm_low": probe.get("alarm_low"),
                                "alarm_high": probe.get("alarm_high"),
                                "min_temp": probe.get("min_temp", -40),
                                "max_temp": probe.get("max_temp", 572),
                            }
                            probes_data.append(probe_data)

                    if probe_id:
                        # Return single probe data
                        return probes_data[0] if probes_data else {}
                    else:
                        # Return all probes data
                        return {
                            "device_id": device_id,
                            "probes": probes_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

            logger.warning("Device not found: %s", device_id)
            return {}

        except Exception as e:
            logger.error("Error getting temperature data for %s/%s: %s", device_id, probe_id, e)
            return {}

    def get_historical_data(
        self,
        device_id: str,
        probe_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get historical temperature data

        Args:
            device_id: Device identifier
            probe_id: Probe identifier
            start_time: Start time for data (default: 4 hours ago)
            end_time: End time for data (default: now)

        Returns:
            List of historical temperature readings
        """
        try:
            # Set default time range if not provided
            if end_time is None:
                end_time = datetime.utcnow()
            if start_time is None:
                start_time = end_time - timedelta(hours=4)

            # Try to load historical data from file
            if self.historical_file.exists():
                with open(self.historical_file, "r") as f:
                    historical_data = json.load(f)

                # Filter data for requested device/probe
                readings = []
                for reading in historical_data.get("readings", []):
                    if reading["device_id"] == device_id and reading["probe_id"] == probe_id:
                        reading_time = datetime.fromisoformat(reading["timestamp"].replace("Z", ""))
                        # Convert both to naive datetime for comparison
                        if hasattr(start_time, "tzinfo") and start_time.tzinfo is not None:
                            start_time_naive = start_time.replace(tzinfo=None)
                            end_time_naive = end_time.replace(tzinfo=None)
                        else:
                            start_time_naive = start_time
                            end_time_naive = end_time
                        if start_time_naive <= reading_time <= end_time_naive:
                            readings.append(reading)

                return sorted(readings, key=lambda x: x["timestamp"])

            # Generate synthetic historical data if file doesn't exist
            return self._generate_synthetic_historical_data(device_id, probe_id, start_time, end_time)

        except Exception as e:
            logger.error("Error getting historical data for %s/%s: %s", device_id, probe_id, e)
            return []

    def _generate_synthetic_historical_data(
        self, device_id: str, probe_id: str, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Generate synthetic historical data for testing"""
        readings = []
        current_time = start_time
        interval = timedelta(seconds=30)  # 30-second intervals

        # Get current device/probe info
        devices = self.get_devices()
        current_temp = 70.0  # Default starting temperature
        probe_name = "Unknown"
        probe_type = "food"

        for device in devices:
            if device["device_id"] == device_id:
                for probe in device.get("probes", []):
                    if probe["probe_id"] == probe_id:
                        current_temp = probe["current_temp"]
                        probe_name = probe["name"]
                        probe_type = probe.get("type", "food")
                        break
                break

        # Create a temporary cooking session for this historical data
        from .cooking_profiles import get_profile_by_name
        from .temp_simulator import CookingSession

        profile = get_profile_by_name(probe_name)

        # Calculate how far back in time this is
        now = datetime.utcnow()
        days_ago = (now - start_time).days

        # Adjust the final temp based on how old this data is
        # If recent, end near current temp; if older, use a completed cook
        if days_ago < 1:
            # Recent - start from a lower temp and work toward current
            start_temp = max(40.0, current_temp - random.uniform(100.0, 150.0))
            session = CookingSession(
                device_id=device_id, probe_id=probe_id, probe_name=probe_name, initial_temp=start_temp, profile=profile
            )
        else:
            # Older - complete cook that reached target temp
            session = CookingSession(
                device_id=device_id,
                probe_id=probe_id,
                probe_name=probe_name,
                initial_temp=40.0,  # Start from refrigerator temp
                profile=profile,
            )

        # Generate time series data
        elapsed_minutes: float = 0.0
        while current_time <= end_time:
            # Simulate time passing in our session
            # Speed up time 10x for this simulation
            for _ in range(10):
                session.last_update_time = session.start_time + timedelta(minutes=elapsed_minutes).total_seconds()
                temp = session.update_temperature()
                elapsed_minutes = float(elapsed_minutes + 0.1)  # Small time steps for smoother curve

            # Get device status for this historical point
            device_status = temp_simulator.get_device_status(device_id)

            reading = {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": temp,
                "unit": "F",
                "timestamp": current_time.isoformat() + "Z",
                "battery_level": device_status["battery_level"],
                "signal_strength": device_status["signal_strength"],
            }

            readings.append(reading)
            current_time += interval

        return readings

    def is_device_online(self, device_id: str) -> bool:
        """Check if a device is online"""
        try:
            devices = self._device_data.get("devices", [])
            for device in devices:
                if device["device_id"] == device_id:
                    return bool(device.get("is_online", True))
            return False
        except Exception as e:
            logger.error("Error checking device online status for %s: %s", device_id, e)
            return False

    def get_device_battery_level(self, device_id: str) -> Optional[int]:
        """Get battery level for a device"""
        try:
            # Use the enhanced device status
            device_status = temp_simulator.get_device_status(device_id)
            return int(device_status["battery_level"])
        except Exception as e:
            logger.error("Error getting battery level for %s: %s", device_id, e)
            return None
