"""Authentication tools for MinIO MCP Server."""

import logging
from typing import Any, Dict
from fastmcp import FastMCP

from auth import KeycloakAuth, AuthenticationError, UserInfo
from minio_client import MinIOClient


logger = logging.getLogger(__name__)

def register_auth_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register authentication tools with the MCP server."""

    @mcp.tool()
    async def minio_login(username: str, password: str) -> str:
        """
        Authenticate with MinIO using Keycloak credentials.

        Args:
            username: User's username for Keycloak authentication
            password: User's password for Keycloak authentication

        Returns:
            Login status message with token information and user details
        """
        try:
            # Authenticate with Keycloak
            token_info = await client.auth.login(username, password)

            # Set token for MinIO client
            client.set_auth_token(token_info.access_token)

            # Get user information
            user_info = await client.auth.validate_token(token_info.access_token)

            # Format response
            expires_in_mins = token_info.expires_in // 60
            role_summary = ", ".join(user_info.roles[:3])  # Show first 3 roles
            if len(user_info.roles) > 3:
                role_summary += f" (+{len(user_info.roles) - 3} more)"

            return (
                f"✅ Login successful!\n"
                f"User: {user_info.username}\n"
                f"Email: {user_info.email or 'N/A'}\n"
                f"Roles: [{role_summary}]\n"
                f"Token expires in: {expires_in_mins} minutes\n"
                f"Access Level: {'Admin' if 'admin' in user_info.roles else 'User'}"
            )

        except AuthenticationError as e:
            logger.error(f"Authentication failed for user {username}: {str(e)}")
            return f"❌ Login failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            return f"❌ Login failed due to unexpected error: {str(e)}"

    @mcp.tool()
    async def minio_refresh_token(refresh_token: str) -> str:
        """
        Refresh authentication token using refresh token.

        Args:
            refresh_token: Valid refresh token from previous authentication

        Returns:
            Token refresh status message with new token information
        """
        try:
            # Refresh token
            token_info = await client.auth.refresh_token(refresh_token)

            # Update MinIO client with new token
            client.set_auth_token(token_info.access_token)

            # Get updated user information
            user_info = await client.auth.validate_token(token_info.access_token)

            expires_in_mins = token_info.expires_in // 60

            return (
                f"✅ Token refreshed successfully!\n"
                f"User: {user_info.username}\n"
                f"New token expires in: {expires_in_mins} minutes\n"
                f"Status: Ready for MinIO operations"
            )

        except AuthenticationError as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return f"❌ Token refresh failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {str(e)}")
            return f"❌ Token refresh failed due to unexpected error: {str(e)}"

    @mcp.tool()
    async def minio_get_user_info() -> str:
        """
        Get current authenticated user information.

        Returns:
            Current user details including roles and permissions
        """
        try:
            # Get current user from auth cache
            user_info = await client.auth.get_current_user()

            if not user_info:
                return "❌ No authenticated user found. Please login first using minio_login."

            # Get current token info
            token_info = await client.auth.get_current_token()

            if token_info and client.auth.is_token_expired(token_info):
                return "⚠️ Authentication token has expired. Please refresh token or login again."

            # Format detailed user information
            realm_roles = ", ".join(user_info.realm_roles) if user_info.realm_roles else "None"

            client_roles_summary = []
            for client, roles in user_info.client_roles.items():
                if roles:
                    client_roles_summary.append(f"{client}: {', '.join(roles)}")

            client_roles_str = "\n  ".join(client_roles_summary) if client_roles_summary else "None"

            # Determine permission level
            permission_level = "Read-Only"
            if any(role in ["admin", "system-admin", "administrator"] for role in user_info.roles):
                permission_level = "Administrator"
            elif any(role in ["manager", "org-admin"] for role in user_info.roles):
                permission_level = "Manager"
            elif any(role in ["user", "operator"] for role in user_info.roles):
                permission_level = "Standard User"

            time_left = ""
            if token_info:
                remaining_mins = max(0, int((token_info.expires_at - __import__('time').time()) / 60))
                time_left = f"\nToken expires in: {remaining_mins} minutes"

            return (
                f"👤 Current User Information:\n"
                f"Username: {user_info.username}\n"
                f"Email: {user_info.email or 'Not provided'}\n"
                f"Permission Level: {permission_level}\n"
                f"Total Roles: {len(user_info.roles)}\n"
                f"Realm Roles: {realm_roles}\n"
                f"Client Roles:\n  {client_roles_str}"
                f"{time_left}\n"
                f"Status: {'🟢 Active' if token_info and not client.auth.is_token_expired(token_info) else '🔴 Expired'}"
            )

        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return f"❌ Failed to get user information: {str(e)}"

    @mcp.tool()
    async def minio_check_auth_status() -> str:
        """
        Check current authentication status and token validity.

        Returns:
            Authentication status information
        """
        try:
            token_info = await client.auth.get_current_token()
            user_info = await client.auth.get_current_user()

            if not token_info or not user_info:
                return (
                    "🔴 Not Authenticated\n"
                    "Status: No active session\n"
                    "Action Required: Please login using minio_login"
                )

            is_expired = client.auth.is_token_expired(token_info)

            if is_expired:
                return (
                    "⚠️ Authentication Expired\n"
                    f"User: {user_info.username}\n"
                    "Status: Token expired\n"
                    "Action Required: Use minio_refresh_token or login again"
                )

            remaining_time = int((token_info.expires_at - __import__('time').time()) / 60)

            # Test MinIO API connectivity
            api_health = await client.health_check()

            return (
                f"🟢 Authentication Active\n"
                f"User: {user_info.username}\n"
                f"Token valid for: {remaining_time} minutes\n"
                f"MinIO API: {'🟢 Connected' if api_health else '🔴 Unreachable'}\n"
                f"Status: Ready for operations"
            )

        except Exception as e:
            logger.error(f"Error checking auth status: {str(e)}")
            return f"❌ Auth status check failed: {str(e)}"

    @mcp.tool()
    async def minio_debug_token() -> str:
        """
        Debug tool to show current JWT token information.
        
        Returns:
            Current token details for debugging purposes
        """
        try:
            # Get current token from auth
            token_info = await client.auth.get_current_token()
            
            # Get current token from client
            client_token = client._current_token
            
            if not token_info and not client_token:
                return "❌ No token found in either auth or client"
            
            result = "🔍 JWT Token Debug Information:\n\n"
            
            if token_info:
                result += f"Auth Token Info:\n"
                result += f"- Has access_token: {'Yes' if hasattr(token_info, 'access_token') else 'No'}\n"
                if hasattr(token_info, 'access_token'):
                    token_preview = token_info.access_token[:50] + "..." if len(token_info.access_token) > 50 else token_info.access_token
                    result += f"- Token preview: {token_preview}\n"
                result += f"- Expires at: {getattr(token_info, 'expires_at', 'Unknown')}\n"
            else:
                result += "Auth Token Info: None\n"
            
            result += f"\nClient Token:\n"
            if client_token:
                token_preview = client_token[:50] + "..." if len(client_token) > 50 else client_token
                result += f"- Token preview: {token_preview}\n"
                result += f"- Length: {len(client_token)}\n"
            else:
                result += "- No token set in client\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in debug token: {str(e)}")
            return f"❌ Debug token failed: {str(e)}"