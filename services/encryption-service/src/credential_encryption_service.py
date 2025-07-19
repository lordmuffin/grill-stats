"""
Credential Encryption Service

This service provides secure encryption and decryption of ThermoWorks user credentials
using HashiCorp Vault Transit secrets engine. It implements AES-256 encryption with
proper key management and audit logging.

Security Features:
- Uses Vault Transit engine for encryption-as-a-service
- No plain text credential storage
- Comprehensive audit logging
- Key rotation capabilities
- Memory-only decryption during API calls
"""

import base64
import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import hvac
from hvac.exceptions import InvalidRequest, VaultError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import enhanced audit logger
from audit_logger import (
    get_audit_logger,
    log_authentication,
    log_credential_decrypt,
    log_credential_encrypt,
    log_error,
    log_key_rotation,
    log_rate_limit_exceeded,
    log_security_violation,
    log_service_start,
)

# Get audit logger instance
audit_logger = get_audit_logger()


class RateLimiter:
    """Rate limiter for encryption operations to prevent abuse"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed based on rate limit"""
        current_time = time.time()

        with self.lock:
            # Clean old requests
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] if current_time - req_time < self.window_seconds
            ]

            # Check if under limit
            if len(self.requests[identifier]) >= self.max_requests:
                return False

            # Add current request
            self.requests[identifier].append(current_time)
            return True

    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for identifier"""
        current_time = time.time()

        with self.lock:
            # Clean old requests
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] if current_time - req_time < self.window_seconds
            ]

            return max(0, self.max_requests - len(self.requests[identifier]))


class CredentialValidator:
    """Validator for credential data"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_password(password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False
        if len(password) > 128:
            return False
        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in password)
        has_number = any(c.isdigit() for c in password)
        return has_letter and has_number

    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """Validate user ID format"""
        if not user_id or not user_id.isdigit():
            return False
        return int(user_id) > 0


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
            "metadata": asdict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedCredential":
        """Create from dictionary data"""
        return cls(
            encrypted_email=data["encrypted_email"],
            encrypted_password=data["encrypted_password"],
            metadata=CredentialMetadata(**data["metadata"]),
        )


@dataclass
class PlainCredential:
    """Plain text credential (used only in memory)"""

    email: str
    password: str

    def __del__(self):
        """Secure cleanup of sensitive data"""
        if hasattr(self, "email"):
            self.email = "0" * len(self.email)
        if hasattr(self, "password"):
            self.password = "0" * len(self.password)


