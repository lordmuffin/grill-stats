#!/usr/bin/env python3
# mypy: ignore-errors
"""
Performance tests for the Device Service

This module contains performance tests for various device-related operations
to ensure the service meets performance requirements under various load conditions.
Tests include:
- Device list retrieval performance
- Device data retrieval performance
- Device operations (add/update/delete) performance
- Concurrent user load tests
"""

import datetime
import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from flask import Flask

# Import from main application
from main import JWT_ALGORITHM, JWT_SECRET, app, device_manager, thermoworks_client

# Set up test constants
TEST_ITERATIONS = 10  # Number of times to run each test
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]  # Number of concurrent users to simulate
PERFORMANCE_THRESHOLDS = {
    "device_list": 500,  # 500ms threshold for device list retrieval
    "device_detail": 200,  # 200ms threshold for device detail retrieval
    "device_register": 300,  # 300ms threshold for device registration
    "device_update": 250,  # 250ms threshold for device update
    "device_delete": 200,  # 200ms threshold for device delete
}


@pytest.fixture
def client():
    """Create a test client"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_token():
    """Create a valid JWT token for testing"""
    payload = {
        "user_id": 1,
        "email": "test@example.com",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture
def mock_devices(count=100):
    """Create a list of mock devices for testing"""
    devices = []
    for i in range(count):
        device_id = f"test_device_{i:03d}"
        device = {
            "device_id": device_id,
            "name": f"Test Device {i}",
            "device_type": "thermoworks",
            "configuration": {
                "model": "ThermoWorks Pro",
                "firmware_version": "1.0.0",
            },
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        devices.append(device)
    return devices


def measure_execution_time(func, *args, **kwargs) -> Tuple[Any, float]:
    """
    Measure the execution time of a function

    Args:
        func: Function to measure
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Tuple of (result, execution_time_ms)
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    execution_time_ms = (end_time - start_time) * 1000.0
    return result, execution_time_ms


def run_timed_test(test_func, iterations=TEST_ITERATIONS, *args, **kwargs) -> Dict[str, Any]:
    """
    Run a test function multiple times and return statistics

    Args:
        test_func: Test function to run
        iterations: Number of iterations to run
        *args: Arguments to pass to the test function
        **kwargs: Keyword arguments to pass to the test function

    Returns:
        Dict with execution time statistics (min, max, avg, median)
    """
    times = []

    for _ in range(iterations):
        _, execution_time = measure_execution_time(test_func, *args, **kwargs)
        times.append(execution_time)

    return {
        "min": min(times),
        "max": max(times),
        "avg": sum(times) / len(times),
        "median": statistics.median(times),
        "p95": sorted(times)[int(len(times) * 0.95)],
        "raw": times,
    }


class TestDeviceListPerformance:
    """Test device list retrieval performance"""

    @patch("main.device_manager")
    def test_get_devices_performance(self, mock_device_manager, client, auth_token, mock_devices) -> None:
        """Test performance of retrieving device list"""
        # Setup mock response
        mock_device_manager.get_devices.return_value = mock_devices

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function
        def test_func():
            return client.get("/api/devices", headers=headers)

        # Run timed test
        stats = run_timed_test(test_func)

        # Print performance statistics
        print(
            f"\nDevice List Performance (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
        )

        # Verify performance meets threshold
        assert (
            stats["p95"] < PERFORMANCE_THRESHOLDS["device_list"]
        ), f"Device list retrieval is too slow: {stats['p95']:.2f}ms > {PERFORMANCE_THRESHOLDS['device_list']}ms threshold"

        # Verify response is correct
        response = test_func()
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert len(data["data"]["devices"]) == len(mock_devices)

    @patch("main.device_manager")
    def test_get_devices_performance_scaling(self, mock_device_manager, client, auth_token) -> None:
        """Test how device list retrieval performance scales with number of devices"""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Test with different numbers of devices
        device_counts = [10, 100, 500, 1000]
        results = {}

        for count in device_counts:
            # Create mock devices
            devices = []
            for i in range(count):
                device_id = f"test_device_{i:03d}"
                device = {
                    "device_id": device_id,
                    "name": f"Test Device {i}",
                    "device_type": "thermoworks",
                    "created_at": "2023-01-01T00:00:00",
                    "updated_at": "2023-01-01T00:00:00",
                }
                devices.append(device)

            # Setup mock
            mock_device_manager.get_devices.return_value = devices

            # Define test function
            def test_func():
                return client.get("/api/devices", headers=headers)

            # Run timed test
            stats = run_timed_test(test_func, iterations=5)  # Fewer iterations for large counts

            # Store results
            results[count] = stats

            # Print statistics
            print(
                f"\nDevice List Performance with {count} devices (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
            )

        # Check that performance scales reasonably (not strictly linear)
        # This is a simple check that p95 time for 1000 devices is less than 10x the time for 100 devices
        assert results[1000]["p95"] < results[100]["p95"] * 10, "Performance does not scale well with number of devices"


