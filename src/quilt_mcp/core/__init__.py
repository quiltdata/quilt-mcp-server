"""Core MCP processing components.

This package contains transport-agnostic MCP request processing logic that works
consistently across all deployment environments (local, Docker, Lambda).

Components:
- processor: Main MCP request/response processing
- tool_registry: Tool registration and management
- exceptions: Core exception types
"""

from .processor import MCPProcessor
from .tool_registry import ToolRegistry
from .exceptions import MCPError, ToolError, ValidationError, ToolNotFoundError

__all__ = ["MCPProcessor", "ToolRegistry", "MCPError", "ToolError", "ValidationError", "ToolNotFoundError"]