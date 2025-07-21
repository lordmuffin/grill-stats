import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from ..models.entity_models import HAAutomation, AutomationTrigger, AutomationCondition, AutomationAction
from ..models.ha_models import HAServiceCall, HAEvent
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class AutomationHelper:
    def __init__(self, ha_client, entity_manager):
        self.ha_client = ha_client
        self.entity_manager = entity_manager
        self.automations: Dict[str, HAAutomation] = {}
        self.triggers: Dict[str, List[Callable]] = {}
        self.metrics = MetricsCollector()

    def create_temperature_alert_automation(
        self,
        device_id: str,
        probe_id: str,
        alert_name: str,
        temperature_threshold: float,
        threshold_type: str = "above",  # "above" or "below"
        notification_title: str = None,
        notification_message: str = None
    ) -> str:
        try:
            automation_id = f"temperature_alert_{device_id}_{probe_id}_{alert_name.lower().replace(' ', '_')}"
            entity_id = f"sensor.grill_stats_{device_id}_{probe_id}_temperature"
            
            # Create trigger
            trigger = AutomationTrigger(
                trigger_type="numeric_state",
                entity_id=entity_id,
                above=temperature_threshold if threshold_type == "above" else None,
                below=temperature_threshold if threshold_type == "below" else None,
                for_duration="00:00:30"  # 30 seconds to avoid false alerts
            )
            
            # Create notification action
            notification_title = notification_title or f"Temperature Alert - {alert_name}"
            notification_message = notification_message or (
                f"Device {device_id} probe {probe_id} temperature is "
                f"{'above' if threshold_type == 'above' else 'below'} {temperature_threshold}°F"
            )
            
            action = AutomationAction(
                action_type="call_service",
                service="notify.persistent_notification",
                service_data={
                    "title": notification_title,
                    "message": notification_message,
                    "notification_id": f"grill_alert_{device_id}_{probe_id}"
                }
            )
            
            # Create automation
            automation = HAAutomation(
                id=automation_id,
                alias=f"Temperature Alert: {alert_name}",
                description=f"Alert when {entity_id} goes {threshold_type} {temperature_threshold}°F",
                trigger=[trigger],
                action=[action]
            )
            
            self.automations[automation_id] = automation
            logger.info(f"Created temperature alert automation: {automation_id}")
            
            return automation_id
            
        except Exception as e:
            logger.error(f"Failed to create temperature alert automation: {e}")
            return ""

    def create_device_offline_automation(
        self,
        device_id: str,
        alert_name: str = "Device Offline",
        offline_duration: str = "00:05:00"  # 5 minutes
    ) -> str:
        try:
            automation_id = f"device_offline_{device_id}"
            entity_id = f"binary_sensor.grill_stats_{device_id}_connection"
            
            # Create trigger for device going offline
            trigger = AutomationTrigger(
                trigger_type="state",
                entity_id=entity_id,
                from_state="on",
                to_state="off",
                for_duration=offline_duration
            )
            
            # Create notification action
            action = AutomationAction(
                action_type="call_service",
                service="notify.persistent_notification",
                service_data={
                    "title": f"Device Offline - {alert_name}",
                    "message": f"Device {device_id} has been offline for {offline_duration}",
                    "notification_id": f"grill_offline_{device_id}"
                }
            )
            
            # Create automation
            automation = HAAutomation(
                id=automation_id,
                alias=f"Device Offline: {device_id}",
                description=f"Alert when device {device_id} goes offline",
                trigger=[trigger],
                action=[action]
            )
            
            self.automations[automation_id] = automation
            logger.info(f"Created device offline automation: {automation_id}")
            
            return automation_id
            
        except Exception as e:
            logger.error(f"Failed to create device offline automation: {e}")
            return ""

    def create_battery_low_automation(
        self,
        device_id: str,
        battery_threshold: int = 20,
        alert_name: str = "Low Battery"
    ) -> str:
        try:
            automation_id = f"battery_low_{device_id}"
            entity_id = f"sensor.grill_stats_{device_id}_battery"
            
            # Create trigger for low battery
            trigger = AutomationTrigger(
                trigger_type="numeric_state",
                entity_id=entity_id,
                below=battery_threshold,
                for_duration="00:01:00"  # 1 minute to avoid false alerts
            )
            
            # Create notification action
            action = AutomationAction(
                action_type="call_service",
                service="notify.persistent_notification",
                service_data={
                    "title": f"Low Battery - {alert_name}",
                    "message": f"Device {device_id} battery is below {battery_threshold}%",
                    "notification_id": f"grill_battery_{device_id}"
                }
            )
            
            # Create automation
            automation = HAAutomation(
                id=automation_id,
                alias=f"Low Battery: {device_id}",
                description=f"Alert when device {device_id} battery is low",
                trigger=[trigger],
                action=[action]
            )
            
            self.automations[automation_id] = automation
            logger.info(f"Created battery low automation: {automation_id}")
            
            return automation_id
            
        except Exception as e:
            logger.error(f"Failed to create battery low automation: {e}")
            return ""

    def create_cooking_session_automation(
        self,
        device_ids: List[str],
        session_name: str = "Grilling Session",
        start_temperature_threshold: float = 80.0,
        end_temperature_threshold: float = 60.0
    ) -> str:
        try:
            automation_id = f"cooking_session_{session_name.lower().replace(' ', '_')}"
            
            # Create triggers for session start (any probe above threshold)
            start_triggers = []
            for device_id in device_ids:
                for probe_id in ["1", "2", "3", "4"]:  # Common probe IDs
                    entity_id = f"sensor.grill_stats_{device_id}_{probe_id}_temperature"
                    start_triggers.append(AutomationTrigger(
                        trigger_type="numeric_state",
                        entity_id=entity_id,
                        above=start_temperature_threshold,
                        for_duration="00:02:00"
                    ))
            
            # Create actions for session start
            start_actions = [
                AutomationAction(
                    action_type="call_service",
                    service="notify.persistent_notification",
                    service_data={
                        "title": f"Cooking Session Started",
                        "message": f"{session_name} has begun - temperature threshold reached",
                        "notification_id": f"session_start_{automation_id}"
                    }
                ),
                AutomationAction(
                    action_type="call_service",
                    service="scene.create",
                    service_data={
                        "scene_id": f"grill_session_{automation_id}",
                        "snapshot_entities": [f"sensor.grill_stats_{device_id}_{probe}_temperature" 
                                            for device_id in device_ids 
                                            for probe in ["1", "2", "3", "4"]]
                    }
                )
            ]
            
            # Create automation
            automation = HAAutomation(
                id=automation_id,
                alias=f"Cooking Session: {session_name}",
                description=f"Automation for {session_name} cooking session",
                trigger=start_triggers,
                action=start_actions
            )
            
            self.automations[automation_id] = automation
            logger.info(f"Created cooking session automation: {automation_id}")
            
            return automation_id
            
        except Exception as e:
            logger.error(f"Failed to create cooking session automation: {e}")
            return ""

    async def deploy_automation_to_ha(self, automation_id: str) -> bool:
        try:
            if automation_id not in self.automations:
                logger.error(f"Automation {automation_id} not found")
                return False
            
            automation = self.automations[automation_id]
            
            # Convert to Home Assistant automation format
            ha_automation = {
                "id": automation.id,
                "alias": automation.alias,
                "description": automation.description,
                "trigger": [self._convert_trigger_to_ha(trigger) for trigger in automation.trigger],
                "condition": [self._convert_condition_to_ha(condition) for condition in automation.condition],
                "action": [self._convert_action_to_ha(action) for action in automation.action],
                "mode": automation.mode
            }
            
            # Send to Home Assistant via service call
            service_call = HAServiceCall(
                domain="automation",
                service="reload",
                service_data={}
            )
            
            # For now, we'll store the automation config and let HA discover it
            # In a full implementation, this would integrate with HA's automation system
            success = self.ha_client.call_service(service_call)
            
            if success:
                logger.info(f"Successfully deployed automation {automation_id} to Home Assistant")
                self.metrics.record_api_call("deploy_automation", True)
            else:
                logger.error(f"Failed to deploy automation {automation_id}")
                self.metrics.record_api_call("deploy_automation", False)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to deploy automation {automation_id}: {e}")
            self.metrics.record_api_call("deploy_automation", False)
            return False

    def _convert_trigger_to_ha(self, trigger: AutomationTrigger) -> Dict[str, Any]:
        ha_trigger = {
            "platform": trigger.trigger_type,
            "entity_id": trigger.entity_id
        }
        
        if trigger.from_state:
            ha_trigger["from"] = trigger.from_state
        if trigger.to_state:
            ha_trigger["to"] = trigger.to_state
        if trigger.above is not None:
            ha_trigger["above"] = trigger.above
        if trigger.below is not None:
            ha_trigger["below"] = trigger.below
        if trigger.for_duration:
            ha_trigger["for"] = trigger.for_duration
            
        return ha_trigger

    def _convert_condition_to_ha(self, condition: AutomationCondition) -> Dict[str, Any]:
        ha_condition = {
            "condition": condition.condition_type,
            "entity_id": condition.entity_id
        }
        
        if condition.state:
            ha_condition["state"] = condition.state
        if condition.above is not None:
            ha_condition["above"] = condition.above
        if condition.below is not None:
            ha_condition["below"] = condition.below
            
        return ha_condition

    def _convert_action_to_ha(self, action: AutomationAction) -> Dict[str, Any]:
        if action.action_type == "call_service":
            return {
                "service": action.service,
                "data": action.service_data or {},
                "target": action.target or {}
            }
        else:
            return {"action": action.action_type}

    def get_automation(self, automation_id: str) -> Optional[HAAutomation]:
        return self.automations.get(automation_id)

    def list_automations(self) -> Dict[str, HAAutomation]:
        return self.automations.copy()

    def remove_automation(self, automation_id: str) -> bool:
        try:
            if automation_id in self.automations:
                del self.automations[automation_id]
                logger.info(f"Removed automation: {automation_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove automation {automation_id}: {e}")
            return False

    def enable_automation(self, automation_id: str) -> bool:
        try:
            if automation_id in self.automations:
                self.automations[automation_id].enabled = True
                logger.info(f"Enabled automation: {automation_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to enable automation {automation_id}: {e}")
            return False

    def disable_automation(self, automation_id: str) -> bool:
        try:
            if automation_id in self.automations:
                self.automations[automation_id].enabled = False
                logger.info(f"Disabled automation: {automation_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to disable automation {automation_id}: {e}")
            return False

    def get_automation_stats(self) -> Dict[str, Any]:
        enabled_count = sum(1 for auto in self.automations.values() if auto.enabled)
        disabled_count = len(self.automations) - enabled_count
        
        return {
            "total_automations": len(self.automations),
            "enabled_automations": enabled_count,
            "disabled_automations": disabled_count,
            "automation_types": self._get_automation_types(),
            "last_updated": datetime.utcnow().isoformat()
        }

    def _get_automation_types(self) -> Dict[str, int]:
        types = {}
        for automation in self.automations.values():
            automation_type = "custom"
            if "temperature_alert" in automation.id:
                automation_type = "temperature_alert"
            elif "device_offline" in automation.id:
                automation_type = "device_offline"
            elif "battery_low" in automation.id:
                automation_type = "battery_low"
            elif "cooking_session" in automation.id:
                automation_type = "cooking_session"
            
            types[automation_type] = types.get(automation_type, 0) + 1
        
        return types


