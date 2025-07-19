"""
Anomaly detection service with machine learning capabilities.
"""

import asyncio
import json
import pickle
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import redis.asyncio as redis
import structlog
from joblib import dump, load
from prometheus_client import Counter, Gauge, Histogram
from pyod.models.auto_encoder import AutoEncoder
from pyod.models.knn import KNN
from pyod.models.lof import LOF
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ..kafka.producer_manager import ProducerManager
from ..schemas.events import (
    AlertAction,
    AlertTriggeredEvent,
    AnomalyDetails,
    AnomalyDetectedEvent,
    BaseEvent,
    SeverityLevel,
    TemperatureValidatedEvent,
)
from ..utils.config import RedisConfig

logger = structlog.get_logger()

# Prometheus metrics
ANOMALIES_DETECTED = Counter(
    "anomalies_detected_total",
    "Total anomalies detected",
    ["device_id", "anomaly_type"],
)
DETECTION_DURATION = Histogram(
    "anomaly_detection_duration_seconds", "Time spent on anomaly detection"
)
MODEL_ACCURACY = Gauge("anomaly_model_accuracy", "Anomaly detection model accuracy")
TRAINING_DURATION = Histogram(
    "anomaly_model_training_duration_seconds", "Time spent training anomaly models"
)
ACTIVE_MODELS = Gauge(
    "anomaly_active_models", "Number of active anomaly detection models"
)


