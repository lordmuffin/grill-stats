from flask import Flask, request, jsonify
from datetime import datetime
import logging
from typing import Dict, Any
from ..models.entity_models import TemperatureSensor, DeviceEntity
from ..models.ha_models import HAConfig, HAServiceCall, HAEvent

logger = logging.getLogger(__name__)


class HomeAssistantAPI:
    def __init__(self, ha_client, entity_manager, state_sync, discovery_service, automation_helper, health_monitor):
        self.ha_client = ha_client
        self.entity_manager = entity_manager
        self.state_sync = state_sync
        self.discovery_service = discovery_service
        self.automation_helper = automation_helper
        self.health_monitor = health_monitor

    def setup_routes(self, app: Flask):
        """Setup all API routes"""
        
        @app.route('/health', methods=['GET'])
        def health_check():
            try:
                health_status = self.health_monitor.get_health_status()
                status_code = 200 if health_status["overall_health"] in ["healthy", "degraded"] else 503
                return jsonify(health_status), status_code
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/temperature', methods=['POST'])
        def sync_temperature():
            try:
                data = request.get_json()
                
                # Validate required fields
                required_fields = ['device_id', 'probe_id', 'temperature', 'unit']
                for field in required_fields:
                    if field not in data:
                        return jsonify({"error": f"Missing required field: {field}"}), 400
                
                # Create temperature sensor data
                sensor_data = TemperatureSensor(
                    device_id=data['device_id'],
                    probe_id=data['probe_id'],
                    name=data.get('name', f"Device {data['device_id']} Probe {data['probe_id']}"),
                    temperature=float(data['temperature']),
                    unit=data['unit'],
                    battery_level=data.get('battery_level'),
                    signal_strength=data.get('signal_strength'),
                    last_seen=datetime.fromisoformat(data['last_seen']) if 'last_seen' in data else datetime.utcnow()
                )
                
                # Create or update temperature sensor
                success = self.entity_manager.create_temperature_sensor(sensor_data)
                if not success:
                    return jsonify({"error": "Failed to create temperature sensor"}), 500
                
                # Sync to Home Assistant
                sync_success = await self.state_sync.sync_temperature_data(sensor_data)
                if not sync_success:
                    return jsonify({"error": "Failed to sync temperature data"}), 500
                
                return jsonify({
                    "status": "success",
                    "message": "Temperature data synced successfully",
                    "entity_id": f"sensor.grill_stats_{data['device_id']}_{data['probe_id']}_temperature"
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to sync temperature: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/device', methods=['POST'])
        def register_device():
            try:
                data = request.get_json()
                
                # Validate required fields
                if 'device_id' not in data:
                    return jsonify({"error": "Missing required field: device_id"}), 400
                
                # Create device entity
                device_entity = DeviceEntity(
                    device_id=data['device_id'],
                    name=data.get('name', f"Device {data['device_id']}"),
                    model=data.get('model'),
                    manufacturer=data.get('manufacturer', 'ThermoWorks'),
                    sw_version=data.get('sw_version'),
                    hw_version=data.get('hw_version'),
                    identifiers=data.get('identifiers', [data['device_id']]),
                    connections=data.get('connections', []),
                    via_device=data.get('via_device')
                )
                
                # Register device
                success = self.entity_manager.create_device_group(device_entity)
                if not success:
                    return jsonify({"error": "Failed to register device"}), 500
                
                # Register for discovery
                discovery_success = await self.discovery_service.register_device_discovery(
                    data['device_id'],
                    data
                )
                
                if not discovery_success:
                    logger.warning(f"Failed to register device discovery for {data['device_id']}")
                
                return jsonify({
                    "status": "success",
                    "message": "Device registered successfully",
                    "device_id": data['device_id']
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to register device: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/device/<device_id>/state', methods=['POST'])
        def sync_device_state(device_id: str):
            try:
                data = request.get_json()
                
                # Sync device state
                success = await self.state_sync.sync_device_state(device_id, data)
                if not success:
                    return jsonify({"error": "Failed to sync device state"}), 500
                
                return jsonify({
                    "status": "success",
                    "message": "Device state synced successfully",
                    "device_id": device_id
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to sync device state: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/entities', methods=['GET'])
        def get_entities():
            try:
                entities = self.entity_manager.get_all_entities()
                
                # Convert to serializable format
                entities_data = {}
                for entity_id, entity_state in entities.items():
                    entities_data[entity_id] = {
                        "entity_id": entity_state.entity_id,
                        "state": entity_state.state,
                        "attributes": entity_state.attributes,
                        "last_changed": entity_state.last_changed.isoformat(),
                        "last_updated": entity_state.last_updated.isoformat()
                    }
                
                return jsonify({
                    "entities": entities_data,
                    "count": len(entities_data)
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to get entities: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/entities/<entity_id>', methods=['GET'])
        def get_entity(entity_id: str):
            try:
                entity = self.entity_manager.get_entity(entity_id)
                if not entity:
                    return jsonify({"error": "Entity not found"}), 404
                
                return jsonify({
                    "entity_id": entity.entity_id,
                    "state": entity.state,
                    "attributes": entity.attributes,
                    "last_changed": entity.last_changed.isoformat(),
                    "last_updated": entity.last_updated.isoformat()
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to get entity: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/sync/force', methods=['POST'])
        def force_sync():
            try:
                result = await self.state_sync.force_sync_all()
                return jsonify(result), 200
                
            except Exception as e:
                logger.error(f"Failed to force sync: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/discovery/auto', methods=['POST'])
        def auto_discover():
            try:
                result = await self.discovery_service.auto_discover_devices()
                return jsonify(result), 200
                
            except Exception as e:
                logger.error(f"Failed to auto discover: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/automation', methods=['POST'])
        def create_automation():
            try:
                data = request.get_json()
                automation_type = data.get('type')
                
                if automation_type == 'temperature_alert':
                    automation_id = self.automation_helper.create_temperature_alert_automation(
                        device_id=data['device_id'],
                        probe_id=data['probe_id'],
                        alert_name=data['alert_name'],
                        temperature_threshold=data['temperature_threshold'],
                        threshold_type=data.get('threshold_type', 'above'),
                        notification_title=data.get('notification_title'),
                        notification_message=data.get('notification_message')
                    )
                elif automation_type == 'device_offline':
                    automation_id = self.automation_helper.create_device_offline_automation(
                        device_id=data['device_id'],
                        alert_name=data.get('alert_name', 'Device Offline'),
                        offline_duration=data.get('offline_duration', '00:05:00')
                    )
                elif automation_type == 'battery_low':
                    automation_id = self.automation_helper.create_battery_low_automation(
                        device_id=data['device_id'],
                        battery_threshold=data.get('battery_threshold', 20),
                        alert_name=data.get('alert_name', 'Low Battery')
                    )
                elif automation_type == 'cooking_session':
                    automation_id = self.automation_helper.create_cooking_session_automation(
                        device_ids=data['device_ids'],
                        session_name=data.get('session_name', 'Grilling Session'),
                        start_temperature_threshold=data.get('start_temperature_threshold', 80.0),
                        end_temperature_threshold=data.get('end_temperature_threshold', 60.0)
                    )
                else:
                    return jsonify({"error": f"Unknown automation type: {automation_type}"}), 400
                
                if not automation_id:
                    return jsonify({"error": "Failed to create automation"}), 500
                
                # Deploy to Home Assistant if requested
                if data.get('deploy', False):
                    deploy_success = await self.automation_helper.deploy_automation_to_ha(automation_id)
                    if not deploy_success:
                        logger.warning(f"Failed to deploy automation {automation_id} to HA")
                
                return jsonify({
                    "status": "success",
                    "automation_id": automation_id,
                    "message": "Automation created successfully"
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to create automation: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/automation/<automation_id>', methods=['GET'])
        def get_automation(automation_id: str):
            try:
                automation = self.automation_helper.get_automation(automation_id)
                if not automation:
                    return jsonify({"error": "Automation not found"}), 404
                
                return jsonify({
                    "id": automation.id,
                    "alias": automation.alias,
                    "description": automation.description,
                    "enabled": automation.enabled,
                    "mode": automation.mode,
                    "trigger_count": len(automation.trigger),
                    "condition_count": len(automation.condition),
                    "action_count": len(automation.action)
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to get automation: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/automation', methods=['GET'])
        def list_automations():
            try:
                automations = self.automation_helper.list_automations()
                
                automations_data = []
                for automation_id, automation in automations.items():
                    automations_data.append({
                        "id": automation.id,
                        "alias": automation.alias,
                        "description": automation.description,
                        "enabled": automation.enabled,
                        "mode": automation.mode
                    })
                
                return jsonify({
                    "automations": automations_data,
                    "count": len(automations_data)
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to list automations: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/metrics', methods=['GET'])
        def get_metrics():
            try:
                ha_metrics = self.ha_client.get_metrics()
                sync_stats = self.state_sync.get_sync_stats()
                automation_stats = self.automation_helper.get_automation_stats()
                discovery_stats = self.discovery_service.get_discovery_stats()
                registry_stats = self.entity_manager.get_registry_stats()
                
                return jsonify({
                    "timestamp": datetime.utcnow().isoformat(),
                    "home_assistant": ha_metrics,
                    "state_sync": sync_stats,
                    "automations": automation_stats,
                    "discovery": discovery_stats,
                    "entity_registry": registry_stats
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to get metrics: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/api/v1/status', methods=['GET'])
        def get_status():
            try:
                ha_health = self.ha_client.get_health_status()
                health_status = self.health_monitor.get_health_status()
                
                return jsonify({
                    "service_status": "running",
                    "home_assistant_connection": {
                        "status": ha_health.status.value,
                        "last_successful_connection": ha_health.last_successful_connection.isoformat() if ha_health.last_successful_connection else None,
                        "response_time_ms": ha_health.response_time_ms,
                        "uptime_percentage": ha_health.uptime_percentage
                    },
                    "health_monitoring": health_status,
                    "timestamp": datetime.utcnow().isoformat()
                }), 200
                
            except Exception as e:
                logger.error(f"Failed to get status: {e}")
                return jsonify({"error": str(e)}), 500

        @app.errorhandler(404)
        def not_found(error):
            return jsonify({"error": "Endpoint not found"}), 404

        @app.errorhandler(500)
        def internal_error(error):
            return jsonify({"error": "Internal server error"}), 500