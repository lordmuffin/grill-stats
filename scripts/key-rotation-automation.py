#!/usr/bin/env python3
"""
Automated Key Rotation for Vault Transit Engine

This script provides automated key rotation capabilities for the ThermoWorks
credential encryption system. It includes:

- Scheduled key rotation based on age or usage
- Health checks and monitoring
- Rollback capabilities
- Notification system
- Compliance reporting
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import hvac
import requests
import schedule

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RotationTrigger(Enum):
    """Key rotation trigger types"""

    SCHEDULED = "scheduled"
    AGE_BASED = "age_based"
    USAGE_BASED = "usage_based"
    MANUAL = "manual"
    EMERGENCY = "emergency"


class RotationStatus(Enum):
    """Key rotation status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"


@dataclass
class KeyRotationConfig:
    """Configuration for key rotation"""

    vault_url: str
    vault_token: str
    transit_path: str = "transit"
    key_name: str = "thermoworks-user-credentials"
    rotation_interval_hours: int = 720  # 30 days
    max_key_age_days: int = 90
    max_usage_count: int = 1000000
    notification_webhook: Optional[str] = None
    backup_enabled: bool = True
    backup_path: str = "/var/backups/vault-keys"
    health_check_interval_minutes: int = 60
    monitoring_enabled: bool = True
    dry_run: bool = False


