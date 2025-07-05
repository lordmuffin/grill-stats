import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import json
import redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models.alert_models import Alert, NotificationChannel
from ..models.notification_models import NotificationHistory, NotificationStatus, NotificationPriority
from .email_channel import EmailChannel
from .sms_channel import SMSChannel
from .push_channel import PushChannel
from .webhook_channel import WebhookChannel
from .slack_channel import SlackChannel
from .discord_channel import DiscordChannel

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Central notification manager that coordinates all notification channels.
    
    Features:
    - Multi-channel support (email, SMS, push, webhooks)
    - Priority-based routing
    - Delivery tracking and retry logic
    - Rate limiting and quota management
    - Template-based notifications
    - Batch processing
    
    Target: <30 second delivery, 98% delivery rate
    """
    
    def __init__(self, db_session: AsyncSession, redis_client: redis.Redis, config: Dict[str, Any]):
        self.db = db_session
        self.redis = redis_client
        self.config = config
        
        # Initialize notification channels
        self.channels = {
            'email': EmailChannel(config.get('email', {})),
            'sms': SMSChannel(config.get('sms', {})),
            'push': PushChannel(config.get('push', {})),
            'webhook': WebhookChannel(config.get('webhook', {})),
            'slack': SlackChannel(config.get('slack', {})),
            'discord': DiscordChannel(config.get('discord', {}))
        }
        
        # Notification queue management
        self.notification_queue = asyncio.Queue()
        self.processing_tasks = []
        
        # Performance metrics
        self.metrics = {
            'notifications_sent': 0,
            'notifications_delivered': 0,
            'notifications_failed': 0,
            'delivery_times': [],
            'channel_performance': {}
        }
        
        # Rate limiting configuration
        self.rate_limits = {
            'email': {'per_minute': 100, 'per_hour': 1000},
            'sms': {'per_minute': 10, 'per_hour': 100},
            'push': {'per_minute': 1000, 'per_hour': 10000},
            'webhook': {'per_minute': 200, 'per_hour': 2000},
            'slack': {'per_minute': 50, 'per_hour': 500},
            'discord': {'per_minute': 50, 'per_hour': 500}
        }
        
        # Start background processors
        self._start_background_processors()
    
    async def send_notification(
        self,
        alert: Alert,
        channel_type: str,
        priority: str = 'normal',
        template_variables: Optional[Dict[str, Any]] = None,
        delay_seconds: int = 0
    ) -> Dict[str, Any]:
        """
        Send notification through specified channel.
        
        Args:
            alert: Alert object to send notification for
            channel_type: Type of notification channel
            priority: Notification priority (low, normal, high, urgent)
            template_variables: Variables for template rendering
            delay_seconds: Delay before sending notification
            
        Returns:
            Dictionary with notification result
        """
        try:
            # Validate channel type
            if channel_type not in self.channels:
                raise ValueError(f"Unsupported channel type: {channel_type}")
            
            # Check rate limits
            if not await self._check_rate_limit(channel_type):
                return {
                    'status': 'failed',
                    'error': 'Rate limit exceeded',
                    'channel': channel_type
                }
            
            # Get notification channels for this type
            channels = await self._get_notification_channels(channel_type)
            
            if not channels:
                return {
                    'status': 'failed',
                    'error': 'No configured channels found',
                    'channel': channel_type
                }
            
            # Create notification history record
            notification = NotificationHistory(
                alert_id=alert.id,
                channel_id=channels[0].id,
                channel_type=channel_type,
                recipient=self._get_default_recipient(channels[0]),
                priority=priority,
                status=NotificationStatus.PENDING
            )
            
            self.db.add(notification)
            await self.db.commit()
            
            # Prepare notification data
            notification_data = await self._prepare_notification_data(
                alert, channels[0], template_variables
            )
            
            # Add to queue with priority
            queue_item = {
                'notification_id': notification.id,
                'alert': alert,
                'channel': channels[0],
                'channel_type': channel_type,
                'priority': priority,
                'data': notification_data,
                'delay_seconds': delay_seconds,
                'created_at': datetime.utcnow()
            }
            
            await self.notification_queue.put(queue_item)
            
            return {
                'status': 'queued',
                'notification_id': notification.id,
                'channel': channel_type,
                'estimated_delivery': datetime.utcnow() + timedelta(seconds=delay_seconds + 10)
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return {
                'status': 'failed',
                'error': str(e),
                'channel': channel_type
            }
    
    async def send_bulk_notifications(
        self,
        alerts: List[Alert],
        channel_types: List[str],
        priority: str = 'normal',
        template_variables: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Send notifications for multiple alerts across multiple channels."""
        results = []
        
        for alert in alerts:
            for channel_type in channel_types:
                result = await self.send_notification(
                    alert=alert,
                    channel_type=channel_type,
                    priority=priority,
                    template_variables=template_variables
                )
                results.append(result)
        
        return results
    
    async def _get_notification_channels(self, channel_type: str) -> List[NotificationChannel]:
        """Get configured notification channels for a type."""
        result = await self.db.execute(
            select(NotificationChannel)
            .where(and_(
                NotificationChannel.type == channel_type,
                NotificationChannel.enabled == True
            ))
        )
        
        return result.scalars().all()
    
    def _get_default_recipient(self, channel: NotificationChannel) -> str:
        """Get default recipient for a channel."""
        config = channel.configuration
        
        if channel.type == 'email':
            return config.get('recipients', ['admin@example.com'])[0]
        elif channel.type == 'sms':
            return config.get('to_numbers', ['+1234567890'])[0]
        elif channel.type == 'push':
            return config.get('default_topic', 'alerts')
        elif channel.type in ['webhook', 'slack', 'discord']:
            return config.get('url', 'webhook')
        
        return 'unknown'
    
    async def _prepare_notification_data(
        self,
        alert: Alert,
        channel: NotificationChannel,
        template_variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare notification data for sending."""
        # Get template for the channel
        template = await self._get_notification_template(channel)
        
        # Prepare template variables
        variables = {
            'alert': {
                'id': alert.id,
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity,
                'source': alert.source,
                'status': alert.status,
                'created_at': alert.created_at.isoformat(),
                'labels': alert.labels or {},
                'annotations': alert.annotations or {}
            },
            'timestamp': datetime.utcnow().isoformat(),
            'dashboard_url': self.config.get('dashboard_url', 'http://localhost:3000'),
            **(template_variables or {})
        }
        
        # Render templates
        subject = self._render_template(template.get('subject', ''), variables)
        body = self._render_template(template.get('body', ''), variables)
        
        return {
            'subject': subject,
            'body': body,
            'variables': variables,
            'channel_config': channel.configuration
        }
    
    async def _get_notification_template(self, channel: NotificationChannel) -> Dict[str, str]:
        """Get notification template for channel."""
        # Try to get custom template from database
        # For now, return default templates
        
        templates = {
            'email': {
                'subject': 'Alert: {{alert.title}}',
                'body': '''
Alert Details:
- ID: {{alert.id}}
- Title: {{alert.title}}
- Description: {{alert.description}}
- Severity: {{alert.severity}}
- Source: {{alert.source}}
- Status: {{alert.status}}
- Created: {{alert.created_at}}

View in dashboard: {{dashboard_url}}/alerts/{{alert.id}}
'''
            },
            'sms': {
                'subject': '',
                'body': 'ALERT: {{alert.title}} ({{alert.severity}}) - {{alert.source}}'
            },
            'push': {
                'subject': 'Alert: {{alert.title}}',
                'body': '{{alert.description}} ({{alert.severity}})'
            },
            'webhook': {
                'subject': 'Alert Notification',
                'body': '''
{
    "alert": {
        "id": "{{alert.id}}",
        "title": "{{alert.title}}",
        "description": "{{alert.description}}",
        "severity": "{{alert.severity}}",
        "source": "{{alert.source}}",
        "status": "{{alert.status}}",
        "created_at": "{{alert.created_at}}",
        "labels": {{alert.labels}},
        "annotations": {{alert.annotations}}
    },
    "timestamp": "{{timestamp}}",
    "dashboard_url": "{{dashboard_url}}/alerts/{{alert.id}}"
}
'''
            },
            'slack': {
                'subject': 'Alert Notification',
                'body': '''
{
    "text": "Alert: {{alert.title}}",
    "attachments": [
        {
            "color": "{% if alert.severity == 'critical' %}danger{% elif alert.severity == 'high' %}warning{% else %}good{% endif %}",
            "fields": [
                {
                    "title": "Description",
                    "value": "{{alert.description}}",
                    "short": false
                },
                {
                    "title": "Severity",
                    "value": "{{alert.severity}}",
                    "short": true
                },
                {
                    "title": "Source",
                    "value": "{{alert.source}}",
                    "short": true
                },
                {
                    "title": "Status",
                    "value": "{{alert.status}}",
                    "short": true
                }
            ],
            "actions": [
                {
                    "type": "button",
                    "text": "View Alert",
                    "url": "{{dashboard_url}}/alerts/{{alert.id}}"
                }
            ]
        }
    ]
}
'''
            },
            'discord': {
                'subject': 'Alert Notification',
                'body': '''
{
    "embeds": [
        {
            "title": "Alert: {{alert.title}}",
            "description": "{{alert.description}}",
            "color": {% if alert.severity == 'critical' %}15158332{% elif alert.severity == 'high' %}16776960{% else %}3066993{% endif %},
            "fields": [
                {
                    "name": "Severity",
                    "value": "{{alert.severity}}",
                    "inline": true
                },
                {
                    "name": "Source",
                    "value": "{{alert.source}}",
                    "inline": true
                },
                {
                    "name": "Status",
                    "value": "{{alert.status}}",
                    "inline": true
                }
            ],
            "timestamp": "{{timestamp}}",
            "footer": {
                "text": "Alert ID: {{alert.id}}"
            }
        }
    ]
}
'''
            }
        }
        
        return templates.get(channel.type, templates['email'])
    
    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Render template with variables (simple implementation)."""
        import re
        
        # Simple template rendering - replace {{variable}} with value
        def replace_var(match):
            var_path = match.group(1)
            value = variables
            
            for key in var_path.split('.'):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return match.group(0)  # Return original if not found
            
            return str(value)
        
        return re.sub(r'{{([^}]+)}}', replace_var, template)
    
    async def _check_rate_limit(self, channel_type: str) -> bool:
        """Check if notification is within rate limits."""
        if channel_type not in self.rate_limits:
            return True
        
        limits = self.rate_limits[channel_type]
        
        # Check per-minute limit
        minute_key = f"rate_limit:{channel_type}:minute:{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
        minute_count = await self.redis.incr(minute_key)
        await self.redis.expire(minute_key, 60)
        
        if minute_count > limits['per_minute']:
            return False
        
        # Check per-hour limit
        hour_key = f"rate_limit:{channel_type}:hour:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
        hour_count = await self.redis.incr(hour_key)
        await self.redis.expire(hour_key, 3600)
        
        if hour_count > limits['per_hour']:
            return False
        
        return True
    
    def _start_background_processors(self):
        """Start background processors for notification queue."""
        # Start multiple processors for different priorities
        priorities = ['urgent', 'high', 'normal', 'low']
        
        for priority in priorities:
            task = asyncio.create_task(self._process_notification_queue(priority))
            self.processing_tasks.append(task)
        
        # Start delivery status checker
        status_task = asyncio.create_task(self._check_delivery_status())
        self.processing_tasks.append(status_task)
    
    async def _process_notification_queue(self, priority: str):
        """Process notification queue for specific priority."""
        while True:
            try:
                # Get notification from queue
                notification_item = await self.notification_queue.get()
                
                # Check if this processor should handle this priority
                if notification_item['priority'] != priority:
                    # Put back in queue for appropriate processor
                    await self.notification_queue.put(notification_item)
                    await asyncio.sleep(0.1)
                    continue
                
                # Apply delay if specified
                if notification_item['delay_seconds'] > 0:
                    await asyncio.sleep(notification_item['delay_seconds'])
                
                # Process notification
                await self._process_single_notification(notification_item)
                
            except Exception as e:
                logger.error(f"Error processing notification queue: {str(e)}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _process_single_notification(self, notification_item: Dict[str, Any]):
        """Process a single notification."""
        start_time = datetime.utcnow()
        
        try:
            notification_id = notification_item['notification_id']
            channel_type = notification_item['channel_type']
            channel = notification_item['channel']
            data = notification_item['data']
            
            # Get notification record
            notification = await self.db.get(NotificationHistory, notification_id)
            if not notification:
                logger.error(f"Notification record {notification_id} not found")
                return
            
            # Update status to sending
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            notification.attempts += 1
            
            # Send through appropriate channel
            channel_handler = self.channels[channel_type]
            result = await channel_handler.send(
                recipient=notification.recipient,
                subject=data['subject'],
                body=data['body'],
                channel_config=data['channel_config']
            )
            
            # Update notification record
            if result['success']:
                notification.status = NotificationStatus.DELIVERED
                notification.delivered_at = datetime.utcnow()
                self.metrics['notifications_delivered'] += 1
            else:
                notification.status = NotificationStatus.FAILED
                notification.failed_at = datetime.utcnow()
                notification.error_message = result.get('error', 'Unknown error')
                self.metrics['notifications_failed'] += 1
            
            notification.response_data = result
            
            # Update subject and body
            notification.subject = data['subject']
            notification.body = data['body']
            
            await self.db.commit()
            
            # Update metrics
            delivery_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics['delivery_times'].append(delivery_time)
            self.metrics['notifications_sent'] += 1
            
            # Update channel performance
            if channel_type not in self.metrics['channel_performance']:
                self.metrics['channel_performance'][channel_type] = {
                    'sent': 0, 'delivered': 0, 'failed': 0
                }
            
            self.metrics['channel_performance'][channel_type]['sent'] += 1
            if result['success']:
                self.metrics['channel_performance'][channel_type]['delivered'] += 1
            else:
                self.metrics['channel_performance'][channel_type]['failed'] += 1
            
            # Retry logic for failed notifications
            if not result['success'] and notification.attempts < notification.max_attempts:
                await self._schedule_retry(notification_item)
            
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}", exc_info=True)
    
    async def _schedule_retry(self, notification_item: Dict[str, Any]):
        """Schedule retry for failed notification."""
        # Exponential backoff
        delay = min(300, 30 * (2 ** notification_item.get('retry_count', 0)))  # Max 5 min
        
        # Add retry information
        notification_item['retry_count'] = notification_item.get('retry_count', 0) + 1
        notification_item['delay_seconds'] = delay
        
        # Put back in queue
        await asyncio.sleep(delay)
        await self.notification_queue.put(notification_item)
    
    async def _check_delivery_status(self):
        """Background task to check delivery status for push notifications."""
        while True:
            try:
                # Check pending notifications older than 5 minutes
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                
                result = await self.db.execute(
                    select(NotificationHistory)
                    .where(and_(
                        NotificationHistory.status == NotificationStatus.SENT,
                        NotificationHistory.sent_at < cutoff_time
                    ))
                    .limit(100)
                )
                
                pending_notifications = result.scalars().all()
                
                for notification in pending_notifications:
                    # Check delivery status with the channel
                    channel_handler = self.channels[notification.channel_type]
                    
                    if hasattr(channel_handler, 'check_delivery_status'):
                        status = await channel_handler.check_delivery_status(
                            notification.id,
                            notification.response_data
                        )
                        
                        if status == 'delivered':
                            notification.status = NotificationStatus.DELIVERED
                            notification.delivered_at = datetime.utcnow()
                        elif status == 'failed':
                            notification.status = NotificationStatus.FAILED
                            notification.failed_at = datetime.utcnow()
                        
                        await self.db.commit()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking delivery status: {str(e)}", exc_info=True)
                await asyncio.sleep(60)
    
    async def get_notification_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        delivery_times = self.metrics['delivery_times']
        
        stats = {
            'total_sent': self.metrics['notifications_sent'],
            'total_delivered': self.metrics['notifications_delivered'],
            'total_failed': self.metrics['notifications_failed'],
            'delivery_rate': (
                self.metrics['notifications_delivered'] / 
                max(self.metrics['notifications_sent'], 1)
            ),
            'channel_performance': self.metrics['channel_performance']
        }
        
        if delivery_times:
            stats.update({
                'average_delivery_time': sum(delivery_times) / len(delivery_times),
                'max_delivery_time': max(delivery_times),
                'min_delivery_time': min(delivery_times),
                'p95_delivery_time': sorted(delivery_times)[int(len(delivery_times) * 0.95)],
                'p99_delivery_time': sorted(delivery_times)[int(len(delivery_times) * 0.99)]
            })
        
        return stats
    
    async def get_notification_history(
        self,
        alert_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[NotificationHistory]:
        """Get notification history with filters."""
        query = select(NotificationHistory)
        
        conditions = []
        if alert_id:
            conditions.append(NotificationHistory.alert_id == alert_id)
        if channel_type:
            conditions.append(NotificationHistory.channel_type == channel_type)
        if status:
            conditions.append(NotificationHistory.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(NotificationHistory.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def retry_failed_notification(self, notification_id: int) -> Dict[str, Any]:
        """Retry a failed notification."""
        notification = await self.db.get(NotificationHistory, notification_id)
        
        if not notification:
            return {'success': False, 'error': 'Notification not found'}
        
        if notification.status != NotificationStatus.FAILED:
            return {'success': False, 'error': 'Notification is not in failed state'}
        
        # Reset notification for retry
        notification.status = NotificationStatus.PENDING
        notification.attempts = 0
        notification.error_message = None
        
        await self.db.commit()
        
        # Get original alert
        alert = await self.db.get(Alert, notification.alert_id)
        if not alert:
            return {'success': False, 'error': 'Alert not found'}
        
        # Resend notification
        result = await self.send_notification(
            alert=alert,
            channel_type=notification.channel_type,
            priority='normal'
        )
        
        return {'success': True, 'result': result}
    
    async def cleanup_old_notifications(self, days: int = 30):
        """Clean up old notification history."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(NotificationHistory)
            .where(NotificationHistory.created_at < cutoff_date)
        )
        
        old_notifications = result.scalars().all()
        
        for notification in old_notifications:
            await self.db.delete(notification)
        
        await self.db.commit()
        
        return len(old_notifications)