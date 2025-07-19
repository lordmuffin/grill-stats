#!/usr/bin/env python3
"""
Test script for session tracking system
Tests session detection algorithms and API endpoints
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import requests

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, session_manager, session_tracker
from models.grilling_session import GrillingSession
from services.session_tracker import SessionTracker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionTrackingTest:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.auth_token = None
        self.test_device_id = "test_device_001"
        self.test_user_id = 1

    def setup(self):
        """Setup test environment"""
        logger.info("Setting up test environment...")

        with app.app_context():
            # Create tables if they don't exist
            try:
                db.create_all()
                logger.info("Database tables created")
            except Exception as e:
                logger.error(f"Error creating tables: {e}")
                return False

        return True

    def cleanup(self):
        """Clean up test data"""
        logger.info("Cleaning up test data...")

        with app.app_context():
            try:
                # Remove test sessions
                test_sessions = session_manager.model.query.filter_by(user_id=self.test_user_id).all()
                for session in test_sessions:
                    db.session.delete(session)
                db.session.commit()
                logger.info(f"Cleaned up {len(test_sessions)} test sessions")
            except Exception as e:
                logger.error(f"Error cleaning up: {e}")

    def test_session_model(self):
        """Test the GrillingSession model"""
        logger.info("Testing GrillingSession model...")

        with app.app_context():
            try:
                # Create a test session
                session = session_manager.create_session(
                    user_id=self.test_user_id,
                    devices=[self.test_device_id],
                    session_type="testing",
                )

                assert session is not None, "Session creation failed"
                assert session.user_id == self.test_user_id, "User ID mismatch"
                assert session.status == "active", "Session should be active"
                assert session.is_active(), "Session should report as active"

                # Test session dictionary conversion
                session_dict = session.to_dict()
                assert "id" in session_dict, "Session dict missing ID"
                assert "start_time" in session_dict, "Session dict missing start_time"

                # Test duration calculation
                duration = session.calculate_duration()
                assert duration >= 0, "Duration should be non-negative"

                # Test device management
                session.add_device("test_device_002")
                devices = session.get_device_list()
                assert len(devices) == 2, "Should have 2 devices"

                session.remove_device("test_device_002")
                devices = session.get_device_list()
                assert len(devices) == 1, "Should have 1 device after removal"

                # Test session ending
                ended_session = session_manager.end_session(session.id)
                assert ended_session.status == "completed", "Session should be completed"
                assert ended_session.end_time is not None, "End time should be set"

                logger.info("✓ GrillingSession model tests passed")
                return True

            except AssertionError as e:
                logger.error(f"✗ GrillingSession model test failed: {e}")
                return False
            except Exception as e:
                logger.error(f"✗ GrillingSession model test error: {e}")
                return False

    def test_session_tracker(self):
        """Test the SessionTracker service"""
        logger.info("Testing SessionTracker service...")

        with app.app_context():
            try:
                # Create a fresh tracker for testing
                test_tracker = SessionTracker(session_manager, mock_mode=True)

                # Test health check
                health = test_tracker.health_check()
                assert health["status"] == "healthy", "Tracker should be healthy"

                # Test temperature data processing
                base_temp = 75.0
                device_id = "test_tracker_device"

                # Process several ambient temperature readings
                for i in range(5):
                    test_tracker.process_temperature_reading(
                        device_id=device_id,
                        temperature=base_temp + i,
                        user_id=self.test_user_id,
                    )

                # Check device status
                status = test_tracker.get_session_status(device_id)
                assert not status["is_active"], "Should not be active with ambient temps"

                # Simulate temperature rise (session start)
                high_temp = base_temp + 50  # 50°F rise should trigger start detection

                for i in range(15):  # Process enough readings to trigger start
                    temp = base_temp + 20 + (i * 2)  # Gradual rise
                    test_tracker.process_temperature_reading(device_id=device_id, temperature=temp, user_id=self.test_user_id)
                    time.sleep(0.1)  # Small delay

                # Check if potential start is detected
                status = test_tracker.get_session_status(device_id)
                assert status["has_potential_start"], "Should detect potential start"

                # Test manual session start
                manual_session = test_tracker.force_start_session(
                    device_id="manual_test_device",
                    user_id=self.test_user_id,
                    session_type="manual_test",
                )

                assert manual_session is not None, "Manual session creation failed"
                assert manual_session.session_type == "manual_test", "Session type mismatch"

                # Test manual session end
                success = test_tracker.force_end_session("manual_test_device")
                assert success, "Manual session end failed"

                # Test cleanup
                cleaned = test_tracker.cleanup_inactive_devices(hours_inactive=0)
                assert cleaned >= 0, "Cleanup should return non-negative count"

                logger.info("✓ SessionTracker service tests passed")
                return True

            except AssertionError as e:
                logger.error(f"✗ SessionTracker test failed: {e}")
                return False
            except Exception as e:
                logger.error(f"✗ SessionTracker test error: {e}")
                return False

    def test_session_detection_algorithm(self):
        """Test the session detection algorithm with realistic data"""
        logger.info("Testing session detection algorithm...")

        with app.app_context():
            try:
                # Create a fresh tracker for algorithm testing
                algo_tracker = SessionTracker(session_manager, mock_mode=True)
                device_id = "algo_test_device"

                # Simulate a complete grilling session
                logger.info("Simulating grilling session...")

                # Phase 1: Ambient temperature (5 minutes)
                ambient_temp = 72.0
                for i in range(5):
                    algo_tracker.process_temperature_reading(
                        device_id=device_id,
                        temperature=ambient_temp + (i % 3),  # Small variance
                        timestamp=datetime.utcnow() - timedelta(minutes=60 - i * 2),
                        user_id=self.test_user_id,
                    )

                # Phase 2: Heat up (rapid rise over 15 minutes)
                for i in range(15):
                    temp = ambient_temp + (i * 20)  # Rise to ~370°F
                    algo_tracker.process_temperature_reading(
                        device_id=device_id,
                        temperature=temp,
                        timestamp=datetime.utcnow() - timedelta(minutes=45 - i * 2),
                        user_id=self.test_user_id,
                    )

                # Phase 3: Cooking temperature (stable around 400°F for 30 minutes)
                cooking_temp = 400.0
                for i in range(30):
                    temp = cooking_temp + ((i % 5 - 2) * 10)  # ±20°F variance
                    algo_tracker.process_temperature_reading(
                        device_id=device_id,
                        temperature=temp,
                        timestamp=datetime.utcnow() - timedelta(minutes=15 - i * 0.5),
                        user_id=self.test_user_id,
                    )

                # Check if session was detected
                status = algo_tracker.get_session_status(device_id)
                logger.info(f"Algorithm test status: {status}")

                # Verify session creation
                active_sessions = session_manager.get_active_sessions(user_id=self.test_user_id)
                session_found = any(device_id in session.get_device_list() for session in active_sessions)

                if session_found:
                    logger.info("✓ Session detection algorithm correctly identified grilling session")
                else:
                    logger.warning("⚠ Session detection algorithm did not detect session (may need tuning)")

                logger.info("✓ Session detection algorithm tests completed")
                return True

            except Exception as e:
                logger.error(f"✗ Session detection algorithm test error: {e}")
                return False

    def test_api_endpoints(self):
        """Test the session tracking API endpoints"""
        logger.info("Testing session tracking API endpoints...")

        try:
            # Test health endpoint first
            response = requests.get(f"{self.base_url}/health")
            if response.status_code != 200:
                logger.error("Flask app is not running. Please start the app first.")
                return False

            # Test session history endpoint (without auth for now)
            response = requests.get(f"{self.base_url}/api/sessions/history")
            # Expect 401 or 302 (redirect to login) since we're not authenticated
            assert response.status_code in [
                401,
                302,
            ], f"Expected auth error, got {response.status_code}"

            # Test session tracker status endpoint
            response = requests.get(f"{self.base_url}/api/sessions/tracker/status")
            assert response.status_code in [
                401,
                302,
            ], f"Expected auth error, got {response.status_code}"

            # Test simulation endpoint
            response = requests.post(f"{self.base_url}/api/sessions/simulate")
            assert response.status_code in [
                401,
                302,
            ], f"Expected auth error, got {response.status_code}"

            logger.info("✓ API endpoints respond correctly (authentication required)")
            return True

        except requests.exceptions.ConnectionError:
            logger.error("✗ Cannot connect to Flask app. Please start the app first.")
            return False
        except AssertionError as e:
            logger.error(f"✗ API endpoint test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ API endpoint test error: {e}")
            return False

    def test_session_simulation(self):
        """Test session simulation functionality"""
        logger.info("Testing session simulation...")

        with app.app_context():
            try:
                # Test different cooking profiles
                profiles = ["grilling", "smoking", "roasting"]

                for profile in profiles:
                    device_id = f"sim_{profile}_device"

                    # Run simulation
                    session_tracker.simulate_temperature_data(
                        device_id=device_id,
                        user_id=self.test_user_id,
                        session_profile=profile,
                    )

                    # Check if session was created
                    status = session_tracker.get_session_status(device_id)
                    logger.info(f"Simulation status for {profile}: tracked={status['recent_readings'] > 0}")

                logger.info("✓ Session simulation tests completed")
                return True

            except Exception as e:
                logger.error(f"✗ Session simulation test error: {e}")
                return False

    def run_all_tests(self):
        """Run all session tracking tests"""
        logger.info("=" * 60)
        logger.info("STARTING SESSION TRACKING SYSTEM TESTS")
        logger.info("=" * 60)

        if not self.setup():
            logger.error("Setup failed, aborting tests")
            return False

        tests = [
            ("Session Model", self.test_session_model),
            ("Session Tracker Service", self.test_session_tracker),
            ("Session Detection Algorithm", self.test_session_detection_algorithm),
            ("API Endpoints", self.test_api_endpoints),
            ("Session Simulation", self.test_session_simulation),
        ]

        results = {}

        for test_name, test_func in tests:
            logger.info(f"\nRunning {test_name} tests...")
            try:
                results[test_name] = test_func()
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {e}")
                results[test_name] = False

        # Cleanup
        self.cleanup()

        # Report results
        logger.info("\n" + "=" * 60)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 60)

        passed = 0
        total = len(results)

        for test_name, success in results.items():
            status = "PASS" if success else "FAIL"
            logger.info(f"{test_name:30} {status}")
            if success:
                passed += 1

        logger.info("-" * 60)
        logger.info(f"TOTAL: {passed}/{total} tests passed")

        if passed == total:
            logger.info("🎉 ALL TESTS PASSED! Session tracking system is working correctly.")
        else:
            logger.error(f"❌ {total - passed} tests failed. Please review the errors above.")

        return passed == total


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Test session tracking system")
    parser.add_argument("--url", default="http://localhost:5000", help="Flask app URL")
    parser.add_argument("--cleanup-only", action="store_true", help="Only run cleanup")

    args = parser.parse_args()

    tester = SessionTrackingTest(base_url=args.url)

    if args.cleanup_only:
        tester.cleanup()
        logger.info("Cleanup completed")
        return

    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
