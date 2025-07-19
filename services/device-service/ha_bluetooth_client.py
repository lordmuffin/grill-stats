"""Home Assistant Bluetooth client for managing RFX gateway connections."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from homeassistant_api import Client as HAClient

logger = logging.getLogger(__name__)


class BluetoothDeviceState(Enum):
    """State of a Bluetooth device."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class BluetoothDevice:
    """Represents a Bluetooth device discovered by Home Assistant."""

    id: str
    name: str
    address: str
    rssi: int
    state: BluetoothDeviceState
    attributes: Dict[str, Any]


class HomeAssistantBluetoothClient:
    """Client for interacting with Home Assistant's Bluetooth integration."""

    def __init__(self, ha_url: str, ha_token: str):
        """Initialize the client.

        Args:
            ha_url: Home Assistant URL
            ha_token: Long-lived access token
        """
        self.client = HAClient(ha_url, ha_token)
        self._connected_devices: Dict[str, BluetoothDevice] = {}

    def discover_devices(self, scan_duration: int = 10) -> List[BluetoothDevice]:
        """Discover Bluetooth devices through Home Assistant.

        Args:
            scan_duration: How long to scan for devices in seconds

        Returns:
            List of discovered devices
        """
        logger.info(f"Starting Bluetooth scan via Home Assistant (duration: {scan_duration}s)")

        try:
            # Start a Bluetooth discovery scan
            self.client.post("/api/services/bluetooth/start_discovery", {"duration": scan_duration})

            # Wait for scan to complete
            time.sleep(scan_duration)

            # Get discovered devices
            response = self.client.get("/api/bluetooth/devices")
            devices = []

            for device_data in response.get("devices", []):
                device = BluetoothDevice(
                    id=device_data["id"],
                    name=device_data.get("name", device_data["address"]),
                    address=device_data["address"],
                    rssi=device_data.get("rssi", 0),
                    state=BluetoothDeviceState(device_data.get("state", "disconnected")),
                    attributes=device_data.get("attributes", {}),
                )
                devices.append(device)

            return devices

        except Exception as e:
            logger.error(f"Error discovering Bluetooth devices: {e}")
            return []

    def connect_device(self, device_id: str) -> bool:
        """Connect to a Bluetooth device through Home Assistant.

        Args:
            device_id: ID of the device to connect to

        Returns:
            True if connection successful, False otherwise
        """
        logger.info(f"Connecting to Bluetooth device {device_id}")

        try:
            # Connect to the device
            response = self.client.post(f"/api/bluetooth/connect", {"device_id": device_id})

            if response.get("success"):
                # Get updated device info
                device_info = self.client.get(f"/api/bluetooth/device/{device_id}")

                device = BluetoothDevice(
                    id=device_info["id"],
                    name=device_info.get("name", device_info["address"]),
                    address=device_info["address"],
                    rssi=device_info.get("rssi", 0),
                    state=BluetoothDeviceState(device_info.get("state", "connected")),
                    attributes=device_info.get("attributes", {}),
                )
                self._connected_devices[device_id] = device
                return True

            return False

        except Exception as e:
            logger.error(f"Error connecting to device {device_id}: {e}")
            return False

    def disconnect_device(self, device_id: str) -> bool:
        """Disconnect from a Bluetooth device.

        Args:
            device_id: ID of the device to disconnect from

        Returns:
            True if disconnection successful, False otherwise
        """
        logger.info(f"Disconnecting from Bluetooth device {device_id}")

        try:
            response = self.client.post(f"/api/bluetooth/disconnect", {"device_id": device_id})

            if response.get("success"):
                self._connected_devices.pop(device_id, None)
                return True

            return False

        except Exception as e:
            logger.error(f"Error disconnecting from device {device_id}: {e}")
            return False

    def send_data(self, device_id: str, data: bytes) -> bool:
        """Send data to a connected Bluetooth device.

        Args:
            device_id: ID of the device to send data to
            data: Data to send

        Returns:
            True if data sent successfully, False otherwise
        """
        if device_id not in self._connected_devices:
            logger.error(f"Device {device_id} not connected")
            return False

        try:
            response = self.client.post(f"/api/bluetooth/write", {"device_id": device_id, "data": data.hex()})
            return response.get("success", False)

        except Exception as e:
            logger.error(f"Error sending data to device {device_id}: {e}")
            return False

    def receive_data(self, device_id: str, timeout: int = 5) -> Optional[bytes]:
        """Receive data from a connected Bluetooth device.

        Args:
            device_id: ID of the device to receive data from
            timeout: How long to wait for data in seconds

        Returns:
            Received data or None if no data received
        """
        if device_id not in self._connected_devices:
            logger.error(f"Device {device_id} not connected")
            return None

        try:
            response = self.client.get(f"/api/bluetooth/read", {"device_id": device_id, "timeout": timeout})

            if response.get("success") and "data" in response:
                return bytes.fromhex(response["data"])

            return None

        except Exception as e:
            logger.error(f"Error receiving data from device {device_id}: {e}")
            return None
