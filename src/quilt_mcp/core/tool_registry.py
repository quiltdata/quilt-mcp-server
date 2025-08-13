"""Tool registry for managing MCP tools in a transport-agnostic way."""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from .exceptions import ToolError, ToolNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any]  # JSON Schema for parameters
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """Convert to MCP tools/list format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object", 
                "properties": self.parameters,
                "required": list(self.parameters.keys()) if self.parameters else []
            }
        }


class ToolRegistry:
    """Registry for managing MCP tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        
    def register_tool(
        self, 
        name: str, 
        function: Callable, 
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a tool function.
        
        Args:
            name: Tool name
            function: Python function to call
            description: Tool description for MCP clients
            parameters: JSON Schema for tool parameters
        """
        if not description:
            description = function.__doc__ or f"Execute {name}"
        
        if parameters is None:
            parameters = self._extract_parameters_from_function(function)
        
        tool_def = ToolDefinition(
            name=name,
            description=description, 
            function=function,
            parameters=parameters
        )
        
        self._tools[name] = tool_def
        logger.debug(f"Registered tool: {name}")
    
    def _extract_parameters_from_function(self, function: Callable) -> Dict[str, Any]:
        """Extract parameter schema from function signature."""
        sig = inspect.signature(function)
        parameters = {}
        
        for param_name, param in sig.parameters.items():
            param_schema = {"type": "string"}  # Default to string
            
            # Try to infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_schema["type"] = "integer"
                elif param.annotation == float:
                    param_schema["type"] = "number" 
                elif param.annotation == bool:
                    param_schema["type"] = "boolean"
                elif param.annotation == list:
                    param_schema["type"] = "array"
                elif param.annotation == dict:
                    param_schema["type"] = "object"
            
            # Handle default values
            if param.default != inspect.Parameter.empty:
                if param.default is not None:
                    param_schema["default"] = param.default
                    
            parameters[param_name] = param_schema
            
        return parameters
    
    def get_tool(self, name: str) -> ToolDefinition:
        """Get a tool by name."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools in MCP format."""
        return [tool.to_mcp_format() for tool in self._tools.values()]
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with given arguments."""
        tool = self.get_tool(name)
        
        try:
            # Call the tool function with unpacked arguments
            result = tool.function(**arguments)
            return result
        except TypeError as e:
            raise ToolError(name, f"Invalid arguments: {e}")
        except Exception as e:
            raise ToolError(name, f"Execution failed: {e}")
    
    def register_from_module(self, module: Any, prefix: str = "") -> int:
        """Register all functions from a module that have tool metadata.
        
        Args:
            module: Python module containing tool functions
            prefix: Optional prefix for tool names
            
        Returns:
            Number of tools registered
        """
        registered = 0
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # Skip private attributes and non-functions
            if attr_name.startswith('_') or not callable(attr):
                continue
            
            # Register the function as a tool
            tool_name = f"{prefix}{attr_name}" if prefix else attr_name
            self.register_tool(tool_name, attr)
            registered += 1
            
        return registered