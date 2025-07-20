# Mock Data Service

## Overview

The Mock Data Service provides realistic simulated data for ThermoWorks devices and temperature readings. It is designed for development, testing, and demonstration purposes, eliminating the need for actual ThermoWorks API credentials or hardware during these phases.

## Features

- Simulated device information that matches the ThermoWorks API format
- Realistic temperature patterns based on cooking profiles for different meat types
- Simulated cooking events (lid opening, temperature adjustments, etc.)
- Battery level and signal strength simulation
- Historical temperature data generation
- Support for all ThermoWorks device models (SIGNALS, DOT, BLUEDOT, NODE)

## Usage

### Basic Usage

The mock data service is automatically enabled when:

1. The `MOCK_MODE` environment variable is set to `true` (or `1`, `yes`, `on`)
2. The application is not running in production mode

```python
from thermoworks_client import ThermoWorksClient

# Enable mock mode explicitly
client = ThermoWorksClient(mock_mode=True)

# Or rely on environment variables
# MOCK_MODE=true python app.py

# Use the client as normal
devices = client.get_devices()
temp_data = client.get_temperature_data("mock-signals-001", "probe_1")
```

### Configuration

The mock data service reads device configuration from:

- `services/mock_data/devices.json` - Initial device configuration
- `services/mock_data/historical.json` - Pre-generated historical data (optional)

You can modify these files to customize the mock devices and their behavior.

### Testing

The mock data service is particularly useful for:

1. Integration testing without external dependencies
2. UI development with realistic data patterns
3. Demo environments
4. Local development without ThermoWorks API credentials

Example test usage:

```python
import os
import unittest
from thermoworks_client import ThermoWorksClient

class TestWithMockData(unittest.TestCase):
    def setUp(self):
        os.environ["MOCK_MODE"] = "true"
        self.client = ThermoWorksClient(api_key="mock-key")

    def test_get_devices(self):
        devices = self.client.get_devices()
        self.assertTrue(len(devices) > 0)
```

## Technical Details

### Mock Service Classes

The mock data service consists of several key components:

1. **MockDataService** (`services/mock_data/mock_service.py`) - Main service that implements the ThermoWorks API interface
2. **TemperatureSimulator** (`services/mock_data/temp_simulator.py`) - Generates realistic temperature changes over time
3. **CookingProfiles** (`services/mock_data/cooking_profiles.py`) - Defines temperature patterns for different meat types and cooking methods

### Temperature Simulation

The temperature simulator provides realistic temperature changes for different probe types:

- **Food probes**: Follow cooking profiles with phases like initial rise, stall, and final approach
- **Ambient probes**: Oscillate around a target temperature with random fluctuations
- **Surface probes**: Maintain high temperatures with greater volatility

### Cooking Events

The simulator also generates realistic cooking events that affect temperature patterns:

- Lid opening (causes temperature drop for ambient probes)
- Temperature adjustments (changes target temperature)
- Fuel/wood added (causes temporary temperature spike)
- Basting/spraying (causes brief temperature drop)
- Flipping food (causes temperature plateau)

### Device Status Simulation

The service simulates other device characteristics:

- Battery level (slowly decreases over time)
- Signal strength (random fluctuations)
- Charging status (random changes)

## Customization

### Adding New Devices

To add new mock devices, edit the `services/mock_data/devices.json` file:

```json
{
  "devices": [
    {
      "device_id": "your-new-device-id",
      "name": "Your New Device",
      "model": "SIGNALS",
      "firmware_version": "1.0.0",
      "is_online": true,
      "probes": [
        {
          "probe_id": "probe_1",
          "name": "Brisket",
          "type": "food",
          "current_temp": 150.0,
          "unit": "F"
        }
      ]
    }
  ]
}
```

### Adding Cooking Profiles

To add new cooking profiles, edit the `services/mock_data/cooking_profiles.py` file:

```python
MY_NEW_PROFILE = CookingProfile(
    meat_type=MeatType.BEEF_STEAK,
    cooking_method=CookingMethod.GRILLING,
    description="My custom profile",
    starting_temp_range=(35.0, 45.0),
    final_temp_range=(125.0, 135.0),
    phases=[
        TemperaturePhase(
            name="rapid_rise",
            duration_range=(5.0, 10.0),
            rate_range=(5.0, 8.0),
            volatility=0.8,
        ),
    ],
)

# Add to profiles dictionary
COOKING_PROFILES["my_new_profile"] = MY_NEW_PROFILE
```

## Limitations

- The mock service does not implement authentication or authorization checks
- Network errors and connection issues are not fully simulated
- Some advanced ThermoWorks API features may not be implemented
- Timestamp handling might differ slightly from the real API
