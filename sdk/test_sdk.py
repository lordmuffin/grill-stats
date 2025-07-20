#!/usr/bin/env python3
"""
Test script for the Grill Stats API Client SDK.

This script demonstrates how to use the SDK in mock mode to interact with
ThermoWorks devices and Home Assistant integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, cast

from grill_stats_client import HomeAssistantClient, ThermoWorksClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_thermoworks_client() -> None:
    """Test the ThermoWorks client in mock mode."""
    logger.info("Testing ThermoWorks client...")

    # Initialize client in mock mode
    client = ThermoWorksClient(mock_mode=True)

    # Get devices
    devices = client.get_devices()
    logger.info(f"Found {len(devices)} devices")

    # Get temperature data for the first device
    if devices:
        device_id = cast(str, devices[0].get("id", ""))
        device_name = devices[0].get("name")
        logger.info(f"Getting temperature data for device: {device_name} (ID: {device_id})")

        temp_data = client.get_temperature_data(device_id)
        logger.info(f"Temperature: {temp_data.get('temperature')}°{temp_data.get('unit')}")
        logger.info(f"Battery: {temp_data.get('battery_level')}%")
        logger.info(f"Signal: {temp_data.get('signal_strength')}%")

        # Get historical data
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        logger.info(f"Getting historical data from {start_time} to {end_time}")
        history = client.get_historical_data(device_id, start_time, end_time)
        logger.info(f"Found {len(history)} historical readings")

    logger.info("ThermoWorks client test completed")


def test_homeassistant_client() -> None:
    """Test the Home Assistant client in mock mode."""
    logger.info("Testing Home Assistant client...")

    # Initialize client in mock mode
    client = HomeAssistantClient(mock_mode=True)

    # Test connection
    connection_success = client.test_connection()
    logger.info(f"Connection test: {'Success' if connection_success else 'Failed'}")

    # Create a sensor
    sensor_name = "grill_temperature_test"
    logger.info(f"Creating sensor: {sensor_name}")

    sensor_created = client.create_sensor(
        sensor_name=sensor_name,
        state=225.5,
        attributes={
            "device_id": "test_device_001",
            "last_updated": datetime.now().isoformat(),
            "battery_level": 85,
            "signal_strength": 92,
        },
        unit="F",
    )
    logger.info(f"Sensor creation: {'Success' if sensor_created else 'Failed'}")

    # Send a notification
    notification_sent = client.send_notification(message="Test notification from Grill Stats SDK", title="Grill Stats Test")
    logger.info(f"Notification sent: {'Success' if notification_sent else 'Failed'}")

    # Call a service
    service_called = client.call_service(
        domain="light", service="turn_on", service_data={"brightness": 255}, target={"entity_id": "light.kitchen"}
    )
    logger.info(f"Service call: {'Success' if service_called else 'Failed'}")

    logger.info("Home Assistant client test completed")


if __name__ == "__main__":
    logger.info("Starting SDK tests...")

    try:
        test_thermoworks_client()
        test_homeassistant_client()
        logger.info("All tests completed successfully")
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
