"""
Enhanced Redis client for real-time data streaming and caching.

This module provides a high-performance Redis client with connection pooling,
pub/sub support, and stream processing capabilities.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

import aioredis
from opentelemetry import trace

from temperature_service.config import RedisSettings, get_settings
from temperature_service.utils import create_circuit_breaker, trace_async_function

# Type variable for subscribers
T = TypeVar("T")

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class RedisClient:
    """Enhanced Redis client with advanced features."""

    def __init__(
        self,
        settings: Optional[RedisSettings] = None,
    ):
        """Initialize Redis client.

        Args:
            settings: Optional Redis settings (defaults to app settings)
        """
        self.settings = settings or get_settings().redis
        self.client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self.active_subscriptions: Set[str] = set()
        self._subscription_task: Optional[asyncio.Task] = None

        # Create circuit breaker
        self._circuit_breaker = create_circuit_breaker(
            name="redis",
            failure_threshold=3,
            recovery_timeout=30,
        )

        logger.info("Initialized Redis client (host: %s, port: %d)", self.settings.host, self.settings.port)

    @trace_async_function(name="redis_connect")
    async def connect(self) -> None:
        """Connect to Redis server."""
        if self.client is not None:
            return

        try:
            # Create Redis URL
            redis_url = f"redis://"
            if self.settings.password:
                redis_url += f":{self.settings.password}@"
            redis_url += f"{self.settings.host}:{self.settings.port}/{self.settings.db}"

            # Add SSL if enabled
            if self.settings.ssl:
                redis_url = redis_url.replace("redis://", "rediss://")

            # Connect to Redis
            self.client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=self.settings.connection_timeout,
                socket_connect_timeout=self.settings.connection_timeout,
                max_connections=self.settings.connection_pool_size,
            )

            logger.info("Connected to Redis server")

            # Initialize PubSub
            self.pubsub = self.client.pubsub()

            # Reset circuit breaker on successful connection
            self._circuit_breaker.reset()
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", str(e))
            self._circuit_breaker._on_failure(e)
            raise

    @trace_async_function(name="redis_close")
    async def close(self) -> None:
        """Close Redis connection."""
        if self._subscription_task:
            self._subscription_task.cancel()
            try:
                await self._subscription_task
            except asyncio.CancelledError:
                pass
            self._subscription_task = None

        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None

        if self.client:
            await self.client.close()
            self.client = None

        logger.info("Closed Redis connection")

    @trace_async_function(name="redis_health_check")
    async def health_check(self) -> bool:
        """Check if Redis is healthy.

        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            # Ensure we have a connection
            await self.connect()

            # Ping the server
            if self.client:
                result = await self.client.ping()
                return result == "PONG"
            return False
        except Exception as e:
            logger.error("Redis health check failed: %s", str(e))
            return False

    @trace_async_function(name="redis_set")
    async def set(
        self,
        key: str,
        value: Union[str, Dict, List],
        expire: Optional[int] = None,
    ) -> bool:
        """Set a key in Redis.

        Args:
            key: Key to set
            value: Value to set (will be JSON encoded if not a string)
            expire: Optional expiration time in seconds

        Returns:
            True if key was set, False otherwise
        """
        await self.connect()

        if not isinstance(value, str):
            value = json.dumps(value)

        try:
            if self.client:
                await self.client.set(key, value)

                if expire is not None:
                    await self.client.expire(key, expire)

                return True
            return False
        except Exception as e:
            logger.error("Failed to set Redis key '%s': %s", key, str(e))
            return False

    @trace_async_function(name="redis_get")
    async def get(
        self,
        key: str,
        default: Any = None,
        as_json: bool = True,
    ) -> Any:
        """Get a key from Redis.

        Args:
            key: Key to get
            default: Default value if key doesn't exist
            as_json: Whether to parse value as JSON

        Returns:
            Value or default if key doesn't exist
        """
        await self.connect()

        try:
            if self.client:
                value = await self.client.get(key)

                if value is None:
                    return default

                if as_json:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value

                return value
            return default
        except Exception as e:
            logger.error("Failed to get Redis key '%s': %s", key, str(e))
            return default

    @trace_async_function(name="redis_delete")
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis.

        Args:
            key: Key to delete

        Returns:
            True if key was deleted, False otherwise
        """
        await self.connect()

        try:
            if self.client:
                result = await self.client.delete(key)
                return result > 0
            return False
        except Exception as e:
            logger.error("Failed to delete Redis key '%s': %s", key, str(e))
            return False

    @trace_async_function(name="redis_publish")
    async def publish(
        self,
        channel: str,
        message: Union[str, Dict, List],
    ) -> int:
        """Publish a message to a Redis channel.

        Args:
            channel: Channel to publish to
            message: Message to publish (will be JSON encoded if not a string)

        Returns:
            Number of clients that received the message
        """
        await self.connect()

        if not isinstance(message, str):
            message = json.dumps(message)

        try:
            if self.client:
                result = await self.client.publish(channel, message)
                logger.debug("Published message to channel '%s'", channel)
                return result
            return 0
        except Exception as e:
            logger.error("Failed to publish to channel '%s': %s", channel, str(e))
            return 0

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str, str], None],
    ) -> None:
        """Subscribe to a Redis channel.

        Args:
            channel: Channel to subscribe to
            callback: Function to call when a message is received
        """
        await self.connect()

        # Store subscriber
        if channel not in self.subscribers:
            self.subscribers[channel] = []

        self.subscribers[channel].append(callback)

        # Subscribe to channel if not already subscribed
        if channel not in self.active_subscriptions and self.pubsub:
            await self.pubsub.subscribe(channel)
            self.active_subscriptions.add(channel)

            # Start message processing task if not already running
            if self._subscription_task is None:
                self._subscription_task = asyncio.create_task(self._process_messages())

            logger.info("Subscribed to channel '%s'", channel)

    async def unsubscribe(
        self,
        channel: str,
        callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Unsubscribe from a Redis channel.

        Args:
            channel: Channel to unsubscribe from
            callback: Optional specific callback to unsubscribe (all if None)
        """
        # Remove subscriber(s)
        if channel in self.subscribers:
            if callback is None:
                # Remove all subscribers
                self.subscribers[channel] = []
            else:
                # Remove specific subscriber
                self.subscribers[channel] = [cb for cb in self.subscribers[channel] if cb != callback]

        # Unsubscribe from channel if no subscribers left
        if (
            channel in self.active_subscriptions
            and (channel not in self.subscribers or not self.subscribers[channel])
            and self.pubsub
        ):
            await self.pubsub.unsubscribe(channel)
            self.active_subscriptions.remove(channel)
            logger.info("Unsubscribed from channel '%s'", channel)

    async def _process_messages(self) -> None:
        """Process messages from subscribed channels."""
        if not self.pubsub:
            return

        try:
            # Process messages as they come in
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]

                    # Call all subscribers for this channel
                    if channel in self.subscribers:
                        for callback in self.subscribers[channel]:
                            try:
                                callback(channel, data)
                            except Exception as e:
                                logger.error("Error in subscriber callback for channel '%s': %s", channel, str(e))
        except asyncio.CancelledError:
            # Task was cancelled, which is expected during shutdown
            logger.debug("Message processing task cancelled")
        except Exception as e:
            logger.error("Error processing Redis messages: %s", str(e))
            # Reconnect and restart processing
            await asyncio.sleep(1)
            if self._subscription_task is not None:
                self._subscription_task = asyncio.create_task(self._process_messages())

    @trace_async_function(name="redis_add_to_stream")
    async def add_to_stream(
        self,
        stream_key: str,
        data: Dict[str, Any],
        max_len: Optional[int] = None,
    ) -> str:
        """Add data to a Redis stream.

        Args:
            stream_key: Stream to add to
            data: Data to add (field-value pairs)
            max_len: Maximum length of stream

        Returns:
            ID of added entry
        """
        await self.connect()

        try:
            if self.client:
                # Convert all values to strings
                fields = {}
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        fields[key] = json.dumps(value)
                    else:
                        fields[key] = str(value)

                # Add entry to stream
                if max_len is None:
                    max_len = self.settings.max_stream_length

                entry_id = await self.client.xadd(
                    stream_key,
                    fields,
                    maxlen=max_len,
                    approximate=True,
                )

                logger.debug("Added entry to stream '%s'", stream_key)
                return entry_id

            raise RuntimeError("Redis client is not connected")
        except Exception as e:
            logger.error("Failed to add to stream '%s': %s", stream_key, str(e))
            raise

    @trace_async_function(name="redis_read_stream")
    async def read_stream(
        self,
        stream_key: str,
        count: int = 100,
        last_id: str = "0",
    ) -> List[Dict[str, Any]]:
        """Read entries from a Redis stream.

        Args:
            stream_key: Stream to read from
            count: Maximum number of entries to read
            last_id: ID to start reading from

        Returns:
            List of entries
        """
        await self.connect()

        try:
            if self.client:
                # Read entries from stream
                result = await self.client.xread(
                    streams={stream_key: last_id},
                    count=count,
                    block=0,
                )

                entries = []
                for stream_name, stream_entries in result:
                    for entry_id, fields in stream_entries:
                        # Parse JSON values
                        parsed_fields = {}
                        for key, value in fields.items():
                            try:
                                parsed_fields[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                parsed_fields[key] = value

                        # Add entry ID
                        parsed_fields["id"] = entry_id
                        entries.append(parsed_fields)

                return entries

            return []
        except Exception as e:
            logger.error("Failed to read from stream '%s': %s", stream_key, str(e))
            return []

    @trace_async_function(name="redis_create_consumer_group")
    async def create_consumer_group(
        self,
        stream_key: str,
        group_name: str,
        last_id: str = "$",
    ) -> bool:
        """Create a consumer group for a stream.

        Args:
            stream_key: Stream to create group for
            group_name: Name of consumer group
            last_id: ID to start reading from

        Returns:
            True if group was created, False otherwise
        """
        await self.connect()

        try:
            if self.client:
                # Create stream if it doesn't exist
                try:
                    await self.client.xgroup_create(
                        stream_key,
                        group_name,
                        id=last_id,
                        mkstream=True,
                    )
                    logger.info("Created consumer group '%s' for stream '%s'", group_name, stream_key)
                    return True
                except aioredis.ResponseError as e:
                    # Group already exists
                    if "BUSYGROUP" in str(e):
                        logger.debug("Consumer group '%s' already exists for stream '%s'", group_name, stream_key)
                        return True
                    raise

            return False
        except Exception as e:
            logger.error("Failed to create consumer group '%s' for stream '%s': %s", group_name, stream_key, str(e))
            return False

    @trace_async_function(name="redis_read_group")
    async def read_group(
        self,
        stream_key: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block: Optional[int] = None,
        no_ack: bool = False,
    ) -> List[Dict[str, Any]]:
        """Read entries from a consumer group.

        Args:
            stream_key: Stream to read from
            group_name: Name of consumer group
            consumer_name: Name of consumer
            count: Maximum number of entries to read
            block: Time to block waiting for entries (ms, None=don't block)
            no_ack: Whether to auto-acknowledge entries

        Returns:
            List of entries
        """
        await self.connect()

        try:
            if self.client:
                # Read entries from consumer group
                result = await self.client.xreadgroup(
                    group_name,
                    consumer_name,
                    streams={stream_key: ">"},
                    count=count,
                    block=block,
                    noack=no_ack,
                )

                entries = []
                for stream_name, stream_entries in result:
                    for entry_id, fields in stream_entries:
                        # Parse JSON values
                        parsed_fields = {}
                        for key, value in fields.items():
                            try:
                                parsed_fields[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                parsed_fields[key] = value

                        # Add entry ID
                        parsed_fields["id"] = entry_id
                        entries.append(parsed_fields)

                return entries

            return []
        except Exception as e:
            logger.error("Failed to read from consumer group '%s' for stream '%s': %s", group_name, stream_key, str(e))
            return []

    @trace_async_function(name="redis_acknowledge")
    async def acknowledge(
        self,
        stream_key: str,
        group_name: str,
        entry_ids: List[str],
    ) -> int:
        """Acknowledge entries in a consumer group.

        Args:
            stream_key: Stream to acknowledge in
            group_name: Name of consumer group
            entry_ids: IDs of entries to acknowledge

        Returns:
            Number of entries acknowledged
        """
        await self.connect()

        try:
            if self.client:
                # Acknowledge entries
                result = await self.client.xack(
                    stream_key,
                    group_name,
                    *entry_ids,
                )

                return result

            return 0
        except Exception as e:
            logger.error(
                "Failed to acknowledge entries in consumer group '%s' for stream '%s': %s", group_name, stream_key, str(e)
            )
            return 0


# Singleton instance for application-wide use
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get or create the Redis client singleton."""
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    return _redis_client


async def close_redis_client() -> None:
    """Close the Redis client singleton."""
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
