import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import redis
import json
from ..models.ha_models import HAStateChange, HAEvent
from ..models.entity_models import EntityState, TemperatureSensor
from .ha_client import HomeAssistantClient
from .entity_manager import EntityManager

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    successful_syncs: int = 0
    failed_syncs: int = 0
    last_sync_time: Optional[datetime] = None
    sync_duration_ms: float = 0
    throttled_updates: int = 0
    bulk_updates_sent: int = 0


class StateSynchronizer:
    def __init__(
        self,
        ha_client: HomeAssistantClient,
        entity_manager: EntityManager,
        redis_client: Optional[redis.Redis] = None,
        sync_interval: int = 30,
        throttle_interval: int = 5,
        batch_size: int = 10
    ):
        self.ha_client = ha_client
        self.entity_manager = entity_manager
        self.redis_client = redis_client
        self.sync_interval = sync_interval
        self.throttle_interval = throttle_interval
        self.batch_size = batch_size
        
        self.stats = SyncStats()
        self.pending_updates: Dict[str, Dict] = {}
        self.last_update_times: Dict[str, datetime] = {}
        self.sync_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Error recovery
        self.retry_queue: List[Dict] = []
        self.max_retries = 3
        self.retry_delay = 5
        
        # Event handlers
        self.state_change_handlers: List[Callable] = []

    async def start(self):
        if self.is_running:
            logger.warning("State synchronizer already running")
            return
            
        self.is_running = True
        logger.info("Starting state synchronizer")
        
        # Register for Home Assistant WebSocket events
        self.ha_client.register_event_handler("state_changed", self._handle_ha_state_change)
        
        # Start sync task
        self.sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self):
        if not self.is_running:
            return
            
        self.is_running = False
        logger.info("Stopping state synchronizer")
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass

    async def sync_temperature_data(self, sensor_data: TemperatureSensor) -> bool:
        try:
            entity_id = f"sensor.grill_stats_{sensor_data.device_id}_{sensor_data.probe_id}_temperature"
            
            # Check throttling
            if not self._should_update(entity_id):
                self.stats.throttled_updates += 1
                return True
            
            # Prepare update data
            update_data = {
                "entity_id": entity_id,
                "state": sensor_data.temperature,
                "attributes": {
                    "device_id": sensor_data.device_id,
                    "probe_id": sensor_data.probe_id,
                    "unit_of_measurement": sensor_data.unit,
                    "last_seen": sensor_data.last_seen.isoformat(),
                    "battery_level": sensor_data.battery_level,
                    "signal_strength": sensor_data.signal_strength,
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add to pending updates for batch processing
            self.pending_updates[entity_id] = update_data
            self.last_update_times[entity_id] = datetime.utcnow()
            
            # Cache in Redis if available
            if self.redis_client:
                await self._cache_state_update(update_data)
            
            logger.debug(f"Queued temperature sync for {entity_id}: {sensor_data.temperature}{sensor_data.unit}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync temperature data: {e}")
            return False

    async def sync_device_state(self, device_id: str, state_data: Dict[str, Any]) -> bool:
        try:
            updates = []
            
            # Battery level
            if "battery_level" in state_data:
                battery_entity = f"sensor.grill_stats_{device_id}_battery"
                if self._should_update(battery_entity):
                    updates.append({
                        "entity_id": battery_entity,
                        "state": state_data["battery_level"],
                        "attributes": {"device_id": device_id, "unit_of_measurement": "%"}
                    })
            
            # Signal strength
            if "signal_strength" in state_data:
                signal_entity = f"sensor.grill_stats_{device_id}_signal_strength"
                if self._should_update(signal_entity):
                    updates.append({
                        "entity_id": signal_entity,
                        "state": state_data["signal_strength"],
                        "attributes": {"device_id": device_id, "unit_of_measurement": "dBm"}
                    })
            
            # Connection status
            if "is_connected" in state_data:
                conn_entity = f"binary_sensor.grill_stats_{device_id}_connection"
                if self._should_update(conn_entity):
                    updates.append({
                        "entity_id": conn_entity,
                        "state": "on" if state_data["is_connected"] else "off",
                        "attributes": {"device_id": device_id}
                    })
            
            # Queue updates
            for update in updates:
                self.pending_updates[update["entity_id"]] = update
                self.last_update_times[update["entity_id"]] = datetime.utcnow()
            
            logger.debug(f"Queued {len(updates)} device state updates for {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync device state for {device_id}: {e}")
            return False

    async def force_sync_all(self) -> Dict[str, Any]:
        try:
            start_time = time.time()
            
            # Get all entities from registry
            all_entities = self.entity_manager.get_all_entities()
            
            # Sync each entity to Home Assistant
            successful = 0
            failed = 0
            
            for entity_id, entity_state in all_entities.items():
                try:
                    success = self.ha_client.set_entity_state(
                        entity_id,
                        str(entity_state.state),
                        entity_state.attributes
                    )
                    
                    if success:
                        successful += 1
                    else:
                        failed += 1
                        
                except Exception as e:
                    logger.error(f"Failed to sync entity {entity_id}: {e}")
                    failed += 1
            
            sync_duration = (time.time() - start_time) * 1000
            
            result = {
                "total_entities": len(all_entities),
                "successful_syncs": successful,
                "failed_syncs": failed,
                "sync_duration_ms": sync_duration,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Force sync completed: {successful}/{len(all_entities)} entities synced in {sync_duration:.2f}ms")
            return result
            
        except Exception as e:
            logger.error(f"Failed to force sync all entities: {e}")
            return {"error": str(e)}

    async def _sync_loop(self):
        while self.is_running:
            try:
                await self._process_pending_updates()
                await self._process_retry_queue()
                await asyncio.sleep(self.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(self.sync_interval)

    async def _process_pending_updates(self):
        if not self.pending_updates:
            return
            
        start_time = time.time()
        updates_to_process = list(self.pending_updates.items())
        self.pending_updates.clear()
        
        # Process in batches
        for i in range(0, len(updates_to_process), self.batch_size):
            batch = updates_to_process[i:i + self.batch_size]
            await self._process_batch(batch)
        
        # Update stats
        sync_duration = (time.time() - start_time) * 1000
        self.stats.sync_duration_ms = sync_duration
        self.stats.last_sync_time = datetime.utcnow()
        self.stats.bulk_updates_sent += len(updates_to_process)
        
        logger.debug(f"Processed {len(updates_to_process)} pending updates in {sync_duration:.2f}ms")

    async def _process_batch(self, batch: List[tuple]):
        successful = 0
        failed = 0
        
        for entity_id, update_data in batch:
            try:
                success = self.ha_client.set_entity_state(
                    update_data["entity_id"],
                    str(update_data["state"]),
                    update_data["attributes"]
                )
                
                if success:
                    successful += 1
                    # Update entity manager
                    self.entity_manager.update_entity_state(
                        update_data["entity_id"],
                        update_data["state"],
                        update_data["attributes"]
                    )
                    
                    # Trigger state change handlers
                    await self._trigger_state_change_handlers(update_data)
                    
                else:
                    failed += 1
                    # Add to retry queue
                    self.retry_queue.append({
                        "update_data": update_data,
                        "retry_count": 0,
                        "next_retry": datetime.utcnow() + timedelta(seconds=self.retry_delay)
                    })
                    
            except Exception as e:
                logger.error(f"Failed to process update for {entity_id}: {e}")
                failed += 1
        
        self.stats.successful_syncs += successful
        self.stats.failed_syncs += failed

    async def _process_retry_queue(self):
        if not self.retry_queue:
            return
            
        now = datetime.utcnow()
        items_to_retry = []
        remaining_items = []
        
        for item in self.retry_queue:
            if item["next_retry"] <= now:
                if item["retry_count"] < self.max_retries:
                    items_to_retry.append(item)
                else:
                    logger.warning(f"Max retries exceeded for entity {item['update_data']['entity_id']}")
            else:
                remaining_items.append(item)
        
        self.retry_queue = remaining_items
        
        for item in items_to_retry:
            try:
                update_data = item["update_data"]
                success = self.ha_client.set_entity_state(
                    update_data["entity_id"],
                    str(update_data["state"]),
                    update_data["attributes"]
                )
                
                if success:
                    self.stats.successful_syncs += 1
                    logger.info(f"Retry successful for {update_data['entity_id']}")
                else:
                    item["retry_count"] += 1
                    item["next_retry"] = now + timedelta(seconds=self.retry_delay * (2 ** item["retry_count"]))
                    self.retry_queue.append(item)
                    
            except Exception as e:
                logger.error(f"Retry failed for {item['update_data']['entity_id']}: {e}")
                item["retry_count"] += 1
                item["next_retry"] = now + timedelta(seconds=self.retry_delay * (2 ** item["retry_count"]))
                self.retry_queue.append(item)

    def _should_update(self, entity_id: str) -> bool:
        last_update = self.last_update_times.get(entity_id)
        if not last_update:
            return True
            
        time_since_update = datetime.utcnow() - last_update
        return time_since_update.total_seconds() >= self.throttle_interval

    async def _cache_state_update(self, update_data: Dict):
        try:
            if self.redis_client:
                cache_key = f"ha_state:{update_data['entity_id']}"
                cache_data = json.dumps(update_data, default=str)
                self.redis_client.setex(cache_key, 3600, cache_data)  # 1 hour TTL
        except Exception as e:
            logger.error(f"Failed to cache state update: {e}")

    async def _handle_ha_state_change(self, entity_id: str, event_data: Dict):
        try:
            # Handle incoming state changes from Home Assistant
            if entity_id.startswith("sensor.grill_stats") or entity_id.startswith("binary_sensor.grill_stats"):
                logger.debug(f"Received HA state change for {entity_id}")
                
                # Update local entity registry
                new_state = event_data.get("new_state", {})
                if new_state:
                    self.entity_manager.update_entity_state(
                        entity_id,
                        new_state.get("state"),
                        new_state.get("attributes", {})
                    )
                    
        except Exception as e:
            logger.error(f"Failed to handle HA state change for {entity_id}: {e}")

    async def _trigger_state_change_handlers(self, update_data: Dict):
        for handler in self.state_change_handlers:
            try:
                await handler(update_data)
            except Exception as e:
                logger.error(f"Error in state change handler: {e}")

    def register_state_change_handler(self, handler: Callable):
        self.state_change_handlers.append(handler)

    def get_sync_stats(self) -> Dict[str, Any]:
        return {
            "successful_syncs": self.stats.successful_syncs,
            "failed_syncs": self.stats.failed_syncs,
            "last_sync_time": self.stats.last_sync_time.isoformat() if self.stats.last_sync_time else None,
            "sync_duration_ms": self.stats.sync_duration_ms,
            "throttled_updates": self.stats.throttled_updates,
            "bulk_updates_sent": self.stats.bulk_updates_sent,
            "pending_updates": len(self.pending_updates),
            "retry_queue_size": len(self.retry_queue),
            "is_running": self.is_running
        }