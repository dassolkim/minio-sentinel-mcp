"""MinIO MCP HTTP Server - HTTP transport implementation."""

import asyncio
import logging
import sys
import os
import uvicorn
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from contextlib import asynccontextmanager

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
from auth import KeycloakAuth
from minio_client import MinIOClient
from utils import setup_logging
from minio_mcp_server import create_mcp_server

# Import deployment modules
from sse_handler import sse_manager
from monitoring import metrics_collector
from security import security_manager

logger = logging.getLogger(__name__)


class MCPHTTPServer:
    """HTTP wrapper for MCP Server with SSE support."""
    
    def __init__(self):
        self.config = get_config()
        self.mcp_server = create_mcp_server()
        
    async def handle_mcp_request(self, request_data: dict) -> dict:
        """Handle MCP request and return response."""
        try:
            # Process MCP request through the FastMCP server
            # This is a simplified implementation - you may need to adapt based on FastMCP's HTTP transport API
            response = await self.mcp_server.handle_request(request_data)
            return response
        except Exception as e:
            logger.error(f"Error handling MCP request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MinIO MCP HTTP Server...")
    yield
    # Shutdown
    logger.info("Shutting down MinIO MCP HTTP Server...")


def create_http_app() -> FastAPI:
    """Create FastAPI application with MCP endpoints."""
    
    config = get_config()
    setup_logging(config.log_level)
    
    app = FastAPI(
        title="MinIO MCP HTTP Server",
        description="HTTP transport for MinIO MCP Server with SSE support",
        version=config.mcp_server_version,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize MCP HTTP server
    mcp_http_server = MCPHTTPServer()
    
    @app.get("/")
    async def root():
        """Root endpoint with server information."""
        return {
            "name": config.mcp_server_name,
            "version": config.mcp_server_version,
            "status": "running",
            "transport": "http",
            "endpoints": {
                "mcp": "/mcp",
                "sse": "/sse",
                "health": "/health",
                "docs": "/docs"
            }
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}
    
    @app.get("/debug/connections")
    async def debug_connections():
        """Debug endpoint to show active SSE connections."""
        # This would be implemented with a proper connection manager
        # For now, return basic info
        return {
            "active_connections": 0,  # Would be tracked by connection manager
            "server_uptime": asyncio.get_event_loop().time(),
            "last_connection_attempt": "tracked in logs"
        }
    
    @app.post("/mcp")
    async def handle_mcp_request(request_data: dict):
        """Handle MCP JSON-RPC requests."""
        try:
            response = await mcp_http_server.handle_mcp_request(request_data)
            return response
        except Exception as e:
            logger.error(f"MCP request error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/sse")
    async def sse_endpoint(request: Request):
        """Server-Sent Events endpoint for real-time communication."""
        import json
        import uuid
        
        connection_id = str(uuid.uuid4())
        logger.info(f"New SSE connection: {connection_id} from {request.client.host}")
        
        async def event_stream():
            """Generate SSE events."""
            try:
                # Send initial connection event with proper JSON
                initial_data = {
                    "type": "connected",
                    "connection_id": connection_id,
                    "timestamp": asyncio.get_event_loop().time(),
                    "message": "Connected to MinIO MCP Server"
                }
                yield f"data: {json.dumps(initial_data)}\n\n"
                
                # Send server info
                server_info = {
                    "type": "server_info",
                    "connection_id": connection_id,
                    "server_name": config.mcp_server_name,
                    "server_version": config.mcp_server_version,
                    "available_tools": 34,  # Update based on actual tool count
                    "timestamp": asyncio.get_event_loop().time()
                }
                yield f"data: {json.dumps(server_info)}\n\n"
                
                # Keep connection alive with more frequent heartbeat
                heartbeat_count = 0
                while True:
                    await asyncio.sleep(5)  # Very frequent heartbeat for debugging
                    heartbeat_count += 1
                    
                    heartbeat_data = {
                        "type": "heartbeat",
                        "connection_id": connection_id,
                        "heartbeat_count": heartbeat_count,
                        "timestamp": asyncio.get_event_loop().time(),
                        "server_time": asyncio.get_event_loop().time()
                    }
                    
                    # Add explicit flush
                    yield f"data: {json.dumps(heartbeat_data)}\n\n"
                    
                    # Log heartbeat for debugging
                    if heartbeat_count % 10 == 0:  # Every 50 seconds
                        logger.info(f"SSE heartbeat #{heartbeat_count} sent to {connection_id}")
                    
            except asyncio.CancelledError:
                logger.warning(f"SSE connection cancelled by client: {connection_id} from {request.client.host}")
                # Send disconnection event
                try:
                    disconnect_data = {
                        "type": "disconnected",
                        "connection_id": connection_id,
                        "reason": "client_cancelled",
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    yield f"data: {json.dumps(disconnect_data)}\n\n"
                except Exception as disconnect_error:
                    logger.error(f"Error sending disconnect event: {disconnect_error}")
            except Exception as e:
                logger.error(f"SSE error for connection {connection_id}: {str(e)}")
                error_data = {
                    "type": "error",
                    "connection_id": connection_id,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time()
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control, Accept",
                "Access-Control-Allow-Methods": "GET",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    @app.get("/tools")
    async def list_tools():
        """List available MCP tools."""
        try:
            # Return the actual MinIO MCP tools
            tools = [
                # Authentication tools
                {"name": "minio_login", "category": "auth", "description": "Authenticate with username/password"},
                {"name": "minio_refresh_token", "category": "auth", "description": "Refresh JWT authentication token"},
                {"name": "minio_get_user_info", "category": "auth", "description": "Get current user details and permissions"},
                {"name": "minio_check_auth_status", "category": "auth", "description": "Check authentication status and token validity"},
                
                # Health monitoring tools
                {"name": "minio_health_check", "category": "health", "description": "Basic health status"},
                {"name": "minio_ready_check", "category": "health", "description": "Service readiness with component details"},
                {"name": "minio_live_check", "category": "health", "description": "Liveness probe"},
                {"name": "minio_detailed_health", "category": "health", "description": "Comprehensive system health report"},
                
                # Bucket management tools
                {"name": "minio_list_buckets", "category": "bucket", "description": "List all buckets with pagination"},
                {"name": "minio_create_bucket", "category": "bucket", "description": "Create new bucket with region support"},
                {"name": "minio_get_bucket_info", "category": "bucket", "description": "Get detailed bucket information"},
                {"name": "minio_delete_bucket", "category": "bucket", "description": "Delete empty bucket"},
                {"name": "minio_get_bucket_policy", "category": "bucket", "description": "Retrieve bucket access policy"},
                {"name": "minio_set_bucket_policy", "category": "bucket", "description": "Set/update bucket access policy"},
                
                # Object operations tools
                {"name": "minio_list_objects", "category": "object", "description": "List objects with prefix filtering"},
                {"name": "minio_upload_object", "category": "object", "description": "Upload content as object"},
                {"name": "minio_download_object", "category": "object", "description": "Download object content"},
                {"name": "minio_get_object_info", "category": "object", "description": "Get object metadata without download"},
                {"name": "minio_delete_object", "category": "object", "description": "Delete single object"},
                {"name": "minio_copy_object", "category": "object", "description": "Copy object between locations"},
                {"name": "minio_bulk_delete", "category": "object", "description": "Delete multiple objects"},
                {"name": "minio_generate_presigned", "category": "object", "description": "Generate temporary access URLs"},
                
                # User management tools
                {"name": "minio_list_users", "category": "user", "description": "List all users with status"},
                {"name": "minio_create_user", "category": "user", "description": "Create new user with group assignment"},
                {"name": "minio_get_user", "category": "user", "description": "Get detailed user information"},
                {"name": "minio_update_user", "category": "user", "description": "Update user details and groups"},
                {"name": "minio_delete_user", "category": "user", "description": "Remove user and revoke access"},
                {"name": "minio_get_user_policies", "category": "user", "description": "List user policy assignments"},
                {"name": "minio_assign_user_policy", "category": "user", "description": "Assign policy to user"},
                
                # Policy management tools
                {"name": "minio_list_policies", "category": "policy", "description": "List all IAM policies"},
                {"name": "minio_create_policy", "category": "policy", "description": "Create new IAM policy"},
                {"name": "minio_get_policy", "category": "policy", "description": "Get policy document details"},
                {"name": "minio_update_policy", "category": "policy", "description": "Update existing policy"},
                {"name": "minio_delete_policy", "category": "policy", "description": "Remove policy (if not assigned)"},
                {"name": "minio_validate_policy", "category": "policy", "description": "Validate policy document"}
            ]
            
            return {
                "tools": tools,
                "total_count": len(tools),
                "categories": {
                    "auth": 4,
                    "health": 4,
                    "bucket": 6,
                    "object": 8,
                    "user": 7,
                    "policy": 6
                }
            }
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/resources")
    async def list_resources():
        """List available MCP resources."""
        try:
            # This would need to be implemented based on FastMCP's API  
            resources = []  # Get resources from mcp_server
            return {"resources": resources}
        except Exception as e:
            logger.error(f"Error listing resources: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info(f"Created HTTP app for '{config.mcp_server_name}' v{config.mcp_server_version}")
    return app


async def run_http_server():
    """Run the HTTP server."""
    config = get_config()
    
    # Create the FastAPI app
    app = create_http_app()
    
    # Configure uvicorn
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",  # Listen on all interfaces
        port=8100,       # Default port, make this configurable
        log_level=config.log_level.lower(),
        access_log=True,
        reload=False     # Set to True for development
    )
    
    # Run the server
    server = uvicorn.Server(uvicorn_config)
    
    try:
        logger.info("Starting MinIO MCP HTTP Server on http://0.0.0.0:8100")
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping HTTP server...")
    except Exception as e:
        logger.error(f"HTTP server error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("MinIO MCP HTTP Server stopped")


def main():
    """Main entry point for HTTP server."""
    asyncio.run(run_http_server())


if __name__ == "__main__":
    main()
