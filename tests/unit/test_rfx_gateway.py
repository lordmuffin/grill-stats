import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import json
import time
from datetime import datetime
import sys
import os

# Mock bluetooth module
sys.modules['bluetooth'] = __import__('mock_bluetooth')

from rfx_gateway_client import (
    RFXGatewayClient, 
    RFXGatewayError, 
    GatewaySetupStep, 
    WiFiNetwork, 
    GatewaySetupStatus
)

class TestRFXGatewayClient(unittest.TestCase):
    """Test cases for the RFX Gateway client."""
    
    def setUp(self):
        """Set up the test case."""
        self.thermoworks_client = MagicMock()
        self.gateway_client = RFXGatewayClient(
            thermoworks_client=self.thermoworks_client,
            max_scan_duration=1,
            connection_timeout=1,
            setup_timeout=5
        )
        
    @patch('bluetooth.discover_devices')
    def test_discover_gateways(self, mock_discover):
        """Test discovering RFX Gateways."""
        # Mock discover_devices to return a list of devices
        mock_discover.return_value = [
            ('00:11:22:33:44:55', 'RFX Gateway 123', 0),
            ('AA:BB:CC:DD:EE:FF', 'Regular Bluetooth Device', 0)
        ]
        
        gateways = self.gateway_client.discover_gateways(timeout=1)
        
        # Verify that the discovery found the RFX Gateway
        self.assertEqual(len(gateways), 1)
        self.assertEqual(gateways[0]['id'], '001122334455')
        self.assertEqual(gateways[0]['name'], 'RFX Gateway 123')
        
        # Verify that a setup status was created
        self.assertIn('001122334455', self.gateway_client.active_setups)
        
    @patch('bluetooth.BluetoothSocket')
    def test_connect_to_gateway(self, mock_socket_class):
        """Test connecting to an RFX Gateway."""
        # Mock BluetoothSocket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        
        # Create a setup status
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(gateway_id=gateway_id)
        
        # Connect to the gateway
        result = self.gateway_client.connect_to_gateway(gateway_id)
        
        # Verify connection was successful
        self.assertTrue(result)
        self.assertTrue(self.gateway_client.active_setups[gateway_id].connected_to_bluetooth)
        
        # Verify socket connection was attempted
        mock_socket.connect.assert_called_once()
        
    @patch('bluetooth.BluetoothSocket')
    def test_scan_wifi_networks(self, mock_socket_class):
        """Test scanning for Wi-Fi networks."""
        # Mock BluetoothSocket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        
        # Set up mock response
        wifi_response = {
            'networks': [
                {'ssid': 'Home WiFi', 'rssi': -50, 'security': 'WPA2'},
                {'ssid': 'Guest Network', 'rssi': -70, 'security': 'Open'}
            ]
        }
        mock_socket.recv.return_value = json.dumps(wifi_response).encode()
        
        # Create a setup status and connect
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(
            gateway_id=gateway_id,
            connected_to_bluetooth=True
        )
        self.gateway_client.connected_devices[gateway_id] = mock_socket
        
        # Scan for networks
        networks = self.gateway_client.scan_wifi_networks(gateway_id)
        
        # Verify networks were found
        self.assertEqual(len(networks), 2)
        self.assertEqual(networks[0].ssid, 'Home WiFi')
        self.assertEqual(networks[0].signal_strength, -50)
        self.assertEqual(networks[0].security_type, 'WPA2')
        
        # Verify command was sent
        mock_socket.send.assert_called_once()
        
    @patch('bluetooth.BluetoothSocket')
    def test_configure_wifi(self, mock_socket_class):
        """Test configuring Wi-Fi."""
        # Mock BluetoothSocket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        
        # Set up mock response
        wifi_response = {'success': True}
        mock_socket.recv.return_value = json.dumps(wifi_response).encode()
        
        # Create a setup status, connect, and add networks
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(
            gateway_id=gateway_id,
            connected_to_bluetooth=True,
            wifi_networks=[
                WiFiNetwork(ssid='Home WiFi', signal_strength=-50, security_type='WPA2')
            ]
        )
        self.gateway_client.connected_devices[gateway_id] = mock_socket
        
        # Configure Wi-Fi
        result = self.gateway_client.configure_wifi(
            gateway_id, 'Home WiFi', 'password123', 'WPA2'
        )
        
        # Verify configuration was successful
        self.assertTrue(result)
        self.assertTrue(self.gateway_client.active_setups[gateway_id].wifi_connected)
        self.assertEqual(self.gateway_client.active_setups[gateway_id].selected_wifi, 'Home WiFi')
        
        # Verify command was sent
        mock_socket.send.assert_called_once()
        
    def test_link_to_thermoworks_account(self):
        """Test linking to ThermoWorks Cloud account."""
        # Mock ThermoWorks client response
        self.thermoworks_client._make_api_request.return_value = {'success': True}
        
        # Create a setup status with Wi-Fi connected
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(
            gateway_id=gateway_id,
            wifi_connected=True
        )
        
        # Link to account
        result = self.gateway_client.link_to_thermoworks_account(gateway_id)
        
        # Verify linking was successful
        self.assertTrue(result)
        self.assertTrue(self.gateway_client.active_setups[gateway_id].cloud_linked)
        
        # Verify API request was made
        self.thermoworks_client._make_api_request.assert_called_once()
        
    def test_complete_setup(self):
        """Test completing setup."""
        # Create a setup status with cloud linked
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(
            gateway_id=gateway_id,
            cloud_linked=True
        )
        
        # Complete setup
        result = self.gateway_client.complete_setup(gateway_id)
        
        # Verify setup was completed
        self.assertEqual(result['step'], GatewaySetupStep.COMPLETE.value)
        self.assertEqual(result['progress'], 100)
        
    def test_get_setup_status(self):
        """Test getting setup status."""
        # Create a setup status
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(
            gateway_id=gateway_id,
            step=GatewaySetupStep.WIFI_CONFIGURATION,
            progress=50
        )
        
        # Get status
        status = self.gateway_client.get_setup_status(gateway_id)
        
        # Verify status
        self.assertEqual(status['gateway_id'], gateway_id)
        self.assertEqual(status['step'], GatewaySetupStep.WIFI_CONFIGURATION.value)
        self.assertEqual(status['progress'], 50)
        
    def test_cancel_setup(self):
        """Test cancelling setup."""
        # Create a setup status and connect
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(gateway_id=gateway_id)
        self.gateway_client.connected_devices[gateway_id] = MagicMock()
        
        # Cancel setup
        self.gateway_client.cancel_setup(gateway_id)
        
        # Verify setup was cancelled
        self.assertNotIn(gateway_id, self.gateway_client.active_setups)
        self.assertNotIn(gateway_id, self.gateway_client.connected_devices)
        
    def test_cleanup(self):
        """Test cleanup."""
        # Create a setup status and connect
        gateway_id = '001122334455'
        self.gateway_client.active_setups[gateway_id] = GatewaySetupStatus(gateway_id=gateway_id)
        self.gateway_client.connected_devices[gateway_id] = MagicMock()
        
        # Cleanup
        self.gateway_client.cleanup()
        
        # Verify resources were cleaned up
        self.assertEqual(len(self.gateway_client.active_setups), 0)
        self.assertEqual(len(self.gateway_client.connected_devices), 0)

if __name__ == '__main__':
    unittest.main()