"""
Alert Monitoring Service

This service continuously monitors temperature data from all connected probes
and triggers notifications when user-defined alert conditions are met.
"""

import logging
import json
import time
from datetime import datetime, timedelta
from threading import Thread, Event
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class AlertMonitor:
    """Background service for monitoring temperature alerts"""
    
    def __init__(self, app, alert_manager, socketio=None, notification_system=None):
        self.app = app
        self.alert_manager = alert_manager
        self.socketio = socketio
        self.notification_system = notification_system
        self.running = False
        self.stop_event = Event()
        self.monitor_thread = None
        self.check_interval = 15  # Check every 15 seconds
        self.redis_client = None
        self.last_check_time = None
        
        # Initialize Redis client for caching
        self._init_redis()
        
    def _init_redis(self):
        """Initialize Redis client if available"""
        try:
            import redis
            import os
            
            self.redis_client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", 6379)),
                password=os.environ.get("REDIS_PASSWORD", None),
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established for alert monitoring")
            
        except (ImportError, Exception) as e:
            logger.warning(f"Redis not available for alert monitoring: {e}")
            self.redis_client = None
    
    def start(self):
        """Start the alert monitoring service"""
        if self.running:
            logger.warning("Alert monitor is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Alert monitoring service started")
    
    def stop(self):
        """Stop the alert monitoring service"""
        if not self.running:
            return
        
        logger.info("Stopping alert monitoring service...")
        self.running = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("Alert monitoring service stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop that runs in a separate thread"""
        logger.info("Alert monitoring loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                with self.app.app_context():
                    self._check_all_alerts()
                    self.last_check_time = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
            
            # Wait for next check interval or stop event
            self.stop_event.wait(self.check_interval)
        
        logger.info("Alert monitoring loop ended")
    
    def _check_all_alerts(self):
        """Check all active alerts against current temperature data"""
        try:
            # Get all active alerts
            active_alerts = self.alert_manager.get_active_alerts()
            
            if not active_alerts:
                logger.debug("No active alerts to check")
                return
            
            logger.debug(f"Checking {len(active_alerts)} active alerts")
            
            # Group alerts by device/probe for efficient temperature fetching
            device_probe_alerts = {}
            for alert in active_alerts:
                key = (alert.device_id, alert.probe_id)
                if key not in device_probe_alerts:
                    device_probe_alerts[key] = []
                device_probe_alerts[key].append(alert)
            
            # Check each device/probe combination
            for (device_id, probe_id), alerts in device_probe_alerts.items():
                try:
                    current_temp = self._get_current_temperature(device_id, probe_id)
                    
                    if current_temp is not None:
                        self._check_alerts_for_temperature(alerts, current_temp)
                    else:
                        logger.debug(f"No temperature data available for {device_id}/{probe_id}")
                
                except Exception as e:
                    logger.error(f"Error checking alerts for {device_id}/{probe_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in _check_all_alerts: {e}")
    
    def _get_current_temperature(self, device_id: str, probe_id: str) -> Optional[float]:
        """Get current temperature for a specific device/probe"""
        try:
            # First try to get from Redis cache (fastest)
            if self.redis_client:
                cache_key = f"temperature:latest:{device_id}:{probe_id}"
                cached_data = self.redis_client.get(cache_key)
                
                if cached_data:
                    try:
                        data = json.loads(cached_data)
                        # Check if data is recent (within last 5 minutes)
                        timestamp = data.get('timestamp')
                        if timestamp:
                            data_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            if (datetime.utcnow() - data_time.replace(tzinfo=None)) < timedelta(minutes=5):
                                temperature = data.get('temperature')
                                if temperature is not None:
                                    logger.debug(f"Got cached temperature for {device_id}/{probe_id}: {temperature}")
                                    return float(temperature)
                    except (json.JSONDecodeError, ValueError, KeyError) as e:
                        logger.debug(f"Error parsing cached temperature data: {e}")
            
            # Try device service API
            try:
                device_service_url = self.app.config.get('DEVICE_SERVICE_URL', 'http://localhost:8080')
                response = requests.get(
                    f"{device_service_url}/api/devices/{device_id}/probes/{probe_id}/temperature",
                    timeout=2
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'temperature' in data.get('data', {}):
                        temperature = data['data']['temperature']
                        logger.debug(f"Got temperature from device service for {device_id}/{probe_id}: {temperature}")
                        return float(temperature)
            
            except requests.RequestException as e:
                logger.debug(f"Device service not available: {e}")
            
            # Try ThermoWorks client (fallback)
            try:
                from thermoworks_client import ThermoWorksClient
                
                thermoworks_client = ThermoWorksClient(
                    api_key=self.app.config.get('THERMOWORKS_API_KEY'),
                    mock_mode=self.app.config.get('MOCK_MODE', False)
                )
                
                temp_data = thermoworks_client.get_temperature_data(device_id)
                if temp_data and 'temperature' in temp_data:
                    temperature = temp_data['temperature']
                    logger.debug(f"Got temperature from ThermoWorks for {device_id}: {temperature}")
                    return float(temperature)
            
            except Exception as e:
                logger.debug(f"ThermoWorks client not available: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting temperature for {device_id}/{probe_id}: {e}")
            return None
    
    def _check_alerts_for_temperature(self, alerts: List, current_temperature: float):
        """Check a list of alerts against the current temperature"""
        for alert in alerts:
            try:
                # Update the alert with current temperature
                alert.update_temperature(current_temperature)
                
                # Check if alert should trigger
                should_trigger = alert.should_trigger(current_temperature)
                
                if should_trigger:
                    # Check if we've already sent a notification for this trigger
                    if not alert.notification_sent:
                        logger.info(f"Alert {alert.id} triggered: {alert.name} - {current_temperature}°{alert.temperature_unit}")
                        
                        # Mark alert as triggered
                        alert.trigger_alert()
                        
                        # Send notification
                        self._send_notification(alert, current_temperature)
                        
                        # Mark notification as sent
                        alert.mark_notification_sent()
                        
                        # Commit changes to database
                        self.alert_manager.db.session.commit()
                
                else:
                    # Reset notification flag if condition is no longer met
                    if alert.notification_sent and not should_trigger:
                        alert.notification_sent = False
                        self.alert_manager.db.session.commit()
                
            except Exception as e:
                logger.error(f"Error checking alert {alert.id}: {e}")
                # Rollback any partial changes
                try:
                    self.alert_manager.db.session.rollback()
                except:
                    pass
    
    def _send_notification(self, alert, current_temperature: float):
        """Send notification for a triggered alert"""
        try:
            notification_data = {
                'alert_id': alert.id,
                'alert_name': alert.name or f"Alert {alert.id}",
                'device_id': alert.device_id,
                'probe_id': alert.probe_id,
                'alert_type': alert.alert_type.value,
                'current_temperature': current_temperature,
                'temperature_unit': alert.temperature_unit,
                'target_temperature': alert.target_temperature,
                'min_temperature': alert.min_temperature,
                'max_temperature': alert.max_temperature,
                'threshold_value': alert.threshold_value,
                'triggered_at': alert.triggered_at.isoformat() if alert.triggered_at else None,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Create notification message based on alert type
            message = self._create_notification_message(alert, current_temperature)
            notification_data['message'] = message
            
            # Send through notification system if available
            if self.notification_system:
                self.notification_system.send_notification(
                    user_id=alert.user_id,
                    notification_type='temperature_alert',
                    data=notification_data
                )
            
            # Send real-time notification via WebSocket
            if self.socketio:
                try:
                    user_room = f"user_{alert.user_id}"
                    self.socketio.emit('notification', notification_data, room=user_room)
                    logger.info(f"Real-time notification sent via WebSocket to user {alert.user_id}")
                except Exception as e:
                    logger.error(f"Error sending WebSocket notification: {e}")
            
            # Cache notification in Redis for real-time UI updates
            if self.redis_client:
                try:
                    notification_key = f"notification:alert:{alert.user_id}:{alert.id}:{int(time.time())}"
                    self.redis_client.setex(
                        notification_key,
                        timedelta(hours=1),  # Expire after 1 hour
                        json.dumps(notification_data)
                    )
                    
                    # Also update a user-specific latest notifications list
                    user_notifications_key = f"notifications:user:{alert.user_id}:latest"
                    self.redis_client.lpush(user_notifications_key, json.dumps(notification_data))
                    self.redis_client.ltrim(user_notifications_key, 0, 9)  # Keep only latest 10
                    self.redis_client.expire(user_notifications_key, timedelta(hours=24))
                    
                except Exception as e:
                    logger.error(f"Error caching notification: {e}")
            
            logger.info(f"Notification sent for alert {alert.id}: {message}")
            
        except Exception as e:
            logger.error(f"Error sending notification for alert {alert.id}: {e}")
    
    def _create_notification_message(self, alert, current_temperature: float) -> str:
        """Create a human-readable notification message"""
        temp_str = f"{current_temperature}°{alert.temperature_unit}"
        probe_name = f"{alert.device_id}/{alert.probe_id}"
        
        if alert.alert_type.value == 'target':
            return f"🎯 Target reached! {probe_name} is now {temp_str} (target: {alert.target_temperature}°{alert.temperature_unit})"
        
        elif alert.alert_type.value == 'range':
            if current_temperature < alert.min_temperature:
                return f"🥶 Temperature too low! {probe_name} is {temp_str} (below {alert.min_temperature}°{alert.temperature_unit})"
            else:
                return f"🔥 Temperature too high! {probe_name} is {temp_str} (above {alert.max_temperature}°{alert.temperature_unit})"
        
        elif alert.alert_type.value == 'rising':
            return f"📈 Temperature rising! {probe_name} increased to {temp_str} (+{alert.threshold_value}°{alert.temperature_unit})"
        
        elif alert.alert_type.value == 'falling':
            return f"📉 Temperature dropping! {probe_name} dropped to {temp_str} (-{alert.threshold_value}°{alert.temperature_unit})"
        
        return f"🚨 Alert triggered! {probe_name} is {temp_str}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the alert monitoring service"""
        return {
            'running': self.running,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'check_interval': self.check_interval,
            'redis_available': self.redis_client is not None,
            'active_alerts_count': len(self.alert_manager.get_active_alerts()) if self.running else 0
        }
    
    def trigger_immediate_check(self):
        """Trigger an immediate check of all alerts (useful for testing)"""
        if not self.running:
            logger.warning("Alert monitor is not running")
            return False
        
        try:
            with self.app.app_context():
                self._check_all_alerts()
                return True
        except Exception as e:
            logger.error(f"Error in immediate alert check: {e}")
            return False