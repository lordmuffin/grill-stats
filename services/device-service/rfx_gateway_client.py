"""
RFX Gateway Client

This module provides functionality for setting up and managing RFX Gateways,
including Wi-Fi configuration, Bluetooth connectivity, and ThermoWorks Cloud
account linking.
"""

import os
import json
import time
import logging
import threading
import requests
import datetime
import uuid
import secrets
import base64
import hashlib
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Union, Any, Tuple, Set
from enum import Enum
from ha_bluetooth_client import HomeAssistantBluetoothClient, BluetoothDevice, BluetoothDeviceState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rfx_gateway_client")


class GatewaySetupStep(Enum):
    """Enum for tracking gateway setup progress"""
    DISCOVERY = "discovery"
    BLUETOOTH_CONNECTION = "bluetooth_connection"
    WIFI_CONFIGURATION = "wifi_configuration"
    CLOUD_LINKING = "cloud_linking"
    CONFIRMATION = "confirmation"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class WiFiNetwork:
    """Class for representing a Wi-Fi network"""
    ssid: str
    signal_strength: int  # RSSI value
    security_type: str  # WPA, WPA2, WPA3, WEP, Open
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class GatewaySetupStatus:
    """Class for tracking gateway setup status"""
    gateway_id: str
    step: GatewaySetupStep = GatewaySetupStep.DISCOVERY
    progress: int = 0  # 0-100
    error: Optional[str] = None
    connected_to_bluetooth: bool = False
    wifi_networks: List[WiFiNetwork] = field(default_factory=list)
    selected_wifi: Optional[str] = None
    wifi_connected: bool = False
    cloud_linked: bool = False
    online: bool = False
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["step"] = self.step.value
        return result


class RFXGatewayError(Exception):
    """Exception for RFX Gateway errors"""
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class RFXGatewayClient:
    """
    Client for managing RFX Gateways
    
    This class provides methods for setting up and managing RFX Gateways,
    including Wi-Fi configuration, Bluetooth connectivity, and ThermoWorks
    Cloud account linking.
    """
    
    # RFX Gateway Bluetooth service and characteristic UUIDs
    BT_SERVICE_UUID = "00001234-0000-1000-8000-00805f9b34fb"  # Example UUID - replace with actual
    BT_CONFIG_CHAR_UUID = "00001235-0000-1000-8000-00805f9b34fb"  # Example UUID - replace with actual
    BT_STATUS_CHAR_UUID = "00001236-0000-1000-8000-00805f9b34fb"  # Example UUID - replace with actual
    
    def __init__(
        self,
        thermoworks_client: Any,
        ha_url: str,
        ha_token: str,
        max_scan_duration: int = 30,
        connection_timeout: int = 15,
        setup_timeout: int = 300,
    ):
        """
        Initialize the RFX Gateway client
        
        Args:
            thermoworks_client: ThermoWorks client instance for cloud operations
            ha_url: Home Assistant URL
            ha_token: Long-lived access token for Home Assistant
            max_scan_duration: Maximum Bluetooth scan duration in seconds
            connection_timeout: Bluetooth connection timeout in seconds
            setup_timeout: Overall setup timeout in seconds
        """
        self.thermoworks_client = thermoworks_client
        self.max_scan_duration = max_scan_duration
        self.connection_timeout = connection_timeout
        self.setup_timeout = setup_timeout
        
        # Initialize Home Assistant Bluetooth client
        self.bluetooth_client = HomeAssistantBluetoothClient(ha_url, ha_token)
        
        # Gateway setup tracking
        self.active_setups: Dict[str, GatewaySetupStatus] = {}
        self._setup_lock = threading.RLock()
        
        # Bluetooth connection tracking
        self.connected_devices: Dict[str, BluetoothDevice] = {}
        self._bluetooth_lock = threading.RLock()
    
    def discover_gateways(self, timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Discover nearby RFX Gateways using Home Assistant's Bluetooth integration
        
        Args:
            timeout: Scan timeout in seconds (defaults to max_scan_duration)
            
        Returns:
            List of discovered gateway devices
        """
        timeout = timeout or self.max_scan_duration
        logger.info(f"Starting Bluetooth scan for RFX Gateways via Home Assistant (timeout: {timeout}s)")
        
        discovered_devices = []
        try:
            # Use Home Assistant to discover devices
            devices = self.bluetooth_client.discover_devices(scan_duration=timeout)
            
            for device in devices:
                # Filter for RFX Gateway devices based on name
                if "RFX" in device.name or "Gateway" in device.name:
                    logger.info(f"Found potential RFX Gateway: {device.name} ({device.address})")
                    gateway_id = device.id
                    
                    gateway_info = {
                        "id": gateway_id,
                        "name": device.name,
                        "address": device.address,
                        "signal_strength": device.rssi,
                        "type": "RFX Gateway",
                    }
                    
                    discovered_devices.append(gateway_info)
                    
                    # Create a setup status entry for this gateway
                    with self._setup_lock:
                        if gateway_id not in self.active_setups:
                            self.active_setups[gateway_id] = GatewaySetupStatus(
                                gateway_id=gateway_id
                            )
            
            logger.info(f"Discovered {len(discovered_devices)} RFX Gateway devices")
            return discovered_devices
            
        except Exception as e:
            logger.error(f"Error discovering RFX Gateways: {e}")
            raise RFXGatewayError(f"Failed to discover RFX Gateways: {str(e)}")
    
    def connect_to_gateway(self, gateway_id: str) -> bool:
        """
        Connect to an RFX Gateway via Home Assistant's Bluetooth integration
        
        Args:
            gateway_id: Gateway ID
            
        Returns:
            True if connection successful, False otherwise
        """
        logger.info(f"Connecting to RFX Gateway {gateway_id} via Home Assistant")
        
        with self._setup_lock:
            if gateway_id not in self.active_setups:
                self.active_setups[gateway_id] = GatewaySetupStatus(
                    gateway_id=gateway_id,
                    step=GatewaySetupStep.BLUETOOTH_CONNECTION,
                    progress=10
                )
            else:
                setup = self.active_setups[gateway_id]
                setup.step = GatewaySetupStep.BLUETOOTH_CONNECTION
                setup.progress = 10
                setup.last_updated = time.time()
        
        try:
            # Connect using Home Assistant
            success = self.bluetooth_client.connect_device(gateway_id)
            
            if success:
                with self._bluetooth_lock:
                    self.connected_devices[gateway_id] = success
                    
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.connected_to_bluetooth = True
                    setup.progress = 20
                    setup.last_updated = time.time()
                    
                logger.info(f"Successfully connected to RFX Gateway {gateway_id}")
                return True
            else:
                logger.error(f"Failed to connect to RFX Gateway {gateway_id}")
                
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.error = "Bluetooth connection failed"
                    setup.last_updated = time.time()
                    
                return False
            
        except Exception as e:
            logger.error(f"Failed to connect to RFX Gateway {gateway_id}: {e}")
            
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.error = f"Bluetooth connection failed: {str(e)}"
                setup.last_updated = time.time()
                
            return False