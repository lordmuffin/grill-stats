"""
JWT Authentication Middleware for Grill Stats API Gateway
Provides comprehensive JWT token validation, role-based access control, and security features
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

import jwt
import redis
from flask import current_app, g, jsonify, request
from werkzeug.exceptions import Unauthorized

logger = logging.getLogger(__name__)


class JWTConfig:
    """JWT Configuration with security best practices"""

    # Algorithm and Security
    ALGORITHM = "HS256"
    SECRET_KEY = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-in-production")

    # Token Expiration
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", "30"))

    # Security Settings
    REQUIRE_HTTPS = os.environ.get("JWT_REQUIRE_HTTPS", "true").lower() == "true"
    AUDIENCE = os.environ.get("JWT_AUDIENCE", "grill-stats-api")
    ISSUER = os.environ.get("JWT_ISSUER", "grill-stats-auth")

    # Rate Limiting
    MAX_TOKENS_PER_USER = int(os.environ.get("JWT_MAX_TOKENS_PER_USER", "5"))
    TOKEN_CLEANUP_INTERVAL = int(os.environ.get("JWT_CLEANUP_INTERVAL", "3600"))  # 1 hour


class TokenBlacklist:
    """Redis-based token blacklist for logout and security"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._get_redis_client()
        self.blacklist_prefix = "jwt:blacklist:"
        self.user_tokens_prefix = "jwt:user_tokens:"

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with fallback"""
        try:
            return redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD"),
                db=int(os.environ.get("JWT_REDIS_DB", "1")),
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None

    def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.get(f"{self.blacklist_prefix}{jti}"))
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            return False

    def blacklist_token(self, jti: str, exp: int, user_id: str, reason: str = "logout") -> bool:
        """Add token to blacklist"""
        if not self.redis_client:
            return False

        try:
            # Calculate TTL based on token expiration
            ttl = max(exp - int(time.time()), 0)
            if ttl <= 0:
                return True  # Token already expired

            # Store blacklist entry with metadata
            blacklist_data = {"user_id": user_id, "blacklisted_at": int(time.time()), "reason": reason}

            self.redis_client.setex(f"{self.blacklist_prefix}{jti}", ttl, json.dumps(blacklist_data))

            # Remove from user's active tokens
            self.redis_client.srem(f"{self.user_tokens_prefix}{user_id}", jti)

            logger.info(f"Token {jti} blacklisted for user {user_id}, reason: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False

    def track_user_token(self, user_id: str, jti: str, exp: int) -> None:
        """Track active tokens for a user"""
        if not self.redis_client:
            return

        try:
            # Add to user's active tokens
            self.redis_client.sadd(f"{self.user_tokens_prefix}{user_id}", jti)

            # Set expiration on the set
            ttl = max(exp - int(time.time()), 0)
            if ttl > 0:
                self.redis_client.expire(f"{self.user_tokens_prefix}{user_id}", ttl)

            # Enforce token limit per user
            self._enforce_token_limit(user_id)

        except Exception as e:
            logger.error(f"Error tracking user token: {e}")

    def _enforce_token_limit(self, user_id: str) -> None:
        """Enforce maximum tokens per user"""
        try:
            active_tokens = self.redis_client.smembers(f"{self.user_tokens_prefix}{user_id}")

            if len(active_tokens) > JWTConfig.MAX_TOKENS_PER_USER:
                # Remove oldest tokens (this is basic, could be improved with timestamps)
                excess_count = len(active_tokens) - JWTConfig.MAX_TOKENS_PER_USER
                oldest_tokens = list(active_tokens)[:excess_count]

                for token_jti in oldest_tokens:
                    # Blacklist the excess token
                    self.blacklist_token(token_jti, int(time.time()) + 3600, user_id, "token_limit_exceeded")  # 1 hour TTL

                logger.info(f"Removed {excess_count} excess tokens for user {user_id}")

        except Exception as e:
            logger.error(f"Error enforcing token limit: {e}")

    def revoke_all_user_tokens(self, user_id: str, reason: str = "security") -> int:
        """Revoke all tokens for a user"""
        if not self.redis_client:
            return 0

        try:
            active_tokens = self.redis_client.smembers(f"{self.user_tokens_prefix}{user_id}")
            count = 0

            for jti in active_tokens:
                if self.blacklist_token(jti, int(time.time()) + 3600, user_id, reason):
                    count += 1

            # Clear user's token set
            self.redis_client.delete(f"{self.user_tokens_prefix}{user_id}")

            logger.info(f"Revoked {count} tokens for user {user_id}, reason: {reason}")
            return count

        except Exception as e:
            logger.error(f"Error revoking user tokens: {e}")
            return 0


class JWTManager:
    """Comprehensive JWT token management"""

    def __init__(self, app=None):
        self.blacklist = TokenBlacklist()
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app"""
        app.config.setdefault("JWT_SECRET_KEY", JWTConfig.SECRET_KEY)
        app.config.setdefault("JWT_ALGORITHM", JWTConfig.ALGORITHM)
        app.extensions["jwt_manager"] = self

    def generate_tokens(self, user_data: Dict[str, Any]) -> Tuple[str, str]:
        """Generate access and refresh token pair"""
        user_id = str(user_data.get("id"))
        email = user_data.get("email")
        roles = user_data.get("roles", ["user"])

        now = datetime.now(timezone.utc)

        # Access Token
        access_jti = f"acc_{user_id}_{int(time.time() * 1000)}"
        access_exp = now + timedelta(minutes=JWTConfig.ACCESS_TOKEN_EXPIRE_MINUTES)

        access_payload = {
            "user_id": user_id,
            "email": email,
            "roles": roles,
            "type": "access",
            "jti": access_jti,
            "iat": now,
            "exp": access_exp,
            "aud": JWTConfig.AUDIENCE,
            "iss": JWTConfig.ISSUER,
            "sub": user_id,
        }

        # Refresh Token
        refresh_jti = f"ref_{user_id}_{int(time.time() * 1000)}"
        refresh_exp = now + timedelta(days=JWTConfig.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_payload = {
            "user_id": user_id,
            "email": email,
            "type": "refresh",
            "jti": refresh_jti,
            "iat": now,
            "exp": refresh_exp,
            "aud": JWTConfig.AUDIENCE,
            "iss": JWTConfig.ISSUER,
            "sub": user_id,
        }

        try:
            access_token = jwt.encode(access_payload, JWTConfig.SECRET_KEY, algorithm=JWTConfig.ALGORITHM)
            refresh_token = jwt.encode(refresh_payload, JWTConfig.SECRET_KEY, algorithm=JWTConfig.ALGORITHM)

            # Track tokens
            self.blacklist.track_user_token(user_id, access_jti, int(access_exp.timestamp()))
            self.blacklist.track_user_token(user_id, refresh_jti, int(refresh_exp.timestamp()))

            logger.info(f"Generated token pair for user {user_id}")
            return access_token, refresh_token

        except Exception as e:
            logger.error(f"Error generating tokens: {e}")
            raise

    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            # Decode token
            payload = jwt.decode(
                token,
                JWTConfig.SECRET_KEY,
                algorithms=[JWTConfig.ALGORITHM],
                audience=JWTConfig.AUDIENCE,
                issuer=JWTConfig.ISSUER,
                options={
                    "require_exp": True,
                    "require_iat": True,
                    "require_sub": True,
                    "require_jti": True,
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError(f"Expected {token_type} token")

            # Check blacklist
            jti = payload.get("jti")
            if self.blacklist.is_blacklisted(jti):
                raise jwt.InvalidTokenError("Token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise jwt.InvalidTokenError("Token verification failed")

    def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token"""
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, "refresh")

            user_data = {"id": payload["user_id"], "email": payload["email"], "roles": payload.get("roles", ["user"])}

            # Generate new access token
            access_token, _ = self.generate_tokens(user_data)
            return access_token

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise

    def revoke_token(self, token: str, reason: str = "logout") -> bool:
        """Revoke a specific token"""
        try:
            payload = jwt.decode(
                token,
                JWTConfig.SECRET_KEY,
                algorithms=[JWTConfig.ALGORITHM],
                options={"verify_exp": False},  # Allow expired tokens for revocation
            )

            jti = payload.get("jti")
            user_id = payload.get("user_id")
            exp = payload.get("exp")

            return self.blacklist.blacklist_token(jti, exp, user_id, reason)

        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            return False


# Global JWT manager instance
jwt_manager = JWTManager()


def jwt_required(roles: Optional[List[str]] = None, optional: bool = False):
    """
    JWT authentication decorator with role-based access control

    Args:
        roles: List of required roles (any role matches)
        optional: If True, missing token won't raise error
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None

            # Extract token from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

            # Check for token in cookies as fallback
            if not token:
                token = request.cookies.get("access_token")

            if not token:
                if optional:
                    g.current_user = None
                    return f(*args, **kwargs)
                return jsonify({"error": "Authentication required", "message": "Missing or invalid authentication token"}), 401

            try:
                # Verify token
                payload = jwt_manager.verify_token(token)

                # Set current user in Flask g
                g.current_user = {
                    "id": payload["user_id"],
                    "email": payload["email"],
                    "roles": payload.get("roles", ["user"]),
                    "jti": payload["jti"],
                }

                # Check role requirements
                if roles:
                    user_roles = set(payload.get("roles", []))
                    required_roles = set(roles)

                    if not user_roles.intersection(required_roles):
                        return jsonify({"error": "Access denied", "message": f"Required roles: {', '.join(roles)}"}), 403

                # Log successful authentication
                logger.info(f"Authenticated user {payload['user_id']} for endpoint {request.endpoint}")

                return f(*args, **kwargs)

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired", "message": "Authentication token has expired"}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({"error": "Invalid token", "message": str(e)}), 401
            except Exception as e:
                logger.error(f"Authentication error: {e}")
                return jsonify({"error": "Authentication failed", "message": "An error occurred during authentication"}), 500

        return decorated_function

    return decorator


def api_key_required(f):
    """API key authentication decorator for service-to-service communication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return jsonify({"error": "API key required", "message": "Missing X-API-Key header"}), 401

        # Validate API key (implement your key validation logic)
        valid_keys = os.environ.get("VALID_API_KEYS", "").split(",")

        if api_key not in valid_keys:
            return jsonify({"error": "Invalid API key", "message": "The provided API key is not valid"}), 401

        return f(*args, **kwargs)

    return decorated_function


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current authenticated user from Flask g"""
    return getattr(g, "current_user", None)


def require_https(f):
    """Decorator to enforce HTTPS in production"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if JWTConfig.REQUIRE_HTTPS and not request.is_secure:
            return jsonify({"error": "HTTPS required", "message": "This endpoint requires a secure connection"}), 400
        return f(*args, **kwargs)

    return decorated_function