class CredentialEncryptionService:
    """Service for encrypting/decrypting ThermoWorks credentials using Vault Transit"""

    def __init__(self, vault_url: str = None, vault_token: str = None):
        """Initialize the encryption service

        Args:
            vault_url: Vault server URL (defaults to env var VAULT_URL)
            vault_token: Vault authentication token (defaults to env var VAULT_TOKEN)
        """
        self.vault_url = vault_url or os.getenv("VAULT_URL", "http://vault:8200")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.transit_key_name = "thermoworks-user-credentials"
        self.transit_path = "transit"

        # Initialize rate limiter and validator
        self.rate_limiter = RateLimiter(
            max_requests=int(os.getenv("ENCRYPTION_RATE_LIMIT", "100")),
            window_seconds=int(os.getenv("ENCRYPTION_RATE_WINDOW", "60")),
        )
        self.validator = CredentialValidator()

        # Initialize Vault client
        self.vault_client = hvac.Client(url=self.vault_url)

        # Authenticate with Vault
        self._authenticate()

        # Verify transit engine is available
        self._verify_transit_engine()

        # Log service start
        log_service_start(
            service_name="credential-encryption-service",
            version="1.0.0",
            details={
                "vault_url": self.vault_url,
                "transit_key_name": self.transit_key_name,
                "rate_limit_config": {
                    "max_requests": self.rate_limiter.max_requests,
                    "window_seconds": self.rate_limiter.window_seconds,
                },
            },
        )

        logger.info("Credential encryption service initialized successfully")

    def _authenticate(self):
        """Authenticate with Vault using Kubernetes service account or token"""
        try:
            if self.vault_token:
                # Use provided token
                self.vault_client.token = self.vault_token
                logger.info("Authenticated with Vault using provided token")
            else:
                # Use Kubernetes service account authentication
                jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
                if os.path.exists(jwt_path):
                    with open(jwt_path, "r") as f:
                        jwt_token = f.read().strip()

                    # Authenticate with Vault using Kubernetes auth
                    auth_response = self.vault_client.auth.kubernetes.login(role="grill-stats-role", jwt=jwt_token)

                    self.vault_client.token = auth_response["auth"]["client_token"]

                    # Store token renewal information
                    self.token_renewable = auth_response["auth"]["renewable"]
                    self.token_lease_duration = auth_response["auth"]["lease_duration"]

                    logger.info("Authenticated with Vault using Kubernetes service account")
                else:
                    raise ValueError("No Vault token provided and Kubernetes service account not available")

            # Verify authentication
            if not self.vault_client.is_authenticated():
                raise ValueError("Failed to authenticate with Vault")

            # Log successful authentication
            log_authentication(user_id="service-account", success=True)

        except Exception as e:
            # Log failed authentication
            log_authentication(user_id="service-account", success=False, error_message=str(e))

            logger.error(f"Failed to authenticate with Vault: {e}")
            raise

    def _verify_transit_engine(self):
        """Verify that transit engine is available and key exists"""
        try:
            # Check if transit engine is mounted
            mounts = self.vault_client.sys.list_mounted_secrets_engines()
            if f"{self.transit_path}/" not in mounts["data"]:
                raise ValueError(f"Transit engine not mounted at {self.transit_path}")

            # Check if encryption key exists
            key_info = self.vault_client.secrets.transit.read_key(name=self.transit_key_name, mount_point=self.transit_path)

            if not key_info:
                raise ValueError(f"Encryption key {self.transit_key_name} not found")

            logger.info(f"Transit engine verified with key {self.transit_key_name}")

        except Exception as e:
            logger.error(f"Failed to verify transit engine: {e}")
            raise

    def encrypt_credentials(self, email: str, password: str, user_id: str) -> EncryptedCredential:
        """Encrypt ThermoWorks credentials

        Args:
            email: User's ThermoWorks email
            password: User's ThermoWorks password
            user_id: User ID for audit logging

        Returns:
            EncryptedCredential object with encrypted data and metadata
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not self.validator.validate_user_id(user_id):
                log_security_violation(user_id, "invalid_user_id", details={"provided_user_id": user_id})
                raise ValueError("Invalid user ID format")

            if not self.validator.validate_email(email):
                log_security_violation(
                    user_id,
                    "invalid_email_format",
                    details={"email_domain": (email.split("@")[1] if "@" in email else "unknown")},
                )
                raise ValueError("Invalid email format")

            if not self.validator.validate_password(password):
                log_security_violation(user_id, "weak_password", details={"password_length": len(password)})
                raise ValueError("Password does not meet security requirements")

            # Check rate limit
            if not self.rate_limiter.is_allowed(user_id):
                log_rate_limit_exceeded(
                    user_id,
                    details={"remaining_requests": self.rate_limiter.get_remaining_requests(user_id)},
                )
                raise ValueError("Rate limit exceeded for user")

            # Encrypt email
            email_b64 = base64.b64encode(email.encode("utf-8")).decode("utf-8")
            email_response = self.vault_client.secrets.transit.encrypt_data(
                name=self.transit_key_name,
                plaintext=email_b64,
                mount_point=self.transit_path,
            )

            # Encrypt password
            password_b64 = base64.b64encode(password.encode("utf-8")).decode("utf-8")
            password_response = self.vault_client.secrets.transit.encrypt_data(
                name=self.transit_key_name,
                plaintext=password_b64,
                mount_point=self.transit_path,
            )

            # Get key version for metadata
            key_info = self.vault_client.secrets.transit.read_key(name=self.transit_key_name, mount_point=self.transit_path)

            # Create metadata
            metadata = CredentialMetadata(
                key_version=key_info["data"]["latest_version"],
                algorithm="aes256-gcm96",
                encrypted_at=datetime.now(timezone.utc).isoformat(),
                access_count=0,
            )

            # Create encrypted credential object
            encrypted_credential = EncryptedCredential(
                encrypted_email=email_response["data"]["ciphertext"],
                encrypted_password=password_response["data"]["ciphertext"],
                metadata=metadata,
            )

            # Calculate duration and log success
            duration_ms = int((time.time() - start_time) * 1000)

            log_credential_encrypt(
                user_id=user_id,
                success=True,
                duration_ms=duration_ms,
                ip_address=os.getenv("CLIENT_IP"),
                details={
                    "key_version": metadata.key_version,
                    "algorithm": metadata.algorithm,
                    "email_domain": email.split("@")[1] if "@" in email else "unknown",
                },
            )

            logger.info(f"Successfully encrypted credentials for user {user_id}")
            return encrypted_credential

        except Exception as e:
            # Calculate duration and log failure
            duration_ms = int((time.time() - start_time) * 1000)

            log_credential_encrypt(
                user_id=user_id,
                success=False,
                duration_ms=duration_ms,
                ip_address=os.getenv("CLIENT_IP"),
                details={"error_type": type(e).__name__, "error_message": str(e)},
            )

            logger.error(f"Failed to encrypt credentials for user {user_id}: {e}")
            raise

    def decrypt_credentials(self, encrypted_credential: EncryptedCredential, user_id: str) -> PlainCredential:
        """Decrypt ThermoWorks credentials

        Args:
            encrypted_credential: Encrypted credential object
            user_id: User ID for audit logging

        Returns:
            PlainCredential object with decrypted data (exists only in memory)
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not self.validator.validate_user_id(user_id):
                log_security_violation(user_id, "invalid_user_id", details={"provided_user_id": user_id})
                raise ValueError("Invalid user ID format")

            if (
                not encrypted_credential
                or not encrypted_credential.encrypted_email
                or not encrypted_credential.encrypted_password
            ):
                log_security_violation(
                    user_id,
                    "invalid_encrypted_data",
                    details={
                        "has_email": bool(encrypted_credential and encrypted_credential.encrypted_email),
                        "has_password": bool(encrypted_credential and encrypted_credential.encrypted_password),
                    },
                )
                raise ValueError("Invalid encrypted credential data")

            # Check rate limit
            if not self.rate_limiter.is_allowed(user_id):
                log_rate_limit_exceeded(
                    user_id,
                    details={"remaining_requests": self.rate_limiter.get_remaining_requests(user_id)},
                )
                raise ValueError("Rate limit exceeded for user")

            # Decrypt email
            email_response = self.vault_client.secrets.transit.decrypt_data(
                name=self.transit_key_name,
                ciphertext=encrypted_credential.encrypted_email,
                mount_point=self.transit_path,
            )

            # Decrypt password
            password_response = self.vault_client.secrets.transit.decrypt_data(
                name=self.transit_key_name,
                ciphertext=encrypted_credential.encrypted_password,
                mount_point=self.transit_path,
            )

            # Decode from base64
            email = base64.b64decode(email_response["data"]["plaintext"]).decode("utf-8")
            password = base64.b64decode(password_response["data"]["plaintext"]).decode("utf-8")

            # Update metadata
            encrypted_credential.metadata.last_accessed = datetime.now(timezone.utc).isoformat()
            encrypted_credential.metadata.access_count += 1

            # Create plain credential object
            plain_credential = PlainCredential(email=email, password=password)

            # Calculate duration and log success
            duration_ms = int((time.time() - start_time) * 1000)

            log_credential_decrypt(
                user_id=user_id,
                success=True,
                duration_ms=duration_ms,
                ip_address=os.getenv("CLIENT_IP"),
                details={
                    "key_version": encrypted_credential.metadata.key_version,
                    "access_count": encrypted_credential.metadata.access_count,
                    "algorithm": encrypted_credential.metadata.algorithm,
                },
            )

            logger.info(f"Successfully decrypted credentials for user {user_id}")
            return plain_credential

        except Exception as e:
            # Calculate duration and log failure
            duration_ms = int((time.time() - start_time) * 1000)

            log_credential_decrypt(
                user_id=user_id,
                success=False,
                duration_ms=duration_ms,
                ip_address=os.getenv("CLIENT_IP"),
                details={"error_type": type(e).__name__, "error_message": str(e)},
            )

            logger.error(f"Failed to decrypt credentials for user {user_id}: {e}")
            raise

    def rotate_key(self) -> Dict[str, Any]:
        """Rotate the encryption key

        Returns:
            Dictionary with rotation information
        """
        try:
            # Rotate the key
            rotation_response = self.vault_client.secrets.transit.rotate_key(
                name=self.transit_key_name, mount_point=self.transit_path
            )

            # Get new key information
            key_info = self.vault_client.secrets.transit.read_key(name=self.transit_key_name, mount_point=self.transit_path)

            rotation_info = {
                "rotated_at": datetime.now(timezone.utc).isoformat(),
                "new_version": key_info["data"]["latest_version"],
                "min_decryption_version": key_info["data"]["min_decryption_version"],
                "min_encryption_version": key_info["data"]["min_encryption_version"],
            }

            # Log successful key rotation
            log_key_rotation(
                success=True,
                key_name=self.transit_key_name,
                new_version=rotation_info["new_version"],
                details=rotation_info,
            )

            logger.info(f"Successfully rotated key {self.transit_key_name} to version {rotation_info['new_version']}")
            return rotation_info

        except Exception as e:
            # Log failed key rotation
            log_key_rotation(
                success=False,
                key_name=self.transit_key_name,
                details={"error_type": type(e).__name__, "error_message": str(e)},
            )

            logger.error(f"Failed to rotate key {self.transit_key_name}: {e}")
            raise

    def get_key_info(self) -> Dict[str, Any]:
        """Get information about the encryption key

        Returns:
            Dictionary with key information
        """
        try:
            key_info = self.vault_client.secrets.transit.read_key(name=self.transit_key_name, mount_point=self.transit_path)

            return {
                "name": self.transit_key_name,
                "type": key_info["data"]["type"],
                "latest_version": key_info["data"]["latest_version"],
                "min_decryption_version": key_info["data"]["min_decryption_version"],
                "min_encryption_version": key_info["data"]["min_encryption_version"],
                "deletion_allowed": key_info["data"]["deletion_allowed"],
                "exportable": key_info["data"]["exportable"],
                "allow_plaintext_backup": key_info["data"]["allow_plaintext_backup"],
            }

        except Exception as e:
            logger.error(f"Failed to get key information: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """Perform health check of the encryption service

        Returns:
            Dictionary with health status
        """
        try:
            # Check Vault connection
            if not self.vault_client.is_authenticated():
                return {
                    "status": "unhealthy",
                    "error": "Not authenticated with Vault",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Check transit engine
            self._verify_transit_engine()

            # Test encrypt/decrypt operation
            test_data = "health-check-test"
            test_b64 = base64.b64encode(test_data.encode("utf-8")).decode("utf-8")

            encrypt_response = self.vault_client.secrets.transit.encrypt_data(
                name=self.transit_key_name,
                plaintext=test_b64,
                mount_point=self.transit_path,
            )

            decrypt_response = self.vault_client.secrets.transit.decrypt_data(
                name=self.transit_key_name,
                ciphertext=encrypt_response["data"]["ciphertext"],
                mount_point=self.transit_path,
            )

            decrypted_data = base64.b64decode(decrypt_response["data"]["plaintext"]).decode("utf-8")

            if decrypted_data != test_data:
                return {
                    "status": "unhealthy",
                    "error": "Encrypt/decrypt test failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            return {
                "status": "healthy",
                "vault_url": self.vault_url,
                "transit_key": self.transit_key_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def check_rate_limit(self, user_id: str) -> Dict[str, Any]:
        """Check rate limit status for a user

        Args:
            user_id: User ID to check

        Returns:
            Dictionary with rate limit information
        """
        try:
            if not self.validator.validate_user_id(user_id):
                raise ValueError("Invalid user ID format")

            remaining_requests = self.rate_limiter.get_remaining_requests(user_id)
            is_allowed = remaining_requests > 0

            return {
                "user_id": user_id,
                "remaining_requests": remaining_requests,
                "is_allowed": is_allowed,
                "max_requests": self.rate_limiter.max_requests,
                "window_seconds": self.rate_limiter.window_seconds,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to check rate limit for user {user_id}: {e}")
            raise
