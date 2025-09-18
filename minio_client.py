"""MinIO REST API client for MCP Server."""

import logging
import asyncio
from typing import Any, Dict, Optional, Union
import httpx
from dataclasses import dataclass
import time
import uuid

from config import get_config
from auth import KeycloakAuth, TokenInfo, AuthenticationError


logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standardized API response structure."""
    success: bool
    status_code: int
    data: Any
    error: Optional[str] = None
    correlation_id: Optional[str] = None


class MinIOAPIError(Exception):
    """MinIO API related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, correlation_id: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.correlation_id = correlation_id


class MinIOClient:
    """Async HTTP client for MinIO REST API operations."""

    def __init__(self, auth: Optional[KeycloakAuth] = None):
        self.config = get_config()
        self.auth = auth or KeycloakAuth()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.minio_api_timeout),
            follow_redirects=True
        )
        self._current_token: Optional[str] = None
        self._retry_count = 3
        self._retry_delay = 1.0

    async def __aenter__(self):
        await self.auth.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        await self.auth.__aexit__(exc_type, exc_val, exc_tb)

    def set_auth_token(self, token: str) -> None:
        """Set the authentication token for API requests."""
        self._current_token = token

    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID for request tracking."""
        return f"mcp-{uuid.uuid4().hex[:8]}"

    def _build_headers(self, correlation_id: str, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers with authentication and correlation ID."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"{self.config.mcp_server_name}/{self.config.mcp_server_version}"
        }

        if self._current_token:
            headers["Authorization"] = f"Bearer {self._current_token}"

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for API endpoint."""
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
        return f"{self.config.minio_api_base_url}/{endpoint}"

    async def _handle_response(self, response: httpx.Response, correlation_id: str) -> APIResponse:
        """Handle HTTP response and create standardized response object."""
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
            else:
                data = response.text

            if 200 <= response.status_code < 300:
                logger.debug(f"API request successful [{correlation_id}]: {response.status_code}")
                return APIResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    correlation_id=correlation_id
                )
            else:
                error_msg = data.get("error", data) if isinstance(data, dict) else str(data)
                logger.error(f"API request failed [{correlation_id}]: {response.status_code} - {error_msg}")
                return APIResponse(
                    success=False,
                    status_code=response.status_code,
                    data=data,
                    error=error_msg,
                    correlation_id=correlation_id
                )

        except Exception as e:
            logger.error(f"Error handling response [{correlation_id}]: {str(e)}")
            return APIResponse(
                success=False,
                status_code=response.status_code,
                data=None,
                error=f"Response parsing error: {str(e)}",
                correlation_id=correlation_id
            )

    async def _retry_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with retry logic."""
        last_exception = None

        for attempt in range(self._retry_count):
            try:
                response = await self.client.request(method, url, **kwargs)

                # Don't retry on client errors (4xx) except 401 (unauthorized)
                if 400 <= response.status_code < 500 and response.status_code != 401:
                    return response

                # Retry on 401 (try token refresh), 5xx, and network errors
                if response.status_code == 401 and attempt < self._retry_count - 1:
                    logger.warning(f"Received 401, attempting token refresh (attempt {attempt + 1})")
                    await self._refresh_token_if_needed()
                    # Update headers with new token
                    if "headers" in kwargs and self._current_token:
                        kwargs["headers"]["Authorization"] = f"Bearer {self._current_token}"
                    continue

                if response.status_code >= 500 and attempt < self._retry_count - 1:
                    logger.warning(f"Server error {response.status_code}, retrying in {self._retry_delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))  # Exponential backoff
                    continue

                return response

            except httpx.RequestError as e:
                last_exception = e
                if attempt < self._retry_count - 1:
                    logger.warning(f"Network error, retrying in {self._retry_delay}s (attempt {attempt + 1}): {str(e)}")
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue

        # If we get here, all retries failed
        if last_exception:
            raise MinIOAPIError(f"Request failed after {self._retry_count} attempts: {str(last_exception)}")
        else:
            raise MinIOAPIError(f"Request failed after {self._retry_count} attempts")

    async def _refresh_token_if_needed(self) -> None:
        """Refresh authentication token if available."""
        try:
            current_token_info = await self.auth.get_current_token()
            if current_token_info and self.auth.is_token_expired(current_token_info):
                logger.info("Token expired, attempting refresh")
                new_token_info = await self.auth.refresh_token(current_token_info.refresh_token)
                self.set_auth_token(new_token_info.access_token)
                logger.info("Token refreshed successfully")
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            # Clear current token so user knows to re-authenticate
            self._current_token = None

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """
        Make authenticated HTTP request to MinIO API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            data: Raw request body
            headers: Additional headers
            files: Files for multipart upload

        Returns:
            APIResponse: Standardized response object
        """
        correlation_id = self._generate_correlation_id()
        url = self._build_url(endpoint)
        request_headers = self._build_headers(correlation_id, headers)

        # Log request details
        logger.info(f"Making {method} request to {url} [{correlation_id}]")
        if params:
            logger.debug(f"Query params [{correlation_id}]: {params}")

        try:
            # Prepare request kwargs
            request_kwargs = {
                "headers": request_headers,
                "params": params
            }

            if json_data is not None:
                request_kwargs["json"] = json_data
            elif data is not None:
                request_kwargs["content"] = data
                # Update content type for raw data
                if "Content-Type" not in request_headers:
                    request_headers["Content-Type"] = "application/octet-stream"

            if files:
                # For file uploads, remove Content-Type to let httpx set it
                request_headers.pop("Content-Type", None)
                request_kwargs["files"] = files

            # Execute request with retry logic
            response = await self._retry_request(method, url, **request_kwargs)

            # Handle response
            api_response = await self._handle_response(response, correlation_id)

            # Raise exception for failed requests if needed
            if not api_response.success and response.status_code >= 400:
                raise MinIOAPIError(
                    api_response.error or f"Request failed with status {response.status_code}",
                    status_code=response.status_code,
                    correlation_id=correlation_id
                )

            return api_response

        except MinIOAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in request [{correlation_id}]: {str(e)}")
            raise MinIOAPIError(f"Unexpected request error: {str(e)}", correlation_id=correlation_id)

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make GET request."""
        return await self.request("GET", endpoint, params=params, headers=headers)

    async def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, data: Optional[Union[str, bytes]] = None,
                   files: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make POST request."""
        return await self.request("POST", endpoint, json_data=json_data, data=data, files=files, headers=headers)

    async def put(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, data: Optional[Union[str, bytes]] = None,
                  headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make PUT request."""
        return await self.request("PUT", endpoint, json_data=json_data, data=data, headers=headers)

    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make DELETE request."""
        return await self.request("DELETE", endpoint, params=params, headers=headers)

    async def head(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """Make HEAD request."""
        return await self.request("HEAD", endpoint, params=params, headers=headers)

    async def health_check(self) -> bool:
        """Quick health check for the client connection."""
        try:
            response = await self.get("/api/v1/health")
            return response.success
        except Exception:
            return False