class NotificationHelper:
    def __init__(self, ha_client):
        self.ha_client = ha_client
        self.notification_channels = {
            "persistent": "notify.persistent_notification",
            "mobile": "notify.mobile_app",
            "email": "notify.email",
            "sms": "notify.sms"
        }

    async def send_temperature_alert(
        self,
        device_id: str,
        probe_id: str,
        current_temp: float,
        threshold_temp: float,
        threshold_type: str,
        channels: List[str] = None
    ) -> bool:
        try:
            channels = channels or ["persistent"]
            
            title = f"Temperature Alert - Device {device_id}"
            message = (
                f"Probe {probe_id} temperature is {current_temp}°F "
                f"({'above' if threshold_type == 'above' else 'below'} threshold of {threshold_temp}°F)"
            )
            
            success_count = 0
            for channel in channels:
                if channel in self.notification_channels:
                    service_call = HAServiceCall(
                        domain="notify",
                        service=self.notification_channels[channel].split('.')[1],
                        service_data={
                            "title": title,
                            "message": message,
                            "data": {
                                "device_id": device_id,
                                "probe_id": probe_id,
                                "current_temp": current_temp,
                                "threshold_temp": threshold_temp,
                                "alert_type": "temperature"
                            }
                        }
                    )
                    
                    if self.ha_client.call_service(service_call):
                        success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send temperature alert: {e}")
            return False

    async def send_device_status_notification(
        self,
        device_id: str,
        status: str,
        channels: List[str] = None
    ) -> bool:
        try:
            channels = channels or ["persistent"]
            
            title = f"Device Status - {device_id}"
            message = f"Device {device_id} is now {status}"
            
            success_count = 0
            for channel in channels:
                if channel in self.notification_channels:
                    service_call = HAServiceCall(
                        domain="notify",
                        service=self.notification_channels[channel].split('.')[1],
                        service_data={
                            "title": title,
                            "message": message,
                            "data": {
                                "device_id": device_id,
                                "status": status,
                                "alert_type": "device_status"
                            }
                        }
                    )
                    
                    if self.ha_client.call_service(service_call):
                        success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send device status notification: {e}")
            return False


