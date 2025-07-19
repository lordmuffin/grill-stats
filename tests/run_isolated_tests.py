#!/usr/bin/env python3
"""
Run isolated database tests.

This script runs all tests that have been modified to use isolated database operations.
"""

import os
import sys

import pytest

# Add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Get the path to tests directory
tests_dir = os.path.join(project_root, "tests")


def main():
    """Run all isolated tests."""
    # Find all test files that have been modified for isolated database operations
    isolated_test_files = []

    # Unit tests with isolation
    unit_test_dir = os.path.join(tests_dir, "unit")
    for root, _, files in os.walk(unit_test_dir):
        for file in files:
            if file.startswith("test_") and file.endswith("_isolated.py"):
                isolated_test_files.append(os.path.join(root, file))

    # Integration tests with isolation
    integration_test_dir = os.path.join(tests_dir, "integration")
    if os.path.exists(integration_test_dir):
        for root, _, files in os.walk(integration_test_dir):
            for file in files:
                if file.startswith("test_") and file.endswith("_isolated.py"):
                    isolated_test_files.append(os.path.join(root, file))

    # If no isolated tests found, run a specific isolated test
    if not isolated_test_files:
        # Default to auth isolated test if no other isolated tests found
        auth_isolated_test = os.path.join(tests_dir, "unit", "auth", "test_auth_isolated.py")
        if os.path.exists(auth_isolated_test):
            isolated_test_files.append(auth_isolated_test)

    # Run the tests
    if isolated_test_files:
        print(f"Running {len(isolated_test_files)} isolated tests:")
        for test_file in isolated_test_files:
            print(f"- {os.path.relpath(test_file, project_root)}")

        # Run tests using pytest
        result = pytest.main(["-v"] + isolated_test_files)
        return result
    else:
        print("No isolated tests found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
