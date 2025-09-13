"""
Tests for MCP Optimization Integration Module

This module provides comprehensive unit tests for the optimization/integration.py module,
focusing on error scenarios, edge cases, and boundary conditions that are difficult
to trigger in integration tests.
"""

import os
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
from contextlib import nullcontext

from quilt_mcp.optimization.integration import (
    OptimizedMCPServer,
    create_optimized_server,
    optimization_tool,
    run_optimized_server,
    patch_utils_for_optimization,
)
from quilt_mcp.optimization.interceptor import OptimizationContext


class TestOptimizedMCPServer:
    """Test the OptimizedMCPServer class functionality."""

    def test_init_with_optimization_enabled_by_default(self):
        """Test server initialization with optimization enabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
                 patch('quilt_mcp.optimization.integration.TelemetryConfig') as mock_telemetry_config, \
                 patch('quilt_mcp.optimization.integration.configure_telemetry') as mock_configure_telemetry, \
                 patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
                 patch('quilt_mcp.optimization.integration.get_telemetry_collector') as mock_get_telemetry:
                
                mock_server = Mock()
                # Make _tools an empty dict so it's iterable
                mock_server._tools = {}
                mock_create_server.return_value = mock_server
                mock_config = Mock()
                mock_telemetry_config.from_env.return_value = mock_config
                mock_interceptor = Mock()
                mock_get_interceptor.return_value = mock_interceptor
                mock_telemetry = Mock()
                mock_get_telemetry.return_value = mock_telemetry
                
                server = OptimizedMCPServer()
                
                assert server.optimization_enabled is True
                mock_telemetry_config.from_env.assert_called_once()
                mock_configure_telemetry.assert_called_once_with(mock_config)
                assert server.mcp_server == mock_server
                assert server.interceptor == mock_interceptor
                assert server.telemetry == mock_telemetry

    def test_init_with_optimization_disabled_by_env(self):
        """Test server initialization with optimization disabled via environment variable."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "false"}), \
             patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            
            server = OptimizedMCPServer()
            
            assert server.optimization_enabled is False
            assert server.mcp_server == mock_server
            assert server.interceptor is None
            assert server.telemetry is None

    def test_init_with_explicit_optimization_parameter(self):
        """Test server initialization with explicit optimization parameter overriding environment."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            
            server = OptimizedMCPServer(enable_optimization=False)
            
            assert server.optimization_enabled is False
            assert server.interceptor is None
            assert server.telemetry is None

    def test_init_telemetry_configuration_error(self):
        """Test server initialization when telemetry configuration fails."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
             patch('quilt_mcp.optimization.integration.TelemetryConfig') as mock_telemetry_config, \
             patch('quilt_mcp.optimization.integration.configure_telemetry') as mock_configure_telemetry:
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            mock_configure_telemetry.side_effect = Exception("Telemetry config failed")
            
            # Should not raise exception, just continue without telemetry
            with pytest.raises(Exception, match="Telemetry config failed"):
                OptimizedMCPServer()

    def test_apply_optimization_wrappers_success(self):
        """Test successful application of optimization wrappers to tools."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            mock_server = Mock()
            mock_tools = {
                "tool1": Mock(),
                "tool2": Mock(),
            }
            mock_server._tools = mock_tools
            mock_create_server.return_value = mock_server
            
            mock_interceptor = Mock()
            mock_wrapped_tool1 = Mock()
            mock_wrapped_tool2 = Mock()
            mock_interceptor.intercept_tool_call.side_effect = [mock_wrapped_tool1, mock_wrapped_tool2]
            mock_get_interceptor.return_value = mock_interceptor
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Verify tools were wrapped
            assert mock_tools["tool1"] == mock_wrapped_tool1
            assert mock_tools["tool2"] == mock_wrapped_tool2
            assert mock_interceptor.intercept_tool_call.call_count == 2

    def test_apply_optimization_wrappers_no_tools(self):
        """Test optimization wrapper application when no tools exist."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            mock_server = Mock()
            mock_server._tools = {}
            mock_create_server.return_value = mock_server
            
            mock_interceptor = Mock()
            mock_get_interceptor.return_value = mock_interceptor
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Should not crash with empty tools
            mock_interceptor.intercept_tool_call.assert_not_called()

    def test_apply_optimization_wrappers_missing_tools_attribute(self):
        """Test optimization wrapper application when server has no _tools attribute."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            mock_server = Mock()
            # Delete _tools attribute to simulate missing attribute
            del mock_server._tools
            mock_create_server.return_value = mock_server
            
            mock_interceptor = Mock()
            mock_get_interceptor.return_value = mock_interceptor
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Should handle missing _tools gracefully
            mock_interceptor.intercept_tool_call.assert_not_called()

    def test_run_with_optimization_context_enabled(self):
        """Test optimization context creation when optimization is enabled."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'), \
             patch('quilt_mcp.optimization.integration.optimization_context') as mock_optimization_context:
            
            mock_interceptor = Mock()
            mock_get_interceptor.return_value = mock_interceptor
            mock_context_manager = Mock()
            mock_optimization_context.return_value = mock_context_manager
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            result = server.run_with_optimization_context(
                user_intent="test intent",
                task_type="test task",
                performance_target="speed"
            )
            
            assert result == mock_context_manager
            mock_optimization_context.assert_called_once()
            
            # Verify OptimizationContext was created with correct parameters
            call_args = mock_optimization_context.call_args[0][0]
            assert call_args.user_intent == "test intent"
            assert call_args.task_type == "test task"
            assert call_args.performance_target == "speed"
            assert call_args.cache_enabled is True

    def test_run_with_optimization_context_disabled(self):
        """Test optimization context when optimization is disabled."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'):
            
            server = OptimizedMCPServer(enable_optimization=False)
            
            result = server.run_with_optimization_context()
            
            # Should return nullcontext when optimization is disabled
            assert isinstance(result, type(nullcontext()))

    def test_run_with_optimization_context_no_interceptor(self):
        """Test optimization context when interceptor is None."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            mock_get_interceptor.return_value = None
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            result = server.run_with_optimization_context()
            
            # Should return nullcontext when interceptor is None
            assert isinstance(result, type(nullcontext()))

    def test_get_optimization_stats_disabled(self):
        """Test optimization stats when optimization is disabled."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'):
            
            server = OptimizedMCPServer(enable_optimization=False)
            
            stats = server.get_optimization_stats()
            
            assert stats == {"optimization_enabled": False}

    def test_get_optimization_stats_enabled_with_components(self):
        """Test optimization stats when optimization is enabled with all components."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector') as mock_get_telemetry:
            
            mock_interceptor = Mock()
            mock_interceptor.get_optimization_report.return_value = {"interceptor_stat": "value1"}
            mock_get_interceptor.return_value = mock_interceptor
            
            mock_telemetry = Mock()
            mock_telemetry.get_performance_metrics.return_value = {"telemetry_stat": "value2"}
            mock_get_telemetry.return_value = mock_telemetry
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            stats = server.get_optimization_stats()
            
            expected_stats = {
                "optimization_enabled": True,
                "interceptor_stat": "value1",
                "telemetry_stat": "value2",
            }
            assert stats == expected_stats

    def test_get_optimization_stats_enabled_no_interceptor(self):
        """Test optimization stats when interceptor is None."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector') as mock_get_telemetry:
            
            mock_get_interceptor.return_value = None
            
            mock_telemetry = Mock()
            mock_telemetry.get_performance_metrics.return_value = {"telemetry_stat": "value2"}
            mock_get_telemetry.return_value = mock_telemetry
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            stats = server.get_optimization_stats()
            
            expected_stats = {
                "optimization_enabled": True,
                "telemetry_stat": "value2",
            }
            assert stats == expected_stats

    def test_get_optimization_stats_enabled_no_telemetry(self):
        """Test optimization stats when telemetry is None."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector') as mock_get_telemetry:
            
            mock_interceptor = Mock()
            mock_interceptor.get_optimization_report.return_value = {"interceptor_stat": "value1"}
            mock_get_interceptor.return_value = mock_interceptor
            
            mock_get_telemetry.return_value = None
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            stats = server.get_optimization_stats()
            
            expected_stats = {
                "optimization_enabled": True,
                "interceptor_stat": "value1",
            }
            assert stats == expected_stats

    def test_run_server_success(self):
        """Test successful server run with default transport."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_server = Mock()
            mock_mcp_server = Mock()
            mock_mcp_server.run.return_value = "run_result"
            mock_server._tools = {}
            mock_create_server.return_value = mock_mcp_server
            
            server = OptimizedMCPServer(enable_optimization=False)
            server.mcp_server = mock_mcp_server
            
            result = server.run()
            
            mock_mcp_server.run.assert_called_once_with(transport="stdio")
            assert result == "run_result"

    def test_run_server_with_custom_transport(self):
        """Test server run with custom transport."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_mcp_server = Mock()
            mock_mcp_server.run.return_value = "run_result"
            mock_create_server.return_value = mock_mcp_server
            
            server = OptimizedMCPServer(enable_optimization=False)
            server.mcp_server = mock_mcp_server
            
            result = server.run(transport="http")
            
            mock_mcp_server.run.assert_called_once_with(transport="http")
            assert result == "run_result"

    def test_run_server_with_exception(self):
        """Test server run when underlying server raises exception."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_mcp_server = Mock()
            mock_mcp_server.run.side_effect = Exception("Server run failed")
            mock_create_server.return_value = mock_mcp_server
            
            server = OptimizedMCPServer(enable_optimization=False)
            server.mcp_server = mock_mcp_server
            
            with pytest.raises(Exception, match="Server run failed"):
                server.run()


class TestCreateOptimizedServer:
    """Test the create_optimized_server factory function."""

    def test_create_optimized_server_default(self):
        """Test creating optimized server with default parameters."""
        with patch('quilt_mcp.optimization.integration.OptimizedMCPServer') as mock_server_class:
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            result = create_optimized_server()
            
            mock_server_class.assert_called_once_with(enable_optimization=None)
            assert result == mock_server

    def test_create_optimized_server_explicit_enabled(self):
        """Test creating optimized server with explicit enabled parameter."""
        with patch('quilt_mcp.optimization.integration.OptimizedMCPServer') as mock_server_class:
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            result = create_optimized_server(enable_optimization=True)
            
            mock_server_class.assert_called_once_with(enable_optimization=True)
            assert result == mock_server

    def test_create_optimized_server_explicit_disabled(self):
        """Test creating optimized server with explicit disabled parameter."""
        with patch('quilt_mcp.optimization.integration.OptimizedMCPServer') as mock_server_class:
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            result = create_optimized_server(enable_optimization=False)
            
            mock_server_class.assert_called_once_with(enable_optimization=False)
            assert result == mock_server


class TestOptimizationTool:
    """Test the optimization_tool decorator."""

    def test_optimization_tool_disabled(self):
        """Test optimization tool decorator when optimization is disabled."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "false"}):
            
            @optimization_tool(user_intent="test", task_type="test_task")
            def test_function(x, y):
                return x + y
            
            result = test_function(1, 2)
            
            assert result == 3

    def test_optimization_tool_enabled(self):
        """Test optimization tool decorator when optimization is enabled."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor:
            
            mock_interceptor = Mock()
            mock_context_manager = Mock()
            mock_interceptor.optimization_context.return_value = mock_context_manager
            mock_get_interceptor.return_value = mock_interceptor
            
            @optimization_tool(
                user_intent="test intent",
                task_type="test_task",
                performance_target="speed"
            )
            def test_function(x, y):
                return x + y
            
            # Mock the context manager to call the function
            def context_manager_mock():
                return test_function.__wrapped__(1, 2)
            
            mock_context_manager.__enter__ = Mock(return_value=None)
            mock_context_manager.__exit__ = Mock(return_value=None)
            
            with patch.object(mock_interceptor, 'optimization_context') as mock_opt_context:
                mock_opt_context.return_value.__enter__ = Mock(return_value=None)
                mock_opt_context.return_value.__exit__ = Mock(return_value=None)
                
                result = test_function(1, 2)
                
                assert result == 3
                mock_get_interceptor.assert_called_once()
                mock_opt_context.assert_called_once()
                
                # Verify OptimizationContext was created with correct parameters
                call_args = mock_opt_context.call_args[0][0]
                assert call_args.user_intent == "test intent"
                assert call_args.task_type == "test_task"
                assert call_args.performance_target == "speed"

    def test_optimization_tool_with_exception(self):
        """Test optimization tool decorator when function raises exception."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor:
            
            mock_interceptor = Mock()
            mock_context_manager = Mock()
            mock_interceptor.optimization_context.return_value = mock_context_manager
            mock_get_interceptor.return_value = mock_interceptor
            
            @optimization_tool(user_intent="test", task_type="test_task")
            def test_function():
                raise ValueError("Test error")
            
            mock_context_manager.__enter__ = Mock(return_value=None)
            mock_context_manager.__exit__ = Mock(return_value=None)
            
            with patch.object(mock_interceptor, 'optimization_context') as mock_opt_context:
                mock_opt_context.return_value.__enter__ = Mock(return_value=None)
                mock_opt_context.return_value.__exit__ = Mock(return_value=None)
                
                with pytest.raises(ValueError, match="Test error"):
                    test_function()

    def test_optimization_tool_interceptor_failure(self):
        """Test optimization tool decorator when interceptor creation fails."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor:
            
            mock_get_interceptor.side_effect = Exception("Interceptor failed")
            
            @optimization_tool(user_intent="test", task_type="test_task")
            def test_function(x, y):
                return x + y
            
            # Should raise the interceptor exception
            with pytest.raises(Exception, match="Interceptor failed"):
                test_function(1, 2)

    def test_optimization_tool_default_parameters(self):
        """Test optimization tool decorator with default parameters."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "true"}), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor:
            
            mock_interceptor = Mock()
            mock_context_manager = Mock()
            mock_interceptor.optimization_context.return_value = mock_context_manager
            mock_get_interceptor.return_value = mock_interceptor
            
            @optimization_tool()  # No parameters
            def test_function(x, y):
                return x + y
            
            mock_context_manager.__enter__ = Mock(return_value=None)
            mock_context_manager.__exit__ = Mock(return_value=None)
            
            with patch.object(mock_interceptor, 'optimization_context') as mock_opt_context:
                mock_opt_context.return_value.__enter__ = Mock(return_value=None)
                mock_opt_context.return_value.__exit__ = Mock(return_value=None)
                
                result = test_function(1, 2)
                
                assert result == 3
                
                # Verify OptimizationContext was created with default parameters
                call_args = mock_opt_context.call_args[0][0]
                assert call_args.user_intent is None
                assert call_args.task_type is None
                assert call_args.performance_target == "efficiency"


