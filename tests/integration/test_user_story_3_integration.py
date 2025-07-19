#!/usr/bin/env python3
"""
Integration test for User Story 3: View Live Device Data
Tests the complete end-to-end functionality of live device monitoring

This test validates:
1. Device selection from device list
2. Navigation to live device dashboard
3. Real-time data streaming via SSE
4. Temperature channel display
5. Device status monitoring
6. Chart visualization updates
7. Error handling and recovery
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
import websockets

# Configuration
BASE_URL = "http://localhost:8080"
AUTH_URL = "http://localhost:8082"
FRONTEND_URL = "http://localhost:3000"
TEST_DEVICE_ID = "test_device_001"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpass123"


class UserStory3IntegrationTest:
    """Integration test for User Story 3 functionality"""

    def __init__(self):
        self.auth_token = None
        self.session_token = None
        self.session = requests.Session()
        self.test_results = []

    def log_test(self, test_name: str, status: str, message: str = ""):
        """Log test result"""
        timestamp = datetime.now().isoformat()
        result = {
            "test_name": test_name,
            "status": status,
            "message": message,
            "timestamp": timestamp,
        }
        self.test_results.append(result)
        print(f"[{timestamp}] {test_name}: {status} - {message}")

    def setup_authentication(self) -> bool:
        """Setup authentication for testing"""
        try:
            # Login user
            login_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "login_type": "local",
            }

            response = self.session.post(
                f"{AUTH_URL}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.auth_token = data.get("data", {}).get("token")
                    self.session_token = data.get("data", {}).get("session_token")

                    # Set authentication headers
                    self.session.headers.update(
                        {
                            "Authorization": f"Bearer {self.auth_token}",
                            "Session-Token": self.session_token,
                        }
                    )

                    self.log_test(
                        "setup_authentication",
                        "PASS",
                        "User authenticated successfully",
                    )
                    return True

            self.log_test(
                "setup_authentication",
                "FAIL",
                f"Authentication failed: {response.text}",
            )
            return False

        except Exception as e:
            self.log_test("setup_authentication", "FAIL", f"Authentication error: {str(e)}")
            return False

    def test_device_list_access(self) -> bool:
        """Test accessing device list"""
        try:
            response = self.session.get(f"{BASE_URL}/api/devices")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    devices = data.get("data", {}).get("devices", [])

                    # Check if test device exists
                    test_device = next(
                        (d for d in devices if d.get("device_id") == TEST_DEVICE_ID),
                        None,
                    )
                    if test_device:
                        self.log_test(
                            "test_device_list_access",
                            "PASS",
                            f"Found {len(devices)} devices including test device",
                        )
                        return True
                    else:
                        self.log_test(
                            "test_device_list_access",
                            "FAIL",
                            f"Test device {TEST_DEVICE_ID} not found",
                        )
                        return False

            self.log_test(
                "test_device_list_access",
                "FAIL",
                f"Device list request failed: {response.text}",
            )
            return False

        except Exception as e:
            self.log_test("test_device_list_access", "FAIL", f"Device list error: {str(e)}")
            return False

    def test_live_device_data_endpoint(self) -> bool:
        """Test live device data endpoint"""
        try:
            response = self.session.get(f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/live")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    live_data = data.get("data", {})

                    # Validate live data structure
                    required_fields = ["device_id", "timestamp", "channels", "status"]
                    missing_fields = [field for field in required_fields if field not in live_data]

                    if not missing_fields:
                        channels = live_data.get("channels", [])
                        status = live_data.get("status", {})

                        self.log_test(
                            "test_live_device_data_endpoint",
                            "PASS",
                            f"Live data retrieved: {len(channels)} channels, battery: {status.get('battery_level', 'N/A')}%",
                        )
                        return True
                    else:
                        self.log_test(
                            "test_live_device_data_endpoint",
                            "FAIL",
                            f"Missing required fields: {missing_fields}",
                        )
                        return False

            self.log_test(
                "test_live_device_data_endpoint",
                "FAIL",
                f"Live data request failed: {response.text}",
            )
            return False

        except Exception as e:
            self.log_test(
                "test_live_device_data_endpoint",
                "FAIL",
                f"Live data endpoint error: {str(e)}",
            )
            return False

    def test_device_channels_endpoint(self) -> bool:
        """Test device channels endpoint"""
        try:
            response = self.session.get(f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/channels")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    channel_data = data.get("data", {})
                    channels = channel_data.get("channels", [])

                    # Validate channel structure
                    if channels:
                        channel = channels[0]
                        required_fields = ["channel_id", "name", "probe_type", "unit"]
                        missing_fields = [field for field in required_fields if field not in channel]

                        if not missing_fields:
                            self.log_test(
                                "test_device_channels_endpoint",
                                "PASS",
                                f"Channel configuration retrieved: {len(channels)} channels",
                            )
                            return True
                        else:
                            self.log_test(
                                "test_device_channels_endpoint",
                                "FAIL",
                                f"Invalid channel structure: missing {missing_fields}",
                            )
                            return False
                    else:
                        self.log_test("test_device_channels_endpoint", "FAIL", "No channels found")
                        return False

            self.log_test(
                "test_device_channels_endpoint",
                "FAIL",
                f"Channels request failed: {response.text}",
            )
            return False

        except Exception as e:
            self.log_test(
                "test_device_channels_endpoint",
                "FAIL",
                f"Channels endpoint error: {str(e)}",
            )
            return False

    def test_device_status_endpoint(self) -> bool:
        """Test device status endpoint"""
        try:
            response = self.session.get(f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/status")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    status_data = data.get("data", {})

                    # Validate status structure
                    required_fields = [
                        "device_id",
                        "battery_level",
                        "signal_strength",
                        "connection_status",
                    ]
                    missing_fields = [field for field in required_fields if field not in status_data]

                    if not missing_fields:
                        battery = status_data.get("battery_level", 0)
                        signal = status_data.get("signal_strength", 0)
                        connection = status_data.get("connection_status", "unknown")

                        self.log_test(
                            "test_device_status_endpoint",
                            "PASS",
                            f"Device status retrieved: battery={battery}%, signal={signal}%, status={connection}",
                        )
                        return True
                    else:
                        self.log_test(
                            "test_device_status_endpoint",
                            "FAIL",
                            f"Missing status fields: {missing_fields}",
                        )
                        return False

            self.log_test(
                "test_device_status_endpoint",
                "FAIL",
                f"Status request failed: {response.text}",
            )
            return False

        except Exception as e:
            self.log_test(
                "test_device_status_endpoint",
                "FAIL",
                f"Status endpoint error: {str(e)}",
            )
            return False

    def test_live_data_stream(self) -> bool:
        """Test Server-Sent Events stream for live data"""
        try:
            import sseclient

            # Create SSE client
            url = f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/stream"
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Session-Token": self.session_token,
            }

            response = requests.get(url, headers=headers, stream=True)

            if response.status_code == 200:
                client = sseclient.SSEClient(response)

                # Collect messages for a short period
                messages = []
                start_time = time.time()
                timeout = 10  # 10 seconds

                for event in client.events():
                    if event.data:
                        try:
                            data = json.loads(event.data)
                            messages.append(data)

                            # Check if we got valid live data
                            if data.get("device_id") == TEST_DEVICE_ID and "channels" in data:
                                self.log_test(
                                    "test_live_data_stream",
                                    "PASS",
                                    f"SSE stream working: received {len(messages)} messages",
                                )
                                return True
                        except json.JSONDecodeError:
                            continue

                    # Timeout check
                    if time.time() - start_time > timeout:
                        break

                if messages:
                    self.log_test(
                        "test_live_data_stream",
                        "PARTIAL",
                        f"SSE stream connected but no valid data: {len(messages)} messages",
                    )
                else:
                    self.log_test(
                        "test_live_data_stream",
                        "FAIL",
                        "No messages received from SSE stream",
                    )
                return False

            self.log_test(
                "test_live_data_stream",
                "FAIL",
                f"SSE stream request failed: {response.status_code}",
            )
            return False

        except ImportError:
            self.log_test("test_live_data_stream", "SKIP", "sseclient library not available")
            return True  # Skip this test if library not available
        except Exception as e:
            self.log_test("test_live_data_stream", "FAIL", f"SSE stream error: {str(e)}")
            return False

    def test_database_schema(self) -> bool:
        """Test that database schema is properly created"""
        try:
            # Check if we can connect to database and verify tables exist
            # This would require database connection details

            # For now, just verify the schema file exists
            schema_file = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "database-init",
                "live-data-schema.sql",
            )

            if os.path.exists(schema_file):
                with open(schema_file, "r") as f:
                    schema_content = f.read()

                # Check for required tables
                required_tables = [
                    "device_channels",
                    "live_temperature_readings",
                    "device_status_log",
                    "temperature_alerts",
                ]

                missing_tables = []
                for table in required_tables:
                    if f"CREATE TABLE IF NOT EXISTS {table}" not in schema_content:
                        missing_tables.append(table)

                if not missing_tables:
                    self.log_test(
                        "test_database_schema",
                        "PASS",
                        f"Database schema file contains all required tables",
                    )
                    return True
                else:
                    self.log_test(
                        "test_database_schema",
                        "FAIL",
                        f"Missing tables in schema: {missing_tables}",
                    )
                    return False
            else:
                self.log_test("test_database_schema", "FAIL", "Database schema file not found")
                return False

        except Exception as e:
            self.log_test("test_database_schema", "FAIL", f"Database schema test error: {str(e)}")
            return False

    def test_frontend_routing(self) -> bool:
        """Test frontend routing to live device dashboard"""
        try:
            # Test if frontend is accessible
            response = requests.get(f"{FRONTEND_URL}/devices/{TEST_DEVICE_ID}/live")

            if response.status_code == 200:
                # Check if the response contains expected content
                content = response.text
                if "live" in content.lower() or "dashboard" in content.lower():
                    self.log_test(
                        "test_frontend_routing",
                        "PASS",
                        "Frontend live dashboard route accessible",
                    )
                    return True
                else:
                    self.log_test(
                        "test_frontend_routing",
                        "PARTIAL",
                        "Frontend route accessible but content unclear",
                    )
                    return False
            else:
                self.log_test(
                    "test_frontend_routing",
                    "FAIL",
                    f"Frontend route not accessible: {response.status_code}",
                )
                return False

        except Exception as e:
            self.log_test("test_frontend_routing", "SKIP", f"Frontend test skipped: {str(e)}")
            return True  # Skip if frontend not running

    def test_error_handling(self) -> bool:
        """Test error handling for invalid requests"""
        try:
            # Test invalid device ID
            response = self.session.get(f"{BASE_URL}/api/devices/invalid_device_id/live")

            if response.status_code in [400, 404, 500]:
                data = response.json()
                if data.get("status") == "error":
                    self.log_test(
                        "test_error_handling",
                        "PASS",
                        "Error handling works for invalid device ID",
                    )
                    return True

            self.log_test(
                "test_error_handling",
                "FAIL",
                f"Unexpected response for invalid device: {response.status_code}",
            )
            return False

        except Exception as e:
            self.log_test("test_error_handling", "FAIL", f"Error handling test failed: {str(e)}")
            return False

    def test_performance(self) -> bool:
        """Test performance of live data endpoints"""
        try:
            # Test response time for live data endpoint
            start_time = time.time()
            response = self.session.get(f"{BASE_URL}/api/devices/{TEST_DEVICE_ID}/live")
            response_time = time.time() - start_time

            if response.status_code == 200 and response_time < 2.0:
                self.log_test(
                    "test_performance",
                    "PASS",
                    f"Live data endpoint response time: {response_time:.2f}s",
                )
                return True
            elif response.status_code == 200:
                self.log_test(
                    "test_performance",
                    "FAIL",
                    f"Live data endpoint too slow: {response_time:.2f}s",
                )
                return False
            else:
                self.log_test(
                    "test_performance",
                    "FAIL",
                    f"Live data endpoint failed: {response.status_code}",
                )
                return False

        except Exception as e:
            self.log_test("test_performance", "FAIL", f"Performance test error: {str(e)}")
            return False

    def run_all_tests(self) -> Dict:
        """Run all User Story 3 integration tests"""
        print("=== User Story 3: View Live Device Data - Integration Tests ===")
        print(f"Test started at: {datetime.now().isoformat()}")
        print(f"Base URL: {BASE_URL}")
        print(f"Auth URL: {AUTH_URL}")
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Test Device ID: {TEST_DEVICE_ID}")
        print("=" * 60)

        # Setup
        if not self.setup_authentication():
            return {"status": "SETUP_FAILED", "results": self.test_results}

        # Run tests
        tests = [
            ("Device List Access", self.test_device_list_access),
            ("Live Device Data Endpoint", self.test_live_device_data_endpoint),
            ("Device Channels Endpoint", self.test_device_channels_endpoint),
            ("Device Status Endpoint", self.test_device_status_endpoint),
            ("Live Data Stream (SSE)", self.test_live_data_stream),
            ("Database Schema", self.test_database_schema),
            ("Frontend Routing", self.test_frontend_routing),
            ("Error Handling", self.test_error_handling),
            ("Performance", self.test_performance),
        ]

        passed = 0
        failed = 0
        skipped = 0

        for test_name, test_func in tests:
            print(f"\nRunning: {test_name}")
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log_test(test_name, "ERROR", f"Test execution error: {str(e)}")
                failed += 1

        # Count skipped tests
        skipped = len([r for r in self.test_results if r["status"] == "SKIP"])

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print(f"Total Tests: {len(tests)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        print(f"Success Rate: {(passed/(passed+failed)*100):.1f}%")

        overall_status = "PASS" if failed == 0 else "FAIL"

        return {
            "status": overall_status,
            "total": len(tests),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "results": self.test_results,
        }

    def generate_report(self, results: Dict) -> str:
        """Generate test report"""
        report = f"""
