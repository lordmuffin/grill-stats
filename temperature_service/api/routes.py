"""
API routes for temperature data service.

This module provides the FastAPI routes for temperature data API endpoints,
including current temperature, historical data, and streaming.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import ValidationError

from temperature_service.clients import RedisClient, get_redis_client
from temperature_service.config import get_settings
from temperature_service.models import BatchTemperatureReadings, TemperatureQuery, TemperatureReading
from temperature_service.services import TemperatureService, get_temperature_service
from temperature_service.utils import trace_async_function, trace_function

# Get application settings
settings = get_settings()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Create API router
router = APIRouter(prefix="/api/temperature")


@router.get("/health")
@trace_function(name="api_health_check")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    temperature_service = await get_temperature_service()
    health = await temperature_service.health_check()

    # Return appropriate status code
    status_code = 200
    if health["status"] == "unhealthy":
        status_code = 500

    return Response(
        content=json.dumps(health),
        media_type="application/json",
        status_code=status_code,
    )


@router.get("/current/{device_id}")
@trace_function(name="api_get_current_temperature")
async def get_current_temperature(
    device_id: str,
    probe_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get current temperature reading for a device.

    Args:
        device_id: Device ID
        probe_id: Optional probe ID
    """
    temperature_service = await get_temperature_service()
    result = await temperature_service.get_current_temperature(device_id, probe_id)

    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


@router.get("/history/{device_id}")
@trace_function(name="api_get_temperature_history")
async def get_temperature_history(
    device_id: str,
    probe_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    aggregation: Optional[str] = None,
    interval: Optional[str] = None,
    limit: Optional[int] = 1000,
    offset: Optional[int] = 0,
) -> Dict[str, Any]:
    """Get historical temperature data for a device.

    Args:
        device_id: Device ID
        probe_id: Optional probe ID
        start_time: Optional start time (ISO format)
        end_time: Optional end time (ISO format)
        aggregation: Optional aggregation function (none, mean, max, min)
        interval: Optional time interval for aggregation (e.g., 1m, 5m, 1h)
        limit: Maximum number of points to return
        offset: Number of points to skip
    """
    # Parse datetime strings
    start_dt = None
    end_dt = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid start_time format: {start_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid end_time format: {end_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    # Create query object
    query = TemperatureQuery(
        device_id=device_id,
        probe_id=probe_id,
        start_time=start_dt,
        end_time=end_dt,
        aggregation=aggregation,
        interval=interval,
        limit=limit,
        offset=offset,
    )

    # Get historical data
    temperature_service = await get_temperature_service()
    result = await temperature_service.get_temperature_history(query)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get("/stats/{device_id}")
@trace_function(name="api_get_temperature_stats")
async def get_temperature_stats(
    device_id: str,
    probe_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Get temperature statistics for a device.

    Args:
        device_id: Device ID
        probe_id: Optional probe ID
        start_time: Optional start time (ISO format)
        end_time: Optional end time (ISO format)
    """
    # Parse datetime strings
    start_dt = None
    end_dt = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid start_time format: {start_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid end_time format: {end_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    # Get statistics
    temperature_service = await get_temperature_service()
    result = await temperature_service.get_temperature_statistics(
        device_id=device_id,
        probe_id=probe_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.post("/batch")
@trace_function(name="api_store_batch_temperature_data")
async def store_batch_temperature_data(
    batch: BatchTemperatureReadings,
) -> Dict[str, Any]:
    """Store multiple temperature readings at once.

    Args:
        batch: Batch of temperature readings
    """
    if not batch.readings:
        raise HTTPException(status_code=400, detail="No readings provided")

    # Store readings
    temperature_service = await get_temperature_service()
    result = await temperature_service.store_batch_readings(batch)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get("/alerts/{device_id}")
@trace_function(name="api_get_temperature_alerts")
async def get_temperature_alerts(
    device_id: str,
    probe_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    threshold_high: float = 250.0,
    threshold_low: float = 32.0,
) -> Dict[str, Any]:
    """Get temperature alerts for a device.

    Args:
        device_id: Device ID
        probe_id: Optional probe ID
        start_time: Optional start time (ISO format)
        end_time: Optional end time (ISO format)
        threshold_high: High temperature threshold
        threshold_low: Low temperature threshold
    """
    # Parse datetime strings
    start_dt = None
    end_dt = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid start_time format: {start_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid end_time format: {end_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

    # Get alerts
    temperature_service = await get_temperature_service()
    result = await temperature_service.get_temperature_alerts(
        device_id=device_id,
        probe_id=probe_id,
        start_time=start_dt,
        end_time=end_dt,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get("/stream/{device_id}")
@trace_function(name="api_temperature_stream_sse")
async def temperature_stream_sse(
    device_id: str,
    request: Request,
    probe_id: Optional[str] = None,
) -> StreamingResponse:
    """Server-sent events stream for real-time temperature updates.

    Args:
        device_id: Device ID
        probe_id: Optional probe ID
    """
    if not settings.service.enable_sse:
        raise HTTPException(status_code=501, detail="Server-sent events are disabled in service configuration")

    async def event_generator():
        """Generate SSE events."""
        redis_client = await get_redis_client()
        pubsub = await redis_client.subscribe(settings.redis.pub_sub_channels["temperature"])

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Wait for message
                message = await pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])

                        # Filter for specific device
                        if data.get("device_id") == device_id:
                            # Filter for specific probe if requested
                            if probe_id is None or data.get("probe_id") == probe_id:
                                yield f"data: {json.dumps(data)}\n\n"
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Small delay to reduce CPU usage
                await asyncio.sleep(0.1)
        finally:
            await redis_client.unsubscribe(settings.redis.pub_sub_channels["temperature"])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.websocket("/ws/{device_id}")
@trace_function(name="api_temperature_websocket")
async def temperature_websocket(
    websocket: WebSocket,
    device_id: str,
    probe_id: Optional[str] = None,
    redis_client: RedisClient = Depends(get_redis_client),
):
    """WebSocket endpoint for real-time temperature updates.

    Args:
        websocket: WebSocket connection
        device_id: Device ID
        probe_id: Optional probe ID
        redis_client: Redis client dependency
    """
    if not settings.service.enable_websockets:
        await websocket.close(code=1000, reason="WebSockets are disabled in service configuration")
        return

    await websocket.accept()

    # Subscribe to Redis channel
    pubsub = await redis_client.subscribe(settings.redis.pub_sub_channels["temperature"])

    try:
        # Send initial data
        temperature_service = await get_temperature_service()
        current_data = await temperature_service.get_current_temperature(device_id, probe_id)

        if current_data["status"] == "success":
            await websocket.send_json(current_data["data"])

        # Listen for messages
        while True:
            # Check for messages from client (ping/pong)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                # Echo any received data back to client
                await websocket.send_text(data)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            # Check for Redis messages
            message = await pubsub.get_message(timeout=0.1)
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])

                    # Filter for specific device
                    if data.get("device_id") == device_id:
                        # Filter for specific probe if requested
                        if probe_id is None or data.get("probe_id") == probe_id:
                            await websocket.send_json(data)
                except (json.JSONDecodeError, KeyError):
                    pass
                except WebSocketDisconnect:
                    break

            # Small delay to reduce CPU usage
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
    finally:
        # Unsubscribe from Redis channel
        await redis_client.unsubscribe(settings.redis.pub_sub_channels["temperature"])

        # Close WebSocket
        try:
            await websocket.close()
        except Exception:
            pass
