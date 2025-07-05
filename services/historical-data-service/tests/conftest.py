import pytest
import os
import sys
from unittest.mock import MagicMock

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_timescale_manager():
    """Create a mock TimescaleManager for testing."""
    manager = MagicMock()
    
    # Mock health check
    manager.health_check.return_value = True
    
    # Mock store_temperature_reading
    manager.store_temperature_reading.return_value = True
    
    # Mock store_batch_temperature_readings
    manager.store_batch_temperature_readings.return_value = 2
    
    # Mock get_temperature_history
    manager.get_temperature_history.return_value = []
    
    # Mock get_temperature_statistics
    manager.get_temperature_statistics.return_value = {}
    
    return manager