#!/usr/bin/env python3
"""
ThermoWorks Cloud API Client

This module provides a robust client for interacting with the ThermoWorks Cloud API,
including OAuth2 authentication, device discovery, and temperature data retrieval.
"""

import base64
import datetime
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("thermoworks_client")


@dataclass
class AuthToken:
    """Class for storing OAuth2 tokens"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        # Consider the token expired 5 minutes before actual expiry to allow time for refresh
        return time.time() > (self.created_at + self.expires_in - 300)

    def to_dict(self) -> Dict[str, Any]:
        """Convert token to dictionary for serialization"""
        return asdict(self)


@dataclass
class DeviceInfo:
    """Class for storing device information"""

    device_id: str
    name: str
    model: str
    firmware_version: Optional[str] = None
    last_seen: Optional[str] = None
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None
    is_online: bool = True
    probes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert device info to dictionary"""
        return asdict(self)


@dataclass
class TemperatureReading:
    """Class for storing temperature readings"""

    device_id: str
    probe_id: str
    temperature: float
    unit: str = "F"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert temperature reading to dictionary"""
        return asdict(self)


class ThermoworksAPIError(Exception):
    """Exception raised for ThermoWorks API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class ThermoworksAuthenticationError(ThermoworksAPIError):
    """Exception raised for authentication errors"""

    pass


class ThermoworksConnectionError(ThermoworksAPIError):
    """Exception raised for connection errors"""

    pass