class TestRunOptimizedServer:
    """Test the run_optimized_server function."""

    def test_run_optimized_server_success_default_transport(self):
        """Test successful server run with default transport."""
        with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server, \
             patch.dict(os.environ, {}, clear=True):
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            
            run_optimized_server()
            
            mock_create_server.assert_called_once()
            mock_server.run.assert_called_once_with(transport="stdio")

    def test_run_optimized_server_success_env_transport(self):
        """Test successful server run with transport from environment."""
        with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server, \
             patch.dict(os.environ, {"FASTMCP_TRANSPORT": "http"}):
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            
            run_optimized_server()
            
            mock_create_server.assert_called_once()
            mock_server.run.assert_called_once_with(transport="http")

    def test_run_optimized_server_invalid_transport(self):
        """Test server run with invalid transport falls back to stdio."""
        with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server, \
             patch.dict(os.environ, {"FASTMCP_TRANSPORT": "invalid_transport"}):
            
            mock_server = Mock()
            mock_create_server.return_value = mock_server
            
            run_optimized_server()
            
            mock_create_server.assert_called_once()
            mock_server.run.assert_called_once_with(transport="stdio")

    def test_run_optimized_server_all_valid_transports(self):
        """Test server run with all valid transport types."""
        valid_transports = ["stdio", "http", "sse", "streamable-http"]
        
        for transport in valid_transports:
            with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server, \
                 patch.dict(os.environ, {"FASTMCP_TRANSPORT": transport}):
                
                mock_server = Mock()
                mock_create_server.return_value = mock_server
                
                run_optimized_server()
                
                mock_create_server.assert_called_once()
                mock_server.run.assert_called_once_with(transport=transport)

    def test_run_optimized_server_creation_failure(self):
        """Test server run when server creation fails."""
        with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server:
            
            mock_create_server.side_effect = Exception("Server creation failed")
            
            with pytest.raises(Exception, match="Server creation failed"):
                run_optimized_server()

    def test_run_optimized_server_run_failure(self):
        """Test server run when server run fails."""
        with patch('quilt_mcp.optimization.integration.create_optimized_server') as mock_create_server:
            
            mock_server = Mock()
            mock_server.run.side_effect = Exception("Server run failed")
            mock_create_server.return_value = mock_server
            
            with pytest.raises(Exception, match="Server run failed"):
                run_optimized_server()


