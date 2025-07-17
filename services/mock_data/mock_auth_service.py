#!/usr/bin/env python3
"""
Mock Authentication Service for Grill Stats Application

This service provides a simplified authentication API for testing without requiring
the full auth-service with database and Redis dependencies.
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading

from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mock_auth_service")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mock-secret-key-for-testing'
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# JWT configuration
JWT_SECRET = 'mock-jwt-secret-for-testing'
JWT_ALGORITHM = 'HS256'

# In-memory user store
USERS = {
    "admin@grill-stats.lab.apj.dev": {
        "user_id": "user-001",
        "email": "admin@grill-stats.lab.apj.dev",
        "password": "admin1234",
        "name": "Admin User",
        "is_active": True
    },
    "test@example.com": {
        "user_id": "user-002",
        "email": "test@example.com",
        "password": "password",
        "name": "Test User",
        "is_active": True
    }
}

# In-memory session store
SESSIONS = {}

def generate_jwt_token(user_id, email):
    """Generate JWT token for API authentication"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# API response helpers
def success_response(data=None, message="Success"):
    """Create success response"""
    response = {"status": "success", "message": message}
    if data is not None:
        response["data"] = data
    return response

def error_response(message, status_code=400, details=None):
    """Create error response"""
    response = {"status": "error", "message": message, "status_code": status_code}
    if details is not None:
        response["details"] = details
    return response

# Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'mock-auth-service',
        'version': '1.0.0'
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify(error_response("Email and password are required")), 400
        
        # Check credentials
        user = USERS.get(email)
        if not user or user['password'] != password:
            return jsonify(error_response("Invalid email or password")), 401
        
        if not user['is_active']:
            return jsonify(error_response("Account is deactivated")), 401
        
        # Generate session token
        session_token = f"session-{int(time.time())}-{user['user_id']}"
        SESSIONS[session_token] = {
            'user_id': user['user_id'],
            'email': user['email'],
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        # Generate JWT token
        jwt_token = generate_jwt_token(user['user_id'], user['email'])
        
        response_data = {
            'user': {
                'id': user['user_id'],
                'email': user['email'],
                'name': user['name']
            },
            'token': jwt_token,  # Use 'token' instead of 'jwt_token' for compatibility
            'session_token': session_token,
            'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        
        return jsonify(success_response(response_data, "Login successful"))
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify(error_response("Login failed")), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        # Get session token from headers
        session_token = request.headers.get('Session-Token')
        
        if session_token and session_token in SESSIONS:
            del SESSIONS[session_token]
        
        return jsonify(success_response(message="Logout successful"))
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify(error_response("Logout failed")), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint (simplified for mock)"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', email.split('@')[0])
        
        if not email or not password:
            return jsonify(error_response("Email and password are required")), 400
        
        # Check if user already exists
        if email in USERS:
            return jsonify(error_response("User already exists")), 409
        
        # Create user
        user_id = f"user-{len(USERS) + 1:03d}"
        USERS[email] = {
            "user_id": user_id,
            "email": email,
            "password": password,
            "name": name,
            "is_active": True
        }
        
        return jsonify(success_response({
            'user': {
                'id': user_id,
                'email': email,
                'name': name
            }
        }, "User created successfully"))
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify(error_response("Registration failed")), 500

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Get authentication status"""
    try:
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify(error_response("Invalid authorization header")), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        try:
            # Decode token
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload['user_id']
            email = payload['email']
            
            # Find user
            user = None
            for u in USERS.values():
                if u['user_id'] == user_id:
                    user = u
                    break
            
            if not user:
                return jsonify(error_response("User not found")), 404
            
            return jsonify(success_response({
                'authenticated': True,
                'user': {
                    'id': user['user_id'],
                    'email': user['email'],
                    'name': user['name']
                }
            }))
            
        except jwt.ExpiredSignatureError:
            return jsonify(error_response("Token expired")), 401
        except jwt.InvalidTokenError:
            return jsonify(error_response("Invalid token")), 401
            
    except Exception as e:
        logger.error(f"Auth status error: {e}")
        return jsonify(error_response("Failed to get auth status")), 500

@app.route('/api/auth/sessions', methods=['GET'])
def get_sessions():
    """Get active sessions"""
    try:
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify(error_response("Invalid authorization header")), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        try:
            # Decode token
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload['user_id']
            
            # Get sessions for user
            user_sessions = []
            for session_id, session in SESSIONS.items():
                if session['user_id'] == user_id:
                    user_sessions.append({
                        'session_token': session_id,
                        'expires_at': session['expires_at'].isoformat(),
                        'ip_address': session['ip_address'],
                        'user_agent': session['user_agent']
                    })
            
            return jsonify(success_response({
                'sessions': user_sessions
            }))
            
        except jwt.ExpiredSignatureError:
            return jsonify(error_response("Token expired")), 401
        except jwt.InvalidTokenError:
            return jsonify(error_response("Invalid token")), 401
            
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        return jsonify(error_response("Failed to get sessions")), 500

# Session cleanup thread
def cleanup_expired_sessions():
    """Background task to cleanup expired sessions"""
    while True:
        try:
            now = datetime.utcnow()
            expired_sessions = []
            
            for session_id, session in SESSIONS.items():
                if session['expires_at'] < now:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del SESSIONS[session_id]
                
            time.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

if __name__ == '__main__':
    # Start background cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
    cleanup_thread.start()
    
    # Start Flask app
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8082))
    debug = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 't')
    
    logger.info(f"Starting mock auth service on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)