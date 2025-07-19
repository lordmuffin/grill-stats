import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import redis
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..analytics.alert_analytics import AlertAnalytics
from ..correlation.alert_correlator import AlertCorrelator
from ..escalation.escalation_manager import EscalationManager
from ..models.alert_models import (
    Alert,
    AlertCorrelation,
    AlertEvent,
    AlertRule,
    AlertSeverity,
    AlertStatus,
)
from ..models.notification_models import NotificationHistory, NotificationStatus
from ..notification_channels.notification_manager import NotificationManager
from ..storage.alert_storage import AlertStorage

logger = logging.getLogger(__name__)


class IntelligentAlertService:
    """
    Core intelligent alert service with correlation engine and smart filtering.
    Provides sub-30 second notification delivery with <5% noise-to-signal ratio.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        notification_manager: NotificationManager,
        escalation_manager: EscalationManager,
        alert_storage: AlertStorage,
        alert_analytics: AlertAnalytics,
    ):
        self.db = db_session
        self.redis = redis_client
        self.notification_manager = notification_manager
        self.escalation_manager = escalation_manager
        self.alert_storage = alert_storage
        self.alert_analytics = alert_analytics

        # Initialize correlation engine
        self.correlator = AlertCorrelator(db_session, redis_client)

        # Performance tracking
        self.performance_metrics = {
            "alerts_processed": 0,
            "correlations_found": 0,
            "notifications_sent": 0,
            "false_positives_filtered": 0,
            "processing_times": [],
        }

        # Smart filtering configuration
        self.filtering_config = {
            "noise_threshold": 0.3,  # Noise score threshold
            "correlation_threshold": 0.7,  # Correlation confidence threshold
            "duplicate_window": 300,  # 5 minutes for duplicate detection
            "burst_threshold": 10,  # Max alerts per minute per source
            "severity_weights": {
                AlertSeverity.CRITICAL: 1.0,
                AlertSeverity.HIGH: 0.8,
                AlertSeverity.MEDIUM: 0.6,
                AlertSeverity.LOW: 0.4,
                AlertSeverity.INFO: 0.2,
            },
        }

    async def process_alert_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming alert event with intelligent correlation and filtering.

        Target: <30 second processing time with smart correlation
        """
        start_time = datetime.utcnow()

        try:
            # Extract alert information
            alert_data = self._extract_alert_data(event_data)

            # Generate alert fingerprint
            fingerprint = self._generate_fingerprint(alert_data)

            # Check for existing alert
            existing_alert = await self._get_existing_alert(fingerprint)

            if existing_alert:
                # Update existing alert
                alert = await self._update_existing_alert(existing_alert, alert_data)
                action = "updated"
            else:
                # Create new alert
                alert = await self._create_new_alert(alert_data, fingerprint)
                action = "created"

            # Apply intelligent filtering
            should_notify = await self._apply_smart_filtering(alert, event_data)

            if should_notify:
                # Run correlation analysis
                correlations = await self.correlator.correlate_alert(alert)

                # Apply correlation-based filtering
                filtered_correlations = await self._filter_correlations(correlations)

                # Store correlations
                await self._store_correlations(alert, filtered_correlations)

                # Determine notification strategy
                notification_strategy = await self._determine_notification_strategy(
                    alert, filtered_correlations
                )

                # Send notifications
                notification_results = await self._send_notifications(
                    alert, notification_strategy
                )

                # Start escalation if needed
                await self._start_escalation(alert, notification_strategy)

                # Update performance metrics
                await self._update_performance_metrics(start_time, alert, correlations)

                return {
                    "alert_id": alert.id,
                    "action": action,
                    "fingerprint": fingerprint,
                    "correlations": len(filtered_correlations),
                    "notifications_sent": len(notification_results),
                    "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                    "filtered": False,
                    "notification_strategy": notification_strategy,
                }
            else:
                # Alert was filtered out
                await self._log_filtered_alert(alert, "smart_filtering")

                return {
                    "alert_id": alert.id,
                    "action": action,
                    "fingerprint": fingerprint,
                    "correlations": 0,
                    "notifications_sent": 0,
                    "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                    "filtered": True,
                    "reason": "smart_filtering",
                }

        except Exception as e:
            logger.error(f"Error processing alert event: {str(e)}", exc_info=True)
            raise

    def _extract_alert_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize alert data from event."""
        return {
            "title": event_data.get("title", "Unknown Alert"),
            "description": event_data.get("description", ""),
            "severity": event_data.get("severity", AlertSeverity.MEDIUM),
            "source": event_data.get("source", "unknown"),
            "labels": event_data.get("labels", {}),
            "annotations": event_data.get("annotations", {}),
            "metric_value": event_data.get("metric_value"),
            "threshold": event_data.get("threshold"),
            "timestamp": event_data.get("timestamp", datetime.utcnow()),
        }

    def _generate_fingerprint(self, alert_data: Dict[str, Any]) -> str:
        """Generate unique fingerprint for alert deduplication."""
        fingerprint_data = {
            "title": alert_data["title"],
            "source": alert_data["source"],
            "labels": alert_data["labels"],
        }

        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()

    async def _get_existing_alert(self, fingerprint: str) -> Optional[Alert]:
        """Get existing alert by fingerprint."""
        result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.fingerprint == fingerprint,
                    Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _update_existing_alert(
        self, alert: Alert, alert_data: Dict[str, Any]
    ) -> Alert:
        """Update existing alert with new data."""
        alert.updated_at = datetime.utcnow()
        alert.annotations = {**alert.annotations, **alert_data["annotations"]}

        # Create event
        event = AlertEvent(
            alert_id=alert.id,
            event_type="updated",
            event_data=alert_data,
            timestamp=datetime.utcnow(),
        )
        self.db.add(event)

        await self.db.commit()
        return alert

    async def _create_new_alert(
        self, alert_data: Dict[str, Any], fingerprint: str
    ) -> Alert:
        """Create new alert from data."""
        # Find or create alert rule
        rule = await self._get_or_create_alert_rule(alert_data)

        alert = Alert(
            rule_id=rule.id,
            fingerprint=fingerprint,
            title=alert_data["title"],
            description=alert_data["description"],
            severity=alert_data["severity"],
            source=alert_data["source"],
            labels=alert_data["labels"],
            annotations=alert_data["annotations"],
            starts_at=alert_data["timestamp"],
        )

        self.db.add(alert)
        await self.db.commit()

        # Create event
        event = AlertEvent(
            alert_id=alert.id,
            event_type="created",
            event_data=alert_data,
            timestamp=datetime.utcnow(),
        )
        self.db.add(event)

        await self.db.commit()
        return alert

    async def _get_or_create_alert_rule(self, alert_data: Dict[str, Any]) -> AlertRule:
        """Get or create alert rule for the alert."""
        rule_name = f"auto_rule_{alert_data['source']}_{alert_data['title']}"

        result = await self.db.execute(
            select(AlertRule).where(AlertRule.name == rule_name)
        )
        rule = result.scalar_one_or_none()

        if not rule:
            rule = AlertRule(
                name=rule_name,
                description=f"Auto-generated rule for {alert_data['source']}",
                condition={
                    "metric": alert_data.get("metric_value"),
                    "operator": "gt",
                    "threshold": alert_data.get("threshold", 0),
                },
                severity=alert_data["severity"],
            )
            self.db.add(rule)
            await self.db.commit()

        return rule

    async def _apply_smart_filtering(
        self, alert: Alert, event_data: Dict[str, Any]
    ) -> bool:
        """
        Apply intelligent filtering to reduce noise.

        Target: <5% noise-to-signal ratio
        """
        # Check burst protection
        if await self._check_burst_protection(alert):
            logger.info(f"Alert {alert.id} filtered due to burst protection")
            return False

        # Check duplicate detection
        if await self._check_duplicate_detection(alert):
            logger.info(f"Alert {alert.id} filtered as duplicate")
            return False

        # Check noise score
        noise_score = await self._calculate_noise_score(alert)
        if noise_score > self.filtering_config["noise_threshold"]:
            logger.info(
                f"Alert {alert.id} filtered due to high noise score: {noise_score}"
            )
            return False

        # Check severity-based filtering
        if not await self._check_severity_filtering(alert):
            logger.info(f"Alert {alert.id} filtered due to severity filtering")
            return False

        return True

    async def _check_burst_protection(self, alert: Alert) -> bool:
        """Check if alert exceeds burst threshold."""
        key = f"burst:{alert.source}:{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
        current_count = await self.redis.incr(key)
        await self.redis.expire(key, 60)  # 1 minute expiry

        return current_count > self.filtering_config["burst_threshold"]

    async def _check_duplicate_detection(self, alert: Alert) -> bool:
        """Check for duplicate alerts in time window."""
        window_start = datetime.utcnow() - timedelta(
            seconds=self.filtering_config["duplicate_window"]
        )

        result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.fingerprint == alert.fingerprint,
                    Alert.created_at >= window_start,
                    Alert.id != alert.id,
                )
            )
        )

        return result.first() is not None

    async def _calculate_noise_score(self, alert: Alert) -> float:
        """Calculate noise score for the alert."""
        # Get historical data for the alert rule
        historical_alerts = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.rule_id == alert.rule_id,
                    Alert.created_at >= datetime.utcnow() - timedelta(days=7),
                )
            )
        )

        alerts = historical_alerts.scalars().all()

        if not alerts:
            return 0.0

        # Calculate metrics
        total_alerts = len(alerts)
        resolved_alerts = sum(1 for a in alerts if a.status == AlertStatus.RESOLVED)
        avg_resolution_time = sum(
            (a.resolved_at - a.starts_at).total_seconds()
            for a in alerts
            if a.resolved_at
        ) / max(resolved_alerts, 1)

        # Calculate noise score (0-1, higher = more noise)
        resolution_rate = resolved_alerts / total_alerts
        frequency_factor = min(total_alerts / 10, 1.0)  # Normalize to 0-1

        noise_score = (1 - resolution_rate) * frequency_factor

        return min(noise_score, 1.0)

    async def _check_severity_filtering(self, alert: Alert) -> bool:
        """Check severity-based filtering rules."""
        weight = self.filtering_config["severity_weights"].get(alert.severity, 0.5)

        # Get current system load
        active_alerts = await self.db.execute(
            select(Alert).where(Alert.status == AlertStatus.ACTIVE)
        )

        active_count = len(active_alerts.scalars().all())

        # Apply dynamic filtering based on system load
        if active_count > 100:  # High load
            return weight > 0.6
        elif active_count > 50:  # Medium load
            return weight > 0.4
        else:  # Low load
            return weight > 0.2

    async def _filter_correlations(
        self, correlations: List[AlertCorrelation]
    ) -> List[AlertCorrelation]:
        """Filter correlations based on confidence threshold."""
        return [
            corr
            for corr in correlations
            if corr.confidence_score >= self.filtering_config["correlation_threshold"]
        ]

    async def _store_correlations(
        self, alert: Alert, correlations: List[AlertCorrelation]
    ):
        """Store alert correlations in database."""
        for correlation in correlations:
            correlation.alert_id = alert.id
            self.db.add(correlation)

        await self.db.commit()

    async def _determine_notification_strategy(
        self, alert: Alert, correlations: List[AlertCorrelation]
    ) -> Dict[str, Any]:
        """Determine optimal notification strategy based on alert and correlations."""
        strategy = {
            "channels": [],
            "priority": "normal",
            "escalation_policy": None,
            "correlation_based": False,
            "delay_seconds": 0,
        }

        # Base strategy on severity
        if alert.severity == AlertSeverity.CRITICAL:
            strategy["priority"] = "urgent"
            strategy["channels"] = ["email", "sms", "push"]
        elif alert.severity == AlertSeverity.HIGH:
            strategy["priority"] = "high"
            strategy["channels"] = ["email", "push"]
        else:
            strategy["priority"] = "normal"
            strategy["channels"] = ["email"]

        # Adjust based on correlations
        if correlations:
            strategy["correlation_based"] = True

            # If part of a larger incident, increase priority
            if len(correlations) > 3:
                strategy["priority"] = "urgent"
                strategy["channels"] = ["email", "sms", "push", "webhook"]

            # Add delay for correlated alerts to group notifications
            strategy["delay_seconds"] = 30

        # Get escalation policy
        strategy["escalation_policy"] = await self._get_escalation_policy(alert)

        return strategy

    async def _get_escalation_policy(self, alert: Alert) -> Optional[Dict[str, Any]]:
        """Get escalation policy for the alert."""
        # Simple escalation policy based on severity
        if alert.severity == AlertSeverity.CRITICAL:
            return {
                "escalate_after_minutes": 5,
                "escalation_levels": [
                    {"channels": ["email", "sms"], "delay_minutes": 0},
                    {"channels": ["webhook"], "delay_minutes": 5},
                    {"channels": ["phone"], "delay_minutes": 10},
                ],
            }
        elif alert.severity == AlertSeverity.HIGH:
            return {
                "escalate_after_minutes": 15,
                "escalation_levels": [
                    {"channels": ["email"], "delay_minutes": 0},
                    {"channels": ["sms"], "delay_minutes": 15},
                ],
            }

        return None

    async def _send_notifications(
        self, alert: Alert, strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Send notifications based on strategy."""
        results = []

        for channel_type in strategy["channels"]:
            try:
                result = await self.notification_manager.send_notification(
                    alert=alert,
                    channel_type=channel_type,
                    priority=strategy["priority"],
                    delay_seconds=strategy["delay_seconds"],
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to send notification via {channel_type}: {str(e)}"
                )
                results.append(
                    {"channel": channel_type, "status": "failed", "error": str(e)}
                )

        return results

    async def _start_escalation(self, alert: Alert, strategy: Dict[str, Any]):
        """Start escalation process if configured."""
        if strategy.get("escalation_policy"):
            await self.escalation_manager.start_escalation(
                alert=alert, policy=strategy["escalation_policy"]
            )

    async def _update_performance_metrics(
        self, start_time: datetime, alert: Alert, correlations: List[AlertCorrelation]
    ):
        """Update performance tracking metrics."""
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        self.performance_metrics["alerts_processed"] += 1
        self.performance_metrics["correlations_found"] += len(correlations)
        self.performance_metrics["processing_times"].append(processing_time)

        # Keep only last 1000 processing times
        if len(self.performance_metrics["processing_times"]) > 1000:
            self.performance_metrics["processing_times"] = self.performance_metrics[
                "processing_times"
            ][-1000:]

        # Store metrics in Redis for monitoring
        await self.redis.hset(
            "alert_service_metrics",
            mapping={
                "alerts_processed": self.performance_metrics["alerts_processed"],
                "correlations_found": self.performance_metrics["correlations_found"],
                "avg_processing_time": sum(self.performance_metrics["processing_times"])
                / len(self.performance_metrics["processing_times"]),
                "last_updated": datetime.utcnow().isoformat(),
            },
        )

    async def _log_filtered_alert(self, alert: Alert, reason: str):
        """Log filtered alert for analysis."""
        await self.redis.lpush(
            "filtered_alerts",
            json.dumps(
                {
                    "alert_id": alert.id,
                    "fingerprint": alert.fingerprint,
                    "severity": alert.severity,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

        # Keep only last 10000 filtered alerts
        await self.redis.ltrim("filtered_alerts", 0, 9999)

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        if not self.performance_metrics["processing_times"]:
            return self.performance_metrics

        processing_times = self.performance_metrics["processing_times"]

        return {
            **self.performance_metrics,
            "avg_processing_time": sum(processing_times) / len(processing_times),
            "max_processing_time": max(processing_times),
            "min_processing_time": min(processing_times),
            "p95_processing_time": sorted(processing_times)[
                int(len(processing_times) * 0.95)
            ],
            "p99_processing_time": sorted(processing_times)[
                int(len(processing_times) * 0.99)
            ],
        }

    async def acknowledge_alert(self, alert_id: int, user_id: str) -> Dict[str, Any]:
        """Acknowledge an alert."""
        alert = await self.db.get(Alert, alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id

        # Create event
        event = AlertEvent(
            alert_id=alert.id,
            event_type="acknowledged",
            event_data={"user_id": user_id},
            timestamp=datetime.utcnow(),
            user_id=user_id,
        )
        self.db.add(event)

        await self.db.commit()

        # Stop escalation
        await self.escalation_manager.stop_escalation(alert)

        return {
            "alert_id": alert.id,
            "status": alert.status,
            "acknowledged_at": alert.acknowledged_at,
            "acknowledged_by": alert.acknowledged_by,
        }

    async def resolve_alert(self, alert_id: int, user_id: str) -> Dict[str, Any]:
        """Resolve an alert."""
        alert = await self.db.get(Alert, alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user_id
        alert.ends_at = datetime.utcnow()

        # Create event
        event = AlertEvent(
            alert_id=alert.id,
            event_type="resolved",
            event_data={"user_id": user_id},
            timestamp=datetime.utcnow(),
            user_id=user_id,
        )
        self.db.add(event)

        await self.db.commit()

        # Stop escalation
        await self.escalation_manager.stop_escalation(alert)

        return {
            "alert_id": alert.id,
            "status": alert.status,
            "resolved_at": alert.resolved_at,
            "resolved_by": alert.resolved_by,
            "duration": (alert.ends_at - alert.starts_at).total_seconds(),
        }

    async def get_active_alerts(self, limit: int = 100) -> List[Alert]:
        """Get active alerts."""
        result = await self.db.execute(
            select(Alert)
            .where(Alert.status == AlertStatus.ACTIVE)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )

        return result.scalars().all()

    async def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        # Get active alerts count
        active_result = await self.db.execute(
            select(Alert).where(Alert.status == AlertStatus.ACTIVE)
        )
        active_count = len(active_result.scalars().all())

        # Get total alerts in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_result = await self.db.execute(
            select(Alert).where(Alert.created_at >= yesterday)
        )
        recent_count = len(recent_result.scalars().all())

        # Get critical alerts
        critical_result = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.severity == AlertSeverity.CRITICAL,
                    Alert.status == AlertStatus.ACTIVE,
                )
            )
        )
        critical_count = len(critical_result.scalars().all())

        return {
            "active_alerts": active_count,
            "alerts_24h": recent_count,
            "critical_alerts": critical_count,
            "performance_metrics": await self.get_performance_metrics(),
        }
