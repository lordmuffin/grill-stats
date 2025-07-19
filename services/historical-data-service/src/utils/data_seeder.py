"""
Data seeder for historical temperature data.
This module provides utilities to seed the database with sample temperature data for testing.
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()


class TemperatureDataSeeder:
    """Seeds historical temperature data for testing purposes."""

    def __init__(self, timescale_manager):
        self.timescale_manager = timescale_manager

    def generate_sample_temperature_data(
        self,
        device_id: str,
        probe_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generate sample temperature data for testing.

        Args:
            device_id: ID of the device
            probe_ids: List of probe IDs
            start_time: Start time for data generation
            end_time: End time for data generation
            interval_minutes: Interval between readings in minutes

        Returns:
            List of temperature readings
        """
        readings = []
        current_time = start_time

        # Base temperatures for different probes (simulating different cooking zones)
        base_temps = {
            "probe_1": 225.0,  # Grill temperature
            "probe_2": 165.0,  # Meat probe 1
            "probe_3": 175.0,  # Meat probe 2
            "probe_4": 200.0,  # Ambient probe
        }

        # Temperature trends over time (simulating a cooking session)
        while current_time <= end_time:
            for probe_id in probe_ids:
                # Get base temperature for this probe
                base_temp = base_temps.get(probe_id, 200.0)

                # Add some realistic variation
                # - Gradual temperature rise for meat probes
                # - More stable temperature for grill probes
                hours_elapsed = (current_time - start_time).total_seconds() / 3600

                if probe_id.startswith("probe_1"):  # Grill temperature
                    # Grill temperature stays relatively stable with small variations
                    temperature = base_temp + random.uniform(-10, 10) + (hours_elapsed * 2)
                else:  # Meat probes
                    # Meat temperature rises gradually
                    temperature = base_temp + (hours_elapsed * 15) + random.uniform(-5, 5)

                # Add some realistic constraints
                temperature = max(70, min(500, temperature))  # Reasonable temperature range

                # Create temperature reading
                reading = {
                    "device_id": device_id,
                    "probe_id": probe_id,
                    "temperature": round(temperature, 1),
                    "unit": "F",
                    "timestamp": current_time.isoformat(),
                    "battery_level": random.uniform(80, 100),
                    "signal_strength": random.uniform(70, 95),
                    "metadata": {
                        "source": "data_seeder",
                        "cook_session": f"test_session_{device_id}",
                        "probe_type": "thermocouple",
                    },
                }

                readings.append(reading)

            # Move to next time interval
            current_time += timedelta(minutes=interval_minutes)

        return readings

    def seed_historical_data(
        self,
        device_id: str = "test_device_001",
        probe_ids: List[str] = None,
        days_back: int = 7,
        interval_minutes: int = 5,
    ) -> int:
        """
        Seed the database with historical temperature data.

        Args:
            device_id: Device ID to create data for
            probe_ids: List of probe IDs (default: probe_1, probe_2, probe_3)
            days_back: Number of days back to create data for
            interval_minutes: Interval between readings in minutes

        Returns:
            Number of readings created
        """
        if probe_ids is None:
            probe_ids = ["probe_1", "probe_2", "probe_3"]

        # Generate data for the last N days
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)

        logger.info(
            "Generating sample temperature data",
            device_id=device_id,
            probe_count=len(probe_ids),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        # Generate sample data
        readings = self.generate_sample_temperature_data(
            device_id=device_id,
            probe_ids=probe_ids,
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval_minutes,
        )

        # Store in database
        stored_count = self.timescale_manager.store_batch_temperature_readings(readings)

        logger.info(
            "Sample data seeded successfully",
            device_id=device_id,
            readings_generated=len(readings),
            readings_stored=stored_count,
        )

        return stored_count

    def seed_multiple_devices(
        self,
        device_configs: List[Dict[str, Any]] = None,
        days_back: int = 7,
        interval_minutes: int = 5,
    ) -> Dict[str, int]:
        """
        Seed data for multiple devices.

        Args:
            device_configs: List of device configurations
            days_back: Number of days back to create data for
            interval_minutes: Interval between readings in minutes

        Returns:
            Dictionary with device_id as key and number of readings as value
        """
        if device_configs is None:
            device_configs = [
                {
                    "device_id": "test_device_001",
                    "probe_ids": ["probe_1", "probe_2", "probe_3"],
                },
                {
                    "device_id": "test_device_002",
                    "probe_ids": ["probe_1", "probe_2", "probe_3", "probe_4"],
                },
            ]

        results = {}

        for config in device_configs:
            try:
                count = self.seed_historical_data(
                    device_id=config["device_id"],
                    probe_ids=config["probe_ids"],
                    days_back=days_back,
                    interval_minutes=interval_minutes,
                )
                results[config["device_id"]] = count
            except Exception as e:
                logger.error(
                    "Failed to seed data for device",
                    device_id=config["device_id"],
                    error=str(e),
                )
                results[config["device_id"]] = 0

        return results
