# Enhanced Mock Mode Documentation

This document describes the improvements made to the mock mode functionality in the Grill Stats application.

## Overview

The enhanced mock mode provides realistic temperature simulation for ThermoWorks devices without requiring an actual connection to the ThermoWorks API. The improvements focus on:

1. **Realistic Cooking Profiles**: Temperature patterns based on different meat types and cooking methods.
2. **Dynamic Cooking Events**: Simulation of events like opening the lid, adding fuel, etc.
3. **Improved Battery and Signal Simulation**: More realistic battery drain and signal fluctuations.
4. **Extended Probe Types**: Different behavior for food, ambient, and surface probes.

## Architecture

The mock mode enhancements include the following components:

### 1. Cooking Profiles (`cooking_profiles.py`)

Defines realistic cooking profiles for different meat types and cooking methods:

- **Meat Types**: Brisket, steak, pork shoulder, ribs, chicken, turkey, fish.
- **Cooking Methods**: Smoking, grilling, roasting, sous vide, braising.
- **Temperature Phases**: Each cooking profile includes multiple phases (e.g., initial rise, stall, final rise) with distinct behavior.

### 2. Temperature Simulator (`temp_simulator.py`)

Provides advanced temperature simulation based on cooking profiles:

- **CookingSession**: Tracks an active cooking session with a specific profile.
- **TemperatureSimulator**: Manages multiple cooking sessions and device statuses.
- **Events System**: Simulates cooking events like lid opening, temperature adjustments, etc.

### 3. Updated Mock Service (`mock_service.py`)

Uses the enhanced simulator for more realistic data:

- **Device Status**: Battery level, signal strength, charging status.
- **Temperature Data**: Based on cooking profiles and events.
- **Historical Data**: Generated based on realistic cooking curves.

## Features

### Realistic Cooking Patterns

- **Brisket Smoking**: Includes initial rise, stall phase, and final rise to target temperature.
- **Steak Grilling**: Rapid temperature increase with plateau at target.
- **Chicken Roasting**: Consistent rise to food-safe temperature.
- **Ambient Temperature**: Oscillates around target with occasional fluctuations.

### Dynamic Events

The system simulates various cooking events:

- **Lid Opening**: Causes temperature drop in ambient probes and slows rise in food probes.
- **Temperature Adjustment**: Changes target temperature for ambient probes.
- **Fuel Addition**: Causes temperature spike in smoking environments.
- **Basting/Spraying**: Small temperature drops when adding moisture.
- **Food Flipping**: Temporary plateaus in temperature rise.

### Battery and Connectivity

- **Battery Simulation**: Gradual battery drain with occasional charging.
- **Signal Strength**: Fluctuates over time with occasional connection issues.
- **Device Status**: Full simulation of online/offline status.

## Usage

### Using Mock Mode in Development

Enable mock mode in the application:

```python
# In app.py
thermoworks_client = ThermoWorksClient(
    api_key=app.config["THERMOWORKS_API_KEY"],
    mock_mode=True,  # Enable mock mode
)
```

Or use environment variables:

```
MOCK_MODE=true
```

### Testing the Mock Service

A test script is provided to verify the mock service functionality:

```bash
python test_mock_service.py [device_id] [probe_name] [options]
```

Options:
- `--iterations` / `-i`: Number of temperature readings to collect
- `--interval` / `-t`: Seconds between readings
- `--hours`: Hours of historical data to fetch

Example:
```bash
python test_mock_service.py mock-bluedot-002 brisket -i 30 -t 2
```

## Implementation Notes

### Adding New Cooking Profiles

To add new meat types or cooking profiles:

1. Define a new `CookingProfile` in `cooking_profiles.py`
2. Add phases with appropriate temperature behaviors
3. Add the profile to the `COOKING_PROFILES` dictionary

### Future Enhancements

Potential future improvements:

1. Persistence of historical data to improve simulation
2. User-configurable cooking profiles
3. Integration with user preferences from the application
4. More sophisticated event simulation based on device types

## Testing

The mock mode has been tested to ensure it produces realistic temperature patterns for different scenarios:

- Ambient temperature fluctuations
- Food temperature progression through different cooking phases
- Behavior during events like lid opening
- Battery and signal behavior over time
- Historical data generation

The test script (`test_mock_service.py`) can be used to verify these features.
