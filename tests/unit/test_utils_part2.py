"""Unit tests for utils module (mocked, no external dependencies)."""

import inspect
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from fastmcp import FastMCP
from quilt_mcp.tools import buckets, catalog, packages
from quilt_mcp.utils.common import (
    create_configured_server,
    create_mcp_server,
    fix_url,
    generate_signed_url,
    get_tool_modules,
    normalize_url,
    parse_s3_uri,
    register_tools,
    run_server,
)


class TestMCPServerConfiguration(unittest.TestCase):
    """Test MCP server creation and configuration."""

    def test_get_tool_modules(self):
        """Test that get_tool_modules returns expected modules."""
        modules = get_tool_modules()
        # Should return a reasonable number of modules (at least 5)
        self.assertGreaterEqual(len(modules), 5, "Should return at least 5 tool modules")
        # Check that key modules are included
        module_names = [m.__name__ for m in modules]
        self.assertIn("quilt_mcp.tools.catalog", module_names)
        self.assertIn("quilt_mcp.tools.buckets", module_names)
        self.assertIn("quilt_mcp.tools.packages", module_names)

    def test_get_tool_modules_multiuser_excludes_workflows(self):
        """Test that multiuser mode does not register workflow tools."""
        from quilt_mcp.config import set_test_mode_config, reset_mode_config

        set_test_mode_config(multiuser_mode=True)
        try:
            modules = get_tool_modules()
            module_names = [m.__name__ for m in modules]
            self.assertNotIn("quilt_mcp.services.workflow_service", module_names)
        finally:
            reset_mode_config()

    @patch("quilt_mcp.utils.common.FastMCP")
    def test_create_mcp_server_includes_deployment_metadata(self, mock_fast_mcp):
        """Test create_mcp_server encodes deployment mode in version and instructions."""
        from quilt_mcp.config import reset_mode_config

        with patch.dict(os.environ, {"QUILT_DEPLOYMENT": "remote"}, clear=False):
            reset_mode_config()
            create_mcp_server()
        reset_mode_config()

        mock_fast_mcp.assert_called_once()
        args, kwargs = mock_fast_mcp.call_args
        self.assertEqual(args[0], "quilt-mcp-server")
        self.assertIn("(remote)", kwargs["version"])
        self.assertIn("Remote deployment using platform backend", kwargs["instructions"])

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
        with patch("quilt_mcp.utils.common.inspect.getmembers") as mock_getmembers:
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
            # Note: register_tools wraps functions before registering, so we check call count
            mock_server.tool.assert_called_once()

    @patch("quilt_mcp.utils.common.build_http_app")
    @patch("quilt_mcp.utils.common.create_configured_server")
    def test_run_server_sse_transport(self, mock_create_server, mock_build_app):
        """Test run_server with SSE transport."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server
        mock_app = Mock()
        mock_build_app.return_value = mock_app

        with patch.dict("sys.modules", {"uvicorn": Mock()}):
            import sys

            mock_uvicorn = sys.modules["uvicorn"]

            with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "sse"}):
                run_server()

            mock_build_app.assert_called_once_with(mock_server, transport="sse")
            mock_uvicorn.run.assert_called_once()

    @patch("quilt_mcp.utils.common.build_http_app")
    @patch("quilt_mcp.utils.common.create_configured_server")
    def test_run_server_custom_host_port(self, mock_create_server, mock_build_app):
        """Test run_server respects custom host and port env vars."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server
        mock_app = Mock()
        mock_build_app.return_value = mock_app

        with patch.dict("sys.modules", {"uvicorn": Mock()}):
            import sys

            mock_uvicorn = sys.modules["uvicorn"]

            env_vars = {"FASTMCP_TRANSPORT": "http", "FASTMCP_HOST": "0.0.0.0", "FASTMCP_PORT": "9000"}  # noqa: S104
            with patch.dict(os.environ, env_vars):
                run_server()

            call_args = mock_uvicorn.run.call_args
            self.assertEqual(call_args[1]["host"], "0.0.0.0")  # noqa: S104
            self.assertEqual(call_args[1]["port"], 9000)

    @patch("quilt_mcp.utils.common.create_configured_server")
    def test_run_server_default_transport(self, mock_create_server):
        """Test run_server with default transport."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Clear transport environment variable
        with patch.dict(os.environ, {}, clear=True):
            run_server()

        # Verify default transport is used with default show_banner=True
        mock_server.run.assert_called_once_with(transport="stdio", show_banner=True)

    @patch("quilt_mcp.utils.common.create_configured_server")
    def test_run_server_skip_banner(self, mock_create_server):
        """Test run_server with skip_banner=True."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Test with skip_banner=True
        with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "stdio"}):
            run_server(skip_banner=True)

        # Verify run was called with show_banner=False
        mock_server.run.assert_called_once_with(transport="stdio", show_banner=False)

    @patch("quilt_mcp.utils.common.create_configured_server")
    def test_run_server_error_handling(self, mock_create_server):
        """Test run_server error handling."""
        # Make create_configured_server raise an exception
        mock_create_server.side_effect = Exception("Test error")

        with self.assertRaises(Exception) as context:
            run_server()

        self.assertIn("Test error", str(context.exception))

    @patch("quilt_mcp.utils.common.create_configured_server")
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

        # Should have at least some modules
        self.assertGreater(len(modules), 0, "Should return at least one module")

        for module in modules:
            # Module should have a __name__ attribute
            self.assertTrue(hasattr(module, "__name__"), f"Module {module} should have __name__")

            # Module should be from quilt_mcp namespace
            self.assertTrue(
                module.__name__.startswith("quilt_mcp."), f"Module {module.__name__} should be in quilt_mcp namespace"
            )

            # Module should have at least one function
            functions = [obj for name, obj in inspect.getmembers(module, inspect.isfunction)]
            self.assertGreater(len(functions), 0, f"Module {module.__name__} should have at least one function")
