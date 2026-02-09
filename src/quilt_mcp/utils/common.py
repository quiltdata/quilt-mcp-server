"""Shared utilities for Quilt MCP tools."""

from __future__ import annotations

import base64
import contextlib
import inspect
import io
import json
import os
import pathlib
import re
import sys
from typing import Any, Callable, Dict, Literal, Optional
from urllib.parse import parse_qs, unquote, urlparse

import boto3
from fastmcp import FastMCP
from fastmcp.resources import Resource

from quilt_mcp.context.runtime_context import (
    set_default_environment,
)


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


def normalize_url(url: str, *, strip_trailing_slash: bool = True) -> str:
    """Normalize URL by removing trailing slashes.

    This function is useful for constructing consistent URLs when building paths
    or endpoints. By default, removes trailing slashes to ensure predictable
    URL joining behavior.

    Args:
        url: URL string to normalize
        strip_trailing_slash: If True (default), remove trailing slash

    Returns:
        Normalized URL string

    Examples:
        >>> normalize_url("https://example.com/")
        'https://example.com'
        >>> normalize_url("https://api.quiltdata.com/")
        'https://api.quiltdata.com'
        >>> normalize_url("s3://bucket/")
        's3://bucket'
        >>> normalize_url("https://example.com/", strip_trailing_slash=False)
        'https://example.com/'
    """
    if not url:
        return url

    if strip_trailing_slash:
        return url.rstrip("/")

    return url


def graphql_endpoint(registry_url: str) -> str:
    """Construct GraphQL endpoint URL from registry URL.

    Standardizes GraphQL endpoint URL construction to ensure consistency
    across the codebase. The GraphQL endpoint is always at /graphql
    (not /api/graphql).

    Args:
        registry_url: Registry URL (HTTPS format, e.g., "https://registry.quiltdata.com")

    Returns:
        GraphQL endpoint URL (e.g., "https://registry.quiltdata.com/graphql")

    Examples:
        >>> graphql_endpoint("https://registry.quiltdata.com")
        'https://registry.quiltdata.com/graphql'
        >>> graphql_endpoint("https://registry.quiltdata.com/")
        'https://registry.quiltdata.com/graphql'
        >>> graphql_endpoint("https://nightly-registry.quilttest.com")
        'https://nightly-registry.quilttest.com/graphql'
    """
    normalized = normalize_url(registry_url)
    return f"{normalized}/graphql"


def get_dns_name_from_url(url: str) -> str:
    """Extract DNS hostname from a URL.

    Extracts the DNS hostname from a URL, removing common prefixes like 'www.'
    to provide a clean, human-readable catalog name.

    Args:
        url: URL string to extract hostname from (e.g., 'https://nightly.quilttest.com')

    Returns:
        DNS hostname (e.g., 'nightly.quilttest.com'), or 'unknown' if extraction fails

    Examples:
        >>> get_dns_name_from_url("https://nightly.quilttest.com")
        'nightly.quilttest.com'
        >>> get_dns_name_from_url("https://www.example.com")
        'example.com'
        >>> get_dns_name_from_url("")
        'unknown'
    """
    from urllib.parse import urlparse

    if not url:
        return "unknown"

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.netloc
        if hostname:
            # Remove common subdomain prefixes that don't add semantic value
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname
        return "unknown"
    except Exception:
        return "unknown"


