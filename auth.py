"""Keycloak authentication module for MinIO MCP Server."""

import logging
import time
from typing import Dict, Optional, Any
import httpx
import jwt
from dataclasses import dataclass
from config import get_config


logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information structure."""
    access_token: str
    refresh_token: str
    expires_in: int
    expires_at: float
    token_type: str = "Bearer"


@dataclass
class UserInfo:
    """User information structure."""
    username: str
    email: Optional[str]
    roles: list[str]
    realm_roles: list[str]
    client_roles: Dict[str, list[str]]


class AuthenticationError(Exception):
    """Authentication related errors."""
    pass


class AuthorizationError(Exception):
    """Authorization related errors."""
    pass


class KeycloakAuth:
    """Keycloak authentication and authorization manager."""

    def __init__(self):
        self.config = get_config()
        self.client = httpx.AsyncClient(timeout=30.0)
        self._token_cache: Optional[TokenInfo] = None
        self._user_cache: Optional[UserInfo] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @property
    def token_endpoint(self) -> str:
        """Get the Keycloak token endpoint URL."""
        return f"{self.config.keycloak_server_url}/realms/{self.config.keycloak_realm}/protocol/openid-connect/token"

    @property
    def userinfo_endpoint(self) -> str:
        """Get the Keycloak userinfo endpoint URL."""
        return f"{self.config.keycloak_server_url}/realms/{self.config.keycloak_realm}/protocol/openid-connect/userinfo"

    async def login(self, username: str, password: str) -> TokenInfo:
        """
        Authenticate user with username and password.

        Args:
            username: User's username
            password: User's password

        Returns:
            TokenInfo: Token information including access and refresh tokens

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            data = {
                "grant_type": "password",
                "client_id": self.config.keycloak_client_id,
                "client_secret": self.config.keycloak_client_secret,
                "username": username,
                "password": password,
                "scope": "openid profile email"
            }

            response = await self.client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code != 200:
                error_detail = response.json().get("error_description", "Authentication failed")
                raise AuthenticationError(f"Login failed: {error_detail}")

            token_data = response.json()

            token_info = TokenInfo(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                expires_at=time.time() + token_data["expires_in"],
                token_type=token_data.get("token_type", "Bearer")
            )

            # Cache the token
            self._token_cache = token_info

            # Clear user cache since we have a new token
            self._user_cache = None

            logger.info(f"Successfully authenticated user: {username}")
            return token_info

        except httpx.RequestError as e:
            raise AuthenticationError(f"Network error during authentication: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Unexpected error during authentication: {str(e)}")

    async def refresh_token(self, refresh_token: str) -> TokenInfo:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            TokenInfo: New token information

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.config.keycloak_client_id,
                "client_secret": self.config.keycloak_client_secret,
                "refresh_token": refresh_token
            }

            response = await self.client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code != 200:
                error_detail = response.json().get("error_description", "Token refresh failed")
                raise AuthenticationError(f"Token refresh failed: {error_detail}")

            token_data = response.json()

            token_info = TokenInfo(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", refresh_token),
                expires_in=token_data["expires_in"],
                expires_at=time.time() + token_data["expires_in"],
                token_type=token_data.get("token_type", "Bearer")
            )

            # Update cache
            self._token_cache = token_info
            self._user_cache = None

            logger.info("Successfully refreshed authentication token")
            return token_info

        except httpx.RequestError as e:
            raise AuthenticationError(f"Network error during token refresh: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Unexpected error during token refresh: {str(e)}")

    async def validate_token(self, token: str) -> UserInfo:
        """
        Validate access token and get user information.

        Args:
            token: Access token to validate

        Returns:
            UserInfo: User information from token

        Raises:
            AuthenticationError: If token validation fails
        """
        try:
            # First try to get user info from Keycloak
            headers = {"Authorization": f"Bearer {token}"}

            response = await self.client.get(
                self.userinfo_endpoint,
                headers=headers
            )

            if response.status_code != 200:
                raise AuthenticationError("Invalid or expired token")

            user_data = response.json()

            # Extract roles from token claims
            try:
                # Decode token without verification for role extraction
                # In production, you should verify the token signature
                token_claims = jwt.decode(token, options={"verify_signature": False})

                realm_roles = token_claims.get("realm_access", {}).get("roles", [])
                resource_access = token_claims.get("resource_access", {})
                client_roles = {}

                for client, access in resource_access.items():
                    client_roles[client] = access.get("roles", [])

            except Exception as e:
                logger.warning(f"Could not extract roles from token: {e}")
                realm_roles = []
                client_roles = {}

            user_info = UserInfo(
                username=user_data.get("preferred_username", ""),
                email=user_data.get("email"),
                roles=realm_roles + [role for roles in client_roles.values() for role in roles],
                realm_roles=realm_roles,
                client_roles=client_roles
            )

            # Cache user info
            self._user_cache = user_info

            return user_info

        except httpx.RequestError as e:
            raise AuthenticationError(f"Network error during token validation: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")

    def has_role(self, user_info: UserInfo, required_role: str) -> bool:
        """
        Check if user has required role.

        Args:
            user_info: User information
            required_role: Role to check for

        Returns:
            bool: True if user has the role
        """
        return required_role in user_info.roles

    def has_any_role(self, user_info: UserInfo, required_roles: list[str]) -> bool:
        """
        Check if user has any of the required roles.

        Args:
            user_info: User information
            required_roles: List of roles to check for

        Returns:
            bool: True if user has any of the roles
        """
        return any(role in user_info.roles for role in required_roles)

    def check_authorization(self, user_info: UserInfo, required_roles: list[str]) -> None:
        """
        Check if user is authorized (has required roles).

        Args:
            user_info: User information
            required_roles: List of required roles

        Raises:
            AuthorizationError: If user lacks required authorization
        """
        if not self.has_any_role(user_info, required_roles):
            raise AuthorizationError(
                f"User '{user_info.username}' lacks required roles: {required_roles}"
            )

    def is_token_expired(self, token_info: TokenInfo) -> bool:
        """
        Check if token is expired or will expire soon.

        Args:
            token_info: Token information

        Returns:
            bool: True if token is expired or expires within 60 seconds
        """
        return time.time() + 60 >= token_info.expires_at

    async def get_current_user(self) -> Optional[UserInfo]:
        """Get currently cached user information."""
        return self._user_cache

    async def get_current_token(self) -> Optional[TokenInfo]:
        """Get currently cached token information."""
        return self._token_cache