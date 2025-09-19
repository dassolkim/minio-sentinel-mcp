#!/usr/bin/env python3
"""MinIO MCP SSE Server - Standard MCP SSE transport implementation."""

import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from config import get_config
from auth import KeycloakAuth
from minio_client import MinIOClient
from utils import setup_logging

# Import all tool registration functions
from tools.auth_tools import register_auth_tools
from tools.health_tools import register_health_tools
from tools.bucket_tools import register_bucket_tools
from tools.object_tools import register_object_tools
from tools.user_tools import register_user_tools
from tools.policy_tools import register_policy_tools

# Load environment variables
load_dotenv()

# Configuration
SSE_PORT = int(os.getenv("MCP_SSE_PORT", "8765"))

logger = logging.getLogger(__name__)


def create_mcp_sse_server() -> FastMCP:
    """
    Create and configure the FastMCP SSE server with all MinIO tools.
    
    Returns:
        Configured FastMCP server instance for SSE transport
    """
    # Get configuration
    config = get_config()
    
    # Set up logging
    setup_logging(config.log_level)
    
    # Create MCP server with metadata
    mcp = FastMCP(
        name=config.mcp_server_name,
        instructions=(
            "MinIO MCP Server via SSE Transport - Comprehensive object storage management\n\n"
            "🔐 AUTHENTICATION TOOLS (4):\n"
            "• minio_login - Authenticate with Keycloak credentials\n"
            "• minio_refresh_token - Refresh JWT authentication token\n"
            "• minio_get_user_info - Get current user details and permissions\n"
            "• minio_check_auth_status - Check authentication status\n\n"
            
            "🏥 HEALTH MONITORING TOOLS (4):\n"
            "• minio_health_check - Basic server health status\n"
            "• minio_ready_check - Service readiness with component details\n"
            "• minio_live_check - Liveness probe for monitoring\n"
            "• minio_detailed_health - Comprehensive system health report\n\n"
            
            "📦 BUCKET MANAGEMENT TOOLS (6):\n"
            "• minio_list_buckets - List all buckets with pagination support\n"
            "• minio_create_bucket - Create new bucket with region configuration\n"
            "• minio_get_bucket_info - Get detailed bucket information and metadata\n"
            "• minio_delete_bucket - Delete empty bucket (safety checks included)\n"
            "• minio_get_bucket_policy - Retrieve bucket access policy (IAM format)\n"
            "• minio_set_bucket_policy - Set/update bucket access policy\n\n"
            
            "📄 OBJECT OPERATIONS TOOLS (8):\n"
            "• minio_list_objects - List objects with prefix filtering and pagination\n"
            "• minio_upload_object - Upload content as object with metadata\n"
            "• minio_download_object - Download object content with streaming\n"
            "• minio_get_object_info - Get object metadata without downloading\n"
            "• minio_delete_object - Delete single object with confirmation\n"
            "• minio_copy_object - Copy object between buckets/locations\n"
            "• minio_bulk_delete - Delete multiple objects in batch operation\n"
            "• minio_generate_presigned - Generate temporary access URLs\n\n"
            
            "👤 USER MANAGEMENT TOOLS (7):\n"
            "• minio_list_users - List all users with status and permissions\n"
            "• minio_create_user - Create new user with group assignment\n"
            "• minio_get_user - Get detailed user information and metadata\n"
            "• minio_update_user - Update user details, groups, and settings\n"
            "• minio_delete_user - Remove user and revoke all access\n"
            "• minio_get_user_policies - List policies assigned to user\n"
            "• minio_assign_user_policy - Assign IAM policy to user\n\n"
            
            "📋 POLICY MANAGEMENT TOOLS (6):\n"
            "• minio_list_policies - List all IAM policies with details\n"
            "• minio_create_policy - Create new IAM policy (JSON format)\n"
            "• minio_get_policy - Get policy document and configuration\n"
            "• minio_update_policy - Update existing policy document\n"
            "• minio_delete_policy - Remove policy (if not assigned to users)\n"
            "• minio_validate_policy - Validate policy document before creation\n\n"
            
            "⚡ QUICK START WORKFLOW:\n"
            "1. minio_login('username', 'password') - Authenticate first\n"
            "2. minio_health_check() - Verify server connectivity\n"
            "3. minio_list_buckets() - See available storage buckets\n"
            "4. Use bucket and object tools for storage operations\n"
            "5. Use user/policy tools for access management (admin only)\n\n"
            
            "🔒 SECURITY NOTES:\n"
            "• All operations require valid JWT authentication\n"
            "• Role-based access control enforced (SystemAdmin, OrgAdmin, User, ReadOnly)\n"
            "• Bucket names must follow S3 naming conventions\n"
            "• Policy documents must be valid IAM JSON format\n"
            "• Sensitive operations require appropriate permissions\n\n"
            
            "📊 FEATURES:\n"
            "• Pagination support for large datasets\n"
            "• Comprehensive error handling and validation\n"
            "• Detailed logging for audit and debugging\n"
            "• Streaming support for large file operations\n"
            "• Presigned URL generation for secure temporary access\n"
            "• Bulk operations for efficiency\n\n"
            
            "Total: 35 specialized tools for complete MinIO management via MCP protocol."
        )
    )
    
    # Create shared instances
    auth = KeycloakAuth()
    client = MinIOClient(auth)
    
    # Register all tool categories with the MCP server
    logger.info("Registering MinIO tools with MCP SSE server...")
    
    register_auth_tools(mcp, client)
    logger.debug("✓ Registered authentication tools")
    
    register_health_tools(mcp, client)
    logger.debug("✓ Registered health monitoring tools")
    
    register_bucket_tools(mcp, client)
    logger.debug("✓ Registered bucket management tools")
    
    register_object_tools(mcp, client)
    logger.debug("✓ Registered object operations tools")
    
    register_user_tools(mcp, client)
    logger.debug("✓ Registered user management tools")
    
    register_policy_tools(mcp, client)
    logger.debug("✓ Registered policy management tools")
    
    logger.info(f"✅ Created MCP SSE server '{config.mcp_server_name}' v{config.mcp_server_version}")
    logger.info("📡 Registered 35 MinIO tools across 6 categories for SSE transport")
    
    return mcp


