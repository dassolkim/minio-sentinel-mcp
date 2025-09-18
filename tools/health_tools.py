"""Health check tools for MinIO MCP Server."""

import logging
from typing import Any, Dict
from fastmcp import FastMCP

from minio_client import MinIOClient, MinIOAPIError


logger = logging.getLogger(__name__)


def register_health_tools(mcp: FastMCP, client: MinIOClient) -> None:
    """Register health check tools with the MCP server."""

    @mcp.tool()
    async def minio_health_check() -> str:
        """
        Perform basic health check on MinIO server.

        Returns:
            Basic health status of the MinIO server
        """
        try:
            response = await client.get("/api/v1/health")

            if response.success:
                health_data = response.data
                status = health_data.get("status", "unknown") if isinstance(health_data, dict) else "ok"

                return (
                    f"🟢 MinIO Health Check: PASSED\n"
                    f"Status: {status.upper()}\n"
                    f"Response Time: OK\n"
                    f"API Endpoint: Accessible\n"
                    f"Correlation ID: {response.correlation_id}"
                )
            else:
                return (
                    f"🟡 MinIO Health Check: WARNING\n"
                    f"Status Code: {response.status_code}\n"
                    f"Error: {response.error}\n"
                    f"Correlation ID: {response.correlation_id}"
                )

        except MinIOAPIError as e:
            logger.error(f"Health check API error: {str(e)}")
            return (
                f"🔴 MinIO Health Check: FAILED\n"
                f"Error: {str(e)}\n"
                f"Status Code: {e.status_code}\n"
                f"Correlation ID: {e.correlation_id}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during health check: {str(e)}")
            return f"🔴 MinIO Health Check: FAILED\nUnexpected error: {str(e)}"

    @mcp.tool()
    async def minio_ready_check() -> str:
        """
        Check if MinIO server is ready to accept requests.

        Returns:
            Readiness status with component details
        """
        try:
            response = await client.get("/api/v1/health/ready")

            if response.success:
                ready_data = response.data

                if isinstance(ready_data, dict):
                    status = ready_data.get("ready", True)
                    components = ready_data.get("components", {})

                    component_status = []
                    for component, details in components.items():
                        state = details.get("status", "unknown") if isinstance(details, dict) else str(details)
                        component_status.append(f"  {component}: {state}")

                    components_summary = "\n".join(component_status) if component_status else "  No component details available"

                    return (
                        f"{'🟢' if status else '🔴'} MinIO Readiness Check: {'READY' if status else 'NOT READY'}\n"
                        f"Overall Status: {'Ready' if status else 'Not Ready'}\n"
                        f"Components:\n{components_summary}\n"
                        f"Correlation ID: {response.correlation_id}"
                    )
                else:
                    return (
                        f"🟢 MinIO Readiness Check: READY\n"
                        f"Status: Service is ready\n"
                        f"Response: {ready_data}\n"
                        f"Correlation ID: {response.correlation_id}"
                    )
            else:
                return (
                    f"🔴 MinIO Readiness Check: NOT READY\n"
                    f"Status Code: {response.status_code}\n"
                    f"Error: {response.error}\n"
                    f"Correlation ID: {response.correlation_id}"
                )

        except MinIOAPIError as e:
            logger.error(f"Readiness check API error: {str(e)}")
            return (
                f"🔴 MinIO Readiness Check: FAILED\n"
                f"Error: {str(e)}\n"
                f"Status Code: {e.status_code}\n"
                f"Correlation ID: {e.correlation_id}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during readiness check: {str(e)}")
            return f"🔴 MinIO Readiness Check: FAILED\nUnexpected error: {str(e)}"

    @mcp.tool()
    async def minio_live_check() -> str:
        """
        Perform liveness probe on MinIO server.

        Returns:
            Liveness status indicating if server is running
        """
        try:
            response = await client.get("/api/v1/health/live")

            if response.success:
                live_data = response.data

                if isinstance(live_data, dict):
                    alive = live_data.get("alive", True)
                    uptime = live_data.get("uptime", "unknown")
                    version = live_data.get("version", "unknown")

                    return (
                        f"{'🟢' if alive else '🔴'} MinIO Liveness Check: {'ALIVE' if alive else 'DEAD'}\n"
                        f"Status: {'Service is running' if alive else 'Service is not responding'}\n"
                        f"Uptime: {uptime}\n"
                        f"Version: {version}\n"
                        f"Correlation ID: {response.correlation_id}"
                    )
                else:
                    return (
                        f"🟢 MinIO Liveness Check: ALIVE\n"
                        f"Status: Service is running\n"
                        f"Response: {live_data}\n"
                        f"Correlation ID: {response.correlation_id}"
                    )
            else:
                return (
                    f"🔴 MinIO Liveness Check: DEAD\n"
                    f"Status Code: {response.status_code}\n"
                    f"Error: {response.error}\n"
                    f"Correlation ID: {response.correlation_id}"
                )

        except MinIOAPIError as e:
            logger.error(f"Liveness check API error: {str(e)}")
            return (
                f"🔴 MinIO Liveness Check: FAILED\n"
                f"Error: {str(e)}\n"
                f"Status Code: {e.status_code}\n"
                f"Correlation ID: {e.correlation_id}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during liveness check: {str(e)}")
            return f"🔴 MinIO Liveness Check: FAILED\nUnexpected error: {str(e)}"

    @mcp.tool()
    async def minio_detailed_health() -> str:
        """
        Get comprehensive health information about MinIO server.

        Returns:
            Detailed health report including system metrics and component status
        """
        try:
            response = await client.get("/api/v1/health/detailed")

            if response.success:
                health_data = response.data

                if isinstance(health_data, dict):
                    # Extract key health metrics
                    overall_status = health_data.get("status", "unknown")
                    version = health_data.get("version", "unknown")
                    uptime = health_data.get("uptime", "unknown")
                    memory = health_data.get("memory", {})
                    storage = health_data.get("storage", {})
                    network = health_data.get("network", {})
                    services = health_data.get("services", {})

                    # Format memory information
                    memory_info = "Unknown"
                    if isinstance(memory, dict):
                        used = memory.get("used", "N/A")
                        total = memory.get("total", "N/A")
                        memory_info = f"Used: {used}, Total: {total}"

                    # Format storage information
                    storage_info = "Unknown"
                    if isinstance(storage, dict):
                        used = storage.get("used", "N/A")
                        total = storage.get("total", "N/A")
                        available = storage.get("available", "N/A")
                        storage_info = f"Used: {used}, Available: {available}, Total: {total}"

                    # Format services status
                    services_status = []
                    if isinstance(services, dict):
                        for service, status in services.items():
                            status_icon = "🟢" if status in ["running", "healthy", True] else "🔴"
                            services_status.append(f"  {status_icon} {service}: {status}")

                    services_summary = "\n".join(services_status) if services_status else "  No service information available"

                    # Format network information
                    network_info = "Unknown"
                    if isinstance(network, dict):
                        connections = network.get("connections", "N/A")
                        bandwidth = network.get("bandwidth", "N/A")
                        network_info = f"Connections: {connections}, Bandwidth: {bandwidth}"

                    return (
                        f"🏥 MinIO Detailed Health Report\n"
                        f"═══════════════════════════════════\n"
                        f"Overall Status: {overall_status.upper()}\n"
                        f"Version: {version}\n"
                        f"Uptime: {uptime}\n"
                        f"\n📊 System Metrics:\n"
                        f"Memory: {memory_info}\n"
                        f"Storage: {storage_info}\n"
                        f"Network: {network_info}\n"
                        f"\n🔧 Services:\n{services_summary}\n"
                        f"\n🆔 Correlation ID: {response.correlation_id}"
                    )
                else:
                    return (
                        f"🏥 MinIO Detailed Health Report\n"
                        f"═══════════════════════════════════\n"
                        f"Status: Service responding\n"
                        f"Response: {health_data}\n"
                        f"Correlation ID: {response.correlation_id}"
                    )
            else:
                return (
                    f"🔴 MinIO Detailed Health Check: FAILED\n"
                    f"Status Code: {response.status_code}\n"
                    f"Error: {response.error}\n"
                    f"Correlation ID: {response.correlation_id}"
                )

        except MinIOAPIError as e:
            logger.error(f"Detailed health check API error: {str(e)}")
            return (
                f"🔴 MinIO Detailed Health Check: FAILED\n"
                f"Error: {str(e)}\n"
                f"Status Code: {e.status_code}\n"
                f"Correlation ID: {e.correlation_id}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during detailed health check: {str(e)}")
            return f"🔴 MinIO Detailed Health Check: FAILED\nUnexpected error: {str(e)}"