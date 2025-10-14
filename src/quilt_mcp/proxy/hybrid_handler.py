"""
Hybrid tool handler that routes calls to native or remote MCPs based on namespace.

This is the integration layer between:
- Native Quilt tools (existing implementation)
- Remote MCP servers via mcp-use (Benchling, BioContextAI)
"""

from __future__ import annotations

import logging
from typing import Any

from .mcp_use_proxy import get_mcp_use_proxy

logger = logging.getLogger(__name__)


class HybridToolHandler:
    """
    Handles tool calls by routing to either native or remote implementations.
    
    Routing logic:
    - Tools with "__" namespace (e.g., "benchling__get_entries") → remote
    - Tools without namespace → native Quilt tools
    """
    
    def __init__(self):
        self.proxy = get_mcp_use_proxy()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the hybrid handler (and remote proxy if needed)."""
        if not self._initialized:
            logger.info("🚀 Initializing Hybrid Tool Handler")
            await self.proxy.initialize()
            self._initialized = True
    
    def is_remote_tool(self, tool_name: str) -> bool:
        """Check if a tool name indicates a remote MCP tool."""
        return "__" in tool_name
    
    async def list_all_tools(self, native_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Aggregate tools from both native and remote sources.
        
        Args:
            native_tools: List of native Quilt tools (from existing implementation)
            
        Returns:
            Combined list of all available tools
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"📋 Listing tools: {len(native_tools)} native tools")
        
        # Get remote tools
        remote_tools = await self.proxy.list_remote_tools()
        logger.info(f"📋 Listing tools: {len(remote_tools)} remote tools")
        
        # Combine
        all_tools = native_tools + remote_tools
        logger.info(f"✅ Total tools available: {len(all_tools)}")
        
        return all_tools
    
    async def call_tool(
        self, 
        tool_name: str, 
        arguments: dict[str, Any],
        native_handler: callable | None = None
    ) -> Any:
        """
        Route tool call to appropriate handler (native or remote).
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            native_handler: Function to call for native tools (if None, raises error)
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool routing fails
        """
        if not self._initialized:
            await self.initialize()
        
        # Check if remote tool
        if self.is_remote_tool(tool_name):
            logger.info(f"🌐 Routing {tool_name} to remote MCP")
            return await self.proxy.call_remote_tool(tool_name, arguments)
        else:
            logger.info(f"🏠 Routing {tool_name} to native handler")
            if native_handler is None:
                raise ValueError(f"No native handler provided for tool: {tool_name}")
            return await native_handler(tool_name, arguments)
    
    async def close(self):
        """Clean up resources."""
        await self.proxy.close()
        self._initialized = False


# Global instance
_handler_instance: HybridToolHandler | None = None


def get_hybrid_handler() -> HybridToolHandler:
    """Get or create the global hybrid handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = HybridToolHandler()
    return _handler_instance

