"""Bucket management tools for MinIO MCP Server."""

import logging
import json
from typing import Any, Dict, Optional
from fastmcp import FastMCP

from minio_client import MinIOClient, MinIOAPIError


logger = logging.getLogger(__name__)


def register_bucket_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register bucket management tools with the MCP server."""

    @mcp.tool()
    async def minio_list_buckets(limit: int = 100) -> str:
        """
        List all MinIO buckets with pagination.

        Args:
            limit: Maximum number of buckets to return (default: 100, max: 1000)

        Returns:
            Formatted list of buckets with details
        """
        try:
            # Validate limit
            if limit < 1 or limit > 1000:
                return "❌ Error: limit must be between 1 and 1000"

            response = await client.get("/api/v1/buckets", params={"limit": limit})

            if response.success:
                buckets_data = response.data
                
                # Debug: Print actual response structure
                logger.info(f"Bucket response data type: {type(buckets_data)}")
                logger.info(f"Bucket response data: {buckets_data}")

                if isinstance(buckets_data, dict) and "data" in buckets_data:
                    # MinIO REST API returns data in "data" field
                    buckets = buckets_data["data"]
                    total_count = buckets_data.get("count", len(buckets))
                elif isinstance(buckets_data, dict) and "buckets" in buckets_data:
                    # Fallback for other API formats
                    buckets = buckets_data["buckets"]
                    total_count = buckets_data.get("total", len(buckets))
                elif isinstance(buckets_data, list):
                    buckets = buckets_data
                    total_count = len(buckets)
                else:
                    return f"✅ No buckets found\nTotal: 0 buckets"

                if not buckets:
                    return f"✅ No buckets found\nTotal: 0 buckets"

                # Format bucket list
                bucket_lines = []
                for bucket in buckets:
                    if isinstance(bucket, dict):
                        name = bucket.get("name", "unknown")
                        created = bucket.get("creation_date", bucket.get("created", "unknown"))
                        size = bucket.get("size", bucket.get("used_space", "unknown"))
                        objects = bucket.get("objects", bucket.get("object_count", "unknown"))

                        bucket_lines.append(
                            f"  📦 {name}\n"
                            f"    Created: {created}\n"
                            f"    Size: {size}\n"
                            f"    Objects: {objects}"
                        )
                    else:
                        bucket_lines.append(f"  📦 {bucket}")

                bucket_list = "\n".join(bucket_lines)

                return (
                    f"✅ MinIO Buckets (showing {len(buckets)} of {total_count}):\n"
                    f"{bucket_list}\n"
                    f"\n📊 Summary: {len(buckets)} buckets listed"
                    f"{f' (limited to {limit})' if len(buckets) == limit else ''}"
                )

            else:
                return (
                    f"❌ Failed to list buckets\n"
                    f"Status: {response.status_code}\n"
                    f"Error: {response.error}"
                )

        except MinIOAPIError as e:
            logger.error(f"List buckets API error: {str(e)}")
            return f"❌ Failed to list buckets: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error listing buckets: {str(e)}")
            return f"❌ Unexpected error listing buckets: {str(e)}"

    @mcp.tool()
    async def minio_create_bucket(name: str, region: str = "us-east-1") -> str:
        """
        Create a new MinIO bucket.

        Args:
            name: Bucket name (must be unique and follow naming conventions)
            region: AWS region for bucket (default: us-east-1)

        Returns:
            Bucket creation status
        """
        try:
            # Validate bucket name
            if not name or len(name) < 3 or len(name) > 63:
                return "❌ Error: Bucket name must be between 3 and 63 characters"

            # Basic name validation (simplified)
            if not name.replace("-", "").replace(".", "").isalnum():
                return "❌ Error: Bucket name can only contain letters, numbers, hyphens, and dots"

            if name.startswith("-") or name.endswith("-"):
                return "❌ Error: Bucket name cannot start or end with hyphens"

            request_data = {
                "name": name,
                "region": region
            }

            response = await client.post("/api/v1/buckets", json_data=request_data)

            if response.success:
                bucket_info = response.data

                if isinstance(bucket_info, dict):
                    bucket_name = bucket_info.get("name", name)
                    bucket_region = bucket_info.get("region", region)
                    created_date = bucket_info.get("creation_date", "just now")

                    return (
                        f"✅ Bucket created successfully!\n"
                        f"Name: {bucket_name}\n"
                        f"Region: {bucket_region}\n"
                        f"Created: {created_date}\n"
                        f"Status: Ready for object storage"
                    )
                else:
                    return (
                        f"✅ Bucket '{name}' created successfully!\n"
                        f"Region: {region}\n"
                        f"Status: Ready for object storage"
                    )

            else:
                error_msg = response.error or f"HTTP {response.status_code}"

                # Provide specific error messages for common issues
                if response.status_code == 409:
                    return f"❌ Bucket creation failed: Bucket '{name}' already exists"
                elif response.status_code == 400:
                    return f"❌ Bucket creation failed: Invalid bucket name or parameters"
                elif response.status_code == 403:
                    return f"❌ Bucket creation failed: Insufficient permissions"
                else:
                    return (
                        f"❌ Failed to create bucket '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {error_msg}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Create bucket API error: {str(e)}")
            return f"❌ Failed to create bucket: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error creating bucket: {str(e)}")
            return f"❌ Unexpected error creating bucket: {str(e)}"

    @mcp.tool()
    async def minio_get_bucket_info(name: str) -> str:
        """
        Get detailed information about a specific bucket.

        Args:
            name: Bucket name to get information for

        Returns:
            Detailed bucket information including metadata and statistics
        """
        try:
            if not name:
                return "❌ Error: Bucket name is required"

            response = await client.get(f"/api/v1/buckets/{name}")

            if response.success:
                bucket_info = response.data

                if isinstance(bucket_info, dict):
                    bucket_name = bucket_info.get("name", name)
                    creation_date = bucket_info.get("creation_date", bucket_info.get("created", "unknown"))
                    region = bucket_info.get("region", "unknown")
                    size = bucket_info.get("size", bucket_info.get("used_space", "unknown"))
                    objects = bucket_info.get("objects", bucket_info.get("object_count", "unknown"))
                    access = bucket_info.get("access", bucket_info.get("permission", "unknown"))
                    versioning = bucket_info.get("versioning", {})
                    encryption = bucket_info.get("encryption", {})

                    # Format versioning info
                    versioning_status = "unknown"
                    if isinstance(versioning, dict):
                        versioning_status = versioning.get("status", "disabled")
                    elif isinstance(versioning, bool):
                        versioning_status = "enabled" if versioning else "disabled"

                    # Format encryption info
                    encryption_status = "unknown"
                    if isinstance(encryption, dict):
                        encryption_status = encryption.get("status", "disabled")
                        if encryption_status == "enabled":
                            algorithm = encryption.get("algorithm", "unknown")
                            encryption_status = f"enabled ({algorithm})"
                    elif isinstance(encryption, bool):
                        encryption_status = "enabled" if encryption else "disabled"

                    return (
                        f"📦 Bucket Information: {bucket_name}\n"
                        f"═══════════════════════════════════\n"
                        f"Name: {bucket_name}\n"
                        f"Region: {region}\n"
                        f"Created: {creation_date}\n"
                        f"Size: {size}\n"
                        f"Objects: {objects}\n"
                        f"Access: {access}\n"
                        f"Versioning: {versioning_status}\n"
                        f"Encryption: {encryption_status}\n"
                        f"Status: Active"
                    )
                else:
                    return (
                        f"📦 Bucket Information: {name}\n"
                        f"Status: Active\n"
                        f"Data: {bucket_info}"
                    )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{name}' not found"
                elif response.status_code == 403:
                    return f"❌ Access denied to bucket '{name}'"
                else:
                    return (
                        f"❌ Failed to get bucket info for '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get bucket info API error: {str(e)}")
            return f"❌ Failed to get bucket info: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting bucket info: {str(e)}")
            return f"❌ Unexpected error getting bucket info: {str(e)}"

    @mcp.tool()
    async def minio_delete_bucket(name: str) -> str:
        """
        Delete a MinIO bucket (bucket must be empty).

        Args:
            name: Name of the bucket to delete

        Returns:
            Bucket deletion status
        """
        try:
            if not name:
                return "❌ Error: Bucket name is required"

            response = await client.delete(f"/api/v1/buckets/{name}")

            if response.success:
                return (
                    f"✅ Bucket '{name}' deleted successfully!\n"
                    f"Status: Bucket has been permanently removed\n"
                    f"Note: All bucket metadata and policies have been cleared"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{name}' not found"
                elif response.status_code == 409:
                    return f"❌ Cannot delete bucket '{name}': Bucket is not empty"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to delete bucket '{name}'"
                else:
                    return (
                        f"❌ Failed to delete bucket '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Delete bucket API error: {str(e)}")
            return f"❌ Failed to delete bucket: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error deleting bucket: {str(e)}")
            return f"❌ Unexpected error deleting bucket: {str(e)}"

    @mcp.tool()
    async def minio_get_bucket_policy(name: str) -> str:
        """
        Get the access policy for a specific bucket.

        Args:
            name: Bucket name to get policy for

        Returns:
            Bucket policy in JSON format or policy summary
        """
        try:
            if not name:
                return "❌ Error: Bucket name is required"

            response = await client.get(f"/api/v1/buckets/{name}/policy")

            if response.success:
                policy_data = response.data

                if isinstance(policy_data, dict):
                    # Format policy for readability
                    if "policy" in policy_data:
                        policy = policy_data["policy"]
                        if isinstance(policy, dict):
                            formatted_policy = json.dumps(policy, indent=2)
                        else:
                            formatted_policy = str(policy)
                    else:
                        formatted_policy = json.dumps(policy_data, indent=2)

                    return (
                        f"📋 Bucket Policy for '{name}':\n"
                        f"═══════════════════════════════════\n"
                        f"{formatted_policy}"
                    )
                else:
                    return (
                        f"📋 Bucket Policy for '{name}':\n"
                        f"═══════════════════════════════════\n"
                        f"{policy_data}"
                    )

            else:
                if response.status_code == 404:
                    return f"ℹ️ No policy found for bucket '{name}' (using default policy)"
                elif response.status_code == 403:
                    return f"❌ Access denied to bucket policy for '{name}'"
                else:
                    return (
                        f"❌ Failed to get bucket policy for '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Get bucket policy API error: {str(e)}")
            return f"❌ Failed to get bucket policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error getting bucket policy: {str(e)}")
            return f"❌ Unexpected error getting bucket policy: {str(e)}"

    @mcp.tool()
    async def minio_set_bucket_policy(name: str, policy: str) -> str:
        """
        Set or update the access policy for a specific bucket.

        Args:
            name: Bucket name to set policy for
            policy: Policy document in JSON format (as string)

        Returns:
            Policy update status
        """
        try:
            if not name:
                return "❌ Error: Bucket name is required"

            if not policy:
                return "❌ Error: Policy document is required"

            # Parse policy JSON
            try:
                policy_dict = json.loads(policy)
            except json.JSONDecodeError as e:
                return f"❌ Error: Invalid JSON policy format: {str(e)}"

            # Validate basic policy structure
            if not isinstance(policy_dict, dict):
                return "❌ Error: Policy must be a JSON object"

            if "Version" not in policy_dict:
                return "❌ Error: Policy must include a 'Version' field"

            request_data = {
                "policy": policy_dict
            }

            response = await client.put(f"/api/v1/buckets/{name}/policy", json_data=request_data)

            if response.success:
                return (
                    f"✅ Bucket policy updated successfully!\n"
                    f"Bucket: {name}\n"
                    f"Status: Policy has been applied\n"
                    f"Note: Changes may take a few moments to take effect"
                )

            else:
                if response.status_code == 404:
                    return f"❌ Bucket '{name}' not found"
                elif response.status_code == 400:
                    return f"❌ Invalid policy document for bucket '{name}'"
                elif response.status_code == 403:
                    return f"❌ Access denied: Insufficient permissions to set policy on bucket '{name}'"
                else:
                    return (
                        f"❌ Failed to set bucket policy for '{name}'\n"
                        f"Status: {response.status_code}\n"
                        f"Error: {response.error}"
                    )

        except MinIOAPIError as e:
            logger.error(f"Set bucket policy API error: {str(e)}")
            return f"❌ Failed to set bucket policy: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error setting bucket policy: {str(e)}")
            return f"❌ Unexpected error setting bucket policy: {str(e)}"