def fix_url(url: str) -> str:
    """Convert non-URL paths to file:// URLs.

    This function normalizes file paths and URLs to ensure consistent URL format.
    Paths are expanded (tilde expansion), resolved to absolute paths, and converted
    to file:// URLs. URLs with existing schemes are returned as-is (except Windows
    drive letters which are treated as paths).

    Args:
        url: File path or URL to normalize

    Returns:
        Normalized URL string (file:// URL for paths, unchanged for existing URLs)

    Raises:
        ValueError: If url is empty or None

    Examples:
        >>> fix_url("~/data/file.csv")
        'file:///home/user/data/file.csv'
        >>> fix_url("./relative/path/")
        'file:///absolute/path/relative/path/'
        >>> fix_url("s3://bucket/key")
        's3://bucket/key'
        >>> fix_url("C:/Users/data")  # Windows
        'file:///C:/Users/data'
    """
    if not url:
        raise ValueError("Empty URL")

    url = str(url)

    parsed = urlparse(url)
    # If it has a scheme, we assume it's a URL.
    # On Windows, we ignore schemes that look like drive letters, e.g. C:/users/foo
    if parsed.scheme and not os.path.splitdrive(url)[0]:
        return url

    # `expanduser()` expands any leading "~" or "~user" path components, as a user convenience
    # `resolve()` _tries_ to make the URI absolute - but doesn't guarantee anything.
    # In particular, on Windows, non-existent files won't be resolved.
    # `absolute()` makes the URI absolute, though it can still contain '..'
    fixed_url = pathlib.Path(url).expanduser().resolve().absolute().as_uri()

    # pathlib likes to remove trailing slashes, so add it back if needed.
    if url[-1:] in (os.sep, os.altsep) and not fixed_url.endswith('/'):
        fixed_url += '/'

    return fixed_url


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
    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()
    excluded_modules = set()
    if mode_config.is_multiuser:
        excluded_modules.update({"workflow_orchestration"})

    modules: list[Any] = []
    for module_name, module_path in _MODULE_PATHS.items():
        if module_name in excluded_modules:
            continue
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

    from quilt_mcp.context.factory import RequestContextFactory
    from quilt_mcp.context.handler import wrap_tool_with_context

    context_factory = RequestContextFactory(mode="auto")

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
        # Note: discover_permissions is kept as TOOL (not resource) to accept parameters
        "bucket_recommendations_get",
        "athena_query_history",
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
        "get_tabulator_service",  # Internal use only
        "tabulator_open_query_status",  # Deprecated - use admin://config/tabulator resource
        "tabulator_open_query_toggle",  # Deprecated - use admin_tabulator_open_query_set tool
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
            wrapped = wrap_tool_with_context(func, context_factory)
            mcp.tool(wrapped)
            tools_registered += 1
            if verbose:
                # Use stderr to avoid interfering with JSON-RPC on stdout
                print(f"Registered tool: {module.__name__}.{name}", file=sys.stderr)

    return tools_registered


def _runtime_boto3_session() -> Optional[boto3.Session]:
    """Return a boto3 session sourced from the active runtime context if available."""
    try:
        from quilt_mcp.context.runtime_context import get_runtime_auth
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
    import sys

    mcp = create_mcp_server()

    # Validate auth configuration early so startup fails fast.
    try:
        from quilt_mcp.services.auth_service import create_auth_service
        from quilt_mcp.ops.factory import QuiltOpsFactory

        create_auth_service()

        # Also validate that QuiltOps can be created (Phase 1: quilt3 only)
        # This ensures that the abstraction layer is properly configured
        try:
            QuiltOpsFactory.create()
            if verbose:
                print("QuiltOps abstraction layer validated successfully", file=sys.stderr)
        except Exception as quilt_ops_exc:
            if verbose:
                print(f"QuiltOps validation failed: {quilt_ops_exc}", file=sys.stderr)
            # For now, we'll continue even if QuiltOps fails, as some tools might not need it
            # In the future, this could be made stricter based on which tools are enabled

    except Exception as exc:  # pragma: no cover - startup validation
        if verbose:
            print(f"Auth service initialization failed: {exc}", file=sys.stderr)
        raise

    # Register resources using FastMCP decorator pattern
    from quilt_mcp.config import resource_config

    if resource_config.RESOURCES_ENABLED:
        from quilt_mcp.tools.resources import register_resources

        register_resources(mcp)

        if verbose:
            print("Registered MCP resources", file=sys.stderr)

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

    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()

    try:
        # Use JSON responses in multiuser mode for simpler HTTP client integration
        # (SSE requires stream parsing which complicates testing and client implementations)
        app = mcp.http_app(
            transport=transport, stateless_http=mode_config.is_multiuser, json_response=mode_config.is_multiuser
        )
    except AttributeError as exc:  # pragma: no cover - FastMCP versions prior to HTTP support
        logger.error("HTTP transport requested but FastMCP does not expose http_app(): %s", exc)
        raise

    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.datastructures import MutableHeaders
    except ImportError as exc:  # pragma: no cover
        logger.error("Starlette HTTP middleware unavailable: %s", exc)
        return app

    class QuiltAcceptHeaderMiddleware(BaseHTTPMiddleware):
        """Middleware that fixes Accept headers for SSE compatibility."""

        HEALTH_PATHS = {"/health", "/healthz", "/"}

        async def dispatch(self, request, call_next):
            # Skip Accept header modification for health check endpoints
            if request.url.path in self.HEALTH_PATHS:
                return await call_next(request)

            headers = MutableHeaders(scope=request.scope)
            accept_header = headers.get("accept", "")

            # For MCP protocol endpoints, ensure both application/json and text/event-stream are present
            if request.url.path.startswith("/mcp"):
                needs_json = "application/json" not in accept_header
                needs_sse = "text/event-stream" not in accept_header

                if needs_json and needs_sse:
                    # No Accept header or missing both - add both
                    headers["accept"] = "application/json, text/event-stream"
                elif needs_json:
                    # Has SSE but not JSON
                    headers["accept"] = f"application/json, {accept_header}"
                elif needs_sse:
                    # Has JSON but not SSE
                    headers["accept"] = f"{accept_header}, text/event-stream"
            elif "application/json" in accept_header and "text/event-stream" not in accept_header:
                # For other endpoints, add SSE if JSON is present
                headers["accept"] = f"{accept_header}, text/event-stream"

            return await call_next(request)

    app.add_middleware(QuiltAcceptHeaderMiddleware)

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

    mode_config = get_mode_config()

    try:
        from quilt_mcp.middleware.jwt_extraction import JwtExtractionMiddleware

        # Add last so it runs first in Starlette's middleware stack.
        # This middleware only extracts JWT - GraphQL backend validates it.
        app.add_middleware(JwtExtractionMiddleware, require_jwt=mode_config.requires_jwt)
        if mode_config.requires_jwt:
            logger.info("JWT extraction middleware enabled for HTTP transport (validation at GraphQL)")
        else:
            logger.info("JWT extraction middleware present but not enforced (IAM mode)")
    except ImportError as exc:  # pragma: no cover
        logger.error("JWT extraction middleware unavailable: %s", exc)
        raise

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

    except (ImportError, ModuleNotFoundError) as e:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Error starting MCP server - Missing dependency: {e}", file=sys.stderr)
        print(file=sys.stderr)
        print("This error usually means a required Python package is not installed.", file=sys.stderr)
        print("Please install quilt-mcp with: uvx quilt-mcp  or  pip install quilt-mcp", file=sys.stderr)
        raise

    except Exception as e:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        error_msg = str(e)
        print(f"Error starting MCP server: {error_msg}", file=sys.stderr)

        # Provide helpful context for common error types
        if "address already in use" in error_msg.lower():
            print(file=sys.stderr)
            print("The server port is already in use. Try:", file=sys.stderr)
            print("1. Change the port with FASTMCP_PORT environment variable", file=sys.stderr)
            print("2. Stop the existing server process", file=sys.stderr)
        elif "permission denied" in error_msg.lower():
            print(file=sys.stderr)
            print("Permission denied. Check file/directory permissions or try a different port.", file=sys.stderr)
        elif "connection" in error_msg.lower():
            print(file=sys.stderr)
            print("Network connection issue. Check your network settings and firewall.", file=sys.stderr)

        raise


