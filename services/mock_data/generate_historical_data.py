#!/usr/bin/env python3
"""
Historical Data Generator for Mock Grill Stats Data

This script generates realistic 4-hour historical temperature curves for different BBQ cooking scenarios.
It creates data that mimics real cooking patterns for various types of food and cooking methods.
"""

import json
import math
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List


def generate_brisket_curve(
    device_id: str, probe_id: str, start_time: datetime
) -> List[Dict[str, Any]]:
    """Generate temperature curve for a low and slow brisket cook"""
    readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    # Brisket internal temp progression: 70°F -> 203°F over 4 hours
    # Realistic curve with stall around 160-170°F
    for i in range(480):  # 4 hours * 60 minutes * 2 (30-second intervals)
        time_ratio = i / 480.0

        if time_ratio < 0.3:
            # Initial rise (0-72 minutes): 70°F to 160°F
            base_temp = 70 + (90 * (time_ratio / 0.3))
        elif time_ratio < 0.6:
            # Stall period (72-144 minutes): 160°F to 170°F (slow)
            base_temp = 160 + (10 * ((time_ratio - 0.3) / 0.3))
        else:
            # Final push (144-240 minutes): 170°F to 203°F
            base_temp = 170 + (33 * ((time_ratio - 0.6) / 0.4))

        # Add realistic noise
        actual_temp = base_temp + random.gauss(0, 1.5)
        actual_temp = max(65, min(210, actual_temp))

        reading = {
            "device_id": device_id,
            "probe_id": probe_id,
            "temperature": round(actual_temp, 1),
            "unit": "F",
            "timestamp": current_time.isoformat() + "Z",
            "battery_level": random.randint(85, 100),
            "signal_strength": random.randint(-55, -35),
        }

        readings.append(reading)
        current_time += interval

    return readings


def generate_ribs_curve(
    device_id: str, probe_id: str, start_time: datetime
) -> List[Dict[str, Any]]:
    """Generate temperature curve for pork ribs"""
    readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    # Ribs: 70°F -> 195°F over 4 hours (faster than brisket)
    for i in range(480):
        time_ratio = i / 480.0

        # Steady rise with slight curve
        base_temp = 70 + (125 * (1 - math.exp(-3 * time_ratio)))

        # Add realistic noise
        actual_temp = base_temp + random.gauss(0, 2.0)
        actual_temp = max(65, min(200, actual_temp))

        reading = {
            "device_id": device_id,
            "probe_id": probe_id,
            "temperature": round(actual_temp, 1),
            "unit": "F",
            "timestamp": current_time.isoformat() + "Z",
            "battery_level": random.randint(75, 95),
            "signal_strength": random.randint(-60, -40),
        }

        readings.append(reading)
        current_time += interval

    return readings


def generate_chicken_curve(
    device_id: str, probe_id: str, start_time: datetime
) -> List[Dict[str, Any]]:
    """Generate temperature curve for chicken breast"""
    readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    # Chicken breast: 70°F -> 165°F over 4 hours
    for i in range(480):
        time_ratio = i / 480.0

        # Faster initial rise, then slowing
        if time_ratio < 0.7:
            base_temp = 70 + (80 * (time_ratio / 0.7))
        else:
            base_temp = 150 + (15 * ((time_ratio - 0.7) / 0.3))

        # Add realistic noise
        actual_temp = base_temp + random.gauss(0, 1.8)
        actual_temp = max(65, min(170, actual_temp))

        reading = {
            "device_id": device_id,
            "probe_id": probe_id,
            "temperature": round(actual_temp, 1),
            "unit": "F",
            "timestamp": current_time.isoformat() + "Z",
            "battery_level": random.randint(70, 90),
            "signal_strength": random.randint(-65, -45),
        }

        readings.append(reading)
        current_time += interval

    return readings


def generate_ambient_curve(
    device_id: str, probe_id: str, start_time: datetime, target_temp: float = 225.0
) -> List[Dict[str, Any]]:
    """Generate temperature curve for ambient/pit temperature"""
    readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    for i in range(480):
        time_ratio = i / 480.0

        # Ambient temperature reaches target quickly then fluctuates
        if time_ratio < 0.1:
            # Heat up phase
            base_temp = 70 + ((target_temp - 70) * (time_ratio / 0.1))
        else:
            # Maintenance phase with controlled fluctuations
            base_temp = (
                target_temp + 5 * math.sin(time_ratio * 20) + random.uniform(-8, 8)
            )

        # Add realistic noise for ambient readings
        actual_temp = base_temp + random.gauss(0, 3.0)
        actual_temp = max(60, min(300, actual_temp))

        reading = {
            "device_id": device_id,
            "probe_id": probe_id,
            "temperature": round(actual_temp, 1),
            "unit": "F",
            "timestamp": current_time.isoformat() + "Z",
            "battery_level": random.randint(80, 100),
            "signal_strength": random.randint(-50, -30),
        }

        readings.append(reading)
        current_time += interval

    return readings


