"""Shared utilities for Quilt MCP tools."""

from __future__ import annotations

import contextlib
import inspect
import io
import os
import re
import sys
from typing import Any, Callable, Dict, Literal, Optional
from urllib.parse import parse_qs, unquote, urlparse

import boto3
from starlette.requests import Request
from fastmcp import FastMCP

from .runtime import request_context


def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
    """
    Parse S3 URI into bucket, key, and version_id components.

    Args:
        s3_uri: S3 URI in format 's3://bucket/key' or 's3://bucket/key?versionId=xyz'

    Returns:
        Tuple of (bucket, key, version_id) where version_id is extracted from query params

    Raises:
        ValueError: If URI format is invalid or has unexpected query parameters
    """
    parsed = urlparse(s3_uri)
    if parsed.scheme != 's3':
        raise ValueError(f"Invalid S3 URI scheme: {parsed.scheme}")

    bucket = parsed.netloc
    if not bucket:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")

    path = unquote(parsed.path)[1:]  # Remove leading / and URL decode
    if not path:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")

    # Extract and validate query parameters
    query = parse_qs(parsed.query)
    version_id = query.pop('versionId', [None])[0]

    # Strict validation - no other query parameters allowed
    if query:
        raise ValueError(f"Unexpected S3 query string: {parsed.query!r}")

    return bucket, path, version_id


