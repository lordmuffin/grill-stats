"""
Kafka consumer manager for processing events from topics.
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException
from prometheus_client import Counter, Gauge, Histogram

from ..schemas.events import BaseEvent, deserialize_event
from ..utils.config import KafkaConfig

logger = structlog.get_logger()

# Prometheus metrics
MESSAGES_RECEIVED = Counter(
    "kafka_messages_received_total",
    "Total messages received from Kafka",
    ["topic", "status"],
)
PROCESSING_DURATION = Histogram("kafka_processing_duration_seconds", "Time spent processing messages", ["topic"])
CONSUMER_LAG = Gauge("kafka_consumer_lag", "Consumer lag", ["topic", "partition"])
ACTIVE_CONSUMERS = Gauge("kafka_active_consumers", "Number of active consumers")


class ConsumerManager:
    """Manages Kafka consumers and message processing."""

    def __init__(self, kafka_config: KafkaConfig):
        self.kafka_config = kafka_config
        self.consumers: Dict[str, Consumer] = {}
        self.consumer_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.processing_handlers: Dict[str, Callable] = {}

        # Start the manager
        self.is_running = True
        logger.info("Consumer manager initialized")

    def _create_consumer(self, group_id: str, topics: List[str]) -> Consumer:
        """Create a new Kafka consumer."""
        try:
            consumer_config = {
                "bootstrap.servers": self.kafka_config.bootstrap_servers,
                "security.protocol": self.kafka_config.security_protocol,
                "group.id": group_id,
                "auto.offset.reset": self.kafka_config.auto_offset_reset,
                "enable.auto.commit": self.kafka_config.enable_auto_commit,
                "auto.commit.interval.ms": self.kafka_config.auto_commit_interval_ms,
                "session.timeout.ms": self.kafka_config.session_timeout_ms,
                "max.poll.records": self.kafka_config.max_poll_records,
                "fetch.min.bytes": self.kafka_config.fetch_min_bytes,
                "fetch.max.wait.ms": self.kafka_config.fetch_max_wait_ms,
                "enable.partition.eof": False,
                "api.version.request": True,
                "broker.version.fallback": "0.10.0.0",
                "api.version.fallback.ms": 0,
            }

            if self.kafka_config.sasl_mechanism:
                consumer_config.update(
                    {
                        "sasl.mechanism": self.kafka_config.sasl_mechanism,
                        "sasl.username": self.kafka_config.sasl_username,
                        "sasl.password": self.kafka_config.sasl_password,
                    }
                )

            consumer = Consumer(consumer_config)
            consumer.subscribe(topics)

            logger.info("Kafka consumer created", group_id=group_id, topics=topics)
            return consumer

        except Exception as e:
            logger.error(
                "Failed to create Kafka consumer",
                group_id=group_id,
                topics=topics,
                error=str(e),
            )
            raise

    async def start_consumer(
        self,
        consumer_id: str,
        topics: List[str],
        message_handler: Callable[[BaseEvent], None],
        group_id: Optional[str] = None,
    ):
        """Start a new consumer for the specified topics."""
        try:
            if consumer_id in self.consumers:
                logger.warning("Consumer already exists", consumer_id=consumer_id)
                return

            # Use consumer_id as group_id if not specified
            if group_id is None:
                group_id = f"{self.kafka_config.consumer_group_id}-{consumer_id}"

            # Create consumer
            consumer = self._create_consumer(group_id, topics)
            self.consumers[consumer_id] = consumer
            self.processing_handlers[consumer_id] = message_handler

            # Start consumer task
            task = asyncio.create_task(self._consume_loop(consumer_id, topics))
            self.consumer_tasks[consumer_id] = task

            ACTIVE_CONSUMERS.inc()
            logger.info(
                "Consumer started",
                consumer_id=consumer_id,
                topics=topics,
                group_id=group_id,
            )

        except Exception as e:
            logger.error(
                "Failed to start consumer",
                consumer_id=consumer_id,
                topics=topics,
                error=str(e),
            )
            raise

    async def _consume_loop(self, consumer_id: str, topics: List[str]):
        """Main consumer loop."""
        consumer = self.consumers[consumer_id]
        message_handler = self.processing_handlers[consumer_id]

        try:
            while self.is_running:
                try:
                    # Poll for messages
                    msg = consumer.poll(timeout=1.0)

                    if msg is None:
                        continue

                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            # End of partition event
                            logger.debug(
                                "Reached end of partition",
                                consumer_id=consumer_id,
                                topic=msg.topic(),
                                partition=msg.partition(),
                            )
                            continue
                        else:
                            logger.error(
                                "Consumer error",
                                consumer_id=consumer_id,
                                error=msg.error(),
                            )
                            continue

                    # Process message
                    await self._process_message(consumer_id, msg, message_handler)

                except KafkaException as e:
                    logger.error(
                        "Kafka exception in consumer loop",
                        consumer_id=consumer_id,
                        error=str(e),
                    )
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(
                        "Unexpected error in consumer loop",
                        consumer_id=consumer_id,
                        error=str(e),
                    )
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled", consumer_id=consumer_id)
        finally:
            # Close consumer
            try:
                consumer.close()
            except Exception as e:
                logger.error("Error closing consumer", consumer_id=consumer_id, error=str(e))

            ACTIVE_CONSUMERS.dec()

    async def _process_message(self, consumer_id: str, msg, message_handler: Callable[[BaseEvent], None]):
        """Process a single message."""
        start_time = time.time()
        topic = msg.topic()

        try:
            # Decode message
            value = msg.value().decode("utf-8") if msg.value() else None
            if not value:
                logger.warning("Empty message received", consumer_id=consumer_id, topic=topic)
                return

            # Parse JSON
            try:
                message_data = json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse JSON message",
                    consumer_id=consumer_id,
                    topic=topic,
                    error=str(e),
                )
                MESSAGES_RECEIVED.labels(topic=topic, status="json_error").inc()
                return

            # Deserialize event
            try:
                event = deserialize_event(message_data)
            except Exception as e:
                logger.error(
                    "Failed to deserialize event",
                    consumer_id=consumer_id,
                    topic=topic,
                    error=str(e),
                )
                MESSAGES_RECEIVED.labels(topic=topic, status="deserialize_error").inc()
                return

            # Call message handler
            try:
                if asyncio.iscoroutinefunction(message_handler):
                    await message_handler(event)
                else:
                    message_handler(event)

                MESSAGES_RECEIVED.labels(topic=topic, status="success").inc()

            except Exception as e:
                logger.error(
                    "Message handler failed",
                    consumer_id=consumer_id,
                    topic=topic,
                    event_id=event.event_id,
                    error=str(e),
                )
                MESSAGES_RECEIVED.labels(topic=topic, status="handler_error").inc()
                # Don't raise here - we want to continue processing other messages

            # Update metrics
            processing_time = time.time() - start_time
            PROCESSING_DURATION.labels(topic=topic).observe(processing_time)

            # Update consumer lag
            if hasattr(msg, "offset"):
                # This is a simplified lag calculation
                # In production, you might want to use Kafka's consumer lag metrics
                pass

            logger.debug(
                "Message processed successfully",
                consumer_id=consumer_id,
                topic=topic,
                event_id=event.event_id,
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(
                "Failed to process message",
                consumer_id=consumer_id,
                topic=topic,
                error=str(e),
            )
            MESSAGES_RECEIVED.labels(topic=topic, status="error").inc()

    async def stop_consumer(self, consumer_id: str):
        """Stop a specific consumer."""
        try:
            if consumer_id not in self.consumers:
                logger.warning("Consumer not found", consumer_id=consumer_id)
                return

            # Cancel consumer task
            if consumer_id in self.consumer_tasks:
                task = self.consumer_tasks[consumer_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del self.consumer_tasks[consumer_id]

            # Remove consumer
            if consumer_id in self.consumers:
                del self.consumers[consumer_id]

            # Remove handler
            if consumer_id in self.processing_handlers:
                del self.processing_handlers[consumer_id]

            logger.info("Consumer stopped", consumer_id=consumer_id)

        except Exception as e:
            logger.error("Failed to stop consumer", consumer_id=consumer_id, error=str(e))
            raise

    async def stop_all(self):
        """Stop all consumers."""
        try:
            self.is_running = False

            # Stop all consumers
            consumer_ids = list(self.consumers.keys())
            for consumer_id in consumer_ids:
                await self.stop_consumer(consumer_id)

            logger.info("All consumers stopped")

        except Exception as e:
            logger.error("Failed to stop all consumers", error=str(e))
            raise

    async def restart_consumer(self, consumer_id: str):
        """Restart a specific consumer."""
        try:
            if consumer_id not in self.consumers:
                logger.warning("Consumer not found for restart", consumer_id=consumer_id)
                return

            # Get current topics and handler
            topics = list(self.consumers[consumer_id].list_topics().topics.keys())
            handler = self.processing_handlers[consumer_id]

            # Stop consumer
            await self.stop_consumer(consumer_id)

            # Start consumer again
            await self.start_consumer(consumer_id, topics, handler)

            logger.info("Consumer restarted", consumer_id=consumer_id)

        except Exception as e:
            logger.error("Failed to restart consumer", consumer_id=consumer_id, error=str(e))
            raise

    def get_consumer_status(self, consumer_id: str) -> Dict[str, Any]:
        """Get status of a specific consumer."""
        if consumer_id not in self.consumers:
            return {"status": "not_found"}

        consumer = self.consumers[consumer_id]
        task = self.consumer_tasks.get(consumer_id)

        try:
            # Get assignment
            assignment = consumer.assignment()
            topics = list(set(tp.topic for tp in assignment))

            return {
                "status": "running" if task and not task.done() else "stopped",
                "topics": topics,
                "assignment": [{"topic": tp.topic, "partition": tp.partition} for tp in assignment],
                "task_done": task.done() if task else True,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """Get overall consumer manager status."""
        consumer_statuses = {}
        for consumer_id in self.consumers:
            consumer_statuses[consumer_id] = self.get_consumer_status(consumer_id)

        return {
            "is_running": self.is_running,
            "active_consumers": len(self.consumers),
            "consumers": consumer_statuses,
        }

    def get_consumer_lag(self, consumer_id: str) -> Dict[str, Any]:
        """Get consumer lag information."""
        if consumer_id not in self.consumers:
            return {"error": "Consumer not found"}

        consumer = self.consumers[consumer_id]

        try:
            # Get committed offsets
            assignment = consumer.assignment()
            committed = consumer.committed(assignment)

            # Get high water marks
            high_water_marks = consumer.get_watermark_offsets(assignment[0]) if assignment else (0, 0)

            lag_info = {}
            for tp in assignment:
                committed_offset = committed[tp.partition].offset if tp.partition < len(committed) else 0
                high_water_mark = high_water_marks[1] if len(high_water_marks) > 1 else 0
                lag = max(0, high_water_mark - committed_offset)

                lag_info[f"{tp.topic}_{tp.partition}"] = {
                    "committed_offset": committed_offset,
                    "high_water_mark": high_water_mark,
                    "lag": lag,
                }

            return lag_info

        except Exception as e:
            return {"error": str(e)}
