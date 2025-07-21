import asyncio
import logging
import os
import sys
from flask import Flask
from datetime import datetime
import redis
from dotenv import load_dotenv

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.models.ha_models import HAConfig
from src.services.ha_client import HomeAssistantClient
from src.services.entity_manager import EntityManager
from src.services.state_sync import StateSynchronizer
from src.services.discovery_service import DiscoveryService
from src.utils.automation_helpers import AutomationHelper, NotificationHelper, SceneHelper
from src.utils.health_monitor import HealthMonitor
from src.api.routes import HomeAssistantAPI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/homeassistant-service.log', 'a')
    ]
)

logger = logging.getLogger(__name__)


class HomeAssistantService:
    def __init__(self):
        self.app = Flask(__name__)
        self.config = self._load_config()
        self.redis_client = self._setup_redis()
        
        # Initialize components
        self.ha_client = HomeAssistantClient(
            self.config,
            mock_mode=os.getenv('MOCK_MODE', 'false').lower() == 'true'
        )
        
        self.entity_manager = EntityManager(
            self.ha_client,
            self.config.entity_prefix
        )
        
        self.state_sync = StateSynchronizer(
            self.ha_client,
            self.entity_manager,
            self.redis_client,
            sync_interval=int(os.getenv('SYNC_INTERVAL', '30')),
            throttle_interval=int(os.getenv('THROTTLE_INTERVAL', '5')),
            batch_size=int(os.getenv('BATCH_SIZE', '10'))
        )
        
        self.discovery_service = DiscoveryService(
            self.ha_client,
            self.config
        )
        
        self.automation_helper = AutomationHelper(
            self.ha_client,
            self.entity_manager
        )
        
        self.notification_helper = NotificationHelper(self.ha_client)
        self.scene_helper = SceneHelper(self.ha_client, self.entity_manager)
        
        self.health_monitor = HealthMonitor(
            self.ha_client,
            self.entity_manager,
            self.state_sync,
            self.discovery_service
        )
        
        # Setup API routes
        self.api = HomeAssistantAPI(
            self.ha_client,
            self.entity_manager,
            self.state_sync,
            self.discovery_service,
            self.automation_helper,
            self.health_monitor
        )
        self.api.setup_routes(self.app)

    def _load_config(self) -> HAConfig:
        """Load Home Assistant configuration from environment variables"""
        base_url = os.getenv('HOME_ASSISTANT_URL')
        access_token = os.getenv('HOME_ASSISTANT_TOKEN')
        
        if not base_url or not access_token:
            logger.warning("Home Assistant URL or token not provided, running in mock mode")
            base_url = base_url or "http://mock-homeassistant:8123"
            access_token = access_token or "mock-token"
        
        return HAConfig(
            base_url=base_url,
            access_token=access_token,
            verify_ssl=os.getenv('HOME_ASSISTANT_VERIFY_SSL', 'true').lower() == 'true',
            timeout=int(os.getenv('HOME_ASSISTANT_TIMEOUT', '30')),
            retry_attempts=int(os.getenv('HOME_ASSISTANT_RETRY_ATTEMPTS', '3')),
            retry_delay=int(os.getenv('HOME_ASSISTANT_RETRY_DELAY', '5')),
            websocket_enabled=os.getenv('HOME_ASSISTANT_WEBSOCKET_ENABLED', 'true').lower() == 'true',
            entity_prefix=os.getenv('ENTITY_PREFIX', 'grill_stats')
        )

    def _setup_redis(self) -> redis.Redis:
        """Setup Redis connection for caching and state management"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()  # Test connection
            logger.info("Redis connection established")
            return client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, continuing without Redis")
            return None

    async def start(self):
        """Start all service components"""
        try:
            logger.info("Starting Home Assistant Integration Service")
            
            # Test Home Assistant connection
            connection_success = self.ha_client.test_connection()
            if connection_success:
                logger.info("Home Assistant connection successful")
            else:
                logger.warning("Home Assistant connection failed, continuing with limited functionality")
            
            # Connect WebSocket if enabled
            if self.config.websocket_enabled:
                await self.ha_client.connect_websocket()
            
            # Start state synchronization
            await self.state_sync.start()
            
            # Start health monitoring
            await self.health_monitor.start_monitoring()
            
            # Run auto-discovery
            await self.discovery_service.auto_discover_devices()
            
            logger.info("Home Assistant Integration Service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            raise

    async def stop(self):
        """Stop all service components"""
        try:
            logger.info("Stopping Home Assistant Integration Service")
            
            # Stop health monitoring
            await self.health_monitor.stop_monitoring()
            
            # Stop state synchronization
            await self.state_sync.stop()
            
            # Disconnect from Home Assistant
            await self.ha_client.disconnect()
            
            # Close Redis connection
            if self.redis_client:
                self.redis_client.close()
            
            logger.info("Home Assistant Integration Service stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop service gracefully: {e}")

    def run(self):
        """Run the service"""
        # Create logs directory
        os.makedirs('/app/logs', exist_ok=True)
        
        # Start the service
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Start service components
            loop.run_until_complete(self.start())
            
            # Run Flask app
            logger.info(f"Starting Flask server on port {os.getenv('PORT', '5000')}")
            self.app.run(
                host='0.0.0.0',
                port=int(os.getenv('PORT', '5000')),
                debug=os.getenv('DEBUG', 'false').lower() == 'true'
            )
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            # Cleanup
            loop.run_until_complete(self.stop())
            loop.close()


if __name__ == '__main__':
    service = HomeAssistantService()
    service.run()