"""Health check script for temperature service."""

import json
import sys
from datetime import datetime, timedelta

import requests


def check_health(base_url: str = "http://localhost:8080") -> bool:
    """Check service health and return status."""
    try:
        # Check health endpoint
        health_response = requests.get(f"{base_url}/health")
        health_data = health_response.json()

        print("\n🔍 Temperature Service Health Check")
        print("==================================")
        print(f"Status: {health_data['status']}")
        print(f"Timestamp: {health_data['timestamp']}")
        print("\nFeatures:")
        for feature, enabled in health_data.get("features", {}).items():
            status = "✅ Enabled" if enabled else "⚠️ Disabled"
            print(f"  {feature}: {status}")

        print("\nDependencies:")
        for dep, status in health_data.get("dependencies", {}).items():
            status_icon = (
                "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
            )
            print(f"  {dep}: {status_icon} {status}")

        # Test temperature endpoint
        temp_response = requests.get(f"{base_url}/api/temperature/current/test_device")
        temp_data = temp_response.json()

        print("\nAPI Test:")
        if temp_data.get("status") == "success":
            print("  ✅ Temperature API responding")
            print(f"  🌡️  Temperature: {temp_data['data'].get('temperature')}°F")
            print(f"  📡 Data source: {temp_data.get('source', 'unknown')}")
        else:
            print("  ⚠️  Temperature API in degraded mode")

        return health_data["status"] in ["healthy", "degraded"]

    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        return False


if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1)