class TestPatchUtilsForOptimization:
    """Test the patch_utils_for_optimization function."""

    def test_patch_utils_success(self):
        """Test successful patching of utils module."""
        with patch('quilt_mcp.utils') as mock_utils:
            
            patch_utils_for_optimization()
            
            # Verify the utils.run_server was replaced
            assert mock_utils.run_server == run_optimized_server

    def test_patch_utils_import_failure(self):
        """Test patch utils when import fails."""
        with patch('quilt_mcp.optimization.integration.logger') as mock_logger:
            
            # Mock the import to fail
            with patch('builtins.__import__', side_effect=ImportError("Import failed")):
                
                patch_utils_for_optimization()
                
                # Should log warning but not raise exception
                mock_logger.warning.assert_called_once()
                assert "Failed to patch utils module" in mock_logger.warning.call_args[0][0]

    def test_patch_utils_attribute_error(self):
        """Test patch utils when setting run_server attribute fails."""
        with patch('quilt_mcp.optimization.integration.logger') as mock_logger:
            
            # Create a mock utils module that raises AttributeError when setting run_server
            mock_utils = Mock()
            type(mock_utils).run_server = PropertyMock(side_effect=AttributeError("can't set attribute"))
            
            with patch('quilt_mcp.utils', mock_utils):
                patch_utils_for_optimization()
                
                # Should log warning but not raise exception
                mock_logger.warning.assert_called_once()
                assert "Failed to patch utils module" in mock_logger.warning.call_args[0][0]


