import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add the services directory to the path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/device-service"))

# Import modules
from main import app
from rfx_gateway_client import GatewaySetupStatus, GatewaySetupStep, RFXGatewayClient, WiFiNetwork


class TestRFXGatewayAPI(unittest.TestCase):
    """Integration tests for the RFX Gateway API endpoints."""

    def setUp(self):
        """Set up the test case."""
        app.config["TESTING"] = True
        self.client = app.test_client()

        # Create a temporary token file
        self.temp_token_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_token_file.write(
            json.dumps(
                {
                    "access_token": "test_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "created_at": 1625097600,
                }
            ).encode()
        )
        self.temp_token_file.close()

        # Patch the rfx_gateway_bp.rfx_gateway_client
        self.rfx_gateway_client_patcher = patch("rfx_gateway_routes.rfx_gateway_bp.rfx_gateway_client")
        self.mock_rfx_client = self.rfx_gateway_client_patcher.start()

        # Patch the rfx_gateway_bp.thermoworks_client
        self.thermoworks_client_patcher = patch("rfx_gateway_routes.rfx_gateway_bp.thermoworks_client")
        self.mock_thermoworks_client = self.thermoworks_client_patcher.start()

        # Set up token for authenticated endpoints
        self.mock_thermoworks_client.token = MagicMock()

    def tearDown(self):
        """Tear down the test case."""
        self.rfx_gateway_client_patcher.stop()
        self.thermoworks_client_patcher.stop()
        os.unlink(self.temp_token_file.name)

    def test_get_gateways(self):
        """Test getting all gateways."""
        # Mock response
        self.mock_thermoworks_client.get_gateways.return_value = [
            {"gateway_id": "001122334455", "name": "Test Gateway 1"},
            {"gateway_id": "AABBCCDDEEFF", "name": "Test Gateway 2"},
        ]

        # Make request
        response = self.client.get("/api/gateways")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["data"]["gateways"]), 2)

    def test_get_gateway(self):
        """Test getting a specific gateway."""
        # Mock response
        self.mock_thermoworks_client.get_gateway_status.return_value = {
            "gateway_id": "001122334455",
            "name": "Test Gateway",
            "online": True,
        }

        # Make request
        response = self.client.get("/api/gateways/001122334455")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["gateway"]["gateway_id"], "001122334455")

    def test_discover_gateways(self):
        """Test discovering gateways."""
        # Mock response
        self.mock_rfx_client.discover_gateways.return_value = [{"id": "001122334455", "name": "RFX Gateway 4455"}]

        # Make request
        response = self.client.post("/api/gateways/discover")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["data"]["gateways"]), 1)

    def test_connect_to_gateway(self):
        """Test connecting to a gateway."""
        # Mock response
        self.mock_rfx_client.connect_to_gateway.return_value = True

        # Make request
        response = self.client.post("/api/gateways/001122334455/connect")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["data"]["connected"])

    def test_scan_wifi_networks(self):
        """Test scanning for Wi-Fi networks."""
        # Mock response
        self.mock_rfx_client.scan_wifi_networks.return_value = [
            WiFiNetwork(ssid="Home WiFi", signal_strength=-50, security_type="WPA2"),
            WiFiNetwork(ssid="Guest Network", signal_strength=-70, security_type="Open"),
        ]

        # Make request
        response = self.client.post("/api/gateways/001122334455/wifi/scan")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["data"]["networks"]), 2)
        self.assertEqual(data["data"]["networks"][0]["ssid"], "Home WiFi")

    def test_configure_wifi(self):
        """Test configuring Wi-Fi."""
        # Mock response
        self.mock_rfx_client.configure_wifi.return_value = True

        # Make request
        response = self.client.post(
            "/api/gateways/001122334455/wifi/configure",
            json={
                "ssid": "Home WiFi",
                "password": "password123",
                "security_type": "WPA2",
            },
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["data"]["configured"])

    def test_link_to_account(self):
        """Test linking to ThermoWorks Cloud account."""
        # Mock response
        self.mock_rfx_client.link_to_thermoworks_account.return_value = True

        # Make request
        response = self.client.post("/api/gateways/001122334455/link")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["data"]["linked"])

    def test_complete_setup(self):
        """Test completing setup."""
        # Mock response
        self.mock_rfx_client.complete_setup.return_value = {
            "gateway_id": "001122334455",
            "step": "complete",
            "progress": 100,
        }

        # Make request
        response = self.client.post("/api/gateways/001122334455/setup/complete")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["data"]["setup_complete"])

    def test_get_setup_status(self):
        """Test getting setup status."""
        # Mock response
        self.mock_rfx_client.get_setup_status.return_value = {
            "gateway_id": "001122334455",
            "step": "wifi_configuration",
            "progress": 50,
        }

        # Make request
        response = self.client.get("/api/gateways/001122334455/setup/status")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["setup_status"]["step"], "wifi_configuration")

    def test_cancel_setup(self):
        """Test cancelling setup."""
        # Mock response
        self.mock_rfx_client.cancel_setup.return_value = None

        # Make request
        response = self.client.post("/api/gateways/001122334455/setup/cancel")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["data"]["cancelled"])


if __name__ == "__main__":
    unittest.main()
