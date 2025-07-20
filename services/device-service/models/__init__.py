from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create the base class for declarative models
Base = declarative_base()

from .audit_log import AuditLog

# Import model classes
from .device import Device
from .device_health import DeviceHealth
from .gateway_status import GatewayStatus


# Function to create engine
def create_db_engine(db_host, db_port, db_name, db_user, db_password):
    """Create SQLAlchemy engine with connection pooling"""
    connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(
        connection_string,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
    )


# Create Session factory
def create_session_factory(engine):
    """Create a session factory for database connections"""
    return sessionmaker(bind=engine)


# Export all models
__all__ = ["Base", "Device", "DeviceHealth", "GatewayStatus", "AuditLog", "create_db_engine", "create_session_factory"]
