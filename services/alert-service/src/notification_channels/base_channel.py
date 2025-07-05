from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseNotificationChannel(ABC):
    """Base class for all notification channels."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send notification through this channel.
        
        Args:
            recipient: Recipient identifier (email, phone, etc.)
            subject: Notification subject
            body: Notification body
            channel_config: Channel-specific configuration
            
        Returns:
            Dictionary with success status and additional info
        """
        pass
    
    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate channel configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Dictionary with validation results
        """
        pass
    
    @abstractmethod
    def get_channel_info(self) -> Dict[str, Any]:
        """
        Get channel information and configuration schema.
        
        Returns:
            Dictionary with channel information
        """
        pass
    
    async def check_delivery_status(self, notification_id: int, response_data: Dict[str, Any]) -> str:
        """
        Check delivery status for a notification.
        
        Args:
            notification_id: Notification ID
            response_data: Response data from send operation
            
        Returns:
            Delivery status (delivered, failed, pending)
        """
        # Default implementation - override in subclasses if supported
        return 'delivered'
    
    def is_enabled(self) -> bool:
        """Check if channel is enabled."""
        return self.enabled
    
    def get_rate_limits(self) -> Dict[str, int]:
        """Get rate limits for this channel."""
        return self.config.get('rate_limits', {
            'per_minute': 60,
            'per_hour': 1000,
            'per_day': 10000
        })