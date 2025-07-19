"""
Main entry point for the Kafka-based data pipeline service.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any, Dict

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from src.kafka.consumer_manager import ConsumerManager
from src.kafka.producer_manager import ProducerManager
from src.processors.anomaly_detector import AnomalyDetector
from src.processors.temperature_aggregator import TemperatureAggregationService
from src.utils.config import Config
from src.utils.health_check import HealthChecker
from src.utils.metrics import MetricsCollector

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global components
config = Config()
metrics = MetricsCollector()
health_checker = HealthChecker()
producer_manager = None
consumer_manager = None
temperature_aggregator = None
anomaly_detector = None

# FastAPI app
app = FastAPI(
    title="Grill Stats Data Pipeline",
    description="Kafka-based data pipeline for real-time temperature monitoring",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize all components on startup."""
    global producer_manager, consumer_manager, temperature_aggregator, anomaly_detector

    try:
        logger.info("Starting data pipeline service...")

        # Initialize Kafka managers
        producer_manager = ProducerManager(config.kafka_config)
        consumer_manager = ConsumerManager(config.kafka_config)

        # Initialize processors
        temperature_aggregator = TemperatureAggregationService(
            producer_manager, config.redis_config
        )
        anomaly_detector = AnomalyDetector(producer_manager, config.redis_config)

        # Start background tasks
        asyncio.create_task(start_consumers())
        asyncio.create_task(health_check_loop())

        logger.info("Data pipeline service started successfully")

    except Exception as e:
        logger.error("Failed to start data pipeline service", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        logger.info("Shutting down data pipeline service...")

        if consumer_manager:
            await consumer_manager.stop_all()
        if producer_manager:
            await producer_manager.close()
        if temperature_aggregator:
            await temperature_aggregator.shutdown()
        if anomaly_detector:
            await anomaly_detector.shutdown()

        logger.info("Data pipeline service shutdown complete")

    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


async def start_consumers():
    """Start all Kafka consumers."""
    try:
        # Temperature readings consumer
        await consumer_manager.start_consumer(
            "temperature-readings-consumer",
            ["temperature.readings.raw"],
            temperature_aggregator.process_temperature_reading,
        )

        # Validated readings consumer for anomaly detection
        await consumer_manager.start_consumer(
            "anomaly-detector-consumer",
            ["temperature.readings.validated"],
            anomaly_detector.process_validated_reading,
        )

        logger.info("All consumers started successfully")

    except Exception as e:
        logger.error("Failed to start consumers", error=str(e))
        raise


async def health_check_loop():
    """Periodic health check loop."""
    while True:
        try:
            await health_checker.check_all_components()
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            await asyncio.sleep(10)  # Retry sooner on failure


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        status = await health_checker.get_health_status()
        if status["status"] == "healthy":
            return status
        else:
            raise HTTPException(status_code=503, detail=status)
    except Exception as e:
        logger.error("Health check endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Health check failed")


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    try:
        return generate_latest()
    except Exception as e:
        logger.error("Metrics endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Metrics collection failed")


@app.get("/status")
async def get_status():
    """Get detailed service status."""
    try:
        return {
            "service": "data-pipeline",
            "version": "1.0.0",
            "kafka_status": (
                await consumer_manager.get_status()
                if consumer_manager
                else "not_initialized"
            ),
            "processor_status": {
                "temperature_aggregator": (
                    temperature_aggregator.get_status()
                    if temperature_aggregator
                    else "not_initialized"
                ),
                "anomaly_detector": (
                    anomaly_detector.get_status()
                    if anomaly_detector
                    else "not_initialized"
                ),
            },
            "metrics": metrics.get_summary(),
        }
    except Exception as e:
        logger.error("Status endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Status check failed")


@app.post("/sync/trigger")
async def trigger_sync():
    """Manually trigger a temperature sync."""
    try:
        if temperature_aggregator:
            await temperature_aggregator.trigger_sync()
            return {"status": "sync_triggered"}
        else:
            raise HTTPException(
                status_code=503, detail="Temperature aggregator not initialized"
            )
    except Exception as e:
        logger.error("Manual sync trigger failed", error=str(e))
        raise HTTPException(status_code=500, detail="Sync trigger failed")


@app.post("/anomaly/retrain")
async def retrain_anomaly_detector():
    """Retrain the anomaly detection model."""
    try:
        if anomaly_detector:
            await anomaly_detector.retrain_model()
            return {"status": "retraining_started"}
        else:
            raise HTTPException(
                status_code=503, detail="Anomaly detector not initialized"
            )
    except Exception as e:
        logger.error("Anomaly detector retrain failed", error=str(e))
        raise HTTPException(status_code=500, detail="Retrain failed")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal", signal=signum)
    sys.exit(0)


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configure logging level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level))

    # Run the FastAPI app
    uvicorn.run(
        app, host="0.0.0.0", port=8000, log_level=log_level.lower(), access_log=True
    )
