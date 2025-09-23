"""Shared utilities for Quilt MCP tools."""

from __future__ import annotations

import inspect
import os
import re
import sys
import io
import time
import contextlib
from typing import Any, Dict, Literal, Callable
from urllib.parse import urlparse, parse_qs, unquote

import boto3
from fastmcp import FastMCP
from starlette.responses import JSONResponse


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
    # Create FastMCP server with proper configuration for HTTP transport
    mcp = FastMCP("quilt-mcp-server")
    
    # Configure for HTTP transport to handle initialization properly
    # This helps resolve the "Received request before initialization was complete" issue
    if hasattr(mcp, '_session_manager'):
        # Allow early requests to be processed
        mcp._session_manager._allow_early_requests = True
    
    return mcp


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

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def _health_check(_request):  # type: ignore[reportUnusedFunction]
        """Comprehensive health endpoint for load balancers and monitoring."""
        import time
        import psutil
        
        try:
            # Basic health indicators
            health_data = {
                "status": "ok",
                "timestamp": time.time(),
                "uptime_seconds": time.time() - psutil.boot_time(),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "cpu_usage_percent": psutil.cpu_percent(interval=1),
                "mcp_tools_count": len(mcp.tools),
                "transport": "sse" if hasattr(mcp, '_transport') else "unknown"
            }
            
            # Check if we're under resource pressure
            if health_data["memory_usage_percent"] > 90:
                health_data["status"] = "degraded"
                health_data["warning"] = "High memory usage"
            elif health_data["cpu_usage_percent"] > 90:
                health_data["status"] = "degraded" 
                health_data["warning"] = "High CPU usage"
                
            return JSONResponse(health_data)
            
        except Exception as e:
            # Fallback to basic health check if monitoring fails
            return JSONResponse({
                "status": "ok",
                "timestamp": time.time(),
                "basic_check": True,
                "note": "Basic health check only"
            })

    if verbose:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Successfully registered {tools_count} tools", file=sys.stderr)

    return mcp


def build_http_app(mcp: FastMCP, transport: Literal["http", "sse", "streamable-http"] = "http"):
    """Return an ASGI app for HTTP transports with CORS configured."""
    # Configure FastMCP with proper settings for HTTP transport
    # This helps resolve initialization timing issues
    if hasattr(mcp, '_config'):
        mcp._config['allow_early_requests'] = True
    
    app = mcp.http_app(transport=transport)

    # Add OAuth 2.1 authorization endpoints BEFORE CORS middleware
    # This ensures OAuth endpoints are registered with highest priority
    _add_oauth_endpoints(app)

    try:
        from starlette.middleware.cors import CORSMiddleware

        # Configure CORS middleware with proper settings for MCP Streamable HTTP
        # According to MCP spec: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # For development - in production, specify actual origins
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # MCP requires both GET and POST
            allow_headers=[
                "*",  # Allow all headers including MCP-Protocol-Version and Mcp-Session-Id
                "Content-Type",
                "Accept", 
                "MCP-Protocol-Version",
                "Mcp-Session-Id",
                "Authorization",  # Required for OAuth 2.1 Bearer tokens
                "Origin",
                "Access-Control-Request-Method",
                "Access-Control-Request-Headers"
            ],
            allow_credentials=False,  # Set to False to allow "*" origins
            expose_headers=["mcp-session-id"],  # Required by MCP spec for session management
        )
        
    except ImportError as exc:  # pragma: no cover
        print(f"Warning: CORS middleware unavailable: {exc}", file=sys.stderr)

    return app