class ThermoworksClient:
    """
    ThermoWorks Cloud API Client

    This class provides methods to interact with the ThermoWorks Cloud API,
    including authentication, device discovery, temperature data retrieval,
    and gateway management.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        base_url: Optional[str] = None,
        auth_url: Optional[str] = None,
        token_storage_path: Optional[str] = None,
        polling_interval: int = 60,
        auto_start_polling: bool = True,
        mock_mode: Optional[bool] = None,
    ):
        """
        Initialize the ThermoWorks client

        Args:
            client_id: OAuth2 client ID (falls back to THERMOWORKS_CLIENT_ID env var)
            client_secret: OAuth2 client secret (falls back to THERMOWORKS_CLIENT_SECRET env var)
            redirect_uri: OAuth2 redirect URI (falls back to THERMOWORKS_REDIRECT_URI env var)
            base_url: ThermoWorks API base URL (falls back to THERMOWORKS_BASE_URL env var or default)
            auth_url: ThermoWorks Auth URL (falls back to THERMOWORKS_AUTH_URL env var or default)
            token_storage_path: Path to store token (falls back to ~/.thermoworks_token.json)
            polling_interval: Interval in seconds for polling device data (falls back to env var)
            auto_start_polling: Whether to start polling automatically on initialization
            mock_mode: Whether to use mock data (falls back to MOCK_MODE env var)
        """
        # OAuth2 configuration
        self.client_id = client_id or os.environ.get("THERMOWORKS_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("THERMOWORKS_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.environ.get("THERMOWORKS_REDIRECT_URI")

        # API endpoints
        self.base_url = base_url or os.environ.get("THERMOWORKS_BASE_URL", "https://api.thermoworks.com/v1")
        self.auth_url = auth_url or os.environ.get("THERMOWORKS_AUTH_URL", "https://auth.thermoworks.com")

        # Mock mode configuration
        if mock_mode is None:
            mock_mode = os.environ.get("MOCK_MODE", "false").lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
        self.mock_mode = mock_mode and not os.environ.get("FLASK_ENV", "").lower() == "production"

        if self.mock_mode:
            logger.info("ThermoWorks device service client initialized in MOCK MODE")
            # Import and initialize mock service
            try:
                import sys

                sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
                from mock_data import MockDataService

                self.mock_service = MockDataService()
            except ImportError as e:
                logger.error("Failed to import MockDataService: %s", e)
                self.mock_mode = False
                self.mock_service = None
        else:
            logger.info("ThermoWorks device service client initialized in LIVE MODE")
            self.mock_service = None

        # Token storage
        self.token_storage_path = token_storage_path or os.path.expanduser("~/.thermoworks_token.json")

        # Connection state
        self.session = requests.Session()
        self.token: Optional[AuthToken] = None
        self.connection_state = {
            "connected": False,
            "last_connection_attempt": None,
            "last_successful_connection": None,
            "last_error": None,
            "consecutive_failures": 0,
        }

        # Polling configuration
        polling_interval_env = os.environ.get("THERMOWORKS_POLLING_INTERVAL")
        self.polling_interval = int(polling_interval_env) if polling_interval_env else polling_interval
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_stop_event = threading.Event()
        self._polling_lock = threading.Lock()

        # Device cache
        self._device_cache: Dict[str, DeviceInfo] = {}
        self._device_cache_timestamp = 0
        self._device_cache_lock = threading.Lock()

        # Load token if available
        self._load_token()

        # Start polling if requested and token is available
        if auto_start_polling and self.token:
            self.start_polling()

    def _load_token(self) -> None:
        """Load token from storage if available"""
        try:
            if os.path.exists(self.token_storage_path):
                with open(self.token_storage_path, "r") as f:
                    token_data = json.load(f)
                self.token = AuthToken(**token_data)
                logger.info("Loaded token from storage")

                # Check if token is expired and try to refresh
                if self.token.is_expired and self.token.refresh_token:
                    try:
                        self.refresh_token()
                    except Exception as e:
                        logger.warning(f"Failed to refresh token: {e}")
                        self.token = None
        except Exception as e:
            logger.warning(f"Failed to load token: {e}")
            self.token = None

    def _save_token(self) -> None:
        """Save token to storage"""
        if not self.token:
            return

        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.token_storage_path), exist_ok=True)

            # Write token to file
            with open(self.token_storage_path, "w") as f:
                json.dump(self.token.to_dict(), f)

            # Set secure permissions on Unix-like systems
            if os.name == "posix":
                os.chmod(self.token_storage_path, 0o600)

            logger.info("Saved token to storage")
        except Exception as e:
            logger.warning(f"Failed to save token: {e}")

    def generate_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate an authorization URL for the OAuth2 flow

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Client ID and redirect URI are required for authorization URL generation")

        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)

        # Generate PKCE code verifier and challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")

        # Store code verifier in token storage for later use
        verifier_data = {
            "code_verifier": code_verifier,
            "state": state,
            "created_at": time.time(),
        }

        try:
            verifier_path = os.path.join(os.path.dirname(self.token_storage_path), ".code_verifier.json")
            with open(verifier_path, "w") as f:
                json.dump(verifier_data, f)

            # Set secure permissions on Unix-like systems
            if os.name == "posix":
                os.chmod(verifier_path, 0o600)
        except Exception as e:
            logger.warning(f"Failed to save code verifier: {e}")

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "devices:read temperature:read",
        }

        authorization_url = f"{self.auth_url}/oauth2/authorize?{urlencode(params)}"
        return authorization_url, state

    def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> AuthToken:
        """
        Exchange an authorization code for an access token

        Args:
            code: Authorization code received from the OAuth2 callback
            state: State parameter to validate against the original request

        Returns:
            AuthToken object containing the access token and related information
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("Client ID, client secret, and redirect URI are required for token exchange")

        # Validate state if provided
        if state:
            try:
                verifier_path = os.path.join(os.path.dirname(self.token_storage_path), ".code_verifier.json")
                if os.path.exists(verifier_path):
                    with open(verifier_path, "r") as f:
                        verifier_data = json.load(f)

                    # Check if state matches and verifier is not too old (10 minutes)
                    if verifier_data.get("state") != state or time.time() - verifier_data.get("created_at", 0) > 600:
                        raise ThermoworksAuthenticationError("Invalid or expired state parameter")

                    code_verifier = verifier_data.get("code_verifier")
                else:
                    raise ThermoworksAuthenticationError("No code verifier found")
            except Exception as e:
                logger.error(f"Failed to validate state: {e}")
                raise ThermoworksAuthenticationError("Failed to validate state parameter")
        else:
            # If no state provided, try to use the most recent code verifier
            try:
                verifier_path = os.path.join(os.path.dirname(self.token_storage_path), ".code_verifier.json")
                if os.path.exists(verifier_path):
                    with open(verifier_path, "r") as f:
                        verifier_data = json.load(f)
                    code_verifier = verifier_data.get("code_verifier")
                else:
                    raise ThermoworksAuthenticationError("No code verifier found")
            except Exception:
                raise ThermoworksAuthenticationError("No code verifier found")

        # Exchange code for token
        token_url = f"{self.auth_url}/oauth2/token"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code_verifier": code_verifier,
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            # Create token object
            self.token = AuthToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=int(token_data.get("expires_in", 3600)),
                scope=token_data.get("scope"),
                created_at=time.time(),
            )

            # Save token
            self._save_token()

            # Update connection state
            self.connection_state["connected"] = True
            self.connection_state["last_successful_connection"] = time.time()
            self.connection_state["consecutive_failures"] = 0
            self.connection_state["last_error"] = None

            # Try to delete the code verifier file
            try:
                os.remove(verifier_path)
            except Exception:
                pass

            # Start polling if not already running
            self.start_polling()

            return self.token
        except requests.RequestException as e:
            self.connection_state["connected"] = False
            self.connection_state["last_error"] = str(e)
            self.connection_state["consecutive_failures"] += 1

            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = {"error": "Unknown error"}

                logger.error(f"Token exchange failed: {status_code} - {error_data}")
                raise ThermoworksAuthenticationError(
                    f"Token exchange failed: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}",
                    status_code=status_code,
                    response=error_data,
                )
            else:
                logger.error(f"Token exchange failed: {e}")
                raise ThermoworksConnectionError(f"Token exchange failed: {e}")

    def authenticate_with_client_credentials(self) -> AuthToken:
        """
        Authenticate using client credentials grant

        Returns:
            AuthToken object containing the access token and related information
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Client ID and client secret are required for client credentials authentication")

        # Request token
        token_url = f"{self.auth_url}/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "devices:read temperature:read",
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            # Create token object
            self.token = AuthToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),  # Usually None for client credentials
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=int(token_data.get("expires_in", 3600)),
                scope=token_data.get("scope"),
                created_at=time.time(),
            )

            # Save token
            self._save_token()

            # Update connection state
            self.connection_state["connected"] = True
            self.connection_state["last_successful_connection"] = time.time()
            self.connection_state["consecutive_failures"] = 0
            self.connection_state["last_error"] = None

            # Start polling if not already running
            self.start_polling()

            return self.token
        except requests.RequestException as e:
            self.connection_state["connected"] = False
            self.connection_state["last_error"] = str(e)
            self.connection_state["consecutive_failures"] += 1

            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = {"error": "Unknown error"}

                logger.error(f"Client credentials authentication failed: {status_code} - {error_data}")
                raise ThermoworksAuthenticationError(
                    f"Authentication failed: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}",
                    status_code=status_code,
                    response=error_data,
                )
            else:
                logger.error(f"Client credentials authentication failed: {e}")
                raise ThermoworksConnectionError(f"Authentication failed: {e}")

    def refresh_token(self) -> AuthToken:
        """
        Refresh the access token using the refresh token

        Returns:
            AuthToken object containing the new access token and related information

        Raises:
            ThermoworksAuthenticationError: If the token refresh fails
            ThermoworksConnectionError: If there is a connection error
        """
        if not self.token or not self.token.refresh_token:
            raise ThermoworksAuthenticationError("No refresh token available")

        if not self.client_id or not self.client_secret:
            raise ValueError("Client ID and client secret are required for token refresh")

        # Request new token
        token_url = f"{self.auth_url}/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.token.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            # Update token object
            self.token = AuthToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", self.token.refresh_token),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=int(token_data.get("expires_in", 3600)),
                scope=token_data.get("scope", self.token.scope),
                created_at=time.time(),
            )

            # Save token
            self._save_token()

            # Update connection state
            self.connection_state["connected"] = True
            self.connection_state["last_successful_connection"] = time.time()
            self.connection_state["consecutive_failures"] = 0
            self.connection_state["last_error"] = None

            logger.info("Token refreshed successfully")
            return self.token
        except requests.RequestException as e:
            self.connection_state["connected"] = False
            self.connection_state["last_error"] = str(e)
            self.connection_state["consecutive_failures"] += 1

            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = {"error": "Unknown error"}

                logger.error(f"Token refresh failed: {status_code} - {error_data}")

                # If the refresh token is invalid or expired, we need to re-authenticate
                if status_code in (400, 401) and error_data.get("error") in (
                    "invalid_grant",
                    "invalid_token",
                ):
                    self.token = None
                    self._save_token()  # Clear the stored token

                raise ThermoworksAuthenticationError(
                    f"Token refresh failed: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}",
                    status_code=status_code,
                    response=error_data,
                )
            else:
                logger.error(f"Token refresh failed: {e}")
                raise ThermoworksConnectionError(f"Token refresh failed: {e}")

    def _ensure_authenticated(self) -> None:
        """
        Ensure the client is authenticated

        Raises:
            ThermoworksAuthenticationError: If the client is not authenticated
        """
        if not self.token:
            raise ThermoworksAuthenticationError("Not authenticated")

        # Check if token is expired and refresh if needed
        if self.token.is_expired:
            if self.token.refresh_token:
                self.refresh_token()
            else:
                # For client credentials, we can just get a new token
                self.authenticate_with_client_credentials()

    def _make_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3,
        retry_backoff: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Make an API request with retry logic and token refresh

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Form data
            json_data: JSON data
            headers: Additional headers
            retry_count: Number of retries
            retry_backoff: Initial backoff time (seconds)

        Returns:
            API response as dictionary

        Raises:
            ThermoworksAPIError: If the API request fails
            ThermoworksAuthenticationError: If authentication fails
            ThermoworksConnectionError: If there is a connection error
        """
        self._ensure_authenticated()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = {
            "Authorization": f"{self.token.token_type} {self.token.access_token}",
            "Accept": "application/json",
            "User-Agent": "ThermoWorksClient/1.0",
        }

        if headers:
            request_headers.update(headers)

        # Update connection state
        self.connection_state["last_connection_attempt"] = time.time()

        # Retry logic
        for attempt in range(retry_count):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    timeout=(5, 30),  # 5s connect, 30s read
                )

                # Handle 401 Unauthorized - try to refresh token
                if response.status_code == 401 and attempt < retry_count - 1:
                    logger.warning("Unauthorized response, attempting to refresh token")
                    try:
                        self._ensure_authenticated()
                        request_headers["Authorization"] = f"{self.token.token_type} {self.token.access_token}"
                        continue
                    except Exception as e:
                        logger.error(f"Token refresh failed during request: {e}")

                # Check for successful response
                response.raise_for_status()

                # Update connection state
                self.connection_state["connected"] = True
                self.connection_state["last_successful_connection"] = time.time()
                self.connection_state["consecutive_failures"] = 0
                self.connection_state["last_error"] = None

                # Parse and return response
                try:
                    return response.json()
                except ValueError:
                    # Handle empty or non-JSON responses
                    if not response.text:
                        return {}
                    return {"raw_response": response.text}

            except requests.RequestException as e:
                self.connection_state["connected"] = False
                self.connection_state["last_error"] = str(e)
                self.connection_state["consecutive_failures"] += 1

                # Log the error
                logger.warning(f"API request failed (attempt {attempt+1}/{retry_count}): {e}")

                # Check if we should retry
                if attempt < retry_count - 1:
                    # Calculate backoff time with exponential increase and jitter
                    backoff_time = retry_backoff * (2**attempt) * (0.5 + 0.5 * secrets.SystemRandom().random())
                    logger.info(f"Retrying in {backoff_time:.2f} seconds")
                    time.sleep(backoff_time)
                else:
                    # Last attempt failed, raise exception
                    if hasattr(e, "response") and e.response is not None:
                        status_code = e.response.status_code
                        try:
                            error_data = e.response.json()
                        except Exception:
                            error_data = {
                                "error": "Unknown error",
                                "details": e.response.text,
                            }

                        logger.error(f"API request failed: {status_code} - {error_data}")
                        raise ThermoworksAPIError(
                            f"API request failed: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}",
                            status_code=status_code,
                            response=error_data,
                        )
                    else:
                        logger.error(f"API request failed: {e}")
                        raise ThermoworksConnectionError(f"API request failed: {e}")

        # This should not be reached, but just in case
        raise ThermoworksConnectionError("API request failed after retries")

    def get_devices(self, force_refresh: bool = False) -> List[DeviceInfo]:
        """
        Get a list of all devices

        Args:
            force_refresh: Whether to force a refresh of the device cache

        Returns:
            List of DeviceInfo objects

        Raises:
            ThermoworksAPIError: If the API request fails
        """
        # Use mock data if mock mode is enabled
        if self.mock_mode and self.mock_service:
            try:
                mock_devices = self.mock_service.get_devices()
                devices = []
                for device_data in mock_devices:
                    device = DeviceInfo(
                        device_id=device_data.get("device_id"),
                        name=device_data.get("name", f"Device {device_data.get('device_id')}"),
                        model=device_data.get("model", "Unknown"),
                        firmware_version=device_data.get("firmware_version"),
                        last_seen=device_data.get("last_seen"),
                        battery_level=device_data.get("battery_level"),
                        signal_strength=device_data.get("signal_strength"),
                        is_online=device_data.get("is_online", True),
                        probes=device_data.get("probes", []),
                    )
                    devices.append(device)
                return devices
            except Exception as e:
                logger.error(f"Failed to get mock devices: {e}")
                return []

        # Check if we can use cached data
        with self._device_cache_lock:
            cache_age = time.time() - self._device_cache_timestamp
            if not force_refresh and self._device_cache and cache_age < 300:  # 5 minutes
                return list(self._device_cache.values())

        # Fetch devices from API
        try:
            response = self._make_api_request("GET", "/devices")

            devices = []
            for device_data in response.get("devices", []):
                device_id = device_data.get("id")
                if not device_id:
                    continue

                device = DeviceInfo(
                    device_id=device_id,
                    name=device_data.get("name", f"Device {device_id}"),
                    model=device_data.get("model", "Unknown"),
                    firmware_version=device_data.get("firmware_version"),
                    last_seen=device_data.get("last_seen"),
                    battery_level=device_data.get("battery_level"),
                    signal_strength=device_data.get("signal_strength"),
                    is_online=device_data.get("is_online", True),
                    probes=device_data.get("probes", []),
                )
                devices.append(device)

            # Update cache
            with self._device_cache_lock:
                self._device_cache = {device.device_id: device for device in devices}
                self._device_cache_timestamp = time.time()

            return devices
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")

            # Use cache if available
            with self._device_cache_lock:
                if self._device_cache:
                    logger.info("Using cached device data due to API error")
                    return list(self._device_cache.values())

            # Re-raise if we have no cache
            raise

    def get_device(self, device_id: str) -> DeviceInfo:
        """
        Get information for a specific device

        Args:
            device_id: Device ID

        Returns:
            DeviceInfo object

        Raises:
            ThermoworksAPIError: If the API request fails
            ValueError: If the device is not found
        """
        # Check cache first
        with self._device_cache_lock:
            if device_id in self._device_cache:
                return self._device_cache[device_id]

        # Fetch from API
        response = self._make_api_request("GET", f"/devices/{device_id}")

        if not response:
            raise ValueError(f"Device {device_id} not found")

        device_data = response.get("device", response)  # Handle different response formats

        device = DeviceInfo(
            device_id=device_data.get("id", device_id),
            name=device_data.get("name", f"Device {device_id}"),
            model=device_data.get("model", "Unknown"),
            firmware_version=device_data.get("firmware_version"),
            last_seen=device_data.get("last_seen"),
            battery_level=device_data.get("battery_level"),
            signal_strength=device_data.get("signal_strength"),
            is_online=device_data.get("is_online", True),
            probes=device_data.get("probes", []),
        )

        # Update cache
        with self._device_cache_lock:
            self._device_cache[device_id] = device

        return device

    def get_device_temperature(self, device_id: str, probe_id: Optional[str] = None) -> List[TemperatureReading]:
        """
        Get current temperature readings for a device

        Args:
            device_id: Device ID
            probe_id: Optional probe ID to filter results

        Returns:
            List of TemperatureReading objects

        Raises:
            ThermoworksAPIError: If the API request fails
        """
        params = {}
        if probe_id:
            params["probe"] = probe_id

        response = self._make_api_request("GET", f"/devices/{device_id}/temperature", params=params)

        readings = []
        for reading_data in response.get("readings", []):
            probe = reading_data.get("probe", "default")
            temp = reading_data.get("temperature")

            if temp is None:
                continue

            reading = TemperatureReading(
                device_id=device_id,
                probe_id=probe,
                temperature=float(temp),
                unit=reading_data.get("unit", "F"),
                timestamp=reading_data.get("timestamp", datetime.datetime.now().isoformat()),
                battery_level=reading_data.get("battery_level"),
                signal_strength=reading_data.get("signal_strength"),
            )
            readings.append(reading)

        return readings

    def get_device_history(
        self,
        device_id: str,
        probe_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> List[TemperatureReading]:
        """
        Get historical temperature readings for a device

        Args:
            device_id: Device ID
            probe_id: Optional probe ID to filter results
            start_time: Optional start time in ISO format
            end_time: Optional end time in ISO format
            limit: Maximum number of readings to return

        Returns:
            List of TemperatureReading objects

        Raises:
            ThermoworksAPIError: If the API request fails
        """
        params = {"limit": limit}

        if probe_id:
            params["probe"] = probe_id

        if start_time:
            params["start"] = start_time

        if end_time:
            params["end"] = end_time

        response = self._make_api_request("GET", f"/devices/{device_id}/history", params=params)

        readings = []
        for reading_data in response.get("history", []):
            probe = reading_data.get("probe", "default")
            temp = reading_data.get("temperature")

            if temp is None:
                continue

            reading = TemperatureReading(
                device_id=device_id,
                probe_id=probe,
                temperature=float(temp),
                unit=reading_data.get("unit", "F"),
                timestamp=reading_data.get("timestamp", ""),
                battery_level=reading_data.get("battery_level"),
                signal_strength=reading_data.get("signal_strength"),
            )
            readings.append(reading)

        return readings

    def start_polling(self) -> None:
        """
        Start background polling for device data

        This method starts a background thread that polls for device data
        at the configured interval. If polling is already active, this
        method does nothing.
        """
        with self._polling_lock:
            if self._polling_thread and self._polling_thread.is_alive():
                logger.info("Polling already active")
                return

            self._polling_stop_event.clear()
            self._polling_thread = threading.Thread(
                target=self._polling_worker,
                daemon=True,
                name="ThermoworksPolling",
            )
            self._polling_thread.start()
            logger.info(f"Started polling thread (interval: {self.polling_interval}s)")

    def stop_polling(self) -> None:
        """
        Stop background polling for device data

        This method signals the polling thread to stop and waits for it
        to terminate.
        """
        with self._polling_lock:
            if not self._polling_thread or not self._polling_thread.is_alive():
                logger.info("No active polling thread")
                return

            logger.info("Stopping polling thread")
            self._polling_stop_event.set()

            # Give the thread a chance to exit gracefully
            self._polling_thread.join(timeout=5.0)

            if self._polling_thread.is_alive():
                logger.warning("Polling thread did not exit gracefully")
            else:
                logger.info("Polling thread stopped")

    def _polling_worker(self) -> None:
        """Background worker for polling device data"""
        logger.info("Polling worker started")

        while not self._polling_stop_event.is_set():
            try:
                # Skip if not authenticated
                if not self.token:
                    logger.warning("Not authenticated, skipping poll")
                    if self._polling_stop_event.wait(5.0):  # Check for stop every 5 seconds
                        break
                    continue

                # Check if token needs refresh
                if self.token.is_expired:
                    try:
                        logger.info("Token expired, refreshing")
                        self._ensure_authenticated()
                    except Exception as e:
                        logger.error(f"Failed to refresh token during polling: {e}")
                        if self._polling_stop_event.wait(30.0):  # Wait longer after auth failure
                            break
                        continue

                # Fetch devices
                logger.info("Polling for devices")
                devices = self.get_devices(force_refresh=True)
                logger.info(f"Found {len(devices)} devices")

                # Fetch temperature for each device
                for device in devices:
                    if self._polling_stop_event.is_set():
                        break

                    try:
                        logger.info(f"Polling temperature for device {device.device_id}")
                        readings = self.get_device_temperature(device.device_id)
                        logger.info(f"Got {len(readings)} temperature readings for device {device.device_id}")

                        # Do something with the readings (e.g., publish to a message bus)
                        # This would be implemented by subclasses or event handlers
                        self._handle_temperature_readings(device, readings)

                    except Exception as e:
                        logger.error(f"Failed to get temperature for device {device.device_id}: {e}")

                    # Small delay between devices to avoid overloading the API
                    if len(devices) > 1 and not self._polling_stop_event.is_set():
                        self._polling_stop_event.wait(1.0)

                # Wait for the next polling interval
                logger.info(f"Waiting for next polling interval ({self.polling_interval}s)")
                if self._polling_stop_event.wait(self.polling_interval):
                    break

            except Exception as e:
                logger.error(f"Error during polling: {e}")

                # Wait before retrying
                if self._polling_stop_event.wait(30.0):  # Wait longer after error
                    break

        logger.info("Polling worker stopped")

    def _handle_temperature_readings(self, device: DeviceInfo, readings: List[TemperatureReading]) -> None:
        """
        Handle temperature readings

        This method is called by the polling worker when new temperature readings
        are received. Subclasses can override this method to implement custom
        handling of temperature readings.

        Args:
            device: Device information
            readings: List of temperature readings
        """
        # Default implementation does nothing
        pass

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get the current connection status

        Returns:
            Dictionary with connection status information
        """
        status = self.connection_state.copy()
        status["authenticated"] = self.token is not None

        if self.token:
            status["token_expires_at"] = self.token.created_at + self.token.expires_in
            status["token_expires_in"] = max(0, (self.token.created_at + self.token.expires_in) - time.time())
            status["token_is_expired"] = self.token.is_expired

        status["polling_active"] = bool(self._polling_thread and self._polling_thread.is_alive())

        return status

    def get_gateway_status(self, gateway_id: str) -> Dict[str, Any]:
        """
        Get the status of an RFX Gateway

        Args:
            gateway_id: Gateway ID

        Returns:
            Gateway status information

        Raises:
            ThermoworksAPIError: If the API request fails
            ValueError: If the gateway is not found
        """
        response = self._make_api_request("GET", f"/gateways/{gateway_id}")

        if not response:
            raise ValueError(f"Gateway {gateway_id} not found")

        return response.get("gateway", response)

    def get_gateways(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get a list of all registered RFX Gateways

        Args:
            force_refresh: Whether to force a refresh from the API

        Returns:
            List of gateway information dictionaries

        Raises:
            ThermoworksAPIError: If the API request fails
        """
        response = self._make_api_request("GET", "/gateways")

        return response.get("gateways", [])

    def register_gateway(self, gateway_id: str, name: str) -> Dict[str, Any]:
        """
        Register an RFX Gateway with the ThermoWorks Cloud account

        Args:
            gateway_id: Gateway ID
            name: User-friendly name for the gateway

        Returns:
            Gateway registration response

        Raises:
            ThermoworksAPIError: If the API request fails
        """
        data = {"gateway_id": gateway_id, "name": name, "type": "rfx_gateway"}

        response = self._make_api_request("POST", "/gateways/register", json_data=data)

        return response

    def __del__(self) -> None:
        """Cleanup when the client is deleted"""
        try:
            self.stop_polling()
        except Exception:
            pass