@dataclass
class KeyRotationEvent:
    """Key rotation event"""

    timestamp: str
    trigger: RotationTrigger
    status: RotationStatus
    key_name: str
    old_version: Optional[int] = None
    new_version: Optional[int] = None
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class VaultKeyManager:
    """Manages Vault key operations"""

    def __init__(self, config: KeyRotationConfig):
        self.config = config
        self.vault_client = hvac.Client(url=config.vault_url)
        self.vault_client.token = config.vault_token
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Vault"""
        if not self.vault_client.is_authenticated():
            raise ValueError("Failed to authenticate with Vault")
        logger.info("Successfully authenticated with Vault")

    def get_key_info(self) -> Dict[str, Any]:
        """Get information about the encryption key"""
        try:
            key_info = self.vault_client.secrets.transit.read_key(
                name=self.config.key_name, mount_point=self.config.transit_path
            )
            return key_info["data"]
        except Exception as e:
            logger.error(f"Failed to get key info: {e}")
            raise

    def rotate_key(self) -> Dict[str, Any]:
        """Rotate the encryption key"""
        try:
            logger.info(f"Starting key rotation for {self.config.key_name}")

            # Get current key info
            old_key_info = self.get_key_info()
            old_version = old_key_info["latest_version"]

            # Perform rotation
            if not self.config.dry_run:
                self.vault_client.secrets.transit.rotate_key(name=self.config.key_name, mount_point=self.config.transit_path)

            # Get new key info
            new_key_info = self.get_key_info()
            new_version = new_key_info["latest_version"]

            rotation_info = {
                "old_version": old_version,
                "new_version": new_version,
                "rotated_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": self.config.dry_run,
            }

            logger.info(f"Key rotation completed: {old_version} -> {new_version}")
            return rotation_info

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise

    def get_key_age(self) -> timedelta:
        """Get the age of the current key version"""
        try:
            key_info = self.get_key_info()
            keys = key_info.get("keys", {})
            latest_version = key_info.get("latest_version", 1)

            if str(latest_version) in keys:
                creation_time = keys[str(latest_version)]["creation_time"]
                creation_dt = datetime.fromisoformat(creation_time.replace("Z", "+00:00"))
                return datetime.now(timezone.utc) - creation_dt
            else:
                return timedelta(days=0)

        except Exception as e:
            logger.error(f"Failed to get key age: {e}")
            return timedelta(days=0)

    def get_key_usage_count(self) -> int:
        """Get the usage count for the current key version"""
        # This would typically come from metrics or audit logs
        # For now, return a placeholder
        return 0

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on key"""
        try:
            key_info = self.get_key_info()

            # Test encrypt/decrypt
            test_data = f"health-check-{int(time.time())}"
            import base64

            test_b64 = base64.b64encode(test_data.encode()).decode()

            # Encrypt
            encrypt_response = self.vault_client.secrets.transit.encrypt_data(
                name=self.config.key_name,
                plaintext=test_b64,
                mount_point=self.config.transit_path,
            )

            # Decrypt
            decrypt_response = self.vault_client.secrets.transit.decrypt_data(
                name=self.config.key_name,
                ciphertext=encrypt_response["data"]["ciphertext"],
                mount_point=self.config.transit_path,
            )

            decrypted_data = base64.b64decode(decrypt_response["data"]["plaintext"]).decode()

            if decrypted_data == test_data:
                return {
                    "status": "healthy",
                    "key_version": key_info["latest_version"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Encrypt/decrypt test failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


class KeyRotationScheduler:
    """Schedules and manages key rotation"""

    def __init__(self, config: KeyRotationConfig):
        self.config = config
        self.vault_manager = VaultKeyManager(config)
        self.rotation_events: List[KeyRotationEvent] = []
        self.running = False
        self.last_health_check = None

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def start(self):
        """Start the key rotation scheduler"""
        logger.info("Starting key rotation scheduler")
        self.running = True

        # Schedule regular rotation
        schedule.every(self.config.rotation_interval_hours).hours.do(self._scheduled_rotation)

        # Schedule health checks
        schedule.every(self.config.health_check_interval_minutes).minutes.do(self._health_check)

        # Log service start
        self._log_event(
            KeyRotationEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                trigger=RotationTrigger.SCHEDULED,
                status=RotationStatus.PENDING,
                key_name=self.config.key_name,
                details={"message": "Key rotation scheduler started"},
            )
        )

        # Main loop
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

        logger.info("Key rotation scheduler stopped")

    def _scheduled_rotation(self):
        """Perform scheduled key rotation"""
        logger.info("Performing scheduled key rotation")
        self.rotate_key(RotationTrigger.SCHEDULED)

    def _health_check(self):
        """Perform health check"""
        try:
            health_status = self.vault_manager.health_check()
            self.last_health_check = health_status

            if health_status["status"] == "healthy":
                logger.debug("Health check passed")
            else:
                logger.warning(f"Health check failed: {health_status.get('error')}")
                self._send_notification(
                    "Key Health Check Failed",
                    f"Health check failed for key {self.config.key_name}: {health_status.get('error')}",
                )
        except Exception as e:
            logger.error(f"Health check error: {e}")

    def rotate_key(self, trigger: RotationTrigger) -> bool:
        """Perform key rotation"""
        event = KeyRotationEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger=trigger,
            status=RotationStatus.IN_PROGRESS,
            key_name=self.config.key_name,
        )

        try:
            # Check if rotation is needed
            if not self._should_rotate(trigger):
                logger.info("Key rotation not needed at this time")
                return False

            # Perform rotation
            rotation_info = self.vault_manager.rotate_key()

            # Update event
            event.status = RotationStatus.COMPLETED
            event.old_version = rotation_info["old_version"]
            event.new_version = rotation_info["new_version"]
            event.details = rotation_info

            # Log success
            self._log_event(event)

            # Send notification
            self._send_notification(
                "Key Rotation Successful",
                f"Key {self.config.key_name} rotated successfully from version {rotation_info['old_version']} to {rotation_info['new_version']}",
            )

            # Create backup if enabled
            if self.config.backup_enabled:
                self._create_backup(rotation_info)

            return True

        except Exception as e:
            event.status = RotationStatus.FAILED
            event.error_message = str(e)
            event.details = {"error_type": type(e).__name__}

            self._log_event(event)

            # Send notification
            self._send_notification(
                "Key Rotation Failed",
                f"Key rotation failed for {self.config.key_name}: {str(e)}",
            )

            return False

    def _should_rotate(self, trigger: RotationTrigger) -> bool:
        """Check if key rotation is needed"""
        if trigger == RotationTrigger.MANUAL or trigger == RotationTrigger.EMERGENCY:
            return True

        # Check age-based rotation
        key_age = self.vault_manager.get_key_age()
        if key_age.days >= self.config.max_key_age_days:
            logger.info(f"Key age ({key_age.days} days) exceeds maximum ({self.config.max_key_age_days} days)")
            return True

        # Check usage-based rotation
        usage_count = self.vault_manager.get_key_usage_count()
        if usage_count >= self.config.max_usage_count:
            logger.info(f"Key usage count ({usage_count}) exceeds maximum ({self.config.max_usage_count})")
            return True

        return False

    def _log_event(self, event: KeyRotationEvent):
        """Log rotation event"""
        self.rotation_events.append(event)

        # Log to file
        event_data = {
            "timestamp": event.timestamp,
            "trigger": event.trigger.value,
            "status": event.status.value,
            "key_name": event.key_name,
            "old_version": event.old_version,
            "new_version": event.new_version,
            "error_message": event.error_message,
            "details": event.details,
        }

        logger.info(f"Key rotation event: {json.dumps(event_data)}")

    def _send_notification(self, title: str, message: str):
        """Send notification via webhook"""
        if not self.config.notification_webhook:
            return

        try:
            payload = {
                "title": title,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "key-rotation-automation",
                "key_name": self.config.key_name,
            }

            response = requests.post(
                self.config.notification_webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def _create_backup(self, rotation_info: Dict[str, Any]):
        """Create backup of key information"""
        try:
            backup_dir = Path(self.config.backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_file = backup_dir / f"key-rotation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

            backup_data = {
                "rotation_info": rotation_info,
                "key_info": self.vault_manager.get_key_info(),
                "config": {
                    "key_name": self.config.key_name,
                    "vault_url": self.config.vault_url,
                    "transit_path": self.config.transit_path,
                },
            }

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2)

            logger.info(f"Backup created: {backup_file}")

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of key rotation scheduler"""
        key_info = self.vault_manager.get_key_info()
        key_age = self.vault_manager.get_key_age()

        return {
            "scheduler_running": self.running,
            "key_name": self.config.key_name,
            "current_version": key_info["latest_version"],
            "key_age_days": key_age.days,
            "last_health_check": self.last_health_check,
            "rotation_events_count": len(self.rotation_events),
            "last_rotation": (self.rotation_events[-1].timestamp if self.rotation_events else None),
        }


def load_config(config_file: str) -> KeyRotationConfig:
    """Load configuration from file"""
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config_data = json.load(f)
        return KeyRotationConfig(**config_data)
    else:
        # Use environment variables
        return KeyRotationConfig(
            vault_url=os.getenv("VAULT_URL", "http://vault:8200"),
            vault_token=os.getenv("VAULT_TOKEN", ""),
            transit_path=os.getenv("VAULT_TRANSIT_PATH", "transit"),
            key_name=os.getenv("VAULT_KEY_NAME", "thermoworks-user-credentials"),
            rotation_interval_hours=int(os.getenv("ROTATION_INTERVAL_HOURS", "720")),
            max_key_age_days=int(os.getenv("MAX_KEY_AGE_DAYS", "90")),
            max_usage_count=int(os.getenv("MAX_USAGE_COUNT", "1000000")),
            notification_webhook=os.getenv("NOTIFICATION_WEBHOOK"),
            backup_enabled=os.getenv("BACKUP_ENABLED", "true").lower() == "true",
            backup_path=os.getenv("BACKUP_PATH", "/var/backups/vault-keys"),
            health_check_interval_minutes=int(os.getenv("HEALTH_CHECK_INTERVAL_MINUTES", "60")),
            monitoring_enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        )


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Automated key rotation for Vault Transit Engine")
    parser.add_argument(
        "--config",
        "-c",
        default="/etc/grill-stats/key-rotation.json",
        help="Configuration file path",
    )
    parser.add_argument("--rotate", "-r", action="store_true", help="Perform immediate key rotation")
    parser.add_argument("--status", "-s", action="store_true", help="Show current status")
    parser.add_argument("--health-check", "-h", action="store_true", help="Perform health check")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Override dry run if specified
    if args.dry_run:
        config.dry_run = True

    # Create scheduler
    scheduler = KeyRotationScheduler(config)

    if args.rotate:
        # Perform immediate rotation
        success = scheduler.rotate_key(RotationTrigger.MANUAL)
        sys.exit(0 if success else 1)

    elif args.status:
        # Show status
        status = scheduler.get_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)

    elif args.health_check:
        # Perform health check
        health_status = scheduler.vault_manager.health_check()
        print(json.dumps(health_status, indent=2))
        sys.exit(0 if health_status["status"] == "healthy" else 1)

    else:
        # Start scheduler
        scheduler.start()


if __name__ == "__main__":
    main()
