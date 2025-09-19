"""Server-Sent Events handler for MinIO MCP Server."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """SSE event types."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    HEARTBEAT = "heartbeat"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


@dataclass
class SSEEvent:
    """SSE event data structure."""
    type: EventType
    data: Dict
    timestamp: str
    event_id: str
    retry: Optional[int] = None

    def to_sse_format(self) -> str:
        """Convert to SSE format."""
        lines = []
        
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        
        lines.append(f"event: {self.type}")
        
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # Convert data to JSON and handle multiline
        data_json = json.dumps({
            **self.data,
            "timestamp": self.timestamp,
            "event_id": self.event_id
        })
        
        # Handle multiline data
        for line in data_json.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append("")  # Empty line to end the event
        return "\n".join(lines) + "\n"


class SSEConnectionManager:
    """Manage SSE connections and broadcast events."""
    
    def __init__(self):
        self.connections: Dict[str, asyncio.Queue] = {}
        self.connection_info: Dict[str, Dict] = {}
        
    async def connect(self, connection_id: str, client_info: Dict = None) -> str:
        """Add a new SSE connection."""
        if connection_id in self.connections:
            await self.disconnect(connection_id)
        
        self.connections[connection_id] = asyncio.Queue()
        self.connection_info[connection_id] = {
            "connected_at": datetime.utcnow().isoformat(),
            "client_info": client_info or {},
            "events_sent": 0
        }
        
        # Send connection event
        await self.send_to_connection(
            connection_id,
            SSEEvent(
                type=EventType.CONNECTED,
                data={
                    "connection_id": connection_id,
                    "message": "Successfully connected to MinIO MCP Server"
                },
                timestamp=datetime.utcnow().isoformat(),
                event_id=str(uuid.uuid4())
            )
        )
        
        logger.info(f"SSE connection established: {connection_id}")
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Remove an SSE connection."""
        if connection_id in self.connections:
            # Send disconnection event
            try:
                await self.send_to_connection(
                    connection_id,
                    SSEEvent(
                        type=EventType.DISCONNECTED,
                        data={"connection_id": connection_id, "message": "Connection closed"},
                        timestamp=datetime.utcnow().isoformat(),
                        event_id=str(uuid.uuid4())
                    )
                )
            except:
                pass  # Connection might already be closed
            
            del self.connections[connection_id]
            if connection_id in self.connection_info:
                del self.connection_info[connection_id]
            
            logger.info(f"SSE connection removed: {connection_id}")
    
    async def send_to_connection(self, connection_id: str, event: SSEEvent):
        """Send event to a specific connection."""
        if connection_id in self.connections:
            try:
                await self.connections[connection_id].put(event)
                self.connection_info[connection_id]["events_sent"] += 1
            except Exception as e:
                logger.error(f"Failed to send event to connection {connection_id}: {e}")
                await self.disconnect(connection_id)
    
    async def broadcast(self, event: SSEEvent, exclude: Set[str] = None):
        """Broadcast event to all connections."""
        exclude = exclude or set()
        
        for connection_id in list(self.connections.keys()):
            if connection_id not in exclude:
                await self.send_to_connection(connection_id, event)
    
    async def get_events(self, connection_id: str) -> AsyncGenerator[str, None]:
        """Get events for a specific connection."""
        if connection_id not in self.connections:
            return
        
        queue = self.connections[connection_id]
        
        try:
            while connection_id in self.connections:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse_format()
                    
                except asyncio.TimeoutError:
                    # Send heartbeat
                    heartbeat_event = SSEEvent(
                        type=EventType.HEARTBEAT,
                        data={"connection_id": connection_id},
                        timestamp=datetime.utcnow().isoformat(),
                        event_id=str(uuid.uuid4())
                    )
                    yield heartbeat_event.to_sse_format()
                    
        except asyncio.CancelledError:
            logger.info(f"SSE event stream cancelled for connection: {connection_id}")
        except Exception as e:
            logger.error(f"Error in SSE event stream for {connection_id}: {e}")
            
            # Send error event
            error_event = SSEEvent(
                type=EventType.ERROR,
                data={"error": str(e), "connection_id": connection_id},
                timestamp=datetime.utcnow().isoformat(),
                event_id=str(uuid.uuid4())
            )
            yield error_event.to_sse_format()
        finally:
            await self.disconnect(connection_id)
    
    def get_connection_stats(self) -> Dict:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "connections": {
                conn_id: {
                    **info,
                    "queue_size": self.connections[conn_id].qsize()
                }
                for conn_id, info in self.connection_info.items()
            }
        }
    
    async def send_tool_call_event(self, connection_id: str, tool_name: str, parameters: Dict):
        """Send tool call event."""
        event = SSEEvent(
            type=EventType.TOOL_CALL,
            data={
                "tool_name": tool_name,
                "parameters": parameters,
                "connection_id": connection_id
            },
            timestamp=datetime.utcnow().isoformat(),
            event_id=str(uuid.uuid4())
        )
        await self.send_to_connection(connection_id, event)
    
    async def send_tool_result_event(self, connection_id: str, tool_name: str, result: Dict, success: bool = True):
        """Send tool result event."""
        event = SSEEvent(
            type=EventType.TOOL_RESULT,
            data={
                "tool_name": tool_name,
                "result": result,
                "success": success,
                "connection_id": connection_id
            },
            timestamp=datetime.utcnow().isoformat(),
            event_id=str(uuid.uuid4())
        )
        await self.send_to_connection(connection_id, event)
    
    async def send_status_update(self, status: str, details: Dict = None):
        """Broadcast status update to all connections."""
        event = SSEEvent(
            type=EventType.STATUS_UPDATE,
            data={
                "status": status,
                "details": details or {}
            },
            timestamp=datetime.utcnow().isoformat(),
            event_id=str(uuid.uuid4())
        )
        await self.broadcast(event)


# Global SSE connection manager
sse_manager = SSEConnectionManager()
