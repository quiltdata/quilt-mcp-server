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
from fastmcp import FastMCP
from fastmcp.resources import Resource

from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    push_runtime_context,
    reset_runtime_context,
    set_default_environment,
)
from quilt_mcp.services.bearer_auth_service import JwtAuthError, get_bearer_auth_service


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
    from importlib import import_module

    from quilt_mcp.tools import _MODULE_PATHS

    modules: list[Any] = []
    for module_name, module_path in _MODULE_PATHS.items():
        module = import_module(module_path)
        modules.append(module)
    return modules


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

    # Tools that are now available as resources MUST be excluded from MCP tool registration
    RESOURCE_AVAILABLE_TOOLS = [
        # Phase 1 - Core Discovery Resources
        "admin_users_list",
        "admin_roles_list",
        "admin_sso_config_get",
        "admin_tabulator_open_query_get",
        "athena_databases_list",
        "athena_workgroups_list",
        "list_metadata_templates",
        "show_metadata_examples",
        "fix_metadata_validation_issues",
        "workflow_list_all",
        "tabulator_buckets_list",
        # Phase 2 - Extended Discovery Resources
        "auth_status",
        "catalog_info",
        "catalog_name",
        "filesystem_status",
        "aws_permissions_discover",
        "bucket_recommendations_get",
        "bucket_access_check",
        "admin_user_get",
        "athena_table_schema",
        "athena_query_history",
        "tabulator_tables_list",
        "get_metadata_template",
        "workflow_get_status",
    ]

    # List of deprecated tools (to reduce client confusion)
    excluded_tools = {
        "search_graphql",  # Deprecated - use search_catalog
        "search_objects_graphql",  # Deprecated - use search_catalog
        "list_tabulator_buckets",  # Prefer tabulator_buckets_list resource
        "list_tabulator_tables",  # Prefer tabulator_tables_list resource
        "packages_list",  # Prefer unified_search
        "athena_tables_list",  # Prefer athena_query_execute
        "get_tabulator_service",  # Internal use only
    }

    # Merge resource-available tools into excluded set
    excluded_tools.update(RESOURCE_AVAILABLE_TOOLS)

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
            # Skip deprecated/tools now available as resources to reduce client confusion
            if name in excluded_tools:
                if verbose:
                    print(f"Skipped _list tool: {module.__name__}.{name} (excluded)", file=sys.stderr)
                continue

            # Register each function as an MCP tool
            mcp.tool(func)
            tools_registered += 1
            if verbose:
                # Use stderr to avoid interfering with JSON-RPC on stdout
                print(f"Registered tool: {module.__name__}.{name}", file=sys.stderr)

    return tools_registered


def _runtime_boto3_session() -> Optional[boto3.Session]:
    """Return a boto3 session sourced from the active runtime context if available."""
    try:
        from quilt_mcp.runtime_context import get_runtime_auth
    except ImportError:
        return None

    auth_state = get_runtime_auth()
    if not auth_state:
        return None

    extras = auth_state.extras or {}

    session = extras.get("boto3_session")
    if isinstance(session, boto3.Session):
        return session

    credentials = extras.get("aws_credentials")
    if isinstance(credentials, dict):
        access_key = credentials.get("access_key_id")
        secret_key = credentials.get("secret_access_key")
        session_token = credentials.get("session_token")
        region = credentials.get("region") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

        if access_key and secret_key:
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=region or "us-east-1",
            )

    return None


def get_s3_client(use_quilt_auth: bool = True):
    """Get an S3 client instance with optional Quilt authentication.

    Args:
        use_quilt_auth: Whether to use Quilt's STS session if available (default: True)

    Returns:
        boto3 S3 client instance
    """
    session = _runtime_boto3_session()
    if session:
        return session.client("s3")

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
    session = _runtime_boto3_session()
    if session:
        return session.client("sts")

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

    # Initialize resources AFTER creating server
    from quilt_mcp.resources import register_all_resources, get_registry
    from quilt_mcp.config import resource_config
    import sys

    if resource_config.RESOURCES_ENABLED:
        register_all_resources()
        registry = get_registry()
        resources = registry.list_resources()

        # Register each resource with FastMCP
        import re

        def create_handler(resource_uri: str):
            """Create a handler with proper closure for each resource URI."""
            # Extract parameters from URI pattern (e.g., {bucket} from tabulator://buckets/{bucket}/tables)
            param_names = re.findall(r'\{(\w+)\}', resource_uri)

            if param_names:
                # Create handler with parameters for template URIs
                async def parameterized_handler(**kwargs) -> str:
                    """Resource handler with URI parameters."""
                    # Construct the actual URI by replacing parameters
                    actual_uri = resource_uri
                    for param_name, param_value in kwargs.items():
                        actual_uri = actual_uri.replace(f"{{{param_name}}}", param_value)

                    response = await registry.read_resource(actual_uri)
                    return response._serialize_content()

                return parameterized_handler
            else:
                # Create simple handler for static URIs
                async def static_handler() -> str:
                    """Resource handler."""
                    response = await registry.read_resource(resource_uri)
                    return response._serialize_content()

                return static_handler

        for resource_info in resources:
            uri = resource_info["uri"]
            name = resource_info["name"]
            description = resource_info["description"]
            mime_type = resource_info["mimeType"]

            # Register with FastMCP using the new Resource.from_function API
            resource = Resource.from_function(
                fn=create_handler(uri),
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
            )
            mcp.add_resource(resource)

        if verbose:
            print(f"Registered {len(resources)} MCP resources", file=sys.stderr)

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


