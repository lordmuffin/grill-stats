import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.alert_models import Alert, AlertCorrelation, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class AlertCorrelator:
    """
    Advanced alert correlation engine to prevent notification fatigue.

    Features:
    - Temporal correlation (time-based grouping)
    - Spatial correlation (source/service based)
    - Causal correlation (root cause analysis)
    - Semantic similarity correlation
    - Machine learning-based pattern detection

    Target: 80% duplicate alert reduction
    """

    def __init__(self, db_session: AsyncSession, redis_client: redis.Redis):
        self.db = db_session
        self.redis = redis_client

        # Correlation configuration
        self.config = {
            "temporal_window": 300,  # 5 minutes
            "spatial_distance_threshold": 0.8,
            "semantic_similarity_threshold": 0.7,
            "causality_confidence_threshold": 0.6,
            "max_correlation_group_size": 20,
            "correlation_decay_hours": 24,
            "ml_model_update_interval": 3600,  # 1 hour
        }

        # Initialize ML components
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words="english", ngram_range=(1, 2))

        # Correlation patterns cache
        self.correlation_patterns = {}
        self.last_model_update = datetime.utcnow()

        # Performance metrics
        self.correlation_metrics = {
            "correlations_found": 0,
            "false_positives": 0,
            "processing_times": [],
            "accuracy_scores": [],
        }

    async def correlate_alert(self, alert: Alert) -> List[AlertCorrelation]:
        """
        Find correlations for a given alert using multiple correlation techniques.

        Returns list of AlertCorrelation objects with confidence scores.
        """
        start_time = datetime.utcnow()
        correlations = []

        try:
            # Get candidate alerts for correlation
            candidates = await self._get_correlation_candidates(alert)

            if not candidates:
                return correlations

            # Apply different correlation techniques
            temporal_correlations = await self._find_temporal_correlations(alert, candidates)
            spatial_correlations = await self._find_spatial_correlations(alert, candidates)
            semantic_correlations = await self._find_semantic_correlations(alert, candidates)
            causal_correlations = await self._find_causal_correlations(alert, candidates)

            # Combine and rank correlations
            all_correlations = temporal_correlations + spatial_correlations + semantic_correlations + causal_correlations

            # Remove duplicates and rank by confidence
            unique_correlations = await self._deduplicate_correlations(all_correlations)
            ranked_correlations = await self._rank_correlations(unique_correlations)

            # Apply ML-based filtering
            filtered_correlations = await self._apply_ml_filtering(ranked_correlations)

            # Update correlation patterns
            await self._update_correlation_patterns(alert, filtered_correlations)

            # Update performance metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.correlation_metrics["processing_times"].append(processing_time)
            self.correlation_metrics["correlations_found"] += len(filtered_correlations)

            return filtered_correlations

        except Exception as e:
            logger.error(f"Error correlating alert {alert.id}: {str(e)}", exc_info=True)
            return []

    async def _get_correlation_candidates(self, alert: Alert) -> List[Alert]:
        """Get candidate alerts for correlation within time window."""
        window_start = datetime.utcnow() - timedelta(seconds=self.config["temporal_window"])

        result = await self.db.execute(
            select(Alert)
            .where(
                and_(
                    Alert.id != alert.id,
                    Alert.created_at >= window_start,
                    Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
                )
            )
            .order_by(Alert.created_at.desc())
            .limit(100)  # Limit candidates for performance
        )

        return result.scalars().all()

    async def _find_temporal_correlations(self, alert: Alert, candidates: List[Alert]) -> List[AlertCorrelation]:
        """Find alerts that occurred within temporal proximity."""
        correlations = []

        for candidate in candidates:
            time_diff = abs((alert.created_at - candidate.created_at).total_seconds())

            if time_diff <= self.config["temporal_window"]:
                # Calculate confidence based on time proximity
                confidence = 1.0 - (time_diff / self.config["temporal_window"])

                # Boost confidence for same severity/source
                if alert.severity == candidate.severity:
                    confidence *= 1.2
                if alert.source == candidate.source:
                    confidence *= 1.3

                confidence = min(confidence, 1.0)

                if confidence > 0.5:  # Minimum threshold
                    correlation = AlertCorrelation(
                        alert_id=alert.id,
                        correlation_id=f"temporal_{candidate.id}",
                        correlation_type="temporal",
                        confidence_score=confidence,
                    )
                    correlations.append(correlation)

        return correlations

    async def _find_spatial_correlations(self, alert: Alert, candidates: List[Alert]) -> List[AlertCorrelation]:
        """Find alerts from related sources/services."""
        correlations = []

        for candidate in candidates:
            spatial_score = await self._calculate_spatial_similarity(alert, candidate)

            if spatial_score > self.config["spatial_distance_threshold"]:
                correlation = AlertCorrelation(
                    alert_id=alert.id,
                    correlation_id=f"spatial_{candidate.id}",
                    correlation_type="spatial",
                    confidence_score=spatial_score,
                )
                correlations.append(correlation)

        return correlations

    async def _calculate_spatial_similarity(self, alert1: Alert, alert2: Alert) -> float:
        """Calculate spatial similarity between two alerts."""
        score = 0.0

        # Source similarity
        if alert1.source == alert2.source:
            score += 0.4
        elif alert1.source and alert2.source:
            # Calculate string similarity
            source_sim = self._calculate_string_similarity(alert1.source, alert2.source)
            score += source_sim * 0.3

        # Label similarity
        if alert1.labels and alert2.labels:
            label_sim = self._calculate_label_similarity(alert1.labels, alert2.labels)
            score += label_sim * 0.3

        # Service/component similarity
        service1 = alert1.labels.get("service") or alert1.annotations.get("service")
        service2 = alert2.labels.get("service") or alert2.annotations.get("service")

        if service1 and service2:
            if service1 == service2:
                score += 0.3
            else:
                service_sim = self._calculate_string_similarity(service1, service2)
                score += service_sim * 0.2

        return min(score, 1.0)

    async def _find_semantic_correlations(self, alert: Alert, candidates: List[Alert]) -> List[AlertCorrelation]:
        """Find alerts with similar content using semantic analysis."""
        correlations = []

        # Prepare text for analysis
        alert_text = self._prepare_alert_text(alert)
        candidate_texts = [self._prepare_alert_text(candidate) for candidate in candidates]

        if not alert_text or not any(candidate_texts):
            return correlations

        try:
            # Calculate TF-IDF vectors
            all_texts = [alert_text] + candidate_texts
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)

            # Calculate cosine similarity
            similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

            for i, similarity in enumerate(similarities):
                if similarity > self.config["semantic_similarity_threshold"]:
                    candidate = candidates[i]

                    correlation = AlertCorrelation(
                        alert_id=alert.id,
                        correlation_id=f"semantic_{candidate.id}",
                        correlation_type="semantic",
                        confidence_score=similarity,
                    )
                    correlations.append(correlation)

        except Exception as e:
            logger.error(f"Error in semantic correlation: {str(e)}")

        return correlations

    def _prepare_alert_text(self, alert: Alert) -> str:
        """Prepare alert text for semantic analysis."""
        text_parts = []

        if alert.title:
            text_parts.append(alert.title)

        if alert.description:
            text_parts.append(alert.description)

        if alert.annotations:
            for key, value in alert.annotations.items():
                if isinstance(value, str):
                    text_parts.append(f"{key}: {value}")

        return " ".join(text_parts)

    async def _find_causal_correlations(self, alert: Alert, candidates: List[Alert]) -> List[AlertCorrelation]:
        """Find alerts that might be causally related."""
        correlations = []

        # Define causal relationships
        causal_patterns = await self._get_causal_patterns()

        for candidate in candidates:
            causality_score = await self._calculate_causality_score(alert, candidate, causal_patterns)

            if causality_score > self.config["causality_confidence_threshold"]:
                correlation = AlertCorrelation(
                    alert_id=alert.id,
                    correlation_id=f"causal_{candidate.id}",
                    correlation_type="causal",
                    confidence_score=causality_score,
                )
                correlations.append(correlation)

        return correlations

    async def _get_causal_patterns(self) -> Dict[str, Any]:
        """Get learned causal patterns from Redis cache."""
        patterns_json = await self.redis.get("causal_patterns")

        if patterns_json:
            return json.loads(patterns_json)

        # Default patterns
        return {
            "database_connection": ["application_error", "timeout_error"],
            "disk_full": ["write_error", "application_crash"],
            "network_error": ["service_unavailable", "timeout_error"],
            "memory_leak": ["out_of_memory", "application_crash"],
            "cpu_spike": ["slow_response", "timeout_error"],
        }

    async def _calculate_causality_score(self, alert: Alert, candidate: Alert, patterns: Dict[str, Any]) -> float:
        """Calculate causality score between two alerts."""
        score = 0.0

        # Time-based causality (candidate should occur before alert)
        time_diff = (alert.created_at - candidate.created_at).total_seconds()
        if time_diff <= 0:
            return 0.0  # Candidate occurred after alert

        # Normalize time difference (0-1 scale)
        time_factor = max(0, 1 - (time_diff / 3600))  # 1 hour window

        # Check for known causal patterns
        alert_type = self._extract_alert_type(alert)
        candidate_type = self._extract_alert_type(candidate)

        if candidate_type in patterns:
            if alert_type in patterns[candidate_type]:
                score += 0.7

        # Check for service dependency
        if self._check_service_dependency(alert, candidate):
            score += 0.3

        return min(score * time_factor, 1.0)

    def _extract_alert_type(self, alert: Alert) -> str:
        """Extract alert type from alert title/description."""
        text = f"{alert.title} {alert.description}".lower()

        # Simple keyword matching
        if "database" in text or "db" in text:
            return "database_connection"
        elif "disk" in text or "storage" in text:
            return "disk_full"
        elif "network" in text or "connection" in text:
            return "network_error"
        elif "memory" in text or "oom" in text:
            return "memory_leak"
        elif "cpu" in text or "processor" in text:
            return "cpu_spike"
        else:
            return "unknown"

    def _check_service_dependency(self, alert: Alert, candidate: Alert) -> bool:
        """Check if alerts are from dependent services."""
        # Simple implementation - check if services are related
        alert_service = alert.labels.get("service") or alert.source
        candidate_service = candidate.labels.get("service") or candidate.source

        if not alert_service or not candidate_service:
            return False

        # Check for known service dependencies
        dependencies = {
            "frontend": ["backend", "database"],
            "backend": ["database", "cache"],
            "api": ["database", "auth"],
            "web": ["api", "cdn"],
        }

        for service, deps in dependencies.items():
            if service in alert_service.lower() and candidate_service.lower() in deps:
                return True

        return False

    async def _deduplicate_correlations(self, correlations: List[AlertCorrelation]) -> List[AlertCorrelation]:
        """Remove duplicate correlations."""
        seen = set()
        unique_correlations = []

        for correlation in correlations:
            key = (correlation.correlation_id, correlation.correlation_type)
            if key not in seen:
                seen.add(key)
                unique_correlations.append(correlation)

        return unique_correlations

    async def _rank_correlations(self, correlations: List[AlertCorrelation]) -> List[AlertCorrelation]:
        """Rank correlations by confidence score."""
        return sorted(correlations, key=lambda x: x.confidence_score, reverse=True)

    async def _apply_ml_filtering(self, correlations: List[AlertCorrelation]) -> List[AlertCorrelation]:
        """Apply machine learning-based filtering to correlations."""
        if not correlations:
            return correlations

        # Update ML models if needed
        if (datetime.utcnow() - self.last_model_update).total_seconds() > self.config["ml_model_update_interval"]:
            await self._update_ml_models()

        # Apply clustering to group related correlations
        filtered_correlations = await self._apply_clustering(correlations)

        # Apply confidence boosting based on historical accuracy
        boosted_correlations = await self._apply_confidence_boosting(filtered_correlations)

        return boosted_correlations

    async def _apply_clustering(self, correlations: List[AlertCorrelation]) -> List[AlertCorrelation]:
        """Apply DBSCAN clustering to group related correlations."""
        if len(correlations) < 2:
            return correlations

        try:
            # Prepare feature matrix
            features = []
            for correlation in correlations:
                feature = [
                    correlation.confidence_score,
                    hash(correlation.correlation_type) % 1000 / 1000,  # Normalized hash
                    hash(correlation.correlation_id) % 1000 / 1000,
                ]
                features.append(feature)

            # Apply DBSCAN clustering
            clustering = DBSCAN(eps=0.3, min_samples=2)
            labels = clustering.fit_predict(features)

            # Group correlations by cluster
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                clusters[label].append(correlations[i])

            # Select best correlation from each cluster
            filtered_correlations = []
            for label, cluster_correlations in clusters.items():
                if label != -1:  # Not noise
                    # Select highest confidence correlation from cluster
                    best_correlation = max(cluster_correlations, key=lambda x: x.confidence_score)
                    filtered_correlations.append(best_correlation)
                else:
                    # Keep all noise points (isolated correlations)
                    filtered_correlations.extend(cluster_correlations)

            return filtered_correlations

        except Exception as e:
            logger.error(f"Error in clustering: {str(e)}")
            return correlations

    async def _apply_confidence_boosting(self, correlations: List[AlertCorrelation]) -> List[AlertCorrelation]:
        """Boost confidence scores based on historical accuracy."""
        accuracy_data = await self._get_correlation_accuracy_data()

        for correlation in correlations:
            correlation_type = correlation.correlation_type

            if correlation_type in accuracy_data:
                accuracy = accuracy_data[correlation_type]
                # Boost confidence for historically accurate correlation types
                correlation.confidence_score *= 1.0 + accuracy * 0.2
                correlation.confidence_score = min(correlation.confidence_score, 1.0)

        return correlations

    async def _get_correlation_accuracy_data(self) -> Dict[str, float]:
        """Get historical accuracy data for correlation types."""
        accuracy_json = await self.redis.get("correlation_accuracy")

        if accuracy_json:
            return json.loads(accuracy_json)

        # Default accuracy scores
        return {"temporal": 0.8, "spatial": 0.7, "semantic": 0.6, "causal": 0.5}

    async def _update_correlation_patterns(self, alert: Alert, correlations: List[AlertCorrelation]):
        """Update correlation patterns for future analysis."""
        pattern_key = f"pattern_{alert.source}_{alert.severity}"

        pattern_data = {
            "alert_id": alert.id,
            "correlations": len(correlations),
            "correlation_types": [c.correlation_type for c in correlations],
            "confidence_scores": [c.confidence_score for c in correlations],
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.redis.lpush(f"correlation_patterns:{pattern_key}", json.dumps(pattern_data))
        await self.redis.ltrim(f"correlation_patterns:{pattern_key}", 0, 99)  # Keep last 100

    async def _update_ml_models(self):
        """Update machine learning models with recent data."""
        try:
            # Get recent correlation data
            recent_data = await self._get_recent_correlation_data()

            if len(recent_data) > 100:  # Need sufficient data
                # Update TF-IDF vectorizer with recent alert texts
                alert_texts = [item["alert_text"] for item in recent_data]
                self.tfidf_vectorizer.fit(alert_texts)

                # Update accuracy scores
                await self._update_accuracy_scores(recent_data)

                self.last_model_update = datetime.utcnow()
                logger.info("ML models updated successfully")

        except Exception as e:
            logger.error(f"Error updating ML models: {str(e)}")

    async def _get_recent_correlation_data(self) -> List[Dict[str, Any]]:
        """Get recent correlation data for ML model training."""
        # Get recent alerts with correlations
        recent_alerts = await self.db.execute(
            select(Alert)
            .options(selectinload(Alert.correlations))
            .where(Alert.created_at >= datetime.utcnow() - timedelta(days=7))
            .order_by(Alert.created_at.desc())
            .limit(1000)
        )

        data = []
        for alert in recent_alerts.scalars().all():
            alert_text = self._prepare_alert_text(alert)

            for correlation in alert.correlations:
                data.append(
                    {
                        "alert_id": alert.id,
                        "alert_text": alert_text,
                        "correlation_type": correlation.correlation_type,
                        "confidence_score": correlation.confidence_score,
                        "created_at": alert.created_at.isoformat(),
                    }
                )

        return data

    async def _update_accuracy_scores(self, correlation_data: List[Dict[str, Any]]):
        """Update accuracy scores for correlation types."""
        type_stats = defaultdict(lambda: {"total": 0, "accurate": 0})

        for item in correlation_data:
            correlation_type = item["correlation_type"]
            confidence = item["confidence_score"]

            type_stats[correlation_type]["total"] += 1

            # Consider high confidence correlations as accurate
            if confidence > 0.7:
                type_stats[correlation_type]["accurate"] += 1

        # Calculate accuracy rates
        accuracy_data = {}
        for correlation_type, stats in type_stats.items():
            if stats["total"] > 0:
                accuracy_data[correlation_type] = stats["accurate"] / stats["total"]

        # Store in Redis
        await self.redis.set("correlation_accuracy", json.dumps(accuracy_data))

    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using simple metrics."""
        if not str1 or not str2:
            return 0.0

        # Simple Jaccard similarity
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _calculate_label_similarity(self, labels1: Dict[str, str], labels2: Dict[str, str]) -> float:
        """Calculate similarity between label sets."""
        if not labels1 or not labels2:
            return 0.0

        common_keys = set(labels1.keys()) & set(labels2.keys())
        total_keys = set(labels1.keys()) | set(labels2.keys())

        if not total_keys:
            return 0.0

        matching_values = sum(1 for key in common_keys if labels1[key] == labels2[key])

        return matching_values / len(total_keys)

    async def get_correlation_statistics(self) -> Dict[str, Any]:
        """Get correlation statistics and performance metrics."""
        processing_times = self.correlation_metrics["processing_times"]

        stats = {
            "correlations_found": self.correlation_metrics["correlations_found"],
            "false_positives": self.correlation_metrics["false_positives"],
            "accuracy_rate": 1
            - (self.correlation_metrics["false_positives"] / max(self.correlation_metrics["correlations_found"], 1)),
        }

        if processing_times:
            stats.update(
                {
                    "avg_processing_time": sum(processing_times) / len(processing_times),
                    "max_processing_time": max(processing_times),
                    "min_processing_time": min(processing_times),
                }
            )

        return stats

    async def feedback_correlation(self, correlation_id: str, is_accurate: bool):
        """Provide feedback on correlation accuracy for ML improvement."""
        if is_accurate:
            await self.redis.incr("correlation_feedback:accurate")
        else:
            await self.redis.incr("correlation_feedback:inaccurate")
            self.correlation_metrics["false_positives"] += 1

        # Store detailed feedback
        feedback_data = {
            "correlation_id": correlation_id,
            "is_accurate": is_accurate,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.redis.lpush("correlation_feedback", json.dumps(feedback_data))
        await self.redis.ltrim("correlation_feedback", 0, 9999)  # Keep last 10000