class TestAutoPatching:
    """Test the automatic patching behavior based on environment variables."""

    def test_auto_patch_enabled_by_default(self):
        """Test that auto-patching is enabled by default."""
        # This test is tricky because the auto-patch code runs at module import time
        # We can't really test it directly, but we can verify the logic
        with patch.dict(os.environ, {}, clear=True):
            # Default should be "true"
            assert os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "true"

    def test_auto_patch_disabled_by_env(self):
        """Test that auto-patching can be disabled by environment variable."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": "false"}):
            assert os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "false"

    def test_auto_patch_various_env_values(self):
        """Test auto-patching with various environment variable values."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("True", True),
            ("1", False),  # Only "true" should enable
            ("false", False),
            ("FALSE", False),
            ("False", False),
            ("0", False),
            ("", False),
            ("random", False),
        ]
        
        for env_value, expected_enabled in test_cases:
            with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": env_value}):
                actual_enabled = os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "true"
                assert actual_enabled == expected_enabled, f"Failed for env_value='{env_value}'"


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""

    def test_optimization_context_with_none_values(self):
        """Test OptimizationContext creation with None values."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'), \
             patch('quilt_mcp.optimization.integration.optimization_context') as mock_optimization_context:
            
            mock_interceptor = Mock()
            mock_get_interceptor.return_value = mock_interceptor
            mock_context_manager = Mock()
            mock_optimization_context.return_value = mock_context_manager
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Test with None values
            result = server.run_with_optimization_context(
                user_intent=None,
                task_type=None,
                performance_target="efficiency"
            )
            
            assert result == mock_context_manager
            
            # Verify OptimizationContext was created with None values
            call_args = mock_optimization_context.call_args[0][0]
            assert call_args.user_intent is None
            assert call_args.task_type is None
            assert call_args.performance_target == "efficiency"
            assert call_args.cache_enabled is True

    def test_empty_string_environment_variables(self):
        """Test behavior with empty string environment variables."""
        with patch.dict(os.environ, {"MCP_OPTIMIZATION_ENABLED": ""}), \
             patch('quilt_mcp.optimization.integration.create_configured_server'):
            
            server = OptimizedMCPServer()
            
            # Empty string should be falsy
            assert server.optimization_enabled is False

    def test_server_with_none_mcp_server(self):
        """Test server behavior when create_configured_server returns None."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server:
            
            mock_create_server.return_value = None
            
            server = OptimizedMCPServer(enable_optimization=False)
            
            assert server.mcp_server is None
            
            # Should handle None gracefully in run method
            with pytest.raises(AttributeError):
                server.run()

    def test_large_number_of_tools(self):
        """Test optimization wrapper application with large number of tools."""
        with patch('quilt_mcp.optimization.integration.create_configured_server') as mock_create_server, \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            # Create a large number of mock tools
            large_tool_count = 1000
            mock_tools = {f"tool_{i}": Mock() for i in range(large_tool_count)}
            
            mock_server = Mock()
            mock_server._tools = mock_tools
            mock_create_server.return_value = mock_server
            
            mock_interceptor = Mock()
            mock_interceptor.intercept_tool_call.side_effect = [Mock() for _ in range(large_tool_count)]
            mock_get_interceptor.return_value = mock_interceptor
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Should handle large number of tools without issues
            assert mock_interceptor.intercept_tool_call.call_count == large_tool_count

    def test_unicode_and_special_characters_in_context(self):
        """Test optimization context with unicode and special characters."""
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor') as mock_get_interceptor, \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'), \
             patch('quilt_mcp.optimization.integration.optimization_context') as mock_optimization_context:
            
            mock_interceptor = Mock()
            mock_get_interceptor.return_value = mock_interceptor
            mock_context_manager = Mock()
            mock_optimization_context.return_value = mock_context_manager
            
            server = OptimizedMCPServer(enable_optimization=True)
            
            # Test with unicode and special characters
            unicode_intent = "测试意图 with émojis 🚀 and symbols @#$%"
            special_task = "task/with\\special:characters|and<more>"
            
            server.run_with_optimization_context(
                user_intent=unicode_intent,
                task_type=special_task,
                performance_target="accuracy"
            )
            
            # Verify OptimizationContext was created with special characters
            call_args = mock_optimization_context.call_args[0][0]
            assert call_args.user_intent == unicode_intent
            assert call_args.task_type == special_task
            assert call_args.performance_target == "accuracy"