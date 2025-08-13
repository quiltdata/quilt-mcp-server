"""Core exception types for MCP processing."""

from typing import Any, Optional


class MCPError(Exception):
    """Base exception for MCP-related errors."""
    
    def __init__(self, message: str, code: int = -32603, data: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code  # JSON-RPC error codes
        self.data = data
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC error format."""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            error_dict["data"] = self.data
        return error_dict


class ValidationError(MCPError):
    """Error in request validation."""
    
    def __init__(self, message: str, data: Optional[Any] = None):
        super().__init__(message, code=-32602, data=data)  # Invalid params


class ToolError(MCPError):
    """Error during tool execution."""
    
    def __init__(self, tool_name: str, message: str, data: Optional[Any] = None):
        super().__init__(f"Tool '{tool_name}': {message}", code=-32603, data=data)
        self.tool_name = tool_name


class ToolNotFoundError(MCPError):
    """Requested tool does not exist."""
    
    def __init__(self, tool_name: str):
        super().__init__(f"Tool not found: {tool_name}", code=-32601)  # Method not found
        self.tool_name = tool_name