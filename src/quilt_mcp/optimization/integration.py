"""
Integration Module for MCP Optimization System

This module integrates the optimization system with the existing MCP server,
providing seamless telemetry collection and performance monitoring.
"""

import os
import functools
from typing import Dict, Any, Callable, Optional
import logging

from ..utils import create_configured_server
from .interceptor import get_tool_interceptor, optimization_context, OptimizationContext
from ..telemetry.collector import (
    get_telemetry_collector,
    TelemetryConfig,
    configure_telemetry,
)

logger = logging.getLogger(__name__)


class OptimizedMCPServer:
    """MCP Server with integrated optimization capabilities."""

    def __init__(self, enable_optimization: bool = None):
        # Determine if optimization should be enabled
        if enable_optimization is None:
            enable_optimization = os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "true"

        self.optimization_enabled = enable_optimization

        # Configure telemetry if optimization is enabled
        if self.optimization_enabled:
            telemetry_config = TelemetryConfig.from_env()
            configure_telemetry(telemetry_config)

            logger.info("MCP optimization system enabled")
        else:
            logger.info("MCP optimization system disabled")

        # Create the base MCP server
        self.mcp_server = create_configured_server(verbose=False)

        # Get optimization components
        self.interceptor = get_tool_interceptor() if self.optimization_enabled else None
        self.telemetry = get_telemetry_collector() if self.optimization_enabled else None

        # Apply optimization wrappers if enabled
        if self.optimization_enabled:
            self._apply_optimization_wrappers()

    def _apply_optimization_wrappers(self):
        """Apply optimization wrappers to existing MCP tools."""
        if not self.optimization_enabled or not self.interceptor:
            return

        # Get all registered tools from the MCP server
        tools = getattr(self.mcp_server, "_tools", {})

        for tool_name, tool_func in tools.items():
            # Wrap each tool with the interceptor
            wrapped_func = self.interceptor.intercept_tool_call(tool_func)
            tools[tool_name] = wrapped_func

        logger.info(f"Applied optimization wrappers to {len(tools)} tools")

    def run_with_optimization_context(
        self,
        user_intent: Optional[str] = None,
        task_type: Optional[str] = None,
        performance_target: str = "efficiency",
    ):
        """Context manager for running MCP operations with optimization context."""
        if not self.optimization_enabled or not self.interceptor:
            # Return a no-op context manager
            from contextlib import nullcontext

            return nullcontext()

        context = OptimizationContext(
            user_intent=user_intent,
            task_type=task_type,
            performance_target=performance_target,
            cache_enabled=True,
        )

        return optimization_context(context)

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get current optimization statistics."""
        if not self.optimization_enabled:
            return {"optimization_enabled": False}

        stats = {"optimization_enabled": True}

        if self.interceptor:
            stats.update(self.interceptor.get_optimization_report())

        if self.telemetry:
            stats.update(self.telemetry.get_performance_metrics())

        return stats

    def run(self, transport="stdio"):
        """Run the optimized MCP server."""
        logger.info(f"Starting optimized MCP server with transport: {transport}")

        if self.optimization_enabled:
            logger.info("Optimization features active")

        return self.mcp_server.run(transport=transport)


def create_optimized_server(enable_optimization: bool = None) -> OptimizedMCPServer:
    """Create an optimized MCP server instance."""
    return OptimizedMCPServer(enable_optimization=enable_optimization)


def optimization_tool(
    user_intent: Optional[str] = None,
    task_type: Optional[str] = None,
    performance_target: str = "efficiency",
):
    """Decorator to add optimization context to individual tool functions."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if optimization is enabled
            optimization_enabled = os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "true"

            if not optimization_enabled:
                return func(*args, **kwargs)

            # Create optimization context
            context = OptimizationContext(
                user_intent=user_intent,
                task_type=task_type,
                performance_target=performance_target,
            )

            # Run with optimization context
            interceptor = get_tool_interceptor()
            with interceptor.optimization_context(context):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Integration with existing utils module
def run_optimized_server() -> None:
    """Run the MCP server with optimization capabilities."""
    try:
        # Create optimized server
        server = create_optimized_server()

        # Get transport from environment
        transport_str = os.environ.get("FASTMCP_TRANSPORT", "stdio")
        valid_transports = ["stdio", "http", "sse", "streamable-http"]

        if transport_str not in valid_transports:
            transport_str = "stdio"

        # Run the server
        server.run(transport=transport_str)

    except Exception as e:
        logger.error(f"Error starting optimized MCP server: {e}")
        raise


# Monkey patch the utils module to use optimized server by default
def patch_utils_for_optimization():
    """Patch the utils module to use the optimized server."""
    try:
        from .. import utils

        # Replace the run_server function with our optimized version
        utils.run_server = run_optimized_server

        logger.info("Patched utils module for optimization")

    except Exception as e:
        logger.warning(f"Failed to patch utils module: {e}")


# Auto-patch if optimization is enabled
if os.getenv("MCP_OPTIMIZATION_ENABLED", "true").lower() == "true":
    patch_utils_for_optimization()