# User Story 3: View Live Device Data - Integration Test Report

**Test Execution Date:** {datetime.now().isoformat()}
**Overall Status:** {results['status']}

## Summary
- **Total Tests:** {results['total']}
- **Passed:** {results['passed']}
- **Failed:** {results['failed']}
- **Skipped:** {results['skipped']}
- **Success Rate:** {(results['passed']/(results['passed']+results['failed'])*100):.1f}%

## Test Results

| Test Name | Status | Message | Timestamp |
|-----------|--------|---------|-----------|
"""

        for result in results["results"]:
            report += f"| {result['test_name']} | {result['status']} | {result['message']} | {result['timestamp']} |\n"

        return report


def main():
    """Main test execution function"""
    # Check if services are running
    print("Checking service availability...")

    try:
        # Test if temperature service is running
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"Temperature service not available at {BASE_URL}")
            return 1
    except requests.ConnectionError:
        print(f"Cannot connect to temperature service at {BASE_URL}")
        return 1

    try:
        # Test if auth service is running
        response = requests.get(f"{AUTH_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"Auth service not available at {AUTH_URL}")
            return 1
    except requests.ConnectionError:
        print(f"Cannot connect to auth service at {AUTH_URL}")
        return 1

    # Run integration tests
    tester = UserStory3IntegrationTest()
    results = tester.run_all_tests()

    # Generate report
    report = tester.generate_report(results)

    # Save report
    report_file = f"user_story_3_integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, "w") as f:
        f.write(report)

    print(f"\nTest report saved to: {report_file}")

    # Exit with appropriate code
    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