def build_http_app(mcp: FastMCP, transport: Literal["http", "sse", "streamable-http"] = "http"):
    """Configure the FastMCP HTTP app with JWT-aware middleware."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        app = mcp.http_app(transport=transport)
    except AttributeError as exc:  # pragma: no cover - FastMCP versions prior to HTTP support
        logger.error("HTTP transport requested but FastMCP does not expose http_app(): %s", exc)
        raise

    try:
        from starlette.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*", "Authorization", "Mcp-Session-Id", "MCP-Protocol-Version"],
            expose_headers=["mcp-session-id"],
            allow_credentials=False,
        )
    except ImportError:  # pragma: no cover - starlette optional guard
        logger.warning("CORS middleware unavailable; continuing without CORS configuration")

    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
        from starlette.datastructures import MutableHeaders
    except ImportError as exc:  # pragma: no cover
        logger.error("Starlette HTTP middleware unavailable: %s", exc)
        return app

    require_jwt = os.getenv("MCP_REQUIRE_JWT", "false").lower() == "true"

    class QuiltAuthMiddleware(BaseHTTPMiddleware):
        """Middleware that injects runtime auth state for HTTP requests."""

        HEALTH_PATHS = {"/health", "/healthz"}

        async def dispatch(self, request, call_next):
            context_token = None
            headers = MutableHeaders(scope=request.scope)
            accept_header = headers.get("accept", "")
            if "application/json" in accept_header and "text/event-stream" not in accept_header:
                headers["accept"] = f"{accept_header}, text/event-stream"

            if request.url.path in self.HEALTH_PATHS:
                return await call_next(request)

            authorization = request.headers.get("authorization")
            metadata = {"path": request.url.path}
            auth_state: Optional[RuntimeAuthState] = None

            if authorization:
                auth_service = get_bearer_auth_service()
                try:
                    jwt_result = auth_service.authenticate_header(authorization)
                    boto3_session = auth_service.build_boto3_session(jwt_result)
                    auth_state = RuntimeAuthState(
                        scheme="jwt",
                        access_token=jwt_result.token,
                        claims=jwt_result.claims,
                        extras={
                            "jwt_auth_result": jwt_result,
                            "aws_credentials": jwt_result.aws_credentials,
                            "aws_role_arn": jwt_result.aws_role_arn,
                            "boto3_session": boto3_session,
                        },
                    )
                except JwtAuthError as exc:
                    logger.warning("JWT authentication failed for %s: %s", request.url.path, exc.detail)
                    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=401)
            elif require_jwt:
                return JSONResponse(
                    {"error": "missing_authorization", "detail": "Bearer token required"},
                    status_code=401,
                )

            environment = "web-jwt" if auth_state else "web-iam"
            context_token = push_runtime_context(environment=environment, auth=auth_state, metadata=metadata)

            try:
                return await call_next(request)
            finally:
                if context_token is not None:
                    reset_runtime_context(context_token)

    app.add_middleware(QuiltAuthMiddleware)
    return app


def run_server(skip_banner: bool = False) -> None:
    """Run the MCP server with proper error handling.

    Args:
        skip_banner: If True, skip the FastMCP startup banner display.
                    Useful for multi-server setups where banner output can
                    interfere with JSON-RPC communication over stdio.
                    Defaults to False (show banner).
    """
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

        if transport == "stdio":
            set_default_environment("desktop-stdio")
            mcp.run(transport=transport, show_banner=not skip_banner)
            return

        set_default_environment("web-service")

        if transport in ["http", "sse", "streamable-http"]:
            app = build_http_app(mcp, transport=transport)

            import uvicorn

            host = os.environ.get("FASTMCP_ADDR") or os.environ.get("FASTMCP_HOST") or "127.0.0.1"
            port = int(os.environ.get("FASTMCP_PORT", "8000"))
            uvicorn.run(app, host=host, port=port, log_level="info")
            return

        mcp.run(transport=transport, show_banner=not skip_banner)

    except Exception as e:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        raise
