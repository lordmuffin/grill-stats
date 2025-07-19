#!/usr/bin/env python3
"""
Mock Data Service for Grill Stats Application

This service provides mock data that replaces live ThermoWorks API calls during development
and testing. It generates realistic temperature data variations and supports all the same
methods as the real ThermoWorks client.

Features:
- Realistic temperature data with gradual changes
- Multiple probe types with different cooking patterns
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
        self._last_update = {}
        self._temperature_trends = {}
        self._simulation_lock = threading.Lock()

        # Load initial data
        self._load_device_data()
        self._initialize_temperature_simulation()

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

    def _initialize_temperature_simulation(self) -> None:
        """Initialize temperature simulation for each probe"""
        now = time.time()

        for device in self._device_data.get("devices", []):
            device_id = device["device_id"]
            self._last_update[device_id] = now
            self._temperature_trends[device_id] = {}

            for probe in device.get("probes", []):
                probe_id = probe["probe_id"]
                probe_type = probe.get("type", "food")

                # Initialize temperature trends based on probe type
                if probe_type == "food":
                    # Food probes generally increase slowly
                    trend = {
                        "rate": random.uniform(0.5, 2.0),  # degrees per minute
                        "target": probe.get("alarm_high", probe["current_temp"] + 20),
                        "volatility": 0.5,  # temperature noise
                        "pattern": "rising",
                    }
                elif probe_type == "ambient":
                    # Ambient probes are more stable with small fluctuations
                    trend = {
                        "rate": random.uniform(-0.2, 0.2),  # small changes
                        "target": probe["current_temp"],
                        "volatility": 1.0,
                        "pattern": "stable",
                    }
                else:  # surface, etc.
                    # Surface probes can be more variable
                    trend = {
                        "rate": random.uniform(-1.0, 1.0),
                        "target": probe["current_temp"],
                        "volatility": 2.0,
                        "pattern": "variable",
                    }

                self._temperature_trends[device_id][probe_id] = trend

    def _simulate_temperature_change(self, device_id: str, probe_id: str, current_temp: float, probe_type: str) -> float:
        """
        Simulate realistic temperature changes for a probe

        Args:
            device_id: Device identifier
            probe_id: Probe identifier
            current_temp: Current temperature
            probe_type: Type of probe (food, ambient, surface)

        Returns:
            New simulated temperature
        """
        now = time.time()

        if device_id not in self._last_update:
            self._last_update[device_id] = now
            return current_temp

        # Calculate time elapsed since last update
        time_elapsed = now - self._last_update[device_id]
        minutes_elapsed = time_elapsed / 60.0

        # Get or create trend for this probe
        if device_id not in self._temperature_trends:
            self._temperature_trends[device_id] = {}
        if probe_id not in self._temperature_trends[device_id]:
            self._initialize_temperature_simulation()

        trend = self._temperature_trends[device_id][probe_id]

        # Calculate base temperature change
        base_change = trend["rate"] * minutes_elapsed

        # Add some realistic noise/volatility
        noise = random.gauss(0, trend["volatility"]) * math.sqrt(minutes_elapsed)

        # Apply pattern-specific behavior
        if trend["pattern"] == "rising":
            # Food probes approaching target temperature slow down
            distance_to_target = abs(trend["target"] - current_temp)
            if distance_to_target < 10:
                base_change *= distance_to_target / 10.0
        elif trend["pattern"] == "stable":
            # Ambient probes oscillate around target
            distance_to_target = current_temp - trend["target"]
            base_change = -0.1 * distance_to_target + random.uniform(-0.5, 0.5)

        # Apply changes
        new_temp = current_temp + base_change + noise

        # Ensure reasonable bounds
        new_temp = max(-40, min(572, new_temp))

        # Update last update time
        self._last_update[device_id] = now

        return round(new_temp, 1)

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
                            new_temp = self._simulate_temperature_change(
                                device_copy["device_id"],
                                probe_copy["probe_id"],
                                probe_copy["current_temp"],
                                probe_copy.get("type", "food"),
                            )
                            probe_copy["current_temp"] = new_temp
                            updated_probes.append(probe_copy)

                        device_copy["probes"] = updated_probes

                        # Simulate battery drain (very slowly)
                        if random.random() < 0.01:  # 1% chance per call
                            device_copy["battery_level"] = max(0, device_copy.get("battery_level", 100) - 1)

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
                    return {
                        "device_id": device_id,
                        "name": device["name"],
                        "model": device["model"],
                        "is_online": device.get("is_online", True),
                        "battery_level": device.get("battery_level", 100),
                        "signal_strength": device.get("signal_strength", -50),
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
                            probe_data = {
                                "device_id": device_id,
                                "probe_id": probe["probe_id"],
                                "name": probe["name"],
                                "type": probe.get("type", "food"),
                                "temperature": probe["current_temp"],
                                "unit": probe.get("unit", "F"),
                                "timestamp": datetime.utcnow().isoformat(),
                                "battery_level": device.get("battery_level", 100),
                                "signal_strength": device.get("signal_strength", -50),
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

        for device in devices:
            if device["device_id"] == device_id:
                for probe in device.get("probes", []):
                    if probe["probe_id"] == probe_id:
                        current_temp = probe["current_temp"]
                        break
                break

        # Generate realistic cooking curve
        while current_time <= end_time:
            # Simulate gradual temperature rise for food probes
            time_ratio = (current_time - start_time).total_seconds() / (end_time - start_time).total_seconds()

            if "food" in probe_id.lower() or any(word in probe_id.lower() for word in ["brisket", "ribs", "chicken", "steak"]):
                # Food probe: gradual rise then plateau
                if time_ratio < 0.7:
                    # Rising phase
                    target_temp = 70 + (current_temp - 70) * (time_ratio / 0.7)
                else:
                    # Plateau phase
                    target_temp = current_temp * 0.95 + random.uniform(-2, 1)
            else:
                # Ambient probe: more stable
                target_temp = current_temp + random.uniform(-3, 3)

            # Add some noise
            actual_temp = target_temp + random.gauss(0, 1.0)
            actual_temp = max(-40, min(572, actual_temp))

            reading = {
                "device_id": device_id,
                "probe_id": probe_id,
                "temperature": round(actual_temp, 1),
                "unit": "F",
                "timestamp": current_time.isoformat() + "Z",
                "battery_level": random.randint(70, 100),
                "signal_strength": random.randint(-65, -30),
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
                    return device.get("is_online", True)
            return False
        except Exception as e:
            logger.error("Error checking device online status for %s: %s", device_id, e)
            return False

    def get_device_battery_level(self, device_id: str) -> Optional[int]:
        """Get battery level for a device"""
        try:
            devices = self._device_data.get("devices", [])
            for device in devices:
                if device["device_id"] == device_id:
                    return device.get("battery_level")
            return None
        except Exception as e:
            logger.error("Error getting battery level for %s: %s", device_id, e)
            return None
