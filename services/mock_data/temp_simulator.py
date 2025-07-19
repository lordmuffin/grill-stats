#!/usr/bin/env python3
"""
Enhanced Temperature Simulator for Mock Data Service

This module provides an advanced temperature simulation for mock ThermoWorks devices
that follows realistic cooking profiles and includes events like lid opening.
"""

import logging
import math
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from .cooking_profiles import (
    CookingMethod,
    CookingProfile,
    MeatType,
    TemperaturePhase,
    generate_cooking_event,
    get_ambient_profile_for_cooking_method,
    get_profile_by_name,
)

logger = logging.getLogger(__name__)


class CookingSession:
    """
    Represents an active cooking session with a specific profile.

    Tracks cooking progress, events, and generates realistic temperature changes
    based on the cooking profile and any events that occur.
    """

    def __init__(
        self,
        device_id: str,
        probe_id: str,
        probe_name: str,
        initial_temp: float,
        profile: Optional[CookingProfile] = None,
    ):
        """
        Initialize a new cooking session.

        Args:
            device_id: ThermoWorks device ID
            probe_id: Probe ID
            probe_name: Human-readable probe name (used to guess meat type)
            initial_temp: Starting temperature
            profile: Optional cooking profile (auto-detected from name if None)
        """
        self.device_id = device_id
        self.probe_id = probe_id
        self.probe_name = probe_name
        self.current_temp = initial_temp
        self.start_time = time.time()
        self.last_update_time = self.start_time

        # Auto-detect profile if not provided
        if profile is None:
            profile = get_profile_by_name(probe_name)

        # Use a default profile if none detected
        if profile is None:
            if "ambient" in probe_name.lower() or any(
                word in probe_name.lower() for word in ["air", "grill", "smoker", "pit"]
            ):
                # For ambient probes, use the default ambient pattern
                self.is_food = False
                self.profile = None
                self.target_temp = random.uniform(225.0, 275.0)
                self.volatility = random.uniform(5.0, 15.0)
                self.pattern = "ambient"
                self.expected_duration = 60.0  # Default 1 hour cook time
            else:
                # Default food profile - use steak
                from .cooking_profiles import STEAK_GRILLING

                self.is_food = True
                self.profile = STEAK_GRILLING
                self.pattern = "food"
                self.target_temp = random.uniform(125.0, 165.0)  # Default target temp
                self.expected_duration = 30.0  # Default 30 minute cook time
        else:
            self.is_food = profile.meat_type != MeatType.FISH  # Special case
            self.profile = profile
            self.pattern = "profile_based"

        # For profile-based simulation
        if self.pattern == "profile_based":
            # Calculate total expected cooking time and set up phase tracking
            self.expected_duration = 0
            if self.profile and self.profile.phases:
                for phase in self.profile.phases:
                    # Use average of min/max duration
                    self.expected_duration += (phase.duration_range[0] + phase.duration_range[1]) / 2

            self.current_phase_index = 0
            self.phase_start_time = self.start_time
            self.phase_start_temp = self.current_temp
            if self.profile and self.profile.final_temp_range:
                self.target_temp = self.profile.final_temp_range[0]  # Initial target
            else:
                self.target_temp = 165.0  # Default target if no profile

        # Active events that affect temperature
        self.active_events: List[Dict[str, Any]] = []

        # Simulation state
        self.complete = False

        logger.debug("Started cooking session for %s/%s (%s) at %.1f°F", device_id, probe_id, probe_name, initial_temp)

    def _get_current_phase(self) -> Optional[TemperaturePhase]:
        """Get the current cooking phase or None if not using profile"""
        if self.pattern != "profile_based" or self.profile is None:
            return None

        if self.current_phase_index >= len(self.profile.phases):
            return None

        return self.profile.phases[self.current_phase_index]

    def _advance_to_next_phase(self) -> None:
        """Move to the next cooking phase"""
        if self.pattern != "profile_based" or self.profile is None:
            return

        self.current_phase_index += 1
        self.phase_start_time = time.time()
        self.phase_start_temp = self.current_temp

        # If we've completed all phases, mark as done
        if self.current_phase_index >= len(self.profile.phases):
            self.complete = True
            return

        # Set new target temp if applicable
        current_phase = self._get_current_phase()
        if current_phase and current_phase.target_temp_range:
            self.target_temp = random.uniform(current_phase.target_temp_range[0], current_phase.target_temp_range[1])

    def update_temperature(self) -> float:
        """
        Update the temperature based on elapsed time and cooking profile.

        Returns:
            The new temperature
        """
        now = time.time()
        elapsed_since_last = now - self.last_update_time
        minutes_elapsed = elapsed_since_last / 60.0
        total_minutes_elapsed = (now - self.start_time) / 60.0

        # Process any active events first
        self._process_active_events(minutes_elapsed)

        # Check for new events
        if self.pattern == "profile_based" and self.profile:
            event = generate_cooking_event(total_minutes_elapsed, self.expected_duration, self.profile.cooking_method)
            if event:
                logger.debug("Cooking event occurred: %s", event["type"])
                self.active_events.append(event)

        # Handle different simulation patterns
        if self.pattern == "profile_based" and self.profile:
            # Get current phase
            current_phase = self._get_current_phase()
            if current_phase is None:
                # All phases complete, maintain final temp with minor fluctuations
                self.current_temp += random.gauss(0, 0.5)
                self.complete = True
            else:
                # Calculate phase progress
                phase_elapsed = now - self.phase_start_time
                phase_minutes = phase_elapsed / 60.0

                # Check if we should advance to next phase
                min_duration, max_duration = current_phase.duration_range
                if phase_minutes >= random.uniform(min_duration, max_duration):
                    self._advance_to_next_phase()
                else:
                    # Apply temperature change based on phase parameters
                    if current_phase.target_based and current_phase.target_temp_range:
                        # Target-based approach (like stall or final approach)
                        target = random.uniform(current_phase.target_temp_range[0], current_phase.target_temp_range[1])
                        # Calculate approach rate (faster when further from target)
                        distance = abs(target - self.current_temp)
                        # Use minimum rate when at/beyond target
                        if distance < 0.1:
                            rate = current_phase.rate_range[0]
                        else:
                            # Normalize rate based on distance
                            normalized_rate = min(1.0, distance / 10.0)
                            rate_range = current_phase.rate_range[1] - current_phase.rate_range[0]
                            rate = current_phase.rate_range[0] + (normalized_rate * rate_range)

                        # Apply direction
                        if self.current_temp > target:
                            rate = -rate

                        # Apply temperature change
                        base_change = rate * minutes_elapsed
                    else:
                        # Standard rate-based change
                        rate = random.uniform(current_phase.rate_range[0], current_phase.rate_range[1])
                        base_change = rate * minutes_elapsed

                    # Add some noise
                    noise = random.gauss(0, current_phase.volatility) * math.sqrt(minutes_elapsed)

                    # Apply the change
                    self.current_temp += base_change + noise

        elif self.pattern == "ambient":
            # Ambient probes oscillate around a target temperature
            distance_to_target = self.current_temp - self.target_temp
            # Stronger correction when further from target
            correction = -0.1 * distance_to_target * minutes_elapsed
            # Add some random variation
            variation = random.gauss(0, self.volatility) * math.sqrt(minutes_elapsed)
            self.current_temp += correction + variation

        else:  # "food" or other default
            # Simple food rise pattern
            # Start fast, slow down as we approach target
            distance_to_target = max(0.1, self.target_temp - self.current_temp)

            # If we're past the target, slow the rise significantly
            if distance_to_target <= 0.1:
                rate = random.uniform(0.05, 0.1)  # Very slow rise at the end
            else:
                # Rate depends on how far we are from target
                # Further = faster rise, closer = slower rise
                normalized_distance = min(1.0, distance_to_target / 50.0)
                rate = 0.1 + (normalized_distance * 1.9)  # 0.1 to 2.0 degrees per minute

            # Calculate base change
            base_change = rate * minutes_elapsed

            # Add some noise
            noise = random.gauss(0, 0.5) * math.sqrt(minutes_elapsed)

            # Apply the changes
            self.current_temp += base_change + noise

        # Ensure temperature stays within realistic bounds
        self.current_temp = max(-40, min(572, self.current_temp))

        # Update last update time
        self.last_update_time = now

        return round(self.current_temp, 1)

    def _process_active_events(self, minutes_elapsed: float) -> None:
        """Process and apply any active cooking events"""
        if not self.active_events:
            return

        # Track events to remove
        completed_events = []

        for event in self.active_events:
            event_type = event["type"]

            if event_type == "lid_open":
                # Lid open causes temperature drop for ambient probes
                # and slows rise for food probes
                if not self.is_food:
                    # For ambient probes - direct temperature drop
                    if "applied" not in event:
                        # Initial application of event
                        drop_amount = event["temp_drop"]
                        self.current_temp -= drop_amount
                        event["applied"] = True
                        event["recovery_start"] = self.current_temp
                        event["elapsed"] = 0
                    else:
                        # Recovery phase
                        event["elapsed"] += minutes_elapsed
                        if event["elapsed"] >= event["duration"]:
                            # Event is complete
                            completed_events.append(event)
                else:
                    # For food probes - slow the cooking process
                    if "elapsed" not in event:
                        event["elapsed"] = 0

                    event["elapsed"] += minutes_elapsed
                    if event["elapsed"] >= event["duration"]:
                        # Event is complete
                        completed_events.append(event)

            elif event_type == "temp_adjustment":
                # Ambient temperature adjustment
                if not self.is_food and "applied" not in event:
                    # Only for ambient probes
                    adjustment = event["amount"]
                    if event["direction"] == "down":
                        adjustment = -adjustment

                    # Apply adjustment to target temperature
                    self.target_temp += adjustment
                    event["applied"] = True

                # This is a one-time event
                completed_events.append(event)

            elif event_type == "fuel_added":
                # Adding fuel causes a temperature spike for ambient probes
                if not self.is_food:
                    if "applied" not in event:
                        # Initial spike
                        self.current_temp += event["temp_spike"]
                        event["applied"] = True
                        event["elapsed"] = 0
                    else:
                        # Recovery to normal
                        event["elapsed"] += minutes_elapsed
                        if event["elapsed"] >= event["recovery_time"]:
                            # Event complete
                            completed_events.append(event)
                else:
                    # Not applicable to food probes
                    completed_events.append(event)

            elif event_type == "basting":
                # Basting causes a slight temperature drop
                if self.is_food:
                    if "applied" not in event:
                        self.current_temp -= event["temp_drop"]
                        event["applied"] = True
                        event["elapsed"] = 0
                    else:
                        event["elapsed"] += minutes_elapsed
                        if event["elapsed"] >= event["recovery_time"]:
                            completed_events.append(event)
                else:
                    # Not applicable to ambient probes
                    completed_events.append(event)

            elif event_type == "flip_food":
                # Flipping causes a brief plateau in temperature
                if self.is_food:
                    if "elapsed" not in event:
                        event["elapsed"] = 0
                        event["original_temp"] = self.current_temp

                    event["elapsed"] += minutes_elapsed
                    if event["elapsed"] <= event["temp_plateau"]:
                        # Hold temperature steady during plateau
                        self.current_temp = event["original_temp"]
                    else:
                        # Event complete
                        completed_events.append(event)
                else:
                    # Not applicable to ambient probes
                    completed_events.append(event)

        # Remove completed events
        for event in completed_events:
            if event in self.active_events:
                self.active_events.remove(event)


