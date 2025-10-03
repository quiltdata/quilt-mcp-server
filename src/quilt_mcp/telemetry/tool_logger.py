"""Tool call logging for CloudWatch monitoring and debugging.

This module provides structured logging of MCP tool calls with:
- Request/response payloads
- Execution timing
- Error tracking
- User-controlled verbosity via X-MCP-Debug header
"""

import json
import logging
import time
from typing import Any, Dict, Optional
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Context variable for debug mode (set per-request)
_debug_mode: ContextVar[bool] = ContextVar("mcp_debug_mode", default=False)


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug logging for the current request.
    
    Args:
        enabled: Whether to enable detailed debug logging
    """
    _debug_mode.set(enabled)


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled for the current request."""
    return _debug_mode.get(False)


def sanitize_for_logging(data: Any, max_length: int = 500) -> Any:
    """Sanitize data for logging by truncating large values.
    
    Args:
        data: Data to sanitize
        max_length: Maximum string length before truncation
        
    Returns:
        Sanitized data safe for logging
    """
    if isinstance(data, str):
        if len(data) > max_length:
            return f"{data[:max_length]}... (truncated, {len(data)} chars total)"
        return data
    elif isinstance(data, dict):
        return {k: sanitize_for_logging(v, max_length) for k, v in data.items()}
    elif isinstance(data, list):
        if len(data) > 10:
            return [sanitize_for_logging(item, max_length) for item in data[:10]] + [
                f"... ({len(data) - 10} more items)"
            ]
        return [sanitize_for_logging(item, max_length) for item in data]
    else:
        return data


def log_tool_call_start(
    tool_name: str,
    action: Optional[str],
    params: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Log the start of a tool call.
    
    Args:
        tool_name: Name of the tool being called
        action: Action within the tool (if applicable)
        params: Tool parameters
        session_id: MCP session ID
        
    Returns:
        Context dict with start_time for use in log_tool_call_end
    """
    start_time = time.time()
    
    # Always log basic info
    log_data = {
        "event": "tool_call_start",
        "tool": tool_name,
        "action": action,
        "session_id": session_id,
        "timestamp": start_time,
    }
    
    # Log detailed params only in debug mode
    if is_debug_enabled():
        log_data["params"] = sanitize_for_logging(params)
        logger.info("🔧 Tool Call Start: %s", json.dumps(log_data, default=str))
    else:
        # Compact log for production
        action_str = f".{action}" if action else ""
        logger.info(f"🔧 Tool: {tool_name}{action_str}")
    
    return {"start_time": start_time, "tool": tool_name, "action": action}


def log_tool_call_end(
    context: Dict[str, Any],
    result: Any,
    success: bool = True,
    error: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Log the end of a tool call with results.
    
    Args:
        context: Context dict from log_tool_call_start
        result: Tool execution result
        success: Whether the call succeeded
        error: Error message if call failed
        session_id: MCP session ID
    """
    end_time = time.time()
    execution_time = end_time - context["start_time"]
    
    tool_name = context["tool"]
    action = context.get("action")
    action_str = f".{action}" if action else ""
    
    # Always log basic metrics
    log_data = {
        "event": "tool_call_end",
        "tool": tool_name,
        "action": action,
        "success": success,
        "execution_time_ms": round(execution_time * 1000, 2),
        "session_id": session_id,
        "timestamp": end_time,
    }
    
    if not success:
        log_data["error"] = error
        logger.error("❌ Tool Failed: %s%s - %s (%.2fms)", 
                    tool_name, action_str, error, execution_time * 1000)
    elif is_debug_enabled():
        # Include result details in debug mode
        log_data["result"] = sanitize_for_logging(result)
        log_data["result_size"] = len(str(result)) if result else 0
        logger.info("✅ Tool Call Complete: %s", json.dumps(log_data, default=str))
    else:
        # Compact success log
        logger.info(f"✅ Tool: {tool_name}{action_str} (%.2fms)", execution_time * 1000)


def log_tool_discovery(tool_count: int, session_id: Optional[str] = None) -> None:
    """Log tool discovery/listing.
    
    Args:
        tool_count: Number of tools discovered
        session_id: MCP session ID
    """
    log_data = {
        "event": "tool_discovery",
        "tool_count": tool_count,
        "session_id": session_id,
    }
    
    if is_debug_enabled():
        logger.info("🔍 Tool Discovery: %s", json.dumps(log_data))
    else:
        logger.info(f"🔍 Discovered {tool_count} tools")


def log_request_context(
    has_jwt: bool,
    catalog_url: Optional[str],
    session_id: Optional[str] = None,
) -> None:
    """Log request context information.
    
    Args:
        has_jwt: Whether JWT token is present
        catalog_url: Catalog URL being used
        session_id: MCP session ID
    """
    if is_debug_enabled():
        log_data = {
            "event": "request_context",
            "has_jwt": has_jwt,
            "catalog_url": catalog_url,
            "session_id": session_id,
        }
        logger.info("📋 Request Context: %s", json.dumps(log_data))

