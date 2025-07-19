"""
ThermoWorks Credentials Model

This model handles encrypted storage of ThermoWorks user credentials
using the encryption service for secure credential management.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ThermoWorksCredentials(Base):
    """Model for storing encrypted ThermoWorks credentials"""

    __tablename__ = "thermoworks_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Encrypted credential data
    encrypted_email = Column(Text, nullable=False)
    encrypted_password = Column(Text, nullable=False)

    # Encryption metadata
    encryption_metadata = Column(JSON, nullable=False)

    # Credential status
    is_active = Column(Boolean, default=True)
    last_validated = Column(DateTime, nullable=True)
    validation_attempts = Column(Integer, default=0)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to user
    user = relationship("User", backref="thermoworks_credentials")

    def __repr__(self):
        return f"<ThermoWorksCredentials user_id={self.user_id}>"

    def to_dict(self):
        """Convert to dictionary for API responses (without sensitive data)"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "is_active": self.is_active,
            "last_validated": (
                self.last_validated.isoformat() if self.last_validated else None
            ),
            "validation_attempts": self.validation_attempts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "encryption_metadata": {
                "algorithm": self.encryption_metadata.get("algorithm"),
                "key_version": self.encryption_metadata.get("key_version"),
                "encrypted_at": self.encryption_metadata.get("encrypted_at"),
                "access_count": self.encryption_metadata.get("access_count", 0),
            },
        }