def _add_oauth_endpoints(app):
    """Add OAuth 2.1 authorization endpoints required by MCP specification."""
    from fastapi import Request, Form, Query, HTTPException
    from fastapi.responses import JSONResponse, RedirectResponse
    from quilt_mcp.services.oauth_service import get_oauth_service
    import hashlib
    import base64
    import secrets
    
    # In-memory storage for authorization codes (in production, use Redis or database)
    authorization_codes = {}
    
    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource_metadata(_request: Request):
        """OAuth 2.0 Protected Resource Metadata (RFC9728) for MCP authorization discovery."""
        oauth_service = get_oauth_service()
        return JSONResponse(oauth_service.get_protected_resource_metadata())
    
    @app.get("/.well-known/oauth-authorization-server")
    async def oauth_authorization_server_metadata(_request: Request):
        """OAuth 2.0 Authorization Server Metadata (RFC8414) for MCP authorization."""
        oauth_service = get_oauth_service()
        return JSONResponse(oauth_service.get_authorization_server_metadata())
    
    @app.get("/oauth/authorize")
    async def oauth_authorize(
        _request: Request,
        response_type: str = Query(..., description="Response type (must be 'code')"),
        client_id: str = Query(..., description="Client identifier"),
        redirect_uri: str = Query(..., description="Redirect URI"),
        scope: str = Query(..., description="Requested scopes"),
        state: str = Query(..., description="State parameter"),
        code_challenge: str = Query(..., description="PKCE code challenge"),
        code_challenge_method: str = Query(default="S256", description="PKCE challenge method")
    ):
        """OAuth 2.1 authorization endpoint with PKCE support."""
        
        # Validate response type
        if response_type != "code":
            raise HTTPException(status_code=400, detail="Unsupported response type")
        
        # Validate PKCE challenge method
        if code_challenge_method != "S256":
            raise HTTPException(status_code=400, detail="Unsupported code challenge method")
        
        # Generate authorization code
        auth_code = secrets.token_urlsafe(32)
        
        # Store authorization code with metadata
        authorization_codes[auth_code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
            "expires_at": time.time() + 600  # 10 minutes
        }
        
        # For demo purposes, redirect back to client with authorization code
        # In production, this would redirect to Quilt's authentication system
        redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
        return RedirectResponse(url=redirect_url)
    
    @app.post("/oauth/token")
    async def oauth_token(
        _request: Request,
        grant_type: str = Form(..., description="Grant type"),
        code: str = Form(..., description="Authorization code"),
        redirect_uri: str = Form(..., description="Redirect URI"),
        client_id: str = Form(..., description="Client identifier"),
        code_verifier: str = Form(None, description="PKCE code verifier")
    ):
        """OAuth 2.1 token endpoint with PKCE validation."""
        
        # Validate grant type
        if grant_type != "authorization_code":
            raise HTTPException(status_code=400, detail="Unsupported grant type")
        
        # Check if authorization code exists and is valid
        if code not in authorization_codes:
            raise HTTPException(status_code=400, detail="Invalid authorization code")
        
        auth_data = authorization_codes[code]
        
        # Check expiration
        if time.time() > auth_data["expires_at"]:
            del authorization_codes[code]
            raise HTTPException(status_code=400, detail="Authorization code expired")
        
        # Validate client ID and redirect URI
        if auth_data["client_id"] != client_id:
            raise HTTPException(status_code=400, detail="Invalid client")
        
        if auth_data["redirect_uri"] != redirect_uri:
            raise HTTPException(status_code=400, detail="Invalid redirect URI")
        
        # Validate PKCE code verifier
        if auth_data["code_challenge_method"] == "S256" and code_verifier:
            # Verify PKCE challenge
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip("=")
            
            if challenge != auth_data["code_challenge"]:
                raise HTTPException(status_code=400, detail="Invalid code verifier")
        
        # Generate access token
        oauth_service = get_oauth_service()
        scopes = auth_data["scope"].split()
        token_response = oauth_service.generate_access_token(client_id, scopes)
        
        # Clean up authorization code
        del authorization_codes[code]
        
        return JSONResponse(token_response)
    
    @app.post("/oauth/refresh", include_in_schema=False)  # Alternative endpoint for refresh token
    async def oauth_refresh_token(
        _request: Request,
        grant_type: str = Form(..., description="Grant type"),
        refresh_token: str = Form(..., description="Refresh token"),
        client_id: str = Form(..., description="Client identifier")
    ):
        """OAuth 2.1 refresh token endpoint."""
        
        if grant_type != "refresh_token":
            raise HTTPException(status_code=400, detail="Unsupported grant type")
        
        # For now, generate a new token (in production, validate refresh token)
        # TODO: Validate refresh_token parameter
        _ = refresh_token  # Suppress unused parameter warning
        
        oauth_service = get_oauth_service()
        token_response = oauth_service.generate_access_token(client_id)
        
        return JSONResponse(token_response)
    
    @app.get("/oauth/jwks")
    async def oauth_jwks(_request: Request):
        """OAuth 2.1 JWKS endpoint for token validation."""
        # Return empty JWKS for now since we're using HMAC
        return JSONResponse({"keys": []})
    
    @app.get("/oauth/userinfo")
    async def oauth_userinfo(request: Request):
        """OAuth 2.1 user info endpoint."""
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization required")
        
        token = auth_header[7:]
        oauth_service = get_oauth_service()
        
        try:
            payload = oauth_service.validate_access_token(token)
            return JSONResponse({
                "sub": payload["sub"],
                "scope": payload["scope"],
                "aud": payload["aud"],
                "iss": payload["iss"]
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid token") from e


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

        # For HTTP transport, add CORS middleware
        if transport in ["http", "streamable-http", "sse"]:
            app = build_http_app(mcp, transport=transport)

            import uvicorn

            # Support both FASTMCP_ADDR (production) and FASTMCP_HOST (legacy) for compatibility
            host = os.environ.get("FASTMCP_ADDR") or os.environ.get("FASTMCP_HOST", "0.0.0.0")
            port = int(os.environ.get("FASTMCP_PORT", "8000"))
            uvicorn.run(app, host=host, port=port, log_level="info")
            return

        # Run the server with standard transport
        mcp.run(transport=transport)

    except Exception as e:
        # Use stderr to avoid interfering with JSON-RPC on stdout
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        raise
