"""
Unit tests for the credential encryption service.

These tests validate the encryption service functionality including:
- Encryption/decryption operations
- Rate limiting
- Validation
- Error handling
- Security features
"""

import base64
import json
import os

# Import the modules to test
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../services/encryption-service/src"),
)

from credential_encryption_service import (
    CredentialEncryptionService,
    CredentialMetadata,
    CredentialValidator,
    EncryptedCredential,
    PlainCredential,
    RateLimiter,
)


class TestCredentialValidator:
    """Test the credential validator"""

    def test_validate_email_valid(self):
        """Test valid email validation"""
        assert CredentialValidator.validate_email("test@example.com") == True
        assert CredentialValidator.validate_email("user.name@domain.co.uk") == True
        assert CredentialValidator.validate_email("test+tag@example.com") == True

    def test_validate_email_invalid(self):
        """Test invalid email validation"""
        assert CredentialValidator.validate_email("invalid-email") == False
        assert CredentialValidator.validate_email("@example.com") == False
        assert CredentialValidator.validate_email("test@") == False
        assert CredentialValidator.validate_email("") == False

    def test_validate_password_valid(self):
        """Test valid password validation"""
        assert CredentialValidator.validate_password("password123") == True
        assert CredentialValidator.validate_password("ComplexPass1") == True
        assert CredentialValidator.validate_password("test-pass-123") == True

    def test_validate_password_invalid(self):
        """Test invalid password validation"""
        assert CredentialValidator.validate_password("short") == False  # Too short
        assert (
            CredentialValidator.validate_password("onlyletters") == False
        )  # No numbers
        assert CredentialValidator.validate_password("12345678") == False  # No letters
        assert CredentialValidator.validate_password("a" * 129) == False  # Too long

    def test_validate_user_id_valid(self):
        """Test valid user ID validation"""
        assert CredentialValidator.validate_user_id("123") == True
        assert CredentialValidator.validate_user_id("1") == True
        assert CredentialValidator.validate_user_id("999999") == True

    def test_validate_user_id_invalid(self):
        """Test invalid user ID validation"""
        assert CredentialValidator.validate_user_id("0") == False
        assert CredentialValidator.validate_user_id("-1") == False
        assert CredentialValidator.validate_user_id("abc") == False
        assert CredentialValidator.validate_user_id("") == False
        assert CredentialValidator.validate_user_id("12.5") == False