def generate_signed_url(s3_uri: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL for an S3 URI.

    Args:
        s3_uri: S3 URI (e.g., "s3://bucket/key")
        expiration: URL expiration in seconds (default: 3600)

    Returns:
        Presigned URL string or None if generation fails
    """
    if not s3_uri.startswith("s3://"):
        return None

    without_scheme = s3_uri[5:]
    if "/" not in without_scheme:
        return None

    bucket, key = without_scheme.split("/", 1)
    expiration = max(1, min(expiration, 604800))  # 1 sec to 7 days

    try:
        client = get_s3_client()
        url = client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration)
        return str(url) if url else None
    except Exception:
        return None


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    return FastMCP("quilt-mcp-server")


def get_tool_modules() -> list[Any]:
    """Get list of tool modules to register."""
    from quilt_mcp.tools import (
        auth,
        buckets,
        package_ops,
        packages,
        s3_package,
        permissions,
        unified_package,
        metadata_templates,
        package_management,
        metadata_examples,
        quilt_summary,
        search,
        athena_glue,
        tabulator,
        workflow_orchestration,
        governance,
    )

    # error_recovery temporarily disabled due to Callable parameter issues

    return [
        auth,
        buckets,
        packages,
        package_ops,
        s3_package,
        permissions,
        unified_package,
        metadata_templates,
        package_management,
        metadata_examples,
        quilt_summary,
        search,
        athena_glue,
        tabulator,
        workflow_orchestration,
        governance,
    ]


def get_module_wrappers() -> dict[str, Callable]:
    """Get module wrapper functions to register as MCP tools.
    
    Returns a dictionary mapping tool names to their wrapper functions.
    Each wrapper function provides action-based dispatch to multiple operations.
    """
    from quilt_mcp.tools import (
        auth,
        buckets,
        package_ops,
        packages,
        s3_package,
        permissions,
        unified_package,
        metadata_templates,
        package_management,
        metadata_examples,
        quilt_summary,
        search,
        athena_glue,
        tabulator,
        workflow_orchestration,
        governance,
    )
    
    # Map tool names to their wrapper functions
    # Each wrapper provides action-based dispatch (e.g., auth(action="status"))
    return {
        "auth": auth.auth,
        "buckets": buckets.buckets,
        "athena_glue": athena_glue.athena_glue,
        "governance": governance.governance,
        "metadata_examples": metadata_examples.metadata_examples,
        "metadata_templates": metadata_templates.metadata_templates,
        "package_management": package_management.package_management,
        "package_ops": package_ops.package_ops,
        "packages": packages.packages,
        "permissions": permissions.permissions,
        "quilt_summary": quilt_summary.quilt_summary,
        "s3_package": s3_package.s3_package,
        "search": search.search,
        "tabulator": tabulator.tabulator,
        "unified_package": unified_package.unified_package,
        "workflow_orchestration": workflow_orchestration.workflow_orchestration,
    }


def resolve_catalog_url(explicit: Optional[str] = None) -> Optional[str]:
    """Resolve the Quilt catalog base URL from explicit value or environment."""

    if explicit:
        return explicit.rstrip("/")

    url = os.getenv("QUILT_CATALOG_URL")
    if url:
        return url.rstrip("/")

    domain = os.getenv("QUILT_CATALOG_DOMAIN")
    if domain:
        domain = domain.strip().rstrip("/")
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain
        return f"https://{domain}"

    return None


def register_tools(mcp: FastMCP, tool_modules: list[Any] | None = None, verbose: bool = True) -> int:
    """Register module wrapper functions as MCP tools.
    
    This registers 16 module-based tools (one per module) instead of 84 individual
    function tools. Each module wrapper provides action-based dispatch.

    Args:
        mcp: The FastMCP server instance
        tool_modules: Deprecated parameter (kept for compatibility, not used)
        verbose: Whether to print registration messages

    Returns:
        Number of tools registered (should be 16)
    """
    wrappers = get_module_wrappers()
    tools_registered = 0
    
    for tool_name, wrapper_func in sorted(wrappers.items()):
        # Register the wrapper function as an MCP tool
        mcp.tool(wrapper_func)
        tools_registered += 1
        
        if verbose:
            # Get action count by calling wrapper with action=None
            try:
                if inspect.iscoroutinefunction(wrapper_func):
                    # For async wrappers, we can't easily call them here
                    # Just log that it's registered
                    print(f"Registered tool: {tool_name} (async wrapper)", file=sys.stderr)
                else:
                    result = wrapper_func(action=None)
                    action_count = len(result.get("actions", []))
                    print(f"Registered tool: {tool_name} ({action_count} actions)", file=sys.stderr)
            except Exception:
                # Fallback if discovery fails
                print(f"Registered tool: {tool_name}", file=sys.stderr)
    
    if verbose:
        print(f"\n✅ Registered {tools_registered} module-based tools (reduced from 84 individual tools)", file=sys.stderr)
    
    return tools_registered


def get_s3_client(_use_quilt_auth: bool = True):
    """Return a standard boto3 S3 client."""

    # _use_quilt_auth retained for compatibility; no longer used.
    return boto3.client("s3")


def get_sts_client(_use_quilt_auth: bool = True):
    """Return a standard boto3 STS client."""

    return boto3.client("sts")


def validate_package_name(package_name: str) -> bool:
    """Validate package name format (namespace/name)."""
    if not package_name or "/" not in package_name:
        return False

    parts = package_name.split("/")
    if len(parts) != 2:
        return False

    namespace, name = parts

    # Check for valid characters and format
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-_]*[a-zA-Z0-9])?$"
    return bool(re.match(pattern, namespace) and re.match(pattern, name))


def format_error_response(message: str) -> Dict[str, Any]:
    """Format a standardized error response."""
    return {
        "success": False,
        "error": message,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


@contextlib.contextmanager
def suppress_stdout():
    """Context manager to suppress stdout output to prevent JSON-RPC interference.

    This is critical for MCP servers using stdio transport, as any stdout output
    that isn't valid JSON-RPC will break the communication protocol.
    """
    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            yield stdout_capture
    finally:
        # Log captured output to stderr if needed for debugging
        captured_output = stdout_capture.getvalue().strip()
        if captured_output:
            print(f"Suppressed stdout: {captured_output}", file=sys.stderr)


def create_configured_server(verbose: bool = False) -> FastMCP:
    """Create a fully configured MCP server with all tools registered.

    Args:
        verbose: Whether to print registration messages

    Returns:
        Configured FastMCP server instance
    """
    mcp = create_mcp_server()
    tools_count = register_tools(mcp, verbose=verbose)

    # Register health check endpoint for HTTP transport
    transport = os.environ.get("FASTMCP_TRANSPORT", "stdio")
    if transport in ["http", "sse", "streamable-http"]:
        from quilt_mcp.health import health_check_handler

        # Register health endpoint using FastMCP's custom_route decorator
        mcp.custom_route("/health", methods=["GET"])(health_check_handler)

        if verbose:
            print("Registered health check endpoint: /health", file=sys.stderr)

    if verbose:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Successfully registered {tools_count} tools", file=sys.stderr)

    return mcp


def _wrap_http_app(mcp: FastMCP):
    """Wrap the FastAPI application to manage request context."""

    app = mcp.http_app()

    @app.middleware("http")
    async def _inject_request_context(request: Request, call_next):  # type: ignore
        token = request.headers.get("authorization")
        with request_context(token, {"path": str(request.url.path)}):
            response = await call_next(request)
        return response

    return app


def run_server() -> None:
    """Run the MCP server with proper error handling."""

    try:
        mcp = create_configured_server()
        transport_str = os.environ.get("FASTMCP_TRANSPORT", "stdio")
        valid_transports = ["stdio", "http", "sse", "streamable-http"]
        if transport_str not in valid_transports:
            transport_str = "stdio"

        transport: Literal["stdio", "http", "sse", "streamable-http"] = transport_str  # type: ignore

        if transport in {"http", "streamable-http"}:
            app = _wrap_http_app(mcp)
            from fastapi import FastAPI
            if isinstance(app, FastAPI):
                import uvicorn

                uvicorn.run(app, host=os.environ.get("FASTMCP_ADDR", "0.0.0.0"), port=int(os.environ.get("FASTMCP_PORT", "8000")))
                return

        mcp.run(transport=transport)

    except Exception as e:  # pragma: no cover - startup diagnostics
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        raise
