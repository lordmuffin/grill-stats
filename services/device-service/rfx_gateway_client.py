#!/usr/bin/env python3
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
import bluetooth

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
        max_scan_duration: int = 30,
        connection_timeout: int = 15,
        setup_timeout: int = 300,
    ):
        """
        Initialize the RFX Gateway client
        
        Args:
            thermoworks_client: ThermoWorks client instance for cloud operations
            max_scan_duration: Maximum Bluetooth scan duration in seconds
            connection_timeout: Bluetooth connection timeout in seconds
            setup_timeout: Overall setup timeout in seconds
        """
        self.thermoworks_client = thermoworks_client
        self.max_scan_duration = max_scan_duration
        self.connection_timeout = connection_timeout
        self.setup_timeout = setup_timeout
        
        # Gateway setup tracking
        self.active_setups: Dict[str, GatewaySetupStatus] = {}
        self._setup_lock = threading.RLock()
        
        # Bluetooth connection tracking
        self.connected_devices: Dict[str, Any] = {}
        self._bluetooth_lock = threading.RLock()
        
    def discover_gateways(self, timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Discover nearby RFX Gateways using Bluetooth
        
        Args:
            timeout: Scan timeout in seconds (defaults to max_scan_duration)
            
        Returns:
            List of discovered gateway devices
        """
        timeout = timeout or self.max_scan_duration
        logger.info(f"Starting Bluetooth scan for RFX Gateways (timeout: {timeout}s)")
        
        discovered_devices = []
        try:
            # Use PyBluez to discover devices
            nearby_devices = bluetooth.discover_devices(
                duration=timeout,
                lookup_names=True,
                lookup_class=True,
                device_id=-1
            )
            
            for addr, name, device_class in nearby_devices:
                # Filter for RFX Gateway devices based on name or class
                if "RFX" in name or "Gateway" in name:
                    logger.info(f"Found potential RFX Gateway: {name} ({addr})")
                    gateway_id = addr.replace(":", "")
                    
                    gateway_info = {
                        "id": gateway_id,
                        "name": name,
                        "address": addr,
                        "signal_strength": -1,  # Not available from discovery
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
        Connect to an RFX Gateway via Bluetooth
        
        Args:
            gateway_id: Gateway ID (derived from Bluetooth address)
            
        Returns:
            True if connection successful, False otherwise
        """
        logger.info(f"Connecting to RFX Gateway {gateway_id}")
        
        # Get Bluetooth address from gateway ID
        addr = ':'.join(gateway_id[i:i+2] for i in range(0, len(gateway_id), 2))
        
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
            # Create a Bluetooth socket
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.settimeout(self.connection_timeout)
            
            # Try to connect
            sock.connect((addr, 1))  # RFCOMM channel 1
            
            with self._bluetooth_lock:
                self.connected_devices[gateway_id] = sock
                
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.connected_to_bluetooth = True
                setup.progress = 20
                setup.last_updated = time.time()
                
            logger.info(f"Successfully connected to RFX Gateway {gateway_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to RFX Gateway {gateway_id}: {e}")
            
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.error = f"Bluetooth connection failed: {str(e)}"
                setup.last_updated = time.time()
                
            return False
    
    def scan_wifi_networks(self, gateway_id: str) -> List[WiFiNetwork]:
        """
        Scan for available Wi-Fi networks using the connected gateway
        
        Args:
            gateway_id: Gateway ID
            
        Returns:
            List of discovered Wi-Fi networks
        """
        logger.info(f"Scanning for Wi-Fi networks with gateway {gateway_id}")
        
        with self._setup_lock:
            setup = self.active_setups.get(gateway_id)
            if not setup:
                raise RFXGatewayError(f"No active setup for gateway {gateway_id}")
                
            if not setup.connected_to_bluetooth:
                raise RFXGatewayError(f"Gateway {gateway_id} is not connected via Bluetooth")
                
            setup.step = GatewaySetupStep.WIFI_CONFIGURATION
            setup.progress = 30
            setup.last_updated = time.time()
        
        with self._bluetooth_lock:
            sock = self.connected_devices.get(gateway_id)
            if not sock:
                raise RFXGatewayError(f"No Bluetooth connection to gateway {gateway_id}")
        
        try:
            # Send command to scan for Wi-Fi networks
            command = json.dumps({"command": "scan_wifi"}).encode()
            sock.send(command)
            
            # Wait for response
            response = b""
            start_time = time.time()
            
            while time.time() - start_time < 10:  # 10 second timeout
                try:
                    data = sock.recv(1024)
                    if not data:
                        break
                    response += data
                    
                    # Check if we have a complete JSON response
                    try:
                        result = json.loads(response.decode())
                        break
                    except json.JSONDecodeError:
                        # Not complete yet, keep receiving
                        continue
                        
                except bluetooth.btcommon.BluetoothError as e:
                    logger.warning(f"Bluetooth error while receiving data: {e}")
                    break
            
            # Parse the response
            try:
                result = json.loads(response.decode())
                networks = []
                
                for network in result.get("networks", []):
                    wifi = WiFiNetwork(
                        ssid=network.get("ssid", "Unknown"),
                        signal_strength=network.get("rssi", -100),
                        security_type=network.get("security", "Unknown")
                    )
                    networks.append(wifi)
                
                # Sort by signal strength (strongest first)
                networks.sort(key=lambda x: x.signal_strength, reverse=True)
                
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.wifi_networks = networks
                    setup.progress = 40
                    setup.last_updated = time.time()
                
                logger.info(f"Discovered {len(networks)} Wi-Fi networks")
                return networks
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {response.decode()}")
                raise RFXGatewayError("Invalid response from gateway while scanning for Wi-Fi networks")
                
        except Exception as e:
            logger.error(f"Error scanning for Wi-Fi networks: {e}")
            
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.error = f"Wi-Fi scan failed: {str(e)}"
                setup.last_updated = time.time()
                
            raise RFXGatewayError(f"Failed to scan for Wi-Fi networks: {str(e)}")
    
    def configure_wifi(self, gateway_id: str, ssid: str, password: str, security_type: Optional[str] = None) -> bool:
        """
        Configure the gateway to connect to a Wi-Fi network
        
        Args:
            gateway_id: Gateway ID
            ssid: Wi-Fi network SSID
            password: Wi-Fi network password
            security_type: Wi-Fi security type (auto-detected if not provided)
            
        Returns:
            True if configuration successful, False otherwise
        """
        logger.info(f"Configuring Wi-Fi connection for gateway {gateway_id} to network {ssid}")
        
        with self._setup_lock:
            setup = self.active_setups.get(gateway_id)
            if not setup:
                raise RFXGatewayError(f"No active setup for gateway {gateway_id}")
                
            if not setup.connected_to_bluetooth:
                raise RFXGatewayError(f"Gateway {gateway_id} is not connected via Bluetooth")
                
            setup.selected_wifi = ssid
            setup.progress = 50
            setup.last_updated = time.time()
        
        with self._bluetooth_lock:
            sock = self.connected_devices.get(gateway_id)
            if not sock:
                raise RFXGatewayError(f"No Bluetooth connection to gateway {gateway_id}")
        
        try:
            # Find security type if not provided
            if not security_type:
                for network in setup.wifi_networks:
                    if network.ssid == ssid:
                        security_type = network.security_type
                        break
            
            # Send Wi-Fi configuration command
            config = {
                "command": "configure_wifi",
                "ssid": ssid,
                "password": password,
                "security_type": security_type or "WPA2"
            }
            
            command = json.dumps(config).encode()
            sock.send(command)
            
            # Wait for response
            response = b""
            start_time = time.time()
            
            while time.time() - start_time < 30:  # 30 second timeout for connection
                try:
                    data = sock.recv(1024)
                    if not data:
                        break
                    response += data
                    
                    # Check if we have a complete JSON response
                    try:
                        result = json.loads(response.decode())
                        break
                    except json.JSONDecodeError:
                        # Not complete yet, keep receiving
                        continue
                        
                except bluetooth.btcommon.BluetoothError as e:
                    logger.warning(f"Bluetooth error while receiving data: {e}")
                    break
            
            # Parse the response
            try:
                result = json.loads(response.decode())
                success = result.get("success", False)
                
                if success:
                    with self._setup_lock:
                        setup = self.active_setups[gateway_id]
                        setup.wifi_connected = True
                        setup.progress = 60
                        setup.last_updated = time.time()
                    
                    logger.info(f"Successfully configured Wi-Fi for gateway {gateway_id}")
                    return True
                else:
                    error = result.get("error", "Unknown error")
                    logger.error(f"Failed to configure Wi-Fi: {error}")
                    
                    with self._setup_lock:
                        setup = self.active_setups[gateway_id]
                        setup.error = f"Wi-Fi configuration failed: {error}"
                        setup.last_updated = time.time()
                    
                    return False
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {response.decode()}")
                
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.error = "Invalid response from gateway while configuring Wi-Fi"
                    setup.last_updated = time.time()
                
                return False
                
        except Exception as e:
            logger.error(f"Error configuring Wi-Fi: {e}")
            
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.error = f"Wi-Fi configuration failed: {str(e)}"
                setup.last_updated = time.time()
                
            return False
    
    def link_to_thermoworks_account(self, gateway_id: str) -> bool:
        """
        Link the gateway to the user's ThermoWorks Cloud account
        
        Args:
            gateway_id: Gateway ID
            
        Returns:
            True if linking successful, False otherwise
        """
        logger.info(f"Linking gateway {gateway_id} to ThermoWorks Cloud account")
        
        with self._setup_lock:
            setup = self.active_setups.get(gateway_id)
            if not setup:
                raise RFXGatewayError(f"No active setup for gateway {gateway_id}")
                
            if not setup.wifi_connected:
                raise RFXGatewayError(f"Gateway {gateway_id} is not connected to Wi-Fi")
                
            setup.step = GatewaySetupStep.CLOUD_LINKING
            setup.progress = 70
            setup.last_updated = time.time()
        
        try:
            # Ensure we're authenticated with ThermoWorks Cloud
            if not self.thermoworks_client.token:
                raise RFXGatewayError("Not authenticated with ThermoWorks Cloud")
            
            # Get gateway information from the ThermoWorks Cloud
            # This will help confirm the gateway is online and accessible
            try:
                # Try to get the gateway from the cloud to check if it's already registered
                gateway_info = self.thermoworks_client._make_api_request(
                    "GET", f"/gateways/{gateway_id}"
                )
                
                logger.info(f"Gateway {gateway_id} is already registered with ThermoWorks Cloud")
                
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.cloud_linked = True
                    setup.online = gateway_info.get("is_online", False)
                    setup.progress = 90
                    setup.last_updated = time.time()
                
                return True
                
            except Exception:
                # Gateway not found, proceed with registration
                pass
            
            # Send registration request to ThermoWorks Cloud
            registration_data = {
                "gateway_id": gateway_id,
                "name": f"RFX Gateway {gateway_id[-6:]}",  # Default name using last 6 chars of ID
                "type": "rfx_gateway"
            }
            
            result = self.thermoworks_client._make_api_request(
                "POST", "/gateways/register", json_data=registration_data
            )
            
            success = result.get("success", False)
            
            if success:
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.cloud_linked = True
                    setup.online = True
                    setup.progress = 90
                    setup.step = GatewaySetupStep.CONFIRMATION
                    setup.last_updated = time.time()
                
                logger.info(f"Successfully linked gateway {gateway_id} to ThermoWorks Cloud account")
                return True
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"Failed to link gateway to ThermoWorks Cloud: {error}")
                
                with self._setup_lock:
                    setup = self.active_setups[gateway_id]
                    setup.error = f"Cloud linking failed: {error}"
                    setup.last_updated = time.time()
                
                return False
                
        except Exception as e:
            logger.error(f"Error linking gateway to ThermoWorks Cloud: {e}")
            
            with self._setup_lock:
                setup = self.active_setups[gateway_id]
                setup.error = f"Cloud linking failed: {str(e)}"
                setup.last_updated = time.time()
                
            return False
    
    def complete_setup(self, gateway_id: str) -> Dict[str, Any]:
        """
        Complete the gateway setup process
        
        Args:
            gateway_id: Gateway ID
            
        Returns:
            Dictionary with gateway status information
        """
        logger.info(f"Completing setup for gateway {gateway_id}")
        
        with self._setup_lock:
            setup = self.active_setups.get(gateway_id)
            if not setup:
                raise RFXGatewayError(f"No active setup for gateway {gateway_id}")
                
            if not setup.cloud_linked:
                raise RFXGatewayError(f"Gateway {gateway_id} is not linked to ThermoWorks Cloud")
                
            setup.step = GatewaySetupStep.COMPLETE
            setup.progress = 100
            setup.last_updated = time.time()
            
            # Close Bluetooth connection if still open
            with self._bluetooth_lock:
                sock = self.connected_devices.pop(gateway_id, None)
                if sock:
                    try:
                        sock.close()
                    except Exception as e:
                        logger.warning(f"Error closing Bluetooth connection: {e}")
            
            # Return the final status
            return setup.to_dict()
    
    def get_setup_status(self, gateway_id: str) -> Dict[str, Any]:
        """
        Get the current setup status for a gateway
        
        Args:
            gateway_id: Gateway ID
            
        Returns:
            Dictionary with setup status information
        """
        with self._setup_lock:
            setup = self.active_setups.get(gateway_id)
            if not setup:
                raise RFXGatewayError(f"No active setup for gateway {gateway_id}")
                
            return setup.to_dict()
    
    def cancel_setup(self, gateway_id: str) -> None:
        """
        Cancel an in-progress gateway setup
        
        Args:
            gateway_id: Gateway ID
        """
        logger.info(f"Cancelling setup for gateway {gateway_id}")
        
        with self._setup_lock:
            if gateway_id in self.active_setups:
                del self.active_setups[gateway_id]
                
        with self._bluetooth_lock:
            sock = self.connected_devices.pop(gateway_id, None)
            if sock:
                try:
                    sock.close()
                except Exception as e:
                    logger.warning(f"Error closing Bluetooth connection: {e}")
    
    def cleanup(self) -> None:
        """
        Clean up resources
        """
        logger.info("Cleaning up RFX Gateway client resources")
        
        with self._bluetooth_lock:
            for gateway_id, sock in list(self.connected_devices.items()):
                try:
                    sock.close()
                except Exception as e:
                    logger.warning(f"Error closing Bluetooth connection to {gateway_id}: {e}")
            
            self.connected_devices.clear()
        
        with self._setup_lock:
            self.active_setups.clear()