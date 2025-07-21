import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..models.ha_models import HAConnectionStatus, HAHealthStatus
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    name: str
    check_function: str
    interval_seconds: int
    timeout_seconds: int = 30
    critical: bool = False
    enabled: bool = True


class HealthMonitor:
    def __init__(self, ha_client, entity_manager, state_sync, discovery_service):
        self.ha_client = ha_client
        self.entity_manager = entity_manager
        self.state_sync = state_sync
        self.discovery_service = discovery_service

        self.metrics = MetricsCollector()
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None

        # Health check configurations
        self.health_checks = {
            "ha_connection": HealthCheck(
                name="Home Assistant Connection", check_function="check_ha_connection", interval_seconds=60, critical=True
            ),
            "entity_registry": HealthCheck(
                name="Entity Registry",
                check_function="check_entity_registry",
                interval_seconds=300,  # 5 minutes
                critical=False,
            ),
            "state_sync": HealthCheck(
                name="State Synchronization",
                check_function="check_state_sync",
                interval_seconds=120,  # 2 minutes
                critical=True,
            ),
            "discovery_service": HealthCheck(
                name="Discovery Service",
                check_function="check_discovery_service",
                interval_seconds=600,  # 10 minutes
                critical=False,
            ),
            "memory_usage": HealthCheck(
                name="Memory Usage", check_function="check_memory_usage", interval_seconds=180, critical=False  # 3 minutes
            ),
        }

        # Health status tracking
        self.health_status: Dict[str, Dict[str, Any]] = {}
        self.last_checks: Dict[str, datetime] = {}
        self.overall_health = "unknown"

    async def start_monitoring(self):
        if self.is_running:
            logger.warning("Health monitor already running")
            return

        self.is_running = True
        logger.info("Starting health monitoring")

        # Initialize health status
        for check_name in self.health_checks:
            self.health_status[check_name] = {
                "status": "unknown",
                "last_check": None,
                "message": "Not yet checked",
                "duration_ms": 0,
            }

        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping health monitoring")

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self):
        while self.is_running:
            try:
                # Check which health checks need to run
                current_time = datetime.utcnow()
                checks_to_run = []

                for check_name, check_config in self.health_checks.items():
                    if not check_config.enabled:
                        continue

                    last_check = self.last_checks.get(check_name)
                    if not last_check or (current_time - last_check).total_seconds() >= check_config.interval_seconds:
                        checks_to_run.append(check_name)

                # Run health checks
                if checks_to_run:
                    await self._run_health_checks(checks_to_run)

                # Update overall health status
                self._update_overall_health()

                # Sleep for a short interval before next check
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(30)

    async def _run_health_checks(self, check_names: List[str]):
        for check_name in check_names:
            try:
                check_config = self.health_checks[check_name]
                check_function = getattr(self, check_config.check_function)

                start_time = datetime.utcnow()

                # Run health check with timeout
                try:
                    result = await asyncio.wait_for(check_function(), timeout=check_config.timeout_seconds)
                except asyncio.TimeoutError:
                    result = {"status": "failed", "message": f"Health check timed out after {check_config.timeout_seconds}s"}

                end_time = datetime.utcnow()
                duration_ms = (end_time - start_time).total_seconds() * 1000

                # Update health status
                self.health_status[check_name] = {
                    "status": result.get("status", "unknown"),
                    "last_check": end_time.isoformat(),
                    "message": result.get("message", ""),
                    "duration_ms": duration_ms,
                    "details": result.get("details", {}),
                }

                self.last_checks[check_name] = end_time

                logger.debug(f"Health check {check_name}: {result['status']} ({duration_ms:.2f}ms)")

            except Exception as e:
                logger.error(f"Failed to run health check {check_name}: {e}")
                self.health_status[check_name] = {
                    "status": "error",
                    "last_check": datetime.utcnow().isoformat(),
                    "message": str(e),
                    "duration_ms": 0,
                }

    async def check_ha_connection(self) -> Dict[str, Any]:
        try:
            # Test basic connection
            connection_success = self.ha_client.test_connection()

            if connection_success:
                # Get connection health from HA client
                ha_health = self.ha_client.get_health_status()

                return {
                    "status": "healthy" if ha_health.status == HAConnectionStatus.CONNECTED else "degraded",
                    "message": f"Connection successful, response time: {ha_health.response_time_ms or 0:.2f}ms",
                    "details": {
                        "response_time_ms": ha_health.response_time_ms,
                        "consecutive_failures": ha_health.consecutive_failures,
                        "uptime_percentage": ha_health.uptime_percentage,
                    },
                }
            else:
                return {"status": "failed", "message": "Unable to connect to Home Assistant", "details": {}}

        except Exception as e:
            return {"status": "error", "message": f"Connection check failed: {str(e)}", "details": {}}

    async def check_entity_registry(self) -> Dict[str, Any]:
        try:
            registry_stats = self.entity_manager.get_registry_stats()

            total_entities = registry_stats.get("total_entities", 0)
            total_devices = registry_stats.get("total_devices", 0)

            if total_entities > 0:
                return {
                    "status": "healthy",
                    "message": f"Registry healthy: {total_entities} entities, {total_devices} devices",
                    "details": registry_stats,
                }
            else:
                return {"status": "warning", "message": "No entities in registry", "details": registry_stats}

        except Exception as e:
            return {"status": "error", "message": f"Registry check failed: {str(e)}", "details": {}}

    async def check_state_sync(self) -> Dict[str, Any]:
        try:
            sync_stats = self.state_sync.get_sync_stats()

            success_rate = 0
            if sync_stats.get("successful_syncs", 0) + sync_stats.get("failed_syncs", 0) > 0:
                success_rate = (
                    sync_stats.get("successful_syncs", 0)
                    / (sync_stats.get("successful_syncs", 0) + sync_stats.get("failed_syncs", 0))
                    * 100
                )

            is_running = sync_stats.get("is_running", False)
            pending_updates = sync_stats.get("pending_updates", 0)
            retry_queue_size = sync_stats.get("retry_queue_size", 0)

            if is_running and success_rate >= 95:
                status = "healthy"
                message = f"Sync healthy: {success_rate:.1f}% success rate"
            elif is_running and success_rate >= 80:
                status = "degraded"
                message = f"Sync degraded: {success_rate:.1f}% success rate"
            elif is_running:
                status = "warning"
                message = f"Sync issues: {success_rate:.1f}% success rate"
            else:
                status = "failed"
                message = "State synchronization not running"

            return {
                "status": status,
                "message": message,
                "details": {
                    "success_rate": success_rate,
                    "is_running": is_running,
                    "pending_updates": pending_updates,
                    "retry_queue_size": retry_queue_size,
                    **sync_stats,
                },
            }

        except Exception as e:
            return {"status": "error", "message": f"State sync check failed: {str(e)}", "details": {}}

    async def check_discovery_service(self) -> Dict[str, Any]:
        try:
            discovery_stats = self.discovery_service.get_discovery_stats()

            total_entities = discovery_stats.get("total_entities", 0)
            unique_devices = discovery_stats.get("unique_devices", 0)

            return {
                "status": "healthy",
                "message": f"Discovery service healthy: {total_entities} entities, {unique_devices} devices",
                "details": discovery_stats,
            }

        except Exception as e:
            return {"status": "error", "message": f"Discovery service check failed: {str(e)}", "details": {}}

    async def check_memory_usage(self) -> Dict[str, Any]:
        try:
            import psutil

            # Get memory usage
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()

            memory_usage_percent = memory.percent
            process_memory_mb = process_memory.rss / 1024 / 1024

            if memory_usage_percent < 80:
                status = "healthy"
                message = f"Memory usage normal: {memory_usage_percent:.1f}%"
            elif memory_usage_percent < 90:
                status = "warning"
                message = f"Memory usage high: {memory_usage_percent:.1f}%"
            else:
                status = "critical"
                message = f"Memory usage critical: {memory_usage_percent:.1f}%"

            return {
                "status": status,
                "message": message,
                "details": {
                    "system_memory_percent": memory_usage_percent,
                    "system_memory_available_mb": memory.available / 1024 / 1024,
                    "process_memory_mb": process_memory_mb,
                    "process_memory_percent": process.memory_percent(),
                },
            }

        except ImportError:
            return {"status": "unknown", "message": "psutil not available for memory monitoring", "details": {}}
        except Exception as e:
            return {"status": "error", "message": f"Memory check failed: {str(e)}", "details": {}}

    def _update_overall_health(self):
        try:
            # Count status types
            status_counts = {"healthy": 0, "degraded": 0, "warning": 0, "failed": 0, "error": 0, "unknown": 0}
            critical_failures = 0

            for check_name, check_status in self.health_status.items():
                status = check_status.get("status", "unknown")
                status_counts[status] += 1

                # Check for critical failures
                check_config = self.health_checks.get(check_name, {})
                if check_config.get("critical", False) and status in ["failed", "error"]:
                    critical_failures += 1

            # Determine overall health
            if critical_failures > 0:
                self.overall_health = "critical"
            elif status_counts["failed"] > 0 or status_counts["error"] > 0:
                self.overall_health = "failed"
            elif status_counts["warning"] > 0:
                self.overall_health = "warning"
            elif status_counts["degraded"] > 0:
                self.overall_health = "degraded"
            elif status_counts["healthy"] > 0:
                self.overall_health = "healthy"
            else:
                self.overall_health = "unknown"

        except Exception as e:
            logger.error(f"Failed to update overall health: {e}")
            self.overall_health = "error"

    def get_health_status(self) -> Dict[str, Any]:
        return {
            "overall_health": self.overall_health,
            "last_updated": datetime.utcnow().isoformat(),
            "checks": self.health_status.copy(),
            "summary": self._get_health_summary(),
        }

    def _get_health_summary(self) -> Dict[str, Any]:
        status_counts = {"healthy": 0, "degraded": 0, "warning": 0, "failed": 0, "error": 0, "unknown": 0}
        total_checks = 0
        critical_checks = 0
        critical_failures = 0

        for check_name, check_status in self.health_status.items():
            status = check_status.get("status", "unknown")
            status_counts[status] += 1
            total_checks += 1

            check_config = self.health_checks.get(check_name, {})
            if check_config.get("critical", False):
                critical_checks += 1
                if status in ["failed", "error"]:
                    critical_failures += 1

        return {
            "total_checks": total_checks,
            "critical_checks": critical_checks,
            "critical_failures": critical_failures,
            "status_breakdown": status_counts,
            "health_percentage": (status_counts["healthy"] / max(total_checks, 1) * 100),
        }

    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        # In a full implementation, this would return historical health data
        # For now, return current status as a single point
        return [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_health": self.overall_health,
                "checks": {name: status["status"] for name, status in self.health_status.items()},
            }
        ]

    def enable_health_check(self, check_name: str) -> bool:
        if check_name in self.health_checks:
            self.health_checks[check_name].enabled = True
            logger.info(f"Enabled health check: {check_name}")
            return True
        return False

    def disable_health_check(self, check_name: str) -> bool:
        if check_name in self.health_checks:
            self.health_checks[check_name].enabled = False
            logger.info(f"Disabled health check: {check_name}")
            return True
        return False

    def update_check_interval(self, check_name: str, interval_seconds: int) -> bool:
        if check_name in self.health_checks:
            self.health_checks[check_name].interval_seconds = interval_seconds
            logger.info(f"Updated {check_name} interval to {interval_seconds}s")
            return True
        return False
