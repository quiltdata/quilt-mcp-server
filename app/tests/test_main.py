"""Tests for main.py server configuration and tool registration."""

import inspect
import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import FastMCP
from quilt_mcp.tools import auth, buckets, package_ops, packages
from quilt_mcp.utils import (
    create_configured_server,
    create_mcp_server,
    get_tool_modules,
    register_tools,
)

from app.main import main


class TestMCPServerCreation:
    """Test MCP server creation and configuration."""

    def test_create_mcp_server(self):
        """Test that create_mcp_server returns a FastMCP instance."""
        server = create_mcp_server()
        assert isinstance(server, FastMCP)

    def test_get_tool_modules(self):
        """Test that get_tool_modules returns expected modules."""
        modules = get_tool_modules()
        expected_modules = [auth, buckets, packages, package_ops]
        assert modules == expected_modules
        assert len(modules) == 4


class TestToolRegistration:
    """Test tool registration functionality."""

    def test_register_tools_with_mock_server(self):
        """Test tool registration with a mock server."""
        mock_server = Mock(spec=FastMCP)

        # Test with verbose=False to avoid print output
        tools_count = register_tools(mock_server, verbose=False)

        # Verify that tools were registered
        assert tools_count > 0
        assert mock_server.tool.call_count == tools_count

    def test_register_tools_with_specific_modules(self):
        """Test tool registration with specific modules."""
        mock_server = Mock(spec=FastMCP)

        # Test with just one module
        tools_count = register_tools(mock_server, tool_modules=[auth], verbose=False)

        # Verify tools from auth module were registered
        assert tools_count > 0
        assert mock_server.tool.call_count == tools_count

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
        with patch("inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = [
                ("public_func", public_func),
                ("_private_func", _private_func),
            ]

            tools_count = register_tools(mock_server, tool_modules=[mock_module], verbose=False)

            # Only public function should be registered
            assert tools_count == 1
            mock_server.tool.assert_called_once_with(public_func)

    def test_register_tools_verbose_output(self, capsys):
        """Test that verbose mode produces output."""
        mock_server = Mock(spec=FastMCP)

        # Register with verbose=True
        register_tools(mock_server, tool_modules=[auth], verbose=True)

        # Check that output was produced
        captured = capsys.readouterr()
        assert "Registered tool:" in captured.out
        assert "quilt_mcp.tools.auth" in captured.out


class TestServerConfiguration:
    """Test complete server configuration."""

    def test_create_configured_server(self):
        """Test creating a fully configured server."""
        server = create_configured_server(verbose=False)

        assert isinstance(server, FastMCP)
        # The server should have tools registered (we can't easily verify this
        # without inspecting internal state, but we can verify it doesn't crash)

    def test_create_configured_server_verbose_output(self, capsys):
        """Test that configured server produces verbose output."""
        create_configured_server(verbose=True)

        captured = capsys.readouterr()
        assert "Registered tool:" in captured.out
        assert "Successfully registered" in captured.out
        assert "tools" in captured.out


class TestMainFunction:
    """Test the main function and entry point."""

    @patch("app.main.create_configured_server")
    def test_main_success(self, mock_create_server):
        """Test successful main function execution."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Set environment variable
        with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "test-transport"}):
            main()

        # Verify server was created and run was called
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once_with(transport="test-transport")

    @patch("app.main.create_configured_server")
    def test_main_default_transport(self, mock_create_server):
        """Test main function with default transport."""
        mock_server = Mock(spec=FastMCP)
        mock_create_server.return_value = mock_server

        # Clear transport environment variable
        with patch.dict(os.environ, {}, clear=True):
            main()

        # Verify default transport is used
        mock_server.run.assert_called_once_with(transport="streamable-http")

    @patch("app.main.create_configured_server")
    def test_main_error_handling(self, mock_create_server):
        """Test main function error handling."""
        # Make create_configured_server raise an exception
        mock_create_server.side_effect = Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            main()

    @patch("app.main.create_configured_server")
    def test_main_prints_error(self, mock_create_server, capsys):
        """Test that main function prints errors."""
        test_error = Exception("Test error")
        mock_create_server.side_effect = test_error

        with pytest.raises(Exception, match="Test error"):
            main()

        captured = capsys.readouterr()
        assert "Error starting MCP server: Test error" in captured.out


class TestIntegration:
    """Integration tests for the complete flow."""

    def test_end_to_end_server_creation(self):
        """Test complete server creation and tool registration flow."""
        # This is an integration test that exercises the complete flow
        server = create_configured_server(verbose=False)

        # Verify we have a working server
        assert isinstance(server, FastMCP)

        # Verify that our tool modules have the expected public functions
        for module in get_tool_modules():

            def make_predicate(mod):
                return lambda obj: (
                    inspect.isfunction(obj)
                    and not obj.__name__.startswith("_")
                    and obj.__module__ == mod.__name__
                )

            functions = inspect.getmembers(module, predicate=make_predicate(module))
            # Each module should have at least one public function
            assert len(functions) > 0

    def test_all_tool_modules_importable(self):
        """Test that all tool modules can be imported and have expected structure."""
        modules = get_tool_modules()

        for module in modules:
            # Module should have a __name__ attribute
            assert hasattr(module, "__name__")

            # Module should be one of our expected modules
            assert module.__name__ in [
                "quilt_mcp.tools.auth",
                "quilt_mcp.tools.buckets",
                "quilt_mcp.tools.packages",
                "quilt_mcp.tools.package_ops",
            ]

            # Module should have at least one function
            functions = [obj for name, obj in inspect.getmembers(module, inspect.isfunction)]
            assert len(functions) > 0
