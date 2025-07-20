"""
Temperature Handler Module

This module provides a handler for temperature readings from the ThermoWorks client.
It is responsible for publishing temperature readings to Redis and other processing.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import redis
from containers import ServicesContainer
from dependency_injector.wiring import Provide, inject

from thermoworks_client import DeviceInfo, TemperatureReading

logger = logging.getLogger("device_service")


class TemperatureHandler:
    """Handler for temperature readings from the ThermoWorks client"""

    @inject
    def __init__(self, redis_client: Optional[redis.Redis] = Provide[ServicesContainer.redis_client]):
        """
        Initialize the temperature handler

        Args:
            redis_client: Redis client for publishing readings
        """
        self.redis_client = redis_client

    def handle_temperature_readings(self, device: DeviceInfo, readings: List[TemperatureReading]) -> None:
        """
        Handle temperature readings from a device

        Args:
            device: Device information
            readings: List of temperature readings
        """
        logger.info(f"Received {len(readings)} temperature readings for device {device.device_id}")

        # Publish to Redis if available
        if self.redis_client:
            try:
                # Publish each reading to a device-specific channel
                for reading in readings:
                    channel = f"temperature:{device.device_id}:{reading.probe_id}"
                    message = json.dumps(reading.to_dict())
                    self.redis_client.publish(channel, message)

                    # Also store the latest reading in a key for easy retrieval
                    key = f"temperature:latest:{device.device_id}:{reading.probe_id}"
                    self.redis_client.set(key, message)
                    self.redis_client.expire(key, 3600)  # Expire after 1 hour

                logger.debug(f"Published temperature readings to Redis for device {device.device_id}")
            except redis.RedisError as e:
                logger.error(f"Failed to publish temperature readings to Redis: {e}")
