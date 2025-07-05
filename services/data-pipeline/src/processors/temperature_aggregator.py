"""
Temperature aggregation service with real-time processing.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import redis.asyncio as redis
import structlog
from prometheus_client import Counter, Histogram, Gauge

from ..kafka.producer_manager import ProducerManager
from ..schemas.events import (
    TemperatureReadingEvent, TemperatureValidatedEvent, 
    ValidationError, BaseEvent
)
from ..utils.config import RedisConfig

logger = structlog.get_logger()

# Prometheus metrics
TEMPERATURE_READINGS_PROCESSED = Counter('temperature_readings_processed_total', 'Total temperature readings processed', ['device_id', 'status'])
VALIDATION_DURATION = Histogram('temperature_validation_duration_seconds', 'Time spent validating temperature readings')
AGGREGATION_DURATION = Histogram('temperature_aggregation_duration_seconds', 'Time spent aggregating temperature data')
ACTIVE_DEVICES = Gauge('temperature_active_devices', 'Number of active temperature devices')
CACHE_HIT_RATIO = Gauge('temperature_cache_hit_ratio', 'Cache hit ratio for temperature data')


class TemperatureAggregationService:
    """Service for aggregating and validating temperature readings."""
    
    def __init__(self, producer_manager: ProducerManager, redis_config: RedisConfig):
        self.producer_manager = producer_manager
        self.redis_config = redis_config
        self.redis_client: Optional[redis.Redis] = None
        
        # In-memory data structures
        self.device_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.device_stats: Dict[str, Dict[str, Any]] = {}
        self.last_seen: Dict[str, datetime] = {}
        
        # Processing configuration
        self.window_size_minutes = 5
        self.max_temperature_change_per_minute = 50.0  # degrees
        self.min_temperature = -40.0
        self.max_temperature = 1000.0
        self.validation_rules = self._initialize_validation_rules()
        
        # Background tasks
        self.aggregation_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Initialize Redis connection
        asyncio.create_task(self._initialize_redis())
    
    def _initialize_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize temperature validation rules."""
        return {
            "temperature_range": {
                "min": self.min_temperature,
                "max": self.max_temperature,
                "error_message": "Temperature out of valid range"
            },
            "rate_of_change": {
                "max_change_per_minute": self.max_temperature_change_per_minute,
                "error_message": "Temperature change rate too high"
            },
            "spike_detection": {
                "threshold_multiplier": 3.0,
                "min_samples": 5,
                "error_message": "Temperature spike detected"
            },
            "sensor_health": {
                "max_offline_minutes": 30,
                "min_battery_level": 10.0,
                "error_message": "Sensor health check failed"
            }
        }
    
    async def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_config.host,
                port=self.redis_config.port,
                db=self.redis_config.db,
                password=self.redis_config.password,
                socket_timeout=self.redis_config.socket_timeout,
                socket_connect_timeout=self.redis_config.socket_connect_timeout,
                retry_on_timeout=self.redis_config.retry_on_timeout,
                health_check_interval=self.redis_config.health_check_interval,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established")
            
            # Start background tasks
            self.is_running = True
            self.aggregation_task = asyncio.create_task(self._aggregation_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise
    
    async def process_temperature_reading(self, event: BaseEvent):
        """Process incoming temperature reading."""
        if not isinstance(event, TemperatureReadingEvent):
            logger.warning("Received non-temperature reading event", event_type=type(event).__name__)
            return
        
        start_time = time.time()
        device_id = event.data.device_id
        
        try:
            # Validate the reading
            validation_result = await self._validate_temperature_reading(event)
            
            # Store the reading
            await self._store_temperature_reading(event)
            
            # Update device tracking
            self._update_device_tracking(event)
            
            # Create validated event
            validated_event = TemperatureValidatedEvent(
                event_id=f"{event.event_id}_validated",
                source="temperature_aggregator",
                data=event.data,
                validation_status=validation_result["status"],
                validation_errors=validation_result["errors"],
                processing_time_ms=(time.time() - start_time) * 1000
            )
            
            # Send validated event
            await self.producer_manager.send_event(
                "temperature.readings.validated",
                validated_event
            )
            
            # Update metrics
            TEMPERATURE_READINGS_PROCESSED.labels(
                device_id=device_id,
                status=validation_result["status"]
            ).inc()
            
            VALIDATION_DURATION.observe(time.time() - start_time)
            
            logger.debug("Temperature reading processed", 
                        device_id=device_id,
                        status=validation_result["status"],
                        processing_time_ms=validated_event.processing_time_ms)
            
        except Exception as e:
            logger.error("Failed to process temperature reading", 
                        device_id=device_id,
                        error=str(e))
            TEMPERATURE_READINGS_PROCESSED.labels(
                device_id=device_id,
                status="error"
            ).inc()
            raise
    
    async def _validate_temperature_reading(self, event: TemperatureReadingEvent) -> Dict[str, Any]:
        """Validate a temperature reading against rules."""
        errors = []
        device_id = event.data.device_id
        temperature = event.data.temperature
        
        # Rule 1: Temperature range check
        if temperature < self.validation_rules["temperature_range"]["min"] or \
           temperature > self.validation_rules["temperature_range"]["max"]:
            errors.append(ValidationError(
                field="temperature",
                message=self.validation_rules["temperature_range"]["error_message"],
                value=temperature
            ))
        
        # Rule 2: Rate of change check
        if device_id in self.device_data and self.device_data[device_id]:
            recent_readings = list(self.device_data[device_id])
            if len(recent_readings) > 0:
                last_reading = recent_readings[-1]
                time_diff = (event.timestamp - last_reading["timestamp"]).total_seconds() / 60.0
                if time_diff > 0:
                    temp_change = abs(temperature - last_reading["temperature"])
                    change_rate = temp_change / time_diff
                    
                    if change_rate > self.validation_rules["rate_of_change"]["max_change_per_minute"]:
                        errors.append(ValidationError(
                            field="temperature",
                            message=self.validation_rules["rate_of_change"]["error_message"],
                            value=change_rate
                        ))
        
        # Rule 3: Spike detection
        if device_id in self.device_data and len(self.device_data[device_id]) >= self.validation_rules["spike_detection"]["min_samples"]:
            recent_temps = [r["temperature"] for r in list(self.device_data[device_id])[-10:]]
            if recent_temps:
                mean_temp = sum(recent_temps) / len(recent_temps)
                std_temp = (sum((t - mean_temp) ** 2 for t in recent_temps) / len(recent_temps)) ** 0.5
                threshold = mean_temp + (std_temp * self.validation_rules["spike_detection"]["threshold_multiplier"])
                
                if abs(temperature - mean_temp) > threshold:
                    errors.append(ValidationError(
                        field="temperature",
                        message=self.validation_rules["spike_detection"]["error_message"],
                        value=abs(temperature - mean_temp)
                    ))
        
        # Rule 4: Sensor health check
        if event.data.battery_level is not None and \
           event.data.battery_level < self.validation_rules["sensor_health"]["min_battery_level"]:
            errors.append(ValidationError(
                field="battery_level",
                message=self.validation_rules["sensor_health"]["error_message"],
                value=event.data.battery_level
            ))
        
        status = "valid" if not errors else "invalid"
        return {
            "status": status,
            "errors": errors
        }
    
    async def _store_temperature_reading(self, event: TemperatureReadingEvent):
        """Store temperature reading in Redis and memory."""
        device_id = event.data.device_id
        
        try:
            # Store in Redis
            if self.redis_client:
                key = f"temperature:{device_id}"
                reading_data = {
                    "timestamp": event.timestamp.isoformat(),
                    "temperature": event.data.temperature,
                    "battery_level": event.data.battery_level,
                    "signal_strength": event.data.signal_strength,
                    "location": event.data.location,
                    "status": event.data.status
                }
                
                # Store latest reading
                await self.redis_client.hset(f"{key}:latest", mapping=reading_data)
                
                # Store in time series (sorted set)
                timestamp_score = event.timestamp.timestamp()
                await self.redis_client.zadd(
                    f"{key}:series",
                    {json.dumps(reading_data): timestamp_score}
                )
                
                # Keep only last 24 hours
                cutoff_time = (datetime.utcnow() - timedelta(hours=24)).timestamp()
                await self.redis_client.zremrangebyscore(f"{key}:series", 0, cutoff_time)
                
                # Set expiration
                await self.redis_client.expire(f"{key}:latest", 3600)  # 1 hour
                await self.redis_client.expire(f"{key}:series", 86400)  # 24 hours
        
        except Exception as e:
            logger.error("Failed to store reading in Redis", device_id=device_id, error=str(e))
        
        # Store in memory
        self.device_data[device_id].append({
            "timestamp": event.timestamp,
            "temperature": event.data.temperature,
            "battery_level": event.data.battery_level,
            "signal_strength": event.data.signal_strength,
            "location": event.data.location,
            "status": event.data.status
        })
    
    def _update_device_tracking(self, event: TemperatureReadingEvent):
        """Update device tracking information."""
        device_id = event.data.device_id
        
        # Update last seen
        self.last_seen[device_id] = event.timestamp
        
        # Update device stats
        if device_id not in self.device_stats:
            self.device_stats[device_id] = {
                "first_seen": event.timestamp,
                "reading_count": 0,
                "last_temperature": None,
                "min_temperature": float('inf'),
                "max_temperature": float('-inf'),
                "avg_temperature": 0.0
            }
        
        stats = self.device_stats[device_id]
        stats["reading_count"] += 1
        stats["last_temperature"] = event.data.temperature
        stats["min_temperature"] = min(stats["min_temperature"], event.data.temperature)
        stats["max_temperature"] = max(stats["max_temperature"], event.data.temperature)
        
        # Update running average
        current_avg = stats["avg_temperature"]
        count = stats["reading_count"]
        stats["avg_temperature"] = (current_avg * (count - 1) + event.data.temperature) / count
        
        # Update active devices metric
        ACTIVE_DEVICES.set(len(self.device_stats))
    
    async def _aggregation_loop(self):
        """Background task for data aggregation."""
        while self.is_running:
            try:
                start_time = time.time()
                
                # Perform aggregation
                await self._perform_aggregation()
                
                # Update metrics
                AGGREGATION_DURATION.observe(time.time() - start_time)
                
                # Update cache hit ratio
                total_requests = self.cache_hits + self.cache_misses
                if total_requests > 0:
                    CACHE_HIT_RATIO.set(self.cache_hits / total_requests)
                
                # Wait for next cycle
                await asyncio.sleep(self.window_size_minutes * 60)
                
            except Exception as e:
                logger.error("Error in aggregation loop", error=str(e))
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _perform_aggregation(self):
        """Perform data aggregation for all devices."""
        try:
            for device_id in list(self.device_data.keys()):
                await self._aggregate_device_data(device_id)
        except Exception as e:
            logger.error("Failed to perform aggregation", error=str(e))
    
    async def _aggregate_device_data(self, device_id: str):
        """Aggregate data for a specific device."""
        try:
            if device_id not in self.device_data or not self.device_data[device_id]:
                return
            
            # Get recent readings
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=self.window_size_minutes)
            
            recent_readings = [
                r for r in self.device_data[device_id] 
                if r["timestamp"] >= window_start
            ]
            
            if not recent_readings:
                return
            
            # Calculate aggregated statistics
            temperatures = [r["temperature"] for r in recent_readings]
            
            aggregated_data = {
                "device_id": device_id,
                "window_start": window_start.isoformat(),
                "window_end": now.isoformat(),
                "reading_count": len(recent_readings),
                "min_temperature": min(temperatures),
                "max_temperature": max(temperatures),
                "avg_temperature": sum(temperatures) / len(temperatures),
                "temperature_trend": self._calculate_temperature_trend(temperatures),
                "battery_level": recent_readings[-1]["battery_level"],
                "signal_strength": recent_readings[-1]["signal_strength"],
                "location": recent_readings[-1]["location"],
                "status": recent_readings[-1]["status"]
            }
            
            # Store aggregated data in Redis
            if self.redis_client:
                key = f"temperature:{device_id}:aggregated"
                await self.redis_client.hset(key, mapping=aggregated_data)
                await self.redis_client.expire(key, 3600)  # 1 hour
            
            logger.debug("Device data aggregated", 
                        device_id=device_id, 
                        reading_count=len(recent_readings))
            
        except Exception as e:
            logger.error("Failed to aggregate device data", device_id=device_id, error=str(e))
    
    def _calculate_temperature_trend(self, temperatures: List[float]) -> str:
        """Calculate temperature trend from a list of temperatures."""
        if len(temperatures) < 2:
            return "stable"
        
        # Simple trend calculation
        first_half = temperatures[:len(temperatures)//2]
        second_half = temperatures[len(temperatures)//2:]
        
        if not first_half or not second_half:
            return "stable"
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        diff = second_avg - first_avg
        
        if diff > 2.0:
            return "increasing"
        elif diff < -2.0:
            return "decreasing"
        else:
            return "stable"
    
    async def _cleanup_loop(self):
        """Background task for cleanup operations."""
        while self.is_running:
            try:
                await self._cleanup_old_data()
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))
                await asyncio.sleep(300)  # Wait before retrying
    
    async def _cleanup_old_data(self):
        """Clean up old data from memory and Redis."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            # Clean up memory data
            for device_id in list(self.device_data.keys()):
                original_size = len(self.device_data[device_id])
                self.device_data[device_id] = deque(
                    [r for r in self.device_data[device_id] if r["timestamp"] > cutoff_time],
                    maxlen=1000
                )
                cleaned_size = len(self.device_data[device_id])
                
                if original_size != cleaned_size:
                    logger.debug("Cleaned up old data", 
                                device_id=device_id, 
                                removed=original_size - cleaned_size)
            
            # Clean up Redis data is handled in _store_temperature_reading
            
        except Exception as e:
            logger.error("Failed to cleanup old data", error=str(e))
    
    async def get_device_history(self, device_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get historical temperature data for a device."""
        try:
            # Try Redis first
            if self.redis_client:
                key = f"temperature:{device_id}:series"
                start_score = start_time.timestamp()
                end_score = end_time.timestamp()
                
                redis_data = await self.redis_client.zrangebyscore(
                    key, start_score, end_score
                )
                
                if redis_data:
                    self.cache_hits += 1
                    return [json.loads(data) for data in redis_data]
                else:
                    self.cache_misses += 1
            
            # Fall back to memory data
            if device_id in self.device_data:
                memory_data = [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "temperature": r["temperature"],
                        "battery_level": r["battery_level"],
                        "signal_strength": r["signal_strength"],
                        "location": r["location"],
                        "status": r["status"]
                    }
                    for r in self.device_data[device_id]
                    if start_time <= r["timestamp"] <= end_time
                ]
                return memory_data
            
            return []
            
        except Exception as e:
            logger.error("Failed to get device history", device_id=device_id, error=str(e))
            return []
    
    async def get_device_stats(self, device_id: str) -> Dict[str, Any]:
        """Get statistics for a specific device."""
        try:
            if device_id not in self.device_stats:
                return {"error": "Device not found"}
            
            stats = self.device_stats[device_id].copy()
            stats["last_seen"] = self.last_seen.get(device_id, "never").isoformat() if device_id in self.last_seen else "never"
            stats["first_seen"] = stats["first_seen"].isoformat()
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get device stats", device_id=device_id, error=str(e))
            return {"error": str(e)}
    
    async def trigger_sync(self):
        """Manually trigger a synchronization."""
        try:
            logger.info("Manual sync triggered")
            await self._perform_aggregation()
            return {"status": "sync_completed"}
        except Exception as e:
            logger.error("Manual sync failed", error=str(e))
            return {"status": "sync_failed", "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "is_running": self.is_running,
            "active_devices": len(self.device_stats),
            "total_readings": sum(stats["reading_count"] for stats in self.device_stats.values()),
            "cache_hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "redis_connected": self.redis_client is not None,
            "background_tasks": {
                "aggregation": not self.aggregation_task.done() if self.aggregation_task else False,
                "cleanup": not self.cleanup_task.done() if self.cleanup_task else False
            }
        }
    
    async def shutdown(self):
        """Shutdown the service."""
        try:
            self.is_running = False
            
            # Cancel background tasks
            if self.aggregation_task:
                self.aggregation_task.cancel()
            if self.cleanup_task:
                self.cleanup_task.cancel()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("Temperature aggregation service shutdown complete")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))