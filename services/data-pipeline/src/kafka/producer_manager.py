"""
Kafka producer manager for sending events to topics.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union

import structlog
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from prometheus_client import Counter, Gauge, Histogram

from ..schemas.events import BaseEvent, serialize_event
from ..utils.config import KafkaConfig

logger = structlog.get_logger()

# Prometheus metrics
MESSAGES_SENT = Counter(
    "kafka_messages_sent_total", "Total messages sent to Kafka", ["topic", "status"]
)
SEND_DURATION = Histogram(
    "kafka_send_duration_seconds", "Time spent sending messages to Kafka", ["topic"]
)
PRODUCER_QUEUE_SIZE = Gauge("kafka_producer_queue_size", "Current producer queue size")


class ProducerManager:
    """Manages Kafka producers and message sending."""

    def __init__(self, kafka_config: KafkaConfig):
        self.kafka_config = kafka_config
        self.producer: Optional[Producer] = None
        self.admin_client: Optional[AdminClient] = None
        self.topics_created: set = set()
        self.is_running = False
        self.send_queue = asyncio.Queue()
        self.send_task: Optional[asyncio.Task] = None

        # Initialize producer
        self._initialize_producer()
        self._initialize_admin_client()

        # Start background sending task
        self.send_task = asyncio.create_task(self._send_loop())

    def _initialize_producer(self):
        """Initialize Kafka producer."""
        try:
            producer_config = {
                "bootstrap.servers": self.kafka_config.bootstrap_servers,
                "security.protocol": self.kafka_config.security_protocol,
                "compression.type": self.kafka_config.compression_type,
                "batch.size": self.kafka_config.batch_size,
                "linger.ms": self.kafka_config.linger_ms,
                "buffer.memory": self.kafka_config.buffer_memory,
                "retries": self.kafka_config.retries,
                "retry.backoff.ms": self.kafka_config.retry_backoff_ms,
                "enable.idempotence": True,
                "acks": "all",
                "request.timeout.ms": 30000,
                "delivery.timeout.ms": 120000,
            }

            if self.kafka_config.sasl_mechanism:
                producer_config.update(
                    {
                        "sasl.mechanism": self.kafka_config.sasl_mechanism,
                        "sasl.username": self.kafka_config.sasl_username,
                        "sasl.password": self.kafka_config.sasl_password,
                    }
                )

            self.producer = Producer(producer_config)
            self.is_running = True
            logger.info("Kafka producer initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Kafka producer", error=str(e))
            raise

    def _initialize_admin_client(self):
        """Initialize Kafka admin client."""
        try:
            admin_config = {
                "bootstrap.servers": self.kafka_config.bootstrap_servers,
                "security.protocol": self.kafka_config.security_protocol,
            }

            if self.kafka_config.sasl_mechanism:
                admin_config.update(
                    {
                        "sasl.mechanism": self.kafka_config.sasl_mechanism,
                        "sasl.username": self.kafka_config.sasl_username,
                        "sasl.password": self.kafka_config.sasl_password,
                    }
                )

            self.admin_client = AdminClient(admin_config)
            logger.info("Kafka admin client initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Kafka admin client", error=str(e))
            raise

    async def _send_loop(self):
        """Background task for sending messages."""
        while self.is_running:
            try:
                # Get message from queue with timeout
                try:
                    message = await asyncio.wait_for(self.send_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                topic, key, value, headers = message

                # Send message to Kafka
                await self._send_message_sync(topic, key, value, headers)

                # Mark task as done
                self.send_queue.task_done()

            except Exception as e:
                logger.error("Error in send loop", error=str(e))
                await asyncio.sleep(1)

    async def _send_message_sync(
        self,
        topic: str,
        key: Optional[str],
        value: str,
        headers: Optional[Dict[str, str]],
    ):
        """Send message to Kafka synchronously."""
        try:
            start_time = time.time()

            # Prepare headers
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            # Send message
            future = self.producer.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=value.encode("utf-8"),
                headers=kafka_headers,
                callback=self._delivery_callback,
            )

            # Poll for delivery
            self.producer.poll(0)

            # Update metrics
            duration = time.time() - start_time
            SEND_DURATION.labels(topic=topic).observe(duration)
            PRODUCER_QUEUE_SIZE.set(len(self.producer))

            logger.debug(
                "Message sent to Kafka", topic=topic, key=key, duration=duration
            )

        except Exception as e:
            logger.error("Failed to send message to Kafka", topic=topic, error=str(e))
            MESSAGES_SENT.labels(topic=topic, status="error").inc()
            raise

    def _delivery_callback(self, err, msg):
        """Callback for message delivery."""
        if err:
            logger.error("Message delivery failed", error=str(err), topic=msg.topic())
            MESSAGES_SENT.labels(topic=msg.topic(), status="error").inc()
        else:
            logger.debug(
                "Message delivered",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
            MESSAGES_SENT.labels(topic=msg.topic(), status="success").inc()

    async def create_topics(
        self, topics: List[str], num_partitions: int = 3, replication_factor: int = 1
    ):
        """Create Kafka topics if they don't exist."""
        try:
            if not self.admin_client:
                raise Exception("Admin client not initialized")

            # Check which topics already exist
            existing_topics = set(self.admin_client.list_topics().topics.keys())
            topics_to_create = [
                topic
                for topic in topics
                if topic not in existing_topics and topic not in self.topics_created
            ]

            if not topics_to_create:
                logger.debug("All topics already exist")
                return

            # Create new topics
            new_topics = [
                NewTopic(
                    topic=topic,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                )
                for topic in topics_to_create
            ]

            # Create topics
            futures = self.admin_client.create_topics(new_topics)

            # Wait for creation to complete
            for topic, future in futures.items():
                try:
                    future.result()  # The result itself is None
                    self.topics_created.add(topic)
                    logger.info("Topic created successfully", topic=topic)
                except Exception as e:
                    if "already exists" in str(e):
                        logger.debug("Topic already exists", topic=topic)
                        self.topics_created.add(topic)
                    else:
                        logger.error(
                            "Failed to create topic", topic=topic, error=str(e)
                        )
                        raise

        except Exception as e:
            logger.error("Failed to create topics", error=str(e))
            raise

    async def send_event(
        self,
        topic: str,
        event: BaseEvent,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Send an event to a Kafka topic."""
        try:
            # Serialize event
            event_data = serialize_event(event)
            value = json.dumps(event_data, default=str)

            # Use event ID as key if no key provided
            if key is None:
                key = event.event_id

            # Add default headers
            if headers is None:
                headers = {}

            headers.update(
                {
                    "event_type": event.event_type,
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "source": event.source,
                    "version": event.version,
                }
            )

            # Add to send queue
            await self.send_queue.put((topic, key, value, headers))

            logger.debug(
                "Event queued for sending", topic=topic, event_id=event.event_id
            )

        except Exception as e:
            logger.error(
                "Failed to queue event",
                topic=topic,
                event_id=getattr(event, "event_id", "unknown"),
                error=str(e),
            )
            raise

    async def send_raw_message(
        self,
        topic: str,
        value: Union[str, Dict[str, Any]],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Send a raw message to a Kafka topic."""
        try:
            # Convert dict to JSON string
            if isinstance(value, dict):
                value = json.dumps(value, default=str)

            # Add to send queue
            await self.send_queue.put((topic, key, value, headers))

            logger.debug("Raw message queued for sending", topic=topic, key=key)

        except Exception as e:
            logger.error(
                "Failed to queue raw message", topic=topic, key=key, error=str(e)
            )
            raise

    async def send_batch(
        self,
        topic: str,
        events: List[BaseEvent],
        key_field: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Send multiple events to a Kafka topic in batch."""
        try:
            for event in events:
                # Determine key
                key = None
                if key_field and hasattr(event, key_field):
                    key = getattr(event, key_field)

                await self.send_event(topic, event, key, headers)

            logger.info(
                "Batch events queued for sending", topic=topic, count=len(events)
            )

        except Exception as e:
            logger.error(
                "Failed to queue batch events",
                topic=topic,
                count=len(events),
                error=str(e),
            )
            raise

    async def flush(self, timeout: float = 30.0):
        """Flush all pending messages."""
        try:
            if self.producer:
                # Wait for queue to be empty
                await self.send_queue.join()

                # Flush producer
                remaining = self.producer.flush(timeout)
                if remaining > 0:
                    logger.warning("Not all messages were flushed", remaining=remaining)
                else:
                    logger.debug("All messages flushed successfully")

        except Exception as e:
            logger.error("Failed to flush messages", error=str(e))
            raise

    async def close(self):
        """Close the producer and cleanup resources."""
        try:
            self.is_running = False

            # Cancel send task
            if self.send_task:
                self.send_task.cancel()
                try:
                    await self.send_task
                except asyncio.CancelledError:
                    pass

            # Flush remaining messages
            await self.flush()

            # Close producer
            if self.producer:
                self.producer.close()
                self.producer = None

            logger.info("Producer manager closed successfully")

        except Exception as e:
            logger.error("Failed to close producer manager", error=str(e))
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get producer status."""
        return {
            "is_running": self.is_running,
            "queue_size": self.send_queue.qsize(),
            "topics_created": list(self.topics_created),
            "producer_queue_size": len(self.producer) if self.producer else 0,
        }
