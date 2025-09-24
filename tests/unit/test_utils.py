"""Unit tests for utils module (mocked, no external dependencies)."""

import inspect
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from quilt_mcp.tools import auth, buckets, package_ops, packages
from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    get_runtime_auth,
    get_runtime_environment,
    clear_runtime_auth,
    push_runtime_context,
    reset_runtime_context,
    set_default_environment,
    set_runtime_auth,
    set_runtime_environment,
)
from quilt_mcp.services.bearer_auth_service import BearerAuthStatus
from quilt_mcp.utils import (
    build_http_app,
    create_configured_server,
    create_mcp_server,
    generate_signed_url,
    get_tool_modules,
    parse_s3_uri,
    register_tools,
    run_server,
)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_generate_signed_url_invalid_uri(self):
        """Test generate_signed_url with invalid URI."""
        # Not S3 URI
        self.assertIsNone(generate_signed_url("https://example.com/file"))

        # No path
        self.assertIsNone(generate_signed_url("s3://bucket"))

        # Empty string
        self.assertIsNone(generate_signed_url(""))

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_mocked(self, mock_s3_client):
        """Test successful URL generation with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_s3_client.return_value = mock_client

        result = generate_signed_url("s3://my-bucket/my-key.txt", 1800)

        self.assertEqual(result, "https://signed.url")
        mock_s3_client.assert_called_once()
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "my-key.txt"},
            ExpiresIn=1800,
        )

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_expiration_limits_mocked(self, mock_s3_client):
        """Test expiration time limits with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed.url"
        mock_s3_client.return_value = mock_client

        # Test minimum (0 should become 1)
        generate_signed_url("s3://bucket/key", 0)
        mock_client.generate_presigned_url.assert_called_with(
            "get_object", Params={"Bucket": "bucket", "Key": "key"}, ExpiresIn=1
        )

        # Test maximum (more than 7 days should become 7 days)
        generate_signed_url("s3://bucket/key", 700000)  # > 7 days
        mock_client.generate_presigned_url.assert_called_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "key"},
            ExpiresIn=604800,  # 7 days
        )

    @patch("quilt_mcp.utils.get_s3_client")
    def test_generate_signed_url_exception_mocked(self, mock_s3_client):
        """Test handling of exceptions during URL generation with mocks (unit test)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = Exception("AWS Error")
        mock_s3_client.return_value = mock_client

        result = generate_signed_url("s3://bucket/key")

        assert result is None

    def test_generate_signed_url_complex_key(self):
        """Test with complex S3 key containing slashes."""
        with patch("quilt_mcp.utils.get_s3_client") as mock_s3_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://signed.url"
            mock_s3_client.return_value = mock_client

            result = generate_signed_url("s3://bucket/path/to/my-file.txt")

            self.assertEqual(result, "https://signed.url")
            mock_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={"Bucket": "bucket", "Key": "path/to/my-file.txt"},
                ExpiresIn=3600,  # default
            )

    def test_parse_s3_uri_valid_basic_uri(self):
        """Test parse_s3_uri with valid basic S3 URI."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")
        self.assertIsNone(version_id)  # Phase 2: always returns None

    def test_parse_s3_uri_valid_complex_key(self):
        """Test parse_s3_uri with complex S3 key containing slashes."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/path/to/my-file.txt")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "path/to/my-file.txt")
        self.assertIsNone(version_id)  # Phase 2: always returns None

    def test_parse_s3_uri_with_versionid_parsed(self):
        """Test parse_s3_uri with versionId parameter (parsed in Phase 3)."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")  # Phase 3: query parameters extracted from key
        self.assertEqual(version_id, "abc123")  # Phase 3: returns parsed version_id

    def test_parse_s3_uri_with_versionid_extracted(self):
        """Test parse_s3_uri with versionId parameter (extracted in Phase 3)."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")  # Phase 3: query parameters extracted from key
        self.assertEqual(version_id, "abc123")  # Phase 3: returns parsed version_id

    def test_parse_s3_uri_invalid_not_s3_scheme(self):
        """Test parse_s3_uri with non-s3:// URI."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("https://bucket/key")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))

    def test_parse_s3_uri_invalid_empty_string(self):
        """Test parse_s3_uri with empty string."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))

    def test_parse_s3_uri_invalid_no_key(self):
        """Test parse_s3_uri with URI missing key."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket")

        # This should raise ValueError when trying to split without a slash
        # The exact error message will depend on the implementation

    def test_parse_s3_uri_invalid_only_scheme(self):
        """Test parse_s3_uri with only s3:// scheme."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://")

        # This should raise ValueError when trying to split an empty string

    def test_http_app_exposes_healthz(self):
        """HTTP transport should expose /healthz for load balancer checks."""
        server = create_configured_server()
        app = build_http_app(server, transport="http")

        with TestClient(app) as client:
            response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_http_app_exposes_custom_headers(self):
        """Ensure CORS requests expose the mcp-session-id header."""
        server = create_configured_server()
        app = build_http_app(server, transport="http")

        with TestClient(app) as client:
            response = client.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                },
                headers={"Origin": "https://example.com"},
            )

        expose_header = response.headers.get("Access-Control-Expose-Headers")
        self.assertIsNotNone(expose_header)
        self.assertIn("mcp-session-id", {h.strip().lower() for h in expose_header.split(",")})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


class TestRuntimeContext(unittest.TestCase):
    """Tests for runtime context helpers."""

    def tearDown(self) -> None:  # Ensure we always restore default context between tests
        set_default_environment("desktop")
        clear_runtime_auth()

    def test_runtime_context_default_environment(self):
        """Default environment should be desktop."""
        self.assertEqual(get_runtime_environment(), "desktop")

    def test_runtime_context_push_and_reset(self):
        """Pushing a new context should update environment and auth until reset."""
        token = push_runtime_context(environment="web-unauthenticated")
        try:
            self.assertEqual(get_runtime_environment(), "web-unauthenticated")
            set_runtime_environment("web-jwt")
            set_runtime_auth(RuntimeAuthState(scheme="jwt", access_token="token123"))
            self.assertEqual(get_runtime_environment(), "web-jwt")
            auth = get_runtime_auth()
            self.assertIsNotNone(auth)
            self.assertEqual(auth.scheme, "jwt")
            self.assertEqual(auth.access_token, "token123")
        finally:
            reset_runtime_context(token)

        self.assertEqual(get_runtime_environment(), "desktop")
        self.assertIsNone(get_runtime_auth())


class TestQuiltAuthMiddlewareRuntimeContext(unittest.TestCase):
    """Runtime context integration tests for Quilt auth middleware."""

    def tearDown(self) -> None:
        set_default_environment("desktop")
        clear_runtime_auth()

    def test_middleware_sets_and_resets_environment(self):
        """Middleware should set environment per request and reset afterwards."""
        server = create_configured_server()
        app = build_http_app(server, transport="http")

        async def runtime_env_endpoint(request):  # noqa: ARG001
            auth = get_runtime_auth()
            return JSONResponse(
                {
                    "environment": get_runtime_environment(),
                    "auth_scheme": auth.scheme if auth else None,
                    "has_token": bool(auth and auth.access_token),
                }
            )

        app.router.add_route("/runtime-env", runtime_env_endpoint, methods=["GET"])

        class DummyBearerAuthService:
            def decode_jwt_token(self, auth_header: str):
                return {
                    "id": "user-123",
                    "permissions": ["s3:GetObject"],
                    "roles": ["TestRole"],
                    "buckets": ["bucket" for _ in range(32)],
                    "scope": "write",
                }

            def extract_auth_claims(self, payload):
                return {
                    "permissions": payload["permissions"],
                    "roles": payload["roles"],
                    "groups": [],
                    "buckets": payload["buckets"],
                    "scope": payload["scope"],
                    "user_id": payload.get("id"),
                }

            def validate_bearer_token(self, access_token: str):
                return BearerAuthStatus.AUTHENTICATED, {
                    "username": "user-123",
                    "authorization": {
                        "aws_permissions": ["s3:GetObject"],
                        "buckets": ["bucket" for _ in range(32)],
                        "matched_roles": ["TestRole"],
                    },
                }

        with patch("quilt_mcp.services.bearer_auth_service.get_bearer_auth_service", return_value=DummyBearerAuthService()):
            with TestClient(app) as client:
                jwt_response = client.get(
                    "/runtime-env",
                    headers={"Authorization": "Bearer test-token", "Accept": "application/json"},
                )
                self.assertEqual(jwt_response.status_code, 200)
                self.assertEqual(jwt_response.json()["environment"], "web-jwt")
                self.assertEqual(jwt_response.json()["auth_scheme"], "jwt")
                self.assertTrue(jwt_response.json()["has_token"])

                anon_response = client.get("/runtime-env")
                self.assertEqual(anon_response.status_code, 200)
                self.assertEqual(anon_response.json()["environment"], "web-unauthenticated")
                self.assertIsNone(anon_response.json()["auth_scheme"])
                self.assertFalse(anon_response.json()["has_token"])


class TestBucketAuthorizationRuntimeContext(unittest.TestCase):
    """Tests ensuring bucket tools respect runtime context."""

    def tearDown(self) -> None:
        set_default_environment("desktop")
        clear_runtime_auth()

    def test_bucket_authorization_prefers_runtime_context(self):
        """Authorization should use runtime context even when env vars are unset."""

        class DummyBearerAuthService:
            def authorize_mcp_tool(self, tool_name, tool_args, auth_claims):
                return True

        runtime_auth = RuntimeAuthState(
            scheme="jwt",
            access_token="test-token",
            claims={
                "permissions": ["s3:ListBucket"],
                "roles": ["TestRole"],
                "buckets": ["quilt-bucket"],
            },
            extras={
                "user_info": {
                    "id": "user-123",
                    "permissions": ["s3:ListBucket"],
                    "roles": ["TestRole"],
                    "buckets": ["quilt-bucket"],
                    "scope": "read",
                }
            },
        )

        token = push_runtime_context(environment="web-jwt", auth=runtime_auth)
        try:
            with patch(
                "quilt_mcp.services.bearer_auth_service.get_bearer_auth_service",
                return_value=DummyBearerAuthService(),
            ):
                auth_result = buckets._check_authorization(
                    "bucket_objects_list", {"bucket": "quilt-bucket"}
                )
        finally:
            reset_runtime_context(token)

        self.assertTrue(auth_result["authorized"])

    def test_sse_transport_respects_cors_expose_headers(self):
        """SSE transport should expose mcp-session-id without protocol errors."""
        server = create_configured_server()
        app = build_http_app(server, transport="sse")

        with TestClient(app) as client:
            # Test CORS headers on a simple endpoint first
            response = client.get("/healthz", headers={"Origin": "https://example.com"})
            self.assertEqual(response.status_code, 200)
            
            # Check that CORS headers are properly set
            expose_header = response.headers.get("Access-Control-Expose-Headers")
            self.assertIsNotNone(expose_header)
            self.assertIn(
                "mcp-session-id",
                {h.strip().lower() for h in expose_header.split(",")},
            )
            
            # Verify CORS origin header
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request works correctly."""
        server = create_configured_server()
        app = build_http_app(server, transport="http")

        with TestClient(app) as client:
            # Test preflight request
            response = client.options(
                "/mcp/",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type"
                }
            )
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
            self.assertIn("content-type", response.headers.get("Access-Control-Allow-Headers", ""))

    def test_cors_headers_consistency_across_transports(self):
        """Test that CORS headers are consistent across different transports."""
        server = create_configured_server()
        
        transports = ["http", "sse", "streamable-http"]
        for transport in transports:
            with self.subTest(transport=transport):
                app = build_http_app(server, transport=transport)
                
                with TestClient(app) as client:
                    response = client.get("/healthz", headers={"Origin": "https://example.com"})
                    self.assertEqual(response.status_code, 200)
                    
                    # All transports should expose the mcp-session-id header
                    expose_header = response.headers.get("Access-Control-Expose-Headers")
                    self.assertIsNotNone(expose_header)
                    self.assertIn(
                        "mcp-session-id",
                        {h.strip().lower() for h in expose_header.split(",")},
                    )
                    
                    # All transports should allow any origin
                    self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    def test_parse_s3_uri_bucket_with_special_chars(self):
        """Test parse_s3_uri with bucket containing allowed special characters."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket-123/key.txt")

        self.assertEqual(bucket, "my-bucket-123")
        self.assertEqual(key, "key.txt")
        self.assertIsNone(version_id)

    def test_parse_s3_uri_key_with_special_chars(self):
        """Test parse_s3_uri with key containing special characters."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/path/with spaces and-symbols_123.txt")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "path/with spaces and-symbols_123.txt")
        self.assertIsNone(version_id)

    # Phase 3 Tests: versionId query parameter support

    def test_parse_s3_uri_with_valid_versionid(self):
        """Test parse_s3_uri with valid versionId query parameter."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/my-key.txt?versionId=abc123")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "my-key.txt")
        self.assertEqual(version_id, "abc123")

    def test_parse_s3_uri_with_versionid_complex_key(self):
        """Test parse_s3_uri with versionId and complex key path."""
        bucket, key, version_id = parse_s3_uri("s3://my-bucket/path/to/file.txt?versionId=def456")

        self.assertEqual(bucket, "my-bucket")
        self.assertEqual(key, "path/to/file.txt")
        self.assertEqual(version_id, "def456")

    def test_parse_s3_uri_with_url_encoded_key_and_versionid(self):
        """Test parse_s3_uri with URL encoded key and versionId."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/key%20with%20spaces?versionId=abc123")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "key with spaces")  # Should be URL decoded
        self.assertEqual(version_id, "abc123")

    def test_parse_s3_uri_with_url_encoded_path_and_versionid(self):
        """Test parse_s3_uri with URL encoded path separators and versionId."""
        bucket, key, version_id = parse_s3_uri("s3://bucket/path%2Fto%2Ffile?versionId=def456")

        self.assertEqual(bucket, "bucket")
        self.assertEqual(key, "path/to/file")  # Should be URL decoded
        self.assertEqual(version_id, "def456")

    def test_parse_s3_uri_with_invalid_query_parameter(self):
        """Test parse_s3_uri with invalid query parameter."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?other=value")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_with_multiple_query_parameters(self):
        """Test parse_s3_uri with multiple query parameters (versionId + other)."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?versionId=abc&other=value")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_with_prefix_query_parameter(self):
        """Test parse_s3_uri with prefix query parameter (should fail)."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("s3://bucket/key?prefix=test")

        self.assertIn("Unexpected S3 query string", str(context.exception))

    def test_parse_s3_uri_invalid_scheme_with_query(self):
        """Test parse_s3_uri with invalid scheme but valid query format."""
        with self.assertRaises(ValueError) as context:
            parse_s3_uri("https://bucket/key?versionId=abc123")

        self.assertIn("Invalid S3 URI scheme", str(context.exception))


class TestMCPServerConfiguration(unittest.TestCase):
    """Test MCP server creation and configuration."""

    def test_create_mcp_server(self):
        """Test that create_mcp_server returns a FastMCP instance."""
        server = create_mcp_server()
        self.assertIsInstance(server, FastMCP)

    def test_get_tool_modules(self):
        """Test that get_tool_modules returns expected modules."""
        modules = get_tool_modules()
        # The function returns 16 modules after adding new features
        self.assertEqual(len(modules), 16)
        # Check that key modules are included
        module_names = [m.__name__ for m in modules]
        self.assertIn("quilt_mcp.tools.auth", module_names)
        self.assertIn("quilt_mcp.tools.buckets", module_names)
        self.assertIn("quilt_mcp.tools.packages", module_names)
        self.assertIn("quilt_mcp.tools.package_ops", module_names)

    def test_register_tools_with_mock_server(self):
        """Test tool registration with a mock server."""
        mock_server = Mock(spec=FastMCP)

        # Test with verbose=False to avoid print output
        tools_count = register_tools(mock_server, verbose=False)

        # Verify that tools were registered
        self.assertGreater(tools_count, 0)
        self.assertEqual(mock_server.tool.call_count, tools_count)

    def test_register_tools_with_specific_modules(self):
        """Test tool registration with specific modules."""
        mock_server = Mock(spec=FastMCP)

        # Test with just one module
        tools_count = register_tools(mock_server, tool_modules=[auth], verbose=False)

        # Verify tools from auth module were registered
        self.assertGreater(tools_count, 0)
        self.assertEqual(mock_server.tool.call_count, tools_count)

    def test_register_tools_only_public_functions(self):
        """Test that only public functions are registered as tools."""
        mock_server = Mock(spec=FastMCP)

        # Create a mock module with both public and private functions
        mock_module = Mock()
        mock_module.__name__ = "test_module"

        def public_func():
            pass

        def _private_func():
            pass

        public_func.__name__ = "public_func"
        public_func.__module__ = "test_module"
        _private_func.__name__ = "_private_func"
        _private_func.__module__ = "test_module"

        # Mock inspect.getmembers to return our test functions
        # but also mock the predicate function to properly filter
        with patch("quilt_mcp.utils.inspect.getmembers") as mock_getmembers:
            # The predicate should only return the public function
            def mock_predicate(obj):
                return (
                    inspect.isfunction(obj)
                    and not obj.__name__.startswith("_")
                    and obj.__module__ == mock_module.__name__
                )

            # Filter the functions according to our predicate
            all_functions = [
                ("public_func", public_func),
                ("_private_func", _private_func),
            ]
            filtered_functions = [(name, func) for name, func in all_functions if mock_predicate(func)]
            mock_getmembers.return_value = filtered_functions

            tools_count = register_tools(mock_server, tool_modules=[mock_module], verbose=False)

            # Only public function should be registered
            self.assertEqual(tools_count, 1)
            mock_server.tool.assert_called_once_with(public_func)

    def test_register_tools_verbose_output(self):
        """Test that verbose mode produces output."""
        mock_server = Mock(spec=FastMCP)

        with patch("sys.stderr") as mock_stderr:
            # Register with verbose=True
            register_tools(mock_server, tool_modules=[auth], verbose=True)

            # Check that print was called
            mock_stderr.write.assert_called()

    def test_create_configured_server(self):
        """Test creating a fully configured server."""
        server = create_configured_server(verbose=False)

        self.assertIsInstance(server, FastMCP)
        # The server should have tools registered (we can't easily verify this
        # without inspecting internal state, but we can verify it doesn't crash)

    def test_create_configured_server_verbose_output(self):
        """Test that configured server produces verbose output."""
        with patch("sys.stderr") as mock_stderr:
            create_configured_server(verbose=True)

            # Check that print was called for verbose output
            mock_stderr.write.assert_called()

    @patch("uvicorn.run")
    @patch("quilt_mcp.utils.build_http_app")
    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_success(self, mock_create_server, mock_build_app, mock_uvicorn):
        """HTTP transport invokes uvicorn with configured app."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server
        mock_build_app.return_value = Mock()

        with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "http", "FASTMCP_PORT": "9000"}):
            run_server()

        mock_create_server.assert_called_once()
        mock_build_app.assert_called_once_with(mock_server, transport="http")
        mock_uvicorn.assert_called_once()
        mock_server.run.assert_not_called()

    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_default_transport(self, mock_create_server):
        """Test run_server with default transport."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Clear transport environment variable
        with patch.dict(os.environ, {}, clear=True):
            run_server()

        mock_server.run.assert_called_once_with(transport="stdio")

    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_error_handling(self, mock_create_server):
        """Test run_server error handling."""
        # Make create_configured_server raise an exception
        mock_create_server.side_effect = Exception("Test error")

        with self.assertRaises(Exception) as context:
            run_server()

        self.assertIn("Test error", str(context.exception))

    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_prints_error(self, mock_create_server):
        """Test that run_server prints errors."""
        mock_create_server.side_effect = Exception("Test error")

        with self.assertRaises(Exception) as context:
            run_server()

        # Check that we got the expected error
        self.assertEqual(str(context.exception), "Test error")

    def test_end_to_end_server_creation(self):
        """Test complete server creation and tool registration flow."""
        # This is an integration test that exercises the complete flow
        server = create_configured_server(verbose=False)

        # Verify we have a working server
        self.assertIsInstance(server, FastMCP)

        # Verify that our tool modules have the expected public functions
        for module in get_tool_modules():
            # Create a closure to capture the module variable properly
            def make_predicate(current_module):
                return lambda obj: (
                    inspect.isfunction(obj)
                    and not obj.__name__.startswith("_")
                    and obj.__module__ == current_module.__name__
                )

            functions = inspect.getmembers(module, predicate=make_predicate(module))
            # Each module should have at least one public function
            self.assertGreater(len(functions), 0)

    def test_all_tool_modules_importable(self):
        """Test that all tool modules can be imported and have expected structure."""
        modules = get_tool_modules()

        for module in modules:
            # Module should have a __name__ attribute
            self.assertTrue(hasattr(module, "__name__"))

            # Module should be one of our expected modules
            expected_modules = [
                "quilt_mcp.tools.auth",
                "quilt_mcp.tools.buckets",
                "quilt_mcp.tools.packages",
                "quilt_mcp.tools.package_ops",
                "quilt_mcp.tools.s3_package",
                "quilt_mcp.tools.permissions",
                "quilt_mcp.tools.unified_package",
                "quilt_mcp.tools.metadata_templates",
                "quilt_mcp.tools.package_management",
                "quilt_mcp.tools.metadata_examples",
                "quilt_mcp.tools.quilt_summary",
                "quilt_mcp.tools.athena_glue",
                "quilt_mcp.tools.tabulator",
                "quilt_mcp.tools.graphql",
                "quilt_mcp.tools.governance",
                "quilt_mcp.tools.search",
                "quilt_mcp.tools.workflow_orchestration",
            ]
            self.assertIn(module.__name__, expected_modules)

            # Module should have at least one function
            functions = [obj for name, obj in inspect.getmembers(module, inspect.isfunction)]
            self.assertGreater(len(functions), 0)
