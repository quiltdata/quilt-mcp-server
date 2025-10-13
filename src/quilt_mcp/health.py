"""Health check endpoint handlers for MCP server."""

import os
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
    }


def _build_health_response(route: str) -> JSONResponse:
    """Build a health check response with route information.

    Args:
        route: The route path being checked

    Returns:
        JSONResponse with health status information
    """
    try:
        # Get current timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Get server information
        server_info = get_server_info()

        # Build response
        response_data = {
            "status": "ok",
            "timestamp": timestamp,
            "route": route,
            "server": server_info,
        }

        # Return healthy response
        return JSONResponse(
            content=response_data,
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    except Exception as e:
        # Handle any errors gracefully
        timestamp = datetime.now(timezone.utc).isoformat()
        error_response = {
            "status": "unhealthy",
            "timestamp": timestamp,
            "route": route,
            "error": str(e),
        }

        return JSONResponse(
            content=error_response,
            status_code=503,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )


async def health_check_handler(request: Request) -> JSONResponse:
    """Handle health check requests at /health.

    Args:
        request: The incoming HTTP request

    Returns:
        JSONResponse with health status information
    """
    return _build_health_response("/health")


async def healthz_handler(request: Request) -> JSONResponse:
    """Handle health check requests at /healthz.

    Args:
        request: The incoming HTTP request

    Returns:
        JSONResponse with health status information
    """
    return _build_health_response("/healthz")


async def root_handler(request: Request) -> JSONResponse:
    """Handle health check requests at /.

    Args:
        request: The incoming HTTP request

    Returns:
        JSONResponse with health status information
    """
    return _build_health_response("/")