def validate_environment():
    """Validate required environment variables and configuration."""
    config = get_config()
    
    logger.info("🔍 Validating environment configuration...")
    
    # Check required configuration
    required_configs = [
        ('keycloak_server_url', config.keycloak_server_url),
        ('keycloak_realm', config.keycloak_realm),
        ('keycloak_client_id', config.keycloak_client_id),
        ('minio_api_base_url', config.minio_api_base_url),
    ]
    
    missing_configs = []
    for name, value in required_configs:
        if not value:
            missing_configs.append(name)
    
    if missing_configs:
        logger.error(f"❌ Missing required configuration: {', '.join(missing_configs)}")
        return False
    
    logger.info("✅ Environment configuration validated")
    return True


def main():
    """Main entry point for the MinIO MCP SSE Server."""
    print("🚀 MinIO MCP SSE Server")
    print("=" * 50)
    
    try:
        # Validate environment
        if not validate_environment():
            print("\n❌ Environment validation failed.")
            print("Please check your .env file configuration.")
            sys.exit(1)
        
        # Create the MCP SSE server
        mcp = create_mcp_sse_server()
        
        print(f"\n✅ Starting MCP SSE server on http://0.0.0.0:{SSE_PORT}")
        print("🔗 This server uses standard MCP SSE transport protocol")
        print("📱 Compatible with MCP clients like Langflow, Claude Desktop, etc.")
        print("\n💡 Usage Instructions:")
        print("  1. Connect your MCP client to this SSE endpoint")
        print("  2. Start with 'minio_login' to authenticate")
        print("  3. Use 'minio_health_check' to verify connectivity")
        print("  4. Explore available tools with your MCP client")
        
        print(f"\n🌐 Server URLs:")
        print(f"   Local:    http://127.0.0.1:{SSE_PORT}")
        print(f"   External: http://[your-ip]:{SSE_PORT}")
        print("⚠️  Note: This is for MCP clients only, not direct browser access")
        print("\n🔄 Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the SSE server using FastMCP's built-in SSE transport with external binding
        mcp.run(transport="sse", port=SSE_PORT, host="0.0.0.0")
        
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped by user")
        logger.info("MinIO MCP SSE Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        logger.error(f"MinIO MCP SSE Server error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        print("🔌 MinIO MCP SSE Server shutdown complete")


if __name__ == "__main__":
    main()
