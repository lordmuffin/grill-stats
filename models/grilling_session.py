import json
from datetime import datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship


class GrillingSession:
    """GrillingSession model for tracking cooking sessions"""

    def __init__(self, db):
        self.db = db

        class GrillingSessionModel(db.Model):
            __tablename__ = "grilling_sessions"

            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
            name = Column(String(100), nullable=True)
            start_time = Column(DateTime, nullable=False)
            end_time = Column(DateTime, nullable=True)
            devices_used = Column(Text, nullable=True)  # JSON array of device IDs
            status = Column(String(20), default="active")  # 'active', 'completed', 'cancelled'
            max_temperature = Column(Numeric(5, 2), nullable=True)
            min_temperature = Column(Numeric(5, 2), nullable=True)
            avg_temperature = Column(Numeric(5, 2), nullable=True)
            duration_minutes = Column(Integer, nullable=True)
            session_type = Column(String(50), nullable=True)  # 'smoking', 'grilling', 'roasting', etc.
            notes = Column(Text, nullable=True)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

            # Use a string reference for the relationship to avoid circular imports
            # This will be resolved by SQLAlchemy during mapper configuration
            # The UserModel is defined in the User class's __init__ method as a nested class
            user = relationship("UserModel", backref="grilling_sessions")

            def __repr__(self):
                return f'<GrillingSession {self.id}: {self.name or "Unnamed"} ({self.status})>'

            def to_dict(self):
                """Convert session to dictionary"""
                devices_list = []
                if self.devices_used:
                    try:
                        devices_list = (
                            json.loads(self.devices_used) if isinstance(self.devices_used, str) else self.devices_used
                        )
                    except json.JSONDecodeError:
                        devices_list = []

                return {
                    "id": self.id,
                    "user_id": self.user_id,
                    "name": self.name,
                    "start_time": (self.start_time.isoformat() if self.start_time else None),
                    "end_time": self.end_time.isoformat() if self.end_time else None,
                    "devices_used": devices_list,
                    "status": self.status,
                    "max_temperature": (float(self.max_temperature) if self.max_temperature else None),
                    "min_temperature": (float(self.min_temperature) if self.min_temperature else None),
                    "avg_temperature": (float(self.avg_temperature) if self.avg_temperature else None),
                    "duration_minutes": self.duration_minutes,
                    "session_type": self.session_type,
                    "notes": self.notes,
                    "created_at": (self.created_at.isoformat() if self.created_at else None),
                    "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
                }

            def calculate_duration(self):
                """Calculate session duration in minutes"""
                if self.start_time and self.end_time:
                    delta = self.end_time - self.start_time
                    return int(delta.total_seconds() / 60)
                elif self.start_time:
                    # For active sessions, calculate current duration
                    delta = datetime.utcnow() - self.start_time
                    return int(delta.total_seconds() / 60)
                return 0

            def is_active(self):
                """Check if session is currently active"""
                return self.status == "active"

            def get_device_list(self):
                """Get list of device IDs used in session"""
                if self.devices_used:
                    try:
                        return json.loads(self.devices_used) if isinstance(self.devices_used, str) else self.devices_used
                    except json.JSONDecodeError:
                        return []
                return []

            def add_device(self, device_id):
                """Add a device to the session"""
                devices = self.get_device_list()
                if device_id not in devices:
                    devices.append(device_id)
                    self.devices_used = json.dumps(devices)
                    self.updated_at = datetime.utcnow()

            def remove_device(self, device_id):
                """Remove a device from the session"""
                devices = self.get_device_list()
                if device_id in devices:
                    devices.remove(device_id)
                    self.devices_used = json.dumps(devices)
                    self.updated_at = datetime.utcnow()

        self.model = GrillingSessionModel

    def create_session(self, user_id, start_time=None, devices=None, session_type=None):
        """Create a new grilling session"""
        if start_time is None:
            start_time = datetime.utcnow()

        devices_json = json.dumps(devices) if devices else None

        session = self.model(
            user_id=user_id,
            start_time=start_time,
            devices_used=devices_json,
            status="active",
            session_type=session_type,
        )

        self.db.session.add(session)
        self.db.session.commit()
        return session

    def get_session_by_id(self, session_id):
        """Get a session by ID"""
        return self.model.query.get(session_id)

    def get_user_sessions(self, user_id, status=None, limit=50, offset=0):
        """Get sessions for a user with optional status filter"""
        query = self.model.query.filter_by(user_id=user_id)

        if status:
            query = query.filter_by(status=status)

        return query.order_by(self.model.start_time.desc()).limit(limit).offset(offset).all()

    def get_active_sessions(self, user_id=None):
        """Get currently active sessions"""
        query = self.model.query.filter_by(status="active")

        if user_id:
            query = query.filter_by(user_id=user_id)

        return query.all()

    def update_session(self, session_id, **kwargs):
        """Update session with provided fields"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None

        # Update allowed fields
        allowed_fields = [
            "name",
            "end_time",
            "status",
            "max_temperature",
            "min_temperature",
            "avg_temperature",
            "duration_minutes",
            "session_type",
            "notes",
        ]

        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(session, field, value)

        session.updated_at = datetime.utcnow()
        self.db.session.commit()
        return session

    def end_session(self, session_id, end_time=None):
        """End a grilling session"""
        if end_time is None:
            end_time = datetime.utcnow()

        session = self.get_session_by_id(session_id)
        if not session:
            return None

        session.end_time = end_time
        session.status = "completed"
        session.duration_minutes = session.calculate_duration()
        session.updated_at = datetime.utcnow()

        self.db.session.commit()
        return session

    def cancel_session(self, session_id):
        """Cancel a grilling session"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None

        session.status = "cancelled"
        session.updated_at = datetime.utcnow()

        self.db.session.commit()
        return session

    def update_session_stats(self, session_id, temperature_data):
        """Update session statistics with new temperature data"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None

        # Extract temperature values
        temps = []
        if isinstance(temperature_data, list):
            for reading in temperature_data:
                if isinstance(reading, dict) and "temperature" in reading:
                    temps.append(float(reading["temperature"]))
                elif isinstance(reading, (int, float)):
                    temps.append(float(reading))
        elif isinstance(temperature_data, (int, float)):
            temps.append(float(temperature_data))

        if temps:
            # Update temperature statistics
            current_max = float(session.max_temperature) if session.max_temperature else temps[0]
            current_min = float(session.min_temperature) if session.min_temperature else temps[0]

            session.max_temperature = max(current_max, max(temps))
            session.min_temperature = min(current_min, min(temps))
            session.avg_temperature = (float(session.avg_temperature or 0) + sum(temps)) / (len(temps) + 1)
            session.updated_at = datetime.utcnow()

            self.db.session.commit()

        return session

    def generate_session_name(self, session):
        """Generate a meaningful session name based on cooking patterns"""
        if not session:
            return "Cooking Session"

        # Get session duration and temperature data
        duration_minutes = session.calculate_duration()
        max_temp = float(session.max_temperature) if session.max_temperature else 0

        # Determine cooking type based on temperature and duration
        if max_temp >= 400:  # High heat
            if duration_minutes < 60:
                base_name = "Quick Grill"
            else:
                base_name = "High Heat Cook"
        elif max_temp >= 300:  # Medium-high heat
            if duration_minutes < 90:
                base_name = "Medium Grill"
            else:
                base_name = "Roasting Session"
        elif max_temp >= 200:  # Low and slow
            if duration_minutes >= 180:  # 3+ hours
                base_name = "Smoking Session"
            else:
                base_name = "Low & Slow"
        else:
            base_name = "Cooking Session"

        # Add date for uniqueness
        session_date = session.start_time.strftime("%m/%d")
        return f"{base_name} ({session_date})"

    def cleanup_old_sessions(self, days_old=30):
        """Clean up old incomplete sessions"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Find incomplete sessions older than cutoff
        old_sessions = self.model.query.filter(self.model.status == "active", self.model.start_time < cutoff_date).all()

        cleaned_count = 0
        for session in old_sessions:
            # Cancel old incomplete sessions
            session.status = "cancelled"
            session.updated_at = datetime.utcnow()
            cleaned_count += 1

        if cleaned_count > 0:
            self.db.session.commit()

        return cleaned_count