class TestRateLimiter:
    """Test the rate limiter"""

    def test_rate_limiter_allows_under_limit(self):
        """Test rate limiter allows requests under the limit"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.is_allowed("user123") == True

        # 6th request should be blocked
        assert limiter.is_allowed("user123") == False

    def test_rate_limiter_different_users(self):
        """Test rate limiter handles different users separately"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Each user should have their own limit
        assert limiter.is_allowed("user1") == True
        assert limiter.is_allowed("user2") == True
        assert limiter.is_allowed("user1") == True
        assert limiter.is_allowed("user2") == True

        # Now both users should be at their limit
        assert limiter.is_allowed("user1") == False
        assert limiter.is_allowed("user2") == False

    def test_rate_limiter_remaining_requests(self):
        """Test rate limiter tracks remaining requests correctly"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        assert limiter.get_remaining_requests("user123") == 3

        limiter.is_allowed("user123")
        assert limiter.get_remaining_requests("user123") == 2

        limiter.is_allowed("user123")
        assert limiter.get_remaining_requests("user123") == 1

        limiter.is_allowed("user123")
        assert limiter.get_remaining_requests("user123") == 0


class TestCredentialMetadata:
    """Test credential metadata"""

    def test_metadata_creation(self):
        """Test metadata creation"""
        metadata = CredentialMetadata(
            key_version=1,
            algorithm="aes256-gcm96",
            encrypted_at=datetime.now(timezone.utc).isoformat(),
            access_count=0,
        )

        assert metadata.key_version == 1
        assert metadata.algorithm == "aes256-gcm96"
        assert metadata.access_count == 0
        assert metadata.last_accessed is None


class TestEncryptedCredential:
    """Test encrypted credential"""

    def test_encrypted_credential_creation(self):
        """Test encrypted credential creation"""
        metadata = CredentialMetadata(
            key_version=1,
            algorithm="aes256-gcm96",
            encrypted_at=datetime.now(timezone.utc).isoformat(),
            access_count=0,
        )

        credential = EncryptedCredential(
            encrypted_email="vault:v1:encrypted_email_data",
            encrypted_password="vault:v1:encrypted_password_data",
            metadata=metadata,
        )

        assert credential.encrypted_email == "vault:v1:encrypted_email_data"
        assert credential.encrypted_password == "vault:v1:encrypted_password_data"
        assert credential.metadata.key_version == 1

    def test_encrypted_credential_to_dict(self):
        """Test encrypted credential to dictionary conversion"""
        metadata = CredentialMetadata(
            key_version=1,
            algorithm="aes256-gcm96",
            encrypted_at=datetime.now(timezone.utc).isoformat(),
            access_count=0,
        )

        credential = EncryptedCredential(
            encrypted_email="vault:v1:encrypted_email_data",
            encrypted_password="vault:v1:encrypted_password_data",
            metadata=metadata,
        )

        data = credential.to_dict()

        assert data["encrypted_email"] == "vault:v1:encrypted_email_data"
        assert data["encrypted_password"] == "vault:v1:encrypted_password_data"
        assert data["metadata"]["key_version"] == 1
        assert data["metadata"]["algorithm"] == "aes256-gcm96"

    def test_encrypted_credential_from_dict(self):
        """Test encrypted credential from dictionary conversion"""
        data = {
            "encrypted_email": "vault:v1:encrypted_email_data",
            "encrypted_password": "vault:v1:encrypted_password_data",
            "metadata": {
                "key_version": 1,
                "algorithm": "aes256-gcm96",
                "encrypted_at": datetime.now(timezone.utc).isoformat(),
                "access_count": 0,
            },
        }

        credential = EncryptedCredential.from_dict(data)

        assert credential.encrypted_email == "vault:v1:encrypted_email_data"
        assert credential.encrypted_password == "vault:v1:encrypted_password_data"
        assert credential.metadata.key_version == 1
        assert credential.metadata.algorithm == "aes256-gcm96"


class TestPlainCredential:
    """Test plain credential"""

    def test_plain_credential_creation(self):
        """Test plain credential creation"""
        credential = PlainCredential(email="test@example.com", password="password123")

        assert credential.email == "test@example.com"
        assert credential.password == "password123"


class TestCredentialEncryptionService:
    """Test the credential encryption service"""

    @patch("credential_encryption_service.hvac.Client")
    def test_service_initialization(self, mock_hvac_client):
        """Test service initialization"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            assert service.vault_url == "http://vault:8200"
            assert service.transit_key_name == "thermoworks-user-credentials"
            assert service.transit_path == "transit"
            assert service.rate_limiter is not None
            assert service.validator is not None

    @patch("credential_encryption_service.hvac.Client")
    def test_encrypt_credentials_success(self, mock_hvac_client):
        """Test successful credential encryption"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        # Mock encryption responses
        mock_client.secrets.transit.encrypt_data.side_effect = [
            {"data": {"ciphertext": "vault:v1:encrypted_email"}},
            {"data": {"ciphertext": "vault:v1:encrypted_password"}},
        ]

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            encrypted = service.encrypt_credentials(
                email="test@example.com", password="password123", user_id="123"
            )

            assert encrypted.encrypted_email == "vault:v1:encrypted_email"
            assert encrypted.encrypted_password == "vault:v1:encrypted_password"
            assert encrypted.metadata.key_version == 1
            assert encrypted.metadata.algorithm == "aes256-gcm96"

    @patch("credential_encryption_service.hvac.Client")
    def test_encrypt_credentials_invalid_email(self, mock_hvac_client):
        """Test credential encryption with invalid email"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            with pytest.raises(ValueError, match="Invalid email format"):
                service.encrypt_credentials(
                    email="invalid-email", password="password123", user_id="123"
                )

    @patch("credential_encryption_service.hvac.Client")
    def test_encrypt_credentials_invalid_password(self, mock_hvac_client):
        """Test credential encryption with invalid password"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            with pytest.raises(
                ValueError, match="Password does not meet security requirements"
            ):
                service.encrypt_credentials(
                    email="test@example.com", password="short", user_id="123"
                )

    @patch("credential_encryption_service.hvac.Client")
    def test_encrypt_credentials_invalid_user_id(self, mock_hvac_client):
        """Test credential encryption with invalid user ID"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            with pytest.raises(ValueError, match="Invalid user ID format"):
                service.encrypt_credentials(
                    email="test@example.com", password="password123", user_id="invalid"
                )

    @patch("credential_encryption_service.hvac.Client")
    def test_decrypt_credentials_success(self, mock_hvac_client):
        """Test successful credential decryption"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        # Mock decryption responses
        email_b64 = base64.b64encode("test@example.com".encode()).decode()
        password_b64 = base64.b64encode("password123".encode()).decode()

        mock_client.secrets.transit.decrypt_data.side_effect = [
            {"data": {"plaintext": email_b64}},
            {"data": {"plaintext": password_b64}},
        ]

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            metadata = CredentialMetadata(
                key_version=1,
                algorithm="aes256-gcm96",
                encrypted_at=datetime.now(timezone.utc).isoformat(),
                access_count=0,
            )

            encrypted = EncryptedCredential(
                encrypted_email="vault:v1:encrypted_email",
                encrypted_password="vault:v1:encrypted_password",
                metadata=metadata,
            )

            plain = service.decrypt_credentials(encrypted, "123")

            assert plain.email == "test@example.com"
            assert plain.password == "password123"

    @patch("credential_encryption_service.hvac.Client")
    def test_decrypt_credentials_invalid_user_id(self, mock_hvac_client):
        """Test credential decryption with invalid user ID"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            metadata = CredentialMetadata(
                key_version=1,
                algorithm="aes256-gcm96",
                encrypted_at=datetime.now(timezone.utc).isoformat(),
                access_count=0,
            )

            encrypted = EncryptedCredential(
                encrypted_email="vault:v1:encrypted_email",
                encrypted_password="vault:v1:encrypted_password",
                metadata=metadata,
            )

            with pytest.raises(ValueError, match="Invalid user ID format"):
                service.decrypt_credentials(encrypted, "invalid")

    @patch("credential_encryption_service.hvac.Client")
    def test_rate_limit_exceeded(self, mock_hvac_client):
        """Test rate limit exceeded"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        with patch.dict(
            os.environ, {"VAULT_TOKEN": "test-token", "ENCRYPTION_RATE_LIMIT": "2"}
        ):
            service = CredentialEncryptionService()

            # First two requests should work
            service.encrypt_credentials("test@example.com", "password123", "123")
            service.encrypt_credentials("test@example.com", "password123", "123")

            # Third request should be rate limited
            with pytest.raises(ValueError, match="Rate limit exceeded"):
                service.encrypt_credentials("test@example.com", "password123", "123")

    @patch("credential_encryption_service.hvac.Client")
    def test_health_check_healthy(self, mock_hvac_client):
        """Test health check when service is healthy"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.transit.read_key.return_value = {
            "data": {"latest_version": 1}
        }
        mock_client.sys.list_mounted_secrets_engines.return_value = {
            "data": {"transit/": {}}
        }

        # Mock health check encryption/decryption
        test_b64 = base64.b64encode("health-check-test".encode()).decode()
        mock_client.secrets.transit.encrypt_data.return_value = {
            "data": {"ciphertext": "vault:v1:health_check_encrypted"}
        }
        mock_client.secrets.transit.decrypt_data.return_value = {
            "data": {"plaintext": test_b64}
        }

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            health = service.health_check()

            assert health["status"] == "healthy"
            assert health["vault_url"] == "http://vault:8200"
            assert health["transit_key"] == "thermoworks-user-credentials"

    @patch("credential_encryption_service.hvac.Client")
    def test_health_check_unhealthy(self, mock_hvac_client):
        """Test health check when service is unhealthy"""
        mock_client = Mock()
        mock_hvac_client.return_value = mock_client
        mock_client.is_authenticated.return_value = False

        with patch.dict(os.environ, {"VAULT_TOKEN": "test-token"}):
            service = CredentialEncryptionService()

            health = service.health_check()

            assert health["status"] == "unhealthy"
            assert "error" in health


if __name__ == "__main__":
    pytest.main([__file__])
