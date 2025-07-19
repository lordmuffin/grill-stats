import json
import logging
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class SessionTracker:
    """
    Service for automatically detecting, tracking, and managing grilling sessions
    """

    def __init__(self, session_manager, device_manager=None, mock_mode=False):
        """
        Initialize the session tracker

        Args:
            session_manager: GrillingSession model instance
            device_manager: Device manager for fetching device data
            mock_mode: Whether to use mock data for testing
        """
        self.session_manager = session_manager
        self.device_manager = device_manager
        self.mock_mode = mock_mode

        # Session detection parameters
        self.TEMP_RISE_THRESHOLD = 20.0  # °F rise above ambient
        self.START_TIME_WINDOW = 30  # minutes to detect start
        self.END_TIME_WINDOW = 60  # minutes of stable temp to detect end
        self.MIN_SESSION_DURATION = 30  # minimum minutes to qualify as session
        self.STABLE_TEMP_VARIANCE = 10.0  # °F variance for "stable" temperature

        # Temperature data buffers for each device (rolling windows)
        self.device_temp_buffers = defaultdict(lambda: deque(maxlen=60))  # 60 readings
        self.device_ambient_temps = {}  # Ambient temperature for each device
        self.active_session_devices = set()  # Devices currently in sessions

        # Session state tracking
        self.potential_starts = {}  # Device -> timestamp of potential start
        self.potential_ends = {}  # Device -> timestamp of potential end

        logger.info("SessionTracker initialized", extra={"mock_mode": mock_mode})

    def process_temperature_reading(
        self,
        device_id: str,
        temperature: float,
        timestamp: datetime = None,
        user_id: int = None,
    ):
        """
        Process a new temperature reading and check for session events

        Args:
            device_id: Device identifier
            temperature: Temperature reading in Fahrenheit
            timestamp: Reading timestamp (defaults to now)
            user_id: User ID associated with device
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Add to temperature buffer
        reading = {
            "temperature": temperature,
            "timestamp": timestamp,
            "user_id": user_id,
        }
        self.device_temp_buffers[device_id].append(reading)

        # Update ambient temperature if this is the first reading or device is idle
        if device_id not in self.device_ambient_temps or device_id not in self.active_session_devices:
            self._update_ambient_temperature(device_id)

        # Check for session start
        if device_id not in self.active_session_devices:
            self._check_session_start(device_id, user_id)

        # Check for session end
        if device_id in self.active_session_devices:
            self._check_session_end(device_id)

        # Update active session statistics
        self._update_active_session_stats(device_id, temperature)

    def _update_ambient_temperature(self, device_id: str):
        """Update the ambient temperature baseline for a device"""
        buffer = self.device_temp_buffers[device_id]
        if len(buffer) >= 5:  # Need at least 5 readings
            # Use median of last 10 readings as ambient when device is idle
            recent_temps = [r["temperature"] for r in list(buffer)[-10:]]
            self.device_ambient_temps[device_id] = statistics.median(recent_temps)

    def _check_session_start(self, device_id: str, user_id: int):
        """Check if a grilling session should start for this device"""
        buffer = self.device_temp_buffers[device_id]

        if len(buffer) < 10:  # Need sufficient data
            return

        ambient_temp = self.device_ambient_temps.get(device_id, 70.0)
        current_temp = buffer[-1]["temperature"]

        # Check if temperature has risen significantly
        if current_temp > ambient_temp + self.TEMP_RISE_THRESHOLD:

            # Check if this is a sustained rise over the time window
            start_window = datetime.utcnow() - timedelta(minutes=self.START_TIME_WINDOW)
            recent_readings = [r for r in buffer if r["timestamp"] >= start_window]

            if len(recent_readings) >= 5:
                # Calculate temperature trend
                temps = [r["temperature"] for r in recent_readings]
                temp_increase = max(temps) - min(temps)

                if temp_increase >= self.TEMP_RISE_THRESHOLD:
                    # Mark as potential start
                    if device_id not in self.potential_starts:
                        self.potential_starts[device_id] = recent_readings[0]["timestamp"]
                        logger.info(f"Potential session start detected for device {device_id}")

                    # Confirm start if sustained for enough time
                    time_since_potential = datetime.utcnow() - self.potential_starts[device_id]
                    if time_since_potential >= timedelta(minutes=10):
                        self._start_session(device_id, self.potential_starts[device_id], user_id)
        else:
            # Reset potential start if temperature drops
            self.potential_starts.pop(device_id, None)

    def _check_session_end(self, device_id: str):
        """Check if a grilling session should end for this device"""
        buffer = self.device_temp_buffers[device_id]

        if len(buffer) < 10:
            return

        # Check if temperature has been stable/declining for end window
        end_window = datetime.utcnow() - timedelta(minutes=self.END_TIME_WINDOW)
        recent_readings = [r for r in buffer if r["timestamp"] >= end_window]

        if len(recent_readings) >= 20:  # Need sufficient recent data
            temps = [r["temperature"] for r in recent_readings]

            # Check for stable temperature (low variance)
            temp_variance = max(temps) - min(temps)

            # Check for declining trend
            mid_point = len(temps) // 2
            first_half_avg = statistics.mean(temps[:mid_point])
            second_half_avg = statistics.mean(temps[mid_point:])
            temp_decline = first_half_avg - second_half_avg

            # Conditions for session end:
            # 1. Temperature is stable (low variance) OR
            # 2. Temperature is declining significantly
            if temp_variance <= self.STABLE_TEMP_VARIANCE or temp_decline >= 20.0:

                if device_id not in self.potential_ends:
                    self.potential_ends[device_id] = datetime.utcnow()
                    logger.info(f"Potential session end detected for device {device_id}")

                # Confirm end if sustained
                time_since_potential = datetime.utcnow() - self.potential_ends[device_id]
                if time_since_potential >= timedelta(minutes=20):
                    self._end_session(device_id)
            else:
                # Reset potential end
                self.potential_ends.pop(device_id, None)

    def _start_session(self, device_id: str, start_time: datetime, user_id: int):
        """Start a new grilling session"""
        try:
            # Create new session
            session = self.session_manager.create_session(
                user_id=user_id,
                start_time=start_time,
                devices=[device_id],
                session_type=self._detect_session_type(device_id),
            )

            # Track active session
            self.active_session_devices.add(device_id)

            # Clear potential start tracking
            self.potential_starts.pop(device_id, None)

            logger.info(f"Session started for device {device_id}, session_id: {session.id}")

            return session

        except Exception as e:
            logger.error(f"Failed to start session for device {device_id}: {e}")
            return None

    def _end_session(self, device_id: str):
        """End the active grilling session for a device"""
        try:
            # Find active session for this device
            active_sessions = self.session_manager.get_active_sessions()

            for session in active_sessions:
                device_list = session.get_device_list()
                if device_id in device_list:

                    # Check minimum duration
                    duration = session.calculate_duration()
                    if duration >= self.MIN_SESSION_DURATION:

                        # End the session
                        ended_session = self.session_manager.end_session(session.id)

                        # Generate name if not set
                        if not ended_session.name:
                            name = self.session_manager.generate_session_name(ended_session)
                            self.session_manager.update_session(session.id, name=name)

                        logger.info(
                            f"Session ended for device {device_id}, session_id: {session.id}, duration: {duration} minutes"
                        )

                    else:
                        # Cancel short sessions
                        self.session_manager.cancel_session(session.id)
                        logger.info(f"Session cancelled for device {device_id} (too short: {duration} minutes)")

                    break

            # Remove from active tracking
            self.active_session_devices.discard(device_id)
            self.potential_ends.pop(device_id, None)

            # Update ambient temperature for next session
            self._update_ambient_temperature(device_id)

        except Exception as e:
            logger.error(f"Failed to end session for device {device_id}: {e}")

    def _update_active_session_stats(self, device_id: str, temperature: float):
        """Update statistics for active session"""
        try:
            active_sessions = self.session_manager.get_active_sessions()

            for session in active_sessions:
                device_list = session.get_device_list()
                if device_id in device_list:
                    self.session_manager.update_session_stats(session.id, [temperature])
                    break

        except Exception as e:
            logger.error(f"Failed to update session stats for device {device_id}: {e}")

    def _detect_session_type(self, device_id: str) -> str:
        """Detect the type of cooking session based on temperature patterns"""
        buffer = self.device_temp_buffers[device_id]

        if len(buffer) < 5:
            return "cooking"

        # Analyze recent temperature data
        recent_temps = [r["temperature"] for r in list(buffer)[-10:]]
        max_temp = max(recent_temps)
        avg_temp = statistics.mean(recent_temps)

        # Classify based on temperature ranges
        if max_temp >= 400:
            return "grilling"
        elif max_temp >= 300:
            return "roasting"
        elif avg_temp <= 275 and max_temp <= 300:
            return "smoking"
        else:
            return "cooking"

    def force_start_session(self, device_id: str, user_id: int, session_type: str = None) -> Optional[Any]:
        """Manually start a session for a device"""
        try:
            session = self.session_manager.create_session(
                user_id=user_id,
                devices=[device_id],
                session_type=session_type or "manual",
            )

            self.active_session_devices.add(device_id)
            logger.info(f"Manual session started for device {device_id}")

            return session

        except Exception as e:
            logger.error(f"Failed to manually start session for device {device_id}: {e}")
            return None

    def force_end_session(self, device_id: str) -> bool:
        """Manually end a session for a device"""
        try:
            self._end_session(device_id)
            return True
        except Exception as e:
            logger.error(f"Failed to manually end session for device {device_id}: {e}")
            return False

    def get_session_status(self, device_id: str) -> Dict:
        """Get current session status for a device"""
        return {
            "device_id": device_id,
            "is_active": device_id in self.active_session_devices,
            "has_potential_start": device_id in self.potential_starts,
            "has_potential_end": device_id in self.potential_ends,
            "ambient_temp": self.device_ambient_temps.get(device_id),
            "recent_readings": len(self.device_temp_buffers[device_id]),
            "buffer_status": {
                "size": len(self.device_temp_buffers[device_id]),
                "latest_temp": (
                    self.device_temp_buffers[device_id][-1]["temperature"] if self.device_temp_buffers[device_id] else None
                ),
                "latest_time": (
                    self.device_temp_buffers[device_id][-1]["timestamp"].isoformat()
                    if self.device_temp_buffers[device_id]
                    else None
                ),
            },
        }

    def cleanup_inactive_devices(self, hours_inactive: int = 24):
        """Clean up tracking data for devices that haven't reported in hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_inactive)

        devices_to_remove = []
        for device_id, buffer in self.device_temp_buffers.items():
            if buffer and buffer[-1]["timestamp"] < cutoff_time:
                devices_to_remove.append(device_id)

        for device_id in devices_to_remove:
            # End any active sessions for inactive devices
            if device_id in self.active_session_devices:
                self._end_session(device_id)

            # Clear tracking data
            del self.device_temp_buffers[device_id]
            self.device_ambient_temps.pop(device_id, None)
            self.potential_starts.pop(device_id, None)
            self.potential_ends.pop(device_id, None)

            logger.info(f"Cleaned up inactive device: {device_id}")

        return len(devices_to_remove)

    def get_all_session_statuses(self) -> Dict:
        """Get session status for all tracked devices"""
        return {device_id: self.get_session_status(device_id) for device_id in self.device_temp_buffers.keys()}

    def simulate_temperature_data(self, device_id: str, user_id: int, session_profile: str = "grilling"):
        """
        Simulate temperature data for testing session detection

        Args:
            device_id: Device to simulate
            user_id: User ID
            session_profile: Type of session to simulate ('grilling', 'smoking', 'roasting')
        """
        if not self.mock_mode:
            logger.warning("Simulation attempted but mock mode is disabled")
            return

        logger.info(f"Starting temperature simulation for {device_id} with profile: {session_profile}")

        # Define temperature profiles
        profiles = {
            "grilling": {
                "ambient": 75,
                "target": 425,
                "ramp_time": 15,  # minutes to reach target
                "hold_time": 45,  # minutes at target
                "cool_time": 30,  # minutes to cool down
            },
            "smoking": {
                "ambient": 70,
                "target": 250,
                "ramp_time": 30,
                "hold_time": 240,  # 4 hours
                "cool_time": 60,
            },
            "roasting": {
                "ambient": 72,
                "target": 350,
                "ramp_time": 20,
                "hold_time": 90,
                "cool_time": 45,
            },
        }

        profile = profiles.get(session_profile, profiles["grilling"])

        # Simulate temperature readings over time
        start_time = datetime.utcnow()
        current_time = start_time

        # Phase 1: Ambient temperature
        for i in range(5):
            temp = profile["ambient"] + (i * 2)  # Slight rise
            self.process_temperature_reading(device_id, temp, current_time, user_id)
            current_time += timedelta(minutes=2)

        # Phase 2: Ramp up
        ramp_steps = profile["ramp_time"] // 2
        temp_step = (profile["target"] - profile["ambient"]) / ramp_steps

        for i in range(ramp_steps):
            temp = profile["ambient"] + (temp_step * (i + 1))
            temp += (i % 3 - 1) * 5  # Add some variance
            self.process_temperature_reading(device_id, temp, current_time, user_id)
            current_time += timedelta(minutes=2)

        # Phase 3: Hold at target
        hold_steps = profile["hold_time"] // 3
        for i in range(hold_steps):
            temp = profile["target"] + ((i % 5 - 2) * 8)  # Variance around target
            self.process_temperature_reading(device_id, temp, current_time, user_id)
            current_time += timedelta(minutes=3)

        # Phase 4: Cool down
        cool_steps = profile["cool_time"] // 5
        temp_step = (profile["target"] - profile["ambient"]) / cool_steps

        for i in range(cool_steps):
            temp = profile["target"] - (temp_step * (i + 1))
            self.process_temperature_reading(device_id, temp, current_time, user_id)
            current_time += timedelta(minutes=5)

        logger.info(f"Temperature simulation completed for {device_id}")

    def health_check(self) -> Dict:
        """Return health status of the session tracker"""
        return {
            "status": "healthy",
            "tracked_devices": len(self.device_temp_buffers),
            "active_sessions": len(self.active_session_devices),
            "potential_starts": len(self.potential_starts),
            "potential_ends": len(self.potential_ends),
            "mock_mode": self.mock_mode,
            "timestamp": datetime.utcnow().isoformat(),
        }