# JWT Utilities for Testing and Runtime


def get_jwt_from_auth_config(registry_url: str) -> Optional[str]:
    """
    Read JWT from ~/.quilt/auth.json for a given registry.

    Args:
        registry_url: The registry URL (e.g., "https://registry.quiltdata.com")

    Returns:
        JWT token string if found, None otherwise
    """
    auth_file = pathlib.Path.home() / ".quilt" / "auth.json"

    if not auth_file.exists():
        return None

    try:
        with open(auth_file) as f:
            auth_data = json.load(f)

        # Navigate: auth.json -> tokens -> {registry_url} -> token
        tokens = auth_data.get("tokens", {})
        registry_data = tokens.get(registry_url, {})
        token = registry_data.get("token")
        return token if isinstance(token, str) else None
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def extract_jwt_claims_unsafe(token: str) -> Dict[str, Any]:
    """
    Extract claims from JWT WITHOUT validation (debugging/logging only).

    WARNING: This does NOT validate the JWT signature, expiration, or issuer.
    Only use for debugging, logging, or when the JWT will be validated elsewhere.

    Args:
        token: JWT token string

    Returns:
        Decoded claims dictionary

    Raises:
        ValueError: If token is malformed
    """
    if not token or token.count(".") != 2:
        raise ValueError("Malformed JWT token - must have 3 dot-separated parts")

    # JWT format: header.payload.signature
    parts = token.split(".")
    payload = parts[1]

    # Add padding if needed (base64 requires length divisible by 4)
    padding = len(payload) % 4
    if padding:
        payload += "=" * (4 - padding)

    try:
        decoded_bytes = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded_bytes)
        if not isinstance(claims, dict):
            raise ValueError("JWT payload must be a JSON object")
        return claims
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to decode JWT payload: {exc}") from exc
