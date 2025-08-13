"""Core MCP request processor - transport agnostic."""

import logging
from typing import Any, Dict, Optional
import json

from .tool_registry import ToolRegistry  
from .exceptions import MCPError, ValidationError

logger = logging.getLogger(__name__)


class MCPProcessor:
    """Core MCP request processor that works across all transports."""
    
    def __init__(self):
        self.tool_registry = ToolRegistry()
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize the processor and register tools."""
        if self._initialized:
            return
            
        logger.info("Initializing MCP processor")
        self._register_all_tools()
        self._initialized = True
        
    def _register_all_tools(self) -> None:
        """Register all available tools."""
        try:
            # Import and register tools from each module
            from ..tools import auth, packages, buckets, package_ops
            
            modules_to_register = [
                ("auth_", auth),
                ("packages_", packages), 
                ("buckets_", buckets),
                ("package_ops_", package_ops)
            ]
            
            total_registered = 0
            for prefix, module in modules_to_register:
                count = self.tool_registry.register_from_module(module, prefix="")
                total_registered += count
                logger.debug(f"Registered {count} tools from {module.__name__}")
                
            logger.info(f"Successfully registered {total_registered} tools")
            
        except Exception as e:
            logger.error(f"Failed to register tools: {e}", exc_info=True)
            raise
    
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an MCP request and return response.
        
        Args:
            request: MCP JSON-RPC request
            
        Returns:
            MCP JSON-RPC response
        """
        # Ensure processor is initialized
        self.initialize()
        
        try:
            # Validate basic JSON-RPC structure
            if not isinstance(request, dict):
                raise ValidationError("Request must be a JSON object")
                
            jsonrpc = request.get("jsonrpc")
            if jsonrpc != "2.0":
                raise ValidationError("Invalid jsonrpc version, must be '2.0'")
                
            method = request.get("method")
            if not method:
                raise ValidationError("Missing 'method' field")
                
            request_id = request.get("id")  # Can be None for notifications
            params = request.get("params", {})
            
            # Route to appropriate handler
            result = self._handle_method(method, params)
            
            # Build successful response
            response = {
                "jsonrpc": "2.0",
                "result": result
            }
            
            # Include ID if present (not for notifications)
            if request_id is not None:
                response["id"] = request_id
                
            return response
            
        except MCPError as e:
            return self._error_response(request.get("id"), e)
        except Exception as e:
            logger.error(f"Unexpected error processing request: {e}", exc_info=True)
            mcp_error = MCPError(f"Internal error: {str(e)}")
            return self._error_response(request.get("id"), mcp_error)
    
    def _handle_method(self, method: str, params: Dict[str, Any]) -> Any:
        """Handle a specific MCP method.
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            Method result
        """
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "tools/list":
            return self._handle_tools_list()
        elif method == "tools/call":
            return self._handle_tools_call(params)
        elif method == "resources/list":
            return self._handle_resources_list()
        elif method.startswith("notifications/"):
            # Handle notifications (no response expected)
            return None
        else:
            raise ValidationError(f"Unknown method: {method}")
    
    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "unknown")
        
        logger.info(f"MCP client connected: {client_info.get('name', 'unknown')} v{client_info.get('version', 'unknown')} (protocol: {protocol_version})")
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": "quilt-mcp-server",
                "version": "0.1.0"
            }
        }
    
    def _handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = self.tool_registry.list_tools()
        return {"tools": tools}
    
    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        if not isinstance(params, dict):
            raise ValidationError("tools/call params must be an object")
            
        tool_name = params.get("name")
        if not tool_name:
            raise ValidationError("Missing 'name' in tools/call")
            
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValidationError("arguments must be an object")
        
        # Call the tool
        result = self.tool_registry.call_tool(tool_name, arguments)
        
        # Format result for MCP
        if isinstance(result, dict) and "status" in result:
            # Already formatted result
            content = [{"type": "text", "text": json.dumps(result, indent=2)}]
        elif isinstance(result, str):
            content = [{"type": "text", "text": result}] 
        else:
            content = [{"type": "text", "text": json.dumps(result, indent=2)}]
            
        return {
            "content": content,
            "isError": False
        }
    
    def _handle_resources_list(self) -> Dict[str, Any]:
        """Handle resources/list request."""
        # For now, return empty resources list
        return {"resources": []}
    
    def _error_response(self, request_id: Optional[Any], error: MCPError) -> Dict[str, Any]:
        """Create an error response."""
        response = {
            "jsonrpc": "2.0", 
            "error": error.to_dict()
        }
        
        if request_id is not None:
            response["id"] = request_id
            
        return response