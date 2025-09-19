#!/usr/bin/env python3
"""
Robust SSE Client for MinIO MCP Server Testing
"""

import requests
import json
import time
import threading
import signal
import sys
from typing import Optional, Callable
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RobustSSEClient:
    """A robust SSE client with reconnection and error handling."""
    
    def __init__(self, url: str, headers: Optional[dict] = None):
        self.url = url
        self.headers = headers or {'Accept': 'text/event-stream'}
        self.session = requests.Session()
        self.running = False
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10
        self.event_handlers = {}
        
    def on_event(self, event_type: str, handler: Callable):
        """Register an event handler."""
        self.event_handlers[event_type] = handler
    
    def connect(self):
        """Connect to SSE stream with automatic reconnection."""
        self.running = True
        attempt = 0
        
        while self.running and attempt < self.max_reconnect_attempts:
            try:
                logger.info(f"Attempting to connect to {self.url} (attempt {attempt + 1})")
                
                response = self.session.get(
                    self.url,
                    headers=self.headers,
                    stream=True,
                    timeout=(10, 30)  # (connect_timeout, read_timeout)
                )
                
                if response.status_code == 200:
                    logger.info("✅ Connected to SSE stream")
                    attempt = 0  # Reset attempt counter on successful connection
                    
                    self._process_stream(response)
                    
                else:
                    logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning("⏱️ Connection timeout")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 Connection error: {e}")
            except Exception as e:
                logger.error(f"💥 Unexpected error: {e}")
            
            if self.running:
                attempt += 1
                if attempt < self.max_reconnect_attempts:
                    logger.info(f"🔄 Reconnecting in {self.reconnect_delay} seconds...")
                    time.sleep(self.reconnect_delay)
                else:
                    logger.error("❌ Max reconnection attempts reached")
                    break
    
    def _process_stream(self, response):
        """Process the SSE stream."""
        buffer = ""
        
        try:
            for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                if not self.running:
                    break
                
                if chunk:
                    buffer += chunk
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self._process_line(line.strip())
                        
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
            raise
    
    def _process_line(self, line: str):
        """Process a single SSE line."""
        if not line:
            return
            
        if line.startswith('data: '):
            data_str = line[6:]  # Remove 'data: ' prefix
            
            try:
                data = json.loads(data_str)
                event_type = data.get('type', 'unknown')
                
                # Log the event
                if event_type == 'heartbeat':
                    logger.debug(f"💓 Heartbeat #{data.get('heartbeat_count', 0)}")
                else:
                    logger.info(f"📦 Event: {event_type} - {data}")
                
                # Call registered handler
                if event_type in self.event_handlers:
                    self.event_handlers[event_type](data)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in SSE data: {data_str} - {e}")
        
        elif line.startswith('event: '):
            event_name = line[7:]
            logger.debug(f"Event type: {event_name}")
        
        elif line.startswith('id: '):
            event_id = line[4:]
            logger.debug(f"Event ID: {event_id}")
    
    def disconnect(self):
        """Disconnect from SSE stream."""
        logger.info("🔌 Disconnecting from SSE stream...")
        self.running = False


def main():
    """Main function to test SSE connection."""
    # Configuration
    SERVER_URL = "http://129.254.191.53:8100/sse"
    
    # Create SSE client
    client = RobustSSEClient(SERVER_URL)
    
    # Register event handlers
    def on_connected(data):
        logger.info(f"🔗 Connected with ID: {data.get('connection_id')}")
    
    def on_server_info(data):
        logger.info(f"🛠️ Server: {data.get('server_name')} v{data.get('server_version')}")
        logger.info(f"📋 Available tools: {data.get('available_tools')}")
    
    def on_heartbeat(data):
        count = data.get('heartbeat_count', 0)
        if count % 5 == 0:  # Log every 5th heartbeat
            logger.info(f"💗 Heartbeat #{count} - Connection alive")
    
    def on_error(data):
        logger.error(f"❌ Server error: {data.get('error')}")
    
    def on_disconnected(data):
        logger.warning(f"🔌 Disconnected: {data.get('reason', 'unknown')}")
    
    # Register handlers
    client.on_event('connected', on_connected)
    client.on_event('server_info', on_server_info)
    client.on_event('heartbeat', on_heartbeat)
    client.on_event('error', on_error)
    client.on_event('disconnected', on_disconnected)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        logger.info("🛑 Received interrupt signal")
        client.disconnect()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start connection in a separate thread
    connection_thread = threading.Thread(target=client.connect, daemon=True)
    connection_thread.start()
    
    # Keep main thread alive
    try:
        while connection_thread.is_alive():
            connection_thread.join(1)
    except KeyboardInterrupt:
        logger.info("🛑 Main thread interrupted")
        client.disconnect()


if __name__ == "__main__":
    main()
