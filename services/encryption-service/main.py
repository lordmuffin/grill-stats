"""
Encryption Service Main Entry Point

This service provides a REST API for encrypting and decrypting ThermoWorks credentials
using HashiCorp Vault Transit secrets engine.
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_healthz import healthz
from src.credential_encryption_service import CredentialEncryptionService, EncryptedCredential, PlainCredential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Add health check endpoint
app.register_blueprint(healthz, url_prefix="/healthz")

# Initialize encryption service
try:
    encryption_service = CredentialEncryptionService()
    logger.info("Encryption service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize encryption service: {e}")
    encryption_service = None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    if not encryption_service:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Encryption service not initialized',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    try:
        health_status = encryption_service.health_check()
        if health_status['status'] == 'healthy':
            return jsonify(health_status), 200
        else:
            return jsonify(health_status), 503
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/encrypt', methods=['POST'])
def encrypt_credentials():
    """Encrypt ThermoWorks credentials"""
    if not encryption_service:
        return jsonify({
            'error': 'Encryption service not available'
        }), 503
    
    try:
        # Validate request
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data or 'user_id' not in data:
            return jsonify({
                'error': 'Missing required fields: email, password, user_id'
            }), 400
        
        # Encrypt credentials
        encrypted_credential = encryption_service.encrypt_credentials(
            email=data['email'],
            password=data['password'],
            user_id=data['user_id']
        )
        
        # Return encrypted data (without sensitive information)
        return jsonify({
            'status': 'success',
            'encrypted_credential': encrypted_credential.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to encrypt credentials: {e}")
        return jsonify({
            'error': 'Failed to encrypt credentials',
            'details': str(e)
        }), 500


@app.route('/decrypt', methods=['POST'])
def decrypt_credentials():
    """Decrypt ThermoWorks credentials"""
    if not encryption_service:
        return jsonify({
            'error': 'Encryption service not available'
        }), 503
    
    try:
        # Validate request
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data or 'encrypted_credential' not in data or 'user_id' not in data:
            return jsonify({
                'error': 'Missing required fields: encrypted_credential, user_id'
            }), 400
        
        # Parse encrypted credential
        encrypted_credential = EncryptedCredential.from_dict(data['encrypted_credential'])
        
        # Decrypt credentials
        plain_credential = encryption_service.decrypt_credentials(
            encrypted_credential=encrypted_credential,
            user_id=data['user_id']
        )
        
        # Return decrypted data
        response_data = {
            'status': 'success',
            'credentials': {
                'email': plain_credential.email,
                'password': plain_credential.password
            },
            'metadata': {
                'last_accessed': encrypted_credential.metadata.last_accessed,
                'access_count': encrypted_credential.metadata.access_count
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Clean up sensitive data from memory
        del plain_credential
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {e}")
        return jsonify({
            'error': 'Failed to decrypt credentials',
            'details': str(e)
        }), 500


@app.route('/rotate-key', methods=['POST'])
def rotate_key():
    """Rotate the encryption key"""
    if not encryption_service:
        return jsonify({
            'error': 'Encryption service not available'
        }), 503
    
    try:
        # Validate request - require admin authorization
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Missing or invalid authorization header'
            }), 401
        
        # In a real implementation, validate the token
        # For now, we'll just check if it's present
        
        # Rotate the key
        rotation_info = encryption_service.rotate_key()
        
        return jsonify({
            'status': 'success',
            'rotation_info': rotation_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to rotate key: {e}")
        return jsonify({
            'error': 'Failed to rotate key',
            'details': str(e)
        }), 500


@app.route('/key-info', methods=['GET'])
def get_key_info():
    """Get information about the encryption key"""
    if not encryption_service:
        return jsonify({
            'error': 'Encryption service not available'
        }), 503
    
    try:
        key_info = encryption_service.get_key_info()
        
        return jsonify({
            'status': 'success',
            'key_info': key_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get key info: {e}")
        return jsonify({
            'error': 'Failed to get key info',
            'details': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'timestamp': datetime.utcnow().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.utcnow().isoformat()
    }), 500


@app.route('/rate-limit/<user_id>', methods=['GET'])
def check_rate_limit(user_id):
    """Check rate limit status for a user"""
    if not encryption_service:
        return jsonify({
            'error': 'Encryption service not available'
        }), 503
    
    try:
        rate_limit_info = encryption_service.check_rate_limit(user_id)
        
        return jsonify({
            'status': 'success',
            'rate_limit': rate_limit_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to check rate limit: {e}")
        return jsonify({
            'error': 'Failed to check rate limit',
            'details': str(e)
        }), 500


if __name__ == '__main__':
    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8082))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting encryption service on {host}:{port}")
    
    # Run the application
    app.run(host=host, port=port, debug=debug)