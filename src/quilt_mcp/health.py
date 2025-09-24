"""Health check endpoint handlers for MCP server."""

import os
import sys
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse


def get_server_info() -> dict:
    """Get basic server information for health check response."""
    try:
        # Try to get version from package metadata
        from importlib.metadata import version
        server_version = version("quilt-mcp")
    except Exception:
        # Fallback to hardcoded version if metadata not available
        server_version = "0.6.14"

    return {
        "name": "quilt-mcp-server",
        "version": server_version,
        "transport": os.environ.get("FASTMCP_TRANSPORT", "stdio"),
        "host": os.environ.get("FASTMCP_HOST", "localhost"),
        "port": os.environ.get("FASTMCP_PORT", "8000"),
    }


async def health_check_handler(request: Request) -> JSONResponse:
    """Handle health check requests.

    Args:
        request: The incoming HTTP request

    Returns:
        JSONResponse with health status information
    """
    try:
        # Log health check request
        print(f"[HEALTH] Received health check request from {request.client.host if request.client else 'unknown'}", file=sys.stderr)

        # Get current timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Get server information
        server_info = get_server_info()

        # Check for required environment variables
        env_status = {
            "AWS_DEFAULT_REGION": bool(os.environ.get("AWS_DEFAULT_REGION")),
            "QUILT_WEB_HOST": bool(os.environ.get("QUILT_WEB_HOST")),
            "REGISTRY_URL": bool(os.environ.get("REGISTRY_URL")),
            "FASTMCP_PORT": os.environ.get("FASTMCP_PORT", "8000"),
            "FASTMCP_HOST": os.environ.get("FASTMCP_HOST", "localhost"),
            "FASTMCP_TRANSPORT": os.environ.get("FASTMCP_TRANSPORT", "stdio"),
        }

        # Build response
        response_data = {
            "status": "ok",
            "timestamp": timestamp,
            "server": server_info,
            "environment": env_status,
            "message": "MCP server is healthy and ready to accept connections",
        }

        # Log successful health check
        print(f"[HEALTH] Health check passed - returning 200 OK", file=sys.stderr)

        # Return healthy response
        return JSONResponse(
            content=response_data,
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-MCP-Server": "quilt-mcp",
            },
        )

    except Exception as e:
        # Handle any errors gracefully
        print(f"[HEALTH] Health check failed with error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        timestamp = datetime.now(timezone.utc).isoformat()
        error_response = {
            "status": "unhealthy",
            "timestamp": timestamp,
            "error": str(e),
            "message": "MCP server health check failed",
        }

        return JSONResponse(
            content=error_response,
            status_code=503,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-MCP-Server": "quilt-mcp",
            },
        )
