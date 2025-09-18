"""MinIO MCP Server - Main entry point."""

import asyncio
import logging
import sys
from typing import Optional

from fastmcp import FastMCP

from config import get_config
from auth import KeycloakAuth
from minio_client import MinIOClient
from utils import setup_logging

# Import tool registration functions
from tools.auth_tools import register_auth_tools
from tools.health_tools import register_health_tools
from tools.bucket_tools import register_bucket_tools
from tools.object_tools import register_object_tools
from tools.user_tools import register_user_tools
from tools.policy_tools import register_policy_tools


logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """
    Create and configure the FastMCP server with all MinIO tools.

    Returns:
        Configured FastMCP server instance
    """
    # Get configuration
    config = get_config()

    # Set up logging
    setup_logging(config.log_level)

    # Create MCP server with metadata
    mcp = FastMCP(
        name=config.mcp_server_name,
        instructions=(
            "This server provides comprehensive MinIO object storage management capabilities:\n\n"
            "🔐 AUTHENTICATION (4 tools):\n"
            "- minio_login: Authenticate with username/password\n"
            "- minio_refresh_token: Refresh JWT authentication token\n"
            "- minio_get_user_info: Get current user details and permissions\n"
            "- minio_check_auth_status: Check authentication status and token validity\n\n"
            "🏥 HEALTH MONITORING (4 tools):\n"
            "- minio_health_check: Basic health status\n"
            "- minio_ready_check: Service readiness with component details\n"
            "- minio_live_check: Liveness probe\n"
            "- minio_detailed_health: Comprehensive system health report\n\n"
            "📦 BUCKET MANAGEMENT (6 tools):\n"
            "- minio_list_buckets: List all buckets with pagination\n"
            "- minio_create_bucket: Create new bucket with region support\n"
            "- minio_get_bucket_info: Get detailed bucket information\n"
            "- minio_delete_bucket: Delete empty bucket\n"
            "- minio_get_bucket_policy: Retrieve bucket access policy\n"
            "- minio_set_bucket_policy: Set/update bucket access policy\n\n"
            "📄 OBJECT OPERATIONS (8 tools):\n"
            "- minio_list_objects: List objects with prefix filtering\n"
            "- minio_upload_object: Upload content as object\n"
            "- minio_download_object: Download object content\n"
            "- minio_get_object_info: Get object metadata without download\n"
            "- minio_delete_object: Delete single object\n"
            "- minio_copy_object: Copy object between locations\n"
            "- minio_bulk_delete: Delete multiple objects\n"
            "- minio_generate_presigned: Generate temporary access URLs\n\n"
            "👤 USER MANAGEMENT (7 tools):\n"
            "- minio_list_users: List all users with status\n"
            "- minio_create_user: Create new user with group assignment\n"
            "- minio_get_user: Get detailed user information\n"
            "- minio_update_user: Update user details and groups\n"
            "- minio_delete_user: Remove user and revoke access\n"
            "- minio_get_user_policies: List user policy assignments\n"
            "- minio_assign_user_policy: Assign policy to user\n\n"
            "📋 POLICY MANAGEMENT (6 tools):\n"
            "- minio_list_policies: List all IAM policies\n"
            "- minio_create_policy: Create new IAM policy\n"
            "- minio_get_policy: Get policy document details\n"
            "- minio_update_policy: Update existing policy\n"
            "- minio_delete_policy: Remove policy (if not assigned)\n"
            "- minio_validate_policy: Validate policy document\n\n"
            "⚠️ IMPORTANT USAGE NOTES:\n"
            "1. Start with minio_login to authenticate before using other tools\n"
            "2. Use minio_check_auth_status to verify your session is active\n"
            "3. Refresh tokens with minio_refresh_token when they expire\n"
            "4. All operations require appropriate permissions based on your role\n"
            "5. Bucket names must follow S3 naming conventions\n"
            "6. Large operations support pagination via limit parameters\n"
            "7. Policy documents must be valid IAM JSON format\n\n"
            "🚀 QUICK START:\n"
            "1. minio_login('username', 'password')\n"
            "2. minio_health_check() - verify server connectivity\n"
            "3. minio_list_buckets() - see available buckets\n"
            "4. Use bucket and object tools as needed\n\n"
            "For detailed help on any tool, the tool descriptions include parameter information and examples."
        )
    )

    # Create shared instances
    auth = KeycloakAuth()
    client = MinIOClient(auth)

    # Register all tool categories
    register_auth_tools(mcp, client)
    register_health_tools(mcp, client)
    register_bucket_tools(mcp, client)
    register_object_tools(mcp, client)
    register_user_tools(mcp, client)
    register_policy_tools(mcp, client)

    # Add resource endpoints for documentation
    @mcp.resource("minio://docs/authentication")
    async def get_auth_docs() -> str:
        """Documentation for MinIO authentication tools."""
        return """
# MinIO Authentication Guide

## Overview
The MinIO MCP Server uses Keycloak for JWT-based authentication. You must authenticate before using other tools.

## Authentication Flow
1. **Login**: Use `minio_login(username, password)` with your Keycloak credentials
2. **Check Status**: Use `minio_check_auth_status()` to verify your session
3. **Get User Info**: Use `minio_get_user_info()` to see your permissions
4. **Refresh Token**: Use `minio_refresh_token(refresh_token)` when tokens expire

## Role-Based Access
- **SystemAdmin**: Full access to all operations
- **OrgAdmin**: Organization-level management
- **User**: Basic bucket/object operations
- **ReadOnly**: List and read operations only

## Token Management
- Tokens expire after a configured time (typically 1 hour)
- Refresh tokens can be used to get new access tokens
- The system will automatically attempt token refresh on 401 errors

## Example Usage
```
# Authenticate
result = minio_login("admin", "password123")

# Check your status
status = minio_check_auth_status()

# Get your user information
info = minio_get_user_info()
```
"""

    @mcp.resource("minio://docs/bucket-operations")
    async def get_bucket_docs() -> str:
        """Documentation for MinIO bucket operations."""
        return """
# MinIO Bucket Operations Guide

## Overview
Buckets are containers for objects in MinIO. This guide covers bucket management operations.

## Bucket Naming Rules
- 3-63 characters long
- Lowercase letters, numbers, hyphens, and dots only
- Cannot start/end with hyphens or dots
- Cannot be formatted as IP address
- Must be globally unique within the MinIO instance

## Operations

### List Buckets
```
# List all buckets
buckets = minio_list_buckets()

# List with pagination
buckets = minio_list_buckets(limit=50)
```

### Create Bucket
```
# Create bucket in default region
result = minio_create_bucket("my-data-bucket")

# Create bucket in specific region
result = minio_create_bucket("my-data-bucket", "us-west-2")
```

### Get Bucket Information
```
# Get detailed bucket info
info = minio_get_bucket_info("my-data-bucket")
```

### Bucket Policies
```
# Get current policy
policy = minio_get_bucket_policy("my-data-bucket")

# Set new policy (JSON string)
policy_doc = '{"Version":"2012-10-17","Statement":[...]}'
result = minio_set_bucket_policy("my-data-bucket", policy_doc)
```

### Delete Bucket
```
# Delete empty bucket
result = minio_delete_bucket("my-data-bucket")
```

**Note**: Buckets must be empty before deletion.
"""

    @mcp.resource("minio://docs/object-operations")
    async def get_object_docs() -> str:
        """Documentation for MinIO object operations."""
        return """
# MinIO Object Operations Guide

## Overview
Objects are files stored in MinIO buckets. This guide covers object management operations.

## Object Naming
- Can be up to 1024 characters
- Can contain any Unicode characters except control characters
- Forward slashes create virtual folder structure

## Operations

### List Objects
```
# List all objects in bucket
objects = minio_list_objects("my-bucket")

# List with prefix filter
objects = minio_list_objects("my-bucket", prefix="documents/")

# List with pagination
objects = minio_list_objects("my-bucket", limit=50)
```

### Upload Object
```
# Upload text content
result = minio_upload_object(
    bucket="my-bucket",
    object_name="example.txt",
    content="Hello, World!",
    content_type="text/plain"
)
```

### Download Object
```
# Download object content
content = minio_download_object("my-bucket", "example.txt")
```

### Object Information
```
# Get metadata without downloading
info = minio_get_object_info("my-bucket", "example.txt")
```

### Copy Object
```
# Copy object to new location
result = minio_copy_object(
    src_bucket="source-bucket",
    src_object="file.txt",
    dst_bucket="destination-bucket",
    dst_object="copied-file.txt"
)
```

### Delete Objects
```
# Delete single object
result = minio_delete_object("my-bucket", "file.txt")

# Delete multiple objects
result = minio_bulk_delete("my-bucket", ["file1.txt", "file2.txt"])
```

### Presigned URLs
```
# Generate temporary access URL (1 hour)
url = minio_generate_presigned("my-bucket", "file.txt", expires_in=3600)
```
"""

    @mcp.resource("minio://docs/user-management")
    async def get_user_docs() -> str:
        """Documentation for MinIO user management."""
        return """
# MinIO User Management Guide

## Overview
Manage MinIO users, groups, and permissions. Requires administrative privileges.

## User Operations

### List Users
```
# List all users
users = minio_list_users()

# List with pagination
users = minio_list_users(limit=50)
```

### Create User
```
# Create user with password
result = minio_create_user("newuser", "securepassword123")

# Create user with groups
result = minio_create_user("newuser", "securepassword123", groups=["developers"])
```

### Get User Information
```
# Get detailed user info
info = minio_get_user("username")
```

### Update User
```
# Update user information (JSON string)
update_data = '{"email": "user@example.com", "groups": ["developers", "admins"]}'
result = minio_update_user("username", update_data)
```

### Delete User
```
# Remove user
result = minio_delete_user("username")
```

### User Policies
```
# Get user's policies
policies = minio_get_user_policies("username")

# Assign policy to user
result = minio_assign_user_policy("username", "readwrite-policy")
```

## Validation Rules
- Username: 3-64 characters, alphanumeric plus hyphens, underscores, dots
- Password: Minimum 8 characters
- Cannot start/end with hyphens
"""

    @mcp.resource("minio://docs/policy-management")
    async def get_policy_docs() -> str:
        """Documentation for MinIO policy management."""
        return """
# MinIO Policy Management Guide

## Overview
Policies define permissions for users and applications. Uses IAM-compatible JSON format.

## Policy Operations

### List Policies
```
# List all policies
policies = minio_list_policies()

# List with pagination
policies = minio_list_policies(limit=50)
```

### Create Policy
```
# Create new policy (IAM JSON format)
policy_doc = '''{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::my-bucket/*"]
        }
    ]
}'''
result = minio_create_policy("readonly-policy", policy_doc)
```

### Get Policy
```
# Get policy details
policy = minio_get_policy("readonly-policy")
```

### Update Policy
```
# Update existing policy
updated_doc = '{"Version":"2012-10-17","Statement":[...]}'
result = minio_update_policy("readonly-policy", updated_doc)
```

### Delete Policy
```
# Remove policy (must not be assigned to users)
result = minio_delete_policy("unused-policy")
```

### Validate Policy
```
# Validate policy without creating
validation = minio_validate_policy(policy_doc)
```

## Policy Structure
- **Version**: Always "2012-10-17"
- **Statement**: Array of permission statements
- **Effect**: "Allow" or "Deny"
- **Action**: Permissions (e.g., "s3:GetObject", "s3:*")
- **Resource**: Target resources (ARN format)

## Common Actions
- `s3:GetObject` - Download objects
- `s3:PutObject` - Upload objects
- `s3:DeleteObject` - Delete objects
- `s3:ListBucket` - List bucket contents
- `s3:*` - Full access
"""

    logger.info(f"Created MCP server '{config.mcp_server_name}' v{config.mcp_server_version}")
    logger.info("Registered 34 MinIO tools across 6 categories")

    return mcp


async def main():
    """Main entry point for the MinIO MCP Server."""
    try:
        # Create and run the MCP server
        mcp = create_mcp_server()

        logger.info("Starting MinIO MCP Server...")
        logger.info("Server ready to accept connections")

        # Run the server
        await mcp.run()

    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping server...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("MinIO MCP Server stopped")


if __name__ == "__main__":
    # Run the server directly without asyncio.run() for stdio mode
    mcp = create_mcp_server()
    mcp.run()