class SceneHelper:
    def __init__(self, ha_client, entity_manager):
        self.ha_client = ha_client
        self.entity_manager = entity_manager

    async def create_cooking_scene(self, scene_name: str, device_ids: List[str]) -> bool:
        try:
            # Get current state of all grill entities
            entities_state = {}
            
            for device_id in device_ids:
                device_entities = self.entity_manager.get_entities_by_device(device_id)
                for entity in device_entities:
                    entities_state[entity.entity_id] = {
                        "state": entity.state,
                        "attributes": entity.attributes
                    }
            
            # Create scene
            service_call = HAServiceCall(
                domain="scene",
                service="create",
                service_data={
                    "scene_id": f"grill_{scene_name.lower().replace(' ', '_')}",
                    "entities": entities_state
                }
            )
            
            success = self.ha_client.call_service(service_call)
            
            if success:
                logger.info(f"Created cooking scene: {scene_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to create cooking scene {scene_name}: {e}")
            return False

    async def activate_scene(self, scene_id: str) -> bool:
        try:
            service_call = HAServiceCall(
                domain="scene",
                service="turn_on",
                target={"entity_id": f"scene.{scene_id}"}
            )
            
            success = self.ha_client.call_service(service_call)
            
            if success:
                logger.info(f"Activated scene: {scene_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to activate scene {scene_id}: {e}")
            return False