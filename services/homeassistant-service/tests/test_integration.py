import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.models.ha_models import HAConfig, HAConnectionStatus
from src.models.entity_models import TemperatureSensor, DeviceEntity
from src.services.ha_client import HomeAssistantClient
from src.services.entity_manager import EntityManager
from src.services.state_sync import StateSynchronizer
from src.services.discovery_service import DiscoveryService
from src.utils.automation_helpers import AutomationHelper


class TestHomeAssistantIntegration:
    
    @pytest.fixture
    def ha_config(self):
        return HAConfig(
            base_url="http://test-homeassistant:8123",
            access_token="test-token",
            verify_ssl=False,
            entity_prefix="test_grill"
        )
    
    @pytest.fixture
    def mock_ha_client(self, ha_config):
        return HomeAssistantClient(ha_config, mock_mode=True)
    
    @pytest.fixture
    def entity_manager(self, mock_ha_client):
        return EntityManager(mock_ha_client, "test_grill")
    
    @pytest.fixture
    def state_sync(self, mock_ha_client, entity_manager):
        return StateSynchronizer(mock_ha_client, entity_manager, None, sync_interval=1)
    
    @pytest.fixture
    def discovery_service(self, mock_ha_client, ha_config):
        return DiscoveryService(mock_ha_client, ha_config)
    
    @pytest.fixture
    def automation_helper(self, mock_ha_client, entity_manager):
        return AutomationHelper(mock_ha_client, entity_manager)
    
    @pytest.fixture
    def sample_temperature_data(self):
        return TemperatureSensor(
            device_id="test_device_001",
            probe_id="1",
            name="Test Probe 1",
            temperature=225.5,
            unit="°F",
            battery_level=85,
            signal_strength=-45,
            last_seen=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_device_data(self):
        return DeviceEntity(
            device_id="test_device_001",
            name="Test Grill Device",
            model="ThermoWorks Wireless",
            manufacturer="ThermoWorks",
            identifiers=["test_device_001"],
            connections=[("mac", "00:11:22:33:44:55")]
        )

    def test_ha_client_connection(self, mock_ha_client):
        """Test Home Assistant client connection in mock mode"""
        # Test connection
        assert mock_ha_client.test_connection() == True
        
        # Test health status
        health = mock_ha_client.get_health_status()
        assert health.status == HAConnectionStatus.CONNECTED

    def test_entity_creation(self, entity_manager, sample_temperature_data):
        """Test temperature sensor entity creation"""
        # Create temperature sensor
        success = entity_manager.create_temperature_sensor(sample_temperature_data)
        assert success == True
        
        # Verify entity was created
        entity_id = f"sensor.test_grill_{sample_temperature_data.device_id}_{sample_temperature_data.probe_id}_temperature"
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None
        assert entity.entity_id == entity_id
        assert entity.state == sample_temperature_data.temperature
        assert entity.attributes["device_id"] == sample_temperature_data.device_id

    def test_battery_sensor_creation(self, entity_manager):
        """Test battery sensor entity creation"""
        device_id = "test_device_001"
        battery_level = 75
        
        success = entity_manager.create_battery_sensor(device_id, battery_level)
        assert success == True
        
        # Verify entity was created
        entity_id = f"sensor.test_grill_{device_id}_battery"
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None
        assert entity.state == battery_level
        assert entity.attributes["unit_of_measurement"] == "%"

    def test_signal_strength_sensor_creation(self, entity_manager):
        """Test signal strength sensor entity creation"""
        device_id = "test_device_001"
        signal_strength = -55
        
        success = entity_manager.create_signal_strength_sensor(device_id, signal_strength)
        assert success == True
        
        # Verify entity was created
        entity_id = f"sensor.test_grill_{device_id}_signal_strength"
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None
        assert entity.state == signal_strength
        assert entity.attributes["unit_of_measurement"] == "dBm"

    def test_connection_binary_sensor_creation(self, entity_manager):
        """Test connection binary sensor entity creation"""
        device_id = "test_device_001"
        is_connected = True
        
        success = entity_manager.create_connection_binary_sensor(device_id, is_connected)
        assert success == True
        
        # Verify entity was created
        entity_id = f"binary_sensor.test_grill_{device_id}_connection"
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None
        assert entity.state == "on"

    def test_device_group_creation(self, entity_manager, sample_device_data):
        """Test device group creation"""
        success = entity_manager.create_device_group(sample_device_data)
        assert success == True
        
        # Verify device was registered
        assert sample_device_data.device_id in entity_manager.registry.devices

    @pytest.mark.asyncio
    async def test_state_synchronization(self, state_sync, sample_temperature_data):
        """Test temperature data synchronization"""
        # Start state sync
        await state_sync.start()
        
        # Sync temperature data
        success = await state_sync.sync_temperature_data(sample_temperature_data)
        assert success == True
        
        # Check that data was queued for sync
        entity_id = f"sensor.test_grill_{sample_temperature_data.device_id}_{sample_temperature_data.probe_id}_temperature"
        assert entity_id in state_sync.pending_updates
        
        # Stop state sync
        await state_sync.stop()

    @pytest.mark.asyncio
    async def test_device_state_synchronization(self, state_sync):
        """Test device state synchronization"""
        device_id = "test_device_001"
        state_data = {
            "battery_level": 80,
            "signal_strength": -50,
            "is_connected": True
        }
        
        # Start state sync
        await state_sync.start()
        
        # Sync device state
        success = await state_sync.sync_device_state(device_id, state_data)
        assert success == True
        
        # Stop state sync
        await state_sync.stop()

    @pytest.mark.asyncio
    async def test_force_sync_all(self, state_sync, entity_manager, sample_temperature_data):
        """Test force sync all entities"""
        # Create some entities first
        entity_manager.create_temperature_sensor(sample_temperature_data)
        entity_manager.create_battery_sensor("test_device_001", 85)
        
        # Force sync all
        result = await state_sync.force_sync_all()
        
        # Verify sync results
        assert "total_entities" in result
        assert "successful_syncs" in result
        assert result["total_entities"] > 0

    @pytest.mark.asyncio
    async def test_auto_discovery(self, discovery_service):
        """Test auto-discovery functionality"""
        # Run auto-discovery
        result = await discovery_service.auto_discover_devices()
        
        # Verify discovery results
        assert "discovered_entities" in result
        assert "devices_found" in result
        assert "discovery_time" in result

    @pytest.mark.asyncio
    async def test_device_discovery_registration(self, discovery_service):
        """Test device discovery registration"""
        device_id = "test_device_001"
        device_info = {
            "name": "Test Grill Device",
            "manufacturer": "ThermoWorks",
            "model": "Wireless Thermometer",
            "has_temperature": True,
            "has_battery": True,
            "has_signal_strength": True,
            "has_connectivity": True,
            "probes": ["1", "2"]
        }
        
        # Register device for discovery
        success = await discovery_service.register_device_discovery(device_id, device_info)
        assert success == True
        
        # Verify discovery configs were created
        discovery_configs = discovery_service.get_all_discovery_configs()
        assert len(discovery_configs) > 0

    def test_temperature_alert_automation(self, automation_helper):
        """Test temperature alert automation creation"""
        automation_id = automation_helper.create_temperature_alert_automation(
            device_id="test_device_001",
            probe_id="1",
            alert_name="High Temperature Alert",
            temperature_threshold=250.0,
            threshold_type="above",
            notification_title="Temperature Alert",
            notification_message="Temperature is too high!"
        )
        
        assert automation_id != ""
        assert automation_id in automation_helper.automations
        
        # Verify automation details
        automation = automation_helper.get_automation(automation_id)
        assert automation is not None
        assert automation.alias == "Temperature Alert: High Temperature Alert"
        assert len(automation.trigger) == 1
        assert len(automation.action) == 1

    def test_device_offline_automation(self, automation_helper):
        """Test device offline automation creation"""
        automation_id = automation_helper.create_device_offline_automation(
            device_id="test_device_001",
            alert_name="Device Offline Alert",
            offline_duration="00:05:00"
        )
        
        assert automation_id != ""
        assert automation_id in automation_helper.automations
        
        # Verify automation
        automation = automation_helper.get_automation(automation_id)
        assert automation is not None
        assert "Device Offline" in automation.alias

    def test_battery_low_automation(self, automation_helper):
        """Test battery low automation creation"""
        automation_id = automation_helper.create_battery_low_automation(
            device_id="test_device_001",
            battery_threshold=20,
            alert_name="Low Battery Alert"
        )
        
        assert automation_id != ""
        assert automation_id in automation_helper.automations
        
        # Verify automation
        automation = automation_helper.get_automation(automation_id)
        assert automation is not None
        assert "Low Battery" in automation.alias

    def test_cooking_session_automation(self, automation_helper):
        """Test cooking session automation creation"""
        automation_id = automation_helper.create_cooking_session_automation(
            device_ids=["test_device_001", "test_device_002"],
            session_name="BBQ Session",
            start_temperature_threshold=80.0,
            end_temperature_threshold=60.0
        )
        
        assert automation_id != ""
        assert automation_id in automation_helper.automations
        
        # Verify automation
        automation = automation_helper.get_automation(automation_id)
        assert automation is not None
        assert "BBQ Session" in automation.alias

    def test_automation_management(self, automation_helper):
        """Test automation enable/disable functionality"""
        # Create an automation
        automation_id = automation_helper.create_temperature_alert_automation(
            device_id="test_device_001",
            probe_id="1",
            alert_name="Test Alert",
            temperature_threshold=200.0
        )
        
        # Test disable
        success = automation_helper.disable_automation(automation_id)
        assert success == True
        automation = automation_helper.get_automation(automation_id)
        assert automation.enabled == False
        
        # Test enable
        success = automation_helper.enable_automation(automation_id)
        assert success == True
        automation = automation_helper.get_automation(automation_id)
        assert automation.enabled == True
        
        # Test removal
        success = automation_helper.remove_automation(automation_id)
        assert success == True
        assert automation_id not in automation_helper.automations

    def test_entity_cleanup(self, entity_manager, sample_temperature_data):
        """Test stale entity cleanup"""
        # Create an entity
        entity_manager.create_temperature_sensor(sample_temperature_data)
        
        # Verify entity exists
        entity_id = f"sensor.test_grill_{sample_temperature_data.device_id}_{sample_temperature_data.probe_id}_temperature"
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None
        
        # Test cleanup (should not remove recent entities)
        removed_count = entity_manager.cleanup_stale_entities(max_age_hours=24)
        assert removed_count == 0
        
        # Verify entity still exists
        entity = entity_manager.get_entity(entity_id)
        assert entity is not None

    def test_entity_update(self, entity_manager, sample_temperature_data):
        """Test entity state updates"""
        # Create an entity
        entity_manager.create_temperature_sensor(sample_temperature_data)
        entity_id = f"sensor.test_grill_{sample_temperature_data.device_id}_{sample_temperature_data.probe_id}_temperature"
        
        # Update entity state
        new_temperature = 230.0
        new_attributes = {"updated": True}
        success = entity_manager.update_entity_state(entity_id, new_temperature, new_attributes)
        assert success == True
        
        # Verify update
        entity = entity_manager.get_entity(entity_id)
        assert entity.state == new_temperature
        assert entity.attributes["updated"] == True

    def test_registry_stats(self, entity_manager, sample_temperature_data, sample_device_data):
        """Test entity registry statistics"""
        # Create entities and devices
        entity_manager.create_temperature_sensor(sample_temperature_data)
        entity_manager.create_battery_sensor("test_device_001", 85)
        entity_manager.create_device_group(sample_device_data)
        
        # Get stats
        stats = entity_manager.get_registry_stats()
        
        assert stats["total_entities"] >= 2
        assert stats["total_devices"] >= 1
        assert "entities_by_type" in stats
        assert "sensor" in stats["entities_by_type"]

    def test_automation_stats(self, automation_helper):
        """Test automation statistics"""
        # Create some automations
        automation_helper.create_temperature_alert_automation(
            device_id="test_device_001", probe_id="1", alert_name="Test Alert 1", temperature_threshold=200.0
        )
        automation_helper.create_device_offline_automation(
            device_id="test_device_001", alert_name="Offline Alert"
        )
        
        # Get stats
        stats = automation_helper.get_automation_stats()
        
        assert stats["total_automations"] >= 2
        assert stats["enabled_automations"] >= 2
        assert "automation_types" in stats

    def test_discovery_stats(self, discovery_service):
        """Test discovery service statistics"""
        stats = discovery_service.get_discovery_stats()
        
        assert "total_entities" in stats
        assert "entity_types" in stats
        assert "unique_devices" in stats
        assert "last_discovery" in stats

    @pytest.mark.asyncio
    async def test_complete_integration_workflow(self, mock_ha_client, entity_manager, state_sync, 
                                                discovery_service, automation_helper, sample_temperature_data):
        """Test complete integration workflow"""
        # 1. Register device
        device_entity = DeviceEntity(
            device_id=sample_temperature_data.device_id,
            name="Test Grill Device",
            manufacturer="ThermoWorks"
        )
        success = entity_manager.create_device_group(device_entity)
        assert success == True
        
        # 2. Create temperature sensor
        success = entity_manager.create_temperature_sensor(sample_temperature_data)
        assert success == True
        
        # 3. Create additional sensors
        entity_manager.create_battery_sensor(sample_temperature_data.device_id, 85)
        entity_manager.create_signal_strength_sensor(sample_temperature_data.device_id, -45)
        entity_manager.create_connection_binary_sensor(sample_temperature_data.device_id, True)
        
        # 4. Start state synchronization
        await state_sync.start()
        
        # 5. Sync temperature data
        success = await state_sync.sync_temperature_data(sample_temperature_data)
        assert success == True
        
        # 6. Create automations
        temp_alert_id = automation_helper.create_temperature_alert_automation(
            device_id=sample_temperature_data.device_id,
            probe_id=sample_temperature_data.probe_id,
            alert_name="High Temp Alert",
            temperature_threshold=250.0
        )
        assert temp_alert_id != ""
        
        offline_alert_id = automation_helper.create_device_offline_automation(
            device_id=sample_temperature_data.device_id
        )
        assert offline_alert_id != ""
        
        # 7. Register for discovery
        device_info = {
            "name": device_entity.name,
            "manufacturer": device_entity.manufacturer,
            "has_temperature": True,
            "has_battery": True,
            "probes": ["1"]
        }
        success = await discovery_service.register_device_discovery(
            sample_temperature_data.device_id, device_info
        )
        assert success == True
        
        # 8. Force sync all entities
        sync_result = await state_sync.force_sync_all()
        assert sync_result["total_entities"] >= 4
        
        # 9. Verify all components are working
        registry_stats = entity_manager.get_registry_stats()
        automation_stats = automation_helper.get_automation_stats()
        discovery_stats = discovery_service.get_discovery_stats()
        
        assert registry_stats["total_entities"] >= 4
        assert automation_stats["total_automations"] >= 2
        assert discovery_stats["total_entities"] >= 0
        
        # 10. Stop state sync
        await state_sync.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])