def generate_water_pan_curve(
    device_id: str, probe_id: str, start_time: datetime
) -> List[Dict[str, Any]]:
    """Generate temperature curve for water pan (stays around 212°F)"""
    readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    for i in range(480):
        time_ratio = i / 480.0

        # Water temperature rises to boiling then stays stable
        if time_ratio < 0.15:
            base_temp = 70 + (142 * (time_ratio / 0.15))
        else:
            base_temp = 212 + random.uniform(-3, 1)  # Slight variations around boiling

        # Add minimal noise for water temperature
        actual_temp = base_temp + random.gauss(0, 1.0)
        actual_temp = max(65, min(215, actual_temp))

        reading = {
            "device_id": device_id,
            "probe_id": probe_id,
            "temperature": round(actual_temp, 1),
            "unit": "F",
            "timestamp": current_time.isoformat() + "Z",
            "battery_level": random.randint(75, 95),
            "signal_strength": random.randint(-55, -35),
        }

        readings.append(reading)
        current_time += interval

    return readings


def generate_complete_historical_data() -> Dict[str, Any]:
    """Generate complete historical data for all mock devices"""
    # Start time 4 hours ago
    start_time = datetime.utcnow() - timedelta(hours=4)

    all_readings = []

    # Test Signals device - ambient probe
    all_readings.extend(
        generate_ambient_curve("mock-signals-001", "probe_1", start_time, 225.0)
    )

    # Mock BlueDOT device - brisket and pit temp
    all_readings.extend(
        generate_brisket_curve("mock-bluedot-002", "probe_1", start_time)
    )
    all_readings.extend(
        generate_ambient_curve("mock-bluedot-002", "probe_2", start_time, 235.0)
    )

    # Fake NODE device - ribs, chicken, smoker air, water pan
    all_readings.extend(generate_ribs_curve("mock-node-003", "probe_1", start_time))
    all_readings.extend(generate_chicken_curve("mock-node-003", "probe_2", start_time))
    all_readings.extend(
        generate_ambient_curve("mock-node-003", "probe_3", start_time, 275.0)
    )
    all_readings.extend(
        generate_water_pan_curve("mock-node-003", "probe_4", start_time)
    )

    # Test DOT device - steak and grill surface (high temp)
    # Generate steak curve (similar to chicken but higher target)
    steak_readings = []
    current_time = start_time
    interval = timedelta(seconds=30)

    for i in range(480):
        time_ratio = i / 480.0
        # Steak: 70°F -> 135°F over 4 hours (medium-rare target)
        base_temp = 70 + (65 * (1 - math.exp(-2.5 * time_ratio)))
        actual_temp = base_temp + random.gauss(0, 1.5)
        actual_temp = max(65, min(145, actual_temp))

        steak_readings.append(
            {
                "device_id": "mock-dot-004",
                "probe_id": "probe_1",
                "temperature": round(actual_temp, 1),
                "unit": "F",
                "timestamp": current_time.isoformat() + "Z",
                "battery_level": random.randint(60, 80),
                "signal_strength": random.randint(-70, -50),
            }
        )
        current_time += interval

    all_readings.extend(steak_readings)

    # Grill surface temperature (high and variable)
    surface_readings = []
    current_time = start_time

    for i in range(480):
        time_ratio = i / 480.0
        base_temp = 350 + 75 * math.sin(time_ratio * 15) + random.uniform(-20, 20)
        actual_temp = max(300, min(500, base_temp))

        surface_readings.append(
            {
                "device_id": "mock-dot-004",
                "probe_id": "probe_2",
                "temperature": round(actual_temp, 1),
                "unit": "F",
                "timestamp": current_time.isoformat() + "Z",
                "battery_level": random.randint(60, 80),
                "signal_strength": random.randint(-70, -50),
            }
        )
        current_time += interval

    all_readings.extend(surface_readings)

    return {
        "readings": all_readings,
        "metadata": {
            "total_readings": len(all_readings),
            "time_range": {
                "start": start_time.isoformat() + "Z",
                "end": (start_time + timedelta(hours=4)).isoformat() + "Z",
            },
            "devices_included": [
                "mock-signals-001",
                "mock-bluedot-002",
                "mock-node-003",
                "mock-dot-004",
            ],
            "scenarios": [
                "Low and slow brisket cook with stall",
                "Pork ribs steady rise",
                "Chicken breast cook",
                "Ambient temperature maintenance",
                "Water pan monitoring",
                "High-heat steak cook",
                "Variable grill surface temperature",
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "generator_version": "1.0.0",
        },
    }


if __name__ == "__main__":
    # Generate and save historical data
    historical_data = generate_complete_historical_data()

    with open("historical.json", "w") as f:
        json.dump(historical_data, f, indent=2)

    print(
        f"Generated {len(historical_data['readings'])} historical temperature readings"
    )
    print(
        f"Time range: {historical_data['metadata']['time_range']['start']} to {historical_data['metadata']['time_range']['end']}"
    )
    print("Scenarios included:")
    for scenario in historical_data["metadata"]["scenarios"]:
        print(f"  - {scenario}")
