#!/usr/bin/env python3
"""
Authentication Service API

This module provides a Flask-based API for authentication services, integrating
with ThermoWorks Cloud authentication and session management.
"""

import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import jwt
import psycopg2
import redis
from credential_integration import (
    CredentialIntegrationService,
    DatabaseCredentialManager,
)
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, session, url_for
from flask_cors import CORS
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("auth_service")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Database configuration
DATABASE_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "grill_stats"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# Redis configuration for session storage
try:
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=os.environ.get("REDIS_PASSWORD", None),
        decode_responses=True,
    )
    redis_client.ping()
    logger.info("Connected to Redis")
except redis.RedisError as e:
    logger.warning(f"Failed to connect to Redis: {e}. Using in-memory sessions.")
    redis_client = None

# ThermoWorks API configuration
THERMOWORKS_CONFIG = {
    "client_id": os.environ.get("THERMOWORKS_CLIENT_ID"),
    "client_secret": os.environ.get("THERMOWORKS_CLIENT_SECRET"),
    "base_url": os.environ.get("THERMOWORKS_BASE_URL", "https://api.thermoworks.com"),
    "auth_url": os.environ.get("THERMOWORKS_AUTH_URL", "https://auth.thermoworks.com"),
}

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    "attempts": 5,
    "window": 900,  # 15 minutes
    "lockout_time": 3600,  # 1 hour
}

JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"


class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id, email, name, is_active=True):
        self.id = user_id
        self.email = email
        self.name = name
        self.is_active = is_active

    def get_id(self):
        return str(self.id)


