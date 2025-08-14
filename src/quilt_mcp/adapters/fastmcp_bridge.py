"""FastMCP bridge adapter for local development.

This adapter bridges the core MCP processor with FastMCP's transport layer
for local development and testing. It registers tools with FastMCP while
using the same core logic as the Lambda deployment.
"""

import logging
from typing import Any, Dict, List, Literal

from mcp.server.fastmcp import FastMCP

from ..core import MCPProcessor

logger = logging.getLogger(__name__)


class FastMCPBridge:
    """Bridge between core MCP processor and FastMCP transport."""
    
    def __init__(self, name: str = "quilt"):
        self.fastmcp = FastMCP(name)
        self.processor = MCPProcessor()
        self._registered = False
    
    def initialize(self) -> None:
        """Initialize the bridge and register tools with FastMCP."""
        if self._registered:
            return
            
        logger.info("Initializing FastMCP bridge")
        
        # Initialize core processor (this registers all tools)
        self.processor.initialize()
        
        # Register tools with FastMCP
        self._register_tools_with_fastmcp()
        
        # Register health endpoint
        self._register_health_endpoint()
        
        self._registered = True
        logger.info("FastMCP bridge initialized successfully")
    
    def _register_tools_with_fastmcp(self) -> None:
        """Register all core tools with FastMCP using decorators."""
        tool_registry = self.processor.tool_registry
        
        # Get all registered tools
        tools = tool_registry.list_tools()
        logger.info(f"Registering {len(tools)} tools with FastMCP")
        
        for tool_def in tools:
            self._create_fastmcp_tool(tool_def)
    
    def _create_fastmcp_tool(self, tool_def: Dict[str, Any]) -> None:
        """Create a FastMCP tool wrapper for a core tool.
        
        Args:
            tool_def: Tool definition from core registry
        """
        tool_name = tool_def["name"]
        tool_description = tool_def["description"]
        
        # Create a wrapper function that calls the core tool
        def tool_wrapper(**kwargs) -> str:
            try:
                # Call the core tool through the registry
                result = self.processor.tool_registry.call_tool(tool_name, kwargs)
                
                # Format result as string for FastMCP
                if isinstance(result, dict):
                    import json
                    return json.dumps(result, indent=2)
                elif isinstance(result, str):
                    return result
                else:
                    return str(result)
                    
            except Exception as e:
                logger.error(f"Error calling tool {tool_name}: {e}")
                return f"Error: {str(e)}"
        
        # Set function metadata
        tool_wrapper.__name__ = tool_name
        tool_wrapper.__doc__ = tool_description
        
        # Register with FastMCP using decorator
        decorated_tool = self.fastmcp.tool()(tool_wrapper)
        
        logger.debug(f"Registered FastMCP tool: {tool_name}")
    
    def _register_health_endpoint(self) -> None:
        """Register a health check endpoint for load balancers."""
        @self.fastmcp.tool()
        def health_check() -> str:
            """Health check endpoint for load balancers and monitoring."""
            return "OK"
        
        logger.debug("Registered health check endpoint")
    
    def run(
        self,
        transport: Literal["stdio", "sse", "streamable-http"] = "streamable-http",
        host: str = "127.0.0.1",
        port: int = 8000,
        path: str = "/mcp"
    ) -> None:
        """Run the FastMCP server.
        
        Args:
            transport: Transport protocol to use
            host: Host to bind to (for HTTP transports)
            port: Port to bind to (for HTTP transports)  
            path: Path for HTTP endpoint (for HTTP transports)
        """
        self.initialize()
        
        logger.info(f"Starting FastMCP server with transport: {transport}")
        
        if transport == "stdio":
            self.fastmcp.run(transport=transport)
        elif transport in ["sse", "streamable-http"]:
            # For HTTP transports, FastMCP uses different parameter names
            self.fastmcp.run(transport=transport)
        else:
            raise ValueError(f"Unsupported transport: {transport}")
    
    async def run_async(
        self,
        transport: Literal["stdio", "sse", "streamable-http"] = "streamable-http",
        host: str = "127.0.0.1", 
        port: int = 8000,
        path: str = "/mcp"
    ) -> None:
        """Run the FastMCP server asynchronously.
        
        Args:
            transport: Transport protocol to use
            host: Host to bind to (for HTTP transports)
            port: Port to bind to (for HTTP transports)
            path: Path for HTTP endpoint (for HTTP transports)
        """
        self.initialize()
        
        logger.info(f"Starting FastMCP server async with transport: {transport}")
        
        if transport == "stdio":
            await self.fastmcp.run_async(transport=transport)
        elif transport in ["sse", "streamable-http"]:
            # For HTTP transports, FastMCP uses different parameter names
            await self.fastmcp.run_async(transport=transport)
        else:
            raise ValueError(f"Unsupported transport: {transport}")
    
    def get_fastmcp_instance(self) -> FastMCP:
        """Get the underlying FastMCP instance.
        
        Returns:
            FastMCP instance
        """
        self.initialize()
        return self.fastmcp