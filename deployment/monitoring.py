"""Monitoring and metrics for MinIO MCP Server."""

import time
import psutil
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import json

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Metric data structure."""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels or {}
        }


class MetricsCollector:
    """Collect and store application metrics."""
    
    def __init__(self):
        # Prometheus metrics
        self.request_counter = Counter(
            'mcp_requests_total',
            'Total number of MCP requests',
            ['method', 'endpoint', 'status_code']
        )
        
        self.request_duration = Histogram(
            'mcp_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint']
        )
        
        self.active_connections = Gauge(
            'mcp_active_connections',
            'Number of active SSE connections'
        )
        
        self.tool_calls = Counter(
            'mcp_tool_calls_total',
            'Total number of tool calls',
            ['tool_name', 'status']
        )
        
        self.auth_attempts = Counter(
            'mcp_auth_attempts_total',
            'Total authentication attempts',
            ['status', 'auth_type']
        )
        
        self.system_cpu = Gauge('system_cpu_percent', 'System CPU usage percentage')
        self.system_memory = Gauge('system_memory_percent', 'System memory usage percentage')
        self.system_disk = Gauge('system_disk_percent', 'System disk usage percentage')
        
        # Custom metrics storage
        self.custom_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.metric_history_hours = 24
        
        # Start background tasks
        self._monitoring_task = None
        # Don't start monitoring in __init__, will be started when event loop is available
    
    def start_monitoring(self):
        """Start background monitoring tasks."""
        if self._monitoring_task is None:
            try:
                self._monitoring_task = asyncio.create_task(self._collect_system_metrics())
            except RuntimeError:
                # No event loop running, monitoring will start when HTTP server starts
                pass
    
    async def _collect_system_metrics(self):
        """Collect system metrics periodically."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.system_cpu.set(cpu_percent)
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.system_memory.set(memory.percent)
                
                # Disk usage
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                self.system_disk.set(disk_percent)
                
                # Store in custom metrics for historical data
                now = datetime.utcnow()
                self.add_metric("system.cpu_percent", cpu_percent, now)
                self.add_metric("system.memory_percent", memory.percent, now)
                self.add_metric("system.disk_percent", disk_percent, now)
                
                await asyncio.sleep(30)  # Collect every 30 seconds
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self.request_counter.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_tool_call(self, tool_name: str, success: bool, duration: float = None):
        """Record tool call metrics."""
        status = "success" if success else "error"
        self.tool_calls.labels(tool_name=tool_name, status=status).inc()
        
        if duration is not None:
            self.add_metric(f"tool.{tool_name}.duration", duration)
    
    def record_auth_attempt(self, success: bool, auth_type: str = "unknown"):
        """Record authentication attempt."""
        status = "success" if success else "failure"
        self.auth_attempts.labels(status=status, auth_type=auth_type).inc()
    
    def set_active_connections(self, count: int):
        """Set the number of active SSE connections."""
        self.active_connections.set(count)
    
    def add_metric(self, name: str, value: float, timestamp: datetime = None, labels: Dict[str, str] = None):
        """Add a custom metric."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        metric = MetricData(name=name, value=value, timestamp=timestamp, labels=labels)
        self.custom_metrics[name].append(metric)
    
    def get_metrics_summary(self) -> Dict:
        """Get a summary of all metrics."""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=self.metric_history_hours)
        
        summary = {
            "timestamp": now.isoformat(),
            "system": {},
            "application": {},
            "custom": {}
        }
        
        # System metrics (latest values)
        try:
            summary["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            summary["system"] = {"error": str(e)}
        
        # Application metrics
        summary["application"] = {
            "total_requests": sum([
                sample.value for sample in self.request_counter.collect()[0].samples
            ]),
            "total_tool_calls": sum([
                sample.value for sample in self.tool_calls.collect()[0].samples
            ]),
            "active_connections": self.active_connections._value._value if hasattr(self.active_connections, '_value') else 0
        }
        
        # Custom metrics (recent values)
        for name, metrics in self.custom_metrics.items():
            recent_metrics = [m for m in metrics if m.timestamp > cutoff]
            if recent_metrics:
                values = [m.value for m in recent_metrics]
                summary["custom"][name] = {
                    "count": len(values),
                    "latest": values[-1],
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values)
                }
        
        return summary
    
    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest()
    
    def get_health_status(self) -> Dict:
        """Get health status based on metrics."""
        status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # CPU check
            cpu_percent = psutil.cpu_percent()
            status["checks"]["cpu"] = {
                "status": "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 95 else "critical",
                "value": cpu_percent,
                "unit": "percent"
            }
            
            # Memory check
            memory = psutil.virtual_memory()
            status["checks"]["memory"] = {
                "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 95 else "critical",
                "value": memory.percent,
                "unit": "percent"
            }
            
            # Disk check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            status["checks"]["disk"] = {
                "status": "healthy" if disk_percent < 80 else "warning" if disk_percent < 95 else "critical",
                "value": disk_percent,
                "unit": "percent"
            }
            
            # Overall status
            check_statuses = [check["status"] for check in status["checks"].values()]
            if "critical" in check_statuses:
                status["status"] = "critical"
            elif "warning" in check_statuses:
                status["status"] = "warning"
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            status["status"] = "error"
            status["error"] = str(e)
        
        return status
    
    async def cleanup(self):
        """Clean up monitoring resources."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass


class PerformanceTracker:
    """Track performance metrics for specific operations."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.active_operations: Dict[str, float] = {}
    
    def start_operation(self, operation_id: str) -> str:
        """Start tracking an operation."""
        self.active_operations[operation_id] = time.time()
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, metadata: Dict = None):
        """End tracking an operation."""
        if operation_id in self.active_operations:
            start_time = self.active_operations.pop(operation_id)
            duration = time.time() - start_time
            
            # Record metrics
            operation_type = operation_id.split(':')[0] if ':' in operation_id else 'unknown'
            self.metrics.add_metric(
                f"operation.{operation_type}.duration",
                duration,
                labels={"success": str(success), **(metadata or {})}
            )
            
            return duration
        return None
    
    def get_active_operations(self) -> Dict[str, float]:
        """Get currently active operations."""
        now = time.time()
        return {
            op_id: now - start_time
            for op_id, start_time in self.active_operations.items()
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()
performance_tracker = PerformanceTracker(metrics_collector)


# Decorator for automatic performance tracking
def track_performance(operation_name: str = None):
    """Decorator to automatically track function performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            op_id = f"{op_name}:{int(time.time() * 1000)}"
            
            performance_tracker.start_operation(op_id)
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                performance_tracker.end_operation(op_id, success)
        
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            op_id = f"{op_name}:{int(time.time() * 1000)}"
            
            performance_tracker.start_operation(op_id)
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                performance_tracker.end_operation(op_id, success)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
