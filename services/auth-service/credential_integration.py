"""
Credential Integration Service

This module integrates the auth service with the encryption service for secure
ThermoWorks credential storage and retrieval.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class CredentialMetadata:
    """Metadata for encrypted credentials"""

    key_version: int
    algorithm: str
    encrypted_at: str
    last_accessed: Optional[str] = None
    access_count: int = 0


@dataclass
class EncryptedCredential:
    """Encrypted credential with metadata"""

    encrypted_email: str
    encrypted_password: str
    metadata: CredentialMetadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "encrypted_email": self.encrypted_email,
            "encrypted_password": self.encrypted_password,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedCredential":
        """Create from dictionary data"""
        return cls(
            encrypted_email=data["encrypted_email"],
            encrypted_password=data["encrypted_password"],
            metadata=CredentialMetadata(**data["metadata"]),
        )


class CredentialIntegrationService:
    """Service for integrating auth service with encryption service"""

    def __init__(self, encryption_service_url: str = None):
        """Initialize the credential integration service

        Args:
            encryption_service_url: URL of the encryption service
        """
        self.encryption_service_url = encryption_service_url or os.getenv(
            "ENCRYPTION_SERVICE_URL", "http://encryption-service:8082"
        )
        self.timeout = 30
        self.max_retries = 3
        self.session = requests.Session()

        # Configure session for better security
        self.session.headers.update(
            {
                "User-Agent": "grill-stats-auth-service/1.0",
                "Content-Type": "application/json",
            }
        )

        # Test connection to encryption service
        self._test_connection()

    def _test_connection(self):
        """Test connection to encryption service"""
        try:
            response = self.session.get(
                f"{self.encryption_service_url}/health", timeout=5
            )
            response.raise_for_status()
            health_data = response.json()

            if health_data.get("status") == "healthy":
                logger.info("Successfully connected to encryption service")
            else:
                raise Exception(
                    f"Encryption service is unhealthy: {health_data.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Failed to connect to encryption service: {e}")
            raise

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to encryption service with retry logic"""
        url = f"{self.encryption_service_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, timeout=self.timeout)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=data, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)  # Exponential backoff

        raise Exception("Max retries exceeded")

    def encrypt_credentials(
        self, email: str, password: str, user_id: int
    ) -> EncryptedCredential:
        """Encrypt ThermoWorks credentials

        Args:
            email: ThermoWorks email
            password: ThermoWorks password
            user_id: User ID for audit logging

        Returns:
            EncryptedCredential object
        """
        try:
            data = {"email": email, "password": password, "user_id": str(user_id)}

            response = self._make_request("POST", "/encrypt", data)

            if response.get("status") != "success":
                raise Exception(
                    f"Encryption failed: {response.get('error', 'Unknown error')}"
                )

            encrypted_credential_data = response["encrypted_credential"]
            return EncryptedCredential.from_dict(encrypted_credential_data)

        except Exception as e:
            logger.error(f"Failed to encrypt credentials for user {user_id}: {e}")
            raise

    def decrypt_credentials(
        self, encrypted_credential: EncryptedCredential, user_id: int
    ) -> Tuple[str, str]:
        """Decrypt ThermoWorks credentials

        Args:
            encrypted_credential: EncryptedCredential object
            user_id: User ID for audit logging

        Returns:
            Tuple of (email, password)
        """
        try:
            data = {
                "encrypted_credential": encrypted_credential.to_dict(),
                "user_id": str(user_id),
            }

            response = self._make_request("POST", "/decrypt", data)

            if response.get("status") != "success":
                raise Exception(
                    f"Decryption failed: {response.get('error', 'Unknown error')}"
                )

            credentials = response["credentials"]
            return credentials["email"], credentials["password"]

        except Exception as e:
            logger.error(f"Failed to decrypt credentials for user {user_id}: {e}")
            raise

    def rotate_encryption_key(self, admin_token: str) -> Dict[str, Any]:
        """Rotate the encryption key (admin only)

        Args:
            admin_token: Admin authorization token

        Returns:
            Dictionary with rotation information
        """
        try:
            headers = {"Authorization": f"Bearer {admin_token}"}

            response = requests.post(
                f"{self.encryption_service_url}/rotate-key",
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()

            if result.get("status") != "success":
                raise Exception(
                    f"Key rotation failed: {result.get('error', 'Unknown error')}"
                )

            return result["rotation_info"]

        except Exception as e:
            logger.error(f"Failed to rotate encryption key: {e}")
            raise

    def get_encryption_key_info(self) -> Dict[str, Any]:
        """Get information about the encryption key

        Returns:
            Dictionary with key information
        """
        try:
            response = self._make_request("GET", "/key-info")

            if response.get("status") != "success":
                raise Exception(
                    f"Failed to get key info: {response.get('error', 'Unknown error')}"
                )

            return response["key_info"]

        except Exception as e:
            logger.error(f"Failed to get encryption key info: {e}")
            raise

    def check_rate_limit(self, user_id: int) -> Dict[str, Any]:
        """Check rate limit for user

        Args:
            user_id: User ID

        Returns:
            Dictionary with rate limit information
        """
        try:
            response = self._make_request("GET", f"/rate-limit/{user_id}")

            if response.get("status") != "success":
                raise Exception(
                    f"Rate limit check failed: {response.get('error', 'Unknown error')}"
                )

            return response["rate_limit"]

        except Exception as e:
            logger.error(f"Failed to check rate limit for user {user_id}: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Check health of encryption service

        Returns:
            Dictionary with health status
        """
        try:
            response = self._make_request("GET", "/health")
            return response

        except Exception as e:
            logger.error(f"Encryption service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


class DatabaseCredentialManager:
    """Manager for encrypted credentials in database"""

    def __init__(self, db_connection, credential_service: CredentialIntegrationService):
        """Initialize the database credential manager

        Args:
            db_connection: Database connection
            credential_service: CredentialIntegrationService instance
        """
        self.db = db_connection
        self.credential_service = credential_service

    def store_encrypted_credentials(
        self, user_id: int, email: str, password: str
    ) -> bool:
        """Store encrypted ThermoWorks credentials in database

        Args:
            user_id: User ID
            email: ThermoWorks email
            password: ThermoWorks password

        Returns:
            True if successful, False otherwise
        """
        try:
            # Encrypt the credentials
            encrypted_credential = self.credential_service.encrypt_credentials(
                email, password, user_id
            )

            # Store in database
            cursor = self.db.cursor()

            # Check if credentials already exist
            cursor.execute(
                """
                SELECT id FROM thermoworks_credentials
                WHERE user_id = %s
            """,
                (user_id,),
            )

            existing_record = cursor.fetchone()

            if existing_record:
                # Update existing record
                cursor.execute(
                    """
                    UPDATE thermoworks_credentials
                    SET encrypted_email = %s,
                        encrypted_password = %s,
                        encryption_metadata = %s,
                        updated_at = CURRENT_TIMESTAMP,
                        validation_attempts = 0,
                        is_active = TRUE
                    WHERE user_id = %s
                """,
                    (
                        encrypted_credential.encrypted_email,
                        encrypted_credential.encrypted_password,
                        json.dumps(encrypted_credential.metadata.__dict__),
                        user_id,
                    ),
                )
            else:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO thermoworks_credentials (
                        user_id, encrypted_email, encrypted_password,
                        encryption_metadata, is_active
                    ) VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        user_id,
                        encrypted_credential.encrypted_email,
                        encrypted_credential.encrypted_password,
                        json.dumps(encrypted_credential.metadata.__dict__),
                        True,
                    ),
                )

            self.db.commit()

            # Log the operation
            self._log_credential_access(user_id, "encrypt", True)

            logger.info(f"Successfully stored encrypted credentials for user {user_id}")
            return True

        except Exception as e:
            self.db.rollback()
            self._log_credential_access(user_id, "encrypt", False, str(e))
            logger.error(
                f"Failed to store encrypted credentials for user {user_id}: {e}"
            )
            return False

    def get_decrypted_credentials(
        self, user_id: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get decrypted ThermoWorks credentials from database

        Args:
            user_id: User ID

        Returns:
            Tuple of (email, password) or (None, None) if not found
        """
        try:
            cursor = self.db.cursor()

            # Get encrypted credentials
            cursor.execute(
                """
                SELECT encrypted_email, encrypted_password, encryption_metadata
                FROM thermoworks_credentials
                WHERE user_id = %s AND is_active = TRUE
            """,
                (user_id,),
            )

            result = cursor.fetchone()

            if not result:
                return None, None

            encrypted_email, encrypted_password, metadata_json = result

            # Parse metadata
            metadata = CredentialMetadata(**json.loads(metadata_json))

            # Create encrypted credential object
            encrypted_credential = EncryptedCredential(
                encrypted_email=encrypted_email,
                encrypted_password=encrypted_password,
                metadata=metadata,
            )

            # Decrypt credentials
            email, password = self.credential_service.decrypt_credentials(
                encrypted_credential, user_id
            )

            # Update access metadata
            self._update_access_metadata(user_id, encrypted_credential)

            # Log the operation
            self._log_credential_access(user_id, "decrypt", True)

            return email, password

        except Exception as e:
            self._log_credential_access(user_id, "decrypt", False, str(e))
            logger.error(f"Failed to get decrypted credentials for user {user_id}: {e}")
            return None, None

    def _update_access_metadata(
        self, user_id: int, encrypted_credential: EncryptedCredential
    ):
        """Update access metadata after successful decryption"""
        try:
            cursor = self.db.cursor()

            # Update metadata
            encrypted_credential.metadata.last_accessed = datetime.now(
                timezone.utc
            ).isoformat()
            encrypted_credential.metadata.access_count += 1

            cursor.execute(
                """
                UPDATE thermoworks_credentials
                SET encryption_metadata = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """,
                (json.dumps(encrypted_credential.metadata.__dict__), user_id),
            )

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update access metadata for user {user_id}: {e}")

    def _log_credential_access(
        self, user_id: int, action: str, success: bool, details: str = None
    ):
        """Log credential access operation"""
        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                INSERT INTO credential_access_log (user_id, action, success, details)
                VALUES (%s, %s, %s, %s)
            """,
                (user_id, action, success, details),
            )

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log credential access: {e}")

    def validate_credentials(self, user_id: int) -> bool:
        """Mark credentials as validated after successful ThermoWorks API call"""
        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                UPDATE thermoworks_credentials
                SET last_validated = CURRENT_TIMESTAMP,
                    validation_attempts = 0
                WHERE user_id = %s
            """,
                (user_id,),
            )

            self.db.commit()
            self._log_credential_access(user_id, "validate", True)

            return True

        except Exception as e:
            self._log_credential_access(user_id, "validate", False, str(e))
            logger.error(f"Failed to validate credentials for user {user_id}: {e}")
            return False

    def increment_validation_attempts(self, user_id: int) -> bool:
        """Increment validation attempts after failed ThermoWorks API call"""
        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                UPDATE thermoworks_credentials
                SET validation_attempts = validation_attempts + 1,
                    is_active = CASE
                        WHEN validation_attempts + 1 >= 5 THEN FALSE
                        ELSE TRUE
                    END
                WHERE user_id = %s
            """,
                (user_id,),
            )

            self.db.commit()
            return True

        except Exception as e:
            logger.error(
                f"Failed to increment validation attempts for user {user_id}: {e}"
            )
            return False

    def deactivate_credentials(self, user_id: int) -> bool:
        """Deactivate credentials for user"""
        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                UPDATE thermoworks_credentials
                SET is_active = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """,
                (user_id,),
            )

            self.db.commit()
            self._log_credential_access(user_id, "deactivate", True)

            return True

        except Exception as e:
            self._log_credential_access(user_id, "deactivate", False, str(e))
            logger.error(f"Failed to deactivate credentials for user {user_id}: {e}")
            return False

    def delete_credentials(self, user_id: int) -> bool:
        """Delete credentials for user"""
        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                DELETE FROM thermoworks_credentials
                WHERE user_id = %s
            """,
                (user_id,),
            )

            self.db.commit()
            self._log_credential_access(user_id, "delete", True)

            return True

        except Exception as e:
            self._log_credential_access(user_id, "delete", False, str(e))
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            return False
