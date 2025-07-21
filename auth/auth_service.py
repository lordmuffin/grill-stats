"""
Authentication Service for API Gateway
Provides JWT token verification endpoint for Traefik ForwardAuth
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import BadRequest

from .jwt_middleware import jwt_manager

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for API Gateway integration"""

    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize authentication service with Flask app"""
        app.register_blueprint(self.create_auth_blueprint())
        logger.info("Authentication service initialized")

    def create_auth_blueprint(self):
        """Create authentication blueprint for API Gateway"""
        from flask import Blueprint

        auth_bp = Blueprint("auth_gateway", __name__, url_prefix="/api/auth")

        @auth_bp.route("/verify", methods=["GET", "POST"])
        def verify_token():
            """
            Token verification endpoint for Traefik ForwardAuth
            Validates JWT tokens and returns user information in headers
            """
            try:
                # Extract token from multiple possible sources
                token = self._extract_token()

                if not token:
                    logger.warning(f"No token provided for {request.remote_addr}")
                    return self._auth_failed("Missing authentication token")

                # Verify the token
                try:
                    payload = jwt_manager.verify_token(token)
                    user_info = self._extract_user_info(payload)

                    # Log successful verification
                    logger.info(f"Token verified for user {user_info['user_id']} from {request.remote_addr}")

                    # Return success with user headers
                    return self._auth_success(user_info)

                except Exception as e:
                    logger.warning(f"Token verification failed: {e}")
                    return self._auth_failed(f"Invalid token: {str(e)}")

            except Exception as e:
                logger.error(f"Auth verification error: {e}")
                return self._auth_failed("Authentication service error")

        @auth_bp.route("/health", methods=["GET"])
        def health_check():
            """Health check endpoint"""
            return jsonify({"status": "healthy", "service": "auth-gateway", "timestamp": datetime.utcnow().isoformat()}), 200

        @auth_bp.route("/logout", methods=["POST"])
        def logout():
            """Logout endpoint - revokes the current token"""
            try:
                token = self._extract_token()

                if not token:
                    return jsonify({"message": "No token to revoke"}), 200

                # Revoke the token
                success = jwt_manager.revoke_token(token, "logout")

                if success:
                    return jsonify({"message": "Successfully logged out"}), 200
                else:
                    return jsonify({"message": "Logout completed (token may already be expired)"}), 200

            except Exception as e:
                logger.error(f"Logout error: {e}")
                return jsonify({"error": "Logout failed"}), 500

        @auth_bp.route("/revoke-all", methods=["POST"])
        def revoke_all_tokens():
            """Revoke all tokens for the current user"""
            try:
                token = self._extract_token()

                if not token:
                    return self._auth_failed("Authentication required")

                payload = jwt_manager.verify_token(token)
                user_id = payload["user_id"]

                # Revoke all user tokens
                count = jwt_manager.blacklist.revoke_all_user_tokens(user_id, "revoke_all")

                return jsonify({"message": f"Revoked {count} tokens", "user_id": user_id}), 200

            except Exception as e:
                logger.error(f"Token revocation error: {e}")
                return jsonify({"error": "Token revocation failed"}), 500

        return auth_bp

    def _extract_token(self) -> Optional[str]:
        """Extract JWT token from request"""
        # Priority: Authorization header > Cookie > Query param (for WebSocket)

        # 1. Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        # 2. Cookie
        token = request.cookies.get("access_token")
        if token:
            return token

        # 3. Query parameter (for WebSocket connections)
        token = request.args.get("token")
        if token:
            return token

        # 4. X-Auth-Token header (alternative)
        token = request.headers.get("X-Auth-Token")
        if token:
            return token

        return None

    def _extract_user_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user information from JWT payload"""
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "roles": payload.get("roles", ["user"]),
            "jti": payload.get("jti"),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
        }

    def _auth_success(self, user_info: Dict[str, Any]) -> tuple:
        """Return successful authentication response with user headers"""
        response = jsonify(
            {
                "status": "authenticated",
                "user_id": user_info["user_id"],
                "email": user_info["email"],
                "roles": user_info["roles"],
            }
        )

        # Set headers for Traefik to forward to backend services
        response.headers["X-User-ID"] = str(user_info["user_id"])
        response.headers["X-User-Email"] = user_info["email"]
        response.headers["X-User-Roles"] = ",".join(user_info["roles"])
        response.headers["X-Auth-Status"] = "authenticated"
        response.headers["X-Token-JTI"] = user_info["jti"]

        return response, 200

    def _auth_failed(self, message: str) -> tuple:
        """Return authentication failure response"""
        return jsonify({"status": "unauthorized", "message": message}), 401


def create_auth_app() -> Flask:
    """Create standalone authentication service app"""
    app = Flask(__name__)

    # Configuration
    app.config.update(
        {
            "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-secret-key"),
            "JWT_SECRET_KEY": os.environ.get("JWT_SECRET", "dev-jwt-secret"),
            "REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
        }
    )

    # Initialize JWT manager
    jwt_manager.init_app(app)

    # Initialize auth service
    auth_service = AuthService(app)

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "Forbidden", "message": "Access denied"}), 403

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    # Run standalone auth service
    app = create_auth_app()
    port = int(os.environ.get("AUTH_SERVICE_PORT", "8082"))

    logger.info(f"Starting authentication service on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
