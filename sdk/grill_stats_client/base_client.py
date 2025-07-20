"""
Base client for Grill Stats API SDK.

This module provides a base client class that handles common functionality like
authentication, HTTP requests, error handling, and response parsing.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

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


class AuthenticationError(APIError):
    """Exception raised for authentication errors."""

    pass


class ConnectionError(APIError):
    """Exception raised for connection errors."""

    pass


class ClientError(APIError):
    """Exception raised for client errors (4xx)."""

    pass


class ServerError(APIError):
    """Exception raised for server errors (5xx)."""

    pass


class BaseClient:
    """Base client for making API requests."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
        retry_status_forcelist: Optional[List[int]] = None,
        mock_mode: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the base client.

        Args:
            base_url: Base URL for the API.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff_factor: Backoff factor for retries.
            retry_status_forcelist: List of status codes to retry.
            mock_mode: Whether to run in mock mode.
            **kwargs: Additional arguments.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.mock_mode = mock_mode
        self.session = self._create_session(max_retries, retry_backoff_factor, retry_status_forcelist)

    def _create_session(
        self, max_retries: int, retry_backoff_factor: float, retry_status_forcelist: Optional[List[int]] = None
    ) -> requests.Session:
        """
        Create a requests session with retry logic.

        Args:
            max_retries: Maximum number of retries.
            retry_backoff_factor: Backoff factor for retries.
            retry_status_forcelist: List of status codes to retry.

        Returns:
            A configured requests Session.
        """
        if self.mock_mode:
            return cast(requests.Session, None)  # Type to satisfy mypy

        session = requests.Session()

        # Set up retry logic
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_backoff_factor,
            status_forcelist=retry_status_forcelist or [429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        # Add API key if provided
        if self.api_key:
            session.headers["Authorization"] = f"Bearer {self.api_key}"

        return session

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle API response and parse JSON.

        Args:
            response: The requests Response object.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: For authentication errors.
            ClientError: For client errors (4xx).
            ServerError: For server errors (5xx).
            APIError: For other API errors.
        """
        try:
            response.raise_for_status()
            try:
                return cast(Dict[str, Any], response.json())
            except ValueError:
                return {"data": response.text}
        except requests.exceptions.HTTPError as e:
            status_code = response.status_code
            error_message = f"HTTP Error: {status_code}"

            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_message = error_data.get("message", error_message)
            except ValueError:
                error_data = {"text": response.text}

            if status_code == 401:
                raise AuthenticationError(error_message, status_code, error_data)
            elif 400 <= status_code < 500:
                raise ClientError(error_message, status_code, error_data)
            elif 500 <= status_code < 600:
                raise ServerError(error_message, status_code, error_data)
            else:
                raise APIError(error_message, status_code, error_data)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Connection Error: {str(e)}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint.
            params: Query parameters.
            data: Request body.
            headers: Request headers.

        Returns:
            API response.

        Raises:
            ConnectionError: If the request fails.
            APIError: If the API returns an error.
        """
        if self.mock_mode:
            logger.warning(f"Mock mode enabled - {method} request to {endpoint} not sent")
            return {"mock": True, "endpoint": endpoint, "method": method}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = headers or {}

        try:
            if self.session is None:
                raise ConnectionError("Session not initialized")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except (requests.exceptions.RequestException, ConnectionError) as e:
            logger.error(f"Error making {method} request to {url}: {e}")
            raise ConnectionError(f"Error making {method} request to {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error making {method} request to {url}: {e}")
            raise APIError(f"Unexpected error: {str(e)}")

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a GET request.

        Args:
            endpoint: API endpoint.
            params: Query parameters.
            headers: Request headers.

        Returns:
            API response.
        """
        return self._request("GET", endpoint, params=params, headers=headers)

    def post(
        self,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a POST request.

        Args:
            endpoint: API endpoint.
            data: Request body.
            params: Query parameters.
            headers: Request headers.

        Returns:
            API response.
        """
        return self._request("POST", endpoint, params=params, data=data, headers=headers)

    def put(
        self,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a PUT request.

        Args:
            endpoint: API endpoint.
            data: Request body.
            params: Query parameters.
            headers: Request headers.

        Returns:
            API response.
        """
        return self._request("PUT", endpoint, params=params, data=data, headers=headers)

    def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make a DELETE request.

        Args:
            endpoint: API endpoint.
            params: Query parameters.
            headers: Request headers.

        Returns:
            API response.
        """
        return self._request("DELETE", endpoint, params=params, headers=headers)
