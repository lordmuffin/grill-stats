"""
Metrics collection and monitoring utilities.
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, Info, Summary, generate_latest

logger = structlog.get_logger()


class MetricsCollector:
    """Centralized metrics collection and monitoring."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry
        self.start_time = time.time()

        # Application metrics
        self.app_info = Info(
            "grill_stats_data_pipeline_info",
            "Data pipeline application information",
            registry=self.registry,
        )
        self.app_info.info(
            {
                "version": "1.0.0",
                "service": "data-pipeline",
                "component": "kafka-event-processor",
            }
        )

        # System metrics
        self.uptime = Gauge(
            "grill_stats_uptime_seconds",
            "Application uptime in seconds",
            registry=self.registry,
        )

        # Kafka metrics
        self.kafka_messages_produced = Counter(
            "grill_stats_kafka_messages_produced_total",
            "Total messages produced to Kafka",
            ["topic", "status"],
            registry=self.registry,
        )

        self.kafka_messages_consumed = Counter(
            "grill_stats_kafka_messages_consumed_total",
            "Total messages consumed from Kafka",
            ["topic", "consumer_group", "status"],
            registry=self.registry,
        )

        self.kafka_produce_duration = Histogram(
            "grill_stats_kafka_produce_duration_seconds",
            "Time spent producing messages to Kafka",
            ["topic"],
            registry=self.registry,
        )

        self.kafka_consume_duration = Histogram(
            "grill_stats_kafka_consume_duration_seconds",
            "Time spent consuming messages from Kafka",
            ["topic", "consumer_group"],
            registry=self.registry,
        )

        self.kafka_consumer_lag = Gauge(
            "grill_stats_kafka_consumer_lag",
            "Kafka consumer lag",
            ["topic", "partition", "consumer_group"],
            registry=self.registry,
        )

        # Processing metrics
        self.processing_duration = Histogram(
            "grill_stats_processing_duration_seconds",
            "Time spent processing events",
            ["processor", "event_type"],
            registry=self.registry,
        )

        self.processing_errors = Counter(
            "grill_stats_processing_errors_total",
            "Total processing errors",
            ["processor", "error_type"],
            registry=self.registry,
        )

        self.events_processed = Counter(
            "grill_stats_events_processed_total",
            "Total events processed",
            ["processor", "event_type", "status"],
            registry=self.registry,
        )

        # Temperature metrics
        self.temperature_readings = Counter(
            "grill_stats_temperature_readings_total",
            "Total temperature readings",
            ["device_id", "validation_status"],
            registry=self.registry,
        )

        self.temperature_current = Gauge(
            "grill_stats_temperature_current",
            "Current temperature reading",
            ["device_id", "device_name", "location"],
            registry=self.registry,
        )

        self.temperature_validation_duration = Histogram(
            "grill_stats_temperature_validation_duration_seconds",
            "Time spent validating temperature readings",
            ["device_id"],
            registry=self.registry,
        )

        # Anomaly detection metrics
        self.anomalies_detected = Counter(
            "grill_stats_anomalies_detected_total",
            "Total anomalies detected",
            ["device_id", "anomaly_type", "severity"],
            registry=self.registry,
        )

        self.anomaly_detection_duration = Histogram(
            "grill_stats_anomaly_detection_duration_seconds",
            "Time spent on anomaly detection",
            ["device_id", "model_type"],
            registry=self.registry,
        )

        self.anomaly_model_accuracy = Gauge(
            "grill_stats_anomaly_model_accuracy",
            "Anomaly detection model accuracy",
            ["device_id", "model_type"],
            registry=self.registry,
        )

        # Alert metrics
        self.alerts_triggered = Counter(
            "grill_stats_alerts_triggered_total",
            "Total alerts triggered",
            ["device_id", "alert_type", "severity"],
            registry=self.registry,
        )

        self.alerts_resolved = Counter(
            "grill_stats_alerts_resolved_total",
            "Total alerts resolved",
            ["device_id", "alert_type", "resolution_type"],
            registry=self.registry,
        )

        # Cache metrics
        self.cache_operations = Counter(
            "grill_stats_cache_operations_total",
            "Total cache operations",
            ["operation", "cache_type", "status"],
            registry=self.registry,
        )

        self.cache_hit_ratio = Gauge(
            "grill_stats_cache_hit_ratio",
            "Cache hit ratio",
            ["cache_type"],
            registry=self.registry,
        )

        # Home Assistant metrics
        self.homeassistant_updates = Counter(
            "grill_stats_homeassistant_updates_total",
            "Total Home Assistant updates",
            ["entity_type", "status"],
            registry=self.registry,
        )

        self.homeassistant_update_duration = Histogram(
            "grill_stats_homeassistant_update_duration_seconds",
            "Time spent updating Home Assistant",
            ["entity_type"],
            registry=self.registry,
        )

        # Health metrics
        self.health_checks = Counter(
            "grill_stats_health_checks_total",
            "Total health checks",
            ["component", "status"],
            registry=self.registry,
        )

        self.component_status = Gauge(
            "grill_stats_component_status",
            "Component status (1=healthy, 0=unhealthy)",
            ["component", "instance"],
            registry=self.registry,
        )

        # Custom business metrics
        self.active_devices = Gauge(
            "grill_stats_active_devices",
            "Number of active temperature devices",
            registry=self.registry,
        )

        self.data_quality_score = Gauge(
            "grill_stats_data_quality_score",
            "Data quality score (0-1)",
            ["device_id"],
            registry=self.registry,
        )

        # Performance metrics
        self.memory_usage = Gauge(
            "grill_stats_memory_usage_bytes",
            "Memory usage in bytes",
            ["component"],
            registry=self.registry,
        )

        self.cpu_usage = Gauge(
            "grill_stats_cpu_usage_percent",
            "CPU usage percentage",
            ["component"],
            registry=self.registry,
        )

        # In-memory storage for custom metrics
        self.custom_counters = defaultdict(int)
        self.custom_gauges = defaultdict(float)
        self.custom_histograms = defaultdict(list)
        self.performance_history = defaultdict(lambda: deque(maxlen=1000))

        # Start background updates
        self._update_uptime()

    def _update_uptime(self):
        """Update uptime metric."""
        self.uptime.set(time.time() - self.start_time)

    def record_kafka_message_produced(self, topic: str, status: str = "success"):
        """Record a Kafka message production."""
        self.kafka_messages_produced.labels(topic=topic, status=status).inc()

    def record_kafka_message_consumed(self, topic: str, consumer_group: str, status: str = "success"):
        """Record a Kafka message consumption."""
        self.kafka_messages_consumed.labels(topic=topic, consumer_group=consumer_group, status=status).inc()

    def record_kafka_produce_duration(self, topic: str, duration: float):
        """Record Kafka production duration."""
        self.kafka_produce_duration.labels(topic=topic).observe(duration)

    def record_kafka_consume_duration(self, topic: str, consumer_group: str, duration: float):
        """Record Kafka consumption duration."""
        self.kafka_consume_duration.labels(topic=topic, consumer_group=consumer_group).observe(duration)

    def record_processing_duration(self, processor: str, event_type: str, duration: float):
        """Record event processing duration."""
        self.processing_duration.labels(processor=processor, event_type=event_type).observe(duration)

    def record_processing_error(self, processor: str, error_type: str):
        """Record a processing error."""
        self.processing_errors.labels(processor=processor, error_type=error_type).inc()

    def record_event_processed(self, processor: str, event_type: str, status: str):
        """Record an event processing completion."""
        self.events_processed.labels(processor=processor, event_type=event_type, status=status).inc()

    def record_temperature_reading(
        self,
        device_id: str,
        temperature: float,
        device_name: str = "",
        location: str = "",
        validation_status: str = "valid",
    ):
        """Record a temperature reading."""
        self.temperature_readings.labels(device_id=device_id, validation_status=validation_status).inc()

        self.temperature_current.labels(device_id=device_id, device_name=device_name, location=location).set(temperature)

    def record_temperature_validation_duration(self, device_id: str, duration: float):
        """Record temperature validation duration."""
        self.temperature_validation_duration.labels(device_id=device_id).observe(duration)

    def record_anomaly_detected(self, device_id: str, anomaly_type: str, severity: str):
        """Record an anomaly detection."""
        self.anomalies_detected.labels(device_id=device_id, anomaly_type=anomaly_type, severity=severity).inc()

    def record_anomaly_detection_duration(self, device_id: str, model_type: str, duration: float):
        """Record anomaly detection duration."""
        self.anomaly_detection_duration.labels(device_id=device_id, model_type=model_type).observe(duration)

    def record_anomaly_model_accuracy(self, device_id: str, model_type: str, accuracy: float):
        """Record anomaly model accuracy."""
        self.anomaly_model_accuracy.labels(device_id=device_id, model_type=model_type).set(accuracy)

    def record_alert_triggered(self, device_id: str, alert_type: str, severity: str):
        """Record an alert trigger."""
        self.alerts_triggered.labels(device_id=device_id, alert_type=alert_type, severity=severity).inc()

    def record_alert_resolved(self, device_id: str, alert_type: str, resolution_type: str):
        """Record an alert resolution."""
        self.alerts_resolved.labels(device_id=device_id, alert_type=alert_type, resolution_type=resolution_type).inc()

    def record_cache_operation(self, operation: str, cache_type: str, status: str):
        """Record a cache operation."""
        self.cache_operations.labels(operation=operation, cache_type=cache_type, status=status).inc()

    def record_cache_hit_ratio(self, cache_type: str, ratio: float):
        """Record cache hit ratio."""
        self.cache_hit_ratio.labels(cache_type=cache_type).set(ratio)

    def record_homeassistant_update(self, entity_type: str, status: str, duration: float = None):
        """Record a Home Assistant update."""
        self.homeassistant_updates.labels(entity_type=entity_type, status=status).inc()

        if duration is not None:
            self.homeassistant_update_duration.labels(entity_type=entity_type).observe(duration)

    def record_health_check(self, component: str, status: str, is_healthy: bool):
        """Record a health check."""
        self.health_checks.labels(component=component, status=status).inc()
        self.component_status.labels(component=component, instance="default").set(1 if is_healthy else 0)

    def record_active_devices(self, count: int):
        """Record active device count."""
        self.active_devices.set(count)

    def record_data_quality_score(self, device_id: str, score: float):
        """Record data quality score."""
        self.data_quality_score.labels(device_id=device_id).set(score)

    def record_memory_usage(self, component: str, bytes_used: int):
        """Record memory usage."""
        self.memory_usage.labels(component=component).set(bytes_used)

    def record_cpu_usage(self, component: str, percent_used: float):
        """Record CPU usage."""
        self.cpu_usage.labels(component=component).set(percent_used)

    def increment_custom_counter(self, name: str, value: int = 1):
        """Increment a custom counter."""
        self.custom_counters[name] += value

    def set_custom_gauge(self, name: str, value: float):
        """Set a custom gauge value."""
        self.custom_gauges[name] = value

    def record_custom_histogram(self, name: str, value: float):
        """Record a custom histogram value."""
        self.custom_histograms[name].append(value)

        # Keep only last 1000 values
        if len(self.custom_histograms[name]) > 1000:
            self.custom_histograms[name] = self.custom_histograms[name][-1000:]

    def record_performance_metric(self, component: str, metric_name: str, value: float):
        """Record a performance metric."""
        key = f"{component}_{metric_name}"
        self.performance_history[key].append({"timestamp": datetime.utcnow(), "value": value})

    def get_performance_history(self, component: str, metric_name: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get performance history for a component."""
        key = f"{component}_{metric_name}"
        cutoff_time = datetime.utcnow() - timedelta(minutes=duration_minutes)

        return [entry for entry in self.performance_history[key] if entry["timestamp"] > cutoff_time]

    def get_custom_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of custom metrics."""
        histogram_stats = {}
        for name, values in self.custom_histograms.items():
            if values:
                histogram_stats[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "latest": values[-1],
                }

        return {
            "counters": dict(self.custom_counters),
            "gauges": dict(self.custom_gauges),
            "histograms": histogram_stats,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        self._update_uptime()

        return {
            "uptime_seconds": time.time() - self.start_time,
            "custom_metrics": self.get_custom_metrics_summary(),
            "performance_components": list(set(key.split("_")[0] for key in self.performance_history.keys())),
        }

    def export_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        return generate_latest(self.registry)

    def reset_metrics(self):
        """Reset all custom metrics (for testing)."""
        self.custom_counters.clear()
        self.custom_gauges.clear()
        self.custom_histograms.clear()
        self.performance_history.clear()
        logger.info("Metrics reset")

    def health_check(self) -> Dict[str, Any]:
        """Perform metrics collector health check."""
        try:
            # Basic functionality test
            test_key = "health_check_test"
            self.increment_custom_counter(test_key)
            self.set_custom_gauge(test_key, 1.0)

            return {
                "status": "healthy",
                "metrics_collected": len(self.custom_counters) + len(self.custom_gauges),
                "uptime_seconds": time.time() - self.start_time,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
