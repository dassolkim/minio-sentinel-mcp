"""User management tools for MinIO MCP Server."""

import logging
import json
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from minio_client import MinIOClient, MinIOAPIError


logger = logging.getLogger(__name__)


def register_user_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register user management tools with the MCP server."""

    @mcp.tool()
    async def minio_list_users(limit: int = 100) -> str:
        """
        List all MinIO users with pagination.

        Args:
            limit: Maximum number of users to return (default: 100, max: 1000)

        Returns:
            Formatted list of users with basic information
        """
        try:
            if limit < 1 or limit > 1000:
                return "❌ Error: limit must be between 1 and 1000"

            response = await client.get("/api/v1/users", params={"limit": limit})

            if response.success:
                users_data = response.data

                if isinstance(users_data, dict) and "users" in users_data:
                    users = users_data["users"]
                    total_count = users_data.get("total", len(users))
                elif isinstance(users_data, list):
                    users = users_data
                    total_count = len(users)
                else:
                    return f"✅ No users found\nTotal: 0 users"

                if not users:
                    return f"✅ No users found\nTotal: 0 users"

                # Format user list
                user_lines = []
                for user in users:
                    if isinstance(user, dict):
                        username = user.get("username", user.get("name", "unknown"))
                        email = user.get("email", "N/A")
                        status = user.get("status", user.get("enabled", "unknown"))
                        groups = user.get("groups", user.get("memberOf", []))
                        created = user.get("created_date", user.get("created", "unknown"))

                        # Format status
                        status_icon = "🟢" if status in [True, "enabled", "active"] else "🔴"
                        status_text = "Active" if status in [True, "enabled", "active"] else "Inactive"

                        # Format groups
                        groups_text = ", ".join(groups[:3]) if groups else "None"
                        if len(groups) > 3:
                            groups_text += f" (+{len(groups) - 3} more)"

                        user_lines.append(
                            f"  👤 {username}\n"
                            f"    Status: {status_icon} {status_text}\n"
                            f"    Email: {email}\n"
                            f"    Groups: {groups_text}\n"
                            f"    Created: {created}"
                        )
                    else:
                        user_lines.append(f"  👤 {user}")

                user_list = "\n".join(user_lines)

                return (
                    f"✅ MinIO Users (showing {len(users)} of {total_count}):\n"
                    f"{user_list}\n"
                    f"\n📊 Summary: {len(users)} users listed"
                    f"{f' (limited to {limit})' if len(users) == limit else ''}"
                )

            else:
                return (
                    f"❌ Failed to list users\n"
                    f"Status: {response.status_code}\n"
                    f"Error: {response.error}"
                )

        except MinIOAPIError as e:
            logger.error(f"List users API error: {str(e)}")
            return f"❌ Failed to list users: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error listing users: {str(e)}")
            return f"❌ Unexpected error listing users: {str(e)}"

    @mcp.tool()
    async def minio_create_user(username: str, password: str, groups: List[str] = None) -> str:
        """
        Create a new MinIO user.

        Args:
            username: Username for the new user (must be unique)
            password: Password for the new user (minimum 8 characters)
            groups: Optional list of groups to assign the user to

        Returns:
            User creation status with details
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            if not password:
                return "❌ Error: Password is required"

            if len(username) < 3 or len(username) > 64:
                return "❌ Error: Username must be between 3 and 64 characters"

            if len(password) < 8:
                return "❌ Error: Password must be at least 8 characters long"

            # Prepare user data
            user_data = {
                "username": username,
                "password": password
            }

            if groups:
                user_data["groups"] = groups

            response = await client.post("/api/v1/users", json_data=user_data)

            if response.success:
                user_info = response.data

                if isinstance(user_info, dict):
                    created_username = user_info.get("username", username)
                    user_id = user_info.get("id", user_info.get("user_id", "N/A"))
                    assigned_groups = user_info.get("groups", groups or [])
                    created_date = user_info.get("created_date", "just now")

                    groups_text = ", ".join(assigned_groups) if assigned_groups else "None"

                    return (
                        f"✅ User created successfully!\n"
                        f"Username: {created_username}\n"
                        f"User ID: {user_id}\n"
                        f"Groups: {groups_text}\n"
                        f"Created: {created_date}\n"
                        f"Status: Active and ready for access"
                    )
                else:
                    return (
                        f"✅ User '{username}' created successfully!\n"
                        f"Groups: {', '.join(groups) if groups else 'None'}\n"
                        f"Status: Active and ready for access"
                    )

            else:
                if response.status_code == 409:
                    return f"❌ User creation failed: Username '{username}' already exists"
                elif response.status_code == 400:
                    return f"❌ User creation failed: Invalid username or password format"
                elif response.status_code == 403:
                    return f"❌ User creation failed: Insufficient permissions to create users"
                else:
                    return (
                        f"❌ Failed to create user '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Create user API error: {str(e)}")
            return f"❌ Failed to create user: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error creating user: {str(e)}")
            return f"❌ Unexpected error creating user: {str(e)}"

    @mcp.tool()
    async def minio_get_user(username: str) -> str:
        """
        Get detailed information about a specific user.

        Args:
            username: Username to get information for

        Returns:
            Detailed user information including groups, policies, and metadata
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            response = await client.get(f"/api/v1/users/{username}")

            if response.success:
                user_info = response.data

                if isinstance(user_info, dict):
                    user_username = user_info.get("username", username)
                    email = user_info.get("email", "Not provided")
                    status = user_info.get("status", user_info.get("enabled", "unknown"))
                    groups = user_info.get("groups", user_info.get("memberOf", []))
                    policies = user_info.get("policies", [])
                    created = user_info.get("created_date", user_info.get("created", "unknown"))
                    last_login = user_info.get("last_login", "Never")
                    permissions = user_info.get("permissions", [])

                    # Format status
                    status_icon = "🟢" if status in [True, "enabled", "active"] else "🔴"
                    status_text = "Active" if status in [True, "enabled", "active"] else "Inactive"

                    # Format groups
                    groups_text = ", ".join(groups) if groups else "None"

                    # Format policies
                    policies_text = ", ".join(policies) if policies else "None"

                    # Format permissions
                    permissions_text = ", ".join(permissions[:5]) if permissions else "None"
                    if len(permissions) > 5:
                        permissions_text += f" (+{len(permissions) - 5} more)"

                    return (
                        f"👤 User Information: {user_username}\n"
                        f"═══════════════════════════════════\n"
                        f"Username: {user_username}\n"
                        f"Email: {email}\n"
                        f"Status: {status_icon} {status_text}\n"
                        f"Groups: {groups_text}\n"
                        f"Policies: {policies_text}\n"
                        f"Permissions: {permissions_text}\n"
                        f"Created: {created}\n"
                        f"Last Login: {last_login}"
                    )
                else:
                    return (
                        f"👤 User Information: {username}\n"
                        f"Status: Active\n"
                        f"Data: {user_info}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ User '{username}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to user information for '{username}'"
                else:
                    return (
                        f"❌ Failed to get user info for '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get user info API error: {str(e)}")
            return f"❌ Failed to get user info: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {str(e)}")
            return f"❌ Unexpected error getting user info: {str(e)}"

    @mcp.tool()
    async def minio_update_user(username: str, data: str) -> str:
        """
        Update user information (email, groups, status, etc.).

        Args:
            username: Username of the user to update
            data: JSON string containing update data (e.g., {"email": "new@email.com", "groups": ["group1"]})

        Returns:
            User update status
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            if not data:
                return "❌ Error: Update data is required"

            # Parse update data
            try:
                update_data = json.loads(data)
            except json.JSONDecodeError as e:
                return f"❌ Error: Invalid JSON update data: {str(e)}"

            if not isinstance(update_data, dict):
                return "❌ Error: Update data must be a JSON object"

            response = await client.put(f"/api/v1/users/{username}", json_data=update_data)

            if response.success:
                updated_info = response.data

                if isinstance(updated_info, dict):
                    updated_username = updated_info.get("username", username)
                    email = updated_info.get("email", "N/A")
                    groups = updated_info.get("groups", [])
                    status = updated_info.get("status", updated_info.get("enabled", "unknown"))

                    status_text = "Active" if status in [True, "enabled", "active"] else "Inactive"
                    groups_text = ", ".join(groups) if groups else "None"

                    return (
                        f"✅ User updated successfully!\n"
                        f"Username: {updated_username}\n"
                        f"Email: {email}\n"
                        f"Status: {status_text}\n"
                        f"Groups: {groups_text}\n"
                        f"Updated fields: {', '.join(update_data.keys())}"
                    )
                else:
                    return (
                        f"✅ User '{username}' updated successfully!\n"
                        f"Updated fields: {', '.join(update_data.keys())}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ User '{username}' not found"
                elif response.status_code == 400:
                    return f"❌ Invalid update data for user '{username}'"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to update user '{username}'"
                else:
                    return (
                        f"❌ Failed to update user '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Update user API error: {str(e)}")
            return f"❌ Failed to update user: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error updating user: {str(e)}")
            return f"❌ Unexpected error updating user: {str(e)}"

    @mcp.tool()
    async def minio_delete_user(username: str) -> str:
        """
        Delete a MinIO user.

        Args:
            username: Username of the user to delete

        Returns:
            User deletion status
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            response = await client.delete(f"/api/v1/users/{username}")

            if response.success:
                return (
                    f"✅ User '{username}' deleted successfully!\n"
                    f"Status: User has been permanently removed\n"
                    f"Note: All user data and access permissions have been revoked"
                )

            else:
                if response.status_code == 404:
                    return f"❌ User '{username}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to delete user '{username}'"
                elif response.status_code == 409:
                    return f"❌ Cannot delete user '{username}': User may be referenced by active sessions or policies"
                else:
                    return (
                        f"❌ Failed to delete user '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Delete user API error: {str(e)}")
            return f"❌ Failed to delete user: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error deleting user: {str(e)}")
            return f"❌ Unexpected error deleting user: {str(e)}"

    @mcp.tool()
    async def minio_get_user_policies(username: str) -> str:
        """
        Get all policies assigned to a specific user.

        Args:
            username: Username to get policies for

        Returns:
            List of policies assigned to the user with details
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            response = await client.get(f"/api/v1/users/{username}/policies")

            if response.success:
                policies_data = response.data

                if isinstance(policies_data, dict) and "policies" in policies_data:
                    policies = policies_data["policies"]
                elif isinstance(policies_data, list):
                    policies = policies_data
                else:
                    return f"ℹ️ No policies assigned to user '{username}'"

                if not policies:
                    return f"ℹ️ No policies assigned to user '{username}'"

                # Format policy list
                policy_lines = []
                for policy in policies:
                    if isinstance(policy, dict):
                        name = policy.get("name", "unknown")
                        description = policy.get("description", "N/A")
                        type_info = policy.get("type", "unknown")
                        assigned_date = policy.get("assigned_date", policy.get("created", "unknown"))

                        policy_lines.append(
                            f"  📋 {name}\n"
                            f"    Type: {type_info}\n"
                            f"    Description: {description}\n"
                            f"    Assigned: {assigned_date}"
                        )
                    else:
                        policy_lines.append(f"  📋 {policy}")

                policy_list = "\n".join(policy_lines)

                return (
                    f"📋 Policies for user '{username}':\n"
                    f"{policy_list}\n"
                    f"\n📊 Summary: {len(policies)} policies assigned"
                )

            else:
                if response.status_code == 404:
                    return f"❌ User '{username}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to policies for user '{username}'"
                else:
                    return (
                        f"❌ Failed to get policies for user '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get user policies API error: {str(e)}")
            return f"❌ Failed to get user policies: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting user policies: {str(e)}")
            return f"❌ Unexpected error getting user policies: {str(e)}"

    @mcp.tool()
    async def minio_assign_user_policy(username: str, policy_name: str) -> str:
        """
        Assign a policy to a user.

        Args:
            username: Username to assign policy to
            policy_name: Name of the policy to assign

        Returns:
            Policy assignment status
        """
        try:
            if not username:
                return "❌ Error: Username is required"

            if not policy_name:
                return "❌ Error: Policy name is required"

            assignment_data = {
                "policy": policy_name
            }

            response = await client.post(f"/api/v1/users/{username}/policies", json_data=assignment_data)

            if response.success:
                assignment_info = response.data

                if isinstance(assignment_info, dict):
                    assigned_policy = assignment_info.get("policy", policy_name)
                    user = assignment_info.get("username", username)
                    assigned_date = assignment_info.get("assigned_date", "just now")

                    return (
                        f"✅ Policy assigned successfully!\n"
                        f"User: {user}\n"
                        f"Policy: {assigned_policy}\n"
                        f"Assigned: {assigned_date}\n"
                        f"Status: Policy is now active for this user"
                    )
                else:
                    return (
                        f"✅ Policy '{policy_name}' assigned to user '{username}'!\n"
                        f"Status: Policy is now active for this user"
                    )

            else:
                if response.status_code == 404:
                    if "user" in response.error.lower():
                        return f"❌ User '{username}' not found"
                    else:
                        return f"❌ Policy '{policy_name}' not found"
                elif response.status_code == 409:
                    return f"❌ Policy '{policy_name}' is already assigned to user '{username}'"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to assign policies"
                else:
                    return (
                        f"❌ Failed to assign policy '{policy_name}' to user '{username}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Assign user policy API error: {str(e)}")
            return f"❌ Failed to assign user policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error assigning user policy: {str(e)}")
            return f"❌ Unexpected error assigning user policy: {str(e)}"