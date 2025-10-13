"""Shared utilities for Quilt MCP tools."""

from __future__ import annotations

import inspect
import os
import re
import sys
import io
import contextlib
from typing import Any, Dict, Literal, Callable
from urllib.parse import urlparse, parse_qs, unquote

import boto3
from fastmcp import FastMCP


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


def register_tools(mcp: FastMCP, tool_modules: list[Any] | None = None, verbose: bool = True) -> int:
    """Register all public functions from tool modules as MCP tools.

    Args:
        mcp: The FastMCP server instance
        tool_modules: List of modules to register tools from (defaults to all)
        verbose: Whether to print registration messages

    Returns:
        Number of tools registered
    """
    if tool_modules is None:
        tool_modules = get_tool_modules()

    # List of deprecated tools (to reduce client confusion)
    excluded_tools = {
        "packages_list",  # Prefer packages_search
        "athena_tables_list",  # Prefer athena_query_execute
        "get_tabulator_service",  # Internal use only
    }

    tools_registered = 0

    for module in tool_modules:
        # Get all public functions (not starting with _)
        def make_predicate(mod: Any) -> Callable[[Any], bool]:
            return lambda obj: (
                inspect.isfunction(obj)
                and not obj.__name__.startswith("_")
                and obj.__module__ == mod.__name__  # Only functions defined in this module
            )

        functions = inspect.getmembers(module, predicate=make_predicate(module))

        for name, func in functions:
            # Skip deprecated tools to reduce client confusion
            if name in excluded_tools:
                if verbose:
                    print(f"Skipped _list tool: {module.__name__}.{name} (prefer search instead)", file=sys.stderr)
                continue

            # Register each function as an MCP tool
            mcp.tool(func)
            tools_registered += 1
            if verbose:
                # Use stderr to avoid interfering with JSON-RPC on stdout
                print(f"Registered tool: {module.__name__}.{name}", file=sys.stderr)

    return tools_registered


def get_s3_client(use_quilt_auth: bool = True):
    """Get an S3 client instance with optional Quilt authentication.

    Args:
        use_quilt_auth: Whether to use Quilt's STS session if available (default: True)

    Returns:
        boto3 S3 client instance
    """
    if use_quilt_auth:
        try:
            import quilt3

            # Check if we have Quilt session available
            if hasattr(quilt3, "logged_in") and quilt3.logged_in():
                if hasattr(quilt3, "get_boto3_session"):
                    session = quilt3.get_boto3_session()
                    if session is not None:
                        return session.client("s3")
        except Exception:
            pass

    # Fallback to default boto3 client
    return boto3.client("s3")


def get_sts_client(use_quilt_auth: bool = True):
    """Get an STS client instance with optional Quilt authentication.

    Args:
        use_quilt_auth: Whether to use Quilt's STS session if available (default: True)

    Returns:
        boto3 STS client instance
    """
    if use_quilt_auth:
        try:
            import quilt3

            # Check if we have Quilt session available
            if hasattr(quilt3, "logged_in") and quilt3.logged_in():
                if hasattr(quilt3, "get_boto3_session"):
                    session = quilt3.get_boto3_session()
                    if session is not None:
                        return session.client("sts")
        except Exception:
            pass

    # Fallback to default boto3 client
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

    # Register health check endpoints for HTTP transport
    transport = os.environ.get("FASTMCP_TRANSPORT", "stdio")
    if transport in ["http", "sse", "streamable-http"]:
        from quilt_mcp.health import (
            health_check_handler,
            healthz_handler,
            root_handler,
        )

        # Register all health check endpoint variations
        # Note: /mcp/* paths are reserved by FastMCP for protocol endpoints
        health_routes = [
            ("/health", health_check_handler),
            ("/healthz", healthz_handler),
            ("/", root_handler),
        ]

        for route, handler in health_routes:
            mcp.custom_route(route, methods=["GET"])(handler)
            if verbose:
                print(f"Registered health check endpoint: {route}", file=sys.stderr)

    if verbose:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Successfully registered {tools_count} tools", file=sys.stderr)

    return mcp


def run_server() -> None:
    """Run the MCP server with proper error handling."""
    try:
        # Create and configure the server
        mcp = create_configured_server()

        # Get transport from environment variable (default to stdio for MCP compatibility)
        transport_str = os.environ.get("FASTMCP_TRANSPORT", "stdio")

        # Validate transport string and fall back to default if invalid
        valid_transports = ["stdio", "http", "sse", "streamable-http"]
        if transport_str not in valid_transports:
            transport_str = "stdio"

        transport: Literal["stdio", "http", "sse", "streamable-http"] = transport_str  # type: ignore

        # Run the server
        mcp.run(transport=transport)

    except Exception as e:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        raise