class ThermoWorksCredentialManager:
    """Manager for ThermoWorks credentials with encryption service integration"""

    def __init__(self, db, encryption_service):
        """Initialize the credential manager

        Args:
            db: SQLAlchemy database instance
            encryption_service: CredentialEncryptionService instance
        """
        self.db = db
        self.encryption_service = encryption_service

        # Create the model class dynamically with the database instance
        class ThermoWorksCredentialsModel(db.Model):
            __tablename__ = "thermoworks_credentials"

            id = Column(Integer, primary_key=True)
            user_id = Column(
                Integer, ForeignKey("users.id"), nullable=False, unique=True
            )

            # Encrypted credential data
            encrypted_email = Column(Text, nullable=False)
            encrypted_password = Column(Text, nullable=False)

            # Encryption metadata
            encryption_metadata = Column(JSON, nullable=False)

            # Credential status
            is_active = Column(Boolean, default=True)
            last_validated = Column(DateTime, nullable=True)
            validation_attempts = Column(Integer, default=0)

            # Audit fields
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(
                DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
            )

            def __repr__(self):
                return f"<ThermoWorksCredentials user_id={self.user_id}>"

            def to_dict(self):
                """Convert to dictionary for API responses (without sensitive data)"""
                return {
                    "id": self.id,
                    "user_id": self.user_id,
                    "is_active": self.is_active,
                    "last_validated": (
                        self.last_validated.isoformat() if self.last_validated else None
                    ),
                    "validation_attempts": self.validation_attempts,
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat(),
                    "encryption_metadata": {
                        "algorithm": self.encryption_metadata.get("algorithm"),
                        "key_version": self.encryption_metadata.get("key_version"),
                        "encrypted_at": self.encryption_metadata.get("encrypted_at"),
                        "access_count": self.encryption_metadata.get("access_count", 0),
                    },
                }

        self.model = ThermoWorksCredentialsModel

    def store_credentials(
        self, user_id: int, email: str, password: str
    ) -> ThermoWorksCredentials:
        """Store encrypted ThermoWorks credentials

        Args:
            user_id: User ID
            email: ThermoWorks email
            password: ThermoWorks password

        Returns:
            ThermoWorksCredentials instance
        """
        try:
            # Encrypt the credentials
            encrypted_credential = self.encryption_service.encrypt_credentials(
                email=email, password=password, user_id=str(user_id)
            )

            # Check if credentials already exist for this user
            existing_credentials = self.model.query.filter_by(user_id=user_id).first()

            if existing_credentials:
                # Update existing credentials
                existing_credentials.encrypted_email = (
                    encrypted_credential.encrypted_email
                )
                existing_credentials.encrypted_password = (
                    encrypted_credential.encrypted_password
                )
                existing_credentials.encryption_metadata = (
                    encrypted_credential.metadata.__dict__
                )
                existing_credentials.updated_at = datetime.utcnow()
                existing_credentials.validation_attempts = 0

                credentials = existing_credentials
            else:
                # Create new credentials
                credentials = self.model(
                    user_id=user_id,
                    encrypted_email=encrypted_credential.encrypted_email,
                    encrypted_password=encrypted_credential.encrypted_password,
                    encryption_metadata=encrypted_credential.metadata.__dict__,
                )

                self.db.session.add(credentials)

            self.db.session.commit()
            return credentials

        except Exception as e:
            self.db.session.rollback()
            raise Exception(f"Failed to store credentials: {str(e)}")

    def get_credentials(self, user_id: int) -> tuple:
        """Get decrypted ThermoWorks credentials

        Args:
            user_id: User ID

        Returns:
            Tuple of (email, password) or (None, None) if not found
        """
        try:
            # Get encrypted credentials from database
            credentials = self.model.query.filter_by(
                user_id=user_id, is_active=True
            ).first()

            if not credentials:
                return None, None

            # Create encrypted credential object
            from services.encryption_service.src.credential_encryption_service import (
                CredentialMetadata,
                EncryptedCredential,
            )

            metadata = CredentialMetadata(**credentials.encryption_metadata)
            encrypted_credential = EncryptedCredential(
                encrypted_email=credentials.encrypted_email,
                encrypted_password=credentials.encrypted_password,
                metadata=metadata,
            )

            # Decrypt the credentials
            plain_credential = self.encryption_service.decrypt_credentials(
                encrypted_credential=encrypted_credential, user_id=str(user_id)
            )

            # Update metadata in database
            credentials.encryption_metadata = encrypted_credential.metadata.__dict__
            credentials.updated_at = datetime.utcnow()
            self.db.session.commit()

            return plain_credential.email, plain_credential.password

        except Exception as e:
            raise Exception(f"Failed to retrieve credentials: {str(e)}")

    def delete_credentials(self, user_id: int) -> bool:
        """Delete ThermoWorks credentials

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        try:
            credentials = self.model.query.filter_by(user_id=user_id).first()

            if not credentials:
                return False

            self.db.session.delete(credentials)
            self.db.session.commit()
            return True

        except Exception as e:
            self.db.session.rollback()
            raise Exception(f"Failed to delete credentials: {str(e)}")

    def deactivate_credentials(self, user_id: int) -> bool:
        """Deactivate ThermoWorks credentials

        Args:
            user_id: User ID

        Returns:
            True if deactivated, False if not found
        """
        try:
            credentials = self.model.query.filter_by(user_id=user_id).first()

            if not credentials:
                return False

            credentials.is_active = False
            credentials.updated_at = datetime.utcnow()
            self.db.session.commit()
            return True

        except Exception as e:
            self.db.session.rollback()
            raise Exception(f"Failed to deactivate credentials: {str(e)}")

    def validate_credentials(self, user_id: int) -> bool:
        """Mark credentials as validated

        Args:
            user_id: User ID

        Returns:
            True if marked as validated, False if not found
        """
        try:
            credentials = self.model.query.filter_by(user_id=user_id).first()

            if not credentials:
                return False

            credentials.last_validated = datetime.utcnow()
            credentials.validation_attempts = 0
            self.db.session.commit()
            return True

        except Exception as e:
            self.db.session.rollback()
            raise Exception(f"Failed to validate credentials: {str(e)}")

    def increment_validation_attempts(self, user_id: int) -> bool:
        """Increment validation attempts

        Args:
            user_id: User ID

        Returns:
            True if incremented, False if not found
        """
        try:
            credentials = self.model.query.filter_by(user_id=user_id).first()

            if not credentials:
                return False

            credentials.validation_attempts += 1
            credentials.updated_at = datetime.utcnow()

            # Deactivate after 5 failed attempts
            if credentials.validation_attempts >= 5:
                credentials.is_active = False

            self.db.session.commit()
            return True

        except Exception as e:
            self.db.session.rollback()
            raise Exception(f"Failed to increment validation attempts: {str(e)}")

    def get_credentials_info(self, user_id: int) -> dict:
        """Get credential information (without sensitive data)

        Args:
            user_id: User ID

        Returns:
            Dictionary with credential information
        """
        credentials = self.model.query.filter_by(user_id=user_id).first()

        if not credentials:
            return None

        return credentials.to_dict()