class DatabaseManager:
    """Database connection and user management"""

    def __init__(self, config):
        self.config = config
        self._connection = None
        self._init_database()

    def _get_connection(self):
        """Get database connection"""
        if not self._connection or self._connection.closed:
            self._connection = psycopg2.connect(**self.config)
        return self._connection

    def _init_database(self):
        """Initialize database tables"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP,
                    thermoworks_user_id VARCHAR(255),
                    thermoworks_access_token TEXT,
                    thermoworks_refresh_token TEXT,
                    thermoworks_token_expires TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45),
                    user_agent TEXT
                )
            """
            )

            # Create login attempts table for rate limiting
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255),
                    ip_address VARCHAR(45),
                    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT FALSE
                )
            """
            )

            conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()

            if user_data:
                return User(
                    user_id=user_data["id"],
                    email=user_data["email"],
                    name=user_data["name"],
                    is_active=user_data["is_active"],
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

    def get_user_by_email(self, email):
        """Get user by email"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    def create_user(self, email, password, name=None):
        """Create a new user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO users (email, password_hash, name)
                VALUES (%s, %s, %s)
                RETURNING id
            """,
                (email, password_hash, name),
            )

            user_id = cursor.fetchone()[0]
            conn.commit()

            return self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def verify_password(self, email, password):
        """Verify user password"""
        user_data = self.get_user_by_email(email)
        if user_data and check_password_hash(user_data["password_hash"], password):
            return User(
                user_id=user_data["id"],
                email=user_data["email"],
                name=user_data["name"],
                is_active=user_data["is_active"],
            )
        return None

    def update_thermoworks_tokens(
        self, user_id, access_token, refresh_token=None, expires_at=None
    ):
        """Update ThermoWorks tokens for user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE users
                SET thermoworks_access_token = %s,
                    thermoworks_refresh_token = %s,
                    thermoworks_token_expires = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (access_token, refresh_token, expires_at, user_id),
            )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating ThermoWorks tokens: {e}")
            return False

    def record_login_attempt(self, email, ip_address, success=False):
        """Record login attempt"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO login_attempts (email, ip_address, success)
                VALUES (%s, %s, %s)
            """,
                (email, ip_address, success),
            )

            conn.commit()
        except Exception as e:
            logger.error(f"Error recording login attempt: {e}")

    def get_recent_login_attempts(self, email, ip_address, minutes=15):
        """Get recent login attempts for rate limiting"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*) as attempt_count
                FROM login_attempts
                WHERE (email = %s OR ip_address = %s)
                AND attempt_time > NOW() - INTERVAL '%s minutes'
                AND success = FALSE
            """,
                (email, ip_address, minutes),
            )

            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting recent login attempts: {e}")
            return 0

    def create_session(self, user_id, ip_address, user_agent):
        """Create a new session"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=24)

            cursor.execute(
                """
                INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (user_id, session_token, expires_at, ip_address, user_agent),
            )

            conn.commit()
            return session_token
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    def get_session(self, session_token):
        """Get session by token"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT s.*, u.email, u.name, u.is_active
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = %s
                AND s.expires_at > NOW()
            """,
                (session_token,),
            )

            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None

    def delete_session(self, session_token):
        """Delete session"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM user_sessions WHERE session_token = %s", (session_token,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
            conn.commit()
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")


# Initialize database manager
db_manager = DatabaseManager(DATABASE_CONFIG)

# Initialize credential integration service
try:
    credential_service = CredentialIntegrationService()
    credential_manager = DatabaseCredentialManager(
        db_manager._get_connection(), credential_service
    )
    logger.info("Credential integration service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize credential integration service: {e}")
    credential_service = None
    credential_manager = None


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return db_manager.get_user_by_id(user_id)


def generate_jwt_token(user_id, email):
    """Generate JWT token for API authentication"""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def jwt_required(f):
    """Decorator for JWT authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "No token provided"}), 401

        if token.startswith("Bearer "):
            token = token[7:]

        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        request.current_user = payload
        return f(*args, **kwargs)

    return decorated_function


def check_rate_limit(email, ip_address):
    """Check if user/IP is rate limited"""
    attempts = db_manager.get_recent_login_attempts(email, ip_address)
    return attempts < RATE_LIMIT_CONFIG["attempts"]


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
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "auth-service",
            "version": "1.0.0",
        }
    )


@app.route("/api/auth/login", methods=["POST"])
def login():
    """User login endpoint - supports both local and ThermoWorks authentication"""
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
        login_type = data.get("login_type", "local")  # 'local' or 'thermoworks'

        if not email or not password:
            return jsonify(error_response("Email and password are required")), 400

        # Get client IP
        ip_address = request.remote_addr

        # Check rate limiting
        if not check_rate_limit(email, ip_address):
            db_manager.record_login_attempt(email, ip_address, success=False)
            return (
                jsonify(
                    error_response("Too many failed attempts. Please try again later.")
                ),
                429,
            )

        user = None
        thermoworks_tokens = None

        if login_type == "thermoworks":
            # Authenticate with ThermoWorks
            auth_response = authenticate_thermoworks_user(email, password)

            if auth_response and auth_response.get("access_token"):
                # Check if user exists, if not create one
                user_data = db_manager.get_user_by_email(email)
                if not user_data:
                    # Create new user with ThermoWorks credentials
                    user = db_manager.create_user(email, password, email.split("@")[0])
                else:
                    user = User(
                        user_id=user_data["id"],
                        email=user_data["email"],
                        name=user_data["name"],
                        is_active=user_data["is_active"],
                    )

                # Store ThermoWorks tokens
                thermoworks_tokens = auth_response
                db_manager.update_thermoworks_tokens(
                    user.id,
                    auth_response["access_token"],
                    auth_response.get("refresh_token"),
                    datetime.utcnow()
                    + timedelta(seconds=auth_response.get("expires_in", 3600)),
                )
            else:
                db_manager.record_login_attempt(email, ip_address, success=False)
                return jsonify(error_response("Invalid ThermoWorks credentials")), 401
        else:
            # Local authentication
            user = db_manager.verify_password(email, password)
            if not user:
                db_manager.record_login_attempt(email, ip_address, success=False)
                return jsonify(error_response("Invalid email or password")), 401

        if not user.is_active:
            return jsonify(error_response("Account is deactivated")), 401

        # Create session
        session_token = db_manager.create_session(
            user.id, ip_address, request.headers.get("User-Agent", "")
        )

        if not session_token:
            return jsonify(error_response("Failed to create session")), 500

        # Generate JWT token
        jwt_token = generate_jwt_token(user.id, user.email)

        # Record successful login
        db_manager.record_login_attempt(email, ip_address, success=True)

        # Login user for Flask-Login
        login_user(user)

        response_data = {
            "user": {"id": user.id, "email": user.email, "name": user.name},
            "session_token": session_token,
            "jwt_token": jwt_token,
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "login_type": login_type,
        }

        if thermoworks_tokens:
            response_data["thermoworks_connected"] = True

        return jsonify(success_response(response_data, "Login successful"))

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify(error_response("Login failed")), 500


@app.route("/api/auth/logout", methods=["POST"])
@jwt_required
def logout():
    """User logout endpoint"""
    try:
        # Get session token from headers
        session_token = request.headers.get("Session-Token")

        if session_token:
            db_manager.delete_session(session_token)

        logout_user()

        return jsonify(success_response(message="Logout successful"))

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify(error_response("Logout failed")), 500


@app.route("/api/auth/register", methods=["POST"])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
        name = data.get("name")

        if not email or not password:
            return jsonify(error_response("Email and password are required")), 400

        # Check if user already exists
        if db_manager.get_user_by_email(email):
            return jsonify(error_response("User already exists")), 409

        # Create user
        user = db_manager.create_user(email, password, name)
        if not user:
            return jsonify(error_response("Failed to create user")), 500

        return jsonify(
            success_response(
                {"user": {"id": user.id, "email": user.email, "name": user.name}},
                "User created successfully",
            )
        )

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify(error_response("Registration failed")), 500


@app.route("/api/auth/status", methods=["GET"])
@jwt_required
def auth_status():
    """Get authentication status"""
    try:
        user_id = request.current_user["user_id"]
        user = db_manager.get_user_by_id(user_id)

        if not user:
            return jsonify(error_response("User not found")), 404

        return jsonify(
            success_response(
                {
                    "authenticated": True,
                    "user": {"id": user.id, "email": user.email, "name": user.name},
                }
            )
        )

    except Exception as e:
        logger.error(f"Auth status error: {e}")
        return jsonify(error_response("Failed to get auth status")), 500


@app.route("/api/auth/me", methods=["GET"])
@jwt_required
def get_current_user():
    """Get current user information"""
    try:
        user_id = request.current_user["user_id"]
        user = db_manager.get_user_by_id(user_id)

        if not user:
            return jsonify(error_response("User not found")), 404

        return jsonify(
            success_response(
                {"user": {"id": user.id, "email": user.email, "name": user.name}}
            )
        )

    except Exception as e:
        logger.error(f"Get current user error: {e}")
        return jsonify(error_response("Failed to get user information")), 500


@app.route("/api/auth/thermoworks/connect", methods=["POST"])
@jwt_required
def connect_thermoworks():
    """Connect user account to ThermoWorks with encrypted credential storage"""
    try:
        data = request.get_json()
        thermoworks_email = data.get("thermoworks_email")
        thermoworks_password = data.get("thermoworks_password")

        if not thermoworks_email or not thermoworks_password:
            return jsonify(error_response("ThermoWorks credentials are required")), 400

        if not credential_manager:
            return (
                jsonify(error_response("Credential encryption service unavailable")),
                503,
            )

        user_id = request.current_user["user_id"]

        # Check rate limit for encryption operations
        try:
            rate_limit_info = credential_service.check_rate_limit(user_id)
            if not rate_limit_info.get("is_allowed", False):
                return (
                    jsonify(
                        error_response(
                            "Rate limit exceeded. Please try again later.",
                            details=f"Remaining requests: {rate_limit_info.get('remaining_requests', 0)}",
                        )
                    ),
                    429,
                )
        except Exception as e:
            logger.warning(f"Rate limit check failed for user {user_id}: {e}")
            # Continue with the operation if rate limit check fails

        # Import ThermoWorks client for authentication
        from thermoworks_client import ThermoworksAuthenticationError, ThermoworksClient

        try:
            # First, validate credentials with ThermoWorks API
            auth_response = authenticate_thermoworks_user(
                thermoworks_email, thermoworks_password
            )

            if auth_response and auth_response.get("access_token"):
                # Store encrypted credentials after successful validation
                success = credential_manager.store_encrypted_credentials(
                    user_id, thermoworks_email, thermoworks_password
                )

                if not success:
                    return (
                        jsonify(
                            error_response("Failed to store encrypted credentials")
                        ),
                        500,
                    )

                # Store OAuth tokens in database (these are not sensitive like passwords)
                db_manager.update_thermoworks_tokens(
                    user_id,
                    auth_response["access_token"],
                    auth_response.get("refresh_token"),
                    datetime.utcnow()
                    + timedelta(seconds=auth_response.get("expires_in", 3600)),
                )

                # Mark credentials as validated
                credential_manager.validate_credentials(user_id)

                return jsonify(
                    success_response(
                        {
                            "connected": True,
                            "thermoworks_email": thermoworks_email,
                            "encrypted": True,
                        },
                        "ThermoWorks account connected and credentials encrypted successfully",
                    )
                )
            else:
                # Increment failed attempts
                if credential_manager:
                    credential_manager.increment_validation_attempts(user_id)
                return jsonify(error_response("Invalid ThermoWorks credentials")), 401

        except ThermoworksAuthenticationError as e:
            logger.error(f"ThermoWorks authentication error: {e}")
            if credential_manager:
                credential_manager.increment_validation_attempts(user_id)
            return jsonify(error_response("Invalid ThermoWorks credentials")), 401
        except Exception as e:
            logger.error(f"ThermoWorks connection error: {e}")
            return jsonify(error_response("Failed to connect to ThermoWorks")), 500

    except Exception as e:
        logger.error(f"ThermoWorks connect error: {e}")
        return jsonify(error_response("Failed to connect ThermoWorks account")), 500


def authenticate_thermoworks_user(email, password):
    """
    Authenticate ThermoWorks user using their credentials
    Note: This is a placeholder. Real implementation would use OAuth2 ROPC flow
    """
    # In a real implementation, this would make an API call to ThermoWorks
    # to authenticate the user and get tokens
    # For now, return a mock response
    return {
        "access_token": f"tw_access_{hashlib.sha256(email.encode()).hexdigest()[:16]}",
        "refresh_token": f"tw_refresh_{secrets.token_urlsafe(16)}",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@app.route("/api/auth/sessions", methods=["GET"])
@jwt_required
def get_user_sessions():
    """Get user's active sessions"""
    try:
        user_id = request.current_user["user_id"]

        conn = db_manager._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT session_token, expires_at, created_at, last_activity, ip_address
            FROM user_sessions
            WHERE user_id = %s AND expires_at > NOW()
            ORDER BY last_activity DESC
        """,
            (user_id,),
        )

        sessions = cursor.fetchall()

        return jsonify(
            success_response({"sessions": [dict(session) for session in sessions]})
        )

    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        return jsonify(error_response("Failed to get sessions")), 500


@app.route("/api/auth/thermoworks/credentials", methods=["GET"])
@jwt_required
def get_thermoworks_credentials():
    """Get decrypted ThermoWorks credentials for API calls"""
    try:
        if not credential_manager:
            return (
                jsonify(error_response("Credential encryption service unavailable")),
                503,
            )

        user_id = request.current_user["user_id"]

        # Check rate limit for decryption operations
        try:
            rate_limit_info = credential_service.check_rate_limit(user_id)
            if not rate_limit_info.get("is_allowed", False):
                return (
                    jsonify(
                        error_response(
                            "Rate limit exceeded. Please try again later.",
                            details=f"Remaining requests: {rate_limit_info.get('remaining_requests', 0)}",
                        )
                    ),
                    429,
                )
        except Exception as e:
            logger.warning(f"Rate limit check failed for user {user_id}: {e}")
            # Continue with the operation if rate limit check fails

        # Get decrypted credentials
        email, password = credential_manager.get_decrypted_credentials(user_id)

        if not email or not password:
            return (
                jsonify(error_response("No ThermoWorks credentials found for user")),
                404,
            )

        return jsonify(
            success_response(
                {"email": email, "password": password},
                "Credentials retrieved successfully",
            )
        )

    except Exception as e:
        logger.error(f"Get ThermoWorks credentials error: {e}")
        return jsonify(error_response("Failed to get ThermoWorks credentials")), 500


@app.route("/api/auth/thermoworks/status", methods=["GET"])
@jwt_required
def get_thermoworks_status():
    """Get ThermoWorks credential status"""
    try:
        user_id = request.current_user["user_id"]

        conn = db_manager._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                is_active,
                last_validated,
                validation_attempts,
                created_at,
                updated_at,
                encryption_metadata
            FROM thermoworks_credentials
            WHERE user_id = %s
        """,
            (user_id,),
        )

        result = cursor.fetchone()

        if not result:
            return jsonify(success_response({"connected": False, "encrypted": False}))

        credential_info = dict(result)

        return jsonify(
            success_response(
                {
                    "connected": True,
                    "encrypted": True,
                    "is_active": credential_info["is_active"],
                    "last_validated": (
                        credential_info["last_validated"].isoformat()
                        if credential_info["last_validated"]
                        else None
                    ),
                    "validation_attempts": credential_info["validation_attempts"],
                    "created_at": credential_info["created_at"].isoformat(),
                    "updated_at": credential_info["updated_at"].isoformat(),
                    "encryption_info": {
                        "algorithm": credential_info["encryption_metadata"].get(
                            "algorithm"
                        ),
                        "key_version": credential_info["encryption_metadata"].get(
                            "key_version"
                        ),
                        "encrypted_at": credential_info["encryption_metadata"].get(
                            "encrypted_at"
                        ),
                        "access_count": credential_info["encryption_metadata"].get(
                            "access_count", 0
                        ),
                    },
                }
            )
        )

    except Exception as e:
        logger.error(f"Get ThermoWorks status error: {e}")
        return jsonify(error_response("Failed to get ThermoWorks status")), 500


@app.route("/api/auth/thermoworks/disconnect", methods=["POST"])
@jwt_required
def disconnect_thermoworks():
    """Disconnect ThermoWorks account and delete encrypted credentials"""
    try:
        if not credential_manager:
            return (
                jsonify(error_response("Credential encryption service unavailable")),
                503,
            )

        user_id = request.current_user["user_id"]

        # Delete encrypted credentials
        success = credential_manager.delete_credentials(user_id)

        if not success:
            return (
                jsonify(error_response("Failed to delete encrypted credentials")),
                500,
            )

        # Clear OAuth tokens from users table
        db_manager.update_thermoworks_tokens(user_id, None, None, None)

        return jsonify(
            success_response(
                message="ThermoWorks account disconnected and credentials deleted successfully"
            )
        )

    except Exception as e:
        logger.error(f"Disconnect ThermoWorks error: {e}")
        return jsonify(error_response("Failed to disconnect ThermoWorks account")), 500


@app.route("/api/auth/thermoworks/rate-limit", methods=["GET"])
@jwt_required
def get_thermoworks_rate_limit():
    """Get current rate limit status for ThermoWorks operations"""
    try:
        if not credential_service:
            return (
                jsonify(error_response("Credential encryption service unavailable")),
                503,
            )

        user_id = request.current_user["user_id"]

        # Get rate limit information
        rate_limit_info = credential_service.check_rate_limit(user_id)

        return jsonify(
            success_response({"rate_limit": rate_limit_info, "user_id": user_id})
        )

    except Exception as e:
        logger.error(f"Get rate limit error: {e}")
        return jsonify(error_response("Failed to get rate limit information")), 500


# Error handlers
@app.errorhandler(400)
def bad_request(error):
    return jsonify(error_response("Bad Request", 400)), 400


@app.errorhandler(401)
def unauthorized(error):
    return jsonify(error_response("Unauthorized", 401)), 401


@app.errorhandler(403)
def forbidden(error):
    return jsonify(error_response("Forbidden", 403)), 403


@app.errorhandler(404)
def not_found(error):
    return jsonify(error_response("Not Found", 404)), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify(error_response("Internal Server Error", 500)), 500


# Background task to clean up expired sessions
import threading
import time


def cleanup_expired_sessions():
    """Background task to cleanup expired sessions"""
    while True:
        try:
            db_manager.cleanup_expired_sessions()
            time.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
            time.sleep(60)  # Wait 1 minute before retrying


# Start background cleanup task
cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8082))
    debug = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

    app.run(host=host, port=port, debug=debug)
