"""API client for teapot-cli."""

import json
import time
from datetime import datetime
from enum import Enum
from typing import Any

import httpx
from rich.console import Console

from teapot_cli.core.config import (
    VERBOSITY_BASIC,
    VERBOSITY_DEBUG,
    VERBOSITY_DETAILED,
    TeapotConfig,
    save_config,
)

console = Console()

SUCCESS_STATUS_CODE_RANGE = range(200, 300)
ERROR_STATUS_CODE_RANGE = range(400, 600)
SENSITIVE_KEY_NAMES = [
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
    "nonce",
    "credential",
    "authorization",
    "x-api-key",
    "x-auth-token",
]


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize APIError with a message and optional status code.

        Args:
            message (str): Error message.
            status_code (int | None): HTTP status code, if available.

        """
        super().__init__(message)
        self.status_code = status_code


class APIEndpointPrivacy(Enum):
    """Enum for endpoint privacy levels."""

    PUBLIC = "public"  # No authentication required
    LOGGED_IN = "logged_in"  # Requires authentication


class APIClient:
    """HTTP client for API interactions."""

    def __init__(self, config: TeapotConfig) -> None:
        """Initialize the API client with configuration.

        Args:
            config (TeapotConfig): Configuration object containing API settings.

        """
        self.config = config
        self.client = httpx.Client(
            base_url=config.api.base_url,
            timeout=config.api.timeout,
            headers=self._get_headers(),
        )

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {
            "User-Agent": "teapot-cli/0.1.0",
            "Accept": "application/json",
        }

        if self.config.auth.session_token:
            headers["Authorization"] = f"Bearer {self.config.auth.session_token}"

        return headers

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data for logging (creates a copy)."""
        if not data:
            return data

        sanitized = data.copy()
        for key in list(sanitized.keys()):
            if key.lower() in SENSITIVE_KEY_NAMES:
                sanitized[key] = "***REDACTED***"

        return sanitized

    def _truncate_response(self, data: dict | list, max_length: int = 500) -> str:
        """Truncate response data for logging."""
        data_str = (
            json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
        )

        if len(data_str) > max_length:
            return data_str[:max_length] + "... [TRUNCATED]"
        return data_str

    def _add_auth_data(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Add authentication data to request."""
        if data is None:
            data = {}

        if self.config.auth.user_id and self.config.auth.nonce:
            data["user_id"] = self.config.auth.user_id
            data["nonce"] = self.config.auth.nonce

        return data

    def _handle_auth_response(self, response_data: dict[str, Any]) -> None:
        """Handle authentication data in response."""
        new_nonce = response_data.get("nonce")
        if new_nonce:
            self.config.auth.nonce = new_nonce
            # Save config to persist new nonce
            save_config(self.config)
        else:
            # Request failed, clear nonce
            self.config.auth.nonce = None
            save_config(self.config)

    def _ensure_valid_nonce(self) -> bool:
        """Ensure we have a valid nonce, refresh if needed."""
        # Check if nonce exists and is not expired
        if not self.config.auth.nonce or self._is_nonce_expired():
            return self._refresh_nonce()
        return True

    def _is_nonce_expired(self) -> bool:
        """Check if current nonce is expired."""
        if not self.config.auth.nonce_expiration:
            return True

        try:
            expiration = datetime.fromisoformat(self.config.auth.nonce_expiration)
            # Ensure both datetimes have the same timezone awareness
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=self.config.tz)
            return datetime.now(tz=self.config.tz) > expiration
        except ValueError:
            return True

    def _refresh_nonce(self) -> bool:
        """Refresh nonce using session token."""
        if not self.config.auth.session_token:
            return False

        try:
            # Direct HTTP call to avoid recursive auth handling
            start_time = time.time()
            self._log_request(
                "GET",
                "/nonce/get",
                json={"credential": self.config.auth.session_token},
            )

            data = {
                "action": "nonce/get",
                "credential": self.config.auth.session_token,
            }
            response = self.client.get(self.endpoint, params=data)

            self._log_response(response, start_time)
            response_data = self._handle_response(response)
            if not response_data.get("success"):
                return False

            self.config.auth.nonce = response_data["nonce"]
            self.config.auth.nonce_expiration = response_data["nonce_expiration"]

            save_config(self.config)

        except APIError:
            return False

        else:
            return True

    def _log_request(self, method: str, action: str, **kwargs) -> None:
        """Log HTTP request details based on verbosity level."""
        if self.config.is_verbose(VERBOSITY_BASIC):
            color = {
                "GET": "blue",
                "POST": "green",
                "PUT": "yellow",
                "DELETE": "red",
            }.get(method, "white")
            console.print(f"[{color}]{method}[/{color}] {action}")

        if self.config.is_verbose(VERBOSITY_DETAILED):
            full_url = f"{self.config.api.base_url.rstrip('/')}/rest.php"
            console.print(f"[dim]  → Full URL: {full_url}[/dim]")
            console.print(f"[dim]  → Action: {action}[/dim]")

            if kwargs.get("params"):
                sanitized_params = self._sanitize_data(kwargs["params"])
                console.print(f"[dim]  → Params: {sanitized_params}[/dim]")

            if kwargs.get("json"):
                sanitized_data = self._sanitize_data(kwargs["json"])
                console.print(f"[dim]  → JSON: {sanitized_data}[/dim]")

            if kwargs.get("data"):
                sanitized_data = self._sanitize_data(kwargs["data"])
                console.print(f"[dim]  → Form Data: {sanitized_data}[/dim]")

        if self.config.is_verbose(VERBOSITY_DEBUG):
            sanitized_headers = self._sanitize_data(self.client.headers)
            console.print(f"[dim]  → Headers: {sanitized_headers}[/dim]")

    def _log_response(self, response: httpx.Response, start_time: float) -> None:
        """Log HTTP response details based on verbosity level."""
        if self.config.is_verbose(VERBOSITY_DETAILED):
            elapsed = time.time() - start_time
            status_color = (
                "green" if response.status_code in SUCCESS_STATUS_CODE_RANGE else "red"
            )
            console.print(
                f"[dim]  ← Status: [{status_color}]{response.status_code}[/{status_color}] ({elapsed:.2f}s)[/dim]",  # noqa: E501
            )

        if self.config.is_verbose(VERBOSITY_DEBUG):
            try:
                response_data = response.json()
                if self.config.is_verbose(VERBOSITY_DEBUG):
                    # Full response in debug mode
                    console.print(
                        f"[dim]  ← Response: {json.dumps(response_data, indent=2)}[/dim]",
                    )
                else:
                    # Truncated response in detailed mode
                    truncated = self._truncate_response(response_data)
                    console.print(f"[dim]  ← Response: {truncated}[/dim]")
            except KeyError:
                console.print(f"[dim]  ← Response (raw): {response.text[:200]}[/dim]")

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle HTTP response and raise errors if needed."""
        if response.status_code in ERROR_STATUS_CODE_RANGE:
            try:
                error_data = response.json()
                message = error_data.get("message", f"HTTP {response.status_code}")
            except KeyError:
                message = f"HTTP {response.status_code}: {response.text}"

            raise APIError(message, response.status_code)

        try:
            return response.json()
        except ValueError:
            return {"data": response.text}

    @property
    def endpoint(self) -> str:
        """Construct the base endpoint URL."""
        return f"{self.config.api.base_url.rstrip('/')}/rest.php"

    def get(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        endpoint_privacy: APIEndpointPrivacy = APIEndpointPrivacy.LOGGED_IN,
    ) -> dict[str, Any]:
        """Make a GET request.

        Args:
            action (str): The API action to perform, e.g., "/api/test".
            params (dict[str, Any] | None): Query parameters for the request.
            endpoint_privacy (APIEndpointPrivacy): Privacy level of the endpoint.

        """
        # Skip auth for login and nonce endpoints
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._ensure_valid_nonce()

        start_time = time.time()
        self._log_request("GET", action, params=params)

        if params is None:
            params = {}
        params["action"] = action.lstrip("/")  # Add action to params

        # Add auth data to params for GET requests
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            params = self._add_auth_data(params)

        response = self.client.get(self.endpoint, params=params)

        self._log_response(response, start_time)
        response_data = self._handle_response(response)

        # Handle auth response if not login/nonce endpoint
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._handle_auth_response(response_data)

        return response_data

    def post(
        self,
        action: str,
        data: dict[str, Any] | None = None,
        endpoint_privacy: APIEndpointPrivacy = APIEndpointPrivacy.LOGGED_IN,
    ) -> dict[str, Any]:
        """Make a POST request.

        Args:
            action (str): The API action to post to, e.g., "/api/resource".
            data (dict[str, Any] | None): JSON data to send in the request body.
            endpoint_privacy (EndpointPrivacy): Privacy level of the endpoint.

        """
        start_time = time.time()

        # Skip auth for non logged-in endpoints
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._ensure_valid_nonce()

        # Add data to request body
        if data is None:
            data = {}
        data["action"] = action.lstrip("/")  # Add action to data
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            data = self._add_auth_data(data)

        # Log request details
        self._log_request("POST", action, data=data)
        # Run the request - send as form data instead of JSON
        response = self.client.post(self.endpoint, data=data)

        # Log response details
        self._log_response(response, start_time)
        # Handle response
        response_data = self._handle_response(response)

        # Handle auth response if not login/nonce endpoint
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._handle_auth_response(response_data)

        return response_data

    def put(
        self,
        action: str,
        data: dict[str, Any] | None = None,
        endpoint_privacy: APIEndpointPrivacy = APIEndpointPrivacy.LOGGED_IN,
    ) -> dict[str, Any]:
        """Make a PUT request.

        Args:
            action (str): The API action to perform, e.g., "/api/resource".
            data (dict[str, Any] | None): JSON data to send in the request body.
            endpoint_privacy (APIEndpointPrivacy): Privacy level of the endpoint.

        """
        # Skip auth for login and nonce endpoints
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._ensure_valid_nonce()

        start_time = time.time()
        self._log_request("PUT", action, data=data)

        if data is None:
            data = {}
        data["action"] = action.lstrip("/")  # Add action to data

        # Add auth data to request body
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            data = self._add_auth_data(data)

        response = self.client.put(self.endpoint, data=data)

        self._log_response(response, start_time)
        response_data = self._handle_response(response)

        # Handle auth response if not login/nonce endpoint
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._handle_auth_response(response_data)

        return response_data

    def delete(
        self,
        action: str,
        endpoint_privacy: APIEndpointPrivacy = APIEndpointPrivacy.LOGGED_IN,
    ) -> dict[str, Any]:
        """Make a DELETE request.

        Args:
            action (str): The API action to perform, e.g., "/api/resource".
            endpoint_privacy (APIEndpointPrivacy): Privacy level of the endpoint.

        """
        # Skip auth for login and nonce endpoints
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._ensure_valid_nonce()

        start_time = time.time()
        self._log_request("DELETE", action)

        # For DELETE requests, add auth data as query parameters
        auth_params = {}
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            auth_params = self._add_auth_data({})

        # Build endpoint with auth params
        params = {"action": action.lstrip("/"), **auth_params}
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"{self.endpoint}?{param_str}"

        response = self.client.delete(endpoint)

        self._log_response(response, start_time)
        response_data = self._handle_response(response)

        # Handle auth response if not login/nonce endpoint
        if endpoint_privacy == APIEndpointPrivacy.LOGGED_IN:
            self._handle_auth_response(response_data)

        return response_data

    def test_connection(self) -> bool:
        """Test API connection by calling the test endpoint.

        Returns:
            bool: True if connection successful and response has success=True

        """
        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print("[dim]🔍 Testing API connection...[/dim]")

        try:
            response = self.get("/teapot/api/test")
            success = response.get("success", False) is True

            if self.config.is_verbose(VERBOSITY_DEBUG):
                console.print(f"[dim]  Test response: {response}[/dim]")
                console.print(f"[dim]  Success: {success}[/dim]")

        except APIError as e:
            if self.config.is_verbose(VERBOSITY_DETAILED):
                console.print(f"[dim]  API test failed: {e}[/dim]")
            return False
        else:
            return response

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> None:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Exit the runtime context related to this object."""
        self.close()