class TemperatureSimulator:
    """
    Advanced temperature simulator for mock ThermoWorks devices.

    Manages multiple cooking sessions and generates realistic temperature changes
    based on cooking profiles, events, and probe types.
    """

    def __init__(self) -> None:
        """Initialize the temperature simulator"""
        self.cooking_sessions: Dict[str, Dict[str, CookingSession]] = {}
        self.default_device_status: Dict[str, Dict[str, Any]] = {}

    def get_session_key(self, device_id: str, probe_id: str) -> str:
        """Get a unique key for a device/probe combination"""
        return f"{device_id}:{probe_id}"

    def create_cooking_session(
        self, device_id: str, probe_id: str, probe_name: str, initial_temp: float, probe_type: str = "food"
    ) -> CookingSession:
        """
        Create a new cooking session for a probe.

        Args:
            device_id: ThermoWorks device ID
            probe_id: Probe ID
            probe_name: Human-readable probe name
            initial_temp: Starting temperature
            probe_type: Type of probe (food, ambient, surface)

        Returns:
            The newly created cooking session
        """
        session = CookingSession(device_id=device_id, probe_id=probe_id, probe_name=probe_name, initial_temp=initial_temp)

        # Store in sessions dictionary
        if device_id not in self.cooking_sessions:
            self.cooking_sessions[device_id] = {}

        self.cooking_sessions[device_id][probe_id] = session
        return session

    def get_cooking_session(self, device_id: str, probe_id: str) -> Optional[CookingSession]:
        """Get an existing cooking session or None if not found"""
        device_sessions = self.cooking_sessions.get(device_id, {})
        return device_sessions.get(probe_id)

    def update_temperature(
        self, device_id: str, probe_id: str, current_temp: float, probe_name: str, probe_type: str
    ) -> float:
        """
        Update temperature for a specific probe based on its cooking session.

        Args:
            device_id: ThermoWorks device ID
            probe_id: Probe ID
            current_temp: Current temperature
            probe_name: Human-readable probe name
            probe_type: Type of probe (food, ambient, surface)

        Returns:
            The new temperature
        """
        # Get or create cooking session
        session = self.get_cooking_session(device_id, probe_id)
        if session is None:
            session = self.create_cooking_session(
                device_id=device_id, probe_id=probe_id, probe_name=probe_name, initial_temp=current_temp, probe_type=probe_type
            )

        # Update the temperature using the cooking session
        return session.update_temperature()

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        Get simulated device status (battery, signal, etc.)

        Args:
            device_id: ThermoWorks device ID

        Returns:
            Dict with device status information
        """
        # Create a default status if this is a new device
        if device_id not in self.default_device_status:
            self.default_device_status[device_id] = {
                "battery_level": random.randint(70, 100),
                "signal_strength": random.randint(-70, -30),
                "last_battery_update": time.time(),
                "last_signal_update": time.time(),
                "is_charging": random.random() < 0.2,  # 20% chance of charging
                "last_connection_issue": 0,  # Time of last simulated connection issue
            }

        status = self.default_device_status[device_id].copy()

        # Update battery level
        now = time.time()
        hours_since_battery_update = (now - status["last_battery_update"]) / 3600.0

        # Only update battery every ~8 hours of simulation time
        if hours_since_battery_update > 8:
            if status["is_charging"]:
                # Charging - increase battery
                status["battery_level"] = min(100, status["battery_level"] + random.randint(1, 5))
                # 10% chance to stop charging
                if random.random() < 0.1:
                    status["is_charging"] = False
            else:
                # Discharging - decrease battery
                status["battery_level"] = max(0, status["battery_level"] - random.randint(1, 3))
                # 5% chance to start charging
                if random.random() < 0.05:
                    status["is_charging"] = True

            status["last_battery_update"] = now

        # Update signal strength
        minutes_since_signal_update = (now - status["last_signal_update"]) / 60.0
        if minutes_since_signal_update > 10:  # Every ~10 minutes
            # Fluctuate signal strength
            status["signal_strength"] = max(-99, min(-30, status["signal_strength"] + random.randint(-10, 10)))
            status["last_signal_update"] = now

        # Simulate occasional connection issues (for future use)
        # 0.5% chance of a connection issue per call
        if random.random() < 0.005:
            status["last_connection_issue"] = now

        # Store updated status
        self.default_device_status[device_id] = status

        return {
            "battery_level": status["battery_level"],
            "signal_strength": status["signal_strength"],
            "is_charging": status["is_charging"],
            # Add last_connection_issue for potential future use in simulating
            # intermittent connectivity issues
        }


# Create a global instance that can be imported by the mock service
simulator = TemperatureSimulator()
