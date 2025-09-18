"""Utility functions for MinIO MCP Server."""

import logging
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime


logger = logging.getLogger(__name__)


def format_file_size(size_bytes: Union[int, float, str]) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB", "2.3 GB")
    """
    try:
        size = float(size_bytes)
    except (ValueError, TypeError):
        return str(size_bytes)

    if size < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def format_timestamp(timestamp: Union[str, int, float]) -> str:
    """
    Format timestamp in human-readable format.

    Args:
        timestamp: Timestamp as string, unix timestamp, or ISO format

    Returns:
        Formatted timestamp string
    """
    try:
        if isinstance(timestamp, str):
            # Try to parse ISO format first
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                # Try unix timestamp as string
                try:
                    dt = datetime.fromtimestamp(float(timestamp))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return str(timestamp)
        elif isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return str(timestamp)
    except Exception:
        return str(timestamp)


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "2h 30m", "45s")
    """
    try:
        total_seconds = int(float(seconds))
    except (ValueError, TypeError):
        return str(seconds)

    if total_seconds < 0:
        return "0s"

    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        remaining_seconds = total_seconds % 60
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        else:
            return f"{minutes}m"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        remaining_minutes = (total_seconds % 3600) // 60
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h"
    else:
        days = total_seconds // 86400
        remaining_hours = (total_seconds % 86400) // 3600
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        else:
            return f"{days}d"


def validate_bucket_name(name: str) -> tuple[bool, str]:
    """
    Validate bucket name according to S3/MinIO naming rules.

    Args:
        name: Bucket name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Bucket name cannot be empty"

    if len(name) < 3:
        return False, "Bucket name must be at least 3 characters long"

    if len(name) > 63:
        return False, "Bucket name must be no more than 63 characters long"

    # Check for valid characters
    valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    if not set(name).issubset(valid_chars):
        return False, "Bucket name can only contain lowercase letters, numbers, dots, and hyphens"

    # Check start/end characters
    if name.startswith('-') or name.endswith('-'):
        return False, "Bucket name cannot start or end with hyphens"

    if name.startswith('.') or name.endswith('.'):
        return False, "Bucket name cannot start or end with dots"

    # Check for consecutive dots
    if '..' in name:
        return False, "Bucket name cannot contain consecutive dots"

    # Check for IP address format
    parts = name.split('.')
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return False, "Bucket name cannot be formatted as an IP address"

    return True, ""


def validate_object_name(name: str) -> tuple[bool, str]:
    """
    Validate object name according to S3/MinIO naming rules.

    Args:
        name: Object name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Object name cannot be empty"

    if len(name) > 1024:
        return False, "Object name must be no more than 1024 characters long"

    # Check for invalid characters (basic validation)
    invalid_chars = set('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f')
    if any(char in invalid_chars for char in name):
        return False, "Object name contains invalid control characters"

    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate username according to MinIO naming rules.

    Args:
        username: Username to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username cannot be empty"

    if len(username) < 3:
        return False, "Username must be at least 3 characters long"

    if len(username) > 64:
        return False, "Username must be no more than 64 characters long"

    # Check for valid characters (alphanumeric, hyphens, underscores, dots)
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if not set(username).issubset(valid_chars):
        return False, "Username can only contain letters, numbers, hyphens, underscores, and dots"

    # Check start/end characters
    if username.startswith('-') or username.endswith('-'):
        return False, "Username cannot start or end with hyphens"

    return True, ""


def sanitize_error_message(error: str, max_length: int = 200) -> str:
    """
    Sanitize error message to remove sensitive information.

    Args:
        error: Raw error message
        max_length: Maximum length of sanitized message

    Returns:
        Sanitized error message
    """
    if not error:
        return "Unknown error"

    # Remove potential sensitive information
    sensitive_patterns = [
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "bearer"
    ]

    sanitized = str(error).lower()
    for pattern in sensitive_patterns:
        if pattern in sanitized:
            return "Authentication or authorization error"

    # Truncate if too long
    if len(error) > max_length:
        return error[:max_length] + "..."

    return error


def format_response(success: bool, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Format standardized response for tools.

    Args:
        success: Whether the operation was successful
        message: Response message
        data: Optional additional data

    Returns:
        Formatted response dictionary
    """
    response = {
        "success": success,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if data:
        response["data"] = data

    return response


def paginate_results(items: List[Any], limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Paginate a list of items.

    Args:
        items: List of items to paginate
        limit: Maximum number of items per page
        offset: Number of items to skip

    Returns:
        Paginated result with metadata
    """
    total = len(items)
    start = max(0, offset)
    end = min(total, start + limit)

    paginated_items = items[start:end]

    return {
        "items": paginated_items,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": start,
            "count": len(paginated_items),
            "has_more": end < total
        }
    }


def extract_correlation_id(response_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract correlation ID from response data.

    Args:
        response_data: Response data dictionary

    Returns:
        Correlation ID if found, None otherwise
    """
    if isinstance(response_data, dict):
        return response_data.get("correlation_id") or response_data.get("request_id")
    return None


def format_status_icon(status: Union[bool, str]) -> str:
    """
    Format status as icon.

    Args:
        status: Status value

    Returns:
        Appropriate status icon
    """
    if isinstance(status, bool):
        return "🟢" if status else "🔴"
    elif isinstance(status, str):
        status_lower = status.lower()
        if status_lower in ["active", "enabled", "running", "healthy", "ok", "success", "true"]:
            return "🟢"
        elif status_lower in ["inactive", "disabled", "stopped", "unhealthy", "error", "failed", "false"]:
            return "🔴"
        elif status_lower in ["warning", "pending", "unknown"]:
            return "🟡"
        else:
            return "⚪"
    else:
        return "⚪"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(json_str: str) -> tuple[bool, Union[Dict[str, Any], str]]:
    """
    Safely parse JSON string.

    Args:
        json_str: JSON string to parse

    Returns:
        Tuple of (success, parsed_data_or_error_message)
    """
    try:
        import json
        data = json.loads(json_str)
        return True, data
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, f"JSON parsing error: {str(e)}"


def generate_summary_stats(items: List[Dict[str, Any]], group_by_field: str = "status") -> Dict[str, int]:
    """
    Generate summary statistics from a list of items.

    Args:
        items: List of items to analyze
        group_by_field: Field to group by for statistics

    Returns:
        Dictionary with counts for each group
    """
    stats = {}

    for item in items:
        if isinstance(item, dict) and group_by_field in item:
            value = item[group_by_field]
            key = str(value).lower() if value is not None else "unknown"
            stats[key] = stats.get(key, 0) + 1

    return stats


def format_list_summary(items: List[Any], item_type: str = "item") -> str:
    """
    Format a summary line for a list of items.

    Args:
        items: List of items
        item_type: Type of items for display

    Returns:
        Formatted summary string
    """
    count = len(items)
    if count == 0:
        return f"No {item_type}s found"
    elif count == 1:
        return f"1 {item_type} found"
    else:
        return f"{count} {item_type}s found"


def setup_logging(log_level: str = "INFO") -> None:
    """
    Set up logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set httpx logging to WARNING to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)