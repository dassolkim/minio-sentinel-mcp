"""Policy management tools for MinIO MCP Server."""

import logging
import json
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from minio_client import MinIOClient, MinIOAPIError


logger = logging.getLogger(__name__)


def register_policy_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register policy management tools with the MCP server."""

    @mcp.tool()
    async def minio_list_policies(limit: int = 100) -> str:
        """
        List all MinIO policies with pagination.

        Args:
            limit: Maximum number of policies to return (default: 100, max: 1000)

        Returns:
            Formatted list of policies with basic information
        """
        try:
            if limit < 1 or limit > 1000:
                return "❌ Error: limit must be between 1 and 1000"

            response = await client.get("/api/v1/policies", params={"limit": limit})

            if response.success:
                policies_data = response.data

                if isinstance(policies_data, dict) and "policies" in policies_data:
                    policies = policies_data["policies"]
                    total_count = policies_data.get("total", len(policies))
                elif isinstance(policies_data, list):
                    policies = policies_data
                    total_count = len(policies)
                else:
                    return f"✅ No policies found\nTotal: 0 policies"

                if not policies:
                    return f"✅ No policies found\nTotal: 0 policies"

                # Format policy list
                policy_lines = []
                for policy in policies:
                    if isinstance(policy, dict):
                        name = policy.get("name", "unknown")
                        description = policy.get("description", "N/A")
                        type_info = policy.get("type", "custom")
                        created = policy.get("created_date", policy.get("created", "unknown"))
                        users_count = policy.get("users_count", policy.get("assigned_users", 0))

                        # Policy type icon
                        type_icon = "🏢" if type_info == "built-in" else "📋"

                        policy_lines.append(
                            f"  {type_icon} {name}\n"
                            f"    Type: {type_info}\n"
                            f"    Description: {description}\n"
                            f"    Assigned Users: {users_count}\n"
                            f"    Created: {created}"
                        )
                    else:
                        policy_lines.append(f"  📋 {policy}")

                policy_list = "\n".join(policy_lines)

                return (
                    f"✅ MinIO Policies (showing {len(policies)} of {total_count}):\n"
                    f"{policy_list}\n"
                    f"\n📊 Summary: {len(policies)} policies listed"
                    f"{f' (limited to {limit})' if len(policies) == limit else ''}"
                )

            else:
                return (
                    f"❌ Failed to list policies\n"
                    f"Status: {response.status_code}\n"
                    f"Error: {response.error}"
                )

        except MinIOAPIError as e:
            logger.error(f"List policies API error: {str(e)}")
            return f"❌ Failed to list policies: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error listing policies: {str(e)}")
            return f"❌ Unexpected error listing policies: {str(e)}"

    @mcp.tool()
    async def minio_create_policy(name: str, policy_document: str) -> str:
        """
        Create a new MinIO policy.

        Args:
            name: Policy name (must be unique)
            policy_document: Policy document in JSON format (IAM-style policy)

        Returns:
            Policy creation status with details
        """
        try:
            if not name:
                return "❌ Error: Policy name is required"

            if not policy_document:
                return "❌ Error: Policy document is required"

            if len(name) < 2 or len(name) > 128:
                return "❌ Error: Policy name must be between 2 and 128 characters"

            # Validate policy name format (simplified)
            if not name.replace("-", "").replace("_", "").isalnum():
                return "❌ Error: Policy name can only contain letters, numbers, hyphens, and underscores"

            # Parse policy document
            try:
                policy_dict = json.loads(policy_document)
            except json.JSONDecodeError as e:
                return f"❌ Error: Invalid JSON policy document: {str(e)}"

            # Validate basic policy structure
            if not isinstance(policy_dict, dict):
                return "❌ Error: Policy document must be a JSON object"

            if "Version" not in policy_dict:
                return "❌ Error: Policy document must include a 'Version' field"

            if "Statement" not in policy_dict:
                return "❌ Error: Policy document must include a 'Statement' field"

            # Prepare policy data
            policy_data = {
                "name": name,
                "policy": policy_dict
            }

            response = await client.post("/api/v1/policies", json_data=policy_data)

            if response.success:
                policy_info = response.data

                if isinstance(policy_info, dict):
                    created_name = policy_info.get("name", name)
                    policy_id = policy_info.get("id", policy_info.get("policy_id", "N/A"))
                    created_date = policy_info.get("created_date", "just now")
                    version = policy_info.get("version", policy_dict.get("Version", "unknown"))

                    return (
                        f"✅ Policy created successfully!\n"
                        f"Name: {created_name}\n"
                        f"Policy ID: {policy_id}\n"
                        f"Version: {version}\n"
                        f"Created: {created_date}\n"
                        f"Status: Ready for assignment to users"
                    )
                else:
                    return (
                        f"✅ Policy '{name}' created successfully!\n"
                        f"Status: Ready for assignment to users"
                    )

            else:
                if response.status_code == 409:
                    return f"❌ Policy creation failed: Policy '{name}' already exists"
                elif response.status_code == 400:
                    return f"❌ Policy creation failed: Invalid policy document or name format"
                elif response.status_code == 403:
                    return f"❌ Policy creation failed: Insufficient permissions to create policies"
                else:
                    return (
                        f"❌ Failed to create policy '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Create policy API error: {str(e)}")
            return f"❌ Failed to create policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error creating policy: {str(e)}")
            return f"❌ Unexpected error creating policy: {str(e)}"

    @mcp.tool()
    async def minio_get_policy(name: str) -> str:
        """
        Get detailed information about a specific policy.

        Args:
            name: Policy name to get information for

        Returns:
            Detailed policy information including the policy document
        """
        try:
            if not name:
                return "❌ Error: Policy name is required"

            response = await client.get(f"/api/v1/policies/{name}")

            if response.success:
                policy_info = response.data

                if isinstance(policy_info, dict):
                    policy_name = policy_info.get("name", name)
                    description = policy_info.get("description", "N/A")
                    type_info = policy_info.get("type", "custom")
                    created = policy_info.get("created_date", policy_info.get("created", "unknown"))
                    users_count = policy_info.get("users_count", policy_info.get("assigned_users", 0))
                    policy_doc = policy_info.get("policy", policy_info.get("document", {}))

                    # Format policy document
                    if isinstance(policy_doc, dict):
                        formatted_policy = json.dumps(policy_doc, indent=2)
                    else:
                        formatted_policy = str(policy_doc)

                    # Policy type indicator
                    type_icon = "🏢" if type_info == "built-in" else "📋"

                    return (
                        f"{type_icon} Policy Information: {policy_name}\n"
                        f"═══════════════════════════════════\n"
                        f"Name: {policy_name}\n"
                        f"Type: {type_info}\n"
                        f"Description: {description}\n"
                        f"Assigned Users: {users_count}\n"
                        f"Created: {created}\n"
                        f"\n📜 Policy Document:\n"
                        f"─────────────────────────────────\n"
                        f"{formatted_policy}"
                    )
                else:
                    return (
                        f"📋 Policy Information: {name}\n"
                        f"Data: {policy_info}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Policy '{name}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to policy '{name}'"
                else:
                    return (
                        f"❌ Failed to get policy info for '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get policy info API error: {str(e)}")
            return f"❌ Failed to get policy info: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting policy info: {str(e)}")
            return f"❌ Unexpected error getting policy info: {str(e)}"

    @mcp.tool()
    async def minio_update_policy(name: str, policy_document: str) -> str:
        """
        Update an existing MinIO policy.

        Args:
            name: Policy name to update
            policy_document: New policy document in JSON format

        Returns:
            Policy update status
        """
        try:
            if not name:
                return "❌ Error: Policy name is required"

            if not policy_document:
                return "❌ Error: Policy document is required"

            # Parse policy document
            try:
                policy_dict = json.loads(policy_document)
            except json.JSONDecodeError as e:
                return f"❌ Error: Invalid JSON policy document: {str(e)}"

            # Validate basic policy structure
            if not isinstance(policy_dict, dict):
                return "❌ Error: Policy document must be a JSON object"

            if "Version" not in policy_dict:
                return "❌ Error: Policy document must include a 'Version' field"

            if "Statement" not in policy_dict:
                return "❌ Error: Policy document must include a 'Statement' field"

            # Prepare update data
            update_data = {
                "policy": policy_dict
            }

            response = await client.put(f"/api/v1/policies/{name}", json_data=update_data)

            if response.success:
                policy_info = response.data

                if isinstance(policy_info, dict):
                    updated_name = policy_info.get("name", name)
                    version = policy_info.get("version", policy_dict.get("Version", "unknown"))
                    updated_date = policy_info.get("updated_date", "just now")

                    return (
                        f"✅ Policy updated successfully!\n"
                        f"Name: {updated_name}\n"
                        f"Version: {version}\n"
                        f"Updated: {updated_date}\n"
                        f"Status: Policy changes are now active"
                    )
                else:
                    return (
                        f"✅ Policy '{name}' updated successfully!\n"
                        f"Status: Policy changes are now active"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Policy '{name}' not found"
                elif response.status_code == 400:
                    return f"❌ Invalid policy document for policy '{name}'"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to update policy '{name}'"
                else:
                    return (
                        f"❌ Failed to update policy '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Update policy API error: {str(e)}")
            return f"❌ Failed to update policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error updating policy: {str(e)}")
            return f"❌ Unexpected error updating policy: {str(e)}"

    @mcp.tool()
    async def minio_delete_policy(name: str) -> str:
        """
        Delete a MinIO policy.

        Args:
            name: Policy name to delete

        Returns:
            Policy deletion status
        """
        try:
            if not name:
                return "❌ Error: Policy name is required"

            response = await client.delete(f"/api/v1/policies/{name}")

            if response.success:
                return (
                    f"✅ Policy '{name}' deleted successfully!\n"
                    f"Status: Policy has been permanently removed\n"
                    f"Note: All user assignments for this policy have been revoked"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Policy '{name}' not found"
                elif response.status_code == 409:
                    return f"❌ Cannot delete policy '{name}': Policy is currently assigned to users"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to delete policy '{name}'"
                else:
                    return (
                        f"❌ Failed to delete policy '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Delete policy API error: {str(e)}")
            return f"❌ Failed to delete policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error deleting policy: {str(e)}")
            return f"❌ Unexpected error deleting policy: {str(e)}"

    @mcp.tool()
    async def minio_validate_policy(policy_document: str) -> str:
        """
        Validate a policy document without creating it.

        Args:
            policy_document: Policy document in JSON format to validate

        Returns:
            Policy validation results with any errors or warnings
        """
        try:
            if not policy_document:
                return "❌ Error: Policy document is required"

            # Parse policy document
            try:
                policy_dict = json.loads(policy_document)
            except json.JSONDecodeError as e:
                return f"❌ Policy Validation Failed: Invalid JSON format\nError: {str(e)}"

            # Prepare validation data
            validation_data = {
                "policy": policy_dict
            }

            response = await client.post("/api/v1/policies/validate", json_data=validation_data)

            if response.success:
                validation_result = response.data

                if isinstance(validation_result, dict):
                    is_valid = validation_result.get("valid", True)
                    errors = validation_result.get("errors", [])
                    warnings = validation_result.get("warnings", [])
                    suggestions = validation_result.get("suggestions", [])

                    result_lines = []

                    if is_valid and not errors:
                        result_lines.append("✅ Policy Validation: PASSED")
                        result_lines.append("Status: Policy document is valid and ready for use")
                    else:
                        result_lines.append("❌ Policy Validation: FAILED")

                    if errors:
                        result_lines.append(f"\n🚨 Errors ({len(errors)}):")
                        for i, error in enumerate(errors[:5], 1):  # Show first 5 errors
                            result_lines.append(f"  {i}. {error}")
                        if len(errors) > 5:
                            result_lines.append(f"  ... and {len(errors) - 5} more errors")

                    if warnings:
                        result_lines.append(f"\n⚠️ Warnings ({len(warnings)}):")
                        for i, warning in enumerate(warnings[:3], 1):  # Show first 3 warnings
                            result_lines.append(f"  {i}. {warning}")
                        if len(warnings) > 3:
                            result_lines.append(f"  ... and {len(warnings) - 3} more warnings")

                    if suggestions:
                        result_lines.append(f"\n💡 Suggestions ({len(suggestions)}):")
                        for i, suggestion in enumerate(suggestions[:3], 1):  # Show first 3 suggestions
                            result_lines.append(f"  {i}. {suggestion}")
                        if len(suggestions) > 3:
                            result_lines.append(f"  ... and {len(suggestions) - 3} more suggestions")

                    # Basic structural validation
                    structure_checks = []
                    if "Version" in policy_dict:
                        structure_checks.append("✅ Version field present")
                    else:
                        structure_checks.append("❌ Version field missing")

                    if "Statement" in policy_dict:
                        structure_checks.append("✅ Statement field present")
                        if isinstance(policy_dict["Statement"], list):
                            structure_checks.append(f"✅ {len(policy_dict['Statement'])} statement(s) found")
                        else:
                            structure_checks.append("❌ Statement field should be an array")
                    else:
                        structure_checks.append("❌ Statement field missing")

                    result_lines.append(f"\n🔍 Structure Check:")
                    result_lines.extend([f"  {check}" for check in structure_checks])

                    return "\n".join(result_lines)

                else:
                    return (
                        f"✅ Policy validation completed\n"
                        f"Result: {validation_result}"
                    )

            else:
                if response.status_code == 400:
                    return f"❌ Policy Validation Failed: {response.error}"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to validate policies"
                else:
                    return (
                        f"❌ Policy validation failed\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Validate policy API error: {str(e)}")
            return f"❌ Failed to validate policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error validating policy: {str(e)}")
            return f"❌ Unexpected error validating policy: {str(e)}"