#!/usr/bin/env python3
"""
Tests for Database Models and Migrations

This module tests the SQLAlchemy models, database migrations,
and audit logging functionality.
"""

import datetime
import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Import models
from models import Base
from models.audit_log import AuditLog
from models.device import Device
from models.device_health import DeviceHealth
from models.gateway_status import GatewayStatus


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing"""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


class TestDeviceModel:
    """Tests for the Device model"""

    def test_device_creation(self, in_memory_db):
        """Test creating a device record"""
        device = Device(
            device_id="test_device_001",
            name="Test Device",
            device_type="thermoworks",
            configuration={"setting": "value"},
            user_id="user123",
        )

        in_memory_db.add(device)
        in_memory_db.commit()

        # Query the device back
        queried_device = in_memory_db.query(Device).filter_by(device_id="test_device_001").first()

        assert queried_device is not None
        assert queried_device.device_id == "test_device_001"
        assert queried_device.name == "Test Device"
        assert queried_device.device_type == "thermoworks"
        assert queried_device.configuration == {"setting": "value"}
        assert queried_device.user_id == "user123"
        assert queried_device.active is True
        assert queried_device.created_at is not None
        assert queried_device.updated_at is not None

    def test_device_soft_delete(self, in_memory_db):
        """Test soft deletion of a device record"""
        device = Device(
            device_id="test_device_001",
            name="Test Device",
            device_type="thermoworks",
        )

        in_memory_db.add(device)
        in_memory_db.commit()

        # Soft delete the device
        device.active = False
        in_memory_db.commit()

        # Query the device back
        queried_device = in_memory_db.query(Device).filter_by(device_id="test_device_001").first()

        assert queried_device is not None
        assert queried_device.active is False

    def test_device_relationships(self, in_memory_db):
        """Test device relationships"""
        device = Device(
            device_id="test_device_001",
            name="Test Device",
            device_type="thermoworks",
        )

        # Add health record
        health_record = DeviceHealth(
            device_id=device.device_id,
            battery_level=85,
            signal_strength=92,
            is_online=True,
            last_seen=datetime.datetime.utcnow(),
        )

        device.health_records.append(health_record)

        in_memory_db.add(device)
        in_memory_db.commit()

        # Query the device with health records
        queried_device = in_memory_db.query(Device).filter_by(device_id="test_device_001").first()

        assert queried_device is not None
        assert len(queried_device.health_records) == 1
        assert queried_device.health_records[0].battery_level == 85
        assert queried_device.health_records[0].signal_strength == 92
        assert queried_device.health_records[0].is_online is True


class TestDeviceHealthModel:
    """Tests for the DeviceHealth model"""

    def test_health_record_creation(self, in_memory_db):
        """Test creating a device health record"""
        device = Device(
            device_id="test_device_001",
            name="Test Device",
            device_type="thermoworks",
        )

        in_memory_db.add(device)
        in_memory_db.commit()

        health_record = DeviceHealth(
            device_id=device.device_id,
            battery_level=85,
            signal_strength=92,
            is_online=True,
            last_seen=datetime.datetime.utcnow(),
        )

        in_memory_db.add(health_record)
        in_memory_db.commit()

        # Query the health record back
        queried_record = in_memory_db.query(DeviceHealth).filter_by(device_id="test_device_001").first()

        assert queried_record is not None
        assert queried_record.device_id == "test_device_001"
        assert queried_record.battery_level == 85
        assert queried_record.signal_strength == 92
        assert queried_record.is_online is True
        assert queried_record.last_seen is not None
        assert queried_record.created_at is not None

    def test_health_record_relationship(self, in_memory_db):
        """Test health record relationship to device"""
        device = Device(
            device_id="test_device_001",
            name="Test Device",
            device_type="thermoworks",
        )

        in_memory_db.add(device)
        in_memory_db.commit()

        health_record = DeviceHealth(
            device_id=device.device_id,
            battery_level=85,
            signal_strength=92,
            is_online=True,
            last_seen=datetime.datetime.utcnow(),
        )

        in_memory_db.add(health_record)
        in_memory_db.commit()

        # Query the health record with device relationship
        queried_record = in_memory_db.query(DeviceHealth).filter_by(device_id="test_device_001").first()

        assert queried_record is not None
        assert queried_record.device is not None
        assert queried_record.device.device_id == "test_device_001"
        assert queried_record.device.name == "Test Device"


class TestGatewayStatusModel:
    """Tests for the GatewayStatus model"""

    def test_gateway_status_creation(self, in_memory_db):
        """Test creating a gateway status record"""
        gateway_status = GatewayStatus(
            gateway_id="gateway_001",
            status="online",
            ip_address="192.168.1.100",
            connection_time=datetime.datetime.utcnow(),
            firmware_version="1.0.0",
        )

        in_memory_db.add(gateway_status)
        in_memory_db.commit()

        # Query the gateway status back
        queried_status = in_memory_db.query(GatewayStatus).filter_by(gateway_id="gateway_001").first()

        assert queried_status is not None
        assert queried_status.gateway_id == "gateway_001"
        assert queried_status.status == "online"
        assert queried_status.ip_address == "192.168.1.100"
        assert queried_status.firmware_version == "1.0.0"
        assert queried_status.connection_time is not None
        assert queried_status.created_at is not None
        assert queried_status.updated_at is not None


class TestAuditLogModel:
    """Tests for the AuditLog model"""

    def test_audit_log_creation(self, in_memory_db):
        """Test creating an audit log record"""
        audit_log = AuditLog(
            action="device_update",
            device_id="test_device_001",
            user_id="user123",
            changes={"name": {"old": "Old Device Name", "new": "New Device Name"}},
        )

        in_memory_db.add(audit_log)
        in_memory_db.commit()

        # Query the audit log back
        queried_log = in_memory_db.query(AuditLog).filter_by(device_id="test_device_001").first()

        assert queried_log is not None
        assert queried_log.action == "device_update"
        assert queried_log.device_id == "test_device_001"
        assert queried_log.user_id == "user123"
        assert queried_log.changes == {"name": {"old": "Old Device Name", "new": "New Device Name"}}
        assert queried_log.timestamp is not None

    def test_audit_log_json_serialization(self, in_memory_db):
        """Test JSON serialization of audit log changes"""
        changes = {
            "name": {"old": "Old Device Name", "new": "New Device Name"},
            "configuration": {"old": {"setting": "old_value"}, "new": {"setting": "new_value"}},
        }

        audit_log = AuditLog(
            action="device_update",
            device_id="test_device_001",
            user_id="user123",
            changes=changes,
        )

        in_memory_db.add(audit_log)
        in_memory_db.commit()

        # Query the audit log back and verify JSON deserialization
        queried_log = in_memory_db.query(AuditLog).filter_by(device_id="test_device_001").first()

        assert queried_log is not None
        assert queried_log.changes == changes
        assert queried_log.changes["name"]["old"] == "Old Device Name"
        assert queried_log.changes["name"]["new"] == "New Device Name"
        assert queried_log.changes["configuration"]["old"]["setting"] == "old_value"
        assert queried_log.changes["configuration"]["new"]["setting"] == "new_value"


@patch("run_migrations.command")
class TestMigrations:
    """Tests for database migrations script"""

    def test_get_alembic_config_default(self, mock_command):
        """Test getting Alembic configuration with default settings"""
        from run_migrations import get_alembic_config

        # Call the function
        config = get_alembic_config()

        # Check that the config was created correctly
        assert config is not None
        assert hasattr(config, "get_main_option")
        assert hasattr(config, "set_main_option")

    def test_get_alembic_config_with_env_vars(self, mock_command):
        """Test getting Alembic configuration with environment variables"""
        from run_migrations import get_alembic_config

        # Set environment variables
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "test-db-host",
                "DB_PORT": "5432",
                "DB_NAME": "test-db",
                "DB_USER": "test-user",
                "DB_PASSWORD": "test-password",
            },
        ):
            # Call the function
            config = get_alembic_config()

            # Check that the config includes the database URL
            assert "sqlalchemy.url" in config.get_main_option("sqlalchemy.url")
            assert "postgresql://test-user:test-password@test-db-host:5432/test-db" in config.get_main_option("sqlalchemy.url")

    def test_create_migration(self, mock_command):
        """Test creating a new migration"""
        from run_migrations import create_migration

        # Call the function
        create_migration("Test migration")

        # Check that command.revision was called with the correct arguments
        mock_command.revision.assert_called_once()
        args, kwargs = mock_command.revision.call_args
        assert kwargs["message"] == "Test migration"
        assert kwargs["autogenerate"] is True

    def test_upgrade_database(self, mock_command):
        """Test upgrading database to a specific revision"""
        from run_migrations import upgrade_database

        # Call the function
        upgrade_database("abc123")

        # Check that command.upgrade was called with the correct arguments
        mock_command.upgrade.assert_called_once()
        args, kwargs = mock_command.upgrade.call_args
        assert args[1] == "abc123"

    def test_downgrade_database(self, mock_command):
        """Test downgrading database to a specific revision"""
        from run_migrations import downgrade_database

        # Call the function
        downgrade_database("abc123")

        # Check that command.downgrade was called with the correct arguments
        mock_command.downgrade.assert_called_once()
        args, kwargs = mock_command.downgrade.call_args
        assert args[1] == "abc123"

    def test_show_history(self, mock_command):
        """Test showing migration history"""
        from run_migrations import show_history

        # Call the function
        show_history()

        # Check that command.history was called with the correct arguments
        mock_command.history.assert_called_once()
        args, kwargs = mock_command.history.call_args
        assert kwargs["verbose"] is True

    def test_show_current_revision(self, mock_command):
        """Test showing current database revision"""
        from run_migrations import show_current_revision

        # Call the function
        show_current_revision()

        # Check that command.current was called with the correct arguments
        mock_command.current.assert_called_once()
        args, kwargs = mock_command.current.call_args
        assert kwargs["verbose"] is True

    def test_init_migrations(self, mock_command):
        """Test initializing migrations"""
        from run_migrations import init_migrations

        # Call the function
        init_migrations()

        # Check that command.stamp was called with the correct arguments
        mock_command.stamp.assert_called_once()
        args, kwargs = mock_command.stamp.call_args
        assert args[1] == "head"


if __name__ == "__main__":
    pytest.main([__file__])
