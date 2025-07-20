#!/usr/bin/env python3
"""
Test Runner Script

This script provides a convenient way to run all or specific test files
with proper environment setup and configuration.
"""

import argparse
import os
import subprocess
import sys
from typing import List, Optional


def run_tests(test_files: Optional[List[str]] = None, verbose: bool = False) -> int:
    """
    Run pytest on the specified test files or all test files

    Args:
        test_files: List of test files to run, or None to run all tests
        verbose: Whether to enable verbose output

    Returns:
        Exit code from pytest
    """
    # Set environment variables for testing
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "true"

    # Construct pytest command
    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    # Add coverage if installed
    try:
        import pytest_cov

        cmd.extend(["--cov=.", "--cov-report=term", "--cov-report=html"])
    except ImportError:
        pass

    # Add specific test files if provided
    if test_files:
        cmd.extend(test_files)
    else:
        cmd.append("tests/")

    # Print command to be executed
    print(f"Running: {' '.join(cmd)}")

    # Run pytest and return exit code
    return subprocess.call(cmd)


def main() -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run tests for the device service")
    parser.add_argument("test_files", nargs="*", help="Specific test files to run")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    return run_tests(args.test_files, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