class AnomalyDetector:
    """Machine learning-based anomaly detector for temperature readings."""

    def __init__(self, producer_manager: ProducerManager, redis_config: RedisConfig):
        self.producer_manager = producer_manager
        self.redis_config = redis_config
        self.redis_client: Optional[redis.Redis] = None

        # ML Models
        self.models: Dict[str, Dict[str, Any]] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.model_types = ["isolation_forest", "autoencoder", "lof", "knn"]

        # Data storage
        self.device_features: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.anomaly_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.model_performance: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Configuration
        self.min_training_samples = 100
        self.anomaly_threshold = 0.85
        self.retrain_interval_hours = 24
        self.feature_window_size = 20
        self.severity_thresholds = {
            SeverityLevel.LOW: 0.7,
            SeverityLevel.MEDIUM: 0.8,
            SeverityLevel.HIGH: 0.9,
            SeverityLevel.CRITICAL: 0.95,
        }

        # Background tasks
        self.training_task: Optional[asyncio.Task] = None
        self.maintenance_task: Optional[asyncio.Task] = None
        self.is_running = False

        # Initialize Redis connection
        asyncio.create_task(self._initialize_redis())

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
                decode_responses=False,  # We need binary data for pickle
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established for anomaly detector")

            # Load existing models
            await self._load_models()

            # Start background tasks
            self.is_running = True
            self.training_task = asyncio.create_task(self._training_loop())
            self.maintenance_task = asyncio.create_task(self._maintenance_loop())

        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise

    async def process_validated_reading(self, event: BaseEvent):
        """Process validated temperature reading for anomaly detection."""
        if not isinstance(event, TemperatureValidatedEvent):
            logger.warning(
                "Received non-validated reading event", event_type=type(event).__name__
            )
            return

        start_time = time.time()
        device_id = event.data.device_id

        try:
            # Only process valid readings
            if event.validation_status != "valid":
                logger.debug("Skipping invalid reading", device_id=device_id)
                return

            # Extract features
            features = self._extract_features(event)

            # Store features
            self.device_features[device_id].append(features)

            # Check for anomalies
            anomaly_result = await self._detect_anomalies(device_id, features)

            if anomaly_result["is_anomaly"]:
                # Create anomaly event
                anomaly_event = await self._create_anomaly_event(event, anomaly_result)

                # Send anomaly event
                await self.producer_manager.send_event(
                    "anomalies.detected", anomaly_event
                )

                # Check if alert should be triggered
                if anomaly_result["severity"] in [
                    SeverityLevel.HIGH,
                    SeverityLevel.CRITICAL,
                ]:
                    alert_event = await self._create_alert_event(anomaly_event)
                    await self.producer_manager.send_event(
                        "alerts.triggered", alert_event
                    )

                # Update anomaly history
                self.anomaly_history[device_id].append(
                    {
                        "timestamp": event.timestamp,
                        "anomaly_type": anomaly_result["anomaly_type"],
                        "confidence": anomaly_result["confidence"],
                        "severity": anomaly_result["severity"],
                    }
                )

                # Update metrics
                ANOMALIES_DETECTED.labels(
                    device_id=device_id, anomaly_type=anomaly_result["anomaly_type"]
                ).inc()

            # Update detection duration metric
            DETECTION_DURATION.observe(time.time() - start_time)

            logger.debug(
                "Anomaly detection completed",
                device_id=device_id,
                is_anomaly=anomaly_result["is_anomaly"],
                confidence=anomaly_result["confidence"],
            )

        except Exception as e:
            logger.error(
                "Failed to process validated reading", device_id=device_id, error=str(e)
            )
            raise

    def _extract_features(self, event: TemperatureValidatedEvent) -> Dict[str, float]:
        """Extract features from temperature reading."""
        features = {
            "temperature": event.data.temperature,
            "battery_level": event.data.battery_level or 0.0,
            "signal_strength": event.data.signal_strength or 0.0,
            "hour_of_day": event.timestamp.hour,
            "day_of_week": event.timestamp.weekday(),
            "minute_of_hour": event.timestamp.minute,
            "processing_time": event.processing_time_ms,
        }

        # Add derived features
        device_id = event.data.device_id
        if device_id in self.device_features and self.device_features[device_id]:
            recent_features = list(self.device_features[device_id])[
                -self.feature_window_size :
            ]

            if len(recent_features) > 1:
                # Temperature statistics
                recent_temps = [f["temperature"] for f in recent_features]
                features["temp_mean"] = np.mean(recent_temps)
                features["temp_std"] = np.std(recent_temps)
                features["temp_min"] = np.min(recent_temps)
                features["temp_max"] = np.max(recent_temps)
                features["temp_range"] = features["temp_max"] - features["temp_min"]

                # Temperature derivatives
                if len(recent_temps) >= 2:
                    features["temp_derivative"] = recent_temps[-1] - recent_temps[-2]
                    if len(recent_temps) >= 3:
                        features["temp_second_derivative"] = (
                            recent_temps[-1] - recent_temps[-2]
                        ) - (recent_temps[-2] - recent_temps[-3])

                # Battery trend
                recent_battery = [
                    f["battery_level"]
                    for f in recent_features
                    if f["battery_level"] > 0
                ]
                if len(recent_battery) >= 2:
                    features["battery_trend"] = recent_battery[-1] - recent_battery[0]

                # Signal strength statistics
                recent_signal = [
                    f["signal_strength"]
                    for f in recent_features
                    if f["signal_strength"] != 0
                ]
                if len(recent_signal) >= 2:
                    features["signal_mean"] = np.mean(recent_signal)
                    features["signal_std"] = np.std(recent_signal)

        return features

    async def _detect_anomalies(
        self, device_id: str, features: Dict[str, float]
    ) -> Dict[str, Any]:
        """Detect anomalies using trained models."""
        try:
            if device_id not in self.models:
                return {
                    "is_anomaly": False,
                    "confidence": 0.0,
                    "anomaly_type": "none",
                    "severity": SeverityLevel.LOW,
                    "model_scores": {},
                }

            device_models = self.models[device_id]
            scaler = self.scalers.get(device_id)

            if not scaler:
                return {
                    "is_anomaly": False,
                    "confidence": 0.0,
                    "anomaly_type": "none",
                    "severity": SeverityLevel.LOW,
                    "model_scores": {},
                }

            # Prepare features
            feature_vector = np.array(
                [
                    [
                        features.get("temperature", 0),
                        features.get("battery_level", 0),
                        features.get("signal_strength", 0),
                        features.get("hour_of_day", 0),
                        features.get("day_of_week", 0),
                        features.get("minute_of_hour", 0),
                        features.get("processing_time", 0),
                        features.get("temp_mean", features.get("temperature", 0)),
                        features.get("temp_std", 0),
                        features.get("temp_min", features.get("temperature", 0)),
                        features.get("temp_max", features.get("temperature", 0)),
                        features.get("temp_range", 0),
                        features.get("temp_derivative", 0),
                        features.get("temp_second_derivative", 0),
                        features.get("battery_trend", 0),
                        features.get("signal_mean", features.get("signal_strength", 0)),
                        features.get("signal_std", 0),
                    ]
                ]
            )

            # Scale features
            feature_vector_scaled = scaler.transform(feature_vector)

            # Get predictions from all models
            model_scores = {}
            for model_type, model in device_models.items():
                try:
                    if model_type == "isolation_forest":
                        score = model.decision_function(feature_vector_scaled)[0]
                        anomaly_score = 1 - ((score + 1) / 2)  # Convert to 0-1 scale
                    elif model_type == "autoencoder":
                        anomaly_score = model.decision_function(feature_vector_scaled)[
                            0
                        ]
                    elif model_type in ["lof", "knn"]:
                        anomaly_score = model.decision_function(feature_vector_scaled)[
                            0
                        ]
                    else:
                        continue

                    model_scores[model_type] = anomaly_score

                except Exception as e:
                    logger.warning(
                        f"Model {model_type} prediction failed",
                        device_id=device_id,
                        error=str(e),
                    )

            if not model_scores:
                return {
                    "is_anomaly": False,
                    "confidence": 0.0,
                    "anomaly_type": "none",
                    "severity": SeverityLevel.LOW,
                    "model_scores": {},
                }

            # Ensemble prediction
            ensemble_score = np.mean(list(model_scores.values()))
            is_anomaly = ensemble_score > self.anomaly_threshold

            # Determine anomaly type
            anomaly_type = self._determine_anomaly_type(features, model_scores)

            # Determine severity
            severity = self._determine_severity(ensemble_score)

            return {
                "is_anomaly": is_anomaly,
                "confidence": ensemble_score,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "model_scores": model_scores,
            }

        except Exception as e:
            logger.error(
                "Failed to detect anomalies", device_id=device_id, error=str(e)
            )
            return {
                "is_anomaly": False,
                "confidence": 0.0,
                "anomaly_type": "error",
                "severity": SeverityLevel.LOW,
                "model_scores": {},
            }

    def _determine_anomaly_type(
        self, features: Dict[str, float], model_scores: Dict[str, float]
    ) -> str:
        """Determine the type of anomaly detected."""
        # Rule-based anomaly type classification
        temp = features.get("temperature", 0)
        temp_derivative = features.get("temp_derivative", 0)
        battery_level = features.get("battery_level", 100)
        signal_strength = features.get("signal_strength", -50)

        # Temperature-based anomalies
        if abs(temp_derivative) > 10:
            return "temperature_spike"
        elif temp > 200:
            return "temperature_high"
        elif temp < 32:
            return "temperature_low"
        elif battery_level < 20:
            return "battery_low"
        elif signal_strength < -80:
            return "signal_weak"

        # Model-based classification
        if model_scores.get("isolation_forest", 0) > 0.9:
            return "isolation_anomaly"
        elif model_scores.get("autoencoder", 0) > 0.9:
            return "reconstruction_anomaly"
        elif model_scores.get("lof", 0) > 0.9:
            return "local_outlier"
        elif model_scores.get("knn", 0) > 0.9:
            return "distance_anomaly"

        return "general_anomaly"

    def _determine_severity(self, confidence: float) -> SeverityLevel:
        """Determine severity level based on confidence score."""
        if confidence >= self.severity_thresholds[SeverityLevel.CRITICAL]:
            return SeverityLevel.CRITICAL
        elif confidence >= self.severity_thresholds[SeverityLevel.HIGH]:
            return SeverityLevel.HIGH
        elif confidence >= self.severity_thresholds[SeverityLevel.MEDIUM]:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    async def _create_anomaly_event(
        self, original_event: TemperatureValidatedEvent, anomaly_result: Dict[str, Any]
    ) -> AnomalyDetectedEvent:
        """Create an anomaly detected event."""
        # Calculate expected range
        device_id = original_event.data.device_id
        expected_range = await self._calculate_expected_range(device_id)

        # Get historical statistics
        historical_stats = await self._get_historical_stats(device_id)

        anomaly_details = AnomalyDetails(
            anomaly_type=anomaly_result["anomaly_type"],
            confidence_score=anomaly_result["confidence"],
            severity=anomaly_result["severity"],
            expected_range=expected_range,
            actual_value=original_event.data.temperature,
            historical_stats=historical_stats,
        )

        return AnomalyDetectedEvent(
            event_id=f"anomaly_{original_event.event_id}",
            source="anomaly_detector",
            device_id=device_id,
            temperature_reading=original_event.data,
            anomaly_details=anomaly_details,
            detection_time_ms=(time.time() * 1000)
            - (original_event.timestamp.timestamp() * 1000),
        )

    async def _create_alert_event(
        self, anomaly_event: AnomalyDetectedEvent
    ) -> AlertTriggeredEvent:
        """Create an alert triggered event."""
        device_id = anomaly_event.device_id
        severity = anomaly_event.anomaly_details.severity

        # Define alert actions based on severity
        actions = []
        if severity == SeverityLevel.HIGH:
            actions.append(
                AlertAction(
                    action_type="notification",
                    target="mobile_app",
                    parameters={"priority": "high"},
                )
            )
        elif severity == SeverityLevel.CRITICAL:
            actions.extend(
                [
                    AlertAction(
                        action_type="notification",
                        target="mobile_app",
                        parameters={"priority": "critical"},
                    ),
                    AlertAction(
                        action_type="email",
                        target="admin@example.com",
                        parameters={"template": "critical_alert"},
                    ),
                ]
            )

        # Create alert message
        anomaly_type = anomaly_event.anomaly_details.anomaly_type
        confidence = anomaly_event.anomaly_details.confidence_score
        temperature = anomaly_event.temperature_reading.temperature

        message = f"Anomaly detected on device {device_id}: {anomaly_type} (confidence: {confidence:.2f}, temperature: {temperature}°F)"

        # Set expiration time
        expires_at = datetime.utcnow() + timedelta(hours=24)

        return AlertTriggeredEvent(
            event_id=f"alert_{anomaly_event.event_id}",
            source="anomaly_detector",
            device_id=device_id,
            alert_type=anomaly_type,
            severity=severity,
            message=message,
            anomaly_event=anomaly_event,
            actions=actions,
            expires_at=expires_at,
        )

    async def _calculate_expected_range(self, device_id: str) -> Dict[str, float]:
        """Calculate expected temperature range for a device."""
        try:
            if (
                device_id not in self.device_features
                or not self.device_features[device_id]
            ):
                return {"min": 0.0, "max": 500.0}

            recent_features = list(self.device_features[device_id])[
                -100:
            ]  # Last 100 readings
            temperatures = [f["temperature"] for f in recent_features]

            if not temperatures:
                return {"min": 0.0, "max": 500.0}

            mean_temp = np.mean(temperatures)
            std_temp = np.std(temperatures)

            return {
                "min": mean_temp - (2 * std_temp),
                "max": mean_temp + (2 * std_temp),
            }

        except Exception as e:
            logger.error(
                "Failed to calculate expected range", device_id=device_id, error=str(e)
            )
            return {"min": 0.0, "max": 500.0}

    async def _get_historical_stats(self, device_id: str) -> Dict[str, Any]:
        """Get historical statistics for a device."""
        try:
            if (
                device_id not in self.device_features
                or not self.device_features[device_id]
            ):
                return {}

            recent_features = list(self.device_features[device_id])[
                -1000:
            ]  # Last 1000 readings
            temperatures = [f["temperature"] for f in recent_features]

            if not temperatures:
                return {}

            return {
                "mean_temperature": np.mean(temperatures),
                "std_temperature": np.std(temperatures),
                "min_temperature": np.min(temperatures),
                "max_temperature": np.max(temperatures),
                "median_temperature": np.median(temperatures),
                "sample_count": len(temperatures),
                "anomaly_count": len(self.anomaly_history.get(device_id, [])),
                "last_anomaly": (
                    self.anomaly_history[device_id][-1]["timestamp"].isoformat()
                    if self.anomaly_history.get(device_id)
                    else None
                ),
            }

        except Exception as e:
            logger.error(
                "Failed to get historical stats", device_id=device_id, error=str(e)
            )
            return {}

    async def _training_loop(self):
        """Background task for model training."""
        while self.is_running:
            try:
                start_time = time.time()

                # Train models for all devices
                await self._train_all_models()

                # Update training duration metric
                TRAINING_DURATION.observe(time.time() - start_time)

                # Wait for next training cycle
                await asyncio.sleep(self.retrain_interval_hours * 3600)

            except Exception as e:
                logger.error("Error in training loop", error=str(e))
                await asyncio.sleep(3600)  # Wait before retrying

    async def _train_all_models(self):
        """Train models for all devices."""
        for device_id in list(self.device_features.keys()):
            if len(self.device_features[device_id]) >= self.min_training_samples:
                try:
                    await self._train_device_models(device_id)
                except Exception as e:
                    logger.error(
                        "Failed to train models for device",
                        device_id=device_id,
                        error=str(e),
                    )

    async def _train_device_models(self, device_id: str):
        """Train anomaly detection models for a specific device."""
        try:
            logger.info("Training models for device", device_id=device_id)

            # Prepare training data
            features_list = list(self.device_features[device_id])

            # Convert to feature matrix
            feature_matrix = []
            for features in features_list:
                feature_vector = [
                    features.get("temperature", 0),
                    features.get("battery_level", 0),
                    features.get("signal_strength", 0),
                    features.get("hour_of_day", 0),
                    features.get("day_of_week", 0),
                    features.get("minute_of_hour", 0),
                    features.get("processing_time", 0),
                    features.get("temp_mean", features.get("temperature", 0)),
                    features.get("temp_std", 0),
                    features.get("temp_min", features.get("temperature", 0)),
                    features.get("temp_max", features.get("temperature", 0)),
                    features.get("temp_range", 0),
                    features.get("temp_derivative", 0),
                    features.get("temp_second_derivative", 0),
                    features.get("battery_trend", 0),
                    features.get("signal_mean", features.get("signal_strength", 0)),
                    features.get("signal_std", 0),
                ]
                feature_matrix.append(feature_vector)

            X = np.array(feature_matrix)

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            self.scalers[device_id] = scaler

            # Train multiple models
            models = {}

            # Isolation Forest
            try:
                iso_forest = IsolationForest(
                    contamination=0.1, random_state=42, n_jobs=-1
                )
                iso_forest.fit(X_scaled)
                models["isolation_forest"] = iso_forest
            except Exception as e:
                logger.warning(
                    "Failed to train Isolation Forest",
                    device_id=device_id,
                    error=str(e),
                )

            # Local Outlier Factor
            try:
                lof = LOF(contamination=0.1)
                lof.fit(X_scaled)
                models["lof"] = lof
            except Exception as e:
                logger.warning("Failed to train LOF", device_id=device_id, error=str(e))

            # K-Nearest Neighbors
            try:
                knn = KNN(contamination=0.1)
                knn.fit(X_scaled)
                models["knn"] = knn
            except Exception as e:
                logger.warning("Failed to train KNN", device_id=device_id, error=str(e))

            # AutoEncoder (if enough data)
            if len(X_scaled) >= 500:
                try:
                    autoencoder = AutoEncoder(contamination=0.1, epochs=50, verbose=0)
                    autoencoder.fit(X_scaled)
                    models["autoencoder"] = autoencoder
                except Exception as e:
                    logger.warning(
                        "Failed to train AutoEncoder", device_id=device_id, error=str(e)
                    )

            # Store models
            self.models[device_id] = models

            # Save models to Redis
            await self._save_models(device_id)

            # Update metrics
            ACTIVE_MODELS.set(len(self.models))

            logger.info(
                "Model training completed",
                device_id=device_id,
                models_trained=list(models.keys()),
                training_samples=len(X_scaled),
            )

        except Exception as e:
            logger.error(
                "Failed to train device models", device_id=device_id, error=str(e)
            )
            raise

    async def _save_models(self, device_id: str):
        """Save trained models to Redis."""
        try:
            if not self.redis_client:
                return

            # Save models
            models_data = {}
            for model_type, model in self.models[device_id].items():
                models_data[model_type] = pickle.dumps(model)

            await self.redis_client.hset(
                f"anomaly_models:{device_id}", mapping=models_data
            )

            # Save scaler
            if device_id in self.scalers:
                scaler_data = pickle.dumps(self.scalers[device_id])
                await self.redis_client.set(f"anomaly_scaler:{device_id}", scaler_data)

            # Set expiration
            await self.redis_client.expire(
                f"anomaly_models:{device_id}", 86400 * 7
            )  # 7 days
            await self.redis_client.expire(f"anomaly_scaler:{device_id}", 86400 * 7)

        except Exception as e:
            logger.error(
                "Failed to save models to Redis", device_id=device_id, error=str(e)
            )

    async def _load_models(self):
        """Load existing models from Redis."""
        try:
            if not self.redis_client:
                return

            # Get all model keys
            model_keys = await self.redis_client.keys("anomaly_models:*")

            for key in model_keys:
                device_id = key.decode("utf-8").split(":")[1]

                try:
                    # Load models
                    models_data = await self.redis_client.hgetall(key)
                    models = {}

                    for model_type, model_data in models_data.items():
                        model_type = model_type.decode("utf-8")
                        models[model_type] = pickle.loads(model_data)

                    self.models[device_id] = models

                    # Load scaler
                    scaler_data = await self.redis_client.get(
                        f"anomaly_scaler:{device_id}"
                    )
                    if scaler_data:
                        self.scalers[device_id] = pickle.loads(scaler_data)

                    logger.info(
                        "Models loaded from Redis",
                        device_id=device_id,
                        models=list(models.keys()),
                    )

                except Exception as e:
                    logger.warning(
                        "Failed to load models for device",
                        device_id=device_id,
                        error=str(e),
                    )

            # Update metrics
            ACTIVE_MODELS.set(len(self.models))

        except Exception as e:
            logger.error("Failed to load models from Redis", error=str(e))

    async def _maintenance_loop(self):
        """Background task for maintenance operations."""
        while self.is_running:
            try:
                await self._cleanup_old_anomalies()
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error("Error in maintenance loop", error=str(e))
                await asyncio.sleep(300)  # Wait before retrying

    async def _cleanup_old_anomalies(self):
        """Clean up old anomaly history."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=30)

            for device_id in list(self.anomaly_history.keys()):
                original_count = len(self.anomaly_history[device_id])
                self.anomaly_history[device_id] = [
                    anomaly
                    for anomaly in self.anomaly_history[device_id]
                    if anomaly["timestamp"] > cutoff_time
                ]
                cleaned_count = len(self.anomaly_history[device_id])

                if original_count != cleaned_count:
                    logger.debug(
                        "Cleaned up old anomalies",
                        device_id=device_id,
                        removed=original_count - cleaned_count,
                    )

        except Exception as e:
            logger.error("Failed to cleanup old anomalies", error=str(e))

    async def retrain_model(self, device_id: Optional[str] = None):
        """Manually retrain models."""
        try:
            if device_id:
                if (
                    device_id in self.device_features
                    and len(self.device_features[device_id])
                    >= self.min_training_samples
                ):
                    await self._train_device_models(device_id)
                    return {"status": "retraining_completed", "device_id": device_id}
                else:
                    return {"status": "insufficient_data", "device_id": device_id}
            else:
                await self._train_all_models()
                return {"status": "retraining_all_completed"}

        except Exception as e:
            logger.error(
                "Manual model retraining failed", device_id=device_id, error=str(e)
            )
            return {"status": "retraining_failed", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "is_running": self.is_running,
            "active_models": len(self.models),
            "devices_monitored": len(self.device_features),
            "total_anomalies": sum(
                len(anomalies) for anomalies in self.anomaly_history.values()
            ),
            "model_types": self.model_types,
            "anomaly_threshold": self.anomaly_threshold,
            "min_training_samples": self.min_training_samples,
            "background_tasks": {
                "training": (
                    not self.training_task.done() if self.training_task else False
                ),
                "maintenance": (
                    not self.maintenance_task.done() if self.maintenance_task else False
                ),
            },
        }

    async def shutdown(self):
        """Shutdown the service."""
        try:
            self.is_running = False

            # Cancel background tasks
            if self.training_task:
                self.training_task.cancel()
            if self.maintenance_task:
                self.maintenance_task.cancel()

            # Save models before shutdown
            for device_id in self.models:
                await self._save_models(device_id)

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()

            logger.info("Anomaly detector shutdown complete")

        except Exception as e:
            logger.error("Error during shutdown", error=str(e))
