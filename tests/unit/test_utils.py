"""Unit tests for utils module (mocked, no external dependencies)."""

import inspect
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from fastmcp import FastMCP
from quilt_mcp.tools import auth, buckets, package_ops, packages
from quilt_mcp.utils import (
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

    def test_register_tools_registers_module_wrappers(self):
        """Test that module wrapper functions are registered as tools."""
        mock_server = Mock(spec=FastMCP)

        # Register tools (now uses wrapper functions, not individual functions)
        tools_count = register_tools(mock_server, verbose=False)

        # Should register 16 module wrappers (one per module)
        self.assertEqual(tools_count, 16)
        
        # Verify mock_server.tool was called 16 times
        self.assertEqual(mock_server.tool.call_count, 16)
        
        # Verify some expected wrapper names were registered
        registered_funcs = [call[0][0] for call in mock_server.tool.call_args_list]
        registered_names = [func.__name__ for func in registered_funcs]
        
        # Check that we have the expected wrapper functions
        expected_wrappers = [
            "auth", "buckets", "permissions", "packages", "search",
            "athena_glue", "governance", "tabulator"
        ]
        for wrapper_name in expected_wrappers:
            self.assertIn(wrapper_name, registered_names,
                f"Expected wrapper '{wrapper_name}' not found in registered tools")

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

    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_success(self, mock_create_server):
        """Test successful run_server execution."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Set environment variable to a valid transport
        with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "http"}):
            run_server()

        # Verify server was created and run was called
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once_with(transport="http")

    @patch("quilt_mcp.utils.create_configured_server")
    def test_run_server_default_transport(self, mock_create_server):
        """Test run_server with default transport."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Clear transport environment variable
        with patch.dict(os.environ, {}, clear=True):
            run_server()

        # Verify default transport is used
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