class TestDeviceDetailPerformance:
    """Test device detail retrieval performance"""

    @patch("main.device_manager")
    def test_get_device_performance(self, mock_device_manager, client, auth_token) -> None:
        """Test performance of retrieving a single device"""
        # Setup mock response
        device_id = "test_device_001"
        mock_device = {
            "device_id": device_id,
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"model": "ThermoWorks Pro"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        mock_device_manager.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function
        def test_func():
            return client.get(f"/api/devices/{device_id}", headers=headers)

        # Run timed test
        stats = run_timed_test(test_func)

        # Print performance statistics
        print(
            f"\nDevice Detail Performance (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
        )

        # Verify performance meets threshold
        assert (
            stats["p95"] < PERFORMANCE_THRESHOLDS["device_detail"]
        ), f"Device detail retrieval is too slow: {stats['p95']:.2f}ms > {PERFORMANCE_THRESHOLDS['device_detail']}ms threshold"

        # Verify response is correct
        response = test_func()
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["data"]["device"]["device_id"] == device_id


class TestDeviceOperationsPerformance:
    """Test device operations performance (add/update/delete)"""

    @patch("main.device_manager")
    def test_register_device_performance(self, mock_device_manager, client, auth_token) -> None:
        """Test performance of registering a new device"""
        # Setup mock response
        device_id = "test_device_001"
        mock_device = {
            "device_id": device_id,
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"model": "ThermoWorks Pro"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        mock_device_manager.register_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function
        def test_func():
            new_device = {
                "device_id": str(uuid.uuid4()),
                "name": f"Test Device {uuid.uuid4().hex[:8]}",
                "device_type": "thermoworks",
                "configuration": {"model": "ThermoWorks Pro"},
            }
            return client.post(
                "/api/devices",
                headers=headers,
                json=new_device,
                content_type="application/json",
            )

        # Run timed test
        stats = run_timed_test(test_func)

        # Print performance statistics
        print(
            f"\nDevice Registration Performance (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
        )

        # Verify performance meets threshold
        assert (
            stats["p95"] < PERFORMANCE_THRESHOLDS["device_register"]
        ), f"Device registration is too slow: {stats['p95']:.2f}ms > {PERFORMANCE_THRESHOLDS['device_register']}ms threshold"

        # Verify response is correct
        response = test_func()
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["status"] == "success"

    @patch("main.device_manager")
    def test_update_device_performance(self, mock_device_manager, client, auth_token) -> None:
        """Test performance of updating a device"""
        # Setup mock response
        device_id = "test_device_001"
        mock_device = {
            "device_id": device_id,
            "name": "Updated Device",
            "device_type": "thermoworks",
            "configuration": {"model": "ThermoWorks Pro"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        mock_device_manager.update_device.return_value = mock_device
        mock_device_manager.get_device.return_value = mock_device

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function
        def test_func():
            update_data = {
                "name": f"Updated Device {uuid.uuid4().hex[:8]}",
                "configuration": {"model": "ThermoWorks Pro 2.0"},
            }
            return client.put(
                f"/api/devices/{device_id}",
                headers=headers,
                json=update_data,
                content_type="application/json",
            )

        # Run timed test
        stats = run_timed_test(test_func)

        # Print performance statistics
        print(
            f"\nDevice Update Performance (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
        )

        # Verify performance meets threshold
        assert (
            stats["p95"] < PERFORMANCE_THRESHOLDS["device_update"]
        ), f"Device update is too slow: {stats['p95']:.2f}ms > {PERFORMANCE_THRESHOLDS['device_update']}ms threshold"

        # Verify response is correct
        response = test_func()
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    @patch("main.device_manager")
    def test_delete_device_performance(self, mock_device_manager, client, auth_token) -> None:
        """Test performance of deleting a device"""
        # Setup mock response
        device_id = "test_device_001"
        mock_device_manager.delete_device.return_value = True
        mock_device_manager.get_device.return_value = {
            "device_id": device_id,
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"model": "ThermoWorks Pro"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function
        def test_func():
            return client.delete(f"/api/devices/{device_id}", headers=headers)

        # Run timed test
        stats = run_timed_test(test_func)

        # Print performance statistics
        print(
            f"\nDevice Delete Performance (ms): Min={stats['min']:.2f}, Max={stats['max']:.2f}, Avg={stats['avg']:.2f}, P95={stats['p95']:.2f}"
        )

        # Verify performance meets threshold
        assert (
            stats["p95"] < PERFORMANCE_THRESHOLDS["device_delete"]
        ), f"Device deletion is too slow: {stats['p95']:.2f}ms > {PERFORMANCE_THRESHOLDS['device_delete']}ms threshold"

        # Verify response is correct
        response = test_func()
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"


class TestConcurrentLoadPerformance:
    """Test performance under concurrent load"""

    @patch("main.device_manager")
    def test_concurrent_device_list(self, mock_device_manager, client, auth_token, mock_devices) -> None:
        """Test device list performance under concurrent load"""
        # Setup mock response
        mock_device_manager.get_devices.return_value = mock_devices

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define test function for a single request
        def make_request() -> Any:
            response = client.get("/api/devices", headers=headers)
            assert response.status_code == 200
            return response

        # Test with different concurrency levels
        results = {}

        for concurrency in CONCURRENCY_LEVELS:
            # Run concurrent requests
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(make_request) for _ in range(concurrency)]
                responses = [future.result() for future in futures]

            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000.0
            avg_time_ms = total_time_ms / concurrency

            results[concurrency] = {
                "total_time_ms": total_time_ms,
                "avg_time_ms": avg_time_ms,
                "throughput": concurrency / (total_time_ms / 1000.0),
            }

            # Print statistics
            print(f"\nConcurrent Device List Performance with {concurrency} users:")
            print(f"Total Time: {total_time_ms:.2f}ms")
            print(f"Avg Time Per Request: {avg_time_ms:.2f}ms")
            print(f"Throughput: {results[concurrency]['throughput']:.2f} req/sec")

        # Check that throughput scales reasonably
        # Throughput should not decrease dramatically as concurrency increases
        for i in range(1, len(CONCURRENCY_LEVELS) - 1):
            assert (
                results[CONCURRENCY_LEVELS[i]]["throughput"] >= results[CONCURRENCY_LEVELS[i - 1]]["throughput"] * 0.5
            ), f"Throughput drops significantly at concurrency {CONCURRENCY_LEVELS[i]}"

    @patch("main.device_manager")
    def test_mixed_workload_performance(self, mock_device_manager, client, auth_token, mock_devices) -> None:
        """Test performance with a mixed workload of different operations"""
        # Setup mock responses
        mock_device_manager.get_devices.return_value = mock_devices

        device_id = "test_device_001"
        mock_device = {
            "device_id": device_id,
            "name": "Test Device",
            "device_type": "thermoworks",
            "configuration": {"model": "ThermoWorks Pro"},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        mock_device_manager.get_device.return_value = mock_device
        mock_device_manager.register_device.return_value = mock_device
        mock_device_manager.update_device.return_value = mock_device
        mock_device_manager.delete_device.return_value = True

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Define different request types
        def get_devices() -> Any:
            return client.get("/api/devices", headers=headers)

        def get_device() -> Any:
            return client.get(f"/api/devices/{device_id}", headers=headers)

        def register_device() -> Any:
            new_device = {
                "device_id": str(uuid.uuid4()),
                "name": f"Test Device {uuid.uuid4().hex[:8]}",
                "device_type": "thermoworks",
                "configuration": {"model": "ThermoWorks Pro"},
            }
            return client.post(
                "/api/devices",
                headers=headers,
                json=new_device,
                content_type="application/json",
            )

        def update_device() -> Any:
            update_data = {
                "name": f"Updated Device {uuid.uuid4().hex[:8]}",
                "configuration": {"model": "ThermoWorks Pro 2.0"},
            }
            return client.put(
                f"/api/devices/{device_id}",
                headers=headers,
                json=update_data,
                content_type="application/json",
            )

        # Create mixed workload (70% reads, 30% writes)
        workload = []
        for _ in range(70):
            if _ % 2 == 0:
                workload.append(get_devices)
            else:
                workload.append(get_device)

        for _ in range(20):
            workload.append(register_device)

        for _ in range(10):
            workload.append(update_device)

        # Shuffle workload to simulate random access
        import random

        random.shuffle(workload)

        # Run mixed workload with concurrent users
        concurrency = 10  # Use a moderate concurrency level

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(func) for func in workload]
            responses = [future.result() for future in futures]

        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000.0
        avg_time_ms = total_time_ms / len(workload)
        throughput = len(workload) / (total_time_ms / 1000.0)

        # Print statistics
        print(f"\nMixed Workload Performance with {concurrency} concurrent users:")
        print(f"Total Requests: {len(workload)}")
        print(f"Total Time: {total_time_ms:.2f}ms")
        print(f"Avg Time Per Request: {avg_time_ms:.2f}ms")
        print(f"Throughput: {throughput:.2f} req/sec")

        # Check all responses are successful
        for response in responses:
            assert response.status_code in [200, 201], f"Request failed with status {response.status_code}"


def generate_performance_report(report_path: str) -> None:
    """Generate a performance report from test results"""
    # This would be implemented to collect results from tests
    # and generate a comprehensive report with charts and analysis
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
