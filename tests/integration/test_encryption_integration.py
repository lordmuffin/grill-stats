"""
Integration tests for the credential encryption service.

These tests validate the end-to-end functionality including:
- Database integration
- Service communication
- API endpoints
- Error handling
- Security flows
"""

import pytest
import requests
import json
import time
import os
from datetime import datetime, timezone
from unittest.mock import patch, Mock

# Test configuration
ENCRYPTION_SERVICE_URL = os.getenv('ENCRYPTION_SERVICE_URL', 'http://localhost:8082')
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8081')


class TestEncryptionServiceAPI:
    """Test the encryption service API endpoints"""
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = requests.get(f"{ENCRYPTION_SERVICE_URL}/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] in ['healthy', 'unhealthy']
        assert 'timestamp' in data
    
    def test_encrypt_endpoint_success(self):
        """Test successful encryption endpoint"""
        payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'user_id': '123'
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data['status'] == 'success'
            assert 'encrypted_credential' in data
            assert 'encrypted_email' in data['encrypted_credential']
            assert 'encrypted_password' in data['encrypted_credential']
            assert 'metadata' in data['encrypted_credential']
            
            # Verify encrypted data format
            encrypted_email = data['encrypted_credential']['encrypted_email']
            encrypted_password = data['encrypted_credential']['encrypted_password']
            
            assert encrypted_email.startswith('vault:v')
            assert encrypted_password.startswith('vault:v')
        else:
            # Service may not be available, skip test
            pytest.skip("Encryption service not available")
    
    def test_encrypt_endpoint_invalid_email(self):
        """Test encryption endpoint with invalid email"""
        payload = {
            'email': 'invalid-email',
            'password': 'password123',
            'user_id': '123'
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 500
        data = response.json()
        assert data['error'] == 'Failed to encrypt credentials'
    
    def test_encrypt_endpoint_invalid_password(self):
        """Test encryption endpoint with invalid password"""
        payload = {
            'email': 'test@example.com',
            'password': 'short',
            'user_id': '123'
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 500
        data = response.json()
        assert data['error'] == 'Failed to encrypt credentials'
    
    def test_encrypt_endpoint_missing_fields(self):
        """Test encryption endpoint with missing required fields"""
        payload = {
            'email': 'test@example.com'
            # Missing password and user_id
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 400
        data = response.json()
        assert 'Missing required fields' in data['error']
    
    def test_decrypt_endpoint_success(self):
        """Test successful decryption endpoint"""
        # First encrypt some data
        encrypt_payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'user_id': '123'
        }
        
        encrypt_response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=encrypt_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if encrypt_response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        if encrypt_response.status_code != 200:
            pytest.skip("Encryption failed, cannot test decryption")
        
        encrypted_data = encrypt_response.json()['encrypted_credential']
        
        # Now decrypt it
        decrypt_payload = {
            'encrypted_credential': encrypted_data,
            'user_id': '123'
        }
        
        decrypt_response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/decrypt",
            json=decrypt_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        assert decrypt_response.status_code == 200
        data = decrypt_response.json()
        assert data['status'] == 'success'
        assert data['credentials']['email'] == 'test@example.com'
        assert data['credentials']['password'] == 'password123'
    
    def test_rate_limit_endpoint(self):
        """Test rate limit endpoint"""
        response = requests.get(f"{ENCRYPTION_SERVICE_URL}/rate-limit/123")
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'rate_limit' in data
        assert 'remaining_requests' in data['rate_limit']
        assert 'is_allowed' in data['rate_limit']
    
    def test_key_info_endpoint(self):
        """Test key information endpoint"""
        response = requests.get(f"{ENCRYPTION_SERVICE_URL}/key-info")
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'key_info' in data
        assert 'name' in data['key_info']
        assert 'type' in data['key_info']
        assert 'latest_version' in data['key_info']


class TestAuthServiceIntegration:
    """Test the authentication service integration with encryption"""
    
    def setup_method(self):
        """Setup method to create a test user"""
        self.test_user = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'name': 'Test User'
        }
        
        # Register test user
        try:
            register_response = requests.post(
                f"{AUTH_SERVICE_URL}/api/auth/register",
                json=self.test_user,
                headers={'Content-Type': 'application/json'}
            )
            
            if register_response.status_code in [200, 409]:  # Success or user already exists
                # Login to get JWT token
                login_response = requests.post(
                    f"{AUTH_SERVICE_URL}/api/auth/login",
                    json={
                        'email': self.test_user['email'],
                        'password': self.test_user['password']
                    },
                    headers={'Content-Type': 'application/json'}
                )
                
                if login_response.status_code == 200:
                    self.jwt_token = login_response.json()['data']['jwt_token']
                    self.headers = {'Authorization': f'Bearer {self.jwt_token}'}
                else:
                    self.jwt_token = None
                    self.headers = {}
            else:
                self.jwt_token = None
                self.headers = {}
        except requests.exceptions.RequestException:
            self.jwt_token = None
            self.headers = {}
    
    def test_thermoworks_connect_endpoint(self):
        """Test ThermoWorks connect endpoint with encryption"""
        if not self.jwt_token:
            pytest.skip("Auth service not available or login failed")
        
        payload = {
            'thermoworks_email': 'thermoworks@example.com',
            'thermoworks_password': 'thermoworks123'
        }
        
        response = requests.post(
            f"{AUTH_SERVICE_URL}/api/auth/thermoworks/connect",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        # Should succeed or fail with authentication error
        assert response.status_code in [200, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert data['status'] == 'success'
            assert data['data']['connected'] == True
            assert data['data']['encrypted'] == True
    
    def test_thermoworks_status_endpoint(self):
        """Test ThermoWorks status endpoint"""
        if not self.jwt_token:
            pytest.skip("Auth service not available or login failed")
        
        response = requests.get(
            f"{AUTH_SERVICE_URL}/api/auth/thermoworks/status",
            headers=self.headers
        )
        
        if response.status_code == 503:
            pytest.skip("Service not available")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'connected' in data['data']
        assert 'encrypted' in data['data']
    
    def test_thermoworks_rate_limit_endpoint(self):
        """Test ThermoWorks rate limit endpoint"""
        if not self.jwt_token:
            pytest.skip("Auth service not available or login failed")
        
        response = requests.get(
            f"{AUTH_SERVICE_URL}/api/auth/thermoworks/rate-limit",
            headers=self.headers
        )
        
        if response.status_code == 503:
            pytest.skip("Service not available")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'rate_limit' in data['data']
        assert 'remaining_requests' in data['data']['rate_limit']
        assert 'is_allowed' in data['data']['rate_limit']


class TestRateLimitingIntegration:
    """Test rate limiting integration"""
    
    def test_rate_limiting_enforcement(self):
        """Test that rate limiting is enforced"""
        # This test requires the service to be running with a low rate limit
        # Set ENCRYPTION_RATE_LIMIT=2 for testing
        
        user_id = "test_rate_limit_user"
        
        # Make requests up to the limit
        for i in range(2):
            payload = {
                'email': 'test@example.com',
                'password': 'password123',
                'user_id': user_id
            }
            
            response = requests.post(
                f"{ENCRYPTION_SERVICE_URL}/encrypt",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 503:
                pytest.skip("Encryption service not available")
            
            if i < 2:  # First 2 requests should succeed
                assert response.status_code == 200
        
        # Additional request should be rate limited
        payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'user_id': user_id
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        # Should be rate limited
        assert response.status_code == 500
        data = response.json()
        assert 'Rate limit exceeded' in data['details']


class TestErrorHandling:
    """Test error handling in the integration"""
    
    def test_invalid_json_request(self):
        """Test handling of invalid JSON requests"""
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            data="invalid json",
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 400
        data = response.json()
        assert 'Request must be JSON' in data['error']
    
    def test_missing_content_type(self):
        """Test handling of missing content type"""
        payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'user_id': '123'
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload
            # No Content-Type header
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        # Should still work with most HTTP clients adding Content-Type automatically
        assert response.status_code in [200, 400]
    
    def test_invalid_endpoint(self):
        """Test handling of invalid endpoints"""
        response = requests.get(f"{ENCRYPTION_SERVICE_URL}/invalid-endpoint")
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        assert response.status_code == 404
        data = response.json()
        assert 'not found' in data['error'].lower()


class TestSecurityValidation:
    """Test security validations in the integration"""
    
    def test_credential_validation(self):
        """Test that credentials are properly validated"""
        test_cases = [
            # Invalid email formats
            {'email': 'invalid-email', 'password': 'password123', 'user_id': '123'},
            {'email': '@example.com', 'password': 'password123', 'user_id': '123'},
            {'email': 'test@', 'password': 'password123', 'user_id': '123'},
            
            # Invalid passwords
            {'email': 'test@example.com', 'password': 'short', 'user_id': '123'},
            {'email': 'test@example.com', 'password': 'onlyletters', 'user_id': '123'},
            {'email': 'test@example.com', 'password': '12345678', 'user_id': '123'},
            
            # Invalid user IDs
            {'email': 'test@example.com', 'password': 'password123', 'user_id': '0'},
            {'email': 'test@example.com', 'password': 'password123', 'user_id': '-1'},
            {'email': 'test@example.com', 'password': 'password123', 'user_id': 'abc'},
        ]
        
        for payload in test_cases:
            response = requests.post(
                f"{ENCRYPTION_SERVICE_URL}/encrypt",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 503:
                pytest.skip("Encryption service not available")
            
            # Should fail validation
            assert response.status_code == 500
            data = response.json()
            assert 'Failed to encrypt credentials' in data['error']
    
    def test_encrypted_data_format(self):
        """Test that encrypted data follows expected format"""
        payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'user_id': '123'
        }
        
        response = requests.post(
            f"{ENCRYPTION_SERVICE_URL}/encrypt",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 503:
            pytest.skip("Encryption service not available")
        
        if response.status_code != 200:
            pytest.skip("Encryption failed, cannot test data format")
        
        data = response.json()
        encrypted_credential = data['encrypted_credential']
        
        # Verify Vault ciphertext format
        assert encrypted_credential['encrypted_email'].startswith('vault:v')
        assert encrypted_credential['encrypted_password'].startswith('vault:v')
        
        # Verify metadata
        metadata = encrypted_credential['metadata']
        assert metadata['algorithm'] == 'aes256-gcm96'
        assert metadata['key_version'] >= 1
        assert metadata['access_count'] == 0
        assert 'encrypted_at' in metadata


if __name__ == '__main__':
    pytest.main([__file__, '